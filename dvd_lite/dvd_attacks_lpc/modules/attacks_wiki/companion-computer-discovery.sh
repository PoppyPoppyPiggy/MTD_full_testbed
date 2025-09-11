#!/usr/bin/env bash
set -euo pipefail
export BASE="${BASE:-$PWD}"
if [[ -f "$BASE/00_env.sh" ]]; then . "$BASE/00_env.sh"; else
  DVD_LOG="${DVD_LOG:-$BASE/attack_output/dvd.log}"; mkdir -p "$(dirname "$DVD_LOG")"
  log(){ printf '[%(%F_%T)T] %s
' -1 "$*"; }
fi

# Auto-generated from: /home/kali/MTD_full_testbed/Damn-Vulnerable-Drone.wiki/Companion-Computer-Discovery.md
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

log "[ATTACK] id=companion-computer-discovery src=Companion-Computer-Discovery.md"
log "[BLOCK 1] type=shell"
ip addr show

log "[BLOCK 2] type=shell"
nmap -sn 10.13.0.0/24 --exclude 10.13.0.1,10.13.0.5

log "[BLOCK 3] type=shell"
nmap 10.13.0.3

log "[BLOCK 4] type=shell"
Starting Nmap 7.94SVN ( https://nmap.org ) at 2024-08-02 19:00 EDT
Nmap scan report for 10.13.0.3
Host is up (0.000066s latency).
Not shown: 997 closed tcp ports (conn-refused)
PORT     STATE SERVICE
22/tcp   open  ssh
554/tcp  open  rtsp
3000/tcp open  ppp
Nmap done: 1 IP address (1 host up) scanned in 0.07 seconds

log "[BLOCK 5] type=shell"
nmap -sn 192.168.13.0/24 --exclude 192.168.13.10

log "[BLOCK 6] type=shell"
nmap 192.168.13.1

log "[BLOCK 7] type=shell"
Starting Nmap 7.94SVN ( https://nmap.org ) at 2024-08-02 19:00 EDT
Nmap scan report for 192.168.13.1
Host is up (0.000066s latency).
Not shown: 997 closed tcp ports (conn-refused)
PORT     STATE SERVICE
22/tcp   open  ssh
554/tcp  open  rtsp
3000/tcp open  ppp
Nmap done: 1 IP address (1 host up) scanned in 0.07 seconds

