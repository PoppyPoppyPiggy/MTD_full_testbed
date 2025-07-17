# =============================================================================
# 공격 등록 및 관리 시스템
# =============================================================================

# dvd_attacks/registry/attack_registry.py
"""
DVD 공격 등록 시스템
"""
import logging
from typing import Dict, List, Type, Optional
from ..core.attack_base import BaseAttack
from ..core.scenario import DVDAttackScenario
from ..core.enums import DVDAttackTactic, DVDFlightState, AttackDifficulty

logger = logging.getLogger(__name__)

class DVDAttackRegistry:
    """DVD 공격 등록 및 관리 클래스"""
    
    def __init__(self):
        self.attacks: Dict[str, Type[BaseAttack]] = {}
        self.scenarios: Dict[str, DVDAttackScenario] = {}
        self.categories: Dict[DVDAttackTactic, List[str]] = {}
    
    def register_attack(self, name: str, attack_class: Type[BaseAttack], 
                       scenario: Optional[DVDAttackScenario] = None) -> bool:
        """공격 등록"""
        try:
            # 공격 클래스 등록
            self.attacks[name] = attack_class
            
            # 시나리오 등록
            if scenario:
                self.scenarios[name] = scenario
                
                # 카테고리별 분류
                tactic = scenario.tactic
                if tactic not in self.categories:
                    self.categories[tactic] = []
                self.categories[tactic].append(name)
            
            logger.info(f"공격 등록 성공: {name}")
            return True
            
        except Exception as e:
            logger.error(f"공격 등록 실패 {name}: {str(e)}")
            return False
    
    def get_attack_class(self, name: str) -> Optional[Type[BaseAttack]]:
        """공격 클래스 반환"""
        return self.attacks.get(name)
    
    def get_scenario(self, name: str) -> Optional[DVDAttackScenario]:
        """공격 시나리오 반환"""
        return self.scenarios.get(name)
    
    def list_attacks(self) -> List[str]:
        """등록된 모든 공격 목록"""
        return list(self.attacks.keys())
    
    def get_attacks_by_tactic(self, tactic: DVDAttackTactic) -> List[str]:
        """전술별 공격 목록"""
        return self.categories.get(tactic, [])
    
    def get_attacks_by_difficulty(self, difficulty: AttackDifficulty) -> List[str]:
        """난이도별 공격 목록"""
        return [
            name for name, scenario in self.scenarios.items()
            if scenario.difficulty == difficulty
        ]
    
    def get_attacks_by_flight_state(self, state: DVDFlightState) -> List[str]:
        """비행 상태별 가능한 공격 목록"""
        return [
            name for name, scenario in self.scenarios.items()
            if state in scenario.required_states
        ]
    
    def get_registry_stats(self) -> Dict[str, Any]:
        """등록 현황 통계"""
        return {
            "total_attacks": len(self.attacks),
            "total_scenarios": len(self.scenarios),
            "by_tactic": {tactic.value: len(attacks) for tactic, attacks in self.categories.items()},
            "by_difficulty": {
                difficulty.value: len(self.get_attacks_by_difficulty(difficulty))
                for difficulty in AttackDifficulty
            }
        }

# 전역 레지스트리 인스턴스
DVD_ATTACK_REGISTRY = DVDAttackRegistry()
