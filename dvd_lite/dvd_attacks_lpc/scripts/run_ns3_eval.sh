#!/usr/bin/env bash
# dvd_lite/dvd_attacks_lpc/scripts/run_ns3_eval.sh
# Run ns-3 (cmake launcher ./ns3, fallback to waf) with effect timeline.
set -Eeuo pipefail

TIMELINE="${TIMELINE:?set TIMELINE path}"
OUT="${OUT:-attack_output/ns3_metrics.csv}"

# ns-3 위치/프로그램명
NS3_ROOT="${NS3_ROOT:-/home/kali/MTD/MTD_full_testbed/ns-3.45/ns-3-dev}"
NS3_PROG="${NS3_PROG:-honeydrone_netanim}"   # scratch/<name>.cc
SIM_TIME="${SIM_TIME:-60}"

# 추가 파라미터 전달 (없으면 기본값)
ANIM_MAX_PKTS="${ANIM_MAX_PKTS:-0}"  # 0=unlimited
PKT_SIZE="${PKT_SIZE:-600}"

if [[ ! -f "${TIMELINE}" ]]; then
  echo "[ERR] timeline not found: ${TIMELINE}" >&2; exit 2
fi
if [[ ! -d "${NS3_ROOT}" ]]; then
  echo "[ERR] ns-3 root not found: ${NS3_ROOT}" >&2; exit 2
fi

cd "${NS3_ROOT}"

if [[ ! -f "scratch/${NS3_PROG}.cc" ]]; then
  echo "[ERR] scratch/${NS3_PROG}.cc not found."
  exit 3
fi

# 빌드
if [[ -x ./ns3 ]]; then
  ./ns3 build
elif [[ -x ./waf ]]; then
  ./waf -d optimized build
else
  echo "[ERR] ns-3 launcher not found"; exit 4
fi

# 실행 (cmake 우선)
RUN_ARGS="scratch/${NS3_PROG} --timeline=${TIMELINE} --simTime=${SIM_TIME} --pcap=1 --animMaxPkts=${ANIM_MAX_PKTS} --pktSize=${PKT_SIZE}"
if [[ -x ./ns3 ]]; then
  ./ns3 run "${RUN_ARGS}"
else
  ./waf --run "${RUN_ARGS}"
fi

# 결과 csv 집계
if [[ -f "attack_output/ns3_metrics.csv" ]]; then
  cp -f "attack_output/ns3_metrics.csv" "${OUT}"
elif [[ -f "../../dvd_lite/dvd_attacks_lpc/attack_output/ns3_metrics.csv" ]]; then
  cp -f "../../dvd_lite/dvd_attacks_lpc/attack_output/ns3_metrics.csv" "${OUT}"
elif ls attack_output/ns3_metrics_*.csv >/dev/null 2>&1; then
  cat attack_output/ns3_metrics_*.csv > "${OUT}"
elif ls ../../dvd_lite/dvd_attacks_lpc/attack_output/ns3_metrics_*.csv >/dev/null 2>&1; then
  cat ../../dvd_lite/dvd_attacks_lpc/attack_output/ns3_metrics_*.csv > "${OUT}"
else
  echo "[WARN] NS-3 metrics csv not found"
fi

echo "[OK] ns-3 done -> ${OUT}"
