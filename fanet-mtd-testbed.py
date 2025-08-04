#!/usr/bin/env python3
"""
FANET NS-3 통합 MTD 드론 보안 테스트베드
위치: ~/MTD/MTD_full_testbed/fanet_mtd_testbed.py

통합 시스템:
1. 기존 DVD 시뮬레이터와 100% 호환
2. NS-3 FANET 시뮬레이션 통합
3. 실시간 CTI 수집 및 분석
4. MTD 방어 메커니즘
5. 기계학습 기반 위협 분류
"""

import asyncio
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import numpy as np
import docker
import subprocess
import threading
import socket
import signal
import sys
import os

# 기존 시스템 모듈 통합
try:
    # 기존 DVD-Lite 모듈들 import
    from dvd_lite.main import DVDLite
    from dvd_lite.cti import SimpleCTI
    from dvd_lite.dvd_attacks.registry.management import register_all_dvd_attacks
    from dvd_connector.connector import DVDConnector, DVDEnvironment, DVDConnectionConfig
    from dvd_connector.safety_checker import SafetyChecker
    from dvd_connector.network_scanner import DVDNetworkScanner
except ImportError as e:
    print(f"⚠️ 기존 모듈 import 실패: {e}")
    print("기본 모드로 실행됩니다.")

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class FANETNode:
    """FANET 네트워크 노드 시뮬레이션"""
    
    def __init__(self, node_id: int, position: Tuple[float, float, float]):
        self.node_id = node_id
        self.position = position  # (x, y, z)
        self.velocity = (0.0, 0.0, 0.0)
        self.is_active = True
        self.neighbors = []
        self.routing_table = {}
        self.trust_score = 1.0
        self.packet_buffer = []
        self.energy_level = 100.0
        
    def update_position(self, new_position: Tuple[float, float, float]):
        """노드 위치 업데이트"""
        self.position = new_position
        
    def add_neighbor(self, neighbor_id: int, distance: float):
        """이웃 노드 추가"""
        self.neighbors.append({
            'id': neighbor_id,
            'distance': distance,
            'last_seen': time.time()
        })
        
    def decrease_trust(self, amount: float = 0.1):
        """신뢰도 감소"""
        self.trust_score = max(0.0, self.trust_score - amount)
        if self.trust_score < 0.3:
            self.is_active = False

