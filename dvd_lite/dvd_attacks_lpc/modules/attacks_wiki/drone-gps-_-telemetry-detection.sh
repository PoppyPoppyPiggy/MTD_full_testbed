#!/usr/bin/env bash
# Auto-generated from: /home/kali/MTD_full_testbed/Damn-Vulnerable-Drone.wiki/Drone-GPS-&-Telemetry-Detection.md
# Created: 2025-09-14 13:46:03
# NOTE: 설명/서사는 제거되었고, 코드블록/프롬프트 명령만 포함됩니다.

# MTD_INTERFACE_START
# ==========================================================
# MTD-aware Target Acquisition & Logging Setup
# ==========================================================
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
PROJECT_ROOT=$(realpath "$SCRIPT_DIR/../../..")

# --- Python Module Path FIX ---
# 파이썬이 우리 모듈을 찾을 수 있도록 프로젝트 루트를 PYTHONPATH에 추가합니다.
export PYTHONPATH="${PROJECT_ROOT}:${PYTHONPATH}"

# MTD 타겟 조회
pushd "$PROJECT_ROOT" > /dev/null
# MTD 인터페이스 모듈 직접 실행
TARGET_ADDR=$(python3 -m dvd_lite.dvd_attacks_lpc.interface)
POP_RESULT=$?
popd > /dev/null

if [ $POP_RESULT -ne 0 ] || [ -z "$TARGET_ADDR" ]; then
    echo "ERROR: Could not get active target from MTD interface. Aborting attack."
    exit 1
fi

TARGET_IP=$(echo "$TARGET_ADDR" | cut -d: -f1)
TARGET_PORT=14550 # SITL의 기본 UDP 포트

# 중앙 로거 함수 정의
log() {
    printf '[%(%F_T)T] %s\n' -1 "$*"
    EVENT_TYPE=$1
    shift
    EVENT_DATA_STR="$*"
    pushd "$PROJECT_ROOT" > /dev/null
    python3 -c 'from dvd_lite.dvd_attacks_lpc.bus.logger import log_bus_event; import sys; log_bus_event(sys.argv[1], {"message": sys.argv[2]})' "$EVENT_TYPE" "$EVENT_DATA_STR"
    popd > /dev/null
}
# MTD_INTERFACE_END
set -euo pipefail

# 기준 경로 (요구사항)
export BASE="${BASE:-$PWD}"

# 공통 로그 연결(선택사항) - 존재 시 로드
if [[ -f "$BASE/00_env.sh" ]]; then . "$BASE/00_env.sh"; else
  DVD_LOG="${DVD_LOG:-$BASE/attack_output/dvd.log}"; mkdir -p "$(dirname "$DVD_LOG")"
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
python3 - "${TARGET_IP}:${TARGET_PORT}" <<PY
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
import time
import curses
from pymavlink import mavutil

# Establish connection to the MAVLink device
connection = mavutil.mavlink_connection('tcp:10.13.0.3:5760')

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

