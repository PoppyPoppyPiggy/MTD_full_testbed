#!/bin/bash
# 의존성 없는 간단한 DVD 분석 실행 스크립트
# 위치: /home/kali/MTD/MTD_full_testbed/simple_run.sh

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}"
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║                                                           ║"
echo "║    🚁 간단한 DVD 분석기 (의존성 없음)                   ║"
echo "║                                                           ║"
echo "║    • Docker CLI만 사용                                   ║"
echo "║    • Python 외부 라이브러리 불필요                       ║"
echo "║    • 실시간 로그 및 네트워크 모니터링                    ║"
echo "║                                                           ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# DVD 컨테이너 감지
detect_dvd_containers() {
    echo -e "${BLUE}🔍 DVD 컨테이너 감지...${NC}"
    
    # 실행 중인 컨테이너 확인
    echo -e "${CYAN}현재 실행 중인 컨테이너:${NC}"
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Image}}"
    
    echo ""
    
    # DVD 관련 컨테이너 찾기
    DVD_CONTAINERS=($(docker ps --format "{{.Names}}" | grep -E "(dvd|companion|flight|ground|simulator)" || true))
    
    if [ ${#DVD_CONTAINERS[@]} -eq 0 ]; then
        echo -e "${RED}❌ DVD 관련 컨테이너를 찾을 수 없습니다.${NC}"
        echo -e "${YELLOW}💡 DVD 환경을 시작하세요:${NC}"
        echo "cd Damn-Vulnerable-Drone && docker-compose up -d"
        return 1
    fi
    
    echo -e "${GREEN}✅ 발견된 DVD 컨테이너:${NC}"
    for i in "${!DVD_CONTAINERS[@]}"; do
        container="${DVD_CONTAINERS[$i]}"
        echo -e "${CYAN}  $((i+1)). ${container}${NC}"
        
        # IP 주소 확인
        CONTAINER_IP=$(docker inspect "$container" --format='{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' 2>/dev/null || echo "N/A")
        echo -e "${YELLOW}     IP: ${CONTAINER_IP}${NC}"
    done
    
    return 0
}

# 컨테이너 선택
select_container() {
    if [ ${#DVD_CONTAINERS[@]} -eq 1 ]; then
        SELECTED_CONTAINER="${DVD_CONTAINERS[0]}"
        echo -e "${GREEN}🎯 자동 선택: ${SELECTED_CONTAINER}${NC}"
        return 0
    fi
    
    echo ""
    echo -e "${YELLOW}분석할 컨테이너를 선택하세요:${NC}"
    
    while true; do
        read -p "선택 (1-${#DVD_CONTAINERS[@]}): " choice
        
        if [[ "$choice" =~ ^[0-9]+$ ]] && [ "$choice" -ge 1 ] && [ "$choice" -le "${#DVD_CONTAINERS[@]}" ]; then
            SELECTED_CONTAINER="${DVD_CONTAINERS[$((choice-1))]}"
            echo -e "${GREEN}🎯 선택됨: ${SELECTED_CONTAINER}${NC}"
            break
        else
            echo -e "${RED}❌ 잘못된 선택입니다. 1-${#DVD_CONTAINERS[@]} 사이의 숫자를 입력하세요.${NC}"
        fi
    done
    
    return 0
}

# 간단한 분석 실행
run_simple_analysis() {
    echo -e "${BLUE}🚀 간단한 분석 시작...${NC}"
    
    if [ ! -f "simple_dvd_analyzer_nodeps.py" ]; then
        echo -e "${RED}❌ simple_dvd_analyzer_nodeps.py 파일이 없습니다.${NC}"
        echo -e "${YELLOW}💡 먼저 파일을 생성하세요.${NC}"
        return 1
    fi
    
    echo -e "${GREEN}🎯 분석 대상: ${SELECTED_CONTAINER}${NC}"
    echo -e "${YELLOW}⏹️ 분석 중 Ctrl+C로 언제든 중지할 수 있습니다.${NC}"
    echo ""
    
    python3 simple_dvd_analyzer_nodeps.py "$SELECTED_CONTAINER"
}

# 빠른 네트워크 캡처 (tcpdump)
quick_network_capture() {
    echo -e "${BLUE}📡 빠른 네트워크 캡처...${NC}"
    
    # 컨테이너 IP 가져오기
    CONTAINER_IP=$(docker inspect "$SELECTED_CONTAINER" --format='{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' 2>/dev/null)
    
    if [ -z "$CONTAINER_IP" ]; then
        echo -e "${RED}❌ 컨테이너 IP를 찾을 수 없습니다.${NC}"
        return 1
    fi
    
    echo -e "${GREEN}🎯 대상 IP: ${CONTAINER_IP}${NC}"
    
    # 결과 디렉토리 생성
    mkdir -p results
    
    # 타임스탬프
    TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
    PCAP_FILE="results/quick_capture_${TIMESTAMP}.pcap"
    
    echo -e "${YELLOW}📄 캡처 파일: ${PCAP_FILE}${NC}"
    echo -e "${YELLOW}⏰ 30초간 캡처합니다...${NC}"
    echo -e "${YELLOW}⏹️ Ctrl+C로 조기 종료 가능${NC}"
    
    # tcpdump 실행 (30초 제한)
    timeout 30 tcpdump -i any -w "$PCAP_FILE" "host $CONTAINER_IP and (port 14550 or port 14551 or port 5760 or port 3000 or port 8080)" 2>/dev/null || {
        echo -e "${YELLOW}⚠️ tcpdump 실행 실패 또는 조기 종료${NC}"
    }
    
    if [ -f "$PCAP_FILE" ]; then
        FILE_SIZE=$(stat -c%s "$PCAP_FILE" 2>/dev/null || echo "0")
        echo -e "${GREEN}✅ 캡처 완료: ${PCAP_FILE} (${FILE_SIZE} bytes)${NC}"
        
        # 간단한 분석
        echo -e "${BLUE}📊 캡처된 패킷 샘플:${NC}"
        tcpdump -r "$PCAP_FILE" -c 5 2>/dev/null || echo "패킷 분석 실패"
        
        # 패킷 수 계산
        PACKET_COUNT=$(tcpdump -r "$PCAP_FILE" 2>/dev/null | wc -l)
        echo -e "${GREEN}📈 총 패킷 수: ${PACKET_COUNT}${NC}"
        
    else
        echo -e "${RED}❌ 캡처 파일이 생성되지 않았습니다.${NC}"
    fi
}

# 실시간 로그 모니터링
monitor_logs() {
    echo -e "${BLUE}📋 실시간 로그 모니터링...${NC}"
    echo -e "${GREEN}🎯 대상: ${SELECTED_CONTAINER}${NC}"
    echo -e "${YELLOW}⏹️ Ctrl+C로 중지${NC}"
    echo ""
    
    # 로그 파일 저장
    mkdir -p results
    TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
    LOG_FILE="results/live_logs_${TIMESTAMP}.txt"
    
    echo -e "${YELLOW}📄 로그 파일: ${LOG_FILE}${NC}"
    echo ""
    
    # 실시간 로그 출력 및 저장
    docker logs -f --timestamps "$SELECTED_CONTAINER" 2>&1 | tee "$LOG_FILE"
}

# 컨테이너 상태 확인
check_container_status() {
    echo -e "${BLUE}📊 컨테이너 상태 확인...${NC}"
    echo -e "${GREEN}🎯 대상: ${SELECTED_CONTAINER}${NC}"
    echo ""
    
    # 기본 정보
    echo -e "${CYAN}📋 기본 정보:${NC}"
    docker inspect "$SELECTED_CONTAINER" --format='
이름: {{.Name}}
상태: {{.State.Status}}
시작 시간: {{.State.StartedAt}}
이미지: {{.Config.Image}}
IP 주소: {{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}
'
    
    # 포트 정보
    echo -e "${CYAN}🔌 포트 매핑:${NC}"
    docker port "$SELECTED_CONTAINER" || echo "매핑된 포트 없음"
    
    # 리소스 사용량
    echo ""
    echo -e "${CYAN}📈 리소스 사용량:${NC}"
    docker stats "$SELECTED_CONTAINER" --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}"
    
    # 프로세스 목록
    echo ""
    echo -e "${CYAN}🔧 실행 중인 프로세스:${NC}"
    docker exec "$SELECTED_CONTAINER" ps aux 2>/dev/null | head -10 || echo "프로세스 정보 조회 실패"
    
    # 네트워크 연결 테스트
    echo ""
    echo -e "${CYAN}🌐 네트워크 연결 테스트:${NC}"
    CONTAINER_IP=$(docker inspect "$SELECTED_CONTAINER" --format='{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}')
    if [ -n "$CONTAINER_IP" ]; then
        ping -c 3 "$CONTAINER_IP" > /dev/null 2>&1 && {
            echo -e "${GREEN}✅ 네트워크 연결 정상: ${CONTAINER_IP}${NC}"
        } || {
            echo -e "${RED}❌ 네트워크 연결 실패: ${CONTAINER_IP}${NC}"
        }
    fi
}

# 메뉴 표시
show_menu() {
    echo ""
    echo -e "${CYAN}📋 분석 메뉴:${NC}"
    echo "1. 컨테이너 상태 확인"
    echo "2. 실시간 로그 모니터링"
    echo "3. 빠른 네트워크 캡처 (30초)"
    echo "4. 상세 분석 (Python 스크립트)"
    echo "5. 모든 DVD 컨테이너 상태"
    echo "6. 종료"
    echo ""
}

# 모든 DVD 컨테이너 상태
show_all_dvd_status() {
    echo -e "${BLUE}📊 모든 DVD 컨테이너 상태:${NC}"
    echo ""
    
    for container in "${DVD_CONTAINERS[@]}"; do
        echo -e "${CYAN}📦 ${container}:${NC}"
        
        # 상태
        STATUS=$(docker inspect "$container" --format='{{.State.Status}}' 2>/dev/null || echo "unknown")
        echo "  상태: $STATUS"
        
        # IP
        CONTAINER_IP=$(docker inspect "$container" --format='{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' 2>/dev/null || echo "N/A")
        echo "  IP: $CONTAINER_IP"
        
        # 포트
        PORTS=$(docker port "$container" 2>/dev/null | tr '\n' ', ' | sed 's/,$//')
        echo "  포트: ${PORTS:-없음}"
        
        # CPU/메모리 (빠른 체크)
        STATS=$(docker stats "$container" --no-stream --format "{{.CPUPerc}} {{.MemUsage}}" 2>/dev/null || echo "N/A N/A")
        echo "  리소스: $STATS"
        echo ""
    done
}

# 메인 실행
main() {
    # 컨테이너 감지
    if ! detect_dvd_containers; then
        exit 1
    fi
    
    # 컨테이너 선택
    if ! select_container; then
        exit 1
    fi
    
    # 메뉴 루프
    while true; do
        show_menu
        read -p "선택 (1-6): " choice
        
        case $choice in
            1)
                check_container_status
                ;;
            2)
                monitor_logs
                ;;
            3)
                quick_network_capture
                ;;
            4)
                run_simple_analysis
                ;;
            5)
                show_all_dvd_status
                ;;
            6)
                echo -e "${GREEN}👋 분석을 종료합니다.${NC}"
                exit 0
                ;;
            *)
                echo -e "${RED}❌ 잘못된 선택입니다. 1-6 사이의 숫자를 입력하세요.${NC}"
                ;;
        esac
        
        echo ""
        read -p "계속하려면 Enter를 누르세요..."
    done
}

# 사용법 표시
if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    echo "사용법: $0"
    echo ""
    echo "이 스크립트는 DVD 컨테이너를 자동으로 감지하고 분석 메뉴를 제공합니다."
    echo ""
    echo "요구사항:"
    echo "  • Docker가 설치되어 있어야 함"
    echo "  • DVD 컨테이너가 실행 중이어야 함"
    echo "  • tcpdump (네트워크 캡처용, 선택사항)"
    echo ""
    echo "예제:"
    echo "  $0              # 대화형 모드로 실행"
    echo ""
    exit 0
fi

# 메인 실행
main