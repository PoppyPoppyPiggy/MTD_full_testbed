#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MTD RL Training Script v09 - Complete Training Pipeline with IEEE Figures
==========================================================================

주요 기능:
1. Actor-Critic PPO 학습
2. Curriculum Learning: 점진적 난이도 증가
3. 학술적 MTD 지표 로깅
4. 학습 완료 시 IEEE Access 스타일 그래프 자동 생성
5. W&B 연동 (선택적)

Usage:
    # 기본 학습
    python rl_train_v09.py --episodes 500 --curriculum
    
    # W&B 연동 학습
    python rl_train_v09.py --episodes 500 --curriculum --wandb
    
    # 특정 레벨만 학습
    python rl_train_v09.py --episodes 300 --seeker-level 2

저자: MTD-RL Research Team
버전: 0.9.0
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import time
from collections import deque
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.distributions import Normal

from rl_config_v08 import (
    ACTION_DIM,
    ACTION_PARAM_KEYS,
    SEEKER_PROFILES,
    FEATURE_KEYS,
    STATE_DIM,
    EpisodeStats,
    MTDConfig,
    PPOConfig,
    MTD_METRICS,
    to_serializable,
)
from rl_environment_v08 import MTDEnvironment

# IEEE Figure Utils
try:
    from ieee_figure_utils import (
        generate_all_figures,
        plot_training_curves,
        setup_ieee_style,
    )
    IEEE_FIGURES_AVAILABLE = True
except ImportError:
    IEEE_FIGURES_AVAILABLE = False
    print("⚠️ ieee_figure_utils not found. Figures will not be generated.")

# W&B (optional)
try:
    import wandb
    WANDB_AVAILABLE = True
except ImportError:
    WANDB_AVAILABLE = False


