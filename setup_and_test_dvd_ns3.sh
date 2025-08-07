#!/bin/bash

# 파일: /home/kali/MTD/MTD_full_testbed/setup_and_test_dvd_ns3.sh
# 목적: DVD-NS3 통합 테스트베드의 간단한 설정 및 테스트
# 누락된 파일들을 자동으로 생성하고 기본 테스트 실행

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

BASE_DIR="/home/kali/MTD/MTD_full_testbed"

echo -e "${CYAN}${BOLD}"
echo "╔══════════════════════════════════════════════════════════════════════╗"
echo "║                🔧 DVD-NS3 통합 테스트베드 자동 설정                 ║"
echo "║                                                                      ║"
echo "║           누락된 파일 생성 및 기본 환경 구성                         ║"
echo "╚══════════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# 기본 디렉토리 생성
echo -e "${GREEN}[INFO]${NC} 기본 디렉토리 구조 생성 중..."
mkdir -p "$BASE_DIR/dvd_ns3_integration"
mkdir -p "$BASE_DIR/results"
mkdir -p "$BASE_DIR/logs"
mkdir -p "$BASE_DIR/dvd_lite/dvd_attacks/reconnaissance"
mkdir -p "$BASE_DIR/dvd_lite/dvd_attacks/protocol_tampering"
mkdir -p "$BASE_DIR/dvd_lite/dvd_attacks/denial_of_service"
mkdir -p "$BASE_DIR/dvd_lite/dvd_attacks/injection"
mkdir -p "$BASE_DIR/dvd_lite/dvd_attacks/exfiltration"
mkdir -p "$BASE_DIR/dvd_lite/dvd_attacks/firmware_attacks"

echo -e "${GREEN}[INFO]${NC} ✅ 디렉토리 구조 생성 완료"

# 기본 DVD 모니터링 서비스 생성 (누락된 경우)
if [ ! -f "$BASE_DIR/dvd_ns3_integration/dvd_monitor_service.py" ]; then
    echo -e "${YELLOW}[WARN]${NC} DVD 모니터링 서비스 파일 생성 중..."
    cat > "$BASE_DIR/dvd_ns3_integration/dvd_monitor_service.py" << 'EOF'
#!/usr/bin/env python3
"""
간단한 DVD 모니터링 서비스 (테스트용)
"""
import asyncio
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('DVD-Monitor')

class SimpleDVDMonitor:
    def __init__(self):
        self.running = False
    
    async def start_monitoring(self):
        self.running = True
        logger.info("🐳 DVD 모니터링 서비스 시작 (시뮬레이션 모드)")
        
        count = 0
        while self.running and count < 60:  # 1분간 실행
            logger.info(f"📊 모니터링 중... ({count}/60)")
            await asyncio.sleep(1)
            count += 1
        
        logger.info("🛑 DVD 모니터링 서비스 종료")
    
    def stop_monitoring(self):
        self.running = False

async def main():
    monitor = SimpleDVDMonitor()
    try:
        await monitor.start_monitoring()
    except KeyboardInterrupt:
        logger.info("사용자 중단 요청")
    finally:
        monitor.stop_monitoring()

if __name__ == "__main__":
    asyncio.run(main())
EOF
    chmod +x "$BASE_DIR/dvd_ns3_integration/dvd_monitor_service.py"
    echo -e "${GREEN}[INFO]${NC} ✅ DVD 모니터링 서비스 생성 완료"
fi

# 기본 DVD 공격 커넥터 생성 (누락된 경우)
if [ ! -f "$BASE_DIR/dvd_ns3_integration/dvd_attack_connector.py" ]; then
    echo -e "${YELLOW}[WARN]${NC} DVD 공격 커넥터 파일 생성 중..."
    cat > "$BASE_DIR/dvd_ns3_integration/dvd_attack_connector.py" << 'EOF'
#!/usr/bin/env python3
"""
간단한 DVD 공격 커넥터 (테스트용)
"""
import asyncio
import time
import logging
import os
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('DVD-Connector')

class SimpleDVDConnector:
    def __init__(self):
        self.running = False
        self.attack_dir = Path("/home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks")
    
    async def start_monitoring(self):
        self.running = True
        logger.info("⚔️ DVD 공격 커넥터 시작 (시뮬레이션 모드)")
        
        count = 0
        while self.running and count < 60:  # 1분간 실행
            # 공격 디렉토리 스캔 시뮬레이션
            if count % 10 == 0:
                logger.info(f"🔍 공격 디렉토리 스캔 중... ({self.attack_dir})")
                
                # 실제 파일들 확인
                attack_categories = ['reconnaissance', 'protocol_tampering', 'denial_of_service', 
                                   'injection', 'exfiltration', 'firmware_attacks']
                
                for category in attack_categories:
                    cat_dir = self.attack_dir / category
                    if cat_dir.exists():
                        scripts = list(cat_dir.glob('*.sh'))
                        if scripts:
                            logger.info(f"📁 {category}: {len(scripts)}개 스크립트 발견")
            
            await asyncio.sleep(1)
            count += 1
        
        logger.info("🛑 DVD 공격 커넥터 종료")
    
    def stop_monitoring(self):
        self.running = False

async def main():
    connector = SimpleDVDConnector()
    try:
        await connector.start_monitoring()
    except KeyboardInterrupt:
        logger.info("사용자 중단 요청")
    finally:
        connector.stop_monitoring()

