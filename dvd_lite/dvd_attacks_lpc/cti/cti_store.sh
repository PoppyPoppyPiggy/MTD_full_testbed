#!/usr/bin/env bash
# 초간단 CTI key/value 저장소 (ENV 파일 기반). jq 없이 작동.
set -euo pipefail
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]-$0}")" && pwd)"
. "$SCRIPT_DIR/../00_env.sh"
CTI_STORE="${CTI_STORE:-$LPC_LOG_DIR/cti_targets.env}"
mkdir -p "$(dirname "$CTI_STORE")"; touch "$CTI_STORE"

_cti_set(){ # $1:key  $2:value
  local k="$1" v="$2" tmp="${CTI_STORE}.tmp"
  grep -v -E "^${k}=" "$CTI_STORE" > "$tmp" || true
  echo "${k}=${v}" >> "$tmp"
  mv "$tmp" "$CTI_STORE"
}
cti_set_ip(){ _cti_set TARGET_IP "$1"; }
cti_set_port(){ _cti_set MAVLINK_PORT "$1"; }

cti_get(){ # $1:key
  [ -f "$CTI_STORE" ] || return 1
  . "$CTI_STORE"
  eval "echo \"\${$1:-}\""
}

cti_resolve(){ # export CURRENT_IP, CURRENT_PORT (fallback: env 기본값)
  local ip port
  ip="$(cti_get TARGET_IP)";  [ -z "${ip:-}" ]  && ip="${DVD_MAVLINK_HOST:-127.0.0.1}"
  port="$(cti_get MAVLINK_PORT)"; [ -z "${port:-}" ] && port="${DVD_MAVLINK_PORT:-14550}"
  export CURRENT_IP="$ip" CURRENT_PORT="$port"
  echo "CURRENT_IP=$CURRENT_IP CURRENT_PORT=$CURRENT_PORT"
}
