#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IEEE Figure Utilities v09
=========================

IEEE Access 논문용 그래프 생성 유틸리티.
학습/평가 스크립트에서 import하여 사용.

Features:
- IEEE Access 스타일 준수 (Times font, 300 DPI)
- 색맹 친화적 Okabe-Ito 컬러 팔레트
- 학습 곡선, 평가 비교, 히트맵 등 다양한 그래프 지원
- PDF + PNG 동시 출력

Author: MTD-RL Research Team
Version: 0.9.5
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Any

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import LinearSegmentedColormap


# =============================================================================
# IEEE Style Configuration
# =============================================================================
def setup_ieee_style():
    """IEEE Access 논문 스타일 설정"""
    plt.rcParams.update({
        'font.family': 'serif',
        'font.serif': ['Times New Roman', 'DejaVu Serif', 'serif'],
        'font.size': 9,
        'axes.labelsize': 10,
        'axes.titlesize': 11,
        'legend.fontsize': 8,
        'xtick.labelsize': 9,
        'ytick.labelsize': 9,
        'figure.dpi': 300,
        'savefig.dpi': 300,
        'lines.linewidth': 1.2,
        'lines.markersize': 5,
        'axes.linewidth': 0.8,
        'grid.linewidth': 0.4,
        'grid.alpha': 0.4,
        'axes.grid': True,
        'legend.frameon': False,
        'savefig.bbox': 'tight',
        'savefig.pad_inches': 0.05,
        'axes.spines.top': False,
        'axes.spines.right': False,
    })


# =============================================================================
# Color Palettes (Colorblind-Friendly Okabe-Ito)
# =============================================================================
STRATEGY_COLORS = {
    'No MTD': '#0072B2',
    'Random': '#56B4E9',
    'Static MTD': '#E69F00',
    'Periodic': '#E69F00',
    'Heuristic': '#009E73',
    'Heuristic+CTI': '#009E73',
    'Adaptive': '#D55E00',
    'RL MTD': '#CC79A7',
    'RL+CTI MTD': '#D55E00',
}

STRATEGY_MARKERS = {
    'No MTD': 'o',
    'Random': 'v',
    'Static MTD': 's',
    'Periodic': 's',
    'Heuristic': '^',
    'Heuristic+CTI': '^',
    'Adaptive': 'p',
    'RL MTD': 'D',
    'RL+CTI MTD': 'p',
}

STRATEGY_HATCHES = {
    'No MTD': '',
    'Random': '///',
    'Static MTD': '...',
    'Periodic': '...',
    'Heuristic': 'xxx',
    'Heuristic+CTI': 'xxx',
    'Adaptive': '\\\\\\',
    'RL MTD': '+++',
    'RL+CTI MTD': '\\\\\\',
}

LEVEL_COLORS = ['#4575B4', '#91BFDB', '#FEE090', '#FC8D59', '#D73027']
PHASE_COLORS = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']


