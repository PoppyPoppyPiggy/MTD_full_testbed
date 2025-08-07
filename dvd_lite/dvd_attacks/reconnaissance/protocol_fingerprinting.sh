#!/bin/bash
# protocol_fingerprinting.sh - MAVLink Protocol Fingerprinting Attack Tool
# Path: /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/reconnaissance/protocol_fingerprinting.sh

source "$(dirname "$0")/../common/colors.sh"
source "$(dirname "$0")/../common/utils.sh"

ATTACK_NAME="MAVLink Protocol Fingerprinting"
LOG_FILE="$(get_log_dir)/protocol_fingerprinting.log"

print_banner() {
    echo -e "${CYAN}"
    echo "╔═══════════════════════════════════════╗"
    echo "║      MAVLink 프로토콜 핑거프린팅          ║"
    echo "║     MAVLink Protocol Fingerprinting   ║"
    echo "╚═══════════════════════════════════════╝"
    echo -e "${NC}"
}

check_prerequisites() {
    log_info "Checking prerequisites..."
    
    local required_tools=("tshark" "wireshark" "python3" "netcat")
    for tool in "${required_tools[@]}"; do
        if ! command -v "$tool" &> /dev/null; then
            log_error "$tool is not installed"
            exit 1
        fi
    done
    
    # MAVLink 라이브러리 확인
    if ! python3 -c "import pymavlink" 2>/dev/null; then
        log_warning "pymavlink not installed, some features may be limited"
    fi
    
    log_success "Prerequisites check completed"
}

setup_wireshark_mavlink() {
    log_info "Setting up Wireshark MAVLink dissector..."
    
    local wireshark_plugins_dir="$HOME/.local/lib/wireshark/plugins"
    
    # 플러그인 디렉토리 생성
    mkdir -p "$wireshark_plugins_dir"
    
    # MAVLink dissector 설정 스크립트 생성
    cat > "/tmp/setup_mavlink_dissector.py" << 'EOF'
#!/usr/bin/env python3
import os
import subprocess
import sys

def setup_mavlink_dissector():
    """MAVLink Wireshark dissector 설정"""
    
    print("[*] Setting up MAVLink dissector...")
    
    # pymavlink 설치 확인
    try:
        import pymavlink
        print("[+] pymavlink is available")
    except ImportError:
        print("[!] Installing pymavlink...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pymavlink"], check=True)
    
    # MAVLink Lua dissector 생성
    lua_dissector = '''
-- MAVLink Protocol Dissector
local mavlink_proto = Proto("mavlink_proto", "MAVLink Protocol")

local udp_dissector_table = DissectorTable.get("udp.port")
udp_dissector_table:add(14550, mavlink_proto)
udp_dissector_table:add(14551, mavlink_proto) 
udp_dissector_table:add(14580, mavlink_proto)
udp_dissector_table:add(18570, mavlink_proto)
udp_dissector_table:add(5760, mavlink_proto)

function mavlink_proto.dissector(buffer, pinfo, tree)
    length = buffer:len()
    if length == 0 then return end
    
    pinfo.cols.protocol = mavlink_proto.name
    
    local subtree = tree:add(mavlink_proto, buffer(), "MAVLink Protocol Data")
    
    -- Check for MAVLink magic bytes
    if length >= 1 then
        local magic = buffer(0,1):uint()
        if magic == 0xFE then
            subtree:add(buffer(0,1), "MAVLink 1.0 (Magic: 0xFE)")
        elseif magic == 0xFD then  
            subtree:add(buffer(0,1), "MAVLink 2.0 (Magic: 0xFD)")
        end
    end
end
'''
    
    # Lua dissector 파일 저장
    plugins_dir = os.path.expanduser("~/.local/lib/wireshark/plugins")
    os.makedirs(plugins_dir, exist_ok=True)
    
    lua_file = os.path.join(plugins_dir, "mavlink_dissector.lua")
    with open(lua_file, 'w') as f:
        f.write(lua_dissector)
    
    print(f"[+] MAVLink dissector saved to: {lua_file}")
    
if __name__ == "__main__":
    setup_mavlink_dissector()
EOF
    
    python3 /tmp/setup_mavlink_dissector.py
    rm -f /tmp/setup_mavlink_dissector.py
}

