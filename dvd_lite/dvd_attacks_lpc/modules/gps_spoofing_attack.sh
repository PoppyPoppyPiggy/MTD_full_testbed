#!/usr/bin/env bash
# gps_spoofing_attack.sh — GPS 신호 조작 및 위치 변조
set -euo pipefail
BASE="$(cd -- "$(dirname "$0")/.." && pwd)"
. "$BASE/sh_core/lpc_core.sh"
. "$BASE/sh_core/lpc_bus.sh"

act(){
  local intensity="${INTENSITY:-low}"
  local step="${LPC_STEP:-0.5}"
  
  case "$intensity" in
    low)
      # 미세한 위치 편향
      local drift=$(awk -v s="$step" 'BEGIN{printf "%.2f", s*0.1}')
      bus_emit "protocol" "gps_bias lat_offset=${drift}m"
      effect_emit "position_drift +${drift}m"
      effect_emit "gps_accuracy -5%"
      ;;
    medium)
      # 중간 수준 스푸핑
      local drift=$(awk -v s="$step" 'BEGIN{printf "%.2f", s*0.5}')
      bus_emit "protocol" "gps_spoof lat_drift=${drift}m coordinated=true"
      effect_emit "position_drift +${drift}m"
      effect_emit "mission_bias +${drift}m"
      effect_emit "gps_accuracy -15%"
      ;;
    high)
      # 공격적 위치 조작
      local drift=$(awk -v s="$step" 'BEGIN{printf "%.2f", s*2.0}')
      bus_emit "protocol" "gps_hijack target_location='spoofed' drift=${drift}m"
      effect_emit "position_drift +${drift}m"
      effect_emit "mission_bias +${drift}m"
      effect_emit "gps_accuracy -40%"
      effect_emit "navigation_error +25%"
      ;;
  esac
}

lpc_loop act
