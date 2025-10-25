#!/usr/bin/env bash

# --- Process Command Line Arguments ---
# Example: Assign first arg to INTENSITY, default 'medium'
# INTENSITY="${1:-medium}"
# Example: Assign second arg to DURATION_SECONDS, default '30'
# DURATION_SECONDS="${2:-30}"
# echo "Parameters: Intensity=$INTENSITY, Duration=$DURATION_SECONDS"
# Add more parameter processing as needed for the specific script
# ------------------------------------

# Auto-generated from: /home/kali/MTD_full_testbed/Damn-Vulnerable-Drone.wiki/Firmware-Decompile.md
# Created: 2025-09-14 13:46:03
# NOTE: 설명/서사는 제거되었고, 코드블록/프롬프트 명령만 포함됩니다.

# MTD_INTERFACE_START
# =======================================================================
# MTD-aware Target Acquisition (from Orchestrator Environment)
# =======================================================================
# 이 스크립트는 attack_orchestrator.py에 의해 TARGET_IP와 TARGET_PORT 환경 변수가
# 설정될 것을 기대하고 실행됩니다.

if [[ -z "${TARGET_IP:-}" || -z "${TARGET_PORT:-}" ]]; then
    echo "ERROR: TARGET_IP and TARGET_PORT environment variables are not set." >&2
    echo "This script must be run via the attack_orchestrator.py" >&2
    exit 1
fi

echo "[INFO] Attack target acquired from orchestrator: ${TARGET_IP}:${TARGET_PORT}"
# MTD_INTERFACE_END

set -euo pipefail

# 기준 경로 (요구사항)
export BASE="${BASE:-$PWD}"

# 공통 로그 연결(선택사항) - 존재 시 로드
if [[ -f "$BASE/00_env.sh" ]]; then . "$BASE/00_env.sh"; else
  DVD_LOG="${DVD_LOG:-$BASE/attack_output/dvd.log}"; mkdir -p "$(dirname "$DVD_LOG")"
  log(){ echo "[`date +%F_%T`] $*"; }; export -f log
fi

log "[ATTACK] id=firmware-decompile src=Firmware-Decompile.md"
log "[BLOCK 1] type=shell"
docker exec -it flight-controller bash

log "[BLOCK 2] type=shell"
find / -name "arducopter" 2>/dev/null

log "[BLOCK 3] type=shell"
/home/ardupilot/ArduCopter/build/sitl/bin/arducopter

log "[BLOCK 4] type=shell"
docker cp ardupilot:/home/ardupilot/ArduCopter/build/sitl/bin/arducopter ./arducopter.bin

log "[BLOCK 5] type=shell"
file arducopter.bin

log "[BLOCK 6] type=shell"
ELF 64-bit LSB executable, x86-64, dynamically linked

log "[BLOCK 7] type=shell"
strings arducopter.bin | less

log "[BLOCK 8] type=shell"
objdump -D -M intel arducopter.bin > arducopter.asm

log "[BLOCK 9] type=shell"
wget https://firmware.ardupilot.org/Copter/stable/Pixhawk1/arducopter.apj

log "[BLOCK 10] type=shell"
binwalk -e arducopter.apj
