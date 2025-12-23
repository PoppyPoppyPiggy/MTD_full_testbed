#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Level-wise Training Curve Grid Generator for MTD-RL Paper
==========================================================

실제 training_metrics.json 파일을 로드하여
공격자 레벨별 (L0-L4) × 주요 지표별 학습 곡선 그리드 생성

Usage:
    # 실제 데이터 사용
    python generate_level_grid_figures.py \
        --training-metrics checkpoints_v08/training_metrics.json \
        --output-dir figures
    
    # JSON 구조만 분석
    python generate_level_grid_figures.py \
        --training-metrics checkpoints_v08/training_metrics.json \
        --analyze-only
    
    # Synthetic 데이터 사용 (테스트용)
    python generate_level_grid_figures.py --use-synthetic --output-dir figures

저자: MTD-RL Research Team
버전: 1.1.0
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from collections import defaultdict

import numpy as np
from scipy import stats
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')


# =============================================================================
# Configuration
# =============================================================================
@dataclass
class GridConfig:
    """그리드 설정"""
    n_seeds: int = 5
    n_episodes_per_level: int = 200
    max_steps: int = 200
    seeker_levels: List[int] = field(default_factory=lambda: [0, 1, 2, 3, 4])
    base_seed: int = 42
    moving_avg_window: int = 15
    
    metrics: List[str] = field(default_factory=lambda: [
        "DES",
        "MTTC",
        "ASR",
        "CDI",
        "CER",
        "Breach_Rate",
        "NED",
    ])


LEVEL_NAMES = {
    0: "L0: Script Kiddie",
    1: "L1: Hobbyist",
    2: "L2: Professional",
    3: "L3: Expert",
    4: "L4: APT",
}

METRIC_CONFIG = {
    "DES": {"label": "Defense Effectiveness Score", "ylim": (0, 1), "better": "higher", "color": "#9467bd"},
    "MTTC": {"label": "Mean Time To Compromise", "ylim": (0, 200), "better": "higher", "color": "#1f77b4"},
    "ASR": {"label": "Attack Surface Reduction", "ylim": (0, 1), "better": "higher", "color": "#2ca02c"},
    "CDI": {"label": "Configuration Diversity Index", "ylim": (0, 1), "better": "higher", "color": "#ff7f0e"},
    "CER": {"label": "Cost Efficiency Ratio", "ylim": None, "better": "higher", "color": "#17becf"},
    "Breach_Rate": {"label": "Breach Rate", "ylim": (0, 1), "better": "lower", "color": "#d62728"},
    "NED": {"label": "Normalized Entropy of Defense", "ylim": (0, 1), "better": "higher", "color": "#8c564b"},
    "Reward": {"label": "Episode Reward", "ylim": None, "better": "higher", "color": "#e377c2"},
    "Cost": {"label": "Total Cost", "ylim": None, "better": "lower", "color": "#7f7f7f"},
}

# 실제 JSON 키 매핑 (여러 가능한 키 이름)
JSON_KEY_MAPPING = {
    "DES": ["MTD/DES", "episode/des", "DES", "des"],
    "MTTC": ["MTD/MTTC", "episode/mttc", "MTTC", "mttc"],
    "ASR": ["MTD/ASR", "episode/asr", "ASR", "asr"],
    "CDI": ["MTD/CDI", "episode/cdi", "CDI", "cdi"],
    "CER": ["MTD/CER", "episode/cer", "CER", "cer"],
    "NED": ["MTD/NED", "episode/ned", "NED", "ned"],
    "Reward": ["episode/reward", "reward", "Reward", "total_reward"],
    "Cost": ["Cost/Total", "episode/cost", "cost", "total_cost"],
}


# =============================================================================
# Publication Style
# =============================================================================
def set_publication_style():
    plt.rcParams.update({
        'font.family': 'serif',
        'font.serif': ['Times New Roman', 'DejaVu Serif', 'serif'],
        'font.size': 8,
        'axes.labelsize': 9,
        'axes.titlesize': 10,
        'xtick.labelsize': 7,
        'ytick.labelsize': 7,
        'legend.fontsize': 7,
        'figure.titlesize': 12,
        'axes.linewidth': 0.6,
        'grid.linewidth': 0.4,
        'lines.linewidth': 1.2,
        'savefig.dpi': 300,
        'savefig.bbox': 'tight',
        'axes.grid': True,
        'grid.alpha': 0.3,
    })


