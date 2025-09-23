#!/usr/bin/env bash
#
# reset_bus.sh (v3.0)
# MTD 테스트베드의 모든 로그 파일과 이전 데이터셋을 백업하고 초기화합니다.
#
set -Eeuo pipefail

# 스크립트의 실제 위치를 기준으로 프로젝트 루트 디렉토리를 찾습니다.
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
BASE_DIR=$( cd -- "$SCRIPT_DIR/.." &> /dev/null && pwd )

# 안전 가드: 경로가 올바른지 확인
if ! [[ "$BASE_DIR" == *"/dvd_attacks_lpc" ]]; then
    echo "❌ [오류] 잘못된 기본 경로입니다: $BASE_DIR"
    echo "   이 스크립트는 'dvd_attacks_lpc/tools' 디렉토리 내에 위치해야 합니다."
    exit 1
fi

TS="$(date +%Y%m%d_%H%M%S)"
cd "$BASE_DIR"
echo "[*] 작업 디렉토리: $BASE_DIR"

# 1) 이전 로그 및 데이터 백업
BACKUP_DIR="backups"
mkdir -p "$BACKUP_DIR"
BACKUP_FILE="${BACKUP_DIR}/experiment_backup_${TS}.tar.gz"
TARGETS_TO_BACKUP=""

if [ -d "bus" ]; then
    TARGETS_TO_BACKUP+=" bus"
fi
if [ -f "labeled_cti_dataset.csv" ]; then
    TARGETS_TO_BACKUP+=" labeled_cti_dataset.csv"
fi

if [ -n "$TARGETS_TO_BACKUP" ]; then
    tar -czf "$BACKUP_FILE" $TARGETS_TO_BACKUP
    echo "📦 [백업 완료] -> ${BACKUP_FILE}"
else
    echo "[-] 백업할 기존 로그나 데이터셋이 없습니다."
fi

# 2) 기존 로그 및 데이터셋 흔적 제거
echo "[*] 기존 로그 및 데이터셋을 삭제합니다..."
rm -rf bus
rm -f labeled_cti_dataset.csv

# 3) bus 디렉토리 및 모든 로그 파일 재생성
echo "[*] 새로운 이벤트 버스 및 로그 파일을 생성합니다..."
mkdir -p bus/captures/pcap

touch bus/bus.log
touch bus/bus_dvd.log
touch bus/bus_system_events.log
touch bus/bus_network.log

# 파일 권한 설정 (모든 사용자가 쓸 수 있도록)
chmod 666 bus/*.log

echo "✅ [초기화 완료] 모든 로그가 성공적으로 초기화되었습니다."
echo "   - $BASE_DIR/bus"