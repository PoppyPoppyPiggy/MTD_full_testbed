#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rl_model_v05.py

MTD PPO용 정책/가치 네트워크 정의.
"""

from typing import Tuple

import torch
import torch.nn as nn
from torch.distributions import Normal

from rl_config_v05 import OBS_DIM, ACTION_DIM


class MTDPolicyNet(nn.Module):
    """
    연속 행동 정책 네트워크.
    입력: obs_dim (16)
    출력: mean ([-1,1] 범위 6차원), log_std (학습 가능한 파라미터)
    """

    def __init__(self, obs_dim: int = OBS_DIM, action_dim: int = ACTION_DIM):
        super().__init__()
        self.obs_dim = obs_dim
        self.action_dim = action_dim

        self.net = nn.Sequential(
            nn.Linear(obs_dim, 128),
            nn.Tanh(),
            nn.Linear(128, 128),
            nn.Tanh(),
        )
        self.mean_head = nn.Linear(128, action_dim)
        # log_std 는 상태에 상관없이 하나의 학습 가능한 파라미터로 유지
        self.log_std = nn.Parameter(torch.zeros(action_dim))

        self._init_weights()

    def _init_weights(self) -> None:
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.orthogonal_(m.weight, gain=1.0)
                nn.init.constant_(m.bias, 0.0)

    def forward(self, obs: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        x = self.net(obs)
        mean = torch.tanh(self.mean_head(x))  # [-1, 1] 범위
        log_std = self.log_std.expand_as(mean)
        return mean, log_std

    def get_dist(self, obs: torch.Tensor) -> Normal:
        mean, log_std = self.forward(obs)
        std = torch.exp(log_std)
        return Normal(mean, std)

    def act(self, obs: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        dist = self.get_dist(obs)
        action = dist.sample()
        log_prob = dist.log_prob(action).sum(-1)
        return action, log_prob

    def act_greedy(self, obs: torch.Tensor) -> torch.Tensor:
        mean, _ = self.forward(obs)
        return mean


class MTDValueNet(nn.Module):
    """
    상태 가치함수 네트워크.
    """

    def __init__(self, obs_dim: int = OBS_DIM):
        super().__init__()
        self.obs_dim = obs_dim

        self.net = nn.Sequential(
            nn.Linear(obs_dim, 128),
            nn.Tanh(),
            nn.Linear(128, 128),
            nn.Tanh(),
            nn.Linear(128, 1),
        )
        self._init_weights()

    def _init_weights(self) -> None:
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.orthogonal_(m.weight, gain=1.0)
                nn.init.constant_(m.bias, 0.0)

    def forward(self, obs: torch.Tensor) -> torch.Tensor:
        return self.net(obs).squeeze(-1)
