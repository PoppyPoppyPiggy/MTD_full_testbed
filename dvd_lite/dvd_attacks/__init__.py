# =============================================================================
# 메인 패키지 초기화
# =============================================================================

# dvd_attacks/__init__.py
"""
DVD 공격 시나리오 통합 패키지
Damn Vulnerable Drone에 대한 포괄적인 보안 테스트 시나리오들
"""

# 핵심 컴포넌트
from .core import (
    AttackType, DVDAttackTactic, DVDFlightState,
    AttackDifficulty, AttackStatus, DVDAttackScenario,
    BaseAttack, AttackResult
)

# 공격 카테고리별 모듈
from .reconnaissance import *
from .protocol_tampering import *
from .denial_of_service import *
from .injection import *
from .exfiltration import *
from .firmware_attacks import *

# 등록 및 관리 시스템
from .registry import (
    DVD_ATTACK_REGISTRY, register_all_dvd_attacks,
    get_attacks_by_tactic, get_attacks_by_difficulty,
    get_attacks_by_flight_state, get_attack_info
)

# 유틸리티
from .utils import *

__version__ = "1.0.0"
__author__ = "DVD Research Team"
__description__ = "Comprehensive DVD Attack Scenarios for Drone Security Testing"

__all__ = [
    # 핵심 타입 및 클래스
    'AttackType', 'DVDAttackTactic', 'DVDFlightState',
    'AttackDifficulty', 'AttackStatus', 'DVDAttackScenario', 
    'BaseAttack', 'AttackResult',
    
    # 등록 시스템
    'DVD_ATTACK_REGISTRY', 'register_all_dvd_attacks',
    'get_attacks_by_tactic', 'get_attacks_by_difficulty',
    'get_attacks_by_flight_state', 'get_attack_info',
    
    # 정찰 공격
    'WiFiNetworkDiscovery', 'MAVLinkServiceDiscovery',
    'DroneComponentEnumeration', 'CameraStreamDiscovery',
    
    # 프로토콜 변조
    'GPSSpoofing', 'MAVLinkPacketInjection', 'RadioFrequencyJamming',
    
    # 서비스 거부
    'MAVLinkFloodAttack', 'WiFiDeauthenticationAttack', 
    'CompanionComputerResourceExhaustion',
    
    # 주입 공격
    'FlightPlanInjection', 'ParameterManipulation', 
    'FirmwareUploadManipulation',
    
    # 데이터 탈취
    'TelemetryDataExfiltration', 'FlightLogExtraction', 
    'VideoStreamHijacking',
    
    # 펌웨어 공격
    'BootloaderExploit', 'FirmwareRollbackAttack', 'SecureBootBypass',
    
    # 유틸리티
    'generate_fake_mac_address', 'generate_fake_ip_address',
    'simulate_network_delay', 'async_network_delay',
    'calculate_success_probability', 'generate_ioc_id',
    'format_duration', 'classify_risk_level'
]