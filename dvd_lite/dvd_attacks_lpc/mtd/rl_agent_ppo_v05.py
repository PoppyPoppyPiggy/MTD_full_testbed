#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[수정됨] MTD_RL v05 - 정석 PPO 에이전트 (Continuous)

- rl_train_v06.py와의 호환성을 위해 API 및 Import 경로 수정.
- RolloutBuffer를 에이전트 내부로 통합 관리.
- rl_config_v06 참조.
"""

import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
import os
from typing import List, Dict, Any, Tuple

# v06 환경 및 모델 호환성을 위한 Import 수정
from .rl_model_v05 import MTDPolicyNet, MTDValueNet
from .rl_config_v06 import ACTION_DIM  # v06 config 사용

class RolloutBuffer:
    def __init__(self, batch_size: int, obs_dim: int, act_dim: int, gamma: float, gae_lambda: float, device):
        self.batch_size = batch_size
        self.obs_dim = obs_dim
        self.act_dim = act_dim
        self.gamma = gamma
        self.gae_lambda = gae_lambda
        self.device = device
        self.reset()

    def reset(self):
        self.obs = np.zeros((self.batch_size, self.obs_dim), dtype=np.float32)
        self.actions = np.zeros((self.batch_size, self.act_dim), dtype=np.float32) 
        self.logprobs = np.zeros(self.batch_size, dtype=np.float32)
        self.rewards = np.zeros(self.batch_size, dtype=np.float32)
        self.dones = np.zeros(self.batch_size, dtype=np.float32)
        self.values = np.zeros(self.batch_size, dtype=np.float32)
        self.advantages = np.zeros(self.batch_size, dtype=np.float32)
        self.returns = np.zeros(self.batch_size, dtype=np.float32)
        self.ptr, self.path_start_idx = 0, 0

    def add(self, obs, action, logprob, reward, value, done):
        if self.ptr >= self.batch_size:
            # 버퍼가 가득 차면 더 이상 추가하지 않음 (학습 루프 제어에 따름)
            return
        self.obs[self.ptr] = obs
        self.actions[self.ptr] = action
        self.rewards[self.ptr] = reward
        self.dones[self.ptr] = float(done)
        self.logprobs[self.ptr] = logprob
        self.values[self.ptr] = value
        self.ptr += 1

    def finish_path(self, last_value: float = 0.0):
        """
        에피소드가 끝났거나 버퍼가 찼을 때 GAE 계산.
        done=True인 경우 last_value는 0이어야 함.
        """
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

    def get_batch(self, minibatch_size: int):
        # 전체 배치에 대해 정규화
        adv_mean = np.mean(self.advantages[:self.ptr])
        adv_std = np.std(self.advantages[:self.ptr]) + 1e-8
        self.advantages[:self.ptr] = (self.advantages[:self.ptr] - adv_mean) / adv_std
        
        indices = np.arange(self.ptr)
        np.random.shuffle(indices)
        
        for start in range(0, self.ptr, minibatch_size):
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
    def __init__(
        self, 
        state_dim: int, 
        action_dim: int, 
        hidden_size: int = 128,
        lr: float = 3e-4, 
        gamma: float = 0.99, 
        gae_lambda: float = 0.95, 
        clip_coef: float = 0.2, 
        max_grad_norm: float = 0.5, 
        ent_coef: float = 0.01, 
        vf_coef: float = 0.5, 
        ppo_epochs: int = 10, 
        minibatch_size: int = 64, 
        target_kl: float = 0.015, 
        device: Any = "cpu",
        buffer_size: int = 2048  # 기본 버퍼 크기
    ):
        # 설정 저장
        self.obs_dim = state_dim
        self.act_dim = action_dim
        self.lr = lr
        self.gamma = gamma
        self.gae_lambda = gae_lambda
        self.clip_coef = clip_coef
        self.max_grad_norm = max_grad_norm
        self.ent_coef = ent_coef
        self.vf_coef = vf_coef
        self.ppo_epochs = ppo_epochs
        self.minibatch_size = minibatch_size
        self.target_kl = target_kl
        self.device = device

        # 네트워크 초기화
        self.policy = MTDPolicyNet(state_dim, action_dim, hidden_size).to(self.device)
        self.value_net = MTDValueNet(state_dim, hidden_size).to(self.device)
        
        self.optimizer_policy = optim.Adam(self.policy.parameters(), lr=lr, eps=1e-5)
        self.optimizer_value = optim.Adam(self.value_net.parameters(), lr=lr, eps=1e-5)
        self.mse_loss = nn.MSELoss()

        # 내부 버퍼 생성
        self.buffer = RolloutBuffer(buffer_size, state_dim, action_dim, gamma, gae_lambda, self.device)

    def get_action_and_value(self, obs_tensor: torch.Tensor, action: torch.Tensor = None) -> Tuple:
        mean, std = self.policy(obs_tensor)
        dist = torch.distributions.Normal(mean, std)
        
        if action is None:
            action = dist.sample()
        
        # Action clipping은 환경(Environment) 적용 시 수행, 여기서는 raw action 반환
        log_prob = dist.log_prob(action).sum(dim=-1)
        entropy = dist.entropy().sum(dim=-1)
        value = self.value_net(obs_tensor).squeeze(-1)
        
        return action, log_prob, value, entropy

    def store_transition(self, obs, action, logprob, reward, value, done):
        """rl_train_v06.py 호환용 데이터 저장 메서드"""
        self.buffer.add(obs, action, logprob, reward, value, done)
        
        # 에피소드가 끝났으면 GAE 경로 계산 마무리
        if done:
            self.buffer.finish_path(last_value=0.0)

    def ready_for_update(self) -> bool:
        """버퍼가 꽉 찼는지 확인"""
        return self.buffer.ptr >= self.buffer.batch_size

    def clear_buffer(self):
        self.buffer.reset()

    def update_policy(self) -> Tuple[float, float, float, float, float]:
        """PPO 업데이트 수행"""
        clip_fracs = []
        approx_kls = []
        policy_losses = []
        value_losses = []
        entropy_losses = []

        # 만약 버퍼가 꽉 차지 않았는데 업데이트가 호출되면 남은 부분을 finish
        if self.buffer.path_start_idx != self.buffer.ptr:
            self.buffer.finish_path(last_value=0.0)

        for epoch in range(self.ppo_epochs):
            for batch in self.buffer.get_batch(self.minibatch_size):
                obs, actions, old_logprobs, advantages, returns, old_values = batch
                
                _, new_logprobs, _, entropy = self.get_action_and_value(obs, actions)
                
                log_ratio = new_logprobs - old_logprobs
                ratio = torch.exp(log_ratio)
                
                with torch.no_grad():
                    # KL Divergence 근사치 계산
                    approx_kl = ((ratio - 1) - log_ratio).mean().item()
                    clip_frac = torch.mean((torch.abs(ratio - 1.0) > self.clip_coef).float()).item()
                    approx_kls.append(approx_kl)
                    clip_fracs.append(clip_frac)

                # Target KL 초과 시 조기 중단 (선택적)
                if self.target_kl is not None and approx_kl > self.target_kl * 1.5:
                    break

                # Policy Loss
                surr1 = ratio * advantages
                surr2 = torch.clamp(ratio, 1.0 - self.clip_coef, 1.0 + self.clip_coef) * advantages
                policy_loss = -torch.min(surr1, surr2).mean()
                
                # Entropy Loss
                entropy_loss = -self.ent_coef * entropy.mean()
                
                # Value Loss
                new_values = self.value_net(obs).squeeze(-1)
                v_loss_unclipped = (new_values - returns) ** 2
                v_clipped = old_values + torch.clamp(new_values - old_values, -self.clip_coef, self.clip_coef)
                v_loss_clipped = (v_clipped - returns) ** 2
                v_loss_max = torch.max(v_loss_unclipped, v_loss_clipped)
                value_loss = 0.5 * v_loss_max.mean() * self.vf_coef

                # Backpropagation
                loss = policy_loss + entropy_loss + value_loss
                
                self.optimizer_policy.zero_grad()
                self.optimizer_value.zero_grad()
                loss.backward()
                
                nn.utils.clip_grad_norm_(self.policy.parameters(), self.max_grad_norm)
                nn.utils.clip_grad_norm_(self.value_net.parameters(), self.max_grad_norm)
                
                self.optimizer_policy.step()
                self.optimizer_value.step()
                
                policy_losses.append(policy_loss.item())
                value_losses.append(value_loss.item())
                entropy_losses.append(entropy_loss.item())

        # 설명된 분산(Explained Variance) 계산
        y_pred, y_true = self.buffer.values[:self.buffer.ptr], self.buffer.returns[:self.buffer.ptr]
        var_y = np.var(y_true)
        explained_var = np.nan if var_y == 0 else 1 - np.var(y_true - y_pred) / var_y

        return (
            np.mean(policy_losses),
            np.mean(value_losses),
            np.mean(entropy_losses),
            np.mean(approx_kls),
            explained_var
        )

    def save_policy(self, path: str):
        torch.save({
            'policy_state_dict': self.policy.state_dict(),
            'value_state_dict': self.value_net.state_dict(),
            'optimizer_policy_state_dict': self.optimizer_policy.state_dict(),
            'optimizer_value_state_dict': self.optimizer_value.state_dict(),
        }, path)

    def load_policy(self, path: str):
        if not os.path.exists(path):
            return
        checkpoint = torch.load(path, map_location=self.device)
        self.policy.load_state_dict(checkpoint['policy_state_dict'])
        self.value_net.load_state_dict(checkpoint['value_state_dict'])
        self.optimizer_policy.load_state_dict(checkpoint['optimizer_policy_state_dict'])
        self.optimizer_value.load_state_dict(checkpoint['optimizer_value_state_dict'])