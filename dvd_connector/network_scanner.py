# dvd_connector/network_scanner.py
"""
DVD 네트워크 스캐너
드론 네트워크 환경 탐지 및 분석
"""

import asyncio
import socket
import logging
import time
import json
import subprocess
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import ipaddress
from concurrent.futures import ThreadPoolExecutor
import struct

logger = logging.getLogger(__name__)

class ServiceType(Enum):
    """서비스 타입"""
    MAVLINK = "mavlink"
    HTTP = "http"
    HTTPS = "https"
    SSH = "ssh"
    RTSP = "rtsp"
    FTP = "ftp"
    TELNET = "telnet"
    UNKNOWN = "unknown"

class DeviceType(Enum):
    """디바이스 타입"""
    FLIGHT_CONTROLLER = "flight_controller"
    COMPANION_COMPUTER = "companion_computer"
    GROUND_STATION = "ground_station"
    CAMERA = "camera"
    ROUTER = "router"
    UNKNOWN = "unknown"

@dataclass
class NetworkService:
    """네트워크 서비스 정보"""
    port: int
    service_type: ServiceType
    banner: str = ""
    version: str = ""
    is_vulnerable: bool = False
    vulnerabilities: List[str] = None
    
    def __post_init__(self):
        if self.vulnerabilities is None:
            self.vulnerabilities = []

@dataclass
class NetworkDevice:
    """네트워크 디바이스 정보"""
    ip: str
    hostname: str = ""
    mac_address: str = ""
    device_type: DeviceType = DeviceType.UNKNOWN
    manufacturer: str = ""
    os_info: str = ""
    services: List[NetworkService] = None
    response_time: float = 0.0
    last_seen: float = 0.0
    is_drone_related: bool = False
    
    def __post_init__(self):
        if self.services is None:
            self.services = []
        if self.last_seen == 0.0:
            self.last_seen = time.time()

@dataclass
class NetworkScanResult:
    """네트워크 스캔 결과"""
    network_range: str
    total_hosts: int
    active_hosts: int
    devices: List[NetworkDevice]
    drone_devices: List[NetworkDevice]
    scan_duration: float
    timestamp: float
    
    def get_device_by_ip(self, ip: str) -> Optional[NetworkDevice]:
        """IP로 디바이스 찾기"""
        for device in self.devices:
            if device.ip == ip:
                return device
        return None

