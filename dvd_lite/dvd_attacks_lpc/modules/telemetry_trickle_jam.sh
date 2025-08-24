#!/usr/bin/env bash
# Low-profile telemetry jamming: add small delay/jitter/loss cycles.
set -euo pipefail
BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$BASE/00_env.sh"; . "$BASE/sh_core/lpc_bus.sh"; . "$BASE/sh_core/netem.sh"; . "$BASE/sh_core/metrics.sh"

: "${INTENSITY:=low}"   # low|medium|high
: "${DUR:=12}"          # total seconds
: "${STEP:=2}"          # on/off step seconds

effects(){ case "$INTENSITY" in
  low)    echo "delay_ms=2 jitter_ms=1 loss_pct=0.05" ;;
  medium) echo "delay_ms=5 jitter_ms=2 loss_pct=0.20" ;;
  high)   echo "delay_ms=12 jitter_ms=5 loss_pct=0.80";;
esac; }

apply_real(){
  case "$INTENSITY" in
    low)    netem_apply "$DVD_C_GCS" delay 2ms 1ms loss 0.05% ;;
    medium) netem_apply "$DVD_C_GCS" delay 5ms 2ms loss 0.20% ;;
    high)   netem_apply "$DVD_C_GCS" delay 12ms 5ms loss 0.80% ;;
  esac
}

main(){
  log "[telemetry_trickle_jam] mode=$LPC_MODE int=$INTENSITY dur=$DUR step=$STEP target=$DVD_C_GCS/$DVD_TARGET_IF"
  local eff="$(effects)"; local t=0
  local before after; before=$(obs_snapshot "$DVD_C_GCS" "$DVD_TARGET_IF")
  while [ "$t" -lt "$DUR" ]; do
    if [ "${ALLOW_REAL_EFFECTS:-0}" -eq 1 ]; then apply_real; fi
    bus_emit "telemetry" "target=$DVD_C_GCS qdisc=netem $eff"
    effect_emit $eff
    sleep "$STEP"
    netem_clear "$DVD_C_GCS" || true
    sleep "$STEP"
    t=$((t + STEP*2))
  done
  after=$(obs_snapshot "$DVD_C_GCS" "$DVD_TARGET_IF"); delta_emit "$before" "$after" "telemetry_obs"
  netem_clear "$DVD_C_GCS" || true
}
main "$@"
