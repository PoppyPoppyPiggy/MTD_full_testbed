#!/bin/bash
# drone_discovery.sh - Drone Network Discovery Attack Tool
# Path: /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/reconnaissance/drone_discovery.sh

source "$(dirname "$0")/../common/colors.sh"
source "$(dirname "$0")/../common/utils.sh"

ATTACK_NAME="Drone Network Discovery" 
LOG_FILE="$(get_log_dir)/drone_discovery.log"
TARGET_NETWORK="192.168.13.0/24"
DOCKER_NETWORK="10.13.0.0/24"
MAVLINK_PORTS=(14550 14551 14552 5760 5762 5763)

print_banner() {
    echo -e "${CYAN}"
    echo "╔═══════════════════════════════════════╗"
    echo "║    Drone Network Discovery Attack     ║"
    echo "╚═══════════════════════════════════════╝"
    echo -e "${NC}"
}

check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # 필수 도구 확인
    local required_tools=("nmap" "aircrack-ng" "airodump-ng")
    for tool in "${required_tools[@]}"; do
        if ! command -v "$tool" &> /dev/null; then
            log_error "$tool is not installed"
            exit 1
        fi
    done
    
    # 네트워크 인터페이스 확인
    if ! ip addr show | grep -q "10.13.0"; then
        log_warning "Docker bridge network not detected"
    fi
    
    log_success "Prerequisites check completed"
}

scan_wifi_networks() {
    log_info "Starting WiFi network scan..."
    
    # 무선 인터페이스 확인
    local wifi_interface=$(iwconfig 2>/dev/null | awk '/IEEE 802.11/ {print $1; exit}')
    
    if [[ -z "$wifi_interface" ]]; then
        log_warning "No wireless interface found, skipping WiFi scan"
        return 1
    fi
    
    log_info "Using interface: $wifi_interface"
    
    # 모니터 모드 활성화 시도
    if ! iwconfig "$wifi_interface" mode monitor 2>/dev/null; then
        log_warning "Failed to enable monitor mode"
    fi
    
    # WiFi 네트워크 스캔
    local scan_file="/tmp/wifi_scan_$(date +%s).txt"
    
    echo -e "${YELLOW}[*] Scanning for drone WiFi networks...${NC}"
    airodump-ng --write-interval 1 -w /tmp/drone_scan "$wifi_interface" &
    local airodump_pid=$!
    
    sleep 10
    kill $airodump_pid 2>/dev/null
    
    # 결과 파싱
    if [[ -f "/tmp/drone_scan-01.csv" ]]; then
        grep -i "drone\|mavic\|phantom\|ardupilot" /tmp/drone_scan-01.csv >> "$LOG_FILE" 2>/dev/null
        local drone_count=$(grep -ic "drone\|mavic\|phantom\|ardupilot" /tmp/drone_scan-01.csv 2>/dev/null || echo "0")
        
        if [[ $drone_count -gt 0 ]]; then
            log_success "Found $drone_count potential drone networks"
        else
            log_info "No obvious drone networks detected"
        fi
        
        rm -f /tmp/drone_scan-* 2>/dev/null
    fi
}

scan_network_hosts() {
    local network="$1"
    log_info "Scanning network: $network"
    
    echo -e "${YELLOW}[*] Discovering active hosts...${NC}"
    
    # Host discovery
    local exclude_ips=""
    if [[ "$network" == "10.13.0.0/24" ]]; then
        exclude_ips="--exclude 10.13.0.1,10.13.0.5"
    elif [[ "$network" == "192.168.13.0/24" ]]; then
        exclude_ips="--exclude 192.168.13.10"
    fi
    
    local hosts_file="/tmp/hosts_$(date +%s).txt"
    nmap -sn $network $exclude_ips | grep -oP '(?<=Nmap scan report for )[0-9.]+' > "$hosts_file"
    
    local host_count=$(wc -l < "$hosts_file" 2>/dev/null || echo "0")
    
    if [[ $host_count -gt 0 ]]; then
        log_success "Discovered $host_count active hosts"
        
        echo -e "${GREEN}Active Hosts:${NC}"
        while IFS= read -r host; do
            echo "  └─ $host"
        done < "$hosts_file"
    else
        log_warning "No active hosts found"
    fi
    
    echo "$hosts_file"
}

