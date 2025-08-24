#!/usr/bin/env bash
set -euo pipefail
. "$(dirname "$0")/../00_env.sh"

_stat(){ # $1:container $2:if $3:stat
  docker exec "$1" bash -lc "cat /sys/class/net/$2/statistics/$3" 2>/dev/null || echo 0
}
obs_snapshot(){ # $1:container $2:if
  local c="$1" i="$2"
  local rxp txp rxb txb rxd txd
  rxp=$(_stat "$c" "$i" rx_packets); txp=$(_stat "$c" "$i" tx_packets)
  rxb=$(_stat "$c" "$i" rx_bytes);   txb=$(_stat "$c" "$i" tx_bytes)
  rxd=$(_stat "$c" "$i" rx_dropped); txd=$(_stat "$c" "$i" tx_dropped)
  echo "rxp=$rxp txp=$txp rxb=$rxb txb=$txb rxd=$rxd txd=$txd"
}
delta_emit(){ # $1:before $2:after $3:tag
  local b="$1" a="$2" tag="$3"
  for k in rxp txp rxb txb rxd txd; do
    local bv av
    bv=$(echo "$b" | tr ' ' '\n' | awk -F= -v K="$k" '$1==K{print $2}')
    av=$(echo "$a" | tr ' ' '\n' | awk -F= -v K="$k" '$1==K{print $2}')
    eval d_$k=$(( av - bv ))
  done
  bus_emit "$tag" "target=$DVD_C_GCS if=$DVD_TARGET_IF obs_rxp=$d_rxp obs_txp=$d_txp obs_rxb=$d_rxb obs_txb=$d_txb obs_rxd=$d_rxd obs_txd=$d_txd"
}
