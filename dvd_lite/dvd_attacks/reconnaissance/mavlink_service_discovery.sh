#!/bin/bash

# =============================================================================
# DVD MAVLink Service Discovery Attack  
# =============================================================================
# 파일: dvd_lite/dvd_attacks/reconnaissance/mavlink_service_discovery.sh
# 목적: MAVLink 서비스 및 포트 스캔
# 기반: Damn Vulnerable Drone Wiki - Drone Discovery
# =============================================================================

source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/colors.sh
source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/utils.sh

# 전역 변수
ATTACK_NAME="mavlink_service_discovery"
LOG_FILE="/home/kali/MTD/MTD_full_testbed/attack_logs/reconnaissance/${ATTACK_NAME}_$(date +%Y%m%d_%H%M%S).log"
IOC_FILE="/tmp/${ATTACK_NAME}_iocs_$(date +%Y%m%d_%H%M%S).txt"
JSON_OUTPUT="/home/kali/MTD/MTD_full_testbed/attack_output/reconnaissance/${ATTACK_NAME}_$(date +%Y%m%d_%H%M%S).json"

# 타겟 네트워크 설정
TARGET_NETWORK_DOCKER="10.13.0.0/24"
TARGET_NETWORK_WIFI="192.168.13.0/24"
EXCLUDE_IPS="10.13.0.1,10.13.0.5"  # 공격자 및 시뮬레이터 IP 제외

# MAVLink 포트 리스트 
MAVLINK_PORTS="14550,14551,14552,14553,14540,14560,14580,5760,5762,5763"
DRONE_PORTS="80,443,22,23,5600,8080,8554,554"

# 공격 명령어 및 결과 저장
declare -a ATTACK_COMMANDS=()
declare -a DISCOVERED_HOSTS=()
declare -a OPEN_PORTS=()

print_header() {
    clear
    print_recon_header "MAVLink Service Discovery Attack"
    echo -e "${INFO_COLOR}Target Networks: Docker Bridge (10.13.0.0/24) & WiFi (192.168.13.0/24)${NC}"
    echo -e "${INFO_COLOR}MAVLink Ports: $MAVLINK_PORTS${NC}"
    echo -e "${INFO_COLOR}Method: nmap port scanning${NC}"
    echo ""
}

# Step 1: 네트워크 연결 확인
check_network_connection() {
    echo -e "${BOLD}${BLUE}[1/4] Checking Network Connection${NC}"
    
    # 네트워크 인터페이스 확인
    local docker_ip=$(ip addr show | grep -o '10\.13\.0\.[0-9]*' | head -1)
    local wifi_ip=$(ip addr show | grep -o '192\.168\.13\.[0-9]*' | head -1)
    
    if [ -n "$docker_ip" ]; then
        echo -e "${GREEN}[+] Docker bridge network detected: $docker_ip${NC}"
        TARGET_NETWORK="$TARGET_NETWORK_DOCKER"
        EXCLUDE_IPS="$docker_ip,$EXCLUDE_IPS"
        add_ioc "$IOC_FILE" "NETWORK:docker:$docker_ip"
    elif [ -n "$wifi_ip" ]; then
        echo -e "${GREEN}[+] WiFi network detected: $wifi_ip${NC}"
        TARGET_NETWORK="$TARGET_NETWORK_WIFI"
        EXCLUDE_IPS="$wifi_ip"
        add_ioc "$IOC_FILE" "NETWORK:wifi:$wifi_ip"
    else
        echo -e "${YELLOW}[!] No target network detected, using simulation mode${NC}"
        TARGET_NETWORK="$TARGET_NETWORK_DOCKER"
        add_ioc "$IOC_FILE" "NETWORK:simulation:10.13.0.0/24"
    fi
    
    ATTACK_COMMANDS+=("ip addr show")
    log_info "Network connection check completed: $TARGET_NETWORK"
}

