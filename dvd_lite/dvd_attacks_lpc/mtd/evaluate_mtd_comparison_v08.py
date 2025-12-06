#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MTD Comparison Evaluation Script v08.5 - Enhanced W&B Visualization
====================================================================

개선된 W&B 시각화:
1. 에피소드별 메트릭 로깅 (시계열 그래프)
2. 전략별 비교 바 차트
3. 레벨별 성능 라인 차트
4. 박스 플롯
5. 히트맵

저자: MTD-RL Research Team
버전: 0.8.5
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
)
from rl_environment_v08 import MTDEnvironment

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
# MTD Strategies
# =============================================================================
class BaseMTDStrategy:
    name = "Base"

    def reset(self):
        pass

    def get_action(self, state: np.ndarray, info: Dict = None) -> np.ndarray:
        raise NotImplementedError


class NoMTDStrategy(BaseMTDStrategy):
    name = "No MTD"

    def __init__(self):
        self.step = 0

    def reset(self):
        self.step = 0

    def get_action(self, state: np.ndarray, info: Dict = None) -> np.ndarray:
        self.step += 1
        return np.ones(ACTION_DIM) * -1.0


class StaticMTDStrategy(BaseMTDStrategy):
    name = "Static MTD"

    def __init__(self, shuffle_period: int = 20, shuffle_intensity: float = 0.7, decoy_ratio: float = 0.3):
        self.shuffle_period = shuffle_period
        self.shuffle_intensity = shuffle_intensity
        self.decoy_ratio = decoy_ratio
        self.step = 0

    def reset(self):
        self.step = 0

    def get_action(self, state: np.ndarray, info: Dict = None) -> np.ndarray:
        self.step += 1
        action = np.ones(ACTION_DIM) * -1.0

        if self.step % self.shuffle_period == 0:
            action[0] = self.shuffle_intensity * 2 - 1

        action[2] = self.decoy_ratio * 2 - 1
        return action


class HeuristicMTDStrategy(BaseMTDStrategy):
    name = "Heuristic MTD"

    def __init__(self, cti_enabled: bool = True):
        self.cti_enabled = cti_enabled
        self.step = 0
        self.last_shuffle_step = 0
        self.threat_level = 0.0

    def reset(self):
        self.step = 0
        self.last_shuffle_step = 0
        self.threat_level = 0.0

    def get_action(self, state: np.ndarray, info: Dict = None) -> np.ndarray:
        self.step += 1
        action = np.ones(ACTION_DIM) * -1.0

        scanned_ratio = state[0]
        services_found = state[1]
        critical_found = state[2]
        exploit_progress = state[3]
        compromise_progress = state[4]
        diversity = state[5]

        if info and self.cti_enabled:
            cti_alert = info.get("cti_alert", False)
            cti_threat_level = info.get("cti_threat_level", 0.0)
            self.threat_level = max(self.threat_level * 0.9, cti_threat_level)

        if self.step - self.last_shuffle_step >= 25:
            action[0] = 0.3
            self.last_shuffle_step = self.step

        if scanned_ratio > 0.2:
            action[0] = max(action[0], 0.4)
            self.last_shuffle_step = self.step

        if services_found > 0.1:
            action[0] = 0.8
            action[1] = 0.4
            self.last_shuffle_step = self.step

        if critical_found > 0.5:
            action[0] = 1.0
            action[1] = 0.8
            action[2] = 0.6
            action[3] = 0.5
            self.last_shuffle_step = self.step

        if exploit_progress > 0.2:
            action[2] = max(action[2], 0.5)
            action[3] = max(action[3], 0.4)

        if compromise_progress > 0.1:
            action[0] = 1.0
            action[1] = 1.0
            action[2] = 0.8
            action[3] = 0.8
            action[5] = 0.7
            self.last_shuffle_step = self.step

        if diversity < 0.3:
            action[0] = max(action[0], 0.5)
            self.last_shuffle_step = self.step

        action[2] = max(action[2], -0.3)
        return action


class RLMTDStrategy(BaseMTDStrategy):
    name = "RL MTD"

    def __init__(self, model_path: str, device: str = "cpu"):
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

    def reset(self):
        pass

    def get_action(self, state: np.ndarray, info: Dict = None) -> np.ndarray:
        with torch.no_grad():
            state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)
            action, _, _ = self.policy.act(state_tensor, deterministic=True)
        return action.cpu().numpy().squeeze()


