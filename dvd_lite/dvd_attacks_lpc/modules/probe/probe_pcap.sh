#!/usr/bin/env bash
# pcap 토글: docker 브릿지 자동탐지 + 타깃 IP 필터
set -euo pipefail

BASE="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck disable=SC1090
source "$BASE/00_env_ext.sh"

CMD="${1:-start}"                          # start|stop
SCN="${2:-attack-$(date +%s)}"             # 시나리오/세션 이름
ROLE="${3:-gcs}"                           # (옵션) 타깃 역할, 기본 gcs
SERVICE="${4:-mavlink}"                    # (옵션) 서비스, 기본 mavlink

OUTD="$OUT_DIR/captures/pcap/$SCN"
mkdir -p "$OUTD"
PIDF="$OUTD/tcpdump.pid"
PCAP="$OUTD/${SCN}_$(date +%s).pcap"

# --- 타깃/네트워크 해석 ---
TJSON="$(python3 "$BASE/modules/attacks/resolve_target.py" "$BASE/modules/attacks/targets/targets.yml" "$ROLE" "$SERVICE" 2>/dev/null || true)"
IP="$(echo "$TJSON"  | jq -r '.ip // empty')"
NET_HINT="$(echo "$TJSON" | jq -r '.network // empty')"
CNAME="$(echo "$TJSON"| jq -r '.container // empty')"

# 브릿지 탐색 순서:
# 1) NET_HINT 유효 → docker network inspect 로 브릿지명
# 2) 컨테이너의 NetworkID 로부터 br-<12>
# 3) 호스트의 첫번째 br-*
BR=""
if [[ -n "$NET_HINT" ]] && docker network inspect "$NET_HINT" >/dev/null 2>&1; then
  BR="$(docker network inspect "$NET_HINT" | jq -r '.[0].Options["com.docker.network.bridge.name"] // empty')"
fi
if [[ -z "$BR" ]] && [[ -n "${CNAME:-}" ]]; then
  NID="$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.NetworkID}}{{end}}' "$CNAME" 2>/dev/null || true)"
  if [[ -n "$NID" ]]; then BR="br-${NID:0:12}"; fi
fi
if [[ -z "$BR" ]]; then
  BR="$(ip -br link | awk '/^br-/{print $1; exit}')"
fi
if [[ -z "$BR" ]]; then
  echo "[pcap] ERROR: docker bridge not found"; exit 2
fi

# 필터: 타깃 IP가 있으면 host 필터, 없으면 전체
FILTER=""
if [[ -n "${IP:-}" ]]; then FILTER="host ${IP}"; fi

start() {
  echo "[pcap] iface=${BR} file=${PCAP} filter='${FILTER}'"
  # -U: 버퍼링 최소화, -nn: 이름해석 안함
  tcpdump -i "$BR" ${FILTER:+$FILTER} -nn -U -w "$PCAP" &
  echo $! > "$PIDF"
  echo "[$(date +%s)] BUS ATK PROBE pcap_start scene=${SCN} iface=${BR} file=${PCAP}" >> "$BUS_LOG"
}

stop() {
  if [[ -f "$PIDF" ]]; then
    kill "$(cat "$PIDF")" 2>/dev/null || true
    rm -f "$PIDF"
    echo "[$(date +%s)] BUS ATK PROBE pcap_stop  scene=${SCN}" >> "$BUS_LOG"
  fi
  if [[ -f "$PCAP" ]]; then ls -lh "$PCAP"; fi
}

case "$CMD" in
  start) start ;;
  stop)  stop ;;
  *) echo "usage: $0 start|stop [scene] [role] [service]"; exit 2 ;;
esac
