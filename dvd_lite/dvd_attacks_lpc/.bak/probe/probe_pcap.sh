#!/usr/bin/env bash
# pcap 토글: start <SCN> [role service] [--all] [--iface=NAME]
#            stop  <SCN>
set -euo pipefail
source "$(cd "$(dirname "$0")/../.." && pwd)/00_env_ext.sh"

cmd="${1:-}"; shift || true
SCN="${1:-}"; [[ -z "${SCN}" ]] && { echo "usage: $0 start|stop <SCN> [role service] [--all] [--iface=NAME]"; exit 2; }
shift || true

ROLE="${1:-}"; [[ -n "${ROLE:-}" ]] && shift || true
SERVICE="${1:-}"; [[ -n "${SERVICE:-}" ]] && shift || true

ALL=0; IFACE=""
for a in "$@"; do
  [[ "$a" == "--all" ]] && ALL=1
  [[ "$a" == --iface=* ]] && IFACE="${a#--iface=}"
done

SCN_DIR="$OUT_DIR/captures/pcap/$SCN"
PIDF="$SCN_DIR/tcpdump.pid"
PCAP="$SCN_DIR/${SCN}_$(date +%s).pcap"

resolve_target() {
  local role="$1" svc="$2"
  python3 "$DVD_BASE/modules/attacks/resolve_target.py" \
    "$DVD_BASE/modules/attacks/targets/targets.yml" "$role" "${svc:-}" 2>/dev/null
}

case "$cmd" in
  start)
    mkdir -p "$SCN_DIR"; chmod -R a+rwX "$SCN_DIR"
    # 네트워크 브리지 자동
    if [[ -z "${IFACE:-}" ]]; then
      NID="$(docker network inspect -f '{{.Id}}' "$DVD_NET" 2>/dev/null || true)"
      [[ -n "$NID" ]] && IFACE="br-${NID:0:12}"
      [[ -z "${IFACE:-}" ]] && IFACE="$(ip -br link | awk '/^br-/{print $1; exit}')"
    fi

    # 대상 IP
    IP=""
    if [[ -n "${ROLE:-}" ]]; then
      TJSON="$(resolve_target "$ROLE" "${SERVICE:-}")"
      IP="$(echo "$TJSON" | jq -r '.ip // empty' 2>/dev/null || true)"
    fi

    FILTER=""
    if [[ $ALL -eq 0 && -n "${IP:-}" ]]; then
      FILTER="host ${IP}"
    fi

    echo "[pcap] iface=${IFACE:-null} file=$PCAP filter='${FILTER:-<none>}'"
    # 백그라운드 실행 + pid 파일
    if [[ -n "${FILTER:-}" ]]; then
      tcpdump -i "$IFACE" $FILTER -nn -w "$PCAP" >/dev/null 2>&1 &
    else
      tcpdump -i "$IFACE" -nn -w "$PCAP" >/dev/null 2>&1 &
    fi
    echo $! > "$PIDF"
    ;;

  stop)
    if [[ -f "$PIDF" ]]; then
      PID="$(cat "$PIDF")"
      # SIGINT로 flush
      kill -2 "$PID" 2>/dev/null || kill "$PID" 2>/dev/null || true
      sleep 1
      rm -f "$PIDF"
    else
      echo "no pidfile: $PIDF"
    fi
    ;;

  *)
    echo "unknown cmd: $cmd"; exit 2;;
esac