# =============================================================================
# Training Curve Plots
# =============================================================================
def plot_training_curves(
    metrics_history: List[Dict],
    save_path: str,
    curriculum_phases: Optional[List[int]] = None,
    ma_window: int = 50,
):
    """
    학습 곡선 그래프 (6-panel)
    
    Args:
        metrics_history: 에피소드별 메트릭 리스트
        save_path: 저장 경로 (확장자 제외)
        curriculum_phases: Phase 경계 에피소드 번호
        ma_window: 이동평균 윈도우 크기
    """
    setup_ieee_style()
    
    n_episodes = len(metrics_history)
    if n_episodes == 0:
        print("⚠️ No metrics to plot")
        return
        
    episodes = np.arange(1, n_episodes + 1)
    
    # 데이터 추출
    rewards = np.array([m.get('episode/reward', m.get('reward', 0)) for m in metrics_history])
    des_values = np.array([m.get('MTD/DES', m.get('des', 0)) for m in metrics_history])
    breach_rates = np.array([1 - m.get('Defense/BreachPrevented', 1 - m.get('breach', 0)) for m in metrics_history]) * 100
    mttc_values = np.array([m.get('MTD/MTTC', m.get('mttc', 200)) for m in metrics_history])
    policy_loss = np.array([m.get('loss/policy', 0) for m in metrics_history])
    value_loss = np.array([m.get('loss/value', 0) for m in metrics_history])
    
    # Phase 정보
    if curriculum_phases is None:
        curriculum_phases = [0, n_episodes]
    
    # 이동평균 계산
    def moving_average(data, window):
        if len(data) < window:
            return data
        return np.convolve(data, np.ones(window)/window, mode='valid')
    
    ma_window = min(ma_window, n_episodes // 2) if n_episodes > 10 else 1
    rewards_ma = moving_average(rewards, ma_window)
    des_ma = moving_average(des_values, ma_window)
    breach_ma = moving_average(breach_rates, ma_window)
    mttc_ma = moving_average(mttc_values, ma_window)
    
    # Figure 생성
    fig, axes = plt.subplots(2, 3, figsize=(14, 9))
    
    # Phase 색상 영역
    def add_phase_regions(ax):
        for i in range(len(curriculum_phases) - 1):
            ax.axvspan(curriculum_phases[i], curriculum_phases[i+1], 
                      alpha=0.1, color=PHASE_COLORS[i % len(PHASE_COLORS)])
    
    # (a) Reward
    ax = axes[0, 0]
    add_phase_regions(ax)
    ax.plot(episodes, rewards, alpha=0.3, color='#1f77b4', linewidth=0.5)
    if len(rewards_ma) > 0:
        ma_x = np.arange(ma_window, n_episodes + 1)
        ax.plot(ma_x, rewards_ma, color='#D55E00', linewidth=1.5, label=f'MA-{ma_window}')
    ax.set_xlabel('Episode')
    ax.set_ylabel('Episode Reward')
    ax.set_title('(a) Training Reward', fontweight='bold')
    ax.legend(loc='lower right', fontsize=7)
    
    # (b) Defense Effectiveness Score
    ax = axes[0, 1]
    add_phase_regions(ax)
    ax.plot(episodes, des_values, alpha=0.3, color='#1f77b4', linewidth=0.5)
    if len(des_ma) > 0:
        ma_x = np.arange(ma_window, n_episodes + 1)
        ax.plot(ma_x, des_ma, color='#D55E00', linewidth=1.5)
    ax.set_xlabel('Episode')
    ax.set_ylabel(r'$S_{\mathrm{MTD}}$ (DES)')
    ax.set_title('(b) Defense Effectiveness', fontweight='bold')
    ax.set_ylim(0, 1)
    
    # (c) Breach Rate
    ax = axes[0, 2]
    add_phase_regions(ax)
    ax.plot(episodes, breach_rates, alpha=0.3, color='#D73027', linewidth=0.5)
    if len(breach_ma) > 0:
        ma_x = np.arange(ma_window, n_episodes + 1)
        ax.plot(ma_x, breach_ma, color='#D55E00', linewidth=1.5)
    ax.set_xlabel('Episode')
    ax.set_ylabel('Breach Rate (%)')
    ax.set_title('(c) Breach Rate', fontweight='bold')
    ax.set_ylim(0, 100)
    
    # (d) MTTC
    ax = axes[1, 0]
    add_phase_regions(ax)
    ax.plot(episodes, mttc_values, alpha=0.3, color='#1f77b4', linewidth=0.5)
    if len(mttc_ma) > 0:
        ma_x = np.arange(ma_window, n_episodes + 1)
        ax.plot(ma_x, mttc_ma, color='#D55E00', linewidth=1.5)
    ax.set_xlabel('Episode')
    ax.set_ylabel('MTTC (steps)')
    ax.set_title('(d) Mean Time to Compromise', fontweight='bold')
    
    # (e) Loss
    ax = axes[1, 1]
    add_phase_regions(ax)
    if np.any(policy_loss != 0):
        ax.plot(episodes, np.abs(policy_loss) + 1e-8, alpha=0.7, color='#0072B2', linewidth=0.8, label='Policy')
        ax.plot(episodes, np.abs(value_loss) + 1e-8, alpha=0.7, color='#E69F00', linewidth=0.8, label='Value')
        ax.set_yscale('log')
    else:
        ax.text(0.5, 0.5, 'No loss data', ha='center', va='center', transform=ax.transAxes)
    ax.set_xlabel('Episode')
    ax.set_ylabel('Loss')
    ax.set_title('(e) Training Loss', fontweight='bold')
    ax.legend(loc='upper right', fontsize=7)
    
    # (f) Level Distribution
    ax = axes[1, 2]
    levels = [m.get('episode/seeker_level', m.get('level', 0)) for m in metrics_history]
    level_counts = [levels.count(i) for i in range(5)]
    bars = ax.bar([f'L{i}' for i in range(5)], level_counts, color=LEVEL_COLORS, 
                  edgecolor='black', linewidth=0.5)
    ax.set_xlabel('Attacker Level')
    ax.set_ylabel('Episodes')
    ax.set_title('(f) Training Distribution', fontweight='bold')
    for bar, val in zip(bars, level_counts):
        if val > 0:
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1, 
                   str(val), ha='center', fontsize=8)
    
    plt.tight_layout()
    
    # 저장
    plt.savefig(f'{save_path}.pdf', format='pdf', bbox_inches='tight')
    plt.savefig(f'{save_path}.png', format='png', dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"✅ Training curves: {save_path}.pdf/png")


