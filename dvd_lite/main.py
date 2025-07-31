# dvd_lite/main.py
"""
DVD-Lite 메인 프레임워크 (완전 수정 버전)
"""

import asyncio
import json
import time
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AttackType(Enum):
    RECONNAISSANCE = "reconnaissance"
    PROTOCOL_TAMPERING = "protocol_tampering"
    INJECTION = "injection"
    DOS = "denial_of_service"
    EXFILTRATION = "exfiltration"
    FIRMWARE_ATTACKS = "firmware_attacks"

class AttackStatus(Enum):
    SUCCESS = "success"
    FAILED = "failed"
    DETECTED = "detected"

@dataclass
class AttackResult:
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
    
    @property
    def success(self) -> bool:
        return self.status == AttackStatus.SUCCESS
    
    @property
    def execution_time(self) -> float:
        return self.response_time
    
    @property
    def error_message(self) -> Optional[str]:
        return self.details.get("error")

class DVDLite:
    """경량화된 DVD 테스트베드 (완전 버전)"""
    
    def __init__(self, config_path: str = "config.json"):
        self.config = self._load_config(config_path)
        self.attack_modules = {}
        self.results = []
        self.cti_collector = None
        
        # DVD 공격 레지스트리와 연동
        self._setup_dvd_attack_registry()
        
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {
                "target": {"ip": "10.13.0.2", "mavlink_port": 14550},
                "attacks": {"enabled": [], "delay_between": 2.0},
                "output": {"results_dir": "results", "log_level": "INFO"}
            }
    
    def _setup_dvd_attack_registry(self):
        """DVD 공격 레지스트리와 연동 설정"""
        try:
            from dvd_lite.dvd_attacks.registry.attack_registry import DVD_ATTACK_REGISTRY
            self.dvd_registry = DVD_ATTACK_REGISTRY
            logger.info("DVD 공격 레지스트리 연동 완료")
        except ImportError:
            self.dvd_registry = None
            logger.warning("DVD 공격 레지스트리 연동 실패")
    
    def register_attack(self, name: str, attack_class):
        """기본 공격 모듈 등록"""
        self.attack_modules[name] = attack_class
        logger.info(f"✅ 기본 공격 모듈 등록: {name}")
    
    def register_cti_collector(self, cti_collector):
        """CTI 수집기 등록 (호환성을 위해 추가)"""
        self.cti_collector = cti_collector
        logger.info("✅ CTI 수집기 등록 완료")
    
    def list_attacks(self) -> List[str]:
        """모든 등록된 공격 목록 반환"""
        attacks = list(self.attack_modules.keys())
        
        # DVD 레지스트리의 공격들도 포함
        if self.dvd_registry:
            attacks.extend(self.dvd_registry.list_attacks())
        
        return list(set(attacks))  # 중복 제거
    
    def get_attack_info(self, attack_name: str) -> Dict[str, Any]:
        """공격 정보 반환"""
        # 먼저 DVD 레지스트리에서 확인
        if self.dvd_registry:
            from dvd_lite.dvd_attacks.registry.management import get_attack_info
            info = get_attack_info(attack_name)
            if info:
                return info
        
        # 기본 공격 모듈에서 확인
        attack_class = self.attack_modules.get(attack_name)
        if attack_class:
            return {
                "name": attack_name,
                "class": attack_class.__name__,
                "docstring": attack_class.__doc__ or "",
                "type": getattr(attack_class, '_get_attack_type', lambda: AttackType.RECONNAISSANCE)().value
            }
        
        return {}
    
    async def run_attack(self, attack_name: str, **kwargs) -> AttackResult:
        """공격 실행 - DVD 레지스트리와 기본 모듈 모두 지원"""
        
        # 1. DVD 레지스트리에서 먼저 확인
        if self.dvd_registry:
            attack_class = self.dvd_registry.get_attack_class(attack_name)
            if attack_class:
                return await self._run_dvd_attack(attack_name, attack_class, **kwargs)
        
        # 2. 기본 공격 모듈에서 확인
        if attack_name in self.attack_modules:
            attack_class = self.attack_modules[attack_name]
            return await self._run_basic_attack(attack_name, attack_class, **kwargs)
        
        # 3. 둘 다 없으면 오류
        available_attacks = self.list_attacks()
        raise ValueError(f"공격 모듈 '{attack_name}'을 찾을 수 없습니다. 사용 가능한 공격: {available_attacks}")
    
    async def _run_dvd_attack(self, attack_name: str, attack_class, **kwargs) -> AttackResult:
        """DVD 공격 실행"""
        attack_instance = attack_class(
            target_ip=self.config["target"]["ip"],
            **kwargs
        )
        
        result = await attack_instance.execute()
        self.results.append(result)
        
        # CTI 수집
        if self.cti_collector:
            try:
                await self.cti_collector.collect_from_result(result)
            except Exception as e:
                logger.warning(f"CTI 수집 실패: {e}")
        
        return result
    
    async def _run_basic_attack(self, attack_name: str, attack_class, **kwargs) -> AttackResult:
        """기본 공격 실행"""
        attack_instance = attack_class(
            target_ip=self.config["target"]["ip"],
            **kwargs
        )
        
        result = await attack_instance.execute()
        self.results.append(result)
        
        return result
    
    async def run_multiple_attacks(self, attack_names: List[str]) -> List[AttackResult]:
        """여러 공격 실행"""
        results = []
        
        for attack_name in attack_names:
            try:
                result = await self.run_attack(attack_name)
                results.append(result)
                await asyncio.sleep(self.config["attacks"]["delay_between"])
            except Exception as e:
                logger.error(f"공격 {attack_name} 실패: {str(e)}")
        
        return results
    
    def get_summary(self) -> Dict[str, Any]:
        """결과 요약"""
        if not self.results:
            return {"message": "실행된 공격이 없습니다."}
        
        total = len(self.results)
        successful = sum(1 for r in self.results if r.status == AttackStatus.SUCCESS)
        
        return {
            "total_attacks": total,
            "successful_attacks": successful,
            "success_rate": f"{(successful/total)*100:.1f}%",
            "avg_response_time": f"{sum(r.response_time for r in self.results)/total:.2f}s"
        }

class BaseAttack:
    """공격 기본 클래스"""
    
    def __init__(self, target_ip: str = "10.13.0.2", **kwargs):
        self.target_ip = target_ip
        self.config = kwargs
        self.attack_id = f"{self.__class__.__name__.lower()}_{int(time.time())}"
    
    async def execute(self) -> AttackResult:
        start_time = time.time()
        
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
            
            return result
            
        except Exception as e:
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
    
    async def _run_attack(self) -> tuple:
        raise NotImplementedError
    
    def _get_attack_type(self) -> AttackType:
        raise NotImplementedError
