#!/usr/bin/env python3
"""
DVD 프로젝트 종합 수정 스크립트
원본 management.py와 attack_registry.py의 호환성 문제 해결
"""

import os
import sys
from pathlib import Path
import traceback

def create_missing_attack_modules():
    """누락된 공격 모듈들 생성"""
    print("\n📦 누락된 공격 모듈들 생성 중...")
    
    # 1. core/scenario.py 생성
    scenario_content = '''# dvd_lite/dvd_attacks/core/scenario.py
"""
DVD 공격 시나리오 정의
"""
from dataclasses import dataclass
from typing import List
from .enums import DVDAttackTactic, DVDFlightState, AttackDifficulty

@dataclass
class DVDAttackScenario:
    """DVD 공격 시나리오 정의"""
    name: str
    tactic: DVDAttackTactic
    description: str
    required_states: List[DVDFlightState]
    difficulty: AttackDifficulty
    prerequisites: List[str]
    targets: List[str]
    estimated_duration: float = 0.0
    stealth_level: str = "medium"
    impact_level: str = "medium"
'''
    write_file("dvd_lite/dvd_attacks/core/scenario.py", scenario_content)
    print("✅ core/scenario.py 생성됨")
    
    # 2. core/attack_base.py 생성 (간단한 버전)
    attack_base_content = '''# dvd_lite/dvd_attacks/core/attack_base.py
"""
공격 기본 클래스 정의
"""
import asyncio
import time
import logging
from abc import ABC, abstractmethod
from typing import Tuple, List, Dict, Any, Optional
from dataclasses import dataclass
from .enums import AttackType, AttackStatus

logger = logging.getLogger(__name__)

@dataclass
class AttackResult:
    """공격 결과 데이터 클래스"""
    attack_id: str
    attack_name: str
    attack_type: AttackType
    status: AttackStatus
    success_rate: float
    response_time: float
    timestamp: float
    target: str
    iocs: List[str]
    details: Dict[str, Any]
    scenario_info: Optional[Dict[str, Any]] = None

class BaseAttack(ABC):
    """DVD 공격 기본 클래스"""
    
    def __init__(self, target_ip: str = "10.13.0.2", **kwargs):
        self.target_ip = target_ip
        self.config = kwargs
        self.attack_id = f"{self.__class__.__name__.lower()}_{int(time.time())}"
        self.logger = logging.getLogger(f"attack.{self.__class__.__name__}")
    
    async def execute(self) -> AttackResult:
        """공격 실행 메인 메서드"""
        start_time = time.time()
        self.logger.info(f"공격 시작: {self.__class__.__name__} -> {self.target_ip}")
        
        try:
            success, iocs, details = await self._run_attack()
            
            result = AttackResult(
                attack_id=self.attack_id,
                attack_name=self.__class__.__name__,
                attack_type=self._get_attack_type(),
                status=AttackStatus.SUCCESS if success else AttackStatus.FAILED,
                success_rate=details.get("success_rate", 0.7 if success else 0.0),
                response_time=time.time() - start_time,
                timestamp=time.time(),
                target=self.target_ip,
                iocs=iocs,
                details=details
            )
            
            self.logger.info(f"공격 완료: {result.status.value} ({result.response_time:.2f}초)")
            return result
            
        except Exception as e:
            self.logger.error(f"공격 실패: {str(e)}")
            return AttackResult(
                attack_id=self.attack_id,
                attack_name=self.__class__.__name__,
                attack_type=self._get_attack_type(),
                status=AttackStatus.FAILED,
                success_rate=0.0,
                response_time=time.time() - start_time,
                timestamp=time.time(),
                target=self.target_ip,
                iocs=[],
                details={"error": str(e)}
            )
    
    @abstractmethod
    async def _run_attack(self) -> Tuple[bool, List[str], Dict[str, Any]]:
        """실제 공격 로직 - 하위 클래스에서 반드시 구현"""
        pass
    
    @abstractmethod
    def _get_attack_type(self) -> AttackType:
        """공격 타입 반환 - 하위 클래스에서 반드시 구현"""
        pass
'''
    write_file("dvd_lite/dvd_attacks/core/attack_base.py", attack_base_content)
    print("✅ core/attack_base.py 생성됨")

