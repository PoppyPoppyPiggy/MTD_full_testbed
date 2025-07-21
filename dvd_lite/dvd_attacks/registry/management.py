# dvd_lite/dvd_attacks/registry/management.py
"""
DVD 공격 시나리오 통합 관리 (Damn Vulnerable Drone 기반 업데이트)
"""
import logging
from typing import List, Dict, Any
from .attack_registry import DVD_ATTACK_REGISTRY
from ..core.scenario import DVDAttackScenario
from ..core.enums import DVDAttackTactic, DVDFlightState, AttackDifficulty

# 모든 공격 모듈 import
from ..reconnaissance import (
    WiFiNetworkDiscovery, MAVLinkServiceDiscovery, 
    DroneComponentEnumeration, CameraStreamDiscovery
)
from ..protocol_tampering import (
    GPSSpoofing, MAVLinkPacketInjection, RadioFrequencyJamming
)
from ..denial_of_service import (
    MAVLinkFloodAttack, WiFiDeauthenticationAttack, 
    CompanionComputerResourceExhaustion
)
from ..injection import (
    FlightPlanInjection, ParameterManipulation, 
    FirmwareUploadManipulation, MAVLinkMessageInjection
)
from ..exfiltration import (
    TelemetryDataExfiltration, FlightLogExtraction, VideoStreamHijacking
)
from ..firmware_attacks import (
    BootloaderExploit, FirmwareRollbackAttack, SecureBootBypass
)

logger = logging.getLogger(__name__)

