#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enhanced MTD RL Training v10 - Paper-Accurate Implementation
===========================================================

v09 → v10 주요 수정:
1. 논문 수식 정확 구현 기반 학습
2. 논문 Figure 7 스타일 학습 그래프 생성 (Reward + DES Convergence)
3. best.pt 모델 저장 및 로딩
4. CTI Table 12/13 성능 지표 반영 학습
5. 커리큘럼 학습 (Phase 0-3)
6. Wandb 통합 + 실시간 메트릭

논문 기반:
- PPO 알고리즘 사용
- Curriculum Learning (4 phases)
- DES 기반 성능 평가
- CTI F1=0.79, Balanced Accuracy=0.847 반영

저자: MTD-RL Research Team
버전: 1.0.0 (Paper Implementation)
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import pickle
import random
import time
from collections import defaultdict, deque
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torch.distributions import Normal
from torch.utils.tensorboard import SummaryWriter

# Plotting for paper figures
try:
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend
    import matplotlib.pyplot as plt
    import seaborn as sns
    plt.style.use('default')
    PLOTTING_AVAILABLE = True
except ImportError:
    PLOTTING_AVAILABLE = False
    print("⚠️ Matplotlib not available. Plots will be skipped.")

# Environment
try:
    from rl_environment_v10 import MTDEnvironment, DefenseStrategy, STATE_DIM, ACTION_DIM
    ENV_AVAILABLE = True
except ImportError:
    print("❌ rl_environment_v10.py not found. Cannot proceed.")
    ENV_AVAILABLE = False
    exit(1)

# Wandb (optional)
try:
    import wandb
    WANDB_AVAILABLE = True
except ImportError:
    WANDB_AVAILABLE = False
    print("⚠️ Wandb not available. Online logging disabled.")


# =============================================================================
# Training Configuration
# =============================================================================
@dataclass
class TrainingConfig:
    """논문 기반 학습 설정 (올바른 시간 스케일)"""
    
    # Environment (세밀한 시간 제어)
    max_episodes: int = 2000
    max_steps_per_episode: int = 150      # 150 * 2초 = 300초 (5분 미션)
    step_duration: float = 2.0            # 2초마다 RL 의사결정 (세밀한 제어)
    seeker_levels: List[int] = field(default_factory=lambda: [0, 1, 2, 3, 4])
    
    # MTD Intensity → 실행 간격 매핑 (현실적 범위)
    mtd_intervals: Dict[str, Dict[str, float]] = field(default_factory=lambda: {
        'shuffle': {'min': 30.0, 'max': 180.0},    # intensity 1.0=30초, 0.1=165초 간격
        'port_hop': {'min': 20.0, 'max': 120.0},   # intensity 1.0=20초, 0.1=108초 간격
        'decoy': {'min': 45.0, 'max': 200.0},      # intensity 1.0=45초, 0.1=185초 간격
        'blacklist': {'min': 15.0, 'max': 90.0},   # intensity 1.0=15초, 0.1=82.5초 간격
        'swap': {'min': 60.0, 'max': 300.0},       # intensity 1.0=60초, 0.1=276초 간격
    })
    
    # PPO Hyperparameters (논문 기준)
    learning_rate: float = 3e-4
    gamma: float = 0.99
    gae_lambda: float = 0.95
    clip_ratio: float = 0.2
    value_coeff: float = 0.5
    entropy_coeff: float = 0.01
    max_grad_norm: float = 0.5
    
    # Network Architecture
    hidden_sizes: List[int] = field(default_factory=lambda: [128, 128])
    activation: str = "tanh"
    
    # Training
    batch_size: int = 64
    update_epochs: int = 10
    target_kl: float = 0.01
    
    # Curriculum Learning (논문 Figure 7)
    curriculum_phases: List[Dict] = field(default_factory=lambda: [
        {"episodes": 500, "name": "Phase 0", "seeker_mix": [0.6, 0.3, 0.1, 0.0, 0.0]},
        {"episodes": 600, "name": "Phase 1", "seeker_mix": [0.3, 0.4, 0.3, 0.0, 0.0]},
        {"episodes": 500, "name": "Phase 2", "seeker_mix": [0.1, 0.2, 0.4, 0.3, 0.0]},
        {"episodes": 400, "name": "Phase 3", "seeker_mix": [0.0, 0.1, 0.3, 0.4, 0.2]},
    ])
    
    # Evaluation
    eval_episodes: int = 10
    eval_interval: int = 50
    save_interval: int = 100
    
    # Logging
    log_interval: int = 10
    plot_interval: int = 100
    
    # Paths
    output_dir: str = "./models"
    log_dir: str = "./logs"
    plots_dir: str = "./plots"
    
    def get_current_phase(self, episode: int) -> Tuple[int, Dict]:
        """현재 에피소드의 커리큘럼 페이즈 반환"""
        cumulative = 0
        for i, phase in enumerate(self.curriculum_phases):
            cumulative += phase["episodes"]
            if episode < cumulative:
                return i, phase
        return len(self.curriculum_phases) - 1, self.curriculum_phases[-1]
    
    def sample_seeker_level(self, episode: int, rng: np.random.Generator) -> int:
        """현재 페이즈에 따른 seeker 레벨 샘플링"""
        phase_idx, phase = self.get_current_phase(episode)
        seeker_mix = phase["seeker_mix"]
        return rng.choice(self.seeker_levels, p=seeker_mix)


