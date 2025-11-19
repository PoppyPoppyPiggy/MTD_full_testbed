MTD-RL v05 아키텍처: 심층 분석 및 향후 과제

이 문서는 MTD_full_testbed/mtd/에 통합된 ver_04 (연속 파라미터, 하이브리드) 아키텍처의 핵심 요소들을 분석하고, 사용자의 질문에 답변하며, 현재 코드의 명확한 한계점과 다음 단계를 제시합니다.

1. MTD 고도화를 위한 그래프 분석 (Wandb 기준)

rl_train_v05.py 스크립트는 wandb에 방대한 양의 데이터를 로깅합니다. 이 데이터를 기반으로 생성되는 그래프와, MTD 고도화를 위해 추가로 생성하면 좋을 그래프는 다음과 같습니다.

(A) 현재 rl_train_v05.py가 생성하는 그래프

wandb 대시보드에서 다음 4개 그룹의 그래프를 실시간으로 확인할 수 있습니다.

RL 성능 지표 (Y-축: Rollout/*)

Rollout/mean_ep_reward: [가장 중요] 에피소드 평균 누적 보상. 이 그래프가 우상향해야 합니다.

Rollout/mean_ep_length: 에피소드 평균 길이.

MTD 환경 지표 (Y-축: Metrics/*)

RL 에이전트가 "보고 있는" 10가지 상태(State) 메트릭의 평균값입니다.

Metrics/breach_success_rate (↓): 방어 성공의 핵심 지표. 낮아져야 합니다.

Metrics/decoy_lure_rate (↑): 디코이 전략이 잘 작동하는지 보여줍니다.

Metrics/system_cost (↓): MTD 전략의 비용. 보상과 트레이드오프 관계입니다.

Metrics/blacklist_size (↔): CTI 에이전트의 활동성 지표.

Metrics/seeker_ip_change_rate (↔): Seeker가 얼마나 공격적으로 블랙리스트를 회피하는지 보여줍니다.

RL 행동 파라미터 (Y-축: Params/*)

RL 에이전트가 "출력하는" 6가지 행동 파라미터(0.0~1.0)의 평균값입니다.

Params/dnat_real_focus_prob

Params/dnat_decoy_focus_prob

Params/dnat_alternate_focus_prob

Params/shuffle_intensity

Params/blacklist_aggression

Params/blacklist_duration

[분석] 이 6개 그래프는 RL 에이전트가 어떤 복합 전략을 선호하도록 학습되는지 명확하게 보여줍니다. 예를 들어, breach_success_rate가 높아질 때 blacklist_aggression 그래프가 따라 올라간다면, 에이전트가 "침투 당하면 -> 블랙리스트를 강화"하는 전략을 학습했음을 의미합니다.

PPO 학습 내부 지표 (Y-축: Loss/*, Debug/*)

Loss/policy_loss, Loss/value_loss: PPO 손실 함수.

Debug/approx_kl, Debug/clip_fraction: 학습 안정성 지표.

(B) MTD 고도화를 위해 추가로 생성하면 좋은 그래프

위 그래프들은 훌륭하지만, 전략적 "이해"를 위해서는 데이터 가공이 더 필요합니다.

전략 행동 상관관계 히트맵 (Correlation Heatmap)

내용: Params/* (행동 6개)와 Metrics/* (상태 10개) 간의 상관계수(Correlation)를 보여주는 히트맵.

목적: "에이전트가 의미 있는 전략을 학습했는가?"를 검증합니다.

예시: Params/blacklist_aggression (행동)과 Metrics/breach_success_rate (상태) 간에 강한 음의 상관관계가 나타나야 합니다. (블랙리스트를 공격적으로 설정할수록, 침투 성공률이 낮아짐).

생성: wandb에 로깅된 데이터를 Pandas DataFrame으로 불러와 df.corr()와 seaborn.heatmap을 사용해 생성할 수 있습니다.

전략 파라미터 묶음 (Radar Chart)

내용: 6개의 Params/*를 6개의 축으로 하는 레이더 차트.

목적: 에이전트가 **"여러 전략을 동시에 채택"**하는지, 아니면 하나의 전략에 "매몰"되는지 시각화합니다.

예시:

"공격적 봉쇄" 전략: blacklist_aggression과 blacklist_duration 축이 길어짐.

"회피 및 기만" 전략: dnat_decoy_focus_prob와 shuffle_intensity 축이 길어짐.

정책 시각화 (Policy Visualization - 2D Histogram)

내용: 가장 중요한 2개의 상태(X, Y축)와 1개의 행동(색상)을 2D 히스토그램으로 시각화합니다.

X축: Metrics/breach_success_rate (침투율)

Y축: Metrics/seeker_ip_change_rate (Seeker 회피율)

색상(Heat): Params/blacklist_aggression (블랙리스트 공격성)

목적: "전략가"의 두뇌를 직접 시각화합니다.

예상 결과: (X가 높고, Y가 낮은) "침투는 잘 당하는데, Seeker가 IP를 안 바꾸는" 영역에서 blacklist_aggression이 1.0(진한 색)으로 나타나야 합니다. (X가 높고, Y도 높은) "침투도 잘 당하고, Seeker가 IP도 자주 바꾸는" 영역에서는 blacklist_aggression 대신 shuffle_intensity가 높아져야 합니다.

2. seeker_level 구현 위치

seeker_level은 v05 아키텍처에서 **"학습 환경의 난이도를 조절하는 핵심 파라미터"**로 작동하며, 다음 위치에 구현되어 있습니다.

설정 (Argument):

mtd/rl_train_v05.py에서 --seeker-level <0~4> 인자를 받습니다. (기본값 3)

전달 (Passing):

rl_train_v05.py -> env = NetworkEnv(cfg)

구현 (Implementation):

파일: mtd/rl_environment_v05.py

클래스: NetworkEnv의 __init__

코드: self.seeker = SimulatedHeuristicSeeker(cfg.seeker_level)

적용 (Application):

파일: mtd/rl_environment_v05.py

클래스: SimulatedHeuristicSeeker의 __init__

코드:

class SimulatedHeuristicSeeker:
    def __init__(self, level: int):
        params = {
            0: (0.1, 0.1, 0.05), # L0: (scan_effort, attack_effort, ip_change_prob)
            1: (0.3, 0.2, 0.1),
            2: (0.5, 0.5, 0.2),
            3: (0.7, 0.7, 0.3),
            4: (0.6, 0.9, 0.5)  # L4: 공격 집중, IP 자주 변경
        }
        # [!] seeker_level이 이 3개 파라미터를 결정합니다.
        self.scan_effort, self.attack_effort, self.ip_change_prob = params[level]


결론: seeker_level은 시뮬레이션된 적의 스캔 빈도, 공격 빈도, IP 변경(블랙리스트 회피) 빈도를 동시에 제어하여 RL 에이전트가 상대할 환경의 난이도를 결정합니다.

3. 학습 명령어 집합 (v05)

MTD_full_testbed/dvd_lite/dvd_attacks_lpc/ 디렉토리에서 다음 명령어를 실행합니다.

1. [디버그용] 빠른 테스트 (Wandb 비활성화, 5회 업데이트)

코드가 정상적으로 실행되고 export_ver04 폴더가 생성되는지 확인합니다.

python3 mtd/rl_train_v05.py \
    --updates 5 \
    --batch-size 200 \
    --disable-wandb \
    --run-name "Debug_Test_v05" \
    --export-dir "./mtd/rl_models/ver_04_debug"


2. [표준 학습] "보통" 난이도 Seeker(L2) 상대 학습

가장 표준적인 학습 명령어입니다.

python3 mtd/rl_train_v05.py \
    --seeker-level 2 \
    --updates 1500 \
    --batch-size 2048 \
    --minibatch-size 64 \
    --n-epochs 10 \
    --lr 3e-4 \
    --wandb-project "MTD_RL_v05_Hybrid" \
    --run-name "PPO_v05_vs_Seeker_L2" \
    --export-dir "./mtd/rl_models/ver_04_L2"


3. [고난도 학습] "공격적" Seeker(L4) 상대 학습

더 어렵고 회피적인 적을 상대로 강인한(robust) 정책을 학습합니다.

python3 mtd/rl_train_v05.py \
    --seeker-level 4 \
    --updates 2500 \
    --batch-size 2048 \
    --minibatch-size 64 \
    --wandb-project "MTD_RL_v05_Hybrid" \
    --run-name "PPO_v05_vs_Seeker_L4" \
    --export-dir "./mtd/rl_models/ver_04_L4"