class DVDNetworkScanner:
    """DVD 네트워크 스캐너"""
    
    def __init__(self, timeout: int = 3, max_threads: int = 50):
        self.timeout = timeout
        self.max_threads = max_threads
        self.executor = ThreadPoolExecutor(max_workers=max_threads)
        
        # 알려진 드론 포트들
        self.drone_ports = {
            14550: ServiceType.MAVLINK,  # Primary MAVLink
            14551: ServiceType.MAVLINK,  # Secondary MAVLink
            14552: ServiceType.MAVLINK,  # Tertiary MAVLink
            5760: ServiceType.MAVLINK,   # SITL MAVLink
            5761: ServiceType.MAVLINK,   # SITL MAVLink
            5762: ServiceType.MAVLINK,   # SITL MAVLink
            5763: ServiceType.MAVLINK,   # SITL MAVLink
            554: ServiceType.RTSP,       # RTSP Video Stream
            8554: ServiceType.RTSP,      # Alternative RTSP
            8000: ServiceType.HTTP,      # Web Interface
            8080: ServiceType.HTTP,      # Alternative Web
            80: ServiceType.HTTP,        # HTTP
            443: ServiceType.HTTPS,      # HTTPS
            22: ServiceType.SSH,         # SSH
            21: ServiceType.FTP,         # FTP
            23: ServiceType.TELNET,      # Telnet
        }
        
        # 드론 관련 배너 시그니처
        self.drone_signatures = [
            "ardupilot", "px4", "mavlink", "qgroundcontrol",
            "mission planner", "apm planner", "companion",
            "pixhawk", "cube", "sitl", "gazebo", "rtsp"
        ]
        
        # 취약점 시그니처
        self.vulnerability_signatures = {
            "default_password": ["admin:admin", "root:root", "admin:password"],
            "weak_auth": ["basic auth", "no auth", "anonymous"],
            "outdated_version": ["old version", "deprecated"],
            "open_telnet": ["telnet", "port 23"],
            "open_ftp": ["ftp", "port 21"],
            "unencrypted_stream": ["rtsp", "http stream"]
        }
    
    async def scan_network(self, network_range: str, 
                          quick_scan: bool = False, 
                          deep_scan: bool = False) -> NetworkScanResult:
        """네트워크 스캔 실행"""
        start_time = time.time()
        logger.info(f"네트워크 스캔 시작: {network_range}")
        
        try:
            # 네트워크 범위 파싱
            network = ipaddress.ip_network(network_range, strict=False)
            
            # 스캔 범위 제한 (보안상 이유)
            if network.num_addresses > 1024:
                logger.warning(f"스캔 범위가 너무 큼: {network_range}")
                network = ipaddress.ip_network(f"{network.network_address}/24", strict=False)
            
            # 호스트 발견
            active_hosts = await self._discover_hosts(network)
            logger.info(f"활성 호스트 {len(active_hosts)}개 발견")
            
            # 각 호스트에 대해 상세 스캔
            devices = []
            for host_ip in active_hosts:
                device = await self._scan_host(host_ip, quick_scan, deep_scan)
                if device:
                    devices.append(device)
            
            # 드론 관련 디바이스 필터링
            drone_devices = [d for d in devices if d.is_drone_related]
            
            scan_duration = time.time() - start_time
            
            result = NetworkScanResult(
                network_range=network_range,
                total_hosts=int(network.num_addresses),
                active_hosts=len(active_hosts),
                devices=devices,
                drone_devices=drone_devices,
                scan_duration=scan_duration,
                timestamp=time.time()
            )
            
            logger.info(f"네트워크 스캔 완료: {scan_duration:.2f}초")
            return result
            
        except Exception as e:
            logger.error(f"네트워크 스캔 오류: {e}")
            raise
    
    async def _discover_hosts(self, network: ipaddress.IPv4Network) -> List[str]:
        """활성 호스트 발견"""
        active_hosts = []
        
        # 핑 스캔
        ping_tasks = []
        for ip in network.hosts():
            if len(ping_tasks) >= self.max_threads:
                # 배치 처리
                results = await asyncio.gather(*ping_tasks, return_exceptions=True)
                for result in results:
                    if isinstance(result, str):
                        active_hosts.append(result)
                ping_tasks = []
            
            ping_tasks.append(self._ping_host(str(ip)))
        
        # 마지막 배치 처리
        if ping_tasks:
            results = await asyncio.gather(*ping_tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, str):
                    active_hosts.append(result)
        
        return active_hosts
    
    async def _ping_host(self, host_ip: str) -> Optional[str]:
        """호스트 ping 테스트"""
        try:
            # 포트 기반 연결 테스트 (ping 대신)
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(host_ip, 80),
                timeout=1
            )
            writer.close()
            await writer.wait_closed()
            return host_ip
        except Exception:
            # 대안으로 다른 일반적인 포트 시도
            try:
                _, writer = await asyncio.wait_for(
                    asyncio.open_connection(host_ip, 22),
                    timeout=1
                )
                writer.close()
                await writer.wait_closed()
                return host_ip
            except Exception:
                return None
    
    async def _scan_host(self, host_ip: str, quick_scan: bool, deep_scan: bool) -> Optional[NetworkDevice]:
        """호스트 상세 스캔"""
        start_time = time.time()
        
        try:
            device = NetworkDevice(ip=host_ip)
            
            # 호스트명 해석
            try:
                hostname = socket.gethostbyaddr(host_ip)[0]
                device.hostname = hostname
            except Exception:
                pass
            
            # 포트 스캔
            if quick_scan:
                ports_to_scan = [22, 80, 443, 14550, 554]
            elif deep_scan:
                ports_to_scan = list(range(1, 1025))
            else:
                ports_to_scan = list(self.drone_ports.keys())
            
            device.services = await self._scan_ports(host_ip, ports_to_scan)
            
            # 디바이스 타입 및 제조사 식별
            device.device_type = self._identify_device_type(device)
            device.manufacturer = await self._identify_manufacturer(device)
            
            # 드론 관련 여부 확인
            device.is_drone_related = self._is_drone_related(device)
            
            # OS 정보 수집 (deep scan 시)
            if deep_scan:
                device.os_info = await self._identify_os(device)
            
            device.response_time = time.time() - start_time
            
            return device
            
        except Exception as e:
            logger.debug(f"호스트 스캔 오류 {host_ip}: {e}")
            return None
    
    async def _scan_ports(self, host_ip: str, ports: List[int]) -> List[NetworkService]:
        """포트 스캔"""
        services = []
        
        # 포트 스캔 태스크 생성
        port_tasks = []
        for port in ports:
            port_tasks.append(self._scan_single_port(host_ip, port))
        
        # 배치 처리로 포트 스캔
        batch_size = 20
        for i in range(0, len(port_tasks), batch_size):
            batch = port_tasks[i:i + batch_size]
            results = await asyncio.gather(*batch, return_exceptions=True)
            
            for result in results:
                if isinstance(result, NetworkService):
                    services.append(result)
        
        return services
    
    async def _scan_single_port(self, host_ip: str, port: int) -> Optional[NetworkService]:
        """단일 포트 스캔"""
        try:
            # 포트 연결 테스트
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host_ip, port),
                timeout=self.timeout
            )
            
            # 서비스 타입 식별
            service_type = self.drone_ports.get(port, ServiceType.UNKNOWN)
            
            # 배너 수집
            banner = ""
            try:
                # 일부 데이터 읽기 시도
                data = await asyncio.wait_for(reader.read(1024), timeout=2)
                banner = data.decode('utf-8', errors='ignore').strip()
            except Exception:
                pass
            
            # HTTP 서비스의 경우 HTTP 요청 시도
            if port in [80, 8000, 8080]:
                banner = await self._get_http_banner(host_ip, port)
                service_type = ServiceType.HTTP
            
            writer.close()
            await writer.wait_closed()
            
            # 서비스 객체 생성
            service = NetworkService(
                port=port,
                service_type=service_type,
                banner=banner
            )
            
            # 버전 정보 추출
            service.version = self._extract_version(banner)
            
            # 취약점 검사
            service.vulnerabilities = self._check_vulnerabilities(service)
            service.is_vulnerable = len(service.vulnerabilities) > 0
            
            return service
            
        except Exception:
            return None
    
    async def _get_http_banner(self, host_ip: str, port: int) -> str:
        """HTTP 배너 수집"""
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host_ip, port),
                timeout=self.timeout
            )
            
            # HTTP GET 요청
            request = f"GET / HTTP/1.1\r\nHost: {host_ip}\r\n\r\n"
            writer.write(request.encode())
            await writer.drain()
            
            # 응답 읽기
            response = await asyncio.wait_for(reader.read(2048), timeout=3)
            banner = response.decode('utf-8', errors='ignore')
            
            writer.close()
            await writer.wait_closed()
            
            return banner
            
        except Exception:
            return ""
    
    def _extract_version(self, banner: str) -> str:
        """배너에서 버전 정보 추출"""
        if not banner:
            return ""
        
        banner_lower = banner.lower()
        
        # 일반적인 버전 패턴
        version_patterns = [
            r"server: (.+)",
            r"version (\d+\.\d+[\.\d]*)",
            r"v(\d+\.\d+[\.\d]*)",
            r"(\d+\.\d+[\.\d]*)"
        ]
        
        import re
        for pattern in version_patterns:
            match = re.search(pattern, banner_lower)
            if match:
                return match.group(1).strip()
        
        return ""
    
    def _check_vulnerabilities(self, service: NetworkService) -> List[str]:
        """서비스 취약점 검사"""
        vulnerabilities = []
        banner_lower = service.banner.lower()
        
        # 기본 인증 취약점
        if any(sig in banner_lower for sig in ["admin", "default", "password"]):
            vulnerabilities.append("기본 인증 정보 사용 가능성")
        
        # 암호화되지 않은 서비스
        if service.service_type in [ServiceType.HTTP, ServiceType.FTP, ServiceType.TELNET]:
            if service.port not in [443]:  # HTTPS 제외
                vulnerabilities.append("암호화되지 않은 통신")
        
        # MAVLink 보안 취약점
        if service.service_type == ServiceType.MAVLINK:
            vulnerabilities.append("MAVLink 프로토콜 - 인증 없음")
            if "signing" not in banner_lower:
                vulnerabilities.append("MAVLink 메시지 서명 없음")
        
        # RTSP 스트림 보안
        if service.service_type == ServiceType.RTSP:
            if "auth" not in banner_lower:
                vulnerabilities.append("인증 없는 비디오 스트림")
        
        # 오래된 버전 확인
        if service.version:
            if self._is_outdated_version(service.version):
                vulnerabilities.append(f"오래된 버전: {service.version}")
        
        return vulnerabilities
    
    def _is_outdated_version(self, version: str) -> bool:
        """오래된 버전 여부 확인"""
        # 간단한 버전 확인 로직
        try:
            import re
            version_match = re.search(r"(\d+)\.(\d+)", version)
            if version_match:
                major, minor = map(int, version_match.groups())
                
                # 예시: 메이저 버전이 3 미만이면 오래된 것으로 판단
                if major < 3:
                    return True
                    
                # 예시: 4.0 미만이면 오래된 것으로 판단
                if major == 4 and minor < 0:
                    return True
        except Exception:
            pass
        
        return False
    
    def _identify_device_type(self, device: NetworkDevice) -> DeviceType:
        """디바이스 타입 식별"""
        services = device.services
        
        # 서비스 포트 기반 식별
        mavlink_ports = [s.port for s in services if s.service_type == ServiceType.MAVLINK]
        http_ports = [s.port for s in services if s.service_type == ServiceType.HTTP]
        rtsp_ports = [s.port for s in services if s.service_type == ServiceType.RTSP]
        
        # 플라이트 컨트롤러 패턴
        if 14550 in mavlink_ports and not http_ports:
            return DeviceType.FLIGHT_CONTROLLER
        
        # 컴패니언 컴퓨터 패턴
        if mavlink_ports and http_ports and rtsp_ports:
            return DeviceType.COMPANION_COMPUTER
        
        # GCS 패턴
        if 14551 in mavlink_ports or (http_ports and not rtsp_ports):
            return DeviceType.GROUND_STATION
        
        # 카메라 패턴
        if rtsp_ports and not mavlink_ports:
            return DeviceType.CAMERA
        
        # 라우터/네트워크 장비 패턴
        if 80 in http_ports and 22 in [s.port for s in services if s.service_type == ServiceType.SSH]:
            return DeviceType.ROUTER
        
        return DeviceType.UNKNOWN
    
    async def _identify_manufacturer(self, device: NetworkDevice) -> str:
        """제조사 식별"""
        manufacturer = ""
        
        # 배너에서 제조사 정보 추출
        for service in device.services:
            banner_lower = service.banner.lower()
            
            # 알려진 드론 제조사들
            manufacturers = [
                "dji", "parrot", "autel", "yuneec", "skydio",
                "3dr", "ardupilot", "px4", "pixhawk", "holybro",
                "cube", "matek", "omnibus", "kakute"
            ]
            
            for mfg in manufacturers:
                if mfg in banner_lower:
                    manufacturer = mfg.upper()
                    break
            
            if manufacturer:
                break
        
        # MAC 주소 기반 제조사 식별
        if not manufacturer and device.mac_address:
            manufacturer = await self._identify_manufacturer_by_mac(device.mac_address)
        
        return manufacturer
    
    async def _identify_manufacturer_by_mac(self, mac_address: str) -> str:
        """MAC 주소로 제조사 식별"""
        try:
            # MAC 주소의 OUI (첫 3바이트)로 제조사 식별
            oui = mac_address.replace(":", "").replace("-", "")[:6].upper()
            
            # 알려진 드론 제조사 OUI 매핑
            oui_mapping = {
                "60C547": "DJI",
                "0026DA": "3D Robotics",
                "A0F3C1": "Parrot",
                "90FD61": "Autel",
                "001EC0": "Yuneec"
            }
            
            return oui_mapping.get(oui, "")
            
        except Exception:
            return ""
    
    def _is_drone_related(self, device: NetworkDevice) -> bool:
        """드론 관련 디바이스 여부 확인"""
        # 디바이스 타입 기반 확인
        if device.device_type in [
            DeviceType.FLIGHT_CONTROLLER,
            DeviceType.COMPANION_COMPUTER,
            DeviceType.GROUND_STATION,
            DeviceType.CAMERA
        ]:
            return True
        
        # MAVLink 서비스 존재 확인
        mavlink_services = [s for s in device.services if s.service_type == ServiceType.MAVLINK]
        if mavlink_services:
            return True
        
        # 배너에서 드론 관련 키워드 확인
        for service in device.services:
            banner_lower = service.banner.lower()
            if any(sig in banner_lower for sig in self.drone_signatures):
                return True
        
        # 호스트명에서 드론 관련 키워드 확인
        if device.hostname:
            hostname_lower = device.hostname.lower()
            drone_keywords = ["drone", "uav", "copter", "quad", "ardupilot", "px4", "mavlink"]
            if any(keyword in hostname_lower for keyword in drone_keywords):
                return True
        
        return False
    
    async def _identify_os(self, device: NetworkDevice) -> str:
        """OS 정보 식별"""
        os_info = ""
        
        # 서비스 배너에서 OS 정보 추출
        for service in device.services:
            banner_lower = service.banner.lower()
            
            if "linux" in banner_lower:
                os_info = "Linux"
            elif "ubuntu" in banner_lower:
                os_info = "Ubuntu Linux"
            elif "raspberry" in banner_lower or "raspbian" in banner_lower:
                os_info = "Raspberry Pi OS"
            elif "windows" in banner_lower:
                os_info = "Windows"
            elif "macos" in banner_lower or "darwin" in banner_lower:
                os_info = "macOS"
            
            if os_info:
                break
        
        # SSH 배너에서 더 정확한 정보 시도
        ssh_services = [s for s in device.services if s.port == 22]
        if ssh_services and not os_info:
            ssh_banner = ssh_services[0].banner.lower()
            if "openssh" in ssh_banner:
                if "ubuntu" in ssh_banner:
                    os_info = "Ubuntu Linux"
                elif "debian" in ssh_banner:
                    os_info = "Debian Linux"
                else:
                    os_info = "Linux"
        
        return os_info
    
    def generate_scan_report(self, result: NetworkScanResult) -> str:
        """스캔 보고서 생성"""
        report = []
        report.append("="*70)
        report.append("🔍 DVD 네트워크 스캔 보고서")
        report.append("="*70)
        report.append(f"스캔 범위: {result.network_range}")
        report.append(f"총 호스트: {result.total_hosts}")
        report.append(f"활성 호스트: {result.active_hosts}")
        report.append(f"드론 관련 디바이스: {len(result.drone_devices)}")
        report.append(f"스캔 시간: {result.scan_duration:.2f}초")
        report.append("")
        
        # 드론 관련 디바이스 상세 정보
        if result.drone_devices:
            report.append("🚁 드론 관련 디바이스:")
            report.append("-"*50)
            
            for device in result.drone_devices:
                report.append(f"IP: {device.ip}")
                if device.hostname:
                    report.append(f"  호스트명: {device.hostname}")
                report.append(f"  타입: {device.device_type.value}")
                if device.manufacturer:
                    report.append(f"  제조사: {device.manufacturer}")
                if device.os_info:
                    report.append(f"  OS: {device.os_info}")
                
                # 서비스 정보
                if device.services:
                    report.append("  서비스:")
                    for service in device.services:
                        status = "🚨" if service.is_vulnerable else "✅"
                        report.append(f"    {status} 포트 {service.port}: {service.service_type.value}")
                        if service.vulnerabilities:
                            for vuln in service.vulnerabilities:
                                report.append(f"      ⚠️ {vuln}")
                
                report.append("")
        
        # 전체 디바이스 요약
        if result.devices:
            report.append("📱 전체 활성 디바이스:")
            report.append("-"*30)
            
            for device in result.devices:
                drone_indicator = "🚁" if device.is_drone_related else "💻"
                vuln_count = sum(len(s.vulnerabilities) for s in device.services)
                vuln_indicator = f"({vuln_count} 취약점)" if vuln_count > 0 else ""
                
                report.append(f"{drone_indicator} {device.ip} - {device.device_type.value} {vuln_indicator}")
        
        report.append("="*70)
        
        return "\n".join(report)
    
    async def quick_drone_scan(self, network_range: str = "10.13.0.0/24") -> List[NetworkDevice]:
        """빠른 드론 디바이스 스캔"""
        result = await self.scan_network(network_range, quick_scan=True)
        return result.drone_devices
    
    async def vulnerability_scan(self, target_ip: str) -> Dict[str, Any]:
        """특정 타겟 취약점 스캔"""
        device = await self._scan_host(target_ip, quick_scan=False, deep_scan=True)
        
        if not device:
            return {"error": "호스트에 연결할 수 없음"}
        
        vulnerabilities = []
        for service in device.services:
            if service.vulnerabilities:
                vulnerabilities.extend([
                    {
                        "port": service.port,
                        "service": service.service_type.value,
                        "vulnerability": vuln
                    }
                    for vuln in service.vulnerabilities
                ])
        
        return {
            "target": target_ip,
            "device_type": device.device_type.value,
            "total_vulnerabilities": len(vulnerabilities),
            "vulnerabilities": vulnerabilities,
            "risk_level": self._calculate_risk_level(vulnerabilities)
        }
    
    def _calculate_risk_level(self, vulnerabilities: List[Dict[str, Any]]) -> str:
        """위험도 계산"""
        if not vulnerabilities:
            return "낮음"
        
        critical_count = sum(1 for v in vulnerabilities if "인증 없음" in v.get("vulnerability", ""))
        high_count = sum(1 for v in vulnerabilities if "암호화되지 않은" in v.get("vulnerability", ""))
        
        if critical_count >= 2:
            return "매우 높음"
        elif critical_count >= 1 or high_count >= 3:
            return "높음"
        elif high_count >= 1:
            return "중간"
        else:
            return "낮음"

# 편의 함수들
async def quick_dvd_scan(network: str = "10.13.0.0/24") -> NetworkScanResult:
    """빠른 DVD 네트워크 스캔"""
    scanner = DVDNetworkScanner()
    return await scanner.scan_network(network, quick_scan=True)

async def find_drone_devices(network: str = "10.13.0.0/24") -> List[NetworkDevice]:
    """드론 디바이스 찾기"""
    scanner = DVDNetworkScanner()
    return await scanner.quick_drone_scan(network)

# 테스트 실행
if __name__ == "__main__":
    async def main():
        print("DVD 네트워크 스캐너 테스트 시작...")
        
        scanner = DVDNetworkScanner()
        
        # 빠른 스캔
        print("빠른 스캔 실행 중...")
        result = await scanner.scan_network("127.0.0.0/24", quick_scan=True)
        
        print(scanner.generate_scan_report(result))
        
        # 드론 디바이스 검색
        drone_devices = await find_drone_devices("10.13.0.0/24")
        print(f"\n드론 디바이스 발견: {len(drone_devices)}개")
        
        for device in drone_devices:
            print(f"  - {device.ip}: {device.device_type.value}")
    
    import asyncio
    asyncio.run(main())