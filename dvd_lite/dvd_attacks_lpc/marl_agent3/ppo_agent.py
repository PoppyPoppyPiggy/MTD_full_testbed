# ppo_agent.py
import torch
import torch.nn as nn
from torch.distributions import Categorical
import config

class ActorCritic(nn.Module):
    def __init__(self, state_dim, action_dim, hidden_dim):
        super(ActorCritic, self).__init__()
        self.actor = nn.Sequential(
            nn.Linear(state_dim, hidden_dim), nn.Tanh(),
            nn.Linear(hidden_dim, hidden_dim), nn.Tanh(),
            nn.Linear(hidden_dim, action_dim),
            nn.Softmax(dim=-1)
        )
        self.critic = nn.Sequential(
            nn.Linear(state_dim, hidden_dim), nn.Tanh(),
            nn.Linear(hidden_dim, hidden_dim), nn.Tanh(),
            nn.Linear(hidden_dim, 1)
        )

    def act(self, state):
        probs = self.actor(state)
        dist = Categorical(probs)
        action = dist.sample()
        log_prob = dist.log_prob(action)
        return action, log_prob

    def evaluate(self, state, action):
        probs = self.actor(state)
        dist = Categorical(probs)
        log_prob = dist.log_prob(action)
        entropy = dist.entropy()
        value = self.critic(state)
        return log_prob, value.squeeze(-1), entropy

class Buffer:
    def __init__(self, capacity, state_dim, device):
        self.capacity = capacity
        self.device = device
        self.ptr = 0
        self.states = torch.zeros((capacity, state_dim), dtype=torch.float32, device=device)
        self.actions = torch.zeros((capacity,), dtype=torch.int64, device=device)
        self.log_probs = torch.zeros((capacity,), dtype=torch.float32, device=device)
        self.rewards = torch.zeros((capacity,), dtype=torch.float32, device=device)
        self.values = torch.zeros((capacity,), dtype=torch.float32, device=device)
        self.dones = torch.zeros((capacity,), dtype=torch.float32, device=device)

    def add_batch(self, states, actions, log_probs, rewards, values, dones):
        n = states.shape[0]
        if self.ptr + n > self.capacity:
            print("Buffer overflow on batch add!")
            return
        self.states[self.ptr:self.ptr+n] = states
        self.actions[self.ptr:self.ptr+n] = actions
        self.log_probs[self.ptr:self.ptr+n] = log_probs
        self.rewards[self.ptr:self.ptr+n] = rewards
        self.values[self.ptr:self.ptr+n] = values
        self.dones[self.ptr:self.ptr+n] = dones
        self.ptr += n

class PPO:
    def __init__(self, state_dim, action_dim, device):
        self.device = device
        
        policy_model = ActorCritic(state_dim, action_dim, config.HIDDEN).to(device)
        old_policy_model = ActorCritic(state_dim, action_dim, config.HIDDEN).to(device)
        
        if config.USE_COMPILE:
            self.policy = torch.compile(policy_model)
            self.old = torch.compile(old_policy_model)
        else:
            self.policy = policy_model
            self.old = old_policy_model

        self.old.load_state_dict(self.policy.state_dict())
        self.optimizer = torch.optim.Adam(self.policy.parameters(), lr=config.LR, eps=1e-5)
        self.scaler = torch.cuda.amp.GradScaler(enabled=config.USE_AMP)

    def act(self, state):
        with torch.no_grad():
            with torch.cuda.amp.autocast(enabled=config.USE_AMP):
                return self.old.act(state)

    def update(self, buffer):
        rewards = buffer.rewards
        values = buffer.values
        dones = buffer.dones
        
        advantages = torch.zeros_like(rewards).to(self.device)
        last_gae = 0
        for t in reversed(range(buffer.ptr)):
            if t == buffer.ptr - 1:
                next_non_terminal = 1.0 - dones[t]
                next_values = 0
            else:
                next_non_terminal = 1.0 - dones[t]
                next_values = values[t + 1]
            
            delta = rewards[t] + config.GAMMA * next_values * next_non_terminal - values[t]
            advantages[t] = last_gae = delta + config.GAMMA * config.LAMBDA * next_non_terminal * last_gae
        
        returns = advantages + values

        b_states = buffer.states[:buffer.ptr].view(-1, buffer.states.shape[-1])
        b_actions = buffer.actions[:buffer.ptr].view(-1)
        b_log_probs = buffer.log_probs[:buffer.ptr].view(-1)
        b_advantages = advantages.view(-1)
        b_returns = returns.view(-1)

        b_advantages = (b_advantages - b_advantages.mean()) / (b_advantages.std() + 1e-8)

        for _ in range(config.EPOCHS):
            idxs = torch.randperm(b_states.shape[0])
            for start in range(0, b_states.shape[0], config.MB_SIZE):
                end = start + config.MB_SIZE
                mb_idxs = idxs[start:end]

                mb_states = b_states[mb_idxs]
                mb_actions = b_actions[mb_idxs]
                mb_log_probs = b_log_probs[mb_idxs]
                mb_advantages = b_advantages[mb_idxs]
                mb_returns = b_returns[mb_idxs]

                with torch.cuda.amp.autocast(enabled=config.USE_AMP):
                    log_probs, values, entropies = self.policy.evaluate(mb_states, mb_actions)
                    ratios = torch.exp(log_probs - mb_log_probs)
                    surr1 = ratios * mb_advantages
                    surr2 = torch.clamp(ratios, 1 - config.EPS_CLIP, 1 + config.EPS_CLIP) * mb_advantages
                    policy_loss = -torch.min(surr1, surr2).mean()
                    value_loss = nn.MSELoss()(values, mb_returns)
                    loss = policy_loss - config.ENT_COEF * entropies.mean() + config.VAL_COEF * value_loss

                self.optimizer.zero_grad()
                self.scaler.scale(loss).backward()
                self.scaler.unscale_(self.optimizer)
                nn.utils.clip_grad_norm_(self.policy.parameters(), config.MAX_GRAD_NORM)
                self.scaler.step(self.optimizer)
                self.scaler.update()
        
        self.old.load_state_dict(self.policy.state_dict())