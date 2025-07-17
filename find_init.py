#!/usr/bin/env python3
"""
__init__.py 파일 검사 및 자동 생성 스크립트
"""

import os
import sys
from pathlib import Path

def check_and_create_init_files():
    """필요한 __init__.py 파일들을 검사하고 생성"""
    
    print("🔍 __init__.py 파일 검사 중...")
    print("=" * 60)
    
    # 검사할 디렉토리 구조 (현재 문서 기준)
    required_dirs = [
        "dvd_lite",
        "dvd_lite/dvd_attacks",
        "dvd_lite/dvd_attacks/core",
        "dvd_lite/dvd_attacks/reconnaissance", 
        "dvd_lite/dvd_attacks/protocol_tampering",
        "dvd_lite/dvd_attacks/denial_of_service",
        "dvd_lite/dvd_attacks/injection",
        "dvd_lite/dvd_attacks/exfiltration",
        "dvd_lite/dvd_attacks/firmware_attacks",
        "dvd_lite/dvd_attacks/registry",
        "dvd_lite/dvd_attacks/utils",
        "dvd_connector",
        "scripts",
        "configs",
        "data",
        "results"
    ]
    
    missing_dirs = []
    missing_init_files = []
    existing_init_files = []
    
    # 1. 디렉토리 존재 확인
    for dir_path in required_dirs:
        full_path = Path(dir_path)
        init_file = full_path / "__init__.py"
        
        if not full_path.exists():
            missing_dirs.append(dir_path)
            print(f"❌ 디렉토리 없음: {dir_path}")
        elif not init_file.exists():
            missing_init_files.append(str(init_file))
            print(f"❌ __init__.py 없음: {init_file}")
        else:
            existing_init_files.append(str(init_file))
            print(f"✅ 존재함: {init_file}")
    
    print("\n" + "=" * 60)
    print("📊 검사 결과 요약")
    print("=" * 60)
    print(f"✅ 존재하는 __init__.py: {len(existing_init_files)}개")
    print(f"❌ 누락된 디렉토리: {len(missing_dirs)}개")
    print(f"❌ 누락된 __init__.py: {len(missing_init_files)}개")
    
    if missing_dirs:
        print(f"\n🚨 누락된 디렉토리들:")
        for dir_path in missing_dirs:
            print(f"   - {dir_path}")
    
    if missing_init_files:
        print(f"\n🚨 누락된 __init__.py 파일들:")
        for init_file in missing_init_files:
            print(f"   - {init_file}")
    
    return missing_dirs, missing_init_files

def create_missing_directories_and_files():
    """누락된 디렉토리와 __init__.py 파일들 생성"""
    
    missing_dirs, missing_init_files = check_and_create_init_files()
    
    if not missing_dirs and not missing_init_files:
        print("\n🎉 모든 필요한 파일이 존재합니다!")
        return
    
    print("\n" + "=" * 60)
    print("🔧 자동 수정 시작")
    print("=" * 60)
    
    # 누락된 디렉토리 생성
    if missing_dirs:
        print("\n📁 누락된 디렉토리 생성 중...")
        for dir_path in missing_dirs:
            try:
                Path(dir_path).mkdir(parents=True, exist_ok=True)
                print(f"✅ 디렉토리 생성: {dir_path}")
                
                # __init__.py 파일도 함께 생성
                init_file = Path(dir_path) / "__init__.py"
                init_content = get_init_content(dir_path)
                with open(init_file, 'w', encoding='utf-8') as f:
                    f.write(init_content)
                print(f"✅ __init__.py 생성: {init_file}")
                
            except Exception as e:
                print(f"❌ 디렉토리 생성 실패 {dir_path}: {e}")
    
    # 누락된 __init__.py 파일 생성
    if missing_init_files:
        print("\n📄 누락된 __init__.py 파일 생성 중...")
        for init_file in missing_init_files:
            try:
                dir_path = str(Path(init_file).parent)
                init_content = get_init_content(dir_path)
                
                with open(init_file, 'w', encoding='utf-8') as f:
                    f.write(init_content)
                print(f"✅ __init__.py 생성: {init_file}")
                
            except Exception as e:
                print(f"❌ 파일 생성 실패 {init_file}: {e}")

