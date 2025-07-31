# dvd_attacks/registry/__init__.py
"""
DVD 공격 등록 관리 시스템
"""
from .attack_registry import DVD_ATTACK_REGISTRY, DVDAttackRegistry
from .management import (
    register_all_dvd_attacks, get_attacks_by_tactic, 
    get_attacks_by_difficulty, get_attacks_by_flight_state,
    get_attack_info, DVD_ATTACK_SCENARIOS
)

__all__ = [
    'DVD_ATTACK_REGISTRY',
    'DVDAttackRegistry',
    'register_all_dvd_attacks',
    'get_attacks_by_tactic',
    'get_attacks_by_difficulty', 
    'get_attacks_by_flight_state',
    'get_attack_info',
    'DVD_ATTACK_SCENARIOS'
]
