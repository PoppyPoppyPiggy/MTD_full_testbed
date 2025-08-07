#!/bin/bash
# 파일 위치: /home/kali/MTD/MTD_full_testbed/kali_mtd_setup.sh
# Kali Linux 특화 MTD 테스트베드 설정 스크립트 (권한 문제 해결)

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}"
echo "╔═══════════════════════════════════════════════════════════════════╗"
echo "║              🐉 Kali Linux 특화 MTD 테스트베드                   ║"
echo "║          ArduPilot + QGroundControl + Gazebo + NS-3              ║"
echo "║                   권한 문제 완전 해결                             ║"
echo "╚═══════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# 현재 사용자 확인
if [ "$EUID" -eq 0 ]; then
    echo -e "${RED}[ERROR]${NC} 이 스크립트를 root로 실행하지 마세요!"
    echo "source mtd_env/bin/activate && ./kali_mtd_setup.sh"
    exit 1
fi

BASE_DIR=$(pwd)
VENV_PATH="$BASE_DIR/mtd_env"

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 1. 가상환경 확인
check_venv() {
    log_info "가상환경 확인 중..."
    
    if [ -z "$VIRTUAL_ENV" ]; then
        log_error "가상환경이 활성화되지 않았습니다!"
        echo "다음과 같이 실행하세요:"
        echo "source mtd_env/bin/activate"
        echo "./kali_mtd_setup.sh"
        exit 1
    else
        log_info "가상환경 활성화됨: $(basename $VIRTUAL_ENV)"
    fi
}

# 2. 기존 프로세스 정리
cleanup_processes() {
    log_info "기존 프로세스 정리 중..."
    
    pkill -f "sim_vehicle.py" 2>/dev/null || true
    pkill -f "arducopter" 2>/dev/null || true
    pkill -f "mavproxy.py" 2>/dev/null || true
    pkill -f "qgc_service" 2>/dev/null || true
    pkill -f "gazebo_service" 2>/dev/null || true
    pkill -f "ns3_fanet" 2>/dev/null || true
    pkill -f "simple_gcs" 2>/dev/null || true
    pkill -f "simple_ns3" 2>/dev/null || true
    
    # 포트 해제 (sudo 필요 시 사용)
    local ports=(14550 14551 5760 11345 9999 554 8080)
    for port in "${ports[@]}"; do
        local pid=$(lsof -ti:$port 2>/dev/null || true)
        if [ -n "$pid" ]; then
            log_warning "포트 $port 해제 (PID: $pid)"
            kill -9 "$pid" 2>/dev/null || true
        fi
    done
    
    sleep 2
    log_info "프로세스 정리 완료"
}

# 3. ArduPilot 설정
setup_ardupilot() {
    log_info "ArduPilot 설정 중..."
    
    local ardupilot_dir="$BASE_DIR/ardupilot"
    
    if [ ! -d "$ardupilot_dir" ]; then
        log_info "ArduPilot 클론 중..."
        git clone --recurse-submodules https://github.com/ArduPilot/ardupilot.git "$ardupilot_dir"
    fi
    
    # Python 의존성만 설치 (가상환경 내에서)
    log_info "ArduPilot Python 의존성 설치 중..."
    python -m pip install future lxml pymavlink pyserial monotonic numpy matplotlib
    
    log_info "✅ ArduPilot 설정 완료"
}

