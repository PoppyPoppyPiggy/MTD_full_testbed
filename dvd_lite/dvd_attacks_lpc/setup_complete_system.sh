#!/bin/bash

# =================================================================
# MTD 드론 보안 테스트베드 완전 자동 구축 스크립트
# 파일: /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks_lpc/setup_complete_system.sh
# 사용법: chmod +x setup_complete_system.sh && ./setup_complete_system.sh
# =================================================================

set -e  # 오류 시 중단

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 로그 함수
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# 현재 디렉토리 설정
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$BASE_DIR"

log_info "MTD 드론 보안 테스트베드 완전 자동 구축 시작"
log_info "기준 디렉토리: $BASE_DIR"

# =================================================================
# 1. 디렉토리 구조 생성
# =================================================================

log_info "=== 디렉토리 구조 생성 ==="

# 모든 필요한 디렉토리 생성
mkdir -p {
    defense_system/{profiles,detectors,mtd_controllers,ml_models},
    honeydrone_network/{nodes,topologies,traffic_generators},
    data_pipeline/{collectors,processors,analyzers,exporters},
    ns3_integration/{scenarios,models,metrics,configs},
    docker_management/{monitors,controllers,networks},
    timestamp_sync/{handlers,validators,correctors},
    scenarios/adaptive/{attack_profiles,defense_configs,combined_scenarios},
    configs/{attack_intensity,defense_levels,network_topologies,thresholds},
    logs/{attacks,defenses,networks,timestamps,ns3},
    results/{experiments,analysis,visualizations,reports},
    ml/{models,datasets,training_logs,evaluation},
    attack_output,
    scripts/{deployment,monitoring,analysis}
}

log_success "디렉토리 구조 생성 완료"

# =================================================================
# 2. 설정 파일들 생성
# =================================================================

log_info "=== 설정 파일 생성 ==="

# --- 공격 강도 프로필 ---
cat > configs/attack_intensity/lpc_profiles.yaml << 'EOF'
attack_profiles:
  stealth_recon:
    intensity: "passive"
    duty_cycle: 0.02
    interval_ms: 30000
    jitter_pct: 40
    max_budget: 50
    stealth_factor: 0.9
    target_modules:
      - "wifi_network_discovery"
      - "mavlink_service_discovery"
    detection_threshold: 0.05
    description: "완전 수동적 정찰"

  active_recon:
    intensity: "low"
    duty_cycle: 0.08
    interval_ms: 15000
    jitter_pct: 30
    max_budget: 80
    stealth_factor: 0.7
    target_modules:
      - "camera_stream_discovery"
      - "component_enumeration"
    detection_threshold: 0.12
    description: "적극적 정찰"

  subtle_infiltration:
    intensity: "medium"
    duty_cycle: 0.12
    interval_ms: 8000
    jitter_pct: 25
    max_budget: 120
    stealth_factor: 0.5
    target_modules:
      - "gps_spoofing_attack"
      - "parameter_manipulation"
    detection_threshold: 0.25
    description: "은밀한 침투"

  aggressive_infiltration:
    intensity: "high"
    duty_cycle: 0.25
    interval_ms: 4000
    jitter_pct: 20
    max_budget: 200
    stealth_factor: 0.3
    target_modules:
      - "mavlink_packet_injection"
      - "flight_plan_injection"
    detection_threshold: 0.45
    description: "공격적 침투"

  persistent_campaign:
    intensity: "medium"
    duty_cycle: 0.06
    interval_ms: 20000
    jitter_pct: 35
    max_budget: 300
    stealth_factor: 0.8
    target_modules:
      - "telemetry_exfiltration"
      - "video_stream_hijack"
    detection_threshold: 0.18
    description: "지속적 캠페인"

  destructive_assault:
    intensity: "critical"
    duty_cycle: 0.4
    interval_ms: 2000
    jitter_pct: 15
    max_budget: 100
    stealth_factor: 0.1
    target_modules:
      - "mavlink_flood_attack"
      - "wifi_deauth_attack"
      - "firmware_upload_attack"
    detection_threshold: 0.75
    description: "파괴적 공격"
EOF

# --- 방어 수준 설정 ---
cat > configs/defense_levels/detection_thresholds.yaml << 'EOF'
defense_levels:
  none:
    packet_loss_threshold: 1.0
    latency_threshold: 1000.0
    cpu_threshold: 1.0
    memory_threshold: 1.0
    anomaly_score_threshold: 1.0
    mtd_interval: 0
    honeypot_ratio: 0.0
    ml_enabled: false
    description: "방어 없음"

  minimal:
    packet_loss_threshold: 0.15
    latency_threshold: 200.0
    cpu_threshold: 0.8
    memory_threshold: 0.8
    anomaly_score_threshold: 0.7
    mtd_interval: 300
    honeypot_ratio: 0.1
    ml_enabled: false
    description: "기본 모니터링만"

  standard:
    packet_loss_threshold: 0.08
    latency_threshold: 100.0
    cpu_threshold: 0.6
    memory_threshold: 0.7
    anomaly_score_threshold: 0.5
    mtd_interval: 180
    honeypot_ratio: 0.2
    ml_enabled: true
    ml_model: "random_forest"
    description: "표준 IDS"

  enhanced:
    packet_loss_threshold: 0.05
    latency_threshold: 50.0
    cpu_threshold: 0.4
    memory_threshold: 0.5
    anomaly_score_threshold: 0.3
    mtd_interval: 120
    honeypot_ratio: 0.3
    ml_enabled: true
    ml_model: "gradient_boosting"
    adaptive_learning: true
    description: "고급 ML 기반"

  maximum:
    packet_loss_threshold: 0.02
    latency_threshold: 25.0
    cpu_threshold: 0.3
    memory_threshold: 0.4
    anomaly_score_threshold: 0.15
    mtd_interval: 60
    honeypot_ratio: 0.4
    ml_enabled: true
    ml_model: "deep_neural_network"
    adaptive_learning: true
    real_time_mtd: true
    description: "실시간 MTD + AI"
EOF

