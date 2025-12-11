#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MTD Scenario-Based Evaluation Script v08.7

시나리오 기반 평가:
1. 다양한 공격 시나리오 (reconnaissance, gps_spoofing, command_injection 등)
2. 레벨별 공격자 시뮬레이션
3. MTD 전략 비교 평가

[v0.8.7] 수정사항:
- HeuristicMTDStrategy가 실제 shuffle/swap 액션 수행
- MTD 액션 카운트 추적
- Diversity/Redundancy/Shuffle 통계 포함

저자: MTD-RL Research Team
버전: 0.8.7
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import random
import sys
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from collections import defaultdict

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

try:
    import wandb
    WANDB_AVAILABLE = True
except ImportError:
    WANDB_AVAILABLE = False

# 프로젝트 모듈
from rl_config_v08 import MTDConfig, SEEKER_PROFILES, STATE_DIM, ACTION_DIM, to_serializable
from rl_environment_v08 import MTDEnvironment

if TORCH_AVAILABLE:
    from rl_train_v08 import ActorCritic

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)-7s] [MTD-Controller] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


# =============================================================================
# 시나리오 정의
# =============================================================================
SCENARIOS = {
    "reconnaissance": {
        "name": "Network Reconnaissance",
        "description": "네트워크 스캔 및 정찰 공격",
        "seeker_levels": [0, 1],
        "attack_phases": ["scan", "enumerate"],
        "difficulty": 1.0
    },
    "gps_spoofing": {
        "name": "GPS Spoofing Attack",
        "description": "GPS 위변조 공격",
        "seeker_levels": [2, 3],
        "attack_phases": ["intercept", "spoof", "manipulate"],
        "difficulty": 1.5
    },
    "command_injection": {
        "name": "MAVLink Command Injection",
        "description": "MAVLink 명령 주입 공격",
        "seeker_levels": [2, 3],
        "attack_phases": ["intercept", "inject", "control"],
        "difficulty": 1.8
    },
    "dos_attack": {
        "name": "DoS Attack",
        "description": "서비스 거부 공격",
        "seeker_levels": [1, 2],
        "attack_phases": ["flood", "exhaust"],
        "difficulty": 1.3
    },
    "data_exfiltration": {
        "name": "Data Exfiltration",
        "description": "데이터 유출 공격",
        "seeker_levels": [1, 2],
        "attack_phases": ["access", "extract", "exfil"],
        "difficulty": 1.4
    },
    "critical_attack": {
        "name": "Critical Flight Safety Attack",
        "description": "비행 안전 위협 공격",
        "seeker_levels": [3, 4],
        "attack_phases": ["compromise", "control", "crash"],
        "difficulty": 2.0
    },
    "mixed_apt": {
        "name": "Mixed APT Campaign",
        "description": "APT 복합 공격",
        "seeker_levels": [3, 4],
        "attack_phases": ["recon", "establish", "lateral", "exfil"],
        "difficulty": 2.5
    }
}


# =============================================================================
# MTD 전략 클래스 - [v0.8.7] 수정됨
# =============================================================================
class BaseMTDStrategy:
    """기본 MTD 전략"""
    name = "Base"
    
    def __init__(self, config: MTDConfig):
        self.config = config
        self.step = 0
        self.shuffle_count = 0
        self.swap_count = 0
        self.total_cost = 0.0
        
    def reset(self):
        self.step = 0
        self.shuffle_count = 0
        self.swap_count = 0
        self.total_cost = 0.0
        
    def get_action(self, state: np.ndarray, info: Dict = None) -> np.ndarray:
        raise NotImplementedError
        
    def get_stats(self) -> Dict[str, Any]:
        return {
            "shuffle_count": self.shuffle_count,
            "swap_count": self.swap_count,
            "total_cost": self.total_cost,
        }


