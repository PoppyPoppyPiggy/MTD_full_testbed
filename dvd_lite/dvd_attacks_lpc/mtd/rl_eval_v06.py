#!/usr/bin/env python3
"""
rl_eval_v06.py
=================

This module provides a simple evaluation routine for a PPO agent
trained on the v06 MTD environment. Given a saved policy
(e.g. ``final_policy.pth``) it will run a number of episodes in
``MTDEnvironment`` and report aggregated metrics such as mean total
reward, defence success rate, combined MTD score and mean values of
each policy parameter. It reuses the ``calculate_metrics_from_infos``
function from the training script to summarise per‑episode metrics.

Example usage::

    # Evaluate a trained model over 50 episodes with seeker level 2
    python3 -m mtd.rl_eval_v06 --model ./runs/.../final_policy.pth \
        --episodes 50 --seeker-level 2 --max-steps 200

The script prints a JSON‑like summary of averaged metrics across all
episodes. You can adjust the number of evaluation episodes, the
attacker difficulty (seeker level) and the maximum steps per episode
via command line arguments.

Note: Evaluation runs do not update the model or environment state
persistent files (e.g. ``mtd_state.json``) beyond the scope of each
episode.
"""

import argparse
import json
import logging
import os
from typing import Dict, Any

import numpy as np
import torch

# Import the environment, model architecture and config
# NOTE: Ensure rl_environment_v06.py, rl_config_v06.py, and rl_train_v06.py exist and are correct in the environment.
from .rl_environment_v06 import MTDEnvironment
# We define our own ActorCritic here rather than importing from the
# training module. The architecture matches the one used during
# training (two hidden layers with Tanh activations, separate actor
# mean head, critic head and a learnable log_std parameter). This
# definition ensures that we can load a saved policy's state dict
# without requiring the original training module.
import torch.nn as nn
from torch.distributions.normal import Normal

# These constants mirror those used in the training code
LOG_STD_MAX = 2
LOG_STD_MIN = -20


class ActorCritic(nn.Module):
    """Simple actor‑critic network for continuous action spaces."""

    def __init__(self, state_dim: int, action_dim: int, hidden_size: int = 128) -> None:
        super().__init__()
        # Two hidden layers with orthogonal initialisation
        self.feature_extractor = nn.Sequential(
            self._layer_init(nn.Linear(state_dim, hidden_size)),
            nn.Tanh(),
            self._layer_init(nn.Linear(hidden_size, hidden_size)),
            nn.Tanh(),
        )
        # Actor head outputs mean of a Normal distribution over actions
        self.actor_mean = self._layer_init(
            nn.Linear(hidden_size, action_dim), std=0.01
        )
        # Critic head outputs a scalar value estimate
        self.critic = self._layer_init(nn.Linear(hidden_size, 1))
        # Log standard deviation parameter (learned)
        self.log_std = nn.Parameter(torch.zeros(action_dim))
        self.log_std.data.fill_(0.0)

    def _layer_init(self, layer: nn.Module, std: float = np.sqrt(2), bias_const: float = 0.0) -> nn.Module:
        """Orthogonal weight initialisation and constant bias."""
        nn.init.orthogonal_(layer.weight, std)
        nn.init.constant_(layer.bias, bias_const)
        return layer

    def get_value(self, x: torch.Tensor) -> torch.Tensor:
        """Return the value estimate for the given state batch."""
        return self.critic(self.feature_extractor(x))

    def get_action_and_value(self, x: torch.Tensor, action: torch.Tensor = None):
        """Sample an action and return it along with log_prob and value."""
        feats = self.feature_extractor(x)
        mean = self.actor_mean(feats)
        # Clamp the log_std to prevent extreme variance
        log_std = torch.clamp(self.log_std, LOG_STD_MIN, LOG_STD_MAX)
        std = torch.exp(log_std)
        dist = Normal(mean, std)
        if action is None:
            action = dist.sample()
        log_prob = dist.log_prob(action).sum(dim=1)
        entropy = dist.entropy().sum(dim=1)
        value = self.critic(feats).flatten()
        return action, log_prob, entropy, value

    def get_log_prob(self, x: torch.Tensor, action: torch.Tensor):
        """Compute log probability and entropy for a given action."""
        feats = self.feature_extractor(x)
        mean = self.actor_mean(feats)
        log_std = torch.clamp(self.log_std, LOG_STD_MIN, LOG_STD_MAX)
        std = torch.exp(log_std)
        dist = Normal(mean, std)
        log_prob = dist.log_prob(action).sum(dim=1)
        entropy = dist.entropy().sum(dim=1)
        value = self.critic(feats).flatten()
        return log_prob, entropy, value