class RLCTIMTDStrategy(BaseMTDStrategy):
    name = "RL-CTI MTD"

    def __init__(self, model_path: str, cti_boost: float = 1.3, device: str = "cpu"):
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

    def reset(self):
        pass

    def get_action(self, state: np.ndarray, info: Dict = None) -> np.ndarray:
        with torch.no_grad():
            state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)
            action, _, _ = self.policy.act(state_tensor, deterministic=True)

        action_np = action.cpu().numpy().squeeze()

        exploit_progress = state[3] if len(state) > 3 else 0
        cti_alert = info.get("cti_alert", False) if info else False
        cti_threat_level = info.get("cti_threat_level", 0.0) if info else 0.0

        if cti_alert or exploit_progress > 0.1 or cti_threat_level > 0.5:
            boost_factor = self.cti_boost * (1 + cti_threat_level * 0.5)
            action_np = np.clip(action_np * boost_factor, -1, 1)

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
    episode_metrics: List[Dict]  # 에피소드별 메트릭 추가


# =============================================================================
# Enhanced W&B Evaluation Logger
# =============================================================================
class EnhancedWandbEvalLogger:
    """개선된 W&B 평가 로깅"""

    def __init__(
        self,
        project: str,
        name: Optional[str] = None,
        config: Optional[Dict] = None,
        tags: Optional[List[str]] = None,
    ):
        if not WANDB_AVAILABLE:
            raise RuntimeError("wandb not installed")

        import datetime
        self.run = wandb.init(
            project=project,
            name=name or f"eval-{datetime.datetime.now():%m%d-%H%M%S}",
            config=config,
            tags=tags or ["evaluation", "mtd", "comparison"],
            job_type="evaluation",
        )
        
        # 에피소드 카운터
        self.episode_counter = 0
        
        # 전체 데이터 저장
        self.all_episode_data = []
        
        print(f"✅ W&B Eval initialized: {self.run.url}")

    def log_episode(
        self,
        mtd_mode: str,
        seeker_level: int,
        episode_idx: int,
        metrics: Dict[str, Any],
    ):
        """에피소드별 메트릭 로깅 (시계열 그래프용)"""
        self.episode_counter += 1
        
        # W&B 로깅 - 고유 step 사용
        log_data = {
            "episode": self.episode_counter,
            "mtd_mode": mtd_mode,
            "seeker_level": seeker_level,
            "episode_in_exp": episode_idx,
            
            # 주요 메트릭
            f"timeseries/DES": metrics.get("MTD/DES", 0),
            f"timeseries/MTTC": metrics.get("MTD/MTTC", 200),
            f"timeseries/ASR": metrics.get("MTD/ASR", 0),
            f"timeseries/CDI": metrics.get("MTD/CDI", 0),
            f"timeseries/Cost": metrics.get("Cost/Total", 0),
            f"timeseries/Survival": metrics.get("Defense/BreachPrevented", 0),
            f"timeseries/Reward": metrics.get("reward", 0),
            
            # 전략별 분류
            f"by_strategy/{mtd_mode}/DES": metrics.get("MTD/DES", 0),
            f"by_strategy/{mtd_mode}/MTTC": metrics.get("MTD/MTTC", 200),
            f"by_strategy/{mtd_mode}/Survival": metrics.get("Defense/BreachPrevented", 0),
            
            # 레벨별 분류
            f"by_level/L{seeker_level}/DES": metrics.get("MTD/DES", 0),
            f"by_level/L{seeker_level}/MTTC": metrics.get("MTD/MTTC", 200),
        }
        
        wandb.log(log_data, step=self.episode_counter)
        
        # 데이터 저장 (차트용)
        self.all_episode_data.append({
            "episode": self.episode_counter,
            "mtd_mode": mtd_mode,
            "seeker_level": seeker_level,
            "des": metrics.get("MTD/DES", 0),
            "mttc": metrics.get("MTD/MTTC", 200),
            "asr": metrics.get("MTD/ASR", 0),
            "cdi": metrics.get("MTD/CDI", 0),
            "cost": metrics.get("Cost/Total", 0),
            "survival": metrics.get("Defense/BreachPrevented", 0),
        })

    def log_strategy_comparison_charts(self, results: Dict[str, ExperimentResult]):
        """전략 비교 차트 생성 및 로깅"""
        set_publication_style()
        
        levels = [0, 1, 2, 3, 4]
        level_names = ["Script\nKiddie", "Hobbyist", "Professional", "Expert", "APT"]
        
        mtd_modes = list(set(r.mtd_mode for r in results.values()))
        mode_order = ["No MTD", "Static MTD", "Heuristic MTD", "RL MTD", "RL-CTI MTD"]
        mtd_modes = [m for m in mode_order if m in mtd_modes]
        
        # ============================================
        # Chart 1: DES 비교 바 차트
        # ============================================
        fig, ax = plt.subplots(figsize=(12, 6))
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
        
        ax.set_xlabel('Attacker Sophistication Level', fontsize=12)
        ax.set_ylabel('Defense Effectiveness Score (DES)', fontsize=12)
        ax.set_title('Defense Effectiveness by MTD Strategy and Attacker Level', fontsize=14)
        ax.set_xticks(x)
        ax.set_xticklabels(level_names)
        ax.set_ylim(0, 1.0)
        ax.legend(loc='upper right', ncol=2, framealpha=0.9)
        ax.grid(axis='y', alpha=0.3, linestyle='--')
        
        plt.tight_layout()
        wandb.log({"charts/DES_Comparison_Bar": wandb.Image(fig)})
        plt.close()
        
        # ============================================
        # Chart 2: MTTC 라인 차트
        # ============================================
        fig, ax = plt.subplots(figsize=(10, 6))
        
        for mode in mtd_modes:
            values = []
            errors = []
            for level in levels:
                key = f"L{level}_{mode.replace(' ', '_').replace('-', '_')}"
                if key in results:
                    values.append(results[key].metrics.get("MTD/MTTC_mean", 200))
                    errors.append(results[key].metrics.get("MTD/MTTC_std", 0))
                else:
                    values.append(200)
                    errors.append(0)
            
            ax.errorbar(levels, values, yerr=errors,
                        marker=MARKERS.get(mode, 'o'),
                        color=COLORS.get(mode, '#999'),
                        label=mode, linewidth=2, capsize=4, markersize=8)
        
        ax.set_xlabel('Attacker Sophistication Level', fontsize=12)
        ax.set_ylabel('Mean Time To Compromise (steps)', fontsize=12)
        ax.set_title('MTTC by MTD Strategy and Attacker Level', fontsize=14)
        ax.set_xticks(levels)
        ax.set_xticklabels([f"L{l}" for l in levels])
        ax.legend(loc='best', framealpha=0.9)
        ax.grid(True, alpha=0.3, linestyle='--')
        
        plt.tight_layout()
        wandb.log({"charts/MTTC_Comparison_Line": wandb.Image(fig)})
        plt.close()
        
        # ============================================
        # Chart 3: Survival Rate 바 차트
        # ============================================
        fig, ax = plt.subplots(figsize=(12, 6))
        
        for i, mode in enumerate(mtd_modes):
            values = []
            for level in levels:
                key = f"L{level}_{mode.replace(' ', '_').replace('-', '_')}"
                if key in results:
                    values.append(results[key].metrics.get("Defense/BreachPrevented_mean", 0) * 100)
                else:
                    values.append(0)
            
            offset = (i - len(mtd_modes)/2 + 0.5) * width
            ax.bar(x + offset, values, width,
                   label=mode, color=COLORS.get(mode, '#999'),
                   hatch=HATCHES[i % len(HATCHES)],
                   edgecolor='black', linewidth=0.5)
        
        ax.set_xlabel('Attacker Sophistication Level', fontsize=12)
        ax.set_ylabel('Survival Rate (%)', fontsize=12)
        ax.set_title('Breach Prevention Rate by MTD Strategy', fontsize=14)
        ax.set_xticks(x)
        ax.set_xticklabels(level_names)
        ax.set_ylim(0, 110)
        ax.legend(loc='upper right', ncol=2, framealpha=0.9)
        ax.grid(axis='y', alpha=0.3, linestyle='--')
        
        plt.tight_layout()
        wandb.log({"charts/Survival_Rate_Bar": wandb.Image(fig)})
        plt.close()
        
        # ============================================
        # Chart 4: 전략별 평균 성능 비교
        # ============================================
        fig, axes = plt.subplots(1, 3, figsize=(15, 5))
        
        metrics_to_plot = [
            ("MTD/DES_mean", "Defense Effectiveness Score", axes[0]),
            ("MTD/MTTC_mean", "Mean Time To Compromise", axes[1]),
            ("Defense/BreachPrevented_mean", "Survival Rate", axes[2]),
        ]
        
        for metric_key, title, ax in metrics_to_plot:
            mode_avgs = []
            mode_stds = []
            
            for mode in mtd_modes:
                mode_values = []
                for level in levels:
                    key = f"L{level}_{mode.replace(' ', '_').replace('-', '_')}"
                    if key in results:
                        val = results[key].metrics.get(metric_key, 0)
                        if "Survival" in title or "Breach" in title:
                            val *= 100
                        mode_values.append(val)
                
                if mode_values:
                    mode_avgs.append(np.mean(mode_values))
                    mode_stds.append(np.std(mode_values))
                else:
                    mode_avgs.append(0)
                    mode_stds.append(0)
            
            bars = ax.bar(range(len(mtd_modes)), mode_avgs, 
                          yerr=mode_stds, capsize=4,
                          color=[COLORS.get(m, '#999') for m in mtd_modes],
                          edgecolor='black', linewidth=0.5)
            
            ax.set_xticks(range(len(mtd_modes)))
            ax.set_xticklabels([m.replace(" MTD", "\nMTD") for m in mtd_modes], fontsize=9)
            ax.set_title(title, fontsize=11)
            ax.grid(axis='y', alpha=0.3, linestyle='--')
            
            # 값 표시
            for bar, val in zip(bars, mode_avgs):
                ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02,
                        f'{val:.2f}' if val < 10 else f'{val:.0f}',
                        ha='center', va='bottom', fontsize=9)
        
        plt.tight_layout()
        wandb.log({"charts/Strategy_Average_Comparison": wandb.Image(fig)})
        plt.close()
        
        # ============================================
        # Chart 5: 히트맵
        # ============================================
        fig, ax = plt.subplots(figsize=(10, 6))
        
        heatmap_data = np.zeros((len(mtd_modes), len(levels)))
        for i, mode in enumerate(mtd_modes):
            for j, level in enumerate(levels):
                key = f"L{level}_{mode.replace(' ', '_').replace('-', '_')}"
                if key in results:
                    heatmap_data[i, j] = results[key].metrics.get("MTD/DES_mean", 0)
        
        im = ax.imshow(heatmap_data, cmap='RdYlGn', aspect='auto', vmin=0, vmax=1)
        ax.set_xticks(np.arange(len(levels)))
        ax.set_yticks(np.arange(len(mtd_modes)))
        ax.set_xticklabels([f"L{l}" for l in levels])
        ax.set_yticklabels(mtd_modes)
        ax.set_xlabel('Attacker Level', fontsize=12)
        ax.set_ylabel('MTD Strategy', fontsize=12)
        ax.set_title('Defense Effectiveness Score (DES) Heatmap', fontsize=14)
        
        for i in range(len(mtd_modes)):
            for j in range(len(levels)):
                text_color = 'white' if heatmap_data[i, j] < 0.5 else 'black'
                ax.text(j, i, f"{heatmap_data[i, j]:.2f}",
                        ha="center", va="center", color=text_color,
                        fontsize=11, fontweight='bold')
        
        cbar = plt.colorbar(im, ax=ax, shrink=0.8)
        cbar.set_label('DES Score', fontsize=11)
        
        plt.tight_layout()
        wandb.log({"charts/DES_Heatmap": wandb.Image(fig)})
        plt.close()
        
        # ============================================
        # Chart 6: 박스 플롯 (DES 분포)
        # ============================================
        fig, ax = plt.subplots(figsize=(12, 6))
        
        box_data = []
        box_labels = []
        box_colors = []
        
        for mode in mtd_modes:
            for level in levels:
                key = f"L{level}_{mode.replace(' ', '_').replace('-', '_')}"
                if key in results:
                    # 에피소드별 DES 값
                    episode_des = [ep.get("MTD/DES", 0) for ep in results[key].raw_metrics]
                    if episode_des:
                        box_data.append(episode_des)
                        box_labels.append(f"{mode[:3]}\nL{level}")
                        box_colors.append(COLORS.get(mode, '#999'))
        
        if box_data:
            bp = ax.boxplot(box_data, patch_artist=True, labels=box_labels)
            for patch, color in zip(bp['boxes'], box_colors):
                patch.set_facecolor(color)
                patch.set_alpha(0.7)
            
            ax.set_xlabel('Strategy and Level', fontsize=12)
            ax.set_ylabel('DES Distribution', fontsize=12)
            ax.set_title('DES Distribution by Strategy and Level', fontsize=14)
            ax.grid(axis='y', alpha=0.3, linestyle='--')
            plt.xticks(rotation=45, ha='right')
        
        plt.tight_layout()
        wandb.log({"charts/DES_BoxPlot": wandb.Image(fig)})
        plt.close()
        
        # ============================================
        # Chart 7: 레이더 차트
        # ============================================
        fig, ax = plt.subplots(figsize=(10, 10), subplot_kw=dict(polar=True))
        
        metrics = ['DES', 'MTTC\n(norm)', 'ASR', 'CDI', 'Breach\nPrev', 'Cost\nEff']
        metric_keys = ['MTD/DES_mean', 'MTD/MTTC_mean', 'MTD/ASR_mean',
                       'MTD/CDI_mean', 'Defense/BreachPrevented_mean', 'Cost/Total_mean']
        
        angles = np.linspace(0, 2 * np.pi, len(metrics), endpoint=False).tolist()
        angles += angles[:1]
        
        target_level = 2
        for mode in mtd_modes:
            key = f"L{target_level}_{mode.replace(' ', '_').replace('-', '_')}"
            if key not in results:
                continue
            
            values = []
            for mk in metric_keys:
                v = results[key].metrics.get(mk, 0)
                if 'MTTC' in mk:
                    v = v / 200
                if 'Cost' in mk:
                    v = 1.0 - min(1.0, v / 50.0)
                values.append(min(1.0, max(0.0, v)))
            
            values += values[:1]
            ax.plot(angles, values, 'o-', linewidth=2,
                    label=mode, color=COLORS.get(mode, '#999'))
            ax.fill(angles, values, alpha=0.15, color=COLORS.get(mode, '#999'))
        
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(metrics, fontsize=10)
        ax.set_ylim(0, 1)
        ax.set_title(f'MTD Strategy Comparison (Level {target_level} Attacker)', pad=20, fontsize=14)
        ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.0))
        
        plt.tight_layout()
        wandb.log({"charts/Radar_Chart": wandb.Image(fig)})
        plt.close()
        
        # ============================================
        # Chart 8: 에피소드별 DES 누적 라인 차트
        # ============================================
        if self.all_episode_data:
            fig, ax = plt.subplots(figsize=(14, 6))
            
            # 전략별로 그룹화
            for mode in mtd_modes:
                mode_data = [d for d in self.all_episode_data if d["mtd_mode"] == mode]
                if mode_data:
                    episodes = list(range(1, len(mode_data) + 1))
                    des_values = [d["des"] for d in mode_data]
                    
                    # 이동 평균
                    window = min(10, len(des_values) // 3) if len(des_values) > 3 else 1
                    if window > 1:
                        des_ma = np.convolve(des_values, np.ones(window)/window, mode='valid')
                        episodes_ma = episodes[window-1:]
                    else:
                        des_ma = des_values
                        episodes_ma = episodes
                    
                    ax.plot(episodes_ma, des_ma, 
                            label=mode, color=COLORS.get(mode, '#999'),
                            linewidth=2, alpha=0.8)
            
            ax.set_xlabel('Episode', fontsize=12)
            ax.set_ylabel('DES (Moving Average)', fontsize=12)
            ax.set_title('DES Progression Across Evaluation Episodes', fontsize=14)
            ax.legend(loc='best', framealpha=0.9)
            ax.grid(True, alpha=0.3, linestyle='--')
            
            plt.tight_layout()
            wandb.log({"charts/DES_Episode_Progression": wandb.Image(fig)})
            plt.close()

    def log_comparison_table(self, results: Dict[str, ExperimentResult]):
        """비교 테이블 로깅"""
        levels = [0, 1, 2, 3, 4]
        mtd_modes = list(set(r.mtd_mode for r in results.values()))
        mode_order = ["No MTD", "Static MTD", "Heuristic MTD", "RL MTD", "RL-CTI MTD"]
        mtd_modes = [m for m in mode_order if m in mtd_modes]
        
        columns = ["Level", "Level_Name", "MTD_Mode", "DES", "MTTC", "ASR", "CDI", "NED", "Cost", "Survival"]
        data = []
        
        for level in levels:
            for mode in mtd_modes:
                key = f"L{level}_{mode.replace(' ', '_').replace('-', '_')}"
                if key in results:
                    r = results[key]
                    level_name = SEEKER_PROFILES.get(level, {}).get("name", "Unknown")
                    data.append([
                        level,
                        level_name,
                        mode,
                        round(r.metrics.get("MTD/DES_mean", 0), 3),
                        round(r.metrics.get("MTD/MTTC_mean", 0), 1),
                        round(r.metrics.get("MTD/ASR_mean", 0), 3),
                        round(r.metrics.get("MTD/CDI_mean", 0), 3),
                        round(r.metrics.get("MTD/NED_mean", 0), 3),
                        round(r.metrics.get("Cost/Total_mean", 0), 2),
                        round(r.metrics.get("Defense/BreachPrevented_mean", 0) * 100, 1),
                    ])
        
        table = wandb.Table(columns=columns, data=data)
        wandb.log({"tables/Full_Comparison": table})
        
        # 요약 테이블 (전략별 평균)
        summary_data = []
        for mode in mtd_modes:
            mode_results = [r for r in results.values() if r.mtd_mode == mode]
            if mode_results:
                summary_data.append([
                    mode,
                    round(np.mean([r.metrics.get("MTD/DES_mean", 0) for r in mode_results]), 3),
                    round(np.mean([r.metrics.get("MTD/MTTC_mean", 0) for r in mode_results]), 1),
                    round(np.mean([r.metrics.get("MTD/ASR_mean", 0) for r in mode_results]), 3),
                    round(np.mean([r.metrics.get("Defense/BreachPrevented_mean", 0) for r in mode_results]) * 100, 1),
                    round(np.mean([r.metrics.get("Cost/Total_mean", 0) for r in mode_results]), 2),
                ])
        
        summary_table = wandb.Table(
            columns=["Strategy", "Avg_DES", "Avg_MTTC", "Avg_ASR", "Avg_Survival%", "Avg_Cost"],
            data=summary_data
        )
        wandb.log({"tables/Strategy_Summary": summary_table})

    def log_summary(self, results: Dict[str, ExperimentResult]):
        """최종 요약 로깅"""
        modes = set(r.mtd_mode for r in results.values())
        
        for mode in modes:
            mode_results = [r for r in results.values() if r.mtd_mode == mode]
            if mode_results:
                avg_des = np.mean([r.metrics.get("MTD/DES_mean", 0) for r in mode_results])
                avg_mttc = np.mean([r.metrics.get("MTD/MTTC_mean", 0) for r in mode_results])
                avg_survival = np.mean([r.metrics.get("Defense/BreachPrevented_mean", 0) for r in mode_results])
                avg_cost = np.mean([r.metrics.get("Cost/Total_mean", 0) for r in mode_results])
                
                wandb.run.summary[f"summary/{mode}/avg_des"] = avg_des
                wandb.run.summary[f"summary/{mode}/avg_mttc"] = avg_mttc
                wandb.run.summary[f"summary/{mode}/avg_survival"] = avg_survival
                wandb.run.summary[f"summary/{mode}/avg_cost"] = avg_cost
        
        # 베스트 전략
        best_mode = max(modes, key=lambda m: np.mean([
            r.metrics.get("MTD/DES_mean", 0) for r in results.values() if r.mtd_mode == m
        ]))
        wandb.run.summary["summary/best_strategy"] = best_mode
        wandb.run.summary["summary/total_episodes"] = self.episode_counter

    def finish(self):
        """W&B 세션 종료"""
        wandb.finish()
        print("✅ W&B Eval session finished")


# =============================================================================
# Evaluation Engine
# =============================================================================
def run_single_experiment(
    seeker_level: int,
    mtd_strategy: BaseMTDStrategy,
    num_episodes: int = 50,
    max_steps: int = 200,
    seed: int = 42,
    wb_logger: Optional[EnhancedWandbEvalLogger] = None,
) -> ExperimentResult:
    """단일 실험 실행"""
    cfg = MTDConfig()
    all_metrics = []
    episode_metrics_list = []
    
    for ep in range(num_episodes):
        env = MTDEnvironment(
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
        
        info["reward"] = episode_reward
        info["steps"] = step + 1
        all_metrics.append(info)
        
        # 에피소드별 로깅
        if wb_logger:
            wb_logger.log_episode(
                mtd_mode=mtd_strategy.name,
                seeker_level=seeker_level,
                episode_idx=ep,
                metrics=info,
            )
        
        episode_metrics_list.append({
            "episode": ep,
            "reward": episode_reward,
            "des": info.get("MTD/DES", 0),
            "mttc": info.get("MTD/MTTC", 200),
            "survival": info.get("Defense/BreachPrevented", 0),
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
    output_dir: str = "eval_results_v08",
    include_static: bool = True,
    include_rl_cti: bool = False,
    wandb_project: Optional[str] = None,
    wandb_name: Optional[str] = None,
) -> Dict[str, ExperimentResult]:
    """모든 실험 실행"""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # W&B 초기화
    wb_logger = None
    if wandb_project and WANDB_AVAILABLE:
        wb_logger = EnhancedWandbEvalLogger(
            project=wandb_project,
            name=wandb_name,
            config={
                "num_episodes": num_episodes,
                "max_steps": max_steps,
                "seed": seed,
                "rl_model": rl_model_path,
            },
        )
    
    # 전략 목록 생성
    strategies: List[BaseMTDStrategy] = [NoMTDStrategy()]
    
    if include_static:
        strategies.append(StaticMTDStrategy())
    
    strategies.append(HeuristicMTDStrategy(cti_enabled=True))
    
    if rl_model_path and TORCH_AVAILABLE:
        try:
            strategies.append(RLMTDStrategy(rl_model_path))
            if include_rl_cti:
                strategies.append(RLCTIMTDStrategy(rl_model_path, cti_boost=1.3))
        except Exception as e:
            print(f"⚠️ Failed to load RL model: {e}")
    
    seeker_levels = [0, 1, 2, 3, 4]
    results = {}
    
    print("\n" + "=" * 90)
    print("MTD Comparison Evaluation v08.5 (Enhanced W&B Visualization)")
    print("=" * 90)
    print(f"Seeker Levels: {seeker_levels}")
    print(f"MTD Strategies: {[s.name for s in strategies]}")
    print(f"Episodes: {num_episodes}, W&B: {wb_logger is not None}")
    print("=" * 90 + "\n")
    
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
                wb_logger=wb_logger,
            )
            
            key = f"L{level}_{strategy.name.replace(' ', '_').replace('-', '_')}"
            results[key] = result
            
            des = result.metrics.get('MTD/DES_mean', 0)
            mttc = result.metrics.get('MTD/MTTC_mean', 200)
            survival = result.metrics.get('Defense/BreachPrevented_mean', 0)
            print(f"DES: {des:.3f} | MTTC: {mttc:.0f} | Survive: {survival:.1%}")
    
    # 결과 저장
    save_results(results, output_path)
    
    # 로컬 시각화 생성
    generate_publication_plots(results, output_path)
    
    # W&B 추가 로깅
    if wb_logger:
        print("\n📊 Generating W&B charts...")
        wb_logger.log_strategy_comparison_charts(results)
        wb_logger.log_comparison_table(results)
        wb_logger.log_summary(results)
        wb_logger.finish()
    
    # LaTeX 테이블
    mtd_modes = list(set(r.mtd_mode for r in results.values()))
    mode_order = ["No MTD", "Static MTD", "Heuristic MTD", "RL MTD", "RL-CTI MTD"]
    mtd_modes = [m for m in mode_order if m in mtd_modes]
    print_latex_table(results, mtd_modes, seeker_levels)
    
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
    
    csv_lines = ["seeker_level,mtd_mode,metric,mean,std"]
    for key, result in results.items():
        for metric_name, value in result.metrics.items():
            if metric_name.endswith("_mean"):
                base_name = metric_name.replace("_mean", "")
                std_name = f"{base_name}_std"
                std_val = result.metrics.get(std_name, 0)
                csv_lines.append(
                    f"{result.seeker_level},{result.mtd_mode},"
                    f"{base_name},{value:.4f},{std_val:.4f}"
                )
    
    with open(output_path / "results.csv", "w") as f:
        f.write("\n".join(csv_lines))


def generate_publication_plots(results: Dict[str, ExperimentResult], output_path: Path):
    """논문 품질 시각화 생성 (로컬 저장)"""
    set_publication_style()
    
    levels = [0, 1, 2, 3, 4]
    level_names = ["Script\nKiddie", "Hobbyist", "Professional", "Expert", "APT"]
    
    mtd_modes = list(set(r.mtd_mode for r in results.values()))
    mode_order = ["No MTD", "Static MTD", "Heuristic MTD", "RL MTD", "RL-CTI MTD"]
    mtd_modes = [m for m in mode_order if m in mtd_modes]
    
    # Figure 1: Main Results (2x2)
    fig, axes = plt.subplots(2, 2, figsize=(10, 8))
    
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
                color=COLORS.get(mode, '#999'), label=mode, linewidth=1.5)
    
    ax.set_xlabel('Attacker Sophistication Level')
    ax.set_ylabel('MTTC (steps)')
    ax.set_title('(b) Mean Time To Compromise')
    ax.set_xticks(levels)
    ax.legend(loc='upper right', framealpha=0.9, fontsize=8)
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
                color=COLORS.get(mode, '#999'), label=mode, linewidth=1.5)
    
    ax.set_xlabel('Attacker Sophistication Level')
    ax.set_ylabel('Attack Surface Reduction (ASR)')
    ax.set_title('(c) Attack Surface Reduction')
    ax.set_xticks(levels)
    ax.set_ylim(0, 1.0)
    ax.legend(loc='upper right', framealpha=0.9, fontsize=8)
    ax.grid(True, alpha=0.3, linestyle='--')
    
    # (d) Cost-Effectiveness Scatter
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
                       marker=MARKERS.get(mode, 'o'), s=80, alpha=0.8,
                       edgecolors='black', linewidth=0.5)
            for j, level in enumerate(levels):
                if j < len(costs):
                    ax.annotate(f"L{level}", (costs[j], effectiveness[j]),
                                textcoords="offset points", xytext=(3, 3),
                                fontsize=7, alpha=0.7)
    
    ax.set_xlabel('Total MTD Cost')
    ax.set_ylabel('Defense Effectiveness Score')
    ax.set_title('(d) Cost-Effectiveness Trade-off')
    ax.legend(loc='best', framealpha=0.9, fontsize=8)
    ax.grid(True, alpha=0.3, linestyle='--')
    
    plt.tight_layout()
    plt.savefig(output_path / "fig_main_results.pdf", format='pdf')
    plt.savefig(output_path / "fig_main_results.png", dpi=300)
    plt.close()
    
    # Console Table
    print("\n" + "=" * 140)
    print("COMPARISON TABLE (Academic Metrics)")
    print("=" * 140)
    header = (
        f"{'Level':<15} {'MTD Mode':<15} {'DES':>8} {'MTTC':>8} {'ASR':>8} "
        f"{'CDI':>8} {'NED':>8} {'ASP':>8} {'Cost':>8} {'Survive':>10}"
    )
    print(header)
    print("-" * 140)
    
    for level in levels:
        for mode in mtd_modes:
            key = f"L{level}_{mode.replace(' ', '_').replace('-', '_')}"
            if key in results:
                r = results[key]
                level_name = SEEKER_PROFILES[level]["name"][:12]
                print(
                    f"L{level} {level_name:<12} {mode:<15} "
                    f"{r.metrics.get('MTD/DES_mean', 0):>8.3f} "
                    f"{r.metrics.get('MTD/MTTC_mean', 0):>8.0f} "
                    f"{r.metrics.get('MTD/ASR_mean', 0):>8.3f} "
                    f"{r.metrics.get('MTD/CDI_mean', 0):>8.3f} "
                    f"{r.metrics.get('MTD/NED_mean', 0):>8.3f} "
                    f"{r.metrics.get('MTD/ASP_mean', 0):>8.3f} "
                    f"{r.metrics.get('Cost/Total_mean', 0):>8.2f} "
                    f"{r.metrics.get('Defense/BreachPrevented_mean', 0)*100:>9.1f}%"
                )
    print("=" * 140)
    
    print(f"\n✅ Publication-quality figures saved to {output_path}")