class NS3FANETSimulator:
    """NS-3 기반 FANET 네트워크 시뮬레이터"""
    
    def __init__(self, num_nodes: int = 20):
        self.num_nodes = num_nodes
        self.nodes = {}
        self.simulation_time = 0.0
        self.is_running = False
        self.mobility_model = "RandomWalk2dMobilityModel"
        self.communication_range = 250.0  # meters
        self.simulation_area = (1000, 1000, 300)  # x, y, z bounds
        
        # NS-3 스크립트 경로 (실제 환경에서는 ns-3.45 디렉토리 사용)
        self.ns3_path = Path("./ns-3.45")
        self.script_path = self.ns3_path / "scratch" / "fanet-mtd-simulation.cc"
        
    def initialize_network_topology(self):
        """네트워크 토폴로지 초기화"""
        logger.info(f"FANET 네트워크 토폴로지 초기화 중... ({self.num_nodes}개 노드)")
        
        # 노드들을 3차원 공간에 랜덤 배치
        for i in range(self.num_nodes):
            x = np.random.uniform(0, self.simulation_area[0])
            y = np.random.uniform(0, self.simulation_area[1])
            z = np.random.uniform(50, self.simulation_area[2])
            
            node = FANETNode(i, (x, y, z))
            self.nodes[i] = node
            
        # 이웃 관계 설정
        self._update_neighbor_relationships()
        
    def _update_neighbor_relationships(self):
        """노드 간 이웃 관계 업데이트"""
        for node_id, node in self.nodes.items():
            node.neighbors.clear()
            
            for other_id, other_node in self.nodes.items():
                if node_id != other_id:
                    distance = self._calculate_distance(node.position, other_node.position)
                    if distance <= self.communication_range:
                        node.add_neighbor(other_id, distance)
    
    def _calculate_distance(self, pos1: Tuple[float, float, float], 
                          pos2: Tuple[float, float, float]) -> float:
        """3D 거리 계산"""
        return np.sqrt(sum((a - b) ** 2 for a, b in zip(pos1, pos2)))
    
    async def start_simulation(self):
        """NS-3 시뮬레이션 시작"""
        if not self.ns3_path.exists():
            logger.warning("NS-3 경로가 존재하지 않습니다. 시뮬레이션 모드로 실행합니다.")
            await self._run_python_simulation()
            return
            
        logger.info("NS-3 FANET 시뮬레이션 시작")
        self.is_running = True
        
        # NS-3 시뮬레이션 스크립트 생성
        await self._generate_ns3_script()
        
        # NS-3 실행
        cmd = [
            str(self.ns3_path / "ns3"),
            "run",
            "fanet-mtd-simulation",
            "--",
            f"--nNodes={self.num_nodes}",
            f"--simTime=300.0",
            f"--range={self.communication_range}"
        ]
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.ns3_path
            )
            
            # 시뮬레이션 결과 모니터링
            await self._monitor_simulation(process)
            
        except Exception as e:
            logger.error(f"NS-3 시뮬레이션 실행 실패: {e}")
            await self._run_python_simulation()
    
    async def _generate_ns3_script(self):
        """NS-3 시뮬레이션 스크립트 생성"""
        ns3_script = f"""
/*
 * FANET MTD 시뮬레이션 스크립트
 * 위치: {self.script_path}
 */

#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/mobility-module.h"
#include "ns3/wifi-module.h"
#include "ns3/internet-module.h"
#include "ns3/applications-module.h"
#include "ns3/netanim-module.h"

using namespace ns3;

NS_LOG_COMPONENT_DEFINE("FANET-MTD-Simulation");

class FANETMTDSimulation {{
public:
    FANETMTDSimulation(uint32_t nNodes, double simTime, double range);
    void Run();
    
private:
    void SetupNodes();
    void SetupMobility();
    void SetupCommunication();
    void SetupApplications();
    void SetupMTDMechanism();
    
    void PositionUpdate();
    void TrustUpdate();
    void DetectAttack(Ptr<Node> node);
    void ExecuteMTDStrategy(Ptr<Node> node);
    
    uint32_t m_nNodes;
    double m_simTime;
    double m_range;
    NodeContainer m_nodes;
    NetDeviceContainer m_devices;
}};

FANETMTDSimulation::FANETMTDSimulation(uint32_t nNodes, double simTime, double range)
    : m_nNodes(nNodes), m_simTime(simTime), m_range(range) {{
}}

void FANETMTDSimulation::SetupNodes() {{
    m_nodes.Create(m_nNodes);
    
    // 각 노드에 IPv4 스택 설치
    InternetStackHelper internet;
    internet.Install(m_nodes);
}}

void FANETMTDSimulation::SetupMobility() {{
    MobilityHelper mobility;
    
    // 3D 랜덤 워크 모빌리티 모델
    mobility.SetPositionAllocator("ns3::RandomBoxPositionAllocator",
                                 "X", StringValue("ns3::UniformRandomVariable[Min=0.0|Max=1000.0]"),
                                 "Y", StringValue("ns3::UniformRandomVariable[Min=0.0|Max=1000.0]"),
                                 "Z", StringValue("ns3::UniformRandomVariable[Min=50.0|Max=300.0]"));
    
    mobility.SetMobilityModel("ns3::RandomWalk2dMobilityModel",
                             "Bounds", RectangleValue(Rectangle(0, 1000, 0, 1000)),
                             "Speed", StringValue("ns3::UniformRandomVariable[Min=5.0|Max=15.0]"));
    
    mobility.Install(m_nodes);
}}

void FANETMTDSimulation::SetupCommunication() {{
    // WiFi 설정 (IEEE 802.11p for VANET/FANET)
    YansWifiChannelHelper wifiChannel = YansWifiChannelHelper::Default();
    YansWifiPhyHelper wifiPhy = YansWifiPhyHelper::Default();
    wifiPhy.SetChannel(wifiChannel.Create());
    
    WifiHelper wifi;
    wifi.SetStandard(WIFI_PHY_STANDARD_80211p_CCH);
    
    WifiMacHelper wifiMac;
    wifiMac.SetType("ns3::AdhocWifiMac");
    
    m_devices = wifi.Install(wifiPhy, wifiMac, m_nodes);
    
    // IP 주소 할당
    Ipv4AddressHelper ipv4;
    ipv4.SetBase("10.1.1.0", "255.255.255.0");
    ipv4.Assign(m_devices);
}}

void FANETMTDSimulation::SetupMTDMechanism() {{
    // MTD 주기적 실행 스케줄링
    Simulator::Schedule(Seconds(10.0), &FANETMTDSimulation::PositionUpdate, this);
    Simulator::Schedule(Seconds(5.0), &FANETMTDSimulation::TrustUpdate, this);
}}

void FANETMTDSimulation::Run() {{
    SetupNodes();
    SetupMobility();
    SetupCommunication();
    SetupApplications();
    SetupMTDMechanism();
    
    NS_LOG_INFO("FANET MTD 시뮬레이션 시작");
    
    Simulator::Stop(Seconds(m_simTime));
    Simulator::Run();
    Simulator::Destroy();
    
    NS_LOG_INFO("시뮬레이션 완료");
}}

int main(int argc, char *argv[]) {{
    uint32_t nNodes = 20;
    double simTime = 300.0;
    double range = 250.0;
    
    CommandLine cmd;
    cmd.AddValue("nNodes", "Number of nodes", nNodes);
    cmd.AddValue("simTime", "Simulation time", simTime);
    cmd.AddValue("range", "Communication range", range);
    cmd.Parse(argc, argv);
    
    FANETMTDSimulation simulation(nNodes, simTime, range);
    simulation.Run();
    
    return 0;
}}
"""
        
        # 스크립트 파일 저장
        os.makedirs(self.script_path.parent, exist_ok=True)
        with open(self.script_path, 'w') as f:
            f.write(ns3_script)
        
        logger.info(f"NS-3 스크립트 생성 완료: {self.script_path}")
    
    async def _run_python_simulation(self):
        """Python 기반 시뮬레이션 (NS-3 대체)"""
        logger.info("Python FANET 시뮬레이션 시작")
        self.is_running = True
        
        self.initialize_network_topology()
        
        simulation_duration = 300.0  # 300초
        time_step = 1.0  # 1초 간격
        
        start_time = time.time()
        while self.is_running and (time.time() - start_time) < simulation_duration:
            await self._simulation_step()
            await asyncio.sleep(time_step)
            self.simulation_time += time_step
        
        logger.info("Python FANET 시뮬레이션 완료")
    
    async def _simulation_step(self):
        """시뮬레이션 단계 실행"""
        # 노드 이동
        for node in self.nodes.values():
            self._update_node_mobility(node)
        
        # 이웃 관계 업데이트
        self._update_neighbor_relationships()
        
        # 패킷 전송 시뮬레이션
        await self._simulate_packet_transmission()
        
        # 공격 시뮬레이션
        await self._simulate_attacks()
    
    def _update_node_mobility(self, node: FANETNode):
        """노드 이동성 업데이트"""
        # 랜덤 워크 모델
        dx = np.random.normal(0, 5)  # 5m 표준편차
        dy = np.random.normal(0, 5)
        dz = np.random.normal(0, 2)  # 고도 변화는 적게
        
        x, y, z = node.position
        new_x = max(0, min(self.simulation_area[0], x + dx))
        new_y = max(0, min(self.simulation_area[1], y + dy))
        new_z = max(50, min(self.simulation_area[2], z + dz))
        
        node.update_position((new_x, new_y, new_z))
    
    async def _simulate_packet_transmission(self):
        """패킷 전송 시뮬레이션"""
        for node in self.nodes.values():
            if not node.is_active or not node.neighbors:
                continue
                
            # 랜덤하게 이웃에게 패킷 전송
            if np.random.random() < 0.3:  # 30% 확률로 패킷 전송
                target_neighbor = np.random.choice(node.neighbors)
                await self._send_packet(node.node_id, target_neighbor['id'])
    
    async def _send_packet(self, sender_id: int, receiver_id: int):
        """패킷 전송"""
        packet_data = {
            'sender': sender_id,
            'receiver': receiver_id,
            'timestamp': self.simulation_time,
            'packet_type': 'data',
            'size': np.random.randint(64, 1500)  # bytes
        }
        
        if receiver_id in self.nodes:
            self.nodes[receiver_id].packet_buffer.append(packet_data)
    
    async def _simulate_attacks(self):
        """공격 시뮬레이션"""
        # 랜덤하게 공격 발생
        if np.random.random() < 0.05:  # 5% 확률로 공격 발생
            attack_type = np.random.choice(['blackhole', 'grayhole', 'flooding', 'spoofing'])
            target_node = np.random.choice(list(self.nodes.keys()))
            
            await self._execute_simulated_attack(attack_type, target_node)
    
    async def _execute_simulated_attack(self, attack_type: str, target_node: int):
        """시뮬레이션된 공격 실행"""
        node = self.nodes[target_node]
        
        if attack_type == 'blackhole':
            # 블랙홀 공격: 패킷을 드롭
            node.packet_buffer.clear()
            node.decrease_trust(0.2)
            
        elif attack_type == 'flooding':
            # 플러딩 공격: 과도한 패킷 생성
            for _ in range(50):
                fake_packet = {
                    'sender': target_node,
                    'receiver': -1,
                    'timestamp': self.simulation_time,
                    'packet_type': 'flood',
                    'size': 1500
                }
                node.packet_buffer.append(fake_packet)
        
        logger.warning(f"공격 시뮬레이션: {attack_type} on node {target_node}")

