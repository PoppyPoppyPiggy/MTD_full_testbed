# ppo_agent.py
import torch
import torch.nn as nn
from torch.optim import Adam
from torch.amp import autocast, GradScaler
import config
from networks import ActorCritic

class PPOAgent:
    def __init__(self, state_dim, action_dim):
        self.policy = ActorCritic(state_dim, action_dim).to(config.DEVICE)
        self.value_loss_fn = nn.MSELoss()
        self.optimizer = Adam(self.policy.parameters(), lr=config.LEARNING_RATE, eps=1e-5)

        if config.TORCH_COMPILE and hasattr(torch, "compile"):
            self.policy = torch.compile(self.policy, mode="reduce-overhead")

    @torch.no_grad()
    def select_action(self, state_batch: torch.Tensor):
        dist = self.policy.get_dist(state_batch)
        action = dist.sample()
        logprob = dist.log_prob(action)
        value = self.policy.critic(state_batch).squeeze(-1)
        return action, logprob, value

    def update(self, rollouts):
        states = rollouts['states']
        actions = rollouts['actions']
        old_logprobs = rollouts['logprobs']
        returns = rollouts['returns']
        advantages = rollouts['advantages']

        advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)
        indices = torch.arange(states.size(0), device=states.device)
        scaler = GradScaler('cuda', enabled=config.USE_AMP)

        for _ in range(config.PPO_EPOCHS):
            perm = indices[torch.randperm(states.size(0))]
            for start in range(0, states.size(0), config.MINIBATCH_SIZE):
                idx = perm[start:start + config.MINIBATCH_SIZE]
                with autocast('cuda', dtype=torch.float16, enabled=config.USE_AMP):
                    new_logprobs, values, entropy = self.policy.evaluate(states[idx], actions[idx])
                    ratio = torch.exp(new_logprobs - old_logprobs[idx])
                    surr1 = ratio * advantages[idx]
                    surr2 = torch.clamp(ratio, 1.0 - config.EPSILON_CLIP, 1.0 + config.EPSILON_CLIP) * advantages[idx]
                    policy_loss = -torch.min(surr1, surr2).mean()
                    value_loss = config.VALUE_COEFF * self.value_loss_fn(values, returns[idx])
                    entropy_loss = -config.ENTROPY_COEFF * entropy.mean()
                    loss = policy_loss + value_loss + entropy_loss

                self.optimizer.zero_grad(set_to_none=True)
                scaler.scale(loss).backward()
                nn.utils.clip_grad_norm_(self.policy.parameters(), config.MAX_GRAD_NORM)
                scaler.step(self.optimizer)
                scaler.update()