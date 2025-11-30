#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rl_train_v07.py

MTD Reinforcement Learning Training Script (v07)
- PPO with Curriculum Learning
- WandB Integration
- Argparse CLI Interface

Usage:
    # 기본 학습
    python rl_train_v07.py --episodes 1000 --wandb

    # 커리큘럼 학습
    python rl_train_v07.py --curriculum --episodes 1500 --wandb --project mtd-rl-v07

    # 특정 seeker level로 학습
    python rl_train_v07.py --seeker-level 3 --episodes 500

    # 모델 이어서 학습
    python rl_train_v07.py --resume checkpoints/model_ep500.pt --episodes 1000

    # 테스트 모드
    python rl_train_v07.py --test --model checkpoints/best_model.pt --episodes 10
"""

import os
import sys

# 현재 디렉토리를 path에 추가 (import 문제 해결)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import argparse
import json
import time
import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import deque
from dataclasses import dataclass, asdict

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.distributions import Normal

# 로컬 모듈 (절대 import)
from rl_config_v07 import (
    MTDConfig,
    STATE_DIM,
    ACTION_DIM,
    SEEKER_PROFILES,
    EpisodeMetrics,
)
from rl_environment_v07 import MTDEnvironment, StepOutcome


# =============================================================================
# PPO Actor-Critic Network
# =============================================================================
class ActorCritic(nn.Module):
    """PPO Actor-Critic Network with separate value and policy heads."""
    
    def __init__(
        self,
        state_dim: int,
        action_dim: int,
        hidden_dim: int = 256,
        log_std_init: float = -0.5,
    ):
        super().__init__()
        
        self.state_dim = state_dim
        self.action_dim = action_dim
        
        # Shared feature extractor
        self.shared = nn.Sequential(
            nn.Linear(state_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.ReLU(),
        )
        
        # Actor (policy) head
        self.actor_mean = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(hidden_dim // 2, action_dim),
            nn.Tanh(),  # Output in [-1, 1]
        )
        
        # Learnable log standard deviation
        self.actor_log_std = nn.Parameter(
            torch.ones(action_dim) * log_std_init
        )
        
        # Critic (value) head
        self.critic = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(hidden_dim // 2, 1),
        )
        
        # Initialize weights
        self._init_weights()
    
    def _init_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.orthogonal_(m.weight, gain=np.sqrt(2))
                nn.init.zeros_(m.bias)
    
    def forward(self, state: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        features = self.shared(state)
        action_mean = self.actor_mean(features)
        value = self.critic(features)
        return action_mean, value
    
    def get_action(
        self, 
        state: torch.Tensor, 
        deterministic: bool = False
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        Get action from policy.
        
        Returns:
            action, log_prob, value
        """
        action_mean, value = self.forward(state)
        
        if deterministic:
            return action_mean, torch.zeros(1), value
        
        std = torch.exp(self.actor_log_std)
        dist = Normal(action_mean, std)
        action = dist.sample()
        action = torch.clamp(action, -1.0, 1.0)
        log_prob = dist.log_prob(action).sum(dim=-1, keepdim=True)
        
        return action, log_prob, value
    
    def evaluate_actions(
        self, 
        states: torch.Tensor, 
        actions: torch.Tensor
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        Evaluate actions for PPO update.
        
        Returns:
            log_probs, values, entropy
        """
        action_mean, values = self.forward(states)
        std = torch.exp(self.actor_log_std)
        dist = Normal(action_mean, std)
        
        log_probs = dist.log_prob(actions).sum(dim=-1, keepdim=True)
        entropy = dist.entropy().sum(dim=-1, keepdim=True)
        
        return log_probs, values, entropy


# =============================================================================
# Rollout Buffer
# =============================================================================
class RolloutBuffer:
    """PPO Rollout Buffer for collecting trajectories."""
    
    def __init__(self, buffer_size: int, state_dim: int, action_dim: int):
        self.buffer_size = buffer_size
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.reset()
    
    def reset(self):
        self.states = []
        self.actions = []
        self.rewards = []
        self.values = []
        self.log_probs = []
        self.dones = []
        self.ptr = 0
    
    def add(
        self,
        state: np.ndarray,
        action: np.ndarray,
        reward: float,
        value: float,
        log_prob: float,
        done: bool,
    ):
        self.states.append(state)
        self.actions.append(action)
        self.rewards.append(reward)
        self.values.append(value)
        self.log_probs.append(log_prob)
        self.dones.append(done)
        self.ptr += 1
    
    def compute_returns_and_advantages(
        self,
        last_value: float,
        gamma: float = 0.99,
        gae_lambda: float = 0.95,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Compute GAE advantages and returns."""
        rewards = np.array(self.rewards)
        values = np.array(self.values + [last_value])
        dones = np.array(self.dones)
        
        advantages = np.zeros_like(rewards)
        last_gae = 0
        
        for t in reversed(range(len(rewards))):
            next_non_terminal = 1.0 - dones[t]
            delta = rewards[t] + gamma * values[t + 1] * next_non_terminal - values[t]
            advantages[t] = last_gae = delta + gamma * gae_lambda * next_non_terminal * last_gae
        
        returns = advantages + values[:-1]
        return returns, advantages
    
    def get_batches(
        self,
        batch_size: int,
        returns: np.ndarray,
        advantages: np.ndarray,
    ):
        """Generate minibatches for PPO update."""
        states = np.array(self.states)
        actions = np.array(self.actions)
        log_probs = np.array(self.log_probs)
        
        # Normalize advantages
        advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)
        
        indices = np.random.permutation(len(states))
        
        for start in range(0, len(states), batch_size):
            end = start + batch_size
            batch_indices = indices[start:end]
            
            yield (
                torch.FloatTensor(states[batch_indices]),
                torch.FloatTensor(actions[batch_indices]),
                torch.FloatTensor(log_probs[batch_indices]).unsqueeze(1),
                torch.FloatTensor(returns[batch_indices]).unsqueeze(1),
                torch.FloatTensor(advantages[batch_indices]).unsqueeze(1),
            )