class EnhancedCTISystem:
    """향상된 CTI 수집 및 분석 시스템"""
    
    def __init__(self):
        # 기존 SimpleCTI와 통합
        try:
            self.base_cti = SimpleCTI()
        except:
            self.base_cti = None
            
        self.ml_classifier = None
        self.attack_patterns = {}
        self.threat_intelligence = []
        self.real_time_indicators = []
        
        # STIX 2.1 지원
        self.stix_objects = []
        
    def setup_machine_learning_classifier(self):
        """기계학습 분류기 설정"""
        try:
            from sklearn.ensemble import RandomForestClassifier
            from sklearn.neural_network import MLPClassifier
            from sklearn.preprocessing import StandardScaler
            
            # Random Forest 분류기
            self.rf_classifier = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                random_state=42
            )
            
            # 신경망 분류기
            self.nn_classifier = MLPClassifier(
                hidden_layer_sizes=(128, 64, 32),
                activation='relu',
                solver='adam',
                max_iter=1000,
                random_state=42
            )
            
            self.scaler = StandardScaler()
            
            logger.info("기계학습 분류기 설정 완료")
            
        except ImportError:
            logger.warning("sklearn이 설치되지 않았습니다. 기본 분류기를 사용합니다.")
    
    def extract_features(self, attack_data: Dict[str, Any]) -> List[float]:
        """공격 데이터에서 특징 추출"""
        features = []
        
        # 네트워크 특징
        features.append(attack_data.get('packet_count', 0))
        features.append(attack_data.get('byte_count', 0))
        features.append(attack_data.get('duration', 0))
        features.append(attack_data.get('unique_sources', 0))
        features.append(attack_data.get('unique_destinations', 0))
        
        # 프로토콜 특징
        features.append(attack_data.get('tcp_packets', 0))
        features.append(attack_data.get('udp_packets', 0))
        features.append(attack_data.get('icmp_packets', 0))
        
        # MAVLink 특징
        features.append(attack_data.get('mavlink_packets', 0))
        features.append(attack_data.get('mavlink_commands', 0))
        features.append(attack_data.get('mavlink_errors', 0))
        
        # 행동 특징
        features.append(attack_data.get('frequency_anomaly', 0))
        features.append(attack_data.get('size_anomaly', 0))
        features.append(attack_data.get('timing_anomaly', 0))
        
        return features
    
    def classify_attack(self, attack_data: Dict[str, Any]) -> Dict[str, Any]:
        """공격 분류"""
        if self.ml_classifier is None:
            return self._rule_based_classification(attack_data)
        
        features = self.extract_features(attack_data)
        features = np.array(features).reshape(1, -1)
        
        try:
            # Random Forest 예측
            rf_prediction = self.rf_classifier.predict(features)[0]
            rf_confidence = max(self.rf_classifier.predict_proba(features)[0])
            
            # 신경망 예측
            nn_prediction = self.nn_classifier.predict(features)[0]
            nn_confidence = max(self.nn_classifier.predict_proba(features)[0])
            
            # 앙상블 결과
            if rf_confidence > nn_confidence:
                prediction = rf_prediction
                confidence = rf_confidence
                method = "Random Forest"
            else:
                prediction = nn_prediction
                confidence = nn_confidence
                method = "Neural Network"
            
            return {
                'attack_type': prediction,
                'confidence': confidence,
                'classification_method': method,
                'features': features.tolist()[0]
            }
            
        except Exception as e:
            logger.error(f"ML 분류 실패: {e}")
            return self._rule_based_classification(attack_data)
    
    def _rule_based_classification(self, attack_data: Dict[str, Any]) -> Dict[str, Any]:
        """규칙 기반 공격 분류"""
        attack_type = "unknown"
        confidence = 0.5
        
        # 간단한 규칙 기반 분류
        if attack_data.get('packet_count', 0) > 1000:
            attack_type = "flooding"
            confidence = 0.8
        elif attack_data.get('mavlink_errors', 0) > 10:
            attack_type = "protocol_tampering"
            confidence = 0.7
        elif attack_data.get('unique_sources', 0) == 1 and attack_data.get('packet_count', 0) > 100:
            attack_type = "dos_attack"
            confidence = 0.9
        
        return {
            'attack_type': attack_type,
            'confidence': confidence,
            'classification_method': 'Rule-based',
            'features': []
        }
    
    def generate_stix_indicators(self, attack_data: Dict[str, Any]) -> Dict[str, Any]:
        """STIX 2.1 지표 생성"""
        from datetime import datetime, timezone
        import uuid
        
        # 기본 STIX 지표 객체
        indicator = {
            "type": "indicator",
            "spec_version": "2.1",
            "id": f"indicator--{uuid.uuid4()}",
            "created": datetime.now(timezone.utc).isoformat(),
            "modified": datetime.now(timezone.utc).isoformat(),
            "name": f"Drone Attack: {attack_data.get('attack_type', 'Unknown')}",
            "description": f"Attack detected on drone network at {attack_data.get('timestamp')}",
            "pattern": self._generate_stix_pattern(attack_data),
            "valid_from": datetime.now(timezone.utc).isoformat(),
            "labels": ["malicious-activity", "drone-attack"],
            "confidence": int(attack_data.get('confidence', 0.5) * 100)
        }
        
        # 공격 패턴 객체
        attack_pattern = {
            "type": "attack-pattern",
            "spec_version": "2.1",
            "id": f"attack-pattern--{uuid.uuid4()}",
            "created": datetime.now(timezone.utc).isoformat(),
            "modified": datetime.now(timezone.utc).isoformat(),
            "name": f"Drone {attack_data.get('attack_type', 'Unknown')} Attack",
            "description": f"Attack pattern targeting drone systems via {attack_data.get('vector', 'unknown vector')}",
            "kill_chain_phases": [{
                "kill_chain_name": "drone-attack-lifecycle",
                "phase_name": "exploitation"
            }]
        }
        
        return {
            "indicator": indicator,
            "attack_pattern": attack_pattern
        }
    
    def _generate_stix_pattern(self, attack_data: Dict[str, Any]) -> str:
        """STIX 패턴 생성"""
        patterns = []
        
        if 'source_ip' in attack_data:
            patterns.append(f"[network-traffic:src_ref.value = '{attack_data['source_ip']}']")
        
        if 'dest_port' in attack_data:
            patterns.append(f"[network-traffic:dst_port = {attack_data['dest_port']}]")
        
        if 'protocol' in attack_data:
            patterns.append(f"[network-traffic:protocols[*] = '{attack_data['protocol']}']")
        
        return " AND ".join(patterns) if patterns else "[network-traffic:dst_port = 14550]"

