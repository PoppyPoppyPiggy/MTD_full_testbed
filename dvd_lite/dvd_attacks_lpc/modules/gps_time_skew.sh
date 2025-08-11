#!/usr/bin/env bash
set -euo pipefail
BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$BASE/sh_core/lpc_core.sh"; . "$BASE/primitives/gps_stub.sh"

# Attack Point: GPS 시간 스큐(시뮬 → 브릿지 반영)
nibble(){ gps_time_skew "${LPC_STEP:-0.05}"; }
main(){ log "[gps_time_skew]"; lpc_loop nibble; }
main "$@"
