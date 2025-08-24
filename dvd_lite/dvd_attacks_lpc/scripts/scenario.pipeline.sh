#!/usr/bin/env bash
#
# MTD Testbed 원클릭 시나리오 파이프라인
# - 공격/MTD 실행 → 타임라인 → (옵션) ns-3 → 점수/데이터셋 → 결과 아카이브
# - 자주 쓰는 프리셋/매트릭스/비교/웹UI 기동까지 포함
#
# 사용법(예시):
#   bash scripts/scenario_pipeline.sh quick
#   bash scripts/scenario_pipeline.sh standard
#   bash scripts/scenario_pipeline.sh aggressive
#   bash scripts/scenario_pipeline.sh stream
#   bash scripts/scenario_pipeline.sh rebuild
#   bash scripts/scenario_pipeline.sh compare    # 직전 2개 아카이브 비교 요약
#   bash scripts/scenario_pipeline.sh sweep      # 공격×강도 매트릭스(빠른 샘플)
#   bash scripts/scenario_pipeline.sh webui      # WebUI 기동
#   bash scripts/scenario_pipeline.sh help
#
set -euo pipefail

# ---------- 경로/환경 ----------
BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"            # .../dvd_attacks_lpc
ROOT="$(cd "$BASE/../.." && pwd)"                                  # .../MTD_full_testbed
OUT="$BASE/attack_output"
TOOLS="$BASE/tools"
SCRIPTS="$BASE/scripts"
NS3ROOT="${NS3ROOT:-$ROOT/ns-3.45/ns-3-dev}"

# Python venv 우선순위: ../mtd_env311 -> webui/.venv -> ../mtd_env
try_activate_venv() {
  local tried=0
  if [[ -f "$ROOT/mtd_env311/bin/activate" ]]; then
    # 권장 3.11 venv
    # shellcheck disable=SC1091
    source "$ROOT/mtd_env311/bin/activate"; tried=1
  elif [[ -f "$BASE/webui/.venv/bin/activate" ]]; then
    # WebUI venv
    # shellcheck disable=SC1091
    source "$BASE/webui/.venv/bin/activate"; tried=1
  elif [[ -f "$ROOT/mtd_env/bin/activate" ]]; then
    # 기존 venv(3.13일 수 있어 pandas 빌드 주의)
    # shellcheck disable=SC1091
    source "$ROOT/mtd_env/bin/activate"; tried=1
  fi
  if [[ $tried -eq 0 ]]; then
    echo "[WARN] Python venv 미발견. 시스템 python을 사용합니다."
  else
    echo "[*] venv 활성화: $(python3 -V 2>/dev/null || python -V 2>/dev/null)"
  fi
}

ensure_outputs() {
  mkdir -p "$OUT"
  : > "$OUT/run.log"
  for f in bus.log effect_timeline.csv ns3_metrics.csv score.json dataset.csv cti_targets.env; do
    touch "$OUT/$f"
  done
}

need_cmd() { command -v "$1" >/dev/null 2>&1 || { echo "[ERR] '$1' 미설치"; exit 2; }; }

stamp() { date +"%Y%m%d_%H%M%S"; }

archive_results() {
  local tag="$1"
  local ts; ts="$(stamp)"
  local dst="$OUT/archive/${ts}_${tag}"
  mkdir -p "$dst"
  cp -f "$OUT"/{bus.log,effect_timeline.csv,ns3_metrics.csv,score.json,dataset.csv,cti_targets.env,run.log} "$dst" 2>/dev/null || true
  [[ -f "$OUT/netanim.xml" ]] && cp -f "$OUT/netanim.xml" "$dst/"
  echo "$dst"
}

emit_scenario_tag() {
  local tag="$1"
  local now_ms
  now_ms="$(date +%s%3N)"
  printf "%s\t%s\t%s\n" "$now_ms" "scenario" "tag=${tag}" >> "$OUT/bus.log"
}