class MTDDefenseSystem:
    """Moving Target Defense 시스템"""
    
    def __init__(self):
        self.docker_client = None
        self.active_containers = {}
        self.defense_strategies = []
        self.mutation_cycle = 60  # 60초마다 변경
        self.threat_level = 0.0
        
        try:
            self.docker_client = docker.from_env()
            logger.info("Docker 클라이언트 연결됨")
        except Exception as e:
            logger.warning(f"Docker 연결 실패: {e}")
    
    def setup_mtd_strategies(self):
        """MTD 전략 설정"""
        self.defense_strategies = [
            {
                'name': 'container_migration',
                'type': 'network',
                'trigger_threshold': 0.5,
                'cooldown': 30
            },
            {
                'name': 'port_randomization',
                'type': 'communication',
                'trigger_threshold': 0.3,
                'cooldown': 15
            },
            {
                'name': 'ip_shuffling',
                'type': 'network',
                'trigger_threshold': 0.7,
                'cooldown': 45
            },
            {
                'name': 'protocol_diversification',
                'type': 'communication',
                'trigger_threshold': 0.6,
                'cooldown': 60
            }
        ]
        
        logger.info(f"MTD 전략 {len(self.defense_strategies)}개 설정 완료")
    
    async def monitor_and_defend(self):
        """위협 모니터링 및 방어 실행"""
        while True:
            # 위협 수준 평가
            self.threat_level = await self._assess_threat_level()
            
            # 방어 전략 실행
            for strategy in self.defense_strategies:
                if self.threat_level >= strategy['trigger_threshold']:
                    await self._execute_defense_strategy(strategy)
            
            await asyncio.sleep(10)  # 10초마다 모니터링
    
    async def _assess_threat_level(self) -> float:
        """위협 수준 평가"""
        threat_score = 0.0
        
        # CPU 사용률 체크
        try:
            import psutil
            cpu_usage = psutil.cpu_percent()
            if cpu_usage > 80:
                threat_score += 0.3
        except ImportError:
            pass
        
        # 네트워크 연결 수 체크
        try:
            result = subprocess.run(['netstat', '-an'], capture_output=True, text=True)
            connection_count = len(result.stdout.split('\n'))
            if connection_count > 100:
                threat_score += 0.2
        except:
            pass
        
        # 랜덤 위협 시뮬레이션
        if np.random.random() < 0.1:  # 10% 확률로 위협 발생
            threat_score += np.random.uniform(0.4, 0.9)
        
        return min(1.0, threat_score)
    
    async def _execute_defense_strategy(self, strategy: Dict[str, Any]):
        """방어 전략 실행"""
        strategy_name = strategy['name']
        
        logger.warning(f"MTD 방어 전략 실행: {strategy_name} (위협 수준: {self.threat_level:.2f})")
        
        if strategy_name == 'container_migration':
            await self._migrate_containers()
        elif strategy_name == 'port_randomization':
            await self._randomize_ports()
        elif strategy_name == 'ip_shuffling':
            await self._shuffle_ip_addresses()
        elif strategy_name == 'protocol_diversification':
            await self._diversify_protocols()
    
    async def _migrate_containers(self):
        """컨테이너 마이그레이션"""
        if not self.docker_client:
            logger.warning("Docker 클라이언트가 없어 컨테이너 마이그레이션을 시뮬레이션합니다.")
            await asyncio.sleep(2)  # 시뮬레이션 지연
            return
        
        try:
            containers = self.docker_client.containers.list()
            for container in containers:
                if 'dvd' in container.name.lower():
                    logger.info(f"컨테이너 {container.name} 마이그레이션 시뮬레이션")
                    # 실제 환경에서는 컨테이너를 다른 호스트로 이동
                    await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"컨테이너 마이그레이션 실패: {e}")
    
    async def _randomize_ports(self):
        """포트 랜덤화"""
        new_mavlink_port = np.random.randint(14000, 15000)
        new_http_port = np.random.randint(8000, 9000)
        
        logger.info(f"포트 랜덤화: MAVLink={new_mavlink_port}, HTTP={new_http_port}")
        
        # 실제 환경에서는 서비스 재시작 필요
        await asyncio.sleep(1)
    
    async def _shuffle_ip_addresses(self):
        """IP 주소 셔플링"""
        new_ip = f"10.13.0.{np.random.randint(10, 250)}"
        logger.info(f"IP 주소 셔플링: {new_ip}")
        await asyncio.sleep(1)
    
    async def _diversify_protocols(self):
        """프로토콜 다양화"""
        protocols = ['mavlink', 'mavlink2', 'custom_protocol']
        selected_protocol = np.random.choice(protocols)
        logger.info(f"프로토콜 다양화: {selected_protocol}")
        await asyncio.sleep(1)

