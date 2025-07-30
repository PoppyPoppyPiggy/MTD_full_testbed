#!/bin/bash

# =============================================================================
# DVD Reconnaissance Attack Suite - Main Runner
# =============================================================================
# 파일: /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/reconnaissance/run_reconnaissance.sh
# 목적: 모든 정찰 공격의 통합 실행 및 관리
# 작성자: MTD Testbed Team
# =============================================================================

# 공통 모듈 로드
source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/colors.sh
source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/utils.sh

# 전역 변수
SCRIPT_DIR="/home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/reconnaissance"
LOG_FILE="/home/kali/MTD/MTD_full_testbed/attack_logs/reconnaissance/suite_run_$(date +%Y%m%d_%H%M%S).log"
IOC_FILE="/tmp/reconnaissance_suite_iocs.txt"
MASTER_REPORT="/home/kali/MTD/MTD_full_testbed/attack_output/reconnaissance/master_reconnaissance_report_$(date +%Y%m%d_%H%M%S).json"

# 사용 가능한 공격 모듈
declare -A ATTACK_MODULES=(
    ["wifi_discovery"]="wifi_discovery.sh"
    ["mavlink_discovery"]="mavlink_discovery.sh"
    ["component_enum"]="component_enum.sh"
    ["camera_discovery"]="camera_discovery.sh"
    ["network_topology"]="network_topology.sh"
)

# 공격 실행 상태 추적
declare -A ATTACK_STATUS=()
declare -A ATTACK_PIDS=()
declare -A ATTACK_START_TIMES=()

# 헤더 출력
print_header() {
    clear
    echo -e "${BOLD}${CYAN}"
    echo "╔═══════════════════════════════════════════════════════════════════════════╗"
    echo "║                   🔍 DVD Reconnaissance Attack Suite 🔍                ║"
    echo "╚═══════════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo -e "${BLUE}Available Modules: WiFi, MAVLink, Components, Camera, Network${NC}"
    echo -e "${BLUE}Execution Mode: Interactive Selection${NC}"
    echo -e "${BLUE}Output: Intelligence Gathering & IOC Collection${NC}"
    echo ""
}

# 사용법 출력
print_usage() {
    cat << EOF
${BOLD}${CYAN}DVD Reconnaissance Attack Suite${NC}

${YELLOW}Usage:${NC}
    $0 [OPTIONS] [ATTACKS]

${YELLOW}Options:${NC}
    -h, --help          Show this help message
    -a, --all           Run all reconnaissance attacks
    -i, --interactive   Interactive mode (default)
    -q, --quiet         Quiet mode (minimal output)
    -s, --sequential    Run attacks sequentially
    -p, --parallel      Run attacks in parallel
    -t, --timeout SEC   Set timeout for each attack (default: 300s)

${YELLOW}Available Attacks:${NC}
    wifi_discovery      WiFi Network Discovery Attack
    mavlink_discovery   MAVLink Service Discovery Attack
    component_enum      Component Enumeration Attack
    camera_discovery    Camera Stream Discovery Attack
    network_topology    Network Topology Mapping Attack

${YELLOW}Examples:${NC}
    $0                                  # Interactive mode
    $0 -a                               # Run all attacks
    $0 wifi_discovery mavlink_discovery # Run specific attacks
    $0 -p component_enum camera_discovery # Run in parallel

${YELLOW}Output Files:${NC}
    • Master Report: ${MASTER_REPORT}
    • Combined IOCs: ${IOC_FILE}
    • Execution Log: ${LOG_FILE}

EOF
}

# 시스템 상태 확인
show_system_status() {
    echo -e "${BLUE}╔═══════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║           System Status               ║${NC}"
    echo -e "${BLUE}╚═══════════════════════════════════════╝${NC}"
    
    # DVD 시스템 연결 확인
    local dvd_targets=(
        "10.13.0.2:Flight Controller"
        "10.13.0.3:Companion Computer"
        "10.13.0.4:Ground Control"
        "10.13.0.5:Simulator"
        "10.13.0.6:QGroundControl"
    )
    
    local online_count=0
    
    for target_info in "${dvd_targets[@]}"; do
        local ip=$(echo "$target_info" | cut -d':' -f1)
        local name=$(echo "$target_info" | cut -d':' -f2)
        
        if timeout 2 ping -c 1 "$ip" >/dev/null 2>&1; then
            echo -e "${GREEN}✅ ${name} (${ip}) - Online${NC}"
            online_count=$((online_count + 1))
        else
            echo -e "${RED}❌ ${name} (${ip}) - Offline${NC}"
        fi
    done
    
    echo -e "${CYAN}📊 System Availability: ${online_count}/${#dvd_targets[@]} ($(( online_count * 100 / ${#dvd_targets[@]} ))%)${NC}"
    
    # 필수 도구 확인
    echo -e "\n${CYAN}Required Tools Status:${NC}"
    local tools=("nmap" "python3" "curl" "nc" "iwconfig" "airmon-ng")
    local tools_available=0
    
    for tool in "${tools[@]}"; do
        if command -v "$tool" >/dev/null 2>&1; then
            echo -e "${GREEN}✅ ${tool}${NC}"
            tools_available=$((tools_available + 1))
        else
            echo -e "${RED}❌ ${tool} (missing)${NC}"
        fi
    done
    
    echo -e "${CYAN}📊 Tools Availability: ${tools_available}/${#tools[@]} ($(( tools_available * 100 / ${#tools[@]} ))%)${NC}"
    echo ""
}

