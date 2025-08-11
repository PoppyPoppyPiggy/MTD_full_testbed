#!/usr/bin/env bash
set -euo pipefail
. "$(dirname "$0")/../sh_core/lpc_bus.sh"

power_bias(){ local w="${1:-0.05}"; bus_emit "power" "route_bias+=${w}"; effect_emit energy_delta "+${w}Wh"; }
