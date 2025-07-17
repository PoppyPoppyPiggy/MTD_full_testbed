#!/usr/bin/env python3
"""
DVD-Lite ↔ Damn Vulnerable Drone 통합 테스트베드 설치 스크립트
논문 작성을 위한 완전한 실험 환경 구축

사용법:
python setup_integrated_testbed.py --install-all
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path
import json

def print_banner():
    """설치 배너 출력"""
    banner = """
╔══════════════════════════════════════════════════════════════════╗
║           DVD-Lite ↔ Damn Vulnerable Drone 통합 테스트베드        ║
║                     자동 설치 및 설정 도구                        ║
║                                                                  ║
║  🎯 논문 작성을 위한 완전한 드론 보안 연구 플랫폼                   ║
║  🔗 GitHub: PoppyPoppyPiggy/MTD_full_testbed                     ║
║  🔗 연동: nicholasaleks/Damn-Vulnerable-Drone                    ║
╚══════════════════════════════════════════════════════════════════╝
"""
    print(banner)

def check_python_version():
    """Python 버전 확인"""
    if sys.version_info < (3, 7):
        print("❌ Python 3.7 이상이 필요합니다.")
        print(f"현재 버전: {sys.version}")
        return False
    
    print(f"✅ Python 버전 확인: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    return True

def create_directory_structure():
    """디렉토리 구조 생성"""
    print("\n📁 디렉토리 구조 생성 중...")
    
    directories = [
        "dvd_lite",
        "dvd_lite/dvd_attacks",
        "dvd_lite/dvd_attacks/core",
        "dvd_lite/dvd_attacks/reconnaissance", 
        "dvd_lite/dvd_attacks/protocol_tampering",
        "dvd_lite/dvd_attacks/denial_of_service",
        "dvd_lite/dvd_attacks/injection",
        "dvd_lite/dvd_attacks/exfiltration",
        "dvd_lite/dvd_attacks/firmware_attacks",
        "dvd_lite/dvd_attacks/utils",
        "dvd_lite/dvd_attacks/registry",
        "dvd_connector",
        "scripts",
        "configs",
        "data",
        "results",
        "logs",
        "tests"
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"📂 생성: {directory}")
    
    print("✅ 디렉토리 구조 생성 완료")

def create_init_files():
    """__init__.py 파일들 생성"""
    print("\n📝 __init__.py 파일들 생성 중...")
    
    init_files = [
        "dvd_lite/__init__.py",
        "dvd_lite/dvd_attacks/__init__.py",
        "dvd_lite/dvd_attacks/core/__init__.py",
        "dvd_lite/dvd_attacks/reconnaissance/__init__.py",
        "dvd_lite/dvd_attacks/protocol_tampering/__init__.py",
        "dvd_lite/dvd_attacks/denial_of_service/__init__.py",
        "dvd_lite/dvd_attacks/injection/__init__.py",
        "dvd_lite/dvd_attacks/exfiltration/__init__.py",
        "dvd_lite/dvd_attacks/firmware_attacks/__init__.py",
        "dvd_lite/dvd_attacks/utils/__init__.py",
        "dvd_lite/dvd_attacks/registry/__init__.py",
        "dvd_connector/__init__.py",
        "scripts/__init__.py",
        "configs/__init__.py",
        "data/__init__.py",
        "results/__init__.py",
        "tests/__init__.py"
    ]
    
    for init_file in init_files:
        init_path = Path(init_file)
        if not init_path.exists():
            init_path.write_text(f'# {init_file}\n"""패키지 초기화 파일"""\n', encoding='utf-8')
            print(f"📄 생성: {init_file}")
    
    print("✅ __init__.py 파일 생성 완료")

def install_basic_dependencies():
    """기본 의존성 설치"""
    print("\n📦 기본 Python 패키지 설치 중...")
    
    basic_packages = [
        "asyncio",
        "dataclasses;python_version<'3.7'",
        "typing-extensions",
        "pathlib2;python_version<'3.4'"
    ]
    
    for package in basic_packages:
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", package], 
                         check=True, capture_output=True)
            print(f"✅ 설치: {package}")
        except subprocess.CalledProcessError as e:
            print(f"⚠️ 설치 실패: {package} - {e}")

def install_optional_dependencies():
    """선택적 의존성 설치"""
    print("\n📦 선택적 패키지 설치 중...")
    
    optional_packages = {
        "aiohttp": "HTTP 클라이언트 (DVD GCS 연동용)",
        "paramiko": "SSH 클라이언트 (DVD Companion Computer 연동용)",
        "pymavlink": "MAVLink 프로토콜 (Flight Controller 연동용)",
        "psutil": "시스템 모니터링",
        "pandas": "데이터 분석 (논문용)",
        "matplotlib": "그래프 생성 (논문용)",
        "websockets": "실시간 대시보드",
        "paho-mqtt": "MQTT 통신"
    }
    
    installed_packages = []
    failed_packages = []
    
    for package, description in optional_packages.items():
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", package], 
                         check=True, capture_output=True)
            print(f"✅ 설치: {package} - {description}")
            installed_packages.append(package)
        except subprocess.CalledProcessError as e:
            print(f"⚠️ 설치 실패: {package} - {description}")
            failed_packages.append(package)
    
    print(f"\n📊 설치 결과: {len(installed_packages)}개 성공, {len(failed_packages)}개 실패")
    
    if failed_packages:
        print("⚠️ 실패한 패키지들은 해당 기능이 제한될 수 있습니다.")
        print("필요시 수동으로 설치하세요:")
        for package in failed_packages:
            print(f"   pip install {package}")

def create_requirements_file():
    """requirements.txt 생성"""
    print("\n📄 requirements.txt 생성 중...")
    
    requirements_content = """# DVD-Lite ↔ Damn Vulnerable Drone 통합 테스트베드 의존성

