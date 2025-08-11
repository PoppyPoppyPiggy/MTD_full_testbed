#!/usr/bin/env bash
set -euo pipefail
. "$(dirname "$0")/../sh_core/lpc_bus.sh"

mav_baseline(){ bus_emit "mavlink" "baseline gcs=$DVD_IP_GCS port=$DVD_MAVLINK_PORT"; }
mav_param_nudge(){ local step="${1:-0.02}"; bus_emit "mavlink" "param_drift+=${step}"; effect_emit mission_bias "+${step}"; }
mav_mode_tease(){ bus_emit "mavlink" "mode_tease"; effect_emit pilot_attention "+1tick"; }
mav_rebind(){ bus_emit "mavlink" "rebind"; }
