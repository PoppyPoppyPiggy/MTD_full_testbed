# dvd_lite/dvd_attacks/__init__.py
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

# 공격 카테고리별 모듈들 - 안전한 import
try:
    from .reconnaissance import *
except ImportError:
    pass

try:
    from .protocol_tampering import *
except ImportError:
    pass

try:
    from .denial_of_service import *
except ImportError:
    pass

try:
    from .injection import *
except ImportError:
    pass

try:
    from .exfiltration import *
except ImportError:
    pass

try:
    from .firmware_attacks import *
except ImportError:
    pass

# 등록 및 관리 시스템
try:
    from .registry import (
        DVD_ATTACK_REGISTRY, register_all_dvd_attacks,
        get_attacks_by_tactic, get_attacks_by_difficulty,
        get_attacks_by_flight_state, get_attack_info
    )
except ImportError:
    # 기본 더미 함수들
    def register_all_dvd_attacks():
        return []
    
    def get_attacks_by_tactic(tactic):
        return []
    
    def get_attacks_by_difficulty(difficulty):
        return []
    
    def get_attacks_by_flight_state(state):
        return []
    
    def get_attack_info(attack_name):
        return {}

# 유틸리티
try:
    from .utils import *
except ImportError:
    pass

__version__ = "1.0.0"
__author__ = "DVD Research Team"
__description__ = "Comprehensive DVD Attack Scenarios for Drone Security Testing"

__all__ = [
    # 핵심 타입 및 클래스
    'AttackType', 'DVDAttackTactic', 'DVDFlightState',
    'AttackDifficulty', 'AttackStatus', 'DVDAttackScenario', 
    'BaseAttack', 'AttackResult',
    
    # 등록 시스템
    'register_all_dvd_attacks',
    'get_attacks_by_tactic', 'get_attacks_by_difficulty',
    'get_attacks_by_flight_state', 'get_attack_info'
]
