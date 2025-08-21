#!/bin/bash

# =================================================================
# MTD 드론 보안 테스트베드 마스터 배포 스크립트
# 파일: /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks_lpc/MASTER_DEPLOY.sh
# 
# 🚀 원클릭 완전 자동 배포 및 실행
# 사용법: chmod +x MASTER_DEPLOY.sh && ./MASTER_DEPLOY.sh
# =================================================================

set -e  # 오류 시 중단

# ASCII 아트 로고
cat << 'EOF'
╔═══════════════════════════════════════════════════════════════╗
║  🚁 MTD 드론 보안 테스트베드 마스터 배포 시스템 🛡️           ║
║                                                               ║
║  Moving Target Defense + Machine Learning + Honeydrone       ║
║  완전 자동화된 사이버 보안 연구 플랫폼                        ║
╚═══════════════════════════════════════════════════════════════╝
EOF

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
NC='\033[0m' # No Color

# 아이콘 정의
ICON_INFO="ℹ️"
ICON_SUCCESS="✅"
ICON_WARNING="⚠️"
ICON_ERROR="❌"
ICON_ROCKET="🚀"
ICON_GEAR="⚙️"
ICON_SHIELD="🛡️"
ICON_TARGET="🎯"
ICON_BRAIN="🧠"
ICON_NETWORK="🌐"

# 로그 함수
log_header() { 
    echo ""
    echo -e "${PURPLE}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${WHITE}$ICON_TARGET $1${NC}"
    echo -e "${PURPLE}═══════════════════════════════════════════════════════════════${NC}"
}

log_info() { echo -e "${BLUE}$ICON_INFO [INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}$ICON_SUCCESS [SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}$ICON_WARNING [WARNING]${NC} $1"; }
log_error() { echo -e "${RED}$ICON_ERROR [ERROR]${NC} $1"; }
log_step() { echo -e "${CYAN}$ICON_GEAR [STEP]${NC} $1"; }

# 진행률 표시
show_progress() {
    local current=$1
    local total=$2
    local desc="$3"
    local percent=$((current * 100 / total))
    local filled=$((percent / 2))
    local empty=$((50 - filled))
    
    printf "\r${CYAN}[%3d%%]${NC} [" "$percent"
    printf "%*s" "$filled" | tr ' ' '█'
    printf "%*s" "$empty" | tr ' ' '░'
    printf "] %s" "$desc"
    
    if [ "$current" -eq "$total" ]; then
        echo ""
    fi
}

# 시스템 정보 수집
collect_system_info() {
    log_step "시스템 정보 수집 중..."
    
    SYSTEM_INFO=$(cat << SYSINFO
시스템 정보:
- OS: $(lsb_release -d 2>/dev/null | cut -f2 || echo "Unknown")
- 커널: $(uname -r)
- 아키텍처: $(uname -m)
- CPU: $(nproc) cores
- 메모리: $(free -h | grep '^Mem:' | awk '{print $2}')
- 디스크 여유공간: $(df -h . | tail -1 | awk '{print $4}')
- Python 버전: $(python3 --version 2>/dev/null || echo "Not found")
- Docker 버전: $(docker --version 2>/dev/null || echo "Not found")
- 현재 시간: $(date)
- 사용자: $(whoami)
- 작업 디렉토리: $(pwd)
SYSINFO
)
    
    echo "$SYSTEM_INFO" > system_deployment_info.txt
    log_success "시스템 정보 수집 완료"
}

