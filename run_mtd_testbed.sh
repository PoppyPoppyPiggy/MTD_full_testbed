#!/bin/bash
# Kali Linux 가상환경 기반 MTD 테스트베드 수정 스크립트
# venv_fix_mtd.sh

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}"
cat << 'EOF'
╔═══════════════════════════════════════════════════════════════════╗
║          🛠️ Kali Linux 가상환경 기반 MTD 수정                     ║
║           externally-managed-environment 문제 해결               ║
╚═══════════════════════════════════════════════════════════════════╝
EOF
echo -e "${NC}"

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 현재 디렉토리 확인
BASE_DIR=$(pwd)
VENV_NAME="mtd_env"
VENV_PATH="$BASE_DIR/$VENV_NAME"

log_info "작업 디렉토리: $BASE_DIR"

# 1. 가상환경 상태 확인
check_virtual_env() {
    log_info "가상환경 상태 확인 중..."
    
    if [ -z "$VIRTUAL_ENV" ]; then
        log_warning "가상환경이 활성화되지 않았습니다"
        
        if [ -d "$VENV_PATH" ]; then
            log_info "기존 가상환경 발견: $VENV_PATH"
            log_info "가상환경 활성화 중..."
            source "$VENV_PATH/bin/activate"
        else
            log_warning "가상환경이 존재하지 않습니다. 새로 생성합니다."
            create_virtual_env
        fi
    else
        log_info "가상환경 활성화됨: $VIRTUAL_ENV"
    fi
}

# 2. 가상환경 생성
create_virtual_env() {
    log_info "가상환경 생성 중: $VENV_PATH"
    
    python3 -m venv "$VENV_PATH"
    
    if [ $? -eq 0 ]; then
        log_info "✅ 가상환경 생성 완료"
        source "$VENV_PATH/bin/activate"
        log_info "✅ 가상환경 활성화됨"
    else
        log_error "❌ 가상환경 생성 실패"
        exit 1
    fi
}

# 3. 의존성 설치 (가상환경에서)
install_dependencies_venv() {
    log_info "가상환경에서 의존성 설치 중..."
    
    # pip 업그레이드
    python -m pip install --upgrade pip
    
    # 필수 패키지 목록
    local packages=(
        "pymavlink"
        "dronekit" 
        "pyyaml"
        "psutil"
        "asyncio-mqtt"
        "scapy"
        "netaddr"
        "numpy"
        "matplotlib"
        "requests"
    )
    
    for package in "${packages[@]}"; do
        log_info "설치 중: $package"
        if pip install "$package"; then
            log_info "✅ $package 설치 완료"
        else
            log_warning "⚠️ $package 설치 실패"
        fi
    done
    
    # MAVProxy 설치 (특별 처리)
    log_info "MAVProxy 설치 중..."
    if pip install MAVProxy; then
        log_info "✅ MAVProxy 설치 완료"
    else
        log_warning "⚠️ MAVProxy 설치 실패"
    fi
}

# 4. 시스템 패키지 설치 (Kali용)
install_system_packages() {
    log_info "시스템 패키지 설치 중..."
    
    # APT 패키지 업데이트
    sudo apt update -qq
    
    # 필수 시스템 패키지
    local sys_packages=(
        "python3-dev"
        "python3-pip"
        "python3-venv"
        "build-essential"
        "git"
        "lsof"
        "netcat-openbsd"
        "nmap"
        "wireshark-common"
        "tshark"
    )
    
    for package in "${sys_packages[@]}"; do
        if ! dpkg -l | grep -q "^ii  $package "; then
            log_info "설치 중: $package"
            sudo apt install -y "$package" || log_warning "⚠️ $package 설치 실패"
        else
            log_info "✅ $package 이미 설치됨"
        fi
    done
}