# =============================================================================
# PPO Agent
# =============================================================================
class PPOAgent:
    """PPO Agent with training and evaluation methods."""
    
    def __init__(
        self,
        state_dim: int,
        action_dim: int,
        config: MTDConfig,
        device: str = "cpu",
    ):
        self.config = config
        self.device = torch.device(device)
        
        # Network
        self.policy = ActorCritic(
            state_dim=state_dim,
            action_dim=action_dim,
            hidden_dim=256,
        ).to(self.device)
        
        # Optimizer
        self.optimizer = optim.Adam(
            self.policy.parameters(),
            lr=config.ppo.learning_rate,
            eps=1e-5,
        )
        
        # PPO hyperparameters
        self.gamma = config.ppo.gamma
        self.gae_lambda = config.ppo.gae_lambda
        self.clip_epsilon = config.ppo.clip_epsilon
        self.entropy_coef = config.ppo.entropy_coef
        self.value_loss_coef = config.ppo.value_loss_coef
        self.max_grad_norm = config.ppo.max_grad_norm
        self.ppo_epochs = config.ppo.ppo_epochs
        self.minibatch_size = config.ppo.minibatch_size
        
        # Training state
        self.total_steps = 0
    
    def select_action(
        self, 
        state: np.ndarray, 
        deterministic: bool = False
    ) -> Tuple[np.ndarray, float, float]:
        """Select action given state."""
        state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)
        
        with torch.no_grad():
            action, log_prob, value = self.policy.get_action(
                state_tensor, deterministic=deterministic
            )
        
        return (
            action.cpu().numpy().squeeze(0),
            log_prob.cpu().item(),
            value.cpu().item(),
        )
    
    def update(self, buffer: RolloutBuffer, last_value: float) -> Dict[str, float]:
        """Perform PPO update."""
        # Compute returns and advantages
        returns, advantages = buffer.compute_returns_and_advantages(
            last_value=last_value,
            gamma=self.gamma,
            gae_lambda=self.gae_lambda,
        )
        
        # Training metrics
        total_policy_loss = 0
        total_value_loss = 0
        total_entropy = 0
        num_updates = 0
        
        # PPO epochs
        for _ in range(self.ppo_epochs):
            for batch in buffer.get_batches(self.minibatch_size, returns, advantages):
                states, actions, old_log_probs, batch_returns, batch_advantages = batch
                
                states = states.to(self.device)
                actions = actions.to(self.device)
                old_log_probs = old_log_probs.to(self.device)
                batch_returns = batch_returns.to(self.device)
                batch_advantages = batch_advantages.to(self.device)
                
                # Evaluate actions
                log_probs, values, entropy = self.policy.evaluate_actions(states, actions)
                
                # Policy loss (clipped surrogate)
                ratio = torch.exp(log_probs - old_log_probs)
                surr1 = ratio * batch_advantages
                surr2 = torch.clamp(
                    ratio, 
                    1.0 - self.clip_epsilon, 
                    1.0 + self.clip_epsilon
                ) * batch_advantages
                policy_loss = -torch.min(surr1, surr2).mean()
                
                # Value loss
                value_loss = nn.functional.mse_loss(values, batch_returns)
                
                # Entropy bonus
                entropy_loss = -entropy.mean()
                
                # Total loss
                loss = (
                    policy_loss 
                    + self.value_loss_coef * value_loss 
                    + self.entropy_coef * entropy_loss
                )
                
                # Optimization step
                self.optimizer.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(self.policy.parameters(), self.max_grad_norm)
                self.optimizer.step()
                
                total_policy_loss += policy_loss.item()
                total_value_loss += value_loss.item()
                total_entropy += -entropy_loss.item()
                num_updates += 1
        
        return {
            "policy_loss": total_policy_loss / num_updates,
            "value_loss": total_value_loss / num_updates,
            "entropy": total_entropy / num_updates,
        }
    
    def set_entropy_coef(self, coef: float):
        """Update entropy coefficient for curriculum learning."""
        self.entropy_coef = coef
    
    def save(self, path: str):
        """Save model checkpoint."""
        torch.save({
            "policy_state_dict": self.policy.state_dict(),
            "optimizer_state_dict": self.optimizer.state_dict(),
            "total_steps": self.total_steps,
            "entropy_coef": self.entropy_coef,
        }, path)
    
    def load(self, path: str):
        """Load model checkpoint."""
        checkpoint = torch.load(path, map_location=self.device)
        self.policy.load_state_dict(checkpoint["policy_state_dict"])
        self.optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
        self.total_steps = checkpoint.get("total_steps", 0)
        self.entropy_coef = checkpoint.get("entropy_coef", self.config.ppo.entropy_coef)


