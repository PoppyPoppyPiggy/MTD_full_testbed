# 🔧 DVD 테스트베드 문제 해결 가이드

이 문서는 DVD 테스트베드 사용 중 발생할 수 있는 일반적인 문제들과 해결 방법을 제공합니다.

## 📋 목차

- [설치 관련 문제](#설치-관련-문제)
- [DVD 연결 문제](#dvd-연결-문제)
- [공격 실행 문제](#공격-실행-문제)
- [CTI 수집 문제](#cti-수집-문제)
- [성능 관련 문제](#성능-관련-문제)
- [Docker 관련 문제](#docker-관련-문제)
- [네트워크 문제](#네트워크-문제)
- [권한 관련 문제](#권한-관련-문제)

## 🚀 설치 관련 문제

### 문제: Import 오류 발생

```
ImportError: No module named 'dvd_lite'
```

**해결 방법:**

```bash
# 1. 프로젝트 루트에서 실행 확인
pwd
ls -la dvd_lite/

# 2. Python 경로 설정
export PYTHONPATH=$PYTHONPATH:$(pwd)

# 3. 모듈 구조 확인
python find_init.py

# 4. 누락된 모듈 생성
python fix_actual_cti.py
```

### 문제: 의존성 설치 실패

```
ERROR: Could not build wheels for package
```

**해결 방법:**

```bash
# 1. pip 업그레이드
pip install --upgrade pip

# 2. 가상환경 재생성
rm -rf dvd_env
python3 -m venv dvd_env
source dvd_env/bin/activate

# 3. 의존성 단계별 설치
pip install asyncio dataclasses typing-extensions
pip install -r requirements.txt

# 4. 개발 도구 설치 (선택)
pip install pytest psutil
```

### 문제: Python 버전 호환성

```
SyntaxError: invalid syntax (async/await)
```

**해결 방법:**

```bash
# Python 버전 확인
python --version

# Python 3.7+ 설치 (Ubuntu/Debian)
sudo apt update
sudo apt install python3.8 python3.8-venv

# Python 3.7+ 설치 (macOS)
brew install python@3.8

# 가상환경을 올바른 버전으로 재생성
python3.8 -m venv dvd_env
source dvd_env/bin/activate
```

## 🔗 DVD 연결 문제

### 문제: DVD 환경에 연결할 수 없음

```
ConnectionError: DVD 연결 실패: half_baked
```

**진단 단계:**

```bash
# 1. Docker 상태 확인
docker ps
docker compose ps

# 2. 네트워크 연결 확인
ping 10.13.0.2
telnet 10.13.0.2 14550

# 3. DVD 컨테이너 로그 확인
docker compose logs ardupilot
docker compose logs companion
```

**해결 방법:**

```bash
# 1. DVD 재시작
cd /path/to/Damn-Vulnerable-Drone
./stop.sh
./start.sh

# 2. 네트워크 재설정
docker network prune
docker compose down
docker compose up -d

# 3. 시뮬레이션 모드로 대체
python3 -c "
from dvd_connector import DVDConnector, DVDEnvironment, DVDConnectionConfig
import asyncio

async def test():
    config = DVDConnectionConfig(environment=DVDEnvironment.SIMULATION)
    connector = DVDConnector(config)
    result = await connector.connect()
    print(f'연결 상태: {result}')

asyncio.run(test())
"
```

### 문제: Docker 권한 오류

```
docker: permission denied while trying to connect to the Docker daemon socket
```

**해결 방법:**

```bash
# 1. 사용자를 docker 그룹에 추가
sudo usermod -aG docker $USER

# 2. 로그아웃 후 재로그인 또는
newgrp docker

# 3. Docker 서비스 재시작
sudo systemctl restart docker

# 4. 권한 확인
docker run hello-world
```

### 문제: 포트 충돌

```
Error: Port 14550 is already in use
```

**해결 방법:**

```bash
# 1. 포트 사용 확인
sudo netstat -tulpn | grep 14550
sudo lsof -i :14550

# 2. 프로세스 종료
sudo kill -9 <PID>

# 3. 대체 포트 사용
python3 -c "
from dvd_connector import DVDConnectionConfig
config = DVDConnectionConfig(mavlink_port=14552)
print(f'대체 포트: {config.mavlink_port}')
"
```

## ⚔️ 공격 실행 문제

### 문제: 공격 모듈 등록 실패

```
ValueError: 공격 모듈 'wifi_network_discovery'을 찾을 수 없습니다.
```

**해결 방법:**

```python
# 1. 등록된 공격 확인
from dvd_lite.main import DVDLite
from dvd_lite.dvd_attacks.registry.management import register_all_dvd_attacks

dvd = DVDLite()
attacks = register_all_dvd_attacks()
print(f"등록된 공격: {attacks}")

# 2. 특정 공격 정보 확인
from dvd_lite.dvd_attacks.registry.management import get_attack_info
info = get_attack_info("wifi_network_discovery")
print(f"공격 정보: {info}")

# 3. 사용 가능한 공격 목록
available_attacks = dvd.list_attacks()
print(f"사용 가능한 공격: {available_attacks}")
```

### 문제: 공격 실행 시 타임아웃

```
asyncio.TimeoutError: Attack execution timeout
```

**해결 방법:**

```python
# 1. 타임아웃 증가
from dvd_lite.main import DVDLite

dvd = DVDLite()
dvd.config["attacks"]["timeout"] = 60  # 60초로 증가

# 2. 네트워크 상태 확인
import asyncio
import socket

async def check_network():
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection("10.13.0.2", 14550),
            timeout=5
        )
        writer.close()
        print("✅ 네트워크 연결 정상")
    except Exception as e:
        print(f"❌ 네트워크 연결 실패: {e}")

asyncio.run(check_network())

# 3. 시뮬레이션 모드로 테스트
result = await dvd.run_attack("wifi_network_discovery", simulation=True)
```

### 문제: 공격 성공률이 낮음

```
많은 공격이 실패 상태로 완료됨
```

**해결 방법:**

```python
# 1. 타겟 환경 확인
from dvd_connector.safety_checker import SafetyChecker

checker = SafetyChecker()
config = {"host": "10.13.0.2", "environment": "HALF_BAKED"}
result = await checker.comprehensive_safety_check(config)
print(f"환경 상태: {result.safety_level}")

# 2. 네트워크 스캔으로 타겟 확인
from dvd_connector.network_scanner import DVDNetworkScanner

scanner = DVDNetworkScanner()
scan_result = await scanner.scan_network("10.13.0.0/24", quick_scan=True)
print(f"활성 호스트: {scan_result.active_hosts}")

# 3. 개별 공격 디버깅
import logging
logging.basicConfig(level=logging.DEBUG)

result = await dvd.run_attack("wifi_network_discovery")
print(f"상세 결과: {result.details}")
```

## 📊 CTI 수집 문제

### 문제: CTI 모듈 Import 오류

```
ImportError: cannot import name 'SimpleCTI' from 'dvd_lite.cti'
```

**해결 방법:**

```bash
# 1. CTI 모듈 재생성
python fix_actual_cti.py

# 2. 모듈 테스트
python -c "
from dvd_lite.cti import SimpleCTI, ThreatIndicator
print('✅ CTI 모듈 정상')
"

# 3. 수동으로 CTI 파일 확인
ls -la dvd_lite/cti.py
head -20 dvd_lite/cti.py
```

### 문제: CTI 데이터 내보내기 실패

```
FileNotFoundError: No such file or directory: 'results/'
```

**해결 방법:**

```python
# 1. 결과 디렉토리 생성
from pathlib import Path
Path("results").mkdir(exist_ok=True)

# 2. CTI 내보내기 테스트
from dvd_lite.cti import SimpleCTI

cti = SimpleCTI()
# 테스트 데이터 추가
from datetime import datetime
from dvd_lite.cti import ThreatIndicator

indicator = ThreatIndicator(
    ioc_type="test",
    value="test_value",
    confidence=75,
    attack_type="reconnaissance",
    timestamp=datetime.now()
)
cti.indicators.append(indicator)

# 내보내기
json_file = cti.export_json()
print(f"CTI 데이터 저장: {json_file}")
```

### 문제: IOC 신뢰도가 낮음

```
수집된 IOC의 신뢰도가 임계값보다 낮음
```

**해결 방법:**

```python
# 1. 신뢰도 임계값 조정
cti = SimpleCTI({"confidence_threshold": 50})  # 기본값 60에서 50으로 낮춤

# 2. 신뢰도 계산 로직 확인
config = {"confidence_threshold": 40}
cti = SimpleCTI(config)

# 3. 수동으로 고신뢰도 지표 생성
high_confidence_ioc = ThreatIndicator(
    ioc_type="mavlink_host",
    value="10.13.0.2",
    confidence=90,
    attack_type="reconnaissance",
    timestamp=datetime.now()
)
cti.indicators.append(high_confidence_ioc)
```

## 🚀 성능 관련 문제

### 문제: 메모리 사용량이 계속 증가

**진단:**

```python
import psutil
import gc

# 메모리 사용량 모니터링
def monitor_memory():
    process = psutil.Process()
    memory_mb = process.memory_info().rss / 1024 / 1024
    print(f"메모리 사용량: {memory_mb:.1f} MB")
    
monitor_memory()
# 공격 실행 후
monitor_memory()
```

**해결 방법:**

```python
# 1. 명시적 정리
async def run_attack_with_cleanup():
    dvd = DVDLite()
    result = await dvd.run_attack("wifi_network_discovery")
    
    # 명시적 정리
    del dvd
    gc.collect()
    
    return result

# 2. 컨텍스트 매니저 사용
class DVDContext:
    async def __aenter__(self):
        self.dvd = DVDLite()
        return self.dvd
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        del self.dvd
        gc.collect()

# 사용 예시
async with DVDContext() as dvd:
    result = await dvd.run_attack("wifi_network_discovery")
```

### 문제: 공격 실행이 너무 느림

**최적화 방법:**

```python
# 1. 병렬 실행
import asyncio

async def run_parallel_attacks():
    dvd = DVDLite()
    
    attacks = ["wifi_network_discovery", "mavlink_service_discovery"]
    
    # 동시 실행
    tasks = [dvd.run_attack(attack) for attack in attacks]
    results = await asyncio.gather(*tasks)
    
    return results

# 2. 타임아웃 최적화
config = {
    "attacks": {
        "timeout": 10,  # 빠른 타임아웃
        "delay_between": 0.5  # 짧은 지연
    }
}
dvd = DVDLite(config)

# 3. 네트워크 스캐너 최적화
scanner = DVDNetworkScanner(timeout=2, max_threads=20)
```

## 🐳 Docker 관련 문제

### 문제: Docker Compose 서비스가 시작되지 않음

**진단:**

```bash
# 1. Docker Compose 상태 확인
docker compose ps
docker compose logs

# 2. 개별 컨테이너 상태
docker ps -a
docker logs <container_name>

# 3. 이미지 상태 확인
docker images
```

**해결 방법:**

```bash
# 1. 강제 재빌드
docker compose down --volumes
docker compose build --no-cache
docker compose up -d

# 2. 개별 서비스 재시작
docker compose restart ardupilot
docker compose restart companion

# 3. 네트워크 정리
docker network prune
docker volume prune
```

### 문제: DVD 컨테이너 간 통신 실패

**해결 방법:**

```bash
# 1. 네트워크 확인
docker network ls
docker network inspect <network_name>

# 2. 컨테이너 간 연결 테스트
docker exec -it companion ping ardupilot
docker exec -it ardupilot ping companion

# 3. 포트 매핑 확인
docker port ardupilot
docker port companion
```

## 🌐 네트워크 문제

### 문제: 10.13.0.0/24 네트워크에 접근할 수 없음

**진단:**

```bash
# 1. 라우팅 테이블 확인
ip route
route -n

# 2. 네트워크 인터페이스 확인
ip addr
ifconfig

# 3. DVD 네트워크 확인
docker network inspect <dvd_network>
```

**해결 방법:**

```bash
# 1. 대체 네트워크 설정
export DVD_NETWORK="192.168.100.0/24"

# 2. 네트워크 브리지 추가
sudo ip route add 10.13.0.0/24 dev docker0

# 3. 시뮬레이션 모드 사용
python3 -c "
from dvd_connector import DVDConnector, DVDEnvironment
import asyncio

async def test():
    config = DVDConnectionConfig(environment=DVDEnvironment.SIMULATION)
    connector = DVDConnector(config)
    await connector.connect()

asyncio.run(test())
"
```

### 문제: 방화벽으로 인한 연결 차단

**해결 방법:**

```bash
# 1. 방화벽 상태 확인
sudo ufw status
sudo iptables -L

# 2. DVD 포트 허용 (임시)
sudo ufw allow 14550
sudo ufw allow 8000
sudo ufw allow 554

# 3. Docker 네트워크 허용
sudo ufw allow from 172.16.0.0/12
sudo ufw allow from 10.13.0.0/24
```

## 🔐 권한 관련 문제

### 문제: 파일 쓰기 권한 없음

```
PermissionError: [Errno 13] Permission denied: 'results/cti_data.json'
```

**해결 방법:**

```bash
# 1. 디렉토리 권한 확인
ls -la results/

# 2. 권한 설정
chmod 755 results/
chmod 644 results/*

# 3. 소유자 변경 (필요시)
sudo chown $USER:$USER results/
```

### 문제: 네트워크 스캔 권한 부족

```
Operation not permitted: raw socket
```

**해결 방법:**

```bash
# 1. 권한 상승 (주의: 보안 위험)
sudo python quick_start.py

# 2. 대안: 시뮬레이션 모드 사용
python3 -c "
from dvd_connector.network_scanner import DVDNetworkScanner
import asyncio

async def safe_scan():
    scanner = DVDNetworkScanner()
    # TCP 연결 기반 스캔 (권한 불필요)
    result = await scanner.scan_network('127.0.0.0/30', quick_scan=True)
    print(f'스캔 결과: {result.active_hosts}개 호스트')

asyncio.run(safe_scan())
"

# 3. 네트워크 권한 설정
sudo setcap cap_net_raw+ep $(which python3)
```

## 🔄 일반적인 재시작 절차

문제가 지속될 때 시도할 전체 재시작 절차:

```bash
# 1. 모든 프로세스 정리
pkill -f python
pkill -f docker

# 2. Docker 완전 정리
docker compose down --volumes --remove-orphans
docker system prune -f

# 3. DVD 환경 재시작
cd /path/to/Damn-Vulnerable-Drone
./stop.sh
sleep 5
./start.sh

# 4. 테스트베드 재시작
cd /path/to/MTD_full_testbed
source dvd_env/bin/activate
python tests/test_basic.py

# 5. 통합 테스트
python tests/test_integration.py comprehensive
```

## 📞 추가 도움이 필요한 경우

1. **로그 수집**: 문제 상황의 전체 로그를 수집
   ```bash
   python quick_start.py single 2>&1 | tee debug.log
   docker compose logs > docker_debug.log
   ```

2. **환경 정보 수집**:
   ```bash
   python --version
   docker --version
   uname -a
   pip list | grep -E "(asyncio|dataclasses)"
   ```

3. **이슈 리포트**: 수집된 정보와 함께 GitHub Issues에 보고

4. **커뮤니티 지원**: DVD 커뮤니티 슬랙 채널 활용

---

💡 **팁**: 대부분의 문제는 시뮬레이션 모드를 사용하여 우회할 수 있습니다. 실제 DVD 환경이 없어도 테스트베드의 모든 기능을 학습하고 테스트할 수 있습니다.