# DVD 공격 시나리오 정의 (Damn Vulnerable Drone Wiki 기반)
DVD_ATTACK_SCENARIOS = {
    # =================================================================
    # RECONNAISSANCE (정찰 공격들)
    # =================================================================
    "wifi_network_discovery": {
        "class": WiFiNetworkDiscovery,
        "scenario": DVDAttackScenario(
            name="WiFi Network Discovery",
            tactic=DVDAttackTactic.RECONNAISSANCE,
            description="Discover and enumerate drone WiFi networks including the DVD environment",
            required_states=[DVDFlightState.PRE_FLIGHT, DVDFlightState.TAKEOFF, DVDFlightState.AUTOPILOT_FLIGHT],
            difficulty=AttackDifficulty.BEGINNER,
            prerequisites=["wifi_adapter", "monitor_mode"],
            targets=["network", "companion_computer"],
            estimated_duration=2.5,
            stealth_level="high",
            impact_level="low"
        )
    },
    "mavlink_service_discovery": {
        "class": MAVLinkServiceDiscovery,
        "scenario": DVDAttackScenario(
            name="MAVLink Service Discovery",
            tactic=DVDAttackTactic.RECONNAISSANCE,
            description="Scan for and identify MAVLink services in DVD environment",
            required_states=[DVDFlightState.PRE_FLIGHT, DVDFlightState.AUTOPILOT_FLIGHT],
            difficulty=AttackDifficulty.BEGINNER,
            prerequisites=["network_access"],
            targets=["flight_controller", "gcs", "companion_computer"],
            estimated_duration=3.2,
            stealth_level="medium",
            impact_level="low"
        )
    },
    "drone_component_enumeration": {
        "class": DroneComponentEnumeration,
        "scenario": DVDAttackScenario(
            name="Drone Component Enumeration",
            tactic=DVDAttackTactic.RECONNAISSANCE,
            description="Identify and catalog drone system components including autopilot details",
            required_states=list(DVDFlightState),
            difficulty=AttackDifficulty.INTERMEDIATE,
            prerequisites=["network_access", "scanning_tools"],
            targets=["flight_controller", "companion_computer", "gcs"],
            estimated_duration=4.1,
            stealth_level="medium",
            impact_level="medium"
        )
    },
    "camera_stream_discovery": {
        "class": CameraStreamDiscovery,
        "scenario": DVDAttackScenario(
            name="Camera Stream Discovery & Hijacking",
            tactic=DVDAttackTactic.RECONNAISSANCE,
            description="Locate, access and potentially hijack video streams from drone cameras",
            required_states=[DVDFlightState.TAKEOFF, DVDFlightState.AUTOPILOT_FLIGHT],
            difficulty=AttackDifficulty.BEGINNER,
            prerequisites=["network_access"],
            targets=["companion_computer", "camera_system"],
            estimated_duration=2.8,
            stealth_level="high",
            impact_level="high"
        )
    },
    
    # =================================================================
    # PROTOCOL TAMPERING (프로토콜 변조 공격들)
    # =================================================================
    "gps_spoofing": {
        "class": GPSSpoofing,
        "scenario": DVDAttackScenario(
            name="GPS Signal Spoofing",
            tactic=DVDAttackTactic.PROTOCOL_TAMPERING,
            description="Manipulate GPS signals to alter drone position with sophisticated trajectory control",
            required_states=[DVDFlightState.AUTOPILOT_FLIGHT],
            difficulty=AttackDifficulty.ADVANCED,
            prerequisites=["sdr_equipment", "gps_knowledge", "signal_analysis"],
            targets=["flight_controller", "navigation_system"],
            estimated_duration=4.2,
            stealth_level="high",
            impact_level="critical"
        )
    },
    "mavlink_packet_injection": {
        "class": MAVLinkPacketInjection,
        "scenario": DVDAttackScenario(
            name="MAVLink Packet Injection",
            tactic=DVDAttackTactic.PROTOCOL_TAMPERING,
            description="Inject malicious MAVLink messages to control drone behavior",
            required_states=[DVDFlightState.AUTOPILOT_FLIGHT, DVDFlightState.MANUAL_FLIGHT],
            difficulty=AttackDifficulty.INTERMEDIATE,
            prerequisites=["mavlink_knowledge", "packet_crafting"],
            targets=["flight_controller", "gcs"],
            estimated_duration=3.5,
            stealth_level="medium",
            impact_level="high"
        )
    },
    "mavlink_message_injection": {
        "class": MAVLinkMessageInjection,
        "scenario": DVDAttackScenario(
            name="Advanced MAVLink Message Injection",
            tactic=DVDAttackTactic.INJECTION,
            description="Comprehensive MAVLink command injection with chain attack capabilities",
            required_states=[DVDFlightState.STANDBY, DVDFlightState.ARMED, DVDFlightState.AUTOPILOT_FLIGHT],
            difficulty=AttackDifficulty.ADVANCED,
            prerequisites=["mavlink_protocol", "network_access", "flight_controller_knowledge"],
            targets=["flight_controller", "autopilot"],
            estimated_duration=3.5,
            stealth_level="low",
            impact_level="critical"
        )
    },
    "rf_jamming": {
        "class": RadioFrequencyJamming,
        "scenario": DVDAttackScenario(
            name="Radio Frequency Jamming",
            tactic=DVDAttackTactic.PROTOCOL_TAMPERING,
            description="Disrupt drone communications via targeted RF interference",
            required_states=list(DVDFlightState),
            difficulty=AttackDifficulty.INTERMEDIATE,
            prerequisites=["rf_equipment", "frequency_knowledge"],
            targets=["network", "flight_controller", "gcs", "communication_links"],
            estimated_duration=3.8,
            stealth_level="low",
            impact_level="high"
        )
    },
    
    # =================================================================
    # DENIAL OF SERVICE (서비스 거부 공격들)
    # =================================================================
    "mavlink_flood": {
        "class": MAVLinkFloodAttack,
        "scenario": DVDAttackScenario(
            name="MAVLink Flood Attack",
            tactic=DVDAttackTactic.DENIAL_OF_SERVICE,
            description="Overwhelm MAVLink services with excessive traffic to cause DoS",
            required_states=list(DVDFlightState),
            difficulty=AttackDifficulty.BEGINNER,
            prerequisites=["network_access"],
            targets=["flight_controller", "gcs", "mavlink_router"],
            estimated_duration=2.5,
            stealth_level="low",
            impact_level="high"
        )
    },
    "wifi_deauth": {
        "class": WiFiDeauthenticationAttack,
        "scenario": DVDAttackScenario(
            name="WiFi Deauthentication Attack",
            tactic=DVDAttackTactic.DENIAL_OF_SERVICE,
            description="Force disconnect WiFi clients from drone networks using deauth frames",
            required_states=list(DVDFlightState),
            difficulty=AttackDifficulty.BEGINNER,
            prerequisites=["wifi_adapter", "monitor_mode"],
            targets=["network", "companion_computer", "wifi_infrastructure"],
            estimated_duration=3.1,
            stealth_level="medium",
            impact_level="medium"
        )
    },
    "resource_exhaustion": {
        "class": CompanionComputerResourceExhaustion,
        "scenario": DVDAttackScenario(
            name="Companion Computer Resource Exhaustion",
            tactic=DVDAttackTactic.DENIAL_OF_SERVICE,
            description="Exhaust companion computer system resources causing service disruption",
            required_states=list(DVDFlightState),
            difficulty=AttackDifficulty.INTERMEDIATE,
            prerequisites=["system_access", "scripting"],
            targets=["companion_computer"],
            estimated_duration=4.5,
            stealth_level="medium",
            impact_level="high"
        )
    },
    
    # =================================================================
    # INJECTION (주입 공격들)  
    # =================================================================
    "flight_plan_injection": {
        "class": FlightPlanInjection,
        "scenario": DVDAttackScenario(
            name="Flight Plan Injection",
            tactic=DVDAttackTactic.INJECTION,
            description="Inject malicious waypoints into flight plans to redirect missions",
            required_states=[DVDFlightState.PRE_FLIGHT, DVDFlightState.AUTOPILOT_FLIGHT],
            difficulty=AttackDifficulty.INTERMEDIATE,
            prerequisites=["mavlink_access", "mission_planning"],
            targets=["flight_controller", "gcs", "mission_planner"],
            estimated_duration=3.7,
            stealth_level="medium",
            impact_level="critical"
        )
    },
    "parameter_manipulation": {
        "class": ParameterManipulation,
        "scenario": DVDAttackScenario(
            name="Parameter Manipulation",
            tactic=DVDAttackTactic.INJECTION,
            description="Modify critical system parameters to compromise flight safety",
            required_states=[DVDFlightState.PRE_FLIGHT],
            difficulty=AttackDifficulty.ADVANCED,
            prerequisites=["parameter_access", "system_knowledge"],
            targets=["flight_controller", "autopilot"],
            estimated_duration=4.2,
            stealth_level="high",
            impact_level="critical"
        )
    },
    "firmware_upload_manipulation": {
        "class": FirmwareUploadManipulation,
        "scenario": DVDAttackScenario(
            name="Firmware Upload Manipulation",
            tactic=DVDAttackTactic.INJECTION,
            description="Inject malicious code during firmware update process",
            required_states=[DVDFlightState.PRE_FLIGHT, DVDFlightState.POST_FLIGHT],
            difficulty=AttackDifficulty.ADVANCED,
            prerequisites=["firmware_access", "binary_analysis"],
            targets=["flight_controller", "bootloader"],
            estimated_duration=5.5,
            stealth_level="high",
            impact_level="critical"
        )
    },
    
    # =================================================================
    # EXFILTRATION (데이터 탈취 공격들)
    # =================================================================
    "telemetry_exfiltration": {
        "class": TelemetryDataExfiltration,
        "scenario": DVDAttackScenario(
            name="Telemetry Data Exfiltration",
            tactic=DVDAttackTactic.EXFILTRATION,
            description="Extract sensitive telemetry and operational data from drone systems",
            required_states=list(DVDFlightState),
            difficulty=AttackDifficulty.INTERMEDIATE,
            prerequisites=["network_access", "data_analysis"],
            targets=["flight_controller", "companion_computer", "gcs", "telemetry_system"],
            estimated_duration=3.9,
            stealth_level="high",
            impact_level="high"
        )
    },
    "flight_log_extraction": {
        "class": FlightLogExtraction,
        "scenario": DVDAttackScenario(
            name="Flight Log Extraction",
            tactic=DVDAttackTactic.EXFILTRATION,
            description="Extract flight logs and historical operational data",
            required_states=[DVDFlightState.POST_FLIGHT, DVDFlightState.PRE_FLIGHT],
            difficulty=AttackDifficulty.BEGINNER,
            prerequisites=["file_access"],
            targets=["flight_controller", "companion_computer", "storage_systems"],
            estimated_duration=4.8,
            stealth_level="medium",
            impact_level="medium"
        )
    },
    "video_stream_hijacking": {
        "class": VideoStreamHijacking,
        "scenario": DVDAttackScenario(
            name="Video Stream Hijacking",
            tactic=DVDAttackTactic.EXFILTRATION,
            description="Intercept and manipulate real-time video feeds with control capabilities",
            required_states=[DVDFlightState.TAKEOFF, DVDFlightState.AUTOPILOT_FLIGHT],
            difficulty=AttackDifficulty.INTERMEDIATE,
            prerequisites=["network_access", "video_tools"],
            targets=["companion_computer", "camera_system", "video_streams"],
            estimated_duration=3.4,
            stealth_level="medium",
            impact_level="high"
        )
    },
    
    # =================================================================
    # FIRMWARE ATTACKS (펌웨어 공격들)
    # =================================================================
    "bootloader_exploit": {
        "class": BootloaderExploit,
        "scenario": DVDAttackScenario(
            name="Bootloader Exploit",
            tactic=DVDAttackTactic.FIRMWARE_ATTACKS,
            description="Exploit bootloader vulnerabilities for persistent system compromise",
            required_states=[DVDFlightState.PRE_FLIGHT, DVDFlightState.POST_FLIGHT],
            difficulty=AttackDifficulty.ADVANCED,
            prerequisites=["physical_access", "hardware_tools", "firmware_analysis"],
            targets=["flight_controller", "bootloader"],
            estimated_duration=6.2,
            stealth_level="high",
            impact_level="critical"
        )
    },
    "firmware_rollback": {
        "class": FirmwareRollbackAttack,
        "scenario": DVDAttackScenario(
            name="Firmware Rollback Attack",
            tactic=DVDAttackTactic.FIRMWARE_ATTACKS,
            description="Downgrade to vulnerable firmware versions for exploitation",
            required_states=[DVDFlightState.PRE_FLIGHT, DVDFlightState.POST_FLIGHT],
            difficulty=AttackDifficulty.ADVANCED,
            prerequisites=["firmware_access", "vulnerability_database"],
            targets=["flight_controller", "firmware_system"],
            estimated_duration=4.7,
            stealth_level="medium",
            impact_level="critical"
        )
    },
    "secure_boot_bypass": {
        "class": SecureBootBypass,
        "scenario": DVDAttackScenario(
            name="Secure Boot Bypass",
            tactic=DVDAttackTactic.FIRMWARE_ATTACKS,
            description="Bypass secure boot mechanisms to load unauthorized firmware",
            required_states=[DVDFlightState.PRE_FLIGHT],
            difficulty=AttackDifficulty.ADVANCED,
            prerequisites=["hardware_access", "cryptographic_tools", "boot_analysis"],
            targets=["flight_controller", "secure_boot"],
            estimated_duration=5.8,
            stealth_level="high",
            impact_level="critical"
        )
    }
}