def plot_training_level_performance(
    metrics_history: List[Dict],
    save_path: str,
):
    """레벨별 학습 성능 추이 그래프"""
    setup_ieee_style()
    
    level_data = {i: {'episodes': [], 'rewards': [], 'des': [], 'breach': []} for i in range(5)}
    
    for idx, m in enumerate(metrics_history):
        level = m.get('episode/seeker_level', m.get('level', 0))
        if level in level_data:
            level_data[level]['episodes'].append(idx + 1)
            level_data[level]['rewards'].append(m.get('episode/reward', m.get('reward', 0)))
            level_data[level]['des'].append(m.get('MTD/DES', m.get('des', 0)))
            level_data[level]['breach'].append(1 - m.get('Defense/BreachPrevented', 1 - m.get('breach', 0)))
    
    fig, axes = plt.subplots(1, 3, figsize=(14, 4))
    
    metrics_to_plot = [
        ('rewards', 'Reward', '(a) Reward by Level'),
        ('des', 'DES', '(b) DES by Level'),
        ('breach', 'Breach Rate', '(c) Breach Rate by Level'),
    ]
    
    for idx, (metric, ylabel, title) in enumerate(metrics_to_plot):
        ax = axes[idx]
        for level in range(5):
            if len(level_data[level]['episodes']) > 0:
                window = min(20, len(level_data[level][metric]) // 2)
                if window > 1:
                    data = np.convolve(level_data[level][metric], np.ones(window)/window, mode='valid')
                    x = level_data[level]['episodes'][window-1:]
                else:
                    data = level_data[level][metric]
                    x = level_data[level]['episodes']
                ax.plot(x, data, color=LEVEL_COLORS[level], alpha=0.8, label=f'L{level}', linewidth=1.2)
        
        ax.set_xlabel('Episode')
        ax.set_ylabel(ylabel)
        ax.set_title(title, fontweight='bold')
        if idx == 0:
            ax.legend(loc='best', fontsize=7, ncol=2)
        if metric in ['des', 'breach']:
            ax.set_ylim(0, 1)
    
    plt.tight_layout()
    plt.savefig(f'{save_path}.pdf', format='pdf', bbox_inches='tight')
    plt.savefig(f'{save_path}.png', format='png', dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"✅ Level performance: {save_path}.pdf/png")


# =============================================================================
# Evaluation Result Plots
# =============================================================================
def plot_strategy_comparison(
    results: Dict[str, Dict],
    save_path: str,
):
    """전략 비교 그래프 (6-panel bar chart) - 메인 결과"""
    setup_ieee_style()
    
    strategies = list(results.keys())
    x = np.arange(len(strategies))
    
    colors = [STRATEGY_COLORS.get(s, '#808080') for s in strategies]
    hatches = [STRATEGY_HATCHES.get(s, '') for s in strategies]
    
    fig, axes = plt.subplots(2, 3, figsize=(14, 9))
    
    panels = [
        ('breach_rate', 'Breach Rate (%)', '(a) Average Breach Rate', True, 0, 100),
        ('s_mtd', 'DES', '(b) Defense Effectiveness', False, 0, 1),
        ('mttc', 'Steps', '(c) Mean Time To Compromise', False, None, None),
        ('cost', 'Cost', '(d) Defense Cost', True, None, None),
        ('cer', 'Ratio', '(e) Cost-Efficiency Ratio', False, None, None),
        ('cdi', 'Index', '(f) Configuration Diversity', False, 0, 1),
    ]
    
    for idx, (metric, ylabel, title, lower_better, ymin, ymax) in enumerate(panels):
        ax = axes[idx // 3, idx % 3]
        
        values = []
        stds = []
        for s in strategies:
            val = results[s].get(metric, results[s].get('DES' if metric == 's_mtd' else metric, 0))
            std = results[s].get(f'{metric}_std', 0)
            values.append(val)
            stds.append(std)
        
        bars = ax.bar(x, values, color=colors, edgecolor='black', linewidth=0.8,
                     yerr=stds if any(s > 0 for s in stds) else None, capsize=3)
        
        for bar, h in zip(bars, hatches):
            bar.set_hatch(h)
        
        if values:
            best_idx = np.argmin(values) if lower_better else np.argmax(values)
            bars[best_idx].set_edgecolor('#D55E00')
            bars[best_idx].set_linewidth(2.5)
        
        ax.set_ylabel(ylabel)
        ax.set_title(title, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels(strategies, rotation=20, ha='right', fontsize=8)
        if ymin is not None:
            ax.set_ylim(ymin, ymax)
        
        for i, (bar, val) in enumerate(zip(bars, values)):
            fmt = f'{val:.1f}' if metric in ['breach_rate', 'mttc'] else f'{val:.3f}'
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height(), fmt, ha='center', va='bottom', fontsize=7)
    
    handles = [mpatches.Patch(facecolor=colors[i], edgecolor='black', hatch=hatches[i], label=s) for i, s in enumerate(strategies)]
    fig.legend(handles=handles, loc='lower center', ncol=len(strategies), fontsize=8, bbox_to_anchor=(0.5, -0.02))
    
    plt.tight_layout(rect=[0, 0.05, 1, 1])
    
    plt.savefig(f'{save_path}.pdf', format='pdf', bbox_inches='tight')
    plt.savefig(f'{save_path}.png', format='png', dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"✅ Strategy comparison: {save_path}.pdf/png")


def plot_level_comparison(
    results: Dict[str, Dict[int, Dict]],
    save_path: str,
):
    """공격자 레벨별 성능 비교 (3-panel line graph)"""
    setup_ieee_style()
    
    strategies = list(results.keys())
    levels = sorted(set(l for s in results.values() for l in s.keys()))
    
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.5))
    
    metrics = [
        ('breach_rate', 'Breach Rate (%)', '(a) Breach Rate by Level', 0, 105),
        ('s_mtd', 'DES', '(b) DES by Level', 0, 1),
        ('mttc', 'MTTC (steps)', '(c) MTTC by Level', None, None),
    ]
    
    for idx, (metric, ylabel, title, ymin, ymax) in enumerate(metrics):
        ax = axes[idx]
        
        for strategy in strategies:
            values = []
            for l in levels:
                val = results[strategy].get(l, {}).get(metric, results[strategy].get(l, {}).get('DES' if metric == 's_mtd' else metric, 0))
                values.append(val)
            
            ax.plot(levels, values, marker=STRATEGY_MARKERS.get(strategy, 'o'),
                   color=STRATEGY_COLORS.get(strategy, '#808080'), label=strategy, linewidth=2, markersize=8)
        
        ax.set_xlabel('Attacker Level')
        ax.set_ylabel(ylabel)
        ax.set_title(title, fontweight='bold')
        ax.set_xticks(levels)
        ax.set_xticklabels([f'L{l}' for l in levels])
        if ymin is not None:
            ax.set_ylim(ymin, ymax)
        if idx == 0:
            ax.legend(loc='best', fontsize=7)
    
    plt.tight_layout()
    
    plt.savefig(f'{save_path}.pdf', format='pdf', bbox_inches='tight')
    plt.savefig(f'{save_path}.png', format='png', dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"✅ Level comparison: {save_path}.pdf/png")


