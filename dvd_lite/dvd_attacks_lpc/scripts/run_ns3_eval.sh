# dvd_lite/dvd_attacks_lpc/scripts/run_ns3_eval.sh
#!/usr/bin/env bash
# ns-3 실행기(표준): dvd_lite/dvd_attacks_lpc 하위에서만 입출력
set -Eeuo pipefail
IFS=$'\n\t'

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
cd "$ROOT"

[[ -f 00_env.sh ]] && source 00_env.sh || true

LPC_LOG_DIR="${LPC_LOG_DIR:-$ROOT/attack_output}"
TIMELINE="${TIMELINE:-$LPC_LOG_DIR/effect_timeline.csv}"
OUT_CSV="$LPC_LOG_DIR/ns3_metrics.csv"
ANIM_OUT="${ANIM_OUT:-$LPC_LOG_DIR/netanim.xml}"
SIM_TIME="${SIM_TIME:-60}"
VDRONES="${VDRONES:-4}"

# ns-3 위치(없으면 기본 경로 추정)
NS3_ROOT="${NS3_ROOT:-$HOME/MTD/MTD_full_testbed/ns-3.45/ns-3-dev}"
SCRATCH="$NS3_ROOT/scratch"
SRC_LOCAL="$ROOT/eval/ns3/honeydrone_netanim.cc"
SRC_TARGET="$SCRATCH/honeydrone_netanim.cc"

if [ ! -f "$TIMELINE" ]; then
  echo "[run_ns3_eval] missing timeline: $TIMELINE" >&2
  exit 1
fi

# 코드 싱크
mkdir -p "$SCRATCH"
cp -f "$SRC_LOCAL" "$SRC_TARGET"

# 빌드 & 실행
pushd "$NS3_ROOT" >/dev/null
./waf configure --enable-examples --enable-tests  >/dev/null
./waf build >/dev/null
set +e
./waf --run scratch/honeydrone_netanim --command-template="%s --timeline='$TIMELINE' --out='$OUT_CSV' --anim='$ANIM_OUT' --simTime=${SIM_TIME} --virtualDrones=${VDRONES}"
RC=$?
set -e
popd >/dev/null

if [ $RC -ne 0 ]; then
  echo "[run_ns3_eval] ns-3 run failed (rc=$RC)"; exit $RC
fi

echo "[run_ns3_eval] OK -> $OUT_CSV ; summary -> $LPC_LOG_DIR/ns3_metrics_summary.csv ; NetAnim -> $ANIM_OUT"
