#!/usr/bin/env bash
# MTD: Change the container's primary IPv4 (add new, ARP announce, then drop old).
# 공격자가 고정 IP를 전제로 할 때 표적을 "이동"시킴.
set -euo pipefail
BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$BASE/00_env.sh"; . "$BASE/sh_core/lpc_bus.sh"; . "$BASE/sh_core/metrics.sh"

: "${CIDR:=24}"             # 프리픽스 길이
: "${NEW_LAST:=0}"          # 0이면 50~200 랜덤
: "${ANNOUNCE_MS:=600}"     # ARP 갱신 대기(ms)
: "${DROP_OLD:=1}"          # 구주소 삭제(1) / 보존(0)

rand_last(){ echo $((50 + RANDOM % 151)); }

main(){
  local before after; before=$(obs_snapshot "$DVD_C_GCS" "$DVD_TARGET_IF")

  if [ "$NEW_LAST" = "0" ]; then NEW_LAST="$(rand_last)"; fi
  CUR=$(docker exec "$DVD_C_GCS" bash -lc "ip -4 -o addr show dev $DVD_TARGET_IF | awk '{print \$4}' | head -n1" || true)
  [ -z "$CUR" ] && { log "[mtd_ip_shuffle] no current IP on $DVD_TARGET_IF"; exit 1; }
  BASE_NET=$(echo "$CUR" | awk -F. '{printf "%s.%s.%s", $1,$2,$3}')
  OLD_IP=$(echo "$CUR" | cut -d/ -f1)
  NEW_IP="${BASE_NET}.${NEW_LAST}"

  log "[mtd_ip_shuffle] ${OLD_IP}/${CIDR} -> ${NEW_IP}/${CIDR} (announce=${ANNOUNCE_MS}ms drop_old=$DROP_OLD)"
  bus_emit "mtd" "action=ip_shuffle if=$DVD_TARGET_IF old=$OLD_IP new=$NEW_IP/$CIDR target=$DVD_C_GCS"

  # 전환 구간: 아주 짧은 지연/손실 → ns-3 반영
  effect_emit "delay_ms=4 jitter_ms=1 loss_pct=1"

  if [ "${ALLOW_REAL_EFFECTS:-0}" -eq 1 ]; then
    docker exec "$DVD_C_GCS" bash -lc "
      ip addr add ${NEW_IP}/${CIDR} dev ${DVD_TARGET_IF} && \
      (command -v arping >/dev/null 2>&1 && arping -c 1 -U -I ${DVD_TARGET_IF} ${NEW_IP} >/dev/null 2>&1 || true)
    "
    # ARP 전파 대기
    sleep "$(awk "BEGIN{print ${ANNOUNCE_MS}/1000}")"
    if [ "$DROP_OLD" = "1" ]; then
      docker exec "$DVD_C_GCS" bash -lc "ip addr del ${OLD_IP}/${CIDR} dev ${DVD_TARGET_IF}" || true
      bus_emit "mtd" "action=ip_shuffle_cutover old=$OLD_IP new=$NEW_IP drop_old=1"
    fi
  fi

  # 정상화
  effect_emit "loss_pct=0"

  after=$(obs_snapshot "$DVD_C_GCS" "$DVD_TARGET_IF"); delta_emit "$before" "$after" "mtd_obs_ip_shuffle"
}
main "$@"