# --- 허니드론 네트워크 토폴로지 ---
cat > configs/network_topologies/honeydrone_network.yaml << 'EOF'
network_topology:
  name: "honeydrone_fanet"
  description: "FANET 기반 허니드론 네트워크"
  
  segments:
    infrastructure:
      subnet: "10.13.0.0/24"
      description: "DVD 인프라 네트워크"
    
    wifi_simulation:
      subnet: "192.168.13.0/24"
      ssid: "Drone_Wifi"
      description: "시뮬레이션 WiFi 네트워크"
    
    honeydrone_mesh:
      subnet: "172.20.0.0/16"
      description: "허니드론 메시 네트워크"
    
    dummy_drones:
      subnet: "172.30.1.0/24"
      description: "더미드론 네트워크 (CTI 수집용)"
    
    virtual_drones:
      subnet: "172.30.2.0/24"
      description: "가상드론 네트워크 (DVD 기반)"

  nodes:
    # 실제 드론 (DVD 기반)
    real_drone:
      ip: "10.13.0.2"
      mac: "02:42:0a:0d:00:02"
      role: "real_drone"
      docker_container: "simulator"
      honeypot: false
      
    ground_control:
      ip: "10.13.0.3"
      mac: "02:42:0a:0d:00:03"
      role: "ground_control"
      docker_container: "ground-control-station"
      honeypot: false
      
    companion_computer:
      ip: "10.13.0.4"
      mac: "02:42:0a:0d:00:04"
      role: "companion"
      docker_container: "companion-computer"
      honeypot: false
      
    flight_controller:
      ip: "10.13.0.6"
      mac: "02:42:0a:0d:00:06"
      role: "flight_controller"
      docker_container: "flight-controller"
      honeypot: false

    # 허니드론 (물리적 실체)
    honeydrone_main:
      ip: "172.20.0.10"
      mac: "02:42:ac:14:00:0a"
      role: "honeydrone_primary"
      honeypot: true
      decoy_type: "phantom_4_pro"

    # 더미드론 (CTI 유도)
    dummy_drone_1:
      ip: "172.30.1.10"
      mac: "02:42:ac:1e:01:0a"
      role: "dummy_drone"
      honeypot: true
      purpose: "cti_collection"
      decoy_type: "mavic_air"
      
    dummy_drone_2:
      ip: "172.30.1.11"
      mac: "02:42:ac:1e:01:0b"
      role: "dummy_drone"
      honeypot: true
      purpose: "cti_collection"
      decoy_type: "mini_2"

    # 가상드론 (DVD 도커 기반)
    virtual_drone_1:
      ip: "172.30.2.10"
      mac: "02:42:ac:1e:02:0a"
      role: "virtual_drone"
      honeypot: true
      purpose: "simulation"
      docker_base: "dvd_simulator"
      
    virtual_drone_2:
      ip: "172.30.2.11"
      mac: "02:42:ac:1e:02:0b"
      role: "virtual_drone"
      honeypot: true
      purpose: "simulation"
      docker_base: "dvd_companion"

  traffic_flows:
    mavlink_telemetry:
      source: "real_drone"
      destination: "ground_control"
      port: 14550
      protocol: "udp"
      frequency_hz: 20
      
    video_stream:
      source: "real_drone"
      destination: "ground_control"
      port: 5600
      protocol: "udp"
      bandwidth_mbps: 5
      
    honeydrone_beacons:
      sources: ["honeydrone_main", "dummy_drone_1", "dummy_drone_2"]
      destination: "broadcast"
      port: 14550
      protocol: "udp"
      frequency_hz: 1
      
    cti_collection:
      sources: ["dummy_drone_1", "dummy_drone_2"]
      destination: "172.20.0.10"
      port: 8080
      protocol: "tcp"
      purpose: "attack_luring"
EOF

# --- ML 파이프라인 설정 ---
cat > ml/pipeline_config.yaml << 'EOF'
pipeline:
  mode: "integrated"
  update_interval: 1.0
  correlation_window: 60.0
  
sdn:
  host: "localhost"
  port: 6653
  enable_mtd: true
  mtd_interval: 30
  
reinforcement_learning:
  enable_training: true
  episode_length: 300
  learning_rate: 0.001
  epsilon_decay: 0.995
  update_frequency: 10
  
cti:
  enable_realtime: true
  batch_size: 10
  confidence_threshold: 0.8
  anomaly_threshold: -0.5
  
performance:
  enable_monitoring: true
  alert_thresholds:
    latency_ms: 100
    packet_loss_pct: 5
    detection_accuracy: 0.7
EOF

# --- NS-3 시나리오 설정 ---
cat > ns3_integration/configs/honeydrone_scenario.yaml << 'EOF'
ns3_scenario:
  name: "honeydrone_network_simulation"
  duration: 300
  seed: 42
  
  network_config:
    wifi_standard: "802.11n"
    frequency: 2.4
    channel_width: 20
    propagation_model: "LogDistance"
    mobility_model: "RandomWalk2d"
    
  nodes:
    count: 12
    positions:
      real_drone: [0, 0, 100]
      honeydrone_main: [50, 50, 100] 
      dummy_drone_1: [100, 0, 80]
      dummy_drone_2: [-50, 100, 90]
      ground_control: [0, 0, 0]
      
  applications:
    mavlink_traffic:
      type: "UdpEcho"
      port: 14550
      packet_size: 64
      interval: "50ms"
      
    video_streaming:
      type: "UdpClient"
      port: 5600
      packet_size: 1024
      data_rate: "5Mbps"
      
  metrics:
    - "throughput"
    - "delay"
    - "jitter" 
    - "packet_loss"
    - "energy_consumption"
EOF

log_success "설정 파일 생성 완료"

# =================================================================
# 3. 핵심 Python 모듈들 생성
# =================================================================

log_info "=== 핵심 Python 모듈 생성 ==="

# --- 타임스탬프 수집기 ---
cat > data_pipeline/collectors/timestamp_collector.py << 'EOF'
#!/usr/bin/env python3
"""
통합 타임스탬프 수집기
"""

import asyncio
import time
import json
import docker
import pandas as pd
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import threading
import queue
import logging
import os

