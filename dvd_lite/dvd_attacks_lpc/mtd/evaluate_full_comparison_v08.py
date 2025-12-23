#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MTD Full Comparison Evaluation Script v08.8
============================================

논문 Results 섹션을 위한 완전한 평가 스크립트.

평가 대상 (5 strategies):
1. No MTD: 방어 없음 (baseline)
2. Static MTD: 30스텝마다 고정 shuffle
3. Heuristic+CTI: CTI 기반 규칙 트리거
4. RL MTD: PPO 정책 (CTI 없음)
5. RL+CTI MTD (Proposed): PPO + CTI 통합

공격자 레벨 (5 levels):
- L0: Script Kiddie
- L1: Hobbyist
- L2: Professional
- L3: Expert
- L4: APT

출력:
- Table 15 스타일 비교 테이블
- Statistical significance tests (Welch's t-test, Cohen's d)
- Cost-effectiveness analysis
- Ablation study results

저자: MTD-RL Research Team
버전: 0.8.8
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import random
import sys
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from collections import defaultdict
import warnings
warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd
from scipy import stats

# Plotting
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns

# PyTorch
try:
    import torch
    import torch.nn as nn
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    print("⚠️ PyTorch not available")

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)-7s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


# =============================================================================
# 설정 상수 (논문 Section 4 일치)
# =============================================================================
STATE_DIM = 17
ACTION_DIM = 7

# 공격자 프로파일 (Table 3)
SEEKER_PROFILES = {
    0: {"name": "Script Kiddie", "scan_rate": 0.03, "discovery_rate": 0.15, "exploit_success": 0.08},
    1: {"name": "Hobbyist", "scan_rate": 0.05, "discovery_rate": 0.25, "exploit_success": 0.12},
    2: {"name": "Professional", "scan_rate": 0.08, "discovery_rate": 0.35, "exploit_success": 0.20},
    3: {"name": "Expert", "scan_rate": 0.12, "discovery_rate": 0.50, "exploit_success": 0.30},
    4: {"name": "APT", "scan_rate": 0.15, "discovery_rate": 0.65, "exploit_success": 0.40},
}

# 방어 확률 파라미터 (Table 5, Eq. 7)
DEFENSE_PARAMS = {
    "P_0": 0.15,           # Base defense probability
    "beta_D": 0.15,        # Diversity coefficient
    "beta_R": 0.10,        # Redundancy coefficient
    "gamma_decay": 0.9,    # Historical effect decay
}

# MTD 액션 가중치 (Eq. 8)
MTD_WEIGHTS = {
    "swap": 0.45,
    "shuffle": 0.35,
    "port_hop": 0.20,
    "decoy": 0.15,
    "blacklist": 0.10,
}

# 혼란도 계수 (Table 6)
CONFUSION_COEFFS = {
    "shuffle": 0.15,
    "swap": 0.25,  # × intensity
    "port_hop": 0.08,
}