def get_init_content(dir_path):
    """디렉토리에 맞는 __init__.py 내용 생성"""
    
    if dir_path == "dvd_lite":
        return '''# dvd_lite/__init__.py
"""
DVD-Lite 패키지
경량화된 드론 보안 테스트 프레임워크
"""

__version__ = "1.0.0"
__author__ = "DVD-Lite Team"
__description__ = "경량화된 드론 보안 테스트 및 CTI 수집 프레임워크"

try:
    from .main import DVDLite, BaseAttack, AttackResult, AttackType, AttackStatus
    from .cti import SimpleCTI, ThreatIndicator
    from .attacks import register_all_attacks
except ImportError:
    # 일부 모듈이 없을 경우 기본 클래스만 import
    pass

__all__ = [
    "DVDLite",
    "BaseAttack", 
    "AttackResult",
    "AttackType",
    "AttackStatus",
    "SimpleCTI",
    "ThreatIndicator",
    "register_all_attacks"
]
'''
    
    elif dir_path == "dvd_lite/dvd_attacks":
        return '''# dvd_lite/dvd_attacks/__init__.py
"""
DVD 공격 시나리오 통합 패키지
"""

try:
    # 핵심 컴포넌트
    from .core import (
        AttackType, DVDAttackTactic, DVDFlightState,
        AttackDifficulty, AttackStatus, DVDAttackScenario,
        BaseAttack, AttackResult
    )
    
    # 등록 및 관리 시스템
    from .registry import (
        register_all_dvd_attacks,
        get_attacks_by_tactic, 
        get_attacks_by_difficulty,
        get_attacks_by_flight_state, 
        get_attack_info
    )
    
    # 공격 카테고리별 모듈
    from .reconnaissance import *
    from .protocol_tampering import *
    from .denial_of_service import *
    from .injection import *
    from .exfiltration import *
    from .firmware_attacks import *
    
except ImportError as e:
    print(f"Warning: DVD attacks import error: {e}")
    pass

__all__ = [
    'AttackType', 'DVDAttackTactic', 'DVDFlightState',
    'AttackDifficulty', 'AttackStatus', 'DVDAttackScenario',
    'BaseAttack', 'AttackResult',
    'register_all_dvd_attacks',
    'get_attacks_by_tactic', 
    'get_attacks_by_difficulty',
    'get_attacks_by_flight_state',
    'get_attack_info'
]
'''
    
    elif dir_path == "dvd_lite/dvd_attacks/core":
        return '''# dvd_lite/dvd_attacks/core/__init__.py
"""
DVD 공격 시스템 핵심 컴포넌트
"""

from .enums import (
    AttackType, DVDAttackTactic, DVDFlightState, 
    AttackDifficulty, AttackStatus
)
from .scenario import DVDAttackScenario
from .attack_base import BaseAttack, AttackResult

__all__ = [
    'AttackType',
    'DVDAttackTactic', 
    'DVDFlightState',
    'AttackDifficulty',
    'AttackStatus',
    'DVDAttackScenario',
    'BaseAttack',
    'AttackResult'
]
'''
    
    elif dir_path == "dvd_lite/dvd_attacks/reconnaissance":
        return '''# dvd_lite/dvd_attacks/reconnaissance/__init__.py
"""
정찰 공격 모듈
"""

try:
    from .wifi_discovery import WiFiNetworkDiscovery
    from .mavlink_discovery import MAVLinkServiceDiscovery
    from .component_enumeration import DroneComponentEnumeration
    from .camera_discovery import CameraStreamDiscovery
    
    __all__ = [
        'WiFiNetworkDiscovery',
        'MAVLinkServiceDiscovery', 
        'DroneComponentEnumeration',
        'CameraStreamDiscovery'
    ]
except ImportError:
    __all__ = []
'''
    
    elif dir_path == "dvd_lite/dvd_attacks/protocol_tampering":
        return '''# dvd_lite/dvd_attacks/protocol_tampering/__init__.py
"""
프로토콜 변조 공격 모듈
"""

try:
    from .gps_spoofing import GPSSpoofing
    from .mavlink_injection import MAVLinkPacketInjection
    from .rf_jamming import RadioFrequencyJamming
    
    __all__ = [
        'GPSSpoofing',
        'MAVLinkPacketInjection',
        'RadioFrequencyJamming'
    ]
except ImportError:
    __all__ = []
'''
    
    elif dir_path == "dvd_lite/dvd_attacks/denial_of_service":
        return '''# dvd_lite/dvd_attacks/denial_of_service/__init__.py
"""
서비스 거부 공격 모듈
"""

try:
    from .mavlink_flood import MAVLinkFloodAttack
    from .wifi_deauth import WiFiDeauthenticationAttack
    from .resource_exhaustion import CompanionComputerResourceExhaustion
    
    __all__ = [
        'MAVLinkFloodAttack',
        'WiFiDeauthenticationAttack',
        'CompanionComputerResourceExhaustion'
    ]
except ImportError:
    __all__ = []
'''
    
    elif dir_path == "dvd_lite/dvd_attacks/injection":
        return '''# dvd_lite/dvd_attacks/injection/__init__.py
"""
주입 공격 모듈
"""

try:
    from .flight_plan import FlightPlanInjection
    from .parameter_manipulation import ParameterManipulation
    from .firmware_manipulation import FirmwareUploadManipulation
    
    __all__ = [
        'FlightPlanInjection',
        'ParameterManipulation',
        'FirmwareUploadManipulation'
    ]
except ImportError:
    __all__ = []
'''
    
    elif dir_path == "dvd_lite/dvd_attacks/exfiltration":
        return '''# dvd_lite/dvd_attacks/exfiltration/__init__.py
"""
데이터 탈취 공격 모듈
"""

try:
    from .telemetry_data import TelemetryDataExfiltration
    from .flight_logs import FlightLogExtraction
    from .video_hijacking import VideoStreamHijacking
    
    __all__ = [
        'TelemetryDataExfiltration',
        'FlightLogExtraction',
        'VideoStreamHijacking'
    ]
except ImportError:
    __all__ = []
'''
    
    elif dir_path == "dvd_lite/dvd_attacks/firmware_attacks":
        return '''# dvd_lite/dvd_attacks/firmware_attacks/__init__.py
"""
펌웨어 공격 모듈
"""

try:
    from .bootloader_exploit import BootloaderExploit
    from .rollback_attack import FirmwareRollbackAttack
    from .secure_boot_bypass import SecureBootBypass
    
    __all__ = [
        'BootloaderExploit',
        'FirmwareRollbackAttack',
        'SecureBootBypass'
    ]
except ImportError:
    __all__ = []
'''
    
    elif dir_path == "dvd_lite/dvd_attacks/registry":
        return '''# dvd_lite/dvd_attacks/registry/__init__.py
"""
DVD 공격 등록 관리 시스템
"""

try:
    from .management import (
        register_all_dvd_attacks, 
        get_attacks_by_tactic, 
        get_attacks_by_difficulty, 
        get_attacks_by_flight_state,
        get_attack_info
    )
    
    __all__ = [
        'register_all_dvd_attacks',
        'get_attacks_by_tactic',
        'get_attacks_by_difficulty', 
        'get_attacks_by_flight_state',
        'get_attack_info'
    ]
except ImportError:
    __all__ = []
'''
    
    elif dir_path == "dvd_lite/dvd_attacks/utils":
        return '''# dvd_lite/dvd_attacks/utils/__init__.py
"""
DVD 공격 시스템 유틸리티
"""

try:
    from .common import (
        generate_fake_mac_address, 
        generate_fake_ip_address,
        simulate_network_delay, 
        async_network_delay,
        calculate_success_probability, 
        generate_ioc_id,
        format_duration, 
        classify_risk_level
    )
    
    __all__ = [
        'generate_fake_mac_address',
        'generate_fake_ip_address', 
        'simulate_network_delay',
        'async_network_delay',
        'calculate_success_probability',
        'generate_ioc_id',
        'format_duration',
        'classify_risk_level'
    ]
except ImportError:
    __all__ = []
'''
    
    elif dir_path == "dvd_connector":
        return '''# dvd_connector/__init__.py
"""
DVD-Lite ↔ Damn Vulnerable Drone 연계 모듈
"""

try:
    from .connector import DVDConnector, DVDEnvironment
    from .real_attacks import RealAttackAdapter
    from .network_scanner import DVDNetworkScanner
    from .safety_checker import SafetyChecker
    
    __all__ = [
        "DVDConnector",
        "DVDEnvironment", 
        "RealAttackAdapter",
        "DVDNetworkScanner",
        "SafetyChecker"
    ]
except ImportError:
    __all__ = []
'''
    
    else:
        # 기본 __init__.py 내용
        return f'''# {dir_path}/__init__.py
"""
{dir_path.replace('/', '.')} 모듈
"""

# 이 디렉토리의 모듈들을 import 하세요
'''