@dataclass
class TimestampEvent:
    """통합 타임스탬프 이벤트"""
    timestamp: float           # Unix timestamp (microsecond precision)
    event_type: str           # 'attack', 'defense', 'network', 'docker'
    source: str               # 이벤트 소스 식별자
    component: str            # 컴포넌트 이름
    action: str               # 수행된 액션
    data: Dict[str, Any]      # 추가 데이터
    correlation_id: str       # 이벤트 상관관계 ID

class TimestampCollector:
    def __init__(self, output_dir: str = "logs/timestamps"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
        self.event_queue = queue.Queue()
        self.running = False
        self.correlation_counter = 0
        
        # 시간 동기화 기준점
        self.sync_reference = time.time()
        self.ns3_time_offset = 0.0
        
        # Docker 클라이언트 (안전하게 초기화)
        try:
            self.docker_client = docker.from_env()
        except Exception as e:
            print(f"Docker 클라이언트 초기화 실패: {e}")
            self.docker_client = None
        
        # 로거 설정
        self.logger = logging.getLogger("TimestampCollector")
        self.logger.setLevel(logging.INFO)
        handler = logging.FileHandler(f"{output_dir}/collector.log")
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        
    def start_collection(self):
        """타임스탬프 수집 시작"""
        self.running = True
        
        # 각 수집기를 별도 스레드에서 실행
        collectors = [
            threading.Thread(target=self._collect_lpc_events),
            threading.Thread(target=self._collect_network_events),
            threading.Thread(target=self._process_event_queue)
        ]
        
        # Docker 이벤트 수집 (Docker 클라이언트가 있는 경우만)
        if self.docker_client:
            collectors.append(threading.Thread(target=self._collect_docker_events))
        
        for collector in collectors:
            collector.daemon = True
            collector.start()
            
        self.logger.info("타임스탬프 수집기 시작됨")
        
    def _collect_docker_events(self):
        """Docker 컨테이너 이벤트 수집"""
        try:
            for event in self.docker_client.events(decode=True):
                if not self.running:
                    break
                    
                if event.get('Type') == 'container':
                    timestamp_event = TimestampEvent(
                        timestamp=time.time(),
                        event_type='docker',
                        source='docker_daemon',
                        component=event.get('Actor', {}).get('Attributes', {}).get('name', 'unknown'),
                        action=event.get('Action', 'unknown'),
                        data={
                            'container_id': event.get('Actor', {}).get('ID', ''),
                            'image': event.get('Actor', {}).get('Attributes', {}).get('image', ''),
                            'status': event.get('status', '')
                        },
                        correlation_id=self._get_correlation_id()
                    )
                    
                    self.event_queue.put(timestamp_event)
        except Exception as e:
            self.logger.error(f"Docker 이벤트 수집 오류: {e}")
    
    def _collect_lpc_events(self):
        """LPC 공격 이벤트 수집"""
        bus_log_path = "attack_output/bus.log"
        
        # 로그 파일이 없으면 생성
        os.makedirs("attack_output", exist_ok=True)
        if not os.path.exists(bus_log_path):
            open(bus_log_path, 'a').close()
        
        try:
            with open(bus_log_path, 'r') as f:
                f.seek(0, 2)  # 파일 끝으로 이동
                
                while self.running:
                    line = f.readline()
                    if line:
                        self._parse_lpc_event(line.strip())
                    else:
                        time.sleep(0.1)
        except Exception as e:
            self.logger.error(f"LPC 이벤트 수집 오류: {e}")
    
    def _parse_lpc_event(self, log_line: str):
        """LPC 로그 라인 파싱"""
        try:
            if not log_line or log_line.startswith('#'):
                return
                
            parts = log_line.split(',')
            if len(parts) < 2:
                return
                
            timestamp = float(parts[0])
            event_data = {}
            
            for part in parts[1:]:
                if '=' in part:
                    key, value = part.split('=', 1)
                    event_data[key] = value
            
            timestamp_event = TimestampEvent(
                timestamp=timestamp,
                event_type='attack',
                source='lpc_engine',
                component=event_data.get('module', 'unknown'),
                action=event_data.get('type', 'unknown'),
                data=event_data,
                correlation_id=self._get_correlation_id()
            )
            
            self.event_queue.put(timestamp_event)
            
        except Exception as e:
            self.logger.error(f"LPC 이벤트 파싱 오류: {e}")
    
    def _collect_network_events(self):
        """네트워크 이벤트 수집 (시뮬레이션)"""
        while self.running:
            try:
                # 네트워크 상태 시뮬레이션
                import random
                
                if random.random() < 0.1:  # 10% 확률로 이벤트 생성
                    event_types = ['packet_loss', 'latency_spike', 'bandwidth_change']
                    event_type = random.choice(event_types)
                    
                    timestamp_event = TimestampEvent(
                        timestamp=time.time(),
                        event_type='network',
                        source='network_monitor',
                        component='honeydrone_network',
                        action=event_type,
                        data={
                            'value': random.uniform(0, 100),
                            'severity': random.choice(['low', 'medium', 'high'])
                        },
                        correlation_id=self._get_correlation_id()
                    )
                    
                    self.event_queue.put(timestamp_event)
                
                time.sleep(1)
                
            except Exception as e:
                self.logger.error(f"네트워크 이벤트 수집 오류: {e}")
                time.sleep(5)
    
    def _process_event_queue(self):
        """이벤트 큐 처리 및 저장"""
        events_buffer = []
        last_save = time.time()
        
        while self.running:
            try:
                # 이벤트 수집 (최대 1초 대기)
                try:
                    event = self.event_queue.get(timeout=1)
                    events_buffer.append(asdict(event))
                except queue.Empty:
                    pass
                
                # 5초마다 또는 버퍼가 100개 이상일 때 저장
                if (time.time() - last_save > 5) or (len(events_buffer) >= 100):
                    if events_buffer:
                        self._save_events(events_buffer)
                        events_buffer.clear()
                        last_save = time.time()
                        
            except Exception as e:
                self.logger.error(f"이벤트 처리 오류: {e}")
                time.sleep(1)
    
    def _save_events(self, events: List[Dict]):
        """이벤트를 파일에 저장"""
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # JSON 형태로 저장
        json_path = f"{self.output_dir}/events_{timestamp_str}.json"
        with open(json_path, 'w') as f:
            json.dump(events, f, indent=2)
        
        # CSV 형태로도 저장 (분석 용이성)
        try:
            df = pd.DataFrame(events)
            csv_path = f"{self.output_dir}/events_{timestamp_str}.csv"
            df.to_csv(csv_path, index=False)
        except Exception as e:
            self.logger.error(f"CSV 저장 오류: {e}")
        
        self.logger.info(f"이벤트 {len(events)}개 저장: {json_path}")
    
    def _get_correlation_id(self) -> str:
        """상관관계 ID 생성"""
        self.correlation_counter += 1
        return f"corr_{int(time.time())}_{self.correlation_counter}"
    
    def stop_collection(self):
        """수집 중지"""
        self.running = False
        self.logger.info("타임스탬프 수집기 중지됨")

if __name__ == "__main__":
    collector = TimestampCollector()
    collector.start_collection()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        collector.stop_collection()
EOF

# --- 허니드론 네트워크 매니저 ---
cat > honeydrone_network/honeydrone_manager.py << 'EOF'
#!/usr/bin/env python3
"""
허니드론 네트워크 관리자
"""

import docker
import yaml
import subprocess
import time
import json
import logging
from typing import Dict, List, Any
import threading

class HoneydroneManager:
    def __init__(self, config_path: str = "configs/network_topologies/honeydrone_network.yaml"):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.docker_client = docker.from_env()
        self.logger = self._setup_logger()
        self.running_containers = {}
        
    def _setup_logger(self):
        logger = logging.getLogger("HoneydroneManager")
        logger.setLevel(logging.INFO)
        handler = logging.FileHandler("logs/networks/honeydrone_manager.log")
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        return logger
    
    def deploy_honeydrone_network(self):
        """허니드론 네트워크 배포"""
        self.logger.info("허니드론 네트워크 배포 시작")
        
        # 1. 네트워크 생성
        self._create_networks()
        
        # 2. 더미드론 컨테이너 생성
        self._deploy_dummy_drones()
        
        # 3. 가상드론 컨테이너 생성
        self._deploy_virtual_drones()
        
        # 4. 트래픽 생성기 시작
        self._start_traffic_generators()
        
        self.logger.info("허니드론 네트워크 배포 완료")
    
    def _create_networks(self):
        """Docker 네트워크 생성"""
        networks = [
            ("honeydrone_mesh", "172.20.0.0/16"),
            ("dummy_drones", "172.30.1.0/24"),
            ("virtual_drones", "172.30.2.0/24")
        ]
        
        for net_name, subnet in networks:
            try:
                self.docker_client.networks.create(
                    net_name,
                    driver="bridge",
                    ipam=docker.types.IPAMConfig(
                        pool_configs=[
                            docker.types.IPAMPool(subnet=subnet)
                        ]
                    )
                )
                self.logger.info(f"네트워크 생성: {net_name} ({subnet})")
            except docker.errors.APIError as e:
                if "already exists" in str(e):
                    self.logger.info(f"네트워크 이미 존재: {net_name}")
                else:
                    self.logger.error(f"네트워크 생성 실패: {e}")
    
    def _deploy_dummy_drones(self):
        """더미드론 배포 (CTI 수집용)"""
        dummy_config = {
            "dummy_drone_1": {
                "image": "alpine:latest",
                "command": ["sh", "-c", "while true; do echo 'DUMMY_DRONE_1 BEACON'; sleep 5; done"],
                "network": "dummy_drones",
                "ip": "172.30.1.10"
            },
            "dummy_drone_2": {
                "image": "alpine:latest", 
                "command": ["sh", "-c", "while true; do echo 'DUMMY_DRONE_2 BEACON'; sleep 5; done"],
                "network": "dummy_drones",
                "ip": "172.30.1.11"
            }
        }
        
        for name, config in dummy_config.items():
            try:
                container = self.docker_client.containers.run(
                    config["image"],
                    command=config["command"],
                    network=config["network"],
                    name=name,
                    detach=True,
                    remove=False
                )
                
                # IP 주소 설정
                network = self.docker_client.networks.get(config["network"])
                network.connect(container, ipv4_address=config["ip"])
                
                self.running_containers[name] = container
                self.logger.info(f"더미드론 배포: {name} ({config['ip']})")
                
            except Exception as e:
                self.logger.error(f"더미드론 배포 실패 {name}: {e}")
    
    def _deploy_virtual_drones(self):
        """가상드론 배포 (DVD 기반)"""
        virtual_config = {
            "virtual_drone_1": {
                "image": "alpine:latest",
                "command": ["sh", "-c", "apk add --no-cache netcat-openbsd && while true; do echo 'VD1 MAVLink MSG' | nc -u -w1 172.30.2.255 14550; sleep 1; done"],
                "network": "virtual_drones",
                "ip": "172.30.2.10"
            },
            "virtual_drone_2": {
                "image": "alpine:latest",
                "command": ["sh", "-c", "apk add --no-cache netcat-openbsd && while true; do echo 'VD2 MAVLink MSG' | nc -u -w1 172.30.2.255 14550; sleep 1; done"],
                "network": "virtual_drones", 
                "ip": "172.30.2.11"
            }
        }
        
        for name, config in virtual_config.items():
            try:
                container = self.docker_client.containers.run(
                    config["image"],
                    command=config["command"],
                    network=config["network"],
                    name=name,
                    detach=True,
                    remove=False
                )
                
                self.running_containers[name] = container
                self.logger.info(f"가상드론 배포: {name} ({config['ip']})")
                
            except Exception as e:
                self.logger.error(f"가상드론 배포 실패 {name}: {e}")
    
    def _start_traffic_generators(self):
        """트래픽 생성기 시작"""
        # 백그라운드에서 트래픽 생성
        threading.Thread(target=self._generate_mavlink_traffic, daemon=True).start()
        threading.Thread(target=self._generate_honeypot_traffic, daemon=True).start()
        
        self.logger.info("트래픽 생성기 시작됨")
    
    def _generate_mavlink_traffic(self):
        """MAVLink 트래픽 생성"""
        while True:
            try:
                # 시뮬레이션된 MAVLink 메시지 생성
                mavlink_msg = {
                    "timestamp": time.time(),
                    "msg_type": "HEARTBEAT",
                    "system_id": 1,
                    "component_id": 1,
                    "payload": "simulated_heartbeat"
                }
                
                # 로그에 기록
                with open("logs/networks/mavlink_traffic.log", "a") as f:
                    f.write(f"{json.dumps(mavlink_msg)}\n")
                
                time.sleep(1)
                
            except Exception as e:
                self.logger.error(f"MAVLink 트래픽 생성 오류: {e}")
                time.sleep(5)
    
    def _generate_honeypot_traffic(self):
        """허니팟 트래픽 생성"""
        while True:
            try:
                # 허니팟 비콘 메시지
                beacon_msg = {
                    "timestamp": time.time(),
                    "source": "honeydrone",
                    "msg_type": "BEACON",
                    "capabilities": ["GPS", "Camera", "Telemetry"],
                    "status": "active"
                }
                
                with open("logs/networks/honeypot_traffic.log", "a") as f:
                    f.write(f"{json.dumps(beacon_msg)}\n")
                
                time.sleep(5)
                
            except Exception as e:
                self.logger.error(f"허니팟 트래픽 생성 오류: {e}")
                time.sleep(10)
    
    def get_network_status(self) -> Dict:
        """네트워크 상태 조회"""
        status = {
            "containers": {},
            "networks": {},
            "traffic_stats": {}
        }
        
        # 컨테이너 상태
        for name, container in self.running_containers.items():
            try:
                container.reload()
                status["containers"][name] = {
                    "status": container.status,
                    "created": container.attrs["Created"],
                    "image": container.image.tags[0] if container.image.tags else "unknown"
                }
            except Exception as e:
                status["containers"][name] = {"status": "error", "error": str(e)}
        
        return status
    
    def cleanup(self):
        """리소스 정리"""
        self.logger.info("허니드론 네트워크 정리 시작")
        
        # 컨테이너 중지 및 제거
        for name, container in self.running_containers.items():
            try:
                container.stop()
                container.remove()
                self.logger.info(f"컨테이너 제거: {name}")
            except Exception as e:
                self.logger.error(f"컨테이너 제거 실패 {name}: {e}")
        
        # 네트워크 제거
        networks = ["honeydrone_mesh", "dummy_drones", "virtual_drones"]
        for net_name in networks:
            try:
                network = self.docker_client.networks.get(net_name)
                network.remove()
                self.logger.info(f"네트워크 제거: {net_name}")
            except Exception as e:
                self.logger.error(f"네트워크 제거 실패 {net_name}: {e}")

if __name__ == "__main__":
    manager = HoneydroneManager()
    try:
        manager.deploy_honeydrone_network()
        print("허니드론 네트워크가 배포되었습니다. Ctrl+C로 종료하세요.")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        manager.cleanup()
EOF

log_success "핵심 Python 모듈 생성 완료"

# =================================================================
# 4. NS-3 통합 스크립트
# =================================================================

log_info "=== NS-3 통합 스크립트 생성 ==="

cat > ns3_integration/scenarios/honeydrone_simulation.cc << 'EOF'
/* -*- Mode:C++; c-file-style:"gnu"; indent-tabs-mode:nil; -*- */
/*
 * Honeydrone Network Simulation for NS-3
 */

#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/mobility-module.h"
#include "ns3/wifi-module.h"
#include "ns3/internet-module.h"
#include "ns3/applications-module.h"
#include "ns3/flow-monitor-module.h"
#include "ns3/netanim-module.h"

using namespace ns3;

NS_LOG_COMPONENT_DEFINE ("HoneydroneSimulation");

int main (int argc, char *argv[])
{
  // 시뮬레이션 파라미터
  uint32_t nNodes = 12;
  double simTime = 300.0;
  std::string outputDir = "../../../attack_output/";
  
  CommandLine cmd;
  cmd.AddValue ("nNodes", "Number of nodes", nNodes);
  cmd.AddValue ("simTime", "Simulation time", simTime);
  cmd.AddValue ("outputDir", "Output directory", outputDir);
  cmd.Parse (argc, argv);

  // 노드 생성
  NodeContainer nodes;
  nodes.Create (nNodes);

  // WiFi 설정
  WifiHelper wifi;
  wifi.SetStandard (WIFI_STANDARD_80211n);
  
  YansWifiChannelHelper channel = YansWifiChannelHelper::Default ();
  YansWifiPhyHelper phy;
  phy.SetChannel (channel.Create ());

  WifiMacHelper mac;
  Ssid ssid = Ssid ("HoneydroneNetwork");
  mac.SetType ("ns3::StaWifiMac",
               "Ssid", SsidValue (ssid),
               "ActiveProbing", BooleanValue (false));

  NetDeviceContainer devices = wifi.Install (phy, mac, nodes);

  // 이동성 모델
  MobilityHelper mobility;
  mobility.SetPositionAllocator ("ns3::GridPositionAllocator",
                                 "MinX", DoubleValue (0.0),
                                 "MinY", DoubleValue (0.0),
                                 "DeltaX", DoubleValue (100.0),
                                 "DeltaY", DoubleValue (100.0),
                                 "GridWidth", UintegerValue (4),
                                 "LayoutType", StringValue ("RowFirst"));

  mobility.SetMobilityModel ("ns3::RandomWalk2dMobilityModel",
                             "Bounds", RectangleValue (Rectangle (-500, 500, -500, 500)));
  mobility.Install (nodes);

  // 인터넷 스택
  InternetStackHelper stack;
  stack.Install (nodes);

  Ipv4AddressHelper address;
  address.SetBase ("172.20.0.0", "255.255.0.0");
  Ipv4InterfaceContainer interfaces = address.Assign (devices);

  // 애플리케이션 설정 - MAVLink 트래픽 시뮬레이션
  uint16_t mavlinkPort = 14550;
  
  // 서버 (Ground Control)
  UdpEchoServerHelper echoServer (mavlinkPort);
  ApplicationContainer serverApps = echoServer.Install (nodes.Get (0));
  serverApps.Start (Seconds (1.0));
  serverApps.Stop (Seconds (simTime));

  // 클라이언트들 (드론들)
  for (uint32_t i = 1; i < nNodes; ++i)
    {
      UdpEchoClientHelper echoClient (interfaces.GetAddress (0), mavlinkPort);
      echoClient.SetAttribute ("MaxPackets", UintegerValue (1000000));
      echoClient.SetAttribute ("Interval", TimeValue (MilliSeconds (50)));
      echoClient.SetAttribute ("PacketSize", UintegerValue (64));

      ApplicationContainer clientApps = echoClient.Install (nodes.Get (i));
      clientApps.Start (Seconds (2.0 + i * 0.1));
      clientApps.Stop (Seconds (simTime));
    }

  // Flow Monitor 설정
  FlowMonitorHelper flowmon;
  Ptr<FlowMonitor> monitor = flowmon.InstallAll ();

  // 시뮬레이션 실행
  Simulator::Stop (Seconds (simTime));
  Simulator::Run ();

  // 결과 수집
  monitor->CheckForLostPackets ();
  Ptr<Ipv4FlowClassifier> classifier = DynamicCast<Ipv4FlowClassifier> (flowmon.GetClassifier ());
  FlowMonitor::FlowStatsContainer stats = monitor->GetFlowStats ();

  // CSV 파일로 결과 저장
  std::string csvFile = outputDir + "ns3_honeydrone_metrics.csv";
  std::ofstream csv (csvFile);
  csv << "FlowID,SourceIP,DestIP,TxPackets,RxPackets,LostPackets,Throughput_Mbps,MeanDelay_ms,MeanJitter_ms,PacketLossRate\n";

  for (std::map<FlowId, FlowMonitor::FlowStats>::const_iterator i = stats.begin (); i != stats.end (); ++i)
    {
      Ipv4FlowClassifier::FiveTuple t = classifier->FindFlow (i->first);
      
      double throughput = i->second.rxBytes * 8.0 / (i->second.timeLastRxPacket.GetSeconds () - i->second.timeFirstTxPacket.GetSeconds ()) / 1024 / 1024;
      double meanDelay = i->second.delaySum.GetMilliSeconds () / i->second.rxPackets;
      double meanJitter = i->second.jitterSum.GetMilliSeconds () / (i->second.rxPackets - 1);
      double lossRate = (double)(i->second.txPackets - i->second.rxPackets) / i->second.txPackets * 100;

      csv << i->first << ","
          << t.sourceAddress << ","
          << t.destinationAddress << ","
          << i->second.txPackets << ","
          << i->second.rxPackets << ","
          << i->second.lostPackets << ","
          << throughput << ","
          << meanDelay << ","
          << meanJitter << ","
          << lossRate << "\n";
    }

  csv.close ();
  
  std::cout << "시뮬레이션 완료. 결과: " << csvFile << std::endl;

  Simulator::Destroy ();
  return 0;
}
EOF

# --- NS-3 빌드 및 실행 스크립트 ---
cat > scripts/deployment/run_ns3_simulation.sh << 'EOF'
#!/bin/bash

# NS-3 시뮬레이션 실행 스크립트
set -e

NS3_DIR="${NS3_DIR:-~/MTD/MTD_full_testbed/ns-3.45/ns-3-dev}"
SIM_NAME="honeydrone_simulation"

log_info() { echo -e "\033[0;34m[INFO]\033[0m $1"; }
log_error() { echo -e "\033[0;31m[ERROR]\033[0m $1"; }

# NS-3 디렉토리 확인
if [ ! -d "$NS3_DIR" ]; then
    log_error "NS-3 디렉토리를 찾을 수 없습니다: $NS3_DIR"
    exit 1
fi

# 현재 위치 기억
CURRENT_DIR="$(pwd)"

# NS-3 시뮬레이션 파일 복사
cp "ns3_integration/scenarios/honeydrone_simulation.cc" "$NS3_DIR/scratch/"

cd "$NS3_DIR"

# 빌드
log_info "NS-3 시뮬레이션 빌드 중..."
if command -v ./ns3 &> /dev/null; then
    ./ns3 build
    log_info "NS-3 시뮬레이션 실행 중..."
    ./ns3 run "scratch/$SIM_NAME --simTime=300 --nNodes=12 --outputDir=$CURRENT_DIR/attack_output/"
else
    ./waf build
    log_info "NS-3 시뮬레이션 실행 중..."
    ./waf --run "scratch/$SIM_NAME --simTime=300 --nNodes=12 --outputDir=$CURRENT_DIR/attack_output/"
fi

cd "$CURRENT_DIR"
log_info "NS-3 시뮬레이션 완료"
EOF

chmod +x scripts/deployment/run_ns3_simulation.sh

log_success "NS-3 통합 스크립트 생성 완료"

# =================================================================
# 5. 통합 실행 스크립트
# =================================================================

log_info "=== 통합 실행 스크립트 생성 ==="

cat > scripts/deployment/run_integrated_system.sh << 'EOF'
#!/bin/bash

# 통합 시스템 실행 스크립트
set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$BASE_DIR"

# 도움말
show_help() {
    cat << EOF
MTD 드론 보안 테스트베드 통합 실행기

사용법: $0 <명령> [옵션]

명령:
    start                     전체 시스템 시작
    stop                      전체 시스템 중지
    status                    시스템 상태 확인
    experiment <scenario>     실험 시나리오 실행
    full-experiment          전체 실험 스위트 실행
    cleanup                  리소스 정리

실험 시나리오:
    stealth_recon            은밀한 정찰 공격 vs 표준 방어
    aggressive_attack        공격적 침투 vs 고급 방어
    persistent_campaign      지속적 캠페인 vs 실시간 MTD
    combined_scenario        복합 공격 시나리오

옵션:
    --defense-level <level>  방어 수준 (none|minimal|standard|enhanced|maximum)
    --duration <seconds>     실행 시간 (기본: 300초)
    --output-dir <dir>       결과 저장 디렉토리

예시:
    $0 start
    $0 experiment stealth_recon --defense-level standard --duration 600
    $0 full-experiment --output-dir results/full_test
EOF
}

# 기본 설정
DEFENSE_LEVEL="standard"
DURATION=300
OUTPUT_DIR="results/experiments/$(date +%Y%m%d_%H%M%S)"

# 파라미터 파싱
while [[ $# -gt 0 ]]; do
    case $1 in
        --defense-level)
            DEFENSE_LEVEL="$2"
            shift 2
            ;;
        --duration)
            DURATION="$2"
            shift 2
            ;;
        --output-dir)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            COMMAND="$1"
            shift
            ;;
    esac