# =============================================================================
# Statistical Functions
# =============================================================================
def compute_confidence_interval(data: np.ndarray, confidence: float = 0.95) -> Tuple[float, float, float]:
    n = len(data)
    if n < 2:
        m = float(np.mean(data))
        return m, m, m
    mean = np.mean(data)
    se = stats.sem(data)
    ci = se * stats.t.ppf((1 + confidence) / 2, n - 1)
    return float(mean), float(mean - ci), float(mean + ci)


def moving_average(data: np.ndarray, window: int) -> np.ndarray:
    if len(data) < window:
        return data
    return np.convolve(data, np.ones(window) / window, mode='valid')


# =============================================================================
# Real Data Loading
# =============================================================================
def get_value_from_entry(entry: dict, metric: str) -> Optional[float]:
    """JSON 엔트리에서 메트릭 값 추출"""
    # Breach_Rate 특별 처리
    if metric == "Breach_Rate":
        for key in ["Defense/BreachPrevented", "episode/breach_prevented", "breach_prevented", "survival"]:
            if key in entry:
                val = entry[key]
                # 1이면 생존, 0이면 침해 → breach_rate = 1 - survival
                return 1.0 - float(val)
        return None
    
    # 일반 메트릭
    possible_keys = JSON_KEY_MAPPING.get(metric, [metric])
    for key in possible_keys:
        if key in entry:
            try:
                return float(entry[key])
            except (ValueError, TypeError):
                continue
    return None


def analyze_json_structure(metrics_path: str) -> Dict[str, Any]:
    """JSON 파일 구조 분석"""
    with open(metrics_path, 'r') as f:
        raw_data = json.load(f)
    
    print("\n" + "=" * 70)
    print("📋 JSON Structure Analysis")
    print("=" * 70)
    print(f"Type: {type(raw_data).__name__}")
    
    if isinstance(raw_data, list):
        print(f"Length: {len(raw_data)} entries")
        
        if raw_data:
            print(f"\n🔑 All keys in first entry ({len(raw_data[0])} keys):")
            for key in sorted(raw_data[0].keys()):
                value = raw_data[0][key]
                vtype = type(value).__name__
                vstr = str(value)[:50] + "..." if len(str(value)) > 50 else str(value)
                print(f"   {key:<35} ({vtype}): {vstr}")
            
            # 레벨 분포 확인
            level_keys = ["episode/seeker_level", "seeker_level", "level", "attacker_level"]
            found_level_key = None
            level_counts = defaultdict(int)
            
            for key in level_keys:
                if key in raw_data[0]:
                    found_level_key = key
                    break
            
            if found_level_key:
                for entry in raw_data:
                    level = int(entry.get(found_level_key, -1))
                    level_counts[level] += 1
                
                print(f"\n📊 Level distribution (key: {found_level_key}):")
                for level in sorted(level_counts.keys()):
                    print(f"   Level {level}: {level_counts[level]} episodes")
            else:
                print(f"\n⚠️ No level key found. Tried: {level_keys}")
            
            # 메트릭 키 매칭 확인
            print(f"\n🎯 Metric key matching:")
            for metric, possible_keys in JSON_KEY_MAPPING.items():
                found = None
                for key in possible_keys:
                    if key in raw_data[0]:
                        found = key
                        break
                status = f"✅ {found}" if found else "❌ Not found"
                print(f"   {metric:<15} → {status}")
    
    elif isinstance(raw_data, dict):
        print(f"Top-level keys: {list(raw_data.keys())}")
    
    print("=" * 70 + "\n")
    
    return {"type": type(raw_data).__name__, "length": len(raw_data) if isinstance(raw_data, list) else 0}


