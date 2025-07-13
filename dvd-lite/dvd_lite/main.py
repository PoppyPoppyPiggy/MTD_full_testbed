# dvd_lite/main.py
"""
DVD-Lite 메인 프레임워크
경량화된 드론 보안 테스트 및 CTI 수집
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

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# =============================================================================
# 기본 데이터 구조
# =============================================================================

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

# =============================================================================
# DVD-Lite 메인 클래스
# =============================================================================

class DVDLite:
    """경량화된 DVD 테스트베드"""
    
    def __init__(self, config_path: str = "config.json"):
        self.config = self._load_config(config_path)
        self.attack_modules = {}
        self.results = []
        self.cti_collector = None
        
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """설정 파일 로드"""
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"설정 파일 {config_path}를 찾을 수 없습니다. 기본 설정을 사용합니다.")
            return self._default_config()
    
    def _default_config(self) -> Dict[str, Any]:
        """기본 설정"""
        return {
            "target": {"ip": "10.13.0.2", "mavlink_port": 14550},
            "attacks": {"enabled": [], "delay_between": 2.0},
            "cti": {"auto_collect": True, "export_format": "json"},
            "output": {"results_dir": "results", "log_level": "INFO"}
        }
    
    def register_attack(self, name: str, attack_class):
        """공격 모듈 등록"""
        self.attack_modules[name] = attack_class
        logger.info(f"✅ 공격 모듈 등록: {name}")
    
    def register_cti_collector(self, cti_collector):
        """CTI 수집기 등록"""
        self.cti_collector = cti_collector
        logger.info("✅ CTI 수집기 등록 완료")
    
    async def run_attack(self, attack_name: str, **kwargs) -> AttackResult:
        """단일 공격 실행"""
        if attack_name not in self.attack_modules:
            raise ValueError(f"공격 모듈 '{attack_name}'을 찾을 수 없습니다.")
        
        # 공격 모듈 인스턴스 생성
        attack_class = self.attack_modules[attack_name]
        attack_instance = attack_class(
            target_ip=self.config["target"]["ip"],
            **kwargs
        )
        
        # 공격 실행
        result = await attack_instance.execute()
        self.results.append(result)
        
        # CTI 수집
        if self.cti_collector and self.config["cti"]["auto_collect"]:
            await self.cti_collector.collect_from_result(result)
        
        return result
    
    async def run_campaign(self, attack_names: List[str] = None) -> List[AttackResult]:
        """공격 캠페인 실행"""
        if attack_names is None:
            attack_names = self.config["attacks"]["enabled"]
        
        logger.info(f"🚀 공격 캠페인 시작: {len(attack_names)}개 공격")
        results = []
        
        for i, attack_name in enumerate(attack_names, 1):
            logger.info(f"공격 {i}/{len(attack_names)}: {attack_name}")
            
            try:
                result = await self.run_attack(attack_name)
                results.append(result)
                
                # 공격 간 대기
                if i < len(attack_names):
                    await asyncio.sleep(self.config["attacks"]["delay_between"])
                    
            except Exception as e:
                logger.error(f"공격 {attack_name} 실패: {str(e)}")
        
        logger.info(f"✅ 캠페인 완료: {len(results)}개 공격 실행")
        return results
    
    def get_summary(self) -> Dict[str, Any]:
        """결과 요약"""
        if not self.results:
            return {"message": "실행된 공격이 없습니다."}
        
        total = len(self.results)
        successful = sum(1 for r in self.results if r.status == AttackStatus.SUCCESS)
        detected = sum(1 for r in self.results if r.status == AttackStatus.DETECTED)
        
        return {
            "total_attacks": total,
            "successful_attacks": successful,
            "detected_attacks": detected,
            "success_rate": f"{(successful/total)*100:.1f}%",
            "detection_rate": f"{(detected/total)*100:.1f}%",
            "avg_response_time": f"{sum(r.response_time for r in self.results)/total:.2f}s"
        }
    
    def export_results(self, filename: str = None) -> str:
        """결과 내보내기"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"results/dvd_lite_results_{timestamp}.json"
        
        # 결과 디렉토리 생성
        Path(filename).parent.mkdir(parents=True, exist_ok=True)
        
        # 결과 데이터 구성
        export_data = {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "config": self.config,
                "summary": self.get_summary()
            },
            "results": [asdict(result) for result in self.results]
        }
        
        # JSON 파일로 저장
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False, default=str)
        
        logger.info(f"📄 결과 저장: {filename}")
        return filename
    
    def print_summary(self):
        """결과 요약 출력"""
        summary = self.get_summary()
        
        print("\n" + "="*50)
        print("🎯 DVD-Lite 실행 결과 요약")
        print("="*50)
        
        if "message" in summary:
            print(summary["message"])
        else:
            print(f"총 공격 수: {summary['total_attacks']}")
            print(f"성공한 공격: {summary['successful_attacks']} ({summary['success_rate']})")
            print(f"탐지된 공격: {summary['detected_attacks']} ({summary['detection_rate']})")
            print(f"평균 응답 시간: {summary['avg_response_time']}")
        
        print("="*50)
        
        # 개별 결과 출력
        if self.results:
            print("\n📋 개별 공격 결과:")
            for i, result in enumerate(self.results, 1):
                status_icon = "✅" if result.status == AttackStatus.SUCCESS else "❌"
                print(f"{i}. {result.attack_name}: {status_icon} {result.status.value}")
                print(f"   시간: {result.response_time:.2f}s, IOC: {len(result.iocs)}개")

# =============================================================================
# 기본 공격 베이스 클래스
# =============================================================================

class BaseAttack:
    """공격 기본 클래스"""
    
    def __init__(self, target_ip: str = "10.13.0.2", **kwargs):
        self.target_ip = target_ip
        self.config = kwargs
        self.attack_id = f"{self.__class__.__name__.lower()}_{int(time.time())}"
    
    async def execute(self) -> AttackResult:
        """공격 실행"""
        start_time = time.time()
        
        try:
            # 실제 공격 로직 실행
            success, iocs, details = await self._run_attack()
            
            # 결과 생성
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
        """실제 공격 로직 - 하위 클래스에서 구현"""
        raise NotImplementedError
    
    def _get_attack_type(self) -> AttackType:
        """공격 타입 반환 - 하위 클래스에서 구현"""
        raise NotImplementedError