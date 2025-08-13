#!/usr/bin/env bash
set -euo pipefail
ATTACK_NAME="telemetry_trickle_jam"
. "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")"/.. && pwd)/sh_core/attack_std.shlib"

: "${INTENSITY:=low}"
: "${PPS_LIMIT:=auto}"
: "${LATENCY_INCREASE:=auto}"

case "$INTENSITY" in
  low)    PPS_LIMIT=${PPS_LIMIT/auto/5};  LATENCY_INCREASE=${LATENCY_INCREASE/auto/2}  ;;
  medium) PPS_LIMIT=${PPS_LIMIT/auto/15}; LATENCY_INCREASE=${LATENCY_INCREASE/auto/8}  ;;
  high)   PPS_LIMIT=${PPS_LIMIT/auto/30}; LATENCY_INCREASE=${LATENCY_INCREASE/auto/20} ;;
esac

_act(){
  local jitter; jitter=$(awk "BEGIN {srand(); print int(rand()*3)+1}")
  local effective_latency=$((LATENCY_INCREASE + jitter))
  _log_bus "$ATTACK_NAME" "intensity=$INTENSITY" "pps_limit=$PPS_LIMIT" "latency_increase_ms=$effective_latency" "jitter_ms=$jitter"
  return 0
}

run_lpc_loop _act "${DUR:-0}"
