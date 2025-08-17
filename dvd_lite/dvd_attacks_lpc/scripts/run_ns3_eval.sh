#!/usr/bin/env bash
# run_ns3_eval.sh — ns-3 실행기 (NS3_BUILD_MODE 지원: always|once|skip)
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
[[ -f 00_env.sh ]] && source 00_env.sh || true

TIMELINE="${TIMELINE:-$LPC_LOG_DIR/effect_timeline.csv}"
OUT="${OUT:-$LPC_LOG_DIR/ns3_metrics.csv}"
SIM_TIME="${SIM_TIME:-60}"
PKT_SIZE="${PKT_SIZE:-512}"
ANIM_OUT="${ANIM_OUT:-}"
NS3_BUILD_MODE="${NS3_BUILD_MODE:-once}"

NS3="${NS3:-${NS3_ROOT:-$MTD_ROOT/ns-3.45/ns-3-dev}}"
NS3_BIN="$NS3/ns3"
SCRATCH="${NS3_SCRATCH:-scratch/drone_lpc_eval}"

[[ -s "$TIMELINE" ]] || { echo "[run_ns3_eval] missing timeline: $TIMELINE"; exit 2; }

echo "[run_ns3_eval] mode=$NS3_BUILD_MODE"
echo "[run_ns3_eval] ns3=$NS3  bin=$NS3_BIN  scratch=$SCRATCH"

ns3_build() {
  echo "[run_ns3_eval] ns-3 configure+build"
  ( cd "$NS3" && ./ns3 configure && ./ns3 build )
}

ns3_run() {
  local cmd="$SCRATCH --timeline=$TIMELINE --out=$OUT --simTime=$SIM_TIME --pktSize=$PKT_SIZE"
  [[ -n "$ANIM_OUT" ]] && cmd="$cmd --animOut=$ANIM_OUT"
  echo "[run_ns3_eval] ./ns3 run \"$cmd\""
  ( cd "$NS3" && ./ns3 run "$cmd" )
}

case "$NS3_BUILD_MODE" in
  always)
    ns3_build
    ns3_run || { echo "[run_ns3_eval] run failed in always mode."; exit 3; }
    ;;
  skip)
    ns3_run || echo "[run_ns3_eval] run failed in skip mode (no build)."
    ;;
  once|*)
    if ! ns3_run; then
      echo "[run_ns3_eval] initial run failed → building once..."
      ns3_build
      ns3_run || echo "[run_ns3_eval] run still failing after build (will fallback)."
    fi
    ;;
esac

# 스모크 테스트 & fallback
LINES="$( (wc -l < "$OUT") || echo 0 )"
MIN=$(( SIM_TIME ))
if [[ "$LINES" -lt 10 || "$LINES" -lt "$MIN" ]]; then
  echo "[run_ns3_eval] ns3_metrics too short ($LINES). synthesizing from timeline..."
  python3 tools/ns3_window_fallback.py "$TIMELINE" -o "$OUT" --simTime "$SIM_TIME"
fi

echo "[run_ns3_eval] done -> $OUT ($(wc -l < "$OUT") lines)"
