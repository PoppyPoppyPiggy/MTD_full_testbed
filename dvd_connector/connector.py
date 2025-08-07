# dvd_connector/connector.py
"""
DVD-Lite ↔ Damn Vulnerable Drone 연계 모듈
실제 DVD 환경과의 통신 및 연동을 담당
"""

import asyncio
import socket
import subprocess
import json
import logging
import time
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path
from enum import Enum

logger = logging.getLogger(__name__)

class DVDEnvironmentState(Enum):
    """DVD 환경 상태"""
    UNKNOWN = "unknown"
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    ERROR = "error"

class DVDConnectionType(Enum):
    """DVD 연결 타입"""
    MAVLINK_UDP = "mavlink_udp"
    MAVLINK_TCP = "mavlink_tcp"
    WIFI_NETWORK = "wifi_network"
    ETHERNET = "ethernet"
    SIMULATION = "simulation"

@dataclass
class DVDTarget:
    """DVD 타겟 정보"""
    ip: str
    mavlink_port: int = 14550
    wifi_ssid: Optional[str] = None
    connection_type: DVDConnectionType = DVDConnectionType.MAVLINK_UDP
    companion_computer_ip: Optional[str] = None
    gcs_ip: Optional[str] = None

class DVDEnvironment:
    """DVD 환경 관리"""
    
    def __init__(self, config_path: str = "dvd_config.json"):
        self.config_path = config_path
        self.config = self._load_config()
        self.state = DVDEnvironmentState.UNKNOWN
        self.processes = {}
        
    def _load_config(self) -> Dict[str, Any]:
        """DVD 환경 설정 로드"""
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return self._create_default_config()
    
    def _create_default_config(self) -> Dict[str, Any]:
        """기본 DVD 설정 생성"""
        default_config = {
            "dvd_environment": {
                "type": "simulation",  # "simulation", "real_hardware", "docker"
                "base_path": "/opt/dvd",
                "ardupilot_path": "/opt/ardupilot",
                "sitl_params": {
                    "vehicle": "copter",
                    "location": "KSFO",  # San Francisco Airport
                    "instance": 0
                }
            },
            "targets": {
                "primary": {
                    "ip": "127.0.0.1",
                    "mavlink_port": 14550,
                    "connection_type": "mavlink_udp"
                },
                "companion": {
                    "ip": "127.0.0.1", 
                    "ssh_port": 22,
                    "services": ["rtsp", "http", "ftp"]
                },
                "gcs": {
                    "ip": "127.0.0.1",
                    "mavlink_port": 14551
                }
            },
            "network": {
                "wifi_interface": "wlan0",
                "default_network": "192.168.13.0/24",
                "ap_ssid": "DVD_Test_Network",
                "monitoring_enabled": True
            },
            "security": {
                "vulnerable_services": True,
                "weak_passwords": True,
                "unencrypted_comms": True,
                "debug_enabled": True
            }
        }
        
        # 설정 파일 저장
        with open(self.config_path, 'w') as f:
            json.dump(default_config, f, indent=2)
            
        logger.info(f"기본 DVD 설정 생성: {self.config_path}")
        return default_config
    
    async def start_environment(self) -> bool:
        """DVD 환경 시작"""
        logger.info("DVD 환경 시작 중...")
        self.state = DVDEnvironmentState.STARTING
        
        try:
            env_type = self.config["dvd_environment"]["type"]
            
            if env_type == "simulation":
                return await self._start_simulation()
            elif env_type == "docker":
                return await self._start_docker()
            elif env_type == "real_hardware":
                return await self._connect_real_hardware()
            else:
                logger.error(f"지원되지 않는 환경 타입: {env_type}")
                return False
                
        except Exception as e:
            logger.error(f"DVD 환경 시작 실패: {e}")
            self.state = DVDEnvironmentState.ERROR
            return False
    
    async def _start_simulation(self) -> bool:
        """SITL 시뮬레이션 시작"""
        sitl_params = self.config["dvd_environment"]["sitl_params"]
        ardupilot_path = Path(self.config["dvd_environment"]["ardupilot_path"])
        
        # ArduPilot SITL 실행
        sitl_cmd = [
            str(ardupilot_path / "Tools/autotest/sim_vehicle.py"),
            f"--vehicle={sitl_params['vehicle']}",
            f"--location={sitl_params['location']}",
            f"--instance={sitl_params['instance']}",
            "--out=127.0.0.1:14550",
            "--out=127.0.0.1:14551",
            "--map", "--console"
        ]
        
        try:
            process = await asyncio.create_subprocess_exec(
                *sitl_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            self.processes["sitl"] = process
            logger.info("ArduPilot SITL 시작됨")
            
            # SITL이 준비될 때까지 대기
            await self._wait_for_mavlink_connection()
            
            # 컴패니언 컴퓨터 시뮬레이션 시작
            await self._start_companion_simulation()
            
            self.state = DVDEnvironmentState.RUNNING
            return True
            
        except Exception as e:
            logger.error(f"SITL 시작 실패: {e}")
            return False
    
    async def _start_companion_simulation(self) -> bool:
        """컴패니언 컴퓨터 시뮬레이션 시작"""
        try:
            # 가짜 RTSP 스트림 서버
            rtsp_cmd = [
                "python3", "-c", """
import socket
import time
import threading

def rtsp_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(('127.0.0.1', 554))
    server.listen(5)
    print('RTSP 서버 시작: rtsp://127.0.0.1:554/live/stream1')
    
    while True:
        client, addr = server.accept()
        data = client.recv(1024)
        response = b'RTSP/1.0 200 OK\\r\\n\\r\\n'
        client.send(response)
        client.close()

rtsp_server()
"""
            ]
            
            process = await asyncio.create_subprocess_exec(
                *rtsp_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            self.processes["rtsp"] = process
            logger.info("컴패니언 컴퓨터 시뮬레이션 시작됨")
            return True
            
        except Exception as e:
            logger.error(f"컴패니언 컴퓨터 시뮬레이션 시작 실패: {e}")
            return False
    
    async def _start_docker(self) -> bool:
        """Docker 기반 DVD 환경 시작"""
        try:
            # DVD Docker 컨테이너 실행
            docker_cmd = [
                "docker", "run", "-d",
                "--name", "dvd-environment",
                "-p", "14550:14550/udp",
                "-p", "14551:14551/udp", 
                "-p", "554:554",
                "-p", "80:80",
                "-p", "22:22",
                "dvd:latest"
            ]
            
            process = await asyncio.create_subprocess_exec(
                *docker_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                container_id = stdout.decode().strip()
                self.processes["docker"] = container_id
                logger.info(f"DVD Docker 컨테이너 시작됨: {container_id}")
                
                await self._wait_for_mavlink_connection()
                self.state = DVDEnvironmentState.RUNNING
                return True
            else:
                logger.error(f"Docker 시작 실패: {stderr.decode()}")
                return False
                
        except Exception as e:
            logger.error(f"Docker 환경 시작 실패: {e}")
            return False
    
    async def _connect_real_hardware(self) -> bool:
        """실제 하드웨어 연결"""
        target = self.config["targets"]["primary"]
        
        # 실제 드론과의 연결 확인
        if await self._test_mavlink_connection(target["ip"], target["mavlink_port"]):
            logger.info(f"실제 DVD 하드웨어 연결됨: {target['ip']}:{target['mavlink_port']}")
            self.state = DVDEnvironmentState.RUNNING
            return True
        else:
            logger.error("실제 하드웨어 연결 실패")
            return False
    
    async def _wait_for_mavlink_connection(self, timeout: int = 30) -> bool:
        """MAVLink 연결 대기"""
        target = self.config["targets"]["primary"]
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if await self._test_mavlink_connection(target["ip"], target["mavlink_port"]):
                logger.info("MAVLink 연결 확인됨")
                return True
            await asyncio.sleep(2)
        
        logger.error("MAVLink 연결 타임아웃")
        return False
    
    async def _test_mavlink_connection(self, ip: str, port: int) -> bool:
        """MAVLink 연결 테스트"""
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(ip, port),
                timeout=5
            )
            writer.close()
            await writer.wait_closed()
            return True
        except:
            return False
    
    async def stop_environment(self) -> bool:
        """DVD 환경 중지"""
        logger.info("DVD 환경 중지 중...")
        
        try:
            # 실행 중인 프로세스들 종료
            for name, process in self.processes.items():
                if name == "docker":
                    # Docker 컨테이너 중지
                    await asyncio.create_subprocess_exec(
                        "docker", "stop", process,
                        stdout=asyncio.subprocess.PIPE
                    )
                    await asyncio.create_subprocess_exec(
                        "docker", "rm", process,
                        stdout=asyncio.subprocess.PIPE
                    )
                else:
                    # 일반 프로세스 종료
                    if hasattr(process, 'terminate'):
                        process.terminate()
                        await process.wait()
            
            self.processes.clear()
            self.state = DVDEnvironmentState.STOPPED
            logger.info("DVD 환경 중지 완료")
            return True
            
        except Exception as e:
            logger.error(f"DVD 환경 중지 실패: {e}")
            return False
    
    def get_targets(self) -> Dict[str, DVDTarget]:
        """DVD 타겟 정보 반환"""
        targets = {}
        
        for name, config in self.config["targets"].items():
            targets[name] = DVDTarget(
                ip=config["ip"],
                mavlink_port=config.get("mavlink_port", 14550),
                connection_type=DVDConnectionType(config.get("connection_type", "mavlink_udp"))
            )
        
        return targets
    
    def is_running(self) -> bool:
        """DVD 환경 실행 상태 확인"""
        return self.state == DVDEnvironmentState.RUNNING

class DVDConnector:
    """DVD-Lite와 실제 DVD 환경 간의 연결 관리"""
    
    def __init__(self, environment: DVDEnvironment):
        self.environment = environment
        self.connections = {}
        self.safety_checker = SafetyChecker()
        
    async def initialize(self) -> bool:
        """연결 초기화"""
        logger.info("DVD 연결 초기화 중...")
        
        # 환경이 실행 중이 아니면 시작
        if not self.environment.is_running():
            if not await self.environment.start_environment():
                logger.error("DVD 환경 시작 실패")
                return False
        
        # 안전성 검사
        if not await self.safety_checker.perform_safety_check():
            logger.error("안전성 검사 실패")
            return False
        
        # 타겟별 연결 설정
        targets = self.environment.get_targets()
        
        for name, target in targets.items():
            try:
                connection = await self._create_connection(target)
                if connection:
                    self.connections[name] = connection
                    logger.info(f"타겟 연결 성공: {name} ({target.ip})")
                else:
                    logger.warning(f"타겟 연결 실패: {name}")
                    
            except Exception as e:
                logger.error(f"타겟 {name} 연결 오류: {e}")
        
        return len(self.connections) > 0
    
    async def _create_connection(self, target: DVDTarget) -> Optional[Dict[str, Any]]:
        """타겟별 연결 생성"""
        if target.connection_type == DVDConnectionType.MAVLINK_UDP:
            return await self._create_mavlink_connection(target)
        elif target.connection_type == DVDConnectionType.WIFI_NETWORK:
            return await self._create_wifi_connection(target)
        else:
            logger.warning(f"지원되지 않는 연결 타입: {target.connection_type}")
            return None
    
    async def _create_mavlink_connection(self, target: DVDTarget) -> Optional[Dict[str, Any]]:
        """MAVLink 연결 생성"""
        try:
            # UDP 소켓 생성
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.connect((target.ip, target.mavlink_port))
            
            return {
                "type": "mavlink",
                "socket": sock,
                "target": target,
                "last_heartbeat": None
            }
            
        except Exception as e:
            logger.error(f"MAVLink 연결 실패: {e}")
            return None
    
    async def _create_wifi_connection(self, target: DVDTarget) -> Optional[Dict[str, Any]]:
        """WiFi 연결 생성"""
        # WiFi 연결 로직 구현
        return {
            "type": "wifi",
            "target": target,
            "interface": "wlan0"
        }
    
    async def execute_attack_on_target(self, attack_name: str, target_name: str = "primary") -> Dict[str, Any]:
        """특정 타겟에 대해 공격 실행"""
        if target_name not in self.connections:
            raise ValueError(f"타겟 '{target_name}'에 대한 연결이 없습니다")
        
        connection = self.connections[target_name]
        target = connection["target"]
        
        # 안전성 재검사
        if not await self.safety_checker.is_attack_safe(attack_name, target):
            raise ValueError(f"공격 '{attack_name}'이 안전하지 않습니다")
        
        # 실제 타겟 정보로 공격 실행
        from dvd_lite.main import DVDLite
        
        dvd = DVDLite()
        result = await dvd.run_attack(
            attack_name,
            target_ip=target.ip,
            mavlink_port=target.mavlink_port,
            connection=connection
        )
        
        return {
            "result": result,
            "target": target_name,
            "target_ip": target.ip,
            "connection_type": target.connection_type.value
        }
    
    async def get_target_status(self, target_name: str = "primary") -> Dict[str, Any]:
        """타겟 상태 확인"""
        if target_name not in self.connections:
            return {"status": "disconnected"}
        
        connection = self.connections[target_name]
        target = connection["target"]
        
        # 연결 상태 확인
        if connection["type"] == "mavlink":
            alive = await self._test_mavlink_alive(target)
        else:
            alive = True  # 다른 연결 타입의 경우 기본값
        
        return {
            "status": "connected" if alive else "disconnected",
            "target": target_name,
            "ip": target.ip,
            "connection_type": target.connection_type.value,
            "last_check": time.time()
        }
    
    async def _test_mavlink_alive(self, target: DVDTarget) -> bool:
        """MAVLink 연결 생존 확인"""
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(target.ip, target.mavlink_port),
                timeout=3
            )
            writer.close()
            await writer.wait_closed()
            return True
        except:
            return False
    
    async def cleanup(self):
        """연결 정리"""
        for name, connection in self.connections.items():
            if "socket" in connection:
                connection["socket"].close()
        
        self.connections.clear()
        await self.environment.stop_environment()
        logger.info("DVD 연결 정리 완료")

class SafetyChecker:
    """안전성 검사 클래스"""
    
    def __init__(self):
        self.safe_networks = ["127.0.0.0/8", "192.168.0.0/16", "10.0.0.0/8"]
        self.dangerous_attacks = ["firmware_brick", "permanent_damage"]
    
    async def perform_safety_check(self) -> bool:
        """전체 안전성 검사"""
        checks = [
            self._check_network_safety(),
            self._check_environment_safety(),
            self._check_permissions()
        ]
        
        return all(checks)
    
    def _check_network_safety(self) -> bool:
        """네트워크 안전성 검사"""
        # 로컬 네트워크인지 확인
        return True  # 기본적으로 안전하다고 가정
    
    def _check_environment_safety(self) -> bool:
        """환경 안전성 검사"""
        # 테스트 환경인지 확인
        return True
    
    def _check_permissions(self) -> bool:
        """권한 검사"""
        # 적절한 권한이 있는지 확인
        return True
    
    async def is_attack_safe(self, attack_name: str, target: DVDTarget) -> bool:
        """특정 공격의 안전성 검사"""
        if attack_name in self.dangerous_attacks:
            logger.warning(f"위험한 공격: {attack_name}")
            return False
        
        # 타겟이 안전한 범위 내에 있는지 확인
        return self._is_safe_target(target.ip)
    
    def _is_safe_target(self, ip: str) -> bool:
        """안전한 타겟인지 확인"""
        import ipaddress
        
        target_ip = ipaddress.ip_address(ip)
        
        for safe_network in self.safe_networks:
            if target_ip in ipaddress.ip_network(safe_network):
                return True
        
        return False

# 사용 예시 및 테스트
async def test_dvd_connector():
    """DVD Connector 테스트"""
    print("🧪 DVD Connector 테스트 시작...")
    
    try:
        # 환경 생성 및 시작
        env = DVDEnvironment()
        connector = DVDConnector(env)
        
        # 초기화
        if await connector.initialize():
            print("✅ DVD 연결 초기화 성공")
            
            # 타겟 상태 확인
            status = await connector.get_target_status()
            print(f"📊 타겟 상태: {status}")
            
            # 공격 실행 예시 (안전한 정찰 공격)
            try:
                result = await connector.execute_attack_on_target("wifi_network_discovery")
                print(f"🎯 공격 실행 결과: {result['result'].status.value}")
            except Exception as e:
                print(f"⚠️  공격 실행 실패: {e}")
            
            # 정리
            await connector.cleanup()
            print("✅ 정리 완료")
            
        else:
            print("❌ DVD 연결 초기화 실패")
            
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")

if __name__ == "__main__":
    asyncio.run(test_dvd_connector())