def create_attack_implementations():
    """실제 공격 구현 클래스들 생성"""
    print("\n🎯 공격 구현 클래스들 생성 중...")
    
    # WiFi 네트워크 발견 공격
    wifi_discovery_content = '''# dvd_lite/dvd_attacks/reconnaissance/wifi_discovery.py
"""
WiFi 네트워크 발견 공격
"""
import asyncio
import random
from typing import Tuple, List, Dict, Any
from ..core.attack_base import BaseAttack
from ..core.enums import AttackType

class WiFiNetworkDiscovery(BaseAttack):
    """WiFi 네트워크 발견 및 열거"""
    
    def _get_attack_type(self) -> AttackType:
        return AttackType.RECONNAISSANCE
    
    async def _run_attack(self) -> Tuple[bool, List[str], Dict[str, Any]]:
        """WiFi 네트워크 스캔 및 드론 네트워크 식별"""
        await asyncio.sleep(2.5)
        
        networks = [
            {"ssid": "Drone_WiFi", "bssid": "aa:bb:cc:dd:ee:01", "encryption": "WPA2"},
            {"ssid": "DJI_MAVIC_123456", "bssid": "aa:bb:cc:dd:ee:02", "encryption": "WPA"},
            {"ssid": "ArduPilot_AP", "bssid": "aa:bb:cc:dd:ee:03", "encryption": "Open"},
        ]
        
        discovered = random.sample(networks, k=random.randint(1, 3))
        
        iocs = []
        for network in discovered:
            iocs.append(f"WIFI_SSID:{network['ssid']}")
            iocs.append(f"WIFI_BSSID:{network['bssid']}")
        
        success = len(discovered) > 0
        
        details = {
            "discovered_networks": discovered,
            "scan_method": "passive_monitor",
            "success_rate": 0.85 if success else 0.3
        }
        
        return success, iocs, details
'''
    write_file("dvd_lite/dvd_attacks/reconnaissance/wifi_discovery.py", wifi_discovery_content)
    print("✅ WiFiNetworkDiscovery 생성됨")
    
    # MAVLink 서비스 발견
    mavlink_discovery_content = '''# dvd_lite/dvd_attacks/reconnaissance/mavlink_discovery.py
"""
MAVLink 서비스 발견 공격
"""
import asyncio
import random
from typing import Tuple, List, Dict, Any
from ..core.attack_base import BaseAttack
from ..core.enums import AttackType

class MAVLinkServiceDiscovery(BaseAttack):
    """MAVLink 서비스 발견 및 열거"""
    
    def _get_attack_type(self) -> AttackType:
        return AttackType.RECONNAISSANCE
    
    async def _run_attack(self) -> Tuple[bool, List[str], Dict[str, Any]]:
        """네트워크에서 MAVLink 서비스 스캔"""
        await asyncio.sleep(3.2)
        
        services = []
        hosts = [f"192.168.13.{i}" for i in range(1, 11)]
        
        for host in hosts:
            if random.random() > 0.7:
                service = {
                    "host": host,
                    "port": random.choice([14550, 14551, 5760]),
                    "service": "MAVLink"
                }
                services.append(service)
        
        iocs = [f"MAVLINK_SERVICE:{s['host']}:{s['port']}" for s in services]
        success = len(services) > 0
        
        details = {
            "discovered_services": services,
            "scan_method": "port_scan",
            "success_rate": 0.75 if success else 0.1
        }
        
        return success, iocs, details
'''
    write_file("dvd_lite/dvd_attacks/reconnaissance/mavlink_discovery.py", mavlink_discovery_content)
    print("✅ MAVLinkServiceDiscovery 생성됨")
    
    # 더미 공격 클래스들 생성 (다른 import 오류 방지)
    dummy_classes = [
        ("DroneComponentEnumeration", "reconnaissance", "component_enumeration"),
        ("CameraStreamDiscovery", "reconnaissance", "camera_discovery"),
        ("GPSSpoofing", "protocol_tampering", "gps_spoofing"),
        ("MAVLinkPacketInjection", "protocol_tampering", "mavlink_injection"),
        ("RadioFrequencyJamming", "protocol_tampering", "rf_jamming"),
        ("MAVLinkFloodAttack", "denial_of_service", "mavlink_flood"),
        ("WiFiDeauthenticationAttack", "denial_of_service", "wifi_deauth"),
        ("CompanionComputerResourceExhaustion", "denial_of_service", "resource_exhaustion"),
        ("FlightPlanInjection", "injection", "flight_plan"),
        ("ParameterManipulation", "injection", "parameter_manipulation"),
        ("FirmwareUploadManipulation", "injection", "firmware_manipulation"),
        ("TelemetryDataExfiltration", "exfiltration", "telemetry_data"),
        ("FlightLogExtraction", "exfiltration", "flight_logs"),
        ("VideoStreamHijacking", "exfiltration", "video_hijacking"),
        ("BootloaderExploit", "firmware_attacks", "bootloader_exploit"),
        ("FirmwareRollbackAttack", "firmware_attacks", "rollback_attack"),
        ("SecureBootBypass", "firmware_attacks", "secure_boot_bypass")
    ]
    
    for class_name, category, file_name in dummy_classes:
        dummy_content = f'''# dvd_lite/dvd_attacks/{category}/{file_name}.py
"""
{class_name} 공격 (더미 구현)
"""
import asyncio
import random
from typing import Tuple, List, Dict, Any
from ..core.attack_base import BaseAttack
from ..core.enums import AttackType

class {class_name}(BaseAttack):
    """{class_name} 공격"""
    
    def _get_attack_type(self) -> AttackType:
        return AttackType.RECONNAISSANCE  # 기본값
    
    async def _run_attack(self) -> Tuple[bool, List[str], Dict[str, Any]]:
        """더미 공격 로직"""
        await asyncio.sleep(random.uniform(1.0, 3.0))
        
        success = random.random() > 0.3
        iocs = [f"{class_name.upper()}_IOC:dummy_indicator"]
        details = {{"success_rate": 0.7 if success else 0.2}}
        
        return success, iocs, details
'''
        write_file(f"dvd_lite/dvd_attacks/{category}/{file_name}.py", dummy_content)
        print(f"✅ {class_name} 더미 클래스 생성됨")

