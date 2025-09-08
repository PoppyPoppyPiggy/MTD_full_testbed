#!/usr/bin/env bash
set -euo pipefail
BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$BASE"
export OUT_DIR="$BASE/bus"
export BUS_LOG="$OUT_DIR/bus.log"
export BUS_DVD_LOG="$OUT_DIR/bus_dvd.log"
echo "ENV OK  base=$BASE"
echo "OUT_DIR=$OUT_DIR"
echo "BUS_LOG=$BUS_LOG"
echo "BUS_DVD_LOG=$BUS_DVD_LOG"
: "${WIN_S:=5}" "${DRY_RUN:=1}" "${CONF_TH:=0.55}"
python3 tools/infer_attack_now.py
