#!/usr/bin/env bash
set -euo pipefail
. "$(dirname "$0")/../00_env.sh"

# netem 적용: docker 컨테이너 eth0 기준(필요 시 IF 파라미터 확장)
netem_apply(){ # $1=container $2="delay 5ms 2ms distribution normal loss 0.2% corrupt 0.01% duplicate 0.05% reorder 0.05% 25%"
  local c="$1"; shift; local args="$*"
  [[ -z "$c" ]] && { echo "[netem] skip (no container)"; return 0; }
  docker exec "$c" bash -lc "tc qdisc replace dev eth0 root netem $args" || true
}
netem_clear(){ local c="$1"; [[ -z "$c" ]] && return 0; docker exec "$c" bash -lc "tc qdisc del dev eth0 root" || true; }