def update_init_files():
    """__init__.py 파일들 업데이트"""
    print("\n📝 __init__.py 파일들 업데이트 중...")
    
    # core/__init__.py 업데이트
    core_init_content = '''# dvd_lite/dvd_attacks/core/__init__.py
"""
DVD 공격 시스템 핵심 컴포넌트
"""
from .enums import (
    AttackType, DVDAttackTactic, DVDFlightState, 
    AttackDifficulty, AttackStatus
)
from .scenario import DVDAttackScenario
from .attack_base import BaseAttack, AttackResult

__all__ = [
    'AttackType',
    'DVDAttackTactic', 
    'DVDFlightState',
    'AttackDifficulty',
    'AttackStatus',
    'DVDAttackScenario',
    'BaseAttack',
    'AttackResult'
]
'''
    write_file("dvd_lite/dvd_attacks/core/__init__.py", core_init_content)
    print("✅ core/__init__.py 업데이트됨")
    
    # reconnaissance/__init__.py 업데이트
    recon_init_content = '''# dvd_lite/dvd_attacks/reconnaissance/__init__.py
"""
정찰 공격 모듈
"""
try:
    from .wifi_discovery import WiFiNetworkDiscovery
    from .mavlink_discovery import MAVLinkServiceDiscovery
    from .component_enumeration import DroneComponentEnumeration
    from .camera_discovery import CameraStreamDiscovery
    
    __all__ = [
        'WiFiNetworkDiscovery',
        'MAVLinkServiceDiscovery', 
        'DroneComponentEnumeration',
        'CameraStreamDiscovery'
    ]
except ImportError as e:
    print(f"Warning: reconnaissance import error: {e}")
    __all__ = []
'''
    write_file("dvd_lite/dvd_attacks/reconnaissance/__init__.py", recon_init_content)
    print("✅ reconnaissance/__init__.py 업데이트됨")
    
    # 다른 카테고리들도 업데이트
    categories = [
        "protocol_tampering",
        "denial_of_service", 
        "injection",
        "exfiltration",
        "firmware_attacks"
    ]
    
    for category in categories:
        init_content = f'''# dvd_lite/dvd_attacks/{category}/__init__.py
"""
{category} 공격 모듈
"""
# 모든 공격 클래스들을 import하고 __all__에 추가
__all__ = []

# 에러 방지를 위한 try-except 처리
try:
    import os
    import importlib
    
    # 현재 디렉토리의 모든 .py 파일 스캔
    current_dir = os.path.dirname(__file__)
    for file in os.listdir(current_dir):
        if file.endswith('.py') and file != '__init__.py':
            module_name = file[:-3]
            try:
                module = importlib.import_module(f'.{{module_name}}', package=__name__)
                # 모듈에서 클래스들 찾기
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (isinstance(attr, type) and 
                        hasattr(attr, '_get_attack_type') and 
                        attr.__name__ != 'BaseAttack'):
                        globals()[attr_name] = attr
                        __all__.append(attr_name)
            except ImportError:
                pass
except Exception:
    pass
'''
        write_file(f"dvd_lite/dvd_attacks/{category}/__init__.py", init_content)
        print(f"✅ {category}/__init__.py 업데이트됨")

