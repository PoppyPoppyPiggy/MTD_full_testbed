#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MTD RL Training Script v08 - Complete Training Pipeline

핵심 개선사항:
1. Actor-Critic 역할 명확화
   - Actor: MTD 전략 결정 (언제, 어떤 강도로 셔플/디코이/블랙리스트)
   - Critic: 현재 상태의 가치 추정 (방어 성공 가능성)
2. Curriculum Learning: 점진적 난이도 증가
3. 상세 로깅 및 체크포인트
4. 학습 안정성 개선

저자: MTD-RL Research Team
버전: 0.8.0
"""
from __future__ import annotations

import argparse
import datetime
import json
import time
from collections import deque
from pathlib import Path
from typing import Dict, List, Tuple, Optional

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
)
from rl_environment_v08 import MTDEnvironment


def to_serializable(obj):
    # numpy float → Python float
    if isinstance(obj, (np.floating, np.float32, np.float64)):
        return float(obj)
    # numpy int → Python int
    if isinstance(obj, (np.integer, np.int32, np.int64)):
        return int(obj)
    # numpy 배열 → list
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    # torch 텐서 → list
    if isinstance(obj, torch.Tensor):
        return obj.detach().cpu().tolist()
    # 그 외는 문자열로라도 떨어지게
    return str(obj)


# =============================================================================
# Actor-Critic Network
# =============================================================================
class ActorCritic(nn.Module):
    """
    Actor-Critic 네트워크
    """

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

        # === Shared Feature Extractor ===
        layers = []
        input_dim = state_dim
        for i in range(num_layers):
            layers.extend(
                [
                    nn.Linear(input_dim, hidden_size),
                    nn.LayerNorm(hidden_size),
                    nn.ReLU(),
                ]
            )
            input_dim = hidden_size
        self.shared = nn.Sequential(*layers)

        # === Actor Head ===
        self.actor = nn.Sequential(
            nn.Linear(hidden_size, hidden_size // 2),
            nn.ReLU(),
            nn.Linear(hidden_size // 2, action_dim),
            nn.Tanh(),  # 출력을 [-1, 1]로 제한
        )

        # 액션 분산 (학습 가능한 파라미터)
        self.log_std = nn.Parameter(torch.ones(action_dim) * -0.5)

        # === Critic Head ===
        self.critic = nn.Sequential(
            nn.Linear(hidden_size, hidden_size // 2),
            nn.ReLU(),
            nn.Linear(hidden_size // 2, 1),
        )

        # 가중치 초기화
        self._init_weights()

    def _init_weights(self):
        """Orthogonal 초기화 (PPO 권장)"""
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.orthogonal_(m.weight, gain=np.sqrt(2))
                nn.init.zeros_(m.bias)

        # Actor 출력층은 작은 값으로 초기화 (초기 행동 안정화)
        nn.init.orthogonal_(self.actor[-2].weight, gain=0.01)

    def forward(self, state: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        순전파
        """
        features = self.shared(state)
        action_mean = self.actor(features)
        value = self.critic(features)
        return action_mean, value

    def act(
        self,
        state: torch.Tensor,
        deterministic: bool = False,
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        액션 샘플링
        """
        action_mean, value = self.forward(state)

        if deterministic:
            # 평가 모드에서 log_prob는 안 쓰므로 0 반환
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
        """
        액션 평가 (PPO 업데이트용)
        """
        action_mean, values = self.forward(states)

        std = torch.exp(self.log_std)
        dist = Normal(action_mean, std)

        log_probs = dist.log_prob(actions).sum(dim=-1, keepdim=True)
        entropy = dist.entropy().sum(dim=-1, keepdim=True)

        return log_probs, values, entropy

    def get_action_distribution(self, state: torch.Tensor) -> Normal:
        """액션 분포 반환 (분석용)"""
        action_mean, _ = self.forward(state)
        std = torch.exp(self.log_std)
        return Normal(action_mean, std)


# =============================================================================
# Rollout Buffer
# =============================================================================
class RolloutBuffer:
    """
    경험 저장 버퍼
    """

    def __init__(self):
        self.clear()

    def add(
        self,
        state: np.ndarray,
        action: np.ndarray,
        reward: float,
        value: float,
        log_prob: float,
        done: bool,
    ):
        """경험 추가"""
        self.states.append(state)
        self.actions.append(action)
        self.rewards.append(reward)
        self.values.append(value)
        self.log_probs.append(log_prob)
        self.dones.append(done)

    def clear(self):
        """버퍼 초기화"""
        self.states = []
        self.actions = []
        self.rewards = []
        self.values = []
        self.log_probs = []
        self.dones = []

    def compute_gae(
        self,
        last_value: float,
        gamma: float,
        gae_lambda: float,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Generalized Advantage Estimation (GAE) 계산
        """
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

    def iter_batches(
        self,
        batch_size: int,
        returns: np.ndarray,
        advantages: np.ndarray,
    ):
        """미니배치 이터레이터"""
        n = len(self.states)
        indices = np.random.permutation(n)

        for start in range(0, n, batch_size):
            batch_idx = indices[start : start + batch_size]

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
    """
    PPO 에이전트
    """

    def __init__(
        self,
        config: PPOConfig,
        device: str = "cpu",
        hidden_size: int = 256,
    ):
        self.cfg = config
        self.device = device

        # 네트워크 초기화
        self.policy = ActorCritic(
            state_dim=STATE_DIM,
            action_dim=ACTION_DIM,
            hidden_size=hidden_size,
        ).to(device)

        # 옵티마이저
        self.optimizer = optim.Adam(
            self.policy.parameters(),
            lr=config.learning_rate,
            eps=1e-5,
        )

        # 엔트로피 계수 (탐색 조절)
        self.entropy_coef = config.entropy_coef_start

        # 학습 통계
        self.update_count = 0

    def select_action(
        self,
        state: np.ndarray,
        deterministic: bool = False,
    ) -> Tuple[np.ndarray, float, float]:
        """
        액션 선택
        """
        state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)

        with torch.no_grad():
            action, log_prob, value = self.policy.act(state_tensor, deterministic)

        return (
            action.cpu().numpy().squeeze(),
            float(log_prob.item()),
            float(value.item()),
        )

    def update(
        self,
        buffer: RolloutBuffer,
        last_value: float,
    ) -> Dict[str, float]:
        """
        PPO 업데이트
        """
        returns, advantages = buffer.compute_gae(
            last_value,
            self.cfg.gamma,
            self.cfg.gae_lambda,
        )

        total_policy_loss = 0.0
        total_value_loss = 0.0
        total_entropy = 0.0
        n_updates = 0

        for _ in range(self.cfg.update_epochs):
            for (
                states,
                actions,
                old_log_probs,
                batch_returns,
                batch_advs,
            ) in buffer.iter_batches(self.cfg.batch_size, returns, advantages):

                states = states.to(self.device)
                actions = actions.to(self.device)
                old_log_probs = old_log_probs.to(self.device)
                batch_returns = batch_returns.to(self.device)
                batch_advs = batch_advs.to(self.device)

                log_probs, values, entropy = self.policy.evaluate(states, actions)

                ratio = torch.exp(log_probs - old_log_probs)
                surr1 = ratio * batch_advs
                surr2 = torch.clamp(
                    ratio,
                    1 - self.cfg.clip_epsilon,
                    1 + self.cfg.clip_epsilon,
                ) * batch_advs
                policy_loss = -torch.min(surr1, surr2).mean()

                value_loss = nn.functional.mse_loss(values, batch_returns)

                entropy_loss = -entropy.mean()

                loss = (
                    policy_loss
                    + self.cfg.value_loss_coef * value_loss
                    + self.entropy_coef * entropy_loss
                )

                self.optimizer.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(self.policy.parameters(), self.cfg.max_grad_norm)
                self.optimizer.step()

                total_policy_loss += policy_loss.item()
                total_value_loss += value_loss.item()
                total_entropy += -entropy_loss.item()
                n_updates += 1

        self.update_count += 1

        return {
            "policy_loss": total_policy_loss / max(1, n_updates),
            "value_loss": total_value_loss / max(1, n_updates),
            "entropy": total_entropy / max(1, n_updates),
            "update_count": self.update_count,
        }

    def update_entropy_coef(self, episode: int, total_episodes: int):
        """엔트로피 계수 스케줄링"""
        progress = min(1.0, episode / self.cfg.entropy_decay_episodes)
        self.entropy_coef = self.cfg.entropy_coef_start + (
            self.cfg.entropy_coef_final - self.cfg.entropy_coef_start
        ) * progress

    def save(self, path: str):
        """모델 저장"""
        torch.save(
            {
                "policy": self.policy.state_dict(),
                "optimizer": self.optimizer.state_dict(),
                "entropy_coef": self.entropy_coef,
                "update_count": self.update_count,
            },
            path,
        )
        print(f"✅ Model saved: {path}")

    def load(self, path: str):
        """모델 로드"""
        checkpoint = torch.load(path, map_location=self.device, weights_only=True)
        self.policy.load_state_dict(checkpoint["policy"])
        self.optimizer.load_state_dict(checkpoint["optimizer"])
        self.entropy_coef = checkpoint.get("entropy_coef", self.cfg.entropy_coef_start)
        self.update_count = checkpoint.get("update_count", 0)
        print(f"✅ Model loaded: {path}")

    def export_policy(self, path: str):
        """배포용 정책 저장 (정책 네트워크만)"""
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

    if args.wandb:
        import wandb

        run_name = args.wandb_name or f"mtd-v08-{datetime.datetime.now():%m%d-%H%M}"
        wandb.init(project=args.wandb_project, name=run_name, config=vars(args))

    agent = PPOAgent(cfg.ppo, device, hidden_size=args.hidden_size)

    if args.resume:
        agent.load(args.resume)

    if args.curriculum:
        phases = cfg.curriculum.phases
        phase_episodes = cfg.curriculum.phase_episodes
        entropy_schedule = cfg.curriculum.entropy_schedule
    else:
        levels = args.seeker_levels if args.train_all_levels else [args.seeker_level]
        phases = [tuple(levels)] * 5
        phase_episodes = [args.episodes // 5] * 5
        entropy_schedule = [0.02, 0.015, 0.01, 0.005, 0.002]

    rewards_history = deque(maxlen=100)
    best_reward = float("-inf")
    all_metrics: List[Dict] = []
    start_time = time.time()
    global_episode = 0

    print(f"\n{'='*70}")
    print("MTD RL Training v08")
    print(f"{'='*70}")
    print(f"Search Space: {cfg.search_space.total_search_space:,}")
    print(f"State Dim: {STATE_DIM}, Action Dim: {ACTION_DIM}")
    print(f"Total Episodes: {args.episodes}")
    print(f"Curriculum: {args.curriculum}")
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
                episode_actions.append((action + 1) / 2)  # [0, 1]로 스케일

                state = next_state

                if terminated or truncated:
                    break

            _, _, last_value = agent.select_action(state)
            losses = agent.update(buffer, last_value)

            agent.update_entropy_coef(global_episode, args.episodes)

            rewards_history.append(episode_reward)
            avg_reward = float(np.mean(rewards_history))

            episode_actions = np.array(episode_actions)
            action_means = (
                episode_actions.mean(axis=0)
                if len(episode_actions) > 0
                else np.zeros(ACTION_DIM)
            )

            episode_metrics = {
                "episode": global_episode,
                "phase": phase_idx,
                "seeker_level": level,
                "reward": episode_reward,
                "avg_reward": avg_reward,
                "steps": step + 1,
                **info,
                **losses,
                "entropy_coef": agent.entropy_coef,
            }

            for i, key in enumerate(ACTION_PARAM_KEYS):
                episode_metrics[f"Action/{key}"] = float(action_means[i])

            all_metrics.append(episode_metrics)

            if global_episode % args.log_interval == 0:
                elapsed = time.time() - start_time
                s_mtd = info.get("Defense/S_MTD", 0)
                svc_found = info.get("Attack/ServicesFound", 0)
                breach_prevented = info.get("Defense/BreachPrevented", 1)

                print(
                    f"Ep {global_episode:4d} | "
                    f"P{phase_idx} L{level} | "
                    f"R: {episode_reward:7.1f} | "
                    f"Avg: {avg_reward:7.1f} | "
                    f"S_MTD: {s_mtd:.3f} | "
                    f"Found: {svc_found:.0f} | "
                    f"Survive: {breach_prevented:.0f} | "
                    f"{elapsed/60:.1f}m"
                )

            if args.wandb:
                import wandb

                wandb.log(episode_metrics)

            if global_episode % args.save_interval == 0:
                agent.save(str(ckpt_dir / f"model_ep{global_episode}.pt"))

            if avg_reward > best_reward:
                best_reward = avg_reward
                agent.save(str(ckpt_dir / "best.pt"))

    agent.save(str(ckpt_dir / "final.pt"))
    agent.export_policy(str(ckpt_dir / "policy_deploy.pt"))

    training_config = {
        "args": vars(args),
        "state_dim": STATE_DIM,
        "action_dim": ACTION_DIM,
        "feature_keys": FEATURE_KEYS,
        "action_keys": ACTION_PARAM_KEYS,
        "search_space": cfg.search_space.total_search_space,
        "best_reward": best_reward,
        "total_episodes": global_episode,
    }

    with open(ckpt_dir / "training_config.json", "w") as f:
        json.dump(training_config, f, indent=2, default=to_serializable)

    def convert_to_serializable(obj):
        if isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, dict):
            return {k: convert_to_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert_to_serializable(i) for i in obj]
        return obj

    with open(ckpt_dir / "training_metrics.json", "w") as f:
        json.dump(convert_to_serializable(all_metrics), f)

    print(f"\n{'='*70}")
    print("✅ Training Complete!")
    print(f"Best avg reward: {best_reward:.1f}")
    print(f"Checkpoints saved to: {ckpt_dir}")
    print(f"{'='*70}\n")

    if args.wandb:
        import wandb

        wandb.finish()

    return best_reward


