#!/usr/bin/env bash
set -euo pipefail
BASE="$(cd "$(dirname "$0")/../.." && pwd)"
source "$BASE/scripts/lib/log.sh"

CMD="${1:-start}"     # start|stop
SCN="${2:-cc-$(date +%s)}"

CNAME="$(docker ps --format '{{.Names}}' | grep -E 'companion|companion-computer' | head -n1 || true)"
[[ -z "$CNAME" ]] && { echo "companion container not found"; exit 1; }

OUTD="$OUT_DIR/captures/pcap/$SCN"
mkdir -p "$OUTD"

PIDF="$OUTD/cc_tcpdump.pid"
PCAP_IN="/tmp/${SCN}_cc.pcap"
PCAP_OUT="$OUTD/${SCN}_cc.pcap"

start() {
  # CC 내부 eth0에서 전부 캡처(필요시 포트 필터 추가)
  docker exec -d "$CNAME" sh -lc "tcpdump -i eth0 -nn -U -w '$PCAP_IN'" 
  # pidfile은 docker exec의 pid를 직접 얻기 어려우니 종료시 pkill 처리
  echo "docker:$CNAME:$PCAP_IN" > "$PIDF"
  bus_probe "cc_pcap_start scene=${SCN} container=${CNAME} file=${PCAP_OUT}"
}

stop() {
  if [[ -f "$PIDF" ]]; then
    docker exec -i "$CNAME" sh -lc "pkill -f 'tcpdump -i eth0' || true"
    docker cp "$CNAME:$PCAP_IN" "$PCAP_OUT" >/dev/null 2>&1 || true
    docker exec -i "$CNAME" rm -f "$PCAP_IN" || true
    rm -f "$PIDF"
    bus_probe "cc_pcap_stop scene=${SCN} container=${CNAME}"
  fi
}

case "$CMD" in
  start) start ;;
  stop)  stop ;;
  *) echo "usage: probe_cc_pcap.sh start|stop [scenario_id]"; exit 2 ;;
esac
