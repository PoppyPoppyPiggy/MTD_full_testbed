#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd -P)"
BASE="$(cd "$SCRIPT_DIR/.." && pwd -P)"
. "$BASE/00_env_ext.sh"

log(){ printf '%s\n' "$1" >> "$BUS_DVD_LOG"; }

read_bytes(){
  local c="$1"
  # eth0 누적 바이트
  local rx tx ts
  ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  if out="$(docker exec "$c" sh -lc "cat /proc/net/dev 2>/dev/null | sed -n 's/.*eth0:\\s*\\([0-9]\\+\\).*\\s\\([0-9]\\+\\)\\s*$/\\1 \\2/p'")"; then
    rx="$(awk '{print $1}' <<<"$out")"
    tx="$(awk '{print $2}' <<<"$out")"
    jq -n --arg ts "$ts" --arg c "$c" --arg rx "$rx" --arg tx "$tx" \
      '{ts:$ts, evt:"link_bytes", container:$c, rx_bytes:($rx|tonumber), tx_bytes:($tx|tonumber)}'
  fi
}

mode="${1:-loop}"
if [ "$mode" = "once" ]; then
  while read -r name; do
    j="$(read_bytes "$name")"; [ -n "$j" ] && log "$j"
  done < <(docker ps --format '{{.Names}}')
  exit 0
fi

declare -A last_rx last_tx
while true; do
  while read -r name; do
    j="$(read_bytes "$name")" || true
    [ -z "$j" ] && continue
    rx="$(jq -r .rx_bytes <<<"$j")"; tx="$(jq -r .tx_bytes <<<"$j")"
    dr=$(( rx - ${last_rx[$name]:-rx} )); dt=$(( tx - ${last_tx[$name]:-tx} ))
    last_rx[$name]=$rx; last_tx[$name]=$tx
    echo "$j" | jq --argjson dr "$dr" --argjson dt "$dt" '. + {rx_delta: $dr, tx_delta: $dt}' >> "$BUS_DVD_LOG"
  done < <(docker ps --format '{{.Names}}')
  sleep 5
done
