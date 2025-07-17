# dvd_connector/safety_checker.py
"""
DVD 안전성 검사기
실제 드론 하드웨어 보호 및 안전한 테스트 환경 보장
"""

import asyncio
import logging
import time
import socket
import subprocess
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import json
import ipaddress

logger = logging.getLogger(__name__)

class SafetyLevel(Enum):
    """안전성 수준"""
    SAFE = "safe"           # 안전한 시뮬레이션 환경
    CAUTION = "caution"     # 주의 필요 (가상 환경)
    WARNING = "warning"     # 경고 (실제 하드웨어 감지)
    DANGER = "danger"       # 위험 (실제 드론 감지)
    BLOCKED = "blocked"     # 차단됨

class NetworkType(Enum):
    """네트워크 타입"""
    SIMULATION = "simulation"      # 시뮬레이션 네트워크
    VIRTUAL = "virtual"           # 가상 네트워크
    REAL_ISOLATED = "real_isolated"  # 격리된 실제 네트워크
    REAL_PRODUCTION = "real_production"  # 실제 운영 네트워크

@dataclass
class SafetyCheckResult:
    """안전성 검사 결과"""
    safety_level: SafetyLevel
    network_type: NetworkType
    detected_devices: List[Dict[str, Any]]
    safety_violations: List[str]
    recommendations: List[str]
    is_safe_to_proceed: bool
    timestamp: float