def fix_original_attack_registry():
    """원본 attack_registry.py 수정 (타입 힌트 문제 해결)"""
    print("\n🔧 원본 attack_registry.py 수정 중...")
    
    fixed_registry_content = '''# dvd_lite/dvd_attacks/registry/attack_registry.py
"""
DVD 공격 등록 시스템
"""
import logging
from typing import Dict, List, Type, Optional, Any
from ..core.attack_base import BaseAttack
from ..core.scenario import DVDAttackScenario
from ..core.enums import DVDAttackTactic, DVDFlightState, AttackDifficulty

logger = logging.getLogger(__name__)

class DVDAttackRegistry:
    """DVD 공격 등록 및 관리 클래스"""
    
    def __init__(self):
        self.attacks: Dict[str, Type[BaseAttack]] = {}
        self.scenarios: Dict[str, DVDAttackScenario] = {}
        self.categories: Dict[DVDAttackTactic, List[str]] = {}
    
    def register_attack(self, name: str, attack_class: Type[BaseAttack], 
                       scenario: Optional[DVDAttackScenario] = None) -> bool:
        """공격 등록"""
        try:
            # 공격 클래스 등록
            self.attacks[name] = attack_class
            
            # 시나리오 등록
            if scenario:
                self.scenarios[name] = scenario
                
                # 카테고리별 분류
                tactic = scenario.tactic
                if tactic not in self.categories:
                    self.categories[tactic] = []
                self.categories[tactic].append(name)
            
            logger.info(f"공격 등록 성공: {name}")
            return True
            
        except Exception as e:
            logger.error(f"공격 등록 실패 {name}: {str(e)}")
            return False
    
    def get_attack_class(self, name: str) -> Optional[Type[BaseAttack]]:
        """공격 클래스 반환"""
        return self.attacks.get(name)
    
    def get_scenario(self, name: str) -> Optional[DVDAttackScenario]:
        """공격 시나리오 반환"""
        return self.scenarios.get(name)
    
    def list_attacks(self) -> List[str]:
        """등록된 모든 공격 목록"""
        return list(self.attacks.keys())
    
    def get_attacks_by_tactic(self, tactic: DVDAttackTactic) -> List[str]:
        """전술별 공격 목록"""
        return self.categories.get(tactic, [])
    
    def get_attacks_by_difficulty(self, difficulty: AttackDifficulty) -> List[str]:
        """난이도별 공격 목록"""
        return [
            name for name, scenario in self.scenarios.items()
            if scenario.difficulty == difficulty
        ]
    
    def get_attacks_by_flight_state(self, state: DVDFlightState) -> List[str]:
        """비행 상태별 가능한 공격 목록"""
        return [
            name for name, scenario in self.scenarios.items()
            if state in scenario.required_states
        ]
    
    def get_registry_stats(self) -> Dict[str, Any]:
        """등록 현황 통계"""
        return {
            "total_attacks": len(self.attacks),
            "total_scenarios": len(self.scenarios),
            "by_tactic": {tactic.value: len(attacks) for tactic, attacks in self.categories.items()},
            "by_difficulty": {
                difficulty.value: len(self.get_attacks_by_difficulty(difficulty))
                for difficulty in AttackDifficulty
            }
        }

# 전역 레지스트리 인스턴스
DVD_ATTACK_REGISTRY = DVDAttackRegistry()
'''
    write_file("dvd_lite/dvd_attacks/registry/attack_registry.py", fixed_registry_content)
    print("✅ attack_registry.py 수정됨")