# =============================================================================
# Evaluation Function
# =============================================================================
def _aggregate_metrics(metrics_list: List[Dict]) -> Dict[str, float]:
    """
    평가 에피소드에서 나온 info 딕셔너리들을 안전하게 집계.

    - metrics_list가 비어 있어도 에러 없이 {} 리턴
    - key별로 숫자형 값만 모아서 mean 계산
    """
    if not metrics_list:
        return {}

    keys = sorted({k for m in metrics_list if isinstance(m, dict) for k in m.keys()})
    agg: Dict[str, float] = {}

    for k in keys:
        vals = []
        for m in metrics_list:
            if not isinstance(m, dict):
                continue
            v = m.get(k, None)
            if v is None:
                continue
            try:
                vals.append(float(v))
            except (TypeError, ValueError):
                # 숫자로 캐스팅 안 되면 버림
                continue
        if vals:
            agg[k] = float(np.mean(vals))
    return agg


def evaluate(args):
    """모델 평가"""

    device = "cuda" if torch.cuda.is_available() and not args.cpu else "cpu"
    cfg = MTDConfig()

    agent = PPOAgent(cfg.ppo, device)
    if args.model:
        agent.load(args.model)

    test_levels = args.seeker_levels if args.eval_all_levels else [args.seeker_level]

    print(f"\n{'='*80}")
    print("MTD RL Evaluation - Robustness Matrix")
    print(f"{'='*80}")
    print(
        f"{'Level':<18} {'R_succ':>8} {'S_MTD':>8} {'Decoy':>8} "
        f"{'Found':>8} {'Cost':>8} {'Survival':>8}"
    )
    print("-" * 80)

    results: Dict[int, Dict[str, float]] = {}

    for level in test_levels:
        metrics_list: List[Dict] = []

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

            # info가 None일 가능성 방지
            metrics_list.append(info if isinstance(info, dict) else {})

        agg = _aggregate_metrics(metrics_list)
        results[level] = agg

        name = SEEKER_PROFILES[level]["name"]

        print(
            f"L{level} {name:<12} "
            f"{agg.get('Defense/Success', 0.0):>8.3f} "
            f"{agg.get('Defense/S_MTD', 0.0):>8.3f} "
            f"{agg.get('Decoy/Hits', 0.0):>8.1f} "
            f"{agg.get('Attack/ServicesFound', 0.0):>8.1f} "
            f"{agg.get('Cost/Total', 0.0):>8.2f} "
            f"{agg.get('Defense/BreachPrevented', 0.0):>8.1%}"
        )

    print(f"{'='*80}\n")

    with open("eval_results.json", "w") as f:
        json.dump({str(k): v for k, v in results.items()}, f, indent=2, default=float)

    return results


