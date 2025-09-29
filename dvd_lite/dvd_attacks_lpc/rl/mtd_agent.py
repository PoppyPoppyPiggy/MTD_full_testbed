#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import time
import json
import yaml
import numpy as np
from collections import deque

# RL 라이브러리 (예: Stable Baselines3)
# pip install stable-baselines3[extra]
try:
    from stable_baselines3 import PPO
    from stable_baselines3.common.env_checker import check_env
    import gymnasium as gym
    from gymnasium import spaces
except ImportError:
    print("RL 관련 패키지가 필요합니다: pip install stable-baselines3[extra] gymnasium")
    sys.exit(1)


# --- 경로 설정 및 로거 import ---
MTD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
LPC_ROOT = os.path.abspath(os.path.join(MTD_DIR, '..'))
if LPC_ROOT not in sys.path:
    sys.path.insert(0, LPC_ROOT)
from bus.logger import log_bus_event

def get_shared_path(filename: str) -> str:
    return os.path.join(LPC_ROOT, "mtd", "shared_state", filename)

POLICY_FILE_PATH = get_shared_path("mtd_policy.yaml")
BUS_LOG_PATH = os.path.join(LPC_ROOT, "bus", "bus.log")

class MtdEnv(gym.Env):
    """MTD 방어 결정을 위한 Gymnasium 환경"""
    def __init__(self, policy):
        super(MtdEnv, self).__init__()
        self.policy = policy
        self.postures = list(policy.get('defense_postures', {}).keys())
        
        # 행동 공간: 3가지 방어 태세 중 하나를 선택
        self.action_space = spaces.Discrete(len(self.postures))
        
        # 관찰 공간: [분당 공격 수, 블랙리스트 IP 수]
        self.observation_space = spaces.Box(low=0, high=100, shape=(2,), dtype=np.float32)
        
        self.attack_timestamps = deque(maxlen=100)
        self.blacklisted_ips = 0
        self.last_reward = 0

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.attack_timestamps.clear()
        self.blacklisted_ips = 0
        return self._get_obs(), {}

    def step(self, action):
        # 선택된 행동(방어 태세)을 시스템에 전달
        posture_name = self.postures[action]
        log_bus_event("rl_agent_decision", {"posture": posture_name})
        
        # 환경 상태 업데이트 (실제로는 외부에서 들어옴)
        self._update_state_from_log()
        
        # 보상 계산
        reward = self._calculate_reward()
        self.last_reward = reward
        
        # 종료 조건 (여기서는 항상 계속됨)
        terminated = False
        
        return self._get_obs(), reward, terminated, False, {}

    def _get_obs(self):
        now = time.time()
        # 최근 1분간의 공격 수 계산
        apm = sum(1 for ts in self.attack_timestamps if ts > now - 60)
        return np.array([apm, self.blacklisted_ips], dtype=np.float32)

    def _update_state_from_log(self):
        # 실제 구현에서는 bus.log를 파싱하여 상태를 업데이트해야 함
        # 여기서는 간단한 시뮬레이션을 위해 랜덤 요소를 추가
        if np.random.rand() < 0.1: # 10% 확률로 공격 발생
            self.attack_timestamps.append(time.time())
        if np.random.rand() < 0.05:
            self.blacklisted_ips = min(10, self.blacklisted_ips + 1)

    def _calculate_reward(self):
        # 보상 함수: 공격이 적고, 블랙리스트가 적을수록 높은 보상
        apm = self._get_obs()
        reward = 1.0 - (apm / 10.0) - (self.blacklisted_ips / 20.0)
        return reward

def main():
    print(" 시작...")
    with open(POLICY_FILE_PATH, 'r') as f:
        policy = yaml.safe_load(f)

    model_path = os.path.join(MTD_DIR, "rl", "models", policy.get("rl_model_name", "mtd_agent.zip"))
    
    # 훈련된 모델 로드
    if os.path.exists(model_path):
        print(f" 훈련된 모델 로드: {model_path}")
        model = PPO.load(model_path)
    else:
        print(f"[경고] 훈련된 모델({model_path})을 찾을 수 없습니다. 임의 행동 모드로 실행합니다.")
        model = None # Fallback to random actions

    # 환경 초기화
    # 실제 환경에서는 MtdEnv가 bus.log를 실시간으로 파싱해야 함
    # 여기서는 개념 증명을 위해 시뮬레이션된 환경 사용
    env = MtdEnv(policy)
    obs, _ = env.reset()

    decision_interval = policy.get('rl_decision_interval_s', 5)
    
    while True:
        if model:
            action, _states = model.predict(obs, deterministic=True)
        else:
            action = env.action_space.sample() # Random action

        obs, reward, terminated, _, info = env.step(action)
        
        posture = env.postures[action]
        print(f" 현재 관찰: {obs}, 선택된 태세: {posture}, 보상: {reward:.2f}")

        if terminated:
            obs, _ = env.reset()
        
        time.sleep(decision_interval)

if __name__ == "__main__":
    main()