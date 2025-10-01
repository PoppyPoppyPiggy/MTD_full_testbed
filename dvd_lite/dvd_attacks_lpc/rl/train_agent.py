#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 파일 이름: train_agent.py
# 최종 업데이트: v5.1 - 보고서 기반 게임이론, 전략적 보상, 내재적 호기심(ICM) 완전 구현

import os
import yaml
import numpy as np
from collections import deque

import torch
import torch.nn as nn
import torch.optim as optim
from torch.distributions import Categorical

import gymnasium as gym
from gymnasium import spaces

# --- 경로 설정 ---
RL_DIR = os.path.dirname(os.path.realpath(__file__))
LPC_DIR = os.path.abspath(os.path.join(RL_DIR, '..'))
POLICY_FILE_PATH = os.path.join(LPC_DIR, "mtd", "shared_state", "mtd_policy.yaml")
MODEL_SAVE_PATH = os.path.join(LPC_DIR, "rl", "models")
os.makedirs(MODEL_SAVE_PATH, exist_ok=True)
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# ##################################################################
# ## 섹션 1: 게임 이론 기반 환경 (MtdGameEnv)
# ##################################################################
class MtdGameEnv(gym.Env):
    """
    게임 이론 기반 MTD vs Seeker 환경 (v5.1)
    - 보고서 기반 '공격 표면' 상태, 선제적 행동, 전략적 보상 함수 적용
    """
    metadata = {"render_modes": []}

    def __init__(self, policy, training_agent='mtd'):
        super().__init__()
        self.policy = policy
        self.game_config = policy['game_theory_env']
        self.reward_weights = policy['rl']['reward_weights']

        self.attack_surface = self.game_config['attack_surface_ips']
        self.surface_size = len(self.attack_surface)

        self.training_agent = training_agent
        self.defender_agent = None
        self.seeker_agent = None

        # === 행동 공간 확장 (보고서 기반) ===
        # 0:STAY, 1:IP_SHUFFLE, 2:PORT_HOPPING(간소화), 3:DEPLOY_HONEYPOT, 4:BLACKLIST
        self.defender_action_space = spaces.Discrete(5)
        # [0..N-1]: Scan, [N..2N-1]: Attack
        self.seeker_action_space = spaces.Discrete(self.surface_size * 2)

        # === '공격 표면' 중심 상태 공간 (보고서 기반) ===
        self.defender_obs_space = spaces.Box(low=0, high=1, shape=(self.surface_size * 4,), dtype=np.float32)
        self.seeker_obs_space = spaces.Box(low=-2, high=1, shape=(self.surface_size,), dtype=np.float32)

        self.action_space = self.defender_action_space if training_agent == 'mtd' else self.seeker_action_space
        self.observation_space = self.defender_obs_space if training_agent == 'mtd' else self.seeker_obs_space

        self.max_steps = 200

    def set_opponents(self, defender_agent=None, seeker_agent=None):
        if defender_agent: self.defender_agent = defender_agent
        if seeker_agent: self.seeker_agent = seeker_agent

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        # gymnasium이 self.np_random을 세팅하지만 혹시 모를 케이스에 대비
        if not hasattr(self, "np_random"):
            self.np_random = np.random.default_rng(seed)

        self.current_step = 0
        self.real_target_idx = self.np_random.integers(0, self.surface_size)
        self.honeypot_idx = -1
        self.blacklisted_idx = -1
        self.seeker_knowledge = np.zeros(self.surface_size, dtype=np.float32)
        self.scan_log = np.zeros(self.surface_size, dtype=np.float32)
        self.attack_log = np.zeros(self.surface_size, dtype=np.float32)

        obs = self._get_defender_obs() if self.training_agent == 'mtd' else self._get_seeker_obs()
        return obs, {}

    def _get_seeker_obs(self):
        return self.seeker_knowledge.copy()

    def _get_defender_obs(self):
        honeypot_state = np.zeros(self.surface_size, dtype=np.float32)
        if self.honeypot_idx != -1:
            honeypot_state[self.honeypot_idx] = 1.0

        blacklist_state = np.zeros(self.surface_size, dtype=np.float32)
        if self.blacklisted_idx != -1:
            blacklist_state[self.blacklisted_idx] = 1.0

        scan_log_norm = self.scan_log / (np.sum(self.scan_log) + 1e-6)
        attack_log_norm = self.attack_log / (np.sum(self.attack_log) + 1e-6)
        return np.concatenate([attack_log_norm, scan_log_norm, honeypot_state, blacklist_state]).astype(np.float32)

    def step(self, action):
        # === 상대 에이전트 액션 생성 (언패킹 2개!) ===
        if self.training_agent == 'mtd':
            defender_action = int(action)
            obs_seeker = self._get_seeker_obs()
            seeker_action, _ = self.seeker_agent.policy.act(torch.FloatTensor(obs_seeker).to(DEVICE))
            seeker_action = seeker_action.item()
        else:
            seeker_action = int(action)
            obs_defender = self._get_defender_obs()
            defender_action, _ = self.defender_agent.policy.act(torch.FloatTensor(obs_defender).to(DEVICE))
            defender_action = defender_action.item()

        # === 보상 초기값 ===
        mtd_reward = self.reward_weights['mtd_action_cost']
        seeker_reward = self.reward_weights['seeker_action_cost']

        # === 방어자 행동 적용 ===
        if defender_action in [1, 2, 3]:
            mtd_reward += self.reward_weights['mtd_uncertainty_reward']

        if defender_action == 1:  # IP_SHUFFLE
            self.real_target_idx = self.np_random.integers(0, self.surface_size)
            self.seeker_knowledge.fill(0)
        elif defender_action == 3:  # DEPLOY_HONEYPOT
            self.honeypot_idx = (self.real_target_idx + self.np_random.integers(1, self.surface_size)) % self.surface_size
        elif defender_action == 4 and np.sum(self.attack_log) > 0:  # BLACKLIST
            self.blacklisted_idx = int(np.argmax(self.attack_log))
        if defender_action != 4:
            self.blacklisted_idx = -1

        # === 공격자 행동 적용 ===
        breach = False
        is_scan = seeker_action < self.surface_size
        target_idx = seeker_action % self.surface_size

        if is_scan:
            self.scan_log[target_idx] += 1
            if self.seeker_knowledge[target_idx] == 0 and np.random.rand() < self.game_config['scan_success_probability']:
                seeker_reward += self.reward_weights['seeker_scan_reveal_reward']
                if target_idx == self.real_target_idx:
                    self.seeker_knowledge[target_idx] = 1
                elif target_idx == self.honeypot_idx:
                    self.seeker_knowledge[target_idx] = -1
                else:
                    self.seeker_knowledge[target_idx] = -2
        else:
            self.attack_log[target_idx] += 1
            if target_idx == self.blacklisted_idx:
                seeker_reward += self.reward_weights['seeker_blocked_penalty']
                mtd_reward += self.reward_weights['mtd_defense_success_reward']
            elif target_idx == self.real_target_idx:
                seeker_reward += self.reward_weights['seeker_hit_reward']
                mtd_reward += self.reward_weights['mtd_breach_penalty']
                breach = True
            elif target_idx == self.honeypot_idx:
                seeker_reward += self.reward_weights['seeker_decoy_penalty']
                mtd_reward += self.reward_weights['mtd_deception_reward']
            else:
                seeker_reward += self.reward_weights['seeker_miss_penalty']
                mtd_reward += self.reward_weights['mtd_defense_success_reward']

        # === 종료 조건 ===
        self.current_step += 1
        terminated = self.current_step >= self.max_steps or breach

        obs = self._get_defender_obs() if self.training_agent == 'mtd' else self._get_seeker_obs()
        reward = mtd_reward if self.training_agent == 'mtd' else seeker_reward
        return obs, reward, terminated, False, {}

