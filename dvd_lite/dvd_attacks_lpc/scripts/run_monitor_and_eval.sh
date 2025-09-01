#!/usr/bin/env bash
set -Eeuo pipefail
# 사용: run_monitor_and_eval.sh <SIM_TIME> <DT>
: "${ATK_DIR:?ATK_DIR not set}"

SIM_TIME="${1:?sim seconds}"
DT="${2:?dt seconds}"

OUT="${ATK_DIR}/attack_output"
mkdir -p "$OUT"

echo "[run] integrated monitor (no_mtd) ${SIM_TIME}s"
python3 "${ATK_DIR}/tools/integrated_mtd_docker_monitor.py" \
  --mode no_mtd --duration "${SIM_TIME}" --dt "${DT}" \
  --bus "${OUT}/bus.log"

echo "[run] integrated monitor (mtd) ${SIM_TIME}s"
python3 "${ATK_DIR}/tools/integrated_mtd_docker_monitor.py" \
  --mode mtd --duration "${SIM_TIME}" --dt "${DT}" \
  --bus "${OUT}/bus_mtd.log"

echo "[run] gen_timelines"
bash "${ATK_DIR}/scripts/gen_timelines.sh"

echo "[run] scenario eval matrix"
bash "${ATK_DIR}/scripts/scenario_eval_matrix.sh"

echo "[run] scoring export preview"
python3 "${ATK_DIR}/tools/mtd_scoring_calculator.py" --test --export "${OUT}/mtd_scores_demo.json" --format json || true

echo "[run] done"