def register_all_dvd_attacks() -> List[str]:
    """DVD-Lite에 모든 DVD 공격 시나리오 등록"""
    registered_attacks = []
    
    for attack_name, attack_info in DVD_ATTACK_SCENARIOS.items():
        try:
            success = DVD_ATTACK_REGISTRY.register_attack(
                attack_name, 
                attack_info["class"], 
                attack_info["scenario"]
            )
            if success:
                registered_attacks.append(attack_name)
                logger.info(f"✅ 등록 성공: {attack_name}")
        except Exception as e:
            logger.error(f"❌ 공격 등록 실패 {attack_name}: {str(e)}")
    
    logger.info(f"🎯 총 {len(registered_attacks)}개 DVD 공격 시나리오 등록 완료")
    return registered_attacks

def get_attacks_by_tactic(tactic: DVDAttackTactic) -> List[str]:
    """전술별 공격 목록 반환"""
    return DVD_ATTACK_REGISTRY.get_attacks_by_tactic(tactic)

def get_attacks_by_difficulty(difficulty: AttackDifficulty) -> List[str]:
    """난이도별 공격 목록 반환"""
    return DVD_ATTACK_REGISTRY.get_attacks_by_difficulty(difficulty)

def get_attacks_by_flight_state(state: DVDFlightState) -> List[str]:
    """비행 상태별 가능한 공격 목록 반환"""
    return DVD_ATTACK_REGISTRY.get_attacks_by_flight_state(state)

