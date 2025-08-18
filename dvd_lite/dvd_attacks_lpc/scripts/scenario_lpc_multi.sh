#!/usr/bin/env bash
# scripts/scenario_lpc_multi.sh
set -Eeuo pipefail

# ============= 공통 경로/환경 =============
BASE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$BASE_DIR"

# 00_env.sh가 없으면 중단
if [[ ! -f 00_env.sh ]]; then
  echo "[FATAL] 00_env.sh not found in $BASE_DIR" >&2
  exit 1
fi
# 개발/프로덕션 모드(기본: 개발)
: "${MTD_DEV_MODE:=1}"
export MTD_DEV_MODE
source 00_env.sh

# 선택 프로파일(없어도 무시)
if [[ -f "$(dirname "$0")/options.d/profile_stealth.env" ]]; then
  # shellcheck disable=SC1090
  source "$(dirname "$0")/options.d/profile_stealth.env"
fi

OUT_DIR="$BASE_DIR/attack_output"
mkdir -p "$OUT_DIR"

# ============= 파라미터 (환경변수로 덮어쓰기 가능) =============
ATTACK_DURATION="${ATTACK_DURATION:-60}"
OVERLAP_DELAY="${OVERLAP_DELAY:-15}"

# ============= 유틸 =============
ts() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }
bus_line() { echo "[$(ts)] [$1] $2" >> "$OUT_DIR/bus.log"; }

# 모듈 실행 헬퍼: run_mod <module_script> <intensity> <duration>
run_mod() {
  local mod="$1" inten="$2" dur="$3"
  if [[ ! -x "$BASE_DIR/modules/$mod" ]]; then
    echo "[WARN] module not found or not executable: modules/$mod" >&2
    return 1
  fi
  bus_line "scenario" "start module=$mod intensity=$inten dur=${dur}s"
  DUR="$dur" INTENSITY="$inten" \
    "$BASE_DIR/modules/$mod" \
      >> "$OUT_DIR/bus.log" 2>> "$OUT_DIR/bus.log" &
  echo $!
}

# 종료시 자식 프로세스 정리
PIDS=()
cleanup() {
  for pid in "${PIDS[@]:-}"; do
    kill "$pid" 2>/dev/null || true
  done
}
trap cleanup EXIT INT TERM

echo "=== LPC 다중 공격 시나리오 시작 ==="
bus_line "scenario" "LPC multi-attack begin"

echo "1단계: 초기 정찰"
PID_WIFI=$(run_mod "wifi_slow_scan.sh" "low" "$ATTACK_DURATION") || true
[[ -n "${PID_WIFI:-}" ]] && PIDS+=("$PID_WIFI")

sleep "$OVERLAP_DELAY"
echo "2단계: 텔레메트리 간섭"
PID_TELEM=$(run_mod "telemetry_trickle_jam.sh" "low" "$ATTACK_DURATION") || true
[[ -n "${PID_TELEM:-}" ]] && PIDS+=("$PID_TELEM")

sleep "$OVERLAP_DELAY"
echo "3단계: 파라미터 드리프트"
PID_PARAM=$(run_mod "mavlink_param_drift.sh" "medium" "$ATTACK_DURATION") || true
[[ -n "${PID_PARAM:-}" ]] && PIDS+=("$PID_PARAM")

sleep "$OVERLAP_DELAY"
echo "4단계: GPS 교란"
PID_GPS=$(run_mod "gps_slow_spoof.sh" "medium" "$ATTACK_DURATION") || true
[[ -n "${PID_GPS:-}" ]] && PIDS+=("$PID_GPS")

# 모든 모듈 종료 대기
for pid in "${PIDS[@]:-}"; do
  wait "$pid" || true
done

bus_line "scenario" "LPC multi-attack end"
echo "=== LPC 다중 공격 시나리오 완료 ==="

# 자동 평가(타임라인→윈도우→ns-3) 트리거
echo "자동 평가..."
bash "$BASE_DIR/tools/auto_eval.sh"