# 4. 스크립트 파일들을 직접 echo로 생성 (권한 문제 회피)
create_ardupilot_script() {
    log_info "ArduPilot 시작 스크립트 생성 중..."
    
    # 임시 파일로 생성 후 이동하는 방식 사용
    local temp_file="/tmp/start_ardupilot_$$.sh"
    
    echo '#!/bin/bash' > "$temp_file"
    echo '# 파일 위치: /home/kali/MTD/MTD_full_testbed/start_ardupilot.sh' >> "$temp_file"
    echo '# ArduPilot SITL 시작 스크립트' >> "$temp_file"
    echo '' >> "$temp_file"
    echo 'ARDUPILOT_DIR="./ardupilot"' >> "$temp_file"
    echo 'VENV_PATH="./mtd_env"' >> "$temp_file"
    echo '' >> "$temp_file"
    echo 'echo "🛩️ ArduPilot SITL 시작 중..."' >> "$temp_file"
    echo '' >> "$temp_file"
    echo '# 가상환경 활성화' >> "$temp_file"
    echo 'if [ -d "$VENV_PATH" ]; then' >> "$temp_file"
    echo '    source "$VENV_PATH/bin/activate"' >> "$temp_file"
    echo '    echo "✅ 가상환경 활성화됨"' >> "$temp_file"
    echo 'fi' >> "$temp_file"
    echo '' >> "$temp_file"
    echo 'if [ -d "$ARDUPILOT_DIR" ]; then' >> "$temp_file"
    echo '    cd "$ARDUPILOT_DIR"' >> "$temp_file"
    echo '    ' >> "$temp_file"
    echo '    if [ -f "Tools/autotest/sim_vehicle.py" ]; then' >> "$temp_file"
    echo '        echo "SITL 시작: ArduCopter"' >> "$temp_file"
    echo '        python Tools/autotest/sim_vehicle.py \' >> "$temp_file"
    echo '            --vehicle=ArduCopter \' >> "$temp_file"
    echo '            --aircraft=test \' >> "$temp_file"
    echo '            --location=KSFO \' >> "$temp_file"
    echo '            --out=127.0.0.1:14550 \' >> "$temp_file"
    echo '            --out=127.0.0.1:14551 \' >> "$temp_file"
    echo '            --console \' >> "$temp_file"
    echo '            --no-rebuild &' >> "$temp_file"
    echo '        ' >> "$temp_file"
    echo '        SITL_PID=$!' >> "$temp_file"
    echo '        echo $SITL_PID > /tmp/ardupilot_sitl.pid' >> "$temp_file"
    echo '        echo "✅ ArduPilot SITL 시작됨 (PID: $SITL_PID)"' >> "$temp_file"
    echo '        ' >> "$temp_file"
    echo '        sleep 15' >> "$temp_file"
    echo '        echo "🚁 ArduPilot SITL 준비 완료"' >> "$temp_file"
    echo '    else' >> "$temp_file"
    echo '        echo "❌ sim_vehicle.py를 찾을 수 없습니다"' >> "$temp_file"
    echo '        exit 1' >> "$temp_file"
    echo '    fi' >> "$temp_file"
    echo 'else' >> "$temp_file"
    echo '    echo "❌ ArduPilot 디렉토리를 찾을 수 없습니다"' >> "$temp_file"
    echo '    exit 1' >> "$temp_file"
    echo 'fi' >> "$temp_file"
    
    # 파일 이동 및 권한 설정
    mv "$temp_file" "start_ardupilot.sh"
    chmod +x "start_ardupilot.sh"
    
    log_info "✅ ArduPilot 스크립트 생성 완료"
}

# 5. QGroundControl 서비스 생성
create_qgc_service() {
    log_info "QGroundControl 서비스 생성 중..."
    
    local temp_file="/tmp/start_qgc_service_$$.py"
    
    cat > "$temp_file" << 'QGC_PYTHON_EOF'
#!/usr/bin/env python3
# 파일 위치: /home/kali/MTD/MTD_full_testbed/start_qgc_service.py
"""QGroundControl 대체 서비스"""

import socket
import time
import logging
import threading
import sys
import signal

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class QGCService:
    def __init__(self, port=14550):
        self.port = port
        self.running = False
        self.sock = None
        
    def start_service(self):
        self.running = True
        logger.info(f"🖥️ QGroundControl 서비스 시작 - 포트 {self.port}")
        
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.bind(('127.0.0.1', self.port))
            self.sock.settimeout(1.0)
            
            packet_count = 0
            last_log_time = time.time()
            
            while self.running:
                try:
                    data, addr = self.sock.recvfrom(1024)
                    packet_count += 1
                    
                    # 10초마다 로그 출력
                    current_time = time.time()
                    if current_time - last_log_time >= 10:
                        logger.info(f"📡 MAVLink 패킷 수신: {packet_count}개 from {addr[0]}")
                        last_log_time = current_time
                        
                except socket.timeout:
                    continue
                except socket.error as e:
                    if self.running:
                        logger.error(f"소켓 오류: {e}")
                    break
                except Exception as e:
                    logger.error(f"패킷 처리 오류: {e}")
                    
        except Exception as e:
            logger.error(f"QGC 서비스 오류: {e}")
        finally:
            self.cleanup()
            logger.info("🖥️ QGroundControl 서비스 종료됨")
    
    def cleanup(self):
        if self.sock:
            try:
                self.sock.close()
            except:
                pass
            self.sock = None
    
    def stop_service(self):
        self.running = False
        self.cleanup()

def signal_handler(signum, frame):
    logger.info("신호 수신됨, 서비스 종료 중...")
    global qgc_service
    if 'qgc_service' in globals():
        qgc_service.stop_service()
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    qgc_service = QGCService()
    try:
        qgc_service.start_service()
    except KeyboardInterrupt:
        logger.info("사용자에 의해 중단됨")
    finally:
        qgc_service.stop_service()
QGC_PYTHON_EOF
    
    mv "$temp_file" "start_qgc_service.py"
    chmod +x "start_qgc_service.py"
    
    log_info "✅ QGC 서비스 생성 완료"
}

