# File: MTD_full_testbed/dvd_lite/dvd_attacks_lpc/mtd/rl_model_v05.py
#
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[신규 3/11] RL 정책 네트워크 모델 정의 (v05)

- v04 모델(MTDPolicyNet, MTDValueNet)과 구조적으로 100% 동일합니다.
- (Obs_dim=16, Act_dim=6)
"""

import torch
import torch.nn as nn
import numpy as np
from torch.distributions.normal import Normal

class MTDPolicyNet(nn.Module):
    """ (Actor Network - Continuous) """
    def __init__(self, obs_dim: int, act_dim: int):
        super().__init__()
        self.body = nn.Sequential(
            nn.Linear(obs_dim, 128), nn.Tanh(),
            nn.Linear(128, 128), nn.Tanh(),
        )
        self.actor_mean = nn.Sequential(
            nn.Linear(128, act_dim), nn.Tanh() 
        )
        self.actor_log_std = nn.Parameter(torch.zeros(1, act_dim))

    def forward(self, x: torch.Tensor) -> Normal:
        """ PPO 학습 시 (Normal Distribution) 반환 """
        body_out = self.body(x)
        mean = self.actor_mean(body_out)
        log_std = self.actor_log_std.expand_as(mean)
        std = torch.exp(log_std)
        return Normal(mean, std)

    def act_greedy(self, obs_vec: np.ndarray) -> np.ndarray:
        """ 배포 환경에서 사용할 결정론적 행동(평균) 반환 """
        self.eval() 
        with torch.no_grad():
            x = torch.from_numpy(obs_vec).float().unsqueeze(0)
            body_out = self.body(x)
            mean = self.actor_mean(body_out)
            return mean.squeeze(0).cpu().numpy() # (6,) 벡터, -1.0 ~ 1.0

class MTDValueNet(nn.Module):
    """ (Critic Network) """
    def __init__(self, obs_dim: int):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(obs_dim, 128), nn.Tanh(),
            nn.Linear(128, 128), nn.Tanh(),
            nn.Linear(128, 1),
        )
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)