# 기본 패키지
asyncio-3.4.3; python_version < "3.7"
dataclasses; python_version < "3.7"
typing-extensions
pathlib2; python_version < "3.4"

# DVD 연동 패키지
aiohttp>=3.8.0
paramiko>=2.7.0
pymavlink>=2.4.0

# 시스템 모니터링
psutil>=5.8.0

# 데이터 분석 (논문용)
pandas>=1.3.0
matplotlib>=3.5.0
numpy>=1.21.0

# 웹 및 통신
websockets>=10.0
paho-mqtt>=1.6.0

# 개발 및 테스트
pytest>=6.0.0
pytest-asyncio>=0.18.0

# 선택적 패키지 (실제 하드웨어 연동시)
# scapy>=2.4.5  # 네트워크 패킷 분석
# pyserial>=3.5  # 시리얼 통신
# opencv-python>=4.5.0  # 비디오 스트림 처리
"""
    
    with open("requirements.txt", "w", encoding="utf-8") as f:
        f.write(requirements_content)
    
    print("✅ requirements.txt 생성 완료")

def create_config_files():
    """설정 파일들 생성"""
    print("\n⚙️ 설정 파일들 생성 중...")
    
    # 기본 DVD 설정
    dvd_config = {
        "dvd_hosts": {
            "companion_computer": "10.13.0.3",
            "flight_controller": "10.13.0.2",
            "ground_station": "10.13.0.4"
        },
        "authentication": {
            "ssh_username": "dvd",
            "ssh_password": "dvdpassword"
        },
        "communication": {
            "mavlink_port": 5760,
            "http_port": 8080,
            "telemetry_frequency": 50
        },
        "safety": {
            "max_concurrent_attacks": 5,
            "attack_timeout": 300,
            "auto_stop_on_error": True
        }
    }
    
    # 실험 설정
    experiment_config = {
        "modes": {
            "basic": {
                "attacks": ["wifi_network_discovery", "gps_spoofing", "mavlink_flood"],
                "duration": 300
            },
            "full": {
                "attacks": "all_available",
                "duration": 600
            },
            "continuous": {
                "attack_pool": ["wifi_network_discovery", "telemetry_exfiltration"],
                "duration": 1800,
                "round_interval": 60
            }
        },
        "output": {
            "base_directory": "results",
            "formats": ["json", "csv", "markdown"],
            "include_raw_data": True
        }
    }
    
    # 대시보드 설정
    dashboard_config = {
        "websocket": {
            "host": "localhost",
            "port": 8765
        },
        "mqtt": {
            "host": "localhost",
            "port": 1883,
            "topics": {
                "control": "dvd/control/+",
                "status": "dvd/status/+",
                "data": "dvd/data/+"
            }
        },
        "update_intervals": {
            "telemetry": 1.0,
            "system_metrics": 5.0,
            "attack_status": 0.5
        }
    }
    
    # 설정 파일 저장
    configs = {
        "configs/dvd_config.json": dvd_config,
        "configs/experiment_config.json": experiment_config,
        "configs/dashboard_config.json": dashboard_config
    }
    
    for config_file, config_data in configs.items():
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=2, ensure_ascii=False)
        print(f"📄 생성: {config_file}")
    
    print("✅ 설정 파일 생성 완료")

def create_test_scripts():
    """테스트 스크립트 생성"""
    print("\n🧪 테스트 스크립트 생성 중...")
    
    # 기본 연결 테스트
    basic_test = '''#!/usr/bin/env python3
"""
기본 연결 테스트
"""
import asyncio
import sys
from pathlib import Path

# 프로젝트 루트 경로 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

async def test_basic_imports():
    """기본 import 테스트"""
    try:
        from dvd_lite.main import DVDLite
        from dvd_lite.cti import SimpleCTI
        print("✅ DVD-Lite 기본 모듈 import 성공")
        return True
    except ImportError as e:
        print(f"❌ DVD-Lite import 실패: {e}")
        return False

async def test_dvd_lite_creation():
    """DVD-Lite 인스턴스 생성 테스트"""
    try:
        from dvd_lite.main import DVDLite
        dvd = DVDLite()
        print("✅ DVD-Lite 인스턴스 생성 성공")
        return True
    except Exception as e:
        print(f"❌ DVD-Lite 생성 실패: {e}")
        return False

async def test_cti_creation():
    """CTI 수집기 생성 테스트"""
    try:
        from dvd_lite.cti import SimpleCTI
        cti = SimpleCTI()
        summary = cti.get_summary()
        print(f"✅ CTI 수집기 생성 성공: {summary['total_indicators']}개 지표")
        return True
    except Exception as e:
        print(f"❌ CTI 생성 실패: {e}")
        return False

async def main():
    """메인 테스트 함수"""
    print("🧪 DVD-Lite 기본 테스트 시작")
    print("=" * 40)
    
    tests = [
        test_basic_imports,
        test_dvd_lite_creation,
        test_cti_creation
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if await test():
            passed += 1
    
    print("=" * 40)
    print(f"📊 테스트 결과: {passed}/{total} 통과")
    
    if passed == total:
        print("🎉 모든 기본 테스트 통과!")
        return True
    else:
        print("❌ 일부 테스트 실패")
        return False

if __name__ == "__main__":
    asyncio.run(main())
'''
    
    # 통합 테스트
    integration_test = '''#!/usr/bin/env python3
"""
통합 테스트
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