# ---------- 실행 래퍼 ----------
run_collect() {
  local tag="$1"; shift
  local N="${N:-80}"
  local RUN_NS3="${RUN_NS3:-1}"
  local ATK_RATE_MBPS="${ATK_RATE_MBPS:-30}"
  local SIM_TIME="${SIM_TIME:-60}"
  local PORT_HOP_PROB="${PORT_HOP_PROB:-50}"
  local FOLLOW_FLOOD_PROB="${FOLLOW_FLOOD_PROB:-50}"
  local CTI_WAIT_S="${CTI_WAIT_S:-0.5}"

  echo "[*] collect 시작(tag=$tag) N=$N RUN_NS3=$RUN_NS3 ATK_RATE=$ATK_RATE_MBPS HOP=$PORT_HOP_PROB FLOOD=$FOLLOW_FLOOD_PROB CTI_WAIT=$CTI_WAIT_S"
  : > "$OUT/run.log"
  emit_scenario_tag "$tag"

  # 환경변수는 auto_collect.sh 가 그대로 읽음
  N="$N" RUN_NS3="$RUN_NS3" ATK_RATE_MBPS="$ATK_RATE_MBPS" SIM_TIME="$SIM_TIME" \
  PORT_HOP_PROB="$PORT_HOP_PROB" FOLLOW_FLOOD_PROB="$FOLLOW_FLOOD_PROB" CTI_WAIT_S="$CTI_WAIT_S" \
  bash "$SCRIPTS/auto_collect.sh" | tee -a "$OUT/run.log"

  # 아카이브
  local dest; dest="$(archive_results "$tag")"
  echo "[OK] 아카이브: $dest"
}

run_stream_bg() {
  echo "[*] auto_stream 백그라운드 시작"
  nohup bash "$SCRIPTS/auto_stream.sh" >> "$OUT/run.log" 2>&1 &
  echo $! > "$OUT/stream.pid"
  echo "[OK] PID=$(cat "$OUT/stream.pid")"
}

stop_stream_bg() {
  if [[ -f "$OUT/stream.pid" ]]; then
    kill "$(cat "$OUT/stream.pid")" 2>/dev/null || true
    rm -f "$OUT/stream.pid"
    echo "[OK] stream 종료 요청"
  else
    echo "[INFO] stream.pid 없음"
  fi
}

rebuild_timeline() {
  echo "[*] bus.log -> effect_timeline.csv 재생성"
  python3 "$TOOLS/gen_effects_timeline.py" "$OUT/bus.log" \
    -o "$OUT/effect_timeline.csv" --rules "$TOOLS/effects_rules.json" --mode hold | tee -a "$OUT/run.log"
}

run_ns3_once() {
  echo "[*] ns-3 실행 (metrics 업데이트)"
  need_cmd "$NS3ROOT/ns3" || true
  pushd "$NS3ROOT" >/dev/null
  ./ns3 run "scratch/drone_lpc_eval --timeline=$ROOT/dvd_lite/dvd_attacks_lpc/attack_output/effect_timeline.csv --simTime=${SIM_TIME:-60} --animMaxPkts=8000000 --atkRateMbps=${ATK_RATE_MBPS:-30}" | tee -a "$OUT/run.log" || true
  popd >/dev/null
}

brief_summary() {
  echo "---- [NS3 METRICS] ----"
  [[ -s "$OUT/ns3_metrics.csv" ]] && column -s, -t "$OUT/ns3_metrics.csv" | sed -n '1,20p' || echo "(없음)"
  echo "---- [SCORE] ----"
  if command -v jq >/dev/null 2>&1 && [[ -s "$OUT/score.json" ]]; then
    jq '{CTI,MTD,NS3}' "$OUT/score.json" || cat "$OUT/score.json"
  else
    cat "$OUT/score.json" 2>/dev/null || echo "(없음)"
  fi
}

compare_last_two_archives() {
  local dir="$OUT/archive"
  [[ -d "$dir" ]] || { echo "[ERR] archive 디렉토리 없음: $dir"; exit 2; }
  local a b
  readarray -t arr < <(ls -1 "$dir" | sort)
  local n="${#arr[@]}"
  (( n >= 2 )) || { echo "[ERR] 비교할 아카이브가 2개 미만"; exit 2; }
  a="${dir}/${arr[n-2]}"; b="${dir}/${arr[n-1]}"
  echo "[*] 비교: "
  echo " A: $a"
  echo " B: $b"
  echo "---- throughput_avg ----"
  awk -F, '$1=="throughput_avg"{print "A:",$2,"Mbps"}' "$a/ns3_metrics.csv"
  awk -F, '$1=="throughput_avg"{print "B:",$2,"Mbps"}' "$b/ns3_metrics.csv"
  echo "---- delay_avg ----"
  awk -F, '$1=="delay_avg"{print "A:",$2,"s"}' "$a/ns3_metrics.csv"
  awk -F, '$1=="delay_avg"{print "B:",$2,"s"}' "$b/ns3_metrics.csv"
  if command -v jq >/dev/null 2>&1; then
    echo "---- CTI detect_latency_mean_s ----"
    echo -n "A: "; jq -r '.CTI.detect_latency_mean_s // empty' "$a/score.json"
    echo -n "B: "; jq -r '.CTI.detect_latency_mean_s // empty' "$b/score.json"
    echo "---- MTD disruption_window_mean_s ----"
    echo -n "A: "; jq -r '.MTD.disruption_window_mean_s // empty' "$a/score.json"
    echo -n "B: "; jq -r '.MTD.disruption_window_mean_s // empty' "$b/score.json"
  fi
}

