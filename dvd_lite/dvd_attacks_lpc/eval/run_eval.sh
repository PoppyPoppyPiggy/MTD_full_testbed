#!/usr/bin/env bash
set -euo pipefail
BASE="$(cd "$(dirname "$0")/.." && pwd)"
NS3_DIR="/home/kali/MTD/MTD_full_testbed/ns-3.45/ns-3-dev"
PIPELINE="${1:-scenarios/S_lpc_v2.pipeline}"
SIM_TIME="${SIM_TIME:-120}"

echo "[eval] pipeline: $PIPELINE"

# 1) 공격 실행
LPC_WINDOW="" "$BASE/run_scenario.sh" "$PIPELINE"

# 2) bus -> CSV/Timeline
python3 "$BASE/tools/bus2csv.py" "$BASE/attack_output/bus.log" \
        "$BASE/attack_output/bus.csv" "$BASE/attack_output/effect_timeline.csv"

# 3) LPC 메트릭 산출
python3 "$BASE/tools/lpc_metrics.py" "$BASE/attack_output/effect_timeline.csv" \
        "$BASE/attack_output/metrics.csv"

# 4) ns-3 scratch 프로그램 보장
SCR="$NS3_DIR/scratch/drone_lpc_eval.cc"
if [[ ! -f "$SCR" ]]; then
  echo "[eval] installing scratch/drone_lpc_eval.cc ..."
  # 두 위치 모두 시도(dvd_lite/ns3 혹은 ns-3-dev/상대)
  install -m 0644 "$BASE/../ns3/drone_lpc_eval.cc" "$SCR" 2>/dev/null || \
  install -m 0644 "$BASE/../../ns-3.45/ns-3-dev/scratch/drone_lpc_eval.cc" "$SCR" 2>/dev/null || \
  echo "[eval] warn: couldn't auto-copy (확인 필요)"
fi

# 5) CMake 빌드 & 실행
echo "[eval] ns-3 cmake build ..."
cmake -S "$NS3_DIR" -B "$NS3_DIR/build"
cmake --build "$NS3_DIR/build" -j"$(nproc)"

NS3_BIN="$NS3_DIR/build/scratch/drone_lpc_eval"
if [[ ! -x "$NS3_BIN" ]]; then
  echo "[eval] error: ns-3 binary not found at $NS3_BIN"
  echo -e "metric,value\nns3_error,1" > "$BASE/attack_output/ns3_metrics.csv"
else
  echo "[eval] ns-3 run ..."
  "$NS3_BIN" \
    --timeline="$BASE/attack_output/effect_timeline.csv" \
    --out="$BASE/attack_output/ns3_metrics.csv" \
    --simTime="$SIM_TIME" || {
      echo "[eval] ns-3 run failed"
      echo -e "metric,value\nns3_error,1" > "$BASE/attack_output/ns3_metrics.csv"
    }
fi

# 6) 병합
if [[ -f "$BASE/attack_output/ns3_metrics.csv" ]]; then
  tail -n +2 "$BASE/attack_output/ns3_metrics.csv" >> "$BASE/attack_output/metrics.csv" || true
fi

echo "[eval] done -> $BASE/attack_output/{bus.csv,effect_timeline.csv,metrics.csv,ns3_metrics.csv}"
