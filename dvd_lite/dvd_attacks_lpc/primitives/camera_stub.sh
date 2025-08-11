#!/usr/bin/env bash
set -euo pipefail
. "$(dirname "$0")/../sh_core/lpc_bus.sh"

camera_rtsp_tease(){
  bus_emit "camera" "rtsp_toggle"
  effect_emit video_pipeline "restart_hint"
  # TODO: docker exec dvd-cc systemctl restart mock-rtsp (모의)
}
