#!/usr/bin/env bash
# Watch IP change of $DVD_TARGET_IF inside the container (not docker inspect)
set -euo pipefail
BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$BASE/00_env.sh"; . "$BASE/sh_core/lpc_bus.sh"; . "$BASE/cti/cti_store.sh"

: "${WATCH_INT:=1}"

get_ip(){
  docker exec "$DVD_C_GCS" bash -lc "ip -4 -o addr show dev $DVD_TARGET_IF | awk '{print \$4}' | cut -d/ -f1 | head -n1"
}

main(){
  log "[cti_watch_ip] container=$DVD_C_GCS if=$DVD_TARGET_IF every ${WATCH_INT}s"
  prev="$(cti_get TARGET_IP || true)"
  [ -z "${prev:-}" ] && prev="$(get_ip)"
  [ -n "${prev:-}" ] && cti_set_ip "$prev"
  while true; do
    cur="$(get_ip)"
    if [ -n "${cur:-}" ] && [ "$cur" != "${prev:-}" ]; then
      cti_set_ip "$cur"
      bus_emit "cti" "type=ip_change container=$DVD_C_GCS old=${prev:-none} new=$cur"
      log "[cti_watch_ip] IP change: ${prev:-none} -> $cur"
      prev="$cur"
    fi
    sleep "$WATCH_INT"
  done
}
main "$@"
