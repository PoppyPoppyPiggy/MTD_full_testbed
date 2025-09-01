#!/usr/bin/env bash
set -Eeuo pipefail

: "${NS3_ROOT:?NS3_ROOT not set}"
: "${ATK_DIR:?ATK_DIR not set}"
: "${SIM_TIME:=60}"
: "${PKT_SIZE:=10000}"
: "${ANIM_MAX_PKTS:=100000000}"

MODULES_DEFAULT=("follow_flood" "follow_mavlink" "telemetry_trickle_jam" "wifi_slow_scan")
LEVELS_DEFAULT=("low" "med" "high")
read -r -a MODULES <<< "${MODULES:-${MODULES_DEFAULT[*]}}"
read -r -a LEVELS  <<< "${LEVELS:-${LEVELS_DEFAULT[*]}}"

TL_BASE="${ATK_DIR}/attack_output/effect_timeline.baseline.csv"
TL_MTD="${ATK_DIR}/attack_output/effect_timeline.mtd.csv"

if [[ ! -s "$TL_BASE" || ! -s "$TL_MTD" ]]; then
  echo "[scenario_eval_matrix] timelines missing → generating..."
  bash "${ATK_DIR}/scripts/gen_timelines.sh"
fi

cd "$NS3_ROOT"

run_one() {
  local mode="$1" module="$2" level="$3" tl_global="$4"
  local mtd_flag="0"; [[ "$mode" == "mtd" ]] && mtd_flag="1"
  local OUT_DIR="${ATK_DIR}/attack_output/${module}/${mode}/level-${level}"
  mkdir -p "$OUT_DIR"

  # 전역 타임라인 → 시나리오별 타임라인(포트 주석 포함)
  local TL_SCEN="${OUT_DIR}/timeline_${module}_${mode}_${level}.csv"
  bash "${ATK_DIR}/scripts/mk_timeline_for_scenario.sh" "$module" "$mode" "$level" "$tl_global" "$TL_SCEN"

  # 선/후 도커 스냅샷
  bash "${ATK_DIR}/scripts/docker_observer.sh" "$OUT_DIR" "pre" || true

  ./ns3 run "scratch/drone_lpc_eval \
    --module=${module} \
    --level=${level} \
    --mtd=${mtd_flag} \
    --simTime=${SIM_TIME} \
    --pktSize=${PKT_SIZE} \
    --animMaxPkts=${ANIM_MAX_PKTS} \
    --timeline=${TL_SCEN} \
    --outRoot=${ATK_DIR}/attack_output" >/dev/null

  bash "${ATK_DIR}/scripts/docker_observer.sh" "$OUT_DIR" "post" || true

  test -s "${OUT_DIR}/ns3_metrics_summary_${module}_${mode}_${level}.csv"
  test -s "${OUT_DIR}/${module}_${mode}_${level}.xml"
  echo "[run] ${module}/${mode}/level-${level} done."
}

for m in "${MODULES[@]}"; do
  for lv in "${LEVELS[@]}"; do
    run_one "no_mtd" "$m" "$lv" "$TL_BASE"
    run_one "mtd"    "$m" "$lv" "$TL_MTD"
  done
done

echo "[scenario_eval_matrix] all done."
