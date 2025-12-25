#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MTD Real Model Evaluation + IEEE Paper Figures
===============================================
학습된 PPO 모델(best.pt)을 로드해서 실제 평가 수행 후 IEEE 스타일 그래프 생성

Usage:
    python mtd_real_evaluation_complete.py --model checkpoints_v08/best.pt

Requirements:
    pip install torch numpy matplotlib scienceplots

Author: MTD-RL Research Team
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
from datetime import datetime

import numpy as np
import torch
import torch.nn as nn
import matplotlib.pyplot as plt

# rl_config_v08, rl_environment_v08가 같은 디렉토리에 있어야 함
try:
    from rl_config_v08 import (
        ACTION_DIM,
        ACTION_PARAM_KEYS,
        SEEKER_PROFILES,
        STATE_DIM,
        MTDConfig,
    )
    from rl_environment_v08 import MTDEnvironment
    print("✅ rl_config_v08, rl_environment_v08 imported")
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("rl_config_v08.py와 rl_environment_v08.py가 같은 디렉토리에 필요합니다")
    sys.exit(1)


# =============================================================================
# Actor-Critic Network (rl_train_v08.py와 동일)
# =============================================================================
class ActorCritic(nn.Module):
    """Actor-Critic 네트워크"""

    def __init__(
        self,
        state_dim: int,
        action_dim: int,
        hidden_size: int = 256,
        num_layers: int = 2,
    ):
        super().__init__()

        self.state_dim = state_dim
        self.action_dim = action_dim
        self.hidden_size = hidden_size

        # Shared Feature Extractor
        layers = []
        input_dim = state_dim
        for i in range(num_layers):
            layers.extend([
                nn.Linear(input_dim, hidden_size),
                nn.LayerNorm(hidden_size),
                nn.ReLU(),
            ])
            input_dim = hidden_size
        self.shared = nn.Sequential(*layers)

        # Actor Head
        self.actor = nn.Sequential(
            nn.Linear(hidden_size, hidden_size // 2),
            nn.ReLU(),
            nn.Linear(hidden_size // 2, action_dim),
            nn.Tanh(),
        )

        # 액션 분산
        self.log_std = nn.Parameter(torch.ones(action_dim) * -0.5)

        # Critic Head
        self.critic = nn.Sequential(
            nn.Linear(hidden_size, hidden_size // 2),
            nn.ReLU(),
            nn.Linear(hidden_size // 2, 1),
        )

    def forward(self, state: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        features = self.shared(state)
        action_mean = self.actor(features)
        value = self.critic(features)
        return action_mean, value

    def act(self, state: torch.Tensor, deterministic: bool = False):
        action_mean, value = self.forward(state)
        if deterministic:
            return action_mean, torch.zeros(1), value
        std = torch.exp(self.log_std)
        from torch.distributions import Normal
        dist = Normal(action_mean, std)
        action = dist.sample()
        action = torch.clamp(action, -1, 1)
        log_prob = dist.log_prob(action).sum(dim=-1, keepdim=True)
        return action, log_prob, value


# =============================================================================
# Strategies
# =============================================================================
class RealRLCTIStrategy:
    """실제 학습된 PPO 모델 (RL+CTI)"""
    
    def __init__(self, model_path: str, device: str = "cpu", hidden_size: int = 256):
        self.device = device
        self.name = "RL+CTI MTD"
        
        self.policy = ActorCritic(
            state_dim=STATE_DIM,
            action_dim=ACTION_DIM,
            hidden_size=hidden_size,
        ).to(device)
        
        checkpoint = torch.load(model_path, map_location=device, weights_only=False)
        
        if "policy" in checkpoint:
            self.policy.load_state_dict(checkpoint["policy"])
            hs = checkpoint.get("hidden_size", hidden_size)
            print(f"✅ Model loaded: {model_path} (hidden_size={hs})")
        else:
            self.policy.load_state_dict(checkpoint)
            print(f"✅ Policy loaded: {model_path}")
        
        self.policy.eval()
    
    def get_action(self, state: np.ndarray) -> np.ndarray:
        state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)
        with torch.no_grad():
            action, _, _ = self.policy.act(state_tensor, deterministic=True)
        return action.cpu().numpy().squeeze()
    
    def reset(self):
        pass


class NoMTDStrategy:
    """MTD 없음 (Baseline)"""
    name = "No MTD"
    
    def get_action(self, state: np.ndarray) -> np.ndarray:
        return np.array([-1.0] * ACTION_DIM)
    
    def reset(self):
        pass


class StaticMTDStrategy:
    """고정 주기 MTD"""
    name = "Static MTD"
    
    def __init__(self):
        self.step = 0
    
    def get_action(self, state: np.ndarray) -> np.ndarray:
        self.step += 1
        action = np.array([-1.0] * ACTION_DIM)
        
        if self.step % 30 == 0:
            action[0] = 0.5  # shuffle
            action[1] = 0.3  # port_hop
        
        if self.step % 60 == 0:
            action[5] = 0.4  # swap
        
        action[2] = 0.3  # decoy always
        
        return action
    
    def reset(self):
        self.step = 0


class HeuristicCTIStrategy:
    """휴리스틱 + CTI 규칙 기반"""
    name = "Heuristic+CTI"
    
    def __init__(self):
        self.step = 0
    
    def get_action(self, state: np.ndarray) -> np.ndarray:
        self.step += 1
        action = np.array([-0.5] * ACTION_DIM)
        
        # threat_level (state[12] = normalized_risk)
        threat_level = state[12] if len(state) > 12 else 0.3
        
        if threat_level > 0.6:
            action[0] = 0.7  # shuffle
            action[2] = 0.6  # decoy
            action[5] = 0.5  # swap
        elif threat_level > 0.3:
            action[0] = 0.4
            action[2] = 0.4
        
        if self.step % 20 == 0:
            action[0] = max(action[0], 0.5)
            action[1] = 0.3
        
        return action
    
    def reset(self):
        self.step = 0


class RLOnlyStrategy:
    """RL만 (CTI 없이) - 모델에서 CTI 부분 무시"""
    name = "RL MTD"
    
    def __init__(self, model_path: str = None, device: str = "cpu", hidden_size: int = 256):
        self.device = device
        
        if model_path and os.path.exists(model_path):
            self.policy = ActorCritic(STATE_DIM, ACTION_DIM, hidden_size).to(device)
            checkpoint = torch.load(model_path, map_location=device, weights_only=False)
            if "policy" in checkpoint:
                self.policy.load_state_dict(checkpoint["policy"])
            else:
                self.policy.load_state_dict(checkpoint)
            self.policy.eval()
            self.use_model = True
        else:
            self.use_model = False
    
    def get_action(self, state: np.ndarray) -> np.ndarray:
        if self.use_model:
            # CTI 관련 상태를 0으로 마스킹
            state_masked = state.copy()
            # CTI confidence 관련 인덱스들을 0으로 (예: 인덱스 13-16)
            if len(state_masked) > 13:
                state_masked[13:] = 0.0
            
            state_tensor = torch.FloatTensor(state_masked).unsqueeze(0).to(self.device)
            with torch.no_grad():
                action, _, _ = self.policy.act(state_tensor, deterministic=True)
            return action.cpu().numpy().squeeze()
        else:
            # 폴백: 규칙 기반
            threat_level = state[12] if len(state) > 12 else 0.3
            if threat_level < 0.3:
                base = np.array([0.2, 0.1, 0.3, -0.5, -0.5, 0.1, 0.0])
            elif threat_level < 0.6:
                base = np.array([0.5, 0.4, 0.5, 0.2, -0.2, 0.4, 0.5])
            else:
                base = np.array([0.7, 0.6, 0.7, 0.5, 0.3, 0.6, 0.7])
            return base
    
    def reset(self):
        pass


# =============================================================================
# Evaluator
# =============================================================================
class RealModelEvaluator:
    """실제 모델 평가기"""
    
    def __init__(
        self,
        model_path: str,
        episodes_per_config: int = 50,
        max_steps: int = 200,
        seed: int = 42,
        device: str = "cpu",
        hidden_size: int = 256,
    ):
        self.episodes_per_config = episodes_per_config
        self.max_steps = max_steps
        self.seed = seed
        self.device = device
        self.hidden_size = hidden_size
        self.model_path = model_path
        
        # 전략 생성
        self.strategies = {}
        self.strategies["No MTD"] = NoMTDStrategy()
        self.strategies["Static MTD"] = StaticMTDStrategy()
        self.strategies["Heuristic+CTI"] = HeuristicCTIStrategy()
        self.strategies["RL MTD"] = RLOnlyStrategy(model_path, device, hidden_size)
        self.strategies["RL+CTI MTD"] = RealRLCTIStrategy(model_path, device, hidden_size)
        
        self.results = {}
        self.config = MTDConfig()
    
    def run_episode(self, strategy, level: int, ep_seed: int) -> Dict:
        """단일 에피소드 실행"""
        env = MTDEnvironment(
            seed=ep_seed,
            seeker_level=level,
            config=self.config,
        )
        
        state, info = env.reset()
        strategy.reset()
        
        total_reward = 0.0
        
        for step in range(self.max_steps):
            action = strategy.get_action(state)
            state, reward, terminated, truncated, info = env.step(action)
            total_reward += reward
            
            if terminated or truncated:
                break
        
        return {
            "reward": total_reward,
            "steps": step + 1,
            "breach": 1 - info.get("Defense/BreachPrevented", 0),
            "s_mtd": info.get("MTD/DES", 0),
            "mttc": info.get("MTD/MTTC", self.max_steps),
            "asr": info.get("MTD/ASR", 0),
            "cdi": info.get("MTD/CDI", 0),
            "ned": info.get("MTD/NED", 0),
            "cost": info.get("Cost/Total", 0),
            "cer": info.get("MTD/CER", 0),
            "redundancy": info.get("Defense/Redundancy_Avg", 0),
            "confusion": info.get("Attack/ConfusionLevel", 0),
        }
    
    def evaluate(self, levels: List[int] = None, verbose: bool = True) -> Dict:
        """전체 평가 실행"""
        if levels is None:
            levels = [0, 1, 2, 3, 4]
        
        np.random.seed(self.seed)
        torch.manual_seed(self.seed)
        
        total_configs = len(self.strategies) * len(levels)
        current = 0
        
        for strategy_name, strategy in self.strategies.items():
            for level in levels:
                current += 1
                
                episode_results = []
                for ep in range(self.episodes_per_config):
                    ep_seed = self.seed + current * 1000 + ep
                    result = self.run_episode(strategy, level, ep_seed)
                    episode_results.append(result)
                
                # 집계
                agg = {
                    "strategy": strategy_name,
                    "level": level,
                    "breach_rate": np.mean([r["breach"] for r in episode_results]) * 100,
                    "s_mtd": np.mean([r["s_mtd"] for r in episode_results]),
                    "mttc": np.mean([r["mttc"] for r in episode_results]),
                    "asr": np.mean([r["asr"] for r in episode_results]),
                    "cdi": np.mean([r["cdi"] for r in episode_results]),
                    "cost": np.mean([r["cost"] for r in episode_results]),
                    "cer": np.mean([r["cer"] for r in episode_results]),
                    "redundancy": np.mean([r["redundancy"] for r in episode_results]),
                    "confusion": np.mean([r["confusion"] for r in episode_results]),
                    "reward": np.mean([r["reward"] for r in episode_results]),
                }
                
                self.results[(strategy_name, level)] = agg
                
                if verbose:
                    breach_count = sum(1 for r in episode_results if r["breach"] > 0.5)
                    print(f"[{current:2d}/{total_configs}] {strategy_name:<15} vs L{level}: "
                          f"Breach={breach_count:2d}/{self.episodes_per_config}, "
                          f"S_MTD={agg['s_mtd']:.3f}, MTTC={agg['mttc']:.0f}")
        
        return self.results
    
    def get_summary_by_strategy(self) -> Dict:
        """전략별 평균"""
        summary = {}
        for strategy_name in self.strategies.keys():
            strategy_results = [v for (s, l), v in self.results.items() if s == strategy_name]
            if strategy_results:
                summary[strategy_name] = {
                    "s_mtd": np.mean([r["s_mtd"] for r in strategy_results]),
                    "breach_rate": np.mean([r["breach_rate"] for r in strategy_results]),
                    "mttc": np.mean([r["mttc"] for r in strategy_results]),
                    "asr": np.mean([r["asr"] for r in strategy_results]),
                    "cdi": np.mean([r["cdi"] for r in strategy_results]),
                    "cost": np.mean([r["cost"] for r in strategy_results]),
                    "cer": np.mean([r["cer"] for r in strategy_results]),
                    "redundancy": np.mean([r["redundancy"] for r in strategy_results]),
                    "confusion": np.mean([r["confusion"] for r in strategy_results]),
                }
        return summary
    
    def get_summary_by_level(self, strategy_name: str) -> Dict:
        """특정 전략의 레벨별 결과"""
        return {l: v for (s, l), v in self.results.items() if s == strategy_name}


# =============================================================================
# IEEE Style Plotting
# =============================================================================
def setup_ieee_style():
    """IEEE 논문 스타일 설정"""
    try:
        import scienceplots
        plt.style.use(['science', 'ieee', 'no-latex'])
    except:
        pass
    
    plt.rcParams.update({
        'font.family': 'serif',
        'font.size': 8,
        'axes.labelsize': 9,
        'axes.titlesize': 9,
        'legend.fontsize': 7,
        'xtick.labelsize': 8,
        'ytick.labelsize': 8,
        'figure.dpi': 300,
        'savefig.dpi': 300,
        'lines.linewidth': 1.0,
        'lines.markersize': 4,
        'axes.linewidth': 0.6,
        'grid.linewidth': 0.4,
        'grid.alpha': 0.4,
        'axes.grid': True,
        'legend.frameon': False,
        'savefig.bbox': 'tight',
        'savefig.pad_inches': 0.05,
        'axes.spines.top': False,
        'axes.spines.right': False,
    })


# 색상 팔레트 (색맹 친화)
COLORS = {
    'No MTD': '#0072B2',
    'Static MTD': '#E69F00',
    'Heuristic+CTI': '#009E73',
    'RL MTD': '#CC79A7',
    'RL+CTI MTD': '#D55E00',
}

MARKERS = {
    'No MTD': 'o',
    'Static MTD': 's',
    'Heuristic+CTI': '^',
    'RL MTD': 'D',
    'RL+CTI MTD': 'p',
}


def plot_all_figures(evaluator: RealModelEvaluator, output_dir: str):
    """모든 IEEE 스타일 그래프 생성"""
    os.makedirs(output_dir, exist_ok=True)
    setup_ieee_style()
    
    summary = evaluator.get_summary_by_strategy()
    strategies = list(summary.keys())
    
    # ==========================================================================
    # Figure 9: Strategy Comparison (6-panel bar chart)
    # ==========================================================================
    fig, axes = plt.subplots(2, 3, figsize=(7.0, 4.0))
    x = np.arange(len(strategies))
    width = 0.65
    short_names = ['No', 'Static', 'Heur.', 'RL', 'RL+CTI']
    colors = [COLORS[s] for s in strategies]
    
    # (a) S_MTD
    ax = axes[0, 0]
    vals = [summary[s]['s_mtd'] for s in strategies]
    ax.bar(x, vals, width, color=colors, edgecolor='black', linewidth=0.4)
    ax.set_ylabel(r'$S_{\mathrm{MTD}}$')
    ax.set_title('(a) Defense Effectiveness')
    ax.set_xticks(x)
    ax.set_xticklabels(short_names, fontsize=7)
    ax.set_ylim(0, 1.0)
    for i, v in enumerate(vals):
        ax.text(i, v + 0.02, f'{v:.2f}', ha='center', fontsize=6)
    
    # (b) Breach Rate
    ax = axes[0, 1]
    vals = [summary[s]['breach_rate'] for s in strategies]
    ax.bar(x, vals, width, color=colors, edgecolor='black', linewidth=0.4)
    ax.set_ylabel('Breach Rate (%)')
    ax.set_title('(b) Breach Rate')
    ax.set_xticks(x)
    ax.set_xticklabels(short_names, fontsize=7)
    ax.set_ylim(0, 100)
    for i, v in enumerate(vals):
        ax.text(i, v + 2, f'{v:.0f}', ha='center', fontsize=6)
    
    # (c) CER
    ax = axes[0, 2]
    vals = [summary[s]['cer'] for s in strategies]
    ax.bar(x, vals, width, color=colors, edgecolor='black', linewidth=0.4)
    ax.set_ylabel('CER')
    ax.set_title('(c) Cost Efficiency')
    ax.set_xticks(x)
    ax.set_xticklabels(short_names, fontsize=7)
    for i, v in enumerate(vals):
        ax.text(i, v + 0.05, f'{v:.2f}', ha='center', fontsize=6)
    
    # (d) CDI
    ax = axes[1, 0]
    vals = [summary[s]['cdi'] for s in strategies]
    ax.bar(x, vals, width, color=colors, edgecolor='black', linewidth=0.4)
    ax.set_ylabel('CDI')
    ax.set_title('(d) Config. Diversity')
    ax.set_xticks(x)
    ax.set_xticklabels(short_names, fontsize=7)
    ax.set_ylim(0, 1.0)
    for i, v in enumerate(vals):
        ax.text(i, v + 0.02, f'{v:.2f}', ha='center', fontsize=6)
    
    # (e) Redundancy
    ax = axes[1, 1]
    vals = [summary[s]['redundancy'] for s in strategies]
    ax.bar(x, vals, width, color=colors, edgecolor='black', linewidth=0.4)
    ax.set_ylabel('Redundancy')
    ax.set_title('(e) Redundancy Score')
    ax.set_xticks(x)
    ax.set_xticklabels(short_names, fontsize=7)
    ax.set_ylim(0, 1.0)
    for i, v in enumerate(vals):
        ax.text(i, v + 0.02, f'{v:.2f}', ha='center', fontsize=6)
    
    # (f) Total Cost
    ax = axes[1, 2]
    vals = [summary[s]['cost'] for s in strategies]
    ax.bar(x, vals, width, color=colors, edgecolor='black', linewidth=0.4)
    ax.set_ylabel('Total Cost')
    ax.set_title('(f) MTD Cost')
    ax.set_xticks(x)
    ax.set_xticklabels(short_names, fontsize=7)
    for i, v in enumerate(vals):
        ax.text(i, v + 0.02, f'{v:.2f}', ha='center', fontsize=6)
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'fig9_strategy_comparison.pdf'))
    plt.savefig(os.path.join(output_dir, 'fig9_strategy_comparison.png'), dpi=300)
    plt.close()
    print("  ✓ Fig 9: Strategy Comparison")
    
    # ==========================================================================
    # Figure 10: Performance vs Attacker Level
    # ==========================================================================
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.4))
    levels = [0, 1, 2, 3, 4]
    
    # (a) S_MTD vs Level
    ax = axes[0]
    for s in strategies:
        level_data = evaluator.get_summary_by_level(s)
        vals = [level_data.get(l, {}).get('s_mtd', 0) for l in levels]
        ax.plot(levels, vals, marker=MARKERS[s], color=COLORS[s],
                label=s.replace(' MTD', ''), linewidth=1.0, markersize=4)
    ax.set_xlabel('Attacker Level')
    ax.set_ylabel(r'$S_{\mathrm{MTD}}$')
    ax.set_title('(a) Defense Effectiveness')
    ax.set_xticks(levels)
    ax.set_xticklabels(['L0', 'L1', 'L2', 'L3', 'L4'])
    ax.legend(loc='lower left', fontsize=6, ncol=2)
    
    # (b) Breach Rate vs Level
    ax = axes[1]
    for s in strategies:
        level_data = evaluator.get_summary_by_level(s)
        vals = [level_data.get(l, {}).get('breach_rate', 0) for l in levels]
        ax.plot(levels, vals, marker=MARKERS[s], color=COLORS[s],
                label=s.replace(' MTD', ''), linewidth=1.0, markersize=4)
    ax.set_xlabel('Attacker Level')
    ax.set_ylabel('Breach Rate (%)')
    ax.set_title('(b) Breach Rate')
    ax.set_xticks(levels)
    ax.set_xticklabels(['L0', 'L1', 'L2', 'L3', 'L4'])
    ax.legend(loc='upper left', fontsize=6, ncol=2)
    ax.set_ylim(0, 100)
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'fig10_level_comparison.pdf'))
    plt.savefig(os.path.join(output_dir, 'fig10_level_comparison.png'), dpi=300)
    plt.close()
    print("  ✓ Fig 10: Level Comparison")
    
    # ==========================================================================
    # Figure 11: MTTC Comparison
    # ==========================================================================
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.4))
    
    # (a) MTTC by Strategy
    ax = axes[0]
    vals = [summary[s]['mttc'] for s in strategies]
    ax.bar(x, vals, width, color=colors, edgecolor='black', linewidth=0.4)
    ax.set_ylabel('MTTC (steps)')
    ax.set_title('(a) Mean Time to Compromise')
    ax.set_xticks(x)
    ax.set_xticklabels(short_names, fontsize=7)
    for i, v in enumerate(vals):
        ax.text(i, v + 2, f'{v:.0f}', ha='center', fontsize=6)
    
    # (b) MTTC vs Level
    ax = axes[1]
    for s in strategies:
        level_data = evaluator.get_summary_by_level(s)
        vals = [level_data.get(l, {}).get('mttc', 0) for l in levels]
        ax.plot(levels, vals, marker=MARKERS[s], color=COLORS[s],
                label=s.replace(' MTD', ''), linewidth=1.0, markersize=4)
    ax.set_xlabel('Attacker Level')
    ax.set_ylabel('MTTC (steps)')
    ax.set_title('(b) MTTC by Attacker Level')
    ax.set_xticks(levels)
    ax.set_xticklabels(['L0', 'L1', 'L2', 'L3', 'L4'])
    ax.legend(loc='upper right', fontsize=6)
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'fig11_mttc.pdf'))
    plt.savefig(os.path.join(output_dir, 'fig11_mttc.png'), dpi=300)
    plt.close()
    print("  ✓ Fig 11: MTTC Comparison")
    
    # ==========================================================================
    # Figure 12: CER vs Level, Cost vs S_MTD
    # ==========================================================================
    fig, axes = plt.subplots(1, 3, figsize=(7.0, 2.0))
    
    # (a) CER vs Level
    ax = axes[0]
    for s in strategies:
        level_data = evaluator.get_summary_by_level(s)
        vals = [level_data.get(l, {}).get('cer', 0) for l in levels]
        ax.plot(levels, vals, marker=MARKERS[s], color=COLORS[s],
                label=s.replace(' MTD', ''), linewidth=1.0, markersize=4)
    ax.set_xlabel('Attacker Level')
    ax.set_ylabel('CER')
    ax.set_title('(a) CER vs Level')
    ax.set_xticks(levels)
    ax.set_xticklabels(['L0', 'L1', 'L2', 'L3', 'L4'])
    ax.legend(loc='upper right', fontsize=5.5)
    
    # (b) Cost vs S_MTD (scatter)
    ax = axes[1]
    for s in strategies:
        ax.scatter(summary[s]['cost'], summary[s]['s_mtd'], s=60,
                   color=COLORS[s], marker=MARKERS[s],
                   label=s.replace(' MTD', ''), edgecolors='black', linewidth=0.3)
    ax.set_xlabel('Total Cost')
    ax.set_ylabel(r'$S_{\mathrm{MTD}}$')
    ax.set_title('(b) Cost vs Defense')
    ax.legend(loc='lower right', fontsize=5.5)
    
    # (c) MTTC vs CER
    ax = axes[2]
    for s in strategies:
        ax.scatter(summary[s]['mttc'], summary[s]['cer'], s=60,
                   color=COLORS[s], marker=MARKERS[s],
                   label=s.replace(' MTD', ''), edgecolors='black', linewidth=0.3)
    ax.set_xlabel('MTTC (steps)')
    ax.set_ylabel('CER')
    ax.set_title('(c) MTTC vs CER')
    ax.legend(loc='upper right', fontsize=5.5)
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'fig12_tradeoffs.pdf'))
    plt.savefig(os.path.join(output_dir, 'fig12_tradeoffs.png'), dpi=300)
    plt.close()
    print("  ✓ Fig 12: Trade-off Analysis")
    
    print(f"\n✅ All figures saved to: {output_dir}/")