class NoMTDStrategy(BaseMTDStrategy):
    """MTD 없음"""
    name = "No MTD"
    
    def get_action(self, state: np.ndarray, info: Dict = None) -> np.ndarray:
        self.step += 1
        return np.ones(ACTION_DIM) * -1.0


class StaticMTDStrategy(BaseMTDStrategy):
    """Static MTD - 고정 주기 shuffle"""
    name = "Static MTD"
    
    def __init__(self, config: MTDConfig, interval: int = 15, intensity: float = 0.6):
        super().__init__(config)
        self.interval = interval
        self.intensity = intensity
        
    def get_action(self, state: np.ndarray, info: Dict = None) -> np.ndarray:
        self.step += 1
        action = np.ones(ACTION_DIM) * -1.0
        
        if self.step % self.interval == 0:
            action[0] = self.intensity * 2 - 1
            self.shuffle_count += 1
            self.total_cost += self.intensity * 0.5
            
        action[2] = 0.3 * 2 - 1  # Decoy
        return action


class HeuristicCTIMTDStrategy(BaseMTDStrategy):
    """
    Heuristic+CTI MTD - 위협 기반 규칙
    
    [v0.8.7] 실제 shuffle/swap 액션 수행
    """
    name = "Heuristic+CTI MTD"
    
    def __init__(self, config: MTDConfig):
        super().__init__(config)
        self.last_shuffle_step = 0
        self.last_swap_step = 0
        self.threat_level = 0.0
        self.min_interval = 3
        
    def reset(self):
        super().reset()
        self.last_shuffle_step = 0
        self.last_swap_step = 0
        self.threat_level = 0.0
        
    def get_action(self, state: np.ndarray, info: Dict = None) -> np.ndarray:
        self.step += 1
        action = np.ones(ACTION_DIM) * -1.0
        
        # State 파싱
        scanned_ratio = state[0] if len(state) > 0 else 0.0
        services_found = state[1] if len(state) > 1 else 0.0
        critical_found = state[2] if len(state) > 2 else 0.0
        exploit_progress = state[3] if len(state) > 3 else 0.0
        compromise_progress = state[4] if len(state) > 4 else 0.0
        diversity = state[5] if len(state) > 5 else 0.5
        
        # 위협 수준 계산
        threat = max(
            scanned_ratio * 0.3,
            services_found * 0.5,
            critical_found * 0.8,
            exploit_progress,
            compromise_progress,
        )
        
        can_shuffle = (self.step - self.last_shuffle_step) >= self.min_interval
        can_swap = (self.step - self.last_swap_step) >= self.min_interval
        
        # 고위협: Service Swap
        if can_swap and (compromise_progress > 0.1 or (critical_found > 0.5 and services_found > 0.1)):
            intensity = min(0.6 + threat * 0.4, 1.0)
            action[5] = intensity * 2 - 1
            action[6] = 0.8
            action[0] = 0.9 * 2 - 1
            self.swap_count += 1
            self.shuffle_count += 1
            self.total_cost += intensity * 1.5
            self.last_swap_step = self.step
            self.last_shuffle_step = self.step
            return action
            
        # 중위협: Shuffle
        if can_shuffle and services_found > 0.05:
            intensity = 0.5 + threat * 0.4
            action[0] = intensity * 2 - 1
            action[1] = 0.4 * 2 - 1
            action[2] = 0.5 * 2 - 1
            self.shuffle_count += 1
            self.total_cost += intensity * 0.7
            self.last_shuffle_step = self.step
            return action
            
        # 스캔 감지
        if can_shuffle and scanned_ratio > 0.15:
            intensity = 0.4 + scanned_ratio * 0.3
            action[0] = intensity * 2 - 1
            self.shuffle_count += 1
            self.total_cost += intensity * 0.5
            self.last_shuffle_step = self.step
            return action
            
        # 다양성 낮음
        if can_shuffle and diversity < 0.4:
            action[0] = 0.5 * 2 - 1
            self.shuffle_count += 1
            self.total_cost += 0.35
            self.last_shuffle_step = self.step
            return action
            
        # 주기적 Shuffle
        if can_shuffle and (self.step - self.last_shuffle_step) >= 15:
            action[0] = 0.3 * 2 - 1
            self.shuffle_count += 1
            self.total_cost += 0.2
            self.last_shuffle_step = self.step
            return action
            
        action[2] = 0.2 * 2 - 1
        return action


