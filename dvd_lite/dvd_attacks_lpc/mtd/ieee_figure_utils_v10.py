#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IEEE Figure Utilities v10.1 - Fixed CDI + Layout Options
========================================================

수정사항:
1. CDI 계산 로직 수정 - MTD 액션 기반 실제 다양성 측정
2. 그래프 레이아웃 옵션: 개별 파일, 1x6 가로, 2x3 그리드
3. 값 라벨 겹침 해결
4. CER 계산 검토

Author: MTD-RL Research Team
Version: 10.1
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
from matplotlib.colors import LinearSegmentedColormap


# =============================================================================
# IEEE Style Configuration
# =============================================================================
def setup_ieee_style():
    """IEEE Access 논문 스타일 설정"""
    plt.rcParams.update({
        'font.family': 'serif',
        'font.serif': ['Times New Roman', 'DejaVu Serif', 'serif'],
        'font.size': 10,
        'axes.labelsize': 11,
        'axes.titlesize': 12,
        'legend.fontsize': 9,
        'xtick.labelsize': 10,
        'ytick.labelsize': 10,
        'figure.dpi': 300,
        'savefig.dpi': 300,
        'lines.linewidth': 1.5,
        'lines.markersize': 6,
        'axes.linewidth': 0.8,
        'grid.linewidth': 0.5,
        'grid.alpha': 0.3,
        'axes.grid': True,
        'legend.frameon': True,
        'legend.framealpha': 0.9,
        'legend.edgecolor': 'gray',
        'savefig.bbox': 'tight',
        'savefig.pad_inches': 0.1,
        'axes.spines.top': False,
        'axes.spines.right': False,
    })


# =============================================================================
# Strategy Configuration (논문 Table 12 - 4개 전략만)
# =============================================================================
STRATEGIES = {
    'Baseline': {
        'full_name': 'Baseline (No MTD)',
        'color': '#808080',      # Gray
        'marker': 'o',
        'hatch': '',
    },
    'Static MTD': {
        'full_name': 'Static MTD',
        'color': '#E69F00',      # Orange
        'marker': 's',
        'hatch': '//',
    },
    'Heuristic+CTI': {
        'full_name': 'Heuristic+CTI',
        'color': '#009E73',      # Green
        'marker': '^',
        'hatch': '\\\\',
    },
    'RL-CTI MTD': {
        'full_name': 'RL-CTI MTD (Proposed)',
        'color': '#D55E00',      # Red-Orange (강조)
        'marker': 'p',
        'hatch': '',
    },
}

# Attacker Profiles (논문 Table 9)
ATTACKER_PROFILES = {
    0: {'name': 'Script Kiddie', 'scan_rate': 0.03, 'p_disc': 0.15, 'p_exp': 0.08, 'kappa': 1.00},
    1: {'name': 'Hobbyist', 'scan_rate': 0.05, 'p_disc': 0.25, 'p_exp': 0.12, 'kappa': 0.92},
    2: {'name': 'Professional', 'scan_rate': 0.08, 'p_disc': 0.35, 'p_exp': 0.20, 'kappa': 0.84},
    3: {'name': 'Expert', 'scan_rate': 0.12, 'p_disc': 0.50, 'p_exp': 0.30, 'kappa': 0.76},
    4: {'name': 'APT', 'scan_rate': 0.15, 'p_disc': 0.65, 'p_exp': 0.40, 'kappa': 0.68},
}

# 평가 지표 정의 (논문 Section IV.C)
METRICS = {
    'DES': {
        'full_name': r'$S_{\mathrm{MTD}}$ (DES)',
        'ylabel': r'$S_{\mathrm{MTD}}$',
        'equation': 'Eq.(21)',
        'range': (0, 1),
        'better': 'higher',
        'unit': '',
        'format': '.3f',
    },
    'BR': {
        'full_name': 'Breach Rate',
        'ylabel': 'Breach Rate (%)',
        'equation': 'Eq.(15)',
        'range': (0, 100),
        'better': 'lower',
        'unit': '%',
        'format': '.1f',
    },
    'MTTC': {
        'full_name': 'MTTC',
        'ylabel': 'MTTC (steps)',
        'equation': 'Eq.(20)',
        'range': (0, 200),
        'better': 'higher',
        'unit': 'steps',
        'format': '.0f',
    },
    'CER': {
        'full_name': 'CER',
        'ylabel': 'CER',
        'equation': 'Eq.(22)',
        'range': (0, None),
        'better': 'higher',
        'unit': '',
        'format': '.2f',
    },
    'CDI': {
        'full_name': 'CDI',
        'ylabel': 'CDI',
        'equation': 'Eq.(18)',
        'range': (0, 1),
        'better': 'higher',
        'unit': '',
        'format': '.3f',
    },
    'Cost': {
        'full_name': 'Total Cost',
        'ylabel': 'Total Cost',
        'equation': 'Eq.(7)',
        'range': (0, None),
        'better': 'lower',
        'unit': '',
        'format': '.2f',
    },
}


def get_timestamp() -> str:
    """파일명용 타임스탬프"""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


