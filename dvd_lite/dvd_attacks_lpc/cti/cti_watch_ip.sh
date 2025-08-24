#!/usr/bin/env bash
# Defender의 IP Shuffle(MTD)을 능동 추적: docker inspect로 컨테이너 IP 변화 감지
set -euo pipefail
BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$BASE/00_env.sh"; . "$BASE/sh_core/lpc_bus.sh"; . "$BASE/cti/cti_store.sh"

: "${WATCH_INT:=1}"   # polling 주기(s)

get_ip(){
  docker inspect -f '{{range.NetworkSettings.Networks}}{{.IPAddress}} {{end}}' "$DVD_C_GCS" 2>/dev/null | awk '{print $1}'
}

main(){
  log "[cti_watch_ip] watching container=$DVD_C_GCS every ${WATCH_INT}s"
  prev="$(cti_get TARGET_IP)"
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
