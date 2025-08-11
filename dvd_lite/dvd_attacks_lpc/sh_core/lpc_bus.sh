#!/usr/bin/env bash
set -euo pipefail
. "$(dirname "$0")/../00_env.sh"
mkdir -p "$LPC_LOG_DIR"

bus_emit(){ printf "%s\t%s\t%s\n" "$(date +%s)" "$1" "$2" >> "$LPC_LOG_DIR/bus.log"; }
effect_emit(){ bus_emit "effect" "$*"; }