# =============================================================================
# Curriculum Manager
# =============================================================================
class CurriculumManager:
    """Manages curriculum learning progression."""
    
    def __init__(self, config: MTDConfig):
        self.config = config
        self.current_stage = 0
        self.stages = [
            {
                "name": "Stage 1: Basic Defense",
                "episodes": config.ppo.stage_1_episodes,
                "seeker_level": 0,
                "reward_profile": "explore",
                "entropy_coef": 0.01,
            },
            {
                "name": "Stage 2: Intermediate",
                "episodes": config.ppo.stage_2_episodes,
                "seeker_level": 2,
                "reward_profile": "explore",
                "entropy_coef": 0.005,
            },
            {
                "name": "Stage 3: Advanced",
                "episodes": config.ppo.stage_3_episodes,
                "seeker_level": 4,
                "reward_profile": "exploit",
                "entropy_coef": 0.001,
            },
        ]
    
    def get_stage(self, episode: int) -> Dict:
        """Get curriculum stage for given episode."""
        cumulative = 0
        for stage in self.stages:
            cumulative += stage["episodes"]
            if episode < cumulative:
                return stage
        return self.stages[-1]
    
    def should_advance(self, episode: int, avg_reward: float, threshold: float = 50.0) -> bool:
        """Check if curriculum should advance based on performance."""
        return avg_reward >= threshold