# Step 2: 호스트 발견
discover_hosts() {
    echo -e "${BOLD}${BLUE}[2/4] Host Discovery${NC}"
    
    local host_discovery_cmd="nmap -sn $TARGET_NETWORK --exclude $EXCLUDE_IPS"
    ATTACK_COMMANDS+=("$host_discovery_cmd")
    
    echo -e "${CYAN}[*] Command: $host_discovery_cmd${NC}"
    
    if command -v nmap >/dev/null 2>&1; then
        echo -e "${YELLOW}[*] Scanning for active hosts...${NC}"
        
        # nmap 호스트 발견 실행
        local nmap_output=$($host_discovery_cmd 2>/dev/null)
        
        # IP 주소 추출
        while IFS= read -r line; do
            if [[ $line =~ ([0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}) ]]; then
                local ip="${BASH_REMATCH[1]}"
                DISCOVERED_HOSTS+=("$ip")
                add_ioc "$IOC_FILE" "HOST_DISCOVERED:$ip:active"
                echo -e "${GREEN}[+] Active host: $ip${NC}"
            fi
        done <<< "$nmap_output"
    else
        echo -e "${YELLOW}[*] nmap not available - simulating host discovery${NC}"
        # 시뮬레이션된 호스트들
        if [[ $TARGET_NETWORK =~ "10.13.0" ]]; then
            local sim_hosts=("10.13.0.2" "10.13.0.3" "10.13.0.4")
        else
            local sim_hosts=("192.168.13.100" "192.168.13.101" "192.168.13.102")
        fi
        
        for host in "${sim_hosts[@]}"; do
            DISCOVERED_HOSTS+=("$host")
            add_ioc "$IOC_FILE" "HOST_DISCOVERED:$host:simulated"
            echo -e "${GREEN}[+] Simulated host: $host${NC}"
            sleep 1
        done
    fi
    
    echo -e "${INFO_COLOR}[*] Found ${#DISCOVERED_HOSTS[@]} active hosts${NC}"
    log_info "Host discovery completed: ${#DISCOVERED_HOSTS[@]} hosts found"
}

