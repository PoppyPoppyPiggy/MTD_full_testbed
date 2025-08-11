#!/usr/bin/env bash
set -euo pipefail
BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$BASE/sh_core/lpc_core.sh"; . "$BASE/primitives/power_stub.sh"

# Attack Point: 경로/작업 가중치 미세 상승(시뮬)
nibble(){ power_bias "${LPC_STEP:-0.05}"; }
on_service_migration(){ apply_backoff; }
main(){ log "[battery_route_drain]"; lpc_loop nibble; }
main "$@"