# =============================================================================
# PPO Networks (논문 기준)
# =============================================================================
class PolicyNetwork(nn.Module):
    """정책 네트워크"""
    
    def __init__(self, state_dim: int, action_dim: int, hidden_sizes: List[int], activation: str = "tanh"):
        super().__init__()
        
        self.action_dim = action_dim
        
        # Activation function
        if activation == "tanh":
            self.activation = nn.Tanh()
        elif activation == "relu":
            self.activation = nn.ReLU()
        else:
            raise ValueError(f"Unknown activation: {activation}")
        
        # Shared layers
        layers = []
        prev_size = state_dim
        for hidden_size in hidden_sizes:
            layers.extend([
                nn.Linear(prev_size, hidden_size),
                self.activation
            ])
            prev_size = hidden_size
        
        self.shared = nn.Sequential(*layers)
        
        # Policy head (mean)
        self.mean_head = nn.Linear(prev_size, action_dim)
        
        # Log std (learnable parameter)
        self.log_std = nn.Parameter(torch.zeros(action_dim) - 0.5)
        
    def forward(self, state: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """Forward pass"""
        x = self.shared(state)
        mean = self.mean_head(x)
        
        # Constrain mean to [-1, 1] using tanh
        mean = torch.tanh(mean)
        
        std = torch.exp(torch.clamp(self.log_std, min=-10, max=2))
        
        return mean, std
    
    def get_action_and_logprob(self, state: torch.Tensor, action: Optional[torch.Tensor] = None):
        """액션 샘플링 및 log probability 계산"""
        mean, std = self.forward(state)
        
        dist = Normal(mean, std)
        
        if action is None:
            action = dist.sample()
        
        # Squash to [-1, 1] using tanh
        action_squashed = torch.tanh(action)
        
        # Log probability with Jacobian correction for tanh squashing
        logprob = dist.log_prob(action).sum(axis=-1)
        logprob -= (2 * (np.log(2) - action - F.softplus(-2 * action))).sum(axis=-1)
        
        return action_squashed, logprob


class ValueNetwork(nn.Module):
    """가치 네트워크"""
    
    def __init__(self, state_dim: int, hidden_sizes: List[int], activation: str = "tanh"):
        super().__init__()
        
        # Activation function
        if activation == "tanh":
            self.activation = nn.Tanh()
        elif activation == "relu":
            self.activation = nn.ReLU()
        else:
            raise ValueError(f"Unknown activation: {activation}")
        
        # Layers
        layers = []
        prev_size = state_dim
        for hidden_size in hidden_sizes:
            layers.extend([
                nn.Linear(prev_size, hidden_size),
                self.activation
            ])
            prev_size = hidden_size
        
        layers.append(nn.Linear(prev_size, 1))
        
        self.network = nn.Sequential(*layers)
        
    def forward(self, state: torch.Tensor) -> torch.Tensor:
        """Forward pass"""
        return self.network(state).squeeze(-1)


# =============================================================================
# PPO Agent
# =============================================================================
class PPOAgent:
    """PPO 에이전트 (논문 구현)"""
    
    def __init__(self, config: TrainingConfig, device: str = "cpu"):
        self.config = config
        self.device = torch.device(device)
        
        # Networks
        self.policy = PolicyNetwork(
            STATE_DIM, ACTION_DIM, 
            config.hidden_sizes, config.activation
        ).to(self.device)
        
        self.value_net = ValueNetwork(
            STATE_DIM,
            config.hidden_sizes, config.activation
        ).to(self.device)
        
        # Optimizers
        self.policy_optimizer = optim.Adam(self.policy.parameters(), lr=config.learning_rate)
        self.value_optimizer = optim.Adam(self.value_net.parameters(), lr=config.learning_rate)
        
        # Training stats
        self.update_count = 0
        
    def predict(self, state: np.ndarray, deterministic: bool = False) -> Tuple[np.ndarray, None]:
        """예측 (평가용)"""
        state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)
        
        with torch.no_grad():
            if deterministic:
                mean, _ = self.policy(state_tensor)
                action = mean
            else:
                action, _ = self.policy.get_action_and_logprob(state_tensor)
            
        return action.cpu().numpy()[0], None
    
    def get_action_and_value(self, state: np.ndarray) -> Tuple[np.ndarray, float, float]:
        """액션과 가치 예측"""
        state_tensor = torch.FloatTensor(state).to(self.device)
        
        with torch.no_grad():
            action, logprob = self.policy.get_action_and_logprob(state_tensor)
            value = self.value_net(state_tensor)
            
        return action.cpu().numpy(), logprob.cpu().item(), value.cpu().item()
    
    def update(self, rollout_data: Dict) -> Dict[str, float]:
        """PPO 업데이트"""
        states = torch.FloatTensor(rollout_data['states']).to(self.device)
        actions = torch.FloatTensor(rollout_data['actions']).to(self.device)
        old_logprobs = torch.FloatTensor(rollout_data['logprobs']).to(self.device)
        returns = torch.FloatTensor(rollout_data['returns']).to(self.device)
        advantages = torch.FloatTensor(rollout_data['advantages']).to(self.device)
        
        # Normalize advantages
        advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)
        
        # Update metrics
        policy_losses = []
        value_losses = []
        entropies = []
        kl_divs = []
        
        # Multiple epochs of updates
        for epoch in range(self.config.update_epochs):
            # Random minibatches
            indices = torch.randperm(len(states))
            
            for start in range(0, len(states), self.config.batch_size):
                end = start + self.config.batch_size
                batch_indices = indices[start:end]
                
                # Batch data
                batch_states = states[batch_indices]
                batch_actions = actions[batch_indices]
                batch_old_logprobs = old_logprobs[batch_indices]
                batch_returns = returns[batch_indices]
                batch_advantages = advantages[batch_indices]
                
                # Policy update
                _, new_logprobs = self.policy.get_action_and_logprob(batch_states, batch_actions)
                
                # Ratio
                ratio = torch.exp(new_logprobs - batch_old_logprobs)
                
                # Surrogate losses
                surr1 = ratio * batch_advantages
                surr2 = torch.clamp(ratio, 1 - self.config.clip_ratio, 1 + self.config.clip_ratio) * batch_advantages
                
                policy_loss = -torch.min(surr1, surr2).mean()
                
                # Entropy
                mean, std = self.policy(batch_states)
                entropy = Normal(mean, std).entropy().sum(axis=-1).mean()
                
                # Total policy loss
                total_policy_loss = policy_loss - self.config.entropy_coeff * entropy
                
                # Policy gradient step
                self.policy_optimizer.zero_grad()
                total_policy_loss.backward()
                nn.utils.clip_grad_norm_(self.policy.parameters(), self.config.max_grad_norm)
                self.policy_optimizer.step()
                
                # Value update
                values = self.value_net(batch_states)
                value_loss = F.mse_loss(values, batch_returns)
                
                self.value_optimizer.zero_grad()
                value_loss.backward()
                nn.utils.clip_grad_norm_(self.value_net.parameters(), self.config.max_grad_norm)
                self.value_optimizer.step()
                
                # Metrics
                policy_losses.append(policy_loss.item())
                value_losses.append(value_loss.item())
                entropies.append(entropy.item())
                
                # KL divergence (for early stopping)
                with torch.no_grad():
                    kl_div = (batch_old_logprobs - new_logprobs).mean().item()
                    kl_divs.append(kl_div)
            
            # Early stopping based on KL divergence
            mean_kl = np.mean(kl_divs)
            if mean_kl > self.config.target_kl:
                break
        
        self.update_count += 1
        
        return {
            'policy_loss': np.mean(policy_losses),
            'value_loss': np.mean(value_losses),
            'entropy': np.mean(entropies),
            'kl_div': np.mean(kl_divs),
            'update_epochs': epoch + 1,
        }
    
    def save(self, filepath: str):
        """모델 저장"""
        torch.save({
            'policy_state_dict': self.policy.state_dict(),
            'value_state_dict': self.value_net.state_dict(),
            'policy_optimizer_state_dict': self.policy_optimizer.state_dict(),
            'value_optimizer_state_dict': self.value_optimizer.state_dict(),
            'update_count': self.update_count,
        }, filepath)
    
    def load(self, filepath: str):
        """모델 로딩"""
        checkpoint = torch.load(filepath, map_location=self.device)
        self.policy.load_state_dict(checkpoint['policy_state_dict'])
        self.value_net.load_state_dict(checkpoint['value_state_dict'])
        self.policy_optimizer.load_state_dict(checkpoint['policy_optimizer_state_dict'])
        self.value_optimizer.load_state_dict(checkpoint['value_optimizer_state_dict'])
        self.update_count = checkpoint['update_count']


