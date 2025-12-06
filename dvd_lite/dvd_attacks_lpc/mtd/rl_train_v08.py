#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MTD RL Training Script v08 - Complete Training Pipeline with W&B Integration

핵심 기능:
1. Actor-Critic PPO 학습
2. Curriculum Learning: 점진적 난이도 증가
3. 학술적 MTD 지표 로깅
4. 완전한 W&B 연동 (Artifact, Table, Plot, Sweep)

저자: MTD-RL Research Team
버전: 0.8.4
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

# W&B (optional)
try:
    import wandb
    WANDB_AVAILABLE = True
except ImportError:
    WANDB_AVAILABLE = False
    print("⚠️ wandb not installed. Install with: pip install wandb")


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
        """순전파"""
        features = self.shared(state)
        action_mean = self.actor(features)
        value = self.critic(features)
        return action_mean, value

    def act(
        self,
        state: torch.Tensor,
        deterministic: bool = False,
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """액션 샘플링"""
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
        """액션 평가"""
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
        """GAE 계산"""
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

    def __init__(
        self,
        config: PPOConfig,
        device: str = "cpu",
        hidden_size: int = 256,
    ):
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

    def select_action(
        self,
        state: np.ndarray,
        deterministic: bool = False,
    ) -> Tuple[np.ndarray, float, float]:
        """액션 선택"""
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
        """PPO 업데이트"""
        returns, advantages = buffer.compute_gae(
            last_value,
            self.cfg.gamma,
            self.cfg.gae_lambda,
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
                surr2 = torch.clamp(
                    ratio,
                    1 - self.cfg.clip_epsilon,
                    1 + self.cfg.clip_epsilon,
                ) * batch_advs
                policy_loss = -torch.min(surr1, surr2).mean()

                value_loss = nn.functional.mse_loss(values, batch_returns)
                entropy_loss = -entropy.mean()

                # KL divergence 추정
                kl = (old_log_probs - log_probs).mean()

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
                "hidden_size": self.hidden_size,
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
        """배포용 정책 저장"""
        torch.save(self.policy.state_dict(), path)
        print(f"✅ Policy exported: {path}")


# =============================================================================
# W&B Logger
# =============================================================================
class WandbLogger:
    """W&B 로깅 매니저"""

    def __init__(
        self,
        project: str,
        name: Optional[str] = None,
        config: Optional[Dict] = None,
        tags: Optional[List[str]] = None,
        notes: Optional[str] = None,
        save_code: bool = True,
    ):
        if not WANDB_AVAILABLE:
            raise RuntimeError("wandb is not installed. Install with: pip install wandb")

        self.run = wandb.init(
            project=project,
            name=name or f"mtd-v08-{datetime.datetime.now():%m%d-%H%M%S}",
            config=config,
            tags=tags or ["mtd", "ppo", "curriculum"],
            notes=notes,
            save_code=save_code,
        )

        # 메트릭 히스토리
        self.reward_history = []
        self.des_history = []
        self.mttc_history = []

        # 테이블 데이터
        self.episode_data = []

        print(f"✅ W&B initialized: {self.run.url}")

    def log_episode(
        self,
        episode: int,
        metrics: Dict[str, Any],
        step: Optional[int] = None,
    ):
        """에피소드 메트릭 로깅"""
        # 기본 로깅
        wandb.log(metrics, step=step or episode)

        # 히스토리 저장
        self.reward_history.append(metrics.get("episode/reward", 0))
        self.des_history.append(metrics.get("MTD/DES", 0))
        self.mttc_history.append(metrics.get("MTD/MTTC", 200))

        # 테이블 데이터 저장
        self.episode_data.append({
            "episode": episode,
            "reward": metrics.get("episode/reward", 0),
            "des": metrics.get("MTD/DES", 0),
            "mttc": metrics.get("MTD/MTTC", 200),
            "asr": metrics.get("MTD/ASR", 0),
            "cdi": metrics.get("MTD/CDI", 0),
            "cost": metrics.get("Cost/Total", 0),
            "breach_prevented": metrics.get("Defense/BreachPrevented", 0),
            "seeker_level": metrics.get("episode/seeker_level", 0),
            "phase": metrics.get("episode/phase", 0),
        })

    def log_phase_summary(
        self,
        phase: int,
        phase_metrics: Dict[str, float],
    ):
        """Phase 종료 시 요약 로깅"""
        wandb.log({
            f"phase_{phase}/avg_reward": phase_metrics.get("avg_reward", 0),
            f"phase_{phase}/avg_des": phase_metrics.get("avg_des", 0),
            f"phase_{phase}/avg_mttc": phase_metrics.get("avg_mttc", 0),
            f"phase_{phase}/survival_rate": phase_metrics.get("survival_rate", 0),
        })

    def log_model_artifact(
        self,
        model_path: str,
        name: str,
        artifact_type: str = "model",
        metadata: Optional[Dict] = None,
    ):
        """모델 Artifact 저장"""
        artifact = wandb.Artifact(
            name=name,
            type=artifact_type,
            metadata=metadata or {},
        )
        artifact.add_file(model_path)
        self.run.log_artifact(artifact)
        print(f"✅ Artifact logged: {name}")

    def log_config_artifact(
        self,
        config_path: str,
        name: str = "training_config",
    ):
        """설정 파일 Artifact 저장"""
        artifact = wandb.Artifact(
            name=name,
            type="config",
        )
        artifact.add_file(config_path)
        self.run.log_artifact(artifact)

    def log_evaluation_table(
        self,
        results: Dict[str, Any],
        table_name: str = "evaluation_results",
    ):
        """평가 결과 테이블 로깅"""
        columns = ["level", "mtd_mode", "des", "mttc", "asr", "cdi", "cost", "survival"]
        data = []

        for key, result in results.items():
            if hasattr(result, "metrics"):
                metrics = result.metrics
                data.append([
                    result.seeker_level,
                    result.mtd_mode,
                    metrics.get("MTD/DES_mean", 0),
                    metrics.get("MTD/MTTC_mean", 0),
                    metrics.get("MTD/ASR_mean", 0),
                    metrics.get("MTD/CDI_mean", 0),
                    metrics.get("Cost/Total_mean", 0),
                    metrics.get("Defense/BreachPrevented_mean", 0),
                ])

        table = wandb.Table(columns=columns, data=data)
        wandb.log({table_name: table})

    def log_training_curves(self):
        """학습 곡선 로깅"""
        if len(self.reward_history) < 10:
            return

        # 이동 평균
        window = min(50, len(self.reward_history) // 5)
        if window < 2:
            return

        reward_ma = np.convolve(
            self.reward_history,
            np.ones(window) / window,
            mode='valid'
        )
        des_ma = np.convolve(
            self.des_history,
            np.ones(window) / window,
            mode='valid'
        )

        # 학습 곡선 테이블
        data = [[i, r, d] for i, (r, d) in enumerate(zip(reward_ma, des_ma))]
        table = wandb.Table(
            data=data,
            columns=["step", "reward_ma", "des_ma"]
        )

        wandb.log({
            "charts/reward_moving_avg": wandb.plot.line(
                table, "step", "reward_ma",
                title="Reward Moving Average"
            ),
            "charts/des_moving_avg": wandb.plot.line(
                table, "step", "des_ma",
                title="DES Moving Average"
            ),
        })

    def log_action_distribution(
        self,
        action_means: np.ndarray,
        episode: int,
    ):
        """액션 분포 로깅"""
        action_data = [[ACTION_PARAM_KEYS[i], float(action_means[i])]
                       for i in range(len(ACTION_PARAM_KEYS))]

        table = wandb.Table(
            data=action_data,
            columns=["action", "mean_value"]
        )

        wandb.log({
            "actions/distribution": wandb.plot.bar(
                table, "action", "mean_value",
                title=f"Action Distribution (Episode {episode})"
            )
        })

    def log_level_performance(
        self,
        level_metrics: Dict[int, Dict[str, float]],
    ):
        """레벨별 성능 로깅"""
        data = []
        for level, metrics in level_metrics.items():
            data.append([
                level,
                SEEKER_PROFILES[level]["name"],
                metrics.get("avg_des", 0),
                metrics.get("avg_reward", 0),
                metrics.get("survival_rate", 0),
            ])

        table = wandb.Table(
            data=data,
            columns=["level", "name", "des", "reward", "survival"]
        )

        wandb.log({
            "performance/by_level": wandb.plot.bar(
                table, "name", "des",
                title="DES by Attacker Level"
            )
        })

    def log_image(self, image_path: str, caption: str):
        """이미지 로깅"""
        wandb.log({caption: wandb.Image(image_path)})

    def log_summary(self, summary: Dict[str, Any]):
        """최종 요약 로깅"""
        for key, value in summary.items():
            wandb.run.summary[key] = value

    def finish(self):
        """W&B 세션 종료"""
        # 최종 학습 곡선 로깅
        self.log_training_curves()

        # Episode 데이터 테이블
        if self.episode_data:
            columns = list(self.episode_data[0].keys())
            data = [list(ep.values()) for ep in self.episode_data]
            table = wandb.Table(columns=columns, data=data)
            wandb.log({"training/episode_data": table})

        wandb.finish()
        print("✅ W&B session finished")


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

    # W&B 초기화
    wb_logger = None
    if args.wandb and WANDB_AVAILABLE:
        wb_config = {
            "algorithm": "PPO",
            "state_dim": STATE_DIM,
            "action_dim": ACTION_DIM,
            "hidden_size": args.hidden_size,
            "episodes": args.episodes,
            "max_steps": args.max_steps,
            "curriculum": args.curriculum,
            "learning_rate": cfg.ppo.learning_rate,
            "gamma": cfg.ppo.gamma,
            "gae_lambda": cfg.ppo.gae_lambda,
            "clip_epsilon": cfg.ppo.clip_epsilon,
            "batch_size": cfg.ppo.batch_size,
            "update_epochs": cfg.ppo.update_epochs,
            "entropy_coef_start": cfg.ppo.entropy_coef_start,
            "entropy_coef_final": cfg.ppo.entropy_coef_final,
            "seed": args.seed,
            "seeker_levels": args.seeker_levels,
        }

        wb_logger = WandbLogger(
            project=args.wandb_project,
            name=args.wandb_name,
            config=wb_config,
            tags=args.wandb_tags.split(",") if args.wandb_tags else None,
            notes=args.wandb_notes,
        )

        # W&B에서 config 감시 (sweep용)
        if wandb.run and wandb.config:
            for key in ["hidden_size", "learning_rate", "batch_size"]:
                if key in wandb.config:
                    setattr(args, key.replace("_", "-"), wandb.config[key])

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
    des_history = deque(maxlen=100)
    best_reward = float("-inf")
    best_des = float("-inf")
    all_metrics: List[Dict] = []
    level_metrics: Dict[int, List[Dict]] = {i: [] for i in range(5)}
    start_time = time.time()
    global_episode = 0

    print(f"\n{'='*70}")
    print("MTD RL Training v08.4 (with W&B Integration)")
    print(f"{'='*70}")
    print(f"Search Space: {cfg.search_space.total_search_space:,}")
    print(f"State Dim: {STATE_DIM}, Action Dim: {ACTION_DIM}")
    print(f"Total Episodes: {args.episodes}")
    print(f"Curriculum: {args.curriculum}")
    print(f"W&B: {args.wandb and WANDB_AVAILABLE}")
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

        phase_rewards = []
        phase_des = []
        phase_survival = []

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
            action_means = (
                episode_actions.mean(axis=0)
                if len(episode_actions) > 0
                else np.zeros(ACTION_DIM)
            )

            # 메트릭 구성
            episode_metrics = {
                # Episode Info
                "episode/episode": global_episode,
                "episode/phase": phase_idx,
                "episode/seeker_level": level,
                "episode/steps": step + 1,
                "episode/reward": episode_reward,
                "episode/avg_reward": avg_reward,

                # MTD 학술적 지표
                "MTD/DES": info.get("MTD/DES", 0),
                "MTD/MTTC": info.get("MTD/MTTC", 200),
                "MTD/MTTC_Normalized": info.get("MTD/MTTC_Normalized", 1.0),
                "MTD/ASR": info.get("MTD/ASR", 0),
                "MTD/CDI": info.get("MTD/CDI", 0),
                "MTD/NED": info.get("MTD/NED", 0),
                "MTD/ASP": info.get("MTD/ASP", 0),
                "MTD/CER": info.get("MTD/CER", 0),

                # Defense 메트릭
                "Defense/BreachPrevented": info.get("Defense/BreachPrevented", 0),
                "Defense/Diversity_Avg": info.get("Defense/Diversity_Avg", 0),
                "Defense/Redundancy_Avg": info.get("Defense/Redundancy_Avg", 0),

                # Attack 메트릭
                "Attack/ServicesFound": info.get("Attack/ServicesFound", 0),
                "Attack/ServicesExploited": info.get("Attack/ServicesExploited", 0),
                "Attack/ConfusionLevel": info.get("Attack/ConfusionLevel", 0),

                # Cost 메트릭
                "Cost/Total": info.get("Cost/Total", 0),
                "Cost/Efficiency": info.get("Cost/Efficiency", 0),
                "Cost/PerStep": info.get("Cost/PerStep", 0),

                # MTD 액션 횟수
                "MTD_Actions/ShuffleCount": info.get("MTD/ShuffleCount", 0),
                "MTD_Actions/PortHopCount": info.get("MTD/PortHopCount", 0),
                "MTD_Actions/SwapCount": info.get("MTD/SwapCount", 0),
                "MTD_Actions/ActiveSwaps": info.get("MTD/ActiveSwaps", 0),

                # Decoy 메트릭
                "Decoy/Activations": info.get("Decoy/Activations", 0),
                "Decoy/Hits": info.get("Decoy/Hits", 0),
                "Decoy/HitRate": info.get("Decoy/HitRate", 0),

                # Loss 메트릭
                **losses,
            }

            # 액션 평균
            for i, key in enumerate(ACTION_PARAM_KEYS):
                episode_metrics[f"Action/{key}"] = float(action_means[i])

            all_metrics.append(episode_metrics)

            # 레벨별 메트릭 저장
            level_metrics[level].append({
                "reward": episode_reward,
                "des": info.get("MTD/DES", 0),
                "survival": info.get("Defense/BreachPrevented", 0),
            })

            # Phase 통계
            phase_rewards.append(episode_reward)
            phase_des.append(info.get("MTD/DES", 0))
            phase_survival.append(info.get("Defense/BreachPrevented", 0))

            # W&B 로깅
            if wb_logger:
                wb_logger.log_episode(global_episode, episode_metrics)

                # 주기적으로 액션 분포 로깅
                if global_episode % 50 == 0:
                    wb_logger.log_action_distribution(action_means, global_episode)

            # 콘솔 로깅
            if global_episode % args.log_interval == 0:
                elapsed = time.time() - start_time
                des = info.get('MTD/DES', 0)
                mttc = info.get('MTD/MTTC', 200)
                asr = info.get('MTD/ASR', 0)
                breach_prevented = info.get('Defense/BreachPrevented', 1)

                print(
                    f"Ep {global_episode:4d} | "
                    f"P{phase_idx} L{level} | "
                    f"R: {episode_reward:7.1f} | "
                    f"Avg: {avg_reward:7.1f} | "
                    f"DES: {des:.3f} | "
                    f"MTTC: {mttc:3.0f} | "
                    f"ASR: {asr:.2f} | "
                    f"Survive: {breach_prevented:.0f} | "
                    f"{elapsed/60:.1f}m"
                )

            # 체크포인트 저장
            if global_episode % args.save_interval == 0:
                ckpt_path = str(ckpt_dir / f"model_ep{global_episode}.pt")
                agent.save(ckpt_path)

                if wb_logger and args.wandb_save_model:
                    wb_logger.log_model_artifact(
                        ckpt_path,
                        name=f"model-ep{global_episode}",
                        metadata={"episode": global_episode, "avg_reward": avg_reward}
                    )

            # Best 모델 저장
            if avg_reward > best_reward:
                best_reward = avg_reward
                best_path = str(ckpt_dir / "best.pt")
                agent.save(best_path)

                if wb_logger and args.wandb_save_model:
                    wb_logger.log_model_artifact(
                        best_path,
                        name="best-model",
                        metadata={"episode": global_episode, "best_reward": best_reward}
                    )

            if avg_des > best_des:
                best_des = avg_des
                agent.save(str(ckpt_dir / "best_des.pt"))

        # Phase 종료 시 요약
        if wb_logger and phase_rewards:
            wb_logger.log_phase_summary(phase_idx, {
                "avg_reward": np.mean(phase_rewards),
                "avg_des": np.mean(phase_des),
                "survival_rate": np.mean(phase_survival),
            })

    # 최종 모델 저장
    agent.save(str(ckpt_dir / "final.pt"))
    agent.export_policy(str(ckpt_dir / "policy_deploy.pt"))

    # 설정 저장
    training_config = {
        "args": vars(args),
        "state_dim": STATE_DIM,
        "action_dim": ACTION_DIM,
        "feature_keys": FEATURE_KEYS,
        "action_keys": ACTION_PARAM_KEYS,
        "search_space": cfg.search_space.total_search_space,
        "best_reward": best_reward,
        "best_des": best_des,
        "total_episodes": global_episode,
    }

    config_path = ckpt_dir / "training_config.json"
    with open(config_path, "w") as f:
        json.dump(training_config, f, indent=2, default=to_serializable)

    with open(ckpt_dir / "training_metrics.json", "w") as f:
        json.dump(all_metrics, f, default=to_serializable)

    # W&B 최종 로깅
    if wb_logger:
        # 최종 모델 Artifact
        if args.wandb_save_model:
            wb_logger.log_model_artifact(
                str(ckpt_dir / "final.pt"),
                name="final-model",
                metadata={"total_episodes": global_episode, "best_reward": best_reward}
            )
            wb_logger.log_config_artifact(str(config_path))

        # 레벨별 성능
        level_summary = {}
        for level, metrics_list in level_metrics.items():
            if metrics_list:
                level_summary[level] = {
                    "avg_reward": np.mean([m["reward"] for m in metrics_list]),
                    "avg_des": np.mean([m["des"] for m in metrics_list]),
                    "survival_rate": np.mean([m["survival"] for m in metrics_list]),
                }
        wb_logger.log_level_performance(level_summary)

        # 최종 요약
        wb_logger.log_summary({
            "best_reward": best_reward,
            "best_des": best_des,
            "total_episodes": global_episode,
            "training_time_minutes": (time.time() - start_time) / 60,
        })

        wb_logger.finish()

    print(f"\n{'='*70}")
    print("✅ Training Complete!")
    print(f"Best avg reward: {best_reward:.1f}")
    print(f"Best avg DES: {best_des:.3f}")
    print(f"Checkpoints saved to: {ckpt_dir}")
    print(f"{'='*70}\n")

    return best_reward


# =============================================================================
# Evaluation Function
# =============================================================================
def evaluate(args):
    """모델 평가"""
    device = "cuda" if torch.cuda.is_available() and not args.cpu else "cpu"
    cfg = MTDConfig()

    agent = PPOAgent(cfg.ppo, device, hidden_size=args.hidden_size)
    if args.model:
        agent.load(args.model)

    test_levels = args.seeker_levels if args.eval_all_levels else [args.seeker_level]

    print(f"\n{'='*100}")
    print("MTD RL Evaluation - Academic Metrics")
    print(f"{'='*100}")
    print(
        f"{'Level':<18} {'DES':>8} {'MTTC':>8} {'ASR':>8} {'CDI':>8} "
        f"{'NED':>8} {'Cost':>8} {'Survival':>8}"
    )
    print("-" * 100)

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

            metrics_list.append(info if isinstance(info, dict) else {})

        # 집계
        agg = {}
        for key in metrics_list[0].keys() if metrics_list else []:
            vals = [m.get(key, 0) for m in metrics_list if isinstance(m.get(key), (int, float))]
            if vals:
                agg[key] = float(np.mean(vals))

        results[level] = agg
        name = SEEKER_PROFILES[level]["name"]

        print(
            f"L{level} {name:<12} "
            f"{agg.get('MTD/DES', 0):>8.3f} "
            f"{agg.get('MTD/MTTC', 0):>8.0f} "
            f"{agg.get('MTD/ASR', 0):>8.3f} "
            f"{agg.get('MTD/CDI', 0):>8.3f} "
            f"{agg.get('MTD/NED', 0):>8.3f} "
            f"{agg.get('Cost/Total', 0):>8.2f} "
            f"{agg.get('Defense/BreachPrevented', 0):>8.1%}"
        )

    print(f"{'='*100}\n")

    with open("eval_results.json", "w") as f:
        json.dump({str(k): v for k, v in results.items()}, f, indent=2, default=float)

    return results


# =============================================================================
# W&B Sweep Configuration
# =============================================================================
def get_sweep_config() -> Dict:
    """W&B Sweep 설정 반환"""
    return {
        "method": "bayes",
        "metric": {
            "name": "best_reward",
            "goal": "maximize"
        },
        "parameters": {
            "hidden_size": {
                "values": [128, 256, 512]
            },
            "learning_rate": {
                "distribution": "log_uniform_values",
                "min": 1e-5,
                "max": 1e-3
            },
            "batch_size": {
                "values": [32, 64, 128]
            },
            "gamma": {
                "distribution": "uniform",
                "min": 0.95,
                "max": 0.999
            },
            "gae_lambda": {
                "distribution": "uniform",
                "min": 0.9,
                "max": 0.99
            },
            "clip_epsilon": {
                "distribution": "uniform",
                "min": 0.1,
                "max": 0.3
            },
            "entropy_coef_start": {
                "distribution": "uniform",
                "min": 0.01,
                "max": 0.05
            },
        }
    }


def run_sweep_agent():
    """Sweep Agent 실행"""
    if not WANDB_AVAILABLE:
        print("❌ wandb not installed")
        return

    wandb.init()

    # wandb.config에서 하이퍼파라미터 가져오기
    config = wandb.config

    args = argparse.Namespace(
        episodes=300,
        max_steps=200,
        seed=42,
        cpu=False,
        hidden_size=config.get("hidden_size", 256),
        seeker_level=1,
        seeker_levels=[0, 1, 2, 3, 4],
        train_all_levels=True,
        curriculum=True,
        model=None,
        resume=None,
        checkpoint_dir=f"sweep_checkpoints/{wandb.run.id}",
        save_interval=100,
        log_interval=20,
        wandb=False,  # 이미 init됨
        wandb_project="",
        wandb_name="",
        wandb_tags="",
        wandb_notes="",
        wandb_save_model=False,
    )

    # Config 업데이트
    cfg = MTDConfig()
    cfg.ppo.learning_rate = config.get("learning_rate", 3e-4)
    cfg.ppo.batch_size = config.get("batch_size", 64)
    cfg.ppo.gamma = config.get("gamma", 0.99)
    cfg.ppo.gae_lambda = config.get("gae_lambda", 0.95)
    cfg.ppo.clip_epsilon = config.get("clip_epsilon", 0.2)
    cfg.ppo.entropy_coef_start = config.get("entropy_coef_start", 0.03)

    best_reward = train(args)

    wandb.log({"best_reward": best_reward})
    wandb.finish()


# =============================================================================
# CLI
# =============================================================================
def parse_args():
    parser = argparse.ArgumentParser(description="MTD RL Training v08.4 with W&B")

    # 기본 설정
    parser.add_argument("--test", action="store_true", help="평가 모드")
    parser.add_argument("--episodes", type=int, default=500)
    parser.add_argument("--max-steps", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--cpu", action="store_true")
    parser.add_argument("--hidden-size", type=int, default=256)

    # 공격자 설정
    parser.add_argument("--seeker-level", type=int, default=1, choices=[0, 1, 2, 3, 4])
    parser.add_argument("--seeker-levels", type=int, nargs="+", default=[0, 1, 2, 3, 4])
    parser.add_argument("--train-all-levels", action="store_true", dest="train_all_levels")

    # Curriculum Learning
    parser.add_argument("--curriculum", action="store_true")

    # 체크포인트
    parser.add_argument("--model", type=str)
    parser.add_argument("--resume", type=str)
    parser.add_argument("--checkpoint-dir", type=str, default="checkpoints_v08")
    parser.add_argument("--save-interval", type=int, default=100)
    parser.add_argument("--log-interval", type=int, default=10)

    # 평가 설정
    parser.add_argument("--eval-episodes", type=int, default=50)
    parser.add_argument("--eval-all-levels", action="store_true")

    # W&B 설정
    parser.add_argument("--wandb", action="store_true", help="W&B 로깅 활성화")
    parser.add_argument("--wandb-project", type=str, default="mtd-rl-v08")
    parser.add_argument("--wandb-name", type=str, default=None)
    parser.add_argument("--wandb-tags", type=str, default=None, help="쉼표로 구분된 태그")
    parser.add_argument("--wandb-notes", type=str, default=None)
    parser.add_argument("--wandb-save-model", action="store_true", help="모델 Artifact 저장")

    # Sweep
    parser.add_argument("--sweep", action="store_true", help="Sweep 설정 출력")
    parser.add_argument("--sweep-agent", action="store_true", help="Sweep Agent 실행")
    parser.add_argument("--sweep-id", type=str, default=None, help="Sweep ID")
    parser.add_argument("--sweep-count", type=int, default=10, help="Sweep 실행 횟수")

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    np.random.seed(args.seed)
    torch.manual_seed(args.seed)

    if args.sweep:
        # Sweep 설정 출력
        import yaml
        print("\n=== W&B Sweep Configuration ===")
        print(yaml.dump(get_sweep_config(), default_flow_style=False))
        print("\n사용법:")
        print("1. wandb sweep sweep_config.yaml")
        print("2. wandb agent <sweep_id>")

    elif args.sweep_agent:
        # Sweep Agent 실행
        if args.sweep_id:
            wandb.agent(args.sweep_id, function=run_sweep_agent, count=args.sweep_count)
        else:
            print("❌ --sweep-id 필요")

    elif args.test:
        evaluate(args)

    else:
        train(args)
