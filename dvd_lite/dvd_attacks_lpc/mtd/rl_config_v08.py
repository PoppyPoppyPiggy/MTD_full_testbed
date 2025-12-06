#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MTD RL Configuration v08 - 설정 파일 (수정본 v2)

수정사항 v2:
1. 비용 가중치 완화 (cost_weight: 0.15 → 0.08)
2. 방어 보너스 증가
3. MTD 활동 보너스 추가

저자: MTD-RL Research Team
버전: 0.8.2
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

import numpy as np


# =============================================================================
# 상태 공간 정의 (17차원)
# =============================================================================
FEATURE_KEYS = [
    "search_space_scanned_ratio",
    "services_discovered_ratio",
    "critical_discovered",
    "exploitation_progress",
    "compromise_progress",
    "current_diversity",
    "current_redundancy",
    "decoy_engagement_rate",
    "energy_remaining_ratio",
    "swap_active_ratio",
    "steps_since_shuffle",
    "steps_since_swap",
    "attacker_scan_rate",
    "last_shuffle_intensity",
    "last_port_hop_intensity",
    "last_decoy_ratio",
    "last_swap_intensity",
]

STATE_DIM = len(FEATURE_KEYS)  # 17


# =============================================================================
# 액션 공간 정의 (7차원)
# =============================================================================
ACTION_PARAM_KEYS = [
    "shuffle_intensity",
    "port_hop_intensity",
    "decoy_ratio",
    "blacklist_aggression",
    "blacklist_duration",
    "service_swap_intensity",
    "service_swap_target",
]

ACTION_DIM = len(ACTION_PARAM_KEYS)  # 7


# =============================================================================
# 공격자 프로파일
# =============================================================================
SEEKER_PROFILES = {
    0: {
        "name": "Script Kiddie",
        "scan_rate": 0.05,
        "discovery_rate": 0.1,
        "exploit_success": 0.1,
        "persistence": 0.3,
        "description": "자동화 도구 사용, 낮은 스킬",
    },
    1: {
        "name": "Hobbyist",
        "scan_rate": 0.08,
        "discovery_rate": 0.2,
        "exploit_success": 0.2,
        "persistence": 0.4,
        "description": "기본적인 해킹 지식",
    },
    2: {
        "name": "Professional",
        "scan_rate": 0.12,
        "discovery_rate": 0.35,
        "exploit_success": 0.35,
        "persistence": 0.6,
        "description": "전문적인 침투 테스터",
    },
    3: {
        "name": "Expert",
        "scan_rate": 0.15,
        "discovery_rate": 0.5,
        "exploit_success": 0.5,
        "persistence": 0.8,
        "description": "고급 공격 기법 활용",
    },
    4: {
        "name": "APT",
        "scan_rate": 0.18,
        "discovery_rate": 0.7,
        "exploit_success": 0.65,
        "persistence": 0.95,
        "description": "국가 수준의 지속적 위협",
    },
}


# =============================================================================
# 데이터 클래스
# =============================================================================
@dataclass
class SearchSpaceConfig:
    """검색 공간 설정"""
    ip_range: int = 200
    port_range: int = 251
    
    @property
    def total_search_space(self) -> int:
        return self.ip_range * self.port_range


@dataclass
class PPOConfig:
    """PPO 하이퍼파라미터"""
    learning_rate: float = 3e-4
    gamma: float = 0.99
    gae_lambda: float = 0.95
    clip_epsilon: float = 0.2
    value_loss_coef: float = 0.5
    max_grad_norm: float = 0.5
    
    batch_size: int = 64
    update_epochs: int = 10
    
    total_episodes: int = 500
    max_steps: int = 200
    
    # 엔트로피 스케줄링 (탐색 유지)
    entropy_coef_start: float = 0.03   # 0.02 → 0.03 (더 많은 탐색)
    entropy_coef_final: float = 0.005  # 0.001 → 0.005
    entropy_decay_episodes: int = 400