# Step 3: MAVLink 포트 스캔
scan_mavlink_ports() {
    echo -e "${BOLD}${BLUE}[3/4] MAVLink Port Scanning${NC}"
    
    if [ ${#DISCOVERED_HOSTS[@]} -eq 0 ]; then
        echo -e "${YELLOW}[!] No hosts found for port scanning${NC}"
        return
    fi
    
    for host in "${DISCOVERED_HOSTS[@]}"; do
        echo -e "${CYAN}[*] Scanning MAVLink ports on $host${NC}"
        
        local port_scan_cmd="nmap -p $MAVLINK_PORTS -sU -sT $host"
        ATTACK_COMMANDS+=("$port_scan_cmd")
        
        echo -e "${GRAY}    Command: $port_scan_cmd${NC}"
        
        if command -v nmap >/dev/null 2>&1; then
            # 실제 포트 스캔
            local scan_output=$($port_scan_cmd 2>/dev/null)
            
            # 열린 포트 추출
            while IFS= read -r line; do
                if [[ $line =~ ([0-9]+)/(tcp|udp).*open ]]; then
                    local port="${BASH_REMATCH[1]}"
                    local protocol="${BASH_REMATCH[2]}"
                    OPEN_PORTS+=("$host:$port/$protocol")
                    add_ioc "$IOC_FILE" "MAVLINK_PORT:$host:$port:$protocol"
                    echo -e "${GREEN}    [+] MAVLink port open: $port/$protocol${NC}"
                fi
            done <<< "$scan_output"
        else
            # 시뮬레이션된 포트 스캔
            local sim_ports=("14550" "5760")
            for port in "${sim_ports[@]}"; do
                OPEN_PORTS+=("$host:$port/udp")
                add_ioc "$IOC_FILE" "MAVLINK_PORT:$host:$port:udp:simulated"
                echo -e "${GREEN}    [+] Simulated MAVLink port: $port/udp${NC}"
                sleep 0.5
            done
        fi
    done
    
    log_info "MAVLink port scan completed: ${#OPEN_PORTS[@]} ports found"
}

# Step 4: 드론 서비스 스캔
scan_drone_services() {
    echo -e "${BOLD}${BLUE}[4/4] Drone Service Scanning${NC}"
    
    for host in "${DISCOVERED_HOSTS[@]}"; do
        echo -e "${CYAN}[*] Scanning drone services on $host${NC}"
        
        local service_scan_cmd="nmap -p $DRONE_PORTS -sV $host"
        ATTACK_COMMANDS+=("$service_scan_cmd")
        
        echo -e "${GRAY}    Command: $service_scan_cmd${NC}"
        
        if command -v nmap >/dev/null 2>&1; then
            # 실제 서비스 스캔
            local scan_output=$($service_scan_cmd 2>/dev/null)
            
            # 서비스 정보 추출
            while IFS= read -r line; do
                if [[ $line =~ ([0-9]+)/tcp.*open.*([a-zA-Z0-9\-\ ]+) ]]; then
                    local port="${BASH_REMATCH[1]}"
                    local service="${BASH_REMATCH[2]}"
                    add_ioc "$IOC_FILE" "DRONE_SERVICE:$host:$port:$service"
                    echo -e "${GREEN}    [+] Service: $port/tcp - $service${NC}"
                fi
            done <<< "$scan_output"
        else
            # 시뮬레이션된 서비스
            local sim_services=("80:http" "22:ssh" "5600:video-stream")
            for service_info in "${sim_services[@]}"; do
                IFS=':' read -r port service <<< "$service_info"
                add_ioc "$IOC_FILE" "DRONE_SERVICE:$host:$port:$service:simulated"
                echo -e "${GREEN}    [+] Simulated service: $port/tcp - $service${NC}"
                sleep 0.5
            done
        fi
    done
    
    log_info "Drone service scan completed"
}

# 공격 결과 JSON 생성
generate_json_report() {
    local hosts_json="["
    for i in "${!DISCOVERED_HOSTS[@]}"; do
        hosts_json+="\"${DISCOVERED_HOSTS[$i]}\""
        if [ $i -lt $((${#DISCOVERED_HOSTS[@]} - 1)) ]; then
            hosts_json+=","
        fi
    done
    hosts_json+="]"
    
    local ports_json="["
    for i in "${!OPEN_PORTS[@]}"; do
        ports_json+="\"${OPEN_PORTS[$i]}\""
        if [ $i -lt $((${#OPEN_PORTS[@]} - 1)) ]; then
            ports_json+=","
        fi
    done
    ports_json+="]"
    
    local commands_json="["
    for i in "${!ATTACK_COMMANDS[@]}"; do
        commands_json+="\"${ATTACK_COMMANDS[$i]}\""
        if [ $i -lt $((${#ATTACK_COMMANDS[@]} - 1)) ]; then
            commands_json+=","
        fi
    done
    commands_json+="]"
    
    cat > "$JSON_OUTPUT" << EOF
{
  "attack_name": "$ATTACK_NAME",
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "status": "completed",
  "target_network": "$TARGET_NETWORK",
  "hosts_discovered": ${#DISCOVERED_HOSTS[@]},
  "discovered_hosts": $hosts_json,
  "mavlink_ports_found": ${#OPEN_PORTS[@]},
  "open_ports": $ports_json,
  "attack_commands": $commands_json,
  "tools_used": ["nmap", "ip"],
  "mavlink_ports_scanned": "$MAVLINK_PORTS",
  "drone_ports_scanned": "$DRONE_PORTS",
  "ioc_file": "$IOC_FILE",
  "log_file": "$LOG_FILE"
}
EOF
    
    echo -e "${SUCCESS_COLOR}[✓] JSON report: $JSON_OUTPUT${NC}"
}

# 메인 실행 함수
main() {
    # 로그 및 IOC 파일 초기화
    echo "=== MAVLink Service Discovery Attack - $(date) ===" > "$LOG_FILE"
    echo "# MAVLink Service Discovery IOCs - $(date)" > "$IOC_FILE"
    
    START_TIME=$(date +%s)
    
    print_header
    
    # 공격 단계 실행
    check_network_connection
    discover_hosts
    scan_mavlink_ports  
    scan_drone_services
    
    # 결과 요약
    echo ""
    echo -e "${BOLD}${CYAN}=== Attack Summary ===${NC}"
    echo -e "${INFO_COLOR}Target Network: $TARGET_NETWORK${NC}"
    echo -e "${INFO_COLOR}Hosts Found: ${#DISCOVERED_HOSTS[@]}${NC}"
    echo -e "${INFO_COLOR}MAVLink Ports: ${#OPEN_PORTS[@]}${NC}"
    echo -e "${INFO_COLOR}Commands Used: ${#ATTACK_COMMANDS[@]}${NC}"
    echo -e "${INFO_COLOR}IOCs Generated: $(wc -l < "$IOC_FILE")${NC}"
    
    generate_json_report
    
    END_TIME=$(date +%s)
    echo -e "${INFO_COLOR}Duration: $((END_TIME - START_TIME)) seconds${NC}"
    echo -e "${SUCCESS_COLOR}[✓] Attack completed successfully${NC}"
}

main "$@"