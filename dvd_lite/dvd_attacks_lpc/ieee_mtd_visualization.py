#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IEEE ACCESS Style Publication Graphs for MTD RL Results
========================================================
민성님의 MTD RL 테스트베드용 논문 그래프 생성 코드

사용법:
    python ieee_mtd_visualization.py --input results.json --output ./figures/
    
    또는 코드에서 직접:
    from ieee_mtd_visualization import IEEEGraphGenerator
    gen = IEEEGraphGenerator(data)
    gen.plot_all('./figures/')
"""

import json
import argparse
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import Patch
from matplotlib.lines import Line2D
import warnings
warnings.filterwarnings('ignore')


# =============================================================================
# IEEE Style Configuration
# =============================================================================
class IEEEStyle:
    """IEEE ACCESS 논문 스타일 설정"""
    
    # Column widths (inches)
    SINGLE_COL = 3.5
    DOUBLE_COL = 7.16
    
    # Color scheme (colorblind-friendly + grayscale compatible)
    COLORS = {
        'No MTD': '#404040',      # Dark gray
        'Heuristic': '#808080',   # Medium gray  
        'RL MTD': '#1f77b4',      # Blue (stands out)
    }
    
    # Alternative color schemes
    COLORS_VIBRANT = {
        'No MTD': '#E64B35',      # Red
        'Heuristic': '#4DBBD5',   # Cyan
        'RL MTD': '#00A087',      # Green
    }
    
    COLORS_GRAYSCALE = {
        'No MTD': '#000000',
        'Heuristic': '#666666',
        'RL MTD': '#AAAAAA',
    }
    
    # Hatching patterns for grayscale distinction
    HATCHES = {
        'No MTD': '',
        'Heuristic': '///',
        'RL MTD': 'xxx',
    }
    
    # Markers for line plots
    MARKERS = {
        'No MTD': 's',      # Square
        'Heuristic': '^',   # Triangle
        'RL MTD': 'o',      # Circle
    }
    
    LINESTYLES = {
        'No MTD': '--',
        'Heuristic': '-.',
        'RL MTD': '-',
    }
    
    # Attacker level labels
    LEVEL_LABELS = {
        0: 'L0\n(Script Kiddie)',
        1: 'L1\n(Mainstream)',
        2: 'L2\n(Time-Aware)',
        3: 'L3\n(Adaptive)',
        4: 'L4\n(Expert APT)',
    }
    
    LEVEL_LABELS_SHORT = ['L0', 'L1', 'L2', 'L3', 'L4']
    
    @staticmethod
    def apply():
        """Apply IEEE style to matplotlib"""
        plt.rcParams.update({
            # Font settings
            'font.family': 'serif',
            'font.serif': ['Times New Roman', 'DejaVu Serif', 'Times'],
            'font.size': 10,
            'axes.titlesize': 11,
            'axes.labelsize': 10,
            'xtick.labelsize': 9,
            'ytick.labelsize': 9,
            'legend.fontsize': 9,
            
            # Figure settings
            'figure.dpi': 300,
            'savefig.dpi': 300,
            'savefig.bbox': 'tight',
            'savefig.pad_inches': 0.05,
            
            # Line settings
            'lines.linewidth': 1.5,
            'lines.markersize': 6,
            
            # Axes settings
            'axes.linewidth': 0.8,
            'axes.grid': True,
            'axes.axisbelow': True,
            'grid.alpha': 0.3,
            'grid.linewidth': 0.5,
            
            # Legend
            'legend.framealpha': 0.9,
            'legend.edgecolor': '0.8',
            'legend.fancybox': False,
            
            # Ticks
            'xtick.direction': 'in',
            'ytick.direction': 'in',
            'xtick.major.size': 4,
            'ytick.major.size': 4,
        })


# =============================================================================
# Data Handler
# =============================================================================
class MTDDataHandler:
    """MTD 실험 결과 데이터 처리"""
    
    def __init__(self, data: Dict):
        self.data = data
        self.levels = [0, 1, 2, 3, 4]
        self.mtd_modes = ['No MTD', 'Heuristic', 'RL MTD']
    
    @classmethod
    def from_json(cls, filepath: str) -> 'MTDDataHandler':
        """JSON 파일에서 데이터 로드"""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls(data)
    
    @classmethod
    def from_eval_results(cls, results: Dict) -> 'MTDDataHandler':
        """rl_evaluate_v07.py 결과에서 데이터 변환"""
        # 이미 올바른 형식이면 그대로 사용
        if any(key.startswith('L') for key in results.keys()):
            return cls(results)
        
        # 다른 형식이면 변환
        converted = {}
        for key, value in results.items():
            if isinstance(value, dict) and 'metrics' in value:
                converted[key] = value
        return cls(converted)
    
    def get_metric(self, level: int, mode: str, metric: str) -> Tuple[float, float]:
        """특정 레벨/모드의 메트릭 값과 표준편차 반환"""
        key = f"L{level}_{mode.replace(' ', '_')}"
        if key in self.data:
            mean = self.data[key]['metrics'].get(f'{metric}_mean', 0)
            std = self.data[key]['metrics'].get(f'{metric}_std', 0)
            return mean, std
        return 0.0, 0.0
    
    def get_metric_by_level(self, metric: str, mode: str) -> Tuple[List[int], np.ndarray, np.ndarray]:
        """특정 MTD 모드의 모든 레벨 메트릭 반환"""
        means = []
        stds = []
        for lvl in self.levels:
            m, s = self.get_metric(lvl, mode, metric)
            means.append(m)
            stds.append(s)
        return self.levels, np.array(means), np.array(stds)
    
    def get_all_metrics_matrix(self, metric: str) -> np.ndarray:
        """3x5 매트릭스 형태로 메트릭 반환 (modes x levels)"""
        matrix = []
        for mode in self.mtd_modes:
            row = []
            for lvl in self.levels:
                m, _ = self.get_metric(lvl, mode, metric)
                row.append(m)
            matrix.append(row)
        return np.array(matrix)


# =============================================================================
# IEEE Graph Generator
# =============================================================================
class IEEEGraphGenerator:
    """IEEE ACCESS 스타일 그래프 생성기"""
    
    def __init__(self, data: Dict, color_scheme: str = 'default'):
        """
        Args:
            data: MTD 실험 결과 딕셔너리
            color_scheme: 'default', 'vibrant', 'grayscale' 중 선택
        """
        IEEEStyle.apply()
        self.handler = MTDDataHandler(data)
        self.style = IEEEStyle
        
        # 색상 스킴 선택
        if color_scheme == 'vibrant':
            self.colors = IEEEStyle.COLORS_VIBRANT
        elif color_scheme == 'grayscale':
            self.colors = IEEEStyle.COLORS_GRAYSCALE
        else:
            self.colors = IEEEStyle.COLORS
    
    def _save_figure(self, fig, save_path: str, formats: List[str] = ['pdf', 'png']):
        """여러 형식으로 저장"""
        base_path = Path(save_path).with_suffix('')
        for fmt in formats:
            fig.savefig(f"{base_path}.{fmt}", format=fmt, bbox_inches='tight', dpi=300)
        plt.close(fig)
        print(f"✅ Saved: {base_path}.pdf / .png")
    
    # =========================================================================
    # Individual Plot Methods
    # =========================================================================
    
    def plot_defense_success(self, save_path: str = None, show: bool = False):
        """
        Figure: Defense Success Rate by Attacker Level
        - Grouped bar chart
        - Error bars with std
        """
        fig, ax = plt.subplots(figsize=(self.style.DOUBLE_COL, 3.5))
        
        x = np.arange(len(self.handler.levels))
        width = 0.25
        
        for i, mode in enumerate(self.handler.mtd_modes):
            _, means, stds = self.handler.get_metric_by_level('Defense/Success', mode)
            ax.bar(x + (i - 1) * width, means, width, 
                   yerr=stds, capsize=3,
                   label=mode, color=self.colors[mode],
                   hatch=self.style.HATCHES[mode], 
                   edgecolor='black', linewidth=0.5,
                   error_kw={'linewidth': 0.8, 'capthick': 0.8})
        
        ax.set_xlabel('Attacker Skill Level')
        ax.set_ylabel('Defense Success Rate')
        ax.set_title('(a) Defense Success Rate by Attacker Level')
        ax.set_xticks(x)
        ax.set_xticklabels([self.style.LEVEL_LABELS[l] for l in self.handler.levels])
        ax.legend(loc='upper left', frameon=True)
        ax.set_ylim(0, 0.8)
        ax.yaxis.grid(True, linestyle='--', alpha=0.7)
        ax.xaxis.grid(False)
        
        plt.tight_layout()
        
        if save_path:
            self._save_figure(fig, save_path)
        if show:
            plt.show()
        return fig
    
    def plot_breach_prevention(self, save_path: str = None, show: bool = False):
        """
        Figure: Breach Prevention Rate (%)
        """
        fig, ax = plt.subplots(figsize=(self.style.DOUBLE_COL, 3.5))
        
        x = np.arange(len(self.handler.levels))
        width = 0.25
        
        for i, mode in enumerate(self.handler.mtd_modes):
            _, means, stds = self.handler.get_metric_by_level('Defense/BreachPrevented', mode)
            means = means * 100  # Convert to percentage
            stds = stds * 100
            ax.bar(x + (i - 1) * width, means, width,
                   yerr=stds, capsize=3,
                   label=mode, color=self.colors[mode],
                   hatch=self.style.HATCHES[mode],
                   edgecolor='black', linewidth=0.5,
                   error_kw={'linewidth': 0.8, 'capthick': 0.8})
        
        ax.set_xlabel('Attacker Skill Level')
        ax.set_ylabel('Breach Prevention Rate (%)')
        ax.set_title('(b) Breach Prevention Rate by Defense Strategy')
        ax.set_xticks(x)
        ax.set_xticklabels(self.style.LEVEL_LABELS_SHORT)
        ax.legend(loc='lower left', frameon=True)
        ax.set_ylim(0, 110)
        ax.axhline(y=100, color='green', linestyle=':', linewidth=1, alpha=0.7)
        ax.yaxis.grid(True, linestyle='--', alpha=0.7)
        ax.xaxis.grid(False)
        
        plt.tight_layout()
        
        if save_path:
            self._save_figure(fig, save_path)
        if show:
            plt.show()
        return fig
    
    def plot_decoy_effectiveness(self, save_path: str = None, show: bool = False):
        """
        Figure: Decoy Engagement (Line Plot with Markers)
        """
        fig, ax = plt.subplots(figsize=(self.style.SINGLE_COL * 1.5, 3.2))
        
        for mode in self.handler.mtd_modes:
            levels, means, stds = self.handler.get_metric_by_level('Decoy/Hits', mode)
            ax.errorbar(levels, means, yerr=stds,
                       label=mode, color=self.colors[mode],
                       marker=self.style.MARKERS[mode],
                       linestyle=self.style.LINESTYLES[mode],
                       markersize=7, capsize=3, capthick=1, linewidth=1.5,
                       markerfacecolor='white' if mode != 'RL MTD' else self.colors[mode],
                       markeredgewidth=1.5)
        
        ax.set_xlabel('Attacker Skill Level')
        ax.set_ylabel('Average Decoy Hits')
        ax.set_title('(c) Decoy Engagement by Attacker Level')
        ax.set_xticks([0, 1, 2, 3, 4])
        ax.legend(loc='upper right', frameon=True)
        ax.yaxis.grid(True, linestyle='--', alpha=0.7)
        ax.xaxis.grid(False)
        ax.set_xlim(-0.3, 4.3)
        
        plt.tight_layout()
        
        if save_path:
            self._save_figure(fig, save_path)
        if show:
            plt.show()
        return fig
    
    def plot_cost_analysis(self, save_path: str = None, show: bool = False):
        """
        Figure: Operational Cost Comparison
        """
        fig, ax = plt.subplots(figsize=(self.style.DOUBLE_COL, 3.5))
        
        x = np.arange(len(self.handler.levels))
        width = 0.25
        
        for i, mode in enumerate(self.handler.mtd_modes):
            _, means, stds = self.handler.get_metric_by_level('Cost/Total', mode)
            ax.bar(x + (i - 1) * width, means, width,
                   yerr=stds, capsize=3,
                   label=mode, color=self.colors[mode],
                   hatch=self.style.HATCHES[mode],
                   edgecolor='black', linewidth=0.5,
                   error_kw={'linewidth': 0.8, 'capthick': 0.8})
        
        ax.set_xlabel('Attacker Skill Level')
        ax.set_ylabel('Total Operational Cost')
        ax.set_title('(d) MTD Operational Cost Comparison')
        ax.set_xticks(x)
        ax.set_xticklabels(self.style.LEVEL_LABELS_SHORT)
        ax.legend(loc='upper right', frameon=True)
        ax.yaxis.grid(True, linestyle='--', alpha=0.7)
        ax.xaxis.grid(False)
        
        plt.tight_layout()
        
        if save_path:
            self._save_figure(fig, save_path)
        if show:
            plt.show()
        return fig
    
    def plot_combined_metrics(self, save_path: str = None, show: bool = False):
        """
        Figure: Combined 2x2 Multi-panel Figure (추천)
        """
        fig, axes = plt.subplots(2, 2, figsize=(self.style.DOUBLE_COL, 6))
        
        x = np.arange(len(self.handler.levels))
        width = 0.25
        
        # Panel (a): Defense Success Rate
        ax = axes[0, 0]
        for i, mode in enumerate(self.handler.mtd_modes):
            _, means, stds = self.handler.get_metric_by_level('Defense/Success', mode)
            ax.bar(x + (i - 1) * width, means, width, yerr=stds, capsize=2,
                   label=mode, color=self.colors[mode],
                   hatch=self.style.HATCHES[mode],
                   edgecolor='black', linewidth=0.5,
                   error_kw={'linewidth': 0.6})
        ax.set_ylabel('Success Rate')
        ax.set_title('(a) Defense Success Rate')
        ax.set_xticks(x)
        ax.set_xticklabels(self.style.LEVEL_LABELS_SHORT)
        ax.legend(loc='upper left', fontsize=7, frameon=True)
        ax.yaxis.grid(True, linestyle='--', alpha=0.7)
        
        # Panel (b): Breach Prevention
        ax = axes[0, 1]
        for i, mode in enumerate(self.handler.mtd_modes):
            _, means, stds = self.handler.get_metric_by_level('Defense/BreachPrevented', mode)
            ax.bar(x + (i - 1) * width, means * 100, width, yerr=stds * 100, capsize=2,
                   color=self.colors[mode],
                   hatch=self.style.HATCHES[mode],
                   edgecolor='black', linewidth=0.5,
                   error_kw={'linewidth': 0.6})
        ax.set_ylabel('Prevention Rate (%)')
        ax.set_title('(b) Breach Prevention Rate')
        ax.set_xticks(x)
        ax.set_xticklabels(self.style.LEVEL_LABELS_SHORT)
        ax.set_ylim(0, 110)
        ax.yaxis.grid(True, linestyle='--', alpha=0.7)
        
        # Panel (c): Decoy Hits (Line plot)
        ax = axes[1, 0]
        for mode in self.handler.mtd_modes:
            levels, means, stds = self.handler.get_metric_by_level('Decoy/Hits', mode)
            ax.errorbar(levels, means, yerr=stds,
                       label=mode, color=self.colors[mode],
                       marker=self.style.MARKERS[mode],
                       linestyle=self.style.LINESTYLES[mode],
                       markersize=5, capsize=2, linewidth=1.2,
                       markerfacecolor='white' if mode != 'RL MTD' else self.colors[mode])
        ax.set_xlabel('Attacker Level')
        ax.set_ylabel('Decoy Hits')
        ax.set_title('(c) Decoy Engagement')
        ax.set_xticks([0, 1, 2, 3, 4])
        ax.yaxis.grid(True, linestyle='--', alpha=0.7)
        ax.set_xlim(-0.3, 4.3)
        
        # Panel (d): Total Cost
        ax = axes[1, 1]
        for i, mode in enumerate(self.handler.mtd_modes):
            _, means, stds = self.handler.get_metric_by_level('Cost/Total', mode)
            ax.bar(x + (i - 1) * width, means, width, yerr=stds, capsize=2,
                   color=self.colors[mode],
                   hatch=self.style.HATCHES[mode],
                   edgecolor='black', linewidth=0.5,
                   error_kw={'linewidth': 0.6})
        ax.set_xlabel('Attacker Level')
        ax.set_ylabel('Total Cost')
        ax.set_title('(d) Operational Cost')
        ax.set_xticks(x)
        ax.set_xticklabels(self.style.LEVEL_LABELS_SHORT)
        ax.yaxis.grid(True, linestyle='--', alpha=0.7)
        
        plt.tight_layout()
        
        if save_path:
            self._save_figure(fig, save_path)
        if show:
            plt.show()
        return fig
    
    def plot_heatmap(self, save_path: str = None, show: bool = False):
        """
        Figure: Performance Heatmap (3 panels)
        """
        fig, axes = plt.subplots(1, 3, figsize=(self.style.DOUBLE_COL, 3.0))
        
        metrics_config = [
            ('Defense/BreachPrevented', 'Breach Prevention', 'Greens', lambda x: f'{x*100:.0f}%'),
            ('Decoy/Hits', 'Decoy Hits', 'Blues', lambda x: f'{x:.1f}'),
            ('Cost/Total', 'Total Cost', 'Reds_r', lambda x: f'{x/1000:.1f}k'),
        ]
        
        for idx, (metric, title, cmap, fmt_func) in enumerate(metrics_config):
            ax = axes[idx]
            matrix = self.handler.get_all_metrics_matrix(metric)
            
            if metric == 'Cost/Total':
                matrix = matrix / 1000  # Scale for display
            
            im = ax.imshow(matrix, cmap=cmap, aspect='auto')
            
            # Add text annotations
            for i in range(len(self.handler.mtd_modes)):
                for j in range(len(self.handler.levels)):
                    val = self.handler.get_all_metrics_matrix(metric)[i, j]
                    text = fmt_func(val)
                    text_color = 'white' if matrix[i, j] > matrix.mean() else 'black'
                    ax.text(j, i, text, ha='center', va='center', fontsize=8, color=text_color)
            
            ax.set_xticks(range(len(self.handler.levels)))
            ax.set_xticklabels([f'L{l}' for l in self.handler.levels])
            ax.set_yticks(range(len(self.handler.mtd_modes)))
            ax.set_yticklabels(self.handler.mtd_modes)
            ax.set_title(title, fontsize=10)
            
            if idx == 0:
                ax.set_ylabel('MTD Strategy')
        
        plt.tight_layout()
        
        if save_path:
            self._save_figure(fig, save_path)
        if show:
            plt.show()
        return fig
    
    def plot_tradeoff(self, save_path: str = None, show: bool = False):
        """
        Figure: Defense Effectiveness vs. Cost Trade-off (Scatter)
        """
        fig, ax = plt.subplots(figsize=(self.style.SINGLE_COL * 1.5, 3.5))
        
        for mode in self.handler.mtd_modes:
            xs, ys, sizes = [], [], []
            for lvl in self.handler.levels:
                cost, _ = self.handler.get_metric(lvl, mode, 'Cost/Total')
                breach, _ = self.handler.get_metric(lvl, mode, 'Defense/BreachPrevented')
                decoy, _ = self.handler.get_metric(lvl, mode, 'Decoy/Hits')
                
                xs.append(cost)
                ys.append(breach * 100)
                sizes.append((decoy + 1) * 50)
            
            ax.scatter(xs, ys, s=sizes,
                      label=mode, color=self.colors[mode],
                      marker=self.style.MARKERS[mode],
                      alpha=0.7, edgecolors='black', linewidths=0.5)
        
        ax.set_xlabel('Operational Cost')
        ax.set_ylabel('Breach Prevention Rate (%)')
        ax.set_title('Defense Effectiveness vs. Cost Trade-off')
        ax.legend(loc='lower right', frameon=True)
        ax.yaxis.grid(True, linestyle='--', alpha=0.7)
        ax.xaxis.grid(True, linestyle='--', alpha=0.7)
        ax.annotate('Circle size ∝ Decoy Hits', xy=(0.02, 0.02),
                   xycoords='axes fraction', fontsize=8, fontstyle='italic', color='gray')
        
        plt.tight_layout()
        
        if save_path:
            self._save_figure(fig, save_path)
        if show:
            plt.show()
        return fig
    
    def plot_radar(self, save_path: str = None, show: bool = False,
                   levels_to_show: List[int] = [1, 2, 4]):
        """
        Figure: Radar Chart - Multi-dimensional Comparison
        """
        from math import pi
        
        fig, axes = plt.subplots(1, len(levels_to_show), 
                                 figsize=(self.style.DOUBLE_COL, 3.0),
                                 subplot_kw=dict(polar=True))
        
        categories = ['Breach\nPrevention', 'Decoy\nHits', 'Low Cost', 
                     'Defense\nSuccess', 'Stability']
        N = len(categories)
        angles = [n / float(N) * 2 * pi for n in range(N)]
        angles += angles[:1]
        
        for idx, lvl in enumerate(levels_to_show):
            ax = axes[idx] if len(levels_to_show) > 1 else axes
            
            for mode in self.handler.mtd_modes:
                breach, _ = self.handler.get_metric(lvl, mode, 'Defense/BreachPrevented')
                decoy, _ = self.handler.get_metric(lvl, mode, 'Decoy/Hits')
                cost, _ = self.handler.get_metric(lvl, mode, 'Cost/Total')
                success, _ = self.handler.get_metric(lvl, mode, 'Defense/Success')
                success_std, _ = self.handler.get_metric(lvl, mode, 'Defense/Success')
                _, std_val = self.handler.get_metric(lvl, mode, 'Defense/Success')
                
                values = [
                    breach,
                    min(decoy / 4, 1),
                    1 - min(cost / 1500, 1),
                    success,
                    1 - min(std_val / 0.3, 1),
                ]
                values += values[:1]
                
                ax.plot(angles, values, linewidth=1.5,
                       linestyle=self.style.LINESTYLES[mode],
                       label=mode, color=self.colors[mode])
                ax.fill(angles, values, alpha=0.1, color=self.colors[mode])
            
            ax.set_xticks(angles[:-1])
            ax.set_xticklabels(categories, size=7)
            ax.set_ylim(0, 1)
            ax.set_title(f'Level {lvl}', size=10, y=1.08)
            
            if idx == len(levels_to_show) // 2:
                ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.15),
                         ncol=3, fontsize=7)
        
        plt.tight_layout()
        
        if save_path:
            self._save_figure(fig, save_path)
        if show:
            plt.show()
        return fig
    
    def plot_services_found(self, save_path: str = None, show: bool = False):
        """
        Figure: Services Discovered by Attackers
        """
        fig, ax = plt.subplots(figsize=(self.style.DOUBLE_COL, 3.5))
        
        x = np.arange(len(self.handler.levels))
        width = 0.25
        
        for i, mode in enumerate(self.handler.mtd_modes):
            _, means, stds = self.handler.get_metric_by_level('Attack/ServicesFound', mode)
            ax.bar(x + (i - 1) * width, means, width, yerr=stds, capsize=3,
                   label=mode, color=self.colors[mode],
                   hatch=self.style.HATCHES[mode],
                   edgecolor='black', linewidth=0.5,
                   error_kw={'linewidth': 0.8})
        
        ax.set_xlabel('Attacker Skill Level')
        ax.set_ylabel('Services Discovered')
        ax.set_title('(e) Attack Effectiveness: Services Discovered')
        ax.set_xticks(x)
        ax.set_xticklabels([self.style.LEVEL_LABELS[l] for l in self.handler.levels])
        ax.legend(loc='upper left', frameon=True)
        ax.yaxis.grid(True, linestyle='--', alpha=0.7)
        ax.xaxis.grid(False)
        
        plt.tight_layout()
        
        if save_path:
            self._save_figure(fig, save_path)
        if show:
            plt.show()
        return fig
    
    # =========================================================================
    # Batch Generation
    # =========================================================================
    
    def plot_all(self, output_dir: str, show: bool = False):
        """모든 그래프 생성"""
        os.makedirs(output_dir, exist_ok=True)
        
        print(f"\n{'='*60}")
        print("Generating IEEE ACCESS Publication Figures")
        print(f"{'='*60}\n")
        
        self.plot_defense_success(f'{output_dir}/fig1_defense_success', show)
        self.plot_breach_prevention(f'{output_dir}/fig2_breach_prevention', show)
        self.plot_decoy_effectiveness(f'{output_dir}/fig3_decoy_effectiveness', show)
        self.plot_cost_analysis(f'{output_dir}/fig4_cost_analysis', show)
        self.plot_combined_metrics(f'{output_dir}/fig5_combined_metrics', show)
        self.plot_heatmap(f'{output_dir}/fig6_performance_heatmap', show)
        self.plot_tradeoff(f'{output_dir}/fig7_tradeoff_analysis', show)
        self.plot_radar(f'{output_dir}/fig8_radar_comparison', show)
        self.plot_services_found(f'{output_dir}/fig9_services_found', show)
        
        print(f"\n{'='*60}")
        print(f"All figures saved to: {output_dir}")
        print(f"{'='*60}\n")


# =============================================================================
# Example Data (for testing without external file)
# =============================================================================
EXAMPLE_DATA = {
    "L0_No_MTD": {"seeker_level": 0, "mtd_mode": "No MTD", "episodes": 100,
        "metrics": {"Defense/Success_mean": 0.3552, "Defense/Success_std": 0.0866,
            "Defense/BreachPrevented_mean": 0.99, "Defense/BreachPrevented_std": 0.0995,
            "Cost/Total_mean": 592.99, "Cost/Total_std": 47.00,
            "Decoy/Hits_mean": 0.36, "Decoy/Hits_std": 0.62,
            "Attack/ServicesFound_mean": 0.01, "Attack/ServicesFound_std": 0.10}},
    "L0_Heuristic": {"seeker_level": 0, "mtd_mode": "Heuristic", "episodes": 100,
        "metrics": {"Defense/Success_mean": 0.0805, "Defense/Success_std": 0.1554,
            "Defense/BreachPrevented_mean": 1.0, "Defense/BreachPrevented_std": 0.0,
            "Cost/Total_mean": 430.11, "Cost/Total_std": 6.86,
            "Decoy/Hits_mean": 0.71, "Decoy/Hits_std": 0.89,
            "Attack/ServicesFound_mean": 0.0, "Attack/ServicesFound_std": 0.0}},
    "L0_RL_MTD": {"seeker_level": 0, "mtd_mode": "RL MTD", "episodes": 100,
        "metrics": {"Defense/Success_mean": 0.0588, "Defense/Success_std": 0.1398,
            "Defense/BreachPrevented_mean": 1.0, "Defense/BreachPrevented_std": 0.0,
            "Cost/Total_mean": 1243.47, "Cost/Total_std": 5.04,
            "Decoy/Hits_mean": 2.22, "Decoy/Hits_std": 1.64,
            "Attack/ServicesFound_mean": 0.01, "Attack/ServicesFound_std": 0.10}},
    "L1_No_MTD": {"seeker_level": 1, "mtd_mode": "No MTD", "episodes": 100,
        "metrics": {"Defense/Success_mean": 0.4844, "Defense/Success_std": 0.0687,
            "Defense/BreachPrevented_mean": 1.0, "Defense/BreachPrevented_std": 0.0,
            "Cost/Total_mean": 597.75, "Cost/Total_std": 0.50,
            "Decoy/Hits_mean": 0.48, "Decoy/Hits_std": 0.67,
            "Attack/ServicesFound_mean": 0.0, "Attack/ServicesFound_std": 0.0}},
    "L1_Heuristic": {"seeker_level": 1, "mtd_mode": "Heuristic", "episodes": 100,
        "metrics": {"Defense/Success_mean": 0.2110, "Defense/Success_std": 0.2187,
            "Defense/BreachPrevented_mean": 0.99, "Defense/BreachPrevented_std": 0.0995,
            "Cost/Total_mean": 431.05, "Cost/Total_std": 40.85,
            "Decoy/Hits_mean": 0.73, "Decoy/Hits_std": 0.93,
            "Attack/ServicesFound_mean": 0.04, "Attack/ServicesFound_std": 0.20}},
    "L1_RL_MTD": {"seeker_level": 1, "mtd_mode": "RL MTD", "episodes": 100,
        "metrics": {"Defense/Success_mean": 0.0776, "Defense/Success_std": 0.1388,
            "Defense/BreachPrevented_mean": 0.94, "Defense/BreachPrevented_std": 0.2375,
            "Cost/Total_mean": 1198.53, "Cost/Total_std": 188.32,
            "Decoy/Hits_mean": 3.48, "Decoy/Hits_std": 2.23,
            "Attack/ServicesFound_mean": 0.07, "Attack/ServicesFound_std": 0.26}},
    "L2_No_MTD": {"seeker_level": 2, "mtd_mode": "No MTD", "episodes": 100,
        "metrics": {"Defense/Success_mean": 0.5429, "Defense/Success_std": 0.1037,
            "Defense/BreachPrevented_mean": 0.86, "Defense/BreachPrevented_std": 0.3470,
            "Cost/Total_mean": 527.80, "Cost/Total_std": 175.84,
            "Decoy/Hits_mean": 0.52, "Decoy/Hits_std": 0.66,
            "Attack/ServicesFound_mean": 0.15, "Attack/ServicesFound_std": 0.38}},
    "L2_Heuristic": {"seeker_level": 2, "mtd_mode": "Heuristic", "episodes": 100,
        "metrics": {"Defense/Success_mean": 0.3347, "Defense/Success_std": 0.1988,
            "Defense/BreachPrevented_mean": 0.98, "Defense/BreachPrevented_std": 0.14,
            "Cost/Total_mean": 431.20, "Cost/Total_std": 48.24,
            "Decoy/Hits_mean": 0.87, "Decoy/Hits_std": 1.06,
            "Attack/ServicesFound_mean": 0.03, "Attack/ServicesFound_std": 0.17}},
    "L2_RL_MTD": {"seeker_level": 2, "mtd_mode": "RL MTD", "episodes": 100,
        "metrics": {"Defense/Success_mean": 0.0618, "Defense/Success_std": 0.1132,
            "Defense/BreachPrevented_mean": 0.76, "Defense/BreachPrevented_std": 0.4271,
            "Cost/Total_mean": 1076.07, "Cost/Total_std": 341.34,
            "Decoy/Hits_mean": 3.67, "Decoy/Hits_std": 2.38,
            "Attack/ServicesFound_mean": 0.30, "Attack/ServicesFound_std": 0.52}},
    "L3_No_MTD": {"seeker_level": 3, "mtd_mode": "No MTD", "episodes": 100,
        "metrics": {"Defense/Success_mean": 0.6112, "Defense/Success_std": 0.1543,
            "Defense/BreachPrevented_mean": 0.81, "Defense/BreachPrevented_std": 0.3923,
            "Cost/Total_mean": 503.48, "Cost/Total_std": 199.97,
            "Decoy/Hits_mean": 0.29, "Decoy/Hits_std": 0.53,
            "Attack/ServicesFound_mean": 0.22, "Attack/ServicesFound_std": 0.46}},
    "L3_Heuristic": {"seeker_level": 3, "mtd_mode": "Heuristic", "episodes": 100,
        "metrics": {"Defense/Success_mean": 0.4266, "Defense/Success_std": 0.2081,
            "Defense/BreachPrevented_mean": 0.96, "Defense/BreachPrevented_std": 0.1960,
            "Cost/Total_mean": 426.72, "Cost/Total_std": 70.86,
            "Decoy/Hits_mean": 0.50, "Decoy/Hits_std": 0.87,
            "Attack/ServicesFound_mean": 0.06, "Attack/ServicesFound_std": 0.24}},
    "L3_RL_MTD": {"seeker_level": 3, "mtd_mode": "RL MTD", "episodes": 100,
        "metrics": {"Defense/Success_mean": 0.0619, "Defense/Success_std": 0.0914,
            "Defense/BreachPrevented_mean": 0.53, "Defense/BreachPrevented_std": 0.4991,
            "Cost/Total_mean": 914.71, "Cost/Total_std": 414.65,
            "Decoy/Hits_mean": 2.40, "Decoy/Hits_std": 1.68,
            "Attack/ServicesFound_mean": 0.51, "Attack/ServicesFound_std": 0.59}},
    "L4_No_MTD": {"seeker_level": 4, "mtd_mode": "No MTD", "episodes": 100,
        "metrics": {"Defense/Success_mean": 0.6290, "Defense/Success_std": 0.2128,
            "Defense/BreachPrevented_mean": 0.68, "Defense/BreachPrevented_std": 0.4665,
            "Cost/Total_mean": 429.96, "Cost/Total_std": 250.12,
            "Decoy/Hits_mean": 0.13, "Decoy/Hits_std": 0.34,
            "Attack/ServicesFound_mean": 0.37, "Attack/ServicesFound_std": 0.58}},
    "L4_Heuristic": {"seeker_level": 4, "mtd_mode": "Heuristic", "episodes": 100,
        "metrics": {"Defense/Success_mean": 0.5344, "Defense/Success_std": 0.2023,
            "Defense/BreachPrevented_mean": 0.85, "Defense/BreachPrevented_std": 0.3571,
            "Cost/Total_mean": 391.43, "Cost/Total_std": 119.10,
            "Decoy/Hits_mean": 0.26, "Decoy/Hits_std": 0.52,
            "Attack/ServicesFound_mean": 0.15, "Attack/ServicesFound_std": 0.36}},
    "L4_RL_MTD": {"seeker_level": 4, "mtd_mode": "RL MTD", "episodes": 100,
        "metrics": {"Defense/Success_mean": 0.0743, "Defense/Success_std": 0.0943,
            "Defense/BreachPrevented_mean": 0.32, "Defense/BreachPrevented_std": 0.4665,
            "Cost/Total_mean": 687.09, "Cost/Total_std": 469.45,
            "Decoy/Hits_mean": 1.11, "Decoy/Hits_std": 1.11,
            "Attack/ServicesFound_mean": 0.75, "Attack/ServicesFound_std": 0.55}},
}


# =============================================================================
# CLI Entry Point
# =============================================================================
def main():
    parser = argparse.ArgumentParser(
        description='IEEE ACCESS Style Graph Generator for MTD RL Results',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
    # JSON 파일에서 그래프 생성
    python ieee_mtd_visualization.py --input results.json --output ./figures/
    
    # 예제 데이터로 테스트
    python ieee_mtd_visualization.py --example --output ./figures/
    
    # 특정 그래프만 생성
    python ieee_mtd_visualization.py --input results.json --figure combined
    
    # 색상 스킴 변경
    python ieee_mtd_visualization.py --example --color vibrant
        '''
    )
    
    parser.add_argument('--input', '-i', type=str, help='Input JSON file path')
    parser.add_argument('--output', '-o', type=str, default='./figures',
                       help='Output directory (default: ./figures)')
    parser.add_argument('--example', '-e', action='store_true',
                       help='Use example data for testing')
    parser.add_argument('--figure', '-f', type=str, default='all',
                       choices=['all', 'defense', 'breach', 'decoy', 'cost',
                               'combined', 'heatmap', 'tradeoff', 'radar', 'services'],
                       help='Which figure to generate')
    parser.add_argument('--color', '-c', type=str, default='default',
                       choices=['default', 'vibrant', 'grayscale'],
                       help='Color scheme')
    parser.add_argument('--show', '-s', action='store_true',
                       help='Show figures interactively')
    
    args = parser.parse_args()
    
    # 데이터 로드
    if args.example:
        data = EXAMPLE_DATA
        print("Using example data...")
    elif args.input:
        with open(args.input, 'r') as f:
            data = json.load(f)
        print(f"Loaded data from: {args.input}")
    else:
        print("Using example data (no input file specified)...")
        data = EXAMPLE_DATA
    
    # 그래프 생성기 초기화
    gen = IEEEGraphGenerator(data, color_scheme=args.color)
    
    # 출력 디렉토리 생성
    os.makedirs(args.output, exist_ok=True)
    
    # 그래프 생성
    if args.figure == 'all':
        gen.plot_all(args.output, show=args.show)
    else:
        figure_map = {
            'defense': ('plot_defense_success', 'fig1_defense_success'),
            'breach': ('plot_breach_prevention', 'fig2_breach_prevention'),
            'decoy': ('plot_decoy_effectiveness', 'fig3_decoy_effectiveness'),
            'cost': ('plot_cost_analysis', 'fig4_cost_analysis'),
            'combined': ('plot_combined_metrics', 'fig5_combined_metrics'),
            'heatmap': ('plot_heatmap', 'fig6_performance_heatmap'),
            'tradeoff': ('plot_tradeoff', 'fig7_tradeoff_analysis'),
            'radar': ('plot_radar', 'fig8_radar_comparison'),
            'services': ('plot_services_found', 'fig9_services_found'),
        }
        
        method_name, filename = figure_map[args.figure]
        method = getattr(gen, method_name)
        method(f"{args.output}/{filename}", show=args.show)
    
    print("\n✅ Done!")


if __name__ == "__main__":
    main()