"""
DVD 전체 공격 시나리오 통합 파일
기존 2000줄 코드를 모듈화한 후 단일 진입점 제공
"""

# 핵심 컴포넌트 import
from .core.enums import DVDAttackTactic, DVDFlightState
from .core.scenario import DVDAttackScenario
from .core.attack_base import BaseAttack, AttackType, logger

# 정찰 공격들
from .reconnaissance.wifi_discovery import WiFiNetworkDiscovery
from .reconnaissance.mavlink_discovery import MAVLinkServiceDiscovery

# 프로토콜 조작 공격들
from .protocol_tampering.gps_spoofing import GPSSpoofing

# 데이터 탈취 공격들
from .exfiltration.telemetry_data import TelemetryDataExfiltration

# 관리 시스템
from .registry.attack_registry import DVD_ATTACK_SCENARIOS
from .registry.management import (
    register_all_dvd_attacks,
    get_attacks_by_tactic,
    get_attacks_by_difficulty,
    get_attacks_by_flight_state,
    get_attack_info,
    list_all_attacks,
    get_attacks_by_target
)

# 유틸리티
from .utils.common import *

# 하위 호환성을 위한 모든 클래스 export
__all__ = [
    # 열거형 및 데이터 클래스
    "DVDAttackTactic",
    "DVDFlightState", 
    "DVDAttackScenario",
    
    # 베이스 클래스
    "BaseAttack",
    "AttackType",
    
    # 정찰 공격
    "WiFiNetworkDiscovery",
    "MAVLinkServiceDiscovery",
    # TODO: 나머지 정찰 공격들
    # "DroneComponentEnumeration",
    # "CameraStreamDiscovery",
    
    # 프로토콜 조작 공격
    "GPSSpoofing",
    # TODO: 나머지 프로토콜 조작 공격들
    # "MAVLinkPacketInjection",
    # "RadioFrequencyJamming",
    
    # DoS 공격
    # TODO: DoS 공격들
    # "MAVLinkFloodAttack",
    # "WiFiDeauthenticationAttack", 
    # "CompanionComputerResourceExhaustion",
    
    # 주입 공격
    # TODO: 주입 공격들
    # "FlightPlanInjection",
    # "ParameterManipulation",
    # "FirmwareUploadManipulation",
    
    # 데이터 탈취 공격
    "TelemetryDataExfiltration",
    # TODO: 나머지 탈취 공격들
    # "FlightLogExtraction",
    # "VideoStreamHijacking",
    
    # 펌웨어 공격
    # TODO: 펌웨어 공격들
    # "BootloaderExploit",
    # "FirmwareRollbackAttack", 
    # "SecureBootBypass",
    
    # 관리 함수들
    "register_all_dvd_attacks",
    "get_attacks_by_tactic",
    "get_attacks_by_difficulty",
    "get_attacks_by_flight_state",
    "get_attack_info",
    "list_all_attacks",
    "get_attacks_by_target",
    
    # 레지스트리
    "DVD_ATTACK_SCENARIOS"
]

# 편의 함수 - 기존 코드와의 호환성 유지
def get_all_attack_classes():
    """모든 공격 클래스를 반환 (하위 호환성)"""
    return {name: info["class"] for name, info in DVD_ATTACK_SCENARIOS.items()}

def get_implemented_attacks():
    """현재 구현된 공격들만 반환"""
    implemented = [
        "wifi_network_discovery",
        "mavlink_service_discovery", 
        "gps_spoofing",
        "telemetry_exfiltration"
    ]
    return {name: DVD_ATTACK_SCENARIOS[name] for name in implemented if name in DVD_ATTACK_SCENARIOS}

# CTI 수집을 위한 편의 함수들
def get_cti_relevant_attacks():
    """CTI 수집에 관련된 공격들 반환"""
    cti_tactics = [
        DVDAttackTactic.RECONNAISSANCE,
        DVDAttackTactic.EXFILTRATION
    ]
    
    relevant_attacks = []
    for tactic in cti_tactics:
        relevant_attacks.extend(get_attacks_by_tactic(tactic))
    
    return relevant_attacks

def get_high_impact_attacks():
    """높은 영향도를 가진 공격들 반환"""
    high_impact_targets = ["flight_controller", "gcs"]
    high_impact_attacks = []
    
    for target in high_impact_targets:
        high_impact_attacks.extend(get_attacks_by_target(target))
    
    return list(set(high_impact_attacks))  # 중복 제거

if __name__ == "__main__":
    # 간단한 테스트
    print("=== DVD Attack Scenarios 모듈화 테스트 ===")
    print(f"구현된 공격 수: {len(get_implemented_attacks())}")
    print(f"CTI 관련 공격 수: {len(get_cti_relevant_attacks())}")
    print(f"고영향 공격 수: {len(get_high_impact_attacks())}")
    
    print("\n구현된 공격 목록:")
    for name, info in get_implemented_attacks().items():
        scenario = info["scenario"]
        print(f"- {name}: {scenario.description} ({scenario.difficulty})")