#!/usr/bin/env bash
# sensor_fusion_noise.sh — EKF residual/상관관계에 저율 잡음(효과 로깅)
set -euo pipefail
BASE="$(cd -- "$(dirname "$0")/.." && pwd)"
. "$BASE/sh_core/lpc_core.sh"
. "$BASE/sh_core/lpc_bus.sh"

act(){
  local s="${LPC_STEP:-0.02}"
  local nz="${LPC_NOISE:-0.20}"
  local sign; sign=$(( (RANDOM % 2) * 2 - 1 ))
  local scale; scale=$(awk -v n="$nz" 'BEGIN{srand(); print 1.0 + (rand()*2*n - n)}')
  local resid; resid=$(awk -v st="$s" -v sc="$scale" -v sg="$sign" 'BEGIN{printf "%.4f", st*sc*sg}')
  # 잔차/일관성에 작은 hit
  effect_emit "sensor_residual ${resid}"
  effect_emit "mission_bias ${resid}"
}

lpc_loop act
