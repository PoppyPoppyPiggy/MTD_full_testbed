#!/usr/bin/env bash
set -euo pipefail
. "$(dirname "$0")/../00_env.sh"

_ts(){ date +%s; }
_bus_line(){ printf "%s\t%s\tmode=%s actor=%s %s\n" "$(_ts)" "$1" "${LPC_MODE:-SIM}" "${LPC_ACTOR:-attacker}" "$2"; }
bus_emit(){ _bus_line "$1" "$2" >> "$LPC_LOG_DIR/bus.log"; }
effect_emit(){ bus_emit "effect" "$*"; }   # ns3 변환용: loss_pct=.. delay_ms=.. 등
log(){ echo "[$(date +%F %T)] $*" | tee -a "$LPC_LOG_DIR/run.log"; }
