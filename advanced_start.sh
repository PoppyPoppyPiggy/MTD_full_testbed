#!/bin/bash
# advanced_start.sh - DVD 환경 완전 설정 및 실행 스크립트

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 로깅 함수
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_banner() {
    cat << 'EOF'
╔════════════════════════════════════════════════════════════════════════╗
║                    DVD Advanced Environment Setup                      ║
║              Damn Vulnerable Drone 완전 환경 설정                      ║
║                                                                        ║
║  🚁 ArduPilot SITL/Docker/실제 하드웨어 지원                           ║
║  🔗 MAVLink, WiFi, 컴패니언 컴퓨터 연결                                  ║
║  🛡️  안전성 검사 및 환경 검증                                           ║
║  📊 CTI 수집 및 보고서 생성                                             ║
╚════════════════════════════════════════════════════════════════════════╝
EOF
}

# 사용법 출력
usage() {
    cat << EOF
사용법: $0 [옵션]

옵션:
    -e, --environment TYPE    환경 타입 (auto|simulation|docker|real)
    -c, --config FILE        설정 파일 경로 (기본: dvd_config.json)
    -m, --mode MODE          실행 모드 (setup|test|comprehensive|interactive)
    -h, --help              이 도움말 표시

환경 타입:
    auto        - 자동 감지 (기본값)
    simulation  - ArduPilot SITL 시뮬레이션
    docker      - Docker 기반 DVD 환경
    real        - 실제 DVD 하드웨어

실행 모드:
    setup       - 환경 설정만
    test        - 기본 테스트 실행
    comprehensive - 종합 보안 테스트
    interactive - 대화형 모드

예시:
    $0                              # 자동 감지 + 종합 테스트
    $0 -e simulation -m test        # SITL 시뮬레이션 + 기본 테스트
    $0 -e docker -m interactive     # Docker 환경 + 대화형 모드
EOF
}

# 기본값 설정
ENVIRONMENT="auto"
CONFIG_FILE="dvd_config.json"
MODE="comprehensive"
FORCE_SETUP=false

# 옵션 파싱
while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -c|--config)
            CONFIG_FILE="$2"
            shift 2
            ;;
        -m|--mode)
            MODE="$2"
            shift 2
            ;;
        -f|--force)
            FORCE_SETUP=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            log_error "알 수 없는 옵션: $1"
            usage
            exit 1
            ;;
    esac
done

# 환경 변수 설정
export PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH"
export DVD_CONFIG_FILE="$CONFIG_FILE"

