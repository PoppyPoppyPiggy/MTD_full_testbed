# networks.py
import torch, torch.nn as nn
from torch.distributions import Categorical
import config

def mlp(in_f, out_f):
    h = config.HIDDEN
    return nn.Sequential(
        nn.Linear(in_f, h), nn.Tanh(),
        nn.Linear(h, h),    nn.Tanh(),
    )

class ActorCritic(nn.Module):
    def __init__(self, state_dim, action_dim):
        super().__init__()
        self.body = mlp(state_dim, config.HIDDEN)
        self.pi   = nn.Linear(config.HIDDEN, action_dim)
        self.v    = nn.Linear(config.HIDDEN, 1)

    def forward_body(self, x):
        return self.body(x)

    @torch.no_grad()
    def act(self, s):
        # AMP 활성화 시 평가에도 적용 (logprob는 fp32여도 충분)
        with torch.amp.autocast(device_type="cuda", dtype=torch.float16, enabled=config.USE_AMP and s.is_cuda):
            z = self.forward_body(s)
            probs = torch.softmax(self.pi(z), dim=-1)
        dist = Categorical(probs)
        a = dist.sample()
        logp = dist.log_prob(a)
        return a, logp

    def evaluate(self, s, a):
        with torch.amp.autocast(device_type="cuda", dtype=torch.float16, enabled=config.USE_AMP and s.is_cuda):
            z = self.forward_body(s)
            logits = self.pi(z)
            v = self.v(z).squeeze(-1)
            probs = torch.softmax(logits, dim=-1)
        dist = Categorical(probs)
        logp = dist.log_prob(a)
        ent  = dist.entropy()
        return logp, v, ent