done

# 명령 처리
case "${COMMAND:-}" in
    start)
        log_info "통합 시스템 시작 중..."
        
        # 1. 허니드론 네트워크 배포
        log_info "허니드론 네트워크 배포 중..."
        python3 honeydrone_network/honeydrone_manager.py &
        HONEYDRONE_PID=$!
        
        # 2. 타임스탬프 수집기 시작
        log_info "타임스탬프 수집기 시작 중..."
        python3 data_pipeline/collectors/timestamp_collector.py &
        COLLECTOR_PID=$!
        
        # 3. ML 파이프라인 시작
        log_info "ML 파이프라인 시작 중..."
        python3 ml/integrated_ml_pipeline.py --duration 0 &
        ML_PID=$!
        
        # 4. PID 저장
        echo "$HONEYDRONE_PID" > /tmp/honeydrone.pid
        echo "$COLLECTOR_PID" > /tmp/collector.pid
        echo "$ML_PID" > /tmp/ml_pipeline.pid
        
        log_success "통합 시스템 시작 완료"
        log_info "상태 확인: $0 status"
        log_info "중지: $0 stop"
        ;;
        
    stop)
        log_info "통합 시스템 중지 중..."
        
        # PID 파일에서 프로세스 종료
        for pid_file in /tmp/honeydrone.pid /tmp/collector.pid /tmp/ml_pipeline.pid; do
            if [ -f "$pid_file" ]; then
                PID=$(cat "$pid_file")
                if kill -0 "$PID" 2>/dev/null; then
                    kill "$PID"
                    log_info "프로세스 종료: $PID"
                fi
                rm -f "$pid_file"
            fi
        done
        
        # 허니드론 네트워크 정리
        python3 -c "
