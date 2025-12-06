#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MTD-RL Configuration v09 - Fixed Version
=========================================

수정사항:
1. 보상 함수 가중치 재설계 (Breach 패널티 대폭 증가)
2. 액션 Threshold 하향 조정 (Shuffle 등)
3. CDI/NED 계산을 위한 설정 추가
4. Curriculum Learning 파라미터 개선

저자: MTD-RL Research Team
버전: 0.9.0
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
import numpy as np
import json


# =============================================================================
# State/Action Dimensions
# =============================================================================
STATE_DIM = 17
ACTION_DIM = 7

# Feature keys for state vector (17 dimensions)
FEATURE_KEYS = [
    "scanned_ratio",           # 0: 스캔된 IP 비율
    "services_found_ratio",    # 1: 발견된 서비스 비율
    "critical_found_ratio",    # 2: 발견된 중요 서비스 비율
    "exploit_progress",        # 3: 익스플로잇 진행도
    "compromise_progress",     # 4: 침투 진행도
    "diversity_score",         # 5: 설정 다양성 (CDI)
    "redundancy_score",        # 6: 중복성 점수
    "time_since_shuffle",      # 7: 마지막 셔플 이후 시간
    "time_since_swap",         # 8: 마지막 스왑 이후 시간
    "active_decoys",           # 9: 활성 디코이 비율
    "decoy_hits",              # 10: 디코이 히트 비율
    "attacker_energy",         # 11: 공격자 에너지
    "episode_progress",        # 12: 에피소드 진행률
    "config_changes",          # 13: 설정 변경 횟수 (정규화)
    "defense_entropy",         # 14: 방어 엔트로피 (NED)
    "attack_phase",            # 15: 공격 단계 (0-3)
    "threat_level",            # 16: 위협 수준
]

# Action parameter keys (7 dimensions)
ACTION_PARAM_KEYS = [
    "shuffle_intensity",       # 0: 네트워크 셔플 강도
    "port_hop_intensity",      # 1: 포트 호핑 강도
    "decoy_ratio",             # 2: 디코이 활성화 비율
    "blacklist_aggression",    # 3: 블랙리스트 공격성
    "blacklist_duration",      # 4: 블랙리스트 지속 시간
    "service_swap_intensity",  # 5: 서비스 스왑 강도
    "service_swap_target",     # 6: 스왑 대상 선택
]


# =============================================================================
# Action Thresholds (v09: 대폭 하향 조정)
# =============================================================================
@dataclass
class ActionThresholds:
    """
    액션 실행 임계값 - v09에서 대폭 낮춤
    이전 버전에서 RL이 shuffle을 전혀 사용하지 않은 문제 해결
    """
    shuffle: float = 0.10          # v08: 0.25 → v09: 0.10 (더 쉽게 트리거)
    port_hop: float = 0.15         # v08: 0.35 → v09: 0.15
    decoy: float = 0.20            # v08: 0.40 → v09: 0.20
    blacklist: float = 0.30        # v08: 0.60 → v09: 0.30
    service_swap: float = 0.15     # v08: 0.30 → v09: 0.15


