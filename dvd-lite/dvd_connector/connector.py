# dvd_connector/connector.py
"""
DVD 연결 관리자 (의존성 오류 수정 버전)
Damn Vulnerable Drone 환경과의 안전한 연동 관리
"""

import asyncio
import socket
import subprocess
import logging
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass
from enum import Enum
import ipaddress
import json

# 시스템 모듈만 사용하고 문제가 있는 외부 라이브러리는 선택적 import
try:
    from dvd_lite import DVDLite, SimpleCTI
    from dvd_lite.attacks import register_all_attacks
except ImportError as e:
    print(f"Warning: DVD-Lite import 오류: {e}")

logger = logging.getLogger(__name__)

class DVDConnectionMode(Enum):
    """DVD 연결 모드"""
    SIMULATION = "simulation"      # 안전한 시뮬레이션
    LOCAL_DOCKER = "local_docker"  # 로컬 Docker DVD
    LOCAL_VM = "local_vm"         # 로컬 VM DVD
    REMOTE = "remote"             # 원격 DVD 환경
    HYBRID = "hybrid"             # 하이브리드 모드

@dataclass
class DVDTarget:
    """DVD 타겟 정보"""
    host: str
    mode: DVDConnectionMode
    ports: Dict[str, int]
    network_range: str
    wifi_interface: Optional[str] = None
    docker_network: Optional[str] = None
    
    def __post_init__(self):
        """초기화 후 검증"""
        if not self.ports:
            self.ports = {
                "mavlink": 14550,
                "mavlink_gcs": 14551, 
                "http": 80,
                "https": 443,
                "ftp": 21,
                "ssh": 22,
                "rtsp": 8554
            }