from honeydrone_network.honeydrone_manager import HoneydroneManager
manager = HoneydroneManager()
manager.cleanup()
"
        
        log_success "통합 시스템 중지 완료"
        ;;
        
    status)
        log_info "시스템 상태 확인 중..."
        
        # 프로세스 상태 확인
        for service in honeydrone collector ml_pipeline; do
            pid_file="/tmp/${service}.pid"
            if [ -f "$pid_file" ]; then
                PID=$(cat "$pid_file")
                if kill -0 "$PID" 2>/dev/null; then
                    log_success "$service: 실행 중 (PID: $PID)"
                else
                    log_warning "$service: 중지됨"
                fi
            else
                log_warning "$service: PID 파일 없음"
            fi
        done
        
        # 로그 파일 확인
        log_info "\n최근 로그 (마지막 5줄):"
        for log_file in logs/timestamps/collector.log logs/networks/honeydrone_manager.log attack_output/integrated_pipeline.log; do
            if [ -f "$log_file" ]; then
                echo -e "\n${BLUE}=== $log_file ===${NC}"
                tail -5 "$log_file"
            fi
        done
        ;;
        
    experiment)
        SCENARIO="${2:-stealth_recon}"
        log_info "실험 시나리오 실행: $SCENARIO"
        log_info "방어 수준: $DEFENSE_LEVEL, 지속시간: ${DURATION}초"
        
        mkdir -p "$OUTPUT_DIR"
        
        # 실험 설정 생성
        cat > "$OUTPUT_DIR/experiment_config.yaml" << EXPEOF
