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
# MTD-RL v08.4: Reinforcement Learning-based Moving Target Defense

강화학습 기반 이동 표적 방어 시스템 (W&B 완전 연계)

## 📋 개요

드론/UAS 네트워크를 위한 강화학습 기반 Moving Target Defense (MTD) 시스템.
PPO 알고리즘 + Curriculum Learning + W&B 실험 추적.

### 주요 특징

- **학술적 MTD 지표**: MTTC, ASR, CDI, NED, ASP, DES, CER
- **Curriculum Learning**: 점진적 난이도 증가
- **Service Swap**: 서비스 매핑 동적 교환
- **W&B 완전 연계**: 로깅, Artifact, Sweep, 시각화

## 🚀 빠른 시작

### 1. 설치

```bash
pip install -r requirements.txt

# W&B 로그인
wandb login
```

### 2. 기본 학습

```bash
# W&B 없이
python rl_train_v08.py --curriculum --episodes 500

# W&B 로깅 활성화
python rl_train_v08.py --curriculum --episodes 500 --wandb

# W&B + 모델 Artifact 저장
python rl_train_v08.py --curriculum --episodes 500 --wandb --wandb-save-model
```

### 3. 평가

```bash
# W&B 없이
python evaluate_mtd_comparison_v08.py --rl-model checkpoints_v08/best.pt --episodes 50

# W&B 로깅 활성화
python evaluate_mtd_comparison_v08.py --rl-model checkpoints_v08/best.pt --wandb
```

---

## 📊 W&B 연계 기능

### 학습 (rl_train_v08.py)

| 기능 | 설명 | 옵션 |
|------|------|------|
| 메트릭 로깅 | 에피소드별 보상, 지표 | `--wandb` |
| 모델 Artifact | 체크포인트 자동 업로드 | `--wandb-save-model` |
| Config 저장 | 하이퍼파라미터 기록 | 자동 |
| 학습 곡선 | 이동평균 플롯 | 자동 |
| 액션 분포 | Bar Chart | 50 에피소드마다 |
| Phase 요약 | Curriculum 단계별 통계 | 자동 |
| 레벨별 성능 | 공격자 레벨별 비교 | 학습 종료 시 |

### 평가 (evaluate_mtd_comparison_v08.py)

| 기능 | 설명 |
|------|------|
| 비교 테이블 | 전략 × 레벨 결과표 |
| 피벗 테이블 | DES, MTTC 피벗 |
| 이미지 로깅 | 생성된 그래프 업로드 |
| 요약 통계 | 베스트 전략 등 |

### Hyperparameter Sweep

```bash
# Sweep 생성
wandb sweep sweep_config.yaml

# Agent 실행 (10회)
wandb agent <SWEEP_ID> --count 10

# 또는 스크립트로 실행
python rl_train_v08.py --sweep-agent --sweep-id <SWEEP_ID> --sweep-count 10
```

---

## 🎯 W&B 명령어 모음

### 기본 학습 + W&B

```bash
# 기본
python rl_train_v08.py --curriculum --episodes 500 --wandb

# 프로젝트 지정
python rl_train_v08.py --curriculum --episodes 500 --wandb --wandb-project mtd-research

# 실행 이름 지정
python rl_train_v08.py --curriculum --episodes 500 --wandb --wandb-name exp_v1

# 태그 추가
python rl_train_v08.py --curriculum --episodes 500 --wandb --wandb-tags "curriculum,v08,final"

# 메모 추가
python rl_train_v08.py --curriculum --episodes 500 --wandb --wandb-notes "첫 번째 실험"

# 모델 Artifact 저장
python rl_train_v08.py --curriculum --episodes 500 --wandb --wandb-save-model

# 풀 옵션
python rl_train_v08.py \
    --curriculum \
    --episodes 1000 \
    --hidden-size 256 \
    --wandb \
    --wandb-project mtd-rl-final \
    --wandb-name curriculum_v1 \
    --wandb-tags "curriculum,production" \
    --wandb-notes "최종 모델 학습" \
    --wandb-save-model
```

### 평가 + W&B

```bash
# 기본
python evaluate_mtd_comparison_v08.py --rl-model best.pt --wandb

# 프로젝트 지정
python evaluate_mtd_comparison_v08.py --rl-model best.pt --wandb --wandb-project mtd-eval

# 이름 지정
python evaluate_mtd_comparison_v08.py --rl-model best.pt --wandb --wandb-name eval_final

# RL-CTI 포함
python evaluate_mtd_comparison_v08.py \
    --rl-model best.pt \
    --include-rl-cti \
    --episodes 100 \
    --wandb \
    --wandb-project mtd-eval \
    --wandb-name comprehensive_eval
```

### Sweep 실행

```bash
# 1. Sweep 설정 확인
python rl_train_v08.py --sweep

# 2. Bayesian Sweep 생성
wandb sweep sweep_config.yaml

# 3. Architecture Search
wandb sweep sweep_architecture.yaml

# 4. Agent 실행
wandb agent <PROJECT>/<SWEEP_ID>

# 5. 여러 Agent 병렬 실행 (터미널 여러 개)
wandb agent <PROJECT>/<SWEEP_ID> &
wandb agent <PROJECT>/<SWEEP_ID> &
wandb agent <PROJECT>/<SWEEP_ID> &
```

---