# =============================================================================
# Reward Weights (v09: 완전 재설계)
# =============================================================================
@dataclass
class RewardWeights:
    """
    보상 함수 가중치 - v09에서 완전 재설계
    
    문제점:
    - v08에서 No MTD가 가장 높은 reward를 받음
    - Cost 패널티가 너무 커서 방어 액션을 억제
    - Breach 패널티가 불충분
    
    해결:
    - Survival 보상 대폭 증가
    - Cost 패널티 대폭 감소
    - Breach 패널티 대폭 증가
    - 액션 다양성 보상 추가
    """
    # === Survival/Breach (가장 중요) ===
    survival_bonus: float = 500.0       # v08: 100 → v09: 500 (5배)
    breach_penalty: float = -800.0      # v08: -100 → v09: -800 (8배)
    
    # === Defense Effectiveness ===
    des_weight: float = 200.0           # v08: 50 → v09: 200 (4배)
    mttc_weight: float = 2.0            # MTTC당 보상
    asr_weight: float = 50.0            # ASR 보상
    
    # === Cost (대폭 감소) ===
    cost_penalty: float = -0.05         # v08: -0.2 → v09: -0.05 (1/4)
    
    # === Action Diversity Bonus (신규) ===
    action_diversity_bonus: float = 30.0    # 다양한 액션 사용 시 보상
    shuffle_usage_bonus: float = 10.0       # Shuffle 사용 보너스 (학습 유도)
    
    # === Step Rewards ===
    step_survival: float = 1.0          # 스텝당 생존 보상
    step_no_discovery: float = 0.5      # 발견 없을 때 보상
    
    # === Attack Progress Penalties ===
    discovery_penalty: float = -5.0     # 서비스 발견당 패널티
    exploit_penalty: float = -20.0      # 익스플로잇당 패널티
    
    # === Decoy Rewards ===
    decoy_hit_reward: float = 15.0      # 디코이 히트 보상 (v08: 5 → v09: 15)
    decoy_active_reward: float = 2.0    # 활성 디코이당 보상
    
    # === Confusion Reward ===
    confusion_reward: float = 10.0      # 공격자 혼란 보상


# =============================================================================
# Cost Configuration (v09: 비용 감소)
# =============================================================================
@dataclass
class CostConfig:
    """
    MTD 액션별 비용 - v09에서 감소
    비용이 너무 높으면 RL이 방어 액션을 회피함
    """
    shuffle: float = 0.05           # v08: 0.1 → v09: 0.05
    port_hop: float = 0.03          # v08: 0.05 → v09: 0.03
    decoy: float = 0.02             # v08: 0.03 → v09: 0.02
    blacklist: float = 0.02         # v08: 0.02 (유지)
    service_swap: float = 0.05      # v08: 0.08 → v09: 0.05


# =============================================================================
# Curriculum Learning Configuration (v09: 개선)
# =============================================================================
@dataclass
class CurriculumConfig:
    """
    Curriculum Learning 설정 - v09에서 개선
    
    문제점:
    - v08에서 고수준 공격자에 대한 일반화 실패
    - Phase 전환이 너무 급격
    
    해결:
    - Phase별 에피소드 수 증가
    - 더 점진적인 난이도 증가
    - 복습 메커니즘 추가
    """
    # Phase별 에피소드 수 (총 800 에피소드)
    phase_episodes: List[int] = field(default_factory=lambda: [150, 150, 150, 200, 150])
    
    # Phase별 공격자 레벨
    phase_levels: List[List[int]] = field(default_factory=lambda: [
        [0],           # Phase 0: Script Kiddie만
        [0, 1],        # Phase 1: + Hobbyist
        [1, 2],        # Phase 2: + Professional
        [2, 3],        # Phase 3: + Expert
        [1, 2, 3, 4],  # Phase 4: 전체 (L0 제외하여 어려움 유지)
    ])
    
    # Phase별 Entropy coefficient (exploration 제어)
    phase_entropy: List[float] = field(default_factory=lambda: [
        0.05,    # Phase 0: 높은 exploration
        0.04,    # Phase 1
        0.03,    # Phase 2
        0.025,   # Phase 3
        0.02,    # Phase 4: 여전히 적당한 exploration 유지
    ])
    
    # 복습 비율 (이전 레벨 샘플링 비율)
    review_ratio: float = 0.2


