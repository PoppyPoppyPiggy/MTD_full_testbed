container_exists(){ [ -n "$1" ] && docker ps --format "{{.Names}}" | grep -Fxq "$1"; }
_docker_inspect(){ container_exists "$1" && _docker_inspect "$@"; }

container_exists(){ [ -n "$1" ] && docker ps --format "{{.Names}}" | grep -Fxq "$1"; }
_docker_inspect(){ container_exists "$1" && _docker_inspect "$@"; }

#!/usr/bin/env bash
# docker stats + 링크 바이트 + RTSP/HTTP/MAV 스냅샷
set -euo pipefail
source "$(cd "$(dirname "$0")/.." && pwd)/00_env_ext.sh"

LOCK="$OUT_DIR/.dvd_watch.lock"
MODE="${1:-loop}"   # once | loop
INTERVAL="${INTERVAL:-2}"

# 단일 인스턴스 보장
exec 9>"$LOCK"
flock -n 9 || { [[ "$MODE" = "once" ]] || exit 0; }

log(){ printf '%s\n' "$*" >> "$BUS_DVD_LOG"; }

emit_stats(){
  docker stats --no-stream --format '{{json .}}' \
  | while read -r j; do
      ts=$(date -u +%FT%TZ)
      echo "{\"ts\":\"$ts\",\"evt\":\"stats\",\"container\":$(echo "$j" | jq -r .Name),\"data\":$j}" >> "$BUS_DVD_LOG"
    done
}

emit_link_bytes(){
  local net="${DVD_NET:-simulator}"
  # 각 컨테이너별 rx/tx 추정: /proc/net/dev를 컨테이너 내부에서 합산
  for c in $(docker ps --format '{{.Names}}'); do
    # 실패해도 전체 루프는 계속
    local ts; ts=$(date -u +%FT%TZ)
    local js
    js=$(docker exec "$c" sh -lc "cat /proc/net/dev 2>/dev/null | tail -n +3" 2>/dev/null | \
        awk '{rx+=$2; tx+=$10} END {printf(\"{\\\"rx_bytes\\\":%d,\\\"tx_bytes\\\":%d}\",rx,tx)}' 2>/dev/null || echo '{}')
    [[ -z "$js" ]] && js='{}'
    echo "{\"ts\":\"$ts\",\"evt\":\"link_bytes\",\"container\":\"$c\",$(echo "$js" | sed 's/^{//;s/}$//')}" >> "$BUS_DVD_LOG"
  done
}

emit_service_probe(){
  # RTSP / HTTP_CAM은 wiki 기준 포트 사용
  local ts host
  # companion RTSP/HTTP
  host=$(python3 "$DVD_BASE/modules/attacks/resolve_target.py" "$DVD_BASE/modules/attacks/targets/targets.yml" companion rtsp | jq -r .ip)
  ts=$(date -u +%FT%TZ)
  python3 "$DVD_BASE/monitors/metrics_rtsp.py" --host "$host" --port 8554 >> "$BUS_DVD_LOG" 2>/dev/null || echo "{\"ts\":\"$ts\",\"evt\":\"rtsp_probe\",\"ok\":false}" >> "$BUS_DVD_LOG"

  host=$(python3 "$DVD_BASE/modules/attacks/resolve_target.py" "$DVD_BASE/modules/attacks/targets/targets.yml" companion http_cam | jq -r .ip)
  ts=$(date -u +%FT%TZ)
  python3 "$DVD_BASE/monitors/metrics_http_cam.py" --host "$host" --port 8080 >> "$BUS_DVD_LOG" 2>/dev/null || echo "{\"ts\":\"$ts\",\"evt\":\"http_probe\",\"ok\":false}" >> "$BUS_DVD_LOG"
}

emit_mav_snapshot(){
  # GCS mav.tlog 스냅샷 → 요약 추출
  # (Damn-Vulnerable-Drone lite 기본 경로)
  local gcs="ground-control-station-lite"
  local ts; ts=$(date -u +%FT%TZ)
  # 컨테이너 내부에서 mav.tlog를 /tmp로 복사 후 호스트 OUT_DIR로 가져옴
  docker exec "$gcs" sh -lc 'test -s mav.tlog && cp mav.tlog /tmp/mav_copy.tlog || true' 2>/dev/null || true
  docker cp "$gcs:/tmp/mav_copy.tlog" "$OUT_DIR/snapshots/mav_$(date +%s).tlog" >/dev/null 2>&1 || true
  # 요약
  python3 "$DVD_BASE/tools/extract_mav_metrics.py" --logdir "$OUT_DIR/snapshots" >> "$BUS_DVD_LOG" 2>/dev/null || true
}

run_once(){
  emit_stats
  emit_link_bytes
  emit_service_probe
  emit_mav_snapshot
}

if [[ "$MODE" = "once" ]]; then
  run_once
else
  while :; do
    run_once
    sleep "$INTERVAL"
  done
fi
