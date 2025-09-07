#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd -P)"
BASE="$(cd "$SCRIPT_DIR/../.." && pwd -P)"
[ -f "$BASE/00_env.sh" ] && . "$BASE/00_env.sh" || true
. "$BASE/00_env_ext.sh"
LEVEL="${1:-low}"s
python3 "$BASE/modules/attacks/lpc_runner.py" "mavlink_cmdlong_tease" "${1:-low}"