# 필수 도구 확인
check_requirements() {
    log_info "필수 도구 확인 중..."
    
    local missing_tools=()
    
    # Python 확인
    if ! command -v python3 &> /dev/null; then
        missing_tools+=("python3")
    fi
    
    # pip 확인
    if ! python3 -m pip --version &> /dev/null; then
        missing_tools+=("python3-pip")
    fi
    
    # Git 확인 (ArduPilot 다운로드용)
    if ! command -v git &> /dev/null; then
        missing_tools+=("git")
    fi
    
    if [ ${#missing_tools[@]} -ne 0 ]; then
        log_error "다음 도구들이 필요합니다: ${missing_tools[*]}"
        log_info "Ubuntu/Debian: sudo apt-get install ${missing_tools[*]}"
        log_info "CentOS/RHEL: sudo yum install ${missing_tools[*]}"
        log_info "macOS: brew install ${missing_tools[*]}"
        exit 1
    fi
    
    log_success "필수 도구 확인 완료"
}

# Python 가상환경 설정
setup_python_env() {
    log_info "Python 환경 설정 중..."
    
    # 가상환경 생성
    if [ ! -d "venv" ] || [ "$FORCE_SETUP" = true ]; then
        log_info "Python 가상환경 생성 중..."
        python3 -m venv venv
    fi
    
    # 가상환경 활성화
    source venv/bin/activate
    
    # pip 업그레이드
    python -m pip install --upgrade pip
    
    # 의존성 설치
    if [ -f "requirements.txt" ]; then
        log_info "Python 패키지 설치 중..."
        pip install -r requirements.txt
    fi
    
    log_success "Python 환경 설정 완료"
}

# ArduPilot SITL 설정
setup_ardupilot() {
    log_info "ArduPilot SITL 설정 중..."
    
    local ardupilot_dir="/opt/ardupilot"
    
    # ArduPilot 설치 확인
    if [ ! -d "$ardupilot_dir" ]; then
        log_info "ArduPilot 다운로드 중..."
        
        # /opt 디렉토리 권한 확인
        if [ ! -w "/opt" ]; then
            log_info "ArduPilot을 홈 디렉토리에 설치합니다..."
            ardupilot_dir="$HOME/ardupilot"
        fi
        
        git clone https://github.com/ArduPilot/ardupilot.git "$ardupilot_dir"
        cd "$ardupilot_dir"
        git submodule update --init --recursive
        
        # 빌드 도구 설치
        log_info "ArduPilot 빌드 도구 설치 중..."
        Tools/environment_install/install-prereqs-ubuntu.sh -y
        
        # 시뮬레이터 빌드
        log_info "ArduPilot 시뮬레이터 빌드 중..."
        cd ArduCopter
        ../Tools/autotest/sim_vehicle.py --build-only
        
        cd "$SCRIPT_DIR"
    fi
    
    # 설정 파일 업데이트
    update_config_ardupilot_path "$ardupilot_dir"
    
    log_success "ArduPilot SITL 설정 완료"
}

# Docker 환경 설정
setup_docker() {
    log_info "Docker 환경 설정 중..."
    
    # Docker 설치 확인
    if ! command -v docker &> /dev/null; then
        log_error "Docker가 설치되어 있지 않습니다."
        log_info "Docker 설치: https://docs.docker.com/get-docker/"
        return 1
    fi
    
    # Docker 권한 확인
    if ! docker ps &> /dev/null; then
        log_error "Docker 권한이 없습니다."
        log_info "사용자를 docker 그룹에 추가: sudo usermod -aG docker $USER"
        log_info "로그아웃 후 다시 로그인하세요."
        return 1
    fi
    
    # DVD Docker 이미지 확인/빌드
    if ! docker images | grep -q "dvd.*latest"; then
        log_info "DVD Docker 이미지 빌드 중..."
        
        # Dockerfile 생성
        create_dockerfile
        
        # 이미지 빌드
        docker build -t dvd:latest .
    fi
    
    log_success "Docker 환경 설정 완료"
}

# DVD Dockerfile 생성
create_dockerfile() {
    cat > Dockerfile << 'EOF'
FROM ubuntu:20.04

# 환경 변수 설정
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC

# 기본 패키지 설치
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    git \
    wget \
    curl \
    openssh-server \
    vsftpd \
    apache2 \
    mavproxy \
    && rm -rf /var/lib/apt/lists/*

# ArduPilot SITL 설치
RUN git clone https://github.com/ArduPilot/ardupilot.git /opt/ardupilot
WORKDIR /opt/ardupilot
RUN git submodule update --init --recursive
RUN Tools/environment_install/install-prereqs-ubuntu.sh -y
RUN cd ArduCopter && ../Tools/autotest/sim_vehicle.py --build-only

# 취약한 서비스 설정
RUN echo "root:root" | chpasswd
RUN echo "pi:raspberry" | chpasswd
RUN useradd -m -s /bin/bash pi
RUN echo "pi:raspberry" | chpasswd

# SSH 설정
RUN sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config
RUN sed -i 's/#PasswordAuthentication yes/PasswordAuthentication yes/' /etc/ssh/sshd_config

# FTP 설정
RUN echo "anonymous_enable=YES" >> /etc/vsftpd.conf
RUN echo "anon_upload_enable=YES" >> /etc/vsftpd.conf
RUN echo "anon_mkdir_write_enable=YES" >> /etc/vsftpd.conf

# HTTP 설정
RUN echo "Options Indexes FollowSymLinks" >> /etc/apache2/apache2.conf

# 시작 스크립트
COPY docker-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 14550/udp 14551/udp 22 80 21 554

ENTRYPOINT ["/entrypoint.sh"]
EOF

    # Docker entrypoint 스크립트 생성
    cat > docker-entrypoint.sh << 'EOF'
#!/bin/bash

# 서비스 시작
service ssh start
service vsftpd start
service apache2 start

# ArduPilot SITL 시작
cd /opt/ardupilot/ArduCopter
../Tools/autotest/sim_vehicle.py \
    --vehicle=copter \
    --location=KSFO \
    --out=0.0.0.0:14550 \
    --out=0.0.0.0:14551 \
    --map --console &

# 컨테이너 유지
tail -f /dev/null
EOF
}

# 실제 하드웨어 연결 확인
check_real_hardware() {
    log_info "실제 DVD 하드웨어 연결 확인 중..."
    
    # MAVLink 연결 테스트
    if timeout 5 python3 -c "
import socket
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(3)
    sock.connect(('192.168.13.2', 14550))
    sock.close()
    print('Connected')
except:
    exit(1)
" 2>/dev/null; then
        log_success "실제 DVD 하드웨어 연결 확인됨"
        return 0
    else
        log_warning "실제 DVD 하드웨어에 연결할 수 없습니다"
        return 1
    fi
}

# 환경 자동 감지
detect_environment() {
    log_info "DVD 환경 자동 감지 중..."
    
    # Docker 환경 확인
    if docker ps --format "{{.Names}}" 2>/dev/null | grep -q "dvd"; then
        echo "docker"
        return
    fi
    
    # 실제 하드웨어 확인
    if check_real_hardware; then
        echo "real"
        return
    fi
    
    # ArduPilot SITL 확인
    if [ -d "/opt/ardupilot" ] || [ -d "$HOME/ardupilot" ]; then
        echo "simulation"
        return
    fi
    
    # 기본값
    echo "simulation"
}

# 설정 파일 생성/업데이트
create_config_file() {
    log_info "DVD 설정 파일 생성 중..."
    
    if [ ! -f "$CONFIG_FILE" ] || [ "$FORCE_SETUP" = true ]; then
        cat > "$CONFIG_FILE" << 'EOF'
{
  "dvd_environment": {
    "type": "simulation",
    "base_path": "/opt/dvd",
    "ardupilot_path": "/opt/ardupilot",
    "sitl_params": {
      "vehicle": "copter",
      "location": "KSFO",
      "instance": 0
    }
  },
  "targets": {
    "primary": {
      "ip": "127.0.0.1",
      "mavlink_port": 14550,
      "connection_type": "mavlink_udp"
    },
    "companion": {
      "ip": "127.0.0.1", 
      "ssh_port": 22,
      "services": ["rtsp", "http", "ftp"]
    },
    "gcs": {
      "ip": "127.0.0.1",
      "mavlink_port": 14551
    }
  },
  "network": {
    "wifi_interface": "wlan0",
    "default_network": "192.168.13.0/24",
    "ap_ssid": "DVD_Test_Network",
    "monitoring_enabled": true
  },
  "security": {
    "vulnerable_services": true,
    "weak_passwords": true,
    "unencrypted_comms": true,
    "debug_enabled": true
  },
  "safety": {
    "max_altitude": 50,
    "geofence_enabled": true,
    "emergency_stop": true,
    "safe_networks": [
      "127.0.0.0/8",
      "192.168.0.0/16",
      "10.0.0.0/8"
    ]
  }
}
EOF
        log_success "설정 파일 생성: $CONFIG_FILE"
    fi
}

# ArduPilot 경로 업데이트
update_config_ardupilot_path() {
    local ardupilot_path="$1"
    
    if [ -f "$CONFIG_FILE" ]; then
        python3 -c "
import json
with open('$CONFIG_FILE', 'r') as f:
    config = json.load(f)
config['dvd_environment']['ardupilot_path'] = '$ardupilot_path'
with open('$CONFIG_FILE', 'w') as f:
    json.dump(config, f, indent=2)
"
    fi
}

# 환경별 설정
setup_environment() {
    local env_type="$1"
    
    log_info "DVD 환경 설정: $env_type"
    
    case "$env_type" in
        "simulation")
            setup_ardupilot
            ;;
        "docker")
            setup_docker
            ;;
        "real")
            if ! check_real_hardware; then
                log_error "실제 하드웨어에 연결할 수 없습니다"
                exit 1
            fi
            ;;
        *)
            log_error "지원되지 않는 환경 타입: $env_type"
            exit 1
            ;;
    esac
}

# 디렉토리 구조 생성
create_directories() {
    log_info "디렉토리 구조 생성 중..."
    
    local dirs=(
        "dvd_lite/dvd_attacks/core"
        "dvd_lite/dvd_attacks/reconnaissance"
        "dvd_lite/dvd_attacks/protocol_tampering"
        "dvd_lite/dvd_attacks/denial_of_service"
        "dvd_lite/dvd_attacks/injection"
        "dvd_lite/dvd_attacks/exfiltration"
        "dvd_lite/dvd_attacks/firmware_attacks"
        "dvd_lite/dvd_attacks/registry"
        "dvd_lite/dvd_attacks/utils"
        "dvd_connector"
        "results"
        "logs"
        "tests"
    )
    
    for dir in "${dirs[@]}"; do
        mkdir -p "$dir"
        
        # __init__.py 파일 생성
        if [[ "$dir" == *"dvd_lite"* ]] || [[ "$dir" == *"dvd_connector"* ]]; then
            touch "$dir/__init__.py"
        fi
    done
    
    log_success "디렉토리 구조 생성 완료"
}

# 파일 권한 설정
set_permissions() {
    log_info "파일 권한 설정 중..."
    
    # 실행 스크립트 권한
    chmod +x "$0"
    
    # Python 스크립트 권한
    find . -name "*.py" -type f -exec chmod +r {} \;
    
    log_success "파일 권한 설정 완료"
}

# 테스트 실행
run_tests() {
    log_info "기본 테스트 실행 중..."
    
    # 가상환경 활성화
    source venv/bin/activate
    
    # Import 테스트
    if python3 -c "
import sys
sys.path.insert(0, '.')
try:
    from dvd_lite.main import DVDLite
    from dvd_connector.connector import DVDConnector, DVDEnvironment
    print('✅ 모든 모듈 import 성공')
except ImportError as e:
    print(f'❌ Import 오류: {e}')
    exit(1)
"; then
        log_success "Import 테스트 통과"
    else
        log_error "Import 테스트 실패"
        return 1
    fi
    
    # 기본 연결 테스트
    if python3 advanced_start.py --mode test --environment "$ENVIRONMENT"; then
        log_success "기본 테스트 통과"
    else
        log_warning "기본 테스트에서 일부 문제 발생"
    fi
}

# 종합 테스트 실행
run_comprehensive() {
    log_info "종합 보안 테스트 시작..."
    
    # 가상환경 활성화
    source venv/bin/activate
    
    # 종합 테스트 실행
    python3 advanced_start.py --mode comprehensive --environment "$ENVIRONMENT" --config "$CONFIG_FILE"
}

# 대화형 모드 실행
run_interactive() {
    log_info "대화형 모드 시작..."
    
    # 가상환경 활성화
    source venv/bin/activate
    
    # 대화형 모드 실행
    python3 advanced_start.py --mode interactive --environment "$ENVIRONMENT" --config "$CONFIG_FILE"
}

# 정리 함수
cleanup() {
    log_info "정리 작업 수행 중..."
    
    # Docker 컨테이너 정리
    if [ "$ENVIRONMENT" = "docker" ]; then
        docker stop dvd-environment 2>/dev/null || true
        docker rm dvd-environment 2>/dev/null || true
    fi
    
    # 임시 파일 정리
    rm -f Dockerfile docker-entrypoint.sh
    
    log_success "정리 완료"
}

# 메인 실행 함수
main() {
    print_banner
    
    log_info "DVD 고급 환경 설정 시작..."
    log_info "환경: $ENVIRONMENT, 모드: $MODE, 설정: $CONFIG_FILE"
    
    # 인터럽트 핸들러 설정
    trap cleanup EXIT INT TERM
    
    # 1. 필수 도구 확인
    check_requirements
    
    # 2. 디렉토리 구조 생성
    create_directories
    
    # 3. Python 환경 설정
    setup_python_env
    
    # 4. 설정 파일 생성
    create_config_file
    
    # 5. 환경 자동 감지
    if [ "$ENVIRONMENT" = "auto" ]; then
        ENVIRONMENT=$(detect_environment)
        log_info "감지된 환경: $ENVIRONMENT"
    fi
    
    # 6. 환경별 설정
    if [ "$MODE" != "setup" ]; then
        setup_environment "$ENVIRONMENT"
    fi
    
    # 7. 권한 설정
    set_permissions
    
    # 8. 모드별 실행
    case "$MODE" in
        "setup")
            log_success "환경 설정 완료"
            ;;
        "test")
            run_tests
            ;;
        "comprehensive")
            run_comprehensive
            ;;
        "interactive")
            run_interactive
            ;;
        *)
            log_error "지원되지 않는 모드: $MODE"
            exit 1
            ;;
    esac
    
    log_success "DVD 고급 환경 설정 및 실행 완료!"
}

# 스크립트 실행
main "$@"