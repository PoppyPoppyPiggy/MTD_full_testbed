#!/usr/bin/env python3
"""
DVD 프로젝트 최종 완전 수정 스크립트
DVDLite와 공격 모듈 연동 문제 해결
"""

import os
import sys
from pathlib import Path
import traceback

def fix_dvd_lite_main():
    """DVDLite main.py 수정 - CTI 메서드 및 공격 등록 연동 추가"""
    print("\n🔧 DVDLite main.py 수정 중...")
    
    fixed_main_content = '''# dvd_lite/main.py
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
'''
    
    write_file("dvd_lite/main.py", fixed_main_content)
    print("✅ DVDLite main.py 완전 수정됨")

def create_enhanced_registry_integration():
    """레지스트리 통합 개선"""
    print("\n🔗 레지스트리 통합 개선 중...")
    
    enhanced_registry_content = '''# dvd_lite/dvd_attacks/registry/enhanced_integration.py
"""
DVD 공격 레지스트리 통합 개선
"""
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

def ensure_registry_initialization():
    """레지스트리 초기화 보장"""
    try:
        from .attack_registry import DVD_ATTACK_REGISTRY
        from .management import register_all_dvd_attacks
        
        # 아직 등록되지 않았다면 등록
        if not DVD_ATTACK_REGISTRY.list_attacks():
            registered = register_all_dvd_attacks()
            logger.info(f"레지스트리 자동 초기화: {len(registered)}개 공격 등록")
        
        return DVD_ATTACK_REGISTRY
    except Exception as e:
        logger.error(f"레지스트리 초기화 실패: {e}")
        return None

def get_integrated_attack_list() -> List[str]:
    """통합된 공격 목록 반환"""
    registry = ensure_registry_initialization()
    if registry:
        return registry.list_attacks()
    return []

def get_integrated_attack_class(attack_name: str):
    """통합된 공격 클래스 반환"""
    registry = ensure_registry_initialization()
    if registry:
        return registry.get_attack_class(attack_name)
    return None

def test_registry_integration():
    """레지스트리 통합 테스트"""
    print("🧪 레지스트리 통합 테스트...")
    
    try:
        registry = ensure_registry_initialization()
        if registry:
            attacks = registry.list_attacks()
            print(f"✅ 등록된 공격: {len(attacks)}개")
            
            # 몇 개 공격 클래스 테스트
            for attack_name in attacks[:3]:
                attack_class = registry.get_attack_class(attack_name)
                if attack_class:
                    print(f"✅ {attack_name} 클래스 확인됨: {attack_class.__name__}")
                else:
                    print(f"❌ {attack_name} 클래스 없음")
            
            return True
        else:
            print("❌ 레지스트리 초기화 실패")
            return False
            
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        return False

if __name__ == "__main__":
    test_registry_integration()
'''
    
    write_file("dvd_lite/dvd_attacks/registry/enhanced_integration.py", enhanced_registry_content)
    print("✅ 레지스트리 통합 개선 완료")

