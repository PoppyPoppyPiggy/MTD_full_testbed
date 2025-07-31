#!/bin/bash
# gcs_discovery.sh - Ground Control Station Discovery Attack Tool
# Path: /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/reconnaissance/gcs_discovery.sh

source "$(dirname "$0")/../common/colors.sh"
source "$(dirname "$0")/../common/utils.sh"

ATTACK_NAME="Ground Control Station Discovery"
LOG_FILE="$(get_log_dir)/gcs_discovery.log"

print_banner() {
    echo -e "${CYAN}"
    echo "╔═══════════════════════════════════════╗"
    echo "║   Ground Control Station Discovery    ║"
    echo "╚═══════════════════════════════════════╝"
    echo -e "${NC}"
}

check_prerequisites() {
    log_info "Checking prerequisites..."
    
    local required_tools=("nmap" "wireshark" "tshark" "netstat")
    for tool in "${required_tools[@]}"; do
        if ! command -v "$tool" &> /dev/null; then
            log_error "$tool is not installed"
            exit 1
        fi
    done
    
    log_success "Prerequisites check completed"
}

detect_network_mode() {
    log_info "Detecting network configuration..."
    
    local network_mode=""
    
    # Docker 브리지 네트워크 확인 (Non-WiFi Mode)
    if ip addr show | grep -q "10.13.0"; then
        network_mode="docker"
        TARGET_NETWORK="10.13.0.0/24"
        EXCLUDE_IPS="--exclude 10.13.0.1,10.13.0.5"
        log_info "Docker bridge network detected (Non-WiFi Mode)"
    # WiFi 네트워크 확인 (WiFi Mode)  
    elif ip addr show | grep -q "192.168.13"; then
        network_mode="wifi"
        TARGET_NETWORK="192.168.13.0/24"
        EXCLUDE_IPS="--exclude 192.168.13.10"
        log_info "WiFi network detected (WiFi Mode)"
    else
        log_warning "Network mode not detected, using default scan"
        TARGET_NETWORK="192.168.1.0/24"
        EXCLUDE_IPS=""
        network_mode="default"
    fi
    
    echo "$network_mode"
}

