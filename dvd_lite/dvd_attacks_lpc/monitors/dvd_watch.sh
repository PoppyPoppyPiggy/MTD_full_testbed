#!/usr/bin/env bash
#!/usr/bin/env bash
set -euo pipefail

BASE="$(cd "$(dirname "$0")/.." && pwd)"
source "$BASE/00_env_ext.sh"

# --- 단일 실행 락 ---
LOCK="$OUT_DIR/.dvd_watch.lock"
exec {LOCKFD}>"$LOCK"
if ! flock -n "$LOCKFD"; then
  echo "[dvd_watch] already running (lock=$LOCK)"; exit 0
fi


MODE="${1:-loop}"   # loop|once
INTERVAL="${INTERVAL:-3}"  # 초

# 컨테이너 리스트
_list_cont() { docker ps --format '{{.Names}}'; }

# 컨테이너 net(bytes) 읽기 (eth0의 rx/tx)
_cont_bytes() {
  local c="$1"
  local rx tx
  rx="$(docker exec -i "$c" cat /sys/class/net/eth0/statistics/rx_bytes 2>/dev/null || echo 0)"
  tx="$(docker exec -i "$c" cat /sys/class/net/eth0/statistics/tx_bytes 2>/dev/null || echo 0)"
  echo "$rx $tx"
}

# docker stats 1회
_push_stats_once() {
  while read -r c; do
    local J
    J="$(docker stats --no-stream --format '{{json .}}' "$c" 2>/dev/null || true)"
    [[ -n "$J" ]] && bus_dvd_json "{\"ts\":\"$(_log_now_ts)\",\"evt\":\"stats\",\"container\":\"$c\",\"data\":${J}}"
    # 링크 바이트
    read -r RX TX <<< "$(_cont_bytes "$c")"
    bus_dvd_json "{\"ts\":\"$(_log_now_ts)\",\"evt\":\"link_bytes\",\"container\":\"$c\",\"rx_bytes\":$RX,\"tx_bytes\":$TX}"
  done < <(_list_cont)
}

# GCS mav.tlog 스냅샷 요약
_mav_snapshot() {
  local gcs
  gcs="$(_list_cont | grep -E 'ground-control-station|gcs' | head -n1)"
  [[ -z "$gcs" ]] && return 0
  local TMP="$OUT_DIR/snapshots"
  mkdir -p "$TMP"
  # 파일 위치: 이미지에 따라 다름. 기본 /root/mav.tlog 시도
  if docker exec -i "$gcs" test -f /root/mav.tlog; then
    local dst="$TMP/mav_$(date +%s).tlog"
    docker cp "$gcs:/root/mav.tlog" "$dst" >/dev/null 2>&1 || return 0
    python3 "$BASE/monitors/mav_tlog_summary.py" "$dst" >> "$BUS_DVD_LOG" 2>/dev/null || true
  fi
}

# 서비스 프로빙 (RTSP/HTTP_CAM)
_service_probe() {
  local TJSON
  # RTSP
  TJSON="$(python3 "$BASE/modules/attacks/resolve_target.py" "$BASE/modules/attacks/targets/targets.yml" companion rtsp)"
  local H="$(echo "$TJSON" | jq -r .ip)"; local P="$(echo "$TJSON" | jq -r .port)"
  python3 "$BASE/monitors/http_rtsp_probe.py" companion "$H" "$P" "rtsp"
  # HTTP_CAM
  TJSON="$(python3 "$BASE/modules/attacks/resolve_target.py" "$BASE/modules/attacks/targets/targets.yml" companion http_cam)"
  H="$(echo "$TJSON" | jq -r .ip)"; P="$(echo "$TJSON" | jq -r .port)"
  python3 "$BASE/monitors/http_rtsp_probe.py" companion "$H" "$P" "http"
}

_once() {
  _push_stats_once
  _mav_snapshot
  _service_probe
}

if [[ "$MODE" == "once" ]]; then
  _once
  exit 0
fi

# loop
while :; do
  _once
  sleep "$INTERVAL"
done
