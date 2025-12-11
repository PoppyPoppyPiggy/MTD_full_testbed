#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MTD Comparison Evaluation Script v08.8 - Fair Comparison
=========================================================

[v0.8.8] 수정사항:
- Heuristic MTD 현실적으로 조정 (과도한 액션 방지)
- RL과 공정한 비교를 위한 환경 조정
- 방어 확률이 MTD 액션에 비례하도록 수정

저자: MTD-RL Research Team
버전: 0.8.8
"""
from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

import numpy as np

# Plotting
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')

try:
    import seaborn as sns
    HAS_SEABORN = True
except ImportError:
    HAS_SEABORN = False

# W&B
try:
    import wandb
    WANDB_AVAILABLE = True
except ImportError:
    WANDB_AVAILABLE = False

# Local imports
from rl_config_v08 import (
    ACTION_DIM,
    ACTION_PARAM_KEYS,
    SEEKER_PROFILES,
    FEATURE_KEYS,
    STATE_DIM,
    EpisodeStats,
    MTDConfig,
    MTD_METRICS,
    to_serializable,
    scale_action,
)

# PyTorch
try:
    import torch
    from rl_train_v08 import ActorCritic, PPOAgent
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    print("⚠️ PyTorch not available")


# =============================================================================
# 논문 스타일 설정
# =============================================================================
def set_publication_style():
    """IEEE/ACM 논문 스타일 설정"""
    plt.rcParams.update({
        'font.family': 'serif',
        'font.serif': ['Times New Roman', 'DejaVu Serif', 'serif'],
        'font.size': 10,
        'axes.labelsize': 11,
        'axes.titlesize': 12,
        'xtick.labelsize': 9,
        'ytick.labelsize': 9,
        'legend.fontsize': 9,
        'figure.titlesize': 14,
        'axes.linewidth': 0.8,
        'grid.linewidth': 0.5,
        'lines.linewidth': 1.5,
        'lines.markersize': 6,
        'savefig.dpi': 300,
        'savefig.bbox': 'tight',
        'savefig.pad_inches': 0.1,
    })
    if HAS_SEABORN:
        sns.set_palette("colorblind")


COLORS = {
    "No MTD": '#d62728',
    "Static MTD": '#ff7f0e',
    "Heuristic MTD": '#2ca02c',
    "RL MTD": '#1f77b4',
    "RL-CTI MTD": '#9467bd',
}

MARKERS = {
    "No MTD": 'o',
    "Static MTD": 's',
    "Heuristic MTD": '^',
    "RL MTD": 'D',
    "RL-CTI MTD": 'p',
}

HATCHES = ['', '///', '...', 'xxx', '\\\\\\']


# =============================================================================
# 공정한 비교를 위한 환경 래퍼
# =============================================================================
class FairComparisonEnv:
    """
    공정한 비교를 위한 환경 래퍼
    
    핵심 변경:
    - MTD 액션이 방어 확률에 직접 영향
    - 액션 없으면 기본 방어율 25%
    - 과도한 액션에 대한 diminishing returns
    """
    
    def __init__(self, seed: int, seeker_level: int, config: MTDConfig):
        self.seed = seed
        self.seeker_level = seeker_level
        self.config = config
        
        # 내부 상태
        self.step_count = 0
        self.max_steps = config.ppo.max_steps
        self.rng = np.random.RandomState(seed)
        
        # 공격자 상태
        self.attacker_phase = "reconnaissance"
        self.services_discovered = 0
        self.services_exploited = 0
        self.total_services = 6
        self.critical_services = 3
        self.breach_occurred = False
        
        # MTD 상태
        self.recent_shuffles = []
        self.recent_swaps = []
        self.diversity = 0.5
        self.redundancy = 0.3
        self.confusion_level = 0.0
        
        # 통계
        self.total_shuffles = 0
        self.total_swaps = 0
        self.total_cost = 0.0
        self.decoy_hits = 0
        
        # 공격자 프로파일
        self.attacker_profile = SEEKER_PROFILES.get(seeker_level, SEEKER_PROFILES[1])
        
    def reset(self):
        self.step_count = 0
        self.attacker_phase = "reconnaissance"
        self.services_discovered = 0
        self.services_exploited = 0
        self.breach_occurred = False
        self.recent_shuffles = []
        self.recent_swaps = []
        self.diversity = 0.5
        self.redundancy = 0.3
        self.confusion_level = 0.0
        self.total_shuffles = 0
        self.total_swaps = 0
        self.total_cost = 0.0
        self.decoy_hits = 0
        
        return self._get_state(), self._get_info()
    
    def step(self, action: np.ndarray):
        self.step_count += 1
        
        # 1. MTD 액션 처리
        mtd_effect, mtd_cost = self._process_mtd_action(action)
        self.total_cost += mtd_cost
        
        # 2. 방어 확률 계산
        defense_prob = self._calculate_defense_probability(mtd_effect)
        
        # 3. 공격자 시뮬레이션
        attack_result = self._simulate_attack(defense_prob)
        
        # 4. 보상 계산
        reward = self._calculate_reward(mtd_cost, attack_result, mtd_effect)
        
        # 5. 종료 조건
        terminated = self.breach_occurred
        truncated = self.step_count >= self.max_steps
        
        return self._get_state(), reward, terminated, truncated, self._get_info()
    
    def _process_mtd_action(self, action: np.ndarray) -> Tuple[float, float]:
        """MTD 액션 처리 및 효과 계산"""
        scaled = (action + 1) / 2  # [-1, 1] -> [0, 1]
        
        mtd_effect = 0.0
        mtd_cost = 0.0
        
        # Shuffle
        shuffle_intensity = scaled[0]
        if shuffle_intensity > 0.25:
            self.total_shuffles += 1
            self.recent_shuffles.append(self.step_count)
            mtd_effect += 0.25 * shuffle_intensity  # 최대 +25%
            mtd_cost += shuffle_intensity * 0.5
            self.confusion_level += shuffle_intensity * 0.1
            
            # Diversity 증가
            self.diversity = min(1.0, self.diversity + shuffle_intensity * 0.1)
        
        # Port Hop
        port_hop = scaled[1] if len(scaled) > 1 else 0
        if port_hop > 0.35:
            mtd_effect += 0.10 * port_hop
            mtd_cost += port_hop * 0.3
        
        # Decoy
        decoy_ratio = scaled[2] if len(scaled) > 2 else 0
        if decoy_ratio > 0.3:
            self.redundancy = min(1.0, self.redundancy + decoy_ratio * 0.05)
            mtd_effect += 0.08 * decoy_ratio
            mtd_cost += decoy_ratio * 0.2
        
        # Swap
        swap_intensity = scaled[5] if len(scaled) > 5 else 0
        if swap_intensity > 0.30:
            self.total_swaps += 1
            self.recent_swaps.append(self.step_count)
            mtd_effect += 0.30 * swap_intensity  # 최대 +30%
            mtd_cost += swap_intensity * 0.8
            self.confusion_level += swap_intensity * 0.15
        
        # 최근 액션 유지 (최대 10개)
        self.recent_shuffles = [s for s in self.recent_shuffles if self.step_count - s < 20][-10:]
        self.recent_swaps = [s for s in self.recent_swaps if self.step_count - s < 20][-10:]
        
        # 혼란 감쇠
        self.confusion_level *= 0.95
        
        # Diversity 감쇠
        self.diversity = max(0.3, self.diversity * 0.995)
        
        return min(0.50, mtd_effect), mtd_cost  # MTD 효과 최대 50%
    
    def _calculate_defense_probability(self, current_mtd_effect: float) -> float:
        """방어 확률 계산"""
        # 기본 방어 확률 (MTD 없으면 낮음)
        base_defense = 0.20
        
        # 현재 MTD 효과
        mtd_bonus = current_mtd_effect
        
        # 최근 액션의 잔여 효과
        recent_effect = 0.0
        for shuffle_step in self.recent_shuffles:
            decay = 0.9 ** (self.step_count - shuffle_step)
            recent_effect += 0.05 * decay
        for swap_step in self.recent_swaps:
            decay = 0.9 ** (self.step_count - swap_step)
            recent_effect += 0.08 * decay
        recent_effect = min(0.20, recent_effect)
        
        # Diversity/Redundancy 보너스
        diversity_bonus = self.diversity * 0.10
        redundancy_bonus = self.redundancy * 0.08
        confusion_bonus = self.confusion_level * 0.05
        
        # 공격자 레벨에 따른 수정자
        level_modifier = 1.0 - (self.seeker_level * 0.06)  # L0: 1.0, L4: 0.76
        
        total = (base_defense + mtd_bonus + recent_effect + 
                diversity_bonus + redundancy_bonus + confusion_bonus) * level_modifier
        
        return max(0.15, min(0.85, total))
    
    def _simulate_attack(self, defense_prob: float) -> Dict[str, Any]:
        """공격 시뮬레이션"""
        result = {
            "discovered": False,
            "exploited": False,
            "breach": False,
            "defended": False,
        }
        
        profile = self.attacker_profile
        
        if self.attacker_phase == "reconnaissance":
            # 서비스 발견 시도
            if self.services_discovered < self.total_services:
                discover_prob = profile["discovery_rate"] * (1 - self.confusion_level * 0.3)
                
                # 방어 확률 적용
                if self.rng.random() < defense_prob:
                    result["defended"] = True
                elif self.rng.random() < discover_prob:
                    self.services_discovered += 1
                    result["discovered"] = True
            
            if self.services_discovered >= 2:
                self.attacker_phase = "exploitation"
                
        elif self.attacker_phase == "exploitation":
            # 익스플로잇 시도
            if self.services_exploited < self.services_discovered:
                exploit_prob = profile["exploit_success"] * 0.7
                
                # 방어 확률 적용 (exploitation은 방어 더 어려움)
                if self.rng.random() < defense_prob * 0.7:
                    result["defended"] = True
                elif self.rng.random() < exploit_prob:
                    self.services_exploited += 1
                    result["exploited"] = True
            
            if self.services_exploited >= self.critical_services:
                self.attacker_phase = "persistence"
                
        elif self.attacker_phase == "persistence":
            # Breach 시도
            breach_prob = profile.get("persistence", 0.5)
            
            if self.rng.random() < defense_prob * 0.5:
                result["defended"] = True
            elif self.rng.random() < breach_prob:
                self.breach_occurred = True
                result["breach"] = True
        
        return result
    
    def _calculate_reward(self, mtd_cost: float, attack_result: Dict, mtd_effect: float) -> float:
        """보상 계산"""
        reward = 0.0
        
        # 기본 생존 보상
        reward += 0.1
        
        # 비용 페널티
        reward -= mtd_cost * 0.3
        
        # 공격 결과
        if attack_result["breach"]:
            reward -= 10.0
        elif attack_result["exploited"]:
            reward -= 3.0
        elif attack_result["discovered"]:
            reward -= 1.0
        
        # 방어 성공 보너스
        if attack_result["defended"]:
            reward += 2.0
        
        # 효율적 방어 보너스 (적은 비용으로 방어 성공)
        if attack_result["defended"] and mtd_cost < 0.5:
            reward += 1.0
        
        return reward
    
    def _get_state(self) -> np.ndarray:
        """상태 벡터"""
        state = np.zeros(STATE_DIM, dtype=np.float32)
        
        state[0] = self.step_count / self.max_steps  # 진행도
        state[1] = self.services_discovered / self.total_services
        state[2] = float(self.services_discovered >= self.critical_services)
        state[3] = self.services_exploited / self.total_services
        state[4] = {"reconnaissance": 0.0, "exploitation": 0.5, "persistence": 1.0}.get(self.attacker_phase, 0)
        state[5] = self.diversity
        state[6] = self.redundancy
        state[7] = 0.0  # decoy rate
        state[8] = 1.0 - self.step_count / self.max_steps  # 남은 에너지
        state[9] = len(self.recent_swaps) / 5.0
        state[10] = min(1.0, (self.step_count - (self.recent_shuffles[-1] if self.recent_shuffles else 0)) / 30)
        state[11] = min(1.0, (self.step_count - (self.recent_swaps[-1] if self.recent_swaps else 0)) / 30)
        state[12] = self.confusion_level
        
        return state
    
    def _get_info(self) -> Dict[str, Any]:
        """정보 딕셔너리"""
        # MTTC
        if self.breach_occurred:
            mttc = self.step_count
        else:
            mttc = self.max_steps
        
        # ASR
        exposed = self.services_discovered + self.services_exploited * 2
        max_exposure = self.total_services * 3
        asr = 1.0 - min(1.0, exposed / max_exposure)
        
        # ASP
        asp = self.services_exploited / max(1, self.services_discovered)
        
        # DES 계산
        mttc_norm = mttc / self.max_steps
        des = (
            0.25 * mttc_norm +
            0.20 * asr +
            0.20 * self.diversity +
            0.15 * self.confusion_level +
            0.10 * (1.0 - asp) +
            0.10 * self.redundancy
        )
        
        return {
            "MTD/MTTC": mttc,
            "MTD/MTTC_Normalized": mttc_norm,
            "MTD/ASR": asr,
            "MTD/CDI": self.diversity,
            "MTD/NED": self.confusion_level,
            "MTD/ASP": asp,
            "MTD/DES": des,
            "MTD/CER": des / (self.total_cost + 0.1),
            "Defense/BreachPrevented": int(not self.breach_occurred),
            "Defense/Diversity_Avg": self.diversity,
            "Defense/Redundancy_Avg": self.redundancy,
            "Cost/Total": self.total_cost,
            "MTD/ShuffleCount": self.total_shuffles,
            "MTD/SwapCount": self.total_swaps,
            "Attack/ServicesFound": self.services_discovered,
            "Attack/ServicesExploited": self.services_exploited,
            "Attack/Phase": self.attacker_phase,
        }


# =============================================================================
# MTD 전략 클래스 - 공정한 비교용
# =============================================================================
class BaseMTDStrategy:
    name = "Base"

    def __init__(self):
        self.step = 0
        self.shuffle_count = 0
        self.swap_count = 0
        self.total_cost = 0.0

    def reset(self):
        self.step = 0
        self.shuffle_count = 0
        self.swap_count = 0
        self.total_cost = 0.0

    def get_action(self, state: np.ndarray, info: Dict = None) -> np.ndarray:
        raise NotImplementedError
        
    def get_stats(self) -> Dict[str, Any]:
        return {
            "shuffle_count": self.shuffle_count,
            "swap_count": self.swap_count,
            "total_cost": self.total_cost,
        }


class NoMTDStrategy(BaseMTDStrategy):
    """MTD 없음 - 기준선"""
    name = "No MTD"

    def get_action(self, state: np.ndarray, info: Dict = None) -> np.ndarray:
        self.step += 1
        return np.ones(ACTION_DIM) * -1.0  # 모든 액션 비활성화


class StaticMTDStrategy(BaseMTDStrategy):
    """Static MTD - 고정 주기 shuffle"""
    name = "Static MTD"

    def __init__(self, shuffle_period: int = 20, shuffle_intensity: float = 0.5):
        super().__init__()
        self.shuffle_period = shuffle_period
        self.shuffle_intensity = shuffle_intensity

    def get_action(self, state: np.ndarray, info: Dict = None) -> np.ndarray:
        self.step += 1
        action = np.ones(ACTION_DIM) * -1.0

        # 고정 주기로 shuffle
        if self.step % self.shuffle_period == 0:
            action[0] = self.shuffle_intensity * 2 - 1
            self.shuffle_count += 1
            self.total_cost += self.shuffle_intensity * 0.5

        # 기본 decoy
        action[2] = 0.2 * 2 - 1
        
        return action


class HeuristicMTDStrategy(BaseMTDStrategy):
    """
    Heuristic MTD - 규칙 기반 (현실적 조정)
    
    [v0.8.8] 과도한 액션 방지:
    - 최소 액션 간격 유지
    - 위협이 낮을 때는 액션 자제
    - RL과 공정한 비교를 위해 효율성 중시
    """
    name = "Heuristic MTD"

    def __init__(self):
        super().__init__()
        self.last_shuffle_step = -20
        self.last_swap_step = -30
        self.min_shuffle_interval = 8   # 최소 8스텝 간격
        self.min_swap_interval = 15     # 최소 15스텝 간격

    def reset(self):
        super().reset()
        self.last_shuffle_step = -20
        self.last_swap_step = -30

    def get_action(self, state: np.ndarray, info: Dict = None) -> np.ndarray:
        self.step += 1
        action = np.ones(ACTION_DIM) * -1.0

        # State 파싱
        progress = state[0] if len(state) > 0 else 0.0
        services_found = state[1] if len(state) > 1 else 0.0
        critical_found = state[2] if len(state) > 2 else 0.0
        exploit_progress = state[3] if len(state) > 3 else 0.0
        compromise_progress = state[4] if len(state) > 4 else 0.0
        diversity = state[5] if len(state) > 5 else 0.5

        # 위협 수준 계산
        threat = max(
            services_found * 0.4,
            critical_found * 0.6,
            exploit_progress * 0.8,
            compromise_progress
        )

        can_shuffle = (self.step - self.last_shuffle_step) >= self.min_shuffle_interval
        can_swap = (self.step - self.last_swap_step) >= self.min_swap_interval

        # === 규칙 기반 액션 (현실적) ===
        
        # 1. 고위협: Swap (exploitation 이상)
        if can_swap and compromise_progress > 0.3:
            intensity = 0.6
            action[5] = intensity * 2 - 1
            action[0] = 0.5 * 2 - 1  # shuffle도 함께
            self.swap_count += 1
            self.shuffle_count += 1
            self.total_cost += intensity * 1.3
            self.last_swap_step = self.step
            self.last_shuffle_step = self.step
            return action

        # 2. 중위협: Shuffle (서비스 발견)
        if can_shuffle and services_found > 0.2:
            intensity = 0.4 + threat * 0.3
            action[0] = intensity * 2 - 1
            self.shuffle_count += 1
            self.total_cost += intensity * 0.5
            self.last_shuffle_step = self.step
            return action

        # 3. 다양성 낮음: Shuffle
        if can_shuffle and diversity < 0.35:
            action[0] = 0.4 * 2 - 1
            self.shuffle_count += 1
            self.total_cost += 0.2
            self.last_shuffle_step = self.step
            return action

        # 4. 주기적 shuffle (25스텝마다)
        if can_shuffle and (self.step - self.last_shuffle_step) >= 25:
            action[0] = 0.3 * 2 - 1
            self.shuffle_count += 1
            self.total_cost += 0.15
            self.last_shuffle_step = self.step
            return action

        # 5. 기본 decoy 유지
        action[2] = 0.15 * 2 - 1
        
        return action


class RLMTDStrategy(BaseMTDStrategy):
    """RL 기반 MTD"""
    name = "RL MTD"

    def __init__(self, model_path: str, device: str = "cpu"):
        super().__init__()
        if not TORCH_AVAILABLE:
            raise RuntimeError("PyTorch required")

        self.device = device
        self.policy = ActorCritic(STATE_DIM, ACTION_DIM).to(device)

        checkpoint = torch.load(model_path, map_location=device, weights_only=True)
        if "policy" in checkpoint:
            self.policy.load_state_dict(checkpoint["policy"])
        else:
            self.policy.load_state_dict(checkpoint)
        self.policy.eval()
        print(f"✅ RL Policy loaded from {model_path}")

    def get_action(self, state: np.ndarray, info: Dict = None) -> np.ndarray:
        self.step += 1
        with torch.no_grad():
            state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)
            action, _, _ = self.policy.act(state_tensor, deterministic=True)
        
        action_np = action.cpu().numpy().squeeze()
        
        # 액션 카운트 추적
        scaled = (action_np + 1) / 2
        if scaled[0] > 0.25:
            self.shuffle_count += 1
            self.total_cost += scaled[0] * 0.5
        if len(scaled) > 5 and scaled[5] > 0.30:
            self.swap_count += 1
            self.total_cost += scaled[5] * 0.8
            
        return action_np


class RLCTIMTDStrategy(BaseMTDStrategy):
    """RL + CTI 통합 MTD"""
    name = "RL-CTI MTD"

    def __init__(self, model_path: str, cti_boost: float = 1.2, device: str = "cpu"):
        super().__init__()
        if not TORCH_AVAILABLE:
            raise RuntimeError("PyTorch required")

        self.device = device
        self.cti_boost = cti_boost
        self.policy = ActorCritic(STATE_DIM, ACTION_DIM).to(device)

        checkpoint = torch.load(model_path, map_location=device, weights_only=True)
        if "policy" in checkpoint:
            self.policy.load_state_dict(checkpoint["policy"])
        else:
            self.policy.load_state_dict(checkpoint)
        self.policy.eval()
        print(f"✅ RL-CTI Policy loaded from {model_path}")

    def get_action(self, state: np.ndarray, info: Dict = None) -> np.ndarray:
        self.step += 1
        with torch.no_grad():
            state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)
            action, _, _ = self.policy.act(state_tensor, deterministic=True)

        action_np = action.cpu().numpy().squeeze()

        # CTI 부스트 (위협 감지 시)
        exploit_progress = state[3] if len(state) > 3 else 0
        compromise_progress = state[4] if len(state) > 4 else 0
        
        if exploit_progress > 0.1 or compromise_progress > 0.2:
            action_np = np.clip(action_np * self.cti_boost, -1, 1)

        # 액션 카운트
        scaled = (action_np + 1) / 2
        if scaled[0] > 0.25:
            self.shuffle_count += 1
            self.total_cost += scaled[0] * 0.5
        if len(scaled) > 5 and scaled[5] > 0.30:
            self.swap_count += 1
            self.total_cost += scaled[5] * 0.8

        return action_np


# =============================================================================
# Experiment Result
# =============================================================================
@dataclass
class ExperimentResult:
    seeker_level: int
    mtd_mode: str
    episodes: int
    metrics: Dict[str, float]
    raw_metrics: List[Dict]
    episode_metrics: List[Dict]


# =============================================================================
# Evaluation Functions
# =============================================================================
def run_single_experiment(
    seeker_level: int,
    mtd_strategy: BaseMTDStrategy,
    num_episodes: int = 50,
    max_steps: int = 200,
    seed: int = 42,
) -> ExperimentResult:
    """단일 실험 실행"""
    cfg = MTDConfig()
    all_metrics = []
    episode_metrics_list = []
    
    for ep in range(num_episodes):
        # 공정한 비교 환경 사용
        env = FairComparisonEnv(
            seed=seed + ep * 100 + seeker_level,
            seeker_level=seeker_level,
            config=cfg,
        )
        
        mtd_strategy.reset()
        state, info = env.reset()
        episode_reward = 0.0
        
        for step in range(max_steps):
            action = mtd_strategy.get_action(state, info)
            state, reward, terminated, truncated, info = env.step(action)
            episode_reward += reward
            
            if terminated or truncated:
                break
        
        # 전략 통계
        strategy_stats = mtd_strategy.get_stats()
        
        info["reward"] = episode_reward
        info["steps"] = step + 1
        info["strategy_shuffle_count"] = strategy_stats["shuffle_count"]
        info["strategy_swap_count"] = strategy_stats["swap_count"]
        info["strategy_cost"] = strategy_stats["total_cost"]
        
        all_metrics.append(info)
        
        episode_metrics_list.append({
            "episode": ep,
            "reward": episode_reward,
            "des": info.get("MTD/DES", 0),
            "mttc": info.get("MTD/MTTC", 200),
            "survival": info.get("Defense/BreachPrevented", 0),
            "shuffle_count": strategy_stats["shuffle_count"],
            "swap_count": strategy_stats["swap_count"],
        })
    
    # 집계
    aggregated = {}
    for key in all_metrics[0].keys():
        values = [m.get(key, 0) for m in all_metrics]
        if all(isinstance(v, (int, float, np.number)) for v in values):
            aggregated[f"{key}_mean"] = float(np.mean(values))
            aggregated[f"{key}_std"] = float(np.std(values))
    
    return ExperimentResult(
        seeker_level=seeker_level,
        mtd_mode=mtd_strategy.name,
        episodes=num_episodes,
        metrics=aggregated,
        raw_metrics=all_metrics,
        episode_metrics=episode_metrics_list,
    )


def run_all_experiments(
    rl_model_path: Optional[str] = None,
    num_episodes: int = 50,
    max_steps: int = 200,
    seed: int = 42,
    output_dir: str = "eval_results_v088",
    include_static: bool = True,
    include_rl_cti: bool = False,
) -> Dict[str, ExperimentResult]:
    """모든 실험 실행"""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # 전략 목록
    strategies: List[BaseMTDStrategy] = [NoMTDStrategy()]
    
    if include_static:
        strategies.append(StaticMTDStrategy())
    
    strategies.append(HeuristicMTDStrategy())
    
    if rl_model_path and TORCH_AVAILABLE:
        if os.path.exists(rl_model_path):
            try:
                strategies.append(RLMTDStrategy(rl_model_path))
                if include_rl_cti:
                    strategies.append(RLCTIMTDStrategy(rl_model_path, cti_boost=1.2))
            except Exception as e:
                print(f"⚠️ Failed to load RL model: {e}")
        else:
            print(f"⚠️ Model not found: {rl_model_path}")
    else:
        print("⚠️ No RL model specified or PyTorch not available")
    
    seeker_levels = [0, 1, 2, 3, 4]
    results = {}
    
    print("\n" + "=" * 100)
    print("MTD Comparison Evaluation v08.8 (Fair Comparison)")
    print("=" * 100)
    print(f"Seeker Levels: {seeker_levels}")
    print(f"MTD Strategies: {[s.name for s in strategies]}")
    print(f"Episodes: {num_episodes}")
    print("=" * 100 + "\n")
    
    total_experiments = len(seeker_levels) * len(strategies)
    current = 0
    
    for level in seeker_levels:
        for strategy in strategies:
            current += 1
            level_name = SEEKER_PROFILES[level]["name"]
            
            print(
                f"[{current}/{total_experiments}] "
                f"Level {level} ({level_name}) + {strategy.name}...",
                end=" ",
                flush=True
            )
            
            result = run_single_experiment(
                seeker_level=level,
                mtd_strategy=strategy,
                num_episodes=num_episodes,
                max_steps=max_steps,
                seed=seed,
            )
            
            key = f"L{level}_{strategy.name.replace(' ', '_').replace('-', '_')}"
            results[key] = result
            
            des = result.metrics.get('MTD/DES_mean', 0)
            mttc = result.metrics.get('MTD/MTTC_mean', 200)
            survival = result.metrics.get('Defense/BreachPrevented_mean', 0)
            shuffles = result.metrics.get('strategy_shuffle_count_mean', 0)
            swaps = result.metrics.get('strategy_swap_count_mean', 0)
            cost = result.metrics.get('Cost/Total_mean', 0)
            
            print(f"DES: {des:.3f} | MTTC: {mttc:.0f} | Survive: {survival:.1%} | "
                  f"Sh: {shuffles:.0f} | Sw: {swaps:.0f} | Cost: {cost:.1f}")
    
    # 결과 저장 및 시각화
    save_results(results, output_path)
    generate_publication_plots(results, output_path)
    print_comparison_table(results, seeker_levels)
    
    print(f"\n✅ Results saved to {output_path}")
    return results


def save_results(results: Dict[str, ExperimentResult], output_path: Path):
    """결과 저장"""
    json_data = {}
    for key, result in results.items():
        json_data[key] = {
            "seeker_level": result.seeker_level,
            "mtd_mode": result.mtd_mode,
            "episodes": result.episodes,
            "metrics": {k: to_serializable(v) for k, v in result.metrics.items()},
        }
    
    with open(output_path / "results.json", "w") as f:
        json.dump(json_data, f, indent=2)


def generate_publication_plots(results: Dict[str, ExperimentResult], output_path: Path):
    """논문 품질 시각화"""
    set_publication_style()
    
    levels = [0, 1, 2, 3, 4]
    level_names = ["Script\nKiddie", "Hobbyist", "Professional", "Expert", "APT"]
    
    mtd_modes = list(set(r.mtd_mode for r in results.values()))
    mode_order = ["No MTD", "Static MTD", "Heuristic MTD", "RL MTD", "RL-CTI MTD"]
    mtd_modes = [m for m in mode_order if m in mtd_modes]
    
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    
    # (a) DES Bar Chart
    ax = axes[0, 0]
    x = np.arange(len(levels))
    width = 0.8 / len(mtd_modes)
    
    for i, mode in enumerate(mtd_modes):
        values = []
        errors = []
        for level in levels:
            key = f"L{level}_{mode.replace(' ', '_').replace('-', '_')}"
            if key in results:
                values.append(results[key].metrics.get("MTD/DES_mean", 0))
                errors.append(results[key].metrics.get("MTD/DES_std", 0))
            else:
                values.append(0)
                errors.append(0)
        
        offset = (i - len(mtd_modes)/2 + 0.5) * width
        ax.bar(x + offset, values, width,
               label=mode, color=COLORS.get(mode, '#999'),
               yerr=errors, capsize=2,
               hatch=HATCHES[i % len(HATCHES)],
               edgecolor='black', linewidth=0.5)
    
    ax.set_xlabel('Attacker Sophistication Level')
    ax.set_ylabel('Defense Effectiveness Score (DES)')
    ax.set_title('(a) Defense Effectiveness by Attacker Level')
    ax.set_xticks(x)
    ax.set_xticklabels(level_names)
    ax.set_ylim(0, 1.0)
    ax.legend(loc='upper right', ncol=2, framealpha=0.9, fontsize=8)
    ax.grid(axis='y', alpha=0.3, linestyle='--')
    
    # (b) MTTC Line
    ax = axes[0, 1]
    for mode in mtd_modes:
        values = []
        for level in levels:
            key = f"L{level}_{mode.replace(' ', '_').replace('-', '_')}"
            if key in results:
                values.append(results[key].metrics.get("MTD/MTTC_mean", 200))
            else:
                values.append(200)
        ax.plot(levels, values, marker=MARKERS.get(mode, 'o'),
                color=COLORS.get(mode, '#999'), label=mode, linewidth=2, markersize=8)
    
    ax.set_xlabel('Attacker Sophistication Level')
    ax.set_ylabel('MTTC (steps)')
    ax.set_title('(b) Mean Time To Compromise')
    ax.set_xticks(levels)
    ax.legend(loc='best', framealpha=0.9, fontsize=8)
    ax.grid(True, alpha=0.3, linestyle='--')
    
    # (c) ASR Line
    ax = axes[1, 0]
    for mode in mtd_modes:
        values = []
        for level in levels:
            key = f"L{level}_{mode.replace(' ', '_').replace('-', '_')}"
            if key in results:
                values.append(results[key].metrics.get("MTD/ASR_mean", 0))
            else:
                values.append(0)
        ax.plot(levels, values, marker=MARKERS.get(mode, 'o'),
                color=COLORS.get(mode, '#999'), label=mode, linewidth=2, markersize=8)
    
    ax.set_xlabel('Attacker Sophistication Level')
    ax.set_ylabel('Attack Surface Reduction (ASR)')
    ax.set_title('(c) Attack Surface Reduction')
    ax.set_xticks(levels)
    ax.set_ylim(0, 1.0)
    ax.legend(loc='best', framealpha=0.9, fontsize=8)
    ax.grid(True, alpha=0.3, linestyle='--')
    
    # (d) Cost-Effectiveness
    ax = axes[1, 1]
    for mode in mtd_modes:
        costs = []
        effectiveness = []
        for level in levels:
            key = f"L{level}_{mode.replace(' ', '_').replace('-', '_')}"
            if key in results:
                costs.append(results[key].metrics.get("Cost/Total_mean", 0))
                effectiveness.append(results[key].metrics.get("MTD/DES_mean", 0))
        
        if costs and effectiveness:
            ax.scatter(costs, effectiveness,
                       label=mode, color=COLORS.get(mode, '#999'),
                       marker=MARKERS.get(mode, 'o'), s=100, alpha=0.8,
                       edgecolors='black', linewidth=0.5)
            for j, level in enumerate(levels):
                if j < len(costs):
                    ax.annotate(f"L{level}", (costs[j], effectiveness[j]),
                                textcoords="offset points", xytext=(4, 4),
                                fontsize=8, alpha=0.8)
    
    ax.set_xlabel('Total MTD Cost')
    ax.set_ylabel('Defense Effectiveness Score (DES)')
    ax.set_title('(d) Cost-Effectiveness Trade-off')
    ax.legend(loc='best', framealpha=0.9, fontsize=8)
    ax.grid(True, alpha=0.3, linestyle='--')
    
    plt.tight_layout()
    plt.savefig(output_path / "fig_main_results.png", dpi=300)
    plt.savefig(output_path / "fig_main_results.pdf", format='pdf')
    plt.close()
    
    print(f"✅ Figures saved to {output_path}")


def print_comparison_table(results: Dict[str, ExperimentResult], levels: List[int]):
    """비교 테이블 출력"""
    mtd_modes = list(set(r.mtd_mode for r in results.values()))
    mode_order = ["No MTD", "Static MTD", "Heuristic MTD", "RL MTD", "RL-CTI MTD"]
    mtd_modes = [m for m in mode_order if m in mtd_modes]
    
    print("\n" + "=" * 140)
    print("COMPARISON TABLE (v0.8.8 Fair Comparison)")
    print("=" * 140)
    header = (
        f"{'Level':<12} {'MTD Mode':<15} {'DES':>8} {'MTTC':>8} {'ASR':>8} "
        f"{'CDI':>8} {'Shuffle':>8} {'Swap':>6} {'Cost':>8} {'Survive':>10}"
    )
    print(header)
    print("-" * 140)
    
    for level in levels:
        for mode in mtd_modes:
            key = f"L{level}_{mode.replace(' ', '_').replace('-', '_')}"
            if key in results:
                r = results[key]
                level_name = SEEKER_PROFILES[level]["name"][:10]
                print(
                    f"L{level} {level_name:<9} {mode:<15} "
                    f"{r.metrics.get('MTD/DES_mean', 0):>8.3f} "
                    f"{r.metrics.get('MTD/MTTC_mean', 0):>8.0f} "
                    f"{r.metrics.get('MTD/ASR_mean', 0):>8.3f} "
                    f"{r.metrics.get('MTD/CDI_mean', 0):>8.3f} "
                    f"{r.metrics.get('strategy_shuffle_count_mean', 0):>8.0f} "
                    f"{r.metrics.get('strategy_swap_count_mean', 0):>6.0f} "
                    f"{r.metrics.get('Cost/Total_mean', 0):>8.1f} "
                    f"{r.metrics.get('Defense/BreachPrevented_mean', 0)*100:>9.1f}%"
                )
    print("=" * 140)
    
    # 전략별 평균
    print("\n📊 Strategy Average (across all levels):")
    print("-" * 80)
    for mode in mtd_modes:
        mode_results = [r for r in results.values() if r.mtd_mode == mode]
        if mode_results:
            avg_des = np.mean([r.metrics.get("MTD/DES_mean", 0) for r in mode_results])
            avg_survival = np.mean([r.metrics.get("Defense/BreachPrevented_mean", 0) for r in mode_results])
            avg_cost = np.mean([r.metrics.get("Cost/Total_mean", 0) for r in mode_results])
            avg_shuffles = np.mean([r.metrics.get("strategy_shuffle_count_mean", 0) for r in mode_results])
            avg_swaps = np.mean([r.metrics.get("strategy_swap_count_mean", 0) for r in mode_results])
            
            print(f"  {mode:<15}: DES={avg_des:.3f} | Survive={avg_survival:.1%} | "
                  f"Cost={avg_cost:.1f} | Shuffle={avg_shuffles:.0f} | Swap={avg_swaps:.0f}")


# =============================================================================
# CLI
# =============================================================================
def main():
    parser = argparse.ArgumentParser(description="MTD Comparison Evaluation v08.8 (Fair Comparison)")
    
    parser.add_argument("--rl-model", type=str, default=None,
                        help="RL model checkpoint path (REQUIRED for RL comparison)")
    parser.add_argument("--episodes", type=int, default=50)
    parser.add_argument("--max-steps", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output-dir", type=str, default="eval_results_v088")
    parser.add_argument("--include-static", action="store_true", default=True)
    parser.add_argument("--include-rl-cti", action="store_true")
    
    args = parser.parse_args()
    
    if not args.rl_model:
        print("\n" + "!" * 60)
        print("⚠️  WARNING: No RL model specified!")
        print("   Use --rl-model checkpoints_v08/best.pt")
        print("   Only baseline strategies will be evaluated.")
        print("!" * 60 + "\n")
    
    run_all_experiments(
        rl_model_path=args.rl_model,
        num_episodes=args.episodes,
        max_steps=args.max_steps,
        seed=args.seed,
        output_dir=args.output_dir,
        include_static=args.include_static,
        include_rl_cti=args.include_rl_cti,
    )


if __name__ == "__main__":
    main()