#!/bin/bash
# 가상환경 기반 MTD 테스트베드 실행 스크립트

set -e

# 색상 정의
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# 기본 설정
VENV_PATH="./mtd_env"
BASE_DIR=$(pwd)

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# 배너 출력
echo -e "${CYAN}"
cat << 'BANNER'
╔══════════════════════════════════════════════════════════════════╗
║          🚁 MTD 테스트베드 (가상환경 기반)                        ║
║             Moving Target Defense Testbed                       ║
╚══════════════════════════════════════════════════════════════════╝
BANNER
echo -e "${NC}"

# 1. 가상환경 활성화 확인
if [ -z "$VIRTUAL_ENV" ]; then
    if [ -d "$VENV_PATH" ]; then
        log_info "가상환경 활성화 중..."
        source "$VENV_PATH/bin/activate"
    else
        log_warning "가상환경이 없습니다. venv_fix_mtd.sh를 먼저 실행하세요."
        exit 1
    fi
fi

log_info "가상환경 활성화됨: $VIRTUAL_ENV"

# 2. 서비스 시작
start_services() {
    log_info "필수 서비스 시작 중..."
    
    # ArduPilot SITL 시작
    if [ -f "start_ardupilot.sh" ]; then
        log_info "ArduPilot SITL 시작..."
        ./start_ardupilot.sh &
        sleep 5
    fi
    
    # GCS 서비스 시작
    if [ -f "start_gcs.py" ]; then
        log_info "GCS 서비스 시작..."
        python start_gcs.py &
        echo $! > /tmp/gcs_service.pid
        sleep 2
    fi
    
    # NS-3 서비스 시작
    if [ -f "start_ns3.py" ]; then
        log_info "NS-3 서비스 시작..."
        python start_ns3.py &
        echo $! > /tmp/ns3_service.pid
        sleep 2
    fi
}

# 3. 연결 테스트
test_connections() {
    log_info "연결 테스트 중..."
    
    local ports=(14550 14551 9999)
    local success=0
    
    for port in "${ports[@]}"; do
        if timeout 3 bash -c "echo >/dev/tcp/127.0.0.1/$port" 2>/dev/null; then
            log_info "✅ 포트 $port 연결됨"
            ((success++))
        else
            log_warning "❌ 포트 $port 연결 실패"
        fi
    done
    
    echo -e "\n${BLUE}연결 상태: $success/${#ports[@]} 성공${NC}"
    return $success
}

# 4. MTD 테스트베드 실행
run_testbed() {
    local duration=${1:-5}
    local intensity=${2:-light}
    local nodes=${3:-5}
    
    log_info "MTD 테스트베드 실행 시작"
    log_info "지속시간: ${duration}분, 강도: ${intensity}, 노드: ${nodes}개"
    
    if [ -f "mtd_testbed_system.py" ]; then
        python mtd_testbed_system.py \
            --config configs/mtd_config.yaml \
            --duration $duration \
            --intensity $intensity \
            --fanet-nodes $nodes
    else
        log_warning "mtd_testbed_system.py를 찾을 수 없습니다"
        exit 1
    fi
}

# 정리 함수
cleanup() {
    log_info "정리 작업 중..."
    
    # PID 파일들에서 프로세스 종료
    for pid_file in /tmp/ardupilot_sitl.pid /tmp/gcs_service.pid /tmp/ns3_service.pid; do
        if [ -f "$pid_file" ]; then
            local pid=$(cat "$pid_file")
            if kill -0 "$pid" 2>/dev/null; then
                kill "$pid" 2>/dev/null || true
            fi
            rm -f "$pid_file"
        fi
    done
    
    # 패턴으로 프로세스 정리
    pkill -f "sim_vehicle.py" 2>/dev/null || true
    pkill -f "start_gcs.py" 2>/dev/null || true
    pkill -f "start_ns3.py" 2>/dev/null || true
}

# 신호 처리
trap cleanup EXIT INT TERM

# 메인 실행
main() {
    # 파라미터 파싱
    local duration=${1:-5}
    local intensity=${2:-light}
    local nodes=${3:-5}
    
    # 서비스 시작
    start_services
    
    # 연결 대기
    sleep 5
    
    # 연결 테스트
    if test_connections; then
        # MTD 테스트베드 실행
        run_testbed $duration $intensity $nodes
    else
        log_warning "일부 서비스 연결에 실패했지만 계속 진행합니다"
        run_testbed $duration $intensity $nodes
    fi
}

# 사용법 출력
if [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
    echo "사용법: $0 [지속시간(분)] [강도] [노드수]"
    echo "예제: $0 5 light 5"
    echo "     $0 30 moderate 10"
    exit 0
fi

# 스크립트 실행
main "$@"