# =============================================================================
# CLI
# =============================================================================
def parse_args():
    parser = argparse.ArgumentParser(description="MTD RL Training v08")

    parser.add_argument("--test", action="store_true", help="평가 모드")

    parser.add_argument("--episodes", type=int, default=500, help="총 에피소드 수")
    parser.add_argument("--max-steps", type=int, default=200, help="에피소드당 최대 스텝")
    parser.add_argument("--seed", type=int, default=42, help="랜덤 시드")
    parser.add_argument("--cpu", action="store_true", help="CPU 강제 사용")
    parser.add_argument("--hidden-size", type=int, default=256, help="은닉층 크기")

    parser.add_argument("--seeker-level", type=int, default=1, choices=[0, 1, 2, 3, 4])
    parser.add_argument("--seeker-levels", type=int, nargs="+", default=[0, 1, 2, 3, 4])
    parser.add_argument("--train-all-levels", action="store_true", dest="train_all_levels")

    parser.add_argument("--curriculum", action="store_true", help="Curriculum Learning 사용")

    parser.add_argument("--model", type=str, help="평가할 모델 경로")
    parser.add_argument("--resume", type=str, help="이어서 학습할 모델 경로")

    parser.add_argument("--checkpoint-dir", type=str, default="checkpoints_v08")
    parser.add_argument("--save-interval", type=int, default=100)
    parser.add_argument("--log-interval", type=int, default=10)

    parser.add_argument("--eval-episodes", type=int, default=50)
    parser.add_argument("--eval-all-levels", action="store_true")

    parser.add_argument("--wandb", action="store_true")
    parser.add_argument("--wandb-project", type=str, default="mtd-rl-v08")
    parser.add_argument("--wandb-name", type=str, dest="wandb_name")

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    np.random.seed(args.seed)
    torch.manual_seed(args.seed)

    if args.test:
        evaluate(args)
    else:
        train(args)