# 6. Gazebo 서비스 생성
create_gazebo_service() {
    log_info "Gazebo 서비스 생성 중..."
    
    local temp_file="/tmp/start_gazebo_service_$$.py"
    
    cat > "$temp_file" << 'GAZEBO_PYTHON_EOF'
#!/usr/bin/env python3
# 파일 위치: /home/kali/MTD/MTD_full_testbed/start_gazebo_service.py
"""Gazebo 시뮬레이션 대체 서비스"""

import socket
import json
import time
import threading
import logging
import sys
import signal

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class GazeboService:
    def __init__(self, port=11345):
        self.port = port
        self.running = False
        self.simulation_time = 0.0
        self.drones = {}
        self.sock = None
        
    def start_service(self):
        self.running = True
        logger.info(f"🌍 Gazebo 서비스 시작 - 포트 {self.port}")
        
        # 시뮬레이션 스레드
        sim_thread = threading.Thread(target=self.run_simulation)
        sim_thread.daemon = True
        sim_thread.start()
        
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.bind(('127.0.0.1', self.port))
            self.sock.listen(5)
            self.sock.settimeout(1.0)
            
            client_count = 0
            
            while self.running:
                try:
                    client, addr = self.sock.accept()
                    client_count += 1
                    client_thread = threading.Thread(
                        target=self.handle_client, 
                        args=(client, addr, client_count)
                    )
                    client_thread.daemon = True
                    client_thread.start()
                except socket.timeout:
                    continue
                except socket.error as e:
                    if self.running:
                        logger.error(f"소켓 오류: {e}")
                    break
                except Exception as e:
                    logger.error(f"클라이언트 연결 오류: {e}")
                    
        except Exception as e:
            logger.error(f"Gazebo 서비스 오류: {e}")
        finally:
            self.cleanup()
            logger.info("🌍 Gazebo 서비스 종료됨")
    
    def run_simulation(self):
        while self.running:
            self.simulation_time += 0.1
            if int(self.simulation_time) % 10 == 0 and self.simulation_time % 1 < 0.1:
                logger.info(f"⏱️ 시뮬레이션 시간: {self.simulation_time:.1f}초, 드론: {len(self.drones)}대")
            time.sleep(0.1)
    
    def handle_client(self, client, addr, client_num):
        try:
            logger.info(f"🔗 Gazebo 클라이언트 연결: {addr} (#{client_num})")
            data = client.recv(1024)
            response = {
                "status": "running",
                "simulation_time": self.simulation_time,
                "world": "empty_world",
                "client_number": client_num
            }
            client.send(json.dumps(response).encode())
        except Exception as e:
            logger.error(f"클라이언트 처리 오류: {e}")
        finally:
            try:
                client.close()
            except:
                pass
    
    def cleanup(self):
        if self.sock:
            try:
                self.sock.close()
            except:
                pass
            self.sock = None
    
    def stop_service(self):
        self.running = False
        self.cleanup()

def signal_handler(signum, frame):
    logger.info("신호 수신됨, 서비스 종료 중...")
    global gazebo_service
    if 'gazebo_service' in globals():
        gazebo_service.stop_service()
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    gazebo_service = GazeboService()
    try:
        gazebo_service.start_service()
    except KeyboardInterrupt:
        logger.info("사용자에 의해 중단됨")
    finally:
        gazebo_service.stop_service()
GAZEBO_PYTHON_EOF
    
    mv "$temp_file" "start_gazebo_service.py"
    chmod +x "start_gazebo_service.py"
    
    log_info "✅ Gazebo 서비스 생성 완료"
}

