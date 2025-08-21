#!/usr/bin/env bash
# mavlink_packet_injection.sh — 악성 MAVLink 메시지 주입
set -euo pipefail
BASE="$(cd -- "$(dirname "$0")/.." && pwd)"
. "$BASE/sh_core/lpc_core.sh"
. "$BASE/sh_core/lpc_bus.sh"

act(){
  local intensity="${INTENSITY:-low}"
  
  case "$intensity" in
    low)
      # 하트비트 스푸핑
      bus_emit "protocol" "heartbeat_spoof component_id=fake"
      effect_emit "protocol_confusion +1%"
      effect_emit "telemetry_noise +0.1%"
      ;;
    medium)
      # 파라미터 변조 시도
      bus_emit "protocol" "param_injection type=set fake_values=true"
      effect_emit "param_drift +2%"
      effect_emit "system_confusion +5%"
      ;;
    high)
      # 미션 명령 주입
      bus_emit "protocol" "mission_injection waypoint_override=true malicious=true"
      effect_emit "mission_corruption +15%"
      effect_emit "flight_path_deviation +3m"
      effect_emit "safety_risk +8%"
      ;;
  esac
}

lpc_loop act
