#!/usr/bin/env bash
# Telemetry burst drop: short high-loss bursts on container link.
set -euo pipefail
BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$BASE/00_env.sh"; . "$BASE/sh_core/lpc_bus.sh"; . "$BASE/sh_core/netem.sh"; . "$BASE/sh_core/metrics.sh"

: "${INTENSITY:=medium}"   # low|medium|high
: "${BURST_MS:=800}"
: "${GAP_MS:=700}"
: "${REPEAT:=8}"

loss_rule(){
  case "$INTENSITY" in
    low) echo "loss 10% 20%";;
    medium) echo "loss 35% 25%";;
    high) echo "loss 75% 25%";;
  esac
}

main(){
  log "[telemetry_burst_drop] mode=$LPC_MODE int=$INTENSITY burst=${BURST_MS}ms gap=${GAP_MS}ms x${REPEAT} target=$DVD_C_GCS/$DVD_TARGET_IF"
  local before after; before=$(obs_snapshot "$DVD_C_GCS" "$DVD_TARGET_IF")
  for _ in $(seq 1 "$REPEAT"); do
    if [ "${ALLOW_REAL_EFFECTS:-0}" -eq 1 ]; then netem_apply "$DVD_C_GCS" $(loss_rule); fi
    bus_emit "telemetry" "action=burst_drop target=$DVD_C_GCS if=$DVD_TARGET_IF burst_ms=${BURST_MS} int=$INTENSITY"
    case "$INTENSITY" in low) LP=10;; medium) LP=35;; high) LP=75;; esac
    effect_emit "loss_pct=$LP"
    sleep "$(awk "BEGIN{print ${BURST_MS}/1000}")"
    netem_clear "$DVD_C_GCS" || true
    sleep "$(awk "BEGIN{print ${GAP_MS}/1000}")"
  done
  after=$(obs_snapshot "$DVD_C_GCS" "$DVD_TARGET_IF"); delta_emit "$before" "$after" "telemetry_obs"
}
main "$@"