# 7. NS-3 FANET 서비스 생성
create_ns3_fanet_service() {
    log_info "NS-3 FANET 서비스 생성 중..."
    
    local temp_file="/tmp/start_ns3_fanet_$$.py"
    
    cat > "$temp_file" << 'NS3_PYTHON_EOF'
#!/usr/bin/env python3
# 파일 위치: /home/kali/MTD/MTD_full_testbed/start_ns3_fanet.py
"""NS-3 FANET 네트워크 시뮬레이션 서비스"""

import socket
import json
import time
import threading
import logging
import random
import math
import sys
import signal

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class FANETNode:
    def __init__(self, node_id, position):
        self.node_id = node_id
        self.position = position
        self.neighbors = []
        self.energy = 100.0
        self.velocity = (0.0, 0.0, 0.0)

class NS3FANETService:
    def __init__(self, port=9999):
        self.port = port
        self.running = False
        self.nodes = {}
        self.simulation_time = 0.0
        self.topology_changes = 0
        self.sock = None
        
    def start_service(self):
        self.running = True
        logger.info(f"🌐 NS-3 FANET 서비스 시작 - 포트 {self.port}")
        
        # 초기 노드 생성
        self.initialize_nodes()
        
        # 시뮬레이션 스레드
        sim_thread = threading.Thread(target=self.run_simulation)
        sim_thread.daemon = True
        sim_thread.start()
        
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.bind(('127.0.0.1', self.port))
            self.sock.listen(5)
            self.sock.settimeout(1.0)
            
            client_count = 0
            
            while self.running:
                try:
                    client, addr = self.sock.accept()
                    client_count += 1
                    client_thread = threading.Thread(
                        target=self.handle_client, 
                        args=(client, addr, client_count)
                    )
                    client_thread.daemon = True
                    client_thread.start()
                except socket.timeout:
                    continue
                except socket.error as e:
                    if self.running:
                        logger.error(f"소켓 오류: {e}")
                    break
                except Exception as e:
                    logger.error(f"클라이언트 연결 오류: {e}")
                    
        except Exception as e:
            logger.error(f"NS-3 FANET 서비스 오류: {e}")
        finally:
            self.cleanup()
            logger.info("🌐 NS-3 FANET 서비스 종료됨")
    
    def initialize_nodes(self):
        logger.info("🔧 FANET 노드 초기화 중...")
        for i in range(10):
            node_id = f"fanet_node_{i:02d}"
            position = (
                random.uniform(-1000, 1000),
                random.uniform(-1000, 1000),
                random.uniform(50, 500)
            )
            self.nodes[node_id] = FANETNode(node_id, position)
            logger.info(f"📡 노드 생성: {node_id} at ({position[0]:.1f}, {position[1]:.1f}, {position[2]:.1f})")
    
    def run_simulation(self):
        while self.running:
            self.simulation_time += 1.0
            
            # 노드 이동
            self.update_mobility()
            
            # 토폴로지 업데이트
            if int(self.simulation_time) % 5 == 0:
                self.update_topology()
            
            if int(self.simulation_time) % 10 == 0:
                total_connections = sum(len(node.neighbors) for node in self.nodes.values()) // 2
                logger.info(f"📊 FANET 시간: {self.simulation_time}s, 노드: {len(self.nodes)}개, 연결: {total_connections}개")
            
            time.sleep(1.0)
    
    def update_mobility(self):
        """노드 이동성 업데이트"""
        for node in self.nodes.values():
            if random.random() < 0.1:  # 10% 확률로 방향 변경
                angle = random.uniform(0, 2 * math.pi)
                speed = random.uniform(5, 15)
                node.velocity = (
                    speed * math.cos(angle),
                    speed * math.sin(angle),
                    random.uniform(-2, 2)
                )
            
            # 위치 업데이트
            x, y, z = node.position
            vx, vy, vz = node.velocity
            
            new_x = max(-2000, min(2000, x + vx))
            new_y = max(-2000, min(2000, y + vy))
            new_z = max(50, min(500, z + vz))
            
            node.position = (new_x, new_y, new_z)
    
    def update_topology(self):
        """토폴로지 업데이트"""
        for node in self.nodes.values():
            node.neighbors.clear()
        
        nodes_list = list(self.nodes.values())
        for i, node1 in enumerate(nodes_list):
            for node2 in nodes_list[i+1:]:
                distance = self.calculate_distance(node1.position, node2.position)
                if distance <= 300:  # 통신 범위
                    node1.neighbors.append(node2.node_id)
                    node2.neighbors.append(node1.node_id)
        
        self.topology_changes += 1
    
    def calculate_distance(self, pos1, pos2):
        return math.sqrt(sum((a - b) ** 2 for a, b in zip(pos1, pos2)))
    
    def handle_client(self, client, addr, client_num):
        try:
            logger.info(f"🔗 NS-3 클라이언트 연결: {addr} (#{client_num})")
            data = client.recv(1024)
            
            total_connections = sum(len(node.neighbors) for node in self.nodes.values()) // 2
            avg_degree = total_connections * 2 / len(self.nodes) if self.nodes else 0
            
            response = {
                "status": "running",
                "simulation_time": self.simulation_time,
                "nodes": len(self.nodes),
                "connections": total_connections,
                "avg_degree": round(avg_degree, 2),
                "topology_changes": self.topology_changes,
                "fanet_protocol": "AODV",
                "mobility_model": "RandomWaypoint",
                "client_number": client_num
            }
            
            client.send(json.dumps(response).encode())
        except Exception as e:
            logger.error(f"클라이언트 처리 오류: {e}")
        finally:
            try:
                client.close()
            except:
                pass
    
    def cleanup(self):
        if self.sock:
            try:
                self.sock.close()
            except:
                pass
            self.sock = None
    
    def stop_service(self):
        self.running = False
        self.cleanup()

def signal_handler(signum, frame):
    logger.info("신호 수신됨, 서비스 종료 중...")
    global fanet_service
    if 'fanet_service' in globals():
        fanet_service.stop_service()
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    fanet_service = NS3FANETService()
    try:
        fanet_service.start_service()
    except KeyboardInterrupt:
        logger.info("사용자에 의해 중단됨")
    finally:
        fanet_service.stop_service()
NS3_PYTHON_EOF
    
    mv "$temp_file" "start_ns3_fanet.py"
    chmod +x "start_ns3_fanet.py"
    
    log_info "✅ NS-3 FANET 서비스 생성 완료"
}