experiment:
  name: "$SCENARIO"
  defense_level: "$DEFENSE_LEVEL"
  duration: $DURATION
  scenario_config:
    attack_profile: "$SCENARIO"
    metrics_collection: true
    ns3_simulation: true
EXPEOF
        
        # 실험 실행
        log_info "실험 시작..."
        python3 ml/integrated_ml_pipeline.py \
            --mode experiment \
            --duration "$DURATION" \
            --experiment-config "$OUTPUT_DIR/experiment_config.yaml"
        
        # NS-3 시뮬레이션 실행
        log_info "NS-3 시뮬레이션 실행..."
        ./scripts/deployment/run_ns3_simulation.sh
        
        # 결과 분석
        log_info "결과 분석 중..."
        python3 -c "
import sys
sys.path.append('.')
from ml.integrated_ml_pipeline import IntegratedMLPipeline
pipeline = IntegratedMLPipeline()
report = pipeline.generate_comprehensive_report()
print('실험 완료. 보고서 생성됨.')
"
        
        log_success "실험 완료. 결과: $OUTPUT_DIR"
        ;;
        
    full-experiment)
        log_info "전체 실험 스위트 실행"
        
        # 모든 시나리오 실행
        scenarios=("stealth_recon" "aggressive_attack" "persistent_campaign")
        defense_levels=("minimal" "standard" "enhanced" "maximum")
        
        for scenario in "${scenarios[@]}"; do
            for defense in "${defense_levels[@]}"; do
                log_info "실험: $scenario vs $defense"
                
                exp_dir="${OUTPUT_DIR}/${scenario}_vs_${defense}"
                mkdir -p "$exp_dir"
                
                # 개별 실험 실행
                $0 experiment "$scenario" \
                    --defense-level "$defense" \
                    --duration 300 \
                    --output-dir "$exp_dir"
                
                log_success "완료: $scenario vs $defense"
                sleep 30  # 시스템 안정화 대기
            done
        done
        
        # 최종 비교 분석
        log_info "최종 비교 분석 생성 중..."
        python3 scripts/analysis/generate_comparison_report.py "$OUTPUT_DIR"
        
        log_success "전체 실험 스위트 완료. 결과: $OUTPUT_DIR"
        ;;
        
    cleanup)
        log_info "시스템 리소스 정리 중..."
        
        # 프로세스 중지
        $0 stop
        
        # 로그 파일 정리 (7일 이상 된 파일)
        find logs/ -name "*.log" -mtime +7 -delete 2>/dev/null || true
        
        # 임시 파일 정리
        rm -f /tmp/honeydrone.pid /tmp/collector.pid /tmp/ml_pipeline.pid
        
        # Docker 리소스 정리
        docker system prune -f 2>/dev/null || true
        
        log_success "리소스 정리 완료"
        ;;
        
    *)
        log_error "알 수 없는 명령: ${COMMAND:-}"
        log_info "도움말: $0 --help"
        exit 1
        ;;
