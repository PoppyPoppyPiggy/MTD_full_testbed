#!/usr/bin/env bash
# wifi_deauth_attack.sh — WiFi 연결 강제 차단
set -euo pipefail
BASE="$(cd -- "$(dirname "$0")/.." && pwd)"
. "$BASE/sh_core/lpc_core.sh"
. "$BASE/sh_core/lpc_bus.sh"

act(){
  local intensity="${INTENSITY:-low}"
  local target_mac="${DRONE_MAC:-aa:bb:cc:dd:ee:ff}"
  
  case "$intensity" in
    low)
      # 단일 deauth 패킷
      bus_emit "dos" "deauth_single target=$target_mac count=1"
      effect_emit "connection_instability +5%"
      effect_emit "reconnect_delay +1s"
      ;;
    medium)
      # 연속 deauth 공격
      bus_emit "dos" "deauth_burst target=$target_mac count=10 interval=100ms"
      effect_emit "connection_drops +1"
      effect_emit "reconnect_delay +5s"
      effect_emit "link_quality -20%"
      ;;
    high)
      # 지속적 deauth 폭풍
      bus_emit "dos" "deauth_storm target=broadcast duration=30s"
      effect_emit "connection_drops +5"
      effect_emit "reconnect_delay +15s"
      effect_emit "link_quality -60%"
      effect_emit "mission_interruption +1"
      ;;
  esac
}

lpc_loop act