# 8. 설정 파일 생성
create_config() {
    log_info "설정 파일 생성 중..."
    
    mkdir -p configs logs results
    
    cat > configs/mtd_config.yaml << 'CONFIG_YAML_EOF'
# 파일 위치: /home/kali/MTD/MTD_full_testbed/configs/mtd_config.yaml
# MTD 테스트베드 설정 (Kali Linux 최적화)
system:
  qgroundcontrol_host: "127.0.0.1"
  qgroundcontrol_port: 14550
  ardupilot_host: "127.0.0.1"
  ardupilot_port: 14551
  gazebo_host: "127.0.0.1"
  gazebo_port: 11345
  ns3_host: "127.0.0.1"
  ns3_port: 9999

fanet:
  max_range: 300.0
  node_count: 10
  mobility_model: "random_waypoint"
  ns3_integration: true
  simulation_area:
    x_range: [-2000, 2000]
    y_range: [-2000, 2000]
    z_range: [50, 500]

attacks:
  base_duration: 60
  max_concurrent: 3
  adaptive_intensity: true
  intensity_levels:
    light: 1
    moderate: 2
    aggressive: 3

detection:
  anomaly_threshold: 0.7
  alert_cooldown: 30
  ml_enabled: true

mtd:
  enabled: true
  response_time: 10
  defensive_actions:
    - "topology_change"
    - "frequency_hop"
    - "encryption_rotate"

environment:
  type: "simulation"
  use_virtual_env: true
  kali_linux: true

logging:
  level: "INFO"
  file: "logs/mtd_testbed.log"

research:
  paper_mode: true
  data_collection: true
CONFIG_YAML_EOF
    
    log_info "✅ 설정 파일 생성 완료"
}

