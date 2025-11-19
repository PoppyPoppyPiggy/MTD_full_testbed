# File: MTD_full_testbed/dvd_lite/dvd_attacks_lpc/mtd/rl_agent_ppo_v05.py
#
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[신규 5/8] MTD_RL v05 - 정석 PPO 에이전트 (Continuous)

- [v04 대비 변경점] 임포트 경로만 v05로 변경, 로직은 100% 동일.
"""

import torch
import torch.nn as nn
import torch.optim as optim
from torch.distributions.normal import Normal
import numpy as np
from typing import List, Dict, Any, Tuple

from mtd.rl_model_v05 import MTDPolicyNet, MTDValueNet
from mtd.rl_config_v05 import ACTION_DIM # 6D

class RolloutBuffer:
    def __init__(self, batch_size: int, obs_dim: int, gamma: float, gae_lambda: float, device):
        self.batch_size = batch_size
        self.obs_dim = obs_dim
        self.gamma = gamma
        self.gae_lambda = gae_lambda
        self.device = device
        self.obs = np.zeros((batch_size, obs_dim), dtype=np.float32)
        self.actions = np.zeros((batch_size, ACTION_DIM), dtype=np.float32) 
        self.logprobs = np.zeros(batch_size, dtype=np.float32)
        self.rewards = np.zeros(batch_size, dtype=np.float32)
        self.dones = np.zeros(batch_size, dtype=np.float32)
        self.values = np.zeros(batch_size, dtype=np.float32)
        self.advantages = np.zeros(batch_size, dtype=np.float32)
        self.returns = np.zeros(batch_size, dtype=np.float32)
        self.ptr, self.path_start_idx = 0, 0

    def add(self, obs, action, reward, done, logprob, value):
        if self.ptr >= self.batch_size:
            raise ValueError(f"RolloutBuffer가 가득 찼습니다.")
        self.obs[self.ptr] = obs
        self.actions[self.ptr] = action
        self.rewards[self.ptr] = reward
        self.dones[self.ptr] = float(done)
        self.logprobs[self.ptr] = logprob
        self.values[self.ptr] = value
        self.ptr += 1

    def finish_path(self, last_value: float):
        path_slice = slice(self.path_start_idx, self.ptr)
        rewards = np.append(self.rewards[path_slice], last_value)
        values = np.append(self.values[path_slice], last_value)
        dones = np.append(self.dones[path_slice], 0.0)
        gae = 0
        for t in reversed(range(len(rewards) - 1)):
            delta = rewards[t] + self.gamma * values[t+1] * (1.0 - dones[t]) - values[t]
            gae = delta + self.gamma * self.gae_lambda * (1.0 - dones[t]) * gae
            self.advantages[self.path_start_idx + t] = gae
        self.returns[path_slice] = self.advantages[path_slice] + self.values[path_slice]
        self.path_start_idx = self.ptr
        if self.ptr == self.batch_size:
             self.path_start_idx = 0
             self.ptr = 0

    def get_batch(self, minibatch_size: int):
        if self.ptr != 0 or self.path_start_idx != 0:
             raise ValueError("get_batch()는 finish_path() 직후, 버퍼가 꽉 찼을 때만 호출해야 합니다.")
        adv_mean = np.mean(self.advantages)
        adv_std = np.std(self.advantages) + 1e-8
        self.advantages = (self.advantages - adv_mean) / adv_std
        indices = np.arange(self.batch_size)
        np.random.shuffle(indices)
        for start in range(0, self.batch_size, minibatch_size):
            end = start + minibatch_size
            batch_indices = indices[start:end]
            yield (
                torch.tensor(self.obs[batch_indices]).to(self.device),
                torch.tensor(self.actions[batch_indices]).to(self.device),
                torch.tensor(self.logprobs[batch_indices]).to(self.device),
                torch.tensor(self.advantages[batch_indices]).to(self.device),
                torch.tensor(self.returns[batch_indices]).to(self.device),
                torch.tensor(self.values[batch_indices]).to(self.device),
            )

class PPOAgent:
    def __init__(self, cfg, obs_dim: int, act_dim: int):
        self.cfg = cfg
        self.device = torch.device(cfg.device)
        self.policy = MTDPolicyNet(obs_dim, act_dim).to(self.device)
        self.value_net = MTDValueNet(obs_dim).to(self.device)
        self.optimizer_policy = optim.Adam(self.policy.parameters(), lr=cfg.lr, eps=1e-5)
        self.optimizer_value = optim.Adam(self.value_net.parameters(), lr=cfg.lr, eps=1e-5)
        self.mse_loss = nn.MSELoss()
        self.state_history: List[np.ndarray] = []

    def get_action_and_value(self, obs_tensor: torch.Tensor, action: torch.Tensor = None) -> Tuple:
        dist = self.policy(obs_tensor) # Normal(mean, std)
        if action is None:
            action = dist.sample()
        log_prob = dist.log_prob(action).sum(dim=-1)
        entropy = dist.entropy().sum(dim=-1)
        value = self.value_net(obs_tensor).squeeze(-1)
        return action, log_prob, value, entropy

    def update(self, buffer: RolloutBuffer) -> Dict[str, float]:
        clip_fracs, approx_kls, policy_losses, value_losses, entropy_losses = [], [], [], [], []
        for epoch in range(self.cfg.n_epochs):
            for batch in buffer.get_batch(self.cfg.minibatch_size):
                obs, actions, old_logprobs, advantages, returns, old_values = batch
                
                _, new_logprobs, _, entropy = self.get_action_and_value(obs, actions)
                
                log_ratio = new_logprobs - old_logprobs
                ratio = torch.exp(log_ratio)
                
                with torch.no_grad():
                    approx_kl = ((ratio - 1) - log_ratio).mean().item()
                    clip_frac = torch.mean((torch.abs(ratio - 1.0) > self.cfg.clip_eps).float()).item()
                    approx_kls.append(approx_kl)
                    clip_fracs.append(clip_frac)

                surr1 = ratio * advantages
                surr2 = torch.clamp(ratio, 1.0 - self.cfg.clip_eps, 1.0 + self.cfg.clip_eps) * advantages
                
                policy_loss = -torch.min(surr1, surr2).mean()
                entropy_loss = -self.cfg.ent_coef * entropy.mean()
                loss_policy = policy_loss + entropy_loss
                
                self.optimizer_policy.zero_grad()
                loss_policy.backward()
                nn.utils.clip_grad_norm_(self.policy.parameters(), self.cfg.max_grad_norm)
                self.optimizer_policy.step()

                new_values = self.value_net(obs).squeeze(-1)
                v_loss_unclipped = (new_values - returns) ** 2
                v_clipped = old_values + torch.clamp(new_values - old_values, -self.cfg.clip_eps, self.cfg.clip_eps)
                v_loss_clipped = (v_clipped - returns) ** 2
                v_loss_max = torch.max(v_loss_unclipped, v_loss_clipped)
                value_loss = 0.5 * v_loss_max.mean() * self.cfg.vf_coef

                self.optimizer_value.zero_grad()
                value_loss.backward()
                nn.utils.clip_grad_norm_(self.value_net.parameters(), self.cfg.max_grad_norm)
                self.optimizer_value.step()
                
                policy_losses.append(policy_loss.item())
                value_losses.append(value_loss.item())
                entropy_losses.append(entropy_loss.item())
        return {
            "policy_loss": np.mean(policy_losses),
            "value_loss": np.mean(value_losses),
            "entropy_loss": np.mean(entropy_losses),
            "approx_kl": np.mean(approx_kls),
            "clip_fraction": np.mean(clip_fracs),
        }