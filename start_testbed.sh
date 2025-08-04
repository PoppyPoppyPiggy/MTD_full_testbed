#!/bin/bash
# 통합 MTD 테스트베드 시작 스크립트
# 위치: ~/MTD/MTD_full_testbed/start_testbed.sh

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
NC='\033[0m' # No Color

# 로고 출력
echo -e "${CYAN}"
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║                                                               ║"
echo "║    🚁 FANET NS-3 통합 MTD 드론 보안 테스트베드              ║"
echo "║                                                               ║"
echo "║    • NS-3 FANET 네트워크 시뮬레이션                         ║"
echo "║    • ArduPilot SITL + Gazebo 드론 시뮬레이터                ║"
echo "║    • 실시간 CTI 수집 및 기계학습 분석                        ║"
echo "║    • MTD 방어 메커니즘                                       ║"
echo "║    • 기존 DVD 시스템 완전 통합                              ║"
echo "║                                                               ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# 함수 정의
check_requirements() {
    echo -e "${BLUE}📋 시스템 요구사항 확인 중...${NC}"
    
    # Docker 확인
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}❌ Docker가 설치되지 않았습니다.${NC}"
        exit 1
    fi
    
    # Docker Compose 확인
    if ! command -v docker-compose &> /dev/null; then
        echo -e "${RED}❌ Docker Compose가 설치되지 않았습니다.${NC}"
        exit 1
    fi
    
    # Python 확인
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}❌ Python 3가 설치되지 않았습니다.${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✅ 모든 요구사항이 충족되었습니다.${NC}"
}

build_containers() {
    echo -e "${BLUE}🔨 Docker 컨테이너 빌드 중...${NC}"
    
    # 기존 컨테이너 정리
    docker-compose -f docker-compose-mtd.yml down -v --remove-orphans 2>/dev/null || true
    
    # 컨테이너 빌드
    docker-compose -f docker-compose-mtd.yml build --no-cache
    
    echo -e "${GREEN}✅ 컨테이너 빌드 완료${NC}"
}

start_core_services() {
    echo -e "${BLUE}🚀 핵심 서비스 시작 중...${NC}"
    
    # 모니터링 서비스 먼저 시작
    docker-compose -f docker-compose-mtd.yml up -d elasticsearch kibana grafana prometheus
    
    # 잠시 대기 (ElasticSearch 초기화)
    echo -e "${YELLOW}⏳ ElasticSearch 초기화 대기 중...${NC}"
    sleep 30
    
    # 로그 수집 서비스
    docker-compose -f docker-compose-mtd.yml up -d fluentd falco-security
    
    echo -e "${GREEN}✅ 핵심 서비스 시작 완료${NC}"
}

start_simulation_services() {
    echo -e "${BLUE}🎮 시뮬레이션 서비스 시작 중...${NC}"
    
    # ArduPilot SITL
    docker-compose -f docker-compose-mtd.yml up -d ardupilot-sitl
    
    # 잠시 대기
    sleep 10
    
    # Gazebo 시뮬레이터
    docker-compose -f docker-compose-mtd.yml up -d gazebo-simulator
    
    # NS-3 FANET 시뮬레이터
    docker-compose -f docker-compose-mtd.yml up -d ns3-fanet-simulator
    
    echo -e "${GREEN}✅ 시뮬레이션 서비스 시작 완료${NC}"
}

start_security_services() {
    echo -e "${BLUE}🔒 보안 서비스 시작 중...${NC}"
    
    # MTD 오케스트레이터
    docker-compose -f docker-compose-mtd.yml up -d mtd-orchestrator
    
    # CTI 분석기
    docker-compose -f docker-compose-mtd.yml up -d cti-analyzer
    
    # 네트워크 분석 도구
    docker-compose -f docker-compose-mtd.yml up -d zeek-analyzer suricata-ids
    
    echo -e "${GREEN}✅ 보안 서비스 시작 완료${NC}"
}