async def test_attack_registration():
    """공격 등록 테스트"""
    try:
        from dvd_lite.main import DVDLite
        from dvd_lite.dvd_attacks import register_all_dvd_attacks
        
        dvd = DVDLite()
        attacks = register_all_dvd_attacks()
        
        print(f"✅ 공격 등록 성공: {len(attacks)}개")
        return True
    except Exception as e:
        print(f"❌ 공격 등록 실패: {e}")
        return False

async def test_single_attack():
    """단일 공격 테스트"""
    try:
        from dvd_lite.main import DVDLite
        from dvd_lite.dvd_attacks import register_all_dvd_attacks
        
        dvd = DVDLite()
        register_all_dvd_attacks()
        
        result = await dvd.run_attack("wifi_network_discovery")
        
        print(f"✅ 공격 실행 성공: {result.attack_name}")
        print(f"   상태: {result.status.value}")
        print(f"   IOCs: {len(result.iocs)}개")
        return True
    except Exception as e:
        print(f"❌ 공격 실행 실패: {e}")
        return False

async def main():
    """메인 테스트"""
    print("🧪 DVD-Lite 통합 테스트 시작")
    print("=" * 40)
    
    tests = [
        test_attack_registration,
        test_single_attack
    ]
    
    passed = 0
    for test in tests:
        if await test():
            passed += 1
    
    print("=" * 40)
    print(f"📊 통합 테스트 결과: {passed}/{len(tests)} 통과")

