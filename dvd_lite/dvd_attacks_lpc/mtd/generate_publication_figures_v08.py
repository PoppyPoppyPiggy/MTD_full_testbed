#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MTD-RL Publication Quality Evaluation v08
==========================================

v08 코드와 통합된 IEEE Access 스타일 논문 품질 평가 및 시각화

기능:
1. 기존 evaluate_mtd_comparison_v08.py와 통합
2. IEEE Access 스타일 그래프 생성
3. 트렌드 라인 및 통계 분석
4. 종합 논문 Figure 자동 생성

저자: MTD-RL Research Team
버전: 0.8.6
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')

# Scipy
try:
    from scipy import stats
    from scipy.signal import savgol_filter, find_peaks
    from scipy.ndimage import gaussian_filter1d
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

# Import publication visualizer
sys.path.insert(0, str(Path(__file__).parent))
from publication_visualizer_v08 import (
    IEEEAccessPlotter, 
    set_ieee_style, 
    compute_trend_line,
    find_peaks_and_valleys,
    compute_correlation,
    COLORS, MARKERS, HATCHES,
    MTD_METRICS_INFO
)

# 로컬 v08 모듈 (존재하면 import)
try:
    sys.path.insert(0, str(Path(__file__).parent.parent / "dvd_lite" / "dvd_attacks_lpc" / "mtd"))
    from rl_config_v08 import (
        ACTION_DIM,
        ACTION_PARAM_KEYS,
        SEEKER_PROFILES,
        FEATURE_KEYS,
        STATE_DIM,
        MTDConfig,
    )
    from rl_environment_v08 import MTDEnvironment
    HAS_V08 = True
except ImportError:
    HAS_V08 = False
    # Fallback definitions
    STATE_DIM = 17
    ACTION_DIM = 7
    ACTION_PARAM_KEYS = [
        "shuffle_intensity", "port_hop_intensity", "decoy_ratio",
        "blacklist_aggression", "blacklist_duration", 
        "service_swap_intensity", "service_swap_target"
    ]
    SEEKER_PROFILES = {
        0: {"name": "Script Kiddie"},
        1: {"name": "Hobbyist"},
        2: {"name": "Professional"},
        3: {"name": "Expert"},
        4: {"name": "APT"},
    }

# PyTorch (optional)
try:
    import torch
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False


# =============================================================================
# Experiment Result 데이터 클래스
# =============================================================================
@dataclass
class ExperimentResult:
    """실험 결과"""
    seeker_level: int
    mtd_mode: str
    episodes: int
    metrics: Dict[str, float]
    raw_metrics: List[Dict]
    episode_metrics: List[Dict] = field(default_factory=list)