esac
EOF

chmod +x scripts/deployment/run_integrated_system.sh

log_success "통합 실행 스크립트 생성 완료"

# =================================================================
# 6. Python 의존성 설치
# =================================================================

log_info "=== Python 의존성 설치 ==="

# requirements.txt 생성
cat > requirements.txt << 'EOF'
# 핵심 라이브러리
numpy>=1.21.0
pandas>=1.3.0
scipy>=1.7.0
scikit-learn>=1.0.0
matplotlib>=3.4.0
seaborn>=0.11.0
plotly>=5.0.0

# 머신러닝/딥러닝
torch>=1.9.0
xgboost>=1.4.0
lightgbm>=3.2.0

# 네트워킹/비동기
asyncio
aiohttp>=3.7.0
websockets>=9.0
docker>=5.0.0

# 데이터 처리
pyyaml>=5.4.0
jsonschema>=3.2.0

# 시각화
plotly>=5.0.0
dash>=2.0.0

# 테스트베드 특화
pymavlink>=2.4.0
pyserial>=3.5

# 개발 도구
pytest>=6.0.0
black>=21.0.0
flake8>=3.9.0
EOF

# Python 패키지 설치
if command -v pip3 &> /dev/null; then
    log_info "Python 패키지 설치 중..."
    pip3 install -r requirements.txt
    log_success "Python 패키지 설치 완료"
