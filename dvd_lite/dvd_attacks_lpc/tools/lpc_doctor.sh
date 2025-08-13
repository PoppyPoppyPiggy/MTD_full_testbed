#!/usr/bin/env bash
set -euo pipefail
BASE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")"/.. && pwd)"
echo "== LPC Doctor =="

echo "[1] deps"
command -v yq && echo " - yq OK" || echo " - yq MISSING"
python3 -c 'import sys; print("[py] OK")' || true

echo "[2] env & dirs"
echo " BASE=$BASE"
test -d "$BASE/attack_output" || mkdir -p "$BASE/attack_output"
test -f "$BASE/attack_output/bus.log" || : > "$BASE/attack_output/bus.log"
ls -l "$BASE/attack_output/bus.log" | sed 's/^/  /'

echo "[3] window"
echo " LPC_WINDOW=${LPC_WINDOW:-<empty>}"

echo "[4] try one-shot module (no window, budget=1)"
( cd "$BASE" && LPC_WINDOW="" LPC_MAX_BUDGET=1 LPC_INTERVAL_MS=200 ./modules/mavlink_param_drift.sh )
tail -n 2 "$BASE/attack_output/bus.log" | sed 's/^/  /'

echo "[5] ns-3 eval quick"
( cd "$BASE" && ./eval/run_eval.sh )
test -f "$BASE/attack_output/ns3_metrics.csv" && column -t -s, "$BASE/attack_output/ns3_metrics.csv"
echo "== done =="
