#!/usr/bin/env bash
# zsh/bash 호환: 안전옵션 강제하지 않음(사용자 쉘 안죽게)
set -o pipefail 2>/dev/null || true

# 프로젝트 루트
export DVD_BASE="${DVD_BASE:-$(cd "$(dirname "$0")" && pwd)}"

# 산출물 루트 = bus/
export OUT_DIR="${OUT_DIR:-$DVD_BASE/bus}"
mkdir -p "$OUT_DIR" "$OUT_DIR/captures/pcap" "$OUT_DIR/snapshots"
chmod -R a+rwX "$OUT_DIR"

# 표준 버스 로그
export BUS_LOG="${BUS_LOG:-$OUT_DIR/bus.log}"
export BUS_DVD_LOG="${BUS_DVD_LOG:-$OUT_DIR/bus_dvd.log}"

# PATH 보강
export PATH="$DVD_BASE/scripts:$DVD_BASE/modules/attacks:$DVD_BASE/modules/mtd:$DVD_BASE/modules/probe:$PATH"

# Docker 네트워크 자동 감지 (lite 기본: simulator)
if [[ -z "${DVD_NET:-}" || "${DVD_NET}" = '${DVD_NET}' ]]; then
  if docker network inspect simulator >/dev/null 2>&1; then
    export DVD_NET="simulator"
  else
    # 컨테이너가 붙은 네트워크 중 첫 번째
    _first_net="$(docker ps --format '{{.Networks}}' | head -n1)"
    [[ -n "$_first_net" ]] && export DVD_NET="$_first_net"
  fi
fi

echo "ENV OK  base=$DVD_BASE"
echo "OUT_DIR=$OUT_DIR"
echo "BUS_LOG=$BUS_LOG"
echo "BUS_DVD_LOG=$BUS_DVD_LOG"
echo "DVD_NET=${DVD_NET:-<unset>}"
umask 0002 || true
