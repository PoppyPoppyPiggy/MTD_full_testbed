#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 파일 이름: train.py (rl 폴더의 모든 스크립트를 이것 하나로 교체)
# 최종 업데이트: v6.0 - 시계열 패턴 분석 Seeker vs 적응형 위협 대응 MTD
import os
import sys
import yaml
import numpy as np
import torch
from collections import deque
import gymnasium as gym
from gymnasium import spaces
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv

# --- 경로 설정 ---
RL_DIR = os.path.dirname(os.path.realpath(__file__))
LPC_DIR = os.path.abspath(os.path.join(RL_DIR, '..'))
POLICY_FILE_PATH = os.path.join(LPC_DIR, "mtd", "shared_state", "mtd_policy.yaml")
MODEL_SAVE_PATH = os.path.join(LPC_DIR, "rl", "models")
os.makedirs(MODEL_SAVE_PATH, exist_ok=True)

class MtdAdversarialEnv_v6(gym.Env):
    """ 지능형 사이버 공방 시뮬레이션 환경 (v6.0) """
    def __init__(self, policy, training_agent='mtd', **kwargs):
        super().__init__()
        self.rules = policy['adversarial_rules']
        self.rewards_cfg = policy['rl']['reward_weights']
        self.training_agent = training_agent
        self.agents = kwargs
        
        self.ip_pool = self.rules['attack_surface']['ips']
        self.port_pool = self.rules['attack_surface']['ports']
        self.history_len = self.rules['seeker_observation_history_length']

        # === 행동 공간 ===
        self.mtd_action_space = spaces.Discrete(3) # 0:STAY, 1:SHUFFLE, 2:BLACKLIST
        self.seeker_action_space = spaces.Discrete(len(self.ip_pool) * 2) # SCAN/ATTACK

        # === 관찰 공간 ===
        # MTD: [APM(1), 블랙리스트_상태(N_ips), 현재_IP(1), 현재_PORT(1)]
        self.mtd_obs_space = spaces.Box(low=0, high=1, shape=(1 + len(self.ip_pool) + 2,), dtype=np.float32)
        # Seeker: [과거_IPs(H), 과거_Ports(H)]
        self.seeker_obs_space = spaces.Box(low=0, high=1, shape=(self.history_len * 2,), dtype=np.float32)

        if self.training_agent == 'mtd':
            self.action_space, self.observation_space = self.mtd_action_space, self.mtd_obs_space
        else:
            self.action_space, self.observation_space = self.seeker_action_space, self.seeker_obs_space
            
        self.max_steps = 200

    def set_agents(self, mtd_agent=None, seeker_agent=None):
        if mtd_agent: self.agents['mtd_agent'] = mtd_agent
        if seeker_agent: self.agents['seeker_agent'] = seeker_agent

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.current_step = 0
        self.active_ip_idx = self.np_random.integers(0, len(self.ip_pool))
        self.active_port_idx = self.np_random.integers(0, len(self.port_pool))
        
        self.attack_history = deque(maxlen=self.rules['adaptive_mtd_trigger']['apm_window_seconds'])
        self.blacklist = {i: 0 for i in range(len(self.ip_pool))} # 0: clean, >0: steps remaining
        
        self.surface_history = deque(maxlen=self.history_len)
        for _ in range(self.history_len):
            self.surface_history.append((-1, -1)) # History padding

        obs = self._get_mtd_obs() if self.training_agent == 'mtd' else self._get_seeker_obs()
        return obs, {}

    def _get_apm(self):
        return len(self.attack_history)

    def _get_mtd_obs(self):
        apm_norm = min(self._get_apm() / self.rules['adaptive_mtd_trigger']['apm_blacklist_threshold'], 1.0)
        blacklist_state = np.array([min(v / self.rules['blacklist_duration_steps'], 1.0) for v in self.blacklist.values()])
        ip_norm = self.active_ip_idx / (len(self.ip_pool) -1)
        port_norm = self.active_port_idx / (len(self.port_pool) -1)
        return np.concatenate([[apm_norm], blacklist_state, [ip_norm, port_norm]]).astype(np.float32)

    def _get_seeker_obs(self):
        history = np.array(list(self.surface_history), dtype=np.float32).flatten()
        # Normalize history indices
        history[::2] /= (len(self.ip_pool) - 1) # Normalize IPs
        history[1::2] /= (len(self.port_pool) - 1) # Normalize Ports
        return history

    def step(self, action):
        action = int(action)
        if self.training_agent == 'mtd':
            mtd_action = action
            seeker_action, _ = self.agents['seeker_agent'].predict(self._get_seeker_obs(), deterministic=True)
        else:
            seeker_action = action
            mtd_action, _ = self.agents['mtd_agent'].predict(self._get_mtd_obs(), deterministic=True)

        mtd_reward, seeker_reward = 0, 0
        self.attack_history.append(1) # Record activity for APM
        for ip_idx in self.blacklist: self.blacklist[ip_idx] = max(0, self.blacklist[ip_idx] - 1)
        
        # 1. MTD 행동 적용
        if mtd_action == 1: # SHUFFLE
            mtd_reward += self.rewards_cfg['mtd_cost_for_shuffle']
            self.active_ip_idx = self.np_random.integers(0, len(self.ip_pool))
            self.active_port_idx = self.np_random.integers(0, len(self.port_pool))
        elif mtd_action == 2: # BLACKLIST
            mtd_reward += self.rewards_cfg['mtd_cost_for_blacklist']
            # For simulation, we assume Seeker has a fixed source IP index 0.
            # In a real scenario, this would come from packet inspection.
            source_ip_idx_to_block = 0 
            self.blacklist[source_ip_idx_to_block] = self.rules['blacklist_duration_steps']
            mtd_reward += self.rewards_cfg['mtd_on_successful_blacklist']

        # 2. Seeker 행동 적용
        seeker_reward += self.rewards_cfg['seeker_action_cost']
        is_attack = seeker_action >= len(self.ip_pool)
        target_ip_idx = seeker_action % len(self.ip_pool)
        
        # 가정: Seeker의 소스 IP는 index 0
        if self.blacklist[0] > 0:
            seeker_reward += self.rewards_cfg['seeker_penalty_on_blacklisted']
        elif is_attack:
            if target_ip_idx == self.active_ip_idx:
                seeker_reward += self.rewards_cfg['seeker_on_real_hit']
                mtd_reward += self.rewards_cfg['mtd_penalty_on_real_hit']
            else: # Hit a decoy/empty space
                seeker_reward += self.rewards_cfg['seeker_on_decoy_hit']
                mtd_reward += self.rewards_cfg['mtd_on_decoy_hit']
        
        self.surface_history.append((self.active_ip_idx, self.active_port_idx))
        self.current_step += 1
        terminated = self.current_step >= self.max_steps
        
        obs = self._get_mtd_obs() if self.training_agent == 'mtd' else self._get_seeker_obs()
        reward = mtd_reward if self.training_agent == 'mtd' else seeker_reward
        return obs, reward, terminated, False, {}

