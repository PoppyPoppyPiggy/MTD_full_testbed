#!/bin/bash

# 파일: /home/kali/MTD/MTD_full_testbed/run_integrated_dvd_ns3_testbed.sh
# 목적: DVD 공격 시나리오와 NS-3 FANET 네트워크 통합 테스트베드 실행
# 기반: 전체 MTD 시스템 통합

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# 기본 설정
BASE_DIR="/home/kali/MTD/MTD_full_testbed"
RESULTS_DIR="$BASE_DIR/results/integrated_simulation_$(date +%Y%m%d_%H%M%S)"
LOG_FILE="$RESULTS_DIR/integrated_testbed.log"

# 실행 파라미터
DVD_ATTACKS_ENABLED=true
NS3_SIMULATION_ENABLED=true
FANET_NODES=10
SIMULATION_TIME=600  # 10분
ATTACK_SCENARIOS="reconnaissance,protocol_tampering,denial_of_service"

# PID 저장 배열
declare -a SERVICE_PIDS

log_info() {
    if [ -f "$LOG_FILE" ]; then
        echo -e "${GREEN}[INFO]${NC} $1" | tee -a "$LOG_FILE"
    else
        echo -e "${GREEN}[INFO]${NC} $1"
    fi
}

log_warning() {
    if [ -f "$LOG_FILE" ]; then
        echo -e "${YELLOW}[WARN]${NC} $1" | tee -a "$LOG_FILE"
    else
        echo -e "${YELLOW}[WARN]${NC} $1"
    fi
}

log_error() {
    if [ -f "$LOG_FILE" ]; then
        echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
    else
        echo -e "${RED}[ERROR]${NC} $1"
    fi
}

