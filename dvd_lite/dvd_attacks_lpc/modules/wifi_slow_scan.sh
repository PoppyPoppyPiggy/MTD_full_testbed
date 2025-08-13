#!/usr/bin/env bash
set -euo pipefail
ATTACK_NAME="wifi_slow_scan"
. "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")"/.. && pwd)/sh_core/attack_std.shlib"

: "${INTENSITY:=low}"
: "${SCAN_RATE:=auto}"
: "${SIGNAL_VARIATION:=auto}"

case "$INTENSITY" in
  low)    SCAN_RATE=${SCAN_RATE/auto/0.1}; SIGNAL_VARIATION=${SIGNAL_VARIATION/auto/2.0} ;;
  medium) SCAN_RATE=${SCAN_RATE/auto/0.3}; SIGNAL_VARIATION=${SIGNAL_VARIATION/auto/5.0} ;;
  high)   SCAN_RATE=${SCAN_RATE/auto/0.8}; SIGNAL_VARIATION=${SIGNAL_VARIATION/auto/10.0} ;;
esac

_act(){
  local noise_factor; noise_factor=$(awk "BEGIN {srand(); print 0.85 + rand()*0.3}") # 0.85~1.15
  local effective_rate; effective_rate=$(awk "BEGIN {print $SCAN_RATE * $noise_factor}")
  _log_bus "$ATTACK_NAME" "intensity=$INTENSITY" "scan_rate=$effective_rate" "signal_variation=$SIGNAL_VARIATION" "noise_factor=$noise_factor"
  return 0
}

run_lpc_loop _act "${DUR:-0}"