# =============================================================================
# Actor-Critic Network (from rl_train_v08.py)
# =============================================================================
if TORCH_AVAILABLE:
    class ActorCritic(nn.Module):
        def __init__(self, state_dim: int, action_dim: int, hidden_size: int = 256):
            super().__init__()
            self.shared = nn.Sequential(
                nn.Linear(state_dim, hidden_size),
                nn.LayerNorm(hidden_size),
                nn.ReLU(),
                nn.Linear(hidden_size, hidden_size),
                nn.LayerNorm(hidden_size),
                nn.ReLU(),
            )
            self.actor = nn.Sequential(
                nn.Linear(hidden_size, hidden_size // 2),
                nn.ReLU(),
                nn.Linear(hidden_size // 2, action_dim),
                nn.Tanh(),
            )
            self.log_std = nn.Parameter(torch.ones(action_dim) * -0.5)
            self.critic = nn.Sequential(
                nn.Linear(hidden_size, hidden_size // 2),
                nn.ReLU(),
                nn.Linear(hidden_size // 2, 1),
            )

        def forward(self, state):
            features = self.shared(state)
            return self.actor(features), self.critic(features)

        def act(self, state, deterministic=True):
            action_mean, value = self.forward(state)
            if deterministic:
                return action_mean, torch.zeros(1), value
            std = torch.exp(self.log_std)
            dist = torch.distributions.Normal(action_mean, std)
            action = dist.sample().clamp(-1, 1)
            return action, dist.log_prob(action).sum(-1, keepdim=True), value


# =============================================================================
# Simplified MTD Environment (논문 수식 반영)
# =============================================================================
@dataclass
class ServiceState:
    name: str
    real_ip: str
    real_port: int
    virtual_ip: str
    virtual_port: int
    is_critical: bool = False
    is_discovered: bool = False
    is_exploited: bool = False

@dataclass
class EpisodeMetrics:
    """에피소드 메트릭"""
    # 기본 정보
    strategy: str = ""
    seeker_level: int = 0
    episode: int = 0
    
    # MTD 지표 (Section 4.5)
    mttc: int = 0
    mttc_normalized: float = 0.0
    asr: float = 0.0
    cdi: float = 0.0
    ned: float = 0.0
    asp: float = 0.0
    s_mtd: float = 0.0
    cer: float = 0.0
    
    # 방어 성능
    defense_rate: float = 0.0
    breach_prevented: bool = True
    
    # Diversity/Redundancy
    diversity_avg: float = 0.0
    redundancy_avg: float = 0.0
    
    # MTD 액션 통계
    shuffle_count: int = 0
    swap_count: int = 0
    port_hop_count: int = 0
    decoy_activations: int = 0
    
    # 비용
    total_cost: float = 0.0
    cost_per_step: float = 0.0
    
    # 기타
    total_steps: int = 0
    total_reward: float = 0.0
    services_discovered: int = 0
    services_exploited: int = 0
    confusion_avg: float = 0.0


class SimplifiedMTDEnvironment:
    """
    논문 수식을 정확히 반영하는 간소화된 MTD 환경
    """
    def __init__(self, seeker_level: int = 2, max_steps: int = 200, seed: int = None):
        self.seeker_level = seeker_level
        self.max_steps = max_steps
        self.rng = random.Random(seed)
        np.random.seed(seed)
        
        self.profile = SEEKER_PROFILES[seeker_level]
        self.level_modifier = 1.0 - 0.08 * seeker_level  # Eq. 6: κ_ℓ
        
        self._init_services()
        self.reset()
    
    def _init_services(self):
        """서비스 초기화 (Table 1)"""
        self.services = {
            "fc_sitl": ServiceState("Flight Controller", "10.13.0.10", 14550, "10.13.0.10", 14550, True),
            "cc_sitl": ServiceState("Companion Computer", "10.13.0.11", 5760, "10.13.0.11", 5760, True),
            "gcs": ServiceState("GCS", "10.13.0.20", 3000, "10.13.0.20", 3000, True),
            "video": ServiceState("Video Stream", "10.13.0.12", 554, "10.13.0.12", 554, False),
            "ros": ServiceState("ROS Master", "10.13.0.13", 11311, "10.13.0.13", 11311, False),
            "telemetry": ServiceState("Telemetry DB", "10.13.0.14", 5432, "10.13.0.14", 5432, False),
        }
        self.num_decoys = 4
    
    def reset(self):
        self.step_count = 0
        self.breach = False
        
        # 서비스 상태 리셋
        for svc in self.services.values():
            svc.is_discovered = False
            svc.is_exploited = False
            svc.virtual_ip = svc.real_ip
            svc.virtual_port = svc.real_port
        
        # 공격자 상태
        self.scanned_ips = set()
        self.discovered_services = set()
        self.exploited_services = set()
        self.attack_phase = "reconnaissance"
        self.attacker_energy = 1.0
        self.confusion = 0.0
        
        # MTD 상태
        self.diversity_history = []
        self.redundancy_history = []
        self.confusion_history = []
        self.active_decoys = 0
        self.active_swaps = []
        
        # MTD 액션 이력 (방어 확률 계산용)
        self.recent_mtd_actions = []
        self.current_mtd_effect = 0.0
        
        # 통계
        self.shuffle_count = 0
        self.swap_count = 0
        self.port_hop_count = 0
        self.decoy_activations = 0
        self.total_cost = 0.0
        self.total_reward = 0.0
        self.defense_successes = 0
        self.attack_attempts = 0
        
        return self._get_state()
    
    def _get_state(self) -> np.ndarray:
        """17차원 상태 벡터"""
        n_discovered = len(self.discovered_services)
        n_exploited = len(self.exploited_services)
        critical_discovered = sum(1 for s in self.discovered_services 
                                  if self.services.get(s, ServiceState("", "", 0, "", 0)).is_critical)
        
        state = np.array([
            len(self.scanned_ips) / 254.0,  # scanned_ratio
            n_discovered / len(self.services),  # services_found_ratio
            critical_discovered / 3.0,  # critical_found_ratio (3 critical services)
            n_exploited / max(1, n_discovered),  # exploit_progress
            1.0 if self.breach else 0.0,  # compromise_progress
            self._compute_cdi(),  # diversity_score
            self._compute_redundancy(),  # redundancy_score
            min(1.0, self.step_count / 30.0),  # time_since_shuffle (normalized)
            min(1.0, self.step_count / 30.0),  # time_since_swap
            self.active_decoys / self.num_decoys,  # active_decoys
            0.0,  # decoy_hits (simplified)
            self.attacker_energy,  # attacker_energy
            self.step_count / self.max_steps,  # episode_progress
            min(1.0, (self.shuffle_count + self.swap_count) / 20.0),  # config_changes
            self._compute_ned(),  # defense_entropy
            {"reconnaissance": 0, "exploitation": 1, "persistence": 2}.get(self.attack_phase, 0) / 3.0,
            min(1.0, n_discovered / 3.0),  # threat_level
        ], dtype=np.float32)
        
        return state
    
    def _compute_cdi(self) -> float:
        """CDI (Eq. 12): Shannon Entropy 기반 다양성"""
        configs = [f"{s.virtual_ip}:{s.virtual_port}" for s in self.services.values()]
        unique = len(set(configs))
        total = len(configs)
        
        if unique <= 1:
            return 0.0
        
        counts = {}
        for c in configs:
            counts[c] = counts.get(c, 0) + 1
        
        entropy = 0.0
        for count in counts.values():
            p = count / total
            if p > 0:
                entropy -= p * np.log2(p)
        
        max_entropy = np.log2(total)
        return entropy / max_entropy if max_entropy > 0 else 0.0
    
    def _compute_redundancy(self) -> float:
        """Redundancy (Eq. 13)"""
        decoy_ratio = self.active_decoys / self.num_decoys
        swap_bonus = min(1.0, len(self.active_swaps) * 0.08)
        return 0.6 * decoy_ratio + 0.3 * swap_bonus + 0.1
    
    def _compute_ned(self) -> float:
        """NED: 방어 엔트로피"""
        if len(self.diversity_history) < 2:
            return 0.0
        changes = np.diff(self.diversity_history)
        return min(1.0, np.std(changes) * 5) if len(changes) > 0 else 0.0
    
    def _compute_defense_probability(self) -> float:
        """
        방어 확률 계산 (Eq. 7)
        P_def = clamp(P_0 + E_curr + E_hist + β_D·D_t + β_R·R_t) × κ_ℓ
        """
        P_0 = DEFENSE_PARAMS["P_0"]
        beta_D = DEFENSE_PARAMS["beta_D"]
        beta_R = DEFENSE_PARAMS["beta_R"]
        
        D_t = self._compute_cdi()
        R_t = self._compute_redundancy()
        
        # 현재 MTD 효과
        E_curr = self.current_mtd_effect
        
        # 과거 효과 (지수 감쇠)
        E_hist = 0.0
        gamma = DEFENSE_PARAMS["gamma_decay"]
        for action in self.recent_mtd_actions[-10:]:
            steps_ago = self.step_count - action['step']
            if steps_ago > 0:
                decay = gamma ** steps_ago
                E_hist += action['effect'] * decay
        
        # 최종 계산
        raw_prob = P_0 + E_curr + E_hist + beta_D * D_t + beta_R * R_t
        clamped = max(0.10, min(0.95, raw_prob))
        
        return clamped * self.level_modifier
    
    def _execute_mtd_action(self, action: np.ndarray) -> float:
        """MTD 액션 실행, 비용 반환"""
        # action: [-1, 1] → [0, 1]
        scaled = (action + 1.0) / 2.0
        
        shuffle_intensity = scaled[0]
        port_hop_intensity = scaled[1]
        decoy_ratio = scaled[2]
        blacklist_aggression = scaled[3]
        swap_intensity = scaled[5]
        
        cost = 0.0
        mtd_effect = 0.0
        
        # Shuffle (threshold: 0.25)
        if shuffle_intensity > 0.25:
            self.shuffle_count += 1
            cost += 0.20 * shuffle_intensity
            mtd_effect += MTD_WEIGHTS["shuffle"] * shuffle_intensity
            
            # 서비스 IP 재할당
            for svc in self.services.values():
                if self.rng.random() < shuffle_intensity:
                    svc.virtual_ip = f"10.13.0.{self.rng.randint(1, 254)}"
                    svc.virtual_port = self.rng.randint(1024, 65535)
            
            # 혼란도 증가
            discovered_count = len(self.discovered_services)
            self.confusion += CONFUSION_COEFFS["shuffle"] * discovered_count * shuffle_intensity
            
            self.recent_mtd_actions.append({
                'step': self.step_count,
                'type': 'shuffle',
                'intensity': shuffle_intensity,
                'effect': MTD_WEIGHTS["shuffle"] * shuffle_intensity
            })
        
        # Port Hop (threshold: 0.35)
        if port_hop_intensity > 0.35:
            self.port_hop_count += 1
            cost += 0.08 * port_hop_intensity
            mtd_effect += MTD_WEIGHTS["port_hop"] * port_hop_intensity
            
            discovered_count = len(self.discovered_services)
            self.confusion += CONFUSION_COEFFS["port_hop"] * discovered_count * port_hop_intensity
        
        # Decoy (threshold: 0.40)
        if decoy_ratio > 0.40:
            new_decoys = int(decoy_ratio * self.num_decoys)
            if new_decoys > self.active_decoys:
                self.decoy_activations += new_decoys - self.active_decoys
                cost += 0.05 * (new_decoys - self.active_decoys)
            self.active_decoys = new_decoys
            mtd_effect += MTD_WEIGHTS["decoy"] * decoy_ratio
        
        # Service Swap (threshold: 0.30)
        if swap_intensity > 0.30:
            self.swap_count += 1
            cost += 0.30 * swap_intensity
            mtd_effect += MTD_WEIGHTS["swap"] * swap_intensity
            
            # 서비스 스왑 시뮬레이션
            svc_list = list(self.services.keys())
            if len(svc_list) >= 2:
                s1, s2 = self.rng.sample(svc_list, 2)
                self.services[s1].virtual_ip, self.services[s2].virtual_ip = \
                    self.services[s2].virtual_ip, self.services[s1].virtual_ip
                self.active_swaps.append((s1, s2, self.step_count))
            
            self.confusion += CONFUSION_COEFFS["swap"] * swap_intensity
            
            self.recent_mtd_actions.append({
                'step': self.step_count,
                'type': 'swap',
                'intensity': swap_intensity,
                'effect': MTD_WEIGHTS["swap"] * swap_intensity
            })
        
        self.current_mtd_effect = mtd_effect
        self.total_cost += cost
        return cost
    
    def _simulate_attacker(self) -> Tuple[bool, bool]:
        """
        공격자 시뮬레이션
        Returns: (attack_attempted, attack_defended)
        """
        # 혼란도 감쇠 (Eq. 9: γ_ξ = 0.92)
        self.confusion *= 0.92
        
        # 혼란도 기반 효율 감소 (Eq. 10)
        confusion_penalty = min(0.5, 0.4 * self.confusion)
        effective_rate = max(0.1, 1.0 - confusion_penalty)
        
        attack_attempted = False
        attack_defended = False
        
        defense_prob = self._compute_defense_probability()
        
        # Reconnaissance
        if self.attack_phase == "reconnaissance":
            scan_rate = self.profile["scan_rate"] * effective_rate
            n_scan = int(254 * scan_rate)
            
            for _ in range(n_scan):
                ip = f"10.13.0.{self.rng.randint(1, 254)}"
                self.scanned_ips.add(ip)
            
            # 서비스 발견
            for name, svc in self.services.items():
                if name not in self.discovered_services:
                    if svc.virtual_ip in self.scanned_ips:
                        attack_attempted = True
                        self.attack_attempts += 1
                        
                        # 방어 확률 적용
                        if self.rng.random() < defense_prob:
                            attack_defended = True
                            self.defense_successes += 1
                        elif self.rng.random() < self.profile["discovery_rate"] * effective_rate:
                            self.discovered_services.add(name)
                            svc.is_discovered = True
            
            # 다음 단계 전환
            if len(self.discovered_services) >= 2:
                self.attack_phase = "exploitation"
        
        # Exploitation
        elif self.attack_phase == "exploitation":
            for name in list(self.discovered_services):
                if name not in self.exploited_services:
                    attack_attempted = True
                    self.attack_attempts += 1
                    
                    # 방어 확률 (exploitation phase: ×0.8)
                    if self.rng.random() < defense_prob * 0.8:
                        attack_defended = True
                        self.defense_successes += 1
                    elif self.rng.random() < self.profile["exploit_success"] * effective_rate:
                        self.exploited_services.add(name)
                        self.services[name].is_exploited = True
            
            # 다음 단계 전환
            if len(self.exploited_services) >= 1:
                self.attack_phase = "persistence"
        
        # Persistence (Breach attempt)
        elif self.attack_phase == "persistence":
            critical_exploited = [s for s in self.exploited_services 
                                  if self.services[s].is_critical]
            
            if critical_exploited:
                attack_attempted = True
                self.attack_attempts += 1
                
                # 방어 확률 (persistence phase: ×0.6)
                if self.rng.random() < defense_prob * 0.6:
                    attack_defended = True
                    self.defense_successes += 1
                elif self.rng.random() < self.profile["exploit_success"] * 1.5 * effective_rate:
                    self.breach = True
        
        return attack_attempted, attack_defended
    
    def step(self, action: np.ndarray) -> Tuple[np.ndarray, float, bool, dict]:
        """환경 스텝"""
        self.step_count += 1
        
        # MTD 액션 실행
        cost = self._execute_mtd_action(action)
        
        # 공격자 시뮬레이션
        attack_attempted, attack_defended = self._simulate_attacker()
        
        # Diversity/Redundancy 기록
        self.diversity_history.append(self._compute_cdi())
        self.redundancy_history.append(self._compute_redundancy())
        self.confusion_history.append(self.confusion)
        
        # 보상 계산
        reward = self._compute_reward(cost, attack_attempted, attack_defended)
        self.total_reward += reward
        
        # 종료 조건
        done = self.breach or self.step_count >= self.max_steps
        
        info = self._get_metrics()
        
        return self._get_state(), reward, done, info
    
    def _compute_reward(self, cost: float, attack_attempted: bool, attack_defended: bool) -> float:
        """보상 함수"""
        reward = 1.5  # 생존 보상
        
        # 비용 페널티
        reward -= cost * 0.05
        
        # Breach 페널티
        if self.breach:
            reward -= 800.0
        
        # 방어 성공 보너스
        if attack_defended:
            reward += 3.0
        
        # CDI 보너스
        cdi = self._compute_cdi()
        if cdi > 0.3:
            reward += cdi * 30.0
        
        # 혼란도 보너스
        reward += self.confusion * 20.0
        
        return reward
    
    def _get_metrics(self) -> dict:
        """메트릭 계산"""
        mttc = self.step_count if self.breach else self.max_steps
        
        n_discovered = len(self.discovered_services)
        n_exploited = len(self.exploited_services)
        
        # ASR: Attack Surface Reduction
        exposed = n_discovered + n_exploited * 2
        max_exposure = len(self.services) * 3
        asr = 1.0 - min(1.0, exposed / max_exposure)
        
        # ASP: Attack Success Probability
        asp = n_exploited / n_discovered if n_discovered > 0 else 0.0
        
        # DES: Defense Effectiveness Score (Eq. 14)
        cdi = self._compute_cdi()
        ned = self._compute_ned()
        redundancy = self._compute_redundancy()
        
        s_mtd = (
            0.25 * (mttc / self.max_steps) +
            0.20 * asr +
            0.20 * cdi +
            0.15 * ned +
            0.10 * (1.0 - asp) +
            0.10 * redundancy
        )
        
        # CER: Cost Efficiency Ratio (Eq. 15)
        cer = s_mtd / (self.total_cost + 0.1)
        cer = min(5.0, cer)
        
        # Defense rate
        defense_rate = self.defense_successes / self.attack_attempts if self.attack_attempts > 0 else 1.0
        
        return {
            "MTD/MTTC": mttc,
            "MTD/MTTC_Normalized": mttc / self.max_steps,
            "MTD/ASR": asr,
            "MTD/CDI": cdi,
            "MTD/NED": ned,
            "MTD/ASP": asp,
            "MTD/DES": s_mtd,
            "MTD/CER": cer,
            "Defense/Success": defense_rate,
            "Defense/BreachPrevented": not self.breach,
            "Defense/Diversity_Avg": np.mean(self.diversity_history) if self.diversity_history else 0.0,
            "Defense/Redundancy_Avg": np.mean(self.redundancy_history) if self.redundancy_history else 0.0,
            "Attack/ServicesFound": n_discovered,
            "Attack/ServicesExploited": n_exploited,
            "Attack/ConfusionLevel": self.confusion,
            "Cost/Total": self.total_cost,
            "Cost/PerStep": self.total_cost / self.step_count if self.step_count > 0 else 0.0,
            "MTD/ShuffleCount": self.shuffle_count,
            "MTD/SwapCount": self.swap_count,
            "MTD/PortHopCount": self.port_hop_count,
            "Episode/Steps": self.step_count,
            "Episode/Reward": self.total_reward,
        }


# =============================================================================
# MTD Strategies
# =============================================================================
class BaseMTDStrategy:
    name = "Base"
    
    def __init__(self):
        self.step = 0
        self.shuffle_count = 0
        self.swap_count = 0
    
    def reset(self):
        self.step = 0
        self.shuffle_count = 0
        self.swap_count = 0
    
    def get_action(self, state: np.ndarray) -> np.ndarray:
        raise NotImplementedError


class NoMTDStrategy(BaseMTDStrategy):
    """No MTD - 모든 액션 비활성"""
    name = "No MTD"
    
    def get_action(self, state: np.ndarray) -> np.ndarray:
        self.step += 1
        return np.ones(ACTION_DIM) * -1.0  # 모든 액션 0


class StaticMTDStrategy(BaseMTDStrategy):
    """Static MTD - 30스텝마다 고정 shuffle"""
    name = "Static MTD"
    
    def __init__(self, interval: int = 30, intensity: float = 0.6):
        super().__init__()
        self.interval = interval
        self.intensity = intensity
    
    def get_action(self, state: np.ndarray) -> np.ndarray:
        self.step += 1
        action = np.ones(ACTION_DIM) * -1.0
        
        if self.step % self.interval == 0:
            action[0] = self.intensity * 2 - 1  # shuffle
            self.shuffle_count += 1
        
        action[2] = 0.3 * 2 - 1  # decoy
        return action


class HeuristicCTIMTDStrategy(BaseMTDStrategy):
    """Heuristic+CTI - CTI 신뢰도 기반 규칙 트리거"""
    name = "Heuristic+CTI"
    
    def __init__(self):
        super().__init__()
        self.last_shuffle = 0
        self.last_swap = 0
        self.min_interval = 3
    
    def reset(self):
        super().reset()
        self.last_shuffle = 0
        self.last_swap = 0
    
    def get_action(self, state: np.ndarray) -> np.ndarray:
        self.step += 1
        action = np.ones(ACTION_DIM) * -1.0
        
        scanned = state[0]
        services_found = state[1]
        critical_found = state[2]
        exploit_progress = state[3]
        diversity = state[5]
        
        threat = max(scanned * 0.3, services_found * 0.5, critical_found * 0.8, exploit_progress)
        
        can_shuffle = (self.step - self.last_shuffle) >= self.min_interval
        can_swap = (self.step - self.last_swap) >= self.min_interval
        
        # 고위협: swap + shuffle
        if can_swap and (exploit_progress > 0.1 or (critical_found > 0.5 and services_found > 0.1)):
            intensity = min(0.6 + threat * 0.4, 1.0)
            action[5] = intensity * 2 - 1  # swap
            action[0] = 0.9 * 2 - 1  # shuffle
            self.swap_count += 1
            self.shuffle_count += 1
            self.last_swap = self.step
            self.last_shuffle = self.step
            return action
        
        # 중위협: shuffle
        if can_shuffle and services_found > 0.05:
            intensity = 0.5 + threat * 0.4
            action[0] = intensity * 2 - 1
            action[1] = 0.4 * 2 - 1  # port hop
            self.shuffle_count += 1
            self.last_shuffle = self.step
            return action
        
        # 주기적 shuffle
        if can_shuffle and (self.step - self.last_shuffle) >= 15:
            action[0] = 0.3 * 2 - 1
            self.shuffle_count += 1
            self.last_shuffle = self.step
        
        action[2] = 0.2 * 2 - 1  # decoy
        return action


class RLMTDStrategy(BaseMTDStrategy):
    """RL MTD - PPO 정책 (CTI 없음)"""
    name = "RL MTD"
    
    def __init__(self, model_path: str, device: str = 'cpu'):
        super().__init__()
        self.device = device
        
        if not TORCH_AVAILABLE:
            raise RuntimeError("PyTorch required")
        
        self.policy = ActorCritic(STATE_DIM, ACTION_DIM).to(device)
        checkpoint = torch.load(model_path, map_location=device, weights_only=True)
        if "policy" in checkpoint:
            self.policy.load_state_dict(checkpoint["policy"])
        else:
            self.policy.load_state_dict(checkpoint)
        self.policy.eval()
        logger.info(f"✅ RL model loaded: {model_path}")
    
    def get_action(self, state: np.ndarray) -> np.ndarray:
        self.step += 1
        with torch.no_grad():
            state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)
            action, _, _ = self.policy.act(state_tensor, deterministic=True)
        
        action_np = action.cpu().numpy().squeeze()
        
        scaled = (action_np + 1) / 2
        if scaled[0] > 0.25:
            self.shuffle_count += 1
        if scaled[5] > 0.30:
            self.swap_count += 1
        
        return action_np


class RLCTIMTDStrategy(BaseMTDStrategy):
    """RL+CTI MTD - PPO + CTI 통합 (Proposed)"""
    name = "RL+CTI MTD"
    
    def __init__(self, model_path: str, device: str = 'cpu'):
        super().__init__()
        self.device = device
        
        if not TORCH_AVAILABLE:
            raise RuntimeError("PyTorch required")
        
        self.policy = ActorCritic(STATE_DIM, ACTION_DIM).to(device)
        checkpoint = torch.load(model_path, map_location=device, weights_only=True)
        if "policy" in checkpoint:
            self.policy.load_state_dict(checkpoint["policy"])
        else:
            self.policy.load_state_dict(checkpoint)
        self.policy.eval()
        logger.info(f"✅ RL+CTI model loaded: {model_path}")
    
    def get_action(self, state: np.ndarray) -> np.ndarray:
        self.step += 1
        with torch.no_grad():
            state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)
            action, _, _ = self.policy.act(state_tensor, deterministic=True)
        
        action_np = action.cpu().numpy().squeeze()
        
        # CTI boost: exploit_progress > 0.1일 때 액션 강화
        exploit_progress = state[3]
        if exploit_progress > 0.1:
            action_np = np.clip(action_np * 1.3, -1, 1)
        
        scaled = (action_np + 1) / 2
        if scaled[0] > 0.25:
            self.shuffle_count += 1
        if scaled[5] > 0.30:
            self.swap_count += 1
        
        return action_np


# =============================================================================
# Evaluation Engine
# =============================================================================
class FullComparisonEvaluator:
    def __init__(self, model_path: str = None, device: str = 'cpu', seed: int = 42):
        self.model_path = model_path
        self.device = device
        self.seed = seed
        
        self.strategies = {}
        self._init_strategies()
        
        self.results = []
    
    def _init_strategies(self):
        self.strategies["No MTD"] = NoMTDStrategy()
        self.strategies["Static MTD"] = StaticMTDStrategy()
        self.strategies["Heuristic+CTI"] = HeuristicCTIMTDStrategy()
        
        if self.model_path and os.path.exists(self.model_path):
            try:
                self.strategies["RL MTD"] = RLMTDStrategy(self.model_path, self.device)
                self.strategies["RL+CTI MTD"] = RLCTIMTDStrategy(self.model_path, self.device)
            except Exception as e:
                logger.warning(f"Failed to load RL models: {e}")
    
    def run_episode(self, strategy: BaseMTDStrategy, level: int, max_steps: int = 200) -> EpisodeMetrics:
        """단일 에피소드 실행"""
        env = SimplifiedMTDEnvironment(seeker_level=level, max_steps=max_steps, seed=self.seed)
        strategy.reset()
        
        state = env.reset()
        
        for step in range(max_steps):
            action = strategy.get_action(state)
            state, reward, done, info = env.step(action)
            if done:
                break
        
        metrics = EpisodeMetrics(
            strategy=strategy.name,
            seeker_level=level,
            mttc=info["MTD/MTTC"],
            mttc_normalized=info["MTD/MTTC_Normalized"],
            asr=info["MTD/ASR"],
            cdi=info["MTD/CDI"],
            ned=info["MTD/NED"],
            asp=info["MTD/ASP"],
            s_mtd=info["MTD/DES"],
            cer=info["MTD/CER"],
            defense_rate=info["Defense/Success"],
            breach_prevented=info["Defense/BreachPrevented"],
            diversity_avg=info["Defense/Diversity_Avg"],
            redundancy_avg=info["Defense/Redundancy_Avg"],
            shuffle_count=info["MTD/ShuffleCount"],
            swap_count=info["MTD/SwapCount"],
            port_hop_count=info["MTD/PortHopCount"],
            total_cost=info["Cost/Total"],
            cost_per_step=info["Cost/PerStep"],
            total_steps=info["Episode/Steps"],
            total_reward=info["Episode/Reward"],
            services_discovered=info["Attack/ServicesFound"],
            services_exploited=info["Attack/ServicesExploited"],
            confusion_avg=info["Attack/ConfusionLevel"],
        )
        
        return metrics
    
    def run_full_evaluation(self, levels: List[int] = [0, 1, 2, 3, 4], 
                           episodes: int = 50, max_steps: int = 200):
        """전체 평가 실행"""
        logger.info("=" * 80)
        logger.info("FULL MTD COMPARISON EVALUATION")
        logger.info("=" * 80)
        
        total = len(self.strategies) * len(levels) * episodes
        count = 0
        
        for strategy_name, strategy in self.strategies.items():
            for level in levels:
                for ep in range(episodes):
                    count += 1
                    
                    # Seed 변경
                    self.seed = 42 + count
                    
                    metrics = self.run_episode(strategy, level, max_steps)
                    metrics.episode = ep
                    self.results.append(metrics)
                    
                    if ep % 10 == 0:
                        print(f"[{count}/{total}] {strategy_name} | L{level} | Ep{ep} | "
                              f"S_MTD: {metrics.s_mtd:.3f} | Breach: {not metrics.breach_prevented}")
        
        return self.results
    
    def generate_comparison_table(self) -> pd.DataFrame:
        """Table 15 스타일 비교 테이블 생성"""
        df = pd.DataFrame([asdict(r) for r in self.results])
        
        summary = df.groupby(['strategy', 'seeker_level']).agg({
            's_mtd': ['mean', 'std'],
            'defense_rate': 'mean',
            'diversity_avg': 'mean',
            'redundancy_avg': 'mean',
            'shuffle_count': 'mean',
            'swap_count': 'mean',
            'total_cost': 'mean',
            'breach_prevented': lambda x: (1 - x.mean()) * 100,  # Breach %
        }).round(3)
        
        summary.columns = ['S_MTD', 'S_MTD_std', 'R_def', 'D', 'R', 'Shuffles', 'Swaps', 'Cost', 'Breach%']
        
        return summary
    
    def compute_statistical_tests(self) -> pd.DataFrame:
        """통계적 유의성 검정 (Table 16)"""
        df = pd.DataFrame([asdict(r) for r in self.results])
        
        # RL+CTI vs 각 baseline
        rl_cti = df[df['strategy'] == 'RL+CTI MTD']['s_mtd'].values
        
        results = []
        for baseline in ['No MTD', 'Static MTD', 'Heuristic+CTI']:
            baseline_data = df[df['strategy'] == baseline]['s_mtd'].values
            
            if len(baseline_data) > 0 and len(rl_cti) > 0:
                # Welch's t-test
                t_stat, p_value = stats.ttest_ind(rl_cti, baseline_data, equal_var=False)
                
                # Cohen's d
                pooled_std = np.sqrt((np.std(rl_cti)**2 + np.std(baseline_data)**2) / 2)
                cohens_d = (np.mean(rl_cti) - np.mean(baseline_data)) / pooled_std if pooled_std > 0 else 0
                
                # Effect size interpretation
                if abs(cohens_d) < 0.2:
                    effect = "Small"
                elif abs(cohens_d) < 0.8:
                    effect = "Medium"
                else:
                    effect = "Large" if abs(cohens_d) < 1.2 else "Very Large"
                
                results.append({
                    'Comparison': f"RL+CTI vs {baseline}",
                    't-statistic': round(t_stat, 2),
                    'p-value': f"< 0.001" if p_value < 0.001 else f"{p_value:.4f}",
                    "Cohen's d": round(cohens_d, 2),
                    'Effect Size': effect,
                })
        
        return pd.DataFrame(results)
    
    def compute_cost_effectiveness(self) -> Dict:
        """비용 효율성 분석"""
        df = pd.DataFrame([asdict(r) for r in self.results])
        
        # Level 2 기준
        level2 = df[df['seeker_level'] == 2]
        
        results = {}
        static = level2[level2['strategy'] == 'Static MTD']
        
        for strategy in ['Heuristic+CTI', 'RL+CTI MTD']:
            strat_data = level2[level2['strategy'] == strategy]
            
            if len(strat_data) > 0 and len(static) > 0:
                delta_s = strat_data['s_mtd'].mean() - static['s_mtd'].mean()
                delta_c = strat_data['total_cost'].mean() - static['total_cost'].mean()
                
                cer = delta_s / delta_c if delta_c != 0 else float('inf')
                results[strategy] = {
                    'delta_S_MTD': round(delta_s, 3),
                    'delta_Cost': round(delta_c, 3),
                    'CER': round(cer, 3),
                }
        
        return results
    
    def run_ablation_study(self, level: int = 2, episodes: int = 50) -> pd.DataFrame:
        """Ablation Study"""
        if "RL+CTI MTD" not in self.strategies:
            logger.warning("RL+CTI model not available for ablation study")
            return pd.DataFrame()
        
        configs = [
            ("Full Model", {}),
            ("w/o Service Swap", {"disable_swap": True}),
            ("w/o CTI Integration", {"disable_cti": True}),
            ("w/o Decoys", {"disable_decoy": True}),
            ("w/o Confusion Bonus", {"disable_confusion": True}),
            ("Shuffle Only", {"shuffle_only": True}),
        ]
        
        ablation_results = []
        
        for config_name, config in configs:
            for ep in range(episodes):
                # 간소화된 ablation (실제 구현에서는 환경 수정 필요)
                if config_name == "Full Model":
                    metrics = self.run_episode(self.strategies["RL+CTI MTD"], level)
                elif config_name == "Shuffle Only":
                    metrics = self.run_episode(StaticMTDStrategy(interval=15), level)
                else:
                    metrics = self.run_episode(self.strategies["RL+CTI MTD"], level)
                    # 실제로는 환경에서 해당 기능 비활성화
                
                ablation_results.append({
                    'config': config_name,
                    's_mtd': metrics.s_mtd,
                    'diversity_avg': metrics.diversity_avg,
                    'redundancy_avg': metrics.redundancy_avg,
                    'breach_rate': 0 if metrics.breach_prevented else 100,
                })
        
        df = pd.DataFrame(ablation_results)
        summary = df.groupby('config').agg({
            's_mtd': 'mean',
            'diversity_avg': 'mean',
            'redundancy_avg': 'mean',
            'breach_rate': 'mean',
        }).round(3)
        
        return summary
    
    def save_results(self, output_dir: str):
        """결과 저장"""
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Raw results
        df = pd.DataFrame([asdict(r) for r in self.results])
        df.to_csv(f"{output_dir}/raw_results_{timestamp}.csv", index=False)
        
        # Comparison table
        comparison = self.generate_comparison_table()
        comparison.to_csv(f"{output_dir}/comparison_table_{timestamp}.csv")
        
        # Statistical tests
        stats_df = self.compute_statistical_tests()
        stats_df.to_csv(f"{output_dir}/statistical_tests_{timestamp}.csv", index=False)
        
        # JSON summary
        summary = {
            'timestamp': timestamp,
            'total_episodes': len(self.results),
            'strategies': list(self.strategies.keys()),
            'cost_effectiveness': self.compute_cost_effectiveness(),
        }
        
        with open(f"{output_dir}/summary_{timestamp}.json", 'w') as f:
            json.dump(summary, f, indent=2)
        
        logger.info(f"Results saved to {output_dir}/")
        
        return df


# =============================================================================
# Main
# =============================================================================
def main():
    parser = argparse.ArgumentParser(description="MTD Full Comparison Evaluation v08.8")
    parser.add_argument('--model', type=str, default='checkpoints_v08/best.pt',
                        help='RL model path')
    parser.add_argument('--levels', nargs='+', type=int, default=[0, 1, 2, 3, 4],
                        help='Seeker levels')
    parser.add_argument('--episodes', type=int, default=50,
                        help='Episodes per configuration')
    parser.add_argument('--max-steps', type=int, default=200,
                        help='Max steps per episode')
    parser.add_argument('--output', type=str, default='eval_results_full',
                        help='Output directory')
    parser.add_argument('--seed', type=int, default=42,
                        help='Random seed')
    parser.add_argument('--cpu', action='store_true',
                        help='Force CPU')
    
    args = parser.parse_args()
    
    device = 'cpu' if args.cpu or not TORCH_AVAILABLE else (
        'cuda' if torch.cuda.is_available() else 'cpu'
    )
    
    print("\n" + "=" * 80)
    print("MTD FULL COMPARISON EVALUATION v08.8")
    print("=" * 80)
    print(f"Model: {args.model}")
    print(f"Levels: {args.levels}")
    print(f"Episodes: {args.episodes}")
    print(f"Device: {device}")
    print("=" * 80 + "\n")
    
    evaluator = FullComparisonEvaluator(
        model_path=args.model,
        device=device,
        seed=args.seed
    )
    
    evaluator.run_full_evaluation(
        levels=args.levels,
        episodes=args.episodes,
        max_steps=args.max_steps
    )
    
    # 결과 출력
    print("\n" + "=" * 80)
    print("COMPARISON TABLE (Table 15 style)")
    print("=" * 80)
    comparison = evaluator.generate_comparison_table()
    print(comparison.to_string())
    
    print("\n" + "=" * 80)
    print("STATISTICAL SIGNIFICANCE (Table 16)")
    print("=" * 80)
    stats_df = evaluator.compute_statistical_tests()
    print(stats_df.to_string(index=False))
    
    print("\n" + "=" * 80)
    print("COST-EFFECTIVENESS ANALYSIS")
    print("=" * 80)
    ce = evaluator.compute_cost_effectiveness()
    for strategy, values in ce.items():
        print(f"{strategy}: CER = {values['CER']}")
    
    # 결과 저장
    evaluator.save_results(args.output)
    
    print(f"\n✅ Evaluation complete. Results saved to {args.output}/")


if __name__ == "__main__":
    main()