print_header() {
    clear
    echo -e "${CYAN}${BOLD}"
    echo "╔══════════════════════════════════════════════════════════════════════╗"
    echo "║                🎯 DVD-NS3 통합 테스트베드 시스템                    ║"
    echo "║                                                                      ║"
    echo "║  🐉 Damn Vulnerable Drone Attack Scenarios                          ║"
    echo "║  🌐 NS-3 FANET Network Simulation                                   ║"
    echo "║  🔗 Real-time Integration & Monitoring                              ║"
    echo "║                                                                      ║"
    echo "║                    논문 작성용 연구 플랫폼                           ║"
    echo "╚══════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

check_prerequisites() {
    # 먼저 결과 디렉토리 생성
    mkdir -p "$RESULTS_DIR"
    
    # 로그 파일 초기화
    echo "=== DVD-NS3 Integrated Testbed Started at $(date) ===" > "$LOG_FILE"
    
    log_info "🔍 전제 조건 확인 중..."
    
    # 필수 디렉토리 확인
    required_dirs=(
        "$BASE_DIR/dvd_lite/dvd_attacks"
        "$BASE_DIR/ns-3.45/ns-3-dev"
        "$BASE_DIR/dvd_ns3_integration"
    )
    
    for dir in "${required_dirs[@]}"; do
        if [ -d "$dir" ]; then
            log_info "✅ 디렉토리 확인: $dir"
        else
            log_error "❌ 디렉토리 누락: $dir"
            
            # 누락된 디렉토리 생성 시도
            if [[ "$dir" == *"dvd_ns3_integration"* ]]; then
                log_info "🔧 dvd_ns3_integration 디렉토리 생성 중..."
                mkdir -p "$dir"
                if [ -d "$dir" ]; then
                    log_info "✅ 디렉토리 생성 완료: $dir"
                else
                    exit 1
                fi
            else
                exit 1
            fi
        fi
    done
    
    # 필수 파일 확인 및 생성
    required_files=(
        "$BASE_DIR/dvd_ns3_integration/dvd_monitor_service.py"
        "$BASE_DIR/dvd_ns3_integration/dvd_attack_connector.py"
    )
    
    for file in "${required_files[@]}"; do
        if [ -f "$file" ]; then
            log_info "✅ 파일 확인: $(basename $file)"
        else
            log_warning "❌ 파일 누락: $file"
            log_info "🔧 필요한 파일을 먼저 생성해주세요."
            
            # 기본 파일 생성 가이드 제공
            if [[ "$file" == *"dvd_monitor_service.py"* ]]; then
                log_info "다음 명령으로 파일을 생성하세요:"
                log_info "touch $file"
                log_info "# 또는 제공된 코드를 복사하여 생성"
            fi
        fi
    done
    
    # NS-3 관련 파일 확인
    ns3_files=(
        "$BASE_DIR/ns-3.45/ns-3-dev/scratch/dvd-fanet-integration.cc"
        "$BASE_DIR/ns-3.45/ns-3-dev/run_dvd_fanet_integration.sh"
    )
    
    for file in "${ns3_files[@]}"; do
        if [ -f "$file" ]; then
            log_info "✅ NS-3 파일 확인: $(basename $file)"
        else
            log_warning "⚠️ NS-3 파일 누락: $file"
            if [[ "$file" == *"scratch"* ]]; then
                log_info "NS-3 시뮬레이션은 건너뛰고 DVD 부분만 실행합니다."
                NS3_SIMULATION_ENABLED=false
            fi
        fi
    done
    
    # Python 의존성 확인 (경고만 출력)
    python_deps=("asyncio" "psutil")
    for dep in "${python_deps[@]}"; do
        if python3 -c "import $dep" 2>/dev/null; then
            log_info "✅ Python 모듈: $dep"
        else
            log_warning "⚠️ Python 모듈 누락: $dep"
            log_info "설치 권장: pip3 install $dep"
        fi
    done
    
    # docker와 watchdog는 선택사항으로 처리
    optional_deps=("docker" "watchdog")
    for dep in "${optional_deps[@]}"; do
        if python3 -c "import $dep" 2>/dev/null; then
            log_info "✅ 선택적 Python 모듈: $dep"
        else
            log_info "ℹ️ 선택적 모듈 없음: $dep (기능 제한될 수 있음)"
        fi
    done
    
    log_info "🔍 전제 조건 확인 완료"
}

start_dvd_services() {
    log_info "🐉 DVD 서비스 시작 중..."
    
    cd "$BASE_DIR"
    
    # 1. DVD 모니터링 서비스 시작
    log_info "📡 DVD 모니터링 서비스 시작..."
    python3 dvd_ns3_integration/dvd_monitor_service.py &
    local dvd_monitor_pid=$!
    SERVICE_PIDS+=($dvd_monitor_pid)
    echo $dvd_monitor_pid > /home/kali/MTD/MTD_full_testbed/pids/dvd_monitor_service.pid
    
    sleep 3
    if kill -0 $dvd_monitor_pid 2>/dev/null; then
        log_info "✅ DVD 모니터링 서비스 시작됨 (PID: $dvd_monitor_pid)"
    else
        log_error "❌ DVD 모니터링 서비스 시작 실패"
        return 1
    fi
    
    # 2. DVD 공격 커넥터 시작
    log_info "⚔️ DVD 공격 커넥터 시작..."
    python3 dvd_ns3_integration/dvd_attack_connector.py &
    local dvd_connector_pid=$!
    SERVICE_PIDS+=($dvd_connector_pid)
    echo $dvd_connector_pid > /home/kali/MTD/MTD_full_testbed/pids/dvd_attack_connector.pid
    
    sleep 3
    if kill -0 $dvd_connector_pid 2>/dev/null; then
        log_info "✅ DVD 공격 커넥터 시작됨 (PID: $dvd_connector_pid)"
    else
        log_error "❌ DVD 공격 커넥터 시작 실패"
        return 1
    fi
    
    # 3. 기존 DVD 테스트베드 서비스들 시작
    if [ -f "run_complete_mtd.sh" ]; then
        log_info "🚁 기존 MTD 서비스 시작..."
        ./run_complete_mtd.sh 1 light $FANET_NODES > "$RESULTS_DIR/mtd_services.log" 2>&1 &
        local mtd_services_pid=$!
        SERVICE_PIDS+=($mtd_services_pid)
        echo $mtd_services_pid > /home/kali/MTD/MTD_full_testbed/pids/mtd_services.pid
        
        sleep 10
        if kill -0 $mtd_services_pid 2>/dev/null; then
            log_info "✅ MTD 서비스 시작됨 (PID: $mtd_services_pid)"
        else
            log_warning "⚠️ MTD 서비스 시작 실패 또는 빠른 종료"
        fi
    fi
    
    log_info "🐉 DVD 서비스 시작 완료"
}

start_ns3_simulation() {
    log_info "🌐 NS-3 FANET 시뮬레이션 시작 중..."
    
    cd "$BASE_DIR/ns-3.45/ns-3-dev"
    
    # NS-3 시뮬레이션 실행
    log_info "🔧 NS-3 시뮬레이션 파라미터:"
    log_info "   • FANET 노드 수: $FANET_NODES"
    log_info "   • 시뮬레이션 시간: $SIMULATION_TIME 초"
    log_info "   • 결과 디렉토리: $RESULTS_DIR"
    
    # 시뮬레이션 실행 (백그라운드)
    ./run_dvd_fanet_integration.sh \
        --nodes $FANET_NODES \
        --time $SIMULATION_TIME \
        --animation "dvd-fanet-$(date +%H%M%S).xml" \
        > "$RESULTS_DIR/ns3_simulation.log" 2>&1 &
    
    local ns3_pid=$!
    SERVICE_PIDS+=($ns3_pid)
    echo $ns3_pid > /home/kali/MTD/MTD_full_testbed/pids/ns3_simulation.pid
    
    sleep 5
    if kill -0 $ns3_pid 2>/dev/null; then
        log_info "✅ NS-3 시뮬레이션 시작됨 (PID: $ns3_pid)"
    else
        log_error "❌ NS-3 시뮬레이션 시작 실패"
        return 1
    fi
    
    log_info "🌐 NS-3 FANET 시뮬레이션 시작 완료"
}

execute_attack_scenarios() {
    log_info "⚔️ DVD 공격 시나리오 실행 중..."
    
    cd "$BASE_DIR"
    
    # 공격 시나리오 배열로 변환
    IFS=',' read -ra ATTACK_ARRAY <<< "$ATTACK_SCENARIOS"
    
    log_info "📋 실행할 공격 시나리오:"
    for scenario in "${ATTACK_ARRAY[@]}"; do
        log_info "   • $scenario"
    done
    
    # 각 공격 시나리오 순차 실행
    for scenario in "${ATTACK_ARRAY[@]}"; do
        log_info "🎯 공격 시나리오 실행: $scenario"
        
        case $scenario in
            "reconnaissance")
                execute_reconnaissance_attacks
                ;;
            "protocol_tampering")
                execute_protocol_tampering_attacks
                ;;
            "denial_of_service")
                execute_dos_attacks
                ;;
            "injection")
                execute_injection_attacks
                ;;
            "exfiltration")
                execute_exfiltration_attacks
                ;;
            "firmware_attacks")
                execute_firmware_attacks
                ;;
            *)
                log_warning "⚠️ 알 수 없는 공격 시나리오: $scenario"
                ;;
        esac
        
        # 공격 간 대기 시간
        log_info "⏱️ 다음 공격까지 30초 대기..."
        sleep 30
    done
    
    log_info "⚔️ 모든 공격 시나리오 실행 완료"
}