# =============================================================================
# IEEE Access Style Figure Generator
# =============================================================================
class IEEEAccessFigureGenerator:
    """IEEE Access 논문 Figure 생성기"""
    
    def __init__(self, output_dir: str = "figures_publication"):
        self.plotter = IEEEAccessPlotter(output_dir=output_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        set_ieee_style()
        
    def generate_all_figures(
        self,
        results: Dict[str, ExperimentResult],
        training_metrics: Optional[List[Dict]] = None,
    ) -> Dict[str, str]:
        """
        모든 논문 Figure 생성
        
        Args:
            results: 평가 결과 {key: ExperimentResult}
            training_metrics: 학습 메트릭 리스트 (optional)
            
        Returns:
            생성된 파일 경로 딕셔너리
        """
        generated = {}
        
        # 데이터 추출
        levels = sorted(list(set(r.seeker_level for r in results.values())))
        strategies = sorted(list(set(r.mtd_mode for r in results.values())))
        mode_order = ["No MTD", "Static MTD", "Heuristic MTD", "RL MTD", "RL-CTI MTD"]
        strategies = [m for m in mode_order if m in strategies]
        
        level_names = ["Script\nKiddie", "Hobbyist", "Professional", "Expert", "APT"]
        
        # === Figure 1: Main Results (2x2) ===
        print("Generating Figure 1: Main Results...")
        fig1_path = self._generate_main_results_figure(
            results, levels, strategies, level_names
        )
        generated["fig_main_results"] = fig1_path
        
        # === Figure 2: DES vs Episode with Trend ===
        if training_metrics:
            print("Generating Figure 2: DES Training Progress...")
            fig2_path = self._generate_training_progress_figure(training_metrics)
            generated["fig_training_progress"] = fig2_path
        
        # === Figure 3: Detailed Metrics Comparison ===
        print("Generating Figure 3: Detailed Metrics...")
        fig3_path = self._generate_detailed_metrics_figure(
            results, levels, strategies, level_names
        )
        generated["fig_detailed_metrics"] = fig3_path
        
        # === Figure 4: Action Distribution ===
        print("Generating Figure 4: Action Distribution...")
        fig4_path = self._generate_action_distribution_figure(
            results, levels, strategies
        )
        generated["fig_action_distribution"] = fig4_path
        
        # === Figure 5: Cost Analysis ===
        print("Generating Figure 5: Cost Analysis...")
        fig5_path = self._generate_cost_analysis_figure(
            results, levels, strategies, level_names
        )
        generated["fig_cost_analysis"] = fig5_path
        
        # === Figure 6: Heatmap ===
        print("Generating Figure 6: Performance Heatmap...")
        fig6_path = self._generate_heatmap_figure(
            results, levels, strategies
        )
        generated["fig_heatmap"] = fig6_path
        
        print(f"\n✅ All figures generated in: {self.output_dir}")
        
        return generated
    
    def _generate_main_results_figure(
        self,
        results: Dict[str, ExperimentResult],
        levels: List[int],
        strategies: List[str],
        level_names: List[str],
    ) -> str:
        """Figure 1: Main Results (2x2 subplot)"""
        fig, axes = plt.subplots(2, 2, figsize=(12, 10))
        
        # (a) DES Bar Chart with Error Bars
        ax = axes[0, 0]
        x = np.arange(len(levels))
        width = 0.8 / len(strategies)
        
        for i, strategy in enumerate(strategies):
            values = []
            errors = []
            for level in levels:
                key = f"L{level}_{strategy.replace(' ', '_').replace('-', '_')}"
                if key in results:
                    values.append(results[key].metrics.get("MTD/DES_mean", 0))
                    errors.append(results[key].metrics.get("MTD/DES_std", 0))
                else:
                    values.append(0)
                    errors.append(0)
            
            offset = (i - len(strategies)/2 + 0.5) * width
            ax.bar(x + offset, values, width,
                   label=strategy, color=COLORS.get(strategy, f'C{i}'),
                   yerr=errors, capsize=2,
                   hatch=HATCHES[i % len(HATCHES)],
                   edgecolor='black', linewidth=0.5)
        
        ax.set_xlabel('Attacker Sophistication Level', fontsize=11)
        ax.set_ylabel('Defense Effectiveness Score (DES)', fontsize=11)
        ax.set_title('(a) Defense Effectiveness by Attacker Level', fontsize=12, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels(level_names)
        ax.set_ylim(0, 1.0)
        ax.legend(loc='upper right', ncol=2, framealpha=0.9, fontsize=8)
        ax.grid(axis='y', alpha=0.3, linestyle='--')
        
        # (b) MTTC Line with Trend
        ax = axes[0, 1]
        for strategy in strategies:
            values = []
            for level in levels:
                key = f"L{level}_{strategy.replace(' ', '_').replace('-', '_')}"
                if key in results:
                    values.append(results[key].metrics.get("MTD/MTTC_mean", 200))
                else:
                    values.append(200)
            
            color = COLORS.get(strategy, '#999')
            ax.plot(levels, values,
                    marker=MARKERS.get(strategy, 'o'),
                    color=color, label=strategy,
                    linewidth=2, markersize=8)
            
            # Trend line
            if HAS_SCIPY and len(levels) >= 3:
                _, y_trend, _ = compute_trend_line(
                    np.array(levels), np.array(values),
                    method='polynomial', degree=2
                )
                ax.plot(levels, y_trend, color=color,
                        linestyle='--', linewidth=1.5, alpha=0.5)
        
        ax.set_xlabel('Attacker Sophistication Level', fontsize=11)
        ax.set_ylabel('MTTC (steps)', fontsize=11)
        ax.set_title('(b) Mean Time To Compromise', fontsize=12, fontweight='bold')
        ax.set_xticks(levels)
        ax.legend(loc='best', framealpha=0.9, fontsize=8)
        ax.grid(True, alpha=0.3, linestyle='--')
        
        # (c) ASR Line with Trend
        ax = axes[1, 0]
        for strategy in strategies:
            values = []
            for level in levels:
                key = f"L{level}_{strategy.replace(' ', '_').replace('-', '_')}"
                if key in results:
                    values.append(results[key].metrics.get("MTD/ASR_mean", 0))
                else:
                    values.append(0)
            
            color = COLORS.get(strategy, '#999')
            ax.plot(levels, values,
                    marker=MARKERS.get(strategy, 'o'),
                    color=color, label=strategy,
                    linewidth=2, markersize=8)
            
            # Trend line
            if HAS_SCIPY and len(levels) >= 3:
                _, y_trend, _ = compute_trend_line(
                    np.array(levels), np.array(values),
                    method='polynomial', degree=2
                )
                ax.plot(levels, y_trend, color=color,
                        linestyle='--', linewidth=1.5, alpha=0.5)
        
        ax.set_xlabel('Attacker Sophistication Level', fontsize=11)
        ax.set_ylabel('Attack Surface Reduction (ASR)', fontsize=11)
        ax.set_title('(c) Attack Surface Reduction', fontsize=12, fontweight='bold')
        ax.set_xticks(levels)
        ax.set_ylim(0, 1.0)
        ax.legend(loc='best', framealpha=0.9, fontsize=8)
        ax.grid(True, alpha=0.3, linestyle='--')
        
        # (d) Cost-Effectiveness Scatter
        ax = axes[1, 1]
        for strategy in strategies:
            costs = []
            effectiveness = []
            for level in levels:
                key = f"L{level}_{strategy.replace(' ', '_').replace('-', '_')}"
                if key in results:
                    costs.append(results[key].metrics.get("Cost/Total_mean", 0))
                    effectiveness.append(results[key].metrics.get("MTD/DES_mean", 0))
            
            if costs and effectiveness:
                ax.scatter(costs, effectiveness,
                           label=strategy, color=COLORS.get(strategy, '#999'),
                           marker=MARKERS.get(strategy, 'o'), s=100, alpha=0.8,
                           edgecolors='black', linewidth=0.5)
                
                # Level annotation
                for j, level in enumerate(levels):
                    if j < len(costs):
                        ax.annotate(f"L{level}", (costs[j], effectiveness[j]),
                                    textcoords="offset points", xytext=(4, 4),
                                    fontsize=7, alpha=0.8)
        
        ax.set_xlabel('Total MTD Cost', fontsize=11)
        ax.set_ylabel('Defense Effectiveness Score (DES)', fontsize=11)
        ax.set_title('(d) Cost-Effectiveness Trade-off', fontsize=12, fontweight='bold')
        ax.legend(loc='best', framealpha=0.9, fontsize=8)
        ax.grid(True, alpha=0.3, linestyle='--')
        
        plt.tight_layout()
        
        filepath = self.output_dir / "fig1_main_results"
        for ext in ['pdf', 'png']:
            fig.savefig(f"{filepath}.{ext}", dpi=300, bbox_inches='tight')
        plt.close()
        
        return str(filepath) + ".pdf"
    
    def _generate_training_progress_figure(
        self,
        training_metrics: List[Dict],
    ) -> str:
        """Figure 2: Training Progress with Trend"""
        fig, axes = plt.subplots(2, 2, figsize=(12, 10))
        
        episodes = np.arange(len(training_metrics))
        
        # DES
        ax = axes[0, 0]
        des_values = np.array([m.get("MTD/DES", 0) for m in training_metrics])
        
        ax.plot(episodes, des_values, color=COLORS['primary_data'],
                linewidth=0.8, alpha=0.6, label='DES')
        
        if HAS_SCIPY and len(episodes) > 10:
            _, y_trend, stats = compute_trend_line(episodes, des_values, method='savgol')
            ax.plot(episodes, y_trend, color=COLORS['trend_line'],
                    linestyle='--', linewidth=2, label='Trend Line')
            
            # Peak detection
            peaks, valleys = find_peaks_and_valleys(des_values)
            if len(peaks) > 0:
                ax.scatter(episodes[peaks], des_values[peaks], 
                           color=COLORS['highlight'], marker='v', s=60, zorder=5)
        
        ax.set_xlabel('Training Episode', fontsize=11)
        ax.set_ylabel('Defense Effectiveness Score', fontsize=11)
        ax.set_title('(a) DES over Training', fontsize=12, fontweight='bold')
        ax.legend(loc='lower right', framealpha=0.9)
        ax.grid(True, alpha=0.3, linestyle='--')
        
        # Reward
        ax = axes[0, 1]
        rewards = np.array([m.get("episode/reward", 0) for m in training_metrics])
        
        ax.plot(episodes, rewards, color=COLORS['primary_data'],
                linewidth=0.8, alpha=0.6, label='Reward')
        
        if HAS_SCIPY and len(episodes) > 10:
            _, y_trend, _ = compute_trend_line(episodes, rewards, method='savgol')
            ax.plot(episodes, y_trend, color=COLORS['trend_line'],
                    linestyle='--', linewidth=2, label='Trend Line')
        
        ax.set_xlabel('Training Episode', fontsize=11)
        ax.set_ylabel('Episode Reward', fontsize=11)
        ax.set_title('(b) Reward over Training', fontsize=12, fontweight='bold')
        ax.legend(loc='lower right', framealpha=0.9)
        ax.grid(True, alpha=0.3, linestyle='--')
        
        # Cost
        ax = axes[1, 0]
        costs = np.array([m.get("Cost/Total", 0) for m in training_metrics])
        
        ax.plot(episodes, costs, color=COLORS['secondary_data'],
                linewidth=0.8, alpha=0.6, label='Cost')
        
        if HAS_SCIPY and len(episodes) > 10:
            _, y_trend, _ = compute_trend_line(episodes, costs, method='savgol')
            ax.plot(episodes, y_trend, color=COLORS['trend_line'],
                    linestyle='--', linewidth=2, label='Trend Line')
        
        ax.set_xlabel('Training Episode', fontsize=11)
        ax.set_ylabel('Total MTD Cost', fontsize=11)
        ax.set_title('(c) Cost over Training', fontsize=12, fontweight='bold')
        ax.legend(loc='upper left', framealpha=0.9)
        ax.grid(True, alpha=0.3, linestyle='--')
        
        # MTTC
        ax = axes[1, 1]
        mttc = np.array([m.get("MTD/MTTC", 200) for m in training_metrics])
        
        ax.plot(episodes, mttc, color=COLORS['annotation'],
                linewidth=0.8, alpha=0.6, label='MTTC')
        
        if HAS_SCIPY and len(episodes) > 10:
            _, y_trend, _ = compute_trend_line(episodes, mttc, method='savgol')
            ax.plot(episodes, y_trend, color=COLORS['trend_line'],
                    linestyle='--', linewidth=2, label='Trend Line')
        
        ax.set_xlabel('Training Episode', fontsize=11)
        ax.set_ylabel('MTTC (steps)', fontsize=11)
        ax.set_title('(d) MTTC over Training', fontsize=12, fontweight='bold')
        ax.legend(loc='lower right', framealpha=0.9)
        ax.grid(True, alpha=0.3, linestyle='--')
        
        plt.tight_layout()
        
        filepath = self.output_dir / "fig2_training_progress"
        for ext in ['pdf', 'png']:
            fig.savefig(f"{filepath}.{ext}", dpi=300, bbox_inches='tight')
        plt.close()
        
        return str(filepath) + ".pdf"
    
    def _generate_detailed_metrics_figure(
        self,
        results: Dict[str, ExperimentResult],
        levels: List[int],
        strategies: List[str],
        level_names: List[str],
    ) -> str:
        """Figure 3: Detailed Metrics (CDI, NED, ASP)"""
        fig, axes = plt.subplots(1, 3, figsize=(15, 5))
        
        # CDI
        ax = axes[0]
        for strategy in strategies:
            values = []
            for level in levels:
                key = f"L{level}_{strategy.replace(' ', '_').replace('-', '_')}"
                if key in results:
                    values.append(results[key].metrics.get("MTD/CDI_mean", 0))
                else:
                    values.append(0)
            
            color = COLORS.get(strategy, '#999')
            ax.plot(levels, values,
                    marker=MARKERS.get(strategy, 'o'),
                    color=color, label=strategy,
                    linewidth=2, markersize=8)
            
            if HAS_SCIPY and len(levels) >= 3:
                _, y_trend, _ = compute_trend_line(
                    np.array(levels), np.array(values),
                    method='polynomial', degree=2
                )
                ax.plot(levels, y_trend, color=color,
                        linestyle='--', linewidth=1.5, alpha=0.5)
        
        ax.set_xlabel('Attacker Level', fontsize=11)
        ax.set_ylabel('CDI', fontsize=11)
        ax.set_title('Configuration Diversity Index', fontsize=12, fontweight='bold')
        ax.legend(loc='best', framealpha=0.9, fontsize=8)
        ax.grid(True, alpha=0.3, linestyle='--')
        ax.set_ylim(0, 1.0)
        
        # NED
        ax = axes[1]
        for strategy in strategies:
            values = []
            for level in levels:
                key = f"L{level}_{strategy.replace(' ', '_').replace('-', '_')}"
                if key in results:
                    values.append(results[key].metrics.get("MTD/NED_mean", 0))
                else:
                    values.append(0)
            
            color = COLORS.get(strategy, '#999')
            ax.plot(levels, values,
                    marker=MARKERS.get(strategy, 'o'),
                    color=color, label=strategy,
                    linewidth=2, markersize=8)
            
            if HAS_SCIPY and len(levels) >= 3:
                _, y_trend, _ = compute_trend_line(
                    np.array(levels), np.array(values),
                    method='polynomial', degree=2
                )
                ax.plot(levels, y_trend, color=color,
                        linestyle='--', linewidth=1.5, alpha=0.5)
        
        ax.set_xlabel('Attacker Level', fontsize=11)
        ax.set_ylabel('NED', fontsize=11)
        ax.set_title('Normalized Entropy of Defense', fontsize=12, fontweight='bold')
        ax.legend(loc='best', framealpha=0.9, fontsize=8)
        ax.grid(True, alpha=0.3, linestyle='--')
        ax.set_ylim(0, 1.0)
        
        # ASP (lower is better)
        ax = axes[2]
        for strategy in strategies:
            values = []
            for level in levels:
                key = f"L{level}_{strategy.replace(' ', '_').replace('-', '_')}"
                if key in results:
                    values.append(results[key].metrics.get("MTD/ASP_mean", 0))
                else:
                    values.append(0)
            
            color = COLORS.get(strategy, '#999')
            ax.plot(levels, values,
                    marker=MARKERS.get(strategy, 'o'),
                    color=color, label=strategy,
                    linewidth=2, markersize=8)
            
            if HAS_SCIPY and len(levels) >= 3:
                _, y_trend, _ = compute_trend_line(
                    np.array(levels), np.array(values),
                    method='polynomial', degree=2
                )
                ax.plot(levels, y_trend, color=color,
                        linestyle='--', linewidth=1.5, alpha=0.5)
        
        ax.set_xlabel('Attacker Level', fontsize=11)
        ax.set_ylabel('ASP', fontsize=11)
        ax.set_title('Attack Success Probability (↓ better)', fontsize=12, fontweight='bold')
        ax.legend(loc='best', framealpha=0.9, fontsize=8)
        ax.grid(True, alpha=0.3, linestyle='--')
        ax.set_ylim(0, 1.0)
        
        plt.tight_layout()
        
        filepath = self.output_dir / "fig3_detailed_metrics"
        for ext in ['pdf', 'png']:
            fig.savefig(f"{filepath}.{ext}", dpi=300, bbox_inches='tight')
        plt.close()
        
        return str(filepath) + ".pdf"
    
    def _generate_action_distribution_figure(
        self,
        results: Dict[str, ExperimentResult],
        levels: List[int],
        strategies: List[str],
    ) -> str:
        """Figure 4: Action Distribution by Strategy"""
        # RL 전략만 필터링
        rl_strategies = [s for s in strategies if "RL" in s]
        if not rl_strategies:
            rl_strategies = strategies[:2]  # Fallback
        
        n_strategies = len(rl_strategies)
        fig, axes = plt.subplots(1, n_strategies, figsize=(6*n_strategies, 5))
        if n_strategies == 1:
            axes = [axes]
        
        action_labels = ['Shuffle', 'Port Hop', 'Decoy', 'Blacklist\nAggr.', 
                        'Blacklist\nDur.', 'Swap\nIntensity', 'Swap\nTarget']
        
        for idx, strategy in enumerate(rl_strategies):
            ax = axes[idx]
            
            # 모든 레벨의 평균 액션
            action_means = np.zeros(len(action_labels))
            count = 0
            
            for level in levels:
                key = f"L{level}_{strategy.replace(' ', '_').replace('-', '_')}"
                if key in results:
                    for i, action_key in enumerate(ACTION_PARAM_KEYS):
                        action_means[i] += results[key].metrics.get(
                            f"Action/{action_key}_mean", 0
                        )
                    count += 1
            
            if count > 0:
                action_means /= count
            
            colors = plt.cm.viridis(np.linspace(0.2, 0.8, len(action_labels)))
            bars = ax.bar(range(len(action_labels)), action_means, color=colors,
                          edgecolor='black', linewidth=0.5)
            
            ax.set_xticks(range(len(action_labels)))
            ax.set_xticklabels(action_labels, rotation=45, ha='right', fontsize=9)
            ax.set_ylabel('Mean Action Value', fontsize=11)
            ax.set_title(f'{strategy} Action Distribution', fontsize=12, fontweight='bold')
            ax.set_ylim(0, 1.0)
            ax.grid(axis='y', alpha=0.3, linestyle='--')
            
            # Value labels
            for bar, val in zip(bars, action_means):
                if val > 0.05:
                    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02,
                            f'{val:.2f}', ha='center', va='bottom', fontsize=8)
        
        plt.tight_layout()
        
        filepath = self.output_dir / "fig4_action_distribution"
        for ext in ['pdf', 'png']:
            fig.savefig(f"{filepath}.{ext}", dpi=300, bbox_inches='tight')
        plt.close()
        
        return str(filepath) + ".pdf"
    
    def _generate_cost_analysis_figure(
        self,
        results: Dict[str, ExperimentResult],
        levels: List[int],
        strategies: List[str],
        level_names: List[str],
    ) -> str:
        """Figure 5: Cost Analysis"""
        fig, axes = plt.subplots(1, 2, figsize=(12, 5))
        
        # (a) Cost by Level and Strategy
        ax = axes[0]
        x = np.arange(len(levels))
        width = 0.8 / len(strategies)
        
        for i, strategy in enumerate(strategies):
            values = []
            for level in levels:
                key = f"L{level}_{strategy.replace(' ', '_').replace('-', '_')}"
                if key in results:
                    values.append(results[key].metrics.get("Cost/Total_mean", 0))
                else:
                    values.append(0)
            
            offset = (i - len(strategies)/2 + 0.5) * width
            ax.bar(x + offset, values, width,
                   label=strategy, color=COLORS.get(strategy, f'C{i}'),
                   hatch=HATCHES[i % len(HATCHES)],
                   edgecolor='black', linewidth=0.5)
        
        ax.set_xlabel('Attacker Level', fontsize=11)
        ax.set_ylabel('Total MTD Cost', fontsize=11)
        ax.set_title('(a) MTD Cost by Strategy', fontsize=12, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels(level_names)
        ax.legend(loc='upper left', framealpha=0.9, fontsize=8)
        ax.grid(axis='y', alpha=0.3, linestyle='--')
        
        # (b) Cost Efficiency Ratio (CER)
        ax = axes[1]
        for strategy in strategies:
            values = []
            for level in levels:
                key = f"L{level}_{strategy.replace(' ', '_').replace('-', '_')}"
                if key in results:
                    values.append(results[key].metrics.get("MTD/CER_mean", 0))
                else:
                    values.append(0)
            
            color = COLORS.get(strategy, '#999')
            ax.plot(levels, values,
                    marker=MARKERS.get(strategy, 'o'),
                    color=color, label=strategy,
                    linewidth=2, markersize=8)
            
            if HAS_SCIPY and len(levels) >= 3:
                _, y_trend, _ = compute_trend_line(
                    np.array(levels), np.array(values),
                    method='polynomial', degree=2
                )
                ax.plot(levels, y_trend, color=color,
                        linestyle='--', linewidth=1.5, alpha=0.5)
        
        ax.set_xlabel('Attacker Level', fontsize=11)
        ax.set_ylabel('Cost Efficiency Ratio (CER)', fontsize=11)
        ax.set_title('(b) Cost Efficiency by Strategy', fontsize=12, fontweight='bold')
        ax.legend(loc='best', framealpha=0.9, fontsize=8)
        ax.grid(True, alpha=0.3, linestyle='--')
        
        plt.tight_layout()
        
        filepath = self.output_dir / "fig5_cost_analysis"
        for ext in ['pdf', 'png']:
            fig.savefig(f"{filepath}.{ext}", dpi=300, bbox_inches='tight')
        plt.close()
        
        return str(filepath) + ".pdf"
    
    def _generate_heatmap_figure(
        self,
        results: Dict[str, ExperimentResult],
        levels: List[int],
        strategies: List[str],
    ) -> str:
        """Figure 6: Performance Heatmap"""
        # DES Heatmap
        heatmap_data = np.zeros((len(strategies), len(levels)))
        
        for i, strategy in enumerate(strategies):
            for j, level in enumerate(levels):
                key = f"L{level}_{strategy.replace(' ', '_').replace('-', '_')}"
                if key in results:
                    heatmap_data[i, j] = results[key].metrics.get("MTD/DES_mean", 0)
        
        fig, ax = plt.subplots(figsize=(10, 6))
        
        im = ax.imshow(heatmap_data, cmap='RdYlGn', aspect='auto', vmin=0, vmax=1)
        
        ax.set_xticks(np.arange(len(levels)))
        ax.set_yticks(np.arange(len(strategies)))
        ax.set_xticklabels([f"L{l}" for l in levels])
        ax.set_yticklabels(strategies)
        
        ax.set_xlabel('Attacker Level', fontsize=11)
        ax.set_ylabel('MTD Strategy', fontsize=11)
        ax.set_title('Defense Effectiveness Score (DES) Heatmap', fontsize=12, fontweight='bold')
        
        # Values in cells
        for i in range(len(strategies)):
            for j in range(len(levels)):
                text_color = 'white' if heatmap_data[i, j] < 0.5 else 'black'
                ax.text(j, i, f"{heatmap_data[i, j]:.3f}",
                        ha="center", va="center", color=text_color,
                        fontsize=11, fontweight='bold')
        
        cbar = plt.colorbar(im, ax=ax, shrink=0.8)
        cbar.set_label('DES Score', fontsize=11)
        
        plt.tight_layout()
        
        filepath = self.output_dir / "fig6_heatmap"
        for ext in ['pdf', 'png']:
            fig.savefig(f"{filepath}.{ext}", dpi=300, bbox_inches='tight')
        plt.close()
        
        return str(filepath) + ".pdf"


# =============================================================================
# CLI and Test
# =============================================================================
def generate_sample_results() -> Dict[str, ExperimentResult]:
    """샘플 결과 데이터 생성"""
    np.random.seed(42)
    
    levels = [0, 1, 2, 3, 4]
    strategies = ["No MTD", "Static MTD", "Heuristic MTD", "RL MTD", "RL-CTI MTD"]
    
    # Base effectiveness by strategy
    base_des = {
        "No MTD": 0.47,
        "Static MTD": 0.55,
        "Heuristic MTD": 0.65,
        "RL MTD": 0.78,
        "RL-CTI MTD": 0.85,
    }
    
    results = {}
    
    for strategy in strategies:
        for level in levels:
            # DES decreases with attacker level
            des_mean = base_des[strategy] - level * 0.03
            des_std = 0.05
            
            # MTTC
            mttc_mean = 200 if strategy == "No MTD" else 180 + np.random.randint(0, 20)
            
            # ASR
            asr_mean = 0.0 if strategy == "No MTD" else 0.65 - level * 0.05
            
            # CDI
            cdi_mean = 0.0 if strategy == "No MTD" else 0.5 + np.random.random() * 0.3
            
            # NED
            ned_mean = 0.0 if strategy == "No MTD" else 0.3 + np.random.random() * 0.4
            
            # ASP
            asp_mean = 0.8 if strategy == "No MTD" else 0.3 - base_des[strategy] * 0.2
            
            # Cost
            cost_map = {
                "No MTD": 0,
                "Static MTD": 15 + level * 2,
                "Heuristic MTD": 30 + level * 3,
                "RL MTD": 150 + level * 5,
                "RL-CTI MTD": 160 + level * 5,
            }
            cost_mean = cost_map[strategy]
            
            # CER
            cer_mean = des_mean / (cost_mean + 0.1) if cost_mean > 0 else 0
            
            # Survival rate
            survival_map = {
                "No MTD": 0.12,
                "Static MTD": 0.35,
                "Heuristic MTD": 0.97,
                "RL MTD": 0.85 - level * 0.08,
                "RL-CTI MTD": 0.92 - level * 0.05,
            }
            survival_mean = survival_map[strategy]
            
            key = f"L{level}_{strategy.replace(' ', '_').replace('-', '_')}"
            
            results[key] = ExperimentResult(
                seeker_level=level,
                mtd_mode=strategy,
                episodes=50,
                metrics={
                    "MTD/DES_mean": des_mean,
                    "MTD/DES_std": des_std,
                    "MTD/MTTC_mean": mttc_mean,
                    "MTD/MTTC_std": 10,
                    "MTD/ASR_mean": max(0, asr_mean),
                    "MTD/ASR_std": 0.05,
                    "MTD/CDI_mean": cdi_mean,
                    "MTD/CDI_std": 0.03,
                    "MTD/NED_mean": ned_mean,
                    "MTD/NED_std": 0.05,
                    "MTD/ASP_mean": max(0, min(1, asp_mean)),
                    "MTD/ASP_std": 0.05,
                    "MTD/CER_mean": cer_mean,
                    "Cost/Total_mean": cost_mean,
                    "Cost/Total_std": cost_mean * 0.1,
                    "Defense/BreachPrevented_mean": survival_mean,
                },
                raw_metrics=[],
            )
    
    return results


def generate_sample_training_metrics() -> List[Dict]:
    """샘플 학습 메트릭 생성"""
    np.random.seed(42)
    
    n_episodes = 300
    metrics = []
    
    for ep in range(n_episodes):
        # DES: gradually improving
        des_base = 0.3 + 0.5 * (1 - np.exp(-ep / 80))
        des = des_base + np.random.normal(0, 0.05)
        
        # Reward: correlated with DES
        reward = des * 100 + np.random.normal(0, 10)
        
        # Cost: increases then stabilizes
        cost = 10 + 20 * (1 - np.exp(-ep / 50)) + np.random.normal(0, 2)
        
        # MTTC
        mttc = 120 + 60 * (1 - np.exp(-ep / 100)) + np.random.normal(0, 10)
        
        metrics.append({
            "MTD/DES": np.clip(des, 0, 1),
            "episode/reward": reward,
            "Cost/Total": max(0, cost),
            "MTD/MTTC": np.clip(mttc, 50, 200),
        })
    
    return metrics


def main():
    parser = argparse.ArgumentParser(
        description="MTD-RL Publication Quality Figure Generator v08"
    )
    parser.add_argument("--output-dir", "-o", type=str, 
                        default="figures_publication",
                        help="Output directory")
    parser.add_argument("--results-file", "-r", type=str, default=None,
                        help="JSON results file from evaluation")
    parser.add_argument("--training-file", "-t", type=str, default=None,
                        help="JSON training metrics file")
    parser.add_argument("--sample", action="store_true",
                        help="Use sample data for demo")
    
    args = parser.parse_args()
    
    print("\n" + "="*60)
    print("MTD-RL Publication Quality Figure Generator v08")
    print("="*60)
    
    generator = IEEEAccessFigureGenerator(output_dir=args.output_dir)
    
    # Load or generate data
    if args.sample:
        print("\nUsing sample data for demonstration...")
        results = generate_sample_results()
        training_metrics = generate_sample_training_metrics()
    else:
        # Load from files
        if args.results_file and os.path.exists(args.results_file):
            with open(args.results_file, 'r') as f:
                results_data = json.load(f)
            # Convert to ExperimentResult objects
            results = {}
            for key, data in results_data.items():
                results[key] = ExperimentResult(
                    seeker_level=data.get("seeker_level", 0),
                    mtd_mode=data.get("mtd_mode", "Unknown"),
                    episodes=data.get("episodes", 50),
                    metrics=data.get("metrics", {}),
                    raw_metrics=data.get("raw_metrics", []),
                )
        else:
            print("No results file provided, using sample data...")
            results = generate_sample_results()
        
        training_metrics = None
        if args.training_file and os.path.exists(args.training_file):
            with open(args.training_file, 'r') as f:
                training_metrics = json.load(f)
        else:
            training_metrics = generate_sample_training_metrics()
    
    # Generate all figures
    generated = generator.generate_all_figures(
        results=results,
        training_metrics=training_metrics,
    )
    
    print("\n" + "="*60)
    print("Generated Figures:")
    print("="*60)
    for name, path in generated.items():
        print(f"  {name}: {path}")
    
    print("\n✅ All figures generated successfully!")
    print(f"   Output directory: {args.output_dir}")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()