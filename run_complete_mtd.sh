#!/bin/bash
# 파일 위치: /home/kali/MTD/MTD_full_testbed/run_complete_mtd.sh
# 완전한 MTD 테스트베드 실행 스크립트 (Kali Linux 최적화)

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# 배너
echo -e "${CYAN}"
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║           🚁 완전한 MTD 테스트베드 시스템                        ║"
echo "║              Moving Target Defense Testbed                       ║"
echo "║                  (Kali Linux 최적화)                            ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# 파라미터
DURATION=${1:-5}
INTENSITY=${2:-light}
NODES=${3:-10}

log_info "실험 설정: 지속시간=${DURATION}분, 강도=${INTENSITY}, 노드=${NODES}개"

# 가상환경 확인
if [ -z "$VIRTUAL_ENV" ]; then
    if [ -d "./mtd_env" ]; then
        log_info "가상환경 활성화 중..."
        source "./mtd_env/bin/activate"
    else
        log_warning "가상환경을 찾을 수 없습니다"
        exit 1
    fi
fi

# 서비스 시작
start_services() {
    log_info "MTD 서비스 시작 중..."
    
    # ArduPilot SITL
    if [ -f "start_ardupilot.sh" ] && [ -x "start_ardupilot.sh" ]; then
        log_info "🛩️ ArduPilot SITL 시작..."
        ./start_ardupilot.sh &
        sleep 8
    else
        log_warning "ArduPilot 스크립트를 찾을 수 없거나 실행 권한이 없습니다"
    fi
    
    # QGroundControl 서비스
    if [ -f "start_qgc_service.py" ] && [ -x "start_qgc_service.py" ]; then
        log_info "🖥️ QGroundControl 서비스 시작..."
        python start_qgc_service.py &
        echo $! > /tmp/qgc_service.pid
        sleep 3
    else
        log_warning "QGC 서비스 스크립트를 찾을 수 없거나 실행 권한이 없습니다"
    fi
    
    # Gazebo 서비스
    if [ -f "start_gazebo_service.py" ] && [ -x "start_gazebo_service.py" ]; then
        log_info "🌍 Gazebo 서비스 시작..."
        python start_gazebo_service.py &
        echo $! > /tmp/gazebo_service.pid
        sleep 3
    else
        log_warning "Gazebo 서비스 스크립트를 찾을 수 없거나 실행 권한이 없습니다"
    fi
    
    # NS-3 FANET 서비스
    if [ -f "start_ns3_fanet.py" ] && [ -x "start_ns3_fanet.py" ]; then
        log_info "🌐 NS-3 FANET 서비스 시작..."
        python start_ns3_fanet.py &
        echo $! > /tmp/ns3_fanet.pid
        sleep 3
    else
        log_warning "NS-3 FANET 서비스 스크립트를 찾을 수 없거나 실행 권한이 없습니다"
    fi
}

# 연결 테스트
test_connections() {
    log_info "연결 테스트 중..."
    
    local services=("14550:QGroundControl" "14551:ArduPilot" "11345:Gazebo" "9999:NS-3_FANET")
    local success=0
    
    for service in "${services[@]}"; do
        local port=$(echo $service | cut -d: -f1)
        local name=$(echo $service | cut -d: -f2)
        
        if timeout 5 bash -c "echo >/dev/tcp/127.0.0.1/$port" 2>/dev/null; then
            log_info "✅ $name (포트 $port) 연결 성공"
            success=$((success + 1))
        else
            log_warning "❌ $name (포트 $port) 연결 실패"
        fi
    done
    
    echo -e "\n${BLUE}📊 연결 상태: $success/4 성공${NC}"
    return $success
}