# =============================================================================
# Actor-Critic Network
# =============================================================================
class ActorCritic(nn.Module):
    """Actor-Critic 네트워크"""

    def __init__(
        self,
        state_dim: int,
        action_dim: int,
        hidden_size: int = 256,
        num_layers: int = 2,
    ):
        super().__init__()

        self.state_dim = state_dim
        self.action_dim = action_dim
        self.hidden_size = hidden_size

        # Shared Feature Extractor
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

        # Actor Head
        self.actor = nn.Sequential(
            nn.Linear(hidden_size, hidden_size // 2),
            nn.ReLU(),
            nn.Linear(hidden_size // 2, action_dim),
            nn.Tanh(),
        )

        # 액션 분산
        self.log_std = nn.Parameter(torch.ones(action_dim) * -0.5)

        # Critic Head
        self.critic = nn.Sequential(
            nn.Linear(hidden_size, hidden_size // 2),
            nn.ReLU(),
            nn.Linear(hidden_size // 2, 1),
        )

        self._init_weights()

    def _init_weights(self):
        """Orthogonal 초기화"""
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.orthogonal_(m.weight, gain=np.sqrt(2))
                nn.init.zeros_(m.bias)
        nn.init.orthogonal_(self.actor[-2].weight, gain=0.01)

    def forward(self, state: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        features = self.shared(state)
        action_mean = self.actor(features)
        value = self.critic(features)
        return action_mean, value

    def act(
        self,
        state: torch.Tensor,
        deterministic: bool = False,
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        action_mean, value = self.forward(state)

        if deterministic:
            return action_mean, torch.zeros(1, device=state.device), value

        std = torch.exp(self.log_std)
        dist = Normal(action_mean, std)
        action = dist.sample()
        action = torch.clamp(action, -1, 1)
        log_prob = dist.log_prob(action).sum(dim=-1, keepdim=True)

        return action, log_prob, value

    def evaluate(
        self,
        states: torch.Tensor,
        actions: torch.Tensor,
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        action_mean, values = self.forward(states)
        std = torch.exp(self.log_std)
        dist = Normal(action_mean, std)
        log_probs = dist.log_prob(actions).sum(dim=-1, keepdim=True)
        entropy = dist.entropy().sum(dim=-1, keepdim=True)
        return log_probs, values, entropy


# =============================================================================
# Rollout Buffer
# =============================================================================
class RolloutBuffer:
    """경험 저장 버퍼"""

    def __init__(self):
        self.clear()

    def add(self, state, action, reward, value, log_prob, done):
        self.states.append(state)
        self.actions.append(action)
        self.rewards.append(reward)
        self.values.append(value)
        self.log_probs.append(log_prob)
        self.dones.append(done)

    def clear(self):
        self.states = []
        self.actions = []
        self.rewards = []
        self.values = []
        self.log_probs = []
        self.dones = []

    def compute_gae(self, last_value: float, gamma: float, gae_lambda: float):
        rewards = np.array(self.rewards)
        values = np.array(self.values + [last_value])
        dones = np.array(self.dones)

        advantages = np.zeros_like(rewards)
        gae = 0.0

        for t in reversed(range(len(rewards))):
            mask = 1.0 - dones[t]
            delta = rewards[t] + gamma * values[t + 1] * mask - values[t]
            gae = delta + gamma * gae_lambda * mask * gae
            advantages[t] = gae

        returns = advantages + values[:-1]
        advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)

        return returns, advantages

    def iter_batches(self, batch_size, returns, advantages):
        n = len(self.states)
        indices = np.random.permutation(n)

        for start in range(0, n, batch_size):
            batch_idx = indices[start:start + batch_size]
            yield (
                torch.FloatTensor(np.array(self.states)[batch_idx]),
                torch.FloatTensor(np.array(self.actions)[batch_idx]),
                torch.FloatTensor(np.array(self.log_probs)[batch_idx]).unsqueeze(1),
                torch.FloatTensor(returns[batch_idx]).unsqueeze(1),
                torch.FloatTensor(advantages[batch_idx]).unsqueeze(1),
            )

    def __len__(self):
        return len(self.states)


# =============================================================================
# PPO Agent
# =============================================================================
class PPOAgent:
    """PPO 에이전트"""

    def __init__(self, config: PPOConfig, device: str = "cpu", hidden_size: int = 256):
        self.cfg = config
        self.device = device
        self.hidden_size = hidden_size

        self.policy = ActorCritic(
            state_dim=STATE_DIM,
            action_dim=ACTION_DIM,
            hidden_size=hidden_size,
        ).to(device)

        self.optimizer = optim.Adam(
            self.policy.parameters(),
            lr=config.learning_rate,
            eps=1e-5,
        )

        self.entropy_coef = config.entropy_coef_start
        self.update_count = 0

    def select_action(self, state: np.ndarray, deterministic: bool = False):
        state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)
        with torch.no_grad():
            action, log_prob, value = self.policy.act(state_tensor, deterministic)
        return (
            action.cpu().numpy().squeeze(),
            float(log_prob.item()),
            float(value.item()),
        )

    def update(self, buffer: RolloutBuffer, last_value: float) -> Dict[str, float]:
        returns, advantages = buffer.compute_gae(
            last_value, self.cfg.gamma, self.cfg.gae_lambda
        )

        total_policy_loss = 0.0
        total_value_loss = 0.0
        total_entropy = 0.0
        total_kl = 0.0
        n_updates = 0

        for _ in range(self.cfg.update_epochs):
            for (states, actions, old_log_probs, batch_returns, batch_advs) in \
                    buffer.iter_batches(self.cfg.batch_size, returns, advantages):

                states = states.to(self.device)
                actions = actions.to(self.device)
                old_log_probs = old_log_probs.to(self.device)
                batch_returns = batch_returns.to(self.device)
                batch_advs = batch_advs.to(self.device)

                log_probs, values, entropy = self.policy.evaluate(states, actions)

                ratio = torch.exp(log_probs - old_log_probs)
                surr1 = ratio * batch_advs
                surr2 = torch.clamp(ratio, 1 - self.cfg.clip_epsilon, 1 + self.cfg.clip_epsilon) * batch_advs
                policy_loss = -torch.min(surr1, surr2).mean()
                value_loss = nn.functional.mse_loss(values, batch_returns)
                entropy_loss = -entropy.mean()
                kl = (old_log_probs - log_probs).mean()

                loss = policy_loss + self.cfg.value_loss_coef * value_loss + self.entropy_coef * entropy_loss

                self.optimizer.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(self.policy.parameters(), self.cfg.max_grad_norm)
                self.optimizer.step()

                total_policy_loss += policy_loss.item()
                total_value_loss += value_loss.item()
                total_entropy += -entropy_loss.item()
                total_kl += kl.item()
                n_updates += 1

        self.update_count += 1

        return {
            "loss/policy": total_policy_loss / max(1, n_updates),
            "loss/value": total_value_loss / max(1, n_updates),
            "loss/entropy": total_entropy / max(1, n_updates),
            "loss/kl_divergence": total_kl / max(1, n_updates),
            "train/update_count": self.update_count,
            "train/entropy_coef": self.entropy_coef,
        }

    def update_entropy_coef(self, episode: int, total_episodes: int):
        progress = min(1.0, episode / self.cfg.entropy_decay_episodes)
        self.entropy_coef = self.cfg.entropy_coef_start + (
            self.cfg.entropy_coef_final - self.cfg.entropy_coef_start
        ) * progress

    def save(self, path: str):
        torch.save({
            "policy": self.policy.state_dict(),
            "optimizer": self.optimizer.state_dict(),
            "entropy_coef": self.entropy_coef,
            "update_count": self.update_count,
            "hidden_size": self.hidden_size,
        }, path)
        print(f"✅ Model saved: {path}")

    def load(self, path: str):
        checkpoint = torch.load(path, map_location=self.device, weights_only=False)
        self.policy.load_state_dict(checkpoint["policy"])
        self.optimizer.load_state_dict(checkpoint["optimizer"])
        self.entropy_coef = checkpoint.get("entropy_coef", self.cfg.entropy_coef_start)
        self.update_count = checkpoint.get("update_count", 0)
        print(f"✅ Model loaded: {path}")

    def export_policy(self, path: str):
        torch.save(self.policy.state_dict(), path)
        print(f"✅ Policy exported: {path}")


# =============================================================================
# Training Function
# =============================================================================
def train(args):
    """메인 학습 함수"""
    device = "cuda" if torch.cuda.is_available() and not args.cpu else "cpu"
    print(f"🖥️ Device: {device}")

    cfg = MTDConfig()
    cfg.ppo.total_episodes = args.episodes
    cfg.ppo.max_steps = args.max_steps

    ckpt_dir = Path(args.checkpoint_dir)
    ckpt_dir.mkdir(parents=True, exist_ok=True)
    
    fig_dir = ckpt_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    # W&B 초기화 (선택적)
    if args.wandb and WANDB_AVAILABLE:
        wandb.init(
            project=args.wandb_project,
            name=args.wandb_name or f"mtd-v09-{datetime.datetime.now():%m%d-%H%M%S}",
            config=vars(args),
        )

    agent = PPOAgent(cfg.ppo, device, hidden_size=args.hidden_size)

    if args.resume:
        agent.load(args.resume)

    # Curriculum 설정
    if args.curriculum:
        phases = cfg.curriculum.phases
        phase_episodes = cfg.curriculum.phase_episodes
        entropy_schedule = cfg.curriculum.entropy_schedule
        curriculum_boundaries = [0]
        for pe in phase_episodes:
            curriculum_boundaries.append(curriculum_boundaries[-1] + pe)
    else:
        levels = args.seeker_levels if args.train_all_levels else [args.seeker_level]
        phases = [tuple(levels)] * 5
        phase_episodes = [args.episodes // 5] * 5
        entropy_schedule = [0.02] * 5
        curriculum_boundaries = [0, args.episodes]

    rewards_history = deque(maxlen=100)
    des_history = deque(maxlen=100)
    best_reward = float("-inf")
    best_des = float("-inf")
    all_metrics: List[Dict] = []
    level_metrics: Dict[int, List[Dict]] = {i: [] for i in range(5)}
    start_time = time.time()
    global_episode = 0

    print(f"\n{'='*70}")
    print("MTD RL Training v09 (with IEEE Figure Generation)")
    print(f"{'='*70}")
    print(f"State Dim: {STATE_DIM}, Action Dim: {ACTION_DIM}")
    print(f"Total Episodes: {args.episodes}")
    print(f"Curriculum: {args.curriculum}")
    print(f"Output: {ckpt_dir}")
    print(f"{'='*70}\n")

    for phase_idx, (phase_levels, n_episodes, ent_coef) in enumerate(
        zip(phases, phase_episodes, entropy_schedule)
    ):
        print(f"\n{'='*50}")
        print(f"Phase {phase_idx}: Levels {phase_levels}")
        print(f"Episodes: {n_episodes}, Entropy: {ent_coef}")
        print(f"{'='*50}")

        agent.entropy_coef = ent_coef
        reward_profile = "explore" if phase_idx < 2 else "exploit"

        for ep_in_phase in range(n_episodes):
            global_episode += 1
            level = int(np.random.choice(phase_levels))

            env = MTDEnvironment(
                seed=args.seed + global_episode,
                seeker_level=level,
                config=cfg,
            )
            env.set_reward_profile(reward_profile)

            buffer = RolloutBuffer()
            state, info = env.reset()
            episode_reward = 0.0
            episode_actions = []

            for step in range(args.max_steps):
                action, log_prob, value = agent.select_action(state)
                next_state, reward, terminated, truncated, info = env.step(action)

                buffer.add(state, action, reward, value, log_prob, terminated or truncated)
                episode_reward += reward
                episode_actions.append((action + 1) / 2)
                state = next_state

                if terminated or truncated:
                    break

            _, _, last_value = agent.select_action(state)
            losses = agent.update(buffer, last_value)
            agent.update_entropy_coef(global_episode, args.episodes)

            rewards_history.append(episode_reward)
            des_history.append(info.get('MTD/DES', 0))
            avg_reward = float(np.mean(rewards_history))
            avg_des = float(np.mean(des_history))

            episode_actions = np.array(episode_actions)
            action_means = episode_actions.mean(axis=0) if len(episode_actions) > 0 else np.zeros(ACTION_DIM)

            # 메트릭 저장
            episode_metrics = {
                "episode/episode": global_episode,
                "episode/phase": phase_idx,
                "episode/seeker_level": level,
                "episode/steps": step + 1,
                "episode/reward": episode_reward,
                "episode/avg_reward": avg_reward,
                "MTD/DES": info.get("MTD/DES", 0),
                "MTD/MTTC": info.get("MTD/MTTC", 200),
                "MTD/MTTC_Normalized": info.get("MTD/MTTC_Normalized", 1.0),
                "MTD/ASR": info.get("MTD/ASR", 0),
                "MTD/CDI": info.get("MTD/CDI", 0),
                "MTD/NED": info.get("MTD/NED", 0),
                "MTD/ASP": info.get("MTD/ASP", 0),
                "MTD/CER": info.get("MTD/CER", 0),
                "Defense/BreachPrevented": info.get("Defense/BreachPrevented", 0),
                "Defense/Diversity_Avg": info.get("Defense/Diversity_Avg", 0),
                "Defense/Redundancy_Avg": info.get("Defense/Redundancy_Avg", 0),
                "Attack/ServicesFound": info.get("Attack/ServicesFound", 0),
                "Attack/ServicesExploited": info.get("Attack/ServicesExploited", 0),
                "Attack/ConfusionLevel": info.get("Attack/ConfusionLevel", 0),
                "Cost/Total": info.get("Cost/Total", 0),
                "Cost/Efficiency": info.get("Cost/Efficiency", 0),
                "MTD_Actions/ShuffleCount": info.get("MTD/ShuffleCount", 0),
                "MTD_Actions/SwapCount": info.get("MTD/SwapCount", 0),
                "Decoy/Hits": info.get("Decoy/Hits", 0),
                **losses,
            }

            for i, key in enumerate(ACTION_PARAM_KEYS):
                episode_metrics[f"Action/{key}"] = float(action_means[i])

            all_metrics.append(episode_metrics)
            level_metrics[level].append({
                "reward": episode_reward,
                "des": info.get("MTD/DES", 0),
                "survival": info.get("Defense/BreachPrevented", 0),
            })

            # W&B 로깅
            if args.wandb and WANDB_AVAILABLE:
                wandb.log(episode_metrics, step=global_episode)

            # 콘솔 로깅
            if global_episode % args.log_interval == 0:
                elapsed = time.time() - start_time
                des = info.get('MTD/DES', 0)
                mttc = info.get('MTD/MTTC', 200)
                breach_prevented = info.get('Defense/BreachPrevented', 1)

                print(
                    f"Ep {global_episode:4d} | P{phase_idx} L{level} | "
                    f"R: {episode_reward:7.1f} | Avg: {avg_reward:7.1f} | "
                    f"DES: {des:.3f} | MTTC: {mttc:3.0f} | "
                    f"Survive: {breach_prevented:.0f} | {elapsed/60:.1f}m"
                )

            # 체크포인트 저장
            if global_episode % args.save_interval == 0:
                agent.save(str(ckpt_dir / f"model_ep{global_episode}.pt"))

            # Best 모델 저장
            if avg_reward > best_reward:
                best_reward = avg_reward
                agent.save(str(ckpt_dir / "best.pt"))

            if avg_des > best_des:
                best_des = avg_des
                agent.save(str(ckpt_dir / "best_des.pt"))

    # ==========================================================================
    # 학습 완료 후 처리
    # ==========================================================================
    
    # 최종 모델 저장
    agent.save(str(ckpt_dir / "final.pt"))
    agent.export_policy(str(ckpt_dir / "policy_deploy.pt"))

    # 메트릭 저장
    metrics_path = ckpt_dir / "training_metrics.json"
    with open(metrics_path, "w") as f:
        json.dump(all_metrics, f, default=to_serializable)
    print(f"✅ Training metrics saved: {metrics_path}")

    # 설정 저장
    config_data = {
        "args": vars(args),
        "state_dim": STATE_DIM,
        "action_dim": ACTION_DIM,
        "best_reward": best_reward,
        "best_des": best_des,
        "total_episodes": global_episode,
        "curriculum_boundaries": curriculum_boundaries,
    }
    with open(ckpt_dir / "training_config.json", "w") as f:
        json.dump(config_data, f, indent=2, default=to_serializable)

    # ==========================================================================
    # IEEE 스타일 그래프 생성
    # ==========================================================================
    if IEEE_FIGURES_AVAILABLE:
        print("\n" + "="*60)
        print("📊 Generating IEEE-style Training Figures...")
        print("="*60)
        
        try:
            plot_training_curves(
                all_metrics,
                str(fig_dir / "fig07_training_curves"),
                curriculum_phases=curriculum_boundaries,
            )
            print(f"✅ Training curves saved to: {fig_dir}/")
        except Exception as e:
            print(f"⚠️ Failed to generate training curves: {e}")
    
    # W&B 종료
    if args.wandb and WANDB_AVAILABLE:
        wandb.finish()

    print(f"\n{'='*70}")
    print("✅ Training Complete!")
    print(f"Best avg reward: {best_reward:.1f}")
    print(f"Best avg DES: {best_des:.3f}")
    print(f"Checkpoints: {ckpt_dir}")
    print(f"{'='*70}\n")

    return best_reward


# =============================================================================
# Evaluation Function (Quick)
# =============================================================================
def evaluate(args):
    """빠른 모델 평가"""
    device = "cuda" if torch.cuda.is_available() and not args.cpu else "cpu"
    cfg = MTDConfig()

    agent = PPOAgent(cfg.ppo, device, hidden_size=args.hidden_size)
    if args.model:
        agent.load(args.model)

    test_levels = args.seeker_levels if args.eval_all_levels else [args.seeker_level]

    print(f"\n{'='*80}")
    print("MTD RL Quick Evaluation")
    print(f"{'='*80}")
    print(f"{'Level':<15} {'DES':>10} {'Breach%':>10} {'MTTC':>10} {'Cost':>10}")
    print("-"*80)

    for level in test_levels:
        metrics_list = []

        for ep in range(args.eval_episodes):
            env = MTDEnvironment(
                seed=args.seed + ep * 100 + level,
                seeker_level=level,
                config=cfg,
            )
            state, _ = env.reset()

            for _ in range(args.max_steps):
                action, _, _ = agent.select_action(state, deterministic=True)
                state, _, terminated, truncated, info = env.step(action)
                if terminated or truncated:
                    break

            metrics_list.append(info)

        # 집계
        des = np.mean([m.get('MTD/DES', 0) for m in metrics_list])
        br = np.mean([1 - m.get('Defense/BreachPrevented', 1) for m in metrics_list]) * 100
        mttc = np.mean([m.get('MTD/MTTC', 200) for m in metrics_list])
        cost = np.mean([m.get('Cost/Total', 0) for m in metrics_list])

        name = SEEKER_PROFILES[level]["name"]
        print(f"L{level} {name:<10} {des:>10.3f} {br:>9.1f}% {mttc:>10.0f} {cost:>10.2f}")

    print(f"{'='*80}\n")


# =============================================================================
# CLI
# =============================================================================
def parse_args():
    parser = argparse.ArgumentParser(description="MTD RL Training v09 with IEEE Figures")

    parser.add_argument("--test", action="store_true", help="평가 모드")
    parser.add_argument("--episodes", type=int, default=500)
    parser.add_argument("--max-steps", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--cpu", action="store_true")
    parser.add_argument("--hidden-size", type=int, default=256)

    parser.add_argument("--seeker-level", type=int, default=1, choices=[0, 1, 2, 3, 4])
    parser.add_argument("--seeker-levels", type=int, nargs="+", default=[0, 1, 2, 3, 4])
    parser.add_argument("--train-all-levels", action="store_true")

    parser.add_argument("--curriculum", action="store_true")

    parser.add_argument("--model", type=str)
    parser.add_argument("--resume", type=str)
    parser.add_argument("--checkpoint-dir", type=str, default="checkpoints_v09")
    parser.add_argument("--save-interval", type=int, default=100)
    parser.add_argument("--log-interval", type=int, default=10)

    parser.add_argument("--eval-episodes", type=int, default=50)
    parser.add_argument("--eval-all-levels", action="store_true")

    parser.add_argument("--wandb", action="store_true")
    parser.add_argument("--wandb-project", type=str, default="mtd-rl-v09")
    parser.add_argument("--wandb-name", type=str, default=None)

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)

    if args.test:
        evaluate(args)
    else:
        train(args)