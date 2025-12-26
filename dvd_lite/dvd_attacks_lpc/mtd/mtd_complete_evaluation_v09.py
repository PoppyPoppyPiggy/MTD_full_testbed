#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MTD Complete Evaluation v09 - Full Evaluation Pipeline with IEEE Figures
=========================================================================

학습된 모델을 다양한 전략과 비교 평가하고 IEEE Access 스타일 그래프 생성.

Features:
1. 5가지 전략 비교 (No MTD, Static, Heuristic+CTI, RL, RL+CTI)
2. 5단계 공격자 레벨 (L0-L4) 평가
3. 학술적 MTD 지표 계산 (MTTC, ASR, CDI, NED, DES, CER)
4. IEEE Access 스타일 그래프 및 LaTeX 테이블 자동 생성

Usage:
    # 기본 평가 (50 에피소드)
    python mtd_complete_evaluation_v09.py --model checkpoints_v09/best.pt
    
    # 상세 평가 (100 에피소드)
    python mtd_complete_evaluation_v09.py --model checkpoints_v09/best.pt --episodes 100
    
    # 그래프만 생성 (기존 결과 사용)
    python mtd_complete_evaluation_v09.py --results-json eval_results.json --figures-only

저자: MTD-RL Research Team
버전: 0.9.0
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any

import numpy as np
import torch
import torch.nn as nn

# 환경 및 설정 임포트
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
    sys.exit(1)

# IEEE Figure Utils
try:
    from ieee_figure_utils import (
        generate_all_figures,
        plot_strategy_comparison,
        plot_level_comparison,
        plot_des_heatmap,
        plot_tradeoff_analysis,
        plot_statistical_comparison,
        plot_attacker_profiles,
        generate_latex_table_overall,
        generate_latex_table_improvement,
        generate_latex_table_attacker,
        setup_ieee_style,
    )
    IEEE_FIGURES_AVAILABLE = True
except ImportError:
    IEEE_FIGURES_AVAILABLE = False
    print("⚠️ ieee_figure_utils not found. Install it or ensure it's in the same directory.")


