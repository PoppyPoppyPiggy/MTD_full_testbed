#!/usr/bin/env bash
# safe_rth_penalty.sh — RTH(귀환) 트리거 여유도(%)를 미세하게 낮춤(효과 로깅)
set -euo pipefail
BASE="$(cd -- "$(dirname "$0")/.." && pwd)"
. "$BASE/sh_core/lpc_core.sh"
. "$BASE/sh_core/lpc_bus.sh"

act(){
  local s="${LPC_STEP:-0.02}"   # 기본 0.02 → 2%p 취급
  local nz="${LPC_NOISE:-0.20}"
  local scale; scale=$(awk -v n="$nz" 'BEGIN{srand(); print 1.0 + (rand()*2*n - n)}')
  local p; p=$(awk -v st="$s" -v sc="$scale" 'BEGIN{printf "%.2f", st*sc*100.0}')
  # 여유도를 '감소'로 가정 → 음수 기호
  effect_emit "rth_margin -${p}%"
}

lpc_loop act