class BattleReporter:
    def __init__(self, policy, mtd_agent, seeker_agent):
        self.env = MtdAdversarialEnv_v6(policy, 'mtd', mtd_agent=mtd_agent, seeker_agent=seeker_agent)
        self.policy = policy
    
    def run(self, episodes=1):
        print("\n" + "="*70)
        print(" " * 20 + "최종 에이전트 작전 보고서" + " " * 20)
        print("="*70)
        
        stats = {'seeker_hits': 0, 'total_attacks': 0, 'mtd_blacklists': 0, 'seeker_blacklisted': 0}
        
        for ep in range(episodes):
            obs, _ = self.env.reset()
            done = False
            print(f"\n--- [ 모의전 #{ep+1} 시작 ] ---")
            while not done:
                # 1. 에이전트 의사결정 기록
                mtd_obs = self.env._get_mtd_obs()
                mtd_action, _ = self.env.agents['mtd_agent'].predict(mtd_obs, deterministic=True)
                seeker_obs = self.env._get_seeker_obs()
                seeker_action, _ = self.env.agents['seeker_agent'].predict(seeker_obs, deterministic=True)

                # 2. 의사결정 근거 출력
                log = f"Step {self.env.current_step+1:03d} | "
                apm = self.env._get_apm()
                mtd_action_str = {0:"STAY", 1:"SHUFFLE", 2:"BLACKLIST"}[int(mtd_action)]
                log += f"MTD (APM:{apm}): Sees APM, Decides [{mtd_action_str}] | "

                is_attack = int(seeker_action) >= len(self.env.ip_pool)
                target_idx = int(seeker_action) % len(self.env.ip_pool)
                seeker_action_str = "ATTACK" if is_attack else "SCAN"
                log += f"Seeker: Sees History, Decides [{seeker_action_str} on IP {target_idx}]"
                print(log)

                # 3. 환경 스텝 및 결과 기록
                _, _, done, _, _ = self.env.step(mtd_action)
                
                # 통계 업데이트
                if mtd_action == 2: stats['mtd_blacklists'] += 1
                if self.env.blacklist[0] > 0: stats['seeker_blacklisted'] +=1
                if is_attack and self.env.blacklist[0] == 0:
                    stats['total_attacks'] += 1
                    if target_idx == self.env.active_ip_idx:
                        stats['seeker_hits'] += 1

        # 4. 최종 결과 요약
        hit_rate = (stats['seeker_hits'] / stats['total_attacks'] * 100) if stats['total_attacks'] > 0 else 0
        print("\n" + "="*70)
        print(" " * 25 + "종합 결과 요약" + " " * 25)
        print("="*70)
        print(f"  - Seeker 타격 성공률: {hit_rate:.2f}% ({stats['seeker_hits']} / {stats['total_attacks']})")
        print(f"  - MTD 블랙리스트 발동 횟수: {stats['mtd_blacklists']} 회")
        print(f"  - Seeker 블랙리스트 페널티 횟수: {stats['seeker_blacklisted']} 스텝")
        print("="*70)