class RLCTIMTDStrategy(BaseMTDStrategy):
    """RL+CTI MTD"""
    name = "RL+CTI MTD"
    
    def __init__(self, config: MTDConfig, model_path: str, device: str = 'cpu'):
        super().__init__(config)
        self.device = device
        
        if not TORCH_AVAILABLE:
            raise RuntimeError("PyTorch required")
            
        self.policy = ActorCritic(STATE_DIM, ACTION_DIM).to(device)
        
        checkpoint = torch.load(model_path, map_location=device, weights_only=True)
        if "policy" in checkpoint:
            self.policy.load_state_dict(checkpoint["policy"])
        else:
            self.policy.load_state_dict(checkpoint)
        self.policy.eval()
        logger.info(f"✅ RL+CTI Model loaded: {model_path}")
        
    def get_action(self, state: np.ndarray, info: Dict = None) -> np.ndarray:
        self.step += 1
        
        with torch.no_grad():
            state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)
            action, _, _ = self.policy.act(state_tensor, deterministic=True)
            
        action_np = action.cpu().numpy().squeeze()
        
        # CTI 부스트
        exploit_progress = state[3] if len(state) > 3 else 0
        if exploit_progress > 0.1:
            action_np = np.clip(action_np * 1.3, -1, 1)
            
        # 액션 카운트
        scaled = (action_np + 1) / 2
        if scaled[0] > 0.25:
            self.shuffle_count += 1
            self.total_cost += scaled[0] * 0.5
        if len(scaled) > 5 and scaled[5] > 0.30:
            self.swap_count += 1
            self.total_cost += scaled[5] * 1.0
            
        return action_np


# =============================================================================
# 평가 결과 데이터 클래스
# =============================================================================
@dataclass
class EvaluationResult:
    """평가 결과"""
    scenario: str
    mtd_mode: str
    seeker_level: int
    episode: int
    
    # 기본 메트릭
    defense_rate: float = 0.0
    detection_rate: float = 0.0
    s_mtd_score: float = 0.0
    
    # MTD 메트릭
    diversity_avg: float = 0.0
    redundancy_avg: float = 0.0
    shuffle_count: int = 0
    swap_count: int = 0
    mtd_cost: float = 0.0
    
    # 추가 정보
    total_steps: int = 0
    total_reward: float = 0.0
    breach_prevented: bool = True


