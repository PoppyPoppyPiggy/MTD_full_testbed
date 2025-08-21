#!/usr/bin/env bash
# firmware_upload_attack.sh — 펌웨어 업데이트 과정 악용
set -euo pipefail
BASE="$(cd -- "$(dirname "$0")/.." && pwd)"
. "$BASE/sh_core/lpc_core.sh"
. "$BASE/sh_core/lpc_bus.sh"

act(){
  local intensity="${INTENSITY:-low}"
  
  case "$intensity" in
    low)
      # 업로드 과정 모니터링
      bus_emit "firmware" "upload_monitor passive=true"
      effect_emit "firmware_exposure +low"
      effect_emit "update_delay +5s"
      ;;
    medium)
      # 업로드 간섭
      bus_emit "firmware" "upload_interference corruption=5% delay=true"
      effect_emit "firmware_corruption +5%"
      effect_emit "update_failure_risk +15%"
      effect_emit "update_delay +30s"
      ;;
    high)
      # 악성 펌웨어 주입
      bus_emit "firmware" "malware_injection payload=backdoor persistence=true"
      effect_emit "firmware_compromise +100%"
      effect_emit "system_integrity -80%"
      effect_emit "persistent_access +enabled"
      ;;
  esac
}

lpc_loop act