def generate_latex_table(evaluator: RealModelEvaluator, output_dir: str):
    """LaTeX 테이블 생성"""
    summary = evaluator.get_summary_by_strategy()
    
    table = r"""\begin{table}[!t]
\centering
\caption{Defense Performance Comparison Across MTD Strategies}
\label{tab:comparison}
\renewcommand{\arraystretch}{1.1}
\begin{tabular}{@{}lcccccc@{}}
\toprule
\textbf{Strategy} & $S_{\mathrm{MTD}}$ & \textbf{Breach(\%)} & \textbf{MTTC} & \textbf{CER} & \textbf{CDI} & \textbf{Cost} \\
\midrule
"""
    
    for s, m in summary.items():
        table += f"{s} & {m['s_mtd']:.3f} & {m['breach_rate']:.1f} & {m['mttc']:.0f} & {m['cer']:.2f} & {m['cdi']:.3f} & {m['cost']:.3f} \\\\\n"
    
    table += r"""\bottomrule
\end{tabular}
\end{table}
"""
    
    with open(os.path.join(output_dir, 'table_comparison.tex'), 'w') as f:
        f.write(table)
    
    print(table)
    print(f"✅ LaTeX table saved to: {output_dir}/table_comparison.tex")


def export_results_json(evaluator: RealModelEvaluator, output_dir: str):
    """결과 JSON 저장"""
    data = {
        "timestamp": datetime.now().isoformat(),
        "config": {
            "episodes_per_config": evaluator.episodes_per_config,
            "max_steps": evaluator.max_steps,
            "seed": evaluator.seed,
            "model_path": evaluator.model_path,
        },
        "summary": evaluator.get_summary_by_strategy(),
        "by_level": {
            s: evaluator.get_summary_by_level(s) 
            for s in evaluator.strategies.keys()
        },
    }
    
    with open(os.path.join(output_dir, 'evaluation_results.json'), 'w') as f:
        json.dump(data, f, indent=2, default=float)
    
    print(f"✅ Results JSON saved to: {output_dir}/evaluation_results.json")


