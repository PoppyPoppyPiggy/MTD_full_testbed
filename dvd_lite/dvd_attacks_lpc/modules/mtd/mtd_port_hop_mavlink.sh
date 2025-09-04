#!/usr/bin/env bash
# MTD: Expose MAVLink on a NEW UDP port. Prefer iptables REDIRECT; fallback to socat if iptables missing.
set -euo pipefail

BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$BASE/00_env.sh"
. "$BASE/sh_core/lpc_bus.sh"
. "$BASE/sh_core/metrics.sh"

: "${OLD_PORT:=14550}"       # 내부 서비스(리슨) 포트
: "${NEW_PORT:=0}"           # 0이면 15000~25000 랜덤
: "${GRACE:=5}"              # 병행 수용 시간(초)
: "${DROP_OLD:=1}"           # 컷오버 시 구포트 드롭
: "${CUTOVER_BLOCK_MS:=400}" # iptables 없을 때 전체 차단 모사 시간(ms)

rand_new() { echo $((15000 + RANDOM % 10000)); }

_have() { docker exec "$DVD_C_GCS" bash -lc "command -v $1 >/dev/null 2>&1"; }

ensure_rule() {
  local table="$1"; shift
  local rule="$*"
  docker exec "$DVD_C_GCS" bash -lc "
    iptables -t ${table} -C ${rule} 2>/dev/null || iptables -t ${table} -A ${rule}
  "
}

drop_rule() {
  local table="$1"; shift
  local rule="$*"
  docker exec "$DVD_C_GCS" bash -lc "
    iptables -t ${table} -C ${rule} 2>/dev/null && iptables -t ${table} -D ${rule}
  " >/dev/null 2>&1 || true
}

socat_start() {
  local newp="$1" oldp="$2"
  docker exec -d "$DVD_C_GCS" bash -lc "nohup socat -T0 -u UDP-RECVFROM:${newp},fork,reuseaddr UDP-SENDTO:127.0.0.1:${oldp} >/dev/null 2>&1 & echo \$! > /tmp/mtd_socat_${newp}.pid"
}

socat_stop() {
  local newp="$1"
  docker exec "$DVD_C_GCS" bash -lc "test -f /tmp/mtd_socat_${newp}.pid && kill \$(cat /tmp/mtd_socat_${newp}.pid) || true"
}

# netem 전체 차단(포트별 불가 → 짧게 전체 차단으로 모사)
if_netem_block() {
  local ms="$1"
  if [ -f "$BASE/sh_core/netem.sh" ]; then
    . "$BASE/sh_core/netem.sh"
    netem_apply "$DVD_C_GCS" loss 100% || true
    sleep "$(awk "BEGIN{print ${ms}/1000}")"
    netem_clear "$DVD_C_GCS" || true
  else
    sleep "$(awk "BEGIN{print ${ms}/1000}")"
  fi
}

main() {
  local before after
  before=$(obs_snapshot "$DVD_C_GCS" "$DVD_TARGET_IF")

  [ "$NEW_PORT" = "0" ] && NEW_PORT="$(rand_new)"

  log "[mtd_port_hop_mavlink] expose NEW=${NEW_PORT}/udp -> OLD=${OLD_PORT}/udp grace=${GRACE}s drop_old=${DROP_OLD}"
  bus_emit "mtd" "mode=${LPC_MODE:-SIM} actor=${LPC_ACTOR:-attacker} action=port_hop proto=udp old=${OLD_PORT} new=${NEW_PORT} grace=${GRACE}s target=${DVD_C_GCS}"
  effect_emit "delay_ms=5 jitter_ms=2 loss_pct=1"

  if [ "${ALLOW_REAL_EFFECTS:-0}" -eq 1 ]; then
    if _have iptables; then
      ensure_rule nat PREROUTING -p udp --dport "${NEW_PORT}" -j REDIRECT --to-ports "${OLD_PORT}"
    else
      # iptables 없음 → socat로 NEW 포트 리스닝 및 OLD로 포워딩
      docker exec -u 0 "$DVD_C_GCS" bash -lc 'command -v socat >/dev/null || (apt-get update && apt-get install -y socat)'
      socat_start "${NEW_PORT}" "${OLD_PORT}"
      bus_emit "mtd" "mode=${LPC_MODE:-SIM} actor=${LPC_ACTOR:-attacker} action=port_hop_socat new=${NEW_PORT} old=${OLD_PORT} target=${DVD_C_GCS}"
    fi
  fi

  # CTI 최신 포트로 업데이트(팔로우 공격/평가용)
  echo "MAVLINK_PORT=${NEW_PORT}" >> "$LPC_LOG_DIR/cti_targets.env"

  sleep "${GRACE}"

  if [ "${ALLOW_REAL_EFFECTS:-0}" -eq 1 ] && [ "${DROP_OLD}" = "1" ]; then
    if _have iptables; then
      ensure_rule filter INPUT -p udp --dport "${OLD_PORT}" -j DROP
    else
      if_netem_block "${CUTOVER_BLOCK_MS}"
      # socat 경로 사용 중이면 구포트 정리
      socat_stop "${OLD_PORT}" || true
    fi
    bus_emit "mtd" "mode=${LPC_MODE:-SIM} actor=${LPC_ACTOR:-attacker} action=port_hop_cutover old=${OLD_PORT} new=${NEW_PORT} drop_old=1"
    effect_emit "loss_pct=5"
  fi

  after=$(obs_snapshot "$DVD_C_GCS" "$DVD_TARGET_IF")
  delta_emit "$before" "$after" "mtd_obs_port_hop"
}

main "$@"