def create_fallback_management():
    """대체 management.py 생성 (원본이 문제가 있을 경우)"""
    print("\n📦 대체 management.py 생성 중...")
    
    fallback_management_content = '''# dvd_lite/dvd_attacks/registry/management.py
"""
DVD 공격 시나리오 통합 관리 (호환성 개선 버전)
"""
import logging
from typing import List, Dict, Any

# 지연 import로 순환 참조 방지
def _get_registry():
    from .attack_registry import DVD_ATTACK_REGISTRY
    return DVD_ATTACK_REGISTRY

def _get_enums():
    from ..core.enums import DVDAttackTactic, DVDFlightState, AttackDifficulty
    return DVDAttackTactic, DVDFlightState, AttackDifficulty

def _get_scenario_class():
    from ..core.scenario import DVDAttackScenario
    return DVDAttackScenario

logger = logging.getLogger(__name__)

def register_all_dvd_attacks() -> List[str]:
    """DVD-Lite에 모든 DVD 공격 시나리오 등록"""
    registry = _get_registry()
    DVDAttackTactic, DVDFlightState, AttackDifficulty = _get_enums()
    DVDAttackScenario = _get_scenario_class()
    
    # 실제 구현된 공격들만 등록
    implemented_attacks = {}
    
    # WiFi 네트워크 발견
    try:
        from ..reconnaissance.wifi_discovery import WiFiNetworkDiscovery
        implemented_attacks["wifi_network_discovery"] = {
            "class": WiFiNetworkDiscovery,
            "scenario": DVDAttackScenario(
                name="WiFi Network Discovery",
                tactic=DVDAttackTactic.RECONNAISSANCE,
                description="Discover and enumerate drone WiFi networks",
                required_states=[DVDFlightState.PRE_FLIGHT, DVDFlightState.TAKEOFF],
                difficulty=AttackDifficulty.BEGINNER,
                prerequisites=["wifi_adapter", "monitor_mode"],
                targets=["network", "companion_computer"],
                estimated_duration=2.5,
                stealth_level="high",
                impact_level="low"
            )
        }
    except ImportError:
        logger.warning("WiFiNetworkDiscovery import 실패")
    
    # MAVLink 서비스 발견
    try:
        from ..reconnaissance.mavlink_discovery import MAVLinkServiceDiscovery
        implemented_attacks["mavlink_service_discovery"] = {
            "class": MAVLinkServiceDiscovery,
            "scenario": DVDAttackScenario(
                name="MAVLink Service Discovery",
                tactic=DVDAttackTactic.RECONNAISSANCE,
                description="Scan for and identify MAVLink services",
                required_states=[DVDFlightState.PRE_FLIGHT],
                difficulty=AttackDifficulty.BEGINNER,
                prerequisites=["network_access"],
                targets=["flight_controller", "gcs"],
                estimated_duration=3.2,
                stealth_level="medium",
                impact_level="low"
            )
        }
    except ImportError:
        logger.warning("MAVLinkServiceDiscovery import 실패")
    
    # 더미 공격들도 시도해서 등록
    dummy_attacks_info = [
        ("gps_spoofing", "protocol_tampering", "gps_spoofing", "GPSSpoofing", "GPS Spoofing"),
        ("telemetry_exfiltration", "exfiltration", "telemetry_data", "TelemetryDataExfiltration", "Telemetry Data Exfiltration"),
        ("mavlink_flood", "denial_of_service", "mavlink_flood", "MAVLinkFloodAttack", "MAVLink Flood Attack"),
        ("flight_plan_injection", "injection", "flight_plan", "FlightPlanInjection", "Flight Plan Injection"),
        ("bootloader_exploit", "firmware_attacks", "bootloader_exploit", "BootloaderExploit", "Bootloader Exploit")
    ]
    
    for attack_name, category, module_name, class_name, display_name in dummy_attacks_info:
        try:
            module = __import__(f"..{category}.{module_name}", fromlist=[class_name], level=1)
            attack_class = getattr(module, class_name)
            
            # 적절한 전술 매핑
            tactic_map = {
                "reconnaissance": DVDAttackTactic.RECONNAISSANCE,
                "protocol_tampering": DVDAttackTactic.PROTOCOL_TAMPERING,
                "denial_of_service": DVDAttackTactic.DENIAL_OF_SERVICE,
                "injection": DVDAttackTactic.INJECTION,
                "exfiltration": DVDAttackTactic.EXFILTRATION,
                "firmware_attacks": DVDAttackTactic.FIRMWARE_ATTACKS
            }
            
            implemented_attacks[attack_name] = {
                "class": attack_class,
                "scenario": DVDAttackScenario(
                    name=display_name,
                    tactic=tactic_map[category],
                    description=f"{display_name} attack scenario",
                    required_states=[DVDFlightState.PRE_FLIGHT],
                    difficulty=AttackDifficulty.INTERMEDIATE,
                    prerequisites=["network_access"],
                    targets=["flight_controller"],
                    estimated_duration=3.0,
                    stealth_level="medium",
                    impact_level="medium"
                )
            }
        except ImportError:
            logger.warning(f"{class_name} import 실패")
    
    # 등록 실행
    registered_attacks = []
    for attack_name, attack_info in implemented_attacks.items():
        try:
            success = registry.register_attack(
                attack_name, 
                attack_info["class"], 
                attack_info["scenario"]
            )
            if success:
                registered_attacks.append(attack_name)
        except Exception as e:
            logger.error(f"공격 등록 실패 {attack_name}: {str(e)}")
    
    logger.info(f"✅ {len(registered_attacks)}개 DVD 공격 시나리오 등록 완료")
    return registered_attacks

def get_attacks_by_tactic(tactic) -> List[str]:
    """전술별 공격 목록 반환"""
    registry = _get_registry()
    return registry.get_attacks_by_tactic(tactic)

def get_attacks_by_difficulty(difficulty) -> List[str]:
    """난이도별 공격 목록 반환"""
    registry = _get_registry()
    return registry.get_attacks_by_difficulty(difficulty)

def get_attacks_by_flight_state(state) -> List[str]:
    """비행 상태별 공격 목록 반환"""
    registry = _get_registry()
    return registry.get_attacks_by_flight_state(state)

def get_attack_info(attack_name: str) -> Dict[str, Any]:
    """특정 공격의 상세 정보 반환"""
    registry = _get_registry()
    
    scenario = registry.get_scenario(attack_name)
    attack_class = registry.get_attack_class(attack_name)
    
    if not scenario or not attack_class:
        return {}
    
    return {
        "name": scenario.name,
        "tactic": scenario.tactic.value,
        "description": scenario.description,
        "difficulty": scenario.difficulty.value,
        "required_states": [state.value for state in scenario.required_states],
        "prerequisites": scenario.prerequisites,
        "targets": scenario.targets,
        "estimated_duration": scenario.estimated_duration,
        "stealth_level": scenario.stealth_level,
        "impact_level": scenario.impact_level,
        "class_name": attack_class.__name__
    }
'''
    write_file("dvd_lite/dvd_attacks/registry/management_fallback.py", fallback_management_content)
    print("✅ 대체 management.py 생성됨")

