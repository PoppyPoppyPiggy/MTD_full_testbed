# dvd_lite/dvd_attacks_lpc/scripts/prepare_honey_bridge.sh
#!/usr/bin/env bash
set -Eeuo pipefail

: "${BR:=br-honey}"
: "${TAPS:=tap-gcs tap-dummy1 tap-dummy2}"
: "${GCS_CTN:=ground-control-station}"
: "${DUMMY1_CTN:=dummy-drone-1}"
: "${DUMMY2_CTN:=dummy-drone-2}"

need(){ command -v "$1" >/dev/null 2>&1 || { echo "need $1"; exit 1; }; }
need ip; need docker

# bridge
if ! ip link show "$BR" >/dev/null 2>&1; then
  sudo ip link add "$BR" type bridge
  sudo ip link set "$BR" up
fi

# taps
for t in $TAPS; do
  if ! ip link show "$t" >/dev/null 2>&1; then
    sudo ip tuntap add dev "$t" mode tap
    sudo ip link set "$t" up
    sudo ip link set "$t" master "$BR"
  fi
done

attach_ctn () {
  local ctn="$1"
  # host측 veth 찾아서 bridge에 붙임 (일반 bridge 드라이버 기준)
  local pid; pid=$(docker inspect -f '{{.State.Pid}}' "$ctn" 2>/dev/null || true)
  if [ -z "$pid" ] || [ "$pid" = "0" ]; then echo "[skip] $ctn not running"; return 0; fi
  # ip link 네임스페이스 매칭이 환경별로 달라서 간단한 veth 탐색법 사용
  local veth; veth=$(ip -o link | awk -F': ' '{print $2}' | grep -E '^veth|^br-.*|^eth' | head -n1 || true)
  if [ -n "$veth" ]; then
    sudo ip link set "$veth" master "$BR" || true
    sudo ip link set "$veth" up || true
    echo "[*] attached $ctn($veth) -> $BR"
  else
    echo "[!] cannot find veth for $ctn (adjust script for your driver)"
  fi
}

attach_ctn "$GCS_CTN"
attach_ctn "$DUMMY1_CTN"
attach_ctn "$DUMMY2_CTN"

echo "[OK] $BR with TAPs: $TAPS"