# ##################################################################
# ## 섹션 2: 신경망 아키텍처 (Actor-Critic & ICM)
# ##################################################################
class ActorCritic(nn.Module):
    def __init__(self, state_dim, action_dim):
        super(ActorCritic, self).__init__()
        self.actor = nn.Sequential(
            nn.Linear(state_dim, 128), nn.Tanh(),
            nn.Linear(128, 128), nn.Tanh(),
            nn.Linear(128, action_dim), nn.Softmax(dim=-1)
        )
        self.critic = nn.Sequential(
            nn.Linear(state_dim, 128), nn.Tanh(),
            nn.Linear(128, 128), nn.Tanh(),
            nn.Linear(128, 1)
        )

    def act(self, state):
        action_probs = self.actor(state)
        dist = Categorical(action_probs)
        action = dist.sample()
        action_logprob = dist.log_prob(action)
        return action.detach(), action_logprob.detach()

    def evaluate(self, state, action):
        action_probs = self.actor(state)
        dist = Categorical(action_probs)
        action_logprobs = dist.log_prob(action)
        dist_entropy = dist.entropy()
        state_values = self.critic(state)
        return action_logprobs, state_values, dist_entropy

class ICM(nn.Module):
    def __init__(self, state_dim, action_dim, lr=0.0003):
        super(ICM, self).__init__()
        self.feature_size = 128

        self.feature_encoder = nn.Sequential(nn.Linear(state_dim, 128), nn.ELU())
        self.inverse_model = nn.Sequential(
            nn.Linear(self.feature_size * 2, 128), nn.ELU(),
            nn.Linear(128, action_dim)
        )
        self.forward_model = nn.Sequential(
            nn.Linear(self.feature_size + action_dim, 128), nn.ELU(),
            nn.Linear(128, self.feature_size)
        )
        self.optimizer = optim.Adam(self.parameters(), lr=lr)

    def get_intrinsic_reward(self, state, next_state, action):
        state_feat = self.feature_encoder(state)
        next_state_feat = self.feature_encoder(next_state)
        predicted_next_state_feat = self.forward_model(torch.cat([state_feat, action], dim=1))
        intrinsic_reward = 0.5 * (predicted_next_state_feat - next_state_feat.detach()).pow(2).mean(dim=1)
        return intrinsic_reward.detach()

    def update(self, state, next_state, action_onehot):
        state_feat = self.feature_encoder(state)
        next_state_feat = self.feature_encoder(next_state)

        # Forward loss
        predicted_next_state_feat = self.forward_model(torch.cat([state_feat, action_onehot], dim=1))
        forward_loss = 0.5 * (predicted_next_state_feat - next_state_feat.detach()).pow(2).mean()

        # Inverse loss
        predicted_action = self.inverse_model(torch.cat([state_feat, next_state_feat], dim=1))
        inverse_loss = nn.CrossEntropyLoss()(predicted_action, action_onehot.argmax(dim=1))

        loss = forward_loss + inverse_loss
        self.optimizer.zero_grad()
        loss.backward()
        self.optimizer.step()

