# 파일: /home/kali/MTD/MTD_full_testbed/dvd_ns3_integration/dvd_monitor_service.py
# 목적: DVD 공격 시나리오와 NS-3 FANET 네트워크 연동을 위한 실시간 모니터링 서비스
# 기반: damn-vulnerable-drone과 NS-3 FANET 시뮬레이션 통합

import asyncio
import json
import time
import subprocess
import psutil
import logging
import docker
import socket
import threading
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path
import xml.etree.ElementTree as ET

# 로그 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/home/kali/MTD/MTD_full_testbed/logs/dvd_ns3_integration.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('DVD-NS3-Monitor')

@dataclass
class DVDContainerStatus:
    """DVD 도커 컨테이너 상태"""
    container_id: str
    name: str
    status: str
    cpu_usage: float
    memory_usage: float
    network_traffic: Dict[str, int]
    attack_indicators: List[str]
    timestamp: float

@dataclass
class AttackEvent:
    """공격 이벤트 정보"""
    attack_type: str
    attack_script: str
    target_service: str
    start_time: float
    status: str
    iocs: List[str]
    impact_level: str

@dataclass
class NS3NetworkState:
    """NS-3 네트워크 상태"""
    node_count: int
    active_connections: int
    packet_loss_rate: float
    latency_ms: float
    throughput_mbps: float
    topology_changes: int

class DVDDockerMonitor:
    """DVD 도커 컨테이너 모니터링"""
    
    def __init__(self):
        self.client = docker.from_env()
        self.containers = {}
        self.monitoring = False
        
    async def start_monitoring(self):
        """도커 모니터링 시작"""
        self.monitoring = True
        logger.info("🐳 DVD 도커 컨테이너 모니터링 시작")
        
        while self.monitoring:
            try:
                # DVD 관련 컨테이너 탐지
                containers = self.client.containers.list(all=True)
                dvd_containers = [c for c in containers if 'dvd' in c.name.lower() or 'drone' in c.name.lower()]
                
                for container in dvd_containers:
                    status = await self._analyze_container(container)
                    self.containers[container.id] = status
                    
                    # 공격 지표 탐지
                    if status.attack_indicators:
                        logger.warning(f"🚨 공격 지표 탐지: {container.name} - {status.attack_indicators}")
                
                await asyncio.sleep(5)
                
            except Exception as e:
                logger.error(f"도커 모니터링 오류: {e}")
                await asyncio.sleep(10)
    
    async def _analyze_container(self, container) -> DVDContainerStatus:
        """컨테이너 상태 분석"""
        try:
            # 기본 상태 정보
            stats = container.stats(stream=False)
            
            # CPU 사용률 계산
            cpu_usage = self._calculate_cpu_usage(stats)
            
            # 메모리 사용률 계산
            memory_usage = self._calculate_memory_usage(stats)
            
            # 네트워크 트래픽 정보
            network_traffic = self._get_network_traffic(stats)
            
            # 공격 지표 탐지
            attack_indicators = await self._detect_attack_indicators(container)
            
            return DVDContainerStatus(
                container_id=container.id[:12],
                name=container.name,
                status=container.status,
                cpu_usage=cpu_usage,
                memory_usage=memory_usage,
                network_traffic=network_traffic,
                attack_indicators=attack_indicators,
                timestamp=time.time()
            )
            
        except Exception as e:
            logger.error(f"컨테이너 분석 오류: {e}")
            return DVDContainerStatus("", "", "error", 0, 0, {}, [], time.time())
    
    def _calculate_cpu_usage(self, stats) -> float:
        """CPU 사용률 계산"""
        try:
            cpu_delta = stats['cpu_stats']['cpu_usage']['total_usage'] - \
                       stats['precpu_stats']['cpu_usage']['total_usage']
            system_delta = stats['cpu_stats']['system_cpu_usage'] - \
                          stats['precpu_stats']['system_cpu_usage']
            
            if system_delta > 0:
                cpu_usage = (cpu_delta / system_delta) * 100.0
                return round(cpu_usage, 2)
        except:
            pass
        return 0.0
    
    def _calculate_memory_usage(self, stats) -> float:
        """메모리 사용률 계산"""
        try:
            memory_usage = stats['memory_stats']['usage']
            memory_limit = stats['memory_stats']['limit']
            return round((memory_usage / memory_limit) * 100, 2)
        except:
            return 0.0
    
    def _get_network_traffic(self, stats) -> Dict[str, int]:
        """네트워크 트래픽 정보 추출"""
        try:
            networks = stats.get('networks', {})
            total_rx = sum(net['rx_bytes'] for net in networks.values())
            total_tx = sum(net['tx_bytes'] for net in networks.values())
            return {'rx_bytes': total_rx, 'tx_bytes': total_tx}
        except:
            return {'rx_bytes': 0, 'tx_bytes': 0}
    
    async def _detect_attack_indicators(self, container) -> List[str]:
        """공격 지표 탐지"""
        indicators = []
        
        try:
            # 로그에서 공격 패턴 탐지
            logs = container.logs(tail=100).decode('utf-8', errors='ignore')
            
            attack_patterns = [
                ('SQL_INJECTION', ['union select', 'drop table', '-- ', "' or 1=1"]),
                ('XSS_ATTACK', ['<script>', 'javascript:', 'onerror=']),
                ('COMMAND_INJECTION', ['&& cat', '; cat', '| cat', '`cat`']),
                ('PATH_TRAVERSAL', ['../../../', '....//....', '%2e%2e%2f']),
                ('BRUTE_FORCE', ['401 Unauthorized', 'authentication failed', 'invalid credentials']),
                ('DOS_ATTACK', ['connection timeout', 'too many requests', 'service unavailable'])
            ]
            
            for attack_type, patterns in attack_patterns:
                for pattern in patterns:
                    if pattern.lower() in logs.lower():
                        indicators.append(f"{attack_type}:{pattern}")
            
            # 포트 스캔 탐지
            if self._detect_port_scan(container):
                indicators.append("PORT_SCAN:detected")
            
        except Exception as e:
            logger.debug(f"공격 지표 탐지 오류: {e}")
        
        return indicators
    
    def _detect_port_scan(self, container) -> bool:
        """포트 스캔 탐지"""
        try:
            # 네트워크 연결 상태 확인
            exec_result = container.exec_run("netstat -an")
            if exec_result.exit_code == 0:
                output = exec_result.output.decode()
                # 비정상적으로 많은 연결이 있으면 포트 스캔으로 간주
                connection_count = output.count('ESTABLISHED') + output.count('SYN_SENT')
                return connection_count > 50
        except:
            pass
        return False
    
    def stop_monitoring(self):
        """모니터링 중지"""
        self.monitoring = False
        logger.info("🐳 도커 모니터링 중지")

