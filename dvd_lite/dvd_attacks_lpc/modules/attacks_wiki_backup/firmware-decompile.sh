#!/usr/bin/env bash
# Auto-generated from: /home/kali/MTD_full_testbed/Damn-Vulnerable-Drone.wiki/Firmware-Decompile.md
# Created: 2025-09-14 13:46:03
# NOTE: 설명/서사는 제거되었고, 코드블록/프롬프트 명령만 포함됩니다.
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

