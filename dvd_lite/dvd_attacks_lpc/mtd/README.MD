# MTD (Moving Target Defense) 시스템

이 프로젝트는 드론 테스트베드를 위한 RL(강화학습) 기반의 MTD(Moving Target Defense) 시스템을 구현합니다. PPO 기반 에이전트가 네트워크 라우팅(iptables)을 동적으로 변경하여 공격자를 기만하고 방어하는 것을 목표로 합니다.

## 🌟 아키텍처: Brains, Eyes, Hands

이 MTD 시스템은 3가지 핵심 컴포넌트로 구성됩니다.

* 🧠 **Brain** (`rl_driven_deception_manager.py`)
    * MTD의 **두뇌** 역할을 합니다.
    * 사전 학습된 PPO 정책(`.pth` 파일)을 로드합니다.
    * 주기적으로 "Eyes"로부터 8차원 상태(State) 벡터를 읽어옵니다.
    * 정책에 따라 7가지 방어 행동(Action ID: 0~6) 중 하나를 결정합니다.
    * 결정된 행동을 "Hands"에게 명령합니다.

* 👀 **Eyes** (`mtd_state_reader.py`)
    * MTD의 **눈** 역할을 합니다.
    * 컨트롤러("Hands")가 기록한 현재 MTD 상태 파일(`mtd_state.json`)과 기타 시스템 정보를 읽습니다.
    * 수집된 정보를 "Brain"이 이해할 수 있는 8차원 상태 벡터(numpy 배열)로 변환하여 제공합니다.

* 🖐️ **Hands** (`controller/iptables_mtd_controller.py`)
    * MTD의 **손** 역할을 합니다.
    * "Brain"으로부터 0~6 사이의 Action ID를 전달받습니다.
    * `configs/iptables_mtd.yaml` 규칙서를 참조하여, 해당 ID에 매핑된 실제 `iptables` NAT 룰을 실행합니다.
    * 트래픽을 실제 서비스 또는 디코이(Decoy)로 리디렉션하거나 차단(Drop)합니다.
    * 현재 적용된 상태를 `mtd_state.json` 파일에 기록하여 "Eyes"가 읽을 수 있도록 합니다.

## 🚀 핵심 파일 및 디렉토리

* `rl_driven_deception_manager.py`: (Brain) MTD 매니저 실행 스크립트.
* `mtd/controller/iptables_mtd_controller.py`: (Hands) IPTables 컨트롤러.
* `mtd/mtd_state_reader.py`: (Eyes) MTD 상태 리더.
* `mtd/seeker.py`: (Attacker) L0, L1, L2 레벨별 휴리스틱 공격자 스크립트.
* `mtd/configs/iptables_mtd.yaml`: **핵심 설정 파일.**
    * MTD가 사용할 `iptables` 체인 이름.
    * 공용 포트 및 프로토콜 정의.
    * "Eyes"가 참조할 6개의 실제 타겟(Real Targets) 리스트.
    * "Hands"가 실행할 7개의 행동(Action ID 0-6)과 실제 `iptables` (DNAT/Drop) 룰 매핑.

## ▶️ 실행 방법

이 시스템은 2개의 터미널에서 각각 **방어자(MTD Manager)**와 **공격자(Seeker)**를 실행하여 동작을 테스트합니다.

### 터미널 1: MTD 매니저 (방어자) 실행

`iptables`룰을 수정해야 하므로 **반드시 `sudo` (root) 권한**으로 실행해야 합니다.

```bash
# (dvd_attacks_lpc 디렉토리에서 실행)

sudo python3 mtd/rl_driven_deception_manager.py \
    --policy [사용할_정책_파일.pth] \
    --config mtd/configs/iptables_mtd.yaml \
    --interval 30