# =============================================================================
# 평가 엔진
# =============================================================================
class ScenarioEvaluator:
    """시나리오 기반 평가 엔진"""
    
    def __init__(self, config: MTDConfig, args):
        self.config = config
        self.args = args
        self.device = 'cuda' if TORCH_AVAILABLE and torch.cuda.is_available() and not args.cpu else 'cpu'
        
        self.results: List[EvaluationResult] = []
        self.strategies: Dict[str, BaseMTDStrategy] = {}
        
        self._init_strategies()
        
        # W&B
        self.use_wandb = args.wandb and WANDB_AVAILABLE
        if self.use_wandb:
            wandb.init(
                project=args.wandb_project,
                name=args.wandb_name or f"scenario_{datetime.now().strftime('%Y%m%d_%H%M')}",
                config=vars(args)
            )
            
    def _init_strategies(self):
        """전략 초기화"""
        self.strategies['No MTD'] = NoMTDStrategy(self.config)
        self.strategies['Static MTD'] = StaticMTDStrategy(self.config)
        self.strategies['Heuristic+CTI MTD'] = HeuristicCTIMTDStrategy(self.config)
        
        if self.args.model and os.path.exists(self.args.model):
            try:
                self.strategies['RL+CTI MTD'] = RLCTIMTDStrategy(
                    self.config, self.args.model, self.device
                )
            except Exception as e:
                logger.warning(f"Failed to load RL model: {e}")
                
    def run_episode(self, 
                    env: MTDEnvironment,
                    strategy: BaseMTDStrategy,
                    scenario_name: str,
                    seeker_level: int,
                    max_steps: int = 200) -> EvaluationResult:
        """단일 에피소드 실행"""
        
        strategy.reset()
        state, info = env.reset()
        
        total_reward = 0.0
        diversity_scores = []
        redundancy_scores = []
        
        for step in range(max_steps):
            action = strategy.get_action(state, info)
            state, reward, terminated, truncated, info = env.step(action)
            
            total_reward += reward
            diversity_scores.append(info.get('Defense/Diversity_Current', 0.0))
            redundancy_scores.append(info.get('Defense/Redundancy_Current', 0.0))
            
            if terminated or truncated:
                break
                
        # 전략 통계
        strategy_stats = strategy.get_stats()
        
        result = EvaluationResult(
            scenario=scenario_name,
            mtd_mode=strategy.name,
            seeker_level=seeker_level,
            episode=0,
            defense_rate=info.get('Defense/Success', 0.0),
            detection_rate=1.0 - info.get('MTD/ASP', 0.0),
            s_mtd_score=info.get('MTD/DES', 0.0),
            diversity_avg=np.mean(diversity_scores) if diversity_scores else 0.0,
            redundancy_avg=np.mean(redundancy_scores) if redundancy_scores else 0.0,
            shuffle_count=strategy_stats['shuffle_count'],
            swap_count=strategy_stats['swap_count'],
            mtd_cost=info.get('Cost/Total', 0.0),
            total_steps=step + 1,
            total_reward=total_reward,
            breach_prevented=bool(info.get('Defense/BreachPrevented', 1))
        )
        
        return result
        
    def evaluate_scenario(self,
                         scenario_name: str,
                         seeker_levels: List[int],
                         episodes: int = 5) -> List[EvaluationResult]:
        """시나리오 평가"""
        
        scenario = SCENARIOS.get(scenario_name)
        if not scenario:
            logger.warning(f"Unknown scenario: {scenario_name}")
            return []
            
        results = []
        total_experiments = len(self.strategies) * len(seeker_levels) * episodes
        experiment_idx = 0
        
        for strategy_name, strategy in self.strategies.items():
            for level in seeker_levels:
                for ep in range(episodes):
                    experiment_idx += 1
                    
                    env = MTDEnvironment(
                        seed=self.args.seed + experiment_idx,
                        seeker_level=level,
                        config=self.config
                    )
                    
                    result = self.run_episode(
                        env, strategy, scenario_name, level,
                        max_steps=self.args.max_steps
                    )
                    result.episode = ep
                    results.append(result)
                    
                    print(f"[{experiment_idx}/{total_experiments}] "
                          f"{scenario_name} | {strategy_name} | L{level} | "
                          f"Ep{ep} | S_MTD: {result.s_mtd_score:.3f} | "
                          f"Shuffle: {result.shuffle_count} | Swap: {result.swap_count}")
                    
                    if self.use_wandb:
                        wandb.log({
                            'experiment': experiment_idx,
                            'scenario': scenario_name,
                            'mtd_mode': strategy_name,
                            'seeker_level': level,
                            'episode': ep,
                            's_mtd': result.s_mtd_score,
                            'defense_rate': result.defense_rate,
                            'detection_rate': result.detection_rate,
                            'diversity_avg': result.diversity_avg,
                            'redundancy_avg': result.redundancy_avg,
                            'shuffle_count': result.shuffle_count,
                            'swap_count': result.swap_count,
                            'mtd_cost': result.mtd_cost
                        })
                        
        return results
        
    def run_all_evaluations(self,
                           scenarios: List[str],
                           levels: List[int],
                           episodes: int = 5):
        """전체 평가 실행"""
        
        logger.info("=" * 100)
        logger.info("MTD SCENARIO-BASED EVALUATION v0.8.7")
        logger.info("=" * 100)
        
        all_results = []
        
        for scenario_name in scenarios:
            logger.info(f"\n>>> Evaluating: {scenario_name}")
            results = self.evaluate_scenario(scenario_name, levels, episodes)
            all_results.extend(results)
            self.results.extend(results)
            
        return all_results
        
    def generate_report(self, output_dir: str):
        """결과 리포트 생성"""
        
        os.makedirs(output_dir, exist_ok=True)
        
        # DataFrame 생성
        df = pd.DataFrame([asdict(r) for r in self.results])
        
        # 요약 통계 - [v0.8.7] shuffle/swap 포함
        summary = df.groupby(['mtd_mode', 'seeker_level']).agg({
            's_mtd_score': ['mean', 'std'],
            'defense_rate': 'mean',
            'detection_rate': 'mean',
            'diversity_avg': 'mean',
            'redundancy_avg': 'mean',
            'shuffle_count': 'mean',
            'swap_count': 'mean',
            'mtd_cost': 'mean'
        })
        
        logger.info("\n" + "=" * 100)
        logger.info("EVALUATION SUMMARY (Diversity/Redundancy/Shuffle)")
        logger.info("=" * 100)
        print(summary.to_string())
        
        # JSON 저장
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        json_path = os.path.join(output_dir, f"eval_results_{timestamp}.json")
        
        with open(json_path, 'w') as f:
            json.dump([asdict(r) for r in self.results], f, indent=2, default=to_serializable)
        logger.info(f"\nResults saved: {json_path}")
        
        # 시각화
        self._plot_results(df, output_dir, timestamp)
        
        return df
        
    def _plot_results(self, df: pd.DataFrame, output_dir: str, timestamp: str):
        """결과 시각화"""
        
        fig, axes = plt.subplots(2, 3, figsize=(18, 12))
        
        colors = {
            'No MTD': '#E74C3C',
            'Static MTD': '#F39C12',
            'Heuristic+CTI MTD': '#27AE60',
            'RL+CTI MTD': '#9B59B6'
        }
        
        # 1. S_MTD by Mode
        ax1 = axes[0, 0]
        mode_means = df.groupby('mtd_mode')['s_mtd_score'].mean().sort_values(ascending=False)
        bars = ax1.bar(mode_means.index, mode_means.values,
                       color=[colors.get(m, '#95A5A6') for m in mode_means.index])
        ax1.set_title('S_MTD Score by MTD Mode', fontweight='bold')
        ax1.set_ylabel('S_MTD Score')
        ax1.set_xlabel('mtd_mode')
        ax1.tick_params(axis='x', rotation=45)
        
        # 2. Defense Rate by Mode and Level
        ax2 = axes[0, 1]
        pivot = df.pivot_table(values='defense_rate', index='mtd_mode',
                               columns='seeker_level', aggfunc='mean')
        pivot.plot(kind='bar', ax=ax2, width=0.8)
        ax2.set_title('Defense Rate by Mode and Seeker Level', fontweight='bold')
        ax2.set_ylabel('Defense Rate')
        ax2.legend(title='Seeker Level')
        ax2.tick_params(axis='x', rotation=45)
        
        # 3. Diversity by Mode
        ax3 = axes[0, 2]
        div_means = df.groupby('mtd_mode')['diversity_avg'].mean()
        bars = ax3.bar(div_means.index, div_means.values,
                       color=[colors.get(m, '#95A5A6') for m in div_means.index])
        ax3.set_title('Average Diversity by MTD Mode', fontweight='bold')
        ax3.set_ylabel('Diversity')
        ax3.tick_params(axis='x', rotation=45)
        
        # 4. Cost-Effectiveness
        ax4 = axes[1, 0]
        for mode in df['mtd_mode'].unique():
            mode_df = df[df['mtd_mode'] == mode]
            ax4.scatter(mode_df['mtd_cost'], mode_df['s_mtd_score'],
                       label=mode, color=colors.get(mode, '#95A5A6'), alpha=0.6)
        ax4.set_xlabel('MTD Cost')
        ax4.set_ylabel('S_MTD Score')
        ax4.set_title('Cost-Effectiveness Analysis', fontweight='bold')
        ax4.legend(loc='best', fontsize=8)
        
        # 5. MTD Actions (Shuffle vs Swap) - [v0.8.7]
        ax5 = axes[1, 1]
        action_df = df.groupby('mtd_mode')[['shuffle_count', 'swap_count']].mean()
        action_df.plot(kind='bar', ax=ax5, width=0.8)
        ax5.set_title('MTD Actions (Shuffle vs Swap)', fontweight='bold')
        ax5.set_ylabel('Count')
        ax5.set_xlabel('mtd_mode')
        ax5.tick_params(axis='x', rotation=45)
        
        # 6. Performance by Scenario
        ax6 = axes[1, 2]
        scenario_pivot = df.pivot_table(values='s_mtd_score', index='scenario',
                                        columns='mtd_mode', aggfunc='mean')
        scenario_pivot.plot(kind='bar', ax=ax6, width=0.8)
        ax6.set_title('Performance by Scenario', fontweight='bold')
        ax6.set_ylabel('S_MTD Score')
        ax6.set_xlabel('scenario_name')
        ax6.legend(title='MTD Mode', fontsize=8)
        ax6.tick_params(axis='x', rotation=45)
        
        plt.tight_layout()
        
        plot_path = os.path.join(output_dir, f"eval_comparison_{timestamp}.png")
        plt.savefig(plot_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        logger.info(f"Plot saved: {plot_path}")


# =============================================================================
# 메인
# =============================================================================
def parse_args():
    parser = argparse.ArgumentParser(description='MTD Scenario-Based Evaluation v0.8.7')
    
    parser.add_argument('--model', type=str, default='checkpoints_v08/best.pt',
                        help='RL model checkpoint path')
    parser.add_argument('--scenarios', nargs='+',
                        default=['reconnaissance', 'gps_spoofing', 'command_injection',
                                'dos_attack', 'mixed_apt'],
                        help='Scenarios to evaluate')
    parser.add_argument('--levels', nargs='+', type=int, default=[1, 2, 3, 4],
                        help='Seeker levels to evaluate')
    parser.add_argument('--episodes', type=int, default=5,
                        help='Episodes per scenario')
    parser.add_argument('--max-steps', type=int, default=200,
                        help='Max steps per episode')
    parser.add_argument('--output', type=str, default='eval_results_scenario',
                        help='Output directory')
    parser.add_argument('--cpu', action='store_true', help='Force CPU')
    parser.add_argument('--seed', type=int, default=42, help='Random seed')
    
    parser.add_argument('--wandb', action='store_true', help='Enable W&B logging')
    parser.add_argument('--wandb-project', type=str, default='mtd-rl-eval',
                        help='W&B project name')
    parser.add_argument('--wandb-name', type=str, default=None,
                        help='W&B run name')
    
    return parser.parse_args()


def main():
    args = parse_args()
    
    random.seed(args.seed)
    np.random.seed(args.seed)
    if TORCH_AVAILABLE:
        torch.manual_seed(args.seed)
    
    config = MTDConfig()
    evaluator = ScenarioEvaluator(config, args)
    
    evaluator.run_all_evaluations(
        scenarios=args.scenarios,
        levels=args.levels,
        episodes=args.episodes
    )
    
    evaluator.generate_report(args.output)
    
    if args.wandb and WANDB_AVAILABLE:
        wandb.finish()
        
    print(f"\nTotal experiments: {len(evaluator.results)}")


if __name__ == "__main__":
    main()