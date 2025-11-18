import torch
import torch.nn as nn
from torch.distributions import Normal
import numpy as np
import os
import torch.optim as optim

# Standard deviation initialization (for PPO continuous actions)
LOG_STD_MAX = 2
LOG_STD_MIN = -20

class ActorCritic(nn.Module):
    """
    Implements a single network structure for both Actor (Policy) and Critic (Value).
    The policy output is the mean of a Gaussian distribution, and log_std is learned separately.
    Uses Orthogonal Initialization as recommended in PPO best practices.
    """
    def __init__(self, state_dim, action_dim, hidden_size=128):
        super(ActorCritic, self).__init__()

        # Shared Feature Layers (16D -> 128 -> 128)
        self.feature_extractor = nn.Sequential(
            self._layer_init(nn.Linear(state_dim, hidden_size)),
            nn.Tanh(),
            self._layer_init(nn.Linear(hidden_size, hidden_size)),
            nn.Tanh()
        )

        # Actor (Policy) Head - Outputs mean action (128 -> 6D)
        self.actor_mean = self._layer_init(nn.Linear(hidden_size, action_dim), std=0.01)
        
        # Critic (Value) Head - Outputs state value (128 -> 1)
        self.critic = self._layer_init(nn.Linear(hidden_size, 1))
        
        # Log Standard Deviation (Learned parameter for the Gaussian policy)
        # One log_std parameter per action dimension
        self.log_std = nn.Parameter(torch.zeros(action_dim))
        self.log_std.data.fill_(0.0) # Initialize log_std to 0 (std=1)

    def _layer_init(self, layer, std=np.sqrt(2), bias_const=0.0):
        """Orthogonal Initialization."""
        torch.nn.init.orthogonal_(layer.weight, std)
        torch.nn.init.constant_(layer.bias, bias_const)
        return layer

    def get_value(self, x):
        """Returns the predicted state value."""
        return self.critic(self.feature_extractor(x))

    def get_action_and_value(self, x, action=None):
        """
        Calculates action(s), log probability, entropy, and state value.
        If action is provided, calculates log_prob and entropy for the given action.
        """
        features = self.feature_extractor(x)
        action_mean = self.actor_mean(features)
        
        # Clamp log_std to prevent numerical instability
        log_std = torch.clamp(self.log_std, LOG_STD_MIN, LOG_STD_MAX)
        action_std = torch.exp(log_std)
        
        # Create Gaussian distribution
        probs = Normal(action_mean, action_std)
        
        if action is None:
            # Sample action and calculate its log_prob
            action = probs.sample()
            # Action clipping is done outside this function (e.g., tanh activation in policy head if it were SAC/TD3)
            # For PPO, we sample from the continuous distribution.
            log_prob = probs.log_prob(action).sum(1)
        else:
            # Calculate log_prob for a given action
            log_prob = probs.log_prob(action).sum(1)

        entropy = probs.entropy().sum(1)
        value = self.critic(features).flatten()
        
        return action, log_prob, entropy, value
        
    def get_log_prob(self, x, action):
        """For PPO update, calculates log_prob and value for given states/actions."""
        features = self.feature_extractor(x)
        action_mean = self.actor_mean(features)
        
        log_std = torch.clamp(self.log_std, LOG_STD_MIN, LOG_STD_MAX)
        action_std = torch.exp(log_std)
        
        probs = Normal(action_mean, action_std)
        
        log_prob = probs.log_prob(action).sum(1)
        entropy = probs.entropy().sum(1)
        value = self.critic(features).flatten()
        
        return log_prob, entropy, value