# =============================================================================
# Rollout Buffer
# =============================================================================
class RolloutBuffer:
    """PPO Rollout Buffer"""
    
    def __init__(self, gamma: float, gae_lambda: float):
        self.gamma = gamma
        self.gae_lambda = gae_lambda
        self.reset()
    
    def reset(self):
        """버퍼 초기화"""
        self.states = []
        self.actions = []
        self.rewards = []
        self.values = []
        self.logprobs = []
        self.dones = []
    
    def add(self, state: np.ndarray, action: np.ndarray, reward: float, 
            value: float, logprob: float, done: bool):
        """데이터 추가"""
        self.states.append(state)
        self.actions.append(action)
        self.rewards.append(reward)
        self.values.append(value)
        self.logprobs.append(logprob)
        self.dones.append(done)
    
    def compute_gae(self, next_value: float = 0.0) -> Dict[str, np.ndarray]:
        """GAE 계산"""
        values = np.array(self.values + [next_value])
        rewards = np.array(self.rewards)
        dones = np.array(self.dones)
        
        # Advantages
        advantages = np.zeros_like(rewards)
        gae = 0
        
        for t in reversed(range(len(rewards))):
            delta = rewards[t] + self.gamma * values[t + 1] * (1 - dones[t]) - values[t]
            gae = delta + self.gamma * self.gae_lambda * (1 - dones[t]) * gae
            advantages[t] = gae
        
        # Returns
        returns = advantages + np.array(self.values)
        
        return {
            'states': np.array(self.states),
            'actions': np.array(self.actions),
            'rewards': np.array(self.rewards),
            'values': np.array(self.values),
            'logprobs': np.array(self.logprobs),
            'returns': returns,
            'advantages': advantages,
        }


# =============================================================================
# Training Metrics & Logging
# =============================================================================
@dataclass
class TrainingMetrics:
    """학습 메트릭 (Attack Phase 추적 포함)"""
    episode_rewards: List[float] = field(default_factory=list)
    episode_des_scores: List[float] = field(default_factory=list)
    episode_costs: List[float] = field(default_factory=list)
    episode_breach_rates: List[float] = field(default_factory=list)
    episode_mttc: List[float] = field(default_factory=list)
    
    policy_losses: List[float] = field(default_factory=list)
    value_losses: List[float] = field(default_factory=list)
    entropies: List[float] = field(default_factory=list)
    kl_divs: List[float] = field(default_factory=list)
    
    cti_detections: List[int] = field(default_factory=list)
    cti_classifications: List[int] = field(default_factory=list)
    
    # Attack Phase Progress Tracking
    phase_progressions: List[Dict[str, int]] = field(default_factory=list)
    max_phases_reached: List[str] = field(default_factory=list)
    defense_probabilities: List[List[float]] = field(default_factory=list)
    
    def add_episode(self, info: Dict):
        """에피소드 메트릭 추가 (Attack Phase 정보 포함)"""
        self.episode_rewards.append(info.get('total_reward', 0))
        self.episode_des_scores.append(info.get('MTD/DES', 0))
        self.episode_costs.append(info.get('Cost/Total', 0))
        self.episode_breach_rates.append(1.0 if info.get('breach_occurred', False) else 0.0)
        self.episode_mttc.append(info.get('MTD/MTTC', 0))
        self.cti_detections.append(info.get('CTI/DetectionsCount', 0))
        self.cti_classifications.append(info.get('CTI/ClassificationsCount', 0))
        
        # Attack Phase 정보 추가
        phase_progression = info.get('phase_progression', {})
        self.phase_progressions.append(phase_progression)
        
        max_phase = info.get('max_phase_reached', 'S0_INITIAL')
        self.max_phases_reached.append(max_phase)
        
        defense_prob_history = info.get('defense_probability_history', [])
        self.defense_probabilities.append(defense_prob_history)
    
    def add_update(self, update_info: Dict):
        """업데이트 메트릭 추가"""
        self.policy_losses.append(update_info.get('policy_loss', 0))
        self.value_losses.append(update_info.get('value_loss', 0))
        self.entropies.append(update_info.get('entropy', 0))
        self.kl_divs.append(update_info.get('kl_div', 0))
    
    def get_recent_mean(self, key: str, window: int = 100) -> float:
        """최근 윈도우의 평균"""
        values = getattr(self, key, [])
        if not values:
            return 0.0
        return np.mean(values[-window:])


