# 파일: dvd_lite/dvd_attacks_lpc/mtd/rl_model_v05.py
import os
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.distributions import Normal

LOG_STD_MAX = 2.0
LOG_STD_MIN = -20.0


class ActorCritic(nn.Module):
    """
    PPO용 Actor-Critic 네트워크.
    - 입력: state_dim
    - 출력: action_mean (연속), state_value
    - log_std는 action_dim마다 학습 파라미터
    """
    def __init__(self, state_dim, action_dim, hidden_size=128):
        super().__init__()

        self.feature_extractor = nn.Sequential(
            self._layer_init(nn.Linear(state_dim, hidden_size)),
            nn.Tanh(),
            self._layer_init(nn.Linear(hidden_size, hidden_size)),
            nn.Tanh(),
        )

        self.actor_mean = self._layer_init(nn.Linear(hidden_size, action_dim), std=0.01)
        self.critic = self._layer_init(nn.Linear(hidden_size, 1))

        self.log_std = nn.Parameter(torch.zeros(action_dim))
        self.log_std.data.fill_(0.0)

    def _layer_init(self, layer, std=np.sqrt(2), bias_const=0.0):
        nn.init.orthogonal_(layer.weight, std)
        nn.init.constant_(layer.bias, bias_const)
        return layer

    def get_value(self, x):
        return self.critic(self.feature_extractor(x))

    def get_action_and_value(self, x, action=None):
        features = self.feature_extractor(x)
        mean = self.actor_mean(features)

        log_std = torch.clamp(self.log_std, LOG_STD_MIN, LOG_STD_MAX)
        std = torch.exp(log_std)

        dist = Normal(mean, std)

        if action is None:
            action = dist.sample()
            log_prob = dist.log_prob(action).sum(dim=1)
        else:
            log_prob = dist.log_prob(action).sum(dim=1)

        entropy = dist.entropy().sum(dim=1)
        value = self.critic(features).flatten()

        return action, log_prob, entropy, value

    def get_log_prob(self, x, action):
        features = self.feature_extractor(x)
        mean = self.actor_mean(features)

        log_std = torch.clamp(self.log_std, LOG_STD_MIN, LOG_STD_MAX)
        std = torch.exp(log_std)

        dist = Normal(mean, std)
        log_prob = dist.log_prob(action).sum(dim=1)
        entropy = dist.entropy().sum(dim=1)
        value = self.critic(features).flatten()
        return log_prob, entropy, value


