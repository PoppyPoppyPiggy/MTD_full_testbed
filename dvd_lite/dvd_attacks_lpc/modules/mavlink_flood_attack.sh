#!/usr/bin/env bash
# mavlink_flood_attack.sh — MAVLink 서비스 과부하 공격
set -euo pipefail
BASE="$(cd -- "$(dirname "$0")/.." && pwd)"
. "$BASE/sh_core/lpc_core.sh"
. "$BASE/sh_core/lpc_bus.sh"

act(){
  local intensity="${INTENSITY:-low}"
  
  case "$intensity" in
    low)
      # 저율 플러딩
      bus_emit "dos" "mavlink_flood rate=100pps duration=2s"
      effect_emit "cpu_load +5%"
      effect_emit "response_delay +10ms"
      ;;
    medium)
      # 중간 강도 플러딩
      bus_emit "dos" "mavlink_flood rate=500pps duration=5s"
      effect_emit "cpu_load +15%"
      effect_emit "response_delay +50ms"
      effect_emit "packet_loss +2%"
      ;;
    high)
      # 고강도 DoS
      bus_emit "dos" "mavlink_flood rate=2000pps duration=10s"
      effect_emit "cpu_load +40%"
      effect_emit "response_delay +200ms"
      effect_emit "packet_loss +8%"
      effect_emit "service_degradation +30%"
      ;;
  esac
}

lpc_loop act
