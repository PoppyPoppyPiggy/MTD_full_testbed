# dvd_attacks/core/scenario.py
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
    targets: List[str]  # "flight_controller", "companion_computer", "gcs", "network"
    estimated_duration: float = 0.0  # seconds
    stealth_level: str = "medium"  # "low", "medium", "high"
    impact_level: str = "medium"  # "low", "medium", "high", "critical"
