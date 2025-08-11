#!/usr/bin/env bash
set -euo pipefail
. "$(dirname "$0")/../sh_core/lpc_bus.sh"
. "$(dirname "$0")/../sh_core/netem.sh"

telemetry_trickle(){  # 저율 지터 유도(시뮬 + 선택적 netem)
  bus_emit "telemetry" "trickle_jam target=GCS<->$DVD_MAVLINK_PORT"
  effect_emit link_jitter "+2ms"
  # 실제 연결 포인트(옵션): GCS 측 링크에 소폭 지연/지터
  netem_apply "$DVD_C_GCS" "delay 2ms 1ms loss 0.05%"
}
telemetry_burst_drop(){
  bus_emit "telemetry" "burst_drop target=GCS<->$DVD_MAVLINK_PORT"
  effect_emit packet_loss "+0.5%"
  netem_apply "$DVD_C_GCS" "loss 0.5% 25%"
}
