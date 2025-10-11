# ppo_agent.py
import torch
import torch.nn as nn
import config
from networks import ActorCritic

class RolloutBuffer:
    """PPO 업데이트를 위한 경험(trajectory)을 저장하는 버퍼."""
    def __init__(self):
        # [수정] 버퍼 리스트를 빈 리스트로 초기화
        self.actions = []
        self.states = []
        self.logprobs = []
        self.rewards = []
        self.is_terminals = []

    def clear(self):
        del self.actions[:]
        del self.states[:]
        del self.logprobs[:]
        del self.rewards[:]
        del self.is_terminals[:]

class PPOAgent:
    """PPO 알고리즘을 사용하는 강화학습 에이전트."""
    def __init__(self, state_dim, action_dim):
        self.buffer = RolloutBuffer()

        self.policy = ActorCritic(state_dim, action_dim).to(config.DEVICE)
        # [수정] 옵티마이저에 학습할 파라미터와 학습률을 전달하여 초기화
        self.optimizer = torch.optim.Adam(self.policy.parameters(), lr=config.LEARNING_RATE)

        self.policy_old = ActorCritic(state_dim, action_dim).to(config.DEVICE)
        self.policy_old.load_state_dict(self.policy.state_dict())

        self.MseLoss = nn.MSELoss()

    def select_action(self, state):
        """상태를 입력받아 행동을 선택하고 버퍼에 저장."""
        with torch.no_grad():
            state = torch.FloatTensor(state).to(config.DEVICE)
            action, action_logprob, _ = self.policy_old.act(state)

        self.buffer.states.append(state)
        self.buffer.actions.append(action)
        self.buffer.logprobs.append(action_logprob)

        return action.item()

    def update(self):
        """버퍼에 저장된 데이터를 사용하여 정책을 업데이트."""
        # [수정] 보상 리스트를 빈 리스트로 초기화
        rewards = []
        discounted_reward = 0
        for reward, is_terminal in zip(reversed(self.buffer.rewards), reversed(self.buffer.is_terminals)):
            if is_terminal:
                discounted_reward = 0
            discounted_reward = reward + (config.GAMMA * discounted_reward)
            rewards.insert(0, discounted_reward)

        rewards = torch.tensor(rewards, dtype=torch.float32).to(config.DEVICE)
        rewards = (rewards - rewards.mean()) / (rewards.std() + 1e-7)

        old_states = torch.squeeze(torch.stack(self.buffer.states, dim=0)).detach().to(config.DEVICE)
        old_actions = torch.squeeze(torch.stack(self.buffer.actions, dim=0)).detach().to(config.DEVICE)
        old_logprobs = torch.squeeze(torch.stack(self.buffer.logprobs, dim=0)).detach().to(config.DEVICE)

        for _ in range(config.PPO_EPOCHS):
            logprobs, state_values, dist_entropy = self.policy.evaluate(old_states, old_actions)
            state_values = torch.squeeze(state_values)
            ratios = torch.exp(logprobs - old_logprobs.detach())
            advantages = rewards - state_values.detach()
            surr1 = ratios * advantages
            surr2 = torch.clamp(ratios, 1 - config.EPSILON_CLIP, 1 + config.EPSILON_CLIP) * advantages
            loss = -torch.min(surr1, surr2) + 0.5 * self.MseLoss(state_values, rewards) - config.ENTROPY_COEFF * dist_entropy

            self.optimizer.zero_grad()
            loss.mean().backward()
            self.optimizer.step()

        self.policy_old.load_state_dict(self.policy.state_dict())
        self.buffer.clear()