# 5. 기존 프로세스 정리
cleanup_processes() {
    log_info "기존 프로세스 정리 중..."
    
    local process_patterns=(
        "sim_vehicle.py"
        "arducopter"
        "mavproxy.py"
        "qgroundcontrol"
        "gazebo"
        "gzserver"
        "gzclient"
        "simple_gcs.py"
        "simple_ns3.py"
    )
    
    for pattern in "${process_patterns[@]}"; do
        local pids=$(pgrep -f "$pattern" 2>/dev/null || true)
        if [ -n "$pids" ]; then
            log_warning "프로세스 종료: $pattern (PID: $pids)"
            echo "$pids" | xargs -r kill -9 2>/dev/null || true
        fi
    done
    
    # 포트 해제
    local ports=(14550 14551 5760 5761 11345 9999 554 8080)
    for port in "${ports[@]}"; do
        local pid=$(lsof -ti:$port 2>/dev/null || true)
        if [ -n "$pid" ]; then
            log_warning "포트 $port 해제 (PID: $pid)"
            kill -9 "$pid" 2>/dev/null || true
        fi
    done
    
    sleep 2
    log_info "프로세스 정리 완료"
}

# 6. ArduPilot 설치 및 설정
setup_ardupilot() {
    log_info "ArduPilot 설정 중..."
    
    local ardupilot_dir="$BASE_DIR/ardupilot"
    
    if [ ! -d "$ardupilot_dir" ]; then
        log_info "ArduPilot 다운로드 중..."
        git clone --recurse-submodules https://github.com/ArduPilot/ardupilot.git "$ardupilot_dir"
        
        if [ $? -eq 0 ]; then
            log_info "✅ ArduPilot 다운로드 완료"
        else
            log_error "❌ ArduPilot 다운로드 실패"
            return 1
        fi
    else
        log_info "✅ ArduPilot 디렉토리 존재: $ardupilot_dir"
    fi
    
    # 의존성 설치 스크립트 실행
    local install_script="$ardupilot_dir/Tools/environment_install/install-prereqs-ubuntu.sh"
    if [ -f "$install_script" ]; then
        log_info "ArduPilot 의존성 설치 중..."
        cd "$ardupilot_dir"
        bash "$install_script" -y || log_warning "⚠️ ArduPilot 의존성 설치 부분 실패"
        cd "$BASE_DIR"
    fi
}

