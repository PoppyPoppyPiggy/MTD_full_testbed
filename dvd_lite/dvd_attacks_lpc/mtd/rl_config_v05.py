# File: MTD_full_testbed/dvd_lite/dvd_attacks_lpc/mtd/rl_config_v05.py
#
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[신규 1/8] MTD-RL v04 하이브리드 아키텍처 - 핵심 계약 (Contract)

- [v03 대비 변경점]
- ACTION_MAP (이산적) -> ACTION_PARAM_KEYS (연속적)로 변경
- RL 에이전트는 이제 (N,) 벡터의 연속 파라미터를 출력합니다.
"""

# --- [A] Docker-Compose 기반 타겟 정의 ---
# docker-compose-lite.yaml의 IP/Port 기반
REAL_TARGETS = [
    {"name": "flight-controller", "ip": "10.13.0.2", "port": 14550},
    {"name": "companion-computer", "ip": "10.13.0.3", "port": 3000},
    {"name": "ground-control-station", "ip": "10.13.0.4", "port": 14550},
]
DECOY_TARGETS = [
    {"name": "decoy-gateway", "ip": "10.13.0.6", "port": 80},
]
ALTERNATE_NODE_TARGETS = [
    {"name": "virtual-drone", "ip": "10.13.0.100", "port": 14550},
]

# --- [B] RL 행동(Action) 공간 정의 (v04: 연속적 파라미터) ---
# RL 에이전트("전략가")가 *동시에* 출력하는 6개의 파라미터
# PPO는 각 파라미터의 평균(mean)과 표준편차(std)를 학습합니다.
# [!] 순서가 매우 중요합니다.
ACTION_PARAM_KEYS = [
    # 1. DNAT 라우팅 전략 (3개 파라미터, 합쳐서 100%가 됨)
    "dnat_real_focus_prob",    # (0.0~1.0) 실제 서비스로 보낼 확률 (Softmax Logit)
    "dnat_decoy_focus_prob",   # (0.0~1.0) 디코이 서비스로 보낼 확률 (Softmax Logit)
    "dnat_alternate_focus_prob", # (0.0~1.0) 대체 노드로 보낼 확률 (Softmax Logit)
    
    # 2. 셔플 전략 (1개 파라미터)
    "shuffle_intensity",     # (0.0~1.0) 0.0=Noop, 1.0=Aggressive Shuffle
    
    # 3. 블랙리스트 정책 (2개 파라미터)
    "blacklist_aggression",  # (0.0~1.0) CTI 탐지 공격성 (0.0=느슨, 1.0=공격적)
    "blacklist_duration",    # (0.0~1.0) CTI 차단 시간 (0.0=5분, 1.0=영구)
]
ACTION_DIM = len(ACTION_PARAM_KEYS) # 6

# --- [C] RL 상태(State) 공간 정의 (v04: 16D Vector) ---
# [!] MtdScorer와 CtiAgentStatus는 이 키값과 순서대로 메트릭을 반환해야 함.
# [v03 대비 변경점] current_strategy_id(이산적) 대신 6D action 파라미터(연속적)가 피드백됨
METRIC_FEATURE_KEYS = [
    # 1. CTI Agent (전술가) 성과 (From CtiAgentStatus)
    "cti_alert_rate",       # (0.0 ~ 1.0) CTI 분류기 탐지율
    "blacklist_size",       # (0 ~ N) 현재 블랙리스트에 등록된 IP 수
    "seeker_ip_change_rate",# (0.0 ~ 1.0) Seeker가 IP를 변경(회피)한 비율
    
    # 2. MTD Scorer (전장) 성과 (From MtdScorer)
    "breach_success_rate",  # (0.0 ~ 1.0) `attack_orchestrator.py` 침투 성공률
    "decoy_lure_rate",      # (0.0 ~ 1.0) 디코이 유인 성공률
    "alternate_node_health",# (0.0 ~ 1.0) 대체 노드(GCS/FC) 품질 (QoS)
    
    # 3. 시스템 상태
    "system_cost",          # (0.0 ~ N) 현재 전략의 비용 (MtdScorer)
    "service_uptime_ratio", # (0.0 ~ 1.0) 실제 서비스(Real) 평균 응답률 (MtdScorer)
    "attack_orchestrator_running", # (0.0 or 1.0) `attack_orchestrator.py`가 활성화되었는가 (MtdScorer)
    
    # (v02 레거시 지표 - 단순화)
    "ttbr",                 # Time-to-First-Breach (단순화)
]
METRIC_DIM = len(METRIC_FEATURE_KEYS) # 10

# [핵심] 최종 상태 벡터 = (메트릭 10개) + (이전 행동 파라미터 6개)
# [!] 순서가 매우 중요합니다.
FEATURE_KEYS = METRIC_FEATURE_KEYS + [f"prev_action_{k}" for k in ACTION_PARAM_KEYS]
OBS_DIM = len(FEATURE_KEYS) # 10 + 6 = 16