def main():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"훈련 장치: {device.upper()}")
    with open(POLICY_FILE_PATH, 'r') as f: policy = yaml.safe_load(f)

    mtd_env = DummyVecEnv([lambda: MtdAdversarialEnv_v6(policy, 'mtd')])
    seeker_env = DummyVecEnv([lambda: MtdAdversarialEnv_v6(policy, 'seeker')])
    
    mtd_agent = PPO("MlpPolicy", mtd_env, policy_kwargs=dict(net_arch=[256, 256]), device=device)
    seeker_agent = PPO("MlpPolicy", seeker_env, policy_kwargs=dict(net_arch=[256, 256]), device=device)

    config = policy['rl']['training']
    for i in range(config['total_iterations']):
        print(f"\n--- [ 자체 대련 라운드 {i + 1}/{config['total_iterations']} ] ---")
        mtd_env.env_method('set_agents', seeker_agent=seeker_agent)
        print(">> (1/2) MTD 에이전트 학습 중...")
        mtd_agent.learn(total_timesteps=config['timesteps_per_iteration'], progress_bar=True, reset_num_timesteps=(i==0))
        
        seeker_env.env_method('set_agents', mtd_agent=mtd_agent)
        print(">> (2/2) Seeker 에이전트 학습 중...")
        seeker_agent.learn(total_timesteps=config['timesteps_per_iteration'], progress_bar=True, reset_num_timesteps=(i==0))
        
    print("\n--- 모든 훈련 완료 ---")
    mtd_agent.save(os.path.join(MODEL_SAVE_PATH, policy['rl']['model_name']['mtd']))
    seeker_agent.save(os.path.join(MODEL_SAVE_PATH, policy['rl']['model_name']['seeker']))
    
    reporter = BattleReporter(policy, mtd_agent, seeker_agent)
    reporter.run()

if __name__ == "__main__":
    main()