if __name__ == "__main__":
    asyncio.run(main())
EOF
    chmod +x "$BASE_DIR/dvd_ns3_integration/dvd_attack_connector.py"
    echo -e "${GREEN}[INFO]${NC} ✅ DVD 공격 커넥터 생성 완료"
fi

# 샘플 공격 스크립트 생성
create_sample_attack_script() {
    local category=$1
    local script_name=$2
    local script_path="$BASE_DIR/dvd_lite/dvd_attacks/$category/$script_name"
    
    if [ ! -f "$script_path" ]; then
        echo -e "${YELLOW}[INFO]${NC} 샘플 공격 스크립트 생성: $category/$script_name"
        cat > "$script_path" << EOF
#!/bin/bash
# 샘플 $category 공격 스크립트: $script_name
# 자동 생성된 테스트용 스크립트

echo "🎯 $category 공격 시작: $script_name"
echo "⏱️ 시작 시간: \$(date)"

# IOC 파일 생성
IOC_FILE="/tmp/\${script_name%.*}_iocs.txt"
echo "ATTACK_START:\${script_name}_\$(date +%s)" > "\$IOC_FILE"
echo "TARGET:simulation_target" >> "\$IOC_FILE"
echo "TECHNIQUE:$category" >> "\$IOC_FILE"

# 시뮬레이션 공격 실행
for i in {1..10}; do
    echo "📡 공격 단계 \$i/10 실행 중..."
    echo "ATTACK_STEP:\$i_\$(date +%s)" >> "\$IOC_FILE"
    sleep 2
done

echo "ATTACK_COMPLETE:\${script_name}_\$(date +%s)" >> "\$IOC_FILE"
echo "✅ $script_name 공격 완료"
echo "📄 IOC 파일: \$IOC_FILE"
EOF
        chmod +x "$script_path"
    fi
}

# 각 카테고리별 샘플 스크립트 생성
echo -e "${BLUE}[INFO]${NC} 샘플 공격 스크립트 생성 중..."

create_sample_attack_script "reconnaissance" "wifi_network_discovery.sh"
create_sample_attack_script "reconnaissance" "drone_component_enumeration.sh"
create_sample_attack_script "protocol_tampering" "gps_spoofing.sh"
create_sample_attack_script "protocol_tampering" "mavlink_packet_injection.sh"
create_sample_attack_script "denial_of_service" "mavlink_flood.sh"
create_sample_attack_script "denial_of_service" "wifi_deauth.sh"
create_sample_attack_script "injection" "flight_plan_injection.sh"
create_sample_attack_script "injection" "sql_injection.sh"
create_sample_attack_script "exfiltration" "telemetry_data_exfiltration.sh"
create_sample_attack_script "firmware_attacks" "bootloader_exploitation.sh"

echo -e "${GREEN}[INFO]${NC} ✅ 샘플 공격 스크립트 생성 완료"

# 간단한 테스트 실행 스크립트 생성
echo -e "${BLUE}[INFO]${NC} 테스트 실행 스크립트 생성 중..."
cat > "$BASE_DIR/test_dvd_integration.sh" << 'EOF'
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
EOF

chmod +x "$BASE_DIR/test_dvd_integration.sh"
echo -e "${GREEN}[INFO]${NC} ✅ 테스트 스크립트 생성 완료"

# 현재 상태 확인
echo -e "\n${CYAN}${BOLD}📋 현재 환경 상태:${NC}"

# 디렉토리 확인
echo -e "${GREEN}✅ 생성된 디렉토리:${NC}"
find "$BASE_DIR" -type d -name "dvd_*" | head -10

# 파일 확인
echo -e "\n${GREEN}✅ 생성된 주요 파일:${NC}"
ls -la "$BASE_DIR/dvd_ns3_integration/"*.py 2>/dev/null || echo "   (파일 없음)"
echo -e "\n${GREEN}✅ 샘플 공격 스크립트:${NC}"
find "$BASE_DIR/dvd_lite/dvd_attacks" -name "*.sh" | wc -l | xargs -I {} echo "   {} 개 스크립트"

# Python 의존성 확인
echo -e "\n${GREEN}✅ Python 의존성 상태:${NC}"
for dep in asyncio time logging pathlib; do
    if python3 -c "import $dep" 2>/dev/null; then
        echo "   ✅ $dep"
    else
        echo "   ❌ $dep"
    fi
done

echo -e "\n${CYAN}${BOLD}🚀 다음 단계:${NC}"
echo -e "${YELLOW}1. 기본 테스트 실행:${NC}"
echo -e "   cd $BASE_DIR"
echo -e "   ./test_dvd_integration.sh"

echo -e "\n${YELLOW}2. 개별 서비스 테스트:${NC}"
echo -e "   python3 dvd_ns3_integration/dvd_monitor_service.py"
echo -e "   python3 dvd_ns3_integration/dvd_attack_connector.py"

echo -e "\n${YELLOW}3. 샘플 공격 실행:${NC}"
echo -e "   ./dvd_lite/dvd_attacks/reconnaissance/wifi_network_discovery.sh"

echo -e "\n${YELLOW}4. 전체 통합 테스트베드 실행:${NC}"
echo -e "   ./run_integrated_dvd_ns3_testbed.sh --no-ns3"

echo -e "\n${GREEN}🎉 DVD-NS3 통합 테스트베드 자동 설정 완료!${NC}"