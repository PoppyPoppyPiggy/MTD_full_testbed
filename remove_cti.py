#!/usr/bin/env python3
"""
CTI 의존성을 제거하여 빠르게 실행 가능하게 만드는 스크립트
"""

from pathlib import Path

def update_advanced_start_without_cti():
    """advanced_start.py에서 CTI 의존성 제거"""
    
    content = '''#!/usr/bin/env python3
"""
DVD 공격 시나리오 빠른 실행 스크립트 (CTI 없는 버전)
"""

import asyncio
import sys
import logging
from pathlib import Path

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from dvd_lite.main import DVDLite
    # CTI 제거 - 필요 없음
    # from dvd_lite.cti import SimpleCTI
    
    # DVD 공격 모듈 (있으면 사용)
    try:
        from dvd_lite.dvd_attacks import (
            register_all_dvd_attacks,
            get_attacks_by_tactic,
            get_attacks_by_difficulty,
            get_attacks_by_flight_state,
            get_attack_info,
            DVDAttackTactic,
            DVDFlightState,
            AttackDifficulty,
            AttackStatus
        )
        DVD_ATTACKS_AVAILABLE = True
    except ImportError:
        # DVD 공격 모듈이 없으면 기본 공격 사용
        try:
            from dvd_lite.attacks import register_all_attacks
            DVD_ATTACKS_AVAILABLE = False
        except ImportError:
            print("⚠️  공격 모듈이 없습니다. 기본 모드로 실행합니다.")
            DVD_ATTACKS_AVAILABLE = False
            register_all_attacks = None
        
        register_all_dvd_attacks = None
        get_attacks_by_tactic = None
        get_attacks_by_difficulty = None
        get_attacks_by_flight_state = None
        get_attack_info = None
        DVDAttackTactic = None
        DVDFlightState = None
        AttackDifficulty = None
        AttackStatus = None
        
except ImportError as e:
    print(f"❌ Import 오류: {e}")
    print("파일 구조를 확인하고 필요한 모듈을 생성하세요.")
    sys.exit(1)

def print_banner():
    """배너 출력"""
    banner = """
╔══════════════════════════════════════════════════════════════════╗
║                    DVD Attack Scenarios                          ║
║              Damn Vulnerable Drone 공격 시나리오                  ║
║                     (간소화 버전 - No CTI)                        ║
║                                                                  ║
║  🎯 드론 보안 테스트 프레임워크                                     ║
║  🔥 다양한 공격 시나리오                                           ║
║  📊 실시간 결과 분석                                              ║
╚══════════════════════════════════════════════════════════════════╝
"""
    print(banner)

def print_attack_detail(result) -> None:
    """공격 실행 결과 상세 출력"""
    status_icon = "✅" if result.success else "❌"
    
    print(f"\\n{status_icon} 공격 완료: {result.attack_name}")
    print(f"   📊 상태: {'성공' if result.success else '실패'}")
    print(f"   ⏱️  실행시간: {result.execution_time:.2f}초")
    print(f"   🔍 IOCs: {len(result.iocs)}개")
    print(f"   🎪 타겟: {result.target}")
    
    # IOC 상세 표시
    if result.iocs:
        print("   📋 주요 IOCs:")
        for ioc in result.iocs[:5]:  # 최대 5개만 표시
            print(f"      • {ioc}")
        if len(result.iocs) > 5:
            print(f"      ... 및 {len(result.iocs) - 5}개 더")
    
    # 공격 세부사항 표시
    if hasattr(result, 'details') and result.details:
        print("   📝 세부사항:")
        interesting_keys = ['success_rate', 'attack_vector', 'discovered_networks', 'system_impact']
        
        shown_count = 0
        for key, value in result.details.items():
            if shown_count >= 3:
                break
                
            if key in interesting_keys or isinstance(value, (int, float, str)):
                if isinstance(value, float):
                    print(f"      • {key}: {value:.2f}")
                elif isinstance(value, list) and len(value) <= 3:
                    print(f"      • {key}: {value}")
                else:
                    print(f"      • {key}: {str(value)[:50]}...")
                shown_count += 1

async def run_single_attack_demo():
    """단일 공격 실행 데모"""
    print("\\n" + "="*60)
    print("🎯 단일 공격 실행 데모")
    print("="*60)
    
    # DVD-Lite 인스턴스 생성 (CTI 없이)
    dvd = DVDLite()
    
    # 공격 등록
    if DVD_ATTACKS_AVAILABLE and register_all_dvd_attacks:
        registered_attacks = register_all_dvd_attacks()
        print(f"📋 등록된 DVD 공격: {len(registered_attacks)}개")
        attack_name = "wifi_network_discovery"
    elif register_all_attacks:
        registered_attacks = register_all_attacks(dvd)
        print(f"📋 등록된 기본 공격: {len(registered_attacks)}개")
        attack_name = "wifi_scan"
    else:
        print("❌ 사용 가능한 공격 모듈이 없습니다.")
        return
    
    print(f"\\n🚀 {attack_name} 공격 실행 중...")
    
    try:
        # 공격 정보 표시 (있는 경우)
        if get_attack_info:
            attack_info = get_attack_info(attack_name)
            if attack_info:
                print(f"   📖 설명: {attack_info['description']}")
                print(f"   🎚️  난이도: {attack_info['difficulty']}")
                print(f"   🎯 타겟: {', '.join(attack_info['targets'])}")
        
        # 공격 실행
        result = await dvd.run_attack(attack_name)
        
        # 결과 상세 출력
        print_attack_detail(result)
        
    except Exception as e:
        print(f"❌ 실행 실패: {e}")
        import traceback
        traceback.print_exc()

async def run_multiple_attacks_demo():
    """여러 공격 실행 데모"""
    print("\\n" + "="*60)
    print("🚀 여러 공격 실행 데모")
    print("="*60)
    
    dvd = DVDLite()
    
    # 공격 등록 및 선택
    if DVD_ATTACKS_AVAILABLE and register_all_dvd_attacks:
        register_all_dvd_attacks()
        attacks_to_run = [
            "wifi_network_discovery",
            "mavlink_service_discovery", 
            "gps_spoofing",
            "telemetry_exfiltration"
        ]
    elif register_all_attacks:
        register_all_attacks(dvd)
        attacks_to_run = [
            "wifi_scan",
            "drone_discovery",
            "packet_sniff",
            "telemetry_spoof"
        ]
    else:
        print("❌ 사용 가능한 공격 모듈이 없습니다.")
        return
    
    print(f"📋 실행할 공격 시나리오: {len(attacks_to_run)}개")
    
    # 각 공격 정보 표시
    for attack_name in attacks_to_run:
        if get_attack_info:
            info = get_attack_info(attack_name)
            if info:
                print(f"   • {attack_name} ({info.get('tactic', 'unknown')}) - {info.get('difficulty', 'unknown')}")
        else:
            print(f"   • {attack_name}")
    
    print("\\n🔥 공격 실행 시작...")
    
    results = []
    for i, attack_name in enumerate(attacks_to_run, 1):
        print(f"\\n[{i}/{len(attacks_to_run)}] 🎯 {attack_name} 실행 중...")
        
        try:
            result = await dvd.run_attack(attack_name)
            results.append(result)
            
            # 간단한 결과 출력
            status = "✅" if result.success else "❌"
            print(f"   {status} 완료: {result.execution_time:.2f}초, IOCs: {len(result.iocs)}개")
            
        except Exception as e:
            print(f"   ❌ 실패: {str(e)}")
            
        # 공격 간 간격
        if i < len(attacks_to_run):
            await asyncio.sleep(0.5)
    
    # 전체 결과 요약
    print("\\n" + "="*60)
    print("📊 전체 실행 결과 요약")
    print("="*60)
    
    if results:
        success_count = sum(1 for r in results if r.success)
        total_time = sum(r.execution_time for r in results)
        total_iocs = sum(len(r.iocs) for r in results)
        
        print(f"📈 성공률: {success_count}/{len(results)} ({success_count/len(results)*100:.1f}%)")
        print(f"⏱️  총 실행시간: {total_time:.2f}초")
        print(f"📊 평균 실행시간: {total_time/len(results):.2f}초")
        print(f"🔍 총 IOCs: {total_iocs}개")
        
        print("\\n📋 개별 결과:")
        for result in results:
            status = "✅" if result.success else "❌"
            print(f"   {status} {result.attack_name}: {result.execution_time:.2f}s, IOCs: {len(result.iocs)}")

async def run_basic_demo():
    """기본 데모 실행"""
    print("\\n" + "="*60)
    print("🎮 기본 DVD 공격 데모")
    print("="*60)
    
    dvd = DVDLite()
    
    # 기본 공격 등록
    if register_all_attacks:
        attacks = register_all_attacks(dvd)
        print(f"📋 등록된 공격: {attacks}")
        
        # 샘플 공격 실행
        sample_attacks = attacks[:3] if len(attacks) >= 3 else attacks
        
        for attack in sample_attacks:
            print(f"\\n🎯 {attack} 실행 중...")
            try:
                result = await dvd.run_attack(attack)
                print_attack_detail(result)
                await asyncio.sleep(1)
            except Exception as e:
                print(f"❌ 실행 실패: {e}")
    else:
        print("❌ 공격 모듈을 찾을 수 없습니다.")

def show_available_features():
    """사용 가능한 기능 표시"""
    print("\\n" + "="*60)
    print("📚 사용 가능한 기능")
    print("="*60)
    
    print("✅ 기본 기능:")
    print("   • DVD-Lite 프레임워크")
    print("   • 공격 모듈 등록 및 실행")
    print("   • 결과 분석 및 요약")
    
    if DVD_ATTACKS_AVAILABLE:
        print("\\n✅ DVD 공격 모듈:")
        print("   • 19개 전문 공격 시나리오")
        print("   • 6개 공격 전술 카테고리")
        print("   • 상세한 공격 메타데이터")
    else:
        print("\\n⚠️  DVD 공격 모듈:")
        print("   • 기본 8개 공격만 사용 가능")
        print("   • 고급 공격 기능 제한")
    
    print("\\n❌ 비활성화된 기능:")
    print("   • CTI 수집 및 분석")
    print("   • 위협 지표 추출")
    print("   • JSON/CSV 내보내기")

async def interactive_mode():
    """대화형 모드"""
    print("\\n" + "="*60)
    print("🎮 대화형 모드")
    print("="*60)
    
    dvd = DVDLite()
    
    # 공격 등록
    if DVD_ATTACKS_AVAILABLE and register_all_dvd_attacks:
        register_all_dvd_attacks()
        attacks = get_attacks_by_tactic(DVDAttackTactic.RECONNAISSANCE) if get_attacks_by_tactic else []
    elif register_all_attacks:
        attacks = register_all_attacks(dvd)
    else:
        print("❌ 사용 가능한 공격이 없습니다.")
        return
    
    if not attacks:
        print("❌ 등록된 공격이 없습니다.")
        return
    
    while True:
        print("\\n🎯 사용 가능한 공격:")
        for i, attack in enumerate(attacks, 1):
            print(f"   {i}. {attack}")
        print(f"   {len(attacks) + 1}. 종료")
        
        try:
            choice = input(f"\\n실행할 공격을 선택하세요 (1-{len(attacks) + 1}): ").strip()
            choice_idx = int(choice) - 1
            
            if choice_idx == len(attacks):
                print("👋 종료합니다.")
                break
            elif 0 <= choice_idx < len(attacks):
                selected_attack = attacks[choice_idx]
                print(f"\\n🚀 {selected_attack} 실행 중...")
                
                result = await dvd.run_attack(selected_attack)
                print_attack_detail(result)
            else:
                print("❌ 잘못된 선택입니다.")
                
        except (ValueError, KeyboardInterrupt):
            print("\\n👋 종료합니다.")
            break
        except Exception as e:
            print(f"❌ 오류 발생: {e}")

async def main():
    """메인 함수"""
    print_banner()
    
    if len(sys.argv) > 1:
        mode = sys.argv[1]
        
        if mode == "single":
            await run_single_attack_demo()
        elif mode == "multiple":
            await run_multiple_attacks_demo()
        elif mode == "basic":
            await run_basic_demo()
        elif mode == "features":
            show_available_features()
        elif mode == "interactive":
            await interactive_mode()
        else:
            print(f"❌ 알 수 없는 모드: {mode}")
            print_usage()
    else:
        # 기본: 핵심 데모들 실행
        await run_single_attack_demo()
        await run_multiple_attacks_demo()
        show_available_features()

def print_usage():
    """사용법 출력"""
    print("\\n📖 사용법:")
    print("   python3 advanced_start.py [mode]")
    print("\\n🎯 모드:")
    print("   single      - 단일 공격 데모")
    print("   multiple    - 여러 공격 데모")
    print("   basic       - 기본 데모")
    print("   features    - 사용 가능한 기능")
    print("   interactive - 대화형 모드")
    print("   (없음)      - 핵심 데모 실행")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\\n👋 사용자에 의해 중단되었습니다.")
    except Exception as e:
        print(f"\\n❌ 실행 오류: {e}")
        import traceback
        traceback.print_exc()
'''
    
    file_path = Path("advanced_start_no_cti.py")
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"✅ CTI 없는 버전 생성: {file_path}")