# =============================================================================
# PPO Hyperparameters (v09: 조정)
# =============================================================================
@dataclass 
class PPOConfig:
    """PPO 하이퍼파라미터 - v09에서 exploration 강화"""
    learning_rate: float = 3e-4
    gamma: float = 0.99
    gae_lambda: float = 0.95
    clip_epsilon: float = 0.2
    value_coef: float = 0.5
    
    # Entropy (v09: 증가)
    entropy_coef_start: float = 0.05     # v08: 0.03 → v09: 0.05
    entropy_coef_end: float = 0.02       # v08: 0.01 → v09: 0.02
    entropy_decay_episodes: int = 600    # v08: 400 → v09: 600 (더 천천히 감소)
    
    max_grad_norm: float = 0.5
    update_epochs: int = 10
    batch_size: int = 64
    hidden_size: int = 256


# =============================================================================
# Seeker (Attacker) Profiles
# =============================================================================
SEEKER_PROFILES = {
    0: {
        "name": "Script Kiddie",
        "scan_rate": 0.03,
        "discovery_rate": 0.15,
        "exploit_rate": 0.08,
        "lateral_rate": 0.02,
        "stealth": 0.1,
        "persistence": 0.2,
        "adaptation": 0.1,
        "decoy_detection": 0.1,
        "initial_energy": 1.0,
        "energy_decay": 0.008,
    },
    1: {
        "name": "Hobbyist",
        "scan_rate": 0.05,
        "discovery_rate": 0.25,
        "exploit_rate": 0.12,
        "lateral_rate": 0.05,
        "stealth": 0.25,
        "persistence": 0.35,
        "adaptation": 0.2,
        "decoy_detection": 0.2,
        "initial_energy": 1.0,
        "energy_decay": 0.006,
    },
    2: {
        "name": "Professional",
        "scan_rate": 0.08,
        "discovery_rate": 0.35,
        "exploit_rate": 0.20,
        "lateral_rate": 0.10,
        "stealth": 0.5,
        "persistence": 0.5,
        "adaptation": 0.35,
        "decoy_detection": 0.35,
        "initial_energy": 1.0,
        "energy_decay": 0.004,
    },
    3: {
        "name": "Expert",
        "scan_rate": 0.12,
        "discovery_rate": 0.50,
        "exploit_rate": 0.30,
        "lateral_rate": 0.15,
        "stealth": 0.7,
        "persistence": 0.7,
        "adaptation": 0.5,
        "decoy_detection": 0.5,
        "initial_energy": 1.0,
        "energy_decay": 0.003,
    },
    4: {
        "name": "APT",
        "scan_rate": 0.15,
        "discovery_rate": 0.65,
        "exploit_rate": 0.40,
        "lateral_rate": 0.20,
        "stealth": 0.85,
        "persistence": 0.9,
        "adaptation": 0.7,
        "decoy_detection": 0.65,
        "initial_energy": 1.0,
        "energy_decay": 0.002,
    },
}


# =============================================================================
# Academic MTD Metrics Reference
# =============================================================================
MTD_METRICS = {
    "MTTC": {
        "name": "Mean Time To Compromise",
        "reference": "Zhuang et al., IEEE TDSC 2014",
        "range": "[0, max_steps]",
        "higher_better": True,
    },
    "ASR": {
        "name": "Attack Surface Reduction",
        "reference": "Jajodia et al., Springer 2011",
        "range": "[0, 1]",
        "higher_better": True,
    },
    "CDI": {
        "name": "Configuration Diversity Index",
        "reference": "Evans et al., ACSAC 2011",
        "range": "[0, 1]",
        "higher_better": True,
        "note": "v09: 실제 설정 변경 반영하도록 수정",
    },
    "NED": {
        "name": "Normalized Entropy of Defense",
        "reference": "Cho et al., IEEE CNS 2020",
        "range": "[0, 1]",
        "higher_better": True,
        "note": "v09: 방어 액션 엔트로피 기반으로 수정",
    },
    "ASP": {
        "name": "Attack Success Probability",
        "reference": "Connell et al., IEEE S&P 2017",
        "range": "[0, 1]",
        "higher_better": False,
    },
    "DES": {
        "name": "Defense Effectiveness Score",
        "reference": "Composite (this work)",
        "range": "[0, 1]",
        "higher_better": True,
    },
    "CER": {
        "name": "Cost Efficiency Ratio",
        "reference": "Hong & Kim, IEEE TIFS 2016",
        "range": "[0, 1]",
        "higher_better": True,
    },
}


