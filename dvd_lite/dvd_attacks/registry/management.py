# dvd_lite/dvd_attacks/registry/management.py
"""
DVD 공격 시나리오 통합 관리
"""
import logging
from typing import List, Dict, Any

# 안전한 import
try:
    from .attack_registry import DVD_ATTACK_REGISTRY
    from ..core.scenario import DVDAttackScenario
    from ..core.enums import DVDAttackTactic, DVDFlightState, AttackDifficulty
    CORE_AVAILABLE = True
except ImportError:
    CORE_AVAILABLE = False
    print("Warning: 핵심 레지스트리 모듈 import 실패")

# 모든 공격 모듈 import - 안전하게
attack_classes = {}

try:
    from ..reconnaissance import (
        WiFiNetworkDiscovery, MAVLinkServiceDiscovery, 
        DroneComponentEnumeration, CameraStreamDiscovery
    )
    attack_classes.update({
        'wifi_network_discovery': WiFiNetworkDiscovery,
        'mavlink_service_discovery': MAVLinkServiceDiscovery,
        'drone_component_enumeration': DroneComponentEnumeration,
        'camera_stream_discovery': CameraStreamDiscovery
    })
except ImportError as e:
    print(f"Warning: reconnaissance 모듈 import 실패: {e}")

try:
    from ..protocol_tampering import (
        GPSSpoofing, MAVLinkPacketInjection, RadioFrequencyJamming
    )
    attack_classes.update({
        'gps_spoofing': GPSSpoofing,
        'mavlink_packet_injection': MAVLinkPacketInjection,
        'radio_frequency_jamming': RadioFrequencyJamming
    })
except ImportError as e:
    print(f"Warning: protocol_tampering 모듈 import 실패: {e}")

try:
    from ..denial_of_service import (
        MAVLinkFloodAttack, WiFiDeauthenticationAttack, 
        CompanionComputerResourceExhaustion
    )
    attack_classes.update({
        'mavlink_flood': MAVLinkFloodAttack,
        'wifi_deauth': WiFiDeauthenticationAttack,
        'resource_exhaustion': CompanionComputerResourceExhaustion
    })
except ImportError as e:
    print(f"Warning: denial_of_service 모듈 import 실패: {e}")

try:
    from ..injection import (
        FlightPlanInjection, ParameterManipulation, 
        FirmwareUploadManipulation, MAVLinkMessageInjection
    )
    attack_classes.update({
        'flight_plan_injection': FlightPlanInjection,
        'parameter_manipulation': ParameterManipulation,
        'firmware_upload_manipulation': FirmwareUploadManipulation,
        'mavlink_message_injection': MAVLinkMessageInjection
    })
except ImportError as e:
    print(f"Warning: injection 모듈 import 실패: {e}")

try:
    from ..exfiltration import (
        TelemetryDataExfiltration, FlightLogExtraction, VideoStreamHijacking
    )
    attack_classes.update({
        'telemetry_exfiltration': TelemetryDataExfiltration,
        'flight_log_extraction': FlightLogExtraction,
        'video_stream_hijacking': VideoStreamHijacking
    })
except ImportError as e:
    print(f"Warning: exfiltration 모듈 import 실패: {e}")

try:
    from ..firmware_attacks import (
        BootloaderExploit, FirmwareRollbackAttack, SecureBootBypass
    )
    attack_classes.update({
        'bootloader_exploit': BootloaderExploit,
        'firmware_rollback': FirmwareRollbackAttack,
        'secure_boot_bypass': SecureBootBypass
    })
except ImportError as e:
    print(f"Warning: firmware_attacks 모듈 import 실패: {e}")

logger = logging.getLogger(__name__)

def register_all_dvd_attacks() -> List[str]:
    """DVD-Lite에 모든 DVD 공격 시나리오 등록"""
    registered_attacks = []
    
    for attack_name, attack_class in attack_classes.items():
        try:
            # 기본 DVD-Lite 레지스트리에 등록
            from dvd_lite.main import DVDLite
            
            # 전역 레지스트리가 있다면 사용
            if CORE_AVAILABLE and 'DVD_ATTACK_REGISTRY' in globals():
                # 시나리오 정보 생성 (기본값)
                scenario = create_default_scenario(attack_name, attack_class)
                success = DVD_ATTACK_REGISTRY.register_attack(
                    attack_name, attack_class, scenario
                )
                if success:
                    registered_attacks.append(attack_name)
            else:
                # 단순 등록
                registered_attacks.append(attack_name)
                
        except Exception as e:
            logger.error(f"공격 등록 실패 {attack_name}: {str(e)}")
    
    logger.info(f"✅ {len(registered_attacks)}개 DVD 공격 시나리오 등록 완료")
    return registered_attacks