capture_mavlink_packets() {
    local interface="any"
    local capture_file="/tmp/mavlink_fingerprint_$(date +%s).pcap"
    local capture_duration=60
    
    log_info "Capturing MAVLink packets for analysis..."
    
    echo -e "${YELLOW}[*] Starting packet capture for $capture_duration seconds...${NC}"
    echo -e "${CYAN}[*] Monitoring MAVLink ports: 14550, 14551, 5760${NC}"
    
    # MAVLink 패킷 캡처
    tshark -i "$interface" \
           -f "udp port 14550 or udp port 14551 or udp port 5760 or udp port 14580" \
           -w "$capture_file" \
           -a duration:$capture_duration &> /dev/null &
    
    local tshark_pid=$!
    
    # 진행률 표시
    for i in $(seq 1 $capture_duration); do
        echo -n "."
        sleep 1
    done
    echo ""
    
    # 캡처 완료 대기
    wait $tshark_pid 2>/dev/null
    
    if [[ -f "$capture_file" ]]; then
        local packet_count=$(tshark -r "$capture_file" 2>/dev/null | wc -l)
        log_success "Captured $packet_count packets"
        echo "$capture_file"
    else
        log_error "Failed to capture packets"
        return 1
    fi
}

analyze_mavlink_version() {
    local capture_file="$1"
    
    log_info "Analyzing MAVLink protocol version..."
    
    if [[ ! -f "$capture_file" ]]; then
        log_error "Capture file not found"
        return 1
    fi
    
    echo -e "${CYAN}[*] Analyzing MAVLink version from captured packets...${NC}"
    
    # 패킷에서 MAVLink magic bytes 추출
    local analysis_script="/tmp/mavlink_analysis.py"
    
    cat > "$analysis_script" << 'EOF'
#!/usr/bin/env python3
import sys
from scapy.all import *

def analyze_mavlink_packets(pcap_file):
    """MAVLink 패킷 분석"""
    
    packets = rdpcap(pcap_file)
    
    mavlink_v1_count = 0
    mavlink_v2_count = 0
    system_ids = set()
    component_ids = set()
    message_types = set()
    
    for packet in packets:
        if packet.haslayer(UDP):
            udp_layer = packet[UDP]
            
            # MAVLink 포트 확인
            if udp_layer.dport in [14550, 14551, 5760, 14580] or udp_layer.sport in [14550, 14551, 5760, 14580]:
                
                payload = bytes(udp_layer.payload)
                
                if len(payload) >= 6:
                    magic = payload[0]
                    
                    if magic == 0xFE:  # MAVLink 1.0
                        mavlink_v1_count += 1
                        if len(payload) >= 6:
                            system_ids.add(payload[3])
                            component_ids.add(payload[4])
                            message_types.add(payload[5])
                    
                    elif magic == 0xFD:  # MAVLink 2.0
                        mavlink_v2_count += 1
                        if len(payload) >= 10:
                            system_ids.add(payload[5])
                            component_ids.add(payload[6])
                            # Message ID는 3바이트로 확장됨
                            msg_id = int.from_bytes(payload[7:10], 'little')
                            message_types.add(msg_id)
    
    print(f"MAVLink 1.0 packets: {mavlink_v1_count}")
    print(f"MAVLink 2.0 packets: {mavlink_v2_count}")
    print(f"System IDs found: {sorted(system_ids)}")
    print(f"Component IDs found: {sorted(component_ids)}")
    print(f"Message types found: {len(message_types)}")
    
    return {
        'v1_count': mavlink_v1_count,
        'v2_count': mavlink_v2_count,
        'system_ids': list(system_ids),
        'component_ids': list(component_ids),
        'message_types': list(message_types)
    }

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 analyze_mavlink.py <pcap_file>")
        sys.exit(1)
    
    try:
        result = analyze_mavlink_packets(sys.argv[1])
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
EOF
    
    # Python 스크립트 실행
    if python3 -c "import scapy" 2>/dev/null; then
        echo -e "${GREEN}Protocol Version Analysis:${NC}"
        python3 "$analysis_script" "$capture_file" 2>/dev/null || {
            log_warning "Advanced analysis failed, using basic method"
            analyze_mavlink_basic "$capture_file"
        }
    else
        log_warning "Scapy not available, using basic analysis"
        analyze_mavlink_basic "$capture_file"
    fi
    
    rm -f "$analysis_script"
}

