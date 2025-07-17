# dvd_lite/main.py
"""
DVD-Lite 메인 프레임워크 (CTI 없는 버전)
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
    """경량화된 DVD 테스트베드 (CTI 없는 버전)"""
    
    def __init__(self, config_path: str = "config.json"):
        self.config = self._load_config(config_path)
        self.attack_modules = {}
        self.results = []
        
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
    
    def register_attack(self, name: str, attack_class):
        self.attack_modules[name] = attack_class
        logger.info(f"✅ 공격 모듈 등록: {name}")
    
    def list_attacks(self) -> List[str]:
        return list(self.attack_modules.keys())
    
    def get_attack_info(self, attack_name: str) -> Dict[str, Any]:
        attack_class = self.attack_modules.get(attack_name)
        if not attack_class:
            return {}
        
        return {
            "name": attack_name,
            "class": attack_class.__name__,
            "docstring": attack_class.__doc__ or "",
            "type": getattr(attack_class, '_get_attack_type', lambda: AttackType.RECONNAISSANCE)().value
        }
    
    async def run_attack(self, attack_name: str, **kwargs) -> AttackResult:
        if attack_name not in self.attack_modules:
            raise ValueError(f"공격 모듈 '{attack_name}'을 찾을 수 없습니다.")
        
        attack_class = self.attack_modules[attack_name]
        attack_instance = attack_class(
            target_ip=self.config["target"]["ip"],
            **kwargs
        )
        
        result = await attack_instance.execute()
        self.results.append(result)
        
        return result
    
    async def run_multiple_attacks(self, attack_names: List[str]) -> List[AttackResult]:
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