def load_real_training_data(metrics_path: str, config: GridConfig) -> Dict[int, Dict[str, np.ndarray]]:
    """
    실제 training_metrics.json 로드
    """
    print(f"\n📂 Loading: {metrics_path}")
    
    with open(metrics_path, 'r') as f:
        raw_data = json.load(f)
    
    if not isinstance(raw_data, list):
        print("❌ Expected list format")
        return {level: {} for level in config.seeker_levels}
    
    print(f"   Total entries: {len(raw_data)}")
    
    # seeker_level 키 찾기
    level_keys = ["episode/seeker_level", "seeker_level", "level", "attacker_level", "phase"]
    found_level_key = None
    
    if raw_data:
        for key in level_keys:
            if key in raw_data[0]:
                found_level_key = key
                break
    
    # 레벨별로 데이터 분류
    level_data = {level: defaultdict(list) for level in config.seeker_levels}
    
    if found_level_key:
        print(f"   Level key: {found_level_key}")
        for entry in raw_data:
            level = int(entry.get(found_level_key, 0))
            # 레벨이 범위를 벗어나면 매핑
            if level not in config.seeker_levels:
                level = level % 5  # 0-4로 매핑
            
            for metric in config.metrics:
                value = get_value_from_entry(entry, metric)
                if value is not None:
                    level_data[level][metric].append(value)
    else:
        print("⚠️ No level key found. Distributing by episode index.")
        for i, entry in enumerate(raw_data):
            level = i % 5
            for metric in config.metrics:
                value = get_value_from_entry(entry, metric)
                if value is not None:
                    level_data[level][metric].append(value)
    
    # 데이터 통계 출력
    print("\n📊 Loaded data per level:")
    for level in config.seeker_levels:
        counts = {m: len(level_data[level][m]) for m in config.metrics if level_data[level][m]}
        if counts:
            print(f"   Level {level}: {counts}")
        else:
            print(f"   Level {level}: No data")
    
    # numpy array로 변환
    result = {}
    for level in config.seeker_levels:
        result[level] = {}
        for metric in config.metrics:
            if level_data[level][metric]:
                arr = np.array(level_data[level][metric])
                result[level][metric] = arr.reshape(1, -1)  # (1, n_episodes)
            else:
                result[level][metric] = np.array([[]])
    
    return result


# =============================================================================
# Synthetic Data Generation
# =============================================================================
def generate_synthetic_data(config: GridConfig) -> Dict[int, Dict[str, np.ndarray]]:
    """테스트용 synthetic 데이터"""
    np.random.seed(config.base_seed)
    
    data = {}
    level_performance = {
        0: {"DES": 0.85, "MTTC": 190, "ASR": 0.92, "CDI": 0.88, "CER": 0.22, "Breach_Rate": 0.05, "NED": 0.75},
        1: {"DES": 0.78, "MTTC": 175, "ASR": 0.85, "CDI": 0.82, "CER": 0.19, "Breach_Rate": 0.10, "NED": 0.70},
        2: {"DES": 0.70, "MTTC": 155, "ASR": 0.78, "CDI": 0.75, "CER": 0.16, "Breach_Rate": 0.18, "NED": 0.65},
        3: {"DES": 0.62, "MTTC": 130, "ASR": 0.70, "CDI": 0.68, "CER": 0.13, "Breach_Rate": 0.28, "NED": 0.58},
        4: {"DES": 0.52, "MTTC": 105, "ASR": 0.60, "CDI": 0.58, "CER": 0.10, "Breach_Rate": 0.42, "NED": 0.48},
    }
    initial_values = {"DES": 0.25, "MTTC": 45, "ASR": 0.30, "CDI": 0.25, "CER": 0.05, "Breach_Rate": 0.70, "NED": 0.20}
    
    for level in config.seeker_levels:
        data[level] = {}
        target = level_performance[level]
        
        for metric in config.metrics:
            if metric not in target:
                continue
            metric_data = []
            
            for seed in range(config.n_seeds):
                np.random.seed(config.base_seed + seed * 1000 + level * 100)
                init_val = initial_values[metric]
                target_val = target[metric]
                n_ep = config.n_episodes_per_level
                learning_rate = 0.015 - level * 0.002
                
                curve = np.zeros(n_ep)
                for ep in range(n_ep):
                    progress = 1 - np.exp(-learning_rate * ep)
                    if metric == "Breach_Rate":
                        value = init_val - (init_val - target_val) * progress
                    else:
                        value = init_val + (target_val - init_val) * progress
                    noise_scale = 0.05 if metric != "MTTC" else 10
                    curve[ep] = value + np.random.randn() * noise_scale * (1 - progress * 0.5)
                
                if metric in ["DES", "ASR", "CDI", "NED", "Breach_Rate"]:
                    curve = np.clip(curve, 0, 1)
                elif metric == "MTTC":
                    curve = np.clip(curve, 0, 200)
                
                metric_data.append(curve)
            
            data[level][metric] = np.array(metric_data)
    
    return data


