#!/usr/bin/env bash
# telemetry_exfiltration.sh — 민감한 비행 데이터 수집
set -euo pipefail
BASE="$(cd -- "$(dirname "$0")/.." && pwd)"
. "$BASE/sh_core/lpc_core.sh"
. "$BASE/sh_core/lpc_bus.sh"

act(){
  local intensity="${INTENSITY:-low}"
  
  case "$intensity" in
    low)
      # 기본 텔레메트리 수집
      bus_emit "exfil" "telemetry_capture data_types=['position','altitude'] duration=5s"
      effect_emit "data_exposure +low"
      effect_emit "privacy_breach +1%"
      ;;
    medium)
      # 확장 데이터 수집
      bus_emit "exfil" "telemetry_harvest data_types=['position','speed','battery','mission'] duration=30s"
      effect_emit "data_exposure +medium"
      effect_emit "privacy_breach +5%"
      effect_emit "bandwidth_usage +0.5mbps"
      ;;
    high)
      # 전체 데이터 스트림 탈취
      bus_emit "exfil" "full_telemetry_theft real_time=true store_local=true duration=300s"
      effect_emit "data_exposure +high"
      effect_emit "privacy_breach +20%"
      effect_emit "bandwidth_usage +2mbps"
      effect_emit "storage_consumption +100mb"
      ;;
  esac
}

lpc_loop act