# =============================================================================
# Main Configuration Class
# =============================================================================
@dataclass
class MTDConfig:
    """MTD 시스템 전체 설정"""
    # Sub-configs
    thresholds: ActionThresholds = field(default_factory=ActionThresholds)
    rewards: RewardWeights = field(default_factory=RewardWeights)
    cost: CostConfig = field(default_factory=CostConfig)
    curriculum: CurriculumConfig = field(default_factory=CurriculumConfig)
    ppo: PPOConfig = field(default_factory=PPOConfig)
    
    # Environment settings
    max_steps: int = 200
    num_services: int = 9
    num_decoys: int = 4
    
    # Diversity tracking (v09 신규)
    track_config_history: bool = True
    config_history_size: int = 50
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    def save(self, path: str):
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2, default=str)
    
    @classmethod
    def load(cls, path: str) -> "MTDConfig":
        with open(path, "r") as f:
            data = json.load(f)
        return cls(**data)


# =============================================================================
# Episode Statistics
# =============================================================================
@dataclass
class EpisodeStats:
    """에피소드 통계"""
    total_cost: float = 0.0
    total_shuffles: int = 0
    total_port_hops: int = 0
    total_swaps: int = 0
    total_decoy_activations: int = 0
    total_decoy_hits: int = 0
    total_blacklist_updates: int = 0
    breach_occurred: bool = False
    breach_step: int = -1
    
    # v09 신규: 액션 다양성 추적
    action_types_used: set = field(default_factory=set)
    config_change_count: int = 0
    
    # v09 신규: 설정 변경 히스토리
    config_history: List[str] = field(default_factory=list)


# =============================================================================
# Utility Functions
# =============================================================================
def to_serializable(obj: Any) -> Any:
    """객체를 JSON 직렬화 가능한 형태로 변환"""
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, set):
        return list(obj)
    elif isinstance(obj, dict):
        return {k: to_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [to_serializable(v) for v in obj]
    return obj


def get_default_config() -> MTDConfig:
    """기본 설정 반환"""
    return MTDConfig()


# =============================================================================
# Version Info
# =============================================================================
VERSION = "0.9.0"
VERSION_NOTES = """
v09 주요 변경사항:
1. 보상 함수 완전 재설계 (Breach 패널티 8배, Survival 보상 5배)
2. 액션 Threshold 대폭 하향 (Shuffle 0.25→0.10)
3. Cost 패널티 1/4로 감소
4. CDI/NED 계산 로직 수정 예정 (environment에서)
5. Curriculum Learning 개선 (총 800 에피소드, 복습 메커니즘)
6. Entropy coefficient 증가 (exploration 강화)
7. 액션 다양성 보상 추가
"""

if __name__ == "__main__":
    print(f"MTD-RL Config v{VERSION}")
    print(VERSION_NOTES)
    
    config = get_default_config()
    print("\n=== Action Thresholds ===")
    print(f"Shuffle: {config.thresholds.shuffle}")
    print(f"Port Hop: {config.thresholds.port_hop}")
    print(f"Service Swap: {config.thresholds.service_swap}")
    
    print("\n=== Reward Weights ===")
    print(f"Survival Bonus: {config.rewards.survival_bonus}")
    print(f"Breach Penalty: {config.rewards.breach_penalty}")
    print(f"Cost Penalty: {config.rewards.cost_penalty}")
    
    print("\n=== Curriculum ===")
    print(f"Phase Episodes: {config.curriculum.phase_episodes}")
    print(f"Total Episodes: {sum(config.curriculum.phase_episodes)}")