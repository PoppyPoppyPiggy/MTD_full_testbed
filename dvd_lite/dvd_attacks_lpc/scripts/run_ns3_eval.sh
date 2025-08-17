#!/usr/bin/env bash
# dvd_lite/dvd_attacks_lpc/scripts/run_ns3_eval.sh
# ./ns3 런처만 사용 (waf 미사용). 최초 빌드 자동(clean/configure/build).
set -euo pipefail

TL="${1:-attack_output/effect_timeline.csv}"
OUT="${2:-attack_output/ns3_metrics.csv}"
SIM_TIME="${3:-60}"
PKT_SIZE="${4:-512}"
ANIM_OUT="${5:-}"  # 비우면 전달 안 함

: "${NS3:?source 00_env.sh 먼저 실행하세요}"
: "${NS3_BIN:?source 00_env.sh 먼저 실행하세요}"
: "${NS3_SCRATCH:?source 00_env.sh 먼저 실행하세요}"

ABS_TL="$(realpath -m "$TL")"
ABS_OUT="$(realpath -m "$OUT")"
mkdir -p "$(dirname "$ABS_OUT")"

cd "$NS3"

build_once() {
  echo "[NS3] clean";     ./ns3 clean
  echo "[NS3] configure"; ./ns3 configure
  echo "[NS3] build";     ./ns3 build
}

# 빌드 확인(없으면 최초 빌드)
if [[ "${NS3_FORCE_REBUILD:-0}" == "1" ]]; then
  build_once
else
  if [[ ! -d build || -z "$(find build -type f -name '*drone_lpc_eval*' 2>/dev/null | head -n1)" ]]; then
    build_once
  fi
fi

CMD="$NS3_SCRATCH --timeline=$ABS_TL --out=$ABS_OUT --simTime=$SIM_TIME --pktSize=$PKT_SIZE"
if [[ -n "$ANIM_OUT" ]]; then
  ABS_ANIM="$(realpath -m "$ANIM_OUT")"
  CMD="$CMD --animOut=$ABS_ANIM"
fi

echo "[NS3] run: $CMD"
./ns3 run "$CMD"
echo "[OK] ns-3 metrics -> $ABS_OUT"
