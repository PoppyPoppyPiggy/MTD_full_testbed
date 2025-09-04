#!/usr/bin/env bash
# DVD 상태를 즉시 점검하고 bus_dvd.log에 1회 기록(시계열은 dvd_watch가 담당)
set -euo pipefail
BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
[ -f "$BASE/00_env.sh" ] && . "$BASE/00_env.sh" || true
. "$BASE/00_env_ext.sh"

ts(){ date -u +"%Y-%m-%dT%H:%M:%SZ"; }
jlog(){ printf '%s\n' "$1" >> "$BUS_DVD_LOG"; }

containers=("${DVD_C_GCS}" "${DVD_C_CC}" "${DVD_C_FC}" "${DVD_C_SIM}")

for c in "${containers[@]}"; do
  if docker ps --format '{{.Names}}' | grep -qx "$c"; then
    envs="$(docker exec "$c" env | sort | jq -Rs .)"
    procs="$(docker exec "$c" sh -lc 'ps -eo pid,ppid,cmd --sort=pid' | jq -Rs .)"
    nets="$(docker inspect "$c" | jq '.[0].NetworkSettings.Networks')"
    stats="$(docker stats --no-stream --format '{{json .}}' "$c" 2>/dev/null || echo '{}')"
    jlog "{\"ts\":\"$(ts)\",\"evt\":\"probe\",\"container\":\"$c\",\"env\":$envs,\"proc\":$procs,\"net\":$nets,\"stats\":$stats}"
  fi
done
echo "probe done -> $BUS_DVD_LOG"
