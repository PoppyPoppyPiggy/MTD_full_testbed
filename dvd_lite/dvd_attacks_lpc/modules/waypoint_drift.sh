#!/usr/bin/env bash
# waypoint_drift.sh — 항법 경로점(WP) 미세 편향(효과 로깅 중심)
set -euo pipefail
BASE="$(cd -- "$(dirname "$0")/.." && pwd)"
. "$BASE/sh_core/lpc_core.sh"
. "$BASE/sh_core/lpc_bus.sh"

# drift 1회 적용 액션 (미터 단위 소량 누적)
act(){
  # 편향량: STEP를 기준으로 ±(STEP * (1±NOISE))
  local s="${LPC_STEP:-0.02}"
  local nz="${LPC_NOISE:-0.20}"
  # 부호 무작위, 노이즈 반영
  local sign; sign=$(( (RANDOM % 2) * 2 - 1 ))
  # 노이즈 계수(0.8~1.2 등)
  local scale; scale=$(awk -v n="$nz" 'BEGIN{srand(); print 1.0 + (rand()*2*n - n)}')
  local drift; drift=$(awk -v st="$s" -v sc="$scale" -v sg="$sign" 'BEGIN{printf "%.3f", st*sc*sg}')
  effect_emit "position_drift ${drift}m"
  effect_emit "mission_bias ${drift}m"
}

# 루프 실행
lpc_loop act
