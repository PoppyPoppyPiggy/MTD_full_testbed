#!/usr/bin/env bash
# ~/MTD/MTD_full_testbed/dvd_lite/dvd_attacks_lpc/scripts/ns3_tap_plumb.sh
set -euo pipefail
DVD_CTN=${1:-ground-control-station}    # DVD 컨테이너명
ATTK_CTN=${2:-}                          # 공격자 컨테이너명(없으면 생략)
DVD_TAP=${3:-tap-dvd}
ATTK_TAP=${4:-tap-attk}
DVD_IP=${5:-10.10.0.2/24}
ATTK_IP=${6:-10.10.0.3/24}

make_tap () {
  local IF=$1
  ip link show "$IF" >/dev/null 2>&1 || sudo ip tuntap add mode tap "$IF"
  sudo ip link set "$IF" up
}

into_ctn () {
  local CTN=$1 IF=$2 IPADDR=$3
  local PID=$(docker inspect -f '{{.State.Pid}}' "$CTN")
  sudo ip link set "$IF" netns "$PID"
  sudo nsenter -t "$PID" -n ip link set "$IF" up
  sudo nsenter -t "$PID" -n ip addr add "$IPADDR" dev "$IF" || true
}

echo "[*] creating taps..."
make_tap "$DVD_TAP"
[ -n "$ATTK_CTN" ] && make_tap "$ATTK_TAP"

echo "[*] moving taps into containers..."
into_ctn "$DVD_CTN" "$DVD_TAP" "$DVD_IP"
[ -n "$ATTK_CTN" ] && into_ctn "$ATTK_CTN" "$ATTK_TAP" "$ATTK_IP"

echo "[ok] taps ready: $DVD_TAP -> $DVD_CTN ($DVD_IP) ${ATTK_CTN:+, $ATTK_TAP -> $ATTK_CTN ($ATTK_IP)}"
