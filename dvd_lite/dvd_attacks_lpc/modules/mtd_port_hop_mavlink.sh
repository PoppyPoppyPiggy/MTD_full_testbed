#!/usr/bin/env bash
# MTD: Expose MAVLink on a NEW UDP port via NAT (NEW -> OLD), then optionally drop OLD.
# 예) 외부 20001/udp -> 내부 14550/udp, 그레이스 후 14550 드롭.
set -euo pipefail
BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$BASE/00_env.sh"; . "$BASE/sh_core/lpc_bus.sh"; . "$BASE/sh_core/metrics.sh"

: "${OLD_PORT:=14550}"      # 내부 서비스 포트(리슨 유지)
: "${NEW_PORT:=0}"          # 0이면 15000~25000 랜덤 외부 포트
: "${GRACE:=5}"             # 동시 수용 시간(초)
: "${DROP_OLD:=1}"          # 컷오버 시 OLD 포트 차단

rand_new(){ echo $((15000 + RANDOM % 10000)); }

ensure_rule(){
  local table="$1"; shift
  local rule="$*"
  docker exec "$DVD_C_GCS" bash -lc "
    iptables -t ${table} -C ${rule} 2>/dev/null || iptables -t ${table} -A ${rule}
  "
}

drop_rule(){
  local table="$1"; shift
  local rule="$*"
  docker exec "$DVD_C_GCS" bash -lc "
    iptables -t ${table} -C ${rule} 2>/dev/null && iptables -t ${table} -D ${rule}
  " >/dev/null 2>&1 || true
}

main(){
  local before after; before=$(obs_snapshot "$DVD_C_GCS" "$DVD_TARGET_IF")

  if [ "$NEW_PORT" = "0" ]; then NEW_PORT="$(rand_new)"; fi
  log "[mtd_port_hop_mavlink] expose NEW=${NEW_PORT}/udp -> OLD=${OLD_PORT}/udp grace=${GRACE}s drop_old=$DROP_OLD"
  bus_emit "mtd" "action=port_hop proto=udp old=$OLD_PORT new=$NEW_PORT grace=${GRACE}s target=$DVD_C_GCS"

  # 컷오버 구간: 짧은 지연/약손실
  effect_emit "delay_ms=5 jitter_ms=2 loss_pct=1"

  if [ "${ALLOW_REAL_EFFECTS:-0}" -eq 1 ]; then
    # NEW 포트로 온 트래픽을 내부 OLD로 REDIRECT
    ensure_rule nat PREROUTING -p udp --dport "$NEW_PORT" -j REDIRECT --to-ports "$OLD_PORT"
  fi

  sleep "$GRACE"

  if [ "${ALLOW_REAL_EFFECTS:-0}" -eq 1 ] && [ "$DROP_OLD" = "1" ]; then
    # OLD 포트 직접 접근 차단
    ensure_rule filter INPUT -p udp --dport "$OLD_PORT" -j DROP
    bus_emit "mtd" "action=port_hop_cutover new_open=$NEW_PORT old_drop=1"
    effect_emit "loss_pct=5"   # 컷오버 순간 약간의 손실 가정
  fi

  # NEW 안내(라벨링용 메타)
  bus_emit "mtd" "endpoint_update proto=udp listen_old=$OLD_PORT publish_new=$NEW_PORT"
  after=$(obs_snapshot "$DVD_C_GCS" "$DVD_TARGET_IF"); delta_emit "$before" "$after" "mtd_obs_port_hop"
}
main "$@"
