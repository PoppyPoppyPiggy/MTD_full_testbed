#!/usr/bin/env python3
"""
드론 MTD (Moving Target Defense) 테스트베드
공격 강도 자동 조절 및 실시간 이상 지표 탐지 시스템

통합 모듈:
- QGroundControl 연동
- ArduPilot/PX4 지원
- Gazebo 시뮬레이션 
- NS-3 네트워크 시뮬레이션
- FANET 네트워크 구조

작성자: AI Assistant
날짜: 2025-08-05
라이센스: MIT
"""

import asyncio
import subprocess
import json
import time
import threading
import signal
import sys
import os
import random
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass, asdict, field
from enum import Enum, IntEnum
import logging
import socket
import struct
import yaml
import psutil
import queue
from concurrent.futures import ThreadPoolExecutor
import xml.etree.ElementTree as ET

# 추가 의존성 (설치 필요시)
try:
    import pymavlink.mavutil as mavutil
    from pymavlink import mavlink
    HAS_MAVLINK = True
except ImportError:
    HAS_MAVLINK = False
    print("Warning: pymavlink not available. Install with: pip install pymavlink")

try:
    import gazebo_msgs.srv
    import rospy
    from std_msgs.msg import String
    from geometry_msgs.msg import Twist
    HAS_ROS = True
