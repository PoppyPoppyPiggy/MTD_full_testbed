#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rl_config_v05.py

- 학습 환경(NetworkEnv v0.5)과 실제 테스트베드 인퍼런스에서
  공통으로 사용하는 상태/행동 공간 정의.
- 여기 정의된 FEATURE_KEYS / ACTION_PARAM_KEYS / SIM_TIME_PER_STEP_SEC 를
  기준으로 논문에서 "시뮬레이션과 실제 환경의 의미론적 동일성"을 주장할 수 있음.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any

# --- Action (연속 파라미터) 정의 -------------------------------------------
# [-1, 1] → (action + 1) / 2 → [0, 1] 로 스케일링해서 사용.
# 테스트베드에서도 동일한 해석을 해야 함.

ACTION_PARAM_KEYS: List[str] = [
    # DNAT 포커스 비율 (3개 합이 1이 되도록 softmax / 정규화)
    "dnat_real_focus",
    "dnat_decoy_focus",
    "dnat_alternate_focus",

    # 셔플 강도 (0: 셔플 없음, 1: 매우 공격적인 셔플)
    "shuffle_intensity",

    # 블랙리스트 공격성 (0: 매우 공격적(민감), 1: 거의 차단 안함)
    "blacklist_aggression",

    # 블랙리스트 유지 기간 (0: 짧게, 1: 매우 길게/무기한)
    "blacklist_duration",
]

# --- State (Feature) 정의 ---------------------------------------------------
# 10개 운영/보안 메트릭 + 6개 마지막 액션 파라미터 = 16차원 상태공간

BASE_FEATURE_KEYS: List[str] = [
    # CTI / MTD / 공격 상황
    "cti_alert_rate",          # CTI 경보율 (최근 윈도우 기준)
    "blacklist_size",          # 현재 블랙리스트에 올라간 IP 개수
    "seeker_ip_change_rate",   # 공격자 IP 변경률
    "breach_success_rate",     # 침투 성공률
    "decoy_lure_rate",         # 디코이 유인률

    # 서비스/자원/비용 상태
    "alternate_node_health",   # 대체 노드(ALT) 품질 지표 (0~1)
    "service_uptime_ratio",    # 서비스 가동률 (0~1)
    "system_cost",             # MTD 비용 누적/평균 값

    # 공격 타임라인
    "recent_attack_flag",      # 최근 윈도우 안에 공격 발생 여부 플래그
    "mean_time_to_breach",     # 평균 Time-To-Breach (초 단위)
]

ACTION_FEATURE_KEYS: List[str] = [f"last_{k}" for k in ACTION_PARAM_KEYS]

FEATURE_KEYS: List[str] = BASE_FEATURE_KEYS + ACTION_FEATURE_KEYS

OBS_DIM: int = len(FEATURE_KEYS)
ACTION_DIM: int = len(ACTION_PARAM_KEYS)

# 시뮬레이션 1스텝이 실제 시간에서 몇 초에 대응하는지
# 테스트베드에서 CTI/모니터링 수집 주기와 맞춰서 설정.
SIM_TIME_PER_STEP_SEC: float = 1.0


@dataclass
class RLConfigV05:
    """학습 및 환경 공통 설정."""

    seed: int = 0
    seeker_level: int = 2

    # PPO 하이퍼파라미터
    total_timesteps: int = 200_000
    batch_size: int = 2048
    gamma: float = 0.99
    gae_lambda: float = 0.95
    clip_coef: float = 0.2
    update_epochs: int = 10
    ent_coef: float = 0.01
    vf_coef: float = 0.5
    max_grad_norm: float = 0.5
    learning_rate: float = 3e-4

    # 테스트베드 메트릭 키 매핑 (논문/코드에서 명시적으로 사용 가능)
    testbed_metric_mapping: Dict[str, str] = field(default_factory=lambda: {
        # 아래 값들은 실제 테스트베드에서 사용하는 JSON / 로그 키에 맞게 조정하면 됨.
        "cti_alert_rate": "cti.alert_rate",
        "blacklist_size": "mtd.blacklist_size",
        "seeker_ip_change_rate": "seeker.ip_change_rate",
        "breach_success_rate": "attack.breach_rate",
        "decoy_lure_rate": "attack.decoy_lure_rate",
        "alternate_node_health": "service.alternate_node_health",
        "service_uptime_ratio": "service.uptime_ratio",
        "system_cost": "mtd.system_cost",
        "recent_attack_flag": "attack.recent_flag",
        "mean_time_to_breach": "attack.mean_time_to_breach",
        # last_* 키들은 그대로 사용 (마지막 액션 파라미터 기록용)
    })


def build_state_vector_from_metrics(
    metrics: Dict[str, float],
    last_action_params: List[float],
) -> List[float]:
    """
    실 테스트베드에서 수집한 metrics + 마지막 액션 파라미터를
    FEATURE_KEYS 순서에 맞게 벡터로 정렬.

    metrics: BASE_FEATURE_KEYS 에 해당하는 값 딕셔너리
    last_action_params: 0~1 범위 6차원 리스트 (ACTION_PARAM_KEYS 순서)
    """
    assert len(last_action_params) == len(ACTION_PARAM_KEYS)
    vec: List[float] = []
    for k in BASE_FEATURE_KEYS:
        vec.append(float(metrics.get(k, 0.0)))
    for v in last_action_params:
        vec.append(float(v))
    return vec