def get_attacks_by_target(target: str) -> List[str]:
    """타겟별 공격 목록 반환"""
    matching_attacks = []
    for attack_name, attack_info in DVD_ATTACK_SCENARIOS.items():
        if target in attack_info["scenario"].targets:
            matching_attacks.append(attack_name)
    return matching_attacks

def get_attack_info(attack_name: str) -> Dict[str, Any]:
    """특정 공격의 상세 정보 반환"""
    scenario = DVD_ATTACK_REGISTRY.get_scenario(attack_name)
    attack_class = DVD_ATTACK_REGISTRY.get_attack_class(attack_name)
    
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

def list_all_attacks() -> List[str]:
    """등록된 모든 공격 목록 반환"""
    return list(DVD_ATTACK_SCENARIOS.keys())

def get_attack_statistics() -> Dict[str, Any]:
    """공격 통계 정보 반환"""
    stats = {
        "total_attacks": len(DVD_ATTACK_SCENARIOS),
        "by_tactic": {},
        "by_difficulty": {},
        "by_impact_level": {},
        "by_target": {}
    }
    
    for attack_info in DVD_ATTACK_SCENARIOS.values():
        scenario = attack_info["scenario"]
        
        # 전술별 통계
        tactic = scenario.tactic.value
        stats["by_tactic"][tactic] = stats["by_tactic"].get(tactic, 0) + 1
        
        # 난이도별 통계
        difficulty = scenario.difficulty.value
        stats["by_difficulty"][difficulty] = stats["by_difficulty"].get(difficulty, 0) + 1
        
        # 영향도별 통계
        impact = scenario.impact_level
        stats["by_impact_level"][impact] = stats["by_impact_level"].get(impact, 0) + 1
        
        # 타겟별 통계
        for target in scenario.targets:
            stats["by_target"][target] = stats["by_target"].get(target, 0) + 1
    
    return stats

