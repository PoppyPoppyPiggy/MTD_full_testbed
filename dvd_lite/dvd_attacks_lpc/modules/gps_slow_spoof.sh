#!/usr/bin/env bash
set -euo pipefail
BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$BASE/sh_core/lpc_core.sh"; . "$BASE/primitives/gps_stub.sh"

# Attack Point: 위치 오프셋(시뮬 → NS-3/Gazebo 브릿지에서 반영)
nibble(){ gps_offset_drift "${LPC_STEP:-0.3}"; }
on_service_migration(){ apply_backoff; }  # 재보정 발견 시 둔화
main(){ log "[gps_slow_spoof]"; lpc_loop nibble; }
main "$@"
