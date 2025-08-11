#!/usr/bin/env bash
set -euo pipefail
BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$BASE/sh_core/lpc_core.sh"; . "$BASE/primitives/mavlink_stub.sh"

# Attack Point: GCS 모드 전이 관찰/간헐 자극(시뮬)
nibble(){ mav_mode_tease; }
on_ip_shuffle(){ apply_backoff; mav_rebind; }
main(){ log "[mavlink_mode_tease]"; lpc_loop nibble; }
main "$@"