# ##################################################################
# ## 섹션 3: PPO 에이전트 (생략 없는 완전 구현)
# ##################################################################
class RolloutBuffer:
    def __init__(self):
        self.clear()
    def clear(self):
        self.states, self.actions, self.logprobs, self.rewards, self.is_terminals, self.next_states = [], [], [], [], [], []

class PPOAgent:
    def __init__(self, state_dim, action_dim, lr, ppo_epochs, use_icm=False, icm_config=None):
        self.buffer = RolloutBuffer()
        self.policy = ActorCritic(state_dim, action_dim).to(DEVICE)
        self.optimizer = torch.optim.Adam(self.policy.parameters(), lr=lr)
        self.policy_old = ActorCritic(state_dim, action_dim).to(DEVICE)
        self.policy_old.load_state_dict(self.policy.state_dict())
        self.MseLoss = nn.MSELoss()
        self.ppo_epochs = ppo_epochs

        self.use_icm = use_icm
        if self.use_icm:
            self.icm = ICM(state_dim, action_dim, lr=icm_config['icm_learning_rate']).to(DEVICE)
            self.intrinsic_reward_weight = icm_config['intrinsic_reward_weight']

    def select_action(self, state):
        with torch.no_grad():
            state_tensor = torch.as_tensor(state, dtype=torch.float32, device=DEVICE)
            action, action_logprob = self.policy_old.act(state_tensor)
        return action.item(), action_logprob.cpu()

    def update(self):
        # 1) 누적 보상 계산
        rewards = []
        discounted = 0.0
        for r, done in zip(reversed(self.buffer.rewards), reversed(self.buffer.is_terminals)):
            if done: discounted = 0.0
            discounted = r + 0.99 * discounted
            rewards.insert(0, discounted)
        rewards = torch.tensor(rewards, dtype=torch.float32, device=DEVICE)
        rewards = (rewards - rewards.mean()) / (rewards.std() + 1e-7)

        old_states = torch.stack([torch.from_numpy(s) for s in self.buffer.states]).float().to(DEVICE)
        old_next_states = torch.stack([torch.from_numpy(s) for s in self.buffer.next_states]).float().to(DEVICE)
        old_actions = torch.tensor(self.buffer.actions, dtype=torch.long, device=DEVICE)
        old_logprobs = torch.stack(self.buffer.logprobs).to(DEVICE)

        # 2) ICM 업데이트
        if self.use_icm:
            action_onehot = nn.functional.one_hot(old_actions, num_classes=self.policy.actor[-2].out_features).float()
            self.icm.update(old_states, old_next_states, action_onehot)

        # 3) PPO 업데이트
        for _ in range(self.ppo_epochs):
            logprobs, state_values, dist_entropy = self.policy.evaluate(old_states, old_actions)
            state_values = state_values.squeeze(-1)
            ratios = torch.exp(logprobs - old_logprobs.detach())
            advantages = rewards - state_values.detach()
            surr1 = ratios * advantages
            surr2 = torch.clamp(ratios, 0.8, 1.2) * advantages
            loss = -torch.min(surr1, surr2) + 0.5 * self.MseLoss(state_values, rewards) - 0.01 * dist_entropy

            self.optimizer.zero_grad()
            loss.mean().backward()
            self.optimizer.step()

        self.policy_old.load_state_dict(self.policy.state_dict())
        self.buffer.clear()

    def save(self, path):
        torch.save(self.policy_old.state_dict(), path)

    def load(self, path):
        sd = torch.load(path, map_location=DEVICE)
        self.policy_old.load_state_dict(sd)
        self.policy.load_state_dict(sd)

