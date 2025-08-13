#!/usr/bin/env bash
set -euo pipefail
ATTACK_NAME="power_route_bias"
. "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")"/.. && pwd)/sh_core/attack_std.shlib"

: "${INTENSITY:=low}"
: "${BIAS_FACTOR:=auto}"
: "${CPU_OVERHEAD:=auto}"

case "$INTENSITY" in
  low)    BIAS_FACTOR=${BIAS_FACTOR/auto/1.05}; CPU_OVERHEAD=${CPU_OVERHEAD/auto/2} ;;
  medium) BIAS_FACTOR=${BIAS_FACTOR/auto/1.15}; CPU_OVERHEAD=${CPU_OVERHEAD/auto/8} ;;
  high)   BIAS_FACTOR=${BIAS_FACTOR/auto/1.30}; CPU_OVERHEAD=${CPU_OVERHEAD/auto/20} ;;
esac

_act(){
  local queue_additions; queue_additions=$(awk "BEGIN {print int($BIAS_FACTOR*10)}")
  local cpu_overhead_pct; cpu_overhead_pct=$(awk "BEGIN {print ($BIAS_FACTOR-1)*100}")
  local route_complexity; route_complexity=$(awk "BEGIN {print $BIAS_FACTOR*100}")
  _log_bus "$ATTACK_NAME" "intensity=$INTENSITY" "bias_factor=$BIAS_FACTOR" "queue_additions=$queue_additions" "cpu_overhead_pct=$cpu_overhead_pct" "route_complexity=$route_complexity"
  return 0
}
run_lpc_loop _act "${DUR:-0}"
