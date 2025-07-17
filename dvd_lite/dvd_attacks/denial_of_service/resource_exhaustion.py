# dvd_lite/dvd_attacks/denial_of_service/resource_exhaustion.py
"""
CompanionComputerResourceExhaustion 공격 (더미 구현)
"""
import asyncio
import random
from typing import Tuple, List, Dict, Any
from ..core.attack_base import BaseAttack
from ..core.enums import AttackType

class CompanionComputerResourceExhaustion(BaseAttack):
    """CompanionComputerResourceExhaustion 공격"""
    
    def _get_attack_type(self) -> AttackType:
        return AttackType.RECONNAISSANCE  # 기본값
    
    async def _run_attack(self) -> Tuple[bool, List[str], Dict[str, Any]]:
        """더미 공격 로직"""
        await asyncio.sleep(random.uniform(1.0, 3.0))
        
        success = random.random() > 0.3
        iocs = [f"COMPANIONCOMPUTERRESOURCEEXHAUSTION_IOC:dummy_indicator"]
        details = {"success_rate": 0.7 if success else 0.2}
        
        return success, iocs, details