except ImportError:
    HAS_ROS = False
    print("Warning: ROS not available. Some features may be limited.")

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('mtd_testbed.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class AttackIntensity(IntEnum):
    """공격 강도 레벨 (자동 조절 가능)"""
    RECONNAISSANCE = 1    # 정찰 - 최소 영향
    LIGHT = 2            # 가벼운 공격
    MODERATE = 3         # 보통 공격  
    AGGRESSIVE = 4       # 강력한 공격
    CRITICAL = 5         # 임계적 공격

class ThreatLevel(Enum):
    """위협 수준"""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class SystemModule(Enum):
    """시스템 모듈"""
    QGROUNDCONTROL = "qgroundcontrol"
    ARDUPILOT = "ardupilot"
    GAZEBO = "gazebo"
    NS3 = "ns3"
    FANET = "fanet"
    MAVLINK = "mavlink"

class AttackCategory(Enum):
    """공격 카테고리"""
    RECONNAISSANCE = "reconnaissance"
    PROTOCOL_TAMPERING = "protocol_tampering"
    DENIAL_OF_SERVICE = "denial_of_service"
    INJECTION = "injection"
    EXFILTRATION = "exfiltration"
    FIRMWARE_ATTACKS = "firmware_attacks"
    NETWORK_DISRUPTION = "network_disruption"
    MTD_EVASION = "mtd_evasion"

@dataclass
class SystemMetrics:
    """시스템 메트릭"""
    timestamp: datetime
    cpu_usage: float
    memory_usage: float
    network_latency: float
    packet_loss: float
    connection_count: int
    mavlink_messages: int
    qgc_status: str
    gazebo_entities: int
    ns3_nodes: int
    fanet_topology: Dict[str, Any]
    anomaly_score: float = 0.0

@dataclass
class AttackConfig:
    """공격 설정"""
    name: str
    category: AttackCategory
    intensity: AttackIntensity
    target_modules: List[SystemModule]
    duration: int  # 초
    script_path: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    success_threshold: float = 0.7
    detection_evasion: bool = False
    adaptive: bool = True  # 적응형 공격 여부

@dataclass
class AnomalyDetectionResult:
    """이상 탐지 결과"""
    timestamp: datetime
    anomaly_type: str
    severity: ThreatLevel
    confidence: float
    affected_modules: List[SystemModule]
    metrics: Dict[str, float]
    description: str
    recommended_action: str

@dataclass
class MTDAction:
    """MTD 액션"""
    action_type: str
    target_module: SystemModule
    parameters: Dict[str, Any]
    timestamp: datetime
    success: bool = False

class FANETNode:
    """FANET 노드 모델"""
    def __init__(self, node_id: str, position: Tuple[float, float, float], 
                 node_type: str = "drone"):
        self.node_id = node_id
        self.position = position  # (x, y, z)
        self.node_type = node_type  # drone, gcs, relay
        self.neighbors = []
        self.routing_table = {}
        self.is_active = True
        self.last_seen = datetime.now()
        
    def update_position(self, new_position: Tuple[float, float, float]):
        """위치 업데이트"""
        self.position = new_position
        self.last_seen = datetime.now()
        
    def add_neighbor(self, neighbor_id: str, distance: float):
        """이웃 노드 추가"""
        self.neighbors.append({"id": neighbor_id, "distance": distance})
        
    def is_in_range(self, other_position: Tuple[float, float, float], 
                   max_range: float = 1000.0) -> bool:
        """통신 범위 내 여부 확인"""
        distance = np.sqrt(sum([(a - b)**2 for a, b in zip(self.position, other_position)]))
        return distance <= max_range

class FANETTopologyManager:
    """FANET 토폴로지 관리자"""
    def __init__(self):
        self.nodes = {}
        self.connections = []
        self.topology_history = []
        
    def add_node(self, node: FANETNode):
        """노드 추가"""
        self.nodes[node.node_id] = node
        logger.info(f"FANET node added: {node.node_id} at {node.position}")
        
    def remove_node(self, node_id: str):
        """노드 제거"""
        if node_id in self.nodes:
            del self.nodes[node_id]
            self.connections = [c for c in self.connections 
                              if node_id not in [c['source'], c['target']]]
            logger.info(f"FANET node removed: {node_id}")
            
    def update_topology(self):
        """토폴로지 업데이트"""
        self.connections.clear()
        
        for node_id, node in self.nodes.items():
            node.neighbors.clear()
            
        # 모든 노드 간 거리 계산 및 연결 설정
        node_list = list(self.nodes.values())
        for i, node1 in enumerate(node_list):
            for node2 in node_list[i+1:]:
                if node1.is_in_range(node2.position):
                    distance = np.sqrt(sum([(a - b)**2 for a, b in 
                                          zip(node1.position, node2.position)]))
                    
                    node1.add_neighbor(node2.node_id, distance)
                    node2.add_neighbor(node1.node_id, distance)
                    
                    self.connections.append({
                        'source': node1.node_id,
                        'target': node2.node_id,
                        'distance': distance
                    })
        
        # 토폴로지 히스토리 저장
        topology_snapshot = {
            'timestamp': datetime.now(),
            'node_count': len(self.nodes),
            'connection_count': len(self.connections),
            'nodes': {nid: {'position': n.position, 'type': n.node_type} 
                     for nid, n in self.nodes.items()}
        }
        self.topology_history.append(topology_snapshot)
        
        # 히스토리 크기 제한 (최근 100개)
        if len(self.topology_history) > 100:
            self.topology_history.pop(0)
            
    def get_topology_stats(self) -> Dict[str, Any]:
        """토폴로지 통계"""
        if not self.nodes:
            return {"node_count": 0, "connection_count": 0, "avg_degree": 0}
            
        degrees = [len(node.neighbors) for node in self.nodes.values()]
        return {
            "node_count": len(self.nodes),
            "connection_count": len(self.connections),
            "avg_degree": np.mean(degrees) if degrees else 0,
            "max_degree": max(degrees) if degrees else 0,
            "min_degree": min(degrees) if degrees else 0,
            "density": len(self.connections) / (len(self.nodes) * (len(self.nodes) - 1) / 2) 
                      if len(self.nodes) > 1 else 0
        }

class SystemMonitor:
    """시스템 모니터링"""
    def __init__(self):
        self.metrics_history = []
        self.baseline_metrics = None
        self.monitoring_active = False
        
    async def collect_metrics(self) -> SystemMetrics:
        """시스템 메트릭 수집"""
        # 기본 시스템 메트릭
        cpu_usage = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        memory_usage = memory.percent
        
        # 네트워크 메트릭
        network_latency = await self._measure_network_latency()
        packet_loss = await self._measure_packet_loss()
        connection_count = len(psutil.net_connections())
        
        # 드론 특화 메트릭
        mavlink_messages = await self._count_mavlink_messages()
        qgc_status = await self._check_qgroundcontrol_status()
        gazebo_entities = await self._count_gazebo_entities()
        ns3_nodes = await self._count_ns3_nodes()
        fanet_topology = await self._get_fanet_topology_info()
        
        metrics = SystemMetrics(
            timestamp=datetime.now(),
            cpu_usage=cpu_usage,
            memory_usage=memory_usage,
            network_latency=network_latency,
            packet_loss=packet_loss,
            connection_count=connection_count,
            mavlink_messages=mavlink_messages,
            qgc_status=qgc_status,
            gazebo_entities=gazebo_entities,
            ns3_nodes=ns3_nodes,
            fanet_topology=fanet_topology
        )
        
        # 이상 점수 계산
        metrics.anomaly_score = self._calculate_anomaly_score(metrics)
        
        self.metrics_history.append(metrics)
        
        # 히스토리 크기 제한
        if len(self.metrics_history) > 1000:
            self.metrics_history.pop(0)
            
        return metrics
        
    async def _measure_network_latency(self) -> float:
        """네트워크 지연시간 측정"""
        try:
            start_time = time.time()
            # 로컬 또는 드론 IP에 핑
            subprocess.run(['ping', '-c', '1', '127.0.0.1'], 
                          capture_output=True, timeout=5)
            return (time.time() - start_time) * 1000
        except:
            return 999.0  # 타임아웃 시 높은 값
            
    async def _measure_packet_loss(self) -> float:
        """패킷 손실률 측정"""
        try:
            result = subprocess.run(['ping', '-c', '10', '127.0.0.1'], 
                                  capture_output=True, text=True, timeout=15)
            output = result.stdout
            # 패킷 손실률 파싱
            if "packet loss" in output:
                loss_line = [line for line in output.split('\n') 
                           if 'packet loss' in line][0]
                loss_percent = float(loss_line.split('%')[0].split()[-1])
                return loss_percent
        except:
            pass
        return 0.0
        
    async def _count_mavlink_messages(self) -> int:
        """MAVLink 메시지 개수 세기"""
        # MAVLink 연결이 있는 경우 메시지 수 계산
        # 실제 구현에서는 MAVLink 연결을 통해 수집
        return random.randint(50, 200)  # 시뮬레이션
        
    async def _check_qgroundcontrol_status(self) -> str:
        """QGroundControl 상태 확인"""
        try:
            # QGroundControl 프로세스 확인
            for proc in psutil.process_iter(['pid', 'name']):
                if 'qgroundcontrol' in proc.info['name'].lower():
                    return "running"
            return "stopped"
        except:
            return "unknown"
            
    async def _count_gazebo_entities(self) -> int:
        """Gazebo 엔티티 개수 세기"""
        try:
            if HAS_ROS:
                # ROS 서비스를 통해 Gazebo 모델 개수 확인
                # 실제 구현에서는 gazebo_msgs 사용
                pass
            return random.randint(1, 10)  # 시뮬레이션
        except:
            return 0
            
    async def _count_ns3_nodes(self) -> int:
        """NS-3 노드 개수 세기"""
        # NS-3 시뮬레이션에서 노드 수 확인
        # 실제 구현에서는 NS-3 API 또는 로그 파싱
        return random.randint(5, 20)  # 시뮬레이션
        
    async def _get_fanet_topology_info(self) -> Dict[str, Any]:
        """FANET 토폴로지 정보 수집"""
        return {
            "active_nodes": random.randint(3, 15),
            "total_connections": random.randint(5, 30),
            "routing_efficiency": random.uniform(0.7, 0.95),
            "network_diameter": random.randint(3, 8)
        }
        
    def _calculate_anomaly_score(self, metrics: SystemMetrics) -> float:
        """이상 점수 계산"""
        if not self.baseline_metrics:
            return 0.0
            
        score = 0.0
        
        # CPU 사용률 이상
        cpu_diff = abs(metrics.cpu_usage - self.baseline_metrics.cpu_usage)
        score += min(cpu_diff / 50.0, 1.0) * 0.2
        
        # 메모리 사용률 이상  
        mem_diff = abs(metrics.memory_usage - self.baseline_metrics.memory_usage)
        score += min(mem_diff / 30.0, 1.0) * 0.2
        
        # 네트워크 지연시간 이상
        latency_ratio = metrics.network_latency / max(self.baseline_metrics.network_latency, 1.0)
        score += min(max(latency_ratio - 1.0, 0.0), 1.0) * 0.3
        
        # 패킷 손실 이상
        score += min(metrics.packet_loss / 10.0, 1.0) * 0.3
        
        return min(score, 1.0)
        
    def set_baseline(self, metrics: SystemMetrics):
        """베이스라인 설정"""
        self.baseline_metrics = metrics
        logger.info("System baseline metrics established")

class AnomalyDetector:
    """이상 탐지 시스템"""
    def __init__(self, threshold: float = 0.7):
        self.threshold = threshold
        self.detection_rules = []
        self.alert_history = []
        self._load_detection_rules()
        
    def _load_detection_rules(self):
        """탐지 규칙 로드"""
        self.detection_rules = [
            {
                "name": "high_cpu_usage",
                "condition": lambda m: m.cpu_usage > 90,
                "severity": ThreatLevel.HIGH,
                "description": "Abnormally high CPU usage detected"
            },
            {
                "name": "high_memory_usage", 
                "condition": lambda m: m.memory_usage > 85,
                "severity": ThreatLevel.MEDIUM,
                "description": "High memory usage detected"
            },
            {
                "name": "network_latency_spike",
                "condition": lambda m: m.network_latency > 1000,
                "severity": ThreatLevel.HIGH,
                "description": "Network latency spike detected"
            },
            {
                "name": "packet_loss_high",
                "condition": lambda m: m.packet_loss > 5.0,
                "severity": ThreatLevel.MEDIUM,
                "description": "High packet loss detected"
            },
            {
                "name": "qgc_connection_lost",
                "condition": lambda m: m.qgc_status != "running",
                "severity": ThreatLevel.CRITICAL,
                "description": "QGroundControl connection lost"
            },
            {
                "name": "anomaly_score_high",
                "condition": lambda m: m.anomaly_score > 0.8,
                "severity": ThreatLevel.HIGH,
                "description": "High anomaly score detected"
            }
        ]
        
    def detect_anomalies(self, metrics: SystemMetrics) -> List[AnomalyDetectionResult]:
        """이상 탐지 수행"""
        anomalies = []
        
        for rule in self.detection_rules:
            try:
                if rule["condition"](metrics):
                    anomaly = AnomalyDetectionResult(
                        timestamp=metrics.timestamp,
                        anomaly_type=rule["name"],
                        severity=rule["severity"],
                        confidence=0.9,  # 규칙 기반은 높은 신뢰도
                        affected_modules=self._identify_affected_modules(rule["name"]),
                        metrics={
                            "cpu_usage": metrics.cpu_usage,
                            "memory_usage": metrics.memory_usage,
                            "network_latency": metrics.network_latency,
                            "anomaly_score": metrics.anomaly_score
                        },
                        description=rule["description"],
                        recommended_action=self._get_recommended_action(rule["name"])
                    )
                    anomalies.append(anomaly)
                    
            except Exception as e:
                logger.error(f"Error in anomaly detection rule {rule['name']}: {e}")
                
        # 이상 이력 저장
        self.alert_history.extend(anomalies)
        
        # 이력 크기 제한
        if len(self.alert_history) > 500:
            self.alert_history = self.alert_history[-500:]
            
        return anomalies
        
    def _identify_affected_modules(self, anomaly_type: str) -> List[SystemModule]:
        """영향받는 모듈 식별"""
        module_mapping = {
            "high_cpu_usage": [SystemModule.GAZEBO, SystemModule.NS3],
            "high_memory_usage": [SystemModule.QGROUNDCONTROL, SystemModule.GAZEBO],
            "network_latency_spike": [SystemModule.MAVLINK, SystemModule.FANET],
            "packet_loss_high": [SystemModule.FANET, SystemModule.NS3],
            "qgc_connection_lost": [SystemModule.QGROUNDCONTROL, SystemModule.MAVLINK],
            "anomaly_score_high": list(SystemModule)
        }
        return module_mapping.get(anomaly_type, [])
        
    def _get_recommended_action(self, anomaly_type: str) -> str:
        """권장 조치 반환"""
        action_mapping = {
            "high_cpu_usage": "Reduce Gazebo simulation complexity or NS-3 node count",
            "high_memory_usage": "Restart QGroundControl or reduce Gazebo models",
            "network_latency_spike": "Check network configuration and FANET routing",
            "packet_loss_high": "Optimize FANET topology or check network hardware",
            "qgc_connection_lost": "Restart QGroundControl and check MAVLink connection",
            "anomaly_score_high": "Investigate multiple system metrics for root cause"
        }
        return action_mapping.get(anomaly_type, "Manual investigation required")

class AttackIntensityController:
    """공격 강도 자동 조절기"""
    def __init__(self):
        self.current_intensity = AttackIntensity.LIGHT
        self.target_detection_rate = 0.3  # 목표 탐지율
        self.adjustment_history = []
        self.performance_metrics = {
            'detection_rate': 0.0,
            'success_rate': 0.0,
            'system_impact': 0.0
        }
        
    def adjust_intensity(self, detection_rate: float, success_rate: float, 
                        system_impact: float) -> AttackIntensity:
        """공격 강도 자동 조절"""
        self.performance_metrics.update({
            'detection_rate': detection_rate,
            'success_rate': success_rate,
            'system_impact': system_impact
        })
        
        old_intensity = self.current_intensity
        
        # 탐지율이 목표보다 높으면 강도 감소
        if detection_rate > self.target_detection_rate + 0.1:
            if self.current_intensity > AttackIntensity.RECONNAISSANCE:
                self.current_intensity = AttackIntensity(self.current_intensity - 1)
                
        # 탐지율이 목표보다 낮으면 강도 증가
        elif detection_rate < self.target_detection_rate - 0.1:
            if self.current_intensity < AttackIntensity.CRITICAL:
                self.current_intensity = AttackIntensity(self.current_intensity + 1)
                
        # 성공률이 너무 낮으면 강도 조정
        if success_rate < 0.3:
            if self.current_intensity > AttackIntensity.LIGHT:
                self.current_intensity = AttackIntensity(self.current_intensity - 1)
                
        # 시스템 영향이 너무 크면 강도 감소
        if system_impact > 0.8:
            if self.current_intensity > AttackIntensity.RECONNAISSANCE:
                self.current_intensity = AttackIntensity(self.current_intensity - 1)
        
        # 조정 이력 저장
        if old_intensity != self.current_intensity:
            self.adjustment_history.append({
                'timestamp': datetime.now(),
                'old_intensity': old_intensity,
                'new_intensity': self.current_intensity,
                'reason': f'detection_rate={detection_rate:.2f}, success_rate={success_rate:.2f}',
                'metrics': self.performance_metrics.copy()
            })
            
            logger.info(f"Attack intensity adjusted: {old_intensity.name} -> {self.current_intensity.name}")
            
        return self.current_intensity
        
    def get_intensity_parameters(self, base_config: AttackConfig) -> AttackConfig:
        """강도에 따른 공격 파라미터 조정"""
        adjusted_config = AttackConfig(**asdict(base_config))
        
        intensity_multipliers = {
            AttackIntensity.RECONNAISSANCE: {
                'duration': 0.3, 'threads': 1, 'delay': 3.0, 'stealth': True
            },
            AttackIntensity.LIGHT: {
                'duration': 0.5, 'threads': 2, 'delay': 2.0, 'stealth': True
            },
            AttackIntensity.MODERATE: {
                'duration': 1.0, 'threads': 3, 'delay': 1.0, 'stealth': False
            },
            AttackIntensity.AGGRESSIVE: {
                'duration': 1.5, 'threads': 5, 'delay': 0.5, 'stealth': False
            },
            AttackIntensity.CRITICAL: {
                'duration': 2.0, 'threads': 8, 'delay': 0.1, 'stealth': False
            }
        }
        
        multiplier = intensity_multipliers[self.current_intensity]
        
        # 지속시간 조정
        adjusted_config.duration = int(base_config.duration * multiplier['duration'])
        
        # 파라미터 조정
        adjusted_config.parameters.update({
            'max_threads': multiplier['threads'],
            'request_delay': multiplier['delay'],
            'stealth_mode': multiplier['stealth'],
            'intensity_level': self.current_intensity.value
        })
        
        return adjusted_config

class MTDTestbedOrchestrator:
    """MTD 테스트베드 오케스트레이터"""
    def __init__(self, config_path: str = "configs/mtd_config.yaml"):
        self.config_path = Path(config_path)
        self.config = self._load_config()
        
        # 컴포넌트 초기화
        self.monitor = SystemMonitor()
        self.anomaly_detector = AnomalyDetector()
        self.intensity_controller = AttackIntensityController()
        self.fanet_manager = FANETTopologyManager()
        
        # 상태 관리
        self.is_running = False
        self.active_attacks = {}
        self.mtd_actions = []
        self.attack_results = []
        
        # 실행 스레드 풀
        self.executor = ThreadPoolExecutor(max_workers=10)
        
        # 시그널 핸들러
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        # 결과 디렉토리 생성
        self.results_dir = Path("results")
        self.results_dir.mkdir(exist_ok=True)
        
        logger.info("MTD Testbed Orchestrator initialized")
        
    def _load_config(self) -> Dict[str, Any]:
        """설정 로드"""
        default_config = {
            "system": {
                "qgroundcontrol_host": "localhost",
                "qgroundcontrol_port": 14550,
                "ardupilot_host": "localhost", 
                "ardupilot_port": 14551,
                "gazebo_port": 11345,
                "ns3_port": 9999
            },
            "fanet": {
                "max_range": 1000.0,
                "node_count": 10,
                "mobility_model": "random_waypoint"
            },
            "attacks": {
                "base_duration": 60,
                "max_concurrent": 3,
                "adaptive_intensity": True
            },
            "detection": {
                "anomaly_threshold": 0.7,
                "alert_cooldown": 30
            },
            "mtd": {
                "enabled": True,
                "response_time": 10,
                "defensive_actions": ["topology_change", "frequency_hop", "encryption_rotate"]
            }
        }
        
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    config = yaml.safe_load(f)
                    default_config.update(config)
            except Exception as e:
                logger.error(f"Error loading config: {e}")
                
        return default_config
        
    def _signal_handler(self, signum, frame):
        """시그널 핸들러"""
        logger.info(f"Signal {signum} received. Shutting down...")
        self.stop()
        sys.exit(0)
        
    async def initialize_environment(self):
        """환경 초기화"""
        logger.info("Initializing MTD testbed environment...")
        
        # FANET 노드 초기화
        await self._initialize_fanet_nodes()
        
        # 시스템 연결 확인
        await self._check_system_connections()
        
        # 베이스라인 메트릭 수집
        await self._establish_baseline()
        
        logger.info("Environment initialization completed")
        
    async def _initialize_fanet_nodes(self):
        """FANET 노드 초기화"""
        node_count = self.config["fanet"]["node_count"]
        
        for i in range(node_count):
            # 랜덤 위치 생성 (3D 공간)
            position = (
                random.uniform(-5000, 5000),  # x
                random.uniform(-5000, 5000),  # y  
                random.uniform(100, 1000)     # z (고도)
            )
            
            node_type = "drone" if i < node_count - 2 else "gcs"
            node = FANETNode(f"node_{i:02d}", position, node_type)
            self.fanet_manager.add_node(node)
            
        # 초기 토폴로지 업데이트
        self.fanet_manager.update_topology()
        
        stats = self.fanet_manager.get_topology_stats()
        logger.info(f"FANET topology initialized: {stats}")
        
    async def _check_system_connections(self):
        """시스템 연결 확인"""
        checks = {
            "QGroundControl": self._check_qgc_connection(),
            "ArduPilot": self._check_ardupilot_connection(),
            "Gazebo": self._check_gazebo_connection(),
            "NS-3": self._check_ns3_connection()
        }
        
        results = {}
        for name, check in checks.items():
            try:
                results[name] = await check
            except Exception as e:
                results[name] = False
                logger.warning(f"{name} connection check failed: {e}")
                
        logger.info(f"System connection status: {results}")
        return results
        
    async def _check_qgc_connection(self) -> bool:
        """QGroundControl 연결 확인"""
        try:
            host = self.config["system"]["qgroundcontrol_host"]
            port = self.config["system"]["qgroundcontrol_port"]
            
            # TCP 소켓으로 연결 테스트
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=5.0
            )
            writer.close()
            await writer.wait_closed()
            return True
        except:
            return False
            
    async def _check_ardupilot_connection(self) -> bool:
        """ArduPilot 연결 확인"""
        try:
            if not HAS_MAVLINK:
                return False
                
            host = self.config["system"]["ardupilot_host"]
            port = self.config["system"]["ardupilot_port"]
            
            # MAVLink 연결 테스트
            connection_string = f"tcp:{host}:{port}"
            master = mavutil.mavlink_connection(connection_string, timeout=5)
            
            # Heartbeat 대기
            msg = master.recv_match(type='HEARTBEAT', blocking=True, timeout=5)
            master.close()
            
            return msg is not None
        except:
            return False
            
    async def _check_gazebo_connection(self) -> bool:
        """Gazebo 연결 확인"""
        try:
            # Gazebo 프로세스 확인
            for proc in psutil.process_iter(['pid', 'name']):
                if 'gazebo' in proc.info['name'].lower():
                    return True
            return False
        except:
            return False
            
    async def _check_ns3_connection(self) -> bool:
        """NS-3 연결 확인"""
        try:
            port = self.config["system"]["ns3_port"]
            
            # UDP 소켓으로 NS-3 시뮬레이터 확인
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(2)
            
            # 테스트 패킷 전송
            sock.sendto(b"test", ("localhost", port))
            sock.close()
            return True
        except:
            return False
            
    async def _establish_baseline(self):
        """베이스라인 메트릭 설정"""
        logger.info("Establishing baseline metrics...")
        
        # 여러 번 측정하여 평균값 사용
        metrics_samples = []
        for _ in range(5):
            metrics = await self.monitor.collect_metrics()
            metrics_samples.append(metrics)
            await asyncio.sleep(2)
            
        # 평균 메트릭 계산
        avg_metrics = SystemMetrics(
            timestamp=datetime.now(),
            cpu_usage=np.mean([m.cpu_usage for m in metrics_samples]),
            memory_usage=np.mean([m.memory_usage for m in metrics_samples]),
            network_latency=np.mean([m.network_latency for m in metrics_samples]),
            packet_loss=np.mean([m.packet_loss for m in metrics_samples]),
            connection_count=int(np.mean([m.connection_count for m in metrics_samples])),
            mavlink_messages=int(np.mean([m.mavlink_messages for m in metrics_samples])),
            qgc_status="running",  # 가장 일반적인 상태
            gazebo_entities=int(np.mean([m.gazebo_entities for m in metrics_samples])),
            ns3_nodes=int(np.mean([m.ns3_nodes for m in metrics_samples])),
            fanet_topology=metrics_samples[0].fanet_topology
        )
        
        self.monitor.set_baseline(avg_metrics)
        logger.info("Baseline metrics established successfully")
        
    async def run_adaptive_attack_campaign(self, duration_minutes: int = 30):
        """적응형 공격 캠페인 실행"""
        logger.info(f"Starting adaptive attack campaign for {duration_minutes} minutes")
        
        self.is_running = True
        end_time = datetime.now() + timedelta(minutes=duration_minutes)
        
        # 공격 설정 로드
        attack_configs = self._load_attack_configs()
        
        try:
            # 모니터링 태스크 시작
            monitoring_task = asyncio.create_task(self._monitoring_loop())
            
            # 메인 공격 루프
            cycle_count = 0
            while self.is_running and datetime.now() < end_time:
                cycle_count += 1
                logger.info(f"Starting attack cycle {cycle_count}")
                
                # 현재 강도에 맞는 공격 선택 및 실행
                selected_attacks = self._select_attacks_for_intensity(
                    attack_configs, 
                    self.intensity_controller.current_intensity
                )
                
                # 공격 실행
                cycle_results = await self._execute_attack_cycle(selected_attacks)
                self.attack_results.extend(cycle_results)
                
                # 강도 조절
                await self._adjust_attack_intensity(cycle_results)
                
                # MTD 액션 실행
                if self.config["mtd"]["enabled"]:
                    await self._execute_mtd_actions()
                
                # FANET 토폴로지 업데이트
                await self._update_fanet_topology()
                
                # 사이클 간 대기
                await asyncio.sleep(30)
                
            # 모니터링 종료
            monitoring_task.cancel()
            
        except Exception as e:
            logger.error(f"Error in attack campaign: {e}")
        finally:
            await self._cleanup()
            
        # 최종 보고서 생성
        await self._generate_final_report()
        
    def _load_attack_configs(self) -> List[AttackConfig]:
        """공격 설정 로드"""
        base_dir = Path("/home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks")
        
        configs = [
            # 정찰 공격
            AttackConfig(
                name="wifi_network_discovery",
                category=AttackCategory.RECONNAISSANCE,
                intensity=AttackIntensity.LIGHT,
                target_modules=[SystemModule.FANET],
                duration=30,
                script_path=str(base_dir / "reconnaissance" / "wifi_discovery.sh"),
                parameters={"scan_type": "passive", "max_targets": 50}
            ),
            AttackConfig(
                name="mavlink_service_discovery", 
                category=AttackCategory.RECONNAISSANCE,
                intensity=AttackIntensity.MODERATE,
                target_modules=[SystemModule.MAVLINK, SystemModule.ARDUPILOT],
                duration=45,
                script_path=str(base_dir / "reconnaissance" / "mavlink_discovery.sh"),
                parameters={"port_range": "14550-14560", "timeout": 5}
            ),
            
            # 프로토콜 변조
            AttackConfig(
                name="gps_spoofing",
                category=AttackCategory.PROTOCOL_TAMPERING,
                intensity=AttackIntensity.AGGRESSIVE,
                target_modules=[SystemModule.ARDUPILOT, SystemModule.GAZEBO],
                duration=60,
                script_path=str(base_dir / "protocol_tampering" / "gps_spoofing.sh"),
                parameters={"spoof_latitude": 37.7749, "spoof_longitude": -122.4194}
            ),
            AttackConfig(
                name="mavlink_injection",
                category=AttackCategory.PROTOCOL_TAMPERING,
                intensity=AttackIntensity.AGGRESSIVE,
                target_modules=[SystemModule.MAVLINK, SystemModule.QGROUNDCONTROL],
                duration=45,
                script_path=str(base_dir / "protocol_tampering" / "mavlink_injection.sh"),
                parameters={"injection_rate": 10, "message_type": "COMMAND_LONG"}
            ),
            
            # 서비스 거부
            AttackConfig(
                name="communication_flood",
                category=AttackCategory.DENIAL_OF_SERVICE,
                intensity=AttackIntensity.CRITICAL,
                target_modules=[SystemModule.FANET, SystemModule.NS3],
                duration=30,
                script_path=str(base_dir / "denial_of_service" / "communication_flood.sh"),
                parameters={"flood_rate": 1000, "packet_size": 1024}
            ),
            AttackConfig(
                name="wifi_deauth",
                category=AttackCategory.DENIAL_OF_SERVICE,
                intensity=AttackIntensity.AGGRESSIVE,
                target_modules=[SystemModule.FANET],
                duration=20,
                script_path=str(base_dir / "denial_of_service" / "wifi_deauth.sh"),
                parameters={"target_bssid": "auto", "deauth_count": 100}
            ),
            
            # 주입 공격
            AttackConfig(
                name="waypoint_injection",
                category=AttackCategory.INJECTION,
                intensity=AttackIntensity.AGGRESSIVE,
                target_modules=[SystemModule.QGROUNDCONTROL, SystemModule.ARDUPILOT],
                duration=40,
                script_path=str(base_dir / "injection" / "waypoint_injection.sh"),
                parameters={"waypoint_count": 5, "dangerous_zones": True}
            ),
            
            # 네트워크 방해
            AttackConfig(
                name="fanet_routing_attack",
                category=AttackCategory.NETWORK_DISRUPTION,
                intensity=AttackIntensity.MODERATE,
                target_modules=[SystemModule.FANET, SystemModule.NS3],
                duration=60,
                script_path=str(base_dir / "network_disruption" / "routing_attack.sh"),
                parameters={"attack_type": "blackhole", "affected_nodes": 3}
            ),
            
            # MTD 회피
            AttackConfig(
                name="mtd_evasion",
                category=AttackCategory.MTD_EVASION,
                intensity=AttackIntensity.CRITICAL,
                target_modules=list(SystemModule),
                duration=90,
                script_path=str(base_dir / "mtd_evasion" / "adaptive_attack.sh"),
                parameters={"evasion_techniques": ["timing_variation", "pattern_randomization"]}
            )
        ]
        
        return configs
        
    def _select_attacks_for_intensity(self, configs: List[AttackConfig], 
                                    intensity: AttackIntensity) -> List[AttackConfig]:
        """강도에 맞는 공격 선택"""
        # 현재 강도 이하의 공격들만 선택
        suitable_attacks = [c for c in configs if c.intensity.value <= intensity.value]
        
        # 강도에 따른 동시 공격 수 결정
        max_concurrent = {
            AttackIntensity.RECONNAISSANCE: 1,
            AttackIntensity.LIGHT: 2,
            AttackIntensity.MODERATE: 3,
            AttackIntensity.AGGRESSIVE: 4,
            AttackIntensity.CRITICAL: 5
        }[intensity]
        
        # 가중치 기반 선택 (카테고리 다양성 고려)
        selected = []
        used_categories = set()
        
        for _ in range(min(max_concurrent, len(suitable_attacks))):
            # 아직 사용되지 않은 카테고리 우선
            candidates = [a for a in suitable_attacks 
                         if a not in selected and a.category not in used_categories]
            
            if not candidates:
                candidates = [a for a in suitable_attacks if a not in selected]
                
            if candidates:
                attack = random.choice(candidates)
                selected.append(attack)
                used_categories.add(attack.category)
                
        return selected
        
    async def _execute_attack_cycle(self, attack_configs: List[AttackConfig]) -> List[Dict[str, Any]]:
        """공격 사이클 실행"""
        logger.info(f"Executing {len(attack_configs)} attacks in parallel")
        
        # 강도에 맞게 설정 조정
        adjusted_configs = []
        for config in attack_configs:
            adjusted = self.intensity_controller.get_intensity_parameters(config)
            adjusted_configs.append(adjusted)
            
        # 병렬 공격 실행
        tasks = []
        for config in adjusted_configs:
            task = asyncio.create_task(self._execute_single_attack(config))
            tasks.append(task)
            
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 결과 정리
        cycle_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Attack {adjusted_configs[i].name} failed: {result}")
                cycle_results.append({
                    "attack_name": adjusted_configs[i].name,
                    "success": False,
                    "error": str(result),
                    "execution_time": 0,
                    "timestamp": datetime.now()
                })
            else:
                cycle_results.append(result)
                
        return cycle_results
        
    async def _execute_single_attack(self, config: AttackConfig) -> Dict[str, Any]:
        """단일 공격 실행"""
        start_time = datetime.now()
        
        try:
            # 공격 스크립트 실행
            cmd = self._build_attack_command(config)
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=Path(config.script_path).parent
            )
            
            # 타임아웃과 함께 실행
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=config.duration + 30
            )
            
            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds()
            
            # 성공 여부 판단
            success = process.returncode == 0
            
            # IOC 추출
            iocs = self._extract_iocs(stdout.decode(), stderr.decode())
            
            result = {
                "attack_name": config.name,
                "category": config.category.value,
                "intensity": config.intensity.value,
                "success": success,
                "execution_time": execution_time,
                "return_code": process.returncode,
                "stdout": stdout.decode()[:1000],  # 크기 제한
                "stderr": stderr.decode()[:1000],
                "iocs": iocs,
                "timestamp": start_time,
                "target_modules": [m.value for m in config.target_modules]
            }
            
            logger.info(f"Attack {config.name} completed: success={success}, time={execution_time:.2f}s")
            return result
            
        except asyncio.TimeoutError:
            logger.warning(f"Attack {config.name} timed out")
            return {
                "attack_name": config.name,
                "success": False,
                "error": "timeout",
                "execution_time": config.duration,
                "timestamp": start_time
            }
            
        except Exception as e:
            logger.error(f"Attack {config.name} failed: {e}")
            return {
                "attack_name": config.name,
                "success": False,
                "error": str(e),
                "execution_time": 0,
                "timestamp": start_time
            }
            
    def _build_attack_command(self, config: AttackConfig) -> List[str]:
        """공격 명령 구성"""
        cmd = ["bash", config.script_path]
        
        # 강도별 옵션
        if config.intensity >= AttackIntensity.AGGRESSIVE:
            cmd.extend(["--aggressive", "--no-stealth"])
        elif config.intensity <= AttackIntensity.LIGHT:
            cmd.extend(["--stealth", "--minimal"])
            
        # 지속시간 설정
        cmd.extend(["--duration", str(config.duration)])
        
        # 추가 파라미터
        for key, value in config.parameters.items():
            cmd.extend([f"--{key}", str(value)])
            
        return cmd
        
    def _extract_iocs(self, stdout: str, stderr: str) -> List[str]:
        """IOC 추출"""
        import re
        
        iocs = []
        text = stdout + stderr
        
        # IP 주소
        ip_pattern = r'\b(?:\d{1,3}\.){3}\d{1,3}\b'
        iocs.extend(re.findall(ip_pattern, text))
        
        # MAC 주소
        mac_pattern = r'\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b'
        iocs.extend(re.findall(mac_pattern, text))
        
        # URL/도메인
        url_pattern = r'https?://[^\s<>"\'{}|\\^`\[\]]+'
        iocs.extend(re.findall(url_pattern, text))
        
        return list(set(iocs))  # 중복 제거
        
    async def _monitoring_loop(self):
        """모니터링 루프"""
        logger.info("Starting monitoring loop")
        
        while self.is_running:
            try:
                # 메트릭 수집
                metrics = await self.monitor.collect_metrics()
                
                # 이상 탐지
                anomalies = self.anomaly_detector.detect_anomalies(metrics)
                
                if anomalies:
                    for anomaly in anomalies:
                        logger.warning(f"Anomaly detected: {anomaly.anomaly_type} "
                                     f"(severity: {anomaly.severity.value})")
                        
                        # 심각한 이상 발생 시 대응
                        if anomaly.severity in [ThreatLevel.HIGH, ThreatLevel.CRITICAL]:
                            await self._respond_to_anomaly(anomaly)
                            
                # 모니터링 간격
                await asyncio.sleep(10)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(5)
                
    async def _respond_to_anomaly(self, anomaly: AnomalyDetectionResult):
        """이상 상황 대응"""
        logger.info(f"Responding to anomaly: {anomaly.anomaly_type}")
        
        # 공격 강도 자동 감소
        if anomaly.severity == ThreatLevel.CRITICAL:
            self.intensity_controller.current_intensity = AttackIntensity.RECONNAISSANCE
            logger.info("Attack intensity reduced to RECONNAISSANCE due to critical anomaly")
            
        # MTD 액션 트리거
        if self.config["mtd"]["enabled"]:
            mtd_action = MTDAction(
                action_type="emergency_response",
                target_module=anomaly.affected_modules[0] if anomaly.affected_modules else SystemModule.FANET,
                parameters={"anomaly_type": anomaly.anomaly_type, "severity": anomaly.severity.value},
                timestamp=datetime.now()
            )
            
            await self._execute_mtd_action(mtd_action)
            
    async def _adjust_attack_intensity(self, cycle_results: List[Dict[str, Any]]):
        """공격 강도 조절"""
        if not cycle_results:
            return
            
        # 성공률 계산
        success_count = sum(1 for r in cycle_results if r.get("success", False))
        success_rate = success_count / len(cycle_results)
        
        # 탐지율 계산 (최근 이상 탐지 기록 기반)
        recent_anomalies = [a for a in self.anomaly_detector.alert_history 
                           if (datetime.now() - a.timestamp).total_seconds() < 300]
        detection_rate = len(recent_anomalies) / len(cycle_results) if cycle_results else 0
        
        # 시스템 영향도 계산
        recent_metrics = self.monitor.metrics_history[-5:] if self.monitor.metrics_history else []
        system_impact = np.mean([m.anomaly_score for m in recent_metrics]) if recent_metrics else 0
        
        # 강도 조절 수행
        new_intensity = self.intensity_controller.adjust_intensity(
            detection_rate, success_rate, system_impact
        )
        
        logger.info(f"Intensity adjustment: success_rate={success_rate:.2f}, "
                   f"detection_rate={detection_rate:.2f}, system_impact={system_impact:.2f}")
                   
    async def _execute_mtd_actions(self):
        """MTD 액션 실행"""
        defensive_actions = self.config["mtd"]["defensive_actions"]
        
        for action_type in defensive_actions:
            if random.random() < 0.3:  # 30% 확률로 실행
                mtd_action = MTDAction(
                    action_type=action_type,
                    target_module=random.choice(list(SystemModule)),
                    parameters=self._get_mtd_parameters(action_type),
                    timestamp=datetime.now()
                )
                
                await self._execute_mtd_action(mtd_action)
                
    def _get_mtd_parameters(self, action_type: str) -> Dict[str, Any]:
        """MTD 파라미터 생성"""
        parameter_map = {
            "topology_change": {
                "new_topology": "random",
                "node_count": random.randint(5, 15),
                "connection_probability": random.uniform(0.3, 0.8)
            },
            "frequency_hop": {
                "new_frequency": random.choice([2400, 2450, 2500, 5200, 5500, 5800]),
                "hop_interval": random.uniform(1.0, 5.0)
            },
            "encryption_rotate": {
                "new_key": "".join(random.choices("0123456789ABCDEF", k=32)),
                "encryption_type": random.choice(["AES256", "ChaCha20"])
            }
        }
        
        return parameter_map.get(action_type, {})
        
    async def _execute_mtd_action(self, action: MTDAction):
        """MTD 액션 실행"""
        logger.info(f"Executing MTD action: {action.action_type} on {action.target_module.value}")
        
        try:
            if action.action_type == "topology_change":
                await self._change_fanet_topology(action.parameters)
            elif action.action_type == "frequency_hop":
                await self._perform_frequency_hop(action.parameters)
            elif action.action_type == "encryption_rotate":
                await self._rotate_encryption(action.parameters)
            elif action.action_type == "emergency_response":
                await self._emergency_response(action.parameters)
                
            action.success = True
            logger.info(f"MTD action {action.action_type} completed successfully")
            
        except Exception as e:
            action.success = False
            logger.error(f"MTD action {action.action_type} failed: {e}")
            
        self.mtd_actions.append(action)
        
    async def _change_fanet_topology(self, parameters: Dict[str, Any]):
        """FANET 토폴로지 변경"""
        new_node_count = parameters.get("node_count", 10)
        
        # 기존 노드 일부 제거
        current_nodes = list(self.fanet_manager.nodes.keys())
        remove_count = max(0, len(current_nodes) - new_node_count)
        
        for i in range(remove_count):
            node_to_remove = random.choice(current_nodes)
            self.fanet_manager.remove_node(node_to_remove)
            current_nodes.remove(node_to_remove)
            
        # 새 노드 추가
        add_count = max(0, new_node_count - len(current_nodes))
        
        for i in range(add_count):
            position = (
                random.uniform(-5000, 5000),
                random.uniform(-5000, 5000), 
                random.uniform(100, 1000)
            )
            
            node_id = f"mtd_node_{int(time.time())}_{i}"
            node = FANETNode(node_id, position, "drone")
            self.fanet_manager.add_node(node)
            
        # 토폴로지 업데이트
        self.fanet_manager.update_topology()
        
    async def _perform_frequency_hop(self, parameters: Dict[str, Any]):
        """주파수 호핑"""
        new_frequency = parameters.get("new_frequency", 2400)
        logger.info(f"Frequency hopped to {new_frequency} MHz")
        
        # 실제 구현에서는 물리적 주파수 변경
        await asyncio.sleep(0.1)  # 시뮬레이션
        
    async def _rotate_encryption(self, parameters: Dict[str, Any]):
        """암호화 키 교체"""
        new_key = parameters.get("new_key", "default_key")
        encryption_type = parameters.get("encryption_type", "AES256")
        
        logger.info(f"Encryption rotated: {encryption_type}")
        
        # 실제 구현에서는 암호화 키 갱신
        await asyncio.sleep(0.1)  # 시뮬레이션
        
    async def _emergency_response(self, parameters: Dict[str, Any]):
        """응급 대응"""
        anomaly_type = parameters.get("anomaly_type", "unknown")
        
        # 모든 공격 중지
        self.intensity_controller.current_intensity = AttackIntensity.RECONNAISSANCE
        
        # 시스템 복구 시도
        logger.info(f"Emergency response for {anomaly_type}: reducing attack intensity")
        
    async def _update_fanet_topology(self):
        """FANET 토폴로지 주기적 업데이트"""
        # 노드 위치 이동 (모빌리티 시뮬레이션)
        for node in self.fanet_manager.nodes.values():
            if random.random() < 0.3:  # 30% 확률로 이동
                # 기존 위치에서 약간 이동
                x, y, z = node.position
                new_position = (
                    x + random.uniform(-100, 100),
                    y + random.uniform(-100, 100),
                    max(50, z + random.uniform(-50, 50))  # 최소 고도 유지
                )
                node.update_position(new_position)
                
        # 토폴로지 업데이트
        self.fanet_manager.update_topology()
        
    async def _cleanup(self):
        """정리 작업"""
        logger.info("Performing cleanup...")
        
        self.is_running = False
        
        # 활성 공격 중지
        for attack_name, process in self.active_attacks.items():
            try:
                process.terminate()
                await asyncio.wait_for(process.wait(), timeout=5)
            except:
                try:
                    process.kill()
                except:
                    pass
                    
        self.active_attacks.clear()
        
        # 스레드 풀 종료
        self.executor.shutdown(wait=False)
        
    async def _generate_final_report(self):
        """최종 보고서 생성"""
        logger.info("Generating final report...")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = self.results_dir / f"mtd_testbed_report_{timestamp}.json"
        
        # 통계 계산
        total_attacks = len(self.attack_results)
        successful_attacks = sum(1 for r in self.attack_results if r.get("success", False))
        total_anomalies = len(self.anomaly_detector.alert_history)
        mtd_actions_count = len(self.mtd_actions)
        
        # 카테고리별 성공률
        category_stats = {}
        for result in self.attack_results:
            category = result.get("category", "unknown")
            if category not in category_stats:
                category_stats[category] = {"total": 0, "success": 0}
            category_stats[category]["total"] += 1
            if result.get("success", False):
                category_stats[category]["success"] += 1
                
        # 강도 조절 이력
        intensity_history = self.intensity_controller.adjustment_history
        
        # FANET 토폴로지 통계
        fanet_stats = self.fanet_manager.get_topology_stats()
        
        # 최종 보고서 구성
        report = {
            "metadata": {
                "generation_time": datetime.now().isoformat(),
                "testbed_version": "1.0.0",
                "campaign_duration": len(self.attack_results) * 60,  # 추정
                "configuration": self.config
            },
            "summary": {
                "total_attacks_executed": total_attacks,
                "successful_attacks": successful_attacks,
                "success_rate": successful_attacks / total_attacks if total_attacks > 0 else 0,
                "total_anomalies_detected": total_anomalies,
                "detection_rate": total_anomalies / total_attacks if total_attacks > 0 else 0,
                "mtd_actions_executed": mtd_actions_count,
                "final_attack_intensity": self.intensity_controller.current_intensity.name
            },
            "attack_analysis": {
                "by_category": {
                    cat: {
                        "success_rate": stats["success"] / stats["total"] if stats["total"] > 0 else 0,
                        **stats
                    } for cat, stats in category_stats.items()
                },
                "intensity_adjustments": len(intensity_history),
                "intensity_history": [
                    {
                        "timestamp": adj["timestamp"].isoformat(),
                        "old_intensity": adj["old_intensity"].name,
                        "new_intensity": adj["new_intensity"].name,
                        "reason": adj["reason"]
                    } for adj in intensity_history
                ]
            },
            "system_performance": {
                "baseline_metrics": asdict(self.monitor.baseline_metrics) if self.monitor.baseline_metrics else {},
                "final_metrics": asdict(self.monitor.metrics_history[-1]) if self.monitor.metrics_history else {},
                "anomaly_events": [
                    {
                        "timestamp": anomaly.timestamp.isoformat(),
                        "type": anomaly.anomaly_type,
                        "severity": anomaly.severity.value,
                        "confidence": anomaly.confidence,
                        "description": anomaly.description
                    } for anomaly in self.anomaly_detector.alert_history
                ]
            },
            "fanet_analysis": {
                "final_topology": fanet_stats,
                "topology_changes": len(self.fanet_manager.topology_history),
                "node_mobility": {
                    "active_nodes": len(self.fanet_manager.nodes),
                    "average_connections": fanet_stats.get("avg_degree", 0),
                    "network_density": fanet_stats.get("density", 0)
                }
            },
            "mtd_effectiveness": {
                "total_actions": mtd_actions_count,
                "successful_actions": sum(1 for action in self.mtd_actions if action.success),
                "action_types": {
                    action_type: sum(1 for action in self.mtd_actions if action.action_type == action_type)
                    for action_type in set(action.action_type for action in self.mtd_actions)
                },
                "response_times": [
                    (action.timestamp - anomaly.timestamp).total_seconds()
                    for action in self.mtd_actions
                    for anomaly in self.anomaly_detector.alert_history
                    if abs((action.timestamp - anomaly.timestamp).total_seconds()) < 60
                ]
            },
            "detailed_results": {
                "attack_results": self.attack_results,
                "mtd_actions": [
                    {
                        "timestamp": action.timestamp.isoformat(),
                        "action_type": action.action_type,
                        "target_module": action.target_module.value,
                        "success": action.success,
                        "parameters": action.parameters
                    } for action in self.mtd_actions
                ]
            },
            "recommendations": self._generate_recommendations(
                successful_attacks / total_attacks if total_attacks > 0 else 0,
                total_anomalies / total_attacks if total_attacks > 0 else 0,
                mtd_actions_count
            )
        }
        
        # JSON 파일로 저장
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)
            
        # Markdown 요약 보고서 생성
        md_report_file = self.results_dir / f"mtd_testbed_summary_{timestamp}.md"
        await self._generate_markdown_report(report, md_report_file)
        
        logger.info(f"Final report generated: {report_file}")
        logger.info(f"Summary report generated: {md_report_file}")
        
    def _generate_recommendations(self, success_rate: float, detection_rate: float, 
                                mtd_actions: int) -> List[str]:
        """권장사항 생성"""
        recommendations = []
        
        # 성공률 기반 권장사항
        if success_rate < 0.3:
            recommendations.append(
                "공격 성공률이 낮습니다. 공격 스크립트 또는 대상 시스템 설정을 확인하세요."
            )
        elif success_rate > 0.8:
            recommendations.append(
                "공격 성공률이 높습니다. 방어 시스템 강화를 고려하세요."
            )
            
        # 탐지율 기반 권장사항
        if detection_rate < 0.2:
            recommendations.append(
                "이상 탐지율이 낮습니다. 탐지 시스템의 민감도를 높이거나 새로운 탐지 규칙을 추가하세요."
            )
        elif detection_rate > 0.7:
            recommendations.append(
                "이상 탐지율이 높습니다. 오탐을 줄이기 위해 탐지 임계값을 조정하세요."
            )
            
        # MTD 효율성 기반 권장사항
        if mtd_actions < 5:
            recommendations.append(
                "MTD 액션 실행 횟수가 적습니다. 더 적극적인 방어 전략을 고려하세요."
            )
            
        # 일반적인 권장사항
        recommendations.extend([
            "FANET 토폴로지의 동적 변화가 공격 성공률에 미치는 영향을 분석하세요.",
            "다양한 공격 강도에서의 시스템 성능을 비교 분석하세요.",
            "실제 드론 환경에서의 검증을 위해 하드웨어 테스트를 수행하세요.",
            "논문 작성을 위해 통계적 유의성을 확보할 수 있는 충분한 실험 데이터를 수집하세요."
        ])
        
        return recommendations
        
    async def _generate_markdown_report(self, report: Dict[str, Any], output_file: Path):
        """Markdown 요약 보고서 생성"""
        md_content = f"""# 드론 MTD 테스트베드 실험 보고서

## 📊 실험 개요

- **실험 일시**: {report['metadata']['generation_time']}
- **테스트베드 버전**: {report['metadata']['testbed_version']}
- **추정 실험 시간**: {report['metadata']['campaign_duration']} 초

## 🎯 주요 결과

### 공격 성능
- **총 공격 수행**: {report['summary']['total_attacks_executed']}회
- **성공한 공격**: {report['summary']['successful_attacks']}회
- **전체 성공률**: {report['summary']['success_rate']:.1%}

### 탐지 성능  
- **이상 탐지 건수**: {report['summary']['total_anomalies_detected']}건
- **탐지율**: {report['summary']['detection_rate']:.1%}

### MTD 성능
- **MTD 액션 실행**: {report['summary']['mtd_actions_executed']}회
- **최종 공격 강도**: {report['summary']['final_attack_intensity']}

## 📈 상세 분석

### 공격 카테고리별 성공률
"""
        
        # 카테고리별 성공률 표
        for category, stats in report['attack_analysis']['by_category'].items():
            md_content += f"- **{category}**: {stats['success_rate']:.1%} ({stats['success']}/{stats['total']})\n"
            
        md_content += f"""
### 공격 강도 조절 이력
- **조정 횟수**: {report['attack_analysis']['intensity_adjustments']}회

"""
        
        # 강도 조절 이력
        for adj in report['attack_analysis']['intensity_history'][-5:]:  # 최근 5개만
            md_content += f"- {adj['timestamp']}: {adj['old_intensity']} → {adj['new_intensity']} ({adj['reason']})\n"
            
        md_content += f"""
## 🌐 FANET 네트워크 분석

### 최종 토폴로지 상태
- **활성 노드 수**: {report['fanet_analysis']['node_mobility']['active_nodes']}개
- **평균 연결 수**: {report['fanet_analysis']['node_mobility']['average_connections']:.1f}
- **네트워크 밀도**: {report['fanet_analysis']['node_mobility']['network_density']:.3f}
- **토폴로지 변경 횟수**: {report['fanet_analysis']['topology_changes']}회

## 🛡️ MTD 효율성 분석

### MTD 액션 유형별 실행 횟수
"""
        
        # MTD 액션 통계
        for action_type, count in report['mtd_effectiveness']['action_types'].items():
            md_content += f"- **{action_type}**: {count}회\n"
            
        md_content += f"""
### 평균 대응 시간
- **MTD 대응 시간**: {np.mean(report['mtd_effectiveness']['response_times']) if report['mtd_effectiveness']['response_times'] else 0:.2f}초

## 🚨 이상 탐지 분석

### 심각도별 이상 탐지 건수
"""
        
        # 심각도별 통계
        severity_counts = {}
        for anomaly in report['system_performance']['anomaly_events']:
            severity = anomaly['severity']
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
            
        for severity, count in severity_counts.items():
            md_content += f"- **{severity}**: {count}건\n"
            
        md_content += f"""
## 💡 권장사항

"""
        
        # 권장사항
        for i, recommendation in enumerate(report['recommendations'], 1):
            md_content += f"{i}. {recommendation}\n"
            
        md_content += f"""
## 📋 시스템 설정

### 테스트베드 구성
- **QGroundControl**: {report['metadata']['configuration']['system']['qgroundcontrol_host']}:{report['metadata']['configuration']['system']['qgroundcontrol_port']}
- **ArduPilot**: {report['metadata']['configuration']['system']['ardupilot_host']}:{report['metadata']['configuration']['system']['ardupilot_port']}
- **Gazebo 포트**: {report['metadata']['configuration']['system']['gazebo_port']}
- **NS-3 포트**: {report['metadata']['configuration']['system']['ns3_port']}

### FANET 설정
- **최대 통신 범위**: {report['metadata']['configuration']['fanet']['max_range']}m
- **초기 노드 수**: {report['metadata']['configuration']['fanet']['node_count']}개
- **모빌리티 모델**: {report['metadata']['configuration']['fanet']['mobility_model']}

---

*이 보고서는 드론 MTD 테스트베드 시스템에서 자동 생성되었습니다.*
*논문 작성 시 상세한 통계 분석을 위해 JSON 형식의 원본 데이터를 참조하세요.*
"""
        
        # 파일 저장
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(md_content)
            
    def stop(self):
        """테스트베드 중지"""
        logger.info("Stopping MTD testbed...")
        self.is_running = False