# =============================================================================
# Training Loop
# =============================================================================
def train(args):
    """Main training loop."""
    
    # Device
    device = "cuda" if torch.cuda.is_available() and not args.cpu else "cpu"
    print(f"Using device: {device}")
    
    # Config
    config = MTDConfig()
    
    # WandB initialization
    if args.wandb:
        import wandb
        wandb.init(
            project=args.project,
            name=args.run_name or f"mtd-v07-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}",
            config={
                "algorithm": "PPO",
                "state_dim": STATE_DIM,
                "action_dim": ACTION_DIM,
                "learning_rate": config.ppo.learning_rate,
                "gamma": config.ppo.gamma,
                "clip_epsilon": config.ppo.clip_epsilon,
                "entropy_coef": config.ppo.entropy_coef,
                "episodes": args.episodes,
                "max_steps": args.max_steps,
                "seeker_level": args.seeker_level,
                "curriculum": args.curriculum,
                "seed": args.seed,
            },
        )
    
    # Environment
    env = MTDEnvironment(
        seed=args.seed,
        seeker_level=args.seeker_level,
        config=config,
        initial_state_mode="partial_compromise",
    )
    
    # Agent
    agent = PPOAgent(
        state_dim=STATE_DIM,
        action_dim=ACTION_DIM,
        config=config,
        device=device,
    )
    
    # Resume from checkpoint
    if args.resume:
        print(f"Resuming from {args.resume}")
        agent.load(args.resume)
    
    # Curriculum manager
    curriculum = CurriculumManager(config) if args.curriculum else None
    
    # Rollout buffer
    buffer = RolloutBuffer(
        buffer_size=args.max_steps,
        state_dim=STATE_DIM,
        action_dim=ACTION_DIM,
    )
    
    # Checkpoints directory
    checkpoint_dir = Path(args.checkpoint_dir)
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    
    # Metrics
    episode_rewards = deque(maxlen=100)
    best_avg_reward = float("-inf")
    
    # Training loop
    print(f"\n{'='*60}")
    print("MTD RL Training (v07)")
    print(f"{'='*60}")
    print(f"Episodes: {args.episodes}")
    print(f"Max Steps: {args.max_steps}")
    print(f"Seeker Level: {args.seeker_level}")
    print(f"Curriculum: {args.curriculum}")
    print(f"{'='*60}\n")
    
    start_time = time.time()
    
    for episode in range(args.episodes):
        # Curriculum update
        if curriculum:
            stage = curriculum.get_stage(episode)
            env.set_seeker_level(stage["seeker_level"])
            env.set_reward_profile(stage["reward_profile"])
            agent.set_entropy_coef(stage["entropy_coef"])
            
            if episode % 100 == 0:
                print(f"[Curriculum] {stage['name']} | Seeker: L{stage['seeker_level']}")
        
        # Reset
        state, _ = env.reset(seed=args.seed + episode)
        buffer.reset()
        
        episode_reward = 0
        episode_steps = 0
        episode_info = {}
        
        # Episode loop
        for step in range(args.max_steps):
            # Select action
            action, log_prob, value = agent.select_action(state)
            
            # Step environment
            next_state, reward, terminated, truncated, info = env.step(action)
            done = terminated or truncated
            
            # Store transition
            buffer.add(
                state=state,
                action=action,
                reward=reward,
                value=value,
                log_prob=log_prob,
                done=done,
            )
            
            episode_reward += reward
            episode_steps += 1
            agent.total_steps += 1
            state = next_state
            
            if done:
                episode_info = info
                break
        
        # Get last value for bootstrapping
        _, _, last_value = agent.select_action(state)
        
        # PPO update
        update_metrics = agent.update(buffer, last_value)
        
        # Track rewards
        episode_rewards.append(episode_reward)
        avg_reward = np.mean(episode_rewards)
        
        # Logging
        if (episode + 1) % args.log_interval == 0:
            elapsed = time.time() - start_time
            print(
                f"Episode {episode + 1:4d} | "
                f"Reward: {episode_reward:8.2f} | "
                f"Avg(100): {avg_reward:8.2f} | "
                f"Steps: {episode_steps:3d} | "
                f"Time: {elapsed/60:.1f}m"
            )
        
        # WandB logging
        if args.wandb:
            wandb_log = {
                "episode": episode + 1,
                "reward": episode_reward,
                "avg_reward_100": avg_reward,
                "episode_steps": episode_steps,
                "total_steps": agent.total_steps,
                "policy_loss": update_metrics["policy_loss"],
                "value_loss": update_metrics["value_loss"],
                "entropy": update_metrics["entropy"],
            }
            
            # Add episode info
            for key, value in episode_info.items():
                if isinstance(value, (int, float)):
                    wandb_log[f"env/{key}"] = value
            
            if curriculum:
                wandb_log["curriculum/seeker_level"] = stage["seeker_level"]
                wandb_log["curriculum/entropy_coef"] = stage["entropy_coef"]
            
            wandb.log(wandb_log)
        
        # Save checkpoints
        if (episode + 1) % args.save_interval == 0:
            checkpoint_path = checkpoint_dir / f"model_ep{episode + 1}.pt"
            agent.save(str(checkpoint_path))
            print(f"Checkpoint saved: {checkpoint_path}")
        
        # Save best model
        if avg_reward > best_avg_reward:
            best_avg_reward = avg_reward
            best_path = checkpoint_dir / "best_model.pt"
            agent.save(str(best_path))
    
    # Final save
    final_path = checkpoint_dir / "final_model.pt"
    agent.save(str(final_path))
    print(f"\nTraining complete! Final model saved: {final_path}")
    print(f"Best avg reward: {best_avg_reward:.2f}")
    
    if args.wandb:
        wandb.finish()
    
    return agent