class PPOAgent:
    """
    PPO Agent: Rollout 버퍼 + PPO 업데이트 로직
    """
    def __init__(
        self,
        state_dim,
        action_dim,
        hidden_size,
        lr,
        gamma,
        gae_lambda,
        clip_coef,
        max_grad_norm,
        ent_coef,
        vf_coef,
        ppo_epochs,
        minibatch_size,
        target_kl,
        device,
    ):
        self.device = device
        self.gamma = gamma
        self.gae_lambda = gae_lambda
        self.clip_coef = clip_coef
        self.max_grad_norm = max_grad_norm
        self.ent_coef = ent_coef
        self.vf_coef = vf_coef
        self.ppo_epochs = ppo_epochs
        self.minibatch_size = minibatch_size
        self.target_kl = target_kl

        self.network = ActorCritic(state_dim, action_dim, hidden_size).to(device)
        self.optimizer = optim.Adam(self.network.parameters(), lr=lr, eps=1e-5)

        self.states = []
        self.actions = []
        self.log_probs = []
        self.rewards = []
        self.values = []
        self.dones = []

        self.max_buffer_size = 1000

    def get_action_and_value(self, state):
        with torch.no_grad():
            action, log_prob, _, value = self.network.get_action_and_value(state)
            return action, log_prob, value

    def store_transition(self, state, action, log_prob, reward, value, done):
        self.states.append(state)
        self.actions.append(action)
        self.log_probs.append(log_prob)
        self.rewards.append(reward)
        self.values.append(value)
        self.dones.append(done)

    def ready_for_update(self):
        return len(self.rewards) >= self.max_buffer_size or (self.dones and self.dones[-1])

    def clear_buffer(self):
        self.states.clear()
        self.actions.clear()
        self.log_probs.clear()
        self.rewards.clear()
        self.values.clear()
        self.dones.clear()

    def _prepare_data(self):
        states = torch.as_tensor(np.array(self.states), dtype=torch.float32, device=self.device)
        actions = torch.as_tensor(np.array(self.actions), dtype=torch.float32, device=self.device)
        log_probs = torch.as_tensor(self.log_probs, dtype=torch.float32, device=self.device)
        rewards = torch.as_tensor(self.rewards, dtype=torch.float32, device=self.device)
        values = torch.as_tensor(self.values, dtype=torch.float32, device=self.device)
        dones = torch.as_tensor(self.dones, dtype=torch.float32, device=self.device)

        with torch.no_grad():
            next_state = torch.as_tensor(self.states[-1], dtype=torch.float32, device=self.device).unsqueeze(0)
            last_value = self.network.get_value(next_state).item()

            advantages = torch.zeros_like(rewards, device=self.device)
            last_gae_lambda = 0.0

            for t in reversed(range(len(rewards))):
                if t == len(rewards) - 1:
                    next_non_terminal = 1.0 - dones[t]
                    next_value = last_value
                else:
                    next_non_terminal = 1.0 - dones[t]
                    next_value = values[t + 1]

                delta = rewards[t] + self.gamma * next_value * next_non_terminal - values[t]
                last_gae_lambda = delta + self.gamma * self.gae_lambda * next_non_terminal * last_gae_lambda
                advantages[t] = last_gae_lambda

            returns = advantages + values

        advantages = advantages.flatten()
        advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)

        b_inds = np.arange(len(self.rewards))

        return (
            states,
            actions,
            log_probs.flatten(),
            returns.flatten(),
            values.flatten(),
            advantages,
            b_inds,
        )

    def update_policy(self):
        states, actions, old_log_probs, returns, old_values, advantages, b_inds = self._prepare_data()

        clip_fracs = []
        last_policy_loss = 0.0
        last_value_loss = 0.0
        last_entropy_loss = 0.0

        for epoch in range(self.ppo_epochs):
            np.random.shuffle(b_inds)

            for start in range(0, len(self.rewards), self.minibatch_size):
                end = start + self.minibatch_size
                mb_inds = b_inds[start:end]

                mb_states = states[mb_inds]
                mb_actions = actions[mb_inds]
                mb_old_log_probs = old_log_probs[mb_inds]
                mb_returns = returns[mb_inds]
                mb_old_values = old_values[mb_inds]
                mb_advantages = advantages[mb_inds]

                new_log_probs, entropy, new_values = self.network.get_log_prob(mb_states, mb_actions)

                ratio = torch.exp(new_log_probs - mb_old_log_probs)
                pg_loss1 = -mb_advantages * ratio
                pg_loss2 = -mb_advantages * torch.clamp(ratio, 1 - self.clip_coef, 1 + self.clip_coef)
                policy_loss = torch.max(pg_loss1, pg_loss2).mean()

                with torch.no_grad():
                    clip_fracs.append(((ratio - 1.0).abs() > self.clip_coef).float().mean().item())

                v_loss_unclipped = (new_values - mb_returns) ** 2
                v_clipped = mb_old_values + torch.clamp(new_values - mb_old_values, -self.clip_coef, self.clip_coef)
                v_loss_clipped = (v_clipped - mb_returns) ** 2
                value_loss = 0.5 * torch.max(v_loss_unclipped, v_loss_clipped).mean()

                entropy_loss = entropy.mean()

                total_loss = policy_loss - self.ent_coef * entropy_loss + self.vf_coef * value_loss

                self.optimizer.zero_grad()
                total_loss.backward()
                nn.utils.clip_grad_norm_(self.network.parameters(), self.max_grad_norm)
                self.optimizer.step()

                last_policy_loss = policy_loss
                last_value_loss = value_loss
                last_entropy_loss = entropy_loss

        with torch.no_grad():
            new_log_probs_all, _, new_values_all = self.network.get_log_prob(states, actions)
            ratio_all = torch.exp(new_log_probs_all - old_log_probs)
            approx_kl = (ratio_all - 1.0 - ratio_all.log()).mean().item()

            y_pred = new_values_all.cpu().numpy()
            y_true = returns.cpu().numpy()
            var_y = np.var(y_true)
            explained_variance = 1.0 - np.var(y_true - y_pred) / (var_y + 1e-8) if var_y != 0 else 0.0

        return (
            float(last_policy_loss.item()),
            float(last_value_loss.item()),
            float(last_entropy_loss.item()),
            float(approx_kl),
            float(explained_variance),
        )

    def save_policy(self, path):
        torch.save(self.network.state_dict(), path)

    def load_policy(self, path):
        self.network.load_state_dict(torch.load(path, map_location=self.device))
