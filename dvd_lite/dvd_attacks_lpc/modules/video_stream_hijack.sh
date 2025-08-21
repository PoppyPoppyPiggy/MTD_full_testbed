#!/usr/bin/env bash
# video_stream_hijack.sh — 실시간 비디오 스트림 탈취
set -euo pipefail
BASE="$(cd -- "$(dirname "$0")/.." && pwd)"
. "$BASE/sh_core/lpc_core.sh"
. "$BASE/sh_core/lpc_bus.sh"

act(){
  local intensity="${INTENSITY:-low}"
  
  case "$intensity" in
    low)
      # RTSP 스트림 스니핑
      bus_emit "exfil" "rtsp_sniff passive=true duration=10s"
      effect_emit "video_exposure +low"
      effect_emit "bandwidth_usage +1mbps"
      ;;
    medium)
      # 비디오 녹화
      bus_emit "exfil" "video_capture quality=medium duration=60s"
      effect_emit "video_exposure +medium"
      effect_emit "bandwidth_usage +5mbps"
      effect_emit "storage_consumption +50mb"
      ;;
    high)
      # 스트림 완전 탈취
      bus_emit "exfil" "stream_hijack redirect=true quality=high duration=300s"
      effect_emit "video_exposure +high"
      effect_emit "bandwidth_usage +15mbps"
      effect_emit "stream_degradation +30%"
      effect_emit "privacy_violation +critical"
      ;;
  esac
}

lpc_loop act