else
    log_warning "pip3을 찾을 수 없습니다. 수동으로 패키지를 설치하세요."
fi

# =================================================================
# 7. 최종 검증 및 권한 설정
# =================================================================

log_info "=== 최종 검증 및 권한 설정 ==="

# 모든 Python 파일에 실행 권한 부여
find . -name "*.py" -exec chmod +x {} \;

# 모든 스크립트에 실행 권한 부여
find . -name "*.sh" -exec chmod +x {} \;

# 디렉토리 권한 설정
chmod -R 755 logs/ results/ attack_output/ || true

# 설정 파일 검증
log_info "설정 파일 검증 중..."
python3 -c "
import yaml
import os

config_files = [
    'configs/attack_intensity/lpc_profiles.yaml',
    'configs/defense_levels/detection_thresholds.yaml',
    'configs/network_topologies/honeydrone_network.yaml',
    'ml/pipeline_config.yaml'
]

for config_file in config_files:
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                yaml.safe_load(f)
            print(f'✓ {config_file} - 유효')
        except Exception as e:
            print(f'✗ {config_file} - 오류: {e}')
    else:
        print(f'✗ {config_file} - 파일 없음')
"

# 시스템 정보 출력
cat > system_info.txt << 'EOF'
=================================================================
MTD 드론 보안 테스트베드 시스템 정보
=================================================================

📁 주요 디렉토리:
  • ml/                    - 머신러닝 모델 및 파이프라인
  • configs/               - 시스템 설정 파일
  • honeydrone_network/    - 허니드론 네트워크 관리
  • data_pipeline/         - 데이터 수집 및 처리
  • ns3_integration/       - NS-3 시뮬레이션 통합
  • scripts/               - 실행 및 관리 스크립트
  • attack_output/         - 공격 결과 및 로그
  • logs/                  - 시스템 로그
  • results/               - 실험 결과

🚀 빠른 시작:
  1. 전체 시스템 시작:
     ./scripts/deployment/run_integrated_system.sh start

  2. 실험 실행:
     ./scripts/deployment/run_integrated_system.sh experiment stealth_recon

  3. 상태 확인:
     ./scripts/deployment/run_integrated_system.sh status

  4. 시스템 중지:
     ./scripts/deployment/run_integrated_system.sh stop

🔬 실험 시나리오:
  • stealth_recon        - 은밀한 정찰 공격
  • aggressive_attack    - 공격적 침투
  • persistent_campaign  - 지속적 캠페인
  • combined_scenario    - 복합 공격

🛡️ 방어 수준:
  • none                 - 방어 없음
  • minimal              - 기본 모니터링
  • standard             - 표준 IDS
  • enhanced             - 고급 ML 기반
  • maximum              - 실시간 MTD + AI

📊 주요 구성요소:
  • SDN MTD Controller   - 동적 방어 전략 제어
  • RL Agent            - 강화학습 기반 적응
  • CTI Classifier      - 사이버 위협 인텔리젠스 분류
  • Honeydrone Network  - 허니드론 기반 속임수 네트워크
  • NS-3 Integration    - 네트워크 시뮬레이션

🔗 웹 인터페이스:
  • 공격/평가 콘솔: http://localhost:5001
  • DVD 모니터링: http://localhost:5002
  • SDN 상태: ws://localhost:8765

📝 로그 파일:
  • 통합 파이프라인: attack_output/integrated_pipeline.log
  • 타임스탬프 수집: logs/timestamps/collector.log
  • 허니드론 네트워크: logs/networks/honeydrone_manager.log
  • SDN Controller: attack_output/sdn_mtd.log

=================================================================
EOF

log_success "완전한 MTD 드론 보안 테스트베드 구축 완료!"

# 최종 안내 메시지
echo ""
echo "================================================================="
echo -e "${GREEN}🎉 MTD 드론 보안 테스트베드 구축 완료! 🎉${NC}"
echo "================================================================="
echo ""
echo -e "${BLUE}📋 다음 단계:${NC}"
echo "1. 시스템 시작: ./scripts/deployment/run_integrated_system.sh start"
echo "2. 실험 실행: ./scripts/deployment/run_integrated_system.sh experiment stealth_recon"
echo "3. 전체 문서 확인: cat system_info.txt"
echo ""
echo -e "${YELLOW}⚠️  주의사항:${NC}"
echo "• DVD Docker 컨테이너가 실행 중인지 확인하세요"
echo "• NS-3가 올바르게 설치되어 있는지 확인하세요"
echo "• 충분한 디스크 공간(최소 10GB)을 확보하세요"
echo ""
echo -e "${GREEN}✅ 모든 준비가 완료되었습니다!${NC}"
echo "================================================================="