#!/usr/bin/env bash
# camera_stream_discovery.sh — RTSP/HTTP 비디오 스트림 탐지
set -euo pipefail
BASE="$(cd -- "$(dirname "$0")/.." && pwd)"
. "$BASE/sh_core/lpc_core.sh"
. "$BASE/sh_core/lpc_bus.sh"

act(){
  local intensity="${INTENSITY:-low}"
  
  case "$intensity" in
    low)
      # RTSP 포트 스캔
      bus_emit "recon" "rtsp_scan ports=[554,8554,1935]"
      effect_emit "detection_risk +1%"
      ;;
    medium)
      # 스트림 메타데이터 수집
      bus_emit "recon" "stream_metadata codec_info=true resolution=true"
      effect_emit "detection_risk +3%"
      effect_emit "bandwidth_usage +0.1mbps"
      ;;
    high)
      # 실시간 프레임 캡처
      bus_emit "recon" "frame_capture count=10 stealth=false"
      effect_emit "detection_risk +7%"
      effect_emit "bandwidth_usage +2.5mbps"
      ;;
  esac
}

lpc_loop act
