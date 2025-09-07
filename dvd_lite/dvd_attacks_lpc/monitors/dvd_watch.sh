#!/usr/bin/env bash
# 종합 모니터 (도커 리소스 + 내부 지표 스냅샷)
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd -P)"
BASE="$(cd "$SCRIPT_DIR/.." && pwd -P)"
. "$BASE/00_env_ext.sh"

MODE="${1:-loop}"  # loop | once
mkdir -p "$(dirname "$BUS_DVD_LOG")"; : > /dev/null

log(){ printf '%s\n' "$1" >> "$BUS_DVD_LOG"; }

do_stats() {
  while read -r name; do
    j="$(docker stats --no-stream --format '{{json .}}' "$name" 2>/dev/null || true)"
    [ -z "$j" ] && continue
    jq -n --argjson s "$j" --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
      '{ts:$ts, evt:"stats", container:($s|.Name),
        data:{CPUPerc:($s|.CPUPerc), MemUsage:($s|.MemUsage), NetIO:($s|.NetIO), BlockIO:($s|.BlockIO), PIDs:($s|.PIDs)}}'
  done < <(docker ps --format '{{.Names}}')
}

if [ "$MODE" = "once" ]; then
  # 1) 도커 리소스 스냅샷
  while read -r line; do log "$line"; done < <(do_stats)

  # 2) 링크 바이트 1회
  bash "$BASE/monitors/metrics_link_bytes.sh" once || true

  # 3) RTSP/HTTP 1회
  python3 "$BASE/monitors/metrics_rtsp.py" once || true
  python3 "$BASE/monitors/metrics_http_cam.py" once || true

  # 4) MAV 스냅샷(위치/배터리/레이트/파라미터 개수)
  python3 "$BASE/tools/extract_mav_metrics.py" \
      --container "${DVD_C_GCS}" \
      --out "$OUT_DIR/mav_msgs_once.csv" \
      --summary_json_to "$BUS_DVD_LOG" \
      --window_s 10 || true
  exit 0
fi

# loop 모드
( while true; do do_stats | while read -r L; do log "$L"; done; sleep 3; done ) &
( docker events --format '{{json .}}' 2>/dev/null | while read -r line; do
    [ -z "$line" ] && continue
    jq -n --argjson e "$line" --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '{ts:$ts, evt:"docker_event", data:$e}'
  done | while read -r L; do log "$L"; done ) &
# 내부 지표 루프
( python3 "$BASE/monitors/metrics_rtsp.py" loop >/dev/null 2>&1 ) &
( python3 "$BASE/monitors/metrics_http_cam.py" loop >/dev/null 2>&1 ) &
( bash "$BASE/monitors/metrics_link_bytes.sh" loop >/dev/null 2>&1 ) &
( while true; do
    python3 "$BASE/tools/extract_mav_metrics.py" \
      --container "${DVD_C_GCS}" \
      --out "$OUT_DIR/mav_msgs_loop.csv" \
      --summary_json_to "$BUS_DVD_LOG" \
      --window_s 10 || true
    sleep 10
  done ) &

echo "[dvd_watch] monitors running → $BUS_DVD_LOG"
wait -n || true