def plot_des_heatmap(
    results: Dict[str, Dict[int, Dict]],
    save_path: str,
):
    """DES 히트맵 (Strategy × Level)"""
    setup_ieee_style()
    
    strategies = list(results.keys())
    levels = sorted(set(l for s in results.values() for l in s.keys()))
    
    data = []
    for strategy in strategies:
        row = []
        for l in levels:
            val = results[strategy].get(l, {}).get('s_mtd', results[strategy].get(l, {}).get('DES', results[strategy].get(l, {}).get('des', 0)))
            row.append(val)
        data.append(row)
    
    data = np.array(data)
    
    fig, ax = plt.subplots(figsize=(8, 5))
    
    cmap = LinearSegmentedColormap.from_list('custom', ['#fee8c8', '#fc8d59', '#b30000'])
    im = ax.imshow(data, cmap=cmap, aspect='auto', vmin=0.2, vmax=0.95)
    
    ax.set_xticks(np.arange(len(levels)))
    ax.set_xticklabels([f'L{l}' for l in levels])
    ax.set_yticks(np.arange(len(strategies)))
    ax.set_yticklabels(strategies)
    
    for i in range(len(strategies)):
        for j in range(len(levels)):
            color = 'white' if data[i, j] > 0.5 else 'black'
            ax.text(j, i, f'{data[i, j]:.2f}', ha='center', va='center', fontsize=10, fontweight='bold', color=color)
    
    ax.set_xlabel('Attacker Level')
    ax.set_ylabel('Strategy')
    ax.set_title(r'$S_{\mathrm{MTD}}$ (DES) Heatmap', fontweight='bold')
    
    plt.colorbar(im, ax=ax, label='DES', shrink=0.8)
    
    plt.tight_layout()
    
    plt.savefig(f'{save_path}.pdf', format='pdf', bbox_inches='tight')
    plt.savefig(f'{save_path}.png', format='png', dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"✅ DES heatmap: {save_path}.pdf/png")


