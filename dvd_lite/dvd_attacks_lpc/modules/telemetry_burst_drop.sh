#!/usr/bin/env bash
set -euo pipefail
BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$BASE/sh_core/lpc_core.sh"; . "$BASE/primitives/telemetry_stub.sh"

# Attack Point: GCS 링크에 짧은 burst loss
nibble(){ telemetry_burst_drop; }
on_ip_shuffle(){ apply_backoff; }
main(){ log "[telemetry_burst_drop] GCS=$DVD_C_GCS dst=$DVD_MAVLINK_PORT"; lpc_loop nibble; }
main "$@"
