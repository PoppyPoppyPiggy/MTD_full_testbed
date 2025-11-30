#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rl_evaluate_v07.py

MTD RL Model Evaluation Script
- Level별 성능 평가
- 상세 통계 출력
- 논문용 결과 테이블 생성
- WandB 로깅 지원

Usage:
    # 단일 모델 평가
    python3 rl_evaluate_v07.py --model checkpoints/best_model.pt

    # 전체 레벨 평가
    python3 rl_evaluate_v07.py --model checkpoints/best_model.pt --all-levels

    # CSV 결과 저장
    python3 rl_evaluate_v07.py --model checkpoints/best_model.pt --all-levels --output results.csv
"""

import os
import sys
import argparse
import json
import time
import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from collections import defaultdict
import csv

import numpy as np
import torch

# Path 설정
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rl_config_v07 import (
    MTDConfig,
    STATE_DIM,
    ACTION_DIM,
    SEEKER_PROFILES,
)
from rl_environment_v07 import MTDEnvironment, StepOutcome
from rl_train_v07 import ActorCritic, PPOAgent


# =============================================================================
# 평가 결과 데이터 구조
# =============================================================================
@dataclass
class EvalResult:
    """단일 에피소드 평가 결과"""
    episode: int
    seeker_level: int
    total_reward: float
    steps: int
    successful_breaches: int
    exploit_attempts: int
    scan_attempts: int
    decoy_engagements: int
    decoy_time_absorbed: int
    total_mtd_cost: float
    defense_success_rate: float
    shuffle_count: int
    port_hop_count: int
    terminated_by_breach: bool
    terminated_by_energy: bool


@dataclass
class LevelStats:
    """레벨별 통계"""
    seeker_level: int
    seeker_name: str
    num_episodes: int
    
    # Reward
    avg_reward: float
    std_reward: float
    min_reward: float
    max_reward: float
    
    # Defense
    avg_breaches: float
    breach_rate: float  # 에피소드 중 breach 발생 비율
    avg_defense_success: float
    
    # Decoy
    avg_decoy_hits: float
    avg_decoy_time: float
    
    # Cost
    avg_cost: float
    avg_cost_per_step: float
    
    # MTD Actions
    avg_shuffles: float
    avg_port_hops: float
    
    # Episode Stats
    avg_steps: float
    completion_rate: float  # 200 스텝까지 생존한 비율


# =============================================================================
# 평가기
# =============================================================================
class ModelEvaluator:
    """MTD RL 모델 평가기"""
    
    def __init__(
        self,
        model_path: str,
        device: str = "cpu",
        seed: int = 42,
    ):
        self.device = device
        self.seed = seed
        self.config = MTDConfig()
        
        # 에이전트 로드
        self.agent = PPOAgent(
            state_dim=STATE_DIM,
            action_dim=ACTION_DIM,
            config=self.config,
            device=device,
        )
        
        if model_path and os.path.exists(model_path):
            print(f"Loading model: {model_path}")
            self.agent.load(model_path)
        else:
            print("⚠️ No model loaded - using random policy")
    
    def evaluate_single_episode(
        self,
        env: MTDEnvironment,
        episode_num: int,
        seeker_level: int,
        deterministic: bool = True,
        verbose: bool = False,
    ) -> EvalResult:
        """단일 에피소드 평가"""
        
        state, _ = env.reset(seed=self.seed + episode_num)
        total_reward = 0
        step = 0
        
        terminated_by_breach = False
        terminated_by_energy = False
        
        for step in range(self.config.ppo.max_steps_per_episode):
            action, _, _ = self.agent.select_action(state, deterministic=deterministic)
            next_state, reward, terminated, truncated, info = env.step(action)
            
            total_reward += reward
            state = next_state
            
            if terminated:
                # 종료 원인 파악
                if info.get("Attack/SuccessfulBreaches", 0) > 0:
                    terminated_by_breach = True
                else:
                    terminated_by_energy = True
                break
            
            if truncated:
                break
        
        return EvalResult(
            episode=episode_num,
            seeker_level=seeker_level,
            total_reward=total_reward,
            steps=step + 1,
            successful_breaches=int(info.get("Attack/SuccessfulBreaches", 0)),
            exploit_attempts=int(info.get("Attack/ExploitAttempts", 0)),
            scan_attempts=int(info.get("Attack/ScanAttempts", 0)),
            decoy_engagements=int(info.get("Decoy/Engagements", 0)),
            decoy_time_absorbed=int(info.get("Decoy/TimeAbsorbed", 0)),
            total_mtd_cost=float(info.get("Cost/Total", 0)),
            defense_success_rate=float(info.get("Defense/R_succ", 0)),
            shuffle_count=int(info.get("MTD/ShuffleCount", 0)),
            port_hop_count=int(info.get("MTD/PortHopCount", 0)),
            terminated_by_breach=terminated_by_breach,
            terminated_by_energy=terminated_by_energy,
        )
    
    def evaluate_level(
        self,
        seeker_level: int,
        num_episodes: int = 50,
        verbose: bool = True,
    ) -> Tuple[LevelStats, List[EvalResult]]:
        """특정 레벨에서 여러 에피소드 평가"""
        
        env = MTDEnvironment(
            seed=self.seed,
            seeker_level=seeker_level,
            config=self.config,
            initial_state_mode="partial_compromise",
        )
        
        results = []
        seeker_name = SEEKER_PROFILES[seeker_level]["name"]
        
        if verbose:
            print(f"\n{'='*60}")
            print(f"Evaluating: Level {seeker_level} ({seeker_name})")
            print(f"Episodes: {num_episodes}")
            print(f"{'='*60}")
        
        for ep in range(num_episodes):
            result = self.evaluate_single_episode(
                env=env,
                episode_num=ep,
                seeker_level=seeker_level,
                deterministic=True,
            )
            results.append(result)
            
            if verbose and (ep + 1) % 10 == 0:
                avg_reward = np.mean([r.total_reward for r in results])
                print(f"  Episode {ep + 1:3d}/{num_episodes} | Avg Reward: {avg_reward:.2f}")
        
        # 통계 계산
        rewards = [r.total_reward for r in results]
        breaches = [r.successful_breaches for r in results]
        decoy_hits = [r.decoy_engagements for r in results]
        decoy_time = [r.decoy_time_absorbed for r in results]
        costs = [r.total_mtd_cost for r in results]
        steps_list = [r.steps for r in results]
        shuffles = [r.shuffle_count for r in results]
        port_hops = [r.port_hop_count for r in results]
        defense_rates = [r.defense_success_rate for r in results]
        
        breach_episodes = sum(1 for r in results if r.successful_breaches > 0)
        completed_episodes = sum(1 for r in results if r.steps >= 200)
        
        stats = LevelStats(
            seeker_level=seeker_level,
            seeker_name=seeker_name,
            num_episodes=num_episodes,
            avg_reward=np.mean(rewards),
            std_reward=np.std(rewards),
            min_reward=np.min(rewards),
            max_reward=np.max(rewards),
            avg_breaches=np.mean(breaches),
            breach_rate=breach_episodes / num_episodes,
            avg_defense_success=np.mean(defense_rates),
            avg_decoy_hits=np.mean(decoy_hits),
            avg_decoy_time=np.mean(decoy_time),
            avg_cost=np.mean(costs),
            avg_cost_per_step=np.mean([c / max(1, s) for c, s in zip(costs, steps_list)]),
            avg_shuffles=np.mean(shuffles),
            avg_port_hops=np.mean(port_hops),
            avg_steps=np.mean(steps_list),
            completion_rate=completed_episodes / num_episodes,
        )
        
        return stats, results
    
    def evaluate_all_levels(
        self,
        num_episodes: int = 50,
        verbose: bool = True,
    ) -> Dict[int, Tuple[LevelStats, List[EvalResult]]]:
        """모든 레벨 평가"""
        
        all_results = {}
        
        for level in range(5):
            stats, results = self.evaluate_level(
                seeker_level=level,
                num_episodes=num_episodes,
                verbose=verbose,
            )
            all_results[level] = (stats, results)
        
        return all_results
    
    def print_summary(self, all_stats: Dict[int, LevelStats]):
        """요약 테이블 출력"""
        
        print("\n" + "="*100)
        print("EVALUATION SUMMARY")
        print("="*100)
        
        # 헤더
        header = f"{'Level':<8} {'Name':<20} {'Reward':>12} {'Breaches':>10} {'Decoy':>8} {'Cost':>10} {'Survival':>10}"
        print(header)
        print("-"*100)
        
        for level in sorted(all_stats.keys()):
            stats = all_stats[level]
            row = (
                f"{stats.seeker_level:<8} "
                f"{stats.seeker_name:<20} "
                f"{stats.avg_reward:>8.2f}±{stats.std_reward:>4.1f} "
                f"{stats.avg_breaches:>10.2f} "
                f"{stats.avg_decoy_hits:>8.2f} "
                f"{stats.avg_cost:>10.2f} "
                f"{stats.completion_rate*100:>9.1f}%"
            )
            print(row)
        
        print("="*100)
    
    def print_detailed_stats(self, stats: LevelStats):
        """상세 통계 출력"""
        
        print(f"\n{'='*60}")
        print(f"Level {stats.seeker_level}: {stats.seeker_name}")
        print(f"{'='*60}")
        
        print(f"\n📊 Reward Statistics:")
        print(f"   Average:  {stats.avg_reward:.2f} ± {stats.std_reward:.2f}")
        print(f"   Min/Max:  {stats.min_reward:.2f} / {stats.max_reward:.2f}")
        
        print(f"\n🛡️ Defense Metrics:")
        print(f"   Breach Rate:       {stats.breach_rate*100:.1f}% of episodes")
        print(f"   Avg Breaches:      {stats.avg_breaches:.2f} per episode")
        print(f"   Defense Success:   {stats.avg_defense_success*100:.1f}%")
        print(f"   Survival Rate:     {stats.completion_rate*100:.1f}%")
        
        print(f"\n🎯 Decoy Effectiveness:")
        print(f"   Avg Engagements:   {stats.avg_decoy_hits:.2f}")
        print(f"   Avg Time Absorbed: {stats.avg_decoy_time:.2f} steps")
        
        print(f"\n💰 Cost Analysis:")
        print(f"   Total Cost:        {stats.avg_cost:.2f}")
        print(f"   Cost per Step:     {stats.avg_cost_per_step:.4f}")
        
        print(f"\n🔀 MTD Actions:")
        print(f"   Avg Shuffles:      {stats.avg_shuffles:.2f}")
        print(f"   Avg Port Hops:     {stats.avg_port_hops:.2f}")
        
        print(f"\n📈 Episode Stats:")
        print(f"   Avg Steps:         {stats.avg_steps:.1f}")
        print(f"   Episodes:          {stats.num_episodes}")
    
    def save_results_csv(
        self,
        all_results: Dict[int, Tuple[LevelStats, List[EvalResult]]],
        output_path: str,
    ):
        """결과를 CSV로 저장"""
        
        # 요약 CSV
        summary_path = output_path.replace(".csv", "_summary.csv")
        with open(summary_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Level", "Name", "Episodes", 
                "Avg_Reward", "Std_Reward", "Min_Reward", "Max_Reward",
                "Breach_Rate", "Avg_Breaches", "Defense_Success",
                "Avg_Decoy_Hits", "Avg_Decoy_Time",
                "Avg_Cost", "Cost_Per_Step",
                "Avg_Shuffles", "Avg_Port_Hops",
                "Avg_Steps", "Completion_Rate"
            ])
            
            for level, (stats, _) in sorted(all_results.items()):
                writer.writerow([
                    stats.seeker_level, stats.seeker_name, stats.num_episodes,
                    f"{stats.avg_reward:.2f}", f"{stats.std_reward:.2f}",
                    f"{stats.min_reward:.2f}", f"{stats.max_reward:.2f}",
                    f"{stats.breach_rate:.4f}", f"{stats.avg_breaches:.2f}",
                    f"{stats.avg_defense_success:.4f}",
                    f"{stats.avg_decoy_hits:.2f}", f"{stats.avg_decoy_time:.2f}",
                    f"{stats.avg_cost:.2f}", f"{stats.avg_cost_per_step:.4f}",
                    f"{stats.avg_shuffles:.2f}", f"{stats.avg_port_hops:.2f}",
                    f"{stats.avg_steps:.1f}", f"{stats.completion_rate:.4f}"
                ])
        
        print(f"✅ Summary saved: {summary_path}")
        
        # 상세 CSV
        detail_path = output_path.replace(".csv", "_detail.csv")
        with open(detail_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Level", "Episode", "Reward", "Steps",
                "Breaches", "Exploits", "Scans",
                "Decoy_Hits", "Decoy_Time",
                "Cost", "Defense_Rate",
                "Shuffles", "Port_Hops",
                "Breach_Term", "Energy_Term"
            ])
            
            for level, (_, results) in sorted(all_results.items()):
                for r in results:
                    writer.writerow([
                        r.seeker_level, r.episode, f"{r.total_reward:.2f}", r.steps,
                        r.successful_breaches, r.exploit_attempts, r.scan_attempts,
                        r.decoy_engagements, r.decoy_time_absorbed,
                        f"{r.total_mtd_cost:.2f}", f"{r.defense_success_rate:.4f}",
                        r.shuffle_count, r.port_hop_count,
                        int(r.terminated_by_breach), int(r.terminated_by_energy)
                    ])
        
        print(f"✅ Details saved: {detail_path}")
    
    def generate_latex_table(
        self,
        all_stats: Dict[int, LevelStats],
    ) -> str:
        """LaTeX 테이블 생성 (논문용)"""
        
        latex = r"""
