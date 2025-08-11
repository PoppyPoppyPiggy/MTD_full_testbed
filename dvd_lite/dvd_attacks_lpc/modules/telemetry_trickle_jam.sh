#!/usr/bin/env bash
set -euo pipefail
BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$BASE/sh_core/lpc_core.sh"; . "$BASE/primitives/telemetry_stub.sh"

# Attack Point: GCS 컨테이너 ↔ MAVLink UDP (14550/14551)
nibble(){ telemetry_trickle; }
on_ip_shuffle(){ apply_backoff; }   # MTD 발생 시 즉시 둔화
main(){ log "[telemetry_trickle_jam] GCS=$DVD_C_GCS dst=$DVD_MAVLINK_PORT"; lpc_loop nibble; }
main "$@"