# Assuming these are defined in the correct imported modules:
from .rl_config_v06 import STATE_DIM, ACTION_DIM
from .rl_train_v06 import calculate_metrics_from_infos

logger = logging.getLogger("MTDEval")
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def evaluate(model_path: str,
             episodes: int = 10,
             seeker_level: int = 2,
             max_steps: int = 200,
             device: str = "cpu") -> Dict[str, Any]:
    """
    Evaluate a trained PPO policy on the MTD environment.

    :param model_path: Path to the saved PyTorch model (policy network)
    :param episodes: Number of episodes to run for evaluation
    :param seeker_level: Difficulty level of the heuristic attacker (0–4)
    :param max_steps: Maximum steps per episode
    :param device: Device to load the model on ("cpu" or "cuda")
    :return: A dictionary of averaged metrics over all evaluation episodes
    """
    device_t = torch.device(device)
    # Load policy network
    model = ActorCritic(state_dim=STATE_DIM, action_dim=ACTION_DIM, hidden_size=128)
    model.load_state_dict(torch.load(model_path, map_location=device_t))
    model.to(device_t)
    model.eval()

    # Create evaluation environment
    env = MTDEnvironment(seeker_level=seeker_level)
    env.max_episode_steps = max_steps

    # Aggregators for metrics
    reward_total = []
    metrics_total: Dict[str, list] = {}

    for ep in range(episodes):
        state, _ = env.reset()
        done = False
        ep_reward = 0.0
        ep_infos = []
        steps = 0

        while not done and steps < max_steps:
            state_tensor = torch.as_tensor(state, dtype=torch.float32, device=device_t).unsqueeze(0)
            with torch.no_grad():
                # FIX: Model returns 4 values, explicitly unpack all 4.
                action, _, _, _ = model.get_action_and_value(state_tensor)
                
            # Convert tensor to numpy array for the environment
            action_np = action.squeeze(0).cpu().numpy()
            next_state, reward, terminated, truncated, info = env.step(action_np)
            ep_reward += reward
            ep_infos.append(info.copy())
            state = next_state
            done = terminated or truncated
            steps += 1

        reward_total.append(ep_reward)
        # Aggregate metrics for this episode using the training helper
        ep_metrics = calculate_metrics_from_infos(ep_infos)
        # Collect each metric across episodes
        for k, v in ep_metrics.items():
            metrics_total.setdefault(k, []).append(v)

        logger.debug(f"Episode {ep+1}/{episodes}: reward={ep_reward:.2f}, metrics={ep_metrics}")

    # Average metrics across episodes
    result = {
        "episodes": episodes,
        "seeker_level": seeker_level,
        "average_total_reward": float(np.mean(reward_total)) if reward_total else 0.0,
    }
    for k, vals in metrics_total.items():
        if vals:
            result[k] = float(np.mean(vals))

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate a trained PPO policy on the MTD environment (v06)")
    parser.add_argument('--model', type=str, required=True, help='Path to the saved policy .pth file')
    parser.add_argument('--episodes', type=int, default=20, help='Number of evaluation episodes')
    parser.add_argument('--seeker-level', type=int, default=2, help='Seeker difficulty level (0-4)')
    parser.add_argument('--max-steps', type=int, default=200, help='Maximum steps per episode')
    parser.add_argument('--device', type=str, default='cpu', help='Device for model evaluation (cpu or cuda)')
    parser.add_argument('--output', type=str, default=None, help='Optional path to save the evaluation summary as JSON')
    args = parser.parse_args()

    summary = evaluate(
        model_path=args.model,
        episodes=args.episodes,
        seeker_level=args.seeker_level,
        max_steps=args.max_steps,
        device=args.device
    )

    # Print summary
    print(json.dumps(summary, indent=2))
    # Optionally write to file
    if args.output:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(summary, f, indent=2)
            logger.info(f"Evaluation summary saved to {args.output}")
        except Exception as e:
            logger.error(f"Failed to write evaluation summary: {e}")


if __name__ == '__main__':
    main()