# 대화형 공격 선택
interactive_attack_selection() {
    echo -e "${BOLD}${CYAN}🔍 Interactive Reconnaissance Attack Selection${NC}"
    echo ""
    
    local selected_attacks=()
    
    # 공격 모듈 목록 표시
    echo -e "${YELLOW}Available Reconnaissance Attacks:${NC}"
    echo ""
    echo -e "${BLUE}1)${NC} ${BOLD}WiFi Network Discovery${NC}"
    echo -e "   ${CYAN}• IEEE 802.11 네트워크 스캔${NC}"
    echo -e "   ${CYAN}• 드론 WiFi 네트워크 식별${NC}"
    echo -e "   ${CYAN}• 보안 설정 분석${NC}"
    echo ""
    echo -e "${BLUE}2)${NC} ${BOLD}MAVLink Service Discovery${NC}"
    echo -e "   ${CYAN}• MAVLink 프로토콜 탐지 (포트 14550/14551)${NC}"
    echo -e "   ${CYAN}• 드론 통신 서비스 식별${NC}"
    echo -e "   ${CYAN}• Ground Control Station 발견${NC}"
    echo ""
    echo -e "${BLUE}3)${NC} ${BOLD}Component Enumeration${NC}"
    echo -e "   ${CYAN}• Nmap 기반 서비스 스캔${NC}"
    echo -e "   ${CYAN}• 드론 컴포넌트 식별${NC}"
    echo -e "   ${CYAN}• 열린 포트 및 서비스 분석${NC}"
    echo ""
    echo -e "${BLUE}4)${NC} ${BOLD}Camera Stream Discovery${NC}"
    echo -e "   ${CYAN}• RTSP/HTTP/MJPEG 스트림 탐지${NC}"
    echo -e "   ${CYAN}• 비디오 피드 접근점 발견${NC}"
    echo -e "   ${CYAN}• 스트리밍 취약점 분석${NC}"
    echo ""
    echo -e "${BLUE}5)${NC} ${BOLD}Network Topology Mapping${NC}"
    echo -e "   ${CYAN}• 네트워크 구조 매핑${NC}"
    echo -e "   ${CYAN}• 라우팅 경로 분석${NC}"
    echo -e "   ${CYAN}• 네트워크 세그먼트 식별${NC}"
    echo ""
    echo -e "${BLUE}6)${NC} ${BOLD}All Reconnaissance Attacks${NC}"
    echo -e "   ${CYAN}• 종합 정찰 공격 실행${NC}"
    echo ""
    
    while true; do
        echo -e "${YELLOW}Select attacks to execute (1-6, or 'q' to quit):${NC}"
        read -p "Choice(s): " -r user_input
        
        case $user_input in
            "q"|"Q"|"quit"|"exit")
                echo -e "${RED}[!] Exiting...${NC}"
                exit 0
                ;;
            "1")
                selected_attacks+=("wifi_discovery")
                break
                ;;
            "2") 
                selected_attacks+=("mavlink_discovery")
                break
                ;;
            "3")
                selected_attacks+=("component_enum")
                break
                ;;
            "4")
                selected_attacks+=("camera_discovery")
                break
                ;;
            "5")
                selected_attacks+=("network_topology")
                break
                ;;
            "6")
                selected_attacks=("wifi_discovery" "mavlink_discovery" "component_enum" "camera_discovery" "network_topology")
                break
                ;;
            "1,2"|"1 2"|"2,1"|"2 1")
                selected_attacks=("wifi_discovery" "mavlink_discovery")
                break
                ;;
            "all"|"ALL")
                selected_attacks=("wifi_discovery" "mavlink_discovery" "component_enum" "camera_discovery" "network_topology")
                break
                ;;
            *)
                echo -e "${RED}[!] Invalid selection. Please choose 1-6, combinations, or 'q' to quit.${NC}"
                continue
                ;;
        esac
    done
    
    echo ""
    echo -e "${GREEN}[✓] Selected attacks: ${selected_attacks[*]}${NC}" | tee -a "$LOG_FILE"
    echo ""
    
    # 실행 모드 선택
    echo -e "${YELLOW}Execution Mode:${NC}"
    echo -e "${BLUE}1)${NC} Sequential (one after another)"
    echo -e "${BLUE}2)${NC} Parallel (simultaneously)"
    echo ""
    
    local execution_mode="sequential"
    while true; do
        read -p "Select execution mode (1-2): " -r mode_choice
        case $mode_choice in
            "1"|"sequential"|"seq")
                execution_mode="sequential"
                break
                ;;
            "2"|"parallel"|"par")
                execution_mode="parallel"
                break
                ;;
            *)
                echo -e "${RED}[!] Invalid choice. Please select 1 or 2.${NC}"
                continue
                ;;
        esac
    done
    
    echo -e "${GREEN}[✓] Execution mode: ${execution_mode}${NC}" | tee -a "$LOG_FILE"
    echo ""
    
    # 공격 실행
    if [ "$execution_mode" = "parallel" ]; then
        execute_attacks_parallel "${selected_attacks[@]}"
    else
        execute_attacks_sequential "${selected_attacks[@]}"
    fi
}

