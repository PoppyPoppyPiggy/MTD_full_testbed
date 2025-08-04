#!/usr/bin/env python3
"""
Enhanced CTI Defense Monitoring System for DVD Testbed
통합된 방어자 관점 CTI 수집 및 분류 시스템

기능:
- Docker 컨테이너 간 실시간 모니터링
- MAVLink 프로토콜 분석 및 이상 탐지
- 기계학습 기반 공격 분류
- STIX/TAXII 표준 CTI 생성
- 실시간 대시보드 및 알림
"""

import asyncio
import json
import logging
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import numpy as np
import pandas as pd
from pathlib import Path
import docker
import psutil
import socket
import struct
from collections import defaultdict, deque
import websockets
import sqlite3
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
import joblib
import yaml

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('cti_defense.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# =============================================================================
# 데이터 구조 정의
# =============================================================================

class ThreatLevel(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

class AttackCategory(Enum):
    RECONNAISSANCE = "reconnaissance"
    PROTOCOL_TAMPERING = "protocol_tampering"
    DOS_ATTACK = "denial_of_service"
    INJECTION = "injection"
    EXFILTRATION = "exfiltration"
    FIRMWARE_ATTACK = "firmware_attacks"

@dataclass
class ThreatEvent:
    """위협 이벤트 데이터 구조"""
    timestamp: datetime
    event_id: str
    source_ip: str
    target_ip: str
    attack_category: AttackCategory
    threat_level: ThreatLevel
    confidence: float
    description: str
    iocs: List[str]
    raw_data: Dict[str, Any]
    
@dataclass
class ContainerMetrics:
    """컨테이너 메트릭 데이터"""
    container_id: str
    name: str
    cpu_usage: float
    memory_usage: float
    network_io: Dict[str, int]
    disk_io: Dict[str, int]
    timestamp: datetime

@dataclass
class MAVLinkMessage:
    """MAVLink 메시지 구조"""
    timestamp: datetime
    msg_id: int
    sys_id: int
    comp_id: int
    payload: bytes
    source_ip: str
    is_suspicious: bool = False

# =============================================================================
# Docker 컨테이너 모니터링 시스템
# =============================================================================

class DockerMonitor:
    """Docker 컨테이너 실시간 모니터링"""
    
    def __init__(self):
        self.client = docker.from_env()
        self.monitoring = False
        self.metrics_queue = deque(maxlen=1000)
        self.alert_thresholds = {
            'cpu': 80.0,
            'memory': 85.0,
            'network_anomaly': 5.0  # MB/s
        }
        
    async def start_monitoring(self):
        """모니터링 시작"""
        self.monitoring = True
        logger.info("🔍 Docker 컨테이너 모니터링 시작")
        
        while self.monitoring:
            try:
                containers = self.client.containers.list()
                
                for container in containers:
                    if any(keyword in container.name.lower() 
                          for keyword in ['drone', 'dvd', 'mavlink']):
                        metrics = await self._collect_container_metrics(container)
                        self.metrics_queue.append(metrics)
                        
                        # 이상 징후 감지
                        await self._detect_anomalies(metrics)
                        
                await asyncio.sleep(1)  # 1초 간격 모니터링
                
            except Exception as e:
                logger.error(f"Docker 모니터링 오류: {e}")
                await asyncio.sleep(5)
    
    async def _collect_container_metrics(self, container) -> ContainerMetrics:
        """컨테이너 메트릭 수집"""
        try:
            stats = container.stats(stream=False)
            
            # CPU 사용률 계산
            cpu_usage = self._calculate_cpu_percent(stats)
            
            # 메모리 사용률 계산
            memory_usage = self._calculate_memory_percent(stats)
            
            # 네트워크 I/O
            network_io = stats.get('networks', {})
            
            # 디스크 I/O
            disk_io = stats.get('blkio_stats', {})
            
            return ContainerMetrics(
                container_id=container.id[:12],
                name=container.name,
                cpu_usage=cpu_usage,
                memory_usage=memory_usage,
                network_io=network_io,
                disk_io=disk_io,
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"메트릭 수집 오류 ({container.name}): {e}")
            return None
    
    def _calculate_cpu_percent(self, stats: Dict) -> float:
        """CPU 사용률 계산"""
        try:
            cpu_stats = stats['cpu_stats']
            precpu_stats = stats['precpu_stats']
            
            cpu_delta = cpu_stats['cpu_usage']['total_usage'] - \
                       precpu_stats['cpu_usage']['total_usage']
            system_delta = cpu_stats['system_cpu_usage'] - \
                          precpu_stats['system_cpu_usage']
            
            if system_delta > 0:
                cpu_percent = (cpu_delta / system_delta) * \
                             len(cpu_stats['cpu_usage']['percpu_usage']) * 100
                return round(cpu_percent, 2)
        except (KeyError, ZeroDivisionError):
            pass
        return 0.0
    
    def _calculate_memory_percent(self, stats: Dict) -> float:
        """메모리 사용률 계산"""
        try:
            memory_stats = stats['memory_stats']
            usage = memory_stats['usage']
            limit = memory_stats['limit']
            return round((usage / limit) * 100, 2)
        except (KeyError, ZeroDivisionError):
            return 0.0
    
    async def _detect_anomalies(self, metrics: ContainerMetrics):
        """이상 징후 탐지 및 알림"""
        if not metrics:
            return
            
        alerts = []
        
        # CPU 사용률 체크
        if metrics.cpu_usage > self.alert_thresholds['cpu']:
            alerts.append(f"🚨 높은 CPU 사용률: {metrics.cpu_usage}%")
        
        # 메모리 사용률 체크
        if metrics.memory_usage > self.alert_thresholds['memory']:
            alerts.append(f"🚨 높은 메모리 사용률: {metrics.memory_usage}%")
        
        # 네트워크 이상 트래픽 체크
        if self._detect_network_anomaly(metrics):
            alerts.append("🚨 비정상적인 네트워크 트래픽 감지")
        
        # 알림 전송
        for alert in alerts:
            logger.warning(f"[{metrics.name}] {alert}")
            await self._send_alert(metrics, alert)
    
    def _detect_network_anomaly(self, metrics: ContainerMetrics) -> bool:
        """네트워크 이상 트래픽 감지"""
        # 간단한 임계값 기반 탐지 (실제로는 더 정교한 알고리즘 필요)
        try:
            for interface, data in metrics.network_io.items():
                if interface != 'lo':  # 루프백 제외
                    rx_bytes = data.get('rx_bytes', 0)
                    tx_bytes = data.get('tx_bytes', 0)
                    
                    # 초당 MB 계산 (임시)
                    total_mb = (rx_bytes + tx_bytes) / (1024 * 1024)
                    if total_mb > self.alert_thresholds['network_anomaly']:
                        return True
        except Exception:
            pass
        return False
    
    async def _send_alert(self, metrics: ContainerMetrics, alert: str):
        """알림 전송 (WebSocket, 로그 등)"""
        alert_data = {
            'timestamp': metrics.timestamp.isoformat(),
            'container': metrics.name,
            'alert': alert,
            'metrics': asdict(metrics)
        }
        
        # WebSocket으로 실시간 전송 (구현 필요)
        # await self.websocket_broadcaster.send(alert_data)
        
        # 파일로 저장
        with open('alerts.log', 'a') as f:
            f.write(f"{json.dumps(alert_data)}\n")

# =============================================================================
# MAVLink 프로토콜 분석기
# =============================================================================

class MAVLinkAnalyzer:
    """MAVLink 프로토콜 실시간 분석 및 이상 탐지"""
    
    def __init__(self, interface: str = "any", port: int = 14550):
        self.interface = interface
        self.port = port
        self.analyzing = False
        self.message_queue = deque(maxlen=1000)
        self.suspicious_patterns = self._load_suspicious_patterns()
        self.baseline_stats = defaultdict(int)
        
    def _load_suspicious_patterns(self) -> Dict[str, Any]:
        """악성 MAVLink 패턴 로드"""
        return {
            'high_frequency_commands': {
                'threshold': 10,  # 초당 10개 이상
                'msg_ids': [76, 11, 20]  # COMMAND_LONG, SET_MODE, GPS 관련
            },
            'suspicious_msg_ids': [255, 254, 253],  # 비정상적인 메시지 ID
            'gps_spoofing_indicators': {
                'rapid_position_change': 1000,  # 1km 이상 급격한 위치 변화
                'impossible_speed': 200  # 200m/s 이상
            }
        }
    
    async def start_analysis(self):
        """MAVLink 분석 시작"""
        self.analyzing = True
        logger.info(f"🔍 MAVLink 프로토콜 분석 시작 (포트: {self.port})")
        
        # 소켓 생성 및 바인딩
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('0.0.0.0', self.port))
        sock.settimeout(1.0)
        
        while self.analyzing:
            try:
                data, addr = sock.recvfrom(1024)
                
                # MAVLink 메시지 파싱
                message = await self._parse_mavlink_message(data, addr[0])
                if message:
                    self.message_queue.append(message)
                    
                    # 실시간 분석
                    await self._analyze_message(message)
                    
            except socket.timeout:
                continue
            except Exception as e:
                logger.error(f"MAVLink 분석 오류: {e}")
                await asyncio.sleep(1)
        
        sock.close()
    
    async def _parse_mavlink_message(self, data: bytes, source_ip: str) -> Optional[MAVLinkMessage]:
        """MAVLink 메시지 파싱"""
        try:
            if len(data) < 8:
                return None
            
            # MAVLink v1/v2 헤더 파싱
            if data[0] == 0xFE:  # MAVLink v1
                msg_len, seq, sys_id, comp_id, msg_id = struct.unpack('<BBBBB', data[1:6])
                payload = data[6:6+msg_len]
            elif data[0] == 0xFD:  # MAVLink v2
                msg_len, incompat, compat, seq, sys_id, comp_id = struct.unpack('<BBBBBB', data[1:7])
                msg_id = struct.unpack('<I', data[7:10] + b'\x00')[0]  # 24-bit message ID
                payload = data[10:10+msg_len]
            else:
                return None
            
            return MAVLinkMessage(
                timestamp=datetime.now(),
                msg_id=msg_id,
                sys_id=sys_id,
                comp_id=comp_id,
                payload=payload,
                source_ip=source_ip
            )
            
        except Exception as e:
            logger.debug(f"MAVLink 파싱 오류: {e}")
            return None
    
    async def _analyze_message(self, message: MAVLinkMessage):
        """메시지 분석 및 이상 탐지"""
        # 베이스라인 통계 업데이트
        self.baseline_stats[message.msg_id] += 1
        
        # 의심스러운 패턴 검사
        is_suspicious = False
        
        # 1. 비정상적인 메시지 ID 체크
        if message.msg_id in self.suspicious_patterns['suspicious_msg_ids']:
            logger.warning(f"🚨 의심스러운 메시지 ID 감지: {message.msg_id}")
            is_suspicious = True
        
        # 2. 고빈도 명령 체크
        if await self._check_high_frequency_attack(message):
            logger.warning(f"🚨 고빈도 명령 공격 의심: {message.msg_id}")
            is_suspicious = True
        
        # 3. GPS 스푸핑 체크 (GPS 관련 메시지의 경우)
        if message.msg_id in [24, 25, 33] and await self._check_gps_spoofing(message):
            logger.warning("🚨 GPS 스푸핑 공격 의심")
            is_suspicious = True
        
        message.is_suspicious = is_suspicious
        
        # 의심스러운 메시지는 별도 처리
        if is_suspicious:
            await self._handle_suspicious_message(message)
    
    async def _check_high_frequency_attack(self, message: MAVLinkMessage) -> bool:
        """고빈도 공격 패턴 체크"""
        # 최근 1초간 동일한 메시지 수 계산
        now = datetime.now()
        recent_messages = [
            msg for msg in self.message_queue
            if msg.msg_id == message.msg_id and 
               (now - msg.timestamp).total_seconds() < 1.0
        ]
        
        threshold = self.suspicious_patterns['high_frequency_commands']['threshold']
        return len(recent_messages) > threshold
    
    async def _check_gps_spoofing(self, message: MAVLinkMessage) -> bool:
        """GPS 스푸핑 패턴 체크"""
        # 간단한 GPS 스푸핑 탐지 로직
        # 실제로는 위치 데이터를 파싱하여 비정상적인 위치 변화 탐지
        
        # 페이로드에서 위치 정보 추출 (메시지 타입에 따라 다름)
        try:
            if message.msg_id == 24:  # GPS_RAW_INT
                # 위치 데이터 파싱 및 분석
                pass
            elif message.msg_id == 33:  # GLOBAL_POSITION_INT
                # 글로벌 위치 데이터 분석
                pass
        except Exception:
            pass
        
        return False  # 임시로 False 반환
    
    async def _handle_suspicious_message(self, message: MAVLinkMessage):
        """의심스러운 메시지 처리"""
        # 위협 이벤트 생성
        threat_event = ThreatEvent(
            timestamp=message.timestamp,
            event_id=f"mavlink_{int(time.time())}",
            source_ip=message.source_ip,
            target_ip="10.13.0.2",  # 드론 IP
            attack_category=self._classify_attack_category(message),
            threat_level=ThreatLevel.HIGH,
            confidence=0.8,
            description=f"의심스러운 MAVLink 메시지 (ID: {message.msg_id})",
            iocs=[f"mavlink_msg_id:{message.msg_id}", f"source_ip:{message.source_ip}"],
            raw_data=asdict(message)
        )
        
        # CTI 시스템으로 전달
        await self._send_to_cti_system(threat_event)
    
    def _classify_attack_category(self, message: MAVLinkMessage) -> AttackCategory:
        """메시지 기반 공격 카테고리 분류"""
        # 메시지 ID 기반 간단한 분류
        if message.msg_id in [24, 25, 33]:  # GPS 관련
            return AttackCategory.PROTOCOL_TAMPERING
        elif message.msg_id in [76, 11]:  # 명령 관련
            return AttackCategory.INJECTION
        else:
            return AttackCategory.RECONNAISSANCE
    
    async def _send_to_cti_system(self, threat_event: ThreatEvent):
        """CTI 시스템으로 위협 이벤트 전송"""
        # CTI 수집기로 전송 (구현 필요)
        logger.info(f"📊 CTI 시스템으로 위협 이벤트 전송: {threat_event.event_id}")

# =============================================================================
# 기계학습 기반 공격 분류기
# =============================================================================

class MLAttackClassifier:
    """기계학습 기반 실시간 공격 분류"""
    
    def __init__(self):
        self.model = None
        self.scaler = StandardScaler()
        self.is_trained = False
        self.feature_buffer = deque(maxlen=100)
        
        # 특징 정의
        self.feature_columns = [
            'packet_rate', 'byte_rate', 'msg_frequency',
            'unique_msg_ids', 'cpu_usage', 'memory_usage',
            'network_rx_rate', 'network_tx_rate'
        ]
        
        self.attack_labels = {
            0: 'normal',
            1: 'reconnaissance', 
            2: 'protocol_tampering',
            3: 'dos_attack',
            4: 'injection'
        }
    
    def train_model(self, training_data_path: str = None):
        """모델 훈련 (기존 데이터 또는 시뮬레이션 데이터 사용)"""
        logger.info("🤖 공격 분류 모델 훈련 시작")
        
        if training_data_path and Path(training_data_path).exists():
            # 기존 데이터로 훈련
            df = pd.read_csv(training_data_path)
        else:
            # 시뮬레이션 데이터 생성
            df = self._generate_training_data()
        
        # 특징과 레이블 분리
        X = df[self.feature_columns]
        y = df['label']
        
        # 데이터 정규화
        X_scaled = self.scaler.fit_transform(X)
        
        # Random Forest 모델 훈련
        self.model = RandomForestClassifier(
            n_estimators=9,
            max_depth=6,
            random_state=42,
            class_weight='balanced'
        )
        
        self.model.fit(X_scaled, y)
        self.is_trained = True
        
        # 모델 성능 출력
        train_accuracy = self.model.score(X_scaled, y)
        logger.info(f"✅ 모델 훈련 완료 - 정확도: {train_accuracy:.3f}")
        
        # 모델 저장
        self._save_model()
    
    def _generate_training_data(self) -> pd.DataFrame:
        """시뮬레이션 훈련 데이터 생성"""
        logger.info("📊 시뮬레이션 훈련 데이터 생성")
        
        data = []
        
        # 정상 트래픽 생성 (50%)
        for _ in range(500):
            data.append({
                'packet_rate': np.random.normal(10, 2),
                'byte_rate': np.random.normal(1024, 200),
                'msg_frequency': np.random.normal(5, 1),
                'unique_msg_ids': np.random.randint(3, 8),
                'cpu_usage': np.random.normal(20, 5),
                'memory_usage': np.random.normal(30, 8),
                'network_rx_rate': np.random.normal(100, 20),
                'network_tx_rate': np.random.normal(80, 15),
                'label': 0  # normal
            })
        
        # 정찰 공격 (15%)
        for _ in range(150):
            data.append({
                'packet_rate': np.random.normal(50, 10),
                'byte_rate': np.random.normal(512, 100),
                'msg_frequency': np.random.normal(15, 3),
                'unique_msg_ids': np.random.randint(8, 15),
                'cpu_usage': np.random.normal(15, 3),
                'memory_usage': np.random.normal(25, 5),
                'network_rx_rate': np.random.normal(200, 50),
                'network_tx_rate': np.random.normal(50, 10),
                'label': 1  # reconnaissance
            })
        
        # 프로토콜 변조 (15%)
        for _ in range(150):
            data.append({
                'packet_rate': np.random.normal(30, 8),
                'byte_rate': np.random.normal(2048, 400),
                'msg_frequency': np.random.normal(20, 5),
                'unique_msg_ids': np.random.randint(2, 5),
                'cpu_usage': np.random.normal(40, 10),
                'memory_usage': np.random.normal(35, 8),
                'network_rx_rate': np.random.normal(150, 30),
                'network_tx_rate': np.random.normal(300, 60),
                'label': 2  # protocol_tampering
            })
        
        # DoS 공격 (15%)
        for _ in range(150):
            data.append({
                'packet_rate': np.random.normal(100, 20),
                'byte_rate': np.random.normal(4096, 800),
                'msg_frequency': np.random.normal(50, 10),
                'unique_msg_ids': np.random.randint(1, 3),
                'cpu_usage': np.random.normal(80, 15),
                'memory_usage': np.random.normal(75, 15),
                'network_rx_rate': np.random.normal(500, 100),
                'network_tx_rate': np.random.normal(600, 120),
                'label': 3  # dos_attack
            })
        
        # 인젝션 공격 (5%)
        for _ in range(50):
            data.append({
                'packet_rate': np.random.normal(25, 5),
                'byte_rate': np.random.normal(1536, 300),
                'msg_frequency': np.random.normal(12, 3),
                'unique_msg_ids': np.random.randint(5, 10),
                'cpu_usage': np.random.normal(35, 8),
                'memory_usage': np.random.normal(40, 10),
                'network_rx_rate': np.random.normal(120, 25),
                'network_tx_rate': np.random.normal(200, 40),
                'label': 4  # injection
            })
        
        return pd.DataFrame(data)
    
    def predict_attack(self, features: Dict[str, float]) -> Tuple[str, float]:
        """실시간 공격 분류"""
        if not self.is_trained:
            return "unknown", 0.0
        
        try:
            # 특징 벡터 준비
            feature_vector = [features.get(col, 0.0) for col in self.feature_columns]
            feature_array = np.array([feature_vector])
            
            # 정규화
            feature_scaled = self.scaler.transform(feature_array)
            
            # 예측
            prediction = self.model.predict(feature_scaled)[0]
            probabilities = self.model.predict_proba(feature_scaled)[0]
            confidence = max(probabilities)
            
            attack_type = self.attack_labels.get(prediction, "unknown")
            
            return attack_type, confidence
            
        except Exception as e:
            logger.error(f"공격 분류 오류: {e}")
            return "error", 0.0
    
    def _save_model(self):
        """모델 저장"""
        try:
            joblib.dump(self.model, 'models/attack_classifier.pkl')
            joblib.dump(self.scaler, 'models/feature_scaler.pkl')
            logger.info("✅ 모델 저장 완료")
        except Exception as e:
            logger.error(f"모델 저장 오류: {e}")
    
    def load_model(self):
        """저장된 모델 로드"""
        try:
            if Path('models/attack_classifier.pkl').exists():
                self.model = joblib.load('models/attack_classifier.pkl')
                self.scaler = joblib.load('models/feature_scaler.pkl')
                self.is_trained = True
                logger.info("✅ 저장된 모델 로드 완료")
                return True
        except Exception as e:
            logger.error(f"모델 로드 오류: {e}")
        return False

# =============================================================================
# 통합 CTI 수집 및 분류 시스템
# =============================================================================

class EnhancedCTIDefenseSystem:
    """통합된 방어자 관점 CTI 수집 및 분류 시스템"""
    
    def __init__(self, config_path: str = "cti_config.yaml"):
        self.config = self._load_config(config_path)
        
        # 구성 요소 초기화
        self.docker_monitor = DockerMonitor()
        self.mavlink_analyzer = MAVLinkAnalyzer()
        self.ml_classifier = MLAttackClassifier()
        
        # 데이터 저장
        self.threat_events = deque(maxlen=10000)
        self.db_path = "cti_defense.db"
        self._init_database()
        
        # 실시간 대시보드
        self.dashboard_clients = set()
        self.running = False
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """설정 파일 로드"""
        try:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            return {
                'monitoring': {
                    'docker_enabled': True,
                    'mavlink_enabled': True,
                    'ml_enabled': True
                },
                'thresholds': {
                    'cpu_alert': 80.0,
                    'memory_alert': 85.0,
                    'confidence_threshold': 0.7
                },
                'database': {
                    'path': 'cti_defense.db',
                    'retention_days': 30
                }
            }
    
    def _init_database(self):
        """SQLite 데이터베이스 초기화"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 위협 이벤트 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS threat_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    event_id TEXT UNIQUE NOT NULL,
                    source_ip TEXT,
                    target_ip TEXT,
                    attack_category TEXT,
                    threat_level INTEGER,
                    confidence REAL,
                    description TEXT,
                    iocs TEXT,
                    raw_data TEXT
                )
            ''')
            
            # 컨테이너 메트릭 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS container_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    container_id TEXT,
                    container_name TEXT,
                    cpu_usage REAL,
                    memory_usage REAL,
                    network_io TEXT,
                    disk_io TEXT
                )
            ''')
            
            conn.commit()
            conn.close()
            logger.info("✅ 데이터베이스 초기화 완료")
            
        except Exception as e:
            logger.error(f"데이터베이스 초기화 오류: {e}")
    
    async def start_defense_system(self):
        """방어 시스템 시작"""
        logger.info("🛡️ Enhanced CTI Defense System 시작")
        self.running = True
        
        # ML 모델 로드/훈련
        if not self.ml_classifier.load_model():
            logger.info("기존 모델이 없어 새로 훈련합니다...")
            self.ml_classifier.train_model()
        
        # 모니터링 태스크들 시작
        tasks = []
        
        if self.config['monitoring']['docker_enabled']:
            tasks.append(asyncio.create_task(self.docker_monitor.start_monitoring()))
        
        if self.config['monitoring']['mavlink_enabled']:
            tasks.append(asyncio.create_task(self.mavlink_analyzer.start_analysis()))
        
        # 통합 분석 태스크
        tasks.append(asyncio.create_task(self._integrated_analysis_loop()))
        
        # 실시간 대시보드 서버
        tasks.append(asyncio.create_task(self._start_dashboard_server()))
        
        # 모든 태스크 실행
        try:
            await asyncio.gather(*tasks)
        except KeyboardInterrupt:
            logger.info("시스템 종료 중...")
            await self.stop_defense_system()
    
    async def _integrated_analysis_loop(self):
        """통합 분석 루프"""
        logger.info("🔍 통합 분석 루프 시작")
        
        while self.running:
            try:
                # Docker 메트릭과 MAVLink 데이터를 결합하여 분석
                current_features = await self._extract_features()
                
                if current_features and self.config['monitoring']['ml_enabled']:
                    # ML 기반 공격 분류
                    attack_type, confidence = self.ml_classifier.predict_attack(current_features)
                    
                    # 임계값 이상의 위협만 처리
                    if (confidence > self.config['thresholds']['confidence_threshold'] and 
                        attack_type != 'normal'):
                        
                        # 위협 이벤트 생성
                        threat_event = ThreatEvent(
                            timestamp=datetime.now(),
                            event_id=f"ml_{int(time.time())}_{attack_type}",
                            source_ip="unknown",
                            target_ip="10.13.0.2",
                            attack_category=AttackCategory(attack_type),
                            threat_level=self._determine_threat_level(confidence),
                            confidence=confidence,
                            description=f"ML 분류기가 {attack_type} 공격을 탐지했습니다",
                            iocs=[f"attack_type:{attack_type}", f"confidence:{confidence:.2f}"],
                            raw_data=current_features
                        )
                        
                        await self._process_threat_event(threat_event)
                
                await asyncio.sleep(5)  # 5초 간격
                
            except Exception as e:
                logger.error(f"통합 분석 오류: {e}")
                await asyncio.sleep(10)
    
    async def _extract_features(self) -> Optional[Dict[str, float]]:
        """현재 시스템 상태에서 특징 추출"""
        try:
            features = {}
            
            # Docker 메트릭에서 특징 추출
            recent_metrics = [
                m for m in self.docker_monitor.metrics_queue
                if (datetime.now() - m.timestamp).total_seconds() < 60
            ]
            
            if recent_metrics:
                features['cpu_usage'] = np.mean([m.cpu_usage for m in recent_metrics])
                features['memory_usage'] = np.mean([m.memory_usage for m in recent_metrics])
                
                # 네트워크 I/O 계산
                total_rx = sum(
                    sum(m.network_io.get(iface, {}).get('rx_bytes', 0) 
                        for iface in m.network_io) 
                    for m in recent_metrics
                )
                total_tx = sum(
                    sum(m.network_io.get(iface, {}).get('tx_bytes', 0) 
                        for iface in m.network_io) 
                    for m in recent_metrics
                )
                
                features['network_rx_rate'] = total_rx / max(len(recent_metrics), 1)
                features['network_tx_rate'] = total_tx / max(len(recent_metrics), 1)
            
            # MAVLink 메시지에서 특징 추출
            recent_messages = [
                m for m in self.mavlink_analyzer.message_queue
                if (datetime.now() - m.timestamp).total_seconds() < 60
            ]
            
            if recent_messages:
                features['packet_rate'] = len(recent_messages) / 60.0
                features['msg_frequency'] = len(recent_messages) / 60.0
                features['unique_msg_ids'] = len(set(m.msg_id for m in recent_messages))
                features['byte_rate'] = sum(len(m.payload) for m in recent_messages) / 60.0
            else:
                features.update({
                    'packet_rate': 0,
                    'msg_frequency': 0,
                    'unique_msg_ids': 0,
                    'byte_rate': 0
                })
            
            # 누락된 특징은 기본값으로 채움
            for col in self.ml_classifier.feature_columns:
                if col not in features:
                    features[col] = 0.0
            
            return features
            
        except Exception as e:
            logger.error(f"특징 추출 오류: {e}")
            return None
    
    def _determine_threat_level(self, confidence: float) -> ThreatLevel:
        """신뢰도 기반 위협 레벨 결정"""
        if confidence >= 0.9:
            return ThreatLevel.CRITICAL
        elif confidence >= 0.8:
            return ThreatLevel.HIGH
        elif confidence >= 0.7:
            return ThreatLevel.MEDIUM
        else:
            return ThreatLevel.LOW
    
    async def _process_threat_event(self, event: ThreatEvent):
        """위협 이벤트 처리"""
        logger.warning(f"🚨 위협 탐지: {event.description} (신뢰도: {event.confidence:.2f})")
        
        # 메모리에 저장
        self.threat_events.append(event)
        
        # 데이터베이스에 저장
        await self._save_threat_event_to_db(event)
        
        # 실시간 대시보드로 전송
        await self._broadcast_to_dashboard(event)
        
        # STIX 형식으로 변환 및 저장
        await self._export_to_stix(event)
    
    async def _save_threat_event_to_db(self, event: ThreatEvent):
        """위협 이벤트를 데이터베이스에 저장"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR IGNORE INTO threat_events 
                (timestamp, event_id, source_ip, target_ip, attack_category, 
                 threat_level, confidence, description, iocs, raw_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                event.timestamp.isoformat(),
                event.event_id,
                event.source_ip,
                event.target_ip,
                event.attack_category.value,
                event.threat_level.value,
                event.confidence,
                event.description,
                json.dumps(event.iocs),
                json.dumps(event.raw_data)
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"데이터베이스 저장 오류: {e}")
    
    async def _broadcast_to_dashboard(self, event: ThreatEvent):
        """실시간 대시보드로 이벤트 전송"""
        if not self.dashboard_clients:
            return
        
        message = {
            'type': 'threat_event',
            'data': {
                'timestamp': event.timestamp.isoformat(),
                'event_id': event.event_id,
                'attack_category': event.attack_category.value,
                'threat_level': event.threat_level.name,
                'confidence': event.confidence,
                'description': event.description,
                'iocs': event.iocs
            }
        }
        
        # 연결된 모든 클라이언트에게 전송
        disconnected = set()
        for client in self.dashboard_clients:
            try:
                await client.send(json.dumps(message))
            except:
                disconnected.add(client)
        
        # 연결이 끊어진 클라이언트 제거
        self.dashboard_clients -= disconnected
    
    async def _start_dashboard_server(self):
        """WebSocket 기반 실시간 대시보드 서버 시작"""
        async def handle_client(websocket, path):
            self.dashboard_clients.add(websocket)
            logger.info(f"대시보드 클라이언트 연결: {websocket.remote_address}")
            
            try:
                # 초기 데이터 전송
                await self._send_dashboard_init_data(websocket)
                
                # 클라이언트 연결 유지
                async for message in websocket:
                    # 클라이언트로부터 메시지 처리 (필요시)
                    pass
                    
            except websockets.exceptions.ConnectionClosed:
                pass
            finally:
                self.dashboard_clients.discard(websocket)
                logger.info("대시보드 클라이언트 연결 해제")
        
        # WebSocket 서버 시작
        logger.info("🌐 실시간 대시보드 서버 시작 (포트: 8765)")
        await websockets.serve(handle_client, "localhost", 8765)
    
    async def _send_dashboard_init_data(self, websocket):
        """대시보드 초기 데이터 전송"""
        try:
            # 최근 위협 이벤트 요약
            recent_events = list(self.threat_events)[-50:]  # 최근 50개
            
            init_data = {
                'type': 'init_data',
                'data': {
                    'recent_events': [
                        {
                            'timestamp': event.timestamp.isoformat(),
                            'attack_category': event.attack_category.value,
                            'threat_level': event.threat_level.name,
                            'confidence': event.confidence,
                            'description': event.description
                        }
                        for event in recent_events
                    ],
                    'system_status': {
                        'docker_monitoring': self.docker_monitor.monitoring,
                        'mavlink_analysis': self.mavlink_analyzer.analyzing,
                        'ml_classifier': self.ml_classifier.is_trained
                    }
                }
            }
            
            await websocket.send(json.dumps(init_data))
            
        except Exception as e:
            logger.error(f"초기 데이터 전송 오류: {e}")
    
    async def _export_to_stix(self, event: ThreatEvent):
        """STIX 2.1 형식으로 위협 정보 내보내기"""
        try:
            stix_data = {
                "type": "bundle",
                "id": f"bundle--{event.event_id}",
                "objects": [
                    {
                        "type": "indicator",
                        "spec_version": "2.1",
                        "id": f"indicator--{event.event_id}",
                        "created": event.timestamp.isoformat(),
                        "modified": event.timestamp.isoformat(),
                        "name": f"Drone Attack: {event.attack_category.value}",
                        "description": event.description,
                        "confidence": int(event.confidence * 100),
                        "pattern": f"[network-traffic:src_ref.value = '{event.source_ip}']",
                        "valid_from": event.timestamp.isoformat(),
                        "labels": ["malicious-activity"]
                    },
                    {
                        "type": "attack-pattern",
                        "spec_version": "2.1", 
                        "id": f"attack-pattern--{event.attack_category.value}",
                        "created": event.timestamp.isoformat(),
                        "modified": event.timestamp.isoformat(),
                        "name": f"Drone {event.attack_category.value}",
                        "description": f"Attack pattern for {event.attack_category.value} on drone systems"
                    }
                ]
            }
            
            # STIX 파일 저장
            stix_dir = Path("stix_exports")
            stix_dir.mkdir(exist_ok=True)
            
            stix_file = stix_dir / f"threat_{event.event_id}.json"
            with open(stix_file, 'w') as f:
                json.dump(stix_data, f, indent=2)
                
            logger.info(f"📄 STIX 파일 생성: {stix_file}")
            
        except Exception as e:
            logger.error(f"STIX 내보내기 오류: {e}")
    
    async def stop_defense_system(self):
        """방어 시스템 중지"""
        logger.info("🛑 Enhanced CTI Defense System 중지")
        self.running = False
        self.docker_monitor.monitoring = False
        self.mavlink_analyzer.analyzing = False
    
    def generate_report(self, hours: int = 24) -> Dict[str, Any]:
        """CTI 분석 보고서 생성"""
        logger.info(f"📊 최근 {hours}시간 CTI 분석 보고서 생성")
        
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_events = [
            event for event in self.threat_events
            if event.timestamp > cutoff_time
        ]
        
        # 통계 계산
        total_events = len(recent_events)
        attack_categories = defaultdict(int)
        threat_levels = defaultdict(int)
        
        for event in recent_events:
            attack_categories[event.attack_category.value] += 1
            threat_levels[event.threat_level.name] += 1
        
        # 상위 IOC 추출
        all_iocs = []
        for event in recent_events:
            all_iocs.extend(event.iocs)
        
        ioc_counts = defaultdict(int)
        for ioc in all_iocs:
            ioc_counts[ioc] += 1
        
        top_iocs = dict(sorted(ioc_counts.items(), key=lambda x: x[1], reverse=True)[:10])
        
        report = {
            'report_time': datetime.now().isoformat(),
            'time_range_hours': hours,
            'summary': {
                'total_events': total_events,
                'unique_iocs': len(ioc_counts),
                'avg_confidence': np.mean([e.confidence for e in recent_events]) if recent_events else 0
            },
            'attack_distribution': dict(attack_categories),
            'threat_level_distribution': dict(threat_levels),
            'top_iocs': top_iocs,
            'timeline': [
                {
                    'timestamp': event.timestamp.isoformat(),
                    'category': event.attack_category.value,
                    'level': event.threat_level.name,
                    'confidence': event.confidence
                }
                for event in recent_events[-20:]  # 최근 20개 이벤트
            ]
        }
        
        # 보고서 파일 저장
        reports_dir = Path("reports")
        reports_dir.mkdir(exist_ok=True)
        
        report_file = reports_dir / f"cti_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"📄 CTI 보고서 저장: {report_file}")
        return report

# =============================================================================
# 메인 실행 함수
# =============================================================================

async def main():
    """메인 함수"""
    print("""
╔══════════════════════════════════════════════════════════════════╗
║           Enhanced CTI Defense Monitoring System                ║
║                    방어자 관점 통합 모니터링                      ║
║                                                                  ║
║  🔍 Docker 컨테이너 실시간 모니터링                               ║
║  📡 MAVLink 프로토콜 분석 및 이상 탐지                           ║
║  🤖 기계학습 기반 공격 분류                                       ║
║  📊 실시간 CTI 수집 및 STIX 형식 내보내기                        ║
║  🌐 WebSocket 기반 실시간 대시보드                               ║
╚══════════════════════════════════════════════════════════════════╝
    """)
    
    # 필요한 디렉토리 생성
    Path("models").mkdir(exist_ok=True)
    Path("stix_exports").mkdir(exist_ok=True)
    Path("reports").mkdir(exist_ok=True)
    
    # CTI 방어 시스템 시작
    cti_system = EnhancedCTIDefenseSystem()
    
    try:
        await cti_system.start_defense_system()
    except KeyboardInterrupt:
        logger.info("사용자에 의한 시스템 종료")
    except Exception as e:
        logger.error(f"시스템 오류: {e}")
    finally:
        await cti_system.stop_defense_system()

if __name__ == "__main__":
    asyncio.run(main())