# =============================================================================
# Actor-Critic Network (학습 코드와 동일)
# =============================================================================
class ActorCritic(nn.Module):
    def __init__(self, state_dim: int, action_dim: int, hidden_size: int = 256, num_layers: int = 2):
        super().__init__()
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.hidden_size = hidden_size

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

        self.actor = nn.Sequential(
            nn.Linear(hidden_size, hidden_size // 2),
            nn.ReLU(),
            nn.Linear(hidden_size // 2, action_dim),
            nn.Tanh(),
        )
        self.log_std = nn.Parameter(torch.ones(action_dim) * -0.5)
        self.critic = nn.Sequential(
            nn.Linear(hidden_size, hidden_size // 2),
            nn.ReLU(),
            nn.Linear(hidden_size // 2, 1),
        )

    def forward(self, state):
        features = self.shared(state)
        return self.actor(features), self.critic(features)

    def act(self, state, deterministic: bool = True):
        action_mean, value = self.forward(state)
        if deterministic:
            return action_mean, torch.zeros(1), value
        from torch.distributions import Normal
        std = torch.exp(self.log_std)
        dist = Normal(action_mean, std)
        action = dist.sample()
        action = torch.clamp(action, -1, 1)
        log_prob = dist.log_prob(action).sum(dim=-1, keepdim=True)
        return action, log_prob, value


# =============================================================================
# Evaluation Strategies
# =============================================================================
class BaseStrategy:
    """전략 베이스 클래스"""
    name = "Base"
    
    def get_action(self, state: np.ndarray) -> np.ndarray:
        raise NotImplementedError
    
    def reset(self):
        pass


class NoMTDStrategy(BaseStrategy):
    """No MTD (Baseline) - 아무런 방어 액션 없음"""
    name = "No MTD"
    
    def get_action(self, state: np.ndarray) -> np.ndarray:
        return np.array([-1.0] * ACTION_DIM)


class StaticMTDStrategy(BaseStrategy):
    """Static MTD - 고정 주기로 MTD 액션 수행"""
    name = "Static MTD"
    
    def __init__(self):
        self.step = 0
    
    def get_action(self, state: np.ndarray) -> np.ndarray:
        self.step += 1
        action = np.array([-1.0] * ACTION_DIM)
        
        # 30스텝마다 shuffle + port_hop
        if self.step % 30 == 0:
            action[0] = 0.5  # shuffle_intensity
            action[1] = 0.3  # port_hop_intensity
        
        # 60스텝마다 service swap
        if self.step % 60 == 0:
            action[5] = 0.4  # service_swap_intensity
        
        # 항상 약간의 decoy
        action[2] = 0.3  # decoy_ratio
        
        return action
    
    def reset(self):
        self.step = 0


class HeuristicCTIStrategy(BaseStrategy):
    """Heuristic+CTI - 위협 수준에 따른 규칙 기반 대응"""
    name = "Heuristic+CTI"
    
    def __init__(self):
        self.step = 0
    
    def get_action(self, state: np.ndarray) -> np.ndarray:
        self.step += 1
        action = np.array([-0.5] * ACTION_DIM)
        
        # 위협 수준 추출 (state[12] ≈ scan_rate)
        threat_level = state[12] if len(state) > 12 else 0.3
        discovered_ratio = state[1] if len(state) > 1 else 0.0
        
        # 위협 수준에 따른 대응
        if threat_level > 0.6 or discovered_ratio > 0.3:
            action[0] = 0.7  # 강한 shuffle
            action[2] = 0.6  # 많은 decoy
            action[5] = 0.5  # swap
        elif threat_level > 0.3 or discovered_ratio > 0.1:
            action[0] = 0.4
            action[2] = 0.4
        
        # 주기적 방어
        if self.step % 20 == 0:
            action[0] = max(action[0], 0.5)
            action[1] = 0.3
        
        return action
    
    def reset(self):
        self.step = 0


class RLOnlyStrategy(BaseStrategy):
    """RL MTD - 학습된 모델 사용하되 CTI 정보 무시"""
    name = "RL MTD"
    
    def __init__(self, model_path: str = None, device: str = "cpu", hidden_size: int = 256):
        self.device = device
        self.use_model = False
        
        if model_path and os.path.exists(model_path):
            self.policy = ActorCritic(STATE_DIM, ACTION_DIM, hidden_size).to(device)
            checkpoint = torch.load(model_path, map_location=device, weights_only=False)
            if "policy" in checkpoint:
                self.policy.load_state_dict(checkpoint["policy"])
            else:
                self.policy.load_state_dict(checkpoint)
            self.policy.eval()
            self.use_model = True
    
    def get_action(self, state: np.ndarray) -> np.ndarray:
        if self.use_model:
            # CTI 관련 상태를 0으로 마스킹 (인덱스 13-16)
            state_masked = state.copy()
            if len(state_masked) > 13:
                state_masked[13:] = 0.0
            
            state_tensor = torch.FloatTensor(state_masked).unsqueeze(0).to(self.device)
            with torch.no_grad():
                action, _, _ = self.policy.act(state_tensor, deterministic=True)
            return action.cpu().numpy().squeeze()
        else:
            # 폴백
            return np.array([0.3, 0.2, 0.4, 0.0, 0.0, 0.3, 0.0])


class RLCTIStrategy(BaseStrategy):
    """RL+CTI MTD - 학습된 모델 (전체 상태 사용)"""
    name = "RL+CTI MTD"
    
    def __init__(self, model_path: str, device: str = "cpu", hidden_size: int = 256):
        self.device = device
        
        self.policy = ActorCritic(STATE_DIM, ACTION_DIM, hidden_size).to(device)
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


# =============================================================================
# Evaluator
# =============================================================================
class ComprehensiveEvaluator:
    """종합 평가기"""
    
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
        self.strategies["RL+CTI MTD"] = RLCTIStrategy(model_path, device, hidden_size)
        
        self.results = {}
        self.detailed_results = {}
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
        start_time = time.time()
        
        print(f"\n{'='*70}")
        print("MTD Comprehensive Evaluation v09")
        print(f"{'='*70}")
        print(f"Strategies: {list(self.strategies.keys())}")
        print(f"Levels: {levels}")
        print(f"Episodes per config: {self.episodes_per_config}")
        print(f"{'='*70}\n")
        
        for strategy_name, strategy in self.strategies.items():
            for level in levels:
                current += 1
                
                episode_results = []
                for ep in range(self.episodes_per_config):
                    ep_seed = self.seed + current * 1000 + ep
                    result = self.run_episode(strategy, level, ep_seed)
                    episode_results.append(result)
                
                # 집계 (평균 및 표준편차)
                agg = {
                    "strategy": strategy_name,
                    "level": level,
                    "breach_rate": np.mean([r["breach"] for r in episode_results]) * 100,
                    "breach_rate_std": np.std([r["breach"] for r in episode_results]) * 100,
                    "s_mtd": np.mean([r["s_mtd"] for r in episode_results]),
                    "s_mtd_std": np.std([r["s_mtd"] for r in episode_results]),
                    "mttc": np.mean([r["mttc"] for r in episode_results]),
                    "mttc_std": np.std([r["mttc"] for r in episode_results]),
                    "asr": np.mean([r["asr"] for r in episode_results]),
                    "asr_std": np.std([r["asr"] for r in episode_results]),
                    "cdi": np.mean([r["cdi"] for r in episode_results]),
                    "cdi_std": np.std([r["cdi"] for r in episode_results]),
                    "ned": np.mean([r["ned"] for r in episode_results]),
                    "cost": np.mean([r["cost"] for r in episode_results]),
                    "cost_std": np.std([r["cost"] for r in episode_results]),
                    "cer": np.mean([r["cer"] for r in episode_results]),
                    "cer_std": np.std([r["cer"] for r in episode_results]),
                    "redundancy": np.mean([r["redundancy"] for r in episode_results]),
                    "reward": np.mean([r["reward"] for r in episode_results]),
                }
                
                self.results[(strategy_name, level)] = agg
                
                if verbose:
                    breach_count = sum(1 for r in episode_results if r["breach"] > 0.5)
                    elapsed = time.time() - start_time
                    print(f"[{current:2d}/{total_configs}] {strategy_name:<15} vs L{level}: "
                          f"Breach={breach_count:2d}/{self.episodes_per_config}, "
                          f"DES={agg['s_mtd']:.3f}, MTTC={agg['mttc']:.0f}, "
                          f"Cost={agg['cost']:.2f} ({elapsed:.0f}s)")
        
        return self.results
    
    def get_summary_by_strategy(self) -> Dict:
        """전략별 평균 집계"""
        summary = {}
        for strategy_name in self.strategies.keys():
            strategy_results = [v for (s, l), v in self.results.items() if s == strategy_name]
            if strategy_results:
                summary[strategy_name] = {
                    "s_mtd": np.mean([r["s_mtd"] for r in strategy_results]),
                    "s_mtd_std": np.mean([r["s_mtd_std"] for r in strategy_results]),
                    "breach_rate": np.mean([r["breach_rate"] for r in strategy_results]),
                    "breach_rate_std": np.mean([r["breach_rate_std"] for r in strategy_results]),
                    "mttc": np.mean([r["mttc"] for r in strategy_results]),
                    "mttc_std": np.mean([r["mttc_std"] for r in strategy_results]),
                    "asr": np.mean([r["asr"] for r in strategy_results]),
                    "cdi": np.mean([r["cdi"] for r in strategy_results]),
                    "ned": np.mean([r["ned"] for r in strategy_results]),
                    "cost": np.mean([r["cost"] for r in strategy_results]),
                    "cost_std": np.mean([r["cost_std"] for r in strategy_results]),
                    "cer": np.mean([r["cer"] for r in strategy_results]),
                    "cer_std": np.mean([r["cer_std"] for r in strategy_results]),
                    "redundancy": np.mean([r["redundancy"] for r in strategy_results]),
                    "reward": np.mean([r["reward"] for r in strategy_results]),
                }
        return summary
    
    def get_level_results(self) -> Dict[str, Dict[int, Dict]]:
        """전략별, 레벨별 결과"""
        level_results = {}
        for strategy_name in self.strategies.keys():
            level_results[strategy_name] = {}
            for (s, l), v in self.results.items():
                if s == strategy_name:
                    level_results[strategy_name][l] = v
        return level_results


# =============================================================================
# Figure Generation
# =============================================================================
def generate_evaluation_figures(
    summary: Dict,
    level_results: Dict,
    output_dir: str,
):
    """평가 결과로 IEEE 스타일 그래프 생성"""
    if not IEEE_FIGURES_AVAILABLE:
        print("⚠️ ieee_figure_utils not available. Skipping figure generation.")
        return
    
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(f'{output_dir}/tables', exist_ok=True)
    
    print("\n" + "="*60)
    print("📊 Generating IEEE Access Figures")
    print("="*60)
    
    # 1. Attacker Profiles
    print("\n[1/7] Attacker Profiles...")
    plot_attacker_profiles(f'{output_dir}/fig06_attacker_profiles')
    generate_latex_table_attacker(f'{output_dir}/tables/table_attacker.tex')
    
    # 2. Strategy Comparison (Main Result)
    print("[2/7] Strategy Comparison (Main Result)...")
    plot_strategy_comparison(summary, f'{output_dir}/fig09_strategy_comparison')
    
    # 3. Level Comparison
    print("[3/7] Level Comparison...")
    plot_level_comparison(level_results, f'{output_dir}/fig10_level_comparison')
    
    # 4. DES Heatmap
    print("[4/7] DES Heatmap...")
    plot_des_heatmap(level_results, f'{output_dir}/fig11_des_heatmap')
    
    # 5. Trade-off Analysis
    print("[5/7] Trade-off Analysis...")
    plot_tradeoff_analysis(summary, f'{output_dir}/fig12_tradeoff_analysis')
    
    # 6. Statistical Comparison
    print("[6/7] Statistical Comparison...")
    plot_statistical_comparison(summary, f'{output_dir}/fig13_statistical_comparison')
    
    # 7. LaTeX Tables
    print("[7/7] LaTeX Tables...")
    generate_latex_table_overall(summary, f'{output_dir}/tables/table_overall.tex')
    generate_latex_table_improvement(summary, f'{output_dir}/tables/table_improvement.tex')
    
    print("\n" + "="*60)
    print(f"✅ All figures saved to: {output_dir}/")
    print("="*60)


# =============================================================================
# Main
# =============================================================================
def main():
    parser = argparse.ArgumentParser(description="MTD Complete Evaluation v09 with IEEE Figures")
    parser.add_argument("--model", type=str, required=False, help="Path to best.pt")
    parser.add_argument("--episodes", type=int, default=50, help="Episodes per config")
    parser.add_argument("--max-steps", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--hidden-size", type=int, default=256)
    parser.add_argument("--output-dir", type=str, default="paper_figures")
    parser.add_argument("--levels", type=int, nargs="+", default=[0, 1, 2, 3, 4])
    parser.add_argument("--device", type=str, default="cpu")
    
    # 결과 재사용 옵션
    parser.add_argument("--results-json", type=str, default=None, help="기존 결과 JSON 로드")
    parser.add_argument("--figures-only", action="store_true", help="그래프만 생성")
    
    args = parser.parse_args()
    
    # 기존 결과 로드 또는 새로 평가
    if args.results_json and os.path.exists(args.results_json):
        print(f"📂 Loading existing results from: {args.results_json}")
        with open(args.results_json, 'r') as f:
            saved_data = json.load(f)
        
        summary = saved_data.get("summary", {})
        level_results = saved_data.get("by_level", {})
        
        # Convert string keys back to int for levels
        for strategy in level_results:
            level_results[strategy] = {int(k): v for k, v in level_results[strategy].items()}
    
    else:
        if not args.model:
            print("❌ --model required for evaluation (or use --results-json)")
            return
        
        # 평가 실행
        evaluator = ComprehensiveEvaluator(
            model_path=args.model,
            episodes_per_config=args.episodes,
            max_steps=args.max_steps,
            seed=args.seed,
            hidden_size=args.hidden_size,
            device=args.device,
        )
        
        evaluator.evaluate(levels=args.levels, verbose=True)
        
        summary = evaluator.get_summary_by_strategy()
        level_results = evaluator.get_level_results()
        
        # 결과 요약 출력
        print("\n" + "="*90)
        print("📈 Summary Results")
        print("="*90)
        print(f"\n{'Strategy':<18} {'DES':>10} {'Breach%':>10} {'MTTC':>10} {'CER':>10} {'Cost':>10}")
        print("-"*90)
        for strategy, metrics in summary.items():
            print(f"{strategy:<18} {metrics['s_mtd']:>10.3f} {metrics['breach_rate']:>9.1f}% "
                  f"{metrics['mttc']:>10.0f} {metrics['cer']:>10.2f} {metrics['cost']:>10.3f}")
        
        # 결과 저장
        results_data = {
            "timestamp": datetime.now().isoformat(),
            "config": {
                "episodes_per_config": args.episodes,
                "max_steps": args.max_steps,
                "seed": args.seed,
                "model_path": args.model,
            },
            "summary": summary,
            "by_level": {s: {str(l): v for l, v in levels.items()} 
                        for s, levels in level_results.items()},
        }
        
        results_path = f'{args.output_dir}/evaluation_results.json'
        os.makedirs(args.output_dir, exist_ok=True)
        with open(results_path, 'w') as f:
            json.dump(results_data, f, indent=2, default=float)
        print(f"\n✅ Results saved: {results_path}")
    
    # IEEE 그래프 생성
    generate_evaluation_figures(summary, level_results, args.output_dir)
    
    print("\n" + "="*70)
    print("✅ Evaluation Complete!")
    print("="*70)


if __name__ == "__main__":
    main()