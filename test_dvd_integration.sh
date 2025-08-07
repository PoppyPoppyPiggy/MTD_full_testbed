#!/bin/bash
# 간단한 DVD 통합 테스트

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

BASE_DIR="/home/kali/MTD/MTD_full_testbed"
RESULTS_DIR="$BASE_DIR/results/test_$(date +%Y%m%d_%H%M%S)"

echo -e "${BLUE}🧪 DVD 통합 테스트 시작${NC}"

# 결과 디렉토리 생성
mkdir -p "$RESULTS_DIR"

# 1. DVD 모니터링 서비스 테스트
echo -e "${YELLOW}1. DVD 모니터링 서비스 테스트${NC}"
cd "$BASE_DIR"
timeout 30 python3 dvd_ns3_integration/dvd_monitor_service.py > "$RESULTS_DIR/monitor_test.log" 2>&1 &
MONITOR_PID=$!

# 2. DVD 공격 커넥터 테스트
echo -e "${YELLOW}2. DVD 공격 커넥터 테스트${NC}"
timeout 30 python3 dvd_ns3_integration/dvd_attack_connector.py > "$RESULTS_DIR/connector_test.log" 2>&1 &
CONNECTOR_PID=$!

# 3. 샘플 공격 스크립트 실행
echo -e "${YELLOW}3. 샘플 공격 스크립트 테스트${NC}"
./dvd_lite/dvd_attacks/reconnaissance/wifi_network_discovery.sh > "$RESULTS_DIR/attack_test.log" 2>&1 &
ATTACK_PID=$!

# 4. 모든 프로세스 완료 대기
echo -e "${YELLOW}4. 테스트 실행 중... (30초)${NC}"
sleep 35

# 5. 결과 확인
echo -e "${GREEN}📊 테스트 결과:${NC}"

if [ -f "$RESULTS_DIR/monitor_test.log" ]; then
    echo "✅ 모니터링 서비스 로그: $(wc -l < "$RESULTS_DIR/monitor_test.log") 라인"
fi

if [ -f "$RESULTS_DIR/connector_test.log" ]; then
    echo "✅ 커넥터 로그: $(wc -l < "$RESULTS_DIR/connector_test.log") 라인"
fi

if [ -f "$RESULTS_DIR/attack_test.log" ]; then
    echo "✅ 공격 테스트 로그: $(wc -l < "$RESULTS_DIR/attack_test.log") 라인"
fi

# IOC 파일 확인
IOC_COUNT=$(find /tmp -name "*iocs.txt" 2>/dev/null | wc -l)
echo "✅ 생성된 IOC 파일: $IOC_COUNT 개"

echo -e "${GREEN}🎉 DVD 통합 테스트 완료!${NC}"
echo -e "${BLUE}📁 결과 디렉토리: $RESULTS_DIR${NC}"
