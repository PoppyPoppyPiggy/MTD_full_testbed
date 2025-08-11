#!/usr/bin/env bash
set -euo pipefail
. "$(dirname "$0")/../sh_core/lpc_bus.sh"

wifi_safe_recon(){ bus_emit "wifi_recon" "ap=$DVD_IP_CC/24 ssid=Drone_Wifi"; }
wifi_safe_probe(){ bus_emit "wifi_probe" "ap_touch"; effect_emit link_load "+1pps"; }