def print_latex_table(results: Dict[str, ExperimentResult], mtd_modes: List[str], levels: List[int]):
    """LaTeX 테이블 생성"""
    print("\n" + "=" * 80)
    print("LaTeX Table")
    print("=" * 80)
    
    print("\\begin{table}[htbp]")
    print("\\centering")
    print("\\caption{Defense Effectiveness Score (DES) by MTD Strategy and Attacker Level}")
    print("\\label{tab:des_results}")
    print("\\begin{tabular}{l" + "c" * len(levels) + "c}")
    print("\\toprule")
    print("Strategy & " + " & ".join([f"L{l}" for l in levels]) + " & Avg. \\\\")
    print("\\midrule")
    
    for mode in mtd_modes:
        row = [mode]
        values = []
        for level in levels:
            key = f"L{level}_{mode.replace(' ', '_').replace('-', '_')}"
            if key in results:
                des = results[key].metrics.get("MTD/DES_mean", 0)
                row.append(f"{des:.3f}")
                values.append(des)
            else:
                row.append("-")
        
        if values:
            row.append(f"{np.mean(values):.3f}")
        else:
            row.append("-")
        
        print(" & ".join(row) + " \\\\")
    
    print("\\bottomrule")
    print("\\end{tabular}")
    print("\\end{table}")
    print("=" * 80)


