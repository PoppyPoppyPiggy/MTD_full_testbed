#!/usr/bin/env bash
# wifi_network_discovery.sh — 드론 WiFi 네트워크 발견 및 열거
set -euo pipefail
BASE="$(cd -- "$(dirname "$0")/.." && pwd)"
. "$BASE/sh_core/lpc_core.sh"
. "$BASE/sh_core/lpc_bus.sh"

act(){
  local intensity="${INTENSITY:-low}"
  case "$intensity" in
    low)
      # 조용한 패시브 스캔
      bus_emit "recon" "passive_wifi_scan interfaces=['wlan0']"
      effect_emit "detection_risk +1%"
      ;;
    medium)
      # 액티브 스캔
      bus_emit "recon" "active_wifi_scan target_ssid='Drone_Wifi'"
      effect_emit "detection_risk +3%"
      effect_emit "link_jitter +0.5ms"
      ;;
    high)
      # 공격적 열거
      bus_emit "recon" "aggressive_scan handshake_capture=true"
      effect_emit "detection_risk +8%"
      effect_emit "packet_loss +0.2%"
      ;;
  esac
}

lpc_loop act
