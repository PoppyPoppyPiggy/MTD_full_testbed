#!/usr/bin/env bash
# Wi-Fi deauth (safe emulation via netem loss bursts on container link)
set -euo pipefail
BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$BASE/00_env.sh"; . "$BASE/sh_core/lpc_bus.sh"; . "$BASE/sh_core/netem.sh"; . "$BASE/sh_core/metrics.sh"

: "${INTENSITY:=medium}"   # low|medium|high
: "${BURST_MS:=1500}"
: "${REPEAT:=3}"

apply_real(){
  case "$INTENSITY" in
    low)    netem_apply "$DVD_C_GCS" loss 15% 25% ;;
    medium) netem_apply "$DVD_C_GCS" loss 45% 25% ;;
    high)   netem_apply "$DVD_C_GCS" loss 100%    ;;
  esac
}
loss_val(){ case "$INTENSITY" in low) echo 15; medium) echo 45; high) echo 100; esac; }

main(){
  log "[wifi_deauth_attack] mode=$LPC_MODE int=$INTENSITY burst=${BURST_MS}ms x$REPEAT target=$DVD_C_GCS/$DVD_TARGET_IF"
  local before after; before=$(obs_snapshot "$DVD_C_GCS" "$DVD_TARGET_IF")
  for _ in $(seq 1 "$REPEAT"); do
    if [ "${ALLOW_REAL_EFFECTS:-0}" -eq 1 ]; then apply_real; fi
    bus_emit "wifi" "action=deauth_burst target=$DVD_C_GCS if=$DVD_TARGET_IF burst_ms=$BURST_MS int=$INTENSITY"
    effect_emit "loss_pct=$(loss_val)"
    sleep "$(awk "BEGIN{print $BURST_MS/1000}")"
    netem_clear "$DVD_C_GCS" || true
    sleep 1
  done
  after=$(obs_snapshot "$DVD_C_GCS" "$DVD_TARGET_IF"); delta_emit "$before" "$after" "wifi_obs"
}
main "$@"
