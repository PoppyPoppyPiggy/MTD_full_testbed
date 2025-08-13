#!/usr/bin/env bash
set -euo pipefail
ATTACK_NAME="mavlink_param_drift"
. "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")"/.. && pwd)/sh_core/attack_std.shlib"

: "${INTENSITY:=low}"
: "${PARAM_NAME:=AUTO}"
: "${STEP_SIZE:=auto}"

SAFE_PARAMS=("ATC_RAT_RLL_FF" "ATC_RAT_PIT_FF" "PSC_POSXY_P" "ATC_ANG_RLL_P" "PSC_POSZ_P")

case "$INTENSITY" in
  low)    STEP_SIZE=${STEP_SIZE/auto/0.005} ;;
  medium) STEP_SIZE=${STEP_SIZE/auto/0.015} ;;
  high)   STEP_SIZE=${STEP_SIZE/auto/0.030} ;;
esac

_act(){
  local actual_param="$PARAM_NAME"
  if [[ "$PARAM_NAME" == "AUTO" ]]; then
    local idx=$((RANDOM % ${#SAFE_PARAMS[@]}))
    actual_param="${SAFE_PARAMS[$idx]}"
  fi
  local noise; noise=$(awk "BEGIN {srand(); print (rand()-0.5)*$STEP_SIZE*0.5}")
  local step;  step=$(awk "BEGIN {print $STEP_SIZE + $noise}")
  _log_bus "$ATTACK_NAME" "intensity=$INTENSITY" "param=$actual_param" "step=$step" "noise=$noise"
  return 0
}

run_lpc_loop _act "${DUR:-0}"
