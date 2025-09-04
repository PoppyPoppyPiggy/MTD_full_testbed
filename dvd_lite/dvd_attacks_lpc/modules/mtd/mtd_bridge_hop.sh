#!/usr/bin/env bash
# MTD: Move container to another Docker bridge (NET_FROM -> NET_TO).
# 스니핑·고정 라우팅·정적 ACL을 우회. 전환 중 손실 100%를 타임라인에 남김.
set -euo pipefail
BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$BASE/00_env.sh"; . "$BASE/sh_core/lpc_bus.sh"; . "$BASE/sh_core/metrics.sh"

: "${NET_FROM:=dvd_net_a}"   # 기존 네트워크
: "${NET_TO:=dvd_net_b}"     # 이동 대상
: "${PREF_NEW:=1}"           # 새 링크 기본경로 선호
: "${CUT_OLD:=1}"            # 이동 완료 후 기존 네트워크 분리

main(){
  local before after; before=$(obs_snapshot "$DVD_C_GCS" "$DVD_TARGET_IF")
  log "[mtd_bridge_hop] $DVD_C_GCS: ${NET_FROM} -> ${NET_TO} (pref_new=$PREF_NEW cut_old=$CUT_OLD)"
  bus_emit "mtd" "action=bridge_hop container=$DVD_C_GCS from=$NET_FROM to=$NET_TO"

  # 전환 구간: 완전 손실 + 약간의 지터
  effect_emit "loss_pct=100"
  effect_emit "jitter_ms=3"

  if [ "${ALLOW_REAL_EFFECTS:-0}" -eq 1 ]; then
    docker network connect "$NET_TO" "$DVD_C_GCS" || true

    if [ "$PREF_NEW" = "1" ]; then
      # 새 veth를 기본 경로로 (eth1 가정, 없으면 현재 default IF 유지)
      docker exec "$DVD_C_GCS" bash -lc '
        NEW_IF=$(ip -o -4 addr show | awk "{print \$2}" | grep -E "^eth[0-9]+" | sort | tail -n1)
        [ -z "$NEW_IF" ] && NEW_IF="eth1"
        ip route del default 2>/dev/null || true
        ip route add default dev "$NEW_IF" metric 100 2>/dev/null || true
      ' || true
    fi

    if [ "$CUT_OLD" = "1" ]; then
      docker network disconnect "$NET_FROM" "$DVD_C_GCS" || true
    fi
  fi

  # 안정화 후 손실 해제
  effect_emit "loss_pct=0"

  after=$(obs_snapshot "$DVD_C_GCS" "$DVD_TARGET_IF"); delta_emit "$before" "$after" "mtd_obs_bridge_hop"
}
main "$@"