start_dvd_services() {
    echo -e "${BLUE}🎯 DVD 호환 서비스 시작 중...${NC}"
    
    # DVD 컴패니언 컴퓨터
    docker-compose -f docker-compose-mtd.yml up -d dvd-companion
    
    # DVD 공격 실행기
    docker-compose -f docker-compose-mtd.yml up -d dvd-attack-runner
    
    # QGroundControl 시뮬레이터
    docker-compose -f docker-compose-mtd.yml up -d qgroundcontrol-sim
    
    echo -e "${GREEN}✅ DVD 서비스 시작 완료${NC}"
}

show_status() {
    echo -e "${BLUE}📊 시스템 상태${NC}"
    echo "================================"
    
    docker-compose -f docker-compose-mtd.yml ps
    
    echo ""
    echo -e "${CYAN}📡 접속 정보${NC}"
    echo "================================"
    echo -e "${WHITE}• Kibana 대시보드:${NC} http://localhost:5601"
    echo -e "${WHITE}• Grafana 모니터링:${NC} http://localhost:3000 (admin/mtdadmin)"
    echo -e "${WHITE}• DVD 웹 인터페이스:${NC} http://localhost:80"
    echo -e "${WHITE}• CTI API 서버:${NC} http://localhost:8090"
    echo -e "${WHITE}• MISP 플랫폼:${NC} https://localhost:8443"
    echo -e "${WHITE}• QGroundControl VNC:${NC} localhost:5900"
    echo ""
    echo -e "${WHITE}• MAVLink 연결:${NC} udp://localhost:14550"
    echo -e "${WHITE}• MAVLink GCS:${NC} udp://localhost:14551"
    echo ""
}

run_tests() {
    echo -e "${BLUE}🧪 기본 테스트 실행 중...${NC}"
    
    # 통합 테스트베드 스크립트 실행
    python3 fanet_mtd_testbed.py &
    TESTBED_PID=$!
    
    echo -e "${GREEN}✅ 테스트베드가 백그라운드에서 실행 중입니다 (PID: $TESTBED_PID)${NC}"
    echo -e "${YELLOW}⏹️  중지하려면: kill $TESTBED_PID${NC}"
}

# 메인 실행 로직
main() {
    case "${1:-all}" in
        "check")
            check_requirements
            ;;
        "build")
            check_requirements
            build_containers
            ;;
        "core")
            start_core_services
            ;;
        "sim")
            start_simulation_services
            ;;
        "security")
            start_security_services
            ;;
        "dvd")
            start_dvd_services
            ;;
        "status")
            show_status
            ;;
        "test")
            run_tests
            ;;
        "stop")
            echo -e "${YELLOW}🛑 서비스 중지 중...${NC}"
            docker-compose -f docker-compose-mtd.yml down
            echo -e "${GREEN}✅ 모든 서비스가 중지되었습니다.${NC}"
            ;;
        "clean")
            echo -e "${YELLOW}🧹 완전 정리 중...${NC}"
            docker-compose -f docker-compose-mtd.yml down -v --remove-orphans
            docker system prune -af
            echo -e "${GREEN}✅ 시스템 정리 완료${NC}"
            ;;
        "all"|*)
            check_requirements
            build_containers
            start_core_services
            start_simulation_services
            start_security_services
            start_dvd_services
            show_status
            run_tests
            ;;
    esac
}

# 시그널 핸들러
cleanup() {
    echo -e "${YELLOW}\n🛑 종료 신호 수신. 정리 중...${NC}"
    docker-compose -f docker-compose-mtd.yml down
    exit 0
}

trap cleanup SIGINT SIGTERM

# 사용법 출력
if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    echo "사용법: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  all      모든 서비스 시작 (기본값)"
    echo "  check    시스템 요구사항 확인"
    echo "  build    Docker 컨테이너 빌드"
    echo "  core     핵심 모니터링 서비스 시작"
    echo "  sim      시뮬레이션 서비스 시작"
    echo "  security 보안 서비스 시작"
    echo "  dvd      DVD 호환 서비스 시작"
    echo "  status   시스템 상태 확인"
    echo "  test     테스트베드 실행"
    echo "  stop     모든 서비스 중지"
    echo "  clean    완전 정리 (컨테이너 및 볼륨 삭제)"
    echo ""
    exit 0
fi

# 메인 함수 실행
main "$1"
