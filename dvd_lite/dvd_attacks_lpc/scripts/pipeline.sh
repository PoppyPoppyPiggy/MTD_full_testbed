#!/usr/bin/env bash
set -euo pipefail

echo "==[1/6] 공격 시나리오 실행 =="
if [[ "${RUN_ATTACK:-1}" == "1" ]]; then
  bash scripts/lpc_run.sh
else
  echo "[*] 기존 bus.log 재사용"
fi

echo "==[2/6] bus.log -> effect_timeline.csv =="
[[ -f "${EFFECTS_RULES:-}" ]] || { echo "[ERROR] EFFECTS_RULES 필요"; exit 1; }

python3 tools/gen_effects_timeline.py \
  attack_output/bus.log -o attack_output/effect_timeline.csv \
  --rules "${EFFECTS_RULES}"

echo "==[3/6] NS-3 평가 =="
TIMELINE="attack_output/effect_timeline.csv" \
OUT="attack_output/ns3_metrics.csv" \
SIM_TIME="${SIM_TIME:-60}" PKT_SIZE="${PKT_SIZE:-512}" \
bash scripts/run_ns3_eval.sh

echo "==[4/6] 윈도우링 (안정판) =="
python3 tools/lpc_metrics_cli.py attack_output/effect_timeline.csv \
  -o attack_output/window_features.csv \
  --win "${WIN:-3}" --stride "${STRIDE:-1}"

echo "==[5/6] ML 데이터 빌드 =="
python3 ml/build_supervised.py || true

echo "==[6/6] 건강검진 =="
wc -l attack_output/effect_timeline.csv attack_output/ns3_metrics.csv attack_output/window_features.csv || true
ls -lh ../../supervised_data/* 2>/dev/null || true
echo "[DONE]"
