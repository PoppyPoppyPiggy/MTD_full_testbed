#!/usr/bin/env bash
set -euo pipefail
BASE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")"/.. && pwd)"
NS3="${NS3_ROOT:-$HOME/MTD/MTD_full_testbed/ns-3.45/ns-3-dev}"
BUS="$BASE/attack_output/bus.log"
TL="$BASE/attack_output/effect_timeline.csv"
OUT="$BASE/attack_output/ns3_metrics.csv"
RULES="$BASE/tools/effects_rules.json"
python3 "$BASE/tools/gen_effects_timeline.py" "$BUS" "$TL" "$RULES"
cd "$NS3"
./ns3 run "scratch/drone_lpc_eval --timeline=$TL --out=$OUT --simTime=60 --pktSize=512"
echo "[ns-3] wrote: $OUT"
