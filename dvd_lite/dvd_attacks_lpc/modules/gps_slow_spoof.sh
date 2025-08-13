#!/usr/bin/env bash
set -euo pipefail
ATTACK_NAME="gps_slow_spoof"
. "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")"/.. && pwd)/sh_core/attack_std.shlib"

: "${INTENSITY:=low}"
: "${OFFSET_M:=auto}"
: "${DRIFT_RATE:=auto}"

case "$INTENSITY" in
  low)    OFFSET_M=${OFFSET_M/auto/0.1}; DRIFT_RATE=${DRIFT_RATE/auto/0.05} ;;
  medium) OFFSET_M=${OFFSET_M/auto/0.3}; DRIFT_RATE=${DRIFT_RATE/auto/0.15} ;;
  high)   OFFSET_M=${OFFSET_M/auto/0.8}; DRIFT_RATE=${DRIFT_RATE/auto/0.40} ;;
esac

_act(){
  local lat_offset lon_offset alt_offset total_offset drift_acc
  lat_offset=$(awk "BEGIN {srand(); print $OFFSET_M*(rand()-0.5)*2}")
  lon_offset=$(awk "BEGIN {srand(); print $OFFSET_M*(rand()-0.5)*2}")
  alt_offset=$(awk "BEGIN {srand(); print $OFFSET_M*0.1*(rand()-0.5)*2}")
  total_offset=$(awk "BEGIN {print sqrt(($lat_offset)^2 + ($lon_offset)^2)}")
  drift_acc=$(awk "BEGIN {srand(); print $DRIFT_RATE*(1 + rand()*0.5)}")
  _log_bus "$ATTACK_NAME" "intensity=$INTENSITY" "lat_offset_m=$lat_offset" "lon_offset_m=$lon_offset" "alt_offset_m=$alt_offset" "total_offset_m=$total_offset" "drift_rate=$drift_acc"
  return 0
}

run_lpc_loop _act "${DUR:-0}"