# NS-3 시뮬레이션 인터페이스
class NS3SimulationInterface:
    """NS-3 시뮬레이션 인터페이스"""
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.simulation_process = None
        self.is_running = False
        
    async def start_simulation(self, scenario: str = "fanet_basic"):
        """시뮬레이션 시작"""
        logger.info(f"Starting NS-3 simulation: {scenario}")
        
        # NS-3 시뮬레이션 스크립트 생성
        script_content = self._generate_ns3_script(scenario)
        script_path = Path("ns3_simulation.cc")
        
        with open(script_path, 'w') as f:
            f.write(script_content)
            
        # 시뮬레이션 실행
        try:
            cmd = ["./waf", "--run", f"scratch/{script_path.stem}"]
            self.simulation_process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd="/usr/local/ns-3"  # NS-3 설치 경로
            )
            
            self.is_running = True
            logger.info("NS-3 simulation started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start NS-3 simulation: {e}")
            
    def _generate_ns3_script(self, scenario: str) -> str:
        """NS-3 시뮬레이션 스크립트 생성"""
        return f'''
/* FANET 시뮬레이션 스크립트 - {scenario} */

#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/internet-module.h"
#include "ns3/mobility-module.h"
#include "ns3/wifi-module.h"
#include "ns3/applications-module.h"
#include "ns3/netanim-module.h"

using namespace ns3;

NS_LOG_COMPONENT_DEFINE ("FANETSimulation");

int main (int argc, char *argv[])
{{
    // 시뮬레이션 파라미터
    uint32_t nNodes = {self.config.get("fanet", {}).get("node_count", 10)};
    double simTime = 300.0;  // 5분
    double range = {self.config.get("fanet", {}).get("max_range", 1000.0)};
    
    // 노드 생성
    NodeContainer nodes;
    nodes.Create (nNodes);
    
    // WiFi 설정
    WifiHelper wifi;
    wifi.SetStandard (WIFI_STANDARD_80211n);
    
    WifiMacHelper mac;
    mac.SetType ("ns3::AdhocWifiMac");
    
    YansWifiPhyHelper phy;
    YansWifiChannelHelper channel = YansWifiChannelHelper::Default ();
    phy.SetChannel (channel.Create ());
    
    NetDeviceContainer devices = wifi.Install (phy, mac, nodes);
    
    // 모빌리티 모델
    MobilityHelper mobility;
    mobility.SetPositionAllocator ("ns3::RandomBoxPositionAllocator",
                                   "X", StringValue ("ns3::UniformRandomVariable[Min=-5000|Max=5000]"),
                                   "Y", StringValue ("ns3::UniformRandomVariable[Min=-5000|Max=5000]"),
                                   "Z", StringValue ("ns3::UniformRandomVariable[Min=100|Max=1000]"));
    
    mobility.SetMobilityModel ("ns3::RandomWaypointMobilityModel",
                               "Speed", StringValue ("ns3::UniformRandomVariable[Min=10|Max=50]"),
                               "Pause", StringValue ("ns3::ConstantRandomVariable[Constant=2.0]"),
                               "PositionAllocator", StringValue ("ns3::RandomBoxPositionAllocator"));
    
    mobility.Install (nodes);
    
    // 인터넷 스택
    InternetStackHelper internet;
    internet.Install (nodes);
    
    // IP 주소 할당
    Ipv4AddressHelper address;
    address.SetBase ("10.1.1.0", "255.255.255.0");
    Ipv4InterfaceContainer interfaces = address.Assign (devices);
    
    // 애플리케이션 설정 (ping)
    V4PingHelper ping (interfaces.GetAddress (nNodes - 1));
    ping.SetAttribute ("Verbose", BooleanValue (true));
    ApplicationContainer apps = ping.Install (nodes.Get (0));
    apps.Start (Seconds (1.0));
    apps.Stop (Seconds (simTime));
    
    // 시뮬레이션 실행
    Simulator::Stop (Seconds (simTime));
    Simulator::Run ();
    Simulator::Destroy ();
    
    return 0;
}}
'''
        
    async def stop_simulation(self):
        """시뮬레이션 중지"""
        if self.simulation_process and self.is_running:
            self.simulation_process.terminate()
            await self.simulation_process.wait()
            self.is_running = False
            logger.info("NS-3 simulation stopped")