analyze_mavlink_basic() {
    local capture_file="$1"
    
    echo -e "${CYAN}[*] Performing basic MAVLink analysis...${NC}"
    
    # 기본적인 hex dump 분석
    local temp_hex="/tmp/mavlink_hex.txt"
    tshark -r "$capture_file" -T fields -e data 2>/dev/null | head -20 > "$temp_hex"
    
    local v1_count=0
    local v2_count=0
    
    while IFS= read -r line; do
        if [[ "$line" =~ ^fe ]]; then
            ((v1_count++))
        elif [[ "$line" =~ ^fd ]]; then
            ((v2_count++))
        fi
    done < "$temp_hex"
    
    echo -e "${GREEN}Basic Analysis Results:${NC}"
    echo "  └─ MAVLink 1.0 patterns: $v1_count"
    echo "  └─ MAVLink 2.0 patterns: $v2_count"
    
    if [[ $v2_count -gt $v1_count ]]; then
        echo -e "  └─ ${GREEN}Primary version: MAVLink 2.0${NC}"
    elif [[ $v1_count -gt 0 ]]; then
        echo -e "  └─ ${GREEN}Primary version: MAVLink 1.0${NC}"
    else
        echo -e "  └─ ${YELLOW}No clear MAVLink patterns detected${NC}"
    fi
    
    rm -f "$temp_hex"
}

detect_packet_signing() {
    local capture_file="$1"
    
    log_info "Detecting MAVLink packet signing..."
    
    echo -e "${CYAN}[*] Checking for MAVLink 2.0 message signing...${NC}"
    
    # 패킷 길이 분석으로 서명 여부 추정
    local signing_script="/tmp/signing_detection.py"
    
    cat > "$signing_script" << 'EOF'
#!/usr/bin/env python3
import sys
from scapy.all import *

def detect_signing(pcap_file):
    """MAVLink 메시지 서명 감지"""
    
    packets = rdpcap(pcap_file)
    signed_packets = 0
    unsigned_packets = 0
    
    for packet in packets:
        if packet.haslayer(UDP):
            udp_layer = packet[UDP]
            
            if udp_layer.dport in [14550, 14551, 5760] or udp_layer.sport in [14550, 14551, 5760]:
                payload = bytes(udp_layer.payload)
                
                if len(payload) >= 1 and payload[0] == 0xFD:  # MAVLink 2.0
                    if len(payload) >= 2:
                        flags = payload[2]
                        
                        # MAVLINK_IFLAG_SIGNED (0x01) 확인
                        if flags & 0x01:
                            signed_packets += 1
                        else:
                            unsigned_packets += 1
    
    print(f"Signed packets: {signed_packets}")
    print(f"Unsigned packets: {unsigned_packets}")
    
    if signed_packets > 0:
        print("Message signing: ENABLED")
        return True
    else:
        print("Message signing: DISABLED")
        return False

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(1)
    
    try:
        detect_signing(sys.argv[1])
    except:
        pass
EOF
    
    if python3 -c "import scapy" 2>/dev/null; then
        echo -e "${GREEN}Signing Detection Results:${NC}"
        python3 "$signing_script" "$capture_file" 2>/dev/null | while read line; do
            echo "  └─ $line"
        done
    else
        echo -e "${YELLOW}  └─ Advanced signing detection unavailable${NC}"
    fi
    
    rm -f "$signing_script"
}

extract_system_info() {
    local capture_file="$1"
    
    log_info "Extracting system information..."
    
    echo -e "${CYAN}[*] Extracting system and component IDs...${NC}"
    
    # tshark를 사용한 기본 추출
    local temp_analysis="/tmp/system_analysis.txt"
    
    tshark -r "$capture_file" -Y "udp.port == 14550 or udp.port == 14551 or udp.port == 5760" \
           -T fields -e ip.src -e ip.dst -e udp.srcport -e udp.dstport \
           2>/dev/null > "$temp_analysis"
    
    if [[ -s "$temp_analysis" ]]; then
        echo -e "${GREEN}Communication Endpoints:${NC}"
        
        # 소스 IP 통계
        echo -e "${CYAN}Source IPs:${NC}"
        awk '{print $1}' "$temp_analysis" | sort | uniq -c | sort -nr | while read count ip; do
            echo "  └─ $ip: $count packets"
        done
        
        # 목적지 IP 통계
        echo -e "${CYAN}Destination IPs:${NC}"
        awk '{print $2}' "$temp_analysis" | sort | uniq -c | sort -nr | while read count ip; do
            echo "  └─ $ip: $count packets"
        done
        
        # 포트 사용 통계
        echo -e "${CYAN}Port Usage:${NC}"
        awk '{print $3":"$4}' "$temp_analysis" | sort | uniq -c | sort -nr | head -10 | while read count ports; do
            echo "  └─ $ports: $count connections"
        done
    else
        log_warning "No MAVLink traffic found for analysis"
    fi
    
    rm -f "$temp_analysis"
}