# 7. 서비스 시작 스크립트 생성
create_service_scripts() {
    log_info "서비스 시작 스크립트 생성 중..."
    
    # ArduPilot SITL 시작 스크립트
    cat > start_ardupilot.sh << 'EOF'
#!/bin/bash
# ArduPilot SITL 시작 스크립트

ARDUPILOT_DIR="./ardupilot"
VENV_PATH="./mtd_env"

# 가상환경 활성화
source "$VENV_PATH/bin/activate"

# SITL 시작
cd "$ARDUPILOT_DIR"
python3 Tools/autotest/sim_vehicle.py \
    --vehicle=ArduCopter \
    --aircraft=test \
    --location=KSFO \
    --out=127.0.0.1:14550 \
    --out=127.0.0.1:14551 \
    --console \
    --map &

SITL_PID=$!
echo $SITL_PID > /tmp/ardupilot_sitl.pid
echo "ArduPilot SITL 시작됨 (PID: $SITL_PID)"

# 시작 대기
sleep 10
echo "ArduPilot SITL 준비 완료"
EOF
    
    chmod +x start_ardupilot.sh
    
    # GCS 서비스 스크립트
    cat > start_gcs.py << 'EOF'
#!/usr/bin/env python3
"""
간단한 GCS 시뮬레이션 서비스
MAVLink 패킷 수신 및 응답
"""

import socket
import time
import threading
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SimpleGCS:
    def __init__(self, port=14550):
        self.port = port
        self.running = False
        
    def start_service(self):
        """GCS 서비스 시작"""
        self.running = True
        logger.info(f"GCS 서비스 시작 - 포트 {self.port}")
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.bind(('127.0.0.1', self.port))
            sock.settimeout(1.0)
            
            packet_count = 0
            
            while self.running:
                try:
                    data, addr = sock.recvfrom(1024)
                    packet_count += 1
                    
                    if packet_count % 100 == 0:  # 100개마다 로그
                        logger.info(f"MAVLink 패킷 수신: {packet_count}개")
                        
                except socket.timeout:
                    continue
                except Exception as e:
                    logger.error(f"수신 오류: {e}")
                    
        except Exception as e:
            logger.error(f"GCS 서비스 오류: {e}")
        finally:
            if 'sock' in locals():
                sock.close()
            logger.info("GCS 서비스 종료됨")

    def stop_service(self):
        """GCS 서비스 중지"""
        self.running = False

if __name__ == "__main__":
    gcs = SimpleGCS()
    try:
        gcs.start_service()
    except KeyboardInterrupt:
        logger.info("사용자에 의해 중단됨")
        gcs.stop_service()
EOF
    
    chmod +x start_gcs.py
    
    # NS-3 시뮬레이션 서비스
    cat > start_ns3.py << 'EOF'
#!/usr/bin/env python3
"""
간단한 NS-3 시뮬레이션 서비스
FANET 네트워크 시뮬레이션
"""

import socket
import json
import time
import threading
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SimpleNS3:
    def __init__(self, port=9999):
        self.port = port
        self.running = False
        
    def start_service(self):
        """NS-3 서비스 시작"""
        self.running = True
        logger.info(f"NS-3 시뮬레이션 서비스 시작 - 포트 {self.port}")
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(('127.0.0.1', self.port))
            sock.listen(5)
            sock.settimeout(1.0)
            
            client_count = 0
            
            while self.running:
                try:
                    client, addr = sock.accept()
                    client_count += 1
                    
                    # 클라이언트 요청 처리
                    self.handle_client(client, addr, client_count)
                    
                except socket.timeout:
                    continue
                except Exception as e:
                    logger.error(f"연결 처리 오류: {e}")
                    
        except Exception as e:
            logger.error(f"NS-3 서비스 오류: {e}")
        finally:
            if 'sock' in locals():
                sock.close()
            logger.info("NS-3 서비스 종료됨")
    
    def handle_client(self, client, addr, client_num):
        """클라이언트 요청 처리"""
        try:
            data = client.recv(1024)
            
            response = {
                "status": "ok",
                "simulation_time": time.time(),
                "nodes": 10,
                "topology": "mesh",
                "client_number": client_num,
                "fanet_active": True
            }
            
            client.send(json.dumps(response).encode())
            logger.info(f"클라이언트 {client_num} 응답 전송: {addr}")
            
        except Exception as e:
            logger.error(f"클라이언트 처리 오류: {e}")
        finally:
            client.close()

    def stop_service(self):
        """NS-3 서비스 중지"""
        self.running = False

if __name__ == "__main__":
    ns3 = SimpleNS3()
    try:
        ns3.start_service()
    except KeyboardInterrupt:
        logger.info("사용자에 의해 중단됨")
        ns3.stop_service()
EOF
    
    chmod +x start_ns3.py
    
    log_info "✅ 서비스 스크립트 생성 완료"
}

# 8. 설정 파일 업데이트
update_configs() {
    log_info "설정 파일 업데이트 중..."
    
    mkdir -p configs logs results
    
    # MTD 설정 파일
    cat > configs/mtd_config.yaml << 'EOF'
# MTD 테스트베드 설정 (가상환경용)
system:
  qgroundcontrol_host: "127.0.0.1"
  qgroundcontrol_port: 14550
  ardupilot_host: "127.0.0.1"
  ardupilot_port: 14551
  gazebo_host: "127.0.0.1"
  gazebo_port: 11345
  ns3_host: "127.0.0.1"
  ns3_port: 9999

fanet:
  max_range: 1000.0
  node_count: 10
  mobility_model: "random_waypoint"
  ns3_integration: true
  topology_type: "mesh"

attacks:
  base_duration: 60
  max_concurrent: 3
  adaptive_intensity: true
  target_detection_rate: 0.3

detection:
  anomaly_threshold: 0.7
  alert_cooldown: 30
  ml_enabled: true

mtd:
  enabled: true
  response_time: 10
  defensive_actions:
    - "topology_change"
    - "frequency_hop"
    - "encryption_rotate"
    - "route_diversification"

environment:
  type: "simulation"
  use_virtual_env: true
  venv_path: "./mtd_env"

logging:
  level: "INFO"
  file: "logs/mtd_testbed.log"
  
research:
  paper_mode: true
  data_collection: true
  metrics_export: true
EOF
    
    log_info "✅ 설정 파일 생성: configs/mtd_config.yaml"
}