# =============================================================================
# CLI
# =============================================================================
def main():
    parser = argparse.ArgumentParser(description="MTD Comparison Evaluation v08.5 with Enhanced W&B")
    
    # 기본 설정
    parser.add_argument("--rl-model", type=str, default=None)
    parser.add_argument("--episodes", type=int, default=50)
    parser.add_argument("--max-steps", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output-dir", type=str, default="eval_results_v08")
    
    # 전략 옵션
    parser.add_argument("--include-static", action="store_true", default=True)
    parser.add_argument("--include-rl-cti", action="store_true")
    
    # W&B 설정
    parser.add_argument("--wandb", action="store_true", help="W&B 로깅 활성화")
    parser.add_argument("--wandb-project", type=str, default="mtd-rl-eval")
    parser.add_argument("--wandb-name", type=str, default=None)
    
    args = parser.parse_args()
    
    run_all_experiments(
        rl_model_path=args.rl_model,
        num_episodes=args.episodes,
        max_steps=args.max_steps,
        seed=args.seed,
        output_dir=args.output_dir,
        include_static=args.include_static,
        include_rl_cti=args.include_rl_cti,
        wandb_project=args.wandb_project if args.wandb else None,
        wandb_name=args.wandb_name,
    )


if __name__ == "__main__":
    main()