execute_reconnaissance_attacks() {
    log_info "🔍 정찰 공격 실행 중..."
    
    local attacks=(
        "wifi_network_discovery.sh"
        "mavlink_service_discovery.sh"
        "drone_component_enumeration.sh"
        "camera_stream_discovery.sh"
    )
    
    for attack in "${attacks[@]}"; do
        local attack_path="dvd_lite/dvd_attacks/reconnaissance/$attack"
        if [ -f "$attack_path" ]; then
            log_info "🚀 실행: $attack"
            chmod +x "$attack_path"
            timeout 60 bash "$attack_path" > "$RESULTS_DIR/reconnaissance_$attack.log" 2>&1 &
            sleep 10
        else
            log_warning "⚠️ 공격 스크립트 없음: $attack_path"
        fi
    done
}

execute_protocol_tampering_attacks() {
    log_info "🔧 프로토콜 조작 공격 실행 중..."
    
    local attacks=(
        "gps_spoofing.sh"
        "mavlink_packet_injection.sh"
        "rf_jamming.sh"
    )
    
    for attack in "${attacks[@]}"; do
        local attack_path="dvd_lite/dvd_attacks/protocol_tampering/$attack"
        if [ -f "$attack_path" ]; then
            log_info "🚀 실행: $attack"
            chmod +x "$attack_path"
            timeout 90 bash "$attack_path" > "$RESULTS_DIR/protocol_tampering_$attack.log" 2>&1 &
            sleep 15
        else
            log_warning "⚠️ 공격 스크립트 없음: $attack_path"
        fi
    done
}

