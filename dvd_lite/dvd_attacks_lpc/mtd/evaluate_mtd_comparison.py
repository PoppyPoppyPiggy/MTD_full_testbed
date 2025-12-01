#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MTD Comparison Evaluation Script
================================
Seeker Level (0-4) × MTD Mode (No MTD, Heuristic, RL) = 15 experiments

Outputs:
- Comparison tables
- Bar charts for all metrics
- Heatmaps
- CSV export
"""
from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

# Plotting
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # For headless servers

# Local imports
from .rl_config_v07 import (
    ACTION_DIM, ACTION_PARAM_KEYS, DEFAULT_SEEKER_PROFILES,
    FEATURE_KEYS, STATE_DIM, EpisodeStats, MTDConfig,
)
from .rl_environment_v07 import MTDEnvironment

# Try to import torch for RL agent
try:
    import torch
    from .rl_train_v07 import PPOAgent, ActorCritic
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    print("Warning: PyTorch not available, RL MTD will be disabled")


# ---------------------------------------------------------------------------
# MTD Strategies
# ---------------------------------------------------------------------------
class NoMTDStrategy:
    """No MTD - 방어 없음"""
    name = "No MTD"

    def get_action(self, state: np.ndarray) -> np.ndarray:
        return np.zeros(ACTION_DIM)  # 모든 행동 0


class HeuristicMTDStrategy:
    """Heuristic MTD - 규칙 기반"""
    name = "Heuristic"

    def __init__(self):
        self.shuffle_cooldown = 0
        self.step = 0

    def reset(self):
        self.shuffle_cooldown = 0
        self.step = 0

    def get_action(self, state: np.ndarray) -> np.ndarray:
        self.step += 1
        action = np.zeros(ACTION_DIM)

        # State indices (from FEATURE_KEYS)
        scanned_ratio = state[0]
        services_found = state[1]
        critical_found = state[2]
        exploit_progress = state[3]
        steps_since_shuffle = state[9]

        # Rule 1: 주기적 셔플 (매 20 step)
        if self.step % 20 == 0:
            action[0] = 0.8  # shuffle_intensity

        # Rule 2: 스캔 많이 되면 셔플
        if scanned_ratio > 0.3:
            action[0] = max(action[0], 0.6)

        # Rule 3: 서비스 발견되면 즉시 셔플
        if services_found > 0:
            action[0] = 1.0
            action[1] = 0.8  # port_hop

        # Rule 4: Critical 발견시 강력 대응
        if critical_found > 0.5:
            action[0] = 1.0
            action[1] = 1.0
            action[2] = 0.8  # decoy

        # Rule 5: Exploit 진행시 블랙리스트
        if exploit_progress > 0.3:
            action[3] = 0.7  # blacklist

        # Rule 6: 기본 디코이 유지
        action[2] = max(action[2], 0.3)

        return action * 2 - 1  # Scale to [-1, 1]


class RLMTDStrategy:
    """RL MTD - 학습된 정책"""
    name = "RL MTD"

    def __init__(self, model_path: str, device: str = "cpu"):
        if not TORCH_AVAILABLE:
            raise RuntimeError("PyTorch required for RL MTD")

        self.device = device
        self.policy = ActorCritic(STATE_DIM, ACTION_DIM).to(device)
        
        # Load policy
        ckpt = torch.load(model_path, map_location=device, weights_only=True)
        if "policy" in ckpt:
            self.policy.load_state_dict(ckpt["policy"])
        else:
            self.policy.load_state_dict(ckpt)
        self.policy.eval()
        print(f"✅ RL Policy loaded from {model_path}")

    def get_action(self, state: np.ndarray) -> np.ndarray:
        with torch.no_grad():
            state_t = torch.FloatTensor(state).unsqueeze(0).to(self.device)
            action, _, _ = self.policy.act(state_t, deterministic=True)
        return action.cpu().numpy().squeeze()


# ---------------------------------------------------------------------------
# Evaluation Engine
# ---------------------------------------------------------------------------
@dataclass
class ExperimentResult:
    seeker_level: int
    mtd_mode: str
    episodes: int
    metrics: Dict[str, float]
    raw_metrics: List[Dict]


def run_experiment(
    seeker_level: int,
    mtd_strategy,
    num_episodes: int = 50,
    max_steps: int = 200,
    seed: int = 42,
) -> ExperimentResult:
    """단일 실험 실행"""
    cfg = MTDConfig()
    all_metrics = []

    for ep in range(num_episodes):
        env = MTDEnvironment(
            seed=seed + ep * 100 + seeker_level,
            seeker_level=seeker_level,
            config=cfg,
        )

        if hasattr(mtd_strategy, 'reset'):
            mtd_strategy.reset()

        state, _ = env.reset()
        ep_reward = 0.0

        for step in range(max_steps):
            action = mtd_strategy.get_action(state)
            state, reward, term, trunc, info = env.step(action)
            ep_reward += reward
            if term or trunc:
                break

        info["reward"] = ep_reward
        all_metrics.append(info)

    # Aggregate metrics
    agg_metrics = {}
    for key in all_metrics[0].keys():
        values = [m.get(key, 0) for m in all_metrics]
        # 숫자 타입만 집계
        if all(isinstance(v, (int, float, np.number)) for v in values):
            agg_metrics[f"{key}_mean"] = float(np.mean(values))
            agg_metrics[f"{key}_std"] = float(np.std(values))

    return ExperimentResult(
        seeker_level=seeker_level,
        mtd_mode=mtd_strategy.name,
        episodes=num_episodes,
        metrics=agg_metrics,
        raw_metrics=all_metrics,
    )


def run_all_experiments(
    rl_model_path: Optional[str] = None,
    num_episodes: int = 50,
    max_steps: int = 200,
    seed: int = 42,
    output_dir: str = "eval_results",
) -> Dict[str, ExperimentResult]:
    """15가지 실험 모두 실행"""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Strategies
    strategies = [
        NoMTDStrategy(),
        HeuristicMTDStrategy(),
    ]

    if rl_model_path and TORCH_AVAILABLE:
        try:
            strategies.append(RLMTDStrategy(rl_model_path))
        except Exception as e:
            print(f"Warning: Failed to load RL model: {e}")

    seeker_levels = [0, 1, 2, 3, 4]
    results = {}

    print("\n" + "=" * 90)
    print("MTD Comparison Evaluation")
    print("=" * 90)
    print(f"Seeker Levels: {seeker_levels}")
    print(f"MTD Strategies: {[s.name for s in strategies]}")
    print(f"Episodes per experiment: {num_episodes}")
    print("=" * 90 + "\n")

    total_experiments = len(seeker_levels) * len(strategies)
    current = 0

    for level in seeker_levels:
        for strategy in strategies:
            current += 1
            level_name = DEFAULT_SEEKER_PROFILES[level]["name"]
            print(f"[{current}/{total_experiments}] Level {level} ({level_name}) + {strategy.name}...", end=" ")

            result = run_experiment(
                seeker_level=level,
                mtd_strategy=strategy,
                num_episodes=num_episodes,
                max_steps=max_steps,
                seed=seed,
            )

            key = f"L{level}_{strategy.name.replace(' ', '_')}"
            results[key] = result
            print(f"S_MTD: {result.metrics.get('Defense/S_MTD_mean', 0):.3f}")

    # Save raw results
    save_results(results, output_path)

    # Generate visualizations
    generate_all_plots(results, output_path)

    print(f"\n✅ Results saved to {output_path}")
    return results


# ---------------------------------------------------------------------------
# Save Results
# ---------------------------------------------------------------------------
def save_results(results: Dict[str, ExperimentResult], output_path: Path):
    """결과 저장 (JSON, CSV)"""
    # JSON
    json_data = {}
    for key, result in results.items():
        json_data[key] = {
            "seeker_level": result.seeker_level,
            "mtd_mode": result.mtd_mode,
            "episodes": result.episodes,
            "metrics": result.metrics,
        }

    with open(output_path / "results.json", "w") as f:
        json.dump(json_data, f, indent=2)

    # CSV
    csv_lines = ["seeker_level,mtd_mode,metric,mean,std"]
    for key, result in results.items():
        for metric_name, value in result.metrics.items():
            if metric_name.endswith("_mean"):
                base_name = metric_name.replace("_mean", "")
                std_name = f"{base_name}_std"
                std_val = result.metrics.get(std_name, 0)
                csv_lines.append(f"{result.seeker_level},{result.mtd_mode},{base_name},{value:.4f},{std_val:.4f}")

    with open(output_path / "results.csv", "w") as f:
        f.write("\n".join(csv_lines))


# ---------------------------------------------------------------------------
# Visualization
# ---------------------------------------------------------------------------
def generate_all_plots(results: Dict[str, ExperimentResult], output_path: Path):
    """모든 그래프 생성"""
    # Key metrics to plot
    metrics_to_plot = [
        ("Defense/S_MTD", "S_MTD Score", True),
        ("Defense/Success", "Defense Success Rate", True),
        ("Attack/ServicesFound", "Services Found by Attacker", False),
        ("Attack/TimeToBreach", "Time to Breach (steps)", True),
        ("Decoy/Hits", "Decoy Engagements", True),
        ("Cost/Total", "Total MTD Cost", False),
        ("Defense/Diversity_Avg", "Average Diversity", True),
        ("Defense/Redundancy", "Redundancy Level", True),
        ("Attack/TotalScans", "Total Attacker Scans", False),
        ("Attack/EffectiveScans", "Effective Scans", False),
        ("Decoy/BlockedScans", "Blocked Scans", True),
        ("Cost/Energy", "Energy Consumed", False),
        ("reward", "Episode Reward", True),
    ]

    levels = [0, 1, 2, 3, 4]
    mtd_modes = ["No MTD", "Heuristic", "RL MTD"]
    mtd_modes = [m for m in mtd_modes if any(r.mtd_mode == m for r in results.values())]

    # 1. Bar charts for each metric
    for metric_name, display_name, higher_better in metrics_to_plot:
        fig, ax = plt.subplots(figsize=(12, 6))

        x = np.arange(len(levels))
        width = 0.25
        colors = ['#ff6b6b', '#4ecdc4', '#45b7d1']

        for i, mode in enumerate(mtd_modes):
            values = []
            errors = []
            for level in levels:
                key = f"L{level}_{mode.replace(' ', '_')}"
                if key in results:
                    values.append(results[key].metrics.get(f"{metric_name}_mean", 0))
                    errors.append(results[key].metrics.get(f"{metric_name}_std", 0))
                else:
                    values.append(0)
                    errors.append(0)

            ax.bar(x + i * width, values, width, label=mode, color=colors[i % len(colors)],
                   yerr=errors, capsize=3, alpha=0.8)

        ax.set_xlabel('Seeker Level', fontsize=12)
        ax.set_ylabel(display_name, fontsize=12)
        ax.set_title(f'{display_name} by Seeker Level and MTD Strategy', fontsize=14)
        ax.set_xticks(x + width)
        ax.set_xticklabels([f"L{l}\n{DEFAULT_SEEKER_PROFILES[l]['name'][:8]}" for l in levels])
        ax.legend()
        ax.grid(axis='y', alpha=0.3)

        plt.tight_layout()
        plt.savefig(output_path / f"bar_{metric_name.replace('/', '_')}.png", dpi=150)
        plt.close()

    # 2. Heatmap for S_MTD
    fig, ax = plt.subplots(figsize=(10, 6))
    heatmap_data = np.zeros((len(mtd_modes), len(levels)))

    for i, mode in enumerate(mtd_modes):
        for j, level in enumerate(levels):
            key = f"L{level}_{mode.replace(' ', '_')}"
            if key in results:
                heatmap_data[i, j] = results[key].metrics.get("Defense/S_MTD_mean", 0)

    im = ax.imshow(heatmap_data, cmap='RdYlGn', aspect='auto')
    ax.set_xticks(np.arange(len(levels)))
    ax.set_yticks(np.arange(len(mtd_modes)))
    ax.set_xticklabels([f"L{l}" for l in levels])
    ax.set_yticklabels(mtd_modes)
    ax.set_xlabel('Seeker Level')
    ax.set_ylabel('MTD Strategy')
    ax.set_title('S_MTD Score Heatmap')

    # Add values
    for i in range(len(mtd_modes)):
        for j in range(len(levels)):
            text = ax.text(j, i, f"{heatmap_data[i, j]:.3f}",
                          ha="center", va="center", color="black", fontsize=10)

    plt.colorbar(im, label='S_MTD Score')
    plt.tight_layout()
    plt.savefig(output_path / "heatmap_s_mtd.png", dpi=150)
    plt.close()

    # 3. Comparison table (text)
    print("\n" + "=" * 100)
    print("COMPARISON TABLE")
    print("=" * 100)
    header = f"{'Level':<12} {'MTD Mode':<12} {'S_MTD':>10} {'Success':>10} {'Found':>8} {'Decoy':>8} {'Cost':>8}"
    print(header)
    print("-" * 100)

    for level in levels:
        for mode in mtd_modes:
            key = f"L{level}_{mode.replace(' ', '_')}"
            if key in results:
                r = results[key]
                level_name = DEFAULT_SEEKER_PROFILES[level]["name"][:10]
                print(f"L{level} {level_name:<9} {mode:<12} "
                      f"{r.metrics.get('Defense/S_MTD_mean', 0):>10.3f} "
                      f"{r.metrics.get('Defense/Success_mean', 0):>10.3f} "
                      f"{r.metrics.get('Attack/ServicesFound_mean', 0):>8.1f} "
                      f"{r.metrics.get('Decoy/Hits_mean', 0):>8.1f} "
                      f"{r.metrics.get('Cost/Total_mean', 0):>8.2f}")

    print("=" * 100)

    # 4. Summary statistics
    print("\n📊 Summary by MTD Mode:")
    for mode in mtd_modes:
        mode_results = [r for r in results.values() if r.mtd_mode == mode]
        if mode_results:
            avg_s_mtd = np.mean([r.metrics.get("Defense/S_MTD_mean", 0) for r in mode_results])
            avg_success = np.mean([r.metrics.get("Defense/Success_mean", 0) for r in mode_results])
            avg_cost = np.mean([r.metrics.get("Cost/Total_mean", 0) for r in mode_results])
            print(f"  {mode}: S_MTD={avg_s_mtd:.3f}, Success={avg_success:.3f}, Cost={avg_cost:.2f}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="MTD Comparison Evaluation")
    parser.add_argument("--rl-model", type=str, default=None, help="Path to trained RL model")
    parser.add_argument("--episodes", type=int, default=50, help="Episodes per experiment")
    parser.add_argument("--max-steps", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output-dir", type=str, default="eval_results")
    args = parser.parse_args()

    run_all_experiments(
        rl_model_path=args.rl_model,
        num_episodes=args.episodes,
        max_steps=args.max_steps,
        seed=args.seed,
        output_dir=args.output_dir,
    )


if __name__ == "__main__":
    main()