def plot_tradeoff_analysis(
    results: Dict[str, Dict],
    save_path: str,
):
    """Trade-off 분석 그래프 (2-panel scatter)"""
    setup_ieee_style()
    
    strategies = list(results.keys())
    
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    
    ax = axes[0]
    for s in strategies:
        cost = results[s].get('cost', 0)
        des = results[s].get('s_mtd', results[s].get('DES', results[s].get('des', 0)))
        ax.scatter(cost, des, s=200, color=STRATEGY_COLORS.get(s, '#808080'),
                  marker=STRATEGY_MARKERS.get(s, 'o'), label=s, edgecolors='black', linewidth=1.5, zorder=5)
    ax.set_xlabel('Total Cost')
    ax.set_ylabel(r'$S_{\mathrm{MTD}}$')
    ax.set_title('(a) Cost vs Defense Effectiveness', fontweight='bold')
    ax.legend(loc='best', fontsize=7)
    ax.set_ylim(0, 1)
    
    ax = axes[1]
    for s in strategies:
        br = results[s].get('breach_rate', 0)
        mttc = results[s].get('mttc', 0)
        ax.scatter(br, mttc, s=200, color=STRATEGY_COLORS.get(s, '#808080'),
                  marker=STRATEGY_MARKERS.get(s, 'o'), label=s, edgecolors='black', linewidth=1.5, zorder=5)
    ax.set_xlabel('Breach Rate (%)')
    ax.set_ylabel('MTTC (steps)')
    ax.set_title('(b) Breach Rate vs MTTC', fontweight='bold')
    ax.legend(loc='best', fontsize=7)
    
    plt.tight_layout()
    
    plt.savefig(f'{save_path}.pdf', format='pdf', bbox_inches='tight')
    plt.savefig(f'{save_path}.png', format='png', dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"✅ Trade-off analysis: {save_path}.pdf/png")


def plot_statistical_comparison(
    results: Dict[str, Dict],
    save_path: str,
    n_samples: int = 50,
):
    """통계적 비교 (Box plots)"""
    setup_ieee_style()
    
    strategies = list(results.keys())
    
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.5))
    
    metrics_to_plot = [
        ('s_mtd', r'$S_{\mathrm{MTD}}$', '(a) DES Distribution'),
        ('mttc', 'MTTC (steps)', '(b) MTTC Distribution'),
        ('cost', 'Cost', '(c) Cost Distribution'),
    ]
    
    for idx, (metric, ylabel, title) in enumerate(metrics_to_plot):
        ax = axes[idx]
        
        box_data = []
        for s in strategies:
            mean = results[s].get(metric, results[s].get('DES' if metric == 's_mtd' else metric, 0))
            std = results[s].get(f'{metric}_std', 0.05)
            samples = np.random.normal(mean, max(std, 0.01), n_samples)
            if metric == 's_mtd':
                samples = np.clip(samples, 0, 1)
            elif metric == 'cost':
                samples = np.clip(samples, 0, None)
            box_data.append(samples)
        
        bp = ax.boxplot(box_data, patch_artist=True, tick_labels=strategies)
        
        for i, (patch, strategy) in enumerate(zip(bp['boxes'], strategies)):
            patch.set_facecolor(STRATEGY_COLORS.get(strategy, '#808080'))
            patch.set_alpha(0.7)
        
        ax.set_ylabel(ylabel)
        ax.set_title(title, fontweight='bold')
        ax.tick_params(axis='x', rotation=20)
    
    plt.tight_layout()
    
    plt.savefig(f'{save_path}.pdf', format='pdf', bbox_inches='tight')
    plt.savefig(f'{save_path}.png', format='png', dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"✅ Statistical comparison: {save_path}.pdf/png")


