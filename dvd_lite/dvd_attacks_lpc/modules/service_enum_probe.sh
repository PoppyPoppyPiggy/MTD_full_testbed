#!/usr/bin/env bash
set -euo pipefail
ATTACK_NAME="service_enum_probe"
. "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")"/.. && pwd)/sh_core/attack_std.shlib"

: "${INTENSITY:=low}"
: "${PROBE_RATE:=auto}"
: "${PORT_RANGE:=auto}"

case "$INTENSITY" in
  low)    PROBE_RATE=${PROBE_RATE/auto/0.2}; PORT_RANGE=${PORT_RANGE/auto/10} ;;
  medium) PROBE_RATE=${PROBE_RATE/auto/0.8}; PORT_RANGE=${PORT_RANGE/auto/50} ;;
  high)   PROBE_RATE=${PROBE_RATE/auto/2.0}; PORT_RANGE=${PORT_RANGE/auto/200} ;;
esac

_act(){
  local services=("ssh:22" "http:80" "mavlink:14550" "telnet:23" "ftp:21")
  local idx=$((RANDOM % ${#services[@]}))
  local target="${services[$idx]}"
  local rate; rate=$(awk "BEGIN {srand(); print $PROBE_RATE*(0.7 + rand()*0.6)}")
  _log_bus "$ATTACK_NAME" "intensity=$INTENSITY" "probe_rate_pps=$rate" "port_range=$PORT_RANGE" "target_service=$target"
  return 0
}
run_lpc_loop _act "${DUR:-0}"
