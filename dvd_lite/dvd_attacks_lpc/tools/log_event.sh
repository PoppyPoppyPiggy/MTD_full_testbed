#!/usr/bin/env bash
# dvd_lite/dvd_attacks_lpc/tools/log_event.sh
set -euo pipefail
LOG=${BUS_LOG:-"$(pwd)/dvd_lite/dvd_attacks_lpc/attack_output/bus.log"}
mkdir -p "$(dirname "$LOG")"
ts=$(date +%s)
tag=$1; shift || true
printf "time=%s tag=%s %s\n" "$ts" "$tag" "$*" >> "$LOG"
