#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MTD RL Training Script v07 - Complete logging & policy export."""
from __future__ import annotations

import argparse
import datetime
import json
import time
from collections import deque
from pathlib import Path
from typing import Dict, List

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.distributions import Normal

from .rl_config_v07 import (
    ACTION_DIM, ACTION_PARAM_KEYS, DEFAULT_SEEKER_PROFILES,
    FEATURE_KEYS, STATE_DIM, EpisodeStats, MTDConfig, PPOConfig,
)
from .rl_environment_v07 import MTDEnvironment


# ---------------------------------------------------------------------------
# Actor-Critic Network
# ---------------------------------------------------------------------------
class ActorCritic(nn.Module):
    def __init__(self, state_dim: int, action_dim: int, hidden: int = 256):
        super().__init__()
        self.shared = nn.Sequential(
            nn.Linear(state_dim, hidden), nn.LayerNorm(hidden), nn.ReLU(),
            nn.Linear(hidden, hidden), nn.LayerNorm(hidden), nn.ReLU(),
        )
        self.actor = nn.Sequential(
            nn.Linear(hidden, hidden // 2), nn.ReLU(),
            nn.Linear(hidden // 2, action_dim), nn.Tanh(),
        )
        self.log_std = nn.Parameter(torch.ones(action_dim) * -0.5)
        self.critic = nn.Sequential(
            nn.Linear(hidden, hidden // 2), nn.ReLU(),
            nn.Linear(hidden // 2, 1),
        )
        self._init()

    def _init(self):
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.orthogonal_(m.weight, gain=np.sqrt(2))
                nn.init.zeros_(m.bias)

    def forward(self, x):
        feat = self.shared(x)
        return self.actor(feat), self.critic(feat)

    def act(self, state, deterministic=False):
        mean, value = self.forward(state)
        if deterministic:
            return mean, torch.zeros(1), value
        std = torch.exp(self.log_std)
        dist = Normal(mean, std)
        action = torch.clamp(dist.sample(), -1, 1)
        log_prob = dist.log_prob(action).sum(-1, keepdim=True)
        return action, log_prob, value

    def evaluate(self, states, actions):
        mean, values = self.forward(states)
        std = torch.exp(self.log_std)
        dist = Normal(mean, std)
        log_probs = dist.log_prob(actions).sum(-1, keepdim=True)
        entropy = dist.entropy().sum(-1, keepdim=True)
        return log_probs, values, entropy


# ---------------------------------------------------------------------------
# Rollout Buffer
# ---------------------------------------------------------------------------
class RolloutBuffer:
    def __init__(self):
        self.clear()

    def add(self, s, a, r, v, lp, d):
        self.states.append(s)
        self.actions.append(a)
        self.rewards.append(r)
        self.values.append(v)
        self.log_probs.append(lp)
        self.dones.append(d)

    def clear(self):
        self.states, self.actions, self.rewards = [], [], []
        self.values, self.log_probs, self.dones = [], [], []

    def compute_gae(self, last_val, gamma, lam):
        rewards = np.array(self.rewards)
        values = np.array(self.values + [last_val])
        dones = np.array(self.dones)
        advs = np.zeros_like(rewards)
        gae = 0.0
        for t in reversed(range(len(rewards))):
            mask = 1.0 - dones[t]
            delta = rewards[t] + gamma * values[t + 1] * mask - values[t]
            gae = delta + gamma * lam * mask * gae
            advs[t] = gae
        returns = advs + values[:-1]
        advs = (advs - advs.mean()) / (advs.std() + 1e-8)
        return returns, advs

    def iter_batches(self, batch_size, returns, advs):
        n = len(self.states)
        idx = np.random.permutation(n)
        for start in range(0, n, batch_size):
            batch = idx[start:start + batch_size]
            yield (
                torch.FloatTensor(np.array(self.states)[batch]),
                torch.FloatTensor(np.array(self.actions)[batch]),
                torch.FloatTensor(np.array(self.log_probs)[batch]).unsqueeze(1),
                torch.FloatTensor(returns[batch]).unsqueeze(1),
                torch.FloatTensor(advs[batch]).unsqueeze(1),
            )


# ---------------------------------------------------------------------------
# PPO Agent
# ---------------------------------------------------------------------------
class PPOAgent:
    def __init__(self, cfg: PPOConfig, device="cpu"):
        self.cfg = cfg
        self.device = device
        self.policy = ActorCritic(STATE_DIM, ACTION_DIM).to(device)
        self.optimizer = optim.Adam(self.policy.parameters(), lr=cfg.learning_rate, eps=1e-5)
        self.entropy_coef = cfg.entropy_coef_start

    def select_action(self, state, deterministic=False):
        state_t = torch.FloatTensor(state).unsqueeze(0).to(self.device)
        with torch.no_grad():
            action, log_prob, value = self.policy.act(state_t, deterministic)
        return action.cpu().numpy().squeeze(), log_prob.item(), value.item()

    def update(self, buffer, last_val):
        returns, advs = buffer.compute_gae(last_val, self.cfg.gamma, self.cfg.gae_lambda)
        total_pl, total_vl, total_ent, n = 0.0, 0.0, 0.0, 0

        for _ in range(self.cfg.update_epochs):
            for states, actions, old_lp, rets, adv in buffer.iter_batches(self.cfg.batch_size, returns, advs):
                states, actions = states.to(self.device), actions.to(self.device)
                old_lp, rets, adv = old_lp.to(self.device), rets.to(self.device), adv.to(self.device)

                log_probs, values, entropy = self.policy.evaluate(states, actions)
                ratio = torch.exp(log_probs - old_lp)
                surr1 = ratio * adv
                surr2 = torch.clamp(ratio, 1 - self.cfg.clip_epsilon, 1 + self.cfg.clip_epsilon) * adv
                policy_loss = -torch.min(surr1, surr2).mean()
                value_loss = nn.functional.mse_loss(values, rets)
                entropy_loss = -entropy.mean()

                loss = policy_loss + self.cfg.value_loss_coef * value_loss + self.entropy_coef * entropy_loss
                self.optimizer.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(self.policy.parameters(), self.cfg.max_grad_norm)
                self.optimizer.step()

                total_pl += policy_loss.item()
                total_vl += value_loss.item()
                total_ent += -entropy_loss.item()
                n += 1

        return {"policy_loss": total_pl / n, "value_loss": total_vl / n, "entropy": total_ent / n}

    def save(self, path):
        torch.save({
            "policy": self.policy.state_dict(),
            "optimizer": self.optimizer.state_dict(),
            "entropy_coef": self.entropy_coef
        }, path)
        print(f"✅ Policy saved: {path}")

    def load(self, path):
        ckpt = torch.load(path, map_location=self.device, weights_only=True)
        self.policy.load_state_dict(ckpt["policy"])
        self.optimizer.load_state_dict(ckpt["optimizer"])
        self.entropy_coef = ckpt.get("entropy_coef", self.cfg.entropy_coef_start)
        print(f"✅ Policy loaded: {path}")

    def export_for_deployment(self, path):
        """배포용 정책만 저장"""
        torch.save(self.policy.state_dict(), path)
        print(f"✅ Deployment policy exported: {path}")


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------
def train(args):
    device = "cuda" if torch.cuda.is_available() and not args.cpu else "cpu"
    print(f"Device: {device}")

    cfg = MTDConfig()
    cfg.ppo.total_episodes = args.episodes
    cfg.ppo.max_steps = args.max_steps

    # Checkpoint directory
    ckpt_dir = Path(args.checkpoint_dir)
    ckpt_dir.mkdir(parents=True, exist_ok=True)

    # Wandb
    if args.wandb:
        import wandb
        run_name = args.wandb_name or f"mtd-{datetime.datetime.now():%m%d-%H%M}"
        wandb.init(project=args.wandb_project, name=run_name, config=vars(args))

    agent = PPOAgent(cfg.ppo, device)
    if args.resume:
        agent.load(args.resume)

    # Curriculum setup
    if args.curriculum:
        phases = cfg.curriculum.phases
        phase_eps = cfg.curriculum.phase_episodes
        entropy_sched = cfg.curriculum.entropy_schedule
    else:
        levels = args.seeker_levels if args.train_all_levels else [args.seeker_level]
        phases = [tuple(levels)] * 5
        phase_eps = [args.episodes // 5] * 5
        entropy_sched = [0.01, 0.008, 0.005, 0.003, 0.001]

    rewards_hist = deque(maxlen=100)
    best_reward = float("-inf")
    all_metrics: List[Dict] = []
    start = time.time()
    ep_global = 0

    print(f"\n{'='*70}\nMTD RL Training v07\n{'='*70}")
    print(f"Search Space: {cfg.search_space.total_search_space} (IP:{cfg.search_space.ip_pool_size} × Port:{cfg.search_space.port_pool_size})")
    print(f"Total Episodes: {args.episodes} | Curriculum: {args.curriculum}\n")

    for phase_idx, (phase_levels, n_eps, ent_coef) in enumerate(zip(phases, phase_eps, entropy_sched)):
        print(f"\n--- Phase {phase_idx}: Levels {phase_levels}, Episodes {n_eps}, Entropy {ent_coef} ---")
        agent.entropy_coef = ent_coef
        profile = "explore" if phase_idx < 2 else "exploit"

        for ep_in_phase in range(n_eps):
            ep_global += 1
            level = int(np.random.choice(phase_levels))

            env = MTDEnvironment(
                seed=args.seed + ep_global,
                seeker_level=level,
                seeker_profiles_path=args.seeker_profiles_path,
                config=cfg,
            )
            env.set_reward_profile(profile)

            buffer = RolloutBuffer()
            state, info = env.reset()
            ep_reward = 0.0
            ep_actions = []

            for step in range(args.max_steps):
                action, log_prob, value = agent.select_action(state)
                next_state, reward, term, trunc, info = env.step(action)
                buffer.add(state, action, reward, value, log_prob, term or trunc)
                ep_reward += reward
                ep_actions.append((action + 1) / 2)  # Scaled [0,1]
                state = next_state
                if term or trunc:
                    break

            _, _, last_val = agent.select_action(state)
            losses = agent.update(buffer, last_val)
            rewards_hist.append(ep_reward)
            avg = np.mean(rewards_hist)

            # Compute action statistics
            ep_actions = np.array(ep_actions)
            action_means = ep_actions.mean(axis=0) if len(ep_actions) > 0 else np.zeros(ACTION_DIM)

            # Collect all metrics
            ep_metrics = {
                "episode": ep_global,
                "phase": phase_idx,
                "seeker_level": level,
                "reward": ep_reward,
                "avg_reward": avg,
                **info,
                **losses,
                **{f"Action/{ACTION_PARAM_KEYS[i]}": action_means[i] for i in range(ACTION_DIM)},
            }
            all_metrics.append(ep_metrics)

            # Logging
            if ep_global % args.log_interval == 0:
                elapsed = time.time() - start
                s_mtd = info.get("Defense/S_MTD", 0)
                svc_found = info.get("Attack/ServicesFound", 0)
                print(f"Ep {ep_global:4d} | P{phase_idx} L{level} | R: {ep_reward:7.1f} | "
                      f"Avg: {avg:7.1f} | S_MTD: {s_mtd:.3f} | Found: {svc_found} | {elapsed/60:.1f}m")

            if args.wandb:
                import wandb
                wandb.log(ep_metrics)

            # Save checkpoints
            if ep_global % args.save_interval == 0:
                agent.save(str(ckpt_dir / f"model_ep{ep_global}.pt"))

            if avg > best_reward:
                best_reward = avg
                agent.save(str(ckpt_dir / "best.pt"))

    # Final saves
    agent.save(str(ckpt_dir / "final.pt"))
    agent.export_for_deployment(str(ckpt_dir / "policy_deploy.pt"))

    # Save training config & metrics
    with open(ckpt_dir / "training_config.json", "w") as f:
        json.dump({
            "args": vars(args),
            "state_dim": STATE_DIM,
            "action_dim": ACTION_DIM,
            "feature_keys": FEATURE_KEYS,
            "action_keys": ACTION_PARAM_KEYS,
            "search_space": cfg.search_space.total_search_space,
        }, f, indent=2)

    with open(ckpt_dir / "training_metrics.json", "w") as f:
        json.dump(all_metrics, f, indent=2)
    def convert_to_serializable(obj):
    #"""numpy 타입을 Python 기본 타입으로 변환"""
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

    # JSON 저장 시:
    with open(ckpt_dir / "training_metrics.json", "w") as f:
        json.dump(convert_to_serializable(all_metrics), f, indent=2)
    print(f"\n{'='*70}")
    print(f"Training Complete!")
    print(f"Best avg reward: {best_reward:.1f}")
    print(f"Checkpoints saved to: {ckpt_dir}")
    print(f"{'='*70}\n")

    if args.wandb:
        import wandb
        wandb.finish()


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------
def evaluate(args):
    device = "cuda" if torch.cuda.is_available() and not args.cpu else "cpu"
    cfg = MTDConfig()
    agent = PPOAgent(cfg.ppo, device)

    if args.model:
        agent.load(args.model)

    test_levels = args.seeker_levels if args.eval_all_levels else [args.seeker_level]

    print(f"\n{'='*80}")
    print(f"MTD RL Evaluation - Robustness Matrix")
    print(f"{'='*80}")
    print(f"{'Level':<18} {'R_succ':>8} {'S_MTD':>8} {'Decoy':>8} {'Found':>8} {'Cost':>8} {'TTBr':>8}")
    print("-" * 80)

    results = {}
    for lvl in test_levels:
        metrics_list = []

        for ep in range(args.eval_episodes):
            env = MTDEnvironment(seed=args.seed + ep * 100 + lvl, seeker_level=lvl, config=cfg)
            state, _ = env.reset()

            for _ in range(args.max_steps):
                action, _, _ = agent.select_action(state, deterministic=True)
                state, _, term, trunc, info = env.step(action)
                if term or trunc:
                    break

            metrics_list.append(info)

        # Aggregate
        agg = {k: np.mean([m.get(k, 0) for m in metrics_list]) for k in metrics_list[0].keys()}
        results[lvl] = agg

        name = DEFAULT_SEEKER_PROFILES[lvl]["name"]
        print(f"L{lvl} {name:<12} "
              f"{agg.get('Defense/Success', 0):>8.3f} "
              f"{agg.get('Defense/S_MTD', 0):>8.3f} "
              f"{agg.get('Decoy/Hits', 0):>8.1f} "
              f"{agg.get('Attack/ServicesFound', 0):>8.1f} "
              f"{agg.get('Cost/Total', 0):>8.2f} "
              f"{agg.get('Attack/TimeToBreach', 0):>8.1f}")

    print(f"{'='*80}\n")

    # Save results
    with open("eval_results.json", "w") as f:
        json.dump({str(k): v for k, v in results.items()}, f, indent=2)

    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args():
    p = argparse.ArgumentParser(description="MTD RL Training v07")
    p.add_argument("--test", action="store_true")
    p.add_argument("--total-episodes", type=int, default=500, dest="episodes")
    p.add_argument("--eval-episodes", type=int, default=50)
    p.add_argument("--max-steps", type=int, default=200)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--cpu", action="store_true")
    p.add_argument("--seeker-level", type=int, default=1, choices=[0, 1, 2, 3, 4])
    p.add_argument("--seeker-levels", type=int, nargs="+", default=[0, 1, 2, 3, 4])
    p.add_argument("--seeker-profiles-path", type=str, default=None)
    p.add_argument("--train-all-seeker-levels", action="store_true", dest="train_all_levels")
    p.add_argument("--eval-all-levels", action="store_true")
    p.add_argument("--curriculum", action="store_true")
    p.add_argument("--model", type=str)
    p.add_argument("--resume", type=str)
    p.add_argument("--checkpoint-dir", type=str, default="checkpoints")
    p.add_argument("--save-interval", type=int, default=100)
    p.add_argument("--log-interval", type=int, default=10)
    p.add_argument("--wandb", action="store_true")
    p.add_argument("--wandb-project", type=str, default="mtd-rl-v07")
    p.add_argument("--wandb-run-name", type=str, dest="wandb_name")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    if args.test:
        evaluate(args)
    else:
        train(args)