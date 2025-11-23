#!/usr/bin/env bash
set -euo pipefail

# Attack: Firmware Decompile (Binary Extraction & Analysis, MTD-aware)
# Target Service: DRONE_MAVLINK (Assumed context for environment validation)

# --- MTD_INTERFACE_START (Mandatory dynamic target acquisition) ---
# Orchestrator가 TARGET_IP, TARGET_PORT, TARGET_SERVICE를 주입해야 합니다.
if [[ -z "${TARGET_IP:-}" ]]; then
    echo "ERROR: TARGET_IP environment variable is not set." >&2
    echo "Attack aborted. Must be run via attack_orchestrator.py with MTD state resolution." >&2
    exit 1
fi

# 이 공격은 네트워크 포트와 무관하지만, 표준화를 위해 MAVLink 포트 컨텍스트를 사용합니다.
TARGET_PORT="${TARGET_PORT:-14550}"

echo "[INFO] Attack context validated (Target IP: ${TARGET_IP})"
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

log "[ATTACK] id=firmware-decompile src=Firmware-Decompile.md"

log "[BLOCK 1] type=shell (Find ArduCopter Binary Path)"
# Flight Controller 컨테이너 내부에서 arducopter 바이너리 경로를 찾습니다.
# 컨테이너 이름 'flight-controller'는 정적 이름이라고 가정합니다.
sudo docker exec flight-controller find / -name "arducopter" 2>/dev/null

log "[BLOCK 2] type=shell (Extract Binary from Container)"
# 찾은 바이너리를 공격자 시스템으로 복사합니다.
# 경로: /home/ardupilot/ArduCopter/build/sitl/bin/arducopter (일반적인 SITL 경로)
sudo docker cp flight-controller:/home/ardupilot/ArduCopter/build/sitl/bin/arducopter ./arducopter.bin
log "Extracted firmware binary to ./arducopter.bin"

log "[BLOCK 3] type=shell (Analyze Binary Format)"
# 파일 포맷 확인 (ELF, 아키텍처 등)
file ./arducopter.bin

log "[BLOCK 4] type=shell (Extract Strings for Reconnaissance)"
# 바이너리에서 문자열을 추출하여 파일로 저장합니다.
strings ./arducopter.bin > arducopter.strings
log "Extracted strings to arducopter.strings"

log "[BLOCK 5] type=shell (Generate Assembly Disassembly)"
# objdump를 사용하여 어셈블리 코드를 추출합니다.
objdump -D -M intel ./arducopter.bin > arducopter.asm
log "Generated disassembly to arducopter.asm"

log "[BLOCK 6] type=shell (Download Official Firmware for Comparison)"
# 외부에서 공식 APJ(ArduPilot Journal) 파일을 다운로드합니다.
wget -q -O arducopter.apj https://firmware.ardupilot.org/Copter/stable/Pixhawk1/arducopter.apj
log "Downloaded official firmware arducopter.apj"

log "[BLOCK 7] type=shell (Extract APJ Contents via Binwalk)"
# binwalk를 사용하여 APJ 파일의 내부 구조를 분석 및 추출합니다.
sudo binwalk -e ./arducopter.apj

log "[BLOCK 8] type=control (Decompilation Steps Completed)"
echo "[INFO] Firmware analysis steps completed. Results stored in local files."