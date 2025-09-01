#!/usr/bin/env bash
# dvd_lite/dvd_attacks_lpc/scripts/scenario_eval_matrix.sh
# Baseline vs MTD 평가를 모듈/레벨별로 실행하고 산출물을 자동 폴더에 정리.

set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="${ROOT}/attack_output"
BUS="${OUT_DIR}/bus.log"
TOOLS_DIR="${ROOT}/tools"

NS3_ROOT="${NS3_ROOT:?set NS3_ROOT}"
NS3_PROG="${NS3_PROG:-drone_lpc_eval}"   # 기본: 새 eval 사용
SIM_TIME="${SIM_TIME:-60}"
PKT_SIZE="${PKT_SIZE:-10000}"
ANIM_MAX_PKTS="${ANIM_MAX_PKTS:-0}"
TIMELINE_DT="${TIMELINE_DT:-1.0}"        # 0.1 or 0.01 권장시 바꿔
HORIZON="${HORIZON:-$SIM_TIME}"

MODULES=(${MODULES:-follow_flood follow_mavlink telemetry_trickle_jam})
LEVELS=(${LEVELS:-low med high})

mkdir -p "$OUT_DIR"

gen_timeline() {
  local mode="$1"    # baseline|mtd
  local out_csv="${OUT_DIR}/effect_timeline.${mode}.csv"
  python3 "${TOOLS_DIR}/gen_effects_timeline.py" "${BUS}" \
    -o "${out_csv}" --tools-dir "${TOOLS_DIR}" --horizon "${HORIZON}" --dt "${TIMELINE_DT}" || true
  echo "${out_csv}"
}

ns3_run_one() {
  local module="$1" level="$2" mode_flag="$3" timeline_csv="$4"
  local mode_name; [[ "$mode_flag" == "1" ]] && mode_name="mtd" || mode_name="no_mtd"
  # drone_lpc_eval 은 anim/out 자동 경로 생성하므로 최소 인자만 전달
  ( cd "$NS3_ROOT" && \
    ./ns3 run "${NS3_PROG} \
      --module=${module} --level=${level} --mtd=${mode_flag} \
      --simTime=${SIM_TIME} --pktSize=${PKT_SIZE} --animMaxPkts=${ANIM_MAX_PKTS} \
      --timeline=${timeline_csv}" )
}

echo "=== [A] Baseline: Attack Only ==="
base_tl="$(gen_timeline baseline)"
for m in "${MODULES[@]}"; do
  for lv in "${LEVELS[@]}"; do
    echo "[Baseline] module=${m}, level=${lv}"
    ns3_run_one "${m}" "${lv}" "0" "${base_tl}"
  done
done

echo "=== [B] MTD → Probe → Attack ==="
mtd_tl="$(gen_timeline mtd)"
for m in "${MODULES[@]}"; do
  for lv in "${LEVELS[@]}"; do
    echo "[MTD] module=${m}, level=${lv}"
    ns3_run_one "${m}" "${lv}" "1" "${mtd_tl}"
  done
done

echo "[DONE] outputs under: ${OUT_DIR}/<module>/(no_mtd|mtd)/level-<lv>/"