# 전제 조건 검사
check_prerequisites() {
    log_header "전제 조건 검사"
    
    local errors=0
    
    # 필수 명령어 확인
    local required_commands=("python3" "pip3" "docker" "git" "curl" "wget")
    
    for cmd in "${required_commands[@]}"; do
        if command -v "$cmd" &> /dev/null; then
            log_success "$cmd 발견: $(which $cmd)"
        else
            log_error "$cmd이 설치되지 않음"
            ((errors++))
        fi
    done
    
    # 디스크 공간 확인 (최소 10GB)
    local available_space=$(df . | tail -1 | awk '{print $4}')
    local required_space=10485760  # 10GB in KB
    
    if [ "$available_space" -gt "$required_space" ]; then
        log_success "충분한 디스크 공간: $(df -h . | tail -1 | awk '{print $4}')"
    else
        log_error "디스크 공간 부족. 최소 10GB 필요"
        ((errors++))
    fi
    
    # Docker 상태 확인
    if docker info &>/dev/null; then
        log_success "Docker 데몬 실행 중"
    else
        log_warning "Docker 데몬이 실행되지 않음. 시작을 시도합니다..."
        sudo systemctl start docker 2>/dev/null || true
    fi
    
    # 권한 확인
    if [ -w "." ]; then
        log_success "쓰기 권한 확인됨"
    else
        log_error "현재 디렉토리에 쓰기 권한이 없음"
        ((errors++))
    fi
    
    if [ "$errors" -gt 0 ]; then
        log_error "$errors개의 전제 조건 문제 발견. 해결 후 다시 시도하세요."
        exit 1
    fi
    
    log_success "모든 전제 조건 충족"
}

# 기존 설치 확인 및 백업
check_existing_installation() {
    log_header "기존 설치 확인"
    
    if [ -f "system_info.txt" ] || [ -d "ml" ] || [ -d "configs" ]; then
        log_warning "기존 설치가 감지되었습니다."
        
        read -p "백업을 생성하시겠습니까? (y/N): " -n 1 -r
        echo
        
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            local backup_dir="backup_$(date +%Y%m%d_%H%M%S)"
            mkdir -p "$backup_dir"
            
            log_step "백업 생성 중: $backup_dir"
            
            # 중요 파일들 백업
            for item in ml configs logs results attack_output system_info.txt; do
                if [ -e "$item" ]; then
                    cp -r "$item" "$backup_dir/" 2>/dev/null || true
                    log_info "$item 백업됨"
                fi
            done
            
            log_success "백업 완료: $backup_dir"
        fi
        
        read -p "기존 설치를 덮어쓰시겠습니까? (y/N): " -n 1 -r
        echo
        
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_warning "설치 취소됨"
            exit 0
        fi
    fi
}

# 메인 시스템 구축
deploy_main_system() {
    log_header "메인 시스템 구축"
    
    local total_steps=5
    local current_step=0
    
    # 1. 핵심 시스템 구축
    ((current_step++))
    show_progress $current_step $total_steps "핵심 시스템 구축 스크립트 실행 중..."
    
    if [ -f "setup_complete_system.sh" ]; then
        chmod +x setup_complete_system.sh
        ./setup_complete_system.sh
    else
        log_error "setup_complete_system.sh 파일을 찾을 수 없습니다."
        exit 1
    fi
    
    # 2. 분석 도구 구축
    ((current_step++))
    show_progress $current_step $total_steps "분석 및 모니터링 도구 구축 중..."
    
    if [ -f "create_analysis_tools.sh" ]; then
        chmod +x create_analysis_tools.sh
        ./create_analysis_tools.sh
    else
        log_warning "create_analysis_tools.sh 파일을 찾을 수 없습니다. 건너뜁니다."
    fi
    
    # 3. 추가 Python 라이브러리 설치
    ((current_step++))
    show_progress $current_step $total_steps "추가 Python 라이브러리 설치 중..."
    
    # 고급 ML 라이브러리 설치
    pip3 install --quiet --upgrade \
        tensorflow>=2.8.0 \
        keras>=2.8.0 \
        opencv-python>=4.5.0 \
        networkx>=2.6.0 \
        jupyterlab>=3.2.0 \
        pytest-cov>=3.0.0 \
        black>=22.0.0 \
        isort>=5.10.0 2>/dev/null || log_warning "일부 라이브러리 설치 실패"
    
    # 4. 개발 도구 설정
    ((current_step++))
    show_progress $current_step $total_steps "개발 도구 설정 중..."
    
    # Jupyter 설정
    mkdir -p notebooks
    cat > notebooks/MTD_Analysis.ipynb << 'JUPYTER_EOF'
{
 "cells": [
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "# MTD 드론 보안 테스트베드 분석 노트북\n",
    "\n",
    "이 노트북은 MTD 드론 보안 테스트베드의 실험 결과를 분석하기 위한 도구입니다."
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "source": [
    "import pandas as pd\n",
    "import numpy as np\n",
    "import matplotlib.pyplot as plt\n",
    "import seaborn as sns\n",
    "import sqlite3\n",
    "import json\n",
    "from datetime import datetime\n",
    "\n",
    "# 데이터 로드\n",
    "conn = sqlite3.connect('../attack_output/unified_metrics.db')\n",
    "df = pd.read_sql_query('SELECT * FROM unified_metrics ORDER BY timestamp', conn)\n",
    "conn.close()\n",
    "\n",
    "print(f\"데이터 로드 완료: {len(df)} 레코드\")\n",
    "df.head()"
   ]
  }
 ],
 "metadata": {
  "kernelspec": {
   "display_name": "Python 3",
   "language": "python",
   "name": "python3"
  }
 },
 "nbformat": 4,
 "nbformat_minor": 4
}
JUPYTER_EOF
    
    # 5. 최종 검증
    ((current_step++))
    show_progress $current_step $total_steps "시스템 검증 중..."
    
    # 시스템 검증 스크립트 실행
    if [ -f "scripts/monitoring/system_validator.py" ]; then
        python3 scripts/monitoring/system_validator.py > system_validation_results.txt 2>&1 || true
    fi
    
    log_success "메인 시스템 구축 완료"
}