def create_default_scenario(attack_name: str, attack_class):
    """기본 시나리오 생성"""
    if not CORE_AVAILABLE:
        return None
        
    # 공격 이름에서 타겟과 전술 추론
    if 'wifi' in attack_name or 'network' in attack_name:
        tactic = DVDAttackTactic.RECONNAISSANCE
        targets = ["network", "companion_computer"]
    elif 'mavlink' in attack_name and 'injection' in attack_name:
        tactic = DVDAttackTactic.INJECTION
        targets = ["flight_controller"]
    elif 'gps' in attack_name:
        tactic = DVDAttackTactic.PROTOCOL_TAMPERING
        targets = ["flight_controller"]
    elif 'flood' in attack_name or 'deauth' in attack_name:
        tactic = DVDAttackTactic.DENIAL_OF_SERVICE
        targets = ["network", "flight_controller"]
    elif 'telemetry' in attack_name or 'log' in attack_name:
        tactic = DVDAttackTactic.EXFILTRATION
        targets = ["flight_controller", "companion_computer"]
    elif 'firmware' in attack_name or 'bootloader' in attack_name:
        tactic = DVDAttackTactic.FIRMWARE_ATTACKS
        targets = ["flight_controller"]
    else:
        tactic = DVDAttackTactic.RECONNAISSANCE
        targets = ["flight_controller"]
    
    return DVDAttackScenario(
        name=attack_name.replace('_', ' ').title(),
        tactic=tactic,
        description=f"{attack_class.__name__} 공격",
        required_states=[DVDFlightState.PRE_FLIGHT, DVDFlightState.AUTOPILOT_FLIGHT],
        difficulty=AttackDifficulty.INTERMEDIATE,
        prerequisites=["network_access"],
        targets=targets,
        estimated_duration=3.0,
        stealth_level="medium",
        impact_level="medium"
    )

def get_attacks_by_tactic(tactic) -> List[str]:
    """전술별 공격 목록 반환"""
    if not CORE_AVAILABLE:
        # 기본 분류
        recon_attacks = ['wifi_network_discovery', 'mavlink_service_discovery', 'drone_component_enumeration']
        protocol_attacks = ['gps_spoofing', 'mavlink_packet_injection']
        injection_attacks = ['flight_plan_injection', 'parameter_manipulation']
        
        if hasattr(tactic, 'value'):
            tactic_value = tactic.value
        else:
            tactic_value = str(tactic).lower()
            
        if 'reconnaissance' in tactic_value:
            return [a for a in recon_attacks if a in attack_classes]
        elif 'protocol' in tactic_value:
            return [a for a in protocol_attacks if a in attack_classes]
        elif 'injection' in tactic_value:
            return [a for a in injection_attacks if a in attack_classes]
        else:
            return list(attack_classes.keys())[:3]
    
    return DVD_ATTACK_REGISTRY.get_attacks_by_tactic(tactic)

def get_attacks_by_difficulty(difficulty) -> List[str]:
    """난이도별 공격 목록 반환"""
    if not CORE_AVAILABLE:
        return list(attack_classes.keys())[:5]
    
    return DVD_ATTACK_REGISTRY.get_attacks_by_difficulty(difficulty)

def get_attacks_by_flight_state(state) -> List[str]:
    """비행 상태별 가능한 공격 목록 반환"""
    if not CORE_AVAILABLE:
        return list(attack_classes.keys())[:3]
    
    return DVD_ATTACK_REGISTRY.get_attacks_by_flight_state(state)

def get_attack_info(attack_name: str) -> Dict[str, Any]:
    """특정 공격의 상세 정보 반환"""
    if attack_name not in attack_classes:
        return {}
    
    attack_class = attack_classes[attack_name]
    
    return {
        "name": attack_name.replace('_', ' ').title(),
        "tactic": "reconnaissance",  # 기본값
        "description": f"{attack_class.__name__} 공격",
        "difficulty": "intermediate",
        "targets": ["flight_controller"],
        "estimated_duration": 3.0,
        "stealth_level": "medium",
        "impact_level": "medium",
        "class_name": attack_class.__name__
    }

# 사용 가능한 공격 목록
DVD_ATTACK_SCENARIOS = {name: {"class": cls} for name, cls in attack_classes.items()}
