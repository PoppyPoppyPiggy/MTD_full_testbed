#!/usr/bin/env bash

# --- Process Command Line Arguments ---
# Example: Assign first arg to INTENSITY, default 'medium'
# INTENSITY="${1:-medium}"
# Example: Assign second arg to DURATION_SECONDS, default '30'
# DURATION_SECONDS="${2:-30}"
# echo "Parameters: Intensity=$INTENSITY, Duration=$DURATION_SECONDS"
# Add more parameter processing as needed for the specific script
# ------------------------------------

set -euo pipefail
BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
[ -f "$BASE/00_env.sh" ] && . "$BASE/00_env.sh" || true
. "$BASE/00_env_ext.sh"
python3 "$BASE/modules/attacks/lpc_runner.py" "gps_slow_spoof" "${1:-low}"