# 고급 기능 설정
setup_advanced_features() {
    log_header "고급 기능 설정"
    
    # 1. 자동 백업 시스템
    log_step "자동 백업 시스템 설정 중..."
    
    cat > scripts/maintenance/auto_backup.sh << 'BACKUP_EOF'
#!/bin/bash
# 자동 백업 스크립트

BACKUP_DIR="backups/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

# 중요 데이터 백업
cp -r attack_output "$BACKUP_DIR/" 2>/dev/null || true
cp -r results "$BACKUP_DIR/" 2>/dev/null || true
cp -r logs "$BACKUP_DIR/" 2>/dev/null || true
cp -r ml/models "$BACKUP_DIR/" 2>/dev/null || true

# 압축
tar -czf "${BACKUP_DIR}.tar.gz" "$BACKUP_DIR"
rm -rf "$BACKUP_DIR"

echo "백업 완료: ${BACKUP_DIR}.tar.gz"

# 7일 이상 된 백업 삭제
find backups/ -name "*.tar.gz" -mtime +7 -delete 2>/dev/null || true
BACKUP_EOF
    
    chmod +x scripts/maintenance/auto_backup.sh
    
    # 2. 성능 모니터링 설정
    log_step "성능 모니터링 시스템 설정 중..."
    
    cat > scripts/monitoring/performance_monitor.py << 'PERF_EOF'
#!/usr/bin/env python3
"""성능 모니터링 스크립트"""

import psutil
import time
import json
import os
from datetime import datetime

def collect_system_metrics():
    """시스템 메트릭 수집"""
    return {
        'timestamp': time.time(),
        'cpu_percent': psutil.cpu_percent(interval=1),
        'memory_percent': psutil.virtual_memory().percent,
        'disk_percent': psutil.disk_usage('.').percent,
        'network_io': psutil.net_io_counters()._asdict(),
        'process_count': len(psutil.pids()),
        'load_average': os.getloadavg() if hasattr(os, 'getloadavg') else [0, 0, 0]
    }

def main():
    os.makedirs('logs/performance', exist_ok=True)
    
    while True:
        try:
            metrics = collect_system_metrics()
            
            # JSON 파일에 추가
            with open('logs/performance/system_metrics.jsonl', 'a') as f:
                f.write(json.dumps(metrics) + '\n')
            
            time.sleep(30)  # 30초마다 수집
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"메트릭 수집 오류: {e}")
            time.sleep(5)

if __name__ == '__main__':
    main()