scan_mavlink_services() {
    local hosts_file="$1"
    local network="$2"
    
    log_info "Scanning for MAVLink services..."
    
    if [[ ! -f "$hosts_file" ]]; then
        log_error "Hosts file not found"
        return 1
    fi
    
    echo -e "${YELLOW}[*] Scanning MAVLink ports...${NC}"
    
    local port_list=$(IFS=,; echo "${MAVLINK_PORTS[*]}")
    local results_file="/tmp/mavlink_scan_$(date +%s).txt"
    
    # 모든 호스트에 대해 MAVLink 포트 스캔
    while IFS= read -r host; do
        [[ -z "$host" ]] && continue
        
        echo -e "${CYAN}[*] Scanning $host...${NC}"
        nmap -sU -p "$port_list" --open "$host" 2>/dev/null | \
            grep -E "^[0-9]+/(udp|tcp)" >> "$results_file"
    done < "$hosts_file"
    
    # 전체 네트워크 스캔도 수행
    echo -e "${CYAN}[*] Performing network-wide MAVLink scan...${NC}"
    local exclude_ips=""
    if [[ "$network" == "10.13.0.0/24" ]]; then
        exclude_ips="--exclude 10.13.0.1,10.13.0.5"
    elif [[ "$network" == "192.168.13.0/24" ]]; then
        exclude_ips="--exclude 192.168.13.10"
    fi
    
    nmap -sU -p "$port_list" --open $network $exclude_ips >> "$results_file" 2>/dev/null
    
    # 결과 분석
    if [[ -f "$results_file" && -s "$results_file" ]]; then
        local service_count=$(wc -l < "$results_file")
        log_success "Found $service_count MAVLink services"
        
        echo -e "${GREEN}MAVLink Services:${NC}"
        while IFS= read -r line; do
            [[ -z "$line" ]] && continue
            local port=$(echo "$line" | cut -d'/' -f1)
            local service_type="Unknown"
            
            case "$port" in
                14550) service_type="Flight Controller" ;;
                14551) service_type="Ground Control Station" ;;
                14552) service_type="Companion Computer" ;;
                5760) service_type="SITL Simulator" ;;
                5762) service_type="Secondary GCS" ;;
                5763) service_type="Relay Node" ;;
            esac
            
            echo "  └─ Port $port: $service_type"
        done < "$results_file"
        
        # 로그에 기록
        cat "$results_file" >> "$LOG_FILE"
    else
        log_warning "No MAVLink services detected"
    fi
    
    rm -f "$results_file" 2>/dev/null
}

fingerprint_services() {
    local network="$1"
    log_info "Fingerprinting discovered services..."
    
    echo -e "${YELLOW}[*] Attempting service fingerprinting...${NC}"
    
    # 일반적인 드론 서비스 포트들 확인
    local common_ports="22,23,80,443,8080,5760,14550,14551"
    
    local exclude_ips=""
    if [[ "$network" == "10.13.0.0/24" ]]; then
        exclude_ips="--exclude 10.13.0.1,10.13.0.5"
    elif [[ "$network" == "192.168.13.0/24" ]]; then
        exclude_ips="--exclude 192.168.13.10"
    fi
    
    nmap -sV -p "$common_ports" $network $exclude_ips 2>/dev/null | \
        grep -E "(open|Service)" | \
        tee -a "$LOG_FILE"
}

generate_report() {
    log_info "Generating discovery report..."
    
    local report_file="$(get_log_dir)/drone_discovery_report_$(date +%Y%m%d_%H%M%S).txt"
    
    cat > "$report_file" << EOF
╔══════════════════════════════════════════════════╗
║           Drone Network Discovery Report         ║
╚══════════════════════════════════════════════════╝

Date: $(date)
Target Networks: $TARGET_NETWORK, $DOCKER_NETWORK
Attack Duration: $(cat "$LOG_FILE" | grep "Attack completed" | tail -1 | cut -d' ' -f4-5)

╔═══ SCAN RESULTS ═══╗

$(cat "$LOG_FILE" | grep -E "(SUCCESS|WARNING|INFO)" | tail -20)

╔═══ RECOMMENDATIONS ═══╗

1. 발견된 MAVLink 서비스에 대한 추가 정찰 수행
2. 열린 포트에 대한 취약점 스캔 실시  
3. 무선 네트워크 암호화 강도 점검
4. 네트워크 분할 및 접근 제어 검토

╚═══════════════════════╝
EOF

    log_success "Report saved to: $report_file"
    echo -e "${GREEN}Report location: $report_file${NC}"
}

cleanup() {
    log_info "Cleaning up temporary files..."
    rm -f /tmp/hosts_*.txt /tmp/mavlink_scan_*.txt /tmp/drone_scan* 2>/dev/null
    
    # 무선 인터페이스 복구
    local wifi_interface=$(iwconfig 2>/dev/null | awk '/IEEE 802.11/ {print $1; exit}')
    if [[ -n "$wifi_interface" ]]; then
        iwconfig "$wifi_interface" mode managed 2>/dev/null
    fi
}

main() {
    print_banner
    check_prerequisites
    
    log_info "Starting drone network discovery attack..."
    echo "Attack: $ATTACK_NAME" >> "$LOG_FILE"
    echo "Timestamp: $(date)" >> "$LOG_FILE"
    echo "================================" >> "$LOG_FILE"
    
    # WiFi 네트워크 스캔
    scan_wifi_networks
    
    # 네트워크별 호스트 스캔
    for network in "$TARGET_NETWORK" "$DOCKER_NETWORK"; do
        echo -e "\n${BLUE}[*] Scanning network: $network${NC}"
        
        hosts_file=$(scan_network_hosts "$network")
        
        if [[ -f "$hosts_file" && -s "$hosts_file" ]]; then
            scan_mavlink_services "$hosts_file" "$network"
            fingerprint_services "$network"
        fi
        
        rm -f "$hosts_file" 2>/dev/null
    done
    
    generate_report
    cleanup
    
    log_success "Drone discovery attack completed"
    echo "Attack completed at $(date)" >> "$LOG_FILE"
}

# Signal handlers
trap cleanup EXIT
trap 'echo -e "\n${RED}Attack interrupted${NC}"; cleanup; exit 1' INT TERM

# Execute main function
main "$@"