# Gazebo 시뮬레이션 인터페이스
class GazeboInterface:
    """Gazebo 시뮬레이션 인터페이스"""
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.gazebo_process = None
        self.is_running = False
        
    async def start_gazebo(self, world_file: str = "iris_mtd_world.world"):
        """Gazebo 시작"""
        logger.info(f"Starting Gazebo with world: {world_file}")
        
        try:
            # Gazebo 월드 파일 생성
            world_content = self._generate_world_file()
            world_path = Path(f"/tmp/{world_file}")
            
            with open(world_path, 'w') as f:
                f.write(world_content)
                
            # Gazebo 실행
            cmd = ["gazebo", "--verbose", str(world_path)]
            self.gazebo_process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            self.is_running = True
            logger.info("Gazebo started successfully")
            
            # 드론 모델 스폰
            await self._spawn_drone_models()
            
        except Exception as e:
            logger.error(f"Failed to start Gazebo: {e}")
            
    def _generate_world_file(self) -> str:
        """Gazebo 월드 파일 생성"""
        return '''<?xml version="1.0" ?>
<sdf version="1.6">
  <world name="mtd_test_world">
    <include>
      <uri>model://ground_plane</uri>
    </include>
    
    <include>
      <uri>model://sun</uri>
    </include>
    
    <!-- 드론 테스트를 위한 환경 -->
    <model name="test_area">
      <static>true</static>
      <pose>0 0 0 0 0 0</pose>
      <link name="test_area_link">
        <visual name="test_area_visual">
          <geometry>
            <box>
              <size>100 100 0.1</size>
            </box>
          </geometry>
          <material>
            <ambient>0.2 0.8 0.2 1</ambient>
            <diffuse>0.2 0.8 0.2 1</diffuse>
          </material>
        </visual>
      </link>
    </model>
    
    <!-- 장애물 -->
    <model name="obstacle_1">
      <static>true</static>
      <pose>20 20 2.5 0 0 0</pose>
      <link name="obstacle_link">
        <visual name="obstacle_visual">
          <geometry>
            <box>
              <size>5 5 5</size>
            </box>
          </geometry>
          <material>
            <ambient>0.8 0.2 0.2 1</ambient>
            <diffuse>0.8 0.2 0.2 1</diffuse>
          </material>
        </visual>
        <collision name="obstacle_collision">
          <geometry>
            <box>
              <size>5 5 5</size>
            </box>
          </geometry>
        </collision>
      </link>
    </model>
  </world>
</sdf>'''
        
    async def _spawn_drone_models(self):
        """드론 모델 스폰"""
        drone_count = self.config.get("fanet", {}).get("node_count", 3)
        
        for i in range(min(drone_count, 5)):  # 최대 5대까지
            x = random.uniform(-40, 40)
            y = random.uniform(-40, 40)
            z = random.uniform(5, 20)
            
            # ROS 서비스를 통해 드론 스폰 (실제 구현)
            logger.info(f"Spawning drone {i} at position ({x:.1f}, {y:.1f}, {z:.1f})")
            
            # 시뮬레이션을 위한 대기
            await asyncio.sleep(0.5)
            
    async def stop_gazebo(self):
        """Gazebo 중지"""
        if self.gazebo_process and self.is_running:
            self.gazebo_process.terminate()
            await self.gazebo_process.wait()
            self.is_running = False
            logger.info("Gazebo stopped")

