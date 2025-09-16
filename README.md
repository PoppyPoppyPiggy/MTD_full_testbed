# 드론 군집 MTD 테스트베드 (LPC 공격 분석용)

본 프로젝트는 Docker, Python, ns-3를 기반으로 구축된 동적 MTD(Moving Target Defense) 테스트베드입니다. 지능형 드론 군집을 대상으로 하는 저속/저강도 공격(Loosely-Coupled Attacks, LPC)에 대한 MTD 전략의 효과를 시뮬레이션하고 정량적으로 평가하는 것을 목표로 합니다.



## 주요 특징

* **Docker 기반 에뮬레이션**: 실제 드론의 FCU, 컴패니언 컴퓨터, GCS, 공격자 등을 Docker 컨테이너로 에뮬레이션하여 현실적인 테스트 환경을 제공합니다.
* **모듈식 구성 요소**: MTD 엔진, 공격 오케스트레이터, 네트워크 관찰자, 정찰 프로버 등 각 기능이 독립된 모듈로 구성되어 확장 및 수정이 용이합니다.
* **통합 이벤트 버스 시스템**: 모든 구성 요소의 행동과 상태 변화는 중앙 로그 버스(`bus/` 디렉토리)에 JSONL 형식으로 기록되어 전체 상황을 시간순으로 재구성할 수 있습니다.
* **자동화된 데이터 파이프라인**: 실험 로그를 자동으로 파싱하여 ns-3 시뮬레이션용 이벤트 파일과 NetAnim 시각화용 XML 파일을 생성하는 파이프라인을 갖추고 있습니다.
* **ns-3 네트워크 시뮬레이션**: 실제 테스트베드에서 발생한 이벤트를 ns-3 환경에서 재현하여, 패킷 손실률, 지연 시간 등 정량적인 네트워크 성능 지표를 정밀하게 분석할 수 있습니다.

## 시스템 아키텍처 흐름

1.  **Docker 테스트베드**: `docker-compose.yml`에 정의된 다수의 컨테이너(드론, 공격자, MTD 엔진 등)가 가상 네트워크(`10.13.0.0/24`) 내에서 상호작용하며 시나리오를 수행합니다.
2.  **모니터링 모듈**: 3개의 핵심 모니터가 테스트베드의 모든 움직임을 감지합니다.
    * `container_monitor.py`: 드론의 내부 비행 상태(MAVLink)를 기록합니다.
    * `instance_monitor.py`: 모든 컨테이너의 내부 리소스(CPU, 메모리)를 기록합니다.
    * `network_observer.py`: 컨테이너 간의 모든 네트워크 패킷과 Docker 네트워크 변경 사항을 기록합니다.
3.  **이벤트 버스 (Logs)**: 모든 모니터와 구성 요소는 `bus/` 디렉토리에 시간순 로그를 생성합니다.
4.  **데이터 처리 및 변환 (`export_to_ns3.py`)**: 실험이 끝난 후, 모든 로그를 파싱하여 ns-3 시뮬레이션을 위한 입력 파일(`ns3_events_timeline.csv`)과 시각화 파일(`netanim_trace.xml`)을 생성합니다.
5.  **ns-3 시뮬레이션 (`lpc_mtd_drone_sim.cc`)**: 생성된 입력 파일을 바탕으로 실제 실험에서 발생한 네트워크 이벤트를 재현하고, 정량 분석을 위한 상세 결과물(`.pcap`, `.tr`, NetAnim XML)을 출력합니다.

## 설치 및 준비

1.  **사전 요구사항**: `Docker`, `Docker Compose`, `Python 3.9+`, `ns-3.45`가 설치되어 있어야 합니다.
2.  **저장소 복제**: `git clone --recurse-submodules <repository-url>`
3.  **Python 가상 환경 설정**:
    ```bash
    cd MTD_full_testbed/dvd_lite/dvd_attacks_lpc/
    python3 -m venv mtd_env
    source mtd_env/bin/activate
    pip install -r ../../requirements.txt 
    pip install docker scapy psutil # 추가 의존성 설치
    ```