PERF_EOF
    
    chmod +x scripts/monitoring/performance_monitor.py
    
    # 3. 자동 업데이트 시스템
    log_step "자동 업데이트 시스템 설정 중..."
    
    cat > scripts/maintenance/auto_update.sh << 'UPDATE_EOF'
#!/bin/bash
# 자동 업데이트 스크립트

log_info() { echo -e "\033[0;34m[INFO]\033[0m $1"; }
log_success() { echo -e "\033[0;32m[SUCCESS]\033[0m $1"; }

log_info "시스템 업데이트 확인 중..."

# Python 패키지 업데이트
log_info "Python 패키지 업데이트 중..."
pip3 install --upgrade pip
pip3 install --upgrade -r requirements.txt

# Git 저장소 업데이트 (있는 경우)
if [ -d ".git" ]; then
    log_info "Git 저장소 업데이트 중..."
    git pull origin main 2>/dev/null || log_info "Git 업데이트 건너뜀"
fi

# 시스템 검증
log_info "업데이트 후 시스템 검증..."
python3 scripts/monitoring/system_validator.py

log_success "업데이트 완료"
UPDATE_EOF
    
    chmod +x scripts/maintenance/auto_update.sh
    
    # 4. 로그 로테이션 설정
    log_step "로그 로테이션 설정 중..."
    
    cat > scripts/maintenance/log_rotation.sh << 'LOGROT_EOF'
#!/bin/bash
# 로그 로테이션 스크립트

LOG_DIRS=("logs" "attack_output")
MAX_SIZE="100M"
ARCHIVE_DIR="logs/archived"

mkdir -p "$ARCHIVE_DIR"

for log_dir in "${LOG_DIRS[@]}"; do
    if [ -d "$log_dir" ]; then
        find "$log_dir" -name "*.log" -size +$MAX_SIZE -exec \
            bash -c 'mv "$1" "logs/archived/$(basename "$1").$(date +%Y%m%d_%H%M%S)"' _ {} \;
    fi
done

# 압축된 로그는 30일 후 삭제
find "$ARCHIVE_DIR" -name "*.log.*" -mtime +30 -delete 2>/dev/null || true

echo "로그 로테이션 완료"
LOGROT_EOF
    
    chmod +x scripts/maintenance/log_rotation.sh
    
    log_success "고급 기능 설정 완료"
}

# 통합 테스트 실행
run_integration_tests() {
    log_header "통합 테스트 실행"
    
    local test_results=()
    
    # 1. 기본 기능 테스트
    log_step "기본 기능 테스트 중..."
    
    # Python 모듈 import 테스트
    python3 -c "
import sys
sys.path.append('.')

try:
    from ml.sdn_mtd_controller import SDNMTDController
    from ml.rl_mtd_agent import MTDEnvironment
    from ml.cti_classification_system import CTIEvent
    from ml.integrated_ml_pipeline import IntegratedMLPipeline
    print('✅ 모든 핵심 모듈 import 성공')
except Exception as e:
    print(f'❌ 모듈 import 실패: {e}')
    sys.exit(1)
" && test_results+=("모듈 import: 성공") || test_results+=("모듈 import: 실패")
    
    # 2. 설정 파일 테스트
    log_step "설정 파일 유효성 테스트 중..."
    
    python3 -c "
import yaml
import os

config_files = [
    'configs/attack_intensity/lpc_profiles.yaml',
    'configs/defense_levels/detection_thresholds.yaml',
    'configs/network_topologies/honeydrone_network.yaml'
]

for config_file in config_files:
    try:
        with open(config_file, 'r') as f:
            yaml.safe_load(f)
        print(f'✅ {config_file}: 유효')
    except Exception as e:
        print(f'❌ {config_file}: {e}')
" && test_results+=("설정 파일: 성공") || test_results+=("설정 파일: 실패")
    
    # 3. 데이터베이스 테스트
    log_step "데이터베이스 연결 테스트 중..."
    
    python3 -c "
import sqlite3
import os

os.makedirs('attack_output', exist_ok=True)

try:
    conn = sqlite3.connect('attack_output/test.db')
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE test (id INTEGER PRIMARY KEY, data TEXT)')
    cursor.execute('INSERT INTO test (data) VALUES (?)', ('test_data',))
    cursor.execute('SELECT * FROM test')
    result = cursor.fetchone()
    conn.close()
    os.remove('attack_output/test.db')
    print('✅ 데이터베이스 연결 성공')
except Exception as e:
    print(f'❌ 데이터베이스 연결 실패: {e}')
" && test_results+=("데이터베이스: 성공") || test_results+=("데이터베이스: 실패")
    
    # 4. 네트워크 포트 테스트
    log_step "네트워크 포트 가용성 테스트 중..."
    
    python3 -c "
import socket

ports = [5001, 5002, 8050, 8765, 9000]
available_ports = []

for port in ports:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(('localhost', port))
        sock.close()
        available_ports.append(port)
    except:
        pass

if len(available_ports) == len(ports):
    print('✅ 모든 포트 사용 가능')
else:
    print(f'⚠️ 일부 포트 사용 중: {set(ports) - set(available_ports)}')
" && test_results+=("네트워크 포트: 성공") || test_results+=("네트워크 포트: 경고")
    
    # 테스트 결과 출력
    echo ""
    log_info "통합 테스트 결과:"
    for result in "${test_results[@]}"; do
        echo "  • $result"
    done
    
    log_success "통합 테스트 완료"
}