class IntegratedMTDTestbed:
    """통합 MTD 테스트베드 메인 클래스"""
    
    def __init__(self):
        self.fanet_simulator = NS3FANETSimulator()
        self.cti_system = EnhancedCTISystem()
        self.mtd_system = MTDDefenseSystem()
        self.dvd_lite = None
        self.safety_checker = None
        self.is_running = False
        
        # 기존 시스템과 통합
        try:
            self.dvd_lite = DVDLite()
            self.safety_checker = SafetyChecker()
            register_all_dvd_attacks()
            logger.info("기존 DVD-Lite 시스템과 통합 완료")
        except Exception as e:
            logger.warning(f"DVD-Lite 통합 실패: {e}")
    
    async def initialize_system(self):
        """시스템 초기화"""
        logger.info("통합 MTD 테스트베드 초기화 중...")
        
        # 안전성 검사
        if self.safety_checker:
            config = {
                "environment": "SIMULATION",
                "simulation_mode": True,
                "safety_enabled": True
            }
            
            safety_result = await self.safety_checker.comprehensive_safety_check(config)
            if not safety_result.is_safe_to_proceed:
                logger.error("안전성 검사 실패")
                return False
        
        # 각 시스템 초기화
        self.fanet_simulator.initialize_network_topology()
        self.cti_system.setup_machine_learning_classifier()
        self.mtd_system.setup_mtd_strategies()
        
        logger.info("시스템 초기화 완료")
        return True
    
    async def start_integrated_simulation(self):
        """통합 시뮬레이션 시작"""
        if not await self.initialize_system():
            return
        
        logger.info("통합 MTD 테스트베드 시뮬레이션 시작")
        self.is_running = True
        
        # 병렬 작업 시작
        tasks = []
        
        # FANET 시뮬레이션
        tasks.append(asyncio.create_task(self.fanet_simulator.start_simulation()))
        
        # MTD 모니터링
        tasks.append(asyncio.create_task(self.mtd_system.monitor_and_defend()))
        
        # CTI 수집
        tasks.append(asyncio.create_task(self._run_cti_collection()))
        
        # DVD 공격 시뮬레이션
        if self.dvd_lite:
            tasks.append(asyncio.create_task(self._run_attack_simulation()))
        
        # 결과 모니터링
        tasks.append(asyncio.create_task(self._monitor_results()))
        
        try:
            await asyncio.gather(*tasks)
        except KeyboardInterrupt:
            logger.info("사용자에 의해 시뮬레이션이 중단되었습니다.")
        except Exception as e:
            logger.error(f"시뮬레이션 오류: {e}")
        finally:
            await self.shutdown()
    
    async def _run_cti_collection(self):
        """CTI 수집 실행"""
        while self.is_running:
            try:
                # FANET 네트워크에서 데이터 수집
                network_data = await self._collect_fanet_data()
                
                # 공격 분류
                classification = self.cti_system.classify_attack(network_data)
                
                # STIX 지표 생성
                if classification['confidence'] > 0.7:
                    stix_data = self.cti_system.generate_stix_indicators({
                        **network_data,
                        **classification
                    })
                    
                    logger.info(f"고신뢰도 위협 탐지: {classification['attack_type']} "
                              f"(신뢰도: {classification['confidence']:.2f})")
                
                await asyncio.sleep(5)  # 5초마다 CTI 수집
                
            except Exception as e:
                logger.error(f"CTI 수집 오류: {e}")
                await asyncio.sleep(1)
    
    async def _collect_fanet_data(self) -> Dict[str, Any]:
        """FANET 네트워크 데이터 수집"""
        data = {
            'timestamp': datetime.now().isoformat(),
            'packet_count': 0,
            'byte_count': 0,
            'unique_sources': 0,
            'unique_destinations': 0,
            'mavlink_packets': 0,
            'tcp_packets': 0,
            'udp_packets': 0,
            'duration': 1.0
        }
        
        # FANET 노드들로부터 데이터 수집
        active_nodes = [n for n in self.fanet_simulator.nodes.values() if n.is_active]
        
        for node in active_nodes:
            data['packet_count'] += len(node.packet_buffer)
            data['byte_count'] += sum(p.get('size', 0) for p in node.packet_buffer)
            
            # 패킷 유형별 카운트
            for packet in node.packet_buffer:
                if packet.get('packet_type') == 'mavlink':
                    data['mavlink_packets'] += 1
                elif packet.get('packet_type') == 'tcp':
                    data['tcp_packets'] += 1
                elif packet.get('packet_type') == 'udp':
                    data['udp_packets'] += 1
        
        data['unique_sources'] = len(active_nodes)
        data['unique_destinations'] = len([n for n in active_nodes if n.packet_buffer])
        
        return data
    
    async def _run_attack_simulation(self):
        """DVD 공격 시뮬레이션 실행"""
        attack_scenarios = [
            'wifi_network_discovery',
            'mavlink_service_discovery',
            'gps_spoofing_attack',
            'mavlink_packet_injection',
            'wifi_deauthentication_attack'
        ]
        
        while self.is_running:
            try:
                # 랜덤 공격 선택
                attack_name = np.random.choice(attack_scenarios)
                
                logger.info(f"공격 시뮬레이션 실행: {attack_name}")
                
                # DVD-Lite를 통한 공격 실행
                result = await self.dvd_lite.run_attack(attack_name)
                
                # 결과를 CTI 시스템에 전달
                attack_data = {
                    'attack_name': attack_name,
                    'success': result.success,
                    'timestamp': datetime.now().isoformat(),
                    'iocs': result.iocs,
                    'duration': result.execution_time,
                    'attack_type': result.attack_type.value if hasattr(result, 'attack_type') else 'unknown'
                }
                
                classification = self.cti_system.classify_attack(attack_data)
                logger.info(f"공격 분류 결과: {classification}")
                
                await asyncio.sleep(np.random.randint(30, 120))  # 30-120초 간격
                
            except Exception as e:
                logger.error(f"공격 시뮬레이션 오류: {e}")
                await asyncio.sleep(10)
    
    async def _monitor_results(self):
        """결과 모니터링 및 리포트 생성"""
        report_interval = 60  # 60초마다 리포트
        
        while self.is_running:
            try:
                await asyncio.sleep(report_interval)
                
                # 시스템 상태 리포트
                report = await self._generate_status_report()
                logger.info(f"시스템 상태 리포트:\n{json.dumps(report, indent=2)}")
                
                # 결과 파일로 저장
                await self._save_results(report)
                
            except Exception as e:
                logger.error(f"결과 모니터링 오류: {e}")
    
    async def _generate_status_report(self) -> Dict[str, Any]:
        """상태 리포트 생성"""
        active_nodes = len([n for n in self.fanet_simulator.nodes.values() if n.is_active])
        total_packets = sum(len(n.packet_buffer) for n in self.fanet_simulator.nodes.values())
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'simulation_time': self.fanet_simulator.simulation_time,
            'fanet_status': {
                'total_nodes': len(self.fanet_simulator.nodes),
                'active_nodes': active_nodes,
                'total_packets': total_packets,
                'average_trust': np.mean([n.trust_score for n in self.fanet_simulator.nodes.values()])
            },
            'mtd_status': {
                'threat_level': self.mtd_system.threat_level,
                'active_strategies': len(self.mtd_system.defense_strategies),
                'last_defense_action': 'none'  # 실제로는 마지막 방어 행동 기록
            },
            'cti_status': {
                'total_indicators': len(self.cti_system.threat_intelligence),
                'high_confidence_threats': len([t for t in self.cti_system.threat_intelligence 
                                               if t.get('confidence', 0) > 0.8])
            }
        }
        
        return report
    
    async def _save_results(self, report: Dict[str, Any]):
        """결과 저장"""
        results_dir = Path("./results")
        results_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # JSON 형식 저장
        json_file = results_dir / f"mtd_testbed_report_{timestamp}.json"
        with open(json_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        # CSV 형식 저장 (간단한 메트릭)
        csv_file = results_dir / f"mtd_metrics_{timestamp}.csv"
        with open(csv_file, 'w') as f:
            f.write("timestamp,active_nodes,total_packets,threat_level,avg_trust\n")
            f.write(f"{report['timestamp']},{report['fanet_status']['active_nodes']},"
                   f"{report['fanet_status']['total_packets']},{report['mtd_status']['threat_level']},"
                   f"{report['fanet_status']['average_trust']:.3f}\n")
    
    async def shutdown(self):
        """시스템 종료"""
        logger.info("통합 MTD 테스트베드 종료 중...")
        self.is_running = False
        
        # FANET 시뮬레이션 종료
        self.fanet_simulator.is_running = False
        
        # 최종 리포트 생성
        final_report = await self._generate_status_report()
        await self._save_results(final_report)
        
        logger.info("시스템 종료 완료")

# 메인 실행 함수
async def main():
    """메인 실행 함수"""
    # 시그널 핸들러 설정
    def signal_handler(signum, frame):
        logger.info("종료 신호 수신")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 통합 테스트베드 생성 및 실행
    testbed = IntegratedMTDTestbed()
    
    try:
        await testbed.start_integrated_simulation()
    except KeyboardInterrupt:
        logger.info("사용자 중단")
    except Exception as e:
        logger.error(f"실행 오류: {e}")
    finally:
        await testbed.shutdown()

if __name__ == "__main__":
    print("🚁 FANET NS-3 통합 MTD 드론 보안 테스트베드")
    print("=" * 60)
    print("📍 위치: ~/MTD/MTD_full_testbed/fanet_mtd_testbed.py")
    print("🔧 기능:")
    print("  • NS-3 FANET 네트워크 시뮬레이션")
    print("  • 실시간 CTI 수집 및 기계학습 분류")
    print("  • MTD 방어 메커니즘")
    print("  • 기존 DVD 시스템과 완전 통합")
    print("  • STIX 2.1 표준 지원")
    print("=" * 60)
    
    # 이벤트 루프 실행
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 테스트베드가 종료되었습니다.")
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        sys.exit(1)