execute_dos_attacks() {
    log_info "💥 서비스 거부 공격 실행 중..."
    
    local attacks=(
        "mavlink_flood.sh"
        "wifi_deauth.sh"
        "resource_exhaustion.sh"
        "service_disruption.sh"
    )
    
    for attack in "${attacks[@]}"; do
        local attack_path="dvd_lite/dvd_attacks/denial_of_service/$attack"
        if [ -f "$attack_path" ]; then
            log_info "🚀 실행: $attack"
            chmod +x "$attack_path"
            timeout 120 bash "$attack_path" > "$RESULTS_DIR/dos_$attack.log" 2>&1 &
            sleep 20
        else
            log_warning "⚠️ 공격 스크립트 없음: $attack_path"
        fi
    done
}

execute_injection_attacks() {
    log_info "💉 주입 공격 실행 중..."
    
    local attacks=(
        "flight_plan_injection.sh"
        "parameter_manipulation.sh"
        "firmware_upload_manipulation.sh"
        "sql_injection.sh"
    )
    
    for attack in "${attacks[@]}"; do
        local attack_path="dvd_lite/dvd_attacks/injection/$attack"
        if [ -f "$attack_path" ]; then
            log_info "🚀 실행: $attack"
            chmod +x "$attack_path"
            timeout 90 bash "$attack_path" > "$RESULTS_DIR/injection_$attack.log" 2>&1 &
            sleep 15
        else
            log_warning "⚠️ 공격 스크립트 없음: $attack_path"
        fi
    done
}

execute_exfiltration_attacks() {
    log_info "🕵️ 데이터 탈취 공격 실행 중..."
    
    local attacks=(
        "telemetry_data_exfiltration.sh"
        "flight_log_extraction.sh"
        "video_stream_hijacking.sh"
    )
    
    for attack in "${attacks[@]}"; do
        local attack_path="dvd_lite/dvd_attacks/exfiltration/$attack"
        if [ -f "$attack_path" ]; then
            log_info "🚀 실행: $attack"
            chmod +x "$attack_path"
            timeout 120 bash "$attack_path" > "$RESULTS_DIR/exfiltration_$attack.log" 2>&1 &
            sleep 20
        else
            log_warning "⚠️ 공격 스크립트 없음: $attack_path"
        fi
    done
}

execute_firmware_attacks() {
    log_info "🦠 펌웨어 공격 실행 중..."
    
    local attacks=(
        "bootloader_exploitation.sh"
        "firmware_rollback.sh"
        "secure_boot_bypass.sh"
    )
    
    for attack in "${attacks[@]}"; do
        local attack_path="dvd_lite/dvd_attacks/firmware_attacks/$attack"
        if [ -f "$attack_path" ]; then
            log_info "🚀 실행: $attack"
            chmod +x "$attack_path"
            timeout 150 bash "$attack_path" > "$RESULTS_DIR/firmware_$attack.log" 2>&1 &
            sleep 25
        else
            log_warning "⚠️ 공격 스크립트 없음: $attack_path"
        fi
    done
}

monitor_integration_status() {
    log_info "📊 통합 시스템 모니터링 시작..."
    
    local monitor_duration=$((SIMULATION_TIME - 60))  # 시뮬레이션 종료 1분 전까지
    local check_interval=30
    local elapsed=0
    
    while [ $elapsed -lt $monitor_duration ]; do
        log_info "📈 시스템 상태 확인 (${elapsed}/${monitor_duration}초)"
        
        # 서비스 상태 확인
        check_service_status
        
        # 공격 결과 수집
        collect_attack_results
        
        # NS-3 시뮬레이션 상태 확인
        check_ns3_status
        
        # 시스템 리소스 확인
        check_system_resources
        
        sleep $check_interval
        elapsed=$((elapsed + check_interval))
    done
    
    log_info "📊 시스템 모니터링 완료"
}