@dataclass
class RewardConfig:
    """보상 설정 (개선됨)"""
    # 기본 보상 (증가)
    survival_per_step: float = 0.15  # 0.1 → 0.15
    
    # 방어 성공 보상 (증가)
    discovery_prevented: float = 0.4   # 0.3 → 0.4
    exploit_prevented: float = 0.6     # 0.5 → 0.6
    breach_prevented: float = 1.5      # 1.0 → 1.5
    
    # 패널티 (완화)
    discovery_penalty: float = -0.15   # -0.2 → -0.15
    exploit_penalty: float = -0.4      # -0.5 → -0.4
    breach_penalty: float = -4.0       # -5.0 → -4.0
    
    # 비용 가중치 (대폭 완화)
    cost_weight: float = 0.08          # 0.15 → 0.08
    
    # 보너스 (증가)
    diversity_bonus: float = 0.3       # 0.2 → 0.3
    redundancy_bonus: float = 0.15     # 0.1 → 0.15
    decoy_engagement_bonus: float = 0.25  # 0.15 → 0.25
    confusion_bonus: float = 0.2       # 0.1 → 0.2
    
    # MTD 활동 보너스 (신규)
    shuffle_bonus: float = 0.1
    swap_bonus: float = 0.08
    active_defense_bonus: float = 0.15


@dataclass
class CostConfig:
    """MTD 액션 비용 (완화)"""
    shuffle: float = 0.25      # 0.3 → 0.25
    port_hop: float = 0.15     # 0.2 → 0.15
    decoy: float = 0.12        # 0.15 → 0.12
    blacklist: float = 0.08    # 0.1 → 0.08
    service_swap: float = 0.3  # 0.4 → 0.3


@dataclass
class CurriculumConfig:
    """Curriculum Learning 설정"""
    phases: List[Tuple[int, ...]] = field(default_factory=lambda: [
        (0,),
        (0, 1),
        (1, 2),
        (2, 3),
        (1, 2, 3, 4),
    ])
    
    phase_episodes: List[int] = field(default_factory=lambda: [
        100, 100, 100, 100, 100,
    ])
    
    entropy_schedule: List[float] = field(default_factory=lambda: [
        0.03, 0.025, 0.02, 0.015, 0.01,
    ])


@dataclass
class EpisodeStats:
    """에피소드 통계"""
    total_shuffles: int = 0
    total_port_hops: int = 0
    total_swaps: int = 0
    total_decoy_activations: int = 0
    total_decoy_hits: int = 0
    total_cost: float = 0.0
    total_steps: int = 0
    breach_occurred: bool = False
    services_discovered: int = 0
    services_exploited: int = 0


@dataclass
class MTDConfig:
    """통합 설정"""
    search_space: SearchSpaceConfig = field(default_factory=SearchSpaceConfig)
    ppo: PPOConfig = field(default_factory=PPOConfig)
    reward: RewardConfig = field(default_factory=RewardConfig)
    cost: CostConfig = field(default_factory=CostConfig)
    curriculum: CurriculumConfig = field(default_factory=CurriculumConfig)
    
    def __post_init__(self):
        assert STATE_DIM == 17, f"STATE_DIM must be 17, got {STATE_DIM}"
        assert ACTION_DIM == 7, f"ACTION_DIM must be 7, got {ACTION_DIM}"


# =============================================================================
# 유틸리티
# =============================================================================
def get_seeker_profile(level: int) -> Dict:
    return SEEKER_PROFILES.get(level, SEEKER_PROFILES[1])


def get_action_bounds() -> Tuple[np.ndarray, np.ndarray]:
    low = np.ones(ACTION_DIM) * -1.0
    high = np.ones(ACTION_DIM) * 1.0
    return low, high


if __name__ == "__main__":
    print("=== MTD RL Config v08.2 ===")
    print(f"STATE_DIM: {STATE_DIM}")
    print(f"ACTION_DIM: {ACTION_DIM}")
    
    cfg = MTDConfig()
    print(f"\nReward Settings:")
    print(f"  survival_per_step: {cfg.reward.survival_per_step}")
    print(f"  cost_weight: {cfg.reward.cost_weight}")
    print(f"  diversity_bonus: {cfg.reward.diversity_bonus}")
    print(f"  confusion_bonus: {cfg.reward.confusion_bonus}")
    
    print(f"\nCost Settings:")
    print(f"  shuffle: {cfg.cost.shuffle}")
    print(f"  service_swap: {cfg.cost.service_swap}")