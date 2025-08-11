#!/usr/bin/env bash
set -euo pipefail
BASE="$(cd "$(dirname "$0")/.." && pwd)"

PIPELINE="${1:-scenarios/S_mix_core.pipeline}"
NS3_DIR="/home/kali/MTD/MTD_full_testbed/ns-3.45/ns-3-dev"

# 1) 공격 실행 (짧게)
LPC_WINDOW="" LPC_MAX_BUDGET=${LPC_MAX_BUDGET:-8} LPC_INTERVAL_MS=${LPC_INTERVAL_MS:-500} \
  "$BASE/run_scenario.sh" "$PIPELINE"

# 2) 버스로그 → CSV/타임라인
python3 "$BASE/tools/bus2csv.py" "$BASE/attack_output/bus.log" "$BASE/attack_output/bus.csv" "$BASE/attack_output/effect_timeline.csv"

# 3) 메트릭 산출
python3 "$BASE/tools/lpc_metrics.py" "$BASE/attack_output/effect_timeline.csv" "$BASE/attack_output/metrics.csv"

# 4) ns-3 빌드 & 재현
pushd "$NS3_DIR" >/dev/null
./waf build
./waf --run "scratch/drone_lpc_eval --timeline=$BASE/attack_output/effect_timeline.csv --simTime=120"
popd >/dev/null

echo "[run_eval] done. See: $BASE/attack_output/{bus.csv,effect_timeline.csv,metrics.csv}"