discover_hosts() {
    local network="$1"
    local exclude="$2"
    
    log_info "Discovering active hosts in $network..."
    
    local hosts_file="/tmp/gcs_hosts_$(date +%s).txt"
    
    echo -e "${YELLOW}[*] Scanning for active hosts...${NC}"
    nmap -sn $network $exclude | grep -oP '(?<=Nmap scan report for )[0-9.]+' > "$hosts_file"
    
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

capture_mavlink_traffic() {
    local network_mode="$1"
    local capture_file="/tmp/mavlink_capture_$(date +%s).pcap"
    
    log_info "Starting MAVLink traffic capture..."
    
    # 캡처할 인터페이스 결정
    local interface=""
    if [[ "$network_mode" == "docker" ]]; then
        interface=$(ip route | grep '10.13.0' | head -1 | awk '{print $3}')
    elif [[ "$network_mode" == "wifi" ]]; then
        interface=$(iwconfig 2>/dev/null | awk '/IEEE 802.11/ {print $1; exit}')
    else
        interface="any"
    fi
    
    [[ -z "$interface" ]] && interface="any"
    
    echo -e "${YELLOW}[*] Capturing packets on interface: $interface${NC}"
    echo -e "${YELLOW}[*] Looking for MAVLink traffic (ports 14550, 14551, 5760)...${NC}"
    
    # 백그라운드에서 패킷 캡처 시작
    tshark -i "$interface" -f "udp port 14550 or udp port 14551 or udp port 5760" \
           -w "$capture_file" -a duration:30 &> /dev/null &
    
    local tshark_pid=$!
    
    echo -e "${CYAN}[*] Capturing for 30 seconds... Please generate MAVLink traffic${NC}"
    
    # 진행 표시
    for i in {1..30}; do
        echo -n "."
        sleep 1
    done
    echo ""
    
    # tshark 프로세스 종료
    kill $tshark_pid 2>/dev/null
    wait $tshark_pid 2>/dev/null
    
    echo "$capture_file"
}

analyze_mavlink_traffic() {
    local capture_file="$1"
    local network_mode="$2"
    
    log_info "Analyzing captured MAVLink traffic..."
    
    if [[ ! -f "$capture_file" ]]; then
        log_error "Capture file not found: $capture_file"
        return 1
    fi
    
    # 패킷 수 확인
    local packet_count=$(tshark -r "$capture_file" 2>/dev/null | wc -l)
    
    if [[ $packet_count -eq 0 ]]; then
        log_warning "No packets captured. Please ensure MAVLink traffic is active."
        return 1
    fi
    
    log_success "Captured $packet_count packets"
    
    echo -e "${GREEN}MAVLink Traffic Analysis:${NC}"
    
    # IP 주소별 통계
    echo -e "${CYAN}Source IP Addresses:${NC}"
    tshark -r "$capture_file" -T fields -e ip.src 2>/dev/null | \
        sort | uniq -c | sort -nr | while read count ip; do
        echo "  └─ $ip: $count packets"
        
        # GCS 후보 식별
        case "$network_mode" in
            "docker")
                if [[ "$ip" == "10.13.0.4" ]]; then
                    echo -e "    ${GREEN}└─ Likely GCS (Docker Mode)${NC}"
                fi
                ;;
            "wifi")
                if [[ "$ip" == "192.168.13.14" ]]; then
                    echo -e "    ${GREEN}└─ Likely GCS (WiFi Mode)${NC}"
                fi
                ;;
        esac
    done
    
    echo -e "${CYAN}Destination IP Addresses:${NC}"
    tshark -r "$capture_file" -T fields -e ip.dst 2>/dev/null | \
        sort | uniq -c | sort -nr | while read count ip; do
        echo "  └─ $ip: $count packets"
    done
    
    # 포트별 통계
    echo -e "${CYAN}Port Usage:${NC}"
    tshark -r "$capture_file" -T fields -e udp.port 2>/dev/null | \
        sort | uniq -c | sort -nr | while read count port; do
        local service_type="Unknown"
        case "$port" in
            14550) service_type="MAVLink (Standard)" ;;
            14551) service_type="MAVLink (Secondary)" ;;
            5760) service_type="MAVLink (SITL)" ;;
        esac
        echo "  └─ Port $port: $count packets ($service_type)"
    done
    
    # 상세 분석 결과를 로그에 저장
    {
        echo "=== MAVLink Traffic Analysis ==="
        echo "Capture Time: $(date)"
        echo "Total Packets: $packet_count"
        echo ""
        echo "Source IPs:"
        tshark -r "$capture_file" -T fields -e ip.src 2>/dev/null | sort | uniq -c | sort -nr
        echo ""
        echo "Destination IPs:"
        tshark -r "$capture_file" -T fields -e ip.dst 2>/dev/null | sort | uniq -c | sort -nr
        echo ""
    } >> "$LOG_FILE"
}

identify_gcs_candidates() {
    local network_mode="$1"
    local hosts_file="$2"
    
    log_info "Identifying GCS candidates..."
    
    echo -e "${YELLOW}[*] Scanning for GCS-specific services...${NC}"
    
    # QGroundControl, Mission Planner 등의 일반적인 포트들
    local gcs_ports="5760,14550,14551,14552,8080,9000"
    
    while IFS= read -r host; do
        [[ -z "$host" ]] && continue
        
        echo -e "${CYAN}[*] Scanning $host for GCS services...${NC}"
        
        # 포트 스캔
        local scan_result=$(nmap -sU -sT -p "$gcs_ports" --open "$host" 2>/dev/null)
        
        if echo "$scan_result" | grep -q "open"; then
            echo -e "${GREEN}  └─ Potential GCS detected: $host${NC}"
            
            # 열린 포트 상세 정보
            echo "$scan_result" | grep -E "^[0-9]+/(tcp|udp).*open" | while read line; do
                echo "    └─ $line"
            done
            
            # 서비스 버전 탐지 시도
            local version_scan=$(nmap -sV -p "$gcs_ports" "$host" 2>/dev/null | grep -E "Service Info|Version")
            if [[ -n "$version_scan" ]]; then
                echo -e "${CYAN}    Service Information:${NC}"
                echo "$version_scan" | sed 's/^/      /'
            fi
            
            # 로그에 기록
            echo "GCS Candidate: $host" >> "$LOG_FILE"
            echo "$scan_result" | grep -E "^[0-9]+/(tcp|udp).*open" >> "$LOG_FILE"
        fi
        
    done < "$hosts_file"
}

