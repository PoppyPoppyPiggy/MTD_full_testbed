#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd -P)"
BASE="$(cd "$SCRIPT_DIR/../.." && pwd -P)"
[ -f "$BASE/00_env.sh" ] && . "$BASE/00_env.sh" || true
. "$BASE/00_env_ext.sh"

CMD="${1:-start}"; SCN="${2:-default}"
mkdir -p "$PCAP_DIR/$SCN"

# BRIDGE
NET_JSON="$(python3 "$BASE/modules/attacks/resolve_target.py" "$BASE/modules/attacks/targets/targets.yml" gcs mavlink)"
NET="$(echo "$NET_JSON" | jq -r .network)"
BR="$(docker network inspect "$NET" 2>/dev/null | jq -r '.[0].Options["com.docker.network.bridge.name"] // empty' 2>/dev/null || true)"
[ -z "${BR:-}" ] || [ "$BR" = "null" ] && BR="$(ip -br link | awk '/^br-/{print $1; exit}')"
[ -z "${BR:-}" ] && BR="any"

PID_FILE="$PCAP_DIR/$SCN/tcpdump.pid"
PCAP_FILE="$PCAP_DIR/$SCN/${SCN}_$(date +%s).pcap"

if [ "$CMD" = "start" ]; then
  echo "[pcap] iface=$BR file=$PCAP_FILE"
  nohup tcpdump -i "$BR" -w "$PCAP_FILE" >/dev/null 2>&1 & echo $! > "$PID_FILE"
elif [ "$CMD" = "stop" ]; then
  [ -f "$PID_FILE" ] && kill "$(cat "$PID_FILE")" 2>/dev/null || true
  rm -f "$PID_FILE"
else
  echo "usage: $0 start|stop <scenario_id>"; exit 2
fi
