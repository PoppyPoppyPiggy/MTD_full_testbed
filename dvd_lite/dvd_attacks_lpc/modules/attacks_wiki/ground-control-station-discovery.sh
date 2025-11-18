#!/usr/bin/env bash
# Auto-generated from: Ground-Control-Station-Discovery.md
set -euo pipefail

# MTD_INTERFACE_START
# =======================================================================
# MTD 환경 변수를 통한 동적 타겟 획득
if [[ -z "${TARGET_IP:-}" || -z "${TARGET_PORT:-}" ]]; then
    echo "ERROR: TARGET_IP and TARGET_PORT environment variables are not set." >&2
    echo "Attack aborted. Must be run via attack_orchestrator.py with MTD state resolution." >&2
    exit 1
fi

# 서비스 타입에 따라 TARGET_PORT 기본값 설정
# GCS Discovery는 네트워크 환경을 타겟하지만, MAVLink 통신 영역을 가정합니다.
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

log "[ATTACK] id=ground-control-station-discovery src=Ground-Control-Station-Discovery.md"
log "[BLOCK 1] type=shell (Dynamic Network Discovery)"

# 1. TARGET_IP를 기반으로 서브넷 계산 (일반적인 /24 마스크 가정)
# 예: 10.13.0.6 -> 10.13.0.0/24
TARGET_SUBNET=$(echo "$TARGET_IP" | grep -oE '([0-9]{1,3}\.){3}')0/24

if [[ -z "${TARGET_SUBNET}" ]]; then
    log "[ERROR] Failed to determine subnet from TARGET_IP: ${TARGET_IP}"
    exit 1
fi

echo "[INFO] Scanning subnet ${TARGET_SUBNET} to locate Ground Control Station..."

# nmap을 사용하여 서브넷 내의 모든 호스트(현재 타겟 IP는 제외)에 대한 Ping Sweep 실행
# nmap -sn: Ping Sweep (호스트 발견 전용, 포트 스캔 없음)
# -sn 옵션은 MTD 환경의 RL 에이전트에게 현재 네트워크 맵을 재구성하는 데 필요한 정보를 제공합니다.
nmap -sn "${TARGET_SUBNET}" --exclude "${TARGET_IP}"

# 참고: 이 스캔 결과는 Orchestrator가 네트워크 상태 변화를 감지하는 데 사용됩니다.

log "[BLOCK 2] type=control (Execution Complete)"
log "Network discovery scan executed and output sent to orchestrator."