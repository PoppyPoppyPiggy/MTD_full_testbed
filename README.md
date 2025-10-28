MTD Full Testbed: 자율 드론 시스템을 위한 능동적 기만 및 적응형 이동 표적 방어(MTD) 프레임워크

개요

본 프로젝트는 자율 드론 시스템을 대상으로 하는 지능형 사이버 위협, 특히 저강도 지속 캠페인(LPC, Loose Persistence Campaigns)에 대응하기 위한 포괄적인 테스트베드 및 방어 프레임워크입니다. 능동적 기만(Active Deception)과 적응형 이동 표적 방어(MTD) 전략을 다중 에이전트 강화학습(MARL)과 결합하여, 변화하는 위협 환경에 동적으로 대응하는 것을 목표로 합니다.

이 리포지토리는 Damn Vulnerable Drone (DVD) 프로젝트를 기반으로 확장되었으며, 다양한 공격 시나리오 시뮬레이션, MTD 정책 실행, 강화학습 기반 방어 에이전트 학습 및 평가를 위한 환경을 제공합니다.

주요 기능

다양한 공격 시나리오: 기존 DVD Wiki 기반 공격 및 Low-and-Slow 특성을 가지는 LPC 공격 스크립트 제공 (dvd_lite/dvd_attacks_lpc/modules/attacks, dvd_lite/dvd_attacks_lpc/modules/attacks_wiki).

MTD 프레임워크: iptables 기반의 네트워크 파라미터(IP, Port 등) 변경을 통한 MTD 전략 실행 (dvd_lite/dvd_attacks_lpc/mtd).

MARL 기반 적응형 방어: 공격자(Seeker)와 방어자(Defender) 역할을 하는 MARL 에이전트 학습 및 정책 실행 (dvd_lite/dvd_attacks_lpc/marl_agent*, dvd_lite/dvd_attacks_lpc/rl).

실험 및 평가: 다양한 공격 및 방어 시나리오 조합에 대한 자동화된 실험 실행 및 결과 분석 기능 (dvd_lite/dvd_attacks_lpc/eval, dvd_lite/dvd_attacks_lpc/experiment_orchestrator.py).

모니터링: 시스템 이벤트, 네트워크 트래픽, 드론 텔레메트리 등 다양한 데이터 소스를 모니터링하는 컴포넌트 제공 (dvd_lite/dvd_attacks_lpc/monitors).

시각화: 실험 결과 및 시스템 상태 시각화를 위한 웹 기반 인터페이스 제공 (visualize, dvd_lite/lpc_ui).

프로젝트 구조

MTD_full_testbed/
├── Damn-Vulnerable-Drone.wiki/  # DVD 프로젝트 원본 Wiki 문서 (공격 시나리오 상세 설명)
├── dvd_lite/
│   ├── dvd_attacks_lpc/         # 핵심 로직: 공격, MTD, MARL, 모니터링, 평가 등
│   │   ├── modules/             # 공격 스크립트 및 MTD 관련 모듈
│   │   ├── marl_agent*/         # MARL 에이전트 학습 및 실행 코드
│   │   ├── mtd/                 # MTD 정책 실행 및 관리 코드
│   │   ├── monitors/            # 시스템/네트워크 모니터링 코드
│   │   ├── eval/                # 실험 평가 관련 스크립트
│   │   ├── tools/               # 분석 및 유틸리티 스크립트
│   │   ├── configs/             # MTD 정책 등 설정 파일
│   │   ├── scenarios/           # 실험 파이프라인 정의
│   │   ├── attack_orchestrator.py # 공격 실행 관리
│   │   └── experiment_orchestrator.py # 실험 실행 관리
│   └── lpc_ui/                  # LPC 공격 제어용 웹 UI (Flask 기반)
├── visualize/                   # 실험 결과 시각화 웹 애플리케이션 (Flask 기반)
├── requirements.txt             # Python 의존성 목록
└── README.md                    # 현재 문서


설치

저장소 클론:

