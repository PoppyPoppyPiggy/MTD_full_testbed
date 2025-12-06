#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MTD-RL Configuration v08 - Fixed Version
=========================================

수정사항:
1. scale_action 함수 추가
2. SearchSpaceConfig 추가
3. PPOConfig 누락 필드 추가
4. CurriculumConfig 누락 필드 추가
5. RewardWeights 누락 필드 추가

저자: MTD-RL Research Team
버전: 0.8.5 (Fixed)
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple
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
# Utility Functions
# =============================================================================
def scale_action(action: np.ndarray) -> np.ndarray:
    """
    액션을 [-1, 1] 범위에서 [0, 1] 범위로 스케일링
    
    Args:
        action: [-1, 1] 범위의 액션 배열
        
    Returns:
        [0, 1] 범위로 스케일된 액션 배열
    """
    return (np.array(action) + 1.0) / 2.0


def unscale_action(scaled_action: np.ndarray) -> np.ndarray:
    """
    스케일된 액션을 [0, 1] 범위에서 [-1, 1] 범위로 역스케일링
    
    Args:
        scaled_action: [0, 1] 범위의 스케일된 액션 배열
        
    Returns:
        [-1, 1] 범위의 액션 배열
    """
    return np.array(scaled_action) * 2.0 - 1.0


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


# =============================================================================
# Action Thresholds
# =============================================================================
@dataclass
class ActionThresholds:
    """
    액션 실행 임계값
    """
    shuffle: float = 0.10          # 셔플 실행 임계값
    port_hop: float = 0.15         # 포트 호핑 임계값
    decoy: float = 0.20            # 디코이 활성화 임계값
    blacklist: float = 0.30        # 블랙리스트 임계값
    service_swap: float = 0.15     # 서비스 스왑 임계값


# =============================================================================
# Search Space Configuration
# =============================================================================
@dataclass
class SearchSpaceConfig:
    """
    공격자 탐색 공간 설정
    """
    ip_range: int = 254            # IP 주소 범위 (10.13.0.1 ~ 10.13.0.254)
    port_range: int = 65535        # 포트 범위
    num_services: int = 9          # 서비스 수
    
    @property
    def total_search_space(self) -> int:
        """총 탐색 공간 크기"""
        return self.ip_range * self.port_range


# =============================================================================
# Reward Weights
# =============================================================================
@dataclass
class RewardWeights:
    """
    보상 함수 가중치
    """
    # === Survival/Breach (가장 중요) ===
    survival_bonus: float = 500.0       # 에피소드 생존 보너스
    breach_penalty: float = -800.0      # 침투 발생 시 패널티
    
    # === Step-level Rewards ===
    survival_per_step: float = 1.0      # 스텝당 생존 보상
    step_no_discovery: float = 0.5      # 발견 없을 때 보상
    
    # === Defense Effectiveness ===
    des_weight: float = 200.0           # DES 가중치
    mttc_weight: float = 2.0            # MTTC당 보상
    asr_weight: float = 50.0            # ASR 보상
    
    # === Cost ===
    cost_penalty: float = -0.05         # 비용 패널티
    cost_weight: float = 0.1            # 비용 가중치 (reward 계산용)
    
    # === Action Diversity Bonus ===
    action_diversity_bonus: float = 30.0    # 다양한 액션 사용 시 보상
    shuffle_usage_bonus: float = 10.0       # Shuffle 사용 보너스
    
    # === Attack Progress Penalties ===
    discovery_penalty: float = -5.0     # 서비스 발견당 패널티
    exploit_penalty: float = -20.0      # 익스플로잇당 패널티
    
    # === MTD Bonuses ===
    diversity_bonus: float = 20.0       # 다양성 보너스
    redundancy_bonus: float = 15.0      # 중복성 보너스
    confusion_bonus: float = 10.0       # 공격자 혼란 보너스
    
    # === Decoy Rewards ===
    decoy_hit_reward: float = 15.0      # 디코이 히트 보상
    decoy_engagement_bonus: float = 10.0  # 디코이 유인 보너스
    decoy_active_reward: float = 2.0    # 활성 디코이당 보상
    
    # === Confusion Reward ===
    confusion_reward: float = 10.0      # 공격자 혼란 보상


# =============================================================================
# Cost Configuration
# =============================================================================
@dataclass
class CostConfig:
    """
    MTD 액션별 비용
    """
    shuffle: float = 0.05           # 셔플 비용
    port_hop: float = 0.03          # 포트 호핑 비용
    decoy: float = 0.02             # 디코이 비용
    blacklist: float = 0.02         # 블랙리스트 비용
    service_swap: float = 0.05      # 서비스 스왑 비용