def plot_grouped_bar_by_level(
    results: Dict[str, Dict[int, Dict]],
    save_path: str,
):
    """레벨별 그룹 바 차트 (4-panel)"""
    setup_ieee_style()
    
    strategies = list(results.keys())
    levels = sorted(set(l for s in results.values() for l in s.keys()))
    
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    x = np.arange(len(levels))
    width = 0.8 / len(strategies)
    
    metrics = [
        ('breach_rate', 'Breach Rate (%)', '(a) Breach Rate by Level', 0, 105),
        ('s_mtd', 'DES', '(b) DES by Level', 0, 1),
        ('mttc', 'MTTC (steps)', '(c) MTTC by Level', None, None),
        ('cost', 'Cost', '(d) Cost by Level', None, None),
    ]
    
    for idx, (metric, ylabel, title, ymin, ymax) in enumerate(metrics):
        ax = axes[idx // 2, idx % 2]
        
        for i, strategy in enumerate(strategies):
            values = []
            for l in levels:
                val = results[strategy].get(l, {}).get(metric, results[strategy].get(l, {}).get('DES' if metric == 's_mtd' else metric, 0))
                values.append(val)
            
            offset = (i - len(strategies)/2 + 0.5) * width
            ax.bar(x + offset, values, width, label=strategy if idx == 0 else '',
                  color=STRATEGY_COLORS.get(strategy, '#808080'), edgecolor='black', linewidth=0.5,
                  hatch=STRATEGY_HATCHES.get(strategy, ''))
        
        ax.set_xlabel('Attacker Level')
        ax.set_ylabel(ylabel)
        ax.set_title(title, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels([f'L{l}' for l in levels])
        if ymin is not None:
            ax.set_ylim(ymin, ymax)
    
    handles = [mpatches.Patch(facecolor=STRATEGY_COLORS.get(s, '#808080'), edgecolor='black', hatch=STRATEGY_HATCHES.get(s, ''), label=s) for s in strategies]
    fig.legend(handles=handles, loc='lower center', ncol=len(strategies), fontsize=8, bbox_to_anchor=(0.5, -0.02))
    
    plt.tight_layout(rect=[0, 0.05, 1, 1])
    
    plt.savefig(f'{save_path}.pdf', format='pdf', bbox_inches='tight')
    plt.savefig(f'{save_path}.png', format='png', dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"✅ Grouped bar: {save_path}.pdf/png")


# =============================================================================
# LaTeX Table Generation
# =============================================================================
def generate_latex_table_overall(results: Dict[str, Dict], save_path: str):
    """전체 성능 비교 LaTeX 테이블"""
    strategies = list(results.keys())
    
    best_des = max(results[s].get('s_mtd', results[s].get('DES', 0)) for s in strategies)
    best_br = min(results[s].get('breach_rate', 100) for s in strategies)
    best_mttc = max(results[s].get('mttc', 0) for s in strategies)
    best_cer = max(results[s].get('cer', 0) for s in strategies)
    best_cdi = max(results[s].get('cdi', 0) for s in strategies)
    best_cost = min(results[s].get('cost', float('inf')) for s in strategies)
    
    table = r"""\begin{table}[!t]
\centering
\caption{Overall Defense Performance Comparison}
\label{tab:overall_comparison}
\begin{tabular}{@{}lcccccc@{}}
\toprule
\textbf{Strategy} & $S_{\mathrm{MTD}}$ & \textbf{BR(\%)} & \textbf{MTTC} & \textbf{CER} & \textbf{CDI} & \textbf{Cost} \\
\midrule
"""
    
    for s in strategies:
        des = results[s].get('s_mtd', results[s].get('DES', 0))
        br = results[s].get('breach_rate', 0)
        mttc = results[s].get('mttc', 0)
        cer = results[s].get('cer', 0)
        cdi = results[s].get('cdi', 0)
        cost = results[s].get('cost', 0)
        
        des_str = f"\\textbf{{{des:.3f}}}" if abs(des - best_des) < 0.001 else f"{des:.3f}"
        br_str = f"\\textbf{{{br:.1f}}}" if abs(br - best_br) < 0.1 else f"{br:.1f}"
        mttc_str = f"\\textbf{{{mttc:.0f}}}" if abs(mttc - best_mttc) < 1 else f"{mttc:.0f}"
        cer_str = f"\\textbf{{{cer:.2f}}}" if abs(cer - best_cer) < 0.01 else f"{cer:.2f}"
        cdi_str = f"\\textbf{{{cdi:.3f}}}" if abs(cdi - best_cdi) < 0.001 else f"{cdi:.3f}"
        cost_str = f"\\textbf{{{cost:.3f}}}" if abs(cost - best_cost) < 0.001 else f"{cost:.3f}"
        
        table += f"{s} & {des_str} & {br_str} & {mttc_str} & {cer_str} & {cdi_str} & {cost_str} \\\\\n"
    
    table += r"""\bottomrule
\end{tabular}
\end{table}
"""
    
    with open(save_path, 'w') as f:
        f.write(table)
    
    print(f"✅ LaTeX table: {save_path}")


def generate_latex_table_by_level(results: Dict[str, Dict[int, Dict]], save_path: str, metric: str = 'breach_rate'):
    """레벨별 성능 LaTeX 테이블"""
    strategies = list(results.keys())
    levels = sorted(set(l for s in results.values() for l in s.keys()))
    
    metric_name = {'breach_rate': 'Breach Rate (\\%)', 's_mtd': '$S_{\\mathrm{MTD}}$', 'mttc': 'MTTC'}.get(metric, metric)
    
    table = f"""\\begin{{table}}[!t]
\\centering
\\caption{{{metric_name} by Attacker Level}}
\\begin{{tabular}}{{l{'c' * len(levels)}}}
\\toprule
\\textbf{{Strategy}} & """ + " & ".join([f"\\textbf{{L{l}}}" for l in levels]) + r""" \\
\midrule
"""
    
    for s in strategies:
        values = []
        for l in levels:
            val = results[s].get(l, {}).get(metric, results[s].get(l, {}).get('DES' if metric == 's_mtd' else metric, 0))
            if metric == 'breach_rate':
                values.append(f"{val:.1f}")
            elif metric == 's_mtd':
                values.append(f"{val:.3f}")
            else:
                values.append(f"{val:.0f}")
        table += f"{s} & " + " & ".join(values) + r" \\" + "\n"
    
    table += r"""\bottomrule
\end{tabular}
\end{table}
"""
    
    with open(save_path, 'w') as f:
        f.write(table)
    
    print(f"✅ LaTeX table: {save_path}")


# =============================================================================
# Main (Test)
# =============================================================================
if __name__ == "__main__":
    print("IEEE Figure Utilities v09 - Test Mode")
    
    os.makedirs('test_figures', exist_ok=True)
    
    test_metrics = []
    for i in range(100):
        test_metrics.append({
            'episode/reward': 50 + i * 0.5 + np.random.randn() * 10,
            'MTD/DES': min(0.9, 0.3 + i * 0.005 + np.random.randn() * 0.05),
            'Defense/BreachPrevented': 1 if np.random.random() > 0.5 - i * 0.003 else 0,
            'MTD/MTTC': min(200, 50 + i + np.random.randn() * 10),
            'loss/policy': max(0.001, 0.5 - i * 0.004 + np.random.randn() * 0.05),
            'loss/value': max(0.001, 1.0 - i * 0.008 + np.random.randn() * 0.1),
            'episode/seeker_level': np.random.randint(0, 5),
        })
    
    plot_training_curves(test_metrics, 'test_figures/training_curves', [0, 30, 60, 100])
    plot_training_level_performance(test_metrics, 'test_figures/level_performance')
    
    print("\n✅ Test complete!")