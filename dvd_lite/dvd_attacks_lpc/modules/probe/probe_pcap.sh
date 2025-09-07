#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd -P)"
BASE="$(cd "$SCRIPT_DIR/../.." && pwd -P)"
. "$BASE/00_env_ext.sh"

CMD="${1:-}"; SCN="${2:-scn-$(date +%s)}"
PIDF="$OUT_DIR/captures/pcap/$SCN/tcpdump.pid"
LOGF="$OUT_DIR/bus.log"

log(){ printf '[%s] BUS ATK %s\n' "$(date +%s)" "$1" >> "$LOGF"; }

resolve(){
  python3 "$BASE/modules/attacks/resolve_target.py" \
    "$BASE/modules/attacks/targets/targets.yml" gcs mavlink
}

ensure_iface(){
  local net br
  net="$(jq -r .network <<<"$(resolve)")"
  br="$(docker network inspect "$net" 2>/dev/null \
        | jq -r '.[0].Options["com.docker.network.bridge.name"] // empty')"
  if [ -z "$br" ] || [ "$br" = "null" ]; then
    # network ID → 표준 브릿지명
    local nid; nid="$(docker network inspect -f '{{.Id}}' "$net")"
    br="br-${nid:0:12}"
  fi
  echo "$br"
}

case "$CMD" in
  start)
    mkdir -p "$OUT_DIR/captures/pcap/$SCN"
    IP="$(jq -r .ip <<<"$(resolve)")"
    BR="$(ensure_iface)"
    PCAP="$OUT_DIR/captures/pcap/$SCN/${SCN}_$(date +%s).pcap"
    # -U: packet-buffered (즉시 기록), SIGHUP/SIGINT 시 flush
    tcpdump -i "$BR" host "$IP" -nn -U -w "$PCAP" >/dev/null 2>&1 &
    echo $! > "$PIDF"
    log "PCAP_START scn=$SCN iface=$BR ip=$IP file=$PCAP pid=$(cat "$PIDF")"
    echo "[pcap] iface=$BR file=$PCAP"
    ;;
  stop)
    if [ -f "$PIDF" ]; then
      PID="$(cat "$PIDF")"
      # SIGINT으로 종료(파일 flush 보장)
      kill -INT "$PID" 2>/dev/null || true
      sleep 1
      rm -f "$PIDF"
      log "PCAP_STOP scn=$SCN"
    else
      echo "no pidfile: $PIDF" >&2
    fi
    ;;
  *)
    echo "usage: $0 {start|stop} <scenario_id>" >&2; exit 2;;
esac