class DVDAttackMonitor:
    """DVD 공격 스크립트 모니터링"""
    
    def __init__(self, attack_dir: str = "/home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks"):
        self.attack_dir = Path(attack_dir)
        self.active_attacks = {}
        self.monitoring = False
        
    async def start_monitoring(self):
        """공격 모니터링 시작"""
        self.monitoring = True
        logger.info("⚔️ DVD 공격 스크립트 모니터링 시작")
        
        while self.monitoring:
            try:
                # 실행 중인 공격 스크립트 탐지
                await self._detect_running_attacks()
                
                # IOC 파일 모니터링
                await self._monitor_ioc_files()
                
                await asyncio.sleep(3)
                
            except Exception as e:
                logger.error(f"공격 모니터링 오류: {e}")
                await asyncio.sleep(5)
    
    async def _detect_running_attacks(self):
        """실행 중인 공격 스크립트 탐지"""
        try:
            # 공격 관련 프로세스 탐지
            attack_patterns = [
                'reconnaissance', 'protocol_tampering', 'denial_of_service',
                'injection', 'exfiltration', 'firmware_attacks'
            ]
            
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
                try:
                    cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
                    
                    # DVD 공격 스크립트 실행 탐지
                    for pattern in attack_patterns:
                        if pattern in cmdline and 'dvd_attacks' in cmdline:
                            attack_id = f"{proc.info['pid']}_{pattern}"
                            
                            if attack_id not in self.active_attacks:
                                self.active_attacks[attack_id] = AttackEvent(
                                    attack_type=pattern,
                                    attack_script=cmdline,
                                    target_service="DVD",
                                    start_time=proc.info['create_time'],
                                    status="RUNNING",
                                    iocs=[],
                                    impact_level="UNKNOWN"
                                )
                                logger.info(f"🎯 새로운 공격 탐지: {pattern} (PID: {proc.info['pid']})")
                
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
                    
        except Exception as e:
            logger.error(f"프로세스 탐지 오류: {e}")
    
    async def _monitor_ioc_files(self):
        """IOC 파일 모니터링"""
        try:
            ioc_dir = Path("/tmp")
            ioc_files = list(ioc_dir.glob("*iocs.txt"))
            
            for ioc_file in ioc_files:
                if ioc_file.stat().st_mtime > time.time() - 60:  # 1분 이내 수정된 파일
                    with open(ioc_file, 'r') as f:
                        iocs = [line.strip() for line in f.readlines() if line.strip()]
                    
                    if iocs:
                        attack_type = ioc_file.stem.replace('_iocs', '')
                        logger.info(f"📄 IOC 업데이트: {attack_type} - {len(iocs)}개 지표")
                        
                        # 기존 공격 이벤트에 IOC 추가
                        for attack_id, attack in self.active_attacks.items():
                            if attack_type in attack.attack_type:
                                attack.iocs.extend(iocs)
                                attack.impact_level = self._assess_impact_level(iocs)
                        
        except Exception as e:
            logger.error(f"IOC 파일 모니터링 오류: {e}")
    
    def _assess_impact_level(self, iocs: List[str]) -> str:
        """공격 영향도 평가"""
        critical_indicators = ['root_access', 'system_compromise', 'data_exfiltration']
        high_indicators = ['privilege_escalation', 'service_disruption', 'unauthorized_access']
        
        ioc_text = ' '.join(iocs).lower()
        
        if any(indicator in ioc_text for indicator in critical_indicators):
            return "CRITICAL"
        elif any(indicator in ioc_text for indicator in high_indicators):
            return "HIGH"
        elif len(iocs) > 10:
            return "MEDIUM"
        else:
            return "LOW"
    
    def stop_monitoring(self):
        """모니터링 중지"""
        self.monitoring = False
        logger.info("⚔️ 공격 모니터링 중지")

