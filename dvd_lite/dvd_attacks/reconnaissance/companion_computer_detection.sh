#!/bin/bash

# =============================================================================
# DVD Companion Computer Detection Attack
# =============================================================================
# 파일: dvd_lite/dvd_attacks/reconnaissance/companion_computer_detection.sh
# 목적: 드론 컴패니언 컴퓨터 탐지 및 서비스 스캔
# 기반: Damn Vulnerable Drone Wiki - Companion Computer Detection
# =============================================================================

source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/colors.sh
source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/utils.sh

# 전역 변수
ATTACK_NAME="companion_computer_detection"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="/home/kali/MTD/MTD_full_testbed/attack_logs/reconnaissance/${ATTACK_NAME}_${TIMESTAMP}.log"
JSON_OUTPUT="/home/kali/MTD/MTD_full_testbed/attack_output/reconnaissance/${ATTACK_NAME}_${TIMESTAMP}.json"

# 타겟 IP (Wiki 기반)
DOCKER_TARGET="10.13.0.3"
WIFI_TARGET="192.168.13.1"

declare -a ATTACK_COMMANDS=()
declare -a DISCOVERED_SERVICES=()

print_header() {
    clear
    print_recon_header "Companion Computer Detection"
    echo -e "${INFO_COLOR}Target Services: SSH, RTSP, HTTP${NC}"
    echo -e "${INFO_COLOR}Common Ports: 22, 554, 3000${NC}"
    echo ""
}

# Step 1: 네트워크 모드 확인
check_network_mode() {
    echo -e "${BLUE}[1/3] Network Mode Check${NC}"
    
    local cmd="ip addr show"
    ATTACK_COMMANDS+=("$cmd")
    echo -e "${CYAN}→ $cmd${NC}"
    
    if ip addr show | grep -q "10.13.0"; then
        TARGET_IP="$DOCKER_TARGET"
        echo -e "${GREEN}[+] Docker mode - Target: $TARGET_IP${NC}"
    elif ip addr show | grep -q "192.168.13"; then
        TARGET_IP="$WIFI_TARGET"
        echo -e "${GREEN}[+] WiFi mode - Target: $TARGET_IP${NC}"
    else
        TARGET_IP="$DOCKER_TARGET"
        echo -e "${YELLOW}[!] Simulation mode - Target: $TARGET_IP${NC}"
    fi
}

# Step 2: 호스트 발견
discover_companion() {
    echo -e "${BLUE}[2/3] Host Discovery${NC}"
    
    local subnet=$(echo $TARGET_IP | cut -d. -f1-3).0/24
    local exclude_ips="$(echo $TARGET_IP | cut -d. -f1-3).1,$(echo $TARGET_IP | cut -d. -f1-3).5"
    
    local cmd="nmap -sn $subnet --exclude $exclude_ips"
    ATTACK_COMMANDS+=("$cmd")
    echo -e "${CYAN}→ $cmd${NC}"
    
    if command -v nmap >/dev/null 2>&1; then
        if ping -c 1 "$TARGET_IP" >/dev/null 2>&1; then
            echo -e "${GREEN}[+] Companion computer found: $TARGET_IP${NC}"
        else
            echo -e "${YELLOW}[!] Target unreachable, using simulation${NC}"
        fi
    else
        echo -e "${GREEN}[+] Simulated companion: $TARGET_IP${NC}"
    fi
}

# Step 3: 서비스 포트 스캔
scan_companion_services() {
    echo -e "${BLUE}[3/3] Service Port Scan${NC}"
    
    local cmd="nmap $TARGET_IP"
    ATTACK_COMMANDS+=("$cmd")
    echo -e "${CYAN}→ $cmd${NC}"
    
    if command -v nmap >/dev/null 2>&1; then
        local scan_output=$(nmap "$TARGET_IP" 2>/dev/null)
        
        while IFS= read -r line; do
            if [[ $line =~ ([0-9]+)/tcp.*open.*([a-zA-Z-]+) ]]; then
                local port="${BASH_REMATCH[1]}"
                local service="${BASH_REMATCH[2]}"
                DISCOVERED_SERVICES+=("$port:$service")
                
                case "$port" in
                    "22")
                        echo -e "${RED}[!] SSH service: $TARGET_IP:$port${NC}"
                        ;;
                    "554")
                        echo -e "${RED}[!] RTSP service: $TARGET_IP:$port${NC}"
                        ;;
                    "3000")
                        echo -e "${RED}[!] HTTP service: $TARGET_IP:$port${NC}"
                        ;;
                    *)
                        echo -e "${GREEN}[+] Service: $TARGET_IP:$port ($service)${NC}"
                        ;;
                esac
            fi
        done <<< "$scan_output"
    else
        # 시뮬레이션 (Wiki 예시 출력 기반)
        echo -e "${GREEN}[+] Simulated scan results:${NC}"
        local sim_services=("22:ssh" "554:rtsp" "3000:ppp")
        for service in "${sim_services[@]}"; do
            local port=$(echo $service | cut -d: -f1)
            local name=$(echo $service | cut -d: -f2)
            DISCOVERED_SERVICES+=("$service")
            
            case "$port" in
                "22")
                    echo -e "${RED}[!] SSH service: $TARGET_IP:$port${NC}"
                    ;;
                "554")
                    echo -e "${RED}[!] RTSP service: $TARGET_IP:$port${NC}"
                    ;;
                "3000")
                    echo -e "${RED}[!] HTTP service: $TARGET_IP:$port${NC}"
                    ;;
            esac
        done
    fi
}

# JSON 결과 생성
generate_json_report() {
    cat > "$JSON_OUTPUT" << EOF
{
  "attack_name": "$ATTACK_NAME",
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "target_ip": "$TARGET_IP",
  "services_discovered": ${#DISCOVERED_SERVICES[@]},
  "discovered_services": ["$(IFS='","'; echo "${DISCOVERED_SERVICES[*]}")"],
  "attack_commands": ["$(IFS='","'; echo "${ATTACK_COMMANDS[*]}")"]
}
EOF
}

# 메인 실행
main() {
    START_TIME=$(date +%s)
    
    mkdir -p "$(dirname "$LOG_FILE")" "$(dirname "$JSON_OUTPUT")"
    echo "=== Companion Computer Detection - $(date) ===" > "$LOG_FILE"
    
    print_header
    check_network_mode
    discover_companion
    scan_companion_services
    
    # 결과 요약
    echo ""
    echo -e "${CYAN}=== Attack Summary ===${NC}"
    echo -e "${INFO_COLOR}Target: $TARGET_IP${NC}"
    echo -e "${INFO_COLOR}Services Found: ${#DISCOVERED_SERVICES[@]}${NC}"
    echo -e "${INFO_COLOR}Commands Used: ${#ATTACK_COMMANDS[@]}${NC}"
    
    generate_json_report
    
    END_TIME=$(date +%s)
    echo -e "${INFO_COLOR}Duration: $((END_TIME - START_TIME))s${NC}"
    echo -e "${SUCCESS_COLOR}[✓] Companion computer detection completed${NC}"
}

main "$@"