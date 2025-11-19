#!/usr/bin/env bash
set -euo pipefail

# Attack: Companion Computer Discovery (Nmap Scan, MTD-aware)
# Target Service: COMPANION_HTTP (Default Port 8080 assumed for context)

# --- MTD_INTERFACE_START (Mandatory dynamic target acquisition) ---
# Orchestrator가 TARGET_IP, TARGET_PORT, TARGET_SERVICE를 주입해야 합니다.
if [[ -z "${TARGET_IP:-}" || -z "${TARGET_PORT:-}" ]]; then
    echo "ERROR: TARGET_IP and TARGET_PORT environment variables are not set." >&2
    echo "Attack aborted. Must be run via attack_orchestrator.py with MTD state resolution." >&2
    exit 1
fi

# 서비스 타입별 기본 포트 설정 (이 공격은 포트를 직접 사용하지 않지만, 컨텍스트를 위해 설정)
case "${TARGET_SERVICE:-COMPANION_HTTP}" in
    COMPANION_HTTP)
        TARGET_PORT="${TARGET_PORT:-8080}"
        ;;
    *)
        : # 다른 서비스는 Orchestrator가 포트 값을 넣어준다고 가정
        ;;
esac

echo "[INFO] Target acquired: ${TARGET_IP}:${TARGET_PORT} (service=${TARGET_SERVICE:-UNKNOWN})"
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

log "[ATTACK] id=companion-computer-discovery src=Companion-Computer-Discovery.md"

log "[BLOCK 1] type=shell (Local Interface Status)"
# 공격자가 속한 시스템의 네트워크 정보 확인 (탐색의 기본 단계)
ip addr show

log "[BLOCK 2] type=shell (Dynamic Subnet Discovery - ARP/Ping Scan)"
# Orchestrator가 제공한 TARGET_IP를 기반으로 해당 서브넷(/24) 내의 활성 호스트를 탐색합니다.
# TARGET_IP에서 첫 세 옥텟을 추출하여 네트워크 CIDR을 만듭니다. (예: 10.13.0.10 -> 10.13.0.0/24)
# awk 사용이 불가능한 환경을 고려하여, bash native string manipulation을 사용합니다.
TARGET_NETWORK="${TARGET_IP%.*}.0/24"
log "Scanning network ${TARGET_NETWORK} derived from ${TARGET_IP}..."
# -sn: Ping Scan - 호스트가 활성화되어 있는지 확인
sudo nmap -sn "${TARGET_NETWORK}" --exclude "${TARGET_IP}"

log "[BLOCK 3] type=shell (Target Detailed Port Scan)"
# 현재 타겟으로 지정된 Companion Computer의 주요 포트를 스캔합니다.
sudo nmap "${TARGET_IP}"

log "[BLOCK 4] type=control (Discovery Completed)"
# 탐지 공격은 여기서 완료됩니다.