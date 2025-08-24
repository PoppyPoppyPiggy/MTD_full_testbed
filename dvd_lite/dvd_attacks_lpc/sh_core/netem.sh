#!/usr/bin/env bash
set -euo pipefail
. "$(dirname "$0")/../00_env.sh"

netem_apply(){ # $1:container   $2..:rule
  docker exec "$1" bash -lc "tc qdisc replace dev $DVD_TARGET_IF root netem $*"
}
netem_clear(){ # $1:container
  docker exec "$1" bash -lc "tc qdisc del dev $DVD_TARGET_IF root" >/dev/null 2>&1 || true
}
rate_cap_apply(){ # $1:container $2:mbit
  docker exec "$1" bash -lc "tc qdisc replace dev $DVD_TARGET_IF root tbf rate ${2}mbit burst 32kb latency 400ms"
}
rate_cap_clear(){ # $1:container
  docker exec "$1" bash -lc "tc qdisc del dev $DVD_TARGET_IF root" >/dev/null 2>&1 || true
}