generate_fingerprint_report() {
    log_info "Generating protocol fingerprinting report..."
    
    local report_file="$(get_log_dir)/protocol_fingerprinting_report_$(date +%Y%m%d_%H%M%S).txt"
    
    cat > "$report_file" << EOF
╔═══════════════════════════════════════════════════╗
║           MAVLink 프로토콜 핑거프린팅 보고서           ║
║        MAVLink Protocol Fingerprinting Report     ║
╚═══════════════════════════════════════════════════╝

Date: $(date)
Analysis Duration: 60 seconds
Capture Method: Network packet analysis

╔═══ PROTOCOL ANALYSIS ═══╗

$(cat "$LOG_FILE" | grep -A 20 "Protocol Version Analysis")

╔═══ SECURITY ASSESSMENT ═══╗

$(cat "$LOG_FILE" | grep -A 10 "Signing Detection")

╔═══ ATTACK IMPLICATIONS ═══╗

Based on protocol fingerprinting results:

1. Protocol Version Vulnerabilities
   - MAVLink 1.0: No built-in security features
   - MAVLink 2.0: Optional message signing
   - Version downgrade attacks possible

2. Security Feature Analysis
   - Message signing status affects attack feasibility
   - Unsigned messages vulnerable to injection
   - Replay attacks possible without proper authentication

3. System Identification
   - System/Component IDs enable targeted attacks
   - Communication patterns reveal network topology
   - Message types indicate available attack surfaces

╔═══ RECOMMENDATIONS ═══╗

1. 프로토콜 보안 강화
   - MAVLink 2.0 업그레이드 권장
   - 메시지 서명 기능 활성화
   - 암호화 채널 사용 검토

2. 네트워크 보안
   - MAVLink 트래픽 모니터링
   - 비정상 패킷 탐지 시스템 구축
   - 네트워크 분할 적용

3. 지속적인 모니터링
   - 프로토콜 이상 행위 감지
   - 보안 로그 분석
   - 정기적인 보안 평가

╚═════════════════════════╝
EOF

    log_success "Report saved to: $report_file"
    echo -e "${GREEN}Report location: $report_file${NC}"
}

cleanup() {
    log_info "Cleaning up temporary files..."
    rm -f /tmp/mavlink_fingerprint_*.pcap /tmp/mavlink_analysis.py /tmp/signing_detection.py /tmp/system_analysis.txt 2>/dev/null
}

main() {
    print_banner
    check_prerequisites
    
    log_info "Starting MAVLink protocol fingerprinting attack..."
    echo "Attack: $ATTACK_NAME" >> "$LOG_FILE"
    echo "Timestamp: $(date)" >> "$LOG_FILE"
    echo "================================" >> "$LOG_FILE"
    
    # Wireshark MAVLink dissector 설정
    setup_wireshark_mavlink
    
    # MAVLink 패킷 캡처
    local capture_file=$(capture_mavlink_packets)
    
    if [[ -f "$capture_file" ]]; then
        # 프로토콜 버전 분석
        analyze_mavlink_version "$capture_file"
        
        # 메시지 서명 감지
        detect_packet_signing "$capture_file"
        
        # 시스템 정보 추출
        extract_system_info "$capture_file"
        
        # 보고서 생성
        generate_fingerprint_report
    else
        log_error "Failed to capture MAVLink packets for analysis"
        exit 1
    fi
    
    cleanup
    
    log_success "Protocol fingerprinting attack completed"
    echo "Attack completed at $(date)" >> "$LOG_FILE"
}

# Signal handlers
trap cleanup EXIT
trap 'echo -e "\n${RED}Attack interrupted${NC}"; cleanup; exit 1' INT TERM

# Execute main function
main "$@"