git clone [https://github.com/your-username/MTD_full_testbed.git](https://github.com/your-username/MTD_full_testbed.git)
cd MTD_full_testbed


(참고: 서브모듈이 있다면 git submodule update --init --recursive 명령어가 필요할 수 있습니다.)

가상 환경 생성 및 활성화 (권장):

python -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate  # Windows


의존성 설치:

pip install -r requirements.txt
pip install -r dvd_lite/dvd_attacks_lpc/requirements.txt # 필요시 추가 의존성 설치


(참고: 특정 모듈은 추가적인 시스템 라이브러리나 도구(예: nmap, tcpdump, iptables, aircrack-ng 등) 설치가 필요할 수 있습니다. 각 모듈의 문서를 확인하십시오.)

환경 변수 설정:
dvd_lite/dvd_attacks_lpc/ 디렉토리 내의 00_env*.sh 스크립트들을 사용하여 필요한 환경 변수를 설정합니다. 로컬 환경, 외부 연동 환경 등에 맞게 적절한 스크립트를 사용하거나 수정하십시오.

source dvd_lite/dvd_attacks_lpc/00_env_local.sh # 예시


사용법

1. 공격 실행

attackctl 유틸리티 또는 attack_orchestrator.py 스크립트를 사용하여 개별 공격 또는 시나리오를 실행할 수 있습니다.

attackctl 사용 (간단한 제어):

cd dvd_lite/dvd_attacks_lpc
./attackctl list             # 사용 가능한 공격 목록 보기
./attackctl start <attack_name> # 특정 공격 시작
./attackctl stop <attack_name>  # 특정 공격 중지
./attackctl status           # 실행 중인 공격 상태 보기


attack_orchestrator.py 사용 (상세 제어):

cd dvd_lite/dvd_attacks_lpc
python attack_orchestrator.py --list # 공격 목록 보기
python attack_orchestrator.py --attack <attack_name> --target <target_name> # 특정 공격 실행


(사용 가능한 인자는 python attack_orchestrator.py --help 로 확인하십시오.)

2. 실험 실행

experiment_orchestrator.py 또는 scenarios/run_*.sh 스크립트를 사용하여 정의된 실험 파이프라인을 실행합니다.

파이프라인 실행:

cd dvd_lite/dvd_attacks_lpc/scenarios
./run_matrix_lpc_suite.sh # 예시: LPC 공격 매트릭스 실험 실행


또는

cd dvd_lite/dvd_attacks_lpc
python experiment_orchestrator.py --pipeline scenarios/pipelines/matrix_lpc_suite.yml # YAML 파일로 정의된 파이프라인 실행


3. MARL 에이전트 학습

각 marl_agent* 디렉토리 내의 train.py 스크립트를 사용하여 MARL 에이전트를 학습시킵니다.

cd dvd_lite/dvd_attacks_lpc/marl_agent2 # 예시
python train.py --level <scenario_level> # 특정 레벨의 시나리오로 학습 시작


(자세한 학습 옵션은 각 train.py 스크립트 또는 관련 문서를 참조하십시오.)

4. 모니터링 실행

run_monitors.py 또는 개별 모니터 스크립트를 실행하여 시스템 및 네트워크 상태를 모니터링합니다.

cd dvd_lite/dvd_attacks_lpc
python run_monitors.py # 모든 모니터 실행 (설정 기반)
# 또는
python monitors/network_traffic_monitor.py # 개별 모니터 실행


5. 시각화 도구 실행

실험 결과 시각화:

cd visualize
python server.py


웹 브라우저에서 http://localhost:5000 (기본값)으로 접속합니다.

LPC UI (공격 제어):

cd dvd_lite/lpc_ui
./run.sh


웹 브라우저에서 http://localhost:5001 (기본값)으로 접속합니다.

설정

MTD 정책: dvd_lite/dvd_attacks_lpc/configs/mtd_policy.yaml 또는 dvd_lite/dvd_attacks_lpc/mtd/shared_state/mtd_policy.yaml 에서 MTD 전략 및 파라미터를 설정합니다.

공격 대상: dvd_lite/dvd_attacks_lpc/modules/attacks/targets/targets.yml 에서 공격 대상 시스템 정보를 설정합니다.

실험 파이프라인: dvd_lite/dvd_attacks_lpc/scenarios/pipelines/*.yml 에서 실험 절차 및 시나리오를 정의합니다.

문서

각 공격 시나리오에 대한 자세한 설명은 Damn-Vulnerable-Drone.wiki/ 디렉토리 내의 마크다운 파일들을 참조하십시오.

기여

본 프로젝트에 기여하고 싶으시면 이슈를 생성하거나 풀 리퀘스트를 보내주십시오.

라이선스

본 프로젝트는 MIT 라이선스를 따릅니다. 자세한 내용은 LICENSE 파일을 참조하십시오. (라이선스 파일이 없다면 이 부분을 제거하거나 적절히 수정하십시오.)