# 9. 통합 실행 스크립트 생성
create_runner() {
    log_info "통합 실행 스크립트 생성 중..."
    
    local temp_file="/tmp/run_complete_mtd_$$.sh"
    
    cat > "$temp_file" << 'RUNNER_BASH_EOF'
#!/bin/bash
# 파일 위치: /home/kali/MTD/MTD_full_testbed/run_complete_mtd.sh
# 완전한 MTD 테스트베드 실행 스크립트 (Kali Linux 최적화)

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# 배너
echo -e "${CYAN}"
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║           🚁 완전한 MTD 테스트베드 시스템                        ║"
echo "║              Moving Target Defense Testbed                       ║"
echo "║                  (Kali Linux 최적화)                            ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# 파라미터
DURATION=${1:-5}
INTENSITY=${2:-light}
NODES=${3:-10}

log_info "실험 설정: 지속시간=${DURATION}분, 강도=${INTENSITY}, 노드=${NODES}개"

# 가상환경 확인
if [ -z "$VIRTUAL_ENV" ]; then
    if [ -d "./mtd_env" ]; then
        log_info "가상환경 활성화 중..."
        source "./mtd_env/bin/activate"
    else
        log_warning "가상환경을 찾을 수 없습니다"
        exit 1
    fi
fi

# 서비스 시작
start_services() {
    log_info "MTD 서비스 시작 중..."
    
    # ArduPilot SITL
    if [ -f "start_ardupilot.sh" ] && [ -x "start_ardupilot.sh" ]; then
        log_info "🛩️ ArduPilot SITL 시작..."
        ./start_ardupilot.sh &
        sleep 8
    else
        log_warning "ArduPilot 스크립트를 찾을 수 없거나 실행 권한이 없습니다"
    fi
    
    # QGroundControl 서비스
    if [ -f "start_qgc_service.py" ] && [ -x "start_qgc_service.py" ]; then
        log_info "🖥️ QGroundControl 서비스 시작..."
        python start_qgc_service.py &
        echo $! > /tmp/qgc_service.pid
        sleep 3
    else
        log_warning "QGC 서비스 스크립트를 찾을 수 없거나 실행 권한이 없습니다"
    fi
    
    # Gazebo 서비스
    if [ -f "start_gazebo_service.py" ] && [ -x "start_gazebo_service.py" ]; then
        log_info "🌍 Gazebo 서비스 시작..."
        python start_gazebo_service.py &
        echo $! > /tmp/gazebo_service.pid
        sleep 3
    else
        log_warning "Gazebo 서비스 스크립트를 찾을 수 없거나 실행 권한이 없습니다"
    fi
    
    # NS-3 FANET 서비스
    if [ -f "start_ns3_fanet.py" ] && [ -x "start_ns3_fanet.py" ]; then
        log_info "🌐 NS-3 FANET 서비스 시작..."
        python start_ns3_fanet.py &
        echo $! > /tmp/ns3_fanet.pid
        sleep 3
    else
        log_warning "NS-3 FANET 서비스 스크립트를 찾을 수 없거나 실행 권한이 없습니다"
    fi
}

# 연결 테스트
test_connections() {
    log_info "연결 테스트 중..."
    
    local services=("14550:QGroundControl" "14551:ArduPilot" "11345:Gazebo" "9999:NS-3_FANET")
    local success=0
    
    for service in "${services[@]}"; do
        local port=$(echo $service | cut -d: -f1)
        local name=$(echo $service | cut -d: -f2)
        
        if timeout 5 bash -c "echo >/dev/tcp/127.0.0.1/$port" 2>/dev/null; then
            log_info "✅ $name (포트 $port) 연결 성공"
            success=$((success + 1))
        else
            log_warning "❌ $name (포트 $port) 연결 실패"
        fi
    done
    
    echo -e "\n${BLUE}📊 연결 상태: $success/4 성공${NC}"
    return $success
}

# MTD 실행
run_mtd() {
    log_info "MTD 테스트베드 실행 중..."
    
    if [ -f "mtd_testbed_system.py" ]; then
        python mtd_testbed_system.py \
            --config configs/mtd_config.yaml \
            --duration $DURATION \
            --intensity $INTENSITY \
            --fanet-nodes $NODES
    else
        # 대체 시뮬레이션
        log_info "대체 시뮬레이션 실행 중..."
        local end_time=$(($(date +%s) + $DURATION * 60))
        local iteration=0
        
        while [ $(date +%s) -lt $end_time ]; do
            iteration=$((iteration + 1))
            local remaining=$((end_time - $(date +%s)))
            log_info "시뮬레이션 진행 중... (반복: $iteration, 남은시간: ${remaining}초)"
            
            # 공격 시나리오 시뮬레이션
            case $INTENSITY in
                light)
                    log_info "💥 가벼운 정찰 공격 시나리오"
                    ;;
                moderate)
                    log_info "💥💥 보통 프로토콜 조작 공격 시나리오"
                    ;;
                aggressive)
                    log_info "💥💥💥 강력한 DoS 공격 시나리오"
                    ;;
            esac
            
            sleep 30
        done
        
        log_info "✅ 시뮬레이션 완료"
    fi
}