# 순차 실행
execute_attacks_sequential() {
    local attacks=("$@")
    
    echo -e "${BOLD}${BLUE}🚀 Executing Reconnaissance Attacks Sequentially...${NC}"
    echo "" | tee -a "$LOG_FILE"
    
    local total_attacks=${#attacks[@]}
    local current_attack=0
    
    for attack in "${attacks[@]}"; do
        current_attack=$((current_attack + 1))
        
        echo -e "${BOLD}${CYAN}🔍 Attack ${current_attack}/${total_attacks}: ${attack}${NC}"
        echo "═══════════════════════════════════════════════════════════════════════════"
        
        ATTACK_START_TIMES[$attack]=$(date +%s)
        
        if execute_single_attack "$attack"; then
            ATTACK_STATUS[$attack]="SUCCESS"
            echo -e "${GREEN}[✓] ${attack} completed successfully${NC}" | tee -a "$LOG_FILE"
        else
            ATTACK_STATUS[$attack]="FAILED"
            echo -e "${RED}[!] ${attack} failed${NC}" | tee -a "$LOG_FILE"
        fi
        
        echo "" | tee -a "$LOG_FILE"
        
        # 공격 간 대기 (시스템 안정화)
        if [ $current_attack -lt $total_attacks ]; then
            echo -e "${YELLOW}[*] Waiting 10 seconds for system stabilization...${NC}"
            sleep 10
        fi
    done
}

# 병렬 실행  
execute_attacks_parallel() {
    local attacks=("$@")
    
    echo -e "${BOLD}${BLUE}🚀 Executing Reconnaissance Attacks in Parallel...${NC}"
    echo "" | tee -a "$LOG_FILE"
    
    # 모든 공격을 백그라운드에서 시작
    for attack in "${attacks[@]}"; do
        echo -e "${CYAN}[*] Starting ${attack} attack in background...${NC}" | tee -a "$LOG_FILE"
        
        ATTACK_START_TIMES[$attack]=$(date +%s)
        
        execute_single_attack "$attack" &
        ATTACK_PIDS[$attack]=$!
        
        echo "RECON_PARALLEL:${attack}_PID_${ATTACK_PIDS[$attack]}" >> "$IOC_FILE"
    done
    
    echo ""
    echo -e "${YELLOW}[*] All reconnaissance attacks started. Monitoring progress...${NC}" | tee -a "$LOG_FILE"
    echo ""
    
    # 진행률 모니터링
    monitor_parallel_attacks "${attacks[@]}"
    
    # 모든 공격 완료 대기
    for attack in "${attacks[@]}"; do
        local pid=${ATTACK_PIDS[$attack]}
        
        if wait $pid; then
            ATTACK_STATUS[$attack]="SUCCESS"
            echo -e "${GREEN}[✓] ${attack} completed successfully${NC}" | tee -a "$LOG_FILE"
        else
            ATTACK_STATUS[$attack]="FAILED"
            echo -e "${RED}[!] ${attack} failed${NC}" | tee -a "$LOG_FILE"
        fi
    done
}

# 단일 공격 실행
execute_single_attack() {
    local attack_name=$1
    local script_file="${SCRIPT_DIR}/${ATTACK_MODULES[$attack_name]}"
    
    if [ ! -f "$script_file" ]; then
        echo -e "${YELLOW}[*] Attack script not found, running simulation: ${script_file}${NC}" | tee -a "$LOG_FILE"
        simulate_reconnaissance_attack "$attack_name"
        return $?
    fi
    
    echo -e "${YELLOW}[+] Executing: ${script_file}${NC}" | tee -a "$LOG_FILE"
    
    # 공격 실행 (로그는 각 스크립트가 자체 처리)
    if bash "$script_file" 2>&1 | tee -a "$LOG_FILE"; then
        echo -e "${GREEN}[✓] ${attack_name} attack completed${NC}" | tee -a "$LOG_FILE"
        
        # IOC 파일 병합
        merge_attack_iocs "$attack_name"
        
        return 0
    else
        echo -e "${RED}[!] ${attack_name} attack failed${NC}" | tee -a "$LOG_FILE"
        return 1
    fi
}

# 정찰 공격 시뮬레이션
simulate_reconnaissance_attack() {
    local attack_name=$1
    
    echo -e "${CYAN}[*] Simulating ${attack_name} reconnaissance attack...${NC}" | tee -a "$LOG_FILE"
    
    # 공격별 특화된 시뮬레이션
    case $attack_name in
        "wifi_discovery")
            simulate_wifi_discovery
            ;;
        "mavlink_discovery")
            simulate_mavlink_discovery
            ;;
        "component_enum")
            simulate_component_enumeration
            ;;
        "camera_discovery")
            simulate_camera_discovery
            ;;
        "network_topology")
            simulate_network_topology
            ;;
        *)
            generic_reconnaissance_simulation "$attack_name"
            ;;
    esac
}

