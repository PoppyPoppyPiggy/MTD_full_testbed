# DVD (Damn Vulnerable Drone) 공격 시나리오 테스트베드

드론 보안 테스트를 위한 종합적인 모듈화된 공격 시나리오 프레임워크 및 CTI 수집 시스템

[![Python](https://img.shields.io/badge/Python-3.7+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![DVD Compatible](https://img.shields.io/badge/DVD-Compatible-orange.svg)](https://github.com/nicholasaleks/Damn-Vulnerable-Drone)

## 🎯 개요

이 프로젝트는 [Damn Vulnerable Drone (DVD)](https://github.com/nicholasaleks/Damn-Vulnerable-Drone)과 연동하여 실제적인 드론 보안 테스트 환경을 제공하는 종합적인 테스트베드입니다. 19개의 완전 구현된 공격 시나리오와 실시간 CTI(Cyber Threat Intelligence) 수집 기능을 통해 연구자와 보안 전문가들이 안전한 환경에서 드론 보안을 학습하고 연구할 수 있습니다.

### 🌟 주요 특징

- **19개 완전 구현된 공격 시나리오**: 정찰부터 펌웨어 공격까지 6개 주요 전술 카테고리
- **실시간 CTI 수집**: IOC 추출, 공격 패턴 분석, JSON/CSV 내보내기
- **DVD 연동 기능**: Damn Vulnerable Drone 환경과의 완전한 호환성
- **안전성 검사기**: 실제 하드웨어 보호 및 안전한 테스트 환경 보장
- **네트워크 스캐너**: 드론 네트워크 환경 자동 탐지 및 분석
- **모듈화 설계**: 각 공격을 독립적으로 실행 및 확장 가능
- **대화형 모드**: 사용자 친화적인 인터페이스

## 📋 목차

- [설치 및 설정](#-설치-및-설정)
- [빠른 시작](#-빠른-시작)
- [DVD 연동 설정](#-dvd-연동-설정)
- [공격 시나리오](#-공격-시나리오)
- [CTI 수집 및 분석](#-cti-수집-및-분석)
- [안전성 및 보안](#-안전성-및-보안)
- [고급 사용법](#-고급-사용법)
- [문제 해결](#-문제-해결)
- [기여하기](#-기여하기)

## 🚀 설치 및 설정

### 전제 조건

- Python 3.7 이상
- Docker (DVD 연동 시)
- Linux/macOS 권장 (Windows WSL 지원)

### 자동 설정 (권장)

```bash
# 저장소 클론
git clone https://github.com/PoppyPoppyPiggy/MTD_full_testbed.git
cd MTD_full_testbed

# 자동 설정 스크립트 실행
chmod +x setup.sh
./setup.sh
```

### 수동 설정

```bash
# 의존성 설치
pip install -r requirements.txt

# 기본 구조 확인
python find_init.py

# 누락된 모듈 생성 (필요시)
python fix_actual_cti.py
```

### 가상환경 설정 (권장)

```bash
python3 -m venv dvd_env
source dvd_env/bin/activate  # Linux/Mac
# dvd_env\Scripts\activate   # Windows

pip install -r requirements.txt
```

## ⚡ 빠른 시작

### 1. 기본 테스트

```bash
# 기본 기능 테스트
python tests/test_basic.py

# 모든 데모 실행
python quick_start.py
```

### 2. 단일 공격 실행

```bash
# 단일 공격 데모
python quick_start.py single

# 특정 공격 실행 (대화형)
python quick_start.py interactive
```

### 3. 여러 공격 시나리오

```bash
# 여러 공격 데모
python quick_start.py multiple

# 전술별 공격 실행
python quick_start.py tactic

# 난이도별 공격 실행
python quick_start.py difficulty
```

### 4. 프로그래밍 방식 사용

```python
import asyncio
from dvd_lite.main import DVDLite
from dvd_lite.dvd_attacks.registry.management import register_all_dvd_attacks

async def main():
    # DVD-Lite 인스턴스 생성
    dvd = DVDLite()
    
    # 공격 모듈 등록
    register_all_dvd_attacks()
    
    # 공격 실행
    result = await dvd.run_attack("wifi_network_discovery")
    print(f"결과: {result.status}")
    print(f"IOCs: {result.iocs}")

asyncio.run(main())
```

## 🔗 DVD 연동 설정

### Damn Vulnerable Drone 환경 연결

```python
from dvd_connector.connector import DVDConnector, DVDEnvironment, DVDConnectionConfig
from dvd_connector.safety_checker import SafetyChecker

async def connect_to_dvd():
    # 안전성 검사
    checker = SafetyChecker()
    config = {"host": "localhost", "environment": "SIMULATION"}
    safety_result = await checker.comprehensive_safety_check(config)
    
    if not safety_result.is_safe_to_proceed:
        print("⚠️ 안전하지 않은 환경 감지")
        return
    
    # DVD 연결
    dvd_config = DVDConnectionConfig(
        environment=DVDEnvironment.HALF_BAKED,  # 또는 FULL_DEPLOY
        host="localhost",
        mavlink_port=14550
    )
    
    connector = DVDConnector(dvd_config)
    
    if await connector.connect():
        print("✅ DVD 연결 성공")
        
        # 텔레메트리 데이터 수집
        telemetry = await connector.get_telemetry()
        print(f"텔레메트리: {telemetry}")
        
        await connector.disconnect()
    else:
        print("❌ DVD 연결 실패")

asyncio.run(connect_to_dvd())
```

### DVD 환경 모드

1. **시뮬레이션 모드** (`DVDEnvironment.SIMULATION`)
   - 완전 가상 환경
   - 실제 DVD 없이 테스트 가능
   - 안전한 학습 및 개발

2. **Half-Baked 모드** (`DVDEnvironment.HALF_BAKED`)
   - Docker 컨테이너 기반
   - 네트워크 연결 가정
   - WiFi 시뮬레이션 없음

3. **Full-Deploy 모드** (`DVDEnvironment.FULL_DEPLOY`)
   - 완전한 DVD 환경
   - WiFi 시뮬레이션 포함
   - Kali Linux VM 권장

### DVD 네트워크 스캔

```python
from dvd_connector.network_scanner import DVDNetworkScanner

async def scan_dvd_network():
    scanner = DVDNetworkScanner()
    
    # DVD 네트워크 스캔
    result = await scanner.scan_network("10.13.0.0/24")
    
    print(scanner.generate_scan_report(result))
    
    # 드론 디바이스만 찾기
    drone_devices = await scanner.quick_drone_scan()
    print(f"드론 디바이스 {len(drone_devices)}개 발견")

asyncio.run(scan_dvd_network())
```

## 🎯 공격 시나리오

### 전술별 공격 분류

#### 1. 정찰 (RECONNAISSANCE) - 4개
- **WiFi 네트워크 발견**: 드론 WiFi 네트워크 열거
- **MAVLink 서비스 발견**: MAVLink 서비스 스캔 및 식별
- **드론 컴포넌트 열거**: 시스템 컴포넌트 상세 정보 수집
- **카메라 스트림 발견**: RTSP/HTTP 비디오 스트림 탐지

#### 2. 프로토콜 변조 (PROTOCOL_TAMPERING) - 3개
- **GPS 스푸핑**: GPS 신호 조작을 통한 위치 변조
- **MAVLink 패킷 주입**: 악성 MAVLink 메시지 주입
- **RF 재밍**: 무선 주파수 간섭을 통한 통신 차단

#### 3. 서비스 거부 (DENIAL_OF_SERVICE) - 3개
- **MAVLink 플러드**: MAVLink 서비스 과부하 공격
- **WiFi 인증 해제**: WiFi 연결 강제 차단
- **자원 고갈**: 컴패니언 컴퓨터 시스템 자원 고갈

#### 4. 주입 공격 (INJECTION) - 3개
- **비행 계획 주입**: 악성 웨이포인트 삽입
- **파라미터 조작**: 중요 시스템 설정 변조
- **펌웨어 업로드 조작**: 펌웨어 업데이트 과정 악용

#### 5. 데이터 탈취 (EXFILTRATION) - 3개
- **텔레메트리 데이터 탈취**: 민감한 비행 데이터 수집
- **비행 로그 추출**: 비행 기록 및 로그 파일 획득
- **비디오 스트림 하이재킹**: 실시간 비디오 스트림 탈취

#### 6. 펌웨어 공격 (FIRMWARE_ATTACKS) - 3개
- **부트로더 익스플로잇**: 부트로더 취약점 악용
- **펌웨어 롤백**: 취약한 이전 버전으로 다운그레이드
- **보안 부팅 우회**: 보안 부팅 메커니즘 무력화

### 난이도별 분류

- **🟢 초급 (BEGINNER)**: 6개 - 기본적인 스캔 및 정보 수집
- **🟡 중급 (INTERMEDIATE)**: 8개 - 프로토콜 조작 및 서비스 공격
- **🔴 고급 (ADVANCED)**: 5개 - 펌웨어 및 고급 공격 기법

### 공격 실행 예제

```python
# 전술별 공격 실행
from dvd_lite.dvd_attacks.registry.management import get_attacks_by_tactic, DVDAttackTactic

# 정찰 공격들 가져오기
recon_attacks = get_attacks_by_tactic(DVDAttackTactic.RECONNAISSANCE)
print(f"정찰 공격: {recon_attacks}")

# 특정 공격 정보 확인
from dvd_lite.dvd_attacks.registry.management import get_attack_info
attack_info = get_attack_info("gps_spoofing")
print(f"GPS 스푸핑 공격: {attack_info}")
```

## 📊 CTI 수집 및 분석

### CTI 수집기 사용

```python
from dvd_lite.main import DVDLite
from dvd_lite.cti import SimpleCTI

async def cti_collection_example():
    # CTI 수집기 설정
    cti = SimpleCTI({
        "confidence_threshold": 70,
        "export_format": "json"
    })
    
    # DVD-Lite에 CTI 수집기 등록
    dvd = DVDLite()
    dvd.register_cti_collector(cti)
    
    # 공격 실행 및 CTI 자동 수집
    result = await dvd.run_attack("wifi_network_discovery")
    
    # CTI 요약 정보
    summary = cti.get_summary()
    print(f"수집된 지표: {summary['total_indicators']}개")
    
    # JSON으로 내보내기
    json_file = cti.export_json("results/cti_analysis.json")
    print(f"CTI 데이터 저장: {json_file}")
    
    # CSV로 내보내기
    csv_file = cti.export_csv("results/cti_indicators.csv")
    print(f"IOC 데이터 저장: {csv_file}")

asyncio.run(cti_collection_example())
```

### CTI 데이터 구조

```json
{
  "metadata": {
    "export_time": "2024-12-14T10:30:00",
    "total_indicators": 45,
    "source": "dvd-lite"
  },
  "indicators": [
    {
      "ioc_type": "wifi_ssid",
      "value": "Drone_WiFi_Network",
      "confidence": 85,
      "attack_type": "reconnaissance",
      "timestamp": "2024-12-14T10:25:00"
    }
  ],
  "attack_patterns": {
    "reconnaissance_wifi_scan": {
      "success_rate": 0.85,
      "avg_response_time": 2.3,
      "ioc_count": 12
    }
  }
}
```

## 🛡️ 안전성 및 보안

### 안전성 검사

```python
from dvd_connector.safety_checker import SafetyChecker, quick_safety_check

# 빠른 안전성 검사
is_safe = await quick_safety_check({
    "host": "localhost",
    "environment": "SIMULATION"
})

if is_safe:
    print("✅ 안전한 환경 확인")
else:
    print("⚠️ 안전하지 않은 환경")

# 상세 안전성 검사
checker = SafetyChecker()
result = await checker.comprehensive_safety_check(config)
checker.print_safety_report(result)
```

### 안전성 수준

- **🟢 SAFE**: 완전한 시뮬레이션 환경
- **🟡 CAUTION**: 가상 환경, 기본 주의 필요
- **🟠 WARNING**: 실제 하드웨어 감지 가능성
- **🔴 DANGER**: 실제 드론 하드웨어 감지
- **⛔ BLOCKED**: 테스트 차단됨

### 보안 권장사항

1. **항상 격리된 네트워크에서 테스트**
2. **실제 드론 하드웨어와 분리**
3. **정기적인 안전성 검사 실행**
4. **시뮬레이션 모드 우선 사용**
5. **백업 안전장치 유지**

## 🔧 고급 사용법

### 커스텀 공격 개발

```python
from dvd_lite.dvd_attacks.core.attack_base import BaseAttack
from dvd_lite.dvd_attacks.core.enums import AttackType

class CustomAttack(BaseAttack):
    def _get_attack_type(self) -> AttackType:
        return AttackType.RECONNAISSANCE
    
    async def _run_attack(self) -> tuple:
        # 커스텀 공격 로직
        await asyncio.sleep(2)
        
        success = True
        iocs = ["CUSTOM_IOC:example_value"]
        details = {"custom_field": "example"}
        
        return success, iocs, details

# 공격 등록
dvd.register_attack("custom_attack", CustomAttack)
```

### 배치 공격 실행

```python
async def batch_attack_execution():
    dvd = DVDLite()
    register_all_dvd_attacks()
    
    # 시나리오별 배치 실행
    beginner_attacks = get_attacks_by_difficulty(AttackDifficulty.BEGINNER)
    results = await dvd.run_multiple_attacks(beginner_attacks)
    
    # 결과 분석
    success_rate = sum(1 for r in results if r.success) / len(results)
    print(f"성공률: {success_rate:.1%}")

asyncio.run(batch_attack_execution())
```

### CTI 데이터 분석

```python
# CTI 데이터 쿼리
high_confidence_indicators = cti.query_indicators(min_confidence=80)
reconnaissance_indicators = cti.query_indicators(attack_type="reconnaissance")

# 통계 분석
summary = cti.get_summary()
attack_distribution = summary['statistics']['by_attack_type']
print(f"공격 유형별 분포: {attack_distribution}")
```

## 🐛 문제 해결

### 일반적인 문제들

#### 1. Import 오류

```bash
# 모듈 구조 확인
python find_init.py

# 누락된 모듈 생성
python fix_actual_cti.py

# 권한 문제 해결
chmod +x quick_start.py setup.sh
```

#### 2. DVD 연결 실패

```bash
# Docker 상태 확인
docker compose ps

# DVD 컨테이너 재시작
docker compose down
docker compose up -d

# 네트워크 연결 확인
ping 10.13.0.2
```

#### 3. 안전성 검사 실패

```python
# 시뮬레이션 모드로 강제 설정
config = {
    "environment": "SIMULATION",
    "simulation_mode": True,
    "safety_enabled": True
}

# 안전성 재검사
result = await checker.comprehensive_safety_check(config)
```

#### 4. CTI 수집 오류

```bash
# CTI 모듈 재생성
python fix_actual_cti.py

# 의존성 재설치
pip install -r requirements.txt --force-reinstall
```

### 로그 확인

```bash
# DVD 로그 확인
tail -f dvd.log

# Python 로깅 활성화
export PYTHONPATH=.
python -c "import logging; logging.basicConfig(level=logging.DEBUG)"
```

### 성능 최적화

```python
# 동시 실행 제한
scanner = DVDNetworkScanner(max_threads=10)

# 타임아웃 조정
connector = DVDConnector(DVDConnectionConfig(timeout=60))

# 메모리 사용량 모니터링
import psutil
print(f"메모리 사용량: {psutil.virtual_memory().percent}%")
```

## 📁 프로젝트 구조

```
MTD_full_testbed/
├── dvd_lite/                    # 메인 프레임워크
│   ├── main.py                  # DVD-Lite 베이스
│   ├── cti.py                   # CTI 수집기
│   ├── attacks.py               # 기본 공격 모듈
│   └── dvd_attacks/             # DVD 공격 시나리오
│       ├── core/                # 핵심 정의
│       ├── reconnaissance/      # 정찰 공격
│       ├── protocol_tampering/  # 프로토콜 조작
│       ├── denial_of_service/   # DoS 공격
│       ├── injection/           # 주입 공격
│       ├── exfiltration/        # 데이터 탈취
│       ├── firmware_attacks/    # 펌웨어 공격
│       ├── registry/            # 공격 관리
│       └── utils/               # 유틸리티
├── dvd_connector/               # DVD 연동 모듈
│   ├── connector.py             # DVD 연결 관리
│   ├── safety_checker.py        # 안전성 검사
│   ├── network_scanner.py       # 네트워크 스캐너
│   └── real_attacks.py          # 실제 공격 어댑터
├── tests/                       # 테스트 모듈
├── results/                     # 결과 저장
├── configs/                     # 설정 파일
├── scripts/                     # 유틸리티 스크립트
├── quick_start.py               # 빠른 시작 스크립트
├── advanced_start.py            # 고급 시작 스크립트
├── setup.sh                     # 자동 설정 스크립트
└── README.md                    # 이 파일
```

## 🤝 기여하기

### 개발 환경 설정

```bash
# 개발 버전 클론
git clone https://github.com/PoppyPoppyPiggy/MTD_full_testbed.git
cd MTD_full_testbed

# 개발 환경 설정
python -m venv dev_env
source dev_env/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt  # 개발 의존성
```

### 새로운 공격 시나리오 추가

1. `dvd_lite/dvd_attacks/` 하위에 적절한 카테고리 선택
2. 새로운 공격 클래스 생성 (`BaseAttack` 상속)
3. `registry/management.py`에 공격 등록
4. 테스트 작성 및 문서화

### 코딩 스타일

- Python PEP 8 준수
- Type hints 사용
- Docstring 작성 (Google 스타일)
- 비동기 함수 사용 (`async/await`)

### 테스트

```bash
# 단위 테스트
python -m pytest tests/

# 통합 테스트
python tests/test_integration.py

# 커버리지 확인
python -m pytest --cov=dvd_lite tests/
```

## 📄 라이센스

이 프로젝트는 MIT 라이센스 하에 배포됩니다. 자세한 내용은 [LICENSE](LICENSE) 파일을 참조하세요.

## 📚 참고 자료

- [Damn Vulnerable Drone](https://github.com/nicholasaleks/Damn-Vulnerable-Drone) - 기반 드론 시뮬레이터
- [ArduPilot](https://ardupilot.org/) - 오픈소스 드론 소프트웨어
- [MAVLink Protocol](https://mavlink.io/) - 드론 통신 프로토콜
- [QGroundControl](http://qgroundcontrol.com/) - 드론 제어 소프트웨어

## 🙏 감사의 말

- **Nicholas Aleks** - Damn Vulnerable Drone 개발
- **ArduPilot 커뮤니티** - 오픈소스 드론 소프트웨어
- **MAVLink 개발팀** - 드론 통신 표준

## 📞 연락처

- **이슈 보고**: [GitHub Issues](https://github.com/PoppyPoppyPiggy/MTD_full_testbed/issues)
- **기능 요청**: [GitHub Discussions](https://github.com/PoppyPoppyPiggy/MTD_full_testbed/discussions)
- **보안 취약점**: 비공개 이메일로 연락

---

⚠️ **중요 고지**: 이 도구는 교육 및 연구 목적으로만 사용되어야 합니다. 실제 드론 시스템에 대한 무단 테스트는 불법일 수 있습니다. 항상 적절한 승인을 받고 안전한 환경에서 사용하세요.

🔬 **연구 목적**: 이 테스트베드는 논문 작성 및 학술 연구를 위해 설계되었습니다. 연구 결과 발표 시 적절한 인용을 부탁드립니다.