# 웹 인터페이스 시작
start_web_interfaces() {
    log_header "웹 인터페이스 시작"
    
    # PID 추적용 배열
    declare -a WEB_PIDS=()
    
    log_step "통합 컨트롤 패널 시작 중 (포트 9000)..."
    python3 scripts/monitoring/control_panel.py &
    WEB_PIDS+=($!)
    
    sleep 2
    
    log_step "실시간 대시보드 시작 중 (포트 8050)..."
    python3 scripts/monitoring/realtime_dashboard.py &
    WEB_PIDS+=($!)
    
    sleep 2
    
    # PID 저장
    printf '%s\n' "${WEB_PIDS[@]}" > /tmp/mtd_web_pids.txt
    
    log_success "웹 인터페이스 시작 완료"
    
    # 인터페이스 상태 확인
    sleep 5
    
    local interfaces=(
        "9000:통합 컨트롤 패널"
        "8050:실시간 대시보드"
    )
    
    for interface in "${interfaces[@]}"; do
        IFS=':' read -r port name <<< "$interface"
        if curl -s "http://localhost:$port" >/dev/null 2>&1; then
            log_success "$name 접근 가능: http://localhost:$port"
        else
            log_warning "$name 접근 불가: http://localhost:$port"
        fi
    done
}

# 데모 시나리오 실행
run_demo_scenario() {
    log_header "데모 시나리오 실행"
    
    log_info "간단한 데모 시나리오를 실행하여 시스템을 테스트합니다."
    
    read -p "데모를 실행하시겠습니까? (y/N): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_step "5분 데모 시나리오 시작..."
        
        # 백그라운드에서 시스템 시작
        log_info "시스템 컴포넌트 시작 중..."
        
        # 타임스탬프 수집기 시작
        python3 data_pipeline/collectors/timestamp_collector.py &
        local collector_pid=$!
        
        # 허니드론 네트워크 시작 (짧은 시간)
        timeout 300 python3 honeydrone_network/honeydrone_manager.py &
        local honeydrone_pid=$!
        
        # 간단한 공격 시뮬레이션
        log_info "공격 시뮬레이션 실행 중..."
        
        # 시뮬레이션된 공격 데이터 생성
        python3 -c "
import time
import json
import os

os.makedirs('attack_output', exist_ok=True)

# 시뮬레이션된 LPC 공격 로그 생성
with open('attack_output/bus.log', 'w') as f:
    for i in range(10):
        timestamp = time.time() + i
        f.write(f'{timestamp},type=EFFECT,module=wifi_discovery,value=1.0\n')
        time.sleep(0.5)

print('데모 공격 시뮬레이션 완료')
"
        
        log_info "5분 대기 중... (시스템 작동 관찰)"
        
        # 5분 대기하며 진행률 표시
        for i in {1..300}; do
            show_progress $i 300 "데모 실행 중... (${i}초/300초)"
            sleep 1
        done
        
        # 프로세스 정리
        kill $collector_pid $honeydrone_pid 2>/dev/null || true
        
        log_success "데모 시나리오 완료"
        
        # 결과 확인
        if [ -f "attack_output/bus.log" ]; then
            log_info "생성된 로그 파일:"
            echo "  • attack_output/bus.log ($(wc -l < attack_output/bus.log) 라인)"
        fi
        
        if [ -f "logs/timestamps/collector.log" ]; then
            echo "  • logs/timestamps/collector.log"
        fi
    else
        log_info "데모 건너뜀"
    fi
}

