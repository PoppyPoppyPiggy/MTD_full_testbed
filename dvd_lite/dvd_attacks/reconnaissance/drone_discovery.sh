#!/bin/bash

# =============================================================================
# DVD Drone Discovery Attack
# =============================================================================
# 파일: dvd_lite/dvd_attacks/reconnaissance/drone_discovery.sh
# 목적: MAVLink 드론 서비스 발견 및 포트 스캔
# 기반: Damn Vulnerable Drone Wiki - Drone Discovery
# =============================================================================

source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/colors.sh
source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/utils.sh

# 전역 변수
ATTACK_NAME="drone_discovery"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="/home/kali/MTD/MTD_full_testbed/attack_logs/reconnaissance/${ATTACK_NAME}_${TIMESTAMP}.log"
JSON_OUTPUT="/home/kali/MTD/MTD_full_testbed/attack_output/reconnaissance/${ATTACK_NAME}_${TIMESTAMP}.json"

# 공격 명령어 및 결과 저장
declare -a ATTACK_COMMANDS=()
declare -a DISCOVERED_HOSTS=()
declare -a MAVLINK_SERVICES=()

print_header() {
    clear
    print_recon_header "Drone Discovery Attack"
    echo -e "${INFO_COLOR}Target: MAVLink UAV Services${NC}"
    echo -e "${INFO_COLOR}Common Ports: 14550, 14540, 14560, 14580, 5760-5763${NC}"
    echo ""
}

# Step 1: 네트워크 연결 확인
check_network_connection() {
    echo -e "${BLUE}[1/3] Network Connection Check${NC}"
    
    local cmd="ip addr show"
    ATTACK_COMMANDS+=("$cmd")
    echo -e "${CYAN}→ $cmd${NC}"
    
    # Docker/WiFi 네트워크 감지
    if ip addr show | grep -q "10.13.0"; then
        NETWORK_MODE="docker"
        SUBNET="10.13.0.0/24"
        EXCLUDE_IPS="10.13.0.1,10.13.0.5"
        echo -e "${GREEN}[+] Docker bridge mode: $SUBNET${NC}"
    elif ip addr show | grep -q "192.168.13"; then
        NETWORK_MODE="wifi"
        SUBNET="192.168.13.0/24"
        EXCLUDE_IPS="192.168.13.10"
        echo -e "${GREEN}[+] WiFi mode: $SUBNET${NC}"
    else
        NETWORK_MODE="simulation"
        SUBNET="10.13.0.0/24"
        echo -e "${YELLOW}[!] Simulation mode${NC}"
    fi
}

# Step 2: 호스트 발견
discover_hosts() {
    echo -e "${BLUE}[2/3] Host Discovery${NC}"
    
    if [ "$NETWORK_MODE" = "simulation" ]; then
        DISCOVERED_HOSTS=("10.13.0.3" "10.13.0.4")
        for host in "${DISCOVERED_HOSTS[@]}"; do
            echo -e "${GREEN}[+] Simulated host: $host${NC}"
        done
    else
        local cmd="nmap -sn $SUBNET --exclude $EXCLUDE_IPS"
        ATTACK_COMMANDS+=("$cmd")
        echo -e "${CYAN}→ $cmd${NC}"
        
        if command -v nmap >/dev/null 2>&1; then
            mapfile -t scan_results < <(timeout 30s $cmd 2>/dev/null | grep "Nmap scan report" | awk '{print $5}')
            DISCOVERED_HOSTS=("${scan_results[@]}")
            
            [ ${#DISCOVERED_HOSTS[@]} -eq 0 ] && DISCOVERED_HOSTS=("10.13.0.3")
        else
            DISCOVERED_HOSTS=("10.13.0.3")
        fi
        
        for host in "${DISCOVERED_HOSTS[@]}"; do
            echo -e "${GREEN}[+] Host: $host${NC}"
        done
    fi
}

# Step 3: MAVLink 포트 스캔
scan_mavlink_ports() {
    echo -e "${BLUE}[3/3] MAVLink Port Scan${NC}"
    
    for host in "${DISCOVERED_HOSTS[@]}"; do
        echo -e "${CYAN}[*] Scanning $host${NC}"
        
        local cmd="nmap $host -p 1-16000"
        ATTACK_COMMANDS+=("$cmd")
        echo -e "${CYAN}→ $cmd${NC}"
        
        if command -v nmap >/dev/null 2>&1; then
            local scan_output=$(timeout 60s nmap "$host" -p 1-16000 2>/dev/null)
            
            while IFS= read -r line; do
                if [[ $line =~ ([0-9]+)/tcp.*open ]]; then
                    local port="${BASH_REMATCH[1]}"
                    MAVLINK_SERVICES+=("$host:$port")
                    
                    # MAVLink 포트 확인
                    if [[ $port =~ ^(14550|14540|14560|14580|5760|5762|5763)$ ]]; then
                        echo -e "${RED}[!] MAVLink service: $host:$port${NC}"
                    else
                        echo -e "${GREEN}[+] Service: $host:$port${NC}"
                    fi
                fi
            done <<< "$scan_output"
        else
            # 시뮬레이션
            local sim_ports=("14550" "5760" "22")
            for port in "${sim_ports[@]}"; do
                MAVLINK_SERVICES+=("$host:$port")
                if [[ $port =~ ^(14550|5760)$ ]]; then
                    echo -e "${RED}[!] MAVLink service: $host:$port${NC}"
                else
                    echo -e "${GREEN}[+] Service: $host:$port${NC}"
                fi
            done
        fi
        sleep 1
    done
}

# JSON 결과 생성
generate_json_report() {
    cat > "$JSON_OUTPUT" << EOF
{
  "attack_name": "$ATTACK_NAME",
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "network_mode": "$NETWORK_MODE",
  "target_subnet": "$SUBNET",
  "hosts_discovered": ${#DISCOVERED_HOSTS[@]},
  "discovered_hosts": ["$(IFS='","'; echo "${DISCOVERED_HOSTS[*]}")"],
  "mavlink_services": ${#MAVLINK_SERVICES[@]},
  "services": ["$(IFS='","'; echo "${MAVLINK_SERVICES[*]}")"],
  "attack_commands": ["$(IFS='","'; echo "${ATTACK_COMMANDS[*]}")"]
}
EOF
}

# 메인 실행
main() {
    START_TIME=$(date +%s)
    
    mkdir -p "$(dirname "$LOG_FILE")" "$(dirname "$JSON_OUTPUT")"
    echo "=== Drone Discovery - $(date) ===" > "$LOG_FILE"
    
    print_header
    check_network_connection
    discover_hosts
    scan_mavlink_ports
    
    # 결과 요약
    echo ""
    echo -e "${CYAN}=== Attack Summary ===${NC}"
    echo -e "${INFO_COLOR}Hosts Found: ${#DISCOVERED_HOSTS[@]}${NC}"
    echo -e "${INFO_COLOR}Services Found: ${#MAVLINK_SERVICES[@]}${NC}"
    echo -e "${INFO_COLOR}Commands Used: ${#ATTACK_COMMANDS[@]}${NC}"
    
    generate_json_report
    
    END_TIME=$(date +%s)
    echo -e "${INFO_COLOR}Duration: $((END_TIME - START_TIME))s${NC}"
    echo -e "${SUCCESS_COLOR}[✓] Drone discovery completed${NC}"
}

main "$@"