# dvd_attacks/registry/management.py
"""
DVD 공격 시나리오 통합 관리
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
    FlightPlanInjection, ParameterManipulation, FirmwareUploadManipulation
)
from ..exfiltration import (
    TelemetryDataExfiltration, FlightLogExtraction, VideoStreamHijacking
)
from ..firmware_attacks import (
    BootloaderExploit, FirmwareRollbackAttack, SecureBootBypass
)

logger = logging.getLogger(__name__)

# DVD 공격 시나리오 정의
DVD_ATTACK_SCENARIOS = {
    # Reconnaissance
    "wifi_network_discovery": {
        "class": WiFiNetworkDiscovery,
        "scenario": DVDAttackScenario(
            name="WiFi Network Discovery",
            tactic=DVDAttackTactic.RECONNAISSANCE,
            description="Discover and enumerate drone WiFi networks",
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
            description="Scan for and identify MAVLink services",
            required_states=[DVDFlightState.PRE_FLIGHT, DVDFlightState.AUTOPILOT_FLIGHT],
            difficulty=AttackDifficulty.BEGINNER,
            prerequisites=["network_access"],
            targets=["flight_controller", "gcs"],
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
            description="Identify and catalog drone system components",
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
            name="Camera Stream Discovery",
            tactic=DVDAttackTactic.RECONNAISSANCE,
            description="Locate and access video streams",
            required_states=[DVDFlightState.TAKEOFF, DVDFlightState.AUTOPILOT_FLIGHT],
            difficulty=AttackDifficulty.BEGINNER,
            prerequisites=["network_access"],
            targets=["companion_computer"],
            estimated_duration=2.8,
            stealth_level="high",
            impact_level="medium"
        )
    },
    
    # Protocol Tampering
    "mavlink_packet_injection": {
        "class": MAVLinkPacketInjection,
        "scenario": DVDAttackScenario(
            name="MAVLink Packet Injection",
            tactic=DVDAttackTactic.PROTOCOL_TAMPERING,
            description="Inject malicious MAVLink messages",
            required_states=[DVDFlightState.AUTOPILOT_FLIGHT, DVDFlightState.MANUAL_FLIGHT],
            difficulty=AttackDifficulty.INTERMEDIATE,
            prerequisites=["mavlink_knowledge", "packet_crafting"],
            targets=["flight_controller"],
            estimated_duration=3.5,
            stealth_level="medium",
            impact_level="high"
        )
    },
    "gps_spoofing": {
        "class": GPSSpoofing,
        "scenario": DVDAttackScenario(
            name="GPS Spoofing",
            tactic=DVDAttackTactic.PROTOCOL_TAMPERING,
            description="Manipulate GPS signals to alter drone position",
            required_states=[DVDFlightState.AUTOPILOT_FLIGHT],
            difficulty=AttackDifficulty.ADVANCED,
            prerequisites=["sdr_equipment", "gps_knowledge"],
            targets=["flight_controller"],
            estimated_duration=4.2,
            stealth_level="high",
            impact_level="critical"
        )
    },
    "rf_jamming": {
        "class": RadioFrequencyJamming,
        "scenario": DVDAttackScenario(
            name="Radio Frequency Jamming",
            tactic=DVDAttackTactic.PROTOCOL_TAMPERING,
            description="Disrupt drone communications via RF interference",
            required_states=list(DVDFlightState),
            difficulty=AttackDifficulty.INTERMEDIATE,
            prerequisites=["rf_equipment", "frequency_knowledge"],
            targets=["network", "flight_controller", "gcs"],
            estimated_duration=3.8,
            stealth_level="low",
            impact_level="high"
        )
    },
    
    # Denial of Service
    "mavlink_flood": {
        "class": MAVLinkFloodAttack,
        "scenario": DVDAttackScenario(
            name="MAVLink Flood Attack",
            tactic=DVDAttackTactic.DENIAL_OF_SERVICE,
            description="Overwhelm MAVLink services with excessive traffic",
            required_states=list(DVDFlightState),
            difficulty=AttackDifficulty.BEGINNER,
            prerequisites=["network_access"],
            targets=["flight_controller", "gcs"],
            estimated_duration=2.5,
            stealth_level="low",
            impact_level="high"
        )
    },
    "wifi_deauth": {
        "class": WiFiDeauthenticationAttack,
        "scenario": DVDAttackScenario(
            name="WiFi Deauthentication",
            tactic=DVDAttackTactic.DENIAL_OF_SERVICE,
            description="Force disconnect WiFi clients from drone networks",
            required_states=list(DVDFlightState),
            difficulty=AttackDifficulty.BEGINNER,
            prerequisites=["wifi_adapter", "monitor_mode"],
            targets=["network", "companion_computer"],
            estimated_duration=3.1,
            stealth_level="medium",
            impact_level="medium"
        )
    },
    "resource_exhaustion": {
        "class": CompanionComputerResourceExhaustion,
        "scenario": DVDAttackScenario(
            name="Resource Exhaustion",
            tactic=DVDAttackTactic.DENIAL_OF_SERVICE,
            description="Exhaust companion computer system resources",
            required_states=list(DVDFlightState),
            difficulty=AttackDifficulty.INTERMEDIATE,
            prerequisites=["system_access", "scripting"],
            targets=["companion_computer"],
            estimated_duration=4.5,
            stealth_level="medium",
            impact_level="high"
        )
    },
    
    # Injection
    "flight_plan_injection": {
        "class": FlightPlanInjection,
        "scenario": DVDAttackScenario(
            name="Flight Plan Injection",
            tactic=DVDAttackTactic.INJECTION,
            description="Inject malicious waypoints into flight plans",
            required_states=[DVDFlightState.PRE_FLIGHT, DVDFlightState.AUTOPILOT_FLIGHT],
            difficulty=AttackDifficulty.INTERMEDIATE,
            prerequisites=["mavlink_access", "mission_planning"],
            targets=["flight_controller", "gcs"],
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
            description="Modify critical system parameters",
            required_states=[DVDFlightState.PRE_FLIGHT],
            difficulty=AttackDifficulty.ADVANCED,
            prerequisites=["parameter_access", "system_knowledge"],
            targets=["flight_controller"],
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
            description="Inject malicious code during firmware updates",
            required_states=[DVDFlightState.PRE_FLIGHT, DVDFlightState.POST_FLIGHT],
            difficulty=AttackDifficulty.ADVANCED,
            prerequisites=["firmware_access", "binary_analysis"],
            targets=["flight_controller"],
            estimated_duration=5.5,
            stealth_level="high",
            impact_level="critical"
        )
    },
    
    # Exfiltration
    "telemetry_exfiltration": {
        "class": TelemetryDataExfiltration,
        "scenario": DVDAttackScenario(
            name="Telemetry Data Exfiltration",
            tactic=DVDAttackTactic.EXFILTRATION,
            description="Extract sensitive telemetry and operational data",
            required_states=list(DVDFlightState),
            difficulty=AttackDifficulty.INTERMEDIATE,
            prerequisites=["network_access", "data_analysis"],
            targets=["flight_controller", "companion_computer", "gcs"],
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
            description="Extract flight logs and historical data",
            required_states=[DVDFlightState.POST_FLIGHT],
            difficulty=AttackDifficulty.BEGINNER,
            prerequisites=["file_access"],
            targets=["flight_controller", "companion_computer"],
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
            description="Intercept and manipulate real-time video feeds",
            required_states=[DVDFlightState.TAKEOFF, DVDFlightState.AUTOPILOT_FLIGHT],
            difficulty=AttackDifficulty.INTERMEDIATE,
            prerequisites=["network_access", "video_tools"],
            targets=["companion_computer"],
            estimated_duration=3.4,
            stealth_level="medium",
            impact_level="high"
        )
    },
    
    # Firmware Attacks
    "bootloader_exploit": {
        "class": BootloaderExploit,
        "scenario": DVDAttackScenario(
            name="Bootloader Exploit",
            tactic=DVDAttackTactic.FIRMWARE_ATTACKS,
            description="Exploit bootloader vulnerabilities for system compromise",
            required_states=[DVDFlightState.PRE_FLIGHT, DVDFlightState.POST_FLIGHT],
            difficulty=AttackDifficulty.ADVANCED,
            prerequisites=["physical_access", "hardware_tools"],
            targets=["flight_controller"],
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
            description="Downgrade to vulnerable firmware versions",
            required_states=[DVDFlightState.PRE_FLIGHT, DVDFlightState.POST_FLIGHT],
            difficulty=AttackDifficulty.ADVANCED,
            prerequisites=["firmware_access", "vulnerability_database"],
            targets=["flight_controller"],
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
            description="Bypass secure boot mechanisms",
            required_states=[DVDFlightState.PRE_FLIGHT],
            difficulty=AttackDifficulty.ADVANCED,
            prerequisites=["hardware_access", "cryptographic_tools"],
            targets=["flight_controller"],
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
        except Exception as e:
            logger.error(f"공격 등록 실패 {attack_name}: {str(e)}")
    
    logger.info(f"✅ {len(registered_attacks)}개 DVD 공격 시나리오 등록 완료")
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