## 📈 W&B에서 확인 가능한 지표

### 학습 지표

```
episode/episode          # 에피소드 번호
episode/phase            # Curriculum 단계
episode/seeker_level     # 공격자 레벨
episode/steps            # 에피소드 스텝 수
episode/reward           # 에피소드 보상
episode/avg_reward       # 이동평균 보상

MTD/DES                  # Defense Effectiveness Score
MTD/MTTC                 # Mean Time To Compromise
MTD/MTTC_Normalized      # 정규화된 MTTC
MTD/ASR                  # Attack Surface Reduction
MTD/CDI                  # Configuration Diversity Index
MTD/NED                  # Normalized Entropy of Defense
MTD/ASP                  # Attack Success Probability
MTD/CER                  # Cost Efficiency Ratio

Defense/BreachPrevented  # 침투 방어 성공
Defense/Diversity_Avg    # 평균 다양성
Defense/Redundancy_Avg   # 평균 중복성

Attack/ServicesFound     # 발견된 서비스 수
Attack/ServicesExploited # 익스플로잇된 서비스 수
Attack/ConfusionLevel    # 공격자 혼란도

Cost/Total               # 총 비용
Cost/Efficiency          # 비용 효율성
Cost/PerStep             # 스텝당 비용

MTD_Actions/ShuffleCount # 셔플 횟수
MTD_Actions/PortHopCount # 포트홉 횟수
MTD_Actions/SwapCount    # 스왑 횟수

Decoy/Activations        # 디코이 활성화 수
Decoy/Hits               # 디코이 히트 수
Decoy/HitRate            # 디코이 히트율

loss/policy              # 정책 손실
loss/value               # 가치 손실
loss/entropy             # 엔트로피
loss/kl_divergence       # KL 발산

Action/shuffle_intensity     # 셔플 강도
Action/port_hop_intensity    # 포트홉 강도
Action/decoy_ratio           # 디코이 비율
Action/blacklist_aggression  # 블랙리스트 공격성
Action/blacklist_duration    # 블랙리스트 지속
Action/service_swap_intensity # 스왑 강도
Action/service_swap_target    # 스왑 대상
```

### 평가 지표

```
eval/{MTD_Mode}/L{Level}/DES      # 레벨별 DES
eval/{MTD_Mode}/L{Level}/MTTC     # 레벨별 MTTC
eval/{MTD_Mode}/L{Level}/ASR      # 레벨별 ASR
eval/{MTD_Mode}/L{Level}/Survival # 레벨별 생존율

evaluation/comparison_table       # 전체 비교 테이블
evaluation/des_pivot              # DES 피벗 테이블
evaluation/mttc_pivot             # MTTC 피벗 테이블

figures/Main Results              # 메인 결과 그래프
figures/DES Heatmap               # 히트맵
figures/Radar Chart               # 레이더 차트
figures/Multi Metrics             # 다중 지표 그래프

{MTD_Mode}/avg_des                # 전략별 평균 DES
{MTD_Mode}/avg_mttc               # 전략별 평균 MTTC
{MTD_Mode}/avg_survival           # 전략별 평균 생존율

best_strategy                     # 베스트 전략
```

---

## 📁 파일 구조

```
mtd_v08_wandb/
├── rl_config_v08.py              # 설정
├── rl_environment_v08.py         # 환경
├── rl_train_v08.py               # 학습 (W&B 연계)
├── evaluate_mtd_comparison_v08.py # 평가 (W&B 연계)
├── iptables_mtd_controller_v08.py # 테스트베드 컨트롤러
├── rl_driven_deception_manager_v08.py # 배포용 매니저
├── cti_v08_integration.py        # CTI 연동
├── sweep_config.yaml             # Bayesian Sweep 설정
├── sweep_architecture.yaml       # Architecture Sweep 설정
├── requirements.txt              # 의존성
└── README.md                     # 문서
```

---

## 📚 학술적 MTD 지표

| 지표 | 이름 | 레퍼런스 |
|------|------|----------|
| MTTC | Mean Time To Compromise | Zhuang et al., IEEE TDSC 2014 |
| ASR | Attack Surface Reduction | Jajodia et al., Springer 2011 |
| CDI | Configuration Diversity Index | Evans et al., ACSAC 2011 |
| NED | Normalized Entropy of Defense | Cho et al., IEEE CNS 2020 |
| ASP | Attack Success Probability | Connell et al., IEEE S&P 2017 |
| DES | Defense Effectiveness Score | Composite (this work) |
| CER | Cost Efficiency Ratio | Hong & Kim, IEEE TIFS 2016 |

---

## 🔧 문제 해결

### W&B 로그인

```bash
wandb login
# 또는
export WANDB_API_KEY=your_api_key
```

### W&B 오프라인 모드

```bash
export WANDB_MODE=offline
python rl_train_v08.py --curriculum --episodes 500 --wandb

# 나중에 동기화
wandb sync wandb/offline-run-*
```

### GPU 메모리 부족

```bash
# CPU 사용
python rl_train_v08.py --curriculum --episodes 500 --cpu --wandb

# 작은 배치 사이즈
python rl_train_v08.py --curriculum --episodes 500 --batch-size 32 --wandb
```

---

## 📝 라이선스

MIT License

## 👥 저자

MTD-RL Research Team
Kyonggi University Cybersecurity Lab