class NS3FANETConnector:
    """NS-3 FANET 시뮬레이션 연동"""
    
    def __init__(self, ns3_host: str = "127.0.0.1", ns3_port: int = 9999):
        self.ns3_host = ns3_host
        self.ns3_port = ns3_port
        self.socket = None
        self.connected = False
        
    async def connect(self) -> bool:
        """NS-3 서비스에 연결"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.ns3_host, self.ns3_port))
            self.connected = True
            logger.info(f"🌐 NS-3 FANET 연결 성공: {self.ns3_host}:{self.ns3_port}")
            return True
        except Exception as e:
            logger.error(f"NS-3 연결 실패: {e}")
            return False
    
    async def send_attack_event(self, attack_event: AttackEvent):
        """공격 이벤트를 NS-3에 전송"""
        if not self.connected:
            if not await self.connect():
                return
        
        try:
            # 공격 이벤트를 NS-3 명령으로 변환
            ns3_command = self._convert_to_ns3_command(attack_event)
            
            message = json.dumps({
                'type': 'attack_event',
                'command': ns3_command,
                'timestamp': time.time(),
                'attack_data': asdict(attack_event)
            })
            
            self.socket.send(message.encode() + b'\n')
            logger.info(f"📡 NS-3에 공격 이벤트 전송: {attack_event.attack_type}")
            
        except Exception as e:
            logger.error(f"NS-3 이벤트 전송 오류: {e}")
            self.connected = False
    
    def _convert_to_ns3_command(self, attack_event: AttackEvent) -> str:
        """공격 이벤트를 NS-3 시뮬레이션 명령으로 변환"""
        command_map = {
            'reconnaissance': 'INCREASE_SCAN_TRAFFIC',
            'protocol_tampering': 'INJECT_MALFORMED_PACKETS',
            'denial_of_service': 'SIMULATE_JAMMING',
            'injection': 'MODIFY_ROUTING_TABLE',
            'exfiltration': 'INCREASE_DATA_FLOW',
            'firmware_attacks': 'SIMULATE_NODE_COMPROMISE'
        }
        
        return command_map.get(attack_event.attack_type, 'UNKNOWN_ATTACK')
    
    async def get_network_state(self) -> Optional[NS3NetworkState]:
        """NS-3 네트워크 상태 조회"""
        if not self.connected:
            return None
        
        try:
            query = json.dumps({'type': 'network_state_query'})
            self.socket.send(query.encode() + b'\n')
            
            response = self.socket.recv(1024).decode()
            data = json.loads(response)
            
            return NS3NetworkState(
                node_count=data.get('nodes', 0),
                active_connections=data.get('connections', 0),
                packet_loss_rate=data.get('packet_loss', 0.0),
                latency_ms=data.get('latency', 0.0),
                throughput_mbps=data.get('throughput', 0.0),
                topology_changes=data.get('topology_changes', 0)
            )
            
        except Exception as e:
            logger.error(f"네트워크 상태 조회 오류: {e}")
            return None
    
    def disconnect(self):
        """연결 종료"""
        if self.socket:
            self.socket.close()
            self.connected = False
            logger.info("🌐 NS-3 연결 종료")

class DVDToNS3IntegrationService:
    """DVD와 NS-3 통합 서비스"""
    
    def __init__(self):
        self.docker_monitor = DVDDockerMonitor()
        self.attack_monitor = DVDAttackMonitor()
        self.ns3_connector = NS3FANETConnector()
        self.running = False
        
        # 상태 저장
        self.integration_stats = {
            'total_events': 0,
            'dvd_containers': 0,
            'active_attacks': 0,
            'ns3_connected': False,
            'start_time': None
        }
    
    async def start_service(self):
        """통합 서비스 시작"""
        self.running = True
        self.integration_stats['start_time'] = time.time()
        
        logger.info("🚀 DVD-NS3 통합 서비스 시작")
        
        # NS-3 연결
        await self.ns3_connector.connect()
        self.integration_stats['ns3_connected'] = self.ns3_connector.connected
        
        # 모니터링 태스크 시작
        tasks = [
            asyncio.create_task(self.docker_monitor.start_monitoring()),
            asyncio.create_task(self.attack_monitor.start_monitoring()),
            asyncio.create_task(self._integration_loop())
        ]
        
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            logger.info("서비스 중지 요청됨")
        finally:
            await self.stop_service()
    
    async def _integration_loop(self):
        """통합 처리 루프"""
        while self.running:
            try:
                # DVD 컨테이너 상태 업데이트
                self.integration_stats['dvd_containers'] = len(self.docker_monitor.containers)
                
                # 활성 공격 업데이트
                self.integration_stats['active_attacks'] = len(self.attack_monitor.active_attacks)
                
                # 새로운 공격 이벤트 처리
                for attack_id, attack_event in self.attack_monitor.active_attacks.items():
                    if attack_event.status == "RUNNING":
                        await self.ns3_connector.send_attack_event(attack_event)
                        attack_event.status = "SENT_TO_NS3"
                        self.integration_stats['total_events'] += 1
                
                # NS-3 네트워크 상태 조회
                network_state = await self.ns3_connector.get_network_state()
                if network_state:
                    logger.debug(f"NS-3 상태: 노드={network_state.node_count}, 연결={network_state.active_connections}")
                
                # 상태 로그 (10초마다)
                if int(time.time()) % 10 == 0:
                    self._log_integration_status()
                
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"통합 루프 오류: {e}")
                await asyncio.sleep(5)
    
    def _log_integration_status(self):
        """통합 서비스 상태 로그"""
        runtime = int(time.time() - self.integration_stats['start_time'])
        logger.info(
            f"📊 통합 상태 - 런타임: {runtime}초, "
            f"DVD 컨테이너: {self.integration_stats['dvd_containers']}개, "
            f"활성 공격: {self.integration_stats['active_attacks']}개, "
            f"전송 이벤트: {self.integration_stats['total_events']}개, "
            f"NS-3 연결: {'✓' if self.integration_stats['ns3_connected'] else '✗'}"
        )
    
    async def stop_service(self):
        """서비스 중지"""
        self.running = False
        
        # 모니터링 중지
        self.docker_monitor.stop_monitoring()
        self.attack_monitor.stop_monitoring()
        
        # NS-3 연결 종료
        self.ns3_connector.disconnect()
        
        logger.info("🛑 DVD-NS3 통합 서비스 중지")
    
    def get_status_report(self) -> Dict[str, Any]:
        """상태 보고서 생성"""
        return {
            'service_status': 'RUNNING' if self.running else 'STOPPED',
            'integration_stats': self.integration_stats,
            'dvd_containers': {cid: asdict(status) for cid, status in self.docker_monitor.containers.items()},
            'active_attacks': {aid: asdict(attack) for aid, attack in self.attack_monitor.active_attacks.items()},
            'timestamp': time.time()
        }

async def main():
    """메인 실행 함수"""
    service = DVDToNS3IntegrationService()
    
    try:
        await service.start_service()
    except KeyboardInterrupt:
        logger.info("사용자 중단 요청")
    except Exception as e:
        logger.error(f"서비스 실행 오류: {e}")
    finally:
        await service.stop_service()

if __name__ == "__main__":
    asyncio.run(main())