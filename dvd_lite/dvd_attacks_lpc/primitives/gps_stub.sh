#!/usr/bin/env bash
set -euo pipefail
. "$(dirname "$0")/../sh_core/lpc_bus.sh"

gps_offset_drift(){ local m="${1:-0.3}"; bus_emit "gps" "offset+=${m}m"; effect_emit position_drift "+${m}m"; }
gps_time_skew(){ local s="${1:-0.05}"; bus_emit "gps" "time_skew+=${s}s"; effect_emit time_bias "+${s}s"; }