check_service_status() {
    log_info "🔍 서비스 상태 확인..."
    
    # DVD 모니터링 서비스
    if [ -f "/home/kali/MTD/MTD_full_testbed/pids/dvd_monitor_service.pid" ]; then
        local pid=$(cat /home/kali/MTD/MTD_full_testbed/pids/dvd_monitor_service.pid)
        if kill -0 $pid 2>/dev/null; then
            log_info "✅ DVD 모니터링 서비스: 실행 중 (PID: $pid)"
        else
            log_warning "⚠️ DVD 모니터링 서비스: 중지됨"
        fi
    fi
    
    # DVD 공격 커넥터
    if [ -f "/home/kali/MTD/MTD_full_testbed/pids/dvd_attack_connector.pid" ]; then
        local pid=$(cat /home/kali/MTD/MTD_full_testbed/pids/dvd_attack_connector.pid)
        if kill -0 $pid 2>/dev/null; then
            log_info "✅ DVD 공격 커넥터: 실행 중 (PID: $pid)"
        else
            log_warning "⚠️ DVD 공격 커넥터: 중지됨"
        fi
    fi
    
    # NS-3 시뮬레이션
    if [ -f "/home/kali/MTD/MTD_full_testbed/pids/ns3_simulation.pid" ]; then
        local pid=$(cat /home/kali/MTD/MTD_full_testbed/pids/ns3_simulation.pid)
        if kill -0 $pid 2>/dev/null; then
            log_info "✅ NS-3 시뮬레이션: 실행 중 (PID: $pid)"
        else
            log_warning "⚠️ NS-3 시뮬레이션: 중지됨"
        fi
    fi
}