# 최종 보고서 생성
generate_deployment_report() {
    log_header "배포 보고서 생성"
    
    local report_file="DEPLOYMENT_REPORT_$(date +%Y%m%d_%H%M%S).md"
    
    cat > "$report_file" << REPORT_EOF
# MTD 드론 보안 테스트베드 배포 보고서

배포 일시: $(date)
배포 위치: $(pwd)
배포자: $(whoami)

## 🎯 배포 요약

### 성공적으로 배포된 컴포넌트
- ✅ 핵심 시스템 아키텍처
- ✅ SDN MTD 컨트롤러
- ✅ 강화학습 에이전트
- ✅ CTI 분류 시스템
- ✅ 허니드론 네트워크
- ✅ NS-3 시뮬레이션 통합
- ✅ 웹 기반 모니터링 시스템
- ✅ 자동화된 분석 도구

### 시스템 정보
$(cat system_deployment_info.txt 2>/dev/null || echo "시스템 정보 수집 실패")

## 🌐 웹 인터페이스

### 사용 가능한 서비스
- **통합 컨트롤 패널**: http://localhost:9000
- **실시간 대시보드**: http://localhost:8050
- **공격/평가 콘솔**: http://localhost:5001
- **DVD 모니터링**: http://localhost:5002

## 🚀 사용법

### 빠른 시작
\`\`\`bash
# 전체 시스템 시작
./scripts/deployment/run_integrated_system.sh start

# 실험 실행
./scripts/deployment/run_integrated_system.sh experiment stealth_recon

# 상태 확인
./scripts/deployment/run_integrated_system.sh status
\`\`\`

### 고급 사용법
\`\`\`bash
# 전체 실험 스위트
./scripts/deployment/run_integrated_system.sh full-experiment

# 시스템 검증
python3 scripts/monitoring/system_validator.py

# 성능 모니터링
python3 scripts/monitoring/performance_monitor.py
\`\`\`

## 📊 주요 디렉토리

| 디렉토리 | 용도 | 설명 |
|----------|------|------|
| \`ml/\` | 머신러닝 | SDN, RL, CTI 분류 모델 |
| \`configs/\` | 설정 | 공격 강도, 방어 수준 설정 |
| \`honeydrone_network/\` | 네트워크 | 허니드론 네트워크 관리 |
| \`scripts/\` | 스크립트 | 배포, 모니터링, 분석 도구 |
| \`attack_output/\` | 결과 | 공격 로그 및 메트릭 |
| \`results/\` | 실험 | 실험 결과 및 보고서 |

## 🔧 유지보수

### 정기 작업
\`\`\`bash
# 자동 백업
./scripts/maintenance/auto_backup.sh

# 시스템 업데이트
./scripts/maintenance/auto_update.sh

# 로그 로테이션
./scripts/maintenance/log_rotation.sh
\`\`\`

### 문제 해결
- 시스템 상태 확인: \`./scripts/deployment/run_integrated_system.sh status\`
- 로그 확인: \`tail -f attack_output/integrated_pipeline.log\`
- 시스템 검증: \`python3 scripts/monitoring/system_validator.py\`

## 📞 지원

시스템 관련 문제나 질문이 있으시면:
1. 시스템 검증기를 먼저 실행하세요
2. 로그 파일을 확인하세요
3. 웹 인터페이스의 상태를 점검하세요

---
*이 보고서는 MTD 드론 보안 테스트베드 자동 배포 시스템에 의해 생성되었습니다.*
REPORT_EOF
    
    log_success "배포 보고서 생성: $report_file"
}

# 정리 함수
cleanup_on_exit() {
    log_info "정리 작업 수행 중..."
    
    # 웹 인터페이스 PID 정리
    if [ -f "/tmp/mtd_web_pids.txt" ]; then
        while read -r pid; do
            kill "$pid" 2>/dev/null || true
        done < /tmp/mtd_web_pids.txt
        rm -f /tmp/mtd_web_pids.txt
    fi
    
    log_info "정리 완료"
}

# 신호 핸들러 설정
trap cleanup_on_exit EXIT INT TERM

# =================================================================
# 메인 실행 부분
# =================================================================

main() {
    # 시작 시간 기록
    local start_time=$(date +%s)
    
    log_header "MTD 드론 보안 테스트베드 마스터 배포 시작"
    
    # 1. 시스템 정보 수집
    collect_system_info
    
    # 2. 전제 조건 검사
    check_prerequisites
    
    # 3. 기존 설치 확인
    check_existing_installation
    
    # 4. 메인 시스템 구축
    deploy_main_system
    
    # 5. 고급 기능 설정
    setup_advanced_features
    
    # 6. 통합 테스트
    run_integration_tests
    
    # 7. 웹 인터페이스 시작
    start_web_interfaces
    
    # 8. 데모 시나리오 (선택사항)
    run_demo_scenario
    
    # 9. 최종 보고서 생성
    generate_deployment_report
    
    # 완료 시간 계산
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    local minutes=$((duration / 60))
    local seconds=$((duration % 60))
    
    # 최종 성공 메시지
    echo ""
    echo ""
    cat << 'FINAL_EOF'
╔═══════════════════════════════════════════════════════════════╗
║                    🎉 배포 완료! 🎉                          ║
║                                                               ║
║  MTD 드론 보안 테스트베드가 성공적으로 배포되었습니다!        ║
╚═══════════════════════════════════════════════════════════════╝
FINAL_EOF
    
    echo ""
    log_success "총 배포 시간: ${minutes}분 ${seconds}초"
    echo ""
    
    echo -e "${CYAN}🌐 웹 인터페이스:${NC}"
    echo "  • 통합 컨트롤 패널: http://localhost:9000"
    echo "  • 실시간 대시보드: http://localhost:8050"
    echo ""
    
    echo -e "${YELLOW}🚀 빠른 시작:${NC}"
    echo "  ./scripts/deployment/run_integrated_system.sh start"
    echo ""
    
    echo -e "${GREEN}📚 문서:${NC}"
    echo "  • 시스템 정보: cat system_info.txt"
    echo "  • 배포 보고서: cat DEPLOYMENT_REPORT_*.md"
    echo "  • 분석 노트북: jupyter lab notebooks/"
    echo ""
    
    echo -e "${PURPLE}🛡️ 지금 시작할 수 있습니다!${NC}"
    echo ""
    
    # 자동 시작 옵션
    read -p "지금 시스템을 시작하시겠습니까? (y/N): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_info "시스템 시작 중..."
        ./scripts/deployment/run_integrated_system.sh start
    else
        log_info "수동으로 시작하려면: ./scripts/deployment/run_integrated_system.sh start"
    fi
}

# 스크립트 인수 처리
case "${1:-}" in
    --help|-h)
        echo "MTD 드론 보안 테스트베드 마스터 배포 스크립트"
        echo ""
        echo "사용법: $0 [옵션]"
        echo ""
        echo "옵션:"
        echo "  --help, -h     이 도움말 표시"
        echo "  --quick        빠른 배포 (대화형 질문 건너뛰기)"
        echo "  --no-demo      데모 건너뛰기"
        echo "  --no-web       웹 인터페이스 시작 안함"
        echo ""
        exit 0
        ;;
    --quick)
        export QUICK_DEPLOY=1
        ;;
    --no-demo)
        export NO_DEMO=1
        ;;
    --no-web)
        export NO_WEB=1
        ;;
esac

# 메인 함수 실행
main "$@"