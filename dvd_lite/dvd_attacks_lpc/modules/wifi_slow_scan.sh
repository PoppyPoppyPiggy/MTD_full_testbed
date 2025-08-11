#!/usr/bin/env bash
set -euo pipefail
BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$BASE/sh_core/lpc_core.sh"; . "$BASE/primitives/wifi_stub.sh"

# Attack Point: Companion AP(192.168.13.1, SSID=Drone_Wifi)
recon(){ wifi_safe_recon; }; probe(){ wifi_safe_probe; }
nibble(){ wifi_safe_probe; }
main(){ log "[wifi_slow_scan] AP=$DVD_IP_CC/Drone_Wifi"; recon; probe; lpc_loop nibble; }
main "$@"
