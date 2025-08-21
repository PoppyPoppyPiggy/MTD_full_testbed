#!/usr/bin/env bash
# parameter_manipulation.sh — 중요 시스템 설정 변조
set -euo pipefail
BASE="$(cd -- "$(dirname "$0")/.." && pwd)"
. "$BASE/sh_core/lpc_core.sh"
. "$BASE/sh_core/lpc_bus.sh"

act(){
  local intensity="${INTENSITY:-low}"
  local step="${LPC_STEP:-0.02}"
  
  case "$intensity" in
    low)
      # 비중요 파라미터 조정
      local change=$(awk -v s="$step" 'BEGIN{printf "%.2f", s*5}')
      bus_emit "injection" "param_tweak category=tuning change=${change}%"
      effect_emit "param_drift +${change}%"
      effect_emit "performance_impact +1%"
      ;;
    medium)
      # 중요 파라미터 변조
      local change=$(awk -v s="$step" 'BEGIN{printf "%.2f", s*20}')
      bus_emit "injection" "param_modify category=critical change=${change}%"
      effect_emit "param_drift +${change}%"
      effect_emit "flight_stability -5%"
      effect_emit "control_response_degradation +3%"
      ;;
    high)
      # 안전 임계값 조작
      local change=$(awk -v s="$step" 'BEGIN{printf "%.2f", s*50}')
      bus_emit "injection" "safety_override thresholds=disabled change=${change}%"
      effect_emit "param_drift +${change}%"
      effect_emit "safety_margin -15%"
      effect_emit "critical_parameter_change +1"
      ;;
  esac
}

lpc_loop act