4.  **ns-3 빌드**:
    ```bash
    cd MTD_full_testbed/ns-3.45/ns-3-dev/
    ./ns3 configure --build-profile=debug --enable-examples --enable-tests
    ./ns3 build
    ```

## 전체 실험 워크플로우

**1. (최초 1회) 공격 스크립트 준비**
```bash
# MTD_full_testbed/dvd_lite/dvd_attacks_lpc/ 디렉토리에서 실행
# 원본 복원 후 최신 버전으로 패치
python3 tools/integrate_mtd_interface.py --restore
python3 tools/integrate_mtd_interface.py
# 공격 프로필 생성
python3 tools/generate_attack_profiles.py
2. 실험 환경 및 모니터 시작

Bash

# 터미널 1: Docker 환경 실행 (프로젝트 루트에서)
cd ~/MTD_full_testbed/
docker-compose -f Damn-Vulnerable-Drone/docker-compose-lite.yaml up -d

# 터미널 2: 드론 상태 모니터 실행
python3 dvd_lite/dvd_attacks_lpc/monitors/container_monitor.py

# 터미널 3: 인스턴스 관제 모니터 실행
python3 dvd_lite/dvd_attacks_lpc/monitors/instance_monitor.py

# 터미널 4: 네트워크 관찰자 실행
python3 dvd_lite/dvd_attacks_lpc/monitors/network_observer.py
3. 공격 시나리오 실행

Bash

# 터미널 5: 공격 오케스트레이터 실행
cd dvd_lite/dvd_attacks_lpc/
python3 attack_orchestrator.py -a gps-spoofing.sh
4. 실시간 로그 관측 (선택 사항)

Bash

# 터미널 6: 모든 버스 로그 실시간 확인
tail -f dvd_lite/dvd_attacks_lpc/bus/*.log
5. 실험 종료 및 분석

Bash

# 실행 중인 공격(터미널 5)과 모니터(터미널 2,3,4)를 Ctrl+C로 종료
# Docker 환경 종료
docker-compose -f Damn-Vulnerable-Drone/docker-compose-lite.yaml down

# ns-3용 데이터 변환
python3 dvd_lite/dvd_attacks_lpc/tools/export_to_ns3.py
6. ns-3 시뮬레이션 및 시각화

Bash

# 결과물 저장 디렉토리 생성 (오류 방지)
mkdir -p dvd_lite/dvd_attacks_lpc/test_output/latest/

# ns-3 시뮬레이션 실행
cd ns-3.45/ns-3-dev/
./ns3 run "scratch/lpc_mtd_drone_sim \
  --animFile=/home/kali/MTD_full_testbed/dvd_lite/dvd_attacks_lpc/test_output/latest/netanim_from_ns3.xml"

# NetAnim으로 결과 확인
NetAnim
# -> 생성된 netanim_from_ns3.xml 파일을 열어 시각화 확인

---

### MTD 테스트베드 프로젝트 보고서

#### 1. 개요

본 문서는 드론 군집을 대상으로 하는 LPC(Loosely-Coupled) 공격에 대한 MTD(Moving Target Defense) 전략의 효과를 분석하기 위해 구축된 테스트베드의 시스템 아키텍처, 데이터 파이프라인, 핵심 모듈에 대해 기술한다. 본 테스트베드는 Docker 기반의 고충실도 에뮬레이션 환경과 ns-3 네트워크 시뮬레이터를 유기적으로 연동하여, 실제와 유사한 환경에서 MTD의 성능을 정량적으로 평가하고 시각화하는 것을 목표로 한다.

#### 2. 시스템 아키텍처

본 시스템은 크게 **(1) 에뮬레이션 환경**, **(2) 모니터링 및 로깅 시스템**, **(3) 데이터 처리 및 분석 파이프라인**의 세 부분으로 구성된다.

**2.1. Docker 기반 에뮬레이션 환경**

`docker-compose.yml`을 통해 관리되는 다수의 서비스 컨테이너로 구성된다. 각 컨테이너는 `10.13.0.0/24` 서브넷의 고정 IP를 할당받아 현실적인 드론 네트워크 환경을 모사한다.

* **핵심 드론 컴포넌트**: `flight-controller-lite`, `companion-computer-lite`, `ground-control-station-lite`는 드론의 핵심 기능을 에뮬레이션한다.
* **MTD 컴포넌트**: `mtd-engine`은 주기적으로 MTD 전략(예: `ip_shuffle`)을 결정하고 Docker API를 통해 다른 컨테이너의 네트워크 설정을 동적으로 변경한다.
* **공격 컴포넌트**: `attacker`, `prober`는 각각 공격 페이로드를 실행하고 MTD로 인해 변경되는 네트워크 환경을 정찰하는 역할을 수행한다. `attack_orchestrator`는 이들의 행동을 지휘한다.
* **관측 컴포넌트**: `observer`는 전체 네트워크 패킷을 스니핑하고, `rl-agent`는 강화학습 정책을 적용하기 위한 인터페이스 역할을 한다.

**2.2. 모니터링 및 이벤트 버스 시스템**

테스트베드의 모든 상태와 행위는 `bus/` 디렉토리에 생성되는 3개의 로그 파일에 JSONL 형식으로 기록된다.

* `bus.log`: 공격, MTD, 정찰 등 각 컴포넌트의 **행동(Action)** 이벤트가 기록된다.
* `bus_dvd.log`: `container_monitor`와 `instance_monitor`가 수집한 드론의 **상태(State)** 데이터 및 시스템 이상 경고가 기록된다.
* `bus_dvd_instances.log`: 각 서비스 컨테이너의 **내부 리소스(CPU, 메모리 등)** 상태가 기록된다.

이러한 로그는 3개의 Python 기반 모니터링 모듈을 통해 수집된다.
* **`container_monitor.py`**: 드론의 MAVLink 텔레메트리(비행 상태, 배터리, 모드 등)를 0.1초 주기로 수집한다.
* **`instance_monitor.py`**: 모든 인스턴스가 `instance_heartbeat` 유틸리티를 통해 보고하는 내부 리소스 상태를 종합하고, 이상 징후 발생 시 `instance_alert` 이벤트를 생성한다.
* **`network_observer.py`**: `scapy`와 `docker` API를 사용하여 네트워크 패킷과 Docker 네트워크의 변경 사항을 실시간으로 감지하고 기록한다.

**2.3. 데이터 파이프라인 및 ns-3 연동**

수집된 로그 데이터는 분석 및 시뮬레이션을 위해 다음과 같은 파이프라인을 거친다.

1.  **로그 통합 및 파싱**: `tools/export_to_ns3.py` 스크립트가 `bus/` 디렉토리의 모든 로그 파일을 읽어 시간순으로 병합하고, 표준화된 이벤트 객체로 변환한다.
2.  **ns-3 입력 파일 생성**: 파싱된 이벤트 중 `AttackStart`, `MTD_IP_Shuffle` 등 핵심 네트워크 이벤트를 추출하여 `ns3_events_timeline.csv` 파일을 생성한다.
3.  **NetAnim 시각화 파일 생성**: 드론의 상태 변화(배터리, Arming), MTD 동작, 공격 시작 등 로그에 기록된 모든 동적인 정보를 바탕으로 `netanim_trace.xml` 파일을 생성한다.
4.  **ns-3 시뮬레이션 실행**: `scratch/lpc_mtd_drone_sim.cc`는 `bus.log`를 실시간으로 감시(`tailing`)하여 MTD와 공격 이벤트를 시뮬레이션에 즉시 반영한다. 이 과정에서 정량 분석을 위한 `.pcap` 파일과 ASCII 트레이스 파일이 생성된다.

#### 3. 결론

본 테스트베드는 복잡한 드론 MTD 시나리오를 효과적으로 에뮬레이션하고, 그 결과를 다각도로 분석할 수 있는 강력한 프레임워크를 제공한다. 통합된 이벤트 버스와 자동화된 데이터 파이프라인을 통해, 사용자는 MTD 전략의 효과를 시각적(NetAnim) 및 정량적(ns-3)으로 정밀하게 평가할 수 있다. 이는 MTD 알고리즘 개발 및 검증, 강화학습 기반의 적응형 MTD 정책 연구 등을 위한 견고한 기반이 될 것이다.