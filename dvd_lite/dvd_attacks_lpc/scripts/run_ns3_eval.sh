#!/usr/bin/env bash
# ns-3 실행기 (NS3_BUILD_MODE: always|once|skip)
# - effect_timeline.csv 필수
# - attack_output/dvd_state.csv 존재 시 drone_lpc_eval_dvd 사용(없으면 drone_lpc_eval)
# - dvd_state가 ISO 시각이면 epoch로 자동 변환하여 전달
set -Eeuo pipefail
IFS=$'\n\t'

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
cd "$ROOT"

[[ -f 00_env.sh ]] && source 00_env.sh || true

LPC_LOG_DIR="${LPC_LOG_DIR:-$ROOT/attack_output}"
TIMELINE="${TIMELINE:-$LPC_LOG_DIR/effect_timeline.csv}"
OUT="${OUT:-$LPC_LOG_DIR/ns3_metrics.csv}"
ANIM_OUT="${ANIM_OUT:-$LPC_LOG_DIR/netanim.xml}"

SIM_TIME="${SIM_TIME:-60}"
PKT_SIZE="${PKT_SIZE:-512}"
NS3_BUILD_MODE="${NS3_BUILD_MODE:-once}"

NS3="${NS3:-${NS3_ROOT:-$MTD_ROOT/ns-3.45/ns-3-dev}}"
NS3_BIN="$NS3/ns3"
SCRATCH_LITE="scratch/drone_lpc_eval"
SCRATCH_DVD="scratch/drone_lpc_eval_dvd"

DVD_STATE_SRC="${DVD_STATE:-$LPC_LOG_DIR/dvd_state.csv}"
DVD_STATE_EPOCH="$LPC_LOG_DIR/dvd_state.epoch.csv"

[[ -s "$TIMELINE" ]] || { echo "[run_ns3_eval] missing timeline: $TIMELINE"; exit 2; }

echo "[run_ns3_eval] mode=$NS3_BUILD_MODE"
echo "[run_ns3_eval] ns3=$NS3  bin=$NS3_BIN"

# 1) SIM_TIME 자동 산출(옵션)
if [[ "${AUTO_SIM_TIME:-0}" == "1" ]]; then
  SIM_TIME="$(python3 - "$TIMELINE" <<'PY'
import csv,sys
f=sys.argv[1]; ts=[]
with open(f,newline='') as fp:
  rd=csv.DictReader(fp)
  for r in rd:
    try: ts.append(float(r.get('t',0)))
    except: pass
print(int(max(ts)-min(ts))+5 if ts else 60)
PY
)"
  echo "[run_ns3_eval] AUTO_SIM_TIME -> SIM_TIME=$SIM_TIME"
fi

# 2) dvd_state.csv ISO→epoch 자동 변환
USE_DVD=0
if [[ -s "$DVD_STATE_SRC" ]]; then
  first_line="$(sed -n '2p' "$DVD_STATE_SRC" || true)"
  if [[ "$first_line" == *T* ]]; then
    echo "[run_ns3_eval] dvd_state appears ISO; converting -> $DVD_STATE_EPOCH"
    python3 - "$DVD_STATE_SRC" "$DVD_STATE_EPOCH" <<'PY'
import sys,datetime
src,dst=sys.argv[1],sys.argv[2]
with open(src) as f: lines=[ln.strip() for ln in f if ln.strip()]
with open(dst,'w') as w:
  if not lines: raise SystemExit(1)
  w.write(lines[0]+'\n')
  for ln in lines[1:]:
    cols=ln.split(',')
    t=cols[0].strip()
    try:
      dt=datetime.datetime.fromisoformat(t.replace('Z','+00:00'))
      cols[0]=str(dt.timestamp())
    except Exception:
      try: float(t)  # 이미 epoch
      except Exception: continue
    w.write(','.join(cols)+'\n')
PY
    DVD_STATE="$DVD_STATE_EPOCH"
  else
    DVD_STATE="$DVD_STATE_SRC"
  fi
  USE_DVD=1
fi

# 3) 사용할 scratch 결정
SCRATCH="$SCRATCH_LITE"
[[ "$USE_DVD" == "1" ]] && SCRATCH="$SCRATCH_DVD"
echo "[run_ns3_eval] scratch=$SCRATCH"
[[ -x "$NS3_BIN" ]] || { echo "[run_ns3_eval] launcher not found: $NS3_BIN"; exit 3; }

ns3_build() { echo "[run_ns3_eval] ns-3 configure+build"; ( cd "$NS3" && ./ns3 configure && ./ns3 build ); }
ns3_run() {
  local cmd="$SCRATCH --timeline=$TIMELINE --out=$OUT --simTime=$SIM_TIME --pktSize=$PKT_SIZE --animOut=$ANIM_OUT"
  [[ "$USE_DVD" == "1" ]] && cmd="$cmd --dvdState=$DVD_STATE"
  echo "[run_ns3_eval] ./ns3 run \"$cmd\""
  ( cd "$NS3" && ./ns3 run "$cmd" )
}

case "$NS3_BUILD_MODE" in
  always) ns3_build; ns3_run || { echo "[run_ns3_eval] run failed (always)."; exit 4; } ;;
  skip)   ns3_run || echo "[run_ns3_eval] run failed (skip build)." ;;
  once|*) if ! ns3_run; then echo "[run_ns3_eval] initial run failed → building once..."; ns3_build; ns3_run || echo "[run_ns3_eval] run still failing (fallback)."; fi ;;
esac

# 4) 스모크 테스트 & fallback
LINES="$( (wc -l < "$OUT") || echo 0 )"
MIN=$(( SIM_TIME / 1 ))  # 초당 1줄 기대
if [[ "$LINES" -lt 10 || "$LINES" -lt "$MIN" ]]; then
  echo "[run_ns3_eval] ns3_metrics too short ($LINES). synthesizing from timeline..."
  [[ -f "$OUT" && -s "$OUT" ]] || printf "t,rxPackets,throughput_mbps\n" > "$OUT"
  python3 tools/ns3_window_fallback.py "$TIMELINE" -o "$OUT" --simTime "$SIM_TIME"
fi

echo "[run_ns3_eval] done -> $OUT ($(wc -l < "$OUT") lines)"
[[ -n "$ANIM_OUT" ]] && echo "[run_ns3_eval] NetAnim XML -> $ANIM_OUT"