if __name__ == "__main__":
    asyncio.run(main())
'''
    
    # 테스트 파일 저장
    test_files = {
        "tests/test_basic.py": basic_test,
        "tests/test_integration.py": integration_test
    }
    
    for test_file, test_content in test_files.items():
        with open(test_file, "w", encoding="utf-8") as f:
            f.write(test_content)
        
        # 실행 권한 부여 (Unix/Linux)
        if sys.platform != "win32":
            os.chmod(test_file, 0o755)
        
        print(f"🧪 생성: {test_file}")
    
    print("✅ 테스트 스크립트 생성 완료")

def create_run_scripts():
    """실행 스크립트들 생성"""
    print("\n🚀 실행 스크립트 생성 중...")
    
    # 빠른 시작 스크립트
    quick_start = '''#!/usr/bin/env python3
"""
DVD-Lite 빠른 시작 스크립트
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

async def main():
    """메인 함수"""
    try:
        from integrated_dvd_testbed import main as testbed_main
        print("🚀 통합 테스트베드 시작")
        await testbed_main()
    except ImportError:
        print("❌ 통합 테스트베드를 찾을 수 없습니다.")
        print("먼저 setup_integrated_testbed.py를 실행하세요.")
    except Exception as e:
        print(f"❌ 실행 오류: {e}")

if __name__ == "__main__":
    asyncio.run(main())
'''
    
    # 테스트 실행 스크립트
    run_tests = '''#!/usr/bin/env python3
"""
모든 테스트 실행
"""
import subprocess
import sys
from pathlib import Path

def run_test(test_file):
    """테스트 실행"""
    print(f"🧪 테스트 실행: {test_file}")
    try:
        result = subprocess.run([sys.executable, test_file], 
                              capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"✅ {test_file} 통과")
            print(result.stdout)
            return True
        else:
            print(f"❌ {test_file} 실패")
            print(result.stderr)
            return False
            
    except Exception as e:
        print(f"❌ {test_file} 실행 오류: {e}")
        return False

def main():
    """메인 함수"""
    print("🧪 모든 테스트 실행")
    print("=" * 40)
    
    test_files = [
        "tests/test_basic.py",
        "tests/test_integration.py"
    ]
    
    passed = 0
    total = len(test_files)
    
    for test_file in test_files:
        if Path(test_file).exists():
            if run_test(test_file):
                passed += 1
        else:
            print(f"⚠️ 테스트 파일 없음: {test_file}")
    
    print("=" * 40)
    print(f"📊 전체 테스트 결과: {passed}/{total} 통과")
    
    if passed == total:
        print("🎉 모든 테스트 통과!")
    else:
        print("❌ 일부 테스트 실패")

if __name__ == "__main__":
    main()
'''
    
    # 스크립트 파일 저장
    scripts = {
        "quick_start_testbed.py": quick_start,
        "run_all_tests.py": run_tests
    }
    
    for script_file, script_content in scripts.items():
        with open(script_file, "w", encoding="utf-8") as f:
            f.write(script_content)
        
        # 실행 권한 부여
        if sys.platform != "win32":
            os.chmod(script_file, 0o755)
        
        print(f"🚀 생성: {script_file}")
    
    print("✅ 실행 스크립트 생성 완료")

def create_documentation():
    """문서 생성"""
    print("\n📚 문서 생성 중...")
    
    readme_content = '''# DVD-Lite ↔ Damn Vulnerable Drone 통합 테스트베드

논문 작성을 위한 완전한 드론 보안 연구 플랫폼

## 🎯 프로젝트 개요

이 프로젝트는 DVD-Lite 공격 프레임워크와 실제 Damn Vulnerable Drone 하드웨어를 연동하여, 드론 보안 연구를 위한 완전한 테스트베드를 제공합니다.

### 주요 기능
- 🎯 19개 완전 구현된 드론 공격 시나리오
- 🔗 실제 DVD 하드웨어와의 실시간 연동
- 📊 실시간 CTI 수집 및 분석
- 🌐 WebSocket 기반 실시간 대시보드
- 📝 논문 작성을 위한 체계적 데이터 수집

## 🚀 빠른 시작

### 1. 환경 설정
```bash
# 자동 설치
python setup_integrated_testbed.py --install-all

# 기본 테스트
python run_all_tests.py
```

### 2. 기본 실행
```bash
# 기본 실험 (5분)
python integrated_dvd_testbed.py

# 전체 실험 (10분)
python integrated_dvd_testbed.py --mode full --duration 600

# 연속 실험 (30분)
python integrated_dvd_testbed.py --mode continuous --duration 1800
```

### 3. 실제 DVD 하드웨어 연동
```bash
# DVD 하드웨어 설정
python integrated_dvd_testbed.py --dvd-host 10.13.0.3 --dvd-fc-host 10.13.0.2

# 대화형 모드
python integrated_dvd_testbed.py --mode targeted --target-category reconnaissance
```

## 📁 프로젝트 구조

```
├── dvd_lite/                    # DVD-Lite 프레임워크
│   ├── main.py                  # 메인 엔진
│   ├── cti.py                   # CTI 수집기
│   └── dvd_attacks/             # 공격 시나리오들
│       ├── reconnaissance/      # 정찰 공격
│       ├── protocol_tampering/  # 프로토콜 조작
│       ├── denial_of_service/   # DoS 공격
│       ├── injection/           # 주입 공격
│       ├── exfiltration/        # 데이터 탈취
│       └── firmware_attacks/    # 펌웨어 공격
├── dvd_connector/               # DVD 하드웨어 연동
├── integrated_dvd_testbed.py    # 통합 테스트베드 메인
├── configs/                     # 설정 파일들
├── results/                     # 실험 결과
└── tests/                       # 테스트 코드

```

## 🧪 공격 시나리오

### 정찰 (Reconnaissance)
- WiFi 네트워크 발견
- MAVLink 서비스 발견
- 드론 컴포넌트 열거
- 카메라 스트림 발견

### 프로토콜 조작 (Protocol Tampering)
- GPS 스푸핑
- MAVLink 패킷 주입
- RF 재밍

### 서비스 거부 (Denial of Service)
- MAVLink 플러드 공격
- WiFi 인증 해제
- 자원 고갈 공격

### 주입 (Injection)
- 비행 계획 주입
- 파라미터 조작
- 펌웨어 업로드 조작

### 데이터 탈취 (Exfiltration)
- 텔레메트리 데이터 탈취
- 비행 로그 추출
- 비디오 스트림 하이재킹

### 펌웨어 공격 (Firmware Attacks)
- 부트로더 취약점 공격
- 펌웨어 롤백 공격
- 보안 부팅 우회

## 📊 실험 모드

### Basic 모드
- 5개 핵심 공격 시나리오
- 5분 실행
- 초보자용

### Full 모드
- 19개 모든 공격 시나리오
- 10분 실행
- 완전한 보안 평가

### Continuous 모드
- 지정 시간 동안 반복 실행
- 장기간 모니터링
- 시스템 안정성 테스트

### Targeted 모드
- 특정 공격 카테고리 집중
- 연구 목적별 실험
- 세부 분석

## 🔗 하드웨어 연동

### 필수 하드웨어
- Damn Vulnerable Drone (https://github.com/nicholasaleks/Damn-Vulnerable-Drone)
- Raspberry Pi (Companion Computer)
- Flight Controller (ArduPilot/PX4)
- Ground Control Station

### 네트워크 설정
```
10.13.0.2 - Flight Controller
10.13.0.3 - Companion Computer  
10.13.0.4 - Ground Control Station
```

### 필수 서비스
- SSH 서비스 (포트 22)
- MAVLink 서비스 (포트 5760)
- HTTP 서비스 (포트 8080)

## 📈 결과 분석

### 자동 생성 보고서
- JSON 형식 원시 데이터
- Markdown 형식 요약 보고서
- CSV 형식 분석 데이터

###