# =============================================================================
# Curriculum Learning Configuration
# =============================================================================
@dataclass
class CurriculumConfig:
    """
    Curriculum Learning 설정
    """
    # Phase별 에피소드 수 (총 800 에피소드)
    phase_episodes: List[int] = field(default_factory=lambda: [150, 150, 150, 200, 150])
    
    # Phase별 공격자 레벨
    phase_levels: List[List[int]] = field(default_factory=lambda: [
        [0],           # Phase 0: Script Kiddie만
        [0, 1],        # Phase 1: + Hobbyist
        [1, 2],        # Phase 2: + Professional
        [2, 3],        # Phase 3: + Expert
        [1, 2, 3, 4],  # Phase 4: 전체 (L0 제외)
    ])
    
    # Phase별 Entropy coefficient (exploration 제어)
    phase_entropy: List[float] = field(default_factory=lambda: [
        0.05,    # Phase 0: 높은 exploration
        0.04,    # Phase 1
        0.03,    # Phase 2
        0.025,   # Phase 3
        0.02,    # Phase 4
    ])
    
    # 복습 비율
    review_ratio: float = 0.2
    
    @property
    def phases(self) -> List[Tuple[int, ...]]:
        """Phase별 레벨을 튜플로 반환"""
        return [tuple(levels) for levels in self.phase_levels]
    
    @property
    def entropy_schedule(self) -> List[float]:
        """Entropy 스케줄 반환"""
        return self.phase_entropy


# =============================================================================
# PPO Hyperparameters
# =============================================================================
@dataclass 
class PPOConfig:
    """PPO 하이퍼파라미터"""
    learning_rate: float = 3e-4
    gamma: float = 0.99
    gae_lambda: float = 0.95
    clip_epsilon: float = 0.2
    value_coef: float = 0.5
    value_loss_coef: float = 0.5      # 별칭
    
    # Entropy
    entropy_coef_start: float = 0.05
    entropy_coef_end: float = 0.02
    entropy_coef_final: float = 0.02  # 별칭
    entropy_decay_episodes: int = 600
    
    # Training
    max_grad_norm: float = 0.5
    update_epochs: int = 10
    batch_size: int = 64
    hidden_size: int = 256
    
    # Episodes
    total_episodes: int = 500
    max_steps: int = 200


# =============================================================================
# Seeker (Attacker) Profiles
# =============================================================================
SEEKER_PROFILES = {
    0: {
        "name": "Script Kiddie",
        "scan_rate": 0.03,
        "discovery_rate": 0.15,
        "exploit_rate": 0.08,
        "exploit_success": 0.08,
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
        "exploit_success": 0.12,
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
        "exploit_success": 0.20,
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
        "exploit_success": 0.30,
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
        "exploit_success": 0.40,
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
    },
    "NED": {
        "name": "Normalized Entropy of Defense",
        "reference": "Cho et al., IEEE CNS 2020",
        "range": "[0, 1]",
        "higher_better": True,
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
    reward: RewardWeights = field(default_factory=RewardWeights)  # 별칭
    cost: CostConfig = field(default_factory=CostConfig)
    curriculum: CurriculumConfig = field(default_factory=CurriculumConfig)
    ppo: PPOConfig = field(default_factory=PPOConfig)
    search_space: SearchSpaceConfig = field(default_factory=SearchSpaceConfig)
    
    # Environment settings
    max_steps: int = 200
    num_services: int = 9
    num_decoys: int = 4
    
    # Diversity tracking
    track_config_history: bool = True
    config_history_size: int = 50
    
    def __post_init__(self):
        """Post-initialization to sync aliases"""
        # reward와 rewards 동기화
        self.reward = self.rewards
    
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
    total_steps: int = 0
    
    # 액션 다양성 추적
    action_types_used: set = field(default_factory=set)
    config_change_count: int = 0
    
    # 설정 변경 히스토리
    config_history: List[str] = field(default_factory=list)


# =============================================================================
# Helper Functions
# =============================================================================
def get_default_config() -> MTDConfig:
    """기본 설정 반환"""
    return MTDConfig()


# =============================================================================
# Version Info
# =============================================================================
VERSION = "0.8.5"
VERSION_NOTES = """
v08.5 수정사항:
1. scale_action 함수 추가
2. SearchSpaceConfig 클래스 추가
3. PPOConfig에 누락 필드 추가 (max_steps, total_episodes, value_loss_coef, entropy_coef_final)
4. CurriculumConfig에 phases, entropy_schedule 프로퍼티 추가
5. RewardWeights에 누락 필드 추가 (survival_per_step, cost_weight, diversity_bonus 등)
6. MTDConfig에 search_space 필드 추가
7. SEEKER_PROFILES에 exploit_success 필드 추가
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
    
    print("\n=== Search Space ===")
    print(f"Total Search Space: {config.search_space.total_search_space:,}")
    
    print("\n=== PPO Config ===")
    print(f"Max Steps: {config.ppo.max_steps}")
    print(f"Total Episodes: {config.ppo.total_episodes}")
    
    print("\n=== Curriculum ===")
    print(f"Phase Episodes: {config.curriculum.phase_episodes}")
    print(f"Phases: {config.curriculum.phases}")
    print(f"Total Episodes: {sum(config.curriculum.phase_episodes)}")
    
    print("\n=== Test scale_action ===")
    test_action = np.array([-1, 0, 1, 0.5, -0.5, 0.3, -0.7])
    scaled = scale_action(test_action)
    print(f"Original: {test_action}")
    print(f"Scaled:   {scaled}")