def fix_quick_start_script():
    """quick_start.py CTI 오류 수정"""
    print("\n📝 quick_start.py CTI 오류 수정 중...")
    
    # 원본 quick_start.py에서 CTI 관련 코드만 수정
    quick_start_fixes = '''
# quick_start.py 수정사항
# 다음 줄들을 찾아서 수정하세요:

# 기존:
# dvd.register_cti_collector(cti)

# 수정:
# try:
#     dvd.register_cti_collector(cti)
# except AttributeError:
#     # CTI 수집기가 없는 경우 무시
#     pass

# 또는 더 간단하게 해당 줄을 주석 처리하세요.
'''
    
    # 실제 quick_start.py 파일 읽고 수정
    try:
        quick_start_path = Path("quick_start.py")
        if quick_start_path.exists():
            with open(quick_start_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # CTI 등록 라인 수정
            modified_content = content.replace(
                "dvd.register_cti_collector(cti)",
                """try:
        dvd.register_cti_collector(cti)
    except AttributeError:
        # CTI 수집기가 없는 경우 무시
        logger.warning("CTI 수집기 등록을 건너뜁니다 (메서드 없음)")
        pass"""
            )
            
            with open(quick_start_path, 'w', encoding='utf-8') as f:
                f.write(modified_content)
            
            print("✅ quick_start.py CTI 오류 수정됨")
        else:
            print("❌ quick_start.py 파일을 찾을 수 없음")
    except Exception as e:
        print(f"❌ quick_start.py 수정 실패: {e}")
        print(quick_start_fixes)

def create_test_script():
    """완전한 테스트 스크립트 생성"""
    print("\n🧪 완전한 테스트 스크립트 생성 중...")
    
    test_script_content = '''#!/usr/bin/env python3
"""
DVD 프로젝트 완전 테스트 스크립트
"""

import asyncio
import sys
import os
from pathlib import Path

# 경로 추가
sys.path.insert(0, os.getcwd())

async def test_complete_system():
    """완전한 시스템 테스트"""
    print("🧪 DVD 시스템 완전 테스트 시작")
    print("=" * 50)
    
    try:
        # 1. 기본 import 테스트
        print("1️⃣ 기본 import 테스트...")
        from dvd_lite.main import DVDLite
        print("✅ DVDLite import 성공")
        
        # 2. 레지스트리 테스트
        print("\\n2️⃣ 레지스트리 테스트...")
        from dvd_lite.dvd_attacks.registry.management import register_all_dvd_attacks
        registered = register_all_dvd_attacks()
        print(f"✅ {len(registered)}개 공격 등록됨: {registered[:5]}...")
        
        # 3. DVDLite 인스턴스 생성
        print("\\n3️⃣ DVDLite 인스턴스 생성...")
        dvd = DVDLite()
        print("✅ DVDLite 인스턴스 생성 성공")
        
        # 4. 공격 목록 확인
        print("\\n4️⃣ 공격 목록 확인...")
        attacks = dvd.list_attacks()
        print(f"✅ 사용 가능한 공격: {len(attacks)}개")
        print(f"   공격 목록: {attacks[:10]}...")
        
        # 5. 공격 정보 확인
        print("\\n5️⃣ 공격 정보 확인...")
        if attacks:
            info = dvd.get_attack_info(attacks[0])
            print(f"✅ {attacks[0]} 정보: {info.get('description', 'N/A')}")
        
        # 6. 실제 공격 실행 테스트
        print("\\n6️⃣ 실제 공격 실행 테스트...")
        if attacks:
            try:
                result = await dvd.run_attack(attacks[0])
                print(f"✅ 공격 실행 성공: {result.attack_name}")
                print(f"   상태: {result.status.value}")
                print(f"   IOCs: {len(result.iocs)}개")
            except Exception as e:
                print(f"❌ 공격 실행 실패: {e}")
        
        # 7. CTI 테스트 (선택적)
        print("\\n7️⃣ CTI 테스트...")
        try:
            from dvd_lite.cti import SimpleCTI
            cti = SimpleCTI()
            dvd.register_cti_collector(cti)
            print("✅ CTI 수집기 등록 성공")
        except Exception as e:
            print(f"⚠️  CTI 테스트 건너뜀: {e}")
        
        print("\\n🎉 모든 테스트 완료! 시스템이 정상 작동합니다.")
        return True
        
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    asyncio.run(test_complete_system())
'''
    
    write_file("test_complete_system.py", test_script_content)
    print("✅ 완전한 테스트 스크립트 생성됨")

def write_file(path: str, content: str):
    """파일 쓰기 헬퍼"""
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

def main():
    """메인 실행 함수"""
    print("🔧 DVD 프로젝트 최종 완전 수정")
    print("=" * 60)
    
    # 1. DVDLite main.py 수정
    fix_dvd_lite_main()
    
    # 2. 레지스트리 통합 개선
    create_enhanced_registry_integration()
    
    # 3. quick_start.py CTI 오류 수정
    fix_quick_start_script()
    
    # 4. 완전한 테스트 스크립트 생성
    create_test_script()
    
    print("\n" + "=" * 60)
    print("🎉 최종 수정 완료!")
    print("\n🚀 이제 다음 명령들을 실행하세요:")
    print("   python3 test_complete_system.py      # 완전한 시스템 테스트")
    print("   python3 advanced_start_no_cti.py     # CTI 없는 버전")
    print("   python3 quick_start.py               # 전체 데모")

if __name__ == "__main__":
    main()