\begin{table}[h]
\centering
\caption{MTD RL Defense Performance by Attacker Skill Level}
\label{tab:mtd_evaluation}
\begin{tabular}{lccccc}
\hline
\textbf{Attacker Level} & \textbf{Reward} & \textbf{Breach Rate} & \textbf{Decoy Hits} & \textbf{MTD Cost} & \textbf{Survival} \\
\hline
"""
        
        for level in sorted(all_stats.keys()):
            stats = all_stats[level]
            latex += f"L{level} ({stats.seeker_name}) & "
            latex += f"${stats.avg_reward:.1f} \\pm {stats.std_reward:.1f}$ & "
            latex += f"{stats.breach_rate*100:.1f}\\% & "
            latex += f"{stats.avg_decoy_hits:.1f} & "
            latex += f"{stats.avg_cost:.1f} & "
            latex += f"{stats.completion_rate*100:.1f}\\% \\\\\n"
        
        latex += r"""\hline
\end{tabular}
\end{table}
"""
        return latex


# =============================================================================
# 메인
# =============================================================================
def parse_args():
    parser = argparse.ArgumentParser(
        description="MTD RL Model Evaluation Script (v07)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    
    # 모델
    parser.add_argument("--model", type=str, required=True, help="Model path to evaluate")
    
    # 평가 설정
    parser.add_argument("--episodes", type=int, default=50, help="Episodes per level")
    parser.add_argument("--seeker-level", type=int, default=None, choices=[0, 1, 2, 3, 4],
                        help="Specific level to evaluate (default: all)")
    parser.add_argument("--all-levels", action="store_true", help="Evaluate all levels")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--cpu", action="store_true", help="Force CPU")
    
    # 출력
    parser.add_argument("--output", type=str, default=None, help="Output CSV path")
    parser.add_argument("--latex", action="store_true", help="Generate LaTeX table")
    parser.add_argument("--detailed", action="store_true", help="Print detailed stats")
    parser.add_argument("--quiet", action="store_true", help="Minimal output")
    
    # WandB
    parser.add_argument("--wandb", action="store_true", help="Log to WandB")
    parser.add_argument("--project", type=str, default="mtd-rl-v07-eval", help="WandB project")
    
    return parser.parse_args()


def main():
    args = parse_args()
    
    # Device
    device = "cuda" if torch.cuda.is_available() and not args.cpu else "cpu"
    
    # Evaluator
    evaluator = ModelEvaluator(
        model_path=args.model,
        device=device,
        seed=args.seed,
    )
    
    # WandB
    if args.wandb:
        import wandb
        wandb.init(
            project=args.project,
            name=f"eval-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}",
            config={
                "model": args.model,
                "episodes": args.episodes,
                "seed": args.seed,
            },
        )
    
    # 평가 실행
    if args.all_levels or args.seeker_level is None:
        # 모든 레벨 평가
        all_results = evaluator.evaluate_all_levels(
            num_episodes=args.episodes,
            verbose=not args.quiet,
        )
        
        all_stats = {level: stats for level, (stats, _) in all_results.items()}
        
        # 요약 출력
        evaluator.print_summary(all_stats)
        
        # 상세 출력
        if args.detailed:
            for level, (stats, _) in sorted(all_results.items()):
                evaluator.print_detailed_stats(stats)
        
        # CSV 저장
        if args.output:
            evaluator.save_results_csv(all_results, args.output)
        
        # LaTeX 테이블
        if args.latex:
            latex = evaluator.generate_latex_table(all_stats)
            print("\n📄 LaTeX Table:")
            print(latex)
            
            if args.output:
                latex_path = args.output.replace(".csv", ".tex")
                with open(latex_path, "w") as f:
                    f.write(latex)
                print(f"✅ LaTeX saved: {latex_path}")
        
        # WandB 로깅
        if args.wandb:
            for level, stats in all_stats.items():
                wandb.log({
                    f"eval/L{level}_reward": stats.avg_reward,
                    f"eval/L{level}_breach_rate": stats.breach_rate,
                    f"eval/L{level}_decoy_hits": stats.avg_decoy_hits,
                    f"eval/L{level}_cost": stats.avg_cost,
                    f"eval/L{level}_survival": stats.completion_rate,
                })
    else:
        # 단일 레벨 평가
        stats, results = evaluator.evaluate_level(
            seeker_level=args.seeker_level,
            num_episodes=args.episodes,
            verbose=not args.quiet,
        )
        
        evaluator.print_detailed_stats(stats)
    
    if args.wandb:
        wandb.finish()
    
    print("\n✅ Evaluation complete!")


if __name__ == "__main__":
    main()