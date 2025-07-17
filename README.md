# DVD (Damn Vulnerable Drone) 공격 시나리오

드론 보안 테스트를 위한 모듈화된 공격 시나리오 프레임워크

## 빠른 시작

### 1. 환경 설정
```bash
# 자동 설정 (Linux/Mac)
chmod +x setup.sh
./setup.sh

# 수동 설정
pip install -r requirements.txt
```

### 2. 기본 테스트
```bash
python tests/test_basic.py
```

### 3. 실행
```bash
# 모든 데모 실행
python quick_start.py

# 특정 모드 실행
python quick_start.py single      # 단일 공격
python quick_start.py multiple    # 여러 공격
python quick_start.py interactive # 대화형 모드
python quick_start.py list        # 공격 목록
```

## 구조

```
dvd_lite/
├── main.py                    # DVD-Lite 베이스
└── dvd_attacks/
    ├── core/                  # 핵심 정의
    ├── reconnaissance/        # 정찰 공격
    ├── protocol_tampering/    # 프로토콜 조작
    ├── denial_of_service/     # DoS 공격
    ├── injection/             # 주입 공격
    ├── exfiltration/          # 데이터 탈취
    ├── firmware_attacks/      # 펌웨어 공격
    └── registry/              # 공격 관리
```

## 현재 구현된 공격

- WiFi 네트워크 발견
- MAVLink 서비스 발견  
- GPS 스푸핑
- 텔레메트리 데이터 탈취

## CTI 수집 활용

```python
from dvd_lite.main import DVDLite
from dvd_lite.dvd_attacks.registry.management import register_all_dvd_attacks

dvd = DVDLite()
register_all_dvd_attacks(dvd)

# 공격 실행
result = await dvd.run_attack("wifi_network_discovery")
print(f"IOCs: {result.iocs}")
```
