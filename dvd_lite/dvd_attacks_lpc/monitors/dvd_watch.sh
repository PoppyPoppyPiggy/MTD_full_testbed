#!/usr/bin/env bash
# DVD 내부 상태/이벤트를 JSONL로 bus_dvd.log에 기록
set -euo pipefail
BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[ -f "$BASE/00_env.sh" ] && . "$BASE/00_env.sh" || true
. "$BASE/00_env_ext.sh"

containers=("${DVD_C_GCS}" "${DVD_C_CC}" "${DVD_C_FC}" "${DVD_C_SIM}")

ts() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }
jlog(){ printf '%s\n' "$1" >> "$BUS_DVD_LOG"; }

# 1) docker events 스트림
watch_events() {
  docker events --format '{{json .}}' 2>/dev/null | \
  stdbuf -oL grep -E "\"(container|network)\"" | \
  while IFS= read -r line; do
    # 컨테이너 이름 필터(있을 때만 통과)
    pass=0
    for c in "${containers[@]}"; do
      if printf '%s' "$line" | grep -q "\"name\":\"$c\""; then pass=1; break; fi
    done
    [ $pass -eq 1 ] && jlog "{\"ts\":\"$(ts)\",\"evt\":\"docker_event\",\"data\":$line}"
  done
}

# 2) 주기 통계(docker stats)
watch_stats() {
  while :; do
    for c in "${containers[@]}"; do
      if docker ps --format '{{.Names}}' | grep -qx "$c"; then
        stat="$(docker stats --no-stream --format '{{json .}}' "$c" 2>/dev/null || true)"
        [ -n "$stat" ] && jlog "{\"ts\":\"$(ts)\",\"evt\":\"stats\",\"container\":\"$c\",\"data\":$stat}"
      fi
    done
    sleep 5
  done
}

# 3) 네트워크/상태 스냅샷 변화 감지
snap_diff() {
  local c="$1" kind="$2" cmd="$3"
  local sdir="$OUT_DIR/snapshots/$c"; mkdir -p "$sdir"
  local cur="$sdir/${kind}.cur" ; local prev="$sdir/${kind}.prev"
  bash -c "$cmd" > "$cur" 2>/dev/null || true
  if [ -f "$prev" ]; then
    if ! cmp -s "$prev" "$cur"; then
      # diff를 짧게
      diff_out="$(diff -u --label prev --label cur "$prev" "$cur" | sed -e '1,2d' | head -n 200)"
      jlog "{\"ts\":\"$(ts)\",\"evt\":\"${kind}_change\",\"container\":\"$c\",\"diff\":$(jq -Rs . <<<\"$diff_out\")}"
    fi
  fi
  mv -f "$cur" "$prev" 2>/dev/null || true
}

watch_snapshots() {
  while :; do
    for c in "${containers[@]}"; do
      # ENV
      snap_diff "$c" "env"   "docker exec $c env | sort"
      # PROC
      snap_diff "$c" "proc"  "docker exec $c sh -lc 'ps -eo pid,ppid,cmd --sort=pid'"
      # NET(IPv4/IPv6, 맥, 네트워크명)
      snap_diff "$c" "net"   "docker inspect $c | jq -r '.[0].NetworkSettings.Networks | to_entries[] | \"\(.key) \(.value.IPAddress) \(.value.MacAddress)\"' | sort"
    done
    sleep 10
  done
}

# 시작 배너
echo "# dvd_watch start $(ts) -> $BUS_DVD_LOG" >&2
touch "$BUS_DVD_LOG"
watch_events &  pid_events=$!
watch_stats  &  pid_stats=$!
watch_snapshots & pid_snaps=$!

trap 'kill $pid_events $pid_stats $pid_snaps 2>/dev/null || true; echo "# dvd_watch stop $(ts)" >&2' INT TERM
wait
