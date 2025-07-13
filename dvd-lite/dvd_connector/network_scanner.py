# dvd_connector/network_scanner.py
"""
DVD 네트워크 스캐너
Damn Vulnerable Drone 환경의 네트워크 토폴로지 및 서비스 발견
"""

import asyncio
import socket
import subprocess
import json
import logging
from typing import Dict, List, Any, Optional, Tuple
import ipaddress
import concurrent.futures

logger = logging.getLogger(__name__)

class DVDNetworkScanner:
    """DVD 네트워크 스캐너"""
    
    def __init__(self, target):
        self.target = target
        self.discovered_hosts = {}
        self.discovered_services = {}
        self.network_topology = {}
        
    async def comprehensive_scan(self) -> Dict[str, Any]:
        """종합적인 네트워크 스캔"""
        logger.info(f"🔍 DVD 환경 종합 스캔 시작: {self.target.host}")
        
        scan_results = {
            "accessible": False,
            "hosts": {},
            "services": {},
            "topology": {},
            "dvd_components": {},
            "security_status": {}
        }
        
        try:
            # 1. 기본 연결성 확인
            connectivity = await self._check_basic_connectivity()
            scan_results["accessible"] = connectivity["accessible"]
            
            if not connectivity["accessible"]:
                scan_results["error"] = connectivity["error"]
                return scan_results
            
            # 2. 호스트 발견
            hosts = await self._discover_hosts()
            scan_results["hosts"] = hosts
            
            # 3. 서비스 스캔
            services = await self._scan_services(hosts)
            scan_results["services"] = services
            
            # 4. DVD 컴포넌트 식별
            dvd_components = await self._identify_dvd_components(hosts, services)
            scan_results["dvd_components"] = dvd_components
            
            # 5. 네트워크 토폴로지 매핑
            topology = await self._map_network_topology(hosts, services)
            scan_results["topology"] = topology
            
            # 6. 보안 상태 평가
            security_status = await self._assess_security_status(services)
            scan_results["security_status"] = security_status
            
            logger.info("✅ DVD 환경 스캔 완료")
            return scan_results
            
        except Exception as e:
            logger.error(f"❌ 스캔 실패: {str(e)}")
            scan_results["error"] = str(e)
            return scan_results
    
    async def _check_basic_connectivity(self) -> Dict[str, Any]:
        """기본 연결성 확인"""
        result = {"accessible": False, "error": None, "response_time": None}
        
        try:
            start_time = asyncio.get_event_loop().time()
            
            # TCP 연결 테스트 (MAVLink 포트)
            mavlink_port = self.target.ports.get("mavlink", 14550)
            
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(self.target.host, mavlink_port),
                    timeout=5.0
                )
                writer.close()
                await writer.wait_closed()
                
                result["accessible"] = True
                result["response_time"] = asyncio.get_event_loop().time() - start_time
                logger.info(f"✅ MAVLink 포트 ({mavlink_port}) 연결 성공")
                
            except (ConnectionRefusedError, OSError):
                # MAVLink 포트가 안되면 ping 테스트
                ping_result = await self._ping_host()
                if ping_result:
                    result["accessible"] = True
                    result["response_time"] = ping_result
                    logger.info("✅ Ping 응답 확인")
                else:
                    result["error"] = f"호스트 {self.target.host}에 연결할 수 없습니다"
            
        except Exception as e:
            result["error"] = f"연결성 확인 실패: {str(e)}"
        
        return result
    
    async def _ping_host(self) -> Optional[float]:
        """호스트 ping 테스트"""
        try:
            start_time = asyncio.get_event_loop().time()
            
            # ping 명령 실행
            process = await asyncio.create_subprocess_exec(
                "ping", "-c", "1", "-W", "3", self.target.host,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                return asyncio.get_event_loop().time() - start_time
            else:
                return None
                
        except Exception:
            return None
    
    async def _discover_hosts(self) -> Dict[str, Any]:
        """네트워크 호스트 발견"""
        logger.info(f"🔍 호스트 발견 중: {self.target.network_range}")
        
        discovered = {}
        
        try:
            # 네트워크 범위 파싱
            network = ipaddress.ip_network(self.target.network_range, strict=False)
            
            # DVD 표준 호스트들 우선 확인
            dvd_standard_hosts = {
                "flight_controller": ".2",
                "companion": ".3", 
                "gcs": ".4",
                "simulator": ".5"
            }
            
            base_ip = str(network.network_address).rsplit('.', 1)[0]
            
            # 표준 호스트들 확인
            for role, suffix in dvd_standard_hosts.items():
                host_ip = base_ip + suffix
                if await self._check_host_alive(host_ip):
                    discovered[host_ip] = {
                        "role": role,
                        "response_time": await self._measure_response_time(host_ip),
                        "status": "alive"
                    }
                    logger.info(f"✅ DVD {role} 발견: {host_ip}")
            
            # 추가 호스트 스캔 (처음 10개)
            scan_tasks = []
            for i in range(1, 11):
                host_ip = f"{base_ip}.{i}"
                if host_ip not in discovered:
                    scan_tasks.append(self._scan_single_host(host_ip))
            
            if scan_tasks:
                additional_hosts = await asyncio.gather(*scan_tasks, return_exceptions=True)
                for host_info in additional_hosts:
                    if isinstance(host_info, dict) and host_info.get("alive"):
                        discovered[host_info["ip"]] = host_info
            
        except Exception as e:
            logger.error(f"호스트 발견 실패: {str(e)}")
        
        logger.info(f"📊 발견된 호스트: {len(discovered)}개")
        return discovered
    
    async def _scan_single_host(self, host_ip: str) -> Dict[str, Any]:
        """단일 호스트 스캔"""
        result = {"ip": host_ip, "alive": False}
        
        if await self._check_host_alive(host_ip):
            result.update({
                "alive": True,
                "response_time": await self._measure_response_time(host_ip),
                "role": "unknown",
                "status": "alive"
            })
        
        return result
    
    async def _check_host_alive(self, host_ip: str) -> bool:
        """호스트 생존 확인"""
        try:
            process = await asyncio.create_subprocess_exec(
                "ping", "-c", "1", "-W", "1", host_ip,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )
            
            returncode = await process.wait()
            return returncode == 0
            
        except Exception:
            return False
    
    async def _measure_response_time(self, host_ip: str) -> float:
        """응답 시간 측정"""
        try:
            start_time = asyncio.get_event_loop().time()
            
            process = await asyncio.create_subprocess_exec(
                "ping", "-c", "1", "-W", "3", host_ip,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL
            )
            
            await process.wait()
            return asyncio.get_event_loop().time() - start_time
            
        except Exception:
            return 0.0
    
    async def _scan_services(self, hosts: Dict[str, Any]) -> Dict[str, Any]:
        """서비스 스캔"""
        logger.info("🔍 서비스 스캔 중...")
        
        services = {}
        
        # DVD 표준 포트들
        standard_ports = {
            14550: "mavlink_fc",      # Flight Controller MAVLink
            14551: "mavlink_gcs",     # GCS MAVLink
            14552: "mavlink_companion", # Companion Computer
            80: "http",
            443: "https",
            21: "ftp",
            22: "ssh",
            23: "telnet",
            8554: "rtsp",             # Video streaming
            8080: "http_alt",
            5760: "mavlink_sitl"      # SITL MAVLink
        }
        
        # 각 호스트의 서비스 스캔
        for host_ip, host_info in hosts.items():
            if not host_info.get("alive", False):
                continue
                
            host_services = {}
            
            # 포트 스캔
            scan_tasks = [
                self._scan_port(host_ip, port, service_name)
                for port, service_name in standard_ports.items()
            ]
            
            port_results = await asyncio.gather(*scan_tasks, return_exceptions=True)
            
            for result in port_results:
                if isinstance(result, dict) and result.get("open"):
                    port = result["port"]
                    host_services[port] = result
            
            if host_services:
                services[host_ip] = host_services
                logger.info(f"📊 {host_ip}: {len(host_services)}개 서비스 발견")
        
        return services
    
    async def _scan_port(self, host: str, port: int, service_name: str) -> Dict[str, Any]:
        """단일 포트 스캔"""
        result = {
            "port": port,
            "service": service_name,
            "open": False,
            "banner": None
        }
        
        try:
            # TCP 연결 시도
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=3.0
            )
            
            result["open"] = True
            
            # 배너 정보 수집 시도
            try:
                banner_data = await asyncio.wait_for(reader.read(100), timeout=1.0)
                if banner_data:
                    result["banner"] = banner_data.decode('utf-8', errors='ignore').strip()
            except:
                pass
            
            writer.close()
            await writer.wait_closed()
            
        except (ConnectionRefusedError, OSError, asyncio.TimeoutError):
            pass
        except Exception as e:
            logger.debug(f"포트 스캔 오류 {host}:{port} - {str(e)}")
        
        return result
    
    async def _identify_dvd_components(self, hosts: Dict, services: Dict) -> Dict[str, Any]:
        """DVD 컴포넌트 식별"""
        logger.info("🔍 DVD 컴포넌트 식별 중...")
        
        components = {
            "flight_controller": None,
            "companion_computer": None,
            "ground_control_station": None,
            "simulator": None,
            "unknown_components": []
        }
        
        for host_ip, host_services in services.items():
            component_type = self._classify_dvd_component(host_ip, host_services)
            
            if component_type in components and components[component_type] is None:
                components[component_type] = {
                    "ip": host_ip,
                    "services": host_services,
                    "role": component_type
                }
                logger.info(f"✅ {component_type} 식별: {host_ip}")
            elif component_type == "unknown":
                components["unknown_components"].append({
                    "ip": host_ip,
                    "services": host_services
                })
        
        return components
    
    def _classify_dvd_component(self, host_ip: str, services: Dict) -> str:
        """DVD 컴포넌트 분류"""
        open_ports = set(services.keys())
        
        # Flight Controller: MAVLink 포트만 열려있음
        if 14550 in open_ports and len(open_ports) <= 2:
            return "flight_controller"
        
        # Companion Computer: 여러 서비스 (HTTP, FTP, RTSP 등)
        if any(port in open_ports for port in [80, 21, 8554]) and 14552 in open_ports:
            return "companion_computer"
        
        # Ground Control Station: GCS MAVLink 포트
        if 14551 in open_ports:
            return "ground_control_station"
        
        # Simulator: SITL MAVLink 포트
        if 5760 in open_ports:
            return "simulator"
        
        return "unknown"
    
    async def _map_network_topology(self, hosts: Dict, services: Dict) -> Dict[str, Any]:
        """네트워크 토폴로지 매핑"""
        logger.info("🗺️  네트워크 토폴로지 매핑 중...")
        
        topology = {
            "network_segments": [],
            "communication_flows": [],
            "security_boundaries": []
        }
        
        # 네트워크 세그먼트 식별
        segments = self._identify_network_segments(hosts)
        topology["network_segments"] = segments
        
        # 통신 흐름 분석
        flows = self._analyze_communication_flows(services)
        topology["communication_flows"] = flows
        
        return topology
    
    def _identify_network_segments(self, hosts: Dict) -> List[Dict]:
        """네트워크 세그먼트 식별"""
        segments = []
        
        # IP 주소 기준으로 세그먼트 그룹화
        segments_dict = {}
        
        for host_ip, host_info in hosts.items():
            network = '.'.join(host_ip.split('.')[:-1]) + '.0/24'
            
            if network not in segments_dict:
                segments_dict[network] = {
                    "network": network,
                    "hosts": [],
                    "type": "unknown"
                }
            
            segments_dict[network]["hosts"].append({
                "ip": host_ip,
                "role": host_info.get("role", "unknown")
            })
        
        # DVD 네트워크 타입 식별
        for network, segment in segments_dict.items():
            if network.startswith("10.13.0"):
                segment["type"] = "dvd_infrastructure"
            elif network.startswith("192.168.13"):
                segment["type"] = "dvd_wireless"
            elif network.startswith("172."):
                segment["type"] = "docker_network"
            
            segments.append(segment)
        
        return segments
    
    def _analyze_communication_flows(self, services: Dict) -> List[Dict]:
        """통신 흐름 분석"""
        flows = []
        
        # MAVLink 통신 흐름 분석
        mavlink_hosts = {}
        
        for host_ip, host_services in services.items():
            for port, service_info in host_services.items():
                if "mavlink" in service_info.get("service", ""):
                    if host_ip not in mavlink_hosts:
                        mavlink_hosts[host_ip] = []
                    mavlink_hosts[host_ip].append(port)
        
        # 흐름 정보 생성
        for host_ip, ports in mavlink_hosts.items():
            flow = {
                "source": host_ip,
                "protocol": "mavlink",
                "ports": ports,
                "direction": "bidirectional",
                "type": "control_communication"
            }
            flows.append(flow)
        
        return flows
    
    async def _assess_security_status(self, services: Dict) -> Dict[str, Any]:
        """보안 상태 평가"""
        logger.info("🛡️  보안 상태 평가 중...")
        
        security_status = {
            "risk_level": "unknown",
            "vulnerabilities": [],
            "recommendations": [],
            "open_services": 0,
            "secure_services": 0
        }
        
        vulnerabilities = []
        total_services = 0
        secure_services = 0
        
        for host_ip, host_services in services.items():
            for port, service_info in host_services.items():
                total_services += 1
                service_name = service_info.get("service", "unknown")
                
                # 취약점 확인
                vulns = self._check_service_vulnerabilities(port, service_name, service_info)
                vulnerabilities.extend(vulns)
                
                # 보안 서비스 확인
                if self._is_secure_service(port, service_name):
                    secure_services += 1
        
        security_status["vulnerabilities"] = vulnerabilities
        security_status["open_services"] = total_services
        security_status["secure_services"] = secure_services
        
        # 위험도 계산
        risk_score = len(vulnerabilities) / max(total_services, 1) * 100
        security_status["risk_level"] = self._calculate_risk_level(risk_score)
        
        # 권장사항 생성
        security_status["recommendations"] = self._generate_security_recommendations(vulnerabilities)
        
        return security_status
    
    def _check_service_vulnerabilities(self, port: int, service_name: str, service_info: Dict) -> List[Dict]:
        """서비스 취약점 확인"""
        vulnerabilities = []
        
        # 일반적인 취약 서비스들
        vulnerable_services = {
            21: {"service": "ftp", "risk": "high", "reason": "평문 통신, 약한 인증"},
            23: {"service": "telnet", "risk": "critical", "reason": "평문 통신, 보안 없음"},
            80: {"service": "http", "risk": "medium", "reason": "암호화되지 않은 웹 서비스"},
            14550: {"service": "mavlink", "risk": "high", "reason": "암호화되지 않은 드론 제어"}
        }
        
        if port in vulnerable_services:
            vuln_info = vulnerable_services[port]
            vulnerabilities.append({
                "port": port,
                "service": service_name,
                "risk_level": vuln_info["risk"],
                "description": vuln_info["reason"],
                "recommendation": f"{vuln_info['service']} 서비스 보안 강화 필요"
            })
        
        return vulnerabilities
    
    def _is_secure_service(self, port: int, service_name: str) -> bool:
        """보안 서비스 여부 확인"""
        secure_services = {443, 22}  # HTTPS, SSH
        return port in secure_services
    
    def _calculate_risk_level(self, risk_score: float) -> str:
        """위험도 계산"""
        if risk_score >= 80:
            return "critical"
        elif risk_score >= 60:
            return "high"
        elif risk_score >= 40:
            return "medium"
        elif risk_score >= 20:
            return "low"
        else:
            return "minimal"
    
    def _generate_security_recommendations(self, vulnerabilities: List[Dict]) -> List[str]:
        """보안 권장사항 생성"""
        recommendations = []
        
        if any(v["risk_level"] == "critical" for v in vulnerabilities):
            recommendations.append("즉시 임계 취약점 패치 필요")
        
        if any(v["port"] in [21, 23] for v in vulnerabilities):
            recommendations.append("평문 프로토콜 사용 중단 (FTP, Telnet)")
        
        if any(v["port"] == 14550 for v in vulnerabilities):
            recommendations.append("MAVLink 암호화 활성화")
        
        if any(v["port"] == 80 for v in vulnerabilities):
            recommendations.append("HTTPS 사용으로 전환")
        
        recommendations.append("네트워크 접근 제어 강화")
        recommendations.append("정기적인 보안 스캔 수행")
        
        return recommendations