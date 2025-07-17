# dvd_lite/dvd_attacks/core/attack_base.py
"""
공격 기본 클래스 정의
"""
import asyncio
import time
import logging
from abc import ABC, abstractmethod
from typing import Tuple, List, Dict, Any, Optional
from dataclasses import dataclass
from .enums import AttackType, AttackStatus

logger = logging.getLogger(__name__)

@dataclass
class AttackResult:
    """공격 결과 데이터 클래스"""
    attack_id: str
    attack_name: str
    attack_type: AttackType
    status: AttackStatus
    success_rate: float
    response_time: float
    timestamp: float
    target: str
    iocs: List[str]
    details: Dict[str, Any]
    scenario_info: Optional[Dict[str, Any]] = None

class BaseAttack(ABC):
    """DVD 공격 기본 클래스"""
    
    def __init__(self, target_ip: str = "10.13.0.2", **kwargs):
        self.target_ip = target_ip
        self.config = kwargs
        self.attack_id = f"{self.__class__.__name__.lower()}_{int(time.time())}"
        self.logger = logging.getLogger(f"attack.{self.__class__.__name__}")
    
    async def execute(self) -> AttackResult:
        """공격 실행 메인 메서드"""
        start_time = time.time()
        self.logger.info(f"공격 시작: {self.__class__.__name__} -> {self.target_ip}")
        
        try:
            success, iocs, details = await self._run_attack()
            
            result = AttackResult(
                attack_id=self.attack_id,
                attack_name=self.__class__.__name__,
                attack_type=self._get_attack_type(),
                status=AttackStatus.SUCCESS if success else AttackStatus.FAILED,
                success_rate=details.get("success_rate", 0.7 if success else 0.0),
                response_time=time.time() - start_time,
                timestamp=time.time(),
                target=self.target_ip,
                iocs=iocs,
                details=details
            )
            
            self.logger.info(f"공격 완료: {result.status.value} ({result.response_time:.2f}초)")
            return result
            
        except Exception as e:
            self.logger.error(f"공격 실패: {str(e)}")
            return AttackResult(
                attack_id=self.attack_id,
                attack_name=self.__class__.__name__,
                attack_type=self._get_attack_type(),
                status=AttackStatus.FAILED,
                success_rate=0.0,
                response_time=time.time() - start_time,
                timestamp=time.time(),
                target=self.target_ip,
                iocs=[],
                details={"error": str(e)}
            )
    
    @abstractmethod
    async def _run_attack(self) -> Tuple[bool, List[str], Dict[str, Any]]:
        """실제 공격 로직 - 하위 클래스에서 반드시 구현"""
        pass
    
    @abstractmethod
    def _get_attack_type(self) -> AttackType:
        """공격 타입 반환 - 하위 클래스에서 반드시 구현"""
        pass
