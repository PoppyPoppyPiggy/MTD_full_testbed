#!/usr/bin/env bash
# flight_plan_injection.sh — 악성 웨이포인트 삽입
set -euo pipefail
BASE="$(cd -- "$(dirname "$0")/.." && pwd)"
. "$BASE/sh_core/lpc_core.sh"
. "$BASE/sh_core/lpc_bus.sh"

act(){
  local intensity="${INTENSITY:-low}"
  
  case "$intensity" in
    low)
      # 웨이포인트 미세 조정
      bus_emit "injection" "waypoint_nudge offset=1m stealthy=true"
      effect_emit "waypoint_drift +1m"
      effect_emit "mission_accuracy -2%"
      ;;
    medium)
      # 추가 웨이포인트 삽입
      bus_emit "injection" "waypoint_insert count=2 deviation=5m"
      effect_emit "waypoint_drift +5m"
      effect_emit "mission_time +30s"
      effect_emit "fuel_consumption +3%"
      ;;
    high)
      # 미션 하이재킹
      bus_emit "injection" "mission_hijack replace_all=true malicious_route=true"
      effect_emit "mission_corruption +80%"
      effect_emit "flight_path_deviation +50m"
      effect_emit "safety_violation +1"
      ;;
  esac
}

lpc_loop act