# ##################################################################
# ## 섹션 4: 메인 훈련 및 평가 로직
# ##################################################################
def main():
    print("="*60)
    print("    게임 이론, 전략적 보상, 내재적 호기심 기반 학습 (v5.1)    ")
    print(f"                       훈련 장치: {DEVICE}                       ")
    print("="*60)

    with open(POLICY_FILE_PATH, 'r') as f:
        policy = yaml.safe_load(f)

    cfg_rl = policy['rl']
    cfg_train = cfg_rl['training']
    cfg_icm = cfg_rl.get('icm', {'enable': False})

    # --- 환경 및 에이전트 생성 ---
    env = MtdGameEnv(policy, 'mtd')  # 초기화 시점의 training_agent는 의미 없음
    mtd_state_dim = env.defender_obs_space.shape[0]
    mtd_action_dim = env.defender_action_space.n
    seeker_state_dim = env.seeker_obs_space.shape[0]
    seeker_action_dim = env.seeker_action_space.n

    mtd_agent = PPOAgent(mtd_state_dim, mtd_action_dim, cfg_train['learning_rate'], cfg_train['ppo_epochs'],
                         use_icm=cfg_icm['enable'], icm_config=cfg_icm)
    seeker_agent = PPOAgent(seeker_state_dim, seeker_action_dim, cfg_train['learning_rate'], cfg_train['ppo_epochs'])

    # 🔧 FIX: 올바른 변수로 상대 주입
    env.set_opponents(defender_agent=mtd_agent, seeker_agent=seeker_agent)

    # --- 훈련 루프 ---
    print("--- 훈련 시작 ---")
    time_step = 0
    i_episode = 0

    while time_step < cfg_train['total_timesteps']:
        i_episode += 1
        state, _ = env.reset()
        done = False

        while not done:
            time_step += 1

            # MTD 에이전트 행동 선택
            mtd_obs = env._get_defender_obs()
            mtd_action, mtd_logprob = mtd_agent.select_action(mtd_obs)

            # Seeker 에이전트 행동 선택
            seeker_obs = env._get_seeker_obs()
            seeker_action, seeker_logprob = seeker_agent.select_action(seeker_obs)

            # 환경 진행: 각각의 관점으로 한 번씩 step
            env.training_agent = 'mtd'
            next_mtd_obs, mtd_reward, _, _, _ = env.step(mtd_action)
            env.training_agent = 'seeker'
            next_seeker_obs, seeker_reward, terminated, _, _ = env.step(seeker_action)
            done = terminated

            # ICM 내재 보상 (MTD)
            if mtd_agent.use_icm:
                action_onehot = nn.functional.one_hot(torch.tensor(mtd_action), num_classes=mtd_action_dim).float().to(DEVICE)
                intrinsic = mtd_agent.icm.get_intrinsic_reward(
                    torch.FloatTensor(mtd_obs).unsqueeze(0).to(DEVICE),
                    torch.FloatTensor(next_mtd_obs).unsqueeze(0).to(DEVICE),
                    action_onehot.unsqueeze(0)
                )
                mtd_reward += intrinsic.item() * mtd_agent.intrinsic_reward_weight

            # 버퍼 적재
            mtd_agent.buffer.states.append(mtd_obs)
            mtd_agent.buffer.next_states.append(next_mtd_obs)
            mtd_agent.buffer.actions.append(mtd_action)
            mtd_agent.buffer.logprobs.append(mtd_logprob)
            mtd_agent.buffer.rewards.append(mtd_reward)
            mtd_agent.buffer.is_terminals.append(done)

            seeker_agent.buffer.states.append(seeker_obs)
            seeker_agent.buffer.next_states.append(next_seeker_obs)
            seeker_agent.buffer.actions.append(seeker_action)
            seeker_agent.buffer.logprobs.append(seeker_logprob)
            seeker_agent.buffer.rewards.append(seeker_reward)
            seeker_agent.buffer.is_terminals.append(done)

            # 정책 업데이트
            if time_step % cfg_train['update_timestep'] == 0:
                print(f"\n--- [ Timestep {time_step} ] 정책 업데이트 ---")
                mtd_agent.update()
                seeker_agent.update()

        if i_episode % 100 == 0:
            print(f"Episode {i_episode}, Timestep {time_step}/{cfg_train['total_timesteps']}")

    # --- 모델 저장 ---
    print("\n--- 모든 훈련 완료 ---")
    mtd_path = os.path.join(MODEL_SAVE_PATH, policy['rl']['mtd_model_name'])
    seeker_path = os.path.join(MODEL_SAVE_PATH, policy['rl']['seeker_model_name'])
    mtd_agent.save(mtd_path)
    seeker_agent.save(seeker_path)
    print(f"[성공] 최종 모델 저장 완료:\n  - 방어자: {mtd_path}\n  - 공격자: {seeker_path}")

    # --- 최종 간단 테스트 ---
    print("\n--- 최종 에이전트 성능 테스트 (간략) ---")
    eval_env = MtdGameEnv(policy)
    eval_env.set_opponents(mtd_agent, seeker_agent)
    obs, _ = eval_env.reset()

    for step in range(20):
        def_obs = eval_env._get_defender_obs()
        def_action, _ = mtd_agent.select_action(def_obs)

        seek_obs = eval_env._get_seeker_obs()
        seek_action, _ = seeker_agent.select_action(seek_obs)

        if def_action == 1:
            eval_env.real_target_idx = np.random.randint(0, eval_env.surface_size)
            eval_env.seeker_knowledge.fill(0)
        elif def_action == 3:
            eval_env.honeypot_idx = (eval_env.real_target_idx + np.random.randint(1, eval_env.surface_size)) % eval_env.surface_size

        is_scan = seek_action < eval_env.surface_size
        target_idx = seek_action % eval_env.surface_size

        def_action_str = {0: "STAY", 1: "SHUFFLE", 2: "PORT_HOP", 3: "HONEYPOT", 4: "BLACKLIST"}[def_action]
        seek_action_str = "SCAN" if is_scan else "ATTACK"
        target_ip = eval_env.attack_surface[target_idx]

        result = "MISS"
        if is_scan:
            result = "INFO"
        else:
            if target_idx == eval_env.real_target_idx:
                result = "HIT!"
            elif target_idx == eval_env.honeypot_idx:
                result = "DECOY!"

        print(f"Step {step+1:02d} | Defender: {def_action_str:<12} | Seeker: {seek_action_str} on {target_ip:<12} -> {result}")

        eval_env.current_step += 1
        if eval_env.current_step >= eval_env.max_steps:
            print("--- 에피소드 종료 ---")
            obs, _ = eval_env.reset()

if __name__ == "__main__":
    main()