class PPOAgent:
    """
    PPO Agent implementation managing the ActorCritic network and data buffers.
    """
    def __init__(self, state_dim, action_dim, hidden_size, lr, gamma, gae_lambda, 
                 clip_coef, max_grad_norm, ent_coef, vf_coef, ppo_epochs, 
                 minibatch_size, target_kl, device):
        
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
        
        # Simplified Buffer for Rollouts
        self.states = []
        self.actions = []
        self.log_probs = []
        self.rewards = []
        self.values = []
        self.dones = []
        
        # Buffer size logic should be tuned to the environment's length for best performance
        self.max_buffer_size = 1000 # Max steps before policy update is mandatory

    def get_action_and_value(self, state):
        """Wrapper to get action and value from the network."""
        with torch.no_grad():
            action, log_prob, _, value = self.network.get_action_and_value(state)
            return action, log_prob, value

    def store_transition(self, state, action, log_prob, reward, value, done):
        """Stores experience tuple in the buffer."""
        self.states.append(state)
        self.actions.append(action)
        self.log_probs.append(log_prob)
        self.rewards.append(reward)
        self.values.append(value)
        self.dones.append(done)

    def ready_for_update(self):
        """Check if enough steps have been collected for an update."""
        return len(self.rewards) >= self.max_buffer_size or (self.dones and self.dones[-1])

    def clear_buffer(self):
        """Clears the buffer after an update."""
        self.states = []
        self.actions = []
        self.log_probs = []
        self.rewards = []
        self.values = []
        self.dones = []

    def _prepare_data(self):
        """Converts lists to tensors and computes advantages (GAE)."""
        
        # Convert lists to tensors
        states = torch.as_tensor(np.array(self.states), dtype=torch.float32).to(self.device)
        actions = torch.as_tensor(np.array(self.actions), dtype=torch.float32).to(self.device)
        log_probs = torch.as_tensor(self.log_probs, dtype=torch.float32).to(self.device)
        rewards = torch.as_tensor(self.rewards, dtype=torch.float32).to(self.device)
        values = torch.as_tensor(self.values, dtype=torch.float32).to(self.device)
        dones = torch.as_tensor(self.dones, dtype=torch.float32).to(self.device)
        
        # Generalized Advantage Estimation (GAE)
        with torch.no_grad():
            # Get last value (V(S_{T}) or V(S_{done}) = 0)
            next_state = torch.as_tensor(self.states[-1], dtype=torch.float32).to(self.device)
            last_value = self.network.get_value(next_state).item()
            
            advantages = torch.zeros_like(rewards).to(self.device)
            last_gae_lambda = 0
            
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
            
        # Flatten and normalize advantages
        advantages = advantages.flatten()
        advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)
        
        # Create tensor dataset
        b_inds = np.arange(len(self.rewards))
        
        return states, actions, log_probs.flatten(), returns.flatten(), values.flatten(), advantages, b_inds

    def update_policy(self):
        """Performs PPO policy update over multiple epochs."""
        
        states, actions, old_log_probs, returns, old_values, advantages, b_inds = self._prepare_data()
        
        clip_fracs = []
        
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

                # Re-evaluate network
                new_log_probs, entropy, new_values = self.network.get_log_prob(mb_states, mb_actions)
                
                # Policy Loss calculation (PPO Clip)
                ratio = torch.exp(new_log_probs - mb_old_log_probs)
                pg_loss1 = -mb_advantages * ratio
                pg_loss2 = -mb_advantages * torch.clamp(ratio, 1 - self.clip_coef, 1 + self.clip_coef)
                policy_loss = torch.max(pg_loss1, pg_loss2).mean()
                
                # Clip Fraction Calculation
                with torch.no_grad():
                    clip_fracs += [((ratio - 1.0).abs() > self.clip_coef).float().mean().item()]
                    
                # Value Loss calculation (Clipped Value Loss)
                # Value function is often clipped to improve stability
                v_loss_unclipped = (new_values - mb_returns) ** 2
                v_clipped = mb_old_values + torch.clamp(new_values - mb_old_values, -self.clip_coef, self.clip_coef)
                v_loss_clipped = (v_clipped - mb_returns) ** 2
                value_loss = 0.5 * torch.max(v_loss_unclipped, v_loss_clipped).mean()
                
                # Entropy Loss (Encourages exploration)
                entropy_loss = entropy.mean()
                
                # Total Loss
                total_loss = policy_loss - self.ent_coef * entropy_loss + self.vf_coef * value_loss
                
                # Gradient step
                self.optimizer.zero_grad()
                total_loss.backward()
                nn.utils.clip_grad_norm_(self.network.parameters(), self.max_grad_norm)
                self.optimizer.step()
        
        # Calculate final metrics for logging
        with torch.no_grad():
            new_log_probs, _, new_values = self.network.get_log_prob(states, actions)
            
            # Approx KL divergence
            ratio = torch.exp(new_log_probs - old_log_probs)
            approx_kl = (ratio - 1.0 - ratio.log()).mean().item()
            
            # Explained Variance of Value Function
            y_pred = new_values.cpu().numpy()
            y_true = returns.cpu().numpy()
            var_y = np.var(y_true)
            explained_variance = 1 - np.var(y_true - y_pred) / (var_y + 1e-8) if var_y != 0 else 0
        
        return policy_loss.item(), value_loss.item(), entropy_loss.item(), approx_kl, explained_variance

    def save_policy(self, path):
        """Saves the policy network state dictionary."""
        torch.save(self.network.state_dict(), path)

    def load_policy(self, path):
        """Loads the policy network state dictionary."""
        self.network.load_state_dict(torch.load(path, map_location=self.device))