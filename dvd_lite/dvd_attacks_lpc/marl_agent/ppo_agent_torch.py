# ppo_agent_torch.py
import torch
import torch.nn as nn
from torch.distributions import Categorical
import config

class Buffer:
    def __init__(self, capacity, state_dim, device):
        self.capacity = capacity
        self.dev = device
        self.states = torch.zeros((capacity, state_dim), device=device)
        self.actions = torch.zeros(capacity, device=device, dtype=torch.int64)
        self.logprobs = torch.zeros(capacity, device=device)
        self.rewards = torch.zeros(capacity, device=device)
        self.values = torch.zeros(capacity, device=device)
        self.dones = torch.zeros(capacity, device=device, dtype=torch.bool)
        self.ptr = 0

    def add_batch(self, s, a, lp, r, v, d):
        n = s.shape[0]
        if self.ptr + n > self.capacity: self.ptr = 0
        
        self.states[self.ptr:self.ptr+n] = s
        self.actions[self.ptr:self.ptr+n] = a
        self.logprobs[self.ptr:self.ptr+n] = lp
        self.rewards[self.ptr:self.ptr+n] = r
        self.values[self.ptr:self.ptr+n] = v
        self.dones[self.ptr:self.ptr+n] = d
        self.ptr += n

class ActorCritic(nn.Module):
    def __init__(self, state_dim, action_dim):
        super().__init__()
        self.actor = nn.Sequential(
            nn.Linear(state_dim, config.HIDDEN_SIZE), nn.Tanh(),
            nn.Linear(config.HIDDEN_SIZE, config.HIDDEN_SIZE), nn.Tanh(),
            nn.Linear(config.HIDDEN_SIZE, action_dim)
        )
        self.critic = nn.Sequential(
            nn.Linear(state_dim, config.HIDDEN_SIZE), nn.Tanh(),
            nn.Linear(config.HIDDEN_SIZE, config.HIDDEN_SIZE), nn.Tanh(),
            nn.Linear(config.HIDDEN_SIZE, 1)
        )

    def forward(self, state):
        raise NotImplementedError

    def get_dist(self, state):
        return Categorical(logits=self.actor(state))

    def evaluate(self, state, action):
        dist = self.get_dist(state)
        logprobs = dist.log_prob(action)
        entropy = dist.entropy()
        value = self.critic(state).squeeze(-1)
        return logprobs, value, entropy

class PPO:
    def __init__(self, state_dim, action_dim, device):
        self.dev = device
        self.old = ActorCritic(state_dim, action_dim).to(device)
        self.policy = ActorCritic(state_dim, action_dim).to(device)
        self.policy.load_state_dict(self.old.state_dict())
        
        if config.TORCH_COMPILE:
            self.policy = torch.compile(self.policy, mode="reduce-overhead")

        self.optimizer = torch.optim.Adam(self.policy.parameters(), lr=config.LEARNING_RATE, eps=1e-5)
        # <-- 경고 수정: torch.cuda.amp.GradScaler -> torch.amp.GradScaler
        self.scaler = torch.amp.GradScaler('cuda', enabled=config.USE_AMP)

    def act(self, state):
        dist = self.old.get_dist(state)
        action = dist.sample()
        logprob = dist.log_prob(action)
        return action, logprob

    def update(self, buffer):
        with torch.no_grad():
            advantages = torch.zeros_like(buffer.rewards)
            last_adv = 0
            # 버퍼에 실제로 채워진 만큼만 GAE 계산
            valid_range = range(buffer.ptr)
            for t in reversed(valid_range):
                mask = 1.0 - buffer.dones[t].float()
                # 마지막 스텝의 next_val은 0으로 처리
                next_val = buffer.values[t+1] if t + 1 in valid_range else 0.0
                delta = buffer.rewards[t] + config.GAMMA * next_val * mask - buffer.values[t]
                last_adv = delta + config.GAMMA * config.GAE_LAMBDA * mask * last_adv
                advantages[t] = last_adv
            returns = advantages + buffer.values

        # 실제로 사용된 데이터만 슬라이싱
        s, a, lp = buffer.states[:buffer.ptr], buffer.actions[:buffer.ptr], buffer.logprobs[:buffer.ptr]
        advantages = advantages[:buffer.ptr]
        returns = returns[:buffer.ptr]

        advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)
        
        indices = torch.randperm(buffer.ptr)
        s, a, lp, advantages, returns = s[indices], a[indices], lp[indices], advantages[indices], returns[indices]

        for _ in range(config.PPO_EPOCHS):
            for i in range(0, buffer.ptr, config.MINIBATCH_SIZE):
                idx = slice(i, i+config.MINIBATCH_SIZE)
                with torch.amp.autocast('cuda', enabled=config.USE_AMP):
                    new_lp, new_v, entropy = self.policy.evaluate(s[idx], a[idx])
                    
                    ratio = (new_lp - lp[idx]).exp()
                    surr1 = ratio * advantages[idx]
                    surr2 = torch.clamp(ratio, 1-config.EPSILON_CLIP, 1+config.EPSILON_CLIP) * advantages[idx]
                    
                    policy_loss = -torch.min(surr1, surr2).mean()
                    value_loss = (new_v - returns[idx]).pow(2).mean()
                    entropy_loss = -entropy.mean()
                    
                    loss = policy_loss + config.VALUE_COEFF * value_loss + config.ENTROPY_COEFF * entropy_loss
                
                self.optimizer.zero_grad(set_to_none=True)
                self.scaler.scale(loss).backward()
                nn.utils.clip_grad_norm_(self.policy.parameters(), config.MAX_GRAD_NORM)
                self.scaler.step(self.optimizer)
                self.scaler.update()

        self.old.load_state_dict(self.policy.state_dict())