class SafetyChecker:
    """DVD 안전성 검사기"""
    
    def __init__(self):
        self.known_simulation_networks = [
            "10.13.0.0/24",      # DVD 기본 네트워크
            "127.0.0.0/8",       # 로컬호스트
            "169.254.0.0/16",    # 링크 로컬
            "172.16.0.0/12",     # 사설 네트워크
            "192.168.0.0/16"     # 사설 네트워크
        ]
        
        self.dangerous_indicators = [
            "real_hardware_detected",
            "production_network",
            "internet_accessible",
            "physical_mavlink_device",
            "real_gps_coordinates",
            "actual_flight_controller"
        ]
        
        self.safe_containers = [
            "ardupilot-sitl",
            "gazebo-simulation",
            "qgroundcontrol",
            "companion-sim",
            "dvd-"  # DVD 프리픽스
        ]
    
    async def comprehensive_safety_check(self, target_config: Dict[str, Any]) -> SafetyCheckResult:
        """종합적인 안전성 검사"""
        logger.info("종합적인 안전성 검사 시작")
        
        detected_devices = []
        safety_violations = []
        recommendations = []
        
        # 1. 네트워크 안전성 검사
        network_result = await self._check_network_safety(target_config)
        detected_devices.extend(network_result.get("devices", []))
        safety_violations.extend(network_result.get("violations", []))
        
        # 2. 하드웨어 검사
        hardware_result = await self._check_hardware_safety()
        detected_devices.extend(hardware_result.get("devices", []))
        safety_violations.extend(hardware_result.get("violations", []))
        
        # 3. 프로세스 및 서비스 검사
        process_result = await self._check_process_safety()
        detected_devices.extend(process_result.get("devices", []))
        safety_violations.extend(process_result.get("violations", []))
        
        # 4. 환경 변수 및 설정 검사
        config_result = await self._check_configuration_safety(target_config)
        safety_violations.extend(config_result.get("violations", []))
        
        # 5. 지리적 위치 검사 (GPS 좌표)
        location_result = await self._check_location_safety(target_config)
        safety_violations.extend(location_result.get("violations", []))
        
        # 안전성 수준 결정
        safety_level = self._determine_safety_level(safety_violations, detected_devices)
        network_type = self._determine_network_type(network_result)
        
        # 권장사항 생성
        recommendations = self._generate_recommendations(
            safety_level, safety_violations, detected_devices
        )
        
        # 최종 안전성 결과
        is_safe_to_proceed = safety_level in [SafetyLevel.SAFE, SafetyLevel.CAUTION]
        
        result = SafetyCheckResult(
            safety_level=safety_level,
            network_type=network_type,
            detected_devices=detected_devices,
            safety_violations=safety_violations,
            recommendations=recommendations,
            is_safe_to_proceed=is_safe_to_proceed,
            timestamp=time.time()
        )
        
        logger.info(f"안전성 검사 완료: {safety_level.value}")
        return result
    
    async def _check_network_safety(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """네트워크 안전성 검사"""
        devices = []
        violations = []
        
        target_host = config.get("host", "localhost")
        target_network = config.get("dvd_network", "10.13.0.0/24")
        
        try:
            # 대상 네트워크가 알려진 시뮬레이션 네트워크인지 확인
            is_simulation_network = any(
                ipaddress.ip_network(target_network).subnet_of(ipaddress.ip_network(sim_net))
                for sim_net in self.known_simulation_networks
            )
            
            if not is_simulation_network:
                violations.append(f"알 수 없는 네트워크: {target_network}")
            
            # 네트워크 스캔
            network_devices = await self._scan_network(target_network)
            devices.extend(network_devices)
            
            # 실제 드론 하드웨어 시그니처 확인
            for device in network_devices:
                if self._is_real_drone_hardware(device):
                    violations.append(f"실제 드론 하드웨어 감지: {device}")
            
            # 인터넷 접근 가능성 확인
            if await self._check_internet_access(target_host):
                violations.append("인터넷 접근 가능 - 실제 네트워크 환경")
            
        except Exception as e:
            logger.error(f"네트워크 안전성 검사 오류: {e}")
            violations.append(f"네트워크 검사 오류: {str(e)}")
        
        return {
            "devices": devices,
            "violations": violations,
            "network_type": "simulation" if is_simulation_network else "unknown"
        }
    
    async def _scan_network(self, network: str) -> List[Dict[str, Any]]:
        """네트워크 스캔"""
        devices = []
        
        try:
            # 네트워크 범위 확인
            network_obj = ipaddress.ip_network(network)
            
            # 제한된 범위만 스캔 (보안상 이유)
            if network_obj.num_addresses > 256:
                logger.warning(f"네트워크 범위가 너무 큼: {network}")
                return devices
            
            # 주요 호스트만 스캔
            key_hosts = [
                str(network_obj.network_address + 1),  # 게이트웨이
                str(network_obj.network_address + 2),  # 컴패니언 컴퓨터
                str(network_obj.network_address + 3),  # GCS
                str(network_obj.network_address + 4),  # 플라이트 컨트롤러
            ]
            
            for host_ip in key_hosts:
                device_info = await self._probe_host(host_ip)
                if device_info:
                    devices.append(device_info)
        
        except Exception as e:
            logger.error(f"네트워크 스캔 오류: {e}")
        
        return devices
    
    async def _probe_host(self, host_ip: str) -> Optional[Dict[str, Any]]:
        """호스트 조사"""
        try:
            # 포트 스캔
            open_ports = await self._scan_ports(host_ip, [
                22, 80, 443, 554, 5760, 14550, 14551, 8000
            ])
            
            if not open_ports:
                return None
            
            # 서비스 식별
            services = await self._identify_services(host_ip, open_ports)
            
            return {
                "ip": host_ip,
                "open_ports": open_ports,
                "services": services,
                "is_responsive": True,
                "scan_timestamp": time.time()
            }
            
        except Exception as e:
            logger.debug(f"호스트 조사 실패 {host_ip}: {e}")
            return None
    
    async def _scan_ports(self, host: str, ports: List[int]) -> List[int]:
        """포트 스캔"""
        open_ports = []
        
        for port in ports:
            try:
                # 비동기 포트 연결 테스트
                _, writer = await asyncio.wait_for(
                    asyncio.open_connection(host, port),
                    timeout=2
                )
                writer.close()
                await writer.wait_closed()
                open_ports.append(port)
                
            except Exception:
                continue
        
        return open_ports
    
    async def _identify_services(self, host: str, ports: List[int]) -> List[str]:
        """서비스 식별"""
        services = []
        
        service_map = {
            22: "SSH",
            80: "HTTP",
            443: "HTTPS",
            554: "RTSP",
            5760: "MAVLink",
            14550: "MAVLink Primary",
            14551: "MAVLink Secondary",
            8000: "Web Interface"
        }
        
        for port in ports:
            service = service_map.get(port, f"Unknown-{port}")
            services.append(service)
        
        return services
    
    def _is_real_drone_hardware(self, device: Dict[str, Any]) -> bool:
        """실제 드론 하드웨어 여부 확인"""
        # 실제 하드웨어 시그니처 확인
        services = device.get("services", [])
        
        # 위험한 서비스 조합 확인
        dangerous_combinations = [
            {"SSH", "MAVLink Primary", "RTSP"},  # 실제 컴패니언 컴퓨터
            {"MAVLink Primary", "MAVLink Secondary"},  # 실제 플라이트 컨트롤러
        ]
        
        for dangerous_combo in dangerous_combinations:
            if dangerous_combo.issubset(set(services)):
                return True
        
        return False
    
    async def _check_internet_access(self, host: str) -> bool:
        """인터넷 접근 가능성 확인"""
        try:
            # 외부 DNS 서버 연결 테스트
            _, writer = await asyncio.wait_for(
                asyncio.open_connection("8.8.8.8", 53),
                timeout=3
            )
            writer.close()
            await writer.wait_closed()
            return True
        except Exception:
            return False
    
    async def _check_hardware_safety(self) -> Dict[str, Any]:
        """하드웨어 안전성 검사"""
        devices = []
        violations = []
        
        try:
            # USB 디바이스 검사
            usb_devices = await self._check_usb_devices()
            devices.extend(usb_devices)
            
            # 시리얼 포트 검사
            serial_devices = await self._check_serial_devices()
            devices.extend(serial_devices)
            
            # 실제 하드웨어 감지
            for device in devices:
                if self._is_flight_controller_hardware(device):
                    violations.append(f"실제 플라이트 컨트롤러 감지: {device}")
                elif self._is_radio_hardware(device):
                    violations.append(f"실제 무선 장비 감지: {device}")
        
        except Exception as e:
            logger.error(f"하드웨어 안전성 검사 오류: {e}")
        
        return {"devices": devices, "violations": violations}
    
    async def _check_usb_devices(self) -> List[Dict[str, Any]]:
        """USB 디바이스 검사"""
        devices = []
        
        try:
            result = subprocess.run(
                ["lsusb"], capture_output=True, text=True, timeout=5
            )
            
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if line.strip():
                        devices.append({
                            "type": "usb",
                            "info": line.strip(),
                            "timestamp": time.time()
                        })
        
        except Exception as e:
            logger.debug(f"USB 디바이스 검사 오류: {e}")
        
        return devices
    
    async def _check_serial_devices(self) -> List[Dict[str, Any]]:
        """시리얼 디바이스 검사"""
        devices = []
        
        try:
            serial_paths = [
                "/dev/ttyUSB*",
                "/dev/ttyACM*",
                "/dev/ttyS*"
            ]
            
            for path_pattern in serial_paths:
                serial_files = list(Path("/dev").glob(path_pattern.replace("/dev/", "")))
                
                for serial_file in serial_files:
                    devices.append({
                        "type": "serial",
                        "device": str(serial_file),
                        "timestamp": time.time()
                    })
        
        except Exception as e:
            logger.debug(f"시리얼 디바이스 검사 오류: {e}")
        
        return devices
    
    def _is_flight_controller_hardware(self, device: Dict[str, Any]) -> bool:
        """플라이트 컨트롤러 하드웨어 여부 확인"""
        info = device.get("info", "").lower()
        
        # 알려진 플라이트 컨트롤러 제조사/모델
        flight_controller_signatures = [
            "pixhawk", "cube", "holybro", "ardupilot", "px4",
            "omnibus", "kakute", "matek", "betaflight"
        ]
        
        return any(sig in info for sig in flight_controller_signatures)
    
    def _is_radio_hardware(self, device: Dict[str, Any]) -> bool:
        """무선 장비 여부 확인"""
        info = device.get("info", "").lower()
        
        # 알려진 무선 장비 시그니처
        radio_signatures = [
            "915mhz", "2.4ghz", "elrs", "crossfire", "frsky",
            "spektrum", "futaba", "radiomaster", "horus"
        ]
        
        return any(sig in info for sig in radio_signatures)
    
    async def _check_process_safety(self) -> Dict[str, Any]:
        """프로세스 안전성 검사"""
        devices = []
        violations = []
        
        try:
            # 실행 중인 프로세스 확인
            processes = await self._get_running_processes()
            
            for process in processes:
                # 위험한 프로세스 확인
                if self._is_dangerous_process(process):
                    violations.append(f"위험한 프로세스 감지: {process}")
                
                # 드론 관련 프로세스 확인
                if self._is_drone_process(process):
                    devices.append({
                        "type": "process",
                        "name": process,
                        "timestamp": time.time()
                    })
        
        except Exception as e:
            logger.error(f"프로세스 안전성 검사 오류: {e}")
        
        return {"devices": devices, "violations": violations}
    
    async def _get_running_processes(self) -> List[str]:
        """실행 중인 프로세스 목록"""
        processes = []
        
        try:
            result = subprocess.run(
                ["ps", "aux"], capture_output=True, text=True, timeout=5
            )
            
            if result.returncode == 0:
                for line in result.stdout.split('\n')[1:]:  # 헤더 제외
                    if line.strip():
                        parts = line.split()
                        if len(parts) >= 11:
                            process_name = ' '.join(parts[10:])
                            processes.append(process_name)
        
        except Exception as e:
            logger.debug(f"프로세스 목록 조회 오류: {e}")
        
        return processes
    
    def _is_dangerous_process(self, process: str) -> bool:
        """위험한 프로세스 여부 확인"""
        process_lower = process.lower()
        
        # 실제 드론 조종 프로세스
        dangerous_processes = [
            "mission_planner",
            "apm_planner",
            "qgroundcontrol",  # 실제 버전 (Docker가 아닌)
            "mavproxy",        # 실제 연결
            "dronekit",        # 실제 드론 제어
            "px4_",            # 실제 PX4 프로세스
        ]
        
        return any(dangerous in process_lower for dangerous in dangerous_processes)
    
    def _is_drone_process(self, process: str) -> bool:
        """드론 관련 프로세스 여부 확인"""
        process_lower = process.lower()
        
        drone_processes = [
            "ardupilot", "gazebo", "sitl", "mavlink", "qgroundcontrol",
            "docker", "container", "simulation"
        ]
        
        return any(drone in process_lower for drone in drone_processes)
    
    async def _check_configuration_safety(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """설정 안전성 검사"""
        violations = []
        
        # 위험한 설정 확인
        dangerous_configs = [
            ("environment", "PRODUCTION"),
            ("real_hardware", True),
            ("live_flight", True),
            ("internet_access", True)
        ]
        
        for key, dangerous_value in dangerous_configs:
            if config.get(key) == dangerous_value:
                violations.append(f"위험한 설정: {key}={dangerous_value}")
        
        # 안전한 기본값 확인
        safe_defaults = {
            "environment": "SIMULATION",
            "simulation_mode": True,
            "safety_enabled": True
        }
        
        for key, safe_value in safe_defaults.items():
            if config.get(key) != safe_value:
                violations.append(f"안전하지 않은 설정: {key}={config.get(key)}")
        
        return {"violations": violations}
    
    async def _check_location_safety(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """위치 안전성 검사"""
        violations = []
        
        # GPS 좌표 확인
        lat = config.get("latitude", 0)
        lon = config.get("longitude", 0)
        
        if lat != 0 or lon != 0:
            # 실제 GPS 좌표 사용 여부 확인
            if self._is_real_coordinates(lat, lon):
                violations.append(f"실제 GPS 좌표 사용: {lat}, {lon}")
        
        return {"violations": violations}
    
    def _is_real_coordinates(self, lat: float, lon: float) -> bool:
        """실제 GPS 좌표 여부 확인"""
        # 일반적인 시뮬레이션 좌표
        simulation_coords = [
            (37.7749, -122.4194),  # 샌프란시스코
            (40.7128, -74.0060),   # 뉴욕
            (0.0, 0.0),            # 원점
            (37.6213, -122.3790),  # SFO 공항
        ]
        
        # 시뮬레이션 좌표와 비교
        for sim_lat, sim_lon in simulation_coords:
            if abs(lat - sim_lat) < 0.1 and abs(lon - sim_lon) < 0.1:
                return False
        
        # 실제 좌표로 추정
        return True
    
    def _determine_safety_level(self, violations: List[str], devices: List[Dict[str, Any]]) -> SafetyLevel:
        """안전성 수준 결정"""
        if not violations:
            return SafetyLevel.SAFE
        
        # 위험 수준별 분류
        critical_violations = [v for v in violations if any(
            danger in v.lower() for danger in ["실제", "위험한", "production"]
        )]
        
        if critical_violations:
            return SafetyLevel.DANGER
        
        warning_violations = [v for v in violations if any(
            warning in v.lower() for warning in ["하드웨어", "인터넷", "unknown"]
        )]
        
        if warning_violations:
            return SafetyLevel.WARNING
        
        return SafetyLevel.CAUTION
    
    def _determine_network_type(self, network_result: Dict[str, Any]) -> NetworkType:
        """네트워크 타입 결정"""
        network_type = network_result.get("network_type", "unknown")
        
        if network_type == "simulation":
            return NetworkType.SIMULATION
        elif network_type == "virtual":
            return NetworkType.VIRTUAL
        elif network_type == "real_isolated":
            return NetworkType.REAL_ISOLATED
        else:
            return NetworkType.REAL_PRODUCTION
    
    def _generate_recommendations(self, safety_level: SafetyLevel, violations: List[str], devices: List[Dict[str, Any]]) -> List[str]:
        """권장사항 생성"""
        recommendations = []
        
        if safety_level == SafetyLevel.DANGER:
            recommendations.extend([
                "🚨 즉시 테스트 중단",
                "실제 하드웨어 연결 해제",
                "시뮬레이션 환경으로 전환",
                "안전한 격리 네트워크 사용"
            ])
        
        elif safety_level == SafetyLevel.WARNING:
            recommendations.extend([
                "⚠️ 주의 깊게 진행",
                "하드웨어 연결 확인",
                "네트워크 격리 확인",
                "백업 안전장치 활성화"
            ])
        
        elif safety_level == SafetyLevel.CAUTION:
            recommendations.extend([
                "💡 기본 안전 조치 확인",
                "시뮬레이션 모드 권장",
                "정기적인 안전 검사"
            ])
        
        else:  # SAFE
            recommendations.extend([
                "✅ 안전한 환경 확인됨",
                "테스트 진행 가능",
                "정기 안전 점검 권장"
            ])
        
        return recommendations
    
    def print_safety_report(self, result: SafetyCheckResult) -> None:
        """안전성 검사 보고서 출력"""
        print("\n" + "="*60)
        print("🛡️  DVD 안전성 검사 보고서")
        print("="*60)
        
        # 안전성 수준
        level_icons = {
            SafetyLevel.SAFE: "✅",
            SafetyLevel.CAUTION: "⚠️",
            SafetyLevel.WARNING: "🚨",
            SafetyLevel.DANGER: "🚨",
            SafetyLevel.BLOCKED: "❌"
        }
        
        icon = level_icons.get(result.safety_level, "❓")
        print(f"안전성 수준: {icon} {result.safety_level.value.upper()}")
        print(f"네트워크 타입: {result.network_type.value}")
        print(f"진행 가능: {'✅ 예' if result.is_safe_to_proceed else '❌ 아니오'}")
        
        # 감지된 디바이스
        if result.detected_devices:
            print(f"\n📱 감지된 디바이스: {len(result.detected_devices)}개")
            for device in result.detected_devices[:5]:  # 최대 5개만 표시
                print(f"   • {device.get('type', 'unknown')}: {device.get('info', device.get('ip', 'N/A'))}")
        
        # 안전성 위반사항
        if result.safety_violations:
            print(f"\n🚨 안전성 위반사항: {len(result.safety_violations)}개")
            for violation in result.safety_violations[:3]:  # 최대 3개만 표시
                print(f"   • {violation}")
        
        # 권장사항
        if result.recommendations:
            print(f"\n💡 권장사항:")
            for rec in result.recommendations:
                print(f"   {rec}")
        
        print("="*60)

# 편의 함수
async def quick_safety_check(config: Dict[str, Any] = None) -> bool:
    """빠른 안전성 검사"""
    if config is None:
        config = {"host": "localhost", "environment": "SIMULATION"}
    
    checker = SafetyChecker()
    result = await checker.comprehensive_safety_check(config)
    
    return result.is_safe_to_proceed

# 테스트 실행
if __name__ == "__main__":
    async def main():
        print("DVD 안전성 검사 테스트 시작...")
        
        # 기본 안전성 검사
        test_config = {
            "host": "localhost",
            "dvd_network": "10.13.0.0/24",
            "environment": "SIMULATION",
            "simulation_mode": True,
            "safety_enabled": True
        }
        
        checker = SafetyChecker()
        result = await checker.comprehensive_safety_check(test_config)
        
        checker.print_safety_report(result)
        
        # 빠른 검사
        is_safe = await quick_safety_check(test_config)
        print(f"\n빠른 안전성 검사 결과: {'✅ 안전' if is_safe else '❌ 위험'}")
    
    import asyncio
    asyncio.run(main())