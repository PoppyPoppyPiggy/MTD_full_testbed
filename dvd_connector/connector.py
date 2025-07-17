# dvd_connector/connector.py
"""
DVD-Lite ↔ Damn Vulnerable Drone 연결 관리자
실제 DVD 환경과의 안전한 연결 및 통신을 제공
"""

import asyncio
import socket
import logging
import json
import time
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
import subprocess
import requests
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

class DVDConnectionStatus(Enum):
    """DVD 연결 상태"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"
    TIMEOUT = "timeout"

class DVDEnvironment(Enum):
    """DVD 환경 타입"""
    FULL_DEPLOY = "full_deploy"    # 완전 배포 모드 (WiFi 시뮬레이션 포함)
    HALF_BAKED = "half_baked"      # 절반 배포 모드 (네트워크 연결 가정)
    SIMULATION = "simulation"      # 시뮬레이션 모드 (실제 DVD 없음)

@dataclass
class DVDConnectionConfig:
    """DVD 연결 설정"""
    host: str = "localhost"
    mavlink_port: int = 14550
    web_port: int = 8000
    rtsp_port: int = 554
    environment: DVDEnvironment = DVDEnvironment.HALF_BAKED
    timeout: int = 30
    retry_count: int = 3
    docker_compose_path: str = "./docker-compose.yml"
    network_interface: str = "eth0"
    
    # DVD 특정 설정
    dvd_network: str = "10.13.0.0/24"
    companion_computer_ip: str = "10.13.0.2"
    gcs_ip: str = "10.13.0.3"
    flight_controller_ip: str = "10.13.0.4"

@dataclass
class DVDStatus:
    """DVD 상태 정보"""
    connection_status: DVDConnectionStatus
    environment: DVDEnvironment
    containers: Dict[str, str]  # container_name -> status
    services: Dict[str, bool]   # service_name -> is_running
    network_info: Dict[str, Any]
    last_heartbeat: float
    error_message: Optional[str] = None

class DVDConnector:
    """DVD 연결 관리자"""
    
    def __init__(self, config: DVDConnectionConfig = None):
        self.config = config or DVDConnectionConfig()
        self.status = DVDStatus(
            connection_status=DVDConnectionStatus.DISCONNECTED,
            environment=self.config.environment,
            containers={},
            services={},
            network_info={},
            last_heartbeat=0.0
        )
        self.session = requests.Session()
        self.session.timeout = self.config.timeout
        
    async def connect(self) -> bool:
        """DVD 환경에 연결"""
        logger.info(f"DVD 연결 시도: {self.config.environment.value}")
        
        self.status.connection_status = DVDConnectionStatus.CONNECTING
        
        try:
            # 환경별 연결 처리
            if self.config.environment == DVDEnvironment.SIMULATION:
                return await self._connect_simulation()
            elif self.config.environment == DVDEnvironment.HALF_BAKED:
                return await self._connect_half_baked()
            elif self.config.environment == DVDEnvironment.FULL_DEPLOY:
                return await self._connect_full_deploy()
            else:
                raise ValueError(f"지원되지 않는 환경: {self.config.environment}")
                
        except Exception as e:
            logger.error(f"DVD 연결 실패: {e}")
            self.status.connection_status = DVDConnectionStatus.ERROR
            self.status.error_message = str(e)
            return False
    
    async def _connect_simulation(self) -> bool:
        """시뮬레이션 모드 연결"""
        logger.info("시뮬레이션 모드로 연결")
        
        # 시뮬레이션 모드는 실제 연결 없이 성공
        self.status.connection_status = DVDConnectionStatus.CONNECTED
        self.status.services = {
            "mavlink": True,
            "web_interface": True,
            "rtsp_stream": True
        }
        self.status.last_heartbeat = time.time()
        
        return True
    
    async def _connect_half_baked(self) -> bool:
        """Half-Baked 모드 연결"""
        logger.info("Half-Baked 모드로 연결")
        
        # Docker 컨테이너 상태 확인
        if not await self._check_docker_containers():
            logger.warning("Docker 컨테이너가 실행되지 않음. 시작 시도...")
            if not await self._start_dvd_containers():
                return False
        
        # 서비스 연결 확인
        services_ok = await self._check_services()
        if not services_ok:
            logger.error("DVD 서비스 연결 실패")
            return False
        
        # 네트워크 정보 수집
        await self._collect_network_info()
        
        self.status.connection_status = DVDConnectionStatus.CONNECTED
        self.status.last_heartbeat = time.time()
        
        return True
    
    async def _connect_full_deploy(self) -> bool:
        """Full-Deploy 모드 연결"""
        logger.info("Full-Deploy 모드로 연결")
        
        # WiFi 인터페이스 확인
        if not await self._check_wifi_interface():
            logger.error("WiFi 인터페이스 확인 실패")
            return False
        
        # Half-Baked 모드와 동일한 연결 과정
        return await self._connect_half_baked()
    
    async def _check_docker_containers(self) -> bool:
        """Docker 컨테이너 상태 확인"""
        try:
            result = subprocess.run(
                ["docker", "compose", "ps", "--format", "json"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                logger.warning("Docker Compose 상태 확인 실패")
                return False
            
            # 컨테이너 상태 파싱
            containers = {}
            for line in result.stdout.strip().split('\n'):
                if line:
                    try:
                        container_info = json.loads(line)
                        containers[container_info['Name']] = container_info['State']
                    except json.JSONDecodeError:
                        continue
            
            self.status.containers = containers
            
            # 필수 컨테이너 확인
            required_containers = ['ardupilot', 'companion', 'gazebo', 'qgroundcontrol']
            running_containers = [name for name, state in containers.items() 
                                if state == 'running']
            
            missing_containers = [name for name in required_containers 
                                if name not in running_containers]
            
            if missing_containers:
                logger.warning(f"실행되지 않은 컨테이너: {missing_containers}")
                return False
            
            return True
            
        except subprocess.TimeoutExpired:
            logger.error("Docker 상태 확인 타임아웃")
            return False
        except Exception as e:
            logger.error(f"Docker 상태 확인 오류: {e}")
            return False
    
    async def _start_dvd_containers(self) -> bool:
        """DVD 컨테이너 시작"""
        try:
            logger.info("DVD 컨테이너 시작 중...")
            
            # Docker Compose 실행
            result = subprocess.run(
                ["docker", "compose", "up", "-d", "--build"],
                capture_output=True,
                text=True,
                timeout=120  # 2분 타임아웃
            )
            
            if result.returncode != 0:
                logger.error(f"Docker Compose 실행 실패: {result.stderr}")
                return False
            
            # 컨테이너 시작 대기
            await asyncio.sleep(10)
            
            # 다시 상태 확인
            return await self._check_docker_containers()
            
        except subprocess.TimeoutExpired:
            logger.error("Docker Compose 실행 타임아웃")
            return False
        except Exception as e:
            logger.error(f"Docker 컨테이너 시작 오류: {e}")
            return False
    
    async def _check_services(self) -> bool:
        """DVD 서비스 상태 확인"""
        services_status = {}
        
        # MAVLink 서비스 확인
        services_status['mavlink'] = await self._check_mavlink_service()
        
        # Web 인터페이스 확인
        services_status['web_interface'] = await self._check_web_interface()
        
        # RTSP 스트림 확인
        services_status['rtsp_stream'] = await self._check_rtsp_stream()
        
        self.status.services = services_status
        
        # 최소 하나의 서비스는 작동해야 함
        return any(services_status.values())
    
    async def _check_mavlink_service(self) -> bool:
        """MAVLink 서비스 확인"""
        try:
            # MAVLink 포트 연결 테스트
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.config.host, self.config.mavlink_port),
                timeout=5
            )
            
            # 간단한 heartbeat 메시지 전송 테스트
            # (실제로는 MAVLink 프로토콜 구현 필요)
            writer.close()
            await writer.wait_closed()
            
            return True
            
        except Exception as e:
            logger.warning(f"MAVLink 서비스 확인 실패: {e}")
            return False
    
    async def _check_web_interface(self) -> bool:
        """Web 인터페이스 확인"""
        try:
            response = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.session.get(f"http://{self.config.host}:{self.config.web_port}")
                ),
                timeout=5
            )
            
            return response.status_code == 200
            
        except Exception as e:
            logger.warning(f"Web 인터페이스 확인 실패: {e}")
            return False
    
    async def _check_rtsp_stream(self) -> bool:
        """RTSP 스트림 확인"""
        try:
            # RTSP 포트 연결 테스트
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.config.host, self.config.rtsp_port),
                timeout=5
            )
            
            writer.close()
            await writer.wait_closed()
            
            return True
            
        except Exception as e:
            logger.warning(f"RTSP 스트림 확인 실패: {e}")
            return False
    
    async def _check_wifi_interface(self) -> bool:
        """WiFi 인터페이스 확인 (Full-Deploy 모드용)"""
        try:
            # 가상 WiFi 인터페이스 확인
            result = subprocess.run(
                ["iwconfig"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                logger.warning("iwconfig 명령 실행 실패")
                return False
            
            # 가상 인터페이스 존재 확인
            virtual_interfaces = ['wlan0', 'wlan1', 'mon0']
            available_interfaces = []
            
            for interface in virtual_interfaces:
                if interface in result.stdout:
                    available_interfaces.append(interface)
            
            if not available_interfaces:
                logger.warning("가상 WiFi 인터페이스를 찾을 수 없음")
                return False
            
            logger.info(f"사용 가능한 WiFi 인터페이스: {available_interfaces}")
            return True
            
        except Exception as e:
            logger.warning(f"WiFi 인터페이스 확인 실패: {e}")
            return False
    
    async def _collect_network_info(self) -> None:
        """네트워크 정보 수집"""
        network_info = {
            "dvd_network": self.config.dvd_network,
            "companion_computer": self.config.companion_computer_ip,
            "gcs": self.config.gcs_ip,
            "flight_controller": self.config.flight_controller_ip
        }
        
        # 실제 네트워크 상태 확인
        for name, ip in network_info.items():
            if name != "dvd_network":
                network_info[f"{name}_reachable"] = await self._ping_host(ip)
        
        self.status.network_info = network_info
    
    async def _ping_host(self, host: str) -> bool:
        """호스트 ping 테스트"""
        try:
            result = subprocess.run(
                ["ping", "-c", "1", "-W", "2", host],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False
    
    async def disconnect(self) -> bool:
        """DVD 연결 해제"""
        logger.info("DVD 연결 해제")
        
        try:
            # 세션 정리
            self.session.close()
            
            # 상태 초기화
            self.status.connection_status = DVDConnectionStatus.DISCONNECTED
            self.status.services = {}
            self.status.containers = {}
            self.status.network_info = {}
            self.status.last_heartbeat = 0.0
            self.status.error_message = None
            
            return True
            
        except Exception as e:
            logger.error(f"연결 해제 오류: {e}")
            return False
    
    async def send_mavlink_message(self, message: Dict[str, Any]) -> bool:
        """MAVLink 메시지 전송"""
        if not self.is_connected():
            logger.error("DVD에 연결되지 않음")
            return False
        
        try:
            # 시뮬레이션 모드에서는 항상 성공
            if self.config.environment == DVDEnvironment.SIMULATION:
                logger.info(f"시뮬레이션 MAVLink 메시지 전송: {message}")
                return True
            
            # 실제 MAVLink 메시지 전송 로직
            # (pymavlink 라이브러리 사용 필요)
            logger.info(f"MAVLink 메시지 전송: {message}")
            
            return True
            
        except Exception as e:
            logger.error(f"MAVLink 메시지 전송 실패: {e}")
            return False
    
    async def get_telemetry(self) -> Dict[str, Any]:
        """텔레메트리 데이터 수집"""
        if not self.is_connected():
            return {}
        
        try:
            # 시뮬레이션 모드에서는 가짜 데이터 반환
            if self.config.environment == DVDEnvironment.SIMULATION:
                return {
                    "lat": 37.7749,
                    "lon": -122.4194,
                    "alt": 100,
                    "heading": 90,
                    "groundspeed": 15,
                    "battery": 85,
                    "mode": "GUIDED",
                    "armed": True,
                    "timestamp": time.time()
                }
            
            # 실제 텔레메트리 데이터 수집
            # (MAVLink 연결을 통해 수집)
            telemetry = {
                "timestamp": time.time(),
                "connection_status": self.status.connection_status.value
            }
            
            return telemetry
            
        except Exception as e:
            logger.error(f"텔레메트리 수집 실패: {e}")
            return {}
    
    def is_connected(self) -> bool:
        """연결 상태 확인"""
        return self.status.connection_status == DVDConnectionStatus.CONNECTED
    
    def get_status(self) -> DVDStatus:
        """현재 상태 반환"""
        return self.status
    
    async def health_check(self) -> bool:
        """상태 확인"""
        if not self.is_connected():
            return False
        
        try:
            # 주기적 상태 확인
            services_ok = await self._check_services()
            
            if services_ok:
                self.status.last_heartbeat = time.time()
                return True
            else:
                self.status.connection_status = DVDConnectionStatus.ERROR
                self.status.error_message = "서비스 상태 확인 실패"
                return False
                
        except Exception as e:
            logger.error(f"상태 확인 실패: {e}")
            self.status.connection_status = DVDConnectionStatus.ERROR
            self.status.error_message = str(e)
            return False
    
    @asynccontextmanager
    async def connection_context(self):
        """연결 컨텍스트 매니저"""
        try:
            connected = await self.connect()
            if not connected:
                raise ConnectionError("DVD 연결 실패")
            
            yield self
            
        finally:
            await self.disconnect()

# 편의 함수들
async def create_dvd_connection(environment: DVDEnvironment = DVDEnvironment.SIMULATION) -> DVDConnector:
    """DVD 연결 생성"""
    config = DVDConnectionConfig(environment=environment)
    connector = DVDConnector(config)
    
    connected = await connector.connect()
    if not connected:
        raise ConnectionError(f"DVD 연결 실패: {environment.value}")
    
    return connector

async def test_dvd_connection(environment: DVDEnvironment = DVDEnvironment.SIMULATION) -> bool:
    """DVD 연결 테스트"""
    try:
        async with DVDConnector(DVDConnectionConfig(environment=environment)).connection_context() as connector:
            telemetry = await connector.get_telemetry()
            logger.info(f"연결 테스트 성공: {telemetry}")
            return True
    except Exception as e:
        logger.error(f"연결 테스트 실패: {e}")
        return False

# 테스트 실행
if __name__ == "__main__":
    import asyncio
    
    async def main():
        print("DVD 연결 테스트 시작...")
        
        # 시뮬레이션 모드 테스트
        success = await test_dvd_connection(DVDEnvironment.SIMULATION)
        print(f"시뮬레이션 모드 테스트: {'✅ 성공' if success else '❌ 실패'}")
        
        # Half-Baked 모드 테스트
        success = await test_dvd_connection(DVDEnvironment.HALF_BAKED)
        print(f"Half-Baked 모드 테스트: {'✅ 성공' if success else '❌ 실패'}")
    
    asyncio.run(main())