launch_webui() {
  echo "[*] WebUI 기동: http://127.0.0.1:5001"
  pushd "$BASE/webui" >/dev/null
  if [[ -f ".venv/bin/activate" ]]; then
    # shellcheck disable=SC1091
    source ".venv/bin/activate"
  fi
  python3 app.py
  popd >/dev/null
}

# ---------- 프리셋 ----------
preset_quick() {
  # 빠른 데이터 적재(공격만, ns-3 생략)
  export N=300 RUN_NS3=0 PORT_HOP_PROB=30 FOLLOW_FLOOD_PROB=60 CTI_WAIT_S=0.4
  run_collect "quick"
  brief_summary
}

preset_standard() {
  export N=80 RUN_NS3=1 ATK_RATE_MBPS=30 PORT_HOP_PROB=50 FOLLOW_FLOOD_PROB=50 SIM_TIME=60 CTI_WAIT_S=0.5
  run_collect "standard"
  brief_summary
}

preset_aggressive() {
  export N=50 RUN_NS3=1 ATK_RATE_MBPS=60 PORT_HOP_PROB=20 FOLLOW_FLOOD_PROB=80 SIM_TIME=60 CTI_WAIT_S=0.4
  run_collect "aggressive"
  brief_summary
}

# 공격×강도 매트릭스(샘플): 라운드/시간 부담 낮춤
preset_sweep() {
  # 조합을 바꾸고 싶으면 아래 배열 수정
  local -a atk_pct=("20" "50" "80")     # FOLLOW_FLOOD_PROB
  local -a hop_pct=("20" "50" "70")     # PORT_HOP_PROB
  local -a atk_rate=("10" "30" "60")    # ATK_RATE_MBPS

  for fprob in "${atk_pct[@]}"; do
    for hprob in "${hop_pct[@]}"; do
      for rate in "${atk_rate[@]}"; do
        export N=40 RUN_NS3=1 ATK_RATE_MBPS="$rate" PORT_HOP_PROB="$hprob" FOLLOW_FLOOD_PROB="$fprob" SIM_TIME=60 CTI_WAIT_S=0.5
        local tag="sweep_f${fprob}_h${hprob}_r${rate}"
        run_collect "$tag"
      done
    done
  done
  echo "[OK] sweep 완료. archive/ 에 각 조합 폴더 생성됨."
}

# ---------- 메인 ----------
main() {
  try_activate_venv
  need_cmd bash
  need_cmd python3
  ensure_outputs

  local cmd="${1:-help}"
  case "$cmd" in
    quick)      preset_quick ;;
    standard)   preset_standard ;;
    aggressive) preset_aggressive ;;
    sweep)      preset_sweep ;;
    stream)     run_stream_bg ;;
    stop)       stop_stream_bg ;;
    rebuild)    rebuild_timeline; run_ns3_once; brief_summary ;;
    compare)    compare_last_two_archives ;;
    webui)      launch_webui ;;
    help|*)     cat <<'EOF'
사용법:
  quick        - 빠른 데이터 적재(N=300, NS-3 생략)
  standard     - 표준 시나리오(N=80, NS-3 포함)
  aggressive   - 공격적 시나리오(N=50, flood↑, NS-3 포함)
  sweep        - 공격×강도×레이트 매트릭스(샘플)
  stream       - 무한 스트림 실행(백그라운드), 종료는 'stop'
  stop         - 스트림 종료
  rebuild      - bus.log→timeline 재생성 + NS-3 1회 + 요약 표시
  compare      - 직전 2개 아카이브 비교 요약
  webui        - WebUI 기동(127.0.0.1:5001)

환경변수(옵션, 프리셋 오버라이드 가능):
  N, RUN_NS3(0|1), ATK_RATE_MBPS, SIM_TIME, PORT_HOP_PROB, FOLLOW_FLOOD_PROB, CTI_WAIT_S, NS3ROOT

예:
  N=120 PORT_HOP_PROB=70 FOLLOW_FLOOD_PROB=30 bash scripts/scenario_pipeline.sh standard
EOF
    ;;
  esac
}
main "$@"