# 메인 실행 함수
async def main():
    """메인 실행 함수"""
    import argparse
    
    parser = argparse.ArgumentParser(description="드론 MTD 테스트베드")
    parser.add_argument("--config", default="configs/mtd_config.yaml",
                       help="설정 파일 경로")
    parser.add_argument("--duration", type=int, default=30,
                       help="실험 지속시간 (분)")
    parser.add_argument("--intensity", choices=['reconnaissance', 'light', 'moderate', 'aggressive', 'critical'],
                       default='moderate', help="초기 공격 강도")
    parser.add_argument("--enable-gazebo", action='store_true',
                       help="Gazebo 시뮬레이션 활성화")
    parser.add_argument("--enable-ns3", action='store_true', 
                       help="NS-3 시뮬레이션 활성화")
    parser.add_argument("--fanet-nodes", type=int, default=10,
                       help="FANET 노드 수")
    
    args = parser.parse_args()
    
    # 배너 출력
    print("""
╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║           🚁 드론 MTD 테스트베드 (v1.0.0)                        ║
║              Moving Target Defense Testbed                       ║
║                                                                  ║
║  🎯 자동 공격 강도 조절 및 실시간 이상 탐지                       ║
║  🌐 FANET 네트워크 시뮬레이션                                     ║
║  🔧 QGroundControl + ArduPilot + Gazebo + NS-3                   ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
""")
    
    # 오케스트레이터 초기화
    orchestrator = MTDTestbedOrchestrator(args.config)
    
    # 초기 강도 설정
    intensity_map = {
        'reconnaissance': AttackIntensity.RECONNAISSANCE,
        'light': AttackIntensity.LIGHT,
        'moderate': AttackIntensity.MODERATE,
        'aggressive': AttackIntensity.AGGRESSIVE,
        'critical': AttackIntensity.CRITICAL
    }
    orchestrator.intensity_controller.current_intensity = intensity_map[args.intensity]
    
    # FANET 노드 수 업데이트
    orchestrator.config["fanet"]["node_count"] = args.fanet_nodes
    
    try:
        # 환경 초기화
        await orchestrator.initialize_environment()
        
        # 외부 시뮬레이션 시작
        gazebo_interface = None
        ns3_interface = None
        
        if args.enable_gazebo:
            gazebo_interface = GazeboInterface(orchestrator.config)
            await gazebo_interface.start_gazebo()
            
        if args.enable_ns3:
            ns3_interface = NS3SimulationInterface(orchestrator.config)
            await ns3_interface.start_simulation()
            
        # 메인 실험 실행
        logger.info(f"Starting {args.duration}-minute experiment with {args.intensity} intensity")
        logger.info(f"FANET nodes: {args.fanet_nodes}, Gazebo: {args.enable_gazebo}, NS-3: {args.enable_ns3}")
        
        await orchestrator.run_adaptive_attack_campaign(args.duration)
        
    except KeyboardInterrupt:
        logger.info("실험이 사용자에 의해 중단되었습니다")
    except Exception as e:
        logger.error(f"실험 중 오류 발생: {e}")
    finally:
        # 정리 작업
        await orchestrator.stop()
        
        if gazebo_interface:
            await gazebo_interface.stop_gazebo()
            
        if ns3_interface:
            await ns3_interface.stop_simulation()
            
        logger.info("MTD 테스트베드 실험이 완료되었습니다")

if __name__ == "__main__":
    # 필요한 라이브러리 확인
    missing_deps = []
    
    if not HAS_MAVLINK:
        missing_deps.append("pymavlink")
    if not HAS_ROS:
        missing_deps.append("rospy (ROS)")
        
    if missing_deps:
        print(f"⚠️ 누락된 의존성: {', '.join(missing_deps)}")
        print("📦 설치 명령:")
        if "pymavlink" in missing_deps:
            print("   pip install pymavlink")
        if "rospy" in missing_deps:
            print("   ROS 설치 필요 (http://wiki.ros.org/Installation)")
        print("\n일부 기능이 제한될 수 있습니다.")
        
    # asyncio 실행
    asyncio.run(main())