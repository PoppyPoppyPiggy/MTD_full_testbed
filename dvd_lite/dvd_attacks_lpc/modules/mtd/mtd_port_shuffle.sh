#!/usr/bin/env bash
set -euo pipefail
BASE="$(cd "$(dirname "$0")/../.." && pwd)"
source "$BASE/scripts/lib/log.sh"

ACTION="${1:-apply}"    # apply|revert
ROLE="${2:-gcs}"        # gcs|companion|flight|sim
SERVICE="${3:-mavlink}" # mavlink|rtsp|http_cam

# 타깃 해석
TJSON="$(python3 "$BASE/modules/attacks/resolve_target.py" "$BASE/modules/attacks/targets/targets.yml" "$ROLE" "$SERVICE")"
HOST="$(echo "$TJSON" | jq -r .ip)"
PORT="$(echo "$TJSON" | jq -r .port)"
NET="$(echo "$TJSON" | jq -r .network)"
NID="$(docker network inspect -f '{{.Id}}' "$NET")"
BR="br-${NID:0:12}"

NEWP="${4:-$(( 20000 + (RANDOM % 10000) ))}"  # 새 목적지 포트

# nft/legacy 자동 판별
IPT="iptables"
command -v iptables-nft >/dev/null 2>&1 && IPT="iptables-nft"

apply() {
  # DNAT: dst HOST:PORT -> HOST:NEWP
  sudo $IPT -t nat -A PREROUTING -i "$BR" -p udp --dport "$PORT" -j DNAT --to-destination "$HOST:$NEWP" || true
  sudo $IPT -t nat -A OUTPUT     -p udp -d "$HOST" --dport "$PORT" -j DNAT --to-destination "$HOST:$NEWP" || true
  bus_mtd "action=port_shuffle role=${ROLE} service=${SERVICE} old=${PORT} new=${NEWP} br=${BR}"
  bus_dvd_json "{\"ts\":\"$(_log_now_ts)\",\"evt\":\"mtd_action\",\"kind\":\"port_shuffle\",\"role\":\"${ROLE}\",\"service\":\"${SERVICE}\",\"old\":${PORT},\"new\":${NEWP}}"
}

revert() {
  # 기존 규칙들 제거(대충 매칭)
  set +e
  sudo $IPT -t nat -S PREROUTING | grep "dport ${PORT} .* DNAT .*:${NEWP}" | sed 's/^-A /-D /' | xargs -r -L1 sudo $IPT -t nat
  sudo $IPT -t nat -S OUTPUT     | grep "dport ${PORT} .* DNAT .*:${NEWP}" | sed 's/^-A /-D /' | xargs -r -L1 sudo $IPT -t nat
  set -e
  bus_mtd "action=port_shuffle_revert role=${ROLE} service=${SERVICE} restored=${PORT}"
  bus_dvd_json "{\"ts\":\"$(_log_now_ts)\",\"evt\":\"mtd_revert\",\"kind\":\"port_shuffle\",\"role\":\"${ROLE}\",\"service\":\"${SERVICE}\",\"port\":${PORT}}"
}

case "$ACTION" in
  apply)  apply ;;
  revert) revert ;;
  *) echo "usage: mtd_port_shuffle.sh apply|revert [role] [service] [newPort]"; exit 2 ;;
esac