perform_os_fingerprinting() {
    local hosts_file="$1"
    
    log_info "Performing OS fingerprinting on discovered hosts..."
    
    echo -e "${YELLOW}[*] OS Detection...${NC}"
    
    while IFS= read -r host; do
        [[ -z "$host" ]] && continue
        
        echo -e "${CYAN}[*] Fingerprinting $host...${NC}"
        
        local os_result=$(nmap -O "$host" 2>/dev/null | grep -E "Running|OS details")
        
        if [[ -n "$os_result" ]]; then
            echo -e "${GREEN}  └─ OS Information for $host:${NC}"
            echo "$os_result" | sed 's/^/    /'
            
            # 로그에 기록
            echo "OS Fingerprint for $host:" >> "$LOG_FILE"
            echo "$os_result" >> "$LOG_FILE"
        else
            echo "    └─ OS detection failed"
        fi
        
    done < "$hosts_file"
}

generate_gcs_report() {
    local network_mode="$1"
    
    log_info "Generating GCS discovery report..."
    
    local report_file="$(get_log_dir)/gcs_discovery_report_$(date +%Y%m%d_%H%M%S).txt"
    
    cat > "$report_file" << EOF
╔═══════════════════════════════════════════════════╗
║        Ground Control Station Discovery Report    ║
╚═══════════════════════════════════════════════════╝

Date: $(date)
Network Mode: $network_mode
Target Network: $TARGET_NETWORK

╔═══ DISCOVERY RESULTS ═══╗

$(cat "$LOG_FILE" | grep -E "(GCS Candidate|OS Fingerprint)" | head -20)

╔═══ TRAFFIC ANALYSIS ═══╗

$(cat "$LOG_FILE" | grep -A 10 "MAVLink Traffic Analysis" | tail -20)

╔═══ ATTACK VECTORS ═══╗

Based on discovered GCS systems:

1. MAVLink Protocol Exploitation
   - Target identified MAVLink services
   - Attempt command injection attacks
   - Monitor telemetry data

2. Network-based Attacks  
   - Port scanning for vulnerabilities
   - Service enumeration
   - Credential brute-forcing

3. Protocol Analysis
   - Deep packet inspection
   - Message replay attacks
   - Communication interception

╔═══ RECOMMENDATIONS ═══╗

1. 발견된 GCS에 대한 취약점 스캔 수행
2. MAVLink 트래픽 암호화 검토
3. 네트워크 접근 제어 강화
4. 지속적인 모니터링 체계 구축

╚═══════════════════════╝
EOF

    log_success "Report saved to: $report_file"
    echo -e "${GREEN}Report location: $report_file${NC}"
}

cleanup() {
    log_info "Cleaning up temporary files..."
    rm -f /tmp/gcs_hosts_*.txt /tmp/mavlink_capture_*.pcap 2>/dev/null
}

main() {
    print_banner
    check_prerequisites
    
    log_info "Starting Ground Control Station discovery attack..."
    echo "Attack: $ATTACK_NAME" >> "$LOG_FILE"
    echo "Timestamp: $(date)" >> "$LOG_FILE"
    echo "================================" >> "$LOG_FILE"
    
    # 네트워크 모드 감지
    local network_mode=$(detect_network_mode)
    
    # 호스트 발견
    local hosts_file=$(discover_hosts "$TARGET_NETWORK" "$EXCLUDE_IPS")
    
    if [[ -f "$hosts_file" && -s "$hosts_file" ]]; then
        # GCS 후보 식별
        identify_gcs_candidates "$network_mode" "$hosts_file"
        
        # OS 핑거프린팅
        perform_os_fingerprinting "$hosts_file"
        
        # MAVLink 트래픽 캡처 및 분석
        echo -e "\n${BLUE}[*] Starting traffic capture phase...${NC}"
        local capture_file=$(capture_mavlink_traffic "$network_mode")
        analyze_mavlink_traffic "$capture_file" "$network_mode"
        
    else
        log_warning "No hosts discovered for GCS identification"
    fi
    
    generate_gcs_report "$network_mode"
    cleanup
    
    log_success "GCS discovery attack completed"
    echo "Attack completed at $(date)" >> "$LOG_FILE"
}

# Signal handlers
trap cleanup EXIT
trap 'echo -e "\n${RED}Attack interrupted${NC}"; cleanup; exit 1' INT TERM

# Execute main function  
main "$@"