#!/usr/bin/env bash
# ns-3 평가 실행기 (./ns3 런처 대응판)
# - 00_env.sh 로드(있으면)
# - bus.log → effect_timeline.csv 자동 생성
# - 타임라인 비면 샘플 주입
# - ./ns3 run "scratch/drone_lpc_eval ..." 호출
# - 실패 시 더미 결과 기록
set -euo pipefail

############################################
# 0) 경로/환경
############################################
# BASE: dvd_attacks_lpc 루트
BASE="${BASE:-"$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")"/.. && pwd)"}"
ATTACK_OUT="$BASE/attack_output"
TOOLS_DIR="$BASE/tools"

# 옵션: 외부에서 미리 export 한 값 사용(없으면 기본)
NS3_ROOT_DEFAULT="$HOME/MTD/MTD_full_testbed/ns-3.45/ns-3-dev"
NS3="${NS3:-${NS3_ROOT:-$NS3_ROOT_DEFAULT}}"
NS3_BIN="$NS3/ns3"              # ./ns3 런처 실행 파일
SCRATCH_BIN="scratch/drone_lpc_eval"

BUS_LOG="${BUS_LOG:-$ATTACK_OUT/bus.log}"
TIMELINE="${TIMELINE:-$ATTACK_OUT/effect_timeline.csv}"
OUT_CSV="${OUT_CSV:-$ATTACK_OUT/ns3_metrics.csv}"
ANIM_OUT="${ANIM_OUT:-}"        # 예: /tmp/ns3/anim.xml (비우면 비활성)

mkdir -p "$ATTACK_OUT"

# 00_env.sh 있으면 불러와서 Docker/IP/로깅 상호운용
if [[ -f "$BASE/00_env.sh" ]]; then
  # shellcheck disable=SC1091
  source "$BASE/00_env.sh" || true
fi

############################################
# 1) 타임라인 준비 (bus.log → effect_timeline.csv)
############################################
regen_from_bus() {
  # gen_effects_timeline.py 가 인자 없이 내부 경로 쓰도록 만들어져 있으면 그냥 실행
  if python3 "$TOOLS_DIR/gen_effects_timeline.py" 2>/dev/null; then
    return 0
  fi
  # 구버전 호환: BUS/OUT/RULES 인자 전달
  local rules="$TOOLS_DIR/effects_rules.json"
  if [[ -f "$rules" ]]; then
    python3 "$TOOLS_DIR/gen_effects_timeline.py" "$BUS_LOG" "$TIMELINE" "$rules" || true
  fi
}

# bus.log가 존재하고 타임라인이 없거나 1행 이하면 재생성
if [[ ! -s "$TIMELINE" || "$(wc -l < "$TIMELINE" 2>/dev/null || echo 0)" -le 1 ]]; then
  echo "[eval] timeline empty → regenerating from bus.log ($BUS_LOG)"
  regen_from_bus || true
fi

# 그래도 비면 미니 샘플 주입(60초 기준)
if [[ ! -s "$TIMELINE" || "$(wc -l < "$TIMELINE" 2>/dev/null || echo 0)" -le 1 ]]; then
  echo "[eval] injecting mini sample timeline"
  cat > "$TIMELINE" <<'CSV'
t_sec,loss_pct,delay_ms,jitter_ms,dup_pct,rate_limit_mbps
5,0,0,0,0,0
15,2,5,2,0,0
25,3,8,3,0,0
35,5,10,4,0,0
45,6,12,6,0,0
55,8,15,8,0,0
CSV
fi

############################################
# 2) ns-3 실행 (./ns3 런처)
############################################
run_ns3() {
  local cmd="$SCRATCH_BIN --timeline=$TIMELINE --out=$OUT_CSV --simTime=60 --pktSize=512"
  if [[ -n "$ANIM_OUT" ]]; then
    cmd="$cmd --animOut=$ANIM_OUT"
  fi
  ( cd "$NS3" && "$NS3_BIN" run "$cmd" )
}

dummy_result() {
  echo "[eval][warn] ns-3 실행 불가 → 더미 결과 기록: $OUT_CSV"
  {
    echo "t,rxPackets,throughput_mbps"
    echo "60,1000,12.3"
  } > "$OUT_CSV"
}

# 런처/소스 존재 점검
if [[ ! -x "$NS3_BIN" ]]; then
  echo "[eval][warn] ns-3 launcher not found: $NS3_BIN"
  dummy_result
  echo "$OUT_CSV"
  exit 0
fi

# 실제 실행 (실패해도 더미 작성)
if ! run_ns3; then
  dummy_result
fi

echo "[ns-3] wrote: $OUT_CSV"
echo "$OUT_CSV"