# =============================================================================
# Evaluation Loop
# =============================================================================
def evaluate(args):
    """Evaluation/Test loop."""
    
    device = "cuda" if torch.cuda.is_available() and not args.cpu else "cpu"
    config = MTDConfig()
    
    # Environment
    env = MTDEnvironment(
        seed=args.seed,
        seeker_level=args.seeker_level,
        config=config,
        initial_state_mode="partial_compromise",
    )
    
    # Agent
    agent = PPOAgent(
        state_dim=STATE_DIM,
        action_dim=ACTION_DIM,
        config=config,
        device=device,
    )
    
    # Load model
    if args.model:
        print(f"Loading model: {args.model}")
        agent.load(args.model)
    else:
        print("Warning: No model specified, using random policy")
    
    # Evaluation metrics
    all_rewards = []
    all_breaches = []
    all_decoy_hits = []
    all_costs = []
    
    print(f"\n{'='*60}")
    print("MTD RL Evaluation (v07)")
    print(f"{'='*60}")
    print(f"Model: {args.model}")
    print(f"Episodes: {args.episodes}")
    print(f"Seeker Level: {args.seeker_level}")
    print(f"{'='*60}\n")
    
    for episode in range(args.episodes):
        state, _ = env.reset(seed=args.seed + episode)
        episode_reward = 0
        
        for step in range(args.max_steps):
            action, _, _ = agent.select_action(state, deterministic=True)
            state, reward, terminated, truncated, info = env.step(action)
            episode_reward += reward
            
            if terminated or truncated:
                break
        
        all_rewards.append(episode_reward)
        all_breaches.append(info.get("Attack/SuccessfulBreaches", 0))
        all_decoy_hits.append(info.get("Decoy/Engagements", 0))
        all_costs.append(info.get("Cost/Total", 0))
        
        print(
            f"Episode {episode + 1:3d} | "
            f"Reward: {episode_reward:8.2f} | "
            f"Breaches: {all_breaches[-1]:.0f} | "
            f"Decoy Hits: {all_decoy_hits[-1]:.0f} | "
            f"Cost: {all_costs[-1]:.2f}"
        )
    
    # Summary
    print(f"\n{'='*60}")
    print("EVALUATION SUMMARY")
    print(f"{'='*60}")
    print(f"Avg Reward:     {np.mean(all_rewards):.2f} ± {np.std(all_rewards):.2f}")
    print(f"Avg Breaches:   {np.mean(all_breaches):.2f}")
    print(f"Avg Decoy Hits: {np.mean(all_decoy_hits):.2f}")
    print(f"Avg Cost:       {np.mean(all_costs):.2f}")
    print(f"{'='*60}\n")


# =============================================================================
# Main
# =============================================================================
def parse_args():
    parser = argparse.ArgumentParser(
        description="MTD RL Training Script (v07)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    
    # Mode
    parser.add_argument("--test", action="store_true", help="Run in test/evaluation mode")
    
    # Training
    parser.add_argument("--episodes", type=int, default=1000, help="Number of episodes")
    parser.add_argument("--max-steps", type=int, default=200, help="Max steps per episode")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--cpu", action="store_true", help="Force CPU usage")
    
    # Environment
    parser.add_argument("--seeker-level", type=int, default=1, choices=[0, 1, 2, 3, 4],
                        help="Attacker skill level (0-4)")
    parser.add_argument("--curriculum", action="store_true", help="Enable curriculum learning")
    
    # Model
    parser.add_argument("--model", type=str, default=None, help="Model path for testing")
    parser.add_argument("--resume", type=str, default=None, help="Resume training from checkpoint")
    
    # Checkpoints
    parser.add_argument("--checkpoint-dir", type=str, default="checkpoints",
                        help="Directory for saving checkpoints")
    parser.add_argument("--save-interval", type=int, default=100, help="Save checkpoint every N episodes")
    parser.add_argument("--log-interval", type=int, default=10, help="Log every N episodes")
    
    # WandB
    parser.add_argument("--wandb", action="store_true", help="Enable WandB logging")
    parser.add_argument("--project", type=str, default="mtd-rl-v07", help="WandB project name")
    parser.add_argument("--run-name", type=str, default=None, help="WandB run name")
    
    return parser.parse_args()


def main():
    args = parse_args()
    
    # Set seed
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    
    if args.test:
        evaluate(args)
    else:
        train(args)


if __name__ == "__main__":
    main()