# =============================================================================
# Main
# =============================================================================
def main():
    parser = argparse.ArgumentParser(description="MTD Real Model Evaluation + IEEE Figures")
    parser.add_argument("--model", type=str, required=True, help="Path to best.pt")
    parser.add_argument("--episodes", type=int, default=50, help="Episodes per config")
    parser.add_argument("--max-steps", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--hidden-size", type=int, default=256)
    parser.add_argument("--output-dir", type=str, default="paper_figures_real")
    parser.add_argument("--levels", type=int, nargs="+", default=[0, 1, 2, 3, 4])
    parser.add_argument("--device", type=str, default="cpu")
    args = parser.parse_args()
    
    print("="*70)
    print("MTD Real Model Evaluation + IEEE Paper Figures")
    print("="*70)
    print(f"Model: {args.model}")
    print(f"Episodes per config: {args.episodes}")
    print(f"Max steps: {args.max_steps}")
    print(f"Levels: {args.levels}")
    print(f"Output: {args.output_dir}")
    print("="*70)
    
    # 평가 실행
    evaluator = RealModelEvaluator(
        model_path=args.model,
        episodes_per_config=args.episodes,
        max_steps=args.max_steps,
        seed=args.seed,
        hidden_size=args.hidden_size,
        device=args.device,
    )
    
    print("\n📊 Running evaluation...")
    evaluator.evaluate(levels=args.levels, verbose=True)
    
    # 요약 출력
    print("\n" + "="*70)
    print("📈 Summary Results (Real Model)")
    print("="*70)
    
    summary = evaluator.get_summary_by_strategy()
    print(f"\n{'Strategy':<18} {'S_MTD':>8} {'Breach%':>10} {'MTTC':>8} {'CER':>8} {'Cost':>8}")
    print("-"*70)
    for strategy, metrics in summary.items():
        print(f"{strategy:<18} {metrics['s_mtd']:>8.3f} {metrics['breach_rate']:>9.1f}% "
              f"{metrics['mttc']:>8.0f} {metrics['cer']:>8.2f} {metrics['cost']:>8.3f}")
    
    # 그래프 생성
    print("\n📊 Generating IEEE-style figures...")
    plot_all_figures(evaluator, args.output_dir)
    
    # LaTeX 테이블
    print("\n📋 Generating LaTeX table...")
    generate_latex_table(evaluator, args.output_dir)
    
    # JSON 저장
    export_results_json(evaluator, args.output_dir)
    
    print("\n" + "="*70)
    print("✅ Evaluation Complete!")
    print("="*70)
    
    return evaluator


if __name__ == "__main__":
    main()