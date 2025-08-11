#!/usr/bin/env bash
set -euo pipefail
. "$(dirname "$0")/../sh_core/lpc_bus.sh"

lte_quality_tease(){
  bus_emit "lte" "rsrq_rsrp_tease"
  effect_emit link_quality "-1unit"
  # TODO: LTE emulator / ns-3 LTE hook
}