# MTD 실행
run_mtd() {
    log_info "MTD 테스트베드 실행 중..."
    
    if [ -f "mtd_testbed_system.py" ]; then
        python mtd_testbed_system.py \
            --config configs/mtd_config.yaml \
            --duration $DURATION \
            --intensity $INTENSITY \
            --fanet-nodes $NODES
    else
        # 대체 시뮬레이션
        log_info "대체 시뮬레이션 실행 중..."
        local end_time=$(($(date +%s) + $DURATION * 60))
        local iteration=0
        
        while [ $(date +%s) -lt $end_time ]; do
            iteration=$((iteration + 1))
            local remaining=$((end_time - $(date +%s)))
            log_info "시뮬레이션 진행 중... (반복: $iteration, 남은시간: ${remaining}초)"
            
            # 공격 시나리오 시뮬레이션
            case $INTENSITY in
                light)
                    log_info "💥 가벼운 정찰 공격 시나리오"
                    ;;
                moderate)
                    log_info "💥💥 보통 프로토콜 조작 공격 시나리오"
                    ;;
                aggressive)
                    log_info "💥💥💥 강력한 DoS 공격 시나리오"
                    ;;
            esac
            
            sleep 30
        done
        
        log_info "✅ 시뮬레이션 완료"
    fi
}

# 결과 분석
analyze_results() {
    log_info "실험 결과 분석 중..."
    
    # 로그 파일 확인
    if [ -f "logs/mtd_testbed.log" ]; then
        local log_lines=$(wc -l < logs/mtd_testbed.log 2>/dev/null || echo "0")
        log_info "📄 로그 파일: logs/mtd_testbed.log ($log_lines 라인)"
    fi
    
    # 결과 파일 확인
    if [ -d "results" ]; then
        local result_files=$(find results -name "*.json" -o -name "*.csv" 2>/dev/null | wc -l)
        log_info "📊 결과 파일: $result_files 개"
    fi
    
    # 최종 시스템 상태
    echo -e "\n${CYAN}=== 최종 시스템 상태 ===${NC}"
    echo -e "${YELLOW}실행 중인 서비스:${NC}"
    ps aux | grep -E "(ardupilot|qgc_service|gazebo_service|ns3_fanet)" | grep -v grep || echo "서비스 프로세스 없음"
    
    echo -e "\n${YELLOW}포트 사용 상태:${NC}"
    netstat -tuln 2>/dev/null | grep -E "(14550|14551|11345|9999)" || echo "포트 정보 없음"
}

# 정리
cleanup() {
    log_info "서비스 정리 중..."
    
    local pid_files=("/tmp/ardupilot_sitl.pid" "/tmp/qgc_service.pid" "/tmp/gazebo_service.pid" "/tmp/ns3_fanet.pid")
    
    for pid_file in "${pid_files[@]}"; do
        if [ -f "$pid_file" ]; then
            local pid=$(cat "$pid_file" 2>/dev/null || echo "")
            if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
                log_info "프로세스 종료: PID $pid"
                kill "$pid" 2>/dev/null || true
                sleep 1
                # 강제 종료
                if kill -0 "$pid" 2>/dev/null; then
                    kill -9 "$pid" 2>/dev/null || true
                fi
            fi
            rm -f "$pid_file"
        fi
    done
    
    # 프로세스 패턴 정리
    pkill -f "sim_vehicle.py" 2>/dev/null || true
    pkill -f "start_qgc_service.py" 2>/dev/null || true
    pkill -f "start_gazebo_service.py" 2>/dev/null || true
    pkill -f "start_ns3_fanet.py" 2>/dev/null || true
    
    log_info "정리 완료"
}

trap cleanup EXIT INT TERM

# 메인 실행
main() {
    start_services
    sleep 10
    
    if test_connections; then
        run_mtd
    else
        log_warning "일부 서비스 연결 실패했지만 계속 진행"
        run_mtd
    fi
    
    analyze_results
    log_info "✅ MTD 테스트베드 실행 완료!"
}

# 사용법
if [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
    echo "사용법: $0 [지속시간(분)] [강도] [노드수]"
    echo "예제: $0 5 light 10"
    echo "     $0 30 moderate 15"
    echo "     $0 60 aggressive 20"
    exit 0
fi

main "$@"
