#!/usr/bin/env bash
# Auto-generated from: /home/kali/MTD_full_testbed/Damn-Vulnerable-Drone.wiki/Drone-GPS-&-Telemetry-Detection.md
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

log "[ATTACK] id=drone-gps-_-telemetry-detection src=Drone-GPS-&-Telemetry-Detection.md"
log "[BLOCK 1] type=shell"
(ip.src == 10.13.0.3) && (mavlink_proto.msgid == "HEARTBEAT")

log "[BLOCK 2] type=shell"
(ip.src == 10.13.0.3) && (mavlink_proto.msgid == "SYS_STATUS")

log "[BLOCK 3] type=shell"
(ip.src == 10.13.0.3) && (mavlink_proto.msgid == "GPS_RAW_INT")

log "[BLOCK 4] type=shell"
(ip.src == 10.13.0.3) && (mavlink_proto.msgid == "GLOBAL_POSITION_INT")

log "[BLOCK 5] type=shell"
(ip.src == 10.13.0.3) && (mavlink_proto.msgid == "ATTITUDE")

log "[BLOCK 6] type=shell"
(ip.src == 10.13.0.3) && (mavlink_proto.msgid == "ALTITUDE")

log "[BLOCK 7] type=shell"
(ip.src == 10.13.0.3) && (mavlink_proto.msgid == "BATTERY_STATUS")

log "[BLOCK 8] type=shell"
(ip.src == 10.13.0.3) && (mavlink_proto.msgid == "VFR_HUD")

log "[BLOCK 9] type=shell"
(ip.src == 10.13.0.3) && (mavlink_proto.msgid == "STATUSTEXT")

log "[BLOCK 10] type=shell"
(ip.src == 10.13.0.3) && (mavlink_proto.msgid == "MISSION_CURRENT")

log "[BLOCK 11] type=shell"
(ip.src == 10.13.0.3) && (mavlink_proto.msgid == "NAV_CONTROLLER_OUTPUT")

log "[BLOCK 12] type=shell"
(ip.src == 10.13.0.3) && (mavlink_proto.msgid == "RADIO_STATUS")

log "[BLOCK 13] type=python"
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
import time
import curses
from pymavlink import mavutil

# Establish connection to the MAVLink device
connection = mavutil.mavlink_connection('tcp:${TARGET_IP}:${TARGET_PORT}')

# Wait for the first heartbeat
print("Waiting for heartbeat...")
connection.wait_heartbeat()
print("Heartbeat received from system (system %u component %u)" % (connection.target_system, connection.target_component))

def init_curses():
    stdscr = curses.initscr()
    curses.noecho()
    curses.cbreak()
    stdscr.keypad(True)
    return stdscr

def print_telemetry(stdscr, telemetry_data):
    stdscr.clear()
    for i, (key, value) in enumerate(telemetry_data.items()):
        stdscr.addstr(i, 0, f"{key}: {value}")
    stdscr.refresh()

def main(stdscr):
    telemetry_data = {
        "HEARTBEAT": "N/A",
        "SYS_STATUS": "N/A",
        "GPS_RAW_INT": "N/A",
        "GLOBAL_POSITION_INT": "N/A",
        "ATTITUDE": "N/A",
        "ALTITUDE": "N/A",
        "BATTERY_STATUS": "N/A",
        "VFR_HUD": "N/A",
        "STATUSTEXT": "N/A",
        "MISSION_CURRENT": "N/A",
        "NAV_CONTROLLER_OUTPUT": "N/A",
        "RADIO_STATUS": "N/A",
    }

    while True:
        msg = connection.recv_match(blocking=True)
        if msg:
            if msg.get_type() == 'HEARTBEAT':
                telemetry_data["HEARTBEAT"] = f"Type: {msg.type}, Autopilot: {msg.autopilot}, Base mode: {msg.base_mode}, System status: {msg.system_status}"
            elif msg.get_type() == 'SYS_STATUS':
                telemetry_data["SYS_STATUS"] = f"Battery voltage: {msg.voltage_battery}, Battery current: {msg.current_battery}, Battery remaining: {msg.battery_remaining}"
            elif msg.get_type() == 'GPS_RAW_INT':
                telemetry_data["GPS_RAW_INT"] = f"Lat: {msg.lat}, Lon: {msg.lon}, Alt: {msg.alt}, Satellites: {msg.satellites_visible}"
            elif msg.get_type() == 'GLOBAL_POSITION_INT':
                telemetry_data["GLOBAL_POSITION_INT"] = f"Lat: {msg.lat}, Lon: {msg.lon}, Alt: {msg.alt}, Relative Alt: {msg.relative_alt}"
                telemetry_data["ALTITUDE"] = f"Alt: {msg.alt}, Relative Alt: {msg.relative_alt}"
            elif msg.get_type() == 'ATTITUDE':
                telemetry_data["ATTITUDE"] = f"Roll: {msg.roll}, Pitch: {msg.pitch}, Yaw: {msg.yaw}"
            elif msg.get_type() == 'BATTERY_STATUS':
                telemetry_data["BATTERY_STATUS"] = f"Voltage: {msg.voltages[0]}, Current: {msg.current_battery}"
            elif msg.get_type() == 'VFR_HUD':
                telemetry_data["VFR_HUD"] = f"Airspeed: {msg.airspeed}, Groundspeed: {msg.groundspeed}, Heading: {msg.heading}"
            elif msg.get_type() == 'STATUSTEXT':
                telemetry_data["STATUSTEXT"] = f"Text: {msg.text}"
            elif msg.get_type() == 'MISSION_CURRENT':
                telemetry_data["MISSION_CURRENT"] = f"Seq: {msg.seq}"
            elif msg.get_type() == 'NAV_CONTROLLER_OUTPUT':
                telemetry_data["NAV_CONTROLLER_OUTPUT"] = f"Nav bearing: {msg.nav_bearing}, Target bearing: {msg.target_bearing}, Wp dist: {msg.wp_dist}"
            elif msg.get_type() == 'RADIO_STATUS':
                telemetry_data["RADIO_STATUS"] = f"RSSI: {msg.rssi}, Rem RSSI: {msg.remrssi}, Noise: {msg.noise}, Rem noise: {msg.remnoise}"

            print_telemetry(stdscr, telemetry_data)

# Start telemetry monitor
curses.wrapper(main)
PY

