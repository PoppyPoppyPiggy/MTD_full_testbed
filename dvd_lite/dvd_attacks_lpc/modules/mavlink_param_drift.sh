#!/usr/bin/env bash
# Slow param drift against FCU via MAVLink
set -euo pipefail
BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$BASE/00_env.sh"; . "$BASE/sh_core/lpc_bus.sh"; . "$BASE/sh_core/metrics.sh"

: "${PARAM_NAME:=ATC_RAT_RLL_FF}"
: "${INTENSITY:=low}"   # low|medium|high
: "${DUR:=1}"

case "$INTENSITY" in
  low) STEP=0.005 ;; medium) STEP=0.02 ;; high) STEP=0.05 ;;
esac

main(){
  log "[mavlink_param_drift] mode=$LPC_MODE param=$PARAM_NAME step=$STEP dur=$DUR"
  local before after; before=$(obs_snapshot "$DVD_C_GCS" "$DVD_TARGET_IF")
  if [ "${ALLOW_REAL_EFFECTS:-0}" -eq 1 ]; then
    python3 "$BASE/interface/mavlink_cmd.py" --host "$DVD_MAVLINK_HOST" --port "$DVD_MAVLINK_PORT" \
      set-param "$PARAM_NAME" "$STEP" || true
    bus_emit "mavlink" "action=param_set name=$PARAM_NAME step=$STEP target=${DVD_MAVLINK_HOST}:${DVD_MAVLINK_PORT}"
  else
    bus_emit "mavlink" "action=param_drift_sim name=$PARAM_NAME step=$STEP"
    effect_emit "mission_bias=+$STEP"
  fi
  sleep "$DUR"
  after=$(obs_snapshot "$DVD_C_GCS" "$DVD_TARGET_IF"); delta_emit "$before" "$after" "mavlink_obs"
}
main "$@"