def get_recommended_attack_sequence(target_environment: str = "dvd") -> List[str]:
    """권장 공격 시퀀스 반환"""
    if target_environment.lower() == "dvd":
        return [
            "wifi_network_discovery",           # 1. 네트워크 정찰
            "mavlink_service_discovery",        # 2. MAVLink 서비스 발견  
            "camera_stream_discovery",          # 3. 카메라 스트림 발견
            "telemetry_exfiltration",          # 4. 텔레메트리 데이터 수집
            "parameter_manipulation",           # 5. 파라미터 조작
            "mavlink_message_injection",        # 6. MAVLink 메시지 주입
            "gps_spoofing"                      # 7. GPS 스푸핑 (최종 공격)
        ]
    else:
        # 일반 드론 환경
        return [
            "wifi_network_discovery",
            "drone_component_enumeration", 
            "mavlink_service_discovery",
            "flight_log_extraction",
            "parameter_manipulation"
        ]

def get_beginner_friendly_attacks() -> List[str]:
    """초보자용 공격 목록 반환"""
    return get_attacks_by_difficulty(AttackDifficulty.BEGINNER)

def get_advanced_attacks() -> List[str]:
    """고급 공격 목록 반환"""
    return get_attacks_by_difficulty(AttackDifficulty.ADVANCED)

def get_high_impact_attacks() -> List[str]:
    """고영향도 공격 목록 반환"""
    high_impact_attacks = []
    for attack_name, attack_info in DVD_ATTACK_SCENARIOS.items():
        if attack_info["scenario"].impact_level in ["high", "critical"]:
            high_impact_attacks.append(attack_name)
    return high_impact_attacks