# =============================================================================
# Figure Generation
# =============================================================================
def generate_training_curve_grid(
    data: Dict[int, Dict[str, np.ndarray]],
    config: GridConfig,
    output_path: Path,
) -> None:
    """레벨별 × 지표별 학습 곡선 그리드"""
    set_publication_style()
    
    # 데이터가 있는 메트릭만 사용
    available_metrics = []
    for metric in config.metrics:
        for level in config.seeker_levels:
            if metric in data[level]:
                arr = data[level][metric]
                if arr.size > 1:
                    available_metrics.append(metric)
                    break
    
    if not available_metrics:
        print("❌ No data available!")
        return
    
    print(f"\n📈 Generating grid for: {available_metrics}")
    
    n_levels = len(config.seeker_levels)
    n_metrics = len(available_metrics)
    
    fig, axes = plt.subplots(n_metrics, n_levels, figsize=(14, 2.2 * n_metrics))
    
    if n_metrics == 1:
        axes = axes.reshape(1, -1)
    
    for row_idx, metric in enumerate(available_metrics):
        metric_cfg = METRIC_CONFIG.get(metric, {"label": metric, "ylim": None, "color": "#333333"})
        
        for col_idx, level in enumerate(config.seeker_levels):
            ax = axes[row_idx, col_idx]
            
            arr = data[level].get(metric, np.array([[]]))
            if arr.size < 2:
                ax.text(0.5, 0.5, "No Data", ha='center', va='center', transform=ax.transAxes)
                if row_idx == 0:
                    ax.set_title(LEVEL_NAMES[level], fontsize=9, fontweight='bold')
                continue
            
            metric_data = arr
            n_seeds, n_episodes = metric_data.shape
            
            # 이동 평균
            window = min(config.moving_avg_window, max(1, n_episodes // 5))
            
            smoothed_data = []
            for seed_data in metric_data:
                smoothed = moving_average(seed_data, window) if window > 1 else seed_data
                smoothed_data.append(smoothed)
            
            min_len = min(len(s) for s in smoothed_data)
            smoothed_data = np.array([s[:min_len] for s in smoothed_data])
            episodes = np.arange(min_len)
            
            # 평균 및 CI
            means = np.mean(smoothed_data, axis=0) if n_seeds > 1 else smoothed_data[0]
            
            color = metric_cfg.get("color", "#333333")
            ax.plot(episodes, means, color=color, linewidth=1.5)
            
            if n_seeds > 1:
                stds = np.std(smoothed_data, axis=0)
                ax.fill_between(episodes, means - stds, means + stds, color=color, alpha=0.2)
            
            if metric_cfg.get("ylim"):
                ax.set_ylim(metric_cfg["ylim"])
            
            if row_idx == 0:
                ax.set_title(LEVEL_NAMES[level], fontsize=9, fontweight='bold')
            if col_idx == 0:
                ax.set_ylabel(metric_cfg.get("label", metric), fontsize=8)
            if row_idx == n_metrics - 1:
                ax.set_xlabel('Episode', fontsize=8)
            
            ax.grid(True, alpha=0.3, linestyle=':')
            
            # 수렴값
            final_mean = np.mean(means[-max(1, len(means)//10):])
            if col_idx == n_levels - 1:
                fmt = f'{final_mean:.0f}' if metric == "MTTC" else f'{final_mean:.3f}'
                ax.text(1.02, 0.5, fmt, transform=ax.transAxes, fontsize=7, va='center', color=color)
    
    fig.suptitle('Training Convergence by Attacker Level', fontsize=12, fontweight='bold', y=1.01)
    
    plt.tight_layout()
    plt.savefig(output_path / "grid_training_curves.png", dpi=300, bbox_inches='tight')
    plt.savefig(output_path / "grid_training_curves.pdf", format='pdf', bbox_inches='tight')
    plt.close()
    
    print(f"✅ Saved: {output_path / 'grid_training_curves.png'}")


def generate_summary_table(data: Dict[int, Dict[str, np.ndarray]], config: GridConfig, output_path: Path):
    """통계 요약"""
    summary = {}
    for level in config.seeker_levels:
        summary[f"Level_{level}"] = {}
        for metric in config.metrics:
            arr = data[level].get(metric, np.array([[]]))
            if arr.size < 2:
                continue
            flat = arr.flatten()
            final = flat[-max(1, len(flat)//10):]
            summary[f"Level_{level}"][metric] = {
                "mean": float(np.mean(final)),
                "std": float(np.std(final)),
                "n": len(flat),
            }
    
    with open(output_path / "training_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    
    # 콘솔 출력
    print("\n" + "=" * 80)
    print("FINAL CONVERGENCE VALUES (Last 10%)")
    print("=" * 80)
    
    header = f"{'Metric':<20}"
    for level in config.seeker_levels:
        header += f" | L{level:>8}"
    print(header)
    print("-" * 80)
    
    for metric in config.metrics:
        row = f"{metric:<20}"
        for level in config.seeker_levels:
            key = f"Level_{level}"
            if key in summary and metric in summary[key]:
                val = summary[key][metric]["mean"]
                fmt = f"{val:>8.0f}" if metric == "MTTC" else f"{val:>8.3f}"
                row += f" | {fmt}"
            else:
                row += f" |      N/A"
        print(row)
    
    print("=" * 80)
    print(f"✅ Saved: {output_path / 'training_summary.json'}")


# =============================================================================
# Main
# =============================================================================
def main():
    parser = argparse.ArgumentParser(description="Generate Level-wise Training Curve Grid")
    
    parser.add_argument("--output-dir", type=str, default="level_grid_figures")
    parser.add_argument("--n-seeds", type=int, default=5)
    parser.add_argument("--n-episodes", type=int, default=200)
    parser.add_argument("--window", type=int, default=15)
    parser.add_argument("--training-metrics", type=str, default=None)
    parser.add_argument("--use-synthetic", action="store_true")
    parser.add_argument("--analyze-only", action="store_true")
    
    args = parser.parse_args()
    
    output_path = Path(args.output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    config = GridConfig(
        n_seeds=args.n_seeds,
        n_episodes_per_level=args.n_episodes,
        moving_avg_window=args.window,
    )
    
    print("\n" + "=" * 70)
    print("Level-wise Training Curve Grid Generator v1.1")
    print("=" * 70)
    
    # JSON 분석만
    if args.analyze_only:
        if args.training_metrics:
            analyze_json_structure(args.training_metrics)
        else:
            print("❌ --training-metrics required with --analyze-only")
        return
    
    # 데이터 로드
    if args.use_synthetic:
        print("📊 Mode: SYNTHETIC data")
        data = generate_synthetic_data(config)
    elif args.training_metrics:
        print(f"📊 Mode: REAL data")
        analyze_json_structure(args.training_metrics)
        data = load_real_training_data(args.training_metrics, config)
    else:
        print("📊 Mode: SYNTHETIC (no --training-metrics provided)")
        data = generate_synthetic_data(config)
    
    # Figure 생성
    generate_training_curve_grid(data, config, output_path)
    generate_summary_table(data, config, output_path)
    
    print("\n✅ Done! Output: " + str(output_path))


if __name__ == "__main__":
    main()