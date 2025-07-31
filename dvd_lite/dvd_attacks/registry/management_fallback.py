# dvd_lite/dvd_attacks/registry/management.py
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