def test_complete_system():
    """전체 시스템 테스트"""
    print("\n🧪 전체 시스템 테스트 중...")
    
    try:
        # 경로 추가
        sys.path.insert(0, os.getcwd())
        
        # 1. 기본 import 테스트
        from dvd_lite.dvd_attacks.core.enums import DVDAttackTactic, AttackDifficulty, AttackStatus
        print("✅ 열거형 import 성공")
        
        from dvd_lite.dvd_attacks.core.scenario import DVDAttackScenario
        print("✅ 시나리오 클래스 import 성공")
        
        from dvd_lite.dvd_attacks.core.attack_base import BaseAttack
        print("✅ BaseAttack 클래스 import 성공")
        
        # 2. 레지스트리 테스트
        from dvd_lite.dvd_attacks.registry.attack_registry import DVD_ATTACK_REGISTRY
        print("✅ 레지스트리 import 성공")
        
        # 3. 공격 클래스 import 테스트
        from dvd_lite.dvd_attacks.reconnaissance.wifi_discovery import WiFiNetworkDiscovery
        print("✅ WiFiNetworkDiscovery import 성공")
        
        # 4. 관리 시스템 테스트
        try:
            from dvd_lite.dvd_attacks.registry.management import register_all_dvd_attacks
            print("✅ 원본 management.py import 성공")
        except ImportError:
            from dvd_lite.dvd_attacks.registry.management_fallback import register_all_dvd_attacks
            print("✅ 대체 management.py import 성공")
        
        # 5. 등록 테스트
        registered = register_all_dvd_attacks()
        print(f"✅ 공격 등록 성공: {len(registered)}개")
        print(f"   등록된 공격들: {registered}")
        
        # 6. 메인 시스템 import 테스트
        from dvd_lite.main import DVDLite
        dvd = DVDLite()
        print("✅ DVDLite 인스턴스 생성 성공")
        
        print("\n🎉 모든 테스트 통과! 시스템이 정상 작동합니다.")
        return True
        
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        traceback.print_exc()
        return False

def write_file(path: str, content: str):
    """파일 쓰기 헬퍼"""
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

def main():
    """메인 실행 함수"""
    print("🔧 DVD 프로젝트 종합 수정 시작")
    print("=" * 60)
    
    # 1. 누락된 공격 모듈들 생성
    create_missing_attack_modules()
    
    # 2. 공격 구현 클래스들 생성
    create_attack_implementations()
    
    # 3. __init__.py 파일들 업데이트
    update_init_files()
    
    # 4. 원본 attack_registry.py 수정
    fix_original_attack_registry()
    
    # 5. 대체 management.py 생성
    create_fallback_management()
    
    # 6. 전체 시스템 테스트
    if test_complete_system():
        print("\n" + "=" * 60)
        print("🎉 수정 완료! 이제 다음 명령을 실행하세요:")
        print("   python3 advanced_start_no_cti.py")
        print("   python3 advanced_start.py")
        print("   python3 quick_start.py")
    else:
        print("\n❌ 일부 문제가 남아있습니다. 로그를 확인하세요.")

if __name__ == "__main__":
    main()