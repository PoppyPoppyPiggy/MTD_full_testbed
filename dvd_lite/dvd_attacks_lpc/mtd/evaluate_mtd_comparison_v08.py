#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MTD Comparison Evaluation Script v08
====================================

비교 대상:
1. No MTD: 모든 MTD 비활성화 (baseline)
2. Static MTD: 고정 주기 셔플 (시간 기반)
3. Heuristic MTD: 규칙 기반 반응형 (CTI 통합)
4. RL MTD: 학습된 PPO 정책
5. RL-CTI MTD: RL + CTI Agent 연동

실험 설계:
- Seeker Level (0-4) × MTD Mode (5종) = 25 실험
- 각 실험당 50 에피소드
- S_MTD, Breach Prevention Rate, Cost, Diversity 등 측정

저자: MTD-RL Research Team
버전: 0.8.0
"""
from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

# Plotting
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')

# Local imports
from rl_config_v08 import (
    ACTION_DIM,
    ACTION_PARAM_KEYS,
    SEEKER_PROFILES,
    FEATURE_KEYS,
    STATE_DIM,
    EpisodeStats,
    MTDConfig,
)
from rl_environment_v08 import MTDEnvironment

# PyTorch (RL 전략용)
try:
    import torch
    from rl_train_v08 import ActorCritic, PPOAgent
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    print("⚠️ PyTorch not available, RL strategies will be disabled")


# =============================================================================
# MTD Strategies
# =============================================================================
class BaseMTDStrategy:
    """MTD 전략 베이스 클래스"""
    name = "Base"
    
    def reset(self):
        """에피소드 시작 시 호출"""
        pass
    
    def get_action(self, state: np.ndarray, info: Dict = None) -> np.ndarray:
        """
        현재 상태에서 MTD 액션 결정
        
        Args:
            state: 환경 상태 벡터
            info: 추가 정보 (CTI 알림 등)
        
        Returns:
            action: [-1, 1] 범위의 액션 벡터
        """
        raise NotImplementedError


class NoMTDStrategy(BaseMTDStrategy):
    """
    No MTD - 모든 방어 비활성화 (Baseline)
    
    핵심: action = -1 반환 → scaled = 0 → 모든 MTD 비활성화
    
    주의: action = 0은 scaled = 0.5가 되어 중간 강도 MTD가 됨
    """
    name = "No MTD"
    
    def __init__(self):
        self.step = 0
    
    def reset(self):
        self.step = 0
    
    def get_action(self, state: np.ndarray, info: Dict = None) -> np.ndarray:
        self.step += 1
        # 모든 액션을 -1로 설정하여 MTD 완전 비활성화
        return np.ones(ACTION_DIM) * -1.0


class StaticMTDStrategy(BaseMTDStrategy):
    """
    Static MTD - 고정 주기 셔플
    
    특징:
    - 상태와 무관하게 일정 주기로 셔플
    - 가장 단순한 MTD 구현
    - 예측 가능하여 APT에 취약
    """
    name = "Static MTD"
    
    def __init__(
        self, 
        shuffle_period: int = 20,
        shuffle_intensity: float = 0.7,
        decoy_ratio: float = 0.3,
    ):
        self.shuffle_period = shuffle_period
        self.shuffle_intensity = shuffle_intensity
        self.decoy_ratio = decoy_ratio
        self.step = 0
    
    def reset(self):
        self.step = 0
    
    def get_action(self, state: np.ndarray, info: Dict = None) -> np.ndarray:
        self.step += 1
        
        # 기본: 모두 비활성화
        action = np.ones(ACTION_DIM) * -1.0
        
        # 주기적 셔플
        if self.step % self.shuffle_period == 0:
            # shuffle_intensity 0.7 → raw action = 0.7 * 2 - 1 = 0.4
            action[0] = self.shuffle_intensity * 2 - 1
        
        # 디코이는 항상 일정 비율 활성화
        action[2] = self.decoy_ratio * 2 - 1
        
        return action


class HeuristicMTDStrategy(BaseMTDStrategy):
    """
    Heuristic MTD - 규칙 기반 반응형 MTD (CTI 통합)
    
    특징:
    - 상태 기반 규칙으로 MTD 결정
    - CTI 알림에 반응
    - 위협 수준에 따라 강도 조절
    
    규칙 체계:
    1. 주기적 기본 셔플 (25 step)
    2. 스캔 비율 높으면 셔플
    3. 서비스 발견되면 즉시 셔플 + port hop
    4. Critical 발견 시 전면 대응
    5. Exploit 진행 시 디코이 + 블랙리스트
    6. Diversity 낮으면 셔플
    """
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
        
        # 기본: 비활성화
        action = np.ones(ACTION_DIM) * -1.0
        
        # 상태 파싱
        scanned_ratio = state[0]
        services_found = state[1]
        critical_found = state[2]
        exploit_progress = state[3]
        compromise_progress = state[4]
        diversity = state[5]
        steps_since_shuffle = state[9]
        scan_rate = state[10] if len(state) > 10 else 0.0
        
        # CTI 정보 (있으면)
        cti_alert = False
        cti_threat_level = 0.0
        if info and self.cti_enabled:
            cti_alert = info.get("cti_alert", False)
            cti_threat_level = info.get("cti_threat_level", 0.0)
            self.threat_level = max(self.threat_level * 0.9, cti_threat_level)
        
        # === Rule 1: 주기적 기본 셔플 ===
        if self.step - self.last_shuffle_step >= 25:
            action[0] = 0.3  # scaled 0.65
            self.last_shuffle_step = self.step
        
        # === Rule 2: 스캔 비율이 높으면 셔플 ===
        if scanned_ratio > 0.2:
            action[0] = max(action[0], 0.4)
            self.last_shuffle_step = self.step
        
        # === Rule 3: 서비스 발견되면 즉시 셔플 + port hop ===
        if services_found > 0.1:
            action[0] = 0.8  # 강력 셔플
            action[1] = 0.4  # port hop
            self.last_shuffle_step = self.step
        
        # === Rule 4: Critical 발견 시 전면 대응 ===
        if critical_found > 0.5:
            action[0] = 1.0  # 최대 셔플
            action[1] = 0.8  # 최대 port hop
            action[2] = 0.6  # 디코이 활성화
            action[3] = 0.5  # 블랙리스트
            self.last_shuffle_step = self.step
        
        # === Rule 5: Exploit 진행 시 디코이 + 블랙리스트 ===
        if exploit_progress > 0.2:
            action[2] = max(action[2], 0.5)
            action[3] = max(action[3], 0.4)
        
        # === Rule 6: Compromise 진행 시 최대 대응 ===
        if compromise_progress > 0.1:
            action[0] = 1.0
            action[1] = 1.0
            action[2] = 0.8
            action[3] = 0.8
            self.last_shuffle_step = self.step
        
        # === Rule 7: Diversity가 낮으면 셔플 ===
        if diversity < 0.3:
            action[0] = max(action[0], 0.5)
            self.last_shuffle_step = self.step
        
        # === Rule 8: CTI 알림 반응 ===
        if cti_alert and self.cti_enabled:
            # CTI 위협 수준에 비례하여 대응
            action[0] = max(action[0], self.threat_level * 0.8)
            action[3] = max(action[3], self.threat_level * 0.6)
            self.last_shuffle_step = self.step
        
        # === Rule 9: 기본 디코이 유지 ===
        action[2] = max(action[2], -0.3)  # 최소 scaled 0.35
        
        return action


class RLMTDStrategy(BaseMTDStrategy):
    """
    RL MTD - 학습된 PPO 정책
    
    특징:
    - 데이터 기반 최적화
    - 복잡한 상태-액션 매핑 학습
    - 예측 불가능한 방어
    """
    name = "RL MTD"
    
    def __init__(self, model_path: str, device: str = "cpu"):
        if not TORCH_AVAILABLE:
            raise RuntimeError("PyTorch required for RL MTD")
        
        self.device = device
        self.policy = ActorCritic(STATE_DIM, ACTION_DIM).to(device)
        
        # 모델 로드
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
    """
    RL-CTI MTD - RL 정책 + CTI Agent 연동
    
    특징:
    - RL 정책의 기본 결정
    - CTI 탐지 시 boost/override
    - 하이브리드 접근
    """
    name = "RL-CTI MTD"
    
    def __init__(
        self, 
        model_path: str, 
        cti_boost: float = 1.3,
        device: str = "cpu"
    ):
        if not TORCH_AVAILABLE:
            raise RuntimeError("PyTorch required for RL-CTI MTD")
        
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
        
        # CTI 탐지 시 boost
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
    """실험 결과 데이터 클래스"""
    seeker_level: int
    mtd_mode: str
    episodes: int
    metrics: Dict[str, float]
    raw_metrics: List[Dict]


# =============================================================================
# Evaluation Engine
# =============================================================================
def run_single_experiment(
    seeker_level: int,
    mtd_strategy: BaseMTDStrategy,
    num_episodes: int = 50,
    max_steps: int = 200,
    seed: int = 42,
) -> ExperimentResult:
    """단일 실험 실행"""
    
    cfg = MTDConfig()
    all_metrics = []
    
    for ep in range(num_episodes):
        # 환경 생성
        env = MTDEnvironment(
            seed=seed + ep * 100 + seeker_level,
            seeker_level=seeker_level,
            config=cfg,
        )
        
        # 전략 리셋
        mtd_strategy.reset()
        
        # 에피소드 실행
        state, info = env.reset()
        episode_reward = 0.0
        
        for step in range(max_steps):
            action = mtd_strategy.get_action(state, info)
            state, reward, terminated, truncated, info = env.step(action)
            episode_reward += reward
            
            if terminated or truncated:
                break
        
        # 메트릭 저장
        info["reward"] = episode_reward
        info["steps"] = step + 1
        all_metrics.append(info)
    
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
    )


def run_all_experiments(
    rl_model_path: Optional[str] = None,
    num_episodes: int = 50,
    max_steps: int = 200,
    seed: int = 42,
    output_dir: str = "eval_results_v08",
    include_static: bool = True,
    include_rl_cti: bool = False,
) -> Dict[str, ExperimentResult]:
    """모든 실험 실행"""
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # 전략 목록 생성
    strategies: List[BaseMTDStrategy] = [
        NoMTDStrategy(),
    ]
    
    if include_static:
        strategies.append(StaticMTDStrategy(
            shuffle_period=20,
            shuffle_intensity=0.7,
            decoy_ratio=0.3,
        ))
    
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
    
    # 실험 정보 출력
    print("\n" + "=" * 90)
    print("MTD Comparison Evaluation v08")
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
            )
            
            key = f"L{level}_{strategy.name.replace(' ', '_').replace('-', '_')}"
            results[key] = result
            
            s_mtd = result.metrics.get('Defense/S_MTD_mean', 0)
            breach_prevented = result.metrics.get('Defense/BreachPrevented_mean', 0)
            print(f"S_MTD: {s_mtd:.3f} | Breach Prevented: {breach_prevented:.1%}")
    
    # 결과 저장
    save_results(results, output_path)
    
    # 시각화
    generate_all_plots(results, output_path)
    
    print(f"\n✅ Results saved to {output_path}")
    return results


# =============================================================================
# Results Saving
# =============================================================================
def save_results(results: Dict[str, ExperimentResult], output_path: Path):
    """결과 저장"""
    
    def convert_to_serializable(obj):
        if isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        return obj
    
    # JSON
    json_data = {}
    for key, result in results.items():
        json_data[key] = {
            "seeker_level": result.seeker_level,
            "mtd_mode": result.mtd_mode,
            "episodes": result.episodes,
            "metrics": {
                k: convert_to_serializable(v) 
                for k, v in result.metrics.items()
            },
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
                csv_lines.append(
                    f"{result.seeker_level},{result.mtd_mode},"
                    f"{base_name},{value:.4f},{std_val:.4f}"
                )
    
    with open(output_path / "results.csv", "w") as f:
        f.write("\n".join(csv_lines))


# =============================================================================
# Visualization
# =============================================================================
def generate_all_plots(results: Dict[str, ExperimentResult], output_path: Path):
    """모든 시각화 생성"""
    
    # 측정 지표
    metrics_to_plot = [
        ("Defense/S_MTD", "S_MTD Score", True),
        ("Defense/BreachPrevented", "Breach Prevention Rate", True),
        ("Defense/Success", "Defense Success Rate", True),
        ("Attack/ServicesFound", "Services Found by Attacker", False),
        ("Attack/TimeToBreach", "Time to Breach (steps)", True),
        ("Decoy/Hits", "Decoy Engagements", True),
        ("Cost/Total", "Total MTD Cost", False),
        ("Defense/Diversity_Avg", "Average Diversity", True),
        ("reward", "Episode Reward", True),
        ("steps", "Episode Length", True),
    ]
    
    levels = [0, 1, 2, 3, 4]
    
    # MTD 모드 감지
    mtd_modes = list(set(r.mtd_mode for r in results.values()))
    mode_order = ["No MTD", "Static MTD", "Heuristic MTD", "RL MTD", "RL-CTI MTD"]
    mtd_modes = [m for m in mode_order if m in mtd_modes]
    
    # 색상 맵
    colors = {
        "No MTD": '#e74c3c',
        "Static MTD": '#f39c12',
        "Heuristic MTD": '#2ecc71',
        "RL MTD": '#3498db',
        "RL-CTI MTD": '#9b59b6',
    }
    
    # 1. Bar Charts
    for metric_name, display_name, higher_better in metrics_to_plot:
        fig, ax = plt.subplots(figsize=(14, 7))
        
        x = np.arange(len(levels))
        width = 0.8 / len(mtd_modes)
        
        for i, mode in enumerate(mtd_modes):
            values = []
            errors = []
            
            for level in levels:
                key = f"L{level}_{mode.replace(' ', '_').replace('-', '_')}"
                if key in results:
                    values.append(results[key].metrics.get(f"{metric_name}_mean", 0))
                    errors.append(results[key].metrics.get(f"{metric_name}_std", 0))
                else:
                    values.append(0)
                    errors.append(0)
            
            offset = (i - len(mtd_modes) / 2 + 0.5) * width
            ax.bar(
                x + offset, values, width, 
                label=mode, 
                color=colors.get(mode, '#999999'),
                yerr=errors, 
                capsize=3, 
                alpha=0.85
            )
        
        ax.set_xlabel('Seeker Level', fontsize=12)
        ax.set_ylabel(display_name, fontsize=12)
        ax.set_title(f'{display_name} by Seeker Level and MTD Strategy', fontsize=14, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels([
            f"L{l}\n{SEEKER_PROFILES[l]['name'][:10]}" 
            for l in levels
        ])
        ax.legend(loc='best')
        ax.grid(axis='y', alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(output_path / f"bar_{metric_name.replace('/', '_')}.png", dpi=150)
        plt.close()
    
    # 2. Heatmap
    fig, ax = plt.subplots(figsize=(12, 8))
    heatmap_data = np.zeros((len(mtd_modes), len(levels)))
    
    for i, mode in enumerate(mtd_modes):
        for j, level in enumerate(levels):
            key = f"L{level}_{mode.replace(' ', '_').replace('-', '_')}"
            if key in results:
                heatmap_data[i, j] = results[key].metrics.get("Defense/S_MTD_mean", 0)
    
    im = ax.imshow(heatmap_data, cmap='RdYlGn', aspect='auto', vmin=0, vmax=1)
    ax.set_xticks(np.arange(len(levels)))
    ax.set_yticks(np.arange(len(mtd_modes)))
    ax.set_xticklabels([f"L{l}" for l in levels])
    ax.set_yticklabels(mtd_modes)
    ax.set_xlabel('Seeker Level', fontsize=12)
    ax.set_ylabel('MTD Strategy', fontsize=12)
    ax.set_title('S_MTD Score Heatmap', fontsize=14, fontweight='bold')
    
    for i in range(len(mtd_modes)):
        for j in range(len(levels)):
            ax.text(
                j, i, f"{heatmap_data[i, j]:.3f}",
                ha="center", va="center", 
                color="black", fontsize=11, fontweight='bold'
            )
    
    plt.colorbar(im, label='S_MTD Score')
    plt.tight_layout()
    plt.savefig(output_path / "heatmap_s_mtd.png", dpi=150)
    plt.close()
    
    # 3. Trade-off Plot (Cost vs Performance)
    fig, ax = plt.subplots(figsize=(10, 8))
    
    for mode in mtd_modes:
        costs = []
        performances = []
        
        for level in levels:
            key = f"L{level}_{mode.replace(' ', '_').replace('-', '_')}"
            if key in results:
                costs.append(results[key].metrics.get("Cost/Total_mean", 0))
                performances.append(results[key].metrics.get("Defense/S_MTD_mean", 0))
        
        if costs and performances:
            ax.scatter(
                costs, performances, 
                label=mode, 
                color=colors.get(mode, '#999999'),
                s=100, 
                alpha=0.7
            )
            
            # 레벨 레이블
            for j, level in enumerate(levels):
                if j < len(costs):
                    ax.annotate(
                        f"L{level}", 
                        (costs[j], performances[j]),
                        textcoords="offset points", 
                        xytext=(5, 5),
                        fontsize=8
                    )
    
    ax.set_xlabel('Total Cost', fontsize=12)
    ax.set_ylabel('S_MTD Score (Performance)', fontsize=12)
    ax.set_title('Cost-Performance Trade-off', fontsize=14, fontweight='bold')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(output_path / "tradeoff_cost_performance.png", dpi=150)
    plt.close()
    
    # 4. 비교 테이블 출력
    print("\n" + "=" * 120)
    print("COMPARISON TABLE")
    print("=" * 120)
    
    header = (
        f"{'Level':<15} {'MTD Mode':<15} {'S_MTD':>10} {'Breach%':>10} "
        f"{'Defense%':>10} {'Found':>8} {'Decoy':>8} {'Cost':>8} {'Reward':>10}"
    )
    print(header)
    print("-" * 120)
    
    for level in levels:
        for mode in mtd_modes:
            key = f"L{level}_{mode.replace(' ', '_').replace('-', '_')}"
            if key in results:
                r = results[key]
                level_name = SEEKER_PROFILES[level]["name"][:12]
                print(
                    f"L{level} {level_name:<12} {mode:<15} "
                    f"{r.metrics.get('Defense/S_MTD_mean', 0):>10.3f} "
                    f"{r.metrics.get('Defense/BreachPrevented_mean', 0)*100:>9.1f}% "
                    f"{r.metrics.get('Defense/Success_mean', 0)*100:>9.1f}% "
                    f"{r.metrics.get('Attack/ServicesFound_mean', 0):>8.1f} "
                    f"{r.metrics.get('Decoy/Hits_mean', 0):>8.1f} "
                    f"{r.metrics.get('Cost/Total_mean', 0):>8.2f} "
                    f"{r.metrics.get('reward_mean', 0):>10.1f}"
                )
    
    print("=" * 120)
    
    # 5. 요약 통계
    print("\n📊 Summary by MTD Mode (Averaged across all levels):")
    for mode in mtd_modes:
        mode_results = [r for r in results.values() if r.mtd_mode == mode]
        if mode_results:
            avg_s_mtd = np.mean([
                r.metrics.get("Defense/S_MTD_mean", 0) 
                for r in mode_results
            ])
            avg_breach = np.mean([
                r.metrics.get("Defense/BreachPrevented_mean", 0) 
                for r in mode_results
            ])
            avg_cost = np.mean([
                r.metrics.get("Cost/Total_mean", 0) 
                for r in mode_results
            ])
            avg_reward = np.mean([
                r.metrics.get("reward_mean", 0) 
                for r in mode_results
            ])
            print(
                f"  {mode:<15}: S_MTD={avg_s_mtd:.3f}, "
                f"Breach Prev={avg_breach:.1%}, "
                f"Cost={avg_cost:.2f}, "
                f"Reward={avg_reward:.1f}"
            )


# =============================================================================
# CLI
# =============================================================================
def main():
    parser = argparse.ArgumentParser(description="MTD Comparison Evaluation v08")
    
    parser.add_argument(
        "--rl-model", type=str, default=None,
        help="Path to trained RL model"
    )
    parser.add_argument(
        "--episodes", type=int, default=50,
        help="Episodes per experiment"
    )
    parser.add_argument("--max-steps", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--output-dir", type=str, default="eval_results_v08"
    )
    parser.add_argument(
        "--include-static", action="store_true", default=True,
        help="Include Static MTD"
    )
    parser.add_argument(
        "--include-rl-cti", action="store_true",
        help="Include RL-CTI MTD"
    )
    
    args = parser.parse_args()
    
    run_all_experiments(
        rl_model_path=args.rl_model,
        num_episodes=args.episodes,
        max_steps=args.max_steps,
        seed=args.seed,
        output_dir=args.output_dir,
        include_static=args.include_static,
        include_rl_cti=args.include_rl_cti,
    )


if __name__ == "__main__":
    main()