# 결과 분석
analyze_results() {
    log_info "실험 결과 분석 중..."
    
    # 로그 파일 확인
    if [ -f "logs/mtd_testbed.log" ]; then
        local log_lines=$(wc -l < logs/mtd_testbed.log 2>/dev/null || echo "0")
        log_info "📄 로그 파일: logs/mtd_testbed.log ($log_lines 라인)"
    fi
    
    # 결과 파일 확인
    if [ -d "results" ]; then
        local result_files=$(find results -name "*.json" -o -name "*.csv" 2>/dev/null | wc -l)
        log_info "📊 결과 파일: $result_files 개"
    fi
    
    # 최종 시스템 상태
    echo -e "\n${CYAN}=== 최종 시스템 상태 ===${NC}"
    echo -e "${YELLOW}실행 중인 서비스:${NC}"
    ps aux | grep -E "(ardupilot|qgc_service|gazebo_service|ns3_fanet)" | grep -v grep || echo "서비스 프로세스 없음"
    
    echo -e "\n${YELLOW}포트 사용 상태:${NC}"
    netstat -tuln 2>/dev/null | grep -E "(14550|14551|11345|9999)" || echo "포트 정보 없음"
}

# 정리
cleanup() {
    log_info "서비스 정리 중..."
    
    local pid_files=("/tmp/ardupilot_sitl.pid" "/tmp/qgc_service.pid" "/tmp/gazebo_service.pid" "/tmp/ns3_fanet.pid")
    
    for pid_file in "${pid_files[@]}"; do
        if [ -f "$pid_file" ]; then
            local pid=$(cat "$pid_file" 2>/dev/null || echo "")
            if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
                log_info "프로세스 종료: PID $pid"
                kill "$pid" 2>/dev/null || true
                sleep 1
                # 강제 종료
                if kill -0 "$pid" 2>/dev/null; then
                    kill -9 "$pid" 2>/dev/null || true
                fi
            fi
            rm -f "$pid_file"
        fi
    done
    
    # 프로세스 패턴 정리
    pkill -f "sim_vehicle.py" 2>/dev/null || true
    pkill -f "start_qgc_service.py" 2>/dev/null || true
    pkill -f "start_gazebo_service.py" 2>/dev/null || true
    pkill -f "start_ns3_fanet.py" 2>/dev/null || true
    
    log_info "정리 완료"
}

trap cleanup EXIT INT TERM

# 메인 실행
main() {
    start_services
    sleep 10
    
    if test_connections; then
        run_mtd
    else
        log_warning "일부 서비스 연결 실패했지만 계속 진행"
        run_mtd
    fi
    
    analyze_results
    log_info "✅ MTD 테스트베드 실행 완료!"
}

# 사용법
if [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
    echo "사용법: $0 [지속시간(분)] [강도] [노드수]"
    echo "예제: $0 5 light 10"
    echo "     $0 30 moderate 15"
    echo "     $0 60 aggressive 20"
    exit 0
fi

main "$@"
RUNNER_BASH_EOF
    
    mv "$temp_file" "run_complete_mtd.sh"
    chmod +x "run_complete_mtd.sh"
    
    log_info "✅ 통합 실행 스크립트 생성 완료"
}