collect_attack_results() {
    log_info "📄 공격 결과 수집..."
    
    # IOC 파일들 수집
    local ioc_count=0
    for ioc_file in /tmp/*iocs.txt; do
        if [ -f "$ioc_file" ]; then
            cp "$ioc_file" "$RESULTS_DIR/"
            ioc_count=$((ioc_count + 1))
        fi
    done
    
    if [ $ioc_count -gt 0 ]; then
        log_info "📋 수집된 IOC 파일: $ioc_count 개"
    fi
    
    # NS-3 공격 결과 파일 확인
    if [ -f "/tmp/dvd_ns3_attack_results.csv" ]; then
        local line_count=$(wc -l < /tmp/dvd_ns3_attack_results.csv)
        log_info "📊 NS-3 공격 이벤트: $((line_count - 1)) 개"
        cp /tmp/dvd_ns3_attack_results.csv "$RESULTS_DIR/"
    fi
    
    # 공격 로그 파일들 수집
    for log_file in "$RESULTS_DIR"/*.log; do
        if [ -f "$log_file" ] && [ -s "$log_file" ]; then
            log_info "📝 공격 로그: $(basename $log_file) ($(du -h "$log_file" | cut -f1))"
        fi
    done
}

check_ns3_status() {
    log_info "🌐 NS-3 시뮬레이션 상태 확인..."
    
    # NS-3 로그 파일 크기 확인
    local ns3_log="$RESULTS_DIR/ns3_simulation.log"
    if [ -f "$ns3_log" ]; then
        local log_size=$(du -h "$ns3_log" | cut -f1)
        local last_lines=$(tail -5 "$ns3_log" | grep -c "Flow\|패킷\|노드" || echo "0")
        log_info "📊 NS-3 로그: $log_size, 최근 활동: $last_lines 라인"
    fi
    
    # 네트워크 포트 확인 (NS-3 통신 포트)
    if netstat -tuln 2>/dev/null | grep -q ":9999"; then
        log_info "🌐 NS-3 통신 포트 활성화됨"
    else
        log_warning "⚠️ NS-3 통신 포트 비활성화"
    fi
}

check_system_resources() {
    log_info "💻 시스템 리소스 확인..."
    
    # CPU 사용률
    local cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)
    log_info "💾 CPU 사용률: ${cpu_usage}%"
    
    # 메모리 사용률
    local mem_info=$(free | grep Mem)
    local mem_used=$(echo $mem_info | awk '{printf "%.1f", $3/$2 * 100.0}')
    log_info "🧠 메모리 사용률: ${mem_used}%"
    
    # 디스크 사용률
    local disk_usage=$(df -h "$RESULTS_DIR" | tail -1 | awk '{print $5}')
    log_info "💽 디스크 사용률: $disk_usage"
    
    # 실행 중인 공격 프로세스 수
    local attack_processes=$(ps aux | grep -E "(dvd_attacks|reconnaissance|protocol_tampering|denial_of_service|injection|exfiltration|firmware)" | grep -v grep | wc -l)
    log_info "⚔️ 활성 공격 프로세스: $attack_processes 개"
}

generate_comprehensive_report() {
    log_info "📋 종합 보고서 생성 중..."
    
    local report_file="$RESULTS_DIR/comprehensive_report.md"
    
    cat > "$report_file" << EOF
# DVD-NS3 통합 테스트베드 종합 보고서

## 실험 개요
- **실험 시작**: $(date)
- **FANET 노드 수**: $FANET_NODES
- **시뮬레이션 시간**: $SIMULATION_TIME 초
- **공격 시나리오**: $ATTACK_SCENARIOS
- **결과 디렉토리**: $RESULTS_DIR

## 시스템 구성
### DVD 공격 시나리오
- **모니터링 서비스**: DVD 도커 컨테이너 및 공격 스크립트 실시간 모니터링
- **공격 커넥터**: 공격 이벤트를 NS-3로 실시간 전송
- **공격 카테고리**: 정찰, 프로토콜 조작, DoS, 주입, 데이터 탈취, 펌웨어

### NS-3 FANET 시뮬레이션
- **네트워크 모델**: IEEE 802.11ac 기반 FANET
- **이동성 모델**: 3D 랜덤 웨이포인트
- **통신 범위**: 300m
- **시뮬레이션 영역**: 4km x 4km x 450m

## 실험 결과

### 공격 통계
EOF

    # 공격 통계 추가
    if [ -f "$RESULTS_DIR/dvd_ns3_attack_results.csv" ]; then
        echo "#### 공격 유형별 발생 횟수" >> "$report_file"
        tail -n +2 "$RESULTS_DIR/dvd_ns3_attack_results.csv" | cut -d',' -f2 | sort | uniq -c | while read count type; do
            echo "- **$type**: $count 회" >> "$report_file"
        done
        
        echo "" >> "$report_file"
        echo "#### 네트워크 영향도" >> "$report_file"
        
        # 평균 에너지 레벨
        local avg_energy=$(tail -n +2 "$RESULTS_DIR/dvd_ns3_attack_results.csv" | cut -d',' -f4 | awk '{sum+=$1; count++} END {if(count>0) print sum/count; else print 0}')
        echo "- **평균 노드 에너지**: ${avg_energy}%" >> "$report_file"
        
        # 총 패킷 손실
        local total_dropped=$(tail -n +2 "$RESULTS_DIR/dvd_ns3_attack_results.csv" | cut -d',' -f5 | awk '{sum+=$1} END {print sum+0}')
        echo "- **총 패킷 손실**: $total_dropped 개" >> "$report_file"
        
        # 악성 패킷 수
        local total_malicious=$(tail -n +2 "$RESULTS_DIR/dvd_ns3_attack_results.csv" | cut -d',' -f6 | awk '{sum+=$1} END {print sum+0}')
        echo "- **총 악성 패킷**: $total_malicious 개" >> "$report_file"
    fi
    
    cat >> "$report_file" << EOF

### 수집된 데이터
EOF
    
    # 수집된 파일 목록
    echo "#### 로그 파일" >> "$report_file"
    for log_file in "$RESULTS_DIR"/*.log; do
        if [ -f "$log_file" ]; then
            local size=$(du -h "$log_file" | cut -f1)
            echo "- **$(basename "$log_file")**: $size" >> "$report_file"
        fi
    done
    
    echo "" >> "$report_file"
    echo "#### IOC 파일" >> "$report_file"
    for ioc_file in "$RESULTS_DIR"/*iocs.txt; do
        if [ -f "$ioc_file" ]; then
            local lines=$(wc -l < "$ioc_file")
            echo "- **$(basename "$ioc_file")**: $lines 라인" >> "$report_file"
        fi
    done
    
    cat >> "$report_file" << EOF

## 연구 활용 방안

### 논문 작성 포인트
1. **실시간 공격-네트워크 상관관계 분석**
   - DVD 공격 이벤트와 FANET 네트워크 변화의 시간적 상관관계
   - 공격 유형별 네트워크 성능 영향도 분석

2. **Moving Target Defense 효과성 검증**
   - 공격 탐지 시간 및 대응 시간 측정
   - 네트워크 토폴로지 변화를 통한 공격 완화 효과

3. **드론 보안 위협 분류 체계**
   - 6개 주요 공격 카테고리별 위험도 평가
   - 실제 드론 운용 환경에서의 보안 요구사항 도출

### 추가 분석 도구
- **데이터 시각화**: \`python3 $BASE_DIR/visualization/create_plots.py\`
- **통계 분석**: \`python3 $BASE_DIR/analysis/statistical_analysis.py\`
- **네트워크 애니메이션**: NetAnim으로 시뮬레이션 결과 확인

## 결론
이 통합 테스트베드는 DVD 공격 시나리오와 NS-3 FANET 네트워크 시뮬레이션을 실시간으로 연동하여, 
드론 보안 연구를 위한 포괄적인 실험 환경을 제공합니다. 수집된 데이터는 Moving Target Defense 
효과성 검증 및 드론 보안 메커니즘 개발을 위한 귀중한 자료로 활용될 수 있습니다.

---
*보고서 생성 시간: $(date)*
*실험 ID: $(basename "$RESULTS_DIR")*
EOF

    log_info "✅ 종합 보고서 생성 완료: $report_file"
}

cleanup_all_services() {
    log_info "🧹 모든 서비스 정리 중..."
    
    # 저장된 PID로 서비스 중지
    for pid in "${SERVICE_PIDS[@]}"; do
        if kill -0 $pid 2>/dev/null; then
            log_info "서비스 중지 (PID: $pid)"
            kill $pid
            sleep 2
            if kill -0 $pid 2>/dev/null; then
                kill -9 $pid
            fi
        fi
    done
    
    # PID 파일들 정리
    local pid_files=(
        "/home/kali/MTD/MTD_full_testbed/pids/dvd_monitor_service.pid"
        "/home/kali/MTD/MTD_full_testbed/pids/dvd_attack_connector.pid"
        "/home/kali/MTD/MTD_full_testbed/pids/ns3_simulation.pid"
        "/home/kali/MTD/MTD_full_testbed/pids/mtd_services.pid"
    )
    
    for pid_file in "${pid_files[@]}"; do
        if [ -f "$pid_file" ]; then
            local pid=$(cat "$pid_file" 2>/dev/null || echo "")
            if [ -n "$pid" ] && kill -0 $pid 2>/dev/null; then
                log_info "잔여 프로세스 중지 (PID: $pid)"
                kill $pid 2>/dev/null || kill -9 $pid 2>/dev/null
            fi
            rm -f "$pid_file"
        fi
    done
    
    # 관련 프로세스 강제 정리
    pkill -f "dvd_monitor_service" 2>/dev/null || true
    pkill -f "dvd_attack_connector" 2>/dev/null || true
    pkill -f "dvd-fanet-integration" 2>/dev/null || true
    pkill -f "dvd_attacks" 2>/dev/null || true
    
    # 임시 파일 정리
    rm -f /tmp/dvd_ns3_attack_results.csv
    rm -f /tmp/*iocs.txt
    
    log_info "🧹 서비스 정리 완료"
}

print_final_summary() {
    echo -e "\n${CYAN}${BOLD}══════════════════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}${BOLD}                🎉 DVD-NS3 통합 테스트베드 실행 완료                   ${NC}"
    echo -e "${CYAN}${BOLD}══════════════════════════════════════════════════════════════════════${NC}"
    
    echo -e "${GREEN}📊 실험 결과 요약:${NC}"
    echo -e "   • FANET 노드 수: ${BOLD}$FANET_NODES${NC}개"
    echo -e "   • 시뮬레이션 시간: ${BOLD}$SIMULATION_TIME${NC}초"
    echo -e "   • 공격 시나리오: ${BOLD}$ATTACK_SCENARIOS${NC}"
    echo -e "   • 결과 디렉토리: ${BOLD}$RESULTS_DIR${NC}"
    
    echo -e "\n${YELLOW}📁 생성된 결과 파일:${NC}"
    if [ -d "$RESULTS_DIR" ]; then
        local file_count=$(find "$RESULTS_DIR" -type f | wc -l)
        local total_size=$(du -sh "$RESULTS_DIR" | cut -f1)
        echo -e "   • 총 파일 수: ${BOLD}$file_count${NC}개"
        echo -e "   • 총 크기: ${BOLD}$total_size${NC}"
        echo -e "   • 종합 보고서: ${BOLD}comprehensive_report.md${NC}"
    fi
    
    echo -e "\n${BLUE}🔬 논문 작성 활용:${NC}"
    echo -e "   1. ${BOLD}결과 분석${NC}: cd $RESULTS_DIR && python3 ../../analysis/analyze_results.py"
    echo -e "   2. ${BOLD}그래프 생성${NC}: python3 $BASE_DIR/visualization/create_plots.py"
    echo -e "   3. ${BOLD}통계 분석${NC}: python3 $BASE_DIR/analysis/statistical_analysis.py"
    echo -e "   4. ${BOLD}보고서 확인${NC}: cat $RESULTS_DIR/comprehensive_report.md"
    
    echo -e "\n${GREEN}✅ 모든 작업이 성공적으로 완료되었습니다!${NC}"
    echo -e "${GREEN}📝 연구 논문 작성에 활용하시기 바랍니다.${NC}\n"
}

# 신호 처리
cleanup() {
    echo -e "\n${YELLOW}[*] 긴급 정리 작업 시작...${NC}"
    cleanup_all_services
    exit 0
}

trap cleanup SIGINT SIGTERM

# 메인 실행 함수
main() {
    print_header
    
    # 명령행 파라미터 처리
    while [[ $# -gt 0 ]]; do
        case $1 in
            -n|--nodes)
                FANET_NODES="$2"
                shift 2
                ;;
            -t|--time)
                SIMULATION_TIME="$2"
                shift 2
                ;;
            -s|--scenarios)
                ATTACK_SCENARIOS="$2"
                shift 2
                ;;
            --no-dvd)
                DVD_ATTACKS_ENABLED=false
                shift
                ;;
            --no-ns3)
                NS3_SIMULATION_ENABLED=false
                shift
                ;;
            -h|--help)
                echo "사용법: $0 [옵션]"
                echo "옵션:"
                echo "  -n, --nodes N        FANET 노드 수 (기본값: 10)"
                echo "  -t, --time T         시뮬레이션 시간 초 (기본값: 600)"
                echo "  -s, --scenarios S    공격 시나리오 (기본값: reconnaissance,protocol_tampering,denial_of_service)"
                echo "  --no-dvd            DVD 공격 비활성화"
                echo "  --no-ns3            NS-3 시뮬레이션 비활성화"
                echo "  -h, --help          도움말 표시"
                exit 0
                ;;
            *)
                log_error "알 수 없는 옵션: $1"
                exit 1
                ;;
        esac
    done
    
    log_info "🚀 DVD-NS3 통합 테스트베드 시작..."
    
    # 1. 전제 조건 확인
    check_prerequisites
    
    # 2. DVD 서비스 시작
    if [ "$DVD_ATTACKS_ENABLED" = true ]; then
        start_dvd_services
        sleep 10
    fi
    
    # 3. NS-3 시뮬레이션 시작
    if [ "$NS3_SIMULATION_ENABLED" = true ]; then
        start_ns3_simulation
        sleep 15
    fi
    
    # 4. 공격 시나리오 실행
    if [ "$DVD_ATTACKS_ENABLED" = true ]; then
        execute_attack_scenarios &
        ATTACK_EXECUTOR_PID=$!
        SERVICE_PIDS+=($ATTACK_EXECUTOR_PID)
    fi
    
    # 5. 시스템 모니터링
    monitor_integration_status
    
    # 6. 공격 실행 완료 대기
    if [ "$DVD_ATTACKS_ENABLED" = true ] && [ -n "$ATTACK_EXECUTOR_PID" ]; then
        wait $ATTACK_EXECUTOR_PID
    fi
    
    # 7. 시뮬레이션 완료 대기 (추가 대기 시간)
    log_info "⏱️ 시뮬레이션 완료까지 대기..."
    sleep 60
    
    # 8. 결과 수집 및 보고서 생성
    collect_attack_results
    generate_comprehensive_report
    
    # 9. 서비스 정리
    cleanup_all_services
    
    # 10. 최종 요약
    print_final_summary
    
    log_info "🎉 DVD-NS3 통합 테스트베드 실행 완료!"
}

# 스크립트 실행
main "$@"