# =============================================================================
# Plotting Functions (논문 Figure 7 스타일)
# =============================================================================
def plot_paper_convergence_curves(
    metrics: TrainingMetrics, 
    config: TrainingConfig,
    save_dir: str,
    title_suffix: str = ""
):
    """논문 Figure 7 스타일 수렴 곡선 생성"""
    if not PLOTTING_AVAILABLE:
        return
    
    # 논문 스타일 설정
    plt.style.use('default')
    plt.rcParams.update({
        'font.size': 14,
        'font.family': 'serif',
        'font.serif': ['Times', 'DejaVu Serif'],
        'axes.linewidth': 1.0,
        'grid.alpha': 0.3,
        'figure.dpi': 300,
        'savefig.dpi': 300,
        'savefig.bbox': 'tight',
        'savefig.pad_inches': 0.2
    })
    
    episodes = np.arange(len(metrics.episode_rewards))
    
    # 이동평균 계산
    window = 50
    rewards_smooth = []
    des_smooth = []
    
    for i in range(len(metrics.episode_rewards)):
        start = max(0, i - window // 2)
        end = min(len(metrics.episode_rewards), i + window // 2 + 1)
        rewards_smooth.append(np.mean(metrics.episode_rewards[start:end]))
        des_smooth.append(np.mean(metrics.episode_des_scores[start:end]))
    
    # 표준편차 계산
    rewards_std = []
    des_std = []
    
    for i in range(len(metrics.episode_rewards)):
        start = max(0, i - window // 2)
        end = min(len(metrics.episode_rewards), i + window // 2 + 1)
        rewards_std.append(np.std(metrics.episode_rewards[start:end]))
        des_std.append(np.std(metrics.episode_des_scores[start:end]))
    
    rewards_smooth = np.array(rewards_smooth)
    des_smooth = np.array(des_smooth)
    rewards_std = np.array(rewards_std)
    des_std = np.array(des_std)
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
    
    # (a) Reward Convergence
    ax1.plot(episodes, rewards_smooth, color='purple', linewidth=2, label='Episode Reward')
    ax1.fill_between(episodes, 
                    rewards_smooth - rewards_std, 
                    rewards_smooth + rewards_std,
                    color='purple', alpha=0.3, label='95% CI')
    
    # Phase 구분선 추가
    cumulative = 0
    phase_colors = ['red', 'blue', 'green', 'orange']
    for i, phase in enumerate(config.curriculum_phases):
        cumulative += phase["episodes"]
        if cumulative < len(episodes):
            ax1.axvline(x=cumulative, color=phase_colors[i % len(phase_colors)], 
                       linestyle='--', alpha=0.7, linewidth=1.5)
            if i < len(config.curriculum_phases) - 1:
                mid_point = cumulative - phase["episodes"] // 2
                ax1.text(mid_point, max(rewards_smooth) * 0.9, 
                        phase["name"], ha='center', fontsize=12,
                        bbox=dict(boxstyle="round,pad=0.3", facecolor="lightgray", alpha=0.8))
    
    ax1.set_xlabel('Episode', fontsize=14)
    ax1.set_ylabel('Episode Reward', fontsize=14)
    ax1.set_title('(a) Reward Convergence' + title_suffix, fontsize=16, fontweight='bold')
    ax1.legend(fontsize=12)
    ax1.grid(True, alpha=0.3)
    
    # (b) DES Convergence
    ax2.plot(episodes, des_smooth, color='cyan', linewidth=2, label='Defense Effectiveness Score')
    ax2.fill_between(episodes,
                    des_smooth - des_std,
                    des_smooth + des_std,
                    color='cyan', alpha=0.3, label='95% CI')
    
    # Phase 구분선
    cumulative = 0
    for i, phase in enumerate(config.curriculum_phases):
        cumulative += phase["episodes"]
        if cumulative < len(episodes):
            ax2.axvline(x=cumulative, color=phase_colors[i % len(phase_colors)], 
                       linestyle='--', alpha=0.7, linewidth=1.5)
    
    ax2.set_xlabel('Episode', fontsize=14)
    ax2.set_ylabel('Defense Effectiveness Score (DES)', fontsize=14)
    ax2.set_title('(b) DES Convergence' + title_suffix, fontsize=16, fontweight='bold')
    ax2.legend(fontsize=12)
    ax2.grid(True, alpha=0.3)
    ax2.set_ylim(0, 1.0)
    
    plt.tight_layout()
    
    # 저장
    save_path = Path(save_dir) / f'Fig7_learning_convergence{title_suffix.replace(" ", "_")}.png'
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"📈 논문 Figure 7 스타일 학습 곡선 저장: {save_path}")


def plot_training_metrics(metrics: TrainingMetrics, save_dir: str):
    """상세 학습 메트릭 플롯"""
    if not PLOTTING_AVAILABLE:
        return
    
    fig, axes = plt.subplots(2, 3, figsize=(18, 12))
    fig.suptitle('Training Metrics Overview', fontsize=16, fontweight='bold')
    
    # Breach Rate
    window = 100
    breach_smooth = []
    for i in range(len(metrics.episode_breach_rates)):
        start = max(0, i - window // 2)
        end = min(len(metrics.episode_breach_rates), i + window // 2 + 1)
        breach_smooth.append(np.mean(metrics.episode_breach_rates[start:end]))
    
    axes[0,0].plot(breach_smooth, color='red', linewidth=2)
    axes[0,0].set_title('Breach Rate (Moving Average)')
    axes[0,0].set_ylabel('Breach Rate')
    axes[0,0].grid(True, alpha=0.3)
    
    # Cost
    cost_smooth = []
    for i in range(len(metrics.episode_costs)):
        start = max(0, i - window // 2)
        end = min(len(metrics.episode_costs), i + window // 2 + 1)
        cost_smooth.append(np.mean(metrics.episode_costs[start:end]))
    
    axes[0,1].plot(cost_smooth, color='orange', linewidth=2)
    axes[0,1].set_title('Total Cost (Moving Average)')
    axes[0,1].set_ylabel('Cost')
    axes[0,1].grid(True, alpha=0.3)
    
    # MTTC
    mttc_smooth = []
    for i in range(len(metrics.episode_mttc)):
        start = max(0, i - window // 2)
        end = min(len(metrics.episode_mttc), i + window // 2 + 1)
        mttc_smooth.append(np.mean(metrics.episode_mttc[start:end]))
    
    axes[0,2].plot(mttc_smooth, color='green', linewidth=2)
    axes[0,2].set_title('MTTC (Moving Average)')
    axes[0,2].set_ylabel('MTTC')
    axes[0,2].grid(True, alpha=0.3)
    
    # Policy Loss
    if metrics.policy_losses:
        axes[1,0].plot(metrics.policy_losses, color='blue', linewidth=1, alpha=0.7)
        axes[1,0].set_title('Policy Loss')
        axes[1,0].set_ylabel('Loss')
        axes[1,0].set_xlabel('Update')
        axes[1,0].grid(True, alpha=0.3)
    
    # Value Loss
    if metrics.value_losses:
        axes[1,1].plot(metrics.value_losses, color='purple', linewidth=1, alpha=0.7)
        axes[1,1].set_title('Value Loss')
        axes[1,1].set_ylabel('Loss')
        axes[1,1].set_xlabel('Update')
        axes[1,1].grid(True, alpha=0.3)
    
    # CTI Performance
    if metrics.cti_detections:
        cti_det_smooth = []
        for i in range(len(metrics.cti_detections)):
            start = max(0, i - window // 2)
            end = min(len(metrics.cti_detections), i + window // 2 + 1)
            cti_det_smooth.append(np.mean(metrics.cti_detections[start:end]))
        
        axes[1,2].plot(cti_det_smooth, color='teal', linewidth=2)
        axes[1,2].set_title('CTI Detections (Moving Average)')
        axes[1,2].set_ylabel('CTI Detections')
        axes[1,2].set_xlabel('Episode')
        axes[1,2].grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    save_path = Path(save_dir) / 'training_metrics_overview.png'
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"📊 상세 학습 메트릭 저장: {save_path}")


def plot_attack_phase_progression(metrics: TrainingMetrics, save_dir: str):
    """Attack Phase 진행도 분석 플롯"""
    if not PLOTTING_AVAILABLE:
        return
    
    if not metrics.max_phases_reached:
        print("⚠️ Attack Phase 데이터가 부족합니다.")
        return
    
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle('Attack Phase Progression Analysis', fontsize=16, fontweight='bold')
    
    # Phase별 도달 분포 (최근 100 에피소드)
    recent_phases = metrics.max_phases_reached[-min(100, len(metrics.max_phases_reached)):]
    
    phase_counts = {}
    phase_labels = ['S0_INITIAL', 'S1_RECONNAISSANCE', 'S2_DISCOVERY', 'S3_EXPLOITATION', 'S4_PERSISTENCE', 'S5_BREACH', 'DEFENDED']
    for label in phase_labels:
        phase_counts[label] = recent_phases.count(label)
    
    # 도넛 차트 - 최대 도달 단계 분포
    axes[0,0].pie(phase_counts.values(), labels=[f"{k.replace('_', ' ')}\n({v})" for k, v in phase_counts.items()], 
                  autopct='%1.1f%%', startangle=90)
    axes[0,0].set_title('Max Phase Reached\n(Recent 100 Episodes)')
    
    # 시간에 따른 최대 단계 변화
    phase_numeric = []
    phase_mapping = {'S0_INITIAL': 0, 'S1_RECONNAISSANCE': 1, 'S2_DISCOVERY': 2, 
                    'S3_EXPLOITATION': 3, 'S4_PERSISTENCE': 4, 'S5_BREACH': 5, 'DEFENDED': -1}
    
    for phase in metrics.max_phases_reached:
        phase_numeric.append(phase_mapping.get(phase, 0))
    
    window = 50
    phase_smooth = []
    for i in range(len(phase_numeric)):
        start = max(0, i - window // 2)
        end = min(len(phase_numeric), i + window // 2 + 1)
        phase_smooth.append(np.mean(phase_numeric[start:end]))
    
    axes[0,1].plot(phase_smooth, color='darkred', linewidth=2)
    axes[0,1].set_title('Max Phase Progression Over Time')
    axes[0,1].set_ylabel('Max Phase Reached')
    axes[0,1].set_xlabel('Episode')
    axes[0,1].set_yticks([-1, 0, 1, 2, 3, 4, 5])
    axes[0,1].set_yticklabels(['DEFENDED', 'S0', 'S1', 'S2', 'S3', 'S4', 'S5'])
    axes[0,1].grid(True, alpha=0.3)
    
    # 방어 확률 히스토리 분포
    if metrics.defense_probabilities:
        all_probs = []
        for ep_probs in metrics.defense_probabilities[-100:]:  # 최근 100 에피소드
            all_probs.extend(ep_probs)
        
        if all_probs:
            axes[1,0].hist(all_probs, bins=30, alpha=0.7, color='skyblue', edgecolor='black')
            axes[1,0].set_title('Defense Probability Distribution\n(Recent 100 Episodes)')
            axes[1,0].set_xlabel('Defense Probability')
            axes[1,0].set_ylabel('Frequency')
            axes[1,0].grid(True, alpha=0.3)
    
    # Breach Rate vs Max Phase 관계
    breach_by_phase = {phase: [] for phase in phase_labels}
    for i, (phase, breach) in enumerate(zip(metrics.max_phases_reached, metrics.episode_breach_rates)):
        breach_by_phase[phase].append(breach)
    
    phase_breach_means = []
    phase_names = []
    for phase in phase_labels:
        if breach_by_phase[phase]:
            phase_breach_means.append(np.mean(breach_by_phase[phase]) * 100)
            phase_names.append(phase.replace('_', ' '))
    
    if phase_names:
        bars = axes[1,1].bar(phase_names, phase_breach_means, color='lightcoral', alpha=0.8)
        axes[1,1].set_title('Breach Rate by Max Phase Reached')
        axes[1,1].set_ylabel('Breach Rate (%)')
        axes[1,1].tick_params(axis='x', rotation=45)
        axes[1,1].grid(True, alpha=0.3)
        
        # 값 표시
        for bar, value in zip(bars, phase_breach_means):
            axes[1,1].text(bar.get_x() + bar.get_width()/2., bar.get_height() + 1,
                          f'{value:.1f}%', ha='center', va='bottom', fontweight='bold')
    
    plt.tight_layout()
    
    save_path = Path(save_dir) / 'attack_phase_progression.png'
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"🎯 Attack Phase 진행도 분석 저장: {save_path}")


def plot_attack_phase_summary_table(metrics: TrainingMetrics, save_dir: str):
    """Attack Phase 요약 테이블 생성"""
    if not metrics.max_phases_reached:
        return
    
    # 최근 에피소드 분석
    recent_episodes = min(100, len(metrics.max_phases_reached))
    recent_phases = metrics.max_phases_reached[-recent_episodes:]
    recent_breach = metrics.episode_breach_rates[-recent_episodes:]
    
    phase_stats = {
        'Phase': ['S0 (Initial)', 'S1 (Recon)', 'S2 (Discovery)', 'S3 (Exploit)', 'S4 (Persist)', 'S5 (Breach)', 'Defended'],
        'Reached Count': [],
        'Reached %': [],
        'Avg Breach Rate': []
    }
    
    phase_mapping = {
        'S0_INITIAL': 0, 'S1_RECONNAISSANCE': 1, 'S2_DISCOVERY': 2,
        'S3_EXPLOITATION': 3, 'S4_PERSISTENCE': 4, 'S5_BREACH': 5, 'DEFENDED': 6
    }
    
    for i, phase_name in enumerate(['S0_INITIAL', 'S1_RECONNAISSANCE', 'S2_DISCOVERY', 'S3_EXPLOITATION', 'S4_PERSISTENCE', 'S5_BREACH', 'DEFENDED']):
        count = recent_phases.count(phase_name)
        percentage = (count / recent_episodes) * 100
        
        # 해당 단계에 도달한 에피소드들의 침해율
        phase_breaches = [recent_breach[j] for j, p in enumerate(recent_phases) if p == phase_name]
        avg_breach = np.mean(phase_breaches) * 100 if phase_breaches else 0
        
        phase_stats['Reached Count'].append(count)
        phase_stats['Reached %'].append(f"{percentage:.1f}%")
        phase_stats['Avg Breach Rate'].append(f"{avg_breach:.1f}%")
    
    # 요약 출력
    summary_path = Path(save_dir) / 'attack_phase_summary.txt'
    with open(summary_path, 'w') as f:
        f.write("=== ATTACK PHASE PROGRESSION SUMMARY ===\n")
        f.write(f"Recent {recent_episodes} Episodes Analysis\n\n")
        
        f.write("Phase Distribution:\n")
        for i, phase in enumerate(phase_stats['Phase']):
            f.write(f"  {phase}: {phase_stats['Reached Count'][i]} episodes ({phase_stats['Reached %'][i]}) - Breach Rate: {phase_stats['Avg Breach Rate'][i]}\n")
        
        f.write(f"\nOverall Metrics:\n")
        f.write(f"  Total Breach Rate: {np.mean(recent_breach) * 100:.1f}%\n")
        f.write(f"  Average Max Phase: {np.mean([phase_mapping.get(p, 0) for p in recent_phases]):.1f}\n")
        
        # 개선 여부 분석
        first_half = recent_phases[:recent_episodes//2]
        second_half = recent_phases[recent_episodes//2:]
        
        first_avg = np.mean([phase_mapping.get(p, 0) for p in first_half])
        second_avg = np.mean([phase_mapping.get(p, 0) for p in second_half])
        
        f.write(f"\nLearning Progress:\n")
        f.write(f"  First Half Avg Phase: {first_avg:.1f}\n")
        f.write(f"  Second Half Avg Phase: {second_avg:.1f}\n")
        f.write(f"  Progress: {'+' if second_avg > first_avg else '-'}{abs(second_avg - first_avg):.1f}\n")
    
    print(f"📋 Attack Phase 요약 저장: {summary_path}")


# =============================================================================
# Trainer
# =============================================================================
class MTDTrainer:
    """MTD RL 트레이너"""
    
    def __init__(self, config: TrainingConfig, use_wandb: bool = False, device: str = "cpu"):
        self.config = config
        self.use_wandb = use_wandb
        self.device = device
        
        # 디렉토리 생성
        for dir_path in [config.output_dir, config.log_dir, config.plots_dir]:
            os.makedirs(dir_path, exist_ok=True)
        
        # 로깅 설정
        self._setup_logging()
        
        # 환경 (올바른 Intensity-Timing 연계)
        self.env = MTDEnvironment(
            strategy=DefenseStrategy.RL_CTI,
            seed=42,
            max_steps=config.max_steps_per_episode,
            step_duration=config.step_duration,  # 2초마다 RL 의사결정
            mtd_intervals=config.mtd_intervals   # Intensity → 실행 간격 매핑
        )
        
        # 에이전트
        self.agent = PPOAgent(config, device)
        
        # 버퍼
        self.buffer = RolloutBuffer(config.gamma, config.gae_lambda)
        
        # 메트릭
        self.metrics = TrainingMetrics()
        
        # TensorBoard
        self.writer = SummaryWriter(config.log_dir)
        
        # Wandb
        if self.use_wandb and WANDB_AVAILABLE:
            wandb.init(
                project="mtd-rl-paper",
                config=asdict(config),
                name=f"PPO_MTD_CTI_{int(time.time())}"
            )
        
        # 최고 성능 추적
        self.best_des = 0.0
        self.best_reward = float('-inf')
        
        self.logger.info("MTD Trainer initialized")
        
    def _setup_logging(self):
        """로깅 설정"""
        log_file = Path(self.config.log_dir) / "training.log"
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        
        self.logger = logging.getLogger(__name__)
    
    def train(self):
        """메인 학습 루프"""
        self.logger.info("🚀 Starting MTD RL Training (Paper Implementation)")
        self.logger.info(f"📋 Config: {self.config.max_episodes} episodes, {self.config.max_steps_per_episode} steps")
        
        rng = np.random.default_rng(42)
        
        for episode in range(self.config.max_episodes):
            # 커리큘럼 페이즈
            phase_idx, phase = self.config.get_current_phase(episode)
            seeker_level = self.config.sample_seeker_level(episode, rng)
            
            # 에피소드 실행
            episode_info = self._run_episode(seeker_level)
            
            # 메트릭 기록
            self.metrics.add_episode(episode_info)
            
            # 로깅
            if episode % self.config.log_interval == 0:
                self._log_episode(episode, episode_info, phase)
            
            # 업데이트
            if len(self.buffer.states) >= self.config.batch_size:
                update_info = self._update_agent()
                self.metrics.add_update(update_info)
                
                # TensorBoard 로깅
                self._log_tensorboard(episode, episode_info, update_info)
                
                # Wandb 로깅
                if self.use_wandb and WANDB_AVAILABLE:
                    self._log_wandb(episode, episode_info, update_info)
            
            # 평가 및 저장
            if episode % self.config.eval_interval == 0 and episode > 0:
                eval_results = self._evaluate()
                self._log_evaluation(episode, eval_results)
                
                # Best model 저장
                current_des = eval_results['mean_des']
                current_reward = eval_results['mean_reward']
                
                if current_des > self.best_des:
                    self.best_des = current_des
                    best_path = Path(self.config.output_dir) / "best.pt"
                    self.agent.save(str(best_path))
                    self.logger.info(f"✅ New best DES: {current_des:.3f}, saved to {best_path}")
                
                if current_reward > self.best_reward:
                    self.best_reward = current_reward
            
            # 정기 저장
            if episode % self.config.save_interval == 0 and episode > 0:
                save_path = Path(self.config.output_dir) / f"checkpoint_{episode}.pt"
                self.agent.save(str(save_path))
                self.logger.info(f"💾 Checkpoint saved: {save_path}")
            
            # 그래프 생성
            if episode % self.config.plot_interval == 0 and episode > 0:
                plot_paper_convergence_curves(
                    self.metrics, self.config, 
                    self.config.plots_dir,
                    f" (Episode {episode})"
                )
                plot_training_metrics(self.metrics, self.config.plots_dir)
                plot_attack_phase_progression(self.metrics, self.config.plots_dir)
                plot_attack_phase_summary_table(self.metrics, self.config.plots_dir)
        
        # 최종 저장
        final_path = Path(self.config.output_dir) / "final.pt"
        self.agent.save(str(final_path))
        
        # 최종 그래프
        plot_paper_convergence_curves(
            self.metrics, self.config, 
            self.config.plots_dir,
            " (Final)"
        )
        plot_training_metrics(self.metrics, self.config.plots_dir)
        plot_attack_phase_progression(self.metrics, self.config.plots_dir)
        plot_attack_phase_summary_table(self.metrics, self.config.plots_dir)
        
        # 학습 완료
        self.logger.info("✅ Training completed!")
        self.logger.info(f"📈 Best DES: {self.best_des:.3f}")
        self.logger.info(f"🏆 Best Reward: {self.best_reward:.1f}")
        
        if self.use_wandb and WANDB_AVAILABLE:
            wandb.finish()
    
    def _run_episode(self, seeker_level: int) -> Dict[str, Any]:
        """단일 에피소드 실행"""
        # 환경 초기화
        self.env.seeker_level = seeker_level
        state, _ = self.env.reset()
        
        episode_reward = 0.0
        step_count = 0
        
        while step_count < self.config.max_steps_per_episode:
            # 액션 선택
            action, logprob, value = self.agent.get_action_and_value(state)
            
            # 환경 스텝
            next_state, reward, terminated, truncated, info = self.env.step(action)
            
            # 버퍼에 추가
            self.buffer.add(state, action, reward, value, logprob, terminated or truncated)
            
            episode_reward += reward
            state = next_state
            step_count += 1
            
            if terminated or truncated:
                break
        
        # 에피소드 정보
        episode_info = info.copy()
        episode_info['total_reward'] = episode_reward
        episode_info['steps'] = step_count
        episode_info['seeker_level'] = seeker_level
        
        return episode_info
    
    def _update_agent(self) -> Dict[str, float]:
        """에이전트 업데이트"""
        # GAE 계산
        rollout_data = self.buffer.compute_gae()
        
        # 업데이트
        update_info = self.agent.update(rollout_data)
        
        # 버퍼 초기화
        self.buffer.reset()
        
        return update_info
    
    def _evaluate(self) -> Dict[str, float]:
        """평가 실행"""
        eval_rewards = []
        eval_des_scores = []
        eval_breach_rates = []
        eval_costs = []
        
        for _ in range(self.config.eval_episodes):
            # 랜덤 seeker 레벨
            seeker_level = random.randint(0, 4)
            self.env.seeker_level = seeker_level
            
            state, _ = self.env.reset()
            episode_reward = 0.0
            
            for _ in range(self.config.max_steps_per_episode):
                action, _ = self.agent.predict(state, deterministic=True)
                state, reward, terminated, truncated, info = self.env.step(action)
                episode_reward += reward
                
                if terminated or truncated:
                    break
            
            eval_rewards.append(episode_reward)
            eval_des_scores.append(info.get('MTD/DES', 0))
            eval_breach_rates.append(1.0 if info.get('breach_occurred', False) else 0.0)
            eval_costs.append(info.get('Cost/Total', 0))
        
        return {
            'mean_reward': np.mean(eval_rewards),
            'std_reward': np.std(eval_rewards),
            'mean_des': np.mean(eval_des_scores),
            'std_des': np.std(eval_des_scores),
            'mean_breach_rate': np.mean(eval_breach_rates),
            'mean_cost': np.mean(eval_costs),
        }
    
    def _log_episode(self, episode: int, info: Dict, phase: Dict):
        """에피소드 로깅 (Attack Phase 정보 포함)"""
        des = info.get('MTD/DES', 0)
        reward = info.get('total_reward', 0)
        cost = info.get('Cost/Total', 0)
        breach = info.get('breach_occurred', False)
        max_phase = info.get('max_phase_reached', 'S0').replace('_', '')
        
        self.logger.info(
            f"Episode {episode:4d} ({phase['name']}): "
            f"R={reward:6.1f}, DES={des:.3f}, "
            f"Cost={cost:.2f}, Breach={breach}, "
            f"MaxPhase={max_phase}, "
            f"L{info.get('seeker_level', 0)}"
        )
    
    def _log_evaluation(self, episode: int, eval_results: Dict):
        """평가 로깅"""
        self.logger.info(
            f"💡 Eval {episode:4d}: "
            f"R={eval_results['mean_reward']:.1f}±{eval_results['std_reward']:.1f}, "
            f"DES={eval_results['mean_des']:.3f}±{eval_results['std_des']:.3f}, "
            f"BR={eval_results['mean_breach_rate']:.2f}"
        )
    
    def _log_tensorboard(self, episode: int, episode_info: Dict, update_info: Dict):
        """TensorBoard 로깅"""
        # Episode metrics
        self.writer.add_scalar('Episode/Reward', episode_info.get('total_reward', 0), episode)
        self.writer.add_scalar('Episode/DES', episode_info.get('MTD/DES', 0), episode)
        self.writer.add_scalar('Episode/Cost', episode_info.get('Cost/Total', 0), episode)
        self.writer.add_scalar('Episode/BreachRate', 1.0 if episode_info.get('breach_occurred', False) else 0.0, episode)
        
        # Training metrics
        self.writer.add_scalar('Training/PolicyLoss', update_info.get('policy_loss', 0), self.agent.update_count)
        self.writer.add_scalar('Training/ValueLoss', update_info.get('value_loss', 0), self.agent.update_count)
        self.writer.add_scalar('Training/Entropy', update_info.get('entropy', 0), self.agent.update_count)
        self.writer.add_scalar('Training/KLDiv', update_info.get('kl_div', 0), self.agent.update_count)
        
        # CTI metrics
        self.writer.add_scalar('CTI/Detections', episode_info.get('CTI/DetectionsCount', 0), episode)
        self.writer.add_scalar('CTI/Classifications', episode_info.get('CTI/ClassificationsCount', 0), episode)
    
    def _log_wandb(self, episode: int, episode_info: Dict, update_info: Dict):
        """Wandb 로깅"""
        wandb.log({
            'episode': episode,
            'episode_reward': episode_info.get('total_reward', 0),
            'des': episode_info.get('MTD/DES', 0),
            'cost': episode_info.get('Cost/Total', 0),
            'breach_rate': 1.0 if episode_info.get('breach_occurred', False) else 0.0,
            'policy_loss': update_info.get('policy_loss', 0),
            'value_loss': update_info.get('value_loss', 0),
            'entropy': update_info.get('entropy', 0),
            'kl_div': update_info.get('kl_div', 0),
            'cti_detections': episode_info.get('CTI/DetectionsCount', 0),
            'cti_classifications': episode_info.get('CTI/ClassificationsCount', 0),
        })


# =============================================================================
# Model Loading Function
# =============================================================================
def load_trained_model(filepath: str, device: str = "cpu") -> PPOAgent:
    """학습된 모델 로딩"""
    config = TrainingConfig()  # Default config
    agent = PPOAgent(config, device)
    agent.load(filepath)
    return agent


# =============================================================================
# Main
# =============================================================================
def main():
    parser = argparse.ArgumentParser(description='MTD RL Training v10')
    parser.add_argument('--episodes', type=int, default=2000, help='Max episodes')
    parser.add_argument('--steps', type=int, default=200, help='Max steps per episode')
    parser.add_argument('--lr', type=float, default=3e-4, help='Learning rate')
    parser.add_argument('--device', type=str, default='cpu', help='Device (cpu/cuda)')
    parser.add_argument('--wandb', action='store_true', help='Use Wandb logging')
    parser.add_argument('--output-dir', type=str, default='./models', help='Output directory')
    parser.add_argument('--log-dir', type=str, default='./logs', help='Log directory')
    parser.add_argument('--plots-dir', type=str, default='./plots', help='Plots directory')
    
    args = parser.parse_args()
    
    # Configuration
    config = TrainingConfig(
        max_episodes=args.episodes,
        max_steps_per_episode=args.steps,
        learning_rate=args.lr,
        output_dir=args.output_dir,
        log_dir=args.log_dir,
        plots_dir=args.plots_dir,
    )
    
    print("🚀 MTD RL Training v10 - Paper Implementation")
    print("=" * 60)
    print(f"📊 Episodes: {config.max_episodes}")
    print(f"⏱️ Steps per episode: {config.max_steps_per_episode}")
    print(f"🧠 Learning rate: {config.learning_rate}")
    print(f"🖥️ Device: {args.device}")
    print(f"📁 Output: {config.output_dir}")
    print(f"📈 Plots: {config.plots_dir}")
    print()
    
    # Trainer
    trainer = MTDTrainer(config, use_wandb=args.wandb, device=args.device)
    
    # Training
    try:
        trainer.train()
    except KeyboardInterrupt:
        print("\n⚠️ Training interrupted by user")
        
        # 현재까지 결과 저장
        interrupted_path = Path(config.output_dir) / "interrupted.pt"
        trainer.agent.save(str(interrupted_path))
        print(f"💾 Interrupted model saved: {interrupted_path}")
        
        # 현재까지 그래프 생성
        if len(trainer.metrics.episode_rewards) > 0:
            plot_paper_convergence_curves(
                trainer.metrics, config, 
                config.plots_dir,
                " (Interrupted)"
            )
        
    print("✅ Training session completed!")


if __name__ == "__main__":
    main()