def check_current_structure():
    """현재 파일 구조 확인"""
    print("\n" + "=" * 60)
    print("📁 현재 파일 구조")
    print("=" * 60)
    
    current_dir = Path(".")
    
    def print_tree(path, prefix="", max_depth=3, current_depth=0):
        if current_depth >= max_depth:
            return
            
        items = sorted(path.iterdir())
        dirs = [item for item in items if item.is_dir() and not item.name.startswith('.')]
        files = [item for item in items if item.is_file() and item.name.endswith('.py')]
        
        for i, item in enumerate(dirs + files):
            is_last = i == len(dirs + files) - 1
            current_prefix = "└── " if is_last else "├── "
            print(f"{prefix}{current_prefix}{item.name}")
            
            if item.is_dir():
                next_prefix = prefix + ("    " if is_last else "│   ")
                print_tree(item, next_prefix, max_depth, current_depth + 1)
    
    print_tree(current_dir)

def main():
    """메인 함수"""
    print("🔍 DVD-Lite 프로젝트 구조 검사 도구")
    print("=" * 60)
    
    # 현재 구조 확인
    check_current_structure()
    
    # __init__.py 파일 검사
    create_missing_directories_and_files()
    
    # 재검사
    print("\n" + "=" * 60)
    print("🔍 재검사 결과")
    print("=" * 60)
    
    missing_dirs, missing_init_files = check_and_create_init_files()
    
    if not missing_dirs and not missing_init_files:
        print("\n🎉 모든 필요한 파일이 생성되었습니다!")
        print("\n🚀 이제 다음 명령을 실행해보세요:")
        print("   python3 advanced_start.py")
        print("   또는")
        print("   python3 quick_start.py")
    else:
        print("\n⚠️  일부 파일이 여전히 누락되었습니다.")
        print("수동으로 생성하거나 스크립트를 다시 실행해보세요.")

if __name__ == "__main__":
    main()