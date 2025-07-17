# dvd_attacks/core/enums.py
"""
DVD 공격 시스템 열거형 정의
"""
from enum import Enum

class AttackType(Enum):
    """공격 유형"""
    RECONNAISSANCE = "reconnaissance"
    PROTOCOL_TAMPERING = "protocol_tampering"
    DOS = "denial_of_service"
    INJECTION = "injection"
    EXFILTRATION = "exfiltration"
    FIRMWARE_ATTACKS = "firmware_attacks"

class DVDAttackTactic(Enum):
    """DVD 공격 전술 분류"""
    RECONNAISSANCE = "reconnaissance"
    PROTOCOL_TAMPERING = "protocol_tampering"
    DENIAL_OF_SERVICE = "denial_of_service"
    INJECTION = "injection"
    EXFILTRATION = "exfiltration"
    FIRMWARE_ATTACKS = "firmware_attacks"

class DVDFlightState(Enum):
    """드론 비행 상태"""
    PRE_FLIGHT = "pre_flight"
    TAKEOFF = "takeoff"
    AUTOPILOT_FLIGHT = "autopilot_flight"
    MANUAL_FLIGHT = "manual_flight"
    EMERGENCY_RTL = "emergency_rtl"
    POST_FLIGHT = "post_flight"

class AttackDifficulty(Enum):
    """공격 난이도"""
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"

class AttackStatus(Enum):
    """공격 상태"""
    SUCCESS = "success"
    FAILED = "failed"
    DETECTED = "detected"
    PARTIAL = "partial"