def update_dvd_lite_init_no_cti():
    """dvd_lite/__init__.py CTI 의존성 제거"""
    
    content = '''# dvd_lite/__init__.py
"""
DVD-Lite 패키지 (CTI 없는 버전)
경량화된 드론 보안 테스트 프레임워크
"""

__version__ = "1.0.0"
__author__ = "DVD-Lite Team"
__description__ = "경량화된 드론 보안 테스트 프레임워크"

# 메인 클래스들 import (CTI 제외)
try:
    from .main import DVDLite, BaseAttack, AttackResult, AttackType, AttackStatus
    
    # 기본 공격 모듈들 import (선택적)
    try:
        from .attacks import (
            WiFiScan,
            DroneDiscovery, 
            PacketSniff,
            TelemetrySpoof,
            CommandInject,
            WaypointInject,
            LogExtract,
            ParamExtract,
            register_all_attacks
        )
        BASIC_ATTACKS_AVAILABLE = True
    except ImportError:
        print("Warning: 기본 공격 모듈 import 실패")
        BASIC_ATTACKS_AVAILABLE = False
        register_all_attacks = None
    
    # DVD 공격 시나리오 import (선택적)
    try:
        from .dvd_attacks import (
            register_all_dvd_attacks,
            get_attacks_by_tactic,
            get_attacks_by_difficulty,
            get_attacks_by_flight_state,
            get_attack_info,
            DVDAttackTactic,
            DVDFlightState,
            AttackDifficulty
        )
        
        DVD_ATTACKS_AVAILABLE = True
        
    except ImportError:
        print("Warning: DVD 공격 모듈 import 실패")
        DVD_ATTACKS_AVAILABLE = False
        register_all_dvd_attacks = None
        get_attacks_by_tactic = None
        get_attacks_by_difficulty = None
        get_attacks_by_flight_state = None
        get_attack_info = None
        DVDAttackTactic = None
        DVDFlightState = None
        AttackDifficulty = None
        
except ImportError as e:
    print(f"Warning: DVD-Lite 핵심 모듈 import 오류: {e}")
    DVDLite = None
    BaseAttack = None
    AttackResult = None
    AttackType = None
    AttackStatus = None
    BASIC_ATTACKS_AVAILABLE = False
    DVD_ATTACKS_AVAILABLE = False

# 유틸리티 함수들 (선택적)
try:
    from .utils import (
        check_host_alive,
        check_port_open,
        validate_ip_address,
        validate_port,
        is_safe_target
    )
    UTILS_AVAILABLE = True
except ImportError:
    print("Warning: 유틸리티 모듈 import 실패")
    UTILS_AVAILABLE = False
    check_host_alive = None
    check_port_open = None
    validate_ip_address = None
    validate_port = None
    is_safe_target = None

__all__ = [
    # 메인 클래스들
    "DVDLite",
    "BaseAttack", 
    "AttackResult",
    "AttackType",
    "AttackStatus",
    
    # 기본 공격 모듈들
    "register_all_attacks",
    
    # DVD 공격 시나리오
    "register_all_dvd_attacks",
    "get_attacks_by_tactic",
    "get_attacks_by_difficulty",
    "get_attacks_by_flight_state",
    "get_attack_info",
    "DVDAttackTactic",
    "DVDFlightState", 
    "AttackDifficulty",
    
    # 상태 플래그
    "BASIC_ATTACKS_AVAILABLE",
    "DVD_ATTACKS_AVAILABLE",
    "UTILS_AVAILABLE"
]

# None 값들은 __all__에서 제거
__all__ = [item for item in __all__ if globals().get(item) is not None]
'''

    file_path = Path("dvd_lite/__init__.py")
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"✅ CTI 의존성 제거된 __init__.py 업데이트: {file_path}")

def create_simple_main():
    """간단한 main.py 생성 (CTI 없이)"""
    
    content = '''# dvd_lite/main.py
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
'''
    
    file_path = Path("dvd_lite/main.py")
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"✅ 간단한 main.py 생성: {file_path}")

def main():
    """메인 함수"""
    print("🔧 CTI 의존성 제거 도구")
    print("=" * 50)
    
    # 1. CTI 없는 advanced_start.py 생성
    update_advanced_start_without_cti()
    
    # 2. dvd_lite/__init__.py에서 CTI 제거
    update_dvd_lite_init_no_cti()
    
    # 3. 간단한 main.py 생성
    create_simple_main()
    
    print("\n🎉 CTI 의존성이 제거되었습니다!")
    print("\n🚀 이제 다음 명령을 실행해보세요:")
    print("   python3 advanced_start_no_cti.py")
    print("   또는")
    print("   python3 advanced_start_no_cti.py interactive")

if __name__ == "__main__":
    main()