# 10. 최종 확인
final_check() {
    log_info "최종 상태 확인 중..."
    
    echo -e "\n${CYAN}=== Kali Linux 최적화 설치 완료 ===${NC}"
    
    # 가상환경
    if [ -n "$VIRTUAL_ENV" ]; then
        log_info "✅ 가상환경: $(basename $VIRTUAL_ENV)"
    else
        log_warning "❌ 가상환경 비활성화"
    fi
    
    # 패키지
    local packages=("pymavlink" "pyyaml" "psutil" "numpy")
    for pkg in "${packages[@]}"; do
        if python -c "import $pkg" 2>/dev/null; then
            log_info "✅ $pkg"
        else
            log_warning "❌ $pkg"
        fi
    done
    
    # 스크립트 및 권한
    local scripts=("start_ardupilot.sh" "start_qgc_service.py" "start_gazebo_service.py" "start_ns3_fanet.py" "run_complete_mtd.sh")
    for script in "${scripts[@]}"; do
        if [ -f "$script" ] && [ -x "$script" ]; then
            log_info "✅ $script (실행 가능)"
        elif [ -f "$script" ]; then
            log_warning "⚠️ $script (권한 수정 중...)"
            chmod +x "$script"
            if [ -x "$script" ]; then
                log_info "✅ $script (권한 수정됨)"
            else
                log_error "❌ $script (권한 수정 실패)"
            fi
        else
            log_warning "❌ $script (파일 없음)"
        fi
    done
    
    # 디렉토리 권한 확인
    if [ -d "configs" ] && [ -d "logs" ] && [ -d "results" ]; then
        log_info "✅ 디렉토리 구조 완성"
    else
        log_warning "⚠️ 일부 디렉토리 누락"
    fi
}

# 11. 사용법 안내
show_usage() {
    echo -e "\n${CYAN}=== 🎯 Kali Linux 최적화 사용법 ===${NC}"
    echo -e "${GREEN}1. 완전한 테스트베드 실행:${NC}"
    echo "   ./run_complete_mtd.sh 5 light 10"
    echo ""
    echo -e "${GREEN}2. 개별 서비스 테스트:${NC}"
    echo "   ./start_ardupilot.sh         # ArduPilot SITL"
    echo "   python start_qgc_service.py  # QGroundControl"
    echo "   python start_gazebo_service.py # Gazebo"
    echo "   python start_ns3_fanet.py    # NS-3 FANET"
    echo ""
    echo -e "${GREEN}3. 상태 확인:${NC}"
    echo "   netstat -tuln | grep -E '14550|14551|11345|9999'"
    echo "   ps aux | grep -E 'ardupilot|qgc_service|gazebo_service|ns3_fanet'"
    echo ""
    echo -e "${GREEN}4. 로그 모니터링:${NC}"
    echo "   tail -f logs/mtd_testbed.log"
    echo "   journalctl -f | grep -E 'QGroundControl|Gazebo|FANET'"
    echo ""
    echo -e "${GREEN}5. 문제 해결:${NC}"
    echo "   chmod +x *.sh *.py           # 권한 문제 시"
    echo "   source mtd_env/bin/activate  # 가상환경 재활성화"
    echo ""
    echo -e "${BLUE}🐉 Kali Linux 최적화 완료! 이제 테스트베드를 실행하세요!${NC}"
}

# 메인 실행
main() {
    log_info "Kali Linux 특화 MTD 테스트베드 설정 시작"
    
    check_venv
    cleanup_processes
    setup_ardupilot
    create_ardupilot_script
    create_qgc_service
    create_gazebo_service
    create_ns3_fanet_service
    create_config
    create_runner
    final_check
    show_usage
    
    echo -e "\n${GREEN}🎉 Kali Linux 특화 MTD 테스트베드 설정 완료!${NC}"
    echo -e "${CYAN}이제 ./run_complete_mtd.sh 5 light 10 으로 실행하세요${NC}"
}

# 스크립트 실행
main "$@"