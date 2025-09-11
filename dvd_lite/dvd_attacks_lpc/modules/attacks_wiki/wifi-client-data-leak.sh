#!/usr/bin/env bash
set -euo pipefail
export BASE="${BASE:-$PWD}"
if [[ -f "$BASE/00_env.sh" ]]; then . "$BASE/00_env.sh"; else
  DVD_LOG="${DVD_LOG:-$BASE/attack_output/dvd.log}"; mkdir -p "$(dirname "$DVD_LOG")"
  log(){ printf '[%(%F_%T)T] %s
' -1 "$*"; }
fi

# Auto-generated from: /home/kali/MTD_full_testbed/Damn-Vulnerable-Drone.wiki/Wifi-Client-Data-Leak.md
# Created: 2025-09-10 04:31:52
# NOTE: 설명/서사는 제거되었고, 코드블록/프롬프트 명령만 포함됩니다.
set -euo pipefail

# 기준 경로 (요구사항)
export BASE="${BASE:-$PWD}"

# 공통 로그 연결(선택사항) - 존재 시 로드
if [[ -f "$BASE/00_env.sh" ]]; then . "$BASE/00_env.sh"; else
  DVD_LOG="${DVD_LOG:-$BASE/attack_output/dvd.log}"; mkdir -p "$(dirname "$DVD_LOG")"
  log(){ echo "[`date +%F_%T`] $*"; }; export -f log
fi

log "[ATTACK] id=wifi-client-data-leak src=Wifi-Client-Data-Leak.md"
log "[BLOCK 1] type=shell"
/nicholasaleks/Damn-Vulnerable-Drone/wiki/Wifi-Analysis-&-Cracking

log "[BLOCK 2] type=shell"
tcpdump -i wlan0 -nn -s0 -w client_capture.pcap

log "[BLOCK 3] type=shell"
tcpdump -i wlan0 ether src <client_mac>