# 9. 통합 실행 스크립트 생성
create_integrated_runner() {
    log_info "통합 실행 스크립트 생성 중..."
    
    cat > run_mtd_venv.sh << 'EOF'
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
EOF
    
    chmod +x run_mtd_venv.sh
    log_info "✅ 통합 실행 스크립트 생성: run_mtd_venv.sh"
}

# 10. 상태 확인 및 테스트
final_check() {
    log_info "최종 상태 확인 중..."
    
    echo -e "\n${CYAN}=== 설치 상태 ===${NC}"
    
    # 가상환경 상태
    if [ -n "$VIRTUAL_ENV" ]; then
        log_info "✅ 가상환경 활성화됨: $(basename $VIRTUAL_ENV)"
    else
        log_warning "❌ 가상환경 비활성화"
    fi
    
    # Python 패키지 확인
    echo -e "\n${YELLOW}Python 패키지 확인:${NC}"
    local packages=("pymavlink" "pyyaml" "psutil" "numpy")
    for pkg in "${packages[@]}"; do
        if python -c "import $pkg" 2>/dev/null; then
            log_info "✅ $pkg"
        else
            log_warning "❌ $pkg"
        fi
    done
    
    # 파일 존재 확인
    echo -e "\n${YELLOW}파일 확인:${NC}"
    local files=("configs/mtd_config.yaml" "start_ardupilot.sh" "start_gcs.py" "start_ns3.py" "run_mtd_venv.sh")
    for file in "${files[@]}"; do
        if [ -f "$file" ]; then
            log_info "✅ $file"
        else
            log_warning "❌ $file"
        fi
    done
}

# 사용법 안내
show_usage() {
    echo -e "\n${CYAN}=== 사용법 ===${NC}"
    echo -e "${GREEN}1. 가상환경 활성화:${NC}"
    echo "   source mtd_env/bin/activate"
    echo ""
    echo -e "${GREEN}2. 테스트베드 실행:${NC}"
    echo "   ./run_mtd_venv.sh 5 light 5"
    echo ""
    echo -e "${GREEN}3. 개별 서비스 시작:${NC}"
    echo "   ./start_ardupilot.sh    # ArduPilot SITL"
    echo "   python start_gcs.py     # GCS 서비스"
    echo "   python start_ns3.py     # NS-3 서비스"
    echo ""
    echo -e "${GREEN}4. 상태 확인:${NC}"
    echo "   netstat -tuln | grep -E '14550|14551|9999'"
    echo "   ps aux | grep -E 'sim_vehicle|start_gcs|start_ns3'"
}

# 메인 실행
main() {
    log_info "가상환경 기반 MTD 수정 시작"
    
    check_virtual_env
    install_system_packages
    install_dependencies_venv
    cleanup_processes
    setup_ardupilot
    create_service_scripts
    update_configs
    create_integrated_runner
    final_check
    show_usage
    
    echo -e "\n${GREEN}✅ 가상환경 기반 MTD 수정 완료!${NC}"
    echo -e "${CYAN}이제 ./run_mtd_venv.sh 5 light 5 로 실행하세요${NC}"
}

# 정리 함수
cleanup_on_exit() {
    if [ $? -ne 0 ]; then
        log_warning "스크립트 실행 중 오류 발생"
    fi
}

trap cleanup_on_exit EXIT

# 스크립트 실행
if [ "${BASH_SOURCE[0]}" == "${0}" ]; then
    main "$@"
fi