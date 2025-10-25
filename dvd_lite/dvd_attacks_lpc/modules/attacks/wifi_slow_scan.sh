#!/usr/bin/env bash

# --- Process Command Line Arguments ---
# Example: Assign first arg to INTENSITY, default 'medium'
# INTENSITY="${1:-medium}"
# Example: Assign second arg to DURATION_SECONDS, default '30'
# DURATION_SECONDS="${2:-30}"
# echo "Parameters: Intensity=$INTENSITY, Duration=$DURATION_SECONDS"
# Add more parameter processing as needed for the specific script
# ------------------------------------

set -euo pipefail
BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "$BASE/00_env_ext.sh" 2>/dev/null || true
# 로거 유틸
if [[ -f "$BASE/sh_core/bus2.sh" ]]; then . "$BASE/sh_core/bus2.sh"; else ts(){ date +%s.%3N; }; log_bus(){ echo "t=$(ts) $*" >> "$BASE/bus/bus.log"; }; fi
DUR="${DURATION_S:-30}"; INTERVAL="${SCAN_INTERVAL_S:-5}"
log_bus EVT=ATTACK_START atk=wifi_slow_scan level=${LV:-low} duration_s=$DUR
end=$(( $(date +%s) + DUR )); tick=0
while (( $(date +%s) < end )); do
  if command -v nmcli >/dev/null 2>&1; then
    out="$(nmcli -t -f SSID,BSSID,CHAN,SIGNAL dev wifi list 2>/dev/null | head -n 20 || true)"
    apn="$(printf "%s\n" "$out" | grep -c ':')"
    log_bus EVT=RECON_WIFI tick=$tick ap_seen=$apn
  else
    log_bus EVT=RECON_WIFI tick=$tick ap_seen=0 note=nmcli_not_found
  fi
  tick=$((tick+1))
  sleep "$INTERVAL"
done
log_bus EVT=ATTACK_END atk=wifi_slow_scan level=${LV:-low}