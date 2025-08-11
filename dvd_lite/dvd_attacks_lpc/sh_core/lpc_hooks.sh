#!/usr/bin/env bash
set -euo pipefail
. "$(dirname "$0")/lpc_core.sh"

watch_mtd_events(){
  [[ -f "$MTD_LOG" ]] || { log "MTD_LOG not found: $MTD_LOG"; return 0; }
  tail -F "$MTD_LOG" | while read -r line; do
    case "$line" in
      *IP_SHUFFLE*) on_ip_shuffle ;;
      *SERVICE_MIGRATION*) on_service_migration ;;
      *PORT_SHUFFLE*) on_port_shuffle ;;
    esac
  done
}
