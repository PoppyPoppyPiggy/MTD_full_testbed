#!/usr/bin/env bash
set -euo pipefail
. "$(dirname "$0")/../sh_core/lpc_bus.sh"

cred_touch_tease(){
  bus_emit "creds" "login_touch_lpc"
  effect_emit analysis_cost "+1unit"
  # TODO: very-low-rate auth attempts to a mock endpoint
}
