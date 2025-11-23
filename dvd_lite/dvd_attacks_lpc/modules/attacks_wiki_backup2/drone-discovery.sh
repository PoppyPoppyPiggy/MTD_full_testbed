#!/usr/bin/env bash
set -euo pipefail

# Attack: Drone Discovery (Nmap Scan, MTD-aware)
# Target Service: DRONE_MAVLINK (Default Port 14550 assumed for context)

# --- MTD_INTERFACE_START (Mandatory dynamic target acquisition) ---
# Orchestrator가 TARGET_IP, TARGET_PORT, TARGET_SERVICE를 주입해야 합니다.
if [[ -z "${TARGET_IP:-}" || -z "${TARGET_PORT:-}" ]]; then
    echo "ERROR: TARGET_IP and TARGET_PORT environment variables are not set." >&2
    echo "Attack aborted. Must be run via attack_orchestrator.py with MTD state resolution." >&2
    exit 1
fi

# 서비스 타입별 기본 포트 설정 (이 공격은 포트를 직접 사용하지 않지만, 컨텍스트를 위해 설정)
case "${TARGET_SERVICE:-DRONE_MAVLINK}" in
    DRONE_MAVLINK)
        TARGET_PORT="${TARGET_PORT:-14550}"
        ;;
    *)
        : # 다른 서비스는 Orchestrator가 포트 값을 넣어준다고 가정
        ;;
esac

echo "[INFO] Target acquired: ${TARGET_IP}:${TARGET_PORT} (service=${TARGET_SERVICE:-DRONE_MAVLINK})"
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

log "[ATTACK] id=drone-discovery src=Drone-Discovery.md"

log "[BLOCK 1] type=shell (Local Interface Status)"
# 공격자가 속한 시스템의 네트워크 정보 확인 (탐색의 기본 단계)
ip addr show

log "[BLOCK 2] type=shell (Dynamic Subnet Discovery - ARP/Ping Scan)"
# TARGET_IP를 기반으로 서브넷을 추출합니다. (예: 10.13.0.10 -> 10.13.0.0/24)
TARGET_NETWORK="${TARGET_IP%.*}.0/24"
log "Scanning network ${TARGET_NETWORK} derived from ${TARGET_IP}..."
# -sn: Ping Scan (활성 호스트 탐색)
# --exclude 옵션은 제거하여 TARGET_IP를 포함한 전체 서브넷을 탐색합니다.
sudo nmap -sn "${TARGET_NETWORK}"

log "[BLOCK 3] type=shell (Dynamic Target Detailed Port Scan)"
# TARGET_IP에 대한 자세한 포트 스캔을 수행합니다.
# 원본 스크립트의 포트 범위 1-16000을 유지합니다.
sudo nmap "${TARGET_IP}" -p 1-16000

log "[BLOCK 4] type=control (Discovery Completed)"
# 탐지 공격은 여기서 완료됩니다.