class DVDEnvironment:
    """DVD 환경 정보"""
    
    def __init__(self, target: DVDTarget):
        self.target = target
        self.discovered_services = {}
        self.network_topology = {}
        self.is_accessible = False
        self.safety_level = "unknown"
        
    async def scan_environment(self) -> Dict[str, Any]:
        """DVD 환경 스캔 (간소화된 버전)"""
        try:
            # 기본 연결성 확인
            accessible = await self._check_basic_connectivity()
            
            scan_results = {
                "accessible": accessible,
                "hosts": {},
                "services": {},
                "topology": {},
                "dvd_components": {},
                "security_status": {}
            }
            
            if accessible:
                # 간단한 포트 스캔
                services = await self._simple_port_scan()
                scan_results["services"] = services
                scan_results["dvd_components"] = self._identify_simple_components(services)
            
            self.discovered_services = scan_results.get("services", {})
            self.is_accessible = accessible
            
            return scan_results
            
        except Exception as e:
            logger.error(f"환경 스캔 오류: {str(e)}")
            return {"accessible": False, "error": str(e)}
    
    async def _check_basic_connectivity(self) -> bool:
        """기본 연결성 확인"""
        try:
            # TCP 연결 테스트
            mavlink_port = self.target.ports.get("mavlink", 14550)
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3.0)
            result = sock.connect_ex((self.target.host, mavlink_port))
            sock.close()
            
            if result == 0:
                return True
            
            # Ping 테스트
            return await self._ping_test()
            
        except Exception:
            return False
    
    async def _ping_test(self) -> bool:
        """Ping 테스트"""
        try:
            process = await asyncio.create_subprocess_exec(
                "ping", "-c", "1", "-W", "3", self.target.host,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )
            returncode = await process.wait()
            return returncode == 0
        except:
            return False
    
    async def _simple_port_scan(self) -> Dict[str, Any]:
        """간단한 포트 스캔"""
        services = {}
        
        # 기본 DVD 포트들만 확인
        test_ports = [14550, 14551, 80, 22, 21]
        
        host_services = {}
        for port in test_ports:
            if await self._check_port(port):
                host_services[port] = {
                    "port": port,
                    "open": True,
                    "service": self._guess_service_name(port)
                }
        
        if host_services:
            services[self.target.host] = host_services
        
        return services
    
    async def _check_port(self, port: int) -> bool:
        """포트 확인"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2.0)
            result = sock.connect_ex((self.target.host, port))
            sock.close()
            return result == 0
        except:
            return False
    
    def _guess_service_name(self, port: int) -> str:
        """포트로 서비스명 추측"""
        port_map = {
            14550: "mavlink_fc",
            14551: "mavlink_gcs",
            80: "http",
            22: "ssh",
            21: "ftp",
            8554: "rtsp"
        }
        return port_map.get(port, f"unknown_{port}")
    
    def _identify_simple_components(self, services: Dict) -> Dict[str, Any]:
        """간단한 컴포넌트 식별"""
        components = {
            "flight_controller": None,
            "companion_computer": None,
            "ground_control_station": None,
            "unknown_components": []
        }
        
        for host_ip, host_services in services.items():
            open_ports = set(host_services.keys())
            
            if 14550 in open_ports:
                components["flight_controller"] = {
                    "ip": host_ip,
                    "services": host_services,
                    "role": "flight_controller"
                }
            elif 14551 in open_ports:
                components["ground_control_station"] = {
                    "ip": host_ip,
                    "services": host_services,
                    "role": "ground_control_station"
                }
            elif any(port in open_ports for port in [80, 21]):
                components["companion_computer"] = {
                    "ip": host_ip,
                    "services": host_services,
                    "role": "companion_computer"
                }
        
        return components

class RealAttackAdapter:
    """실제 공격 어댑터 (간소화된 버전)"""
    
    def __init__(self, target, scan_results):
        self.target = target
        self.scan_results = scan_results
        
    async def initialize(self):
        """어댑터 초기화"""
        logger.info("🔧 실제 공격 어댑터 초기화 중...")
        # 실제 구현에서는 더 복잡한 초기화 수행
        
    def register_real_attacks(self, dvd_lite):
        """실제 공격 모듈 등록"""
        # 현재는 기본 공격 모듈 사용
        register_all_attacks(dvd_lite)
        logger.info("✅ 공격 모듈 등록 완료")
    
    async def cleanup(self):
        """정리 작업"""
        logger.info("🧹 어댑터 정리 완료")

class SafetyChecker:
    """간소화된 안전성 검사기"""
    
    def __init__(self):
        self.safe_networks = ["10.13.0.0/24", "192.168.13.0/24", "172.20.0.0/16", "127.0.0.0/8"]
    
    async def check_target_safety(self, target) -> Dict[str, Any]:
        """간단한 안전성 검사"""
        try:
            # IP 주소 검증
            if target.host in ["localhost", "127.0.0.1", "simulation", "docker"]:
                return {"safe": True, "reason": "안전한 로컬 타겟"}
            
            # IP 범위 확인
            try:
                ip = ipaddress.ip_address(target.host)
                for safe_network in self.safe_networks:
                    if ip in ipaddress.ip_network(safe_network):
                        return {"safe": True, "reason": f"안전한 네트워크 범위: {safe_network}"}
            except:
                pass
            
            # 기본적으로 안전하다고 가정 (사용자 판단에 맡김)
            return {"safe": True, "reason": "사용자 확인 필요", "warning": True}
            
        except Exception as e:
            return {"safe": False, "reason": f"안전성 검사 오류: {str(e)}"}

class DVDConnector:
    """DVD 연결 관리자 메인 클래스 (간소화된 버전)"""
    
    def __init__(self, target_spec: Union[str, DVDTarget, Dict], mode: str = "auto"):
        """DVD 연결 관리자 초기화"""
        self.target = self._parse_target_spec(target_spec, mode)
        self.environment = DVDEnvironment(self.target)
        self.safety_checker = SafetyChecker()
        self.dvd_lite = None
        self.attack_adapter = None
        self.is_connected = False
        
    def _parse_target_spec(self, target_spec: Union[str, DVDTarget, Dict], mode: str) -> DVDTarget:
        """타겟 스펙 파싱"""
        if isinstance(target_spec, DVDTarget):
            return target_spec
        
        if isinstance(target_spec, str):
            return self._parse_string_target(target_spec, mode)
        
        if isinstance(target_spec, dict):
            return DVDTarget(**target_spec)
        
        raise ValueError(f"지원하지 않는 타겟 스펙: {type(target_spec)}")
    
    def _parse_string_target(self, target_str: str, mode: str) -> DVDTarget:
        """문자열 타겟 파싱"""
        # 특수 키워드 처리
        if target_str.lower() in ["docker", "local-docker"]:
            return DVDTarget(
                host="localhost",
                mode=DVDConnectionMode.LOCAL_DOCKER,
                ports={},
                network_range="172.20.0.0/16",
                docker_network="dvd_network"
            )
        
        if target_str.lower() in ["simulation", "sim", "safe"]:
            return DVDTarget(
                host="10.13.0.2",
                mode=DVDConnectionMode.SIMULATION,
                ports={},
                network_range="10.13.0.0/24"
            )
        
        # IP 주소 또는 호스트명 처리
        try:
            ip = ipaddress.ip_address(target_str)
            if str(ip).startswith("10.13.0."):
                network_range = "10.13.0.0/24"
                connection_mode = DVDConnectionMode.LOCAL_VM
            elif str(ip).startswith("172.20."):
                network_range = "172.20.0.0/16"
                connection_mode = DVDConnectionMode.LOCAL_DOCKER
            else:
                network_range = f"{str(ip).rsplit('.', 1)[0]}.0/24"
                connection_mode = DVDConnectionMode.REMOTE
        except ValueError:
            # 호스트명
            network_range = "192.168.1.0/24"
            connection_mode = DVDConnectionMode.REMOTE
        
        return DVDTarget(
            host=target_str,
            mode=connection_mode,
            ports={},
            network_range=network_range
        )
    
    async def connect(self) -> bool:
        """DVD 환경에 연결"""
        logger.info(f"🔗 DVD 환경 연결 시작: {self.target.host} ({self.target.mode.value})")
        
        try:
            # 1. 안전성 검사
            safety_result = await self.safety_checker.check_target_safety(self.target)
            if not safety_result["safe"]:
                logger.error(f"❌ 안전성 검사 실패: {safety_result['reason']}")
                return False
            
            if safety_result.get("warning"):
                logger.warning(f"⚠️  {safety_result['reason']}")
            
            # 2. 환경 스캔
            logger.info("🔍 DVD 환경 스캔 중...")
            scan_results = await self.environment.scan_environment()
            
            if not scan_results.get("accessible", False):
                logger.error(f"❌ DVD 환경에 접근할 수 없습니다: {self.target.host}")
                return False
            
            # 3. DVD-Lite 초기화
            logger.info("🚁 DVD-Lite 초기화 중...")
            self.dvd_lite = DVDLite()
            self.dvd_lite.config = self._create_dvd_config()
            
            # 4. CTI 수집기 등록
            cti = SimpleCTI()
            self.dvd_lite.register_cti_collector(cti)
            
            # 5. 공격 모듈 등록
            if self.target.mode != DVDConnectionMode.SIMULATION:
                logger.info("⚔️  실제 공격 어댑터 초기화 중...")
                self.attack_adapter = RealAttackAdapter(self.target, scan_results)
                await self.attack_adapter.initialize()
                self.attack_adapter.register_real_attacks(self.dvd_lite)
            else:
                register_all_attacks(self.dvd_lite)
            
            self.is_connected = True
            logger.info("✅ DVD 환경 연결 완료")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ DVD 연결 실패: {str(e)}")
            return False
    
    def _create_dvd_config(self) -> Dict[str, Any]:
        """DVD 연결용 설정 생성"""
        return {
            "target": {
                "ip": self.target.host,
                "mavlink_port": self.target.ports.get("mavlink", 14550),
                "network_range": self.target.network_range
            },
            "attacks": {
                "enabled": self._get_enabled_attacks(),
                "delay_between": 2.0,
                "timeout": 30.0,
                "real_mode": self.target.mode != DVDConnectionMode.SIMULATION
            },
            "cti": {
                "auto_collect": True,
                "real_iocs": self.target.mode != DVDConnectionMode.SIMULATION
            }
        }
    
    def _get_enabled_attacks(self) -> List[str]:
        """연결 모드에 따른 활성화 공격 목록"""
        if self.target.mode == DVDConnectionMode.SIMULATION:
            return [
                "wifi_scan", "drone_discovery", "packet_sniff",
                "telemetry_spoof", "command_inject", "waypoint_inject",
                "log_extract", "param_extract"
            ]
        else:
            # 실제 모드: 안전한 공격만
            return ["wifi_scan", "drone_discovery", "packet_sniff", "param_extract"]
    
    async def run_security_assessment(self, assessment_type: str = "standard") -> Dict[str, Any]:
        """보안 평가 실행"""
        if not self.is_connected:
            if not await self.connect():
                raise RuntimeError("DVD 환경에 연결할 수 없습니다.")
        
        logger.info(f"🛡️  보안 평가 시작: {assessment_type}")
        
        assessment_configs = {
            "quick": {
                "attacks": ["wifi_scan", "drone_discovery"],
                "iterations": 1
            },
            "standard": {
                "attacks": ["wifi_scan", "drone_discovery", "packet_sniff", "param_extract"],
                "iterations": 1
            },
            "comprehensive": {
                "attacks": self._get_enabled_attacks(),
                "iterations": 2
            }
        }
        
        config = assessment_configs.get(assessment_type, assessment_configs["standard"])
        
        results = []
        for iteration in range(config["iterations"]):
            logger.info(f"평가 반복 {iteration + 1}/{config['iterations']}")
            
            campaign_results = await self.dvd_lite.run_campaign(config["attacks"])
            results.extend(campaign_results)
            
            if iteration < config["iterations"] - 1:
                await asyncio.sleep(5)
        
        # 결과 분석
        return self._analyze_assessment_results(results)
    
    def _analyze_assessment_results(self, results: List) -> Dict[str, Any]:
        """평가 결과 분석"""
        if not results:
            return {"status": "no_results", "message": "평가 결과가 없습니다."}
        
        total = len(results)
        successful = sum(1 for r in results if r.status.value == "success")
        detected = sum(1 for r in results if r.status.value == "detected")
        
        risk_score = (successful / total) * 100 if total > 0 else 0
        risk_level = self._calculate_risk_level(risk_score)
        
        return {
            "status": "completed",
            "summary": {
                "total_attacks": total,
                "successful_attacks": successful,
                "detection_rate": (detected / total) * 100,
                "success_rate": risk_score,
                "risk_level": risk_level
            },
            "results": results,
            "recommendations": self._generate_recommendations(risk_level),
            "target_info": self.get_connection_info()
        }
    
    def _calculate_risk_level(self, success_rate: float) -> str:
        """위험도 계산"""
        if success_rate >= 80:
            return "critical"
        elif success_rate >= 60:
            return "high"
        elif success_rate >= 40:
            return "medium"
        elif success_rate >= 20:
            return "low"
        else:
            return "minimal"
    
    def _generate_recommendations(self, risk_level: str) -> List[str]:
        """보안 권장사항 생성"""
        recommendations = []
        
        if risk_level in ["critical", "high"]:
            recommendations.extend([
                "즉시 보안 패치 및 설정 강화 필요",
                "네트워크 접근 제어 강화",
                "MAVLink 암호화 활성화"
            ])
        elif risk_level == "medium":
            recommendations.extend([
                "보안 설정 검토 필요",
                "불필요한 서비스 비활성화"
            ])
        else:
            recommendations.append("현재 보안 수준 양호")
        
        recommendations.extend([
            "정기적인 보안 스캔 수행",
            "네트워크 모니터링 강화"
        ])
        
        return recommendations
    
    async def disconnect(self):
        """DVD 연결 해제"""
        if self.attack_adapter:
            await self.attack_adapter.cleanup()
        
        self.is_connected = False
        logger.info("🔌 DVD 연결 해제 완료")
    
    def get_connection_info(self) -> Dict[str, Any]:
        """연결 정보 반환"""
        return {
            "target": {
                "host": self.target.host,
                "mode": self.target.mode.value,
                "network_range": self.target.network_range
            },
            "connected": self.is_connected,
            "environment": {
                "accessible": self.environment.is_accessible,
                "services": list(self.environment.discovered_services.keys()),
                "safety_level": self.environment.safety_level
            }
        }