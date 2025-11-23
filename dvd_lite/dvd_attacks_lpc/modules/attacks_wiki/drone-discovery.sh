#!/usr/bin/env bash
# Auto-generated from: /home/kali/MTD_full_testbed/Damn-Vulnerable-Drone.wiki/Drone-Discovery.md
# Created: 2025-11-23 15:43:26
# NOTE: 설명/서사는 제거되었고, 코드블록/프롬프트 명령만 포함됩니다.
set -euo pipefail

# 기준 경로 (요구사항)
export BASE="${BASE:-$PWD}"

# 공통 로그 연결(선택사항) - 존재 시 로드
if [[ -f "$BASE/00_env.sh" ]]; then . "$BASE/00_env.sh"; else
  DVD_LOG="${DVD_LOG:-$BASE/attack_output/dvd.log}"; mkdir -p "$(dirname "$DVD_LOG")"
  log(){ echo "[`date +%F_%T`] $*"; }; export -f log
fi

log "[ATTACK] id=drone-discovery src=Drone-Discovery.md"
log "[BLOCK 1] type=shell"
ip addr show

log "[BLOCK 2] type=shell"
nmap -sn 10.13.0.0/24 --exclude 10.13.0.1,10.13.0.5

log "[BLOCK 3] type=shell"
nmap 10.13.0.0/24 -p 1-16000 --exclude 10.13.0.1,10.13.0.5

log "[BLOCK 4] type=shell"
nmap -sn 192.168.13.0/24 --exclude 192.168.13.10

log "[BLOCK 5] type=shell"
nmap 192.168.13.0/24 -p 1-16000 --exclude 192.168.13.10