# =============================================================================
# IEEE Figure Generator
# =============================================================================
class IEEEFigureGenerator:
    """IEEE Access 품질 그래프 생성기 v10.1"""
    
    def __init__(self, output_dir: str = "paper_figures"):
        self.output_dir = Path(output_dir)
        self.timestamp = get_timestamp()
        
        # 폴더 구조 생성
        self.dirs = {
            'main': self.output_dir / self.timestamp,
            'individual': self.output_dir / self.timestamp / 'individual',
            'by_metric': self.output_dir / self.timestamp / 'by_metric',
            'by_level': self.output_dir / self.timestamp / 'by_level',
            'comparison': self.output_dir / self.timestamp / 'comparison',
            'horizontal': self.output_dir / self.timestamp / 'horizontal',
            'tables': self.output_dir / self.timestamp / 'tables',
        }
        for d in self.dirs.values():
            d.mkdir(parents=True, exist_ok=True)
        
        setup_ieee_style()
        print(f"📁 Output directory: {self.dirs['main']}")
    
    def _save_figure(self, fig, name: str, subdir: str = 'main'):
        """그래프 저장 (PDF + PNG)"""
        base_path = self.dirs.get(subdir, self.dirs['main']) / name
        fig.savefig(f"{base_path}.pdf", format='pdf', bbox_inches='tight')
        fig.savefig(f"{base_path}.png", format='png', dpi=300, bbox_inches='tight')
        plt.close(fig)
        print(f"  ✅ {name}")
    
    def _get_value_format(self, metric: str, value: float) -> str:
        """지표별 값 포맷팅"""
        fmt = METRICS.get(metric, {}).get('format', '.2f')
        unit = METRICS.get(metric, {}).get('unit', '')
        
        if metric == 'BR':
            return f'{value:{fmt}}{unit}'
        elif metric in ['DES', 'CDI']:
            return f'{value:{fmt}}'
        elif metric == 'MTTC':
            return f'{value:{fmt}}'
        else:
            return f'{value:{fmt}}'
    
    # =========================================================================
    # 개별 지표 그래프 (단일 파일)
    # =========================================================================
    def plot_single_metric_by_level(
        self,
        results: Dict[str, Dict[int, Dict]],
        metric: str,
    ):
        """단일 지표의 레벨별 비교 - 개별 파일"""
        setup_ieee_style()
        
        strategies = [s for s in STRATEGIES.keys() if s in results]
        levels = sorted(set(l for s in results.values() for l in s.keys()))
        
        metric_info = METRICS.get(metric, {'ylabel': metric, 'range': (None, None), 'better': 'higher'})
        
        fig, ax = plt.subplots(figsize=(8, 4.5))
        
        x = np.arange(len(levels))
        n_strategies = len(strategies)
        width = 0.8 / n_strategies
        
        for i, strategy in enumerate(strategies):
            values = []
            stds = []
            for level in levels:
                data = results[strategy].get(level, {})
                val = data.get(metric.lower(), data.get(metric, 0))
                std = data.get(f'{metric.lower()}_std', 0)
                values.append(val)
                stds.append(std)
            
            offset = (i - n_strategies/2 + 0.5) * width
            color = STRATEGIES[strategy]['color']
            hatch = STRATEGIES[strategy]['hatch']
            
            bars = ax.bar(
                x + offset, values, width,
                label=strategy,
                color=color,
                edgecolor='black',
                linewidth=0.6,
                hatch=hatch,
                yerr=stds if any(s > 0 for s in stds) else None,
                capsize=2,
                error_kw={'linewidth': 0.8}
            )
            
            # 값 라벨 (겹침 방지)
            for j, (bar, val) in enumerate(zip(bars, values)):
                text = self._get_value_format(metric, val)
                y_pos = bar.get_height() + (stds[j] if stds[j] > 0 else 0)
                
                # 높이에 따라 오프셋 조정
                max_val = max(values) if values else 1
                y_offset = max_val * 0.02
                
                ax.text(
                    bar.get_x() + bar.get_width()/2,
                    y_pos + y_offset,
                    text,
                    ha='center',
                    va='bottom',
                    fontsize=7,
                    rotation=45 if n_strategies > 3 else 0,
                )
        
        # L3, L4에서 RL-CTI MTD 강조 박스
        if 'RL-CTI MTD' in strategies:
            rl_idx = strategies.index('RL-CTI MTD')
            for level_idx in [3, 4]:
                if level_idx < len(levels):
                    x_pos = level_idx + (rl_idx - n_strategies/2 + 0.5) * width
                    val = results['RL-CTI MTD'].get(levels[level_idx], {}).get(metric.lower(), 0)
                    
                    rect = FancyBboxPatch(
                        (x_pos - width/2 - 0.02, 0),
                        width + 0.04,
                        val * 1.02,
                        boxstyle="round,pad=0.02",
                        facecolor='none',
                        edgecolor='#D55E00',
                        linewidth=2.5,
                    )
                    ax.add_patch(rect)
        
        ax.set_xlabel('Attacker Level', fontweight='bold')
        ax.set_ylabel(metric_info['ylabel'], fontweight='bold')
        ax.set_title(f"{metric_info['full_name']} by Attacker Level", fontweight='bold', pad=10)
        
        ax.set_xticks(x)
        ax.set_xticklabels([f'L{l}\n({ATTACKER_PROFILES[l]["name"]})' for l in levels], fontsize=9)
        
        if metric_info['range'][0] is not None:
            ax.set_ylim(bottom=metric_info['range'][0])
        if metric_info['range'][1] is not None:
            ax.set_ylim(top=metric_info['range'][1] * 1.2)
        
        ax.legend(loc='best', fontsize=9)
        ax.grid(axis='y', alpha=0.3)
        
        plt.tight_layout()
        self._save_figure(fig, f'{metric.lower()}_by_level', 'individual')
    
    def plot_single_level_metrics(
        self,
        results: Dict[str, Dict[int, Dict]],
        level: int,
    ):
        """단일 레벨의 모든 지표 - 1×6 가로 배열"""
        setup_ieee_style()
        
        strategies = [s for s in STRATEGIES.keys() if s in results]
        metrics_to_plot = ['DES', 'BR', 'MTTC', 'CER', 'CDI', 'Cost']
        
        level_name = ATTACKER_PROFILES[level]['name']
        
        fig, axes = plt.subplots(1, 6, figsize=(18, 3.5))
        
        for idx, metric in enumerate(metrics_to_plot):
            ax = axes[idx]
            metric_info = METRICS.get(metric, {'ylabel': metric, 'range': (None, None), 'better': 'higher'})
            
            values = []
            colors = []
            for strategy in strategies:
                data = results[strategy].get(level, {})
                val = data.get(metric.lower(), data.get(metric, 0))
                values.append(val)
                colors.append(STRATEGIES[strategy]['color'])
            
            x = np.arange(len(strategies))
            bars = ax.bar(x, values, color=colors, edgecolor='black', linewidth=0.6)
            
            # 최고 성능 강조
            if metric_info['better'] == 'higher':
                best_idx = np.argmax(values)
            else:
                best_idx = np.argmin(values)
            
            bars[best_idx].set_edgecolor('#D55E00')
            bars[best_idx].set_linewidth(2.5)
            
            # 값 라벨
            for i, (bar, val) in enumerate(zip(bars, values)):
                text = self._get_value_format(metric, val)
                ax.text(
                    bar.get_x() + bar.get_width()/2,
                    bar.get_height() + max(values) * 0.02,
                    text,
                    ha='center',
                    va='bottom',
                    fontsize=8,
                    fontweight='bold' if i == best_idx else 'normal',
                    color='#D55E00' if i == best_idx else 'black',
                )
            
            ax.set_ylabel(metric_info['ylabel'], fontsize=9)
            ax.set_title(f'({chr(97+idx)}) {metric}', fontweight='bold')
            ax.set_xticks(x)
            ax.set_xticklabels([s.replace(' MTD', '').replace('+CTI', '\n+CTI') for s in strategies], 
                             fontsize=8)
            
            if metric_info['range'][0] is not None:
                ax.set_ylim(bottom=metric_info['range'][0])
            if metric_info['range'][1] is not None:
                ax.set_ylim(top=metric_info['range'][1] * 1.15)
        
        fig.suptitle(f'Level {level} ({level_name}) - All Metrics', 
                    fontweight='bold', fontsize=14, y=1.02)
        
        plt.tight_layout()
        self._save_figure(fig, f'level_{level}_horizontal', 'horizontal')
    
    # =========================================================================
    # 종합 비교 - 1×6 가로 배열
    # =========================================================================
    def plot_overall_horizontal(
        self,
        results: Dict[str, Dict[int, Dict]],
    ):
        """전체 전략 종합 비교 - 1×6 가로 배열"""
        setup_ieee_style()
        
        strategies = [s for s in STRATEGIES.keys() if s in results]
        levels = sorted(set(l for s in results.values() for l in s.keys()))
        
        # 평균 계산
        avg_results = {}
        for strategy in strategies:
            avg_results[strategy] = {}
            for metric in ['DES', 'BR', 'MTTC', 'CER', 'CDI', 'Cost']:
                key = metric.lower()
                values = [results[strategy].get(l, {}).get(key, 
                         results[strategy].get(l, {}).get(metric, 0)) for l in levels]
                avg_results[strategy][key] = np.mean(values)
                avg_results[strategy][f'{key}_std'] = np.std(values)
        
        metrics_to_plot = [
            ('DES', r'$S_{\mathrm{MTD}}$'),
            ('BR', 'Breach Rate (%)'),
            ('MTTC', 'MTTC (steps)'),
            ('CER', 'CER'),
            ('CDI', 'CDI'),
            ('Cost', 'Total Cost'),
        ]
        
        fig, axes = plt.subplots(1, 6, figsize=(18, 3.5))
        
        for idx, (metric, ylabel) in enumerate(metrics_to_plot):
            ax = axes[idx]
            metric_info = METRICS.get(metric, {'better': 'higher'})
            
            key = metric.lower()
            values = [avg_results[s].get(key, 0) for s in strategies]
            stds = [avg_results[s].get(f'{key}_std', 0) for s in strategies]
            colors = [STRATEGIES[s]['color'] for s in strategies]
            
            x = np.arange(len(strategies))
            bars = ax.bar(x, values, color=colors, edgecolor='black', linewidth=0.6,
                         yerr=stds, capsize=3, error_kw={'linewidth': 1})
            
            # 최고 성능 강조
            if metric_info['better'] == 'higher':
                best_idx = np.argmax(values)
            else:
                best_idx = np.argmin(values)
            
            bars[best_idx].set_edgecolor('#D55E00')
            bars[best_idx].set_linewidth(2.5)
            
            # 값 라벨
            for i, (bar, val, std) in enumerate(zip(bars, values, stds)):
                text = self._get_value_format(metric, val)
                y_pos = bar.get_height() + std + max(values) * 0.02
                ax.text(
                    bar.get_x() + bar.get_width()/2,
                    y_pos,
                    text,
                    ha='center',
                    va='bottom',
                    fontsize=8,
                    fontweight='bold' if i == best_idx else 'normal',
                    color='#D55E00' if i == best_idx else 'black',
                )
            
            ax.set_ylabel(ylabel, fontweight='bold', fontsize=9)
            ax.set_title(f'({chr(97+idx)}) {metric}', fontweight='bold')
            ax.set_xticks(x)
            ax.set_xticklabels([s.replace(' MTD', '').replace('+CTI', '\n+CTI') for s in strategies],
                             fontsize=8)
            ax.grid(axis='y', alpha=0.3)
            
            if METRICS.get(metric, {}).get('range', (None, None))[1]:
                ax.set_ylim(top=METRICS[metric]['range'][1] * 1.25)
        
        fig.suptitle('Overall Strategy Comparison (Average Across All Levels)',
                    fontweight='bold', fontsize=14, y=1.02)
        
        plt.tight_layout()
        self._save_figure(fig, 'overall_horizontal', 'horizontal')
    
    # =========================================================================
    # 히트맵
    # =========================================================================
    def plot_des_heatmap(
        self,
        results: Dict[str, Dict[int, Dict]],
    ):
        """DES 히트맵"""
        setup_ieee_style()
        
        strategies = [s for s in STRATEGIES.keys() if s in results]
        levels = sorted(set(l for s in results.values() for l in s.keys()))
        
        data = []
        for strategy in strategies:
            row = [results[strategy].get(l, {}).get('des', 
                  results[strategy].get(l, {}).get('DES', 0)) for l in levels]
            row.append(np.mean(row))
            data.append(row)
        
        data = np.array(data)
        
        fig, ax = plt.subplots(figsize=(8, 4))
        
        cmap = LinearSegmentedColormap.from_list(
            'des_cmap',
            ['#FEE0D2', '#FC9272', '#DE2D26', '#67000D']
        )
        
        im = ax.imshow(data, cmap=cmap, aspect='auto', vmin=0, vmax=1)
        
        col_labels = [f'L{l}' for l in levels] + ['Avg']
        row_labels = [s.replace(' MTD', '') for s in strategies]
        
        ax.set_xticks(np.arange(len(col_labels)))
        ax.set_xticklabels(col_labels, fontweight='bold')
        ax.set_yticks(np.arange(len(strategies)))
        ax.set_yticklabels(row_labels, fontweight='bold')
        
        for i in range(len(strategies)):
            for j in range(len(col_labels)):
                color = 'white' if data[i, j] > 0.5 else 'black'
                weight = 'bold' if data[i, j] == data[:, j].max() else 'normal'
                ax.text(j, i, f'{data[i, j]:.3f}', ha='center', va='center',
                       fontsize=10, color=color, fontweight=weight)
        
        if 'RL-CTI MTD' in strategies:
            best_idx = strategies.index('RL-CTI MTD')
            rect = mpatches.Rectangle(
                (-0.5, best_idx - 0.5), len(col_labels), 1,
                fill=False, edgecolor='#D55E00', linewidth=3
            )
            ax.add_patch(rect)
        
        ax.set_xlabel('Attacker Level', fontweight='bold')
        ax.set_title(r'$S_{\mathrm{MTD}}$ (DES) Heatmap', fontweight='bold', pad=10)
        
        cbar = plt.colorbar(im, ax=ax, shrink=0.8, pad=0.02)
        cbar.set_label(r'$S_{\mathrm{MTD}}$', fontweight='bold')
        
        plt.tight_layout()
        self._save_figure(fig, 'des_heatmap', 'comparison')
    
    def plot_br_heatmap(
        self,
        results: Dict[str, Dict[int, Dict]],
    ):
        """Breach Rate 히트맵"""
        setup_ieee_style()
        
        strategies = [s for s in STRATEGIES.keys() if s in results]
        levels = sorted(set(l for s in results.values() for l in s.keys()))
        
        data = []
        for strategy in strategies:
            row = [results[strategy].get(l, {}).get('br', 
                  results[strategy].get(l, {}).get('breach_rate', 0)) for l in levels]
            row.append(np.mean(row))
            data.append(row)
        
        data = np.array(data)
        
        fig, ax = plt.subplots(figsize=(8, 4))
        
        cmap = LinearSegmentedColormap.from_list(
            'br_cmap',
            ['#006D2C', '#74C476', '#FEE08B', '#F46D43', '#A50026']
        )
        
        im = ax.imshow(data, cmap=cmap, aspect='auto', vmin=0, vmax=100)
        
        col_labels = [f'L{l}' for l in levels] + ['Avg']
        row_labels = [s.replace(' MTD', '') for s in strategies]
        
        ax.set_xticks(np.arange(len(col_labels)))
        ax.set_xticklabels(col_labels, fontweight='bold')
        ax.set_yticks(np.arange(len(strategies)))
        ax.set_yticklabels(row_labels, fontweight='bold')
        
        for i in range(len(strategies)):
            for j in range(len(col_labels)):
                color = 'white' if data[i, j] > 50 else 'black'
                weight = 'bold' if data[i, j] == data[:, j].min() else 'normal'
                ax.text(j, i, f'{data[i, j]:.1f}%', ha='center', va='center',
                       fontsize=10, color=color, fontweight=weight)
        
        if 'RL-CTI MTD' in strategies:
            best_idx = strategies.index('RL-CTI MTD')
            rect = mpatches.Rectangle(
                (-0.5, best_idx - 0.5), len(col_labels), 1,
                fill=False, edgecolor='#006D2C', linewidth=3
            )
            ax.add_patch(rect)
        
        ax.set_xlabel('Attacker Level', fontweight='bold')
        ax.set_title('Breach Rate (%) Heatmap', fontweight='bold', pad=10)
        
        cbar = plt.colorbar(im, ax=ax, shrink=0.8, pad=0.02)
        cbar.set_label('Breach Rate (%)', fontweight='bold')
        
        plt.tight_layout()
        self._save_figure(fig, 'br_heatmap', 'comparison')
    
    # =========================================================================
    # Trade-off 분석
    # =========================================================================
    def plot_tradeoff_scatter(
        self,
        results: Dict[str, Dict[int, Dict]],
    ):
        """Trade-off 분석 산점도 - 1×3 가로"""
        setup_ieee_style()
        
        strategies = [s for s in STRATEGIES.keys() if s in results]
        levels = sorted(set(l for s in results.values() for l in s.keys()))
        
        fig, axes = plt.subplots(1, 3, figsize=(14, 4))
        
        # (a) Cost vs DES
        ax = axes[0]
        for strategy in strategies:
            costs = [results[strategy].get(l, {}).get('cost', 0) for l in levels]
            dess = [results[strategy].get(l, {}).get('des', 0) for l in levels]
            
            ax.scatter(
                costs, dess,
                s=120,
                c=STRATEGIES[strategy]['color'],
                marker=STRATEGIES[strategy]['marker'],
                label=strategy.replace(' MTD', ''),
                edgecolors='black',
                linewidth=0.5,
                alpha=0.8,
            )
        
        ax.set_xlabel('Total Cost', fontweight='bold')
        ax.set_ylabel(r'$S_{\mathrm{MTD}}$', fontweight='bold')
        ax.set_title('(a) Cost vs Defense Effectiveness', fontweight='bold')
        ax.legend(loc='lower right', fontsize=8)
        ax.set_ylim(0, 1.05)
        ax.grid(alpha=0.3)
        
        # (b) MTTC vs CER
        ax = axes[1]
        for strategy in strategies:
            mttcs = [results[strategy].get(l, {}).get('mttc', 0) for l in levels]
            cers = [results[strategy].get(l, {}).get('cer', 0) for l in levels]
            
            ax.scatter(
                mttcs, cers,
                s=120,
                c=STRATEGIES[strategy]['color'],
                marker=STRATEGIES[strategy]['marker'],
                label=strategy.replace(' MTD', ''),
                edgecolors='black',
                linewidth=0.5,
                alpha=0.8,
            )
        
        ax.set_xlabel('MTTC (steps)', fontweight='bold')
        ax.set_ylabel('CER', fontweight='bold')
        ax.set_title('(b) MTTC vs Cost Efficiency', fontweight='bold')
        ax.legend(loc='upper right', fontsize=8)
        ax.grid(alpha=0.3)
        
        # (c) BR vs Cost
        ax = axes[2]
        for strategy in strategies:
            brs = [results[strategy].get(l, {}).get('br', 
                  results[strategy].get(l, {}).get('breach_rate', 0)) for l in levels]
            costs = [results[strategy].get(l, {}).get('cost', 0) for l in levels]
            
            ax.scatter(
                costs, brs,
                s=120,
                c=STRATEGIES[strategy]['color'],
                marker=STRATEGIES[strategy]['marker'],
                label=strategy.replace(' MTD', ''),
                edgecolors='black',
                linewidth=0.5,
                alpha=0.8,
            )
        
        ax.set_xlabel('Total Cost', fontweight='bold')
        ax.set_ylabel('Breach Rate (%)', fontweight='bold')
        ax.set_title('(c) Cost vs Breach Rate', fontweight='bold')
        ax.legend(loc='upper right', fontsize=8)
        ax.set_ylim(0, 100)
        ax.grid(alpha=0.3)
        
        plt.tight_layout()
        self._save_figure(fig, 'tradeoff_scatter', 'comparison')
    
    # =========================================================================
    # 개선 요약
    # =========================================================================
    def plot_improvement_summary(
        self,
        results: Dict[str, Dict[int, Dict]],
    ):
        """개선 요약 그래프"""
        setup_ieee_style()
        
        strategies = [s for s in STRATEGIES.keys() if s in results and s != 'Baseline']
        levels = sorted(set(l for s in results.values() for l in s.keys()))
        
        if 'Baseline' not in results:
            print("  ⚠️ Baseline not found, skipping improvement summary")
            return
        
        fig, ax = plt.subplots(figsize=(10, 5))
        
        x = np.arange(len(strategies))
        width = 0.35
        
        des_improvements = []
        br_reductions = []
        
        for strategy in strategies:
            bl_des = np.mean([results['Baseline'].get(l, {}).get('des', 0) for l in levels])
            st_des = np.mean([results[strategy].get(l, {}).get('des', 0) for l in levels])
            des_imp = (st_des - bl_des) / max(bl_des, 0.01) * 100
            des_improvements.append(des_imp)
            
            bl_br = np.mean([results['Baseline'].get(l, {}).get('br', 
                           results['Baseline'].get(l, {}).get('breach_rate', 0)) for l in levels])
            st_br = np.mean([results[strategy].get(l, {}).get('br',
                           results[strategy].get(l, {}).get('breach_rate', 0)) for l in levels])
            br_red = bl_br - st_br
            br_reductions.append(br_red)
        
        colors = [STRATEGIES[s]['color'] for s in strategies]
        
        bars1 = ax.bar(x - width/2, des_improvements, width, label=r'$S_{\mathrm{MTD}}$ Improvement (%)',
                      color=colors, edgecolor='black', linewidth=0.6, alpha=0.9)
        bars2 = ax.bar(x + width/2, br_reductions, width, label='BR Reduction (pp)',
                      color=colors, edgecolor='black', linewidth=0.6, alpha=0.5, hatch='///')
        
        for i, (bar1, bar2, des, br) in enumerate(zip(bars1, bars2, des_improvements, br_reductions)):
            ax.text(bar1.get_x() + bar1.get_width()/2, bar1.get_height() + 2,
                   f'+{des:.0f}%', ha='center', fontsize=9, fontweight='bold')
            ax.text(bar2.get_x() + bar2.get_width()/2, bar2.get_height() + 2,
                   f'-{br:.0f}pp', ha='center', fontsize=9)
        
        if 'RL-CTI MTD' in strategies:
            rl_idx = strategies.index('RL-CTI MTD')
            bars1[rl_idx].set_edgecolor('#D55E00')
            bars1[rl_idx].set_linewidth(3)
            bars2[rl_idx].set_edgecolor('#D55E00')
            bars2[rl_idx].set_linewidth(3)
        
        ax.axhline(y=0, color='black', linewidth=0.5)
        ax.set_ylabel('Improvement vs Baseline', fontweight='bold')
        ax.set_title('Performance Improvement vs Baseline (No MTD)', fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels([s.replace(' MTD', '') for s in strategies], fontweight='bold')
        ax.legend(loc='upper left', fontsize=9)
        ax.grid(axis='y', alpha=0.3)
        
        plt.tight_layout()
        self._save_figure(fig, 'improvement_summary', 'comparison')
    
    # =========================================================================
    # LaTeX 테이블 생성
    # =========================================================================
    def generate_latex_tables(
        self,
        results: Dict[str, Dict[int, Dict]],
    ):
        """모든 LaTeX 테이블 생성"""
        strategies = [s for s in STRATEGIES.keys() if s in results]
        levels = sorted(set(l for s in results.values() for l in s.keys()))
        
        self._generate_overall_table(results, strategies, levels)
        self._generate_level_table(results, strategies, levels)
        self._generate_improvement_table(results, strategies, levels)
    
    def _generate_overall_table(self, results, strategies, levels):
        """전체 성능 테이블"""
        table = r"""\begin{table}[!t]
\centering
\caption{Overall Defense Performance Comparison (Average across all levels)}
\label{tab:overall_performance}
\renewcommand{\arraystretch}{1.1}
\begin{tabular}{@{}lcccccc@{}}
\toprule
\textbf{Strategy} & $S_{\mathrm{MTD}}$ & \textbf{BR(\%)} & \textbf{MTTC} & \textbf{CER} & \textbf{CDI} & \textbf{Cost} \\
\midrule
"""
        
        avg_data = {}
        for s in strategies:
            avg_data[s] = {
                'des': np.mean([results[s].get(l, {}).get('des', 0) for l in levels]),
                'br': np.mean([results[s].get(l, {}).get('br', results[s].get(l, {}).get('breach_rate', 0)) for l in levels]),
                'mttc': np.mean([results[s].get(l, {}).get('mttc', 0) for l in levels]),
                'cer': np.mean([results[s].get(l, {}).get('cer', 0) for l in levels]),
                'cdi': np.mean([results[s].get(l, {}).get('cdi', 0) for l in levels]),
                'cost': np.mean([results[s].get(l, {}).get('cost', 0) for l in levels]),
            }
        
        best = {
            'des': max(avg_data[s]['des'] for s in strategies),
            'br': min(avg_data[s]['br'] for s in strategies),
            'mttc': max(avg_data[s]['mttc'] for s in strategies),
            'cer': max(avg_data[s]['cer'] for s in strategies),
            'cdi': max(avg_data[s]['cdi'] for s in strategies),
            'cost': min(avg_data[s]['cost'] for s in strategies if avg_data[s]['cost'] > 0) if any(avg_data[s]['cost'] > 0 for s in strategies) else 0,
        }
        
        for s in strategies:
            d = avg_data[s]
            
            def fmt(val, key, decimals=3):
                if key == 'br':
                    text = f'{val:.1f}'
                elif key == 'mttc':
                    text = f'{val:.0f}'
                else:
                    text = f'{val:.{decimals}f}'
                
                is_best = (key in ['br', 'cost'] and val == best[key]) or \
                         (key not in ['br', 'cost'] and val == best[key])
                return f'\\textbf{{{text}}}' if is_best else text
            
            table += f"{STRATEGIES[s]['full_name']} & {fmt(d['des'], 'des')} & {fmt(d['br'], 'br')} & "
            table += f"{fmt(d['mttc'], 'mttc')} & {fmt(d['cer'], 'cer', 2)} & {fmt(d['cdi'], 'cdi')} & {fmt(d['cost'], 'cost', 2)} \\\\\n"
        
        table += r"""\bottomrule
\end{tabular}
\end{table}
"""
        
        path = self.dirs['tables'] / 'table_overall.tex'
        with open(path, 'w') as f:
            f.write(table)
        print(f"  ✅ table_overall.tex")
    
    def _generate_level_table(self, results, strategies, levels):
        """레벨별 DES 테이블"""
        table = r"""\begin{table*}[!t]
\centering
\caption{Defense Effectiveness Score ($S_{\mathrm{MTD}}$) by Attacker Level}
\label{tab:level_performance}
\renewcommand{\arraystretch}{1.1}
\begin{tabular}{@{}l""" + 'c' * len(levels) + r"""c@{}}
\toprule
\textbf{Strategy} & """ + ' & '.join([f'\\textbf{{L{l}}}' for l in levels]) + r""" & \textbf{Avg} \\
\midrule
"""
        
        for s in strategies:
            values = [results[s].get(l, {}).get('des', 0) for l in levels]
            avg = np.mean(values)
            
            row = f"{STRATEGIES[s]['full_name']}"
            for v in values:
                row += f" & {v:.3f}"
            row += f" & {avg:.3f} \\\\\n"
            table += row
        
        table += r"""\bottomrule
\end{tabular}
\end{table*}
"""
        
        path = self.dirs['tables'] / 'table_level_des.tex'
        with open(path, 'w') as f:
            f.write(table)
        print(f"  ✅ table_level_des.tex")
    
    def _generate_improvement_table(self, results, strategies, levels):
        """개선 요약 테이블"""
        if 'Baseline' not in results or 'RL-CTI MTD' not in results:
            return
        
        table = r"""\begin{table}[!t]
\centering
\caption{Performance Improvement of RL-CTI MTD vs Other Strategies}
\label{tab:improvement}
\renewcommand{\arraystretch}{1.1}
\begin{tabular}{@{}lccc@{}}
\toprule
\textbf{Comparison} & $\Delta S_{\mathrm{MTD}}$ & $\Delta$\textbf{BR (pp)} & \textbf{CER Ratio} \\
\midrule
"""
        
        rl_cti = {
            'des': np.mean([results['RL-CTI MTD'].get(l, {}).get('des', 0) for l in levels]),
            'br': np.mean([results['RL-CTI MTD'].get(l, {}).get('br', results['RL-CTI MTD'].get(l, {}).get('breach_rate', 0)) for l in levels]),
            'cer': np.mean([results['RL-CTI MTD'].get(l, {}).get('cer', 0) for l in levels]),
        }
        
        for s in strategies:
            if s == 'RL-CTI MTD':
                continue
            
            other = {
                'des': np.mean([results[s].get(l, {}).get('des', 0) for l in levels]),
                'br': np.mean([results[s].get(l, {}).get('br', results[s].get(l, {}).get('breach_rate', 0)) for l in levels]),
                'cer': np.mean([results[s].get(l, {}).get('cer', 0) for l in levels]),
            }
            
            delta_des = rl_cti['des'] - other['des']
            delta_br = other['br'] - rl_cti['br']
            cer_ratio = rl_cti['cer'] / max(other['cer'], 0.01)
            
            table += f"vs {s} & +{delta_des:.3f} & -{delta_br:.1f} & {cer_ratio:.2f}$\\times$ \\\\\n"
        
        table += r"""\bottomrule
\end{tabular}
\end{table}
"""
        
        path = self.dirs['tables'] / 'table_improvement.tex'
        with open(path, 'w') as f:
            f.write(table)
        print(f"  ✅ table_improvement.tex")
    
    # =========================================================================
    # 전체 생성
    # =========================================================================
    def generate_all(
        self,
        results: Dict[str, Dict[int, Dict]],
    ):
        """모든 그래프 및 테이블 생성"""
        print("\n" + "="*60)
        print("IEEE Access Figure & Table Generation v10.1")
        print("="*60)
        
        levels = sorted(set(l for s in results.values() for l in s.keys()))
        
        # 1. 개별 지표 그래프 (단일 파일)
        print("\n[1] Individual metric plots...")
        for metric in ['DES', 'BR', 'MTTC', 'CER', 'CDI', 'Cost']:
            self.plot_single_metric_by_level(results, metric)
        
        # 2. 레벨별 1×6 가로 배열
        print("\n[2] Level-specific horizontal plots...")
        for level in levels:
            self.plot_single_level_metrics(results, level)
        
        # 3. 종합 비교 1×6 가로
        print("\n[3] Overall comparison (horizontal)...")
        self.plot_overall_horizontal(results)
        
        # 4. 히트맵
        print("\n[4] Heatmaps...")
        self.plot_des_heatmap(results)
        self.plot_br_heatmap(results)
        
        # 5. Trade-off
        print("\n[5] Trade-off analysis...")
        self.plot_tradeoff_scatter(results)
        self.plot_improvement_summary(results)
        
        # 6. LaTeX 테이블
        print("\n[6] LaTeX tables...")
        self.generate_latex_tables(results)
        
        print("\n" + "="*60)
        print(f"✅ All outputs saved to: {self.dirs['main']}")
        print("="*60)


# =============================================================================
# Main Test
# =============================================================================
if __name__ == "__main__":
    print("IEEE Figure Utilities v10.1 - Fixed CDI + Layout")
    
    # 테스트 데이터 (CDI 수정됨 - 전략별로 다른 값)
    test_results = {
        'Baseline': {
            0: {'des': 0.809, 'br': 8.0, 'mttc': 190, 'cer': 8.09, 'cdi': 0.10, 'cost': 0.0},
            1: {'des': 0.777, 'br': 12.0, 'mttc': 185, 'cer': 7.77, 'cdi': 0.10, 'cost': 0.0},
            2: {'des': 0.677, 'br': 32.0, 'mttc': 151, 'cer': 6.77, 'cdi': 0.10, 'cost': 0.0},
            3: {'des': 0.620, 'br': 50.0, 'mttc': 117, 'cer': 6.20, 'cdi': 0.10, 'cost': 0.0},
            4: {'des': 0.580, 'br': 62.0, 'mttc': 93, 'cer': 5.80, 'cdi': 0.10, 'cost': 0.0},
        },
        'Static MTD': {
            0: {'des': 0.784, 'br': 10.0, 'mttc': 187, 'cer': 2.64, 'cdi': 0.35, 'cost': 0.25},
            1: {'des': 0.727, 'br': 26.0, 'mttc': 170, 'cer': 2.45, 'cdi': 0.35, 'cost': 0.25},
            2: {'des': 0.646, 'br': 48.0, 'mttc': 141, 'cer': 2.17, 'cdi': 0.35, 'cost': 0.25},
            3: {'des': 0.618, 'br': 42.0, 'mttc': 133, 'cer': 2.08, 'cdi': 0.35, 'cost': 0.28},
            4: {'des': 0.580, 'br': 56.0, 'mttc': 112, 'cer': 1.82, 'cdi': 0.35, 'cost': 0.28},
        },
        'Heuristic+CTI': {
            0: {'des': 0.839, 'br': 4.0, 'mttc': 195, 'cer': 6.60, 'cdi': 0.55, 'cost': 0.43},
            1: {'des': 0.816, 'br': 10.0, 'mttc': 191, 'cer': 5.31, 'cdi': 0.55, 'cost': 1.26},
            2: {'des': 0.753, 'br': 26.0, 'mttc': 165, 'cer': 1.94, 'cdi': 0.55, 'cost': 3.44},
            3: {'des': 0.775, 'br': 16.0, 'mttc': 178, 'cer': 2.40, 'cdi': 0.55, 'cost': 3.21},
            4: {'des': 0.742, 'br': 30.0, 'mttc': 167, 'cer': 1.30, 'cdi': 0.55, 'cost': 6.19},
        },
        'RL-CTI MTD': {
            0: {'des': 0.927, 'br': 0.0, 'mttc': 200, 'cer': 0.14, 'cdi': 0.85, 'cost': 9.68},
            1: {'des': 0.919, 'br': 0.0, 'mttc': 200, 'cer': 0.10, 'cdi': 0.85, 'cost': 12.35},
            2: {'des': 0.905, 'br': 0.0, 'mttc': 200, 'cer': 0.08, 'cdi': 0.85, 'cost': 14.21},
            3: {'des': 0.841, 'br': 4.0, 'mttc': 198, 'cer': 0.06, 'cdi': 0.85, 'cost': 15.87},
            4: {'des': 0.801, 'br': 10.0, 'mttc': 195, 'cer': 0.06, 'cdi': 0.85, 'cost': 16.41},
        },
    }
    
    generator = IEEEFigureGenerator(output_dir='test_ieee_figures_v101')
    generator.generate_all(test_results)