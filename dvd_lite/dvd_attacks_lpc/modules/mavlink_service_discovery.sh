#!/usr/bin/env bash
# mavlink_service_discovery.sh — MAVLink 포트 스캔 및 서비스 식별
set -euo pipefail
BASE="$(cd -- "$(dirname "$0")/.." && pwd)"
. "$BASE/sh_core/lpc_core.sh"
. "$BASE/sh_core/lpc_bus.sh"

act(){
  local intensity="${INTENSITY:-low}"
  local target_ip="${DVD_TARGET_IP:-10.13.0.2}"
  
  case "$intensity" in
    low)
      # 기본 포트 확인
      bus_emit "recon" "port_scan target=$target_ip ports=[14550,14551,5760]"
      effect_emit "detection_risk +1%"
      ;;
    medium)
      # MAVLink 버전 탐지
      bus_emit "recon" "mavlink_version_scan target=$target_ip"
      effect_emit "detection_risk +2%"
      effect_emit "telemetry_delay +0.3ms"
      ;;
    high)
      # 컴포넌트 열거
      bus_emit "recon" "component_enumeration autopilot_version=true"
      effect_emit "detection_risk +5%"
      effect_emit "cpu_load +2%"
      ;;
  esac
}

lpc_loop act
