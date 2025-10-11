# networks.py
import torch
import torch.nn as nn
from torch.distributions import Categorical
import config

class ActorCritic(nn.Module):
    def __init__(self, state_dim, action_dim):
        super(ActorCritic, self).__init__()
        self.actor = nn.Sequential(
            nn.Linear(state_dim, config.HIDDEN_SIZE),
            nn.Tanh(),
            nn.Linear(config.HIDDEN_SIZE, config.HIDDEN_SIZE),
            nn.Tanh(),
            nn.Linear(config.HIDDEN_SIZE, action_dim),
        )
        self.critic = nn.Sequential(
            nn.Linear(state_dim, config.HIDDEN_SIZE),
            nn.Tanh(),
            nn.Linear(config.HIDDEN_SIZE, config.HIDDEN_SIZE),
            nn.Tanh(),
            nn.Linear(config.HIDDEN_SIZE, 1)
        )

    def get_dist(self, state):
        logits = self.actor(state)
        return Categorical(logits=logits)

    def evaluate(self, state, action):
        dist = self.get_dist(state)
        logprobs = dist.log_prob(action)
        entropy = dist.entropy()
        value = self.critic(state).squeeze(-1)
        return logprobs, value, entropy