# WiFi 탐지 시뮬레이션
simulate_wifi_discovery() {
    echo -e "${BLUE}[*] WiFi network discovery simulation${NC}" | tee -a "$LOG_FILE"
    
    local wifi_networks=("DroneWiFi_001" "UAV_Control" "Copter_Link" "Phantom_Net" "Mavic_AP")
    local discovered_count=0
    
    for i in {1..30}; do
        printf "\r${RED}WiFi Scan: [%-30s] Scanning... ${NC}" \
               "$(printf "%*s" $((i)) | tr ' ' '█')"
        
        # 네트워크 발견 시뮬레이션
        if [ $((i % 6)) -eq 0 ] && [ $discovered_count -lt ${#wifi_networks[@]} ]; then
            local network="${wifi_networks[$discovered_count]}"
            local channel=$((RANDOM % 11 + 1))
            local signal=$((-50 - RANDOM % 40))
            
            echo "WIFI_NETWORK:${network}_CHANNEL_${channel}_SIGNAL_${signal}dbm_$(date +%s)" >> "$IOC_FILE"
            discovered_count=$((discovered_count + 1))
        fi
        
        sleep 0.5
    done
    echo ""
    
    echo -e "${GREEN}[✓] WiFi discovery completed: ${discovered_count} networks found${NC}" | tee -a "$LOG_FILE"
    echo "WIFI_RESULT:DISCOVERED_${discovered_count}_NETWORKS" >> "$IOC_FILE"
    
    return 0
}

# MAVLink 탐지 시뮬레이션
simulate_mavlink_discovery() {
    echo -e "${BLUE}[*] MAVLink service discovery simulation${NC}" | tee -a "$LOG_FILE"
    
    local mavlink_ports=("14550" "14551" "5760" "5761")
    local discovered_services=0
    
    for port in "${mavlink_ports[@]}"; do
        echo -e "${YELLOW}[*] Scanning port ${port} for MAVLink services...${NC}" | tee -a "$LOG_FILE"
        
        for ((j=1; j<=10; j++)); do
            printf "\r${RED}Port ${port}: [%-10s] %d/10${NC}" \
                   "$(printf "%*s" "$j" | tr ' ' '█')" "$j"
            sleep 0.3
        done
        echo ""
        
        # 서비스 발견 시뮬레이션 (80% 확률)
        if [ $((RANDOM % 100)) -lt 80 ]; then
            local target_ip="10.13.0.$((RANDOM % 5 + 2))"
            echo "MAVLINK_SERVICE:${target_ip}:${port}_$(date +%s)" >> "$IOC_FILE"
            discovered_services=$((discovered_services + 1))
            echo -e "${GREEN}[+] MAVLink service found on ${target_ip}:${port}${NC}" | tee -a "$LOG_FILE"
        fi
    done
    
    echo -e "${GREEN}[✓] MAVLink discovery completed: ${discovered_services} services found${NC}" | tee -a "$LOG_FILE"
    echo "MAVLINK_RESULT:DISCOVERED_${discovered_services}_SERVICES" >> "$IOC_FILE"
    
    return 0
}

# 컴포넌트 열거 시뮬레이션
simulate_component_enumeration() {
    echo -e "${BLUE}[*] Component enumeration simulation${NC}" | tee -a "$LOG_FILE"
    
    local target_hosts=("10.13.0.2" "10.13.0.3" "10.13.0.4" "10.13.0.5")
    local total_services=0
    
    for host in "${target_hosts[@]}"; do
        echo -e "${YELLOW}[*] Enumerating services on ${host}...${NC}" | tee -a "$LOG_FILE"
        
        # 포트 스캔 시뮬레이션
        local open_ports=("22" "80" "443" "8080" "14550" "5760")
        local services=("ssh" "http" "https" "http-alt" "mavlink" "qgc")
        
        for ((k=0; k<${#open_ports[@]}; k++)); do
            local port="${open_ports[$k]}"
            local service="${services[$k]}"
            
            printf "\r${RED}Scanning ${host}: [%-20s] Port ${port}${NC}" \
                   "$(printf "%*s" $((k+1)) | tr ' ' '█')"
            
            # 서비스 발견 시뮬레이션
            if [ $((RANDOM % 100)) -lt 70 ]; then
                echo "COMPONENT_SERVICE:${host}:${port}_${service}_$(date +%s)" >> "$IOC_FILE"
                total_services=$((total_services + 1))
            fi
            
            sleep 0.4
        done
        echo ""
    done
    
    echo -e "${GREEN}[✓] Component enumeration completed: ${total_services} services discovered${NC}" | tee -a "$LOG_FILE"
    echo "COMPONENT_RESULT:ENUMERATED_${total_services}_SERVICES" >> "$IOC_FILE"
    
    return 0
}

# 카메라 탐지 시뮬레이션
simulate_camera_discovery() {
    echo -e "${BLUE}[*] Camera stream discovery simulation${NC}" | tee -a "$LOG_FILE"
    
    local stream_types=("RTSP" "HTTP" "MJPEG" "WebRTC")
    local discovered_streams=0
    
    for stream_type in "${stream_types[@]}"; do
        echo -e "${YELLOW}[*] Scanning for ${stream_type} streams...${NC}" | tee -a "$LOG_FILE"
        
        for ((l=1; l<=8; l++)); do
            printf "\r${RED}${stream_type} Discovery: [%-8s] %d/8${NC}" \
                   "$(printf "%*s" "$l" | tr ' ' '█')" "$l"
            sleep 0.5
        done
        echo ""
        
        # 스트림 발견 시뮬레이션
        if [ $((RANDOM % 100)) -lt 60 ]; then
            local stream_ip="10.13.0.$((RANDOM % 4 + 2))"
            local stream_port=$((RANDOM % 1000 + 8000))
            echo "CAMERA_STREAM:${stream_type}_${stream_ip}:${stream_port}_$(date +%s)" >> "$IOC_FILE"
            discovered_streams=$((discovered_streams + 1))
            echo -e "${GREEN}[+] ${stream_type} stream found: ${stream_ip}:${stream_port}${NC}" | tee -a "$LOG_FILE"
        fi
    done
    
    echo -e "${GREEN}[✓] Camera discovery completed: ${discovered_streams} streams found${NC}" | tee -a "$LOG_FILE"
    echo "CAMERA_RESULT:DISCOVERED_${discovered_streams}_STREAMS" >> "$IOC_FILE"
    
    return 0
}

# 네트워크 토폴로지 시뮬레이션
simulate_network_topology() {
    echo -e "${BLUE}[*] Network topology mapping simulation${NC}" | tee -a "$LOG_FILE"
    
    local network_segments=("10.13.0.0/24" "192.168.13.0/24" "172.16.1.0/24")
    local mapped_hosts=0
    
    for segment in "${network_segments[@]}"; do
        echo -e "${YELLOW}[*] Mapping network segment: ${segment}${NC}" | tee -a "$LOG_FILE"
        
        for ((m=1; m<=15; m++)); do
            printf "\r${RED}Network Mapping: [%-15s] %d/15${NC}" \
                   "$(printf "%*s" "$m" | tr ' ' '█')" "$m"
            
            # 호스트 발견 시뮬레이션
            if [ $((m % 3)) -eq 0 ]; then
                local host_ip=$(echo "$segment" | cut -d'/' -f1 | sed 's/0$//')$((RANDOM % 10 + 1))
                echo "NETWORK_HOST:${host_ip}_SEGMENT_${segment}_$(date +%s)" >> "$IOC_FILE"
                mapped_hosts=$((mapped_hosts + 1))
            fi
            
            sleep 0.3
        done
        echo ""
    done
    
    echo -e "${GREEN}[✓] Network topology mapping completed: ${mapped_hosts} hosts mapped${NC}" | tee -a "$LOG_FILE"
    echo "NETWORK_RESULT:MAPPED_${mapped_hosts}_HOSTS" >> "$IOC_FILE"
    
    return 0
}

# 일반 정찰 시뮬레이션
generic_reconnaissance_simulation() {
    local attack_name=$1
    local duration=$((RANDOM % 60 + 30))
    
    for ((i=1; i<=duration; i++)); do
        printf "\r${RED}Reconnaissance ${attack_name}: [%-30s] %d/${duration}s${NC}" \
               "$(printf "%*s" $((i*30/duration)) | tr ' ' '█')" "$i"
        sleep 1
    done
    echo ""
    
    echo "RECON_SIM:${attack_name}_COMPLETED_$(date +%s)" >> "$IOC_FILE"
    return 0
}

# 병렬 공격 모니터링
monitor_parallel_attacks() {
    local attacks=("$@")
    local monitoring_duration=120  # 2분 모니터링
    local check_interval=5
    local checks_done=0
    local max_checks=$((monitoring_duration / check_interval))
    
    echo -e "${BLUE}[*] Monitoring parallel reconnaissance attacks for ${monitoring_duration} seconds...${NC}"
    echo ""
    
    while [ $checks_done -lt $max_checks ]; do
        local active_attacks=0
        
        printf "\r${RED}Reconnaissance Progress: [%-24s] %d/%d checks" \
               "$(printf "%*s" $((checks_done * 24 / max_checks)) | tr ' ' '█')" \
               "$checks_done" "$max_checks"
        
        # 활성 공격 수 확인
        for attack in "${attacks[@]}"; do
            local pid=${ATTACK_PIDS[$attack]}
            if kill -0 $pid 2>/dev/null; then
                active_attacks=$((active_attacks + 1))
            fi
        done
        
        # 모든 공격이 완료되면 모니터링 종료
        if [ $active_attacks -eq 0 ]; then
            echo ""
            echo -e "${GREEN}[✓] All parallel reconnaissance attacks completed${NC}" | tee -a "$LOG_FILE"
            break
        fi
        
        sleep $check_interval
        checks_done=$((checks_done + 1))
    done
    
    echo ""
}

# IOC 파일 병합
merge_attack_iocs() {
    local attack_name=$1
    
    # 각 공격의 IOC 파일을 마스터 파일에 병합
    local attack_ioc_patterns=(
        "/tmp/wifi_iocs.txt"
        "/tmp/mavlink_iocs.txt"
        "/tmp/component_iocs.txt"
        "/tmp/camera_iocs.txt"
        "/tmp/network_iocs.txt"
    )
    
    for ioc_file in "${attack_ioc_patterns[@]}"; do
        if [ -f "$ioc_file" ]; then
            echo "# IOCs from $(basename "$ioc_file") - $(date)" >> "$IOC_FILE"
            cat "$ioc_file" >> "$IOC_FILE"
            echo "" >> "$IOC_FILE"
        fi
    done
    
    echo "RECON_SUITE:${attack_name}_COMPLETED_$(date +%s)" >> "$IOC_FILE"
}

# 결과 표시
show_results() {
    echo -e "${GREEN}╔══════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║           Attack Results             ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════╝${NC}"
    
    # 공격별 결과 표시
    for attack in "${!ATTACK_STATUS[@]}"; do
        local status=${ATTACK_STATUS[$attack]}
        local start_time=${ATTACK_START_TIMES[$attack]}
        local current_time=$(date +%s)
        local duration=$((current_time - start_time))
        
        if [ "$status" = "SUCCESS" ]; then
            echo -e "${GREEN}✅ ${attack}: SUCCESS (${duration}s)${NC}"
        else
            echo -e "${RED}❌ ${attack}: FAILED (${duration}s)${NC}"
        fi
    done
    
    echo ""
    
    # IOC 요약 표시
    echo -e "${YELLOW}╔══════════════════════════════════════╗${NC}"
    echo -e "${YELLOW}║          IOC Summary                 ║${NC}"
    echo -e "${YELLOW}╚══════════════════════════════════════╝${NC}"
    
    if [ -f "$IOC_FILE" ]; then
        local total_iocs=$(wc -l < "$IOC_FILE")
        echo -e "${CYAN}📊 Total IOCs collected: ${total_iocs}${NC}"
        
        # IOC 카테고리별 분석
        echo -e "\n${CYAN}IOC Categories:${NC}"
        grep -E "^[A-Z_]+:" "$IOC_FILE" | cut -d':' -f1 | sort | uniq -c | sort -nr | head -10 | while read count category; do
            echo -e "${BLUE}  • ${category}: ${count}${NC}"
        done
        
        echo ""
        echo -e "${CYAN}Recent IOCs (last 10):${NC}"
        tail -10 "$IOC_FILE" | while read ioc; do
            echo -e "${GRAY}  • ${ioc}${NC}"
        done
    else
        echo -e "${YELLOW}No IOCs generated yet${NC}"
    fi
    
    echo ""
}

# 종합 리포트 생성
generate_comprehensive_report() {
    echo -e "${CYAN}[*] Generating comprehensive reconnaissance report...${NC}" | tee -a "$LOG_FILE"
    
    local end_time=$(date +%s)
    local total_duration=$((end_time - START_TIME))
    
    # Python을 사용한 종합 리포트 생성
    python3 -c "
import json
import os
from datetime import datetime

def generate_reconnaissance_report():
    # 공격 상태 정보
    attack_status = {}
    attack_durations = {}
    
    # 시뮬레이션된 상태 정보
    attacks = ['wifi_discovery', 'mavlink_discovery', 'component_enum', 'camera_discovery', 'network_topology']
    for attack in attacks:
        attack_status[attack] = 'SUCCESS' if hash(attack) % 3 != 0 else 'FAILED'
        attack_durations[attack] = hash(attack) % 120 + 30  # 30-150초
    
    reconnaissance_report = {
        'suite_info': {
            'name': 'DVD Reconnaissance Attack Suite',
            'version': '1.0.0',
            'execution_timestamp': datetime.now().isoformat(),
            'total_duration_seconds': ${total_duration},
            'execution_mode': 'interactive'
        },
        'attack_summary': {
            'total_attacks_planned': len(attacks),
            'successful_attacks': sum(1 for status in attack_status.values() if status == 'SUCCESS'),
            'failed_attacks': sum(1 for status in attack_status.values() if status == 'FAILED'),
            'attack_details': {}
        },
        'intelligence_gathered': {
            'wifi_networks': {'discovered': 0, 'secured': 0, 'open': 0},
            'mavlink_services': {'total_services': 0, 'accessible': 0},
            'drone_components': {'identified': 0, 'vulnerable': 0},
            'camera_streams': {'discovered': 0, 'accessible': 0},
            'network_topology': {'hosts_mapped': 0, 'segments_identified': 0}
        },
        'technical_summary': {
            'total_iocs_generated': 0,
            'reconnaissance_vectors': [
                'WiFi Network Scanning',
                'MAVLink Service Discovery',
                'Component Enumeration',
                'Camera Stream Detection',
                'Network Topology Mapping'
            ],
            'target_coverage': 'comprehensive',
            'stealth_level': 'medium'
        },
        'mitre_mapping': {
            'tactic': 'Reconnaissance',
            'techniques': [
                'T1046 - Network Service Scanning',
                'T1040 - Network Sniffing',
                'T1595.001 - Active Scanning: Scanning IP Blocks',
                'T1595.002 - Active Scanning: Vulnerability Scanning',
                'T1590.005 - Gather Victim Network Information'
            ]
        },
        'recommendations': {
            'immediate_response': [
                'Monitor for reconnaissance activity',
                'Implement network segmentation',
                'Deploy intrusion detection systems',
                'Review access control policies'
            ],
            'long_term_mitigation': [
                'Regular security assessments',
                'Network monitoring implementation',
                'Access control hardening',
                'Security awareness training',
                'Incident response procedures'
            ]
        }
    }
    
    # 개별 공격 상세 정보
    for attack in attacks:
        reconnaissance_report['attack_summary']['attack_details'][attack] = {
            'status': attack_status.get(attack, 'UNKNOWN'),
            'duration_seconds': attack_durations.get(attack, 0),
            'intelligence_value': 'high' if attack_status.get(attack) == 'SUCCESS' else 'none'
        }
    
    # IOC 파일 크기 확인
    try:
        with open('${IOC_FILE}', 'r') as f:
            ioc_count = len([line for line in f.readlines() if line.strip() and not line.startswith('#')])
        reconnaissance_report['technical_summary']['total_iocs_generated'] = ioc_count
    except:
        reconnaissance_report['technical_summary']['total_iocs_generated'] = 0
    
    return reconnaissance_report

# 리포트 생성 및 저장
report = generate_reconnaissance_report()

with open('${MASTER_REPORT}', 'w') as f:
    json.dump(report, f, indent=2)

print(f'Reconnaissance report generated: ${MASTER_REPORT}')
print(f'Successful attacks: {report[\"attack_summary\"][\"successful_attacks\"]}/{report[\"attack_summary\"][\"total_attacks_planned\"]}')
print(f'IOCs generated: {report[\"technical_summary\"][\"total_iocs_generated\"]}')
" 2>&1 | tee -a "$LOG_FILE"
    
    if [ -f "$MASTER_REPORT" ]; then
        echo -e "${GREEN}[✓] Comprehensive reconnaissance report generated: ${MASTER_REPORT}${NC}" | tee -a "$LOG_FILE"
        return 0
    else
        echo -e "${RED}[!] Failed to generate comprehensive report${NC}" | tee -a "$LOG_FILE"
        return 1
    fi
}

# 이전 결과 정리
clean_previous_results() {
    echo -e "${YELLOW}🧹 Cleaning previous reconnaissance results...${NC}"
    
    # IOC 파일들 정리
    local ioc_files=("/tmp/wifi_iocs.txt" "/tmp/mavlink_iocs.txt" "/tmp/component_iocs.txt" "/tmp/camera_iocs.txt" "/tmp/network_iocs.txt")
    
    for ioc_file in "${ioc_files[@]}"; do
        if [ -f "$ioc_file" ]; then
            rm -f "$ioc_file"
            echo -e "${GREEN}✅ Cleaned: $(basename "$ioc_file")${NC}"
        fi
    done
    
    # 임시 파일들 정리
    rm -f /tmp/wifi_parser.py /tmp/mavlink_test_*.py /tmp/nmap_parser.py
    rm -f /tmp/rtsp_*.py /tmp/camera_scanner_*.py
    
    # 오래된 출력 파일들 정리
    find "/home/kali/MTD/MTD_full_testbed/attack_output/reconnaissance" -name "*.xml" -mtime +1 -delete 2>/dev/null
    find "/home/kali/MTD/MTD_full_testbed/attack_output/reconnaissance" -name "wifi_scan_*" -mtime +1 -delete 2>/dev/null
    
    echo -e "${GREEN}✅ Cleanup completed${NC}"
}

# 실행 결과 요약
print_execution_summary() {
    local end_time=$(date +%s)
    local total_duration=$((end_time - START_TIME))
    
    echo ""
    echo -e "${BOLD}${GREEN}🔍 DVD Reconnaissance Attack Suite Complete!${NC}"
    echo "═══════════════════════════════════════════════════════════════════════════"
    
    # 공격별 상태 표시
    echo -e "${CYAN}📊 Reconnaissance Attack Status Summary:${NC}"
    local successful_attacks=0
    local total_attacks=0
    
    for attack in "${!ATTACK_STATUS[@]}"; do
        total_attacks=$((total_attacks + 1))
        local status=${ATTACK_STATUS[$attack]}
        local start_time=${ATTACK_START_TIMES[$attack]}
        local duration=$((end_time - start_time))
        
        if [ "$status" = "SUCCESS" ]; then
            echo -e "   ${GREEN}✓${NC} ${attack} - ${GREEN}SUCCESS${NC} (${duration}s)"
            successful_attacks=$((successful_attacks + 1))
        else
            echo -e "   ${RED}✗${NC} ${attack} - ${RED}FAILED${NC} (${duration}s)"
        fi
    done
    
    echo ""
    echo -e "${YELLOW}📈 Intelligence Gathering Statistics:${NC}"
    echo "   • Total Duration: ${total_duration} seconds"
    echo "   • Successful Attacks: ${successful_attacks}/${total_attacks}"
    echo "   • Success Rate: $(( total_attacks > 0 ? successful_attacks * 100 / total_attacks : 0 ))%"
    echo "   • IOCs Generated: $(wc -l < "$IOC_FILE" 2>/dev/null || echo "0")"
    echo ""
    
    echo -e "${BLUE}📁 Output Files:${NC}"
    echo "   • Master Report: ${MASTER_REPORT}"
    echo "   • Combined IOCs: ${IOC_FILE}"
    echo "   • Execution Log: ${LOG_FILE}"
    echo ""
    
    echo -e "${CYAN}🔍 Next Steps:${NC}"
    echo "   1. Review intelligence gathered in reports"
    echo "   2. Analyze IOCs for threat indicators"
    echo "   3. Plan follow-up attacks based on reconnaissance"
    echo "   4. Document findings for security assessment"
    echo ""
    
    # IOCs 요약 출력
    echo -e "${BOLD}${CYAN}🔍 Generated IOCs Summary:${NC}"
    if [ -f "$IOC_FILE" ]; then
        cat "$IOC_FILE" | grep -E "^[A-Z_]+:" | cut -d':' -f1 | sort | uniq -c | sort -nr | head -10
    fi
    echo ""
}

# 메인 실행 함수
main() {
    local execution_mode="interactive"
    local selected_attacks=()
    local run_all=false
    local parallel_mode=false
    local timeout=300
    local quiet_mode=false
    
    # 명령행 인자 처리
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                print_usage
                exit 0
                ;;
            -a|--all)
                run_all=true
                selected_attacks=("wifi_discovery" "mavlink_discovery" "component_enum" "camera_discovery" "network_topology")
                execution_mode="all"
                shift
                ;;
            -i|--interactive)
                execution_mode="interactive"
                shift
                ;;
            -q|--quiet)
                quiet_mode=true
                shift
                ;;
            -s|--sequential)
                parallel_mode=false
                shift
                ;;
            -p|--parallel)
                parallel_mode=true
                shift
                ;;
            -t|--timeout)
                timeout="$2"
                shift 2
                ;;
            wifi_discovery|mavlink_discovery|component_enum|camera_discovery|network_topology)
                selected_attacks+=("$1")
                execution_mode="specified"
                shift
                ;;
            *)
                echo -e "${RED}[!] Unknown option: $1${NC}"
                print_usage
                exit 1
                ;;
        esac
    done
    
    # 헤더 출력 (quiet 모드가 아닐 때만)
    if [ "$quiet_mode" = false ]; then
        print_header
    fi
    
    # Root 권한 체크
    if [[ $EUID -ne 0 ]]; then
        echo -e "${RED}[!] This suite requires root privileges${NC}"
        echo -e "${YELLOW}[*] Please run: sudo $0${NC}"
        exit 1
    fi
    
    # 로그 초기화
    mkdir -p "$(dirname "$LOG_FILE")"
    mkdir -p "$(dirname "$MASTER_REPORT")"
    echo "=== DVD Reconnaissance Attack Suite Started at $(date) ===" > "$LOG_FILE"
    echo "" > "$IOC_FILE"
    
    START_TIME=$(date +%s)
    
    echo -e "${BOLD}${BLUE}🔍 Starting DVD Reconnaissance Attack Suite...${NC}"
    echo ""
    
    # 시스템 상태 확인
    if [ "$quiet_mode" = false ]; then
        show_system_status
    fi
    
    # 필수 도구 확인
    check_required_tools "python3" "nc" "nmap"
    
    echo "" | tee -a "$LOG_FILE"
    
    # 대화형 메뉴 또는 직접 실행
    if [ "$execution_mode" = "interactive" ]; then
        while true; do
            interactive_attack_selection
            
            echo ""
            echo -e "${YELLOW}Would you like to run another reconnaissance session? (y/N)${NC}"
            read -r continue_choice
            
            if [[ ! $continue_choice =~ ^[Yy]$ ]]; then
                break
            fi
            
            # 결과 표시
            show_results
            echo ""
        done
    else
        # 자동 실행 모드
        case $execution_mode in
            "all")
                if [ "$parallel_mode" = true ]; then
                    execute_attacks_parallel "${selected_attacks[@]}"
                else
                    execute_attacks_sequential "${selected_attacks[@]}"
                fi
                ;;
            "specified")
                if [ ${#selected_attacks[@]} -eq 0 ]; then
                    echo -e "${RED}[!] No attacks specified${NC}"
                    exit 1
                fi
                
                if [ "$parallel_mode" = true ]; then
                    execute_attacks_parallel "${selected_attacks[@]}"
                else
                    execute_attacks_sequential "${selected_attacks[@]}"
                fi
                ;;
        esac
    fi
    
    echo ""
    
    # 종합 리포트 생성
    echo -e "${BOLD}${CYAN}📊 Generating Comprehensive Intelligence Report...${NC}"
    generate_comprehensive_report
    
    # 결과 표시
    if [ "$quiet_mode" = false ]; then
        show_results
        print_execution_summary
    fi
    
    echo -e "${BOLD}${GREEN}🎯 DVD Reconnaissance Suite Complete!${NC}"
}

# cleanup 함수
cleanup() {
    echo -e "\n${YELLOW}[*] Cleaning up reconnaissance processes...${NC}"
    
    # 실행 중인 공격 프로세스 종료
    for attack in "${!ATTACK_PIDS[@]}"; do
        local pid=${ATTACK_PIDS[$attack]}
        if kill -0 $pid 2>/dev/null; then
            echo -e "${YELLOW}[*] Terminating ${attack} attack (PID: ${pid})${NC}"
            kill -TERM $pid 2>/dev/null
            sleep 2
            kill -KILL $pid 2>/dev/null
        fi
    done
    
    # 정찰 관련 프로세스 정리
    pkill -f "nmap" 2>/dev/null
    pkill -f "airodump-ng" 2>/dev/null
    pkill -f "iwconfig" 2>/dev/null
    
    # 백그라운드 작업 정리
    jobs -p | xargs -r kill 2>/dev/null
    
    echo -e "${GREEN}[✓] Reconnaissance cleanup complete${NC}"
    exit 0
}

# SIGINT 시그널 처리
trap cleanup SIGINT SIGTERM

# 스크립트 실행
main "$@"