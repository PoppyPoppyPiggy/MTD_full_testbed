#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import yaml
import time
import random
import numpy as np
from collections import deque, Counter

# RL 라이브러리 (Stable Baselines3) 및 Gym 환경
try:
    import gymnasium as gym
    from gymnasium import spaces
    from stable_baselines3 import PPO
    from stable_baselines3.common.env_checker import check_env
except ImportError:
    print("RL 관련 패키지가 필요합니다: pip install stable-baselines3[extra] gymnasium torch")
    sys.exit(1)

# --- 경로 설정 ---
MTD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
POLICY_FILE_PATH = os.path.join(MTD_DIR, "mtd", "shared_state", "mtd_policy.yaml")
MODEL_SAVE_PATH = os.path.join(MTD_DIR, "rl", "models")

class SimulatedSeeker:
    """ MTD 환경 내에서 행동하는 가상 Seeker 에이전트 """
    def __init__(self):
        self.knowledge_base = deque(maxlen=20) # 최근 20개의 셔플링 패턴 기억
        self.learning_rate = 0.7

    def observe_and_learn(self, target_ip):
        self.knowledge_base.append(target_ip)

    def predict_and_attack(self):
        if not self.knowledge_base or random.random() > self.learning_rate:
            # 학습이 부족하거나 확률적으로 정찰 실패 시, 무작위 공격
            return f"10.13.0.{random.randint(100, 102)}", False # 주로 디코이 공격
        
        # 가장 빈번하게 나타난 IP를 다음 타겟으로 예측 (간단한 모델)
        most_common_ip = Counter(self.knowledge_base).most_common(1)
        return most_common_ip, True # 예측 기반 공격

class MtdEnv(gym.Env):
    """ MTD 방어 전략 학습을 위한 강화학습 환경 """
    metadata = {'render_modes': ['human']}

    def __init__(self, policy):
        super(MtdEnv, self).__init__()
        self.policy = policy
        self.weights = policy.get('des_scoring', {}).get('weights', {})
        
        # 1. 행동 공간 정의 (3가지 방어 태세)
        self.postures = list(policy.get('defense_postures', {}).keys())
        self.action_space = spaces.Discrete(len(self.postures))

        # 2. 관찰 공간 정의:
        self.observation_space = spaces.Box(
            low=np.array(), 
            high=np.array(), 
            dtype=np.float32
        )
        
        self.seeker = SimulatedSeeker()
        self.real_target_ip = policy.get('real_target_ip')
        self.episode_length = 300 # 1 에피소드 당 스텝 수 (시간)
        self.reset()

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.current_step = 0
        self.current_posture_idx = 0 # 초기: LOW_PROFILE
        self.shuffle_interval = self.policy['defense_postures']['shuffle_interval_s']
        
        self.attack_history = deque(maxlen=60) # 최근 1분간의 공격 기록
        self.decoy_hit_history = deque(maxlen=60)
        
        self.seeker.knowledge_base.clear()
        
        print("\n--- 새로운 에피소드 시작 ---")
        return self._get_obs(), {}

    def step(self, action):
        self.current_step += 1
        
        # 1. 행동(방어 태세) 적용
        self.current_posture_idx = action
        posture_name = self.postures[action]
        self.shuffle_interval = self.policy['defense_postures'][posture_name]['shuffle_interval_s']
        
        # 2. Seeker의 행동 시뮬레이션
        is_attack, is_real_hit, is_decoy_hit = self._simulate_seeker_attack()
        
        if is_attack:
            self.attack_history.append(is_real_hit)
            self.decoy_hit_history.append(is_decoy_hit)

        # 3. 보상 계산
        reward = self._calculate_reward(is_real_hit, is_decoy_hit, posture_name)
        
        # 4. 종료 조건
        terminated = self.current_step >= self.episode_length
        
        return self._get_obs(), reward, terminated, False, {}

    def _get_obs(self):
        apm = len(self.attack_history)
        attack_success_rate = sum(self.attack_history) / apm if apm > 0 else 0
        decoy_hit_rate = sum(self.decoy_hit_history) / apm if apm > 0 else 0
        
        return np.array([apm, attack_success_rate, self.shuffle_interval, decoy_hit_rate], dtype=np.float32)

    def _simulate_seeker_attack(self):
        # 공격 발생 확률 (APM이 높을수록 공격이 잦음)
        if random.random() > 0.5:
            return False, False, False

        # 현재 활성화된 IP (셔플링 주기에 따라 확률적으로 실제 자산 노출)
        # 셔플 주기가 짧을수록 Seeker의 예측이 어려워짐 (혼란 가중)
        real_asset_exposed_prob = self.shuffle_interval / 120.0 
        current_active_ip = self.real_target_ip if random.random() < real_asset_exposed_prob else "10.13.0.100"
        
        self.seeker.observe_and_learn(current_active_ip)
        predicted_ip, is_predictive_attack = self.seeker.predict_and_attack()

        is_real_hit = (predicted_ip == self.real_target_ip and current_active_ip == self.real_target_ip)
        is_decoy_hit = not is_real_hit
        
        return True, is_real_hit, is_decoy_hit

    def _calculate_reward(self, is_real_hit, is_decoy_hit, posture):
        # 4-Axis DES 모델 기반 보상 함수
        
        # 1. 보안성 (Security)
        security_reward = -10.0 if is_real_hit else 1.0 # 실제 자산 피격 시 큰 패널티

        # 2. 기만성 (Deception)
        deception_reward = 2.0 if is_decoy_hit else 0.0

        # 3. 비용 (Cost)
        cost_penalty = 0
        if posture == 'ACTIVE_DECEPTION':
            cost_penalty = -0.2
        elif posture == 'ISOLATION':
            cost_penalty = -0.5
        
        # 4. 기민성 (Agility) - 짧은 주기는 그 자체로 비용이므로 Cost에 반영됨
        
        total_reward = (self.weights['security'] * security_reward +
                        self.weights['deception'] * deception_reward +
                        self.weights['cost'] * cost_penalty)
        
        return total_reward

    def render(self, mode='human'):
        obs = self._get_obs()
        posture = self.postures[self.current_posture_idx]
        print(f"Step: {self.current_step} | Posture: {posture:<18} | APM: {obs:.0f} | SuccessRate: {obs:.2f} | Interval: {obs:.0f}s")


def main():
    # 정책 파일 로드
    try:
        with open(POLICY_FILE_PATH, 'r') as f:
            policy = yaml.safe_load(f)
    except FileNotFoundError:
        print(f"[오류] 정책 파일({POLICY_FILE_PATH})을 찾을 수 없습니다.")
        sys.exit(1)

    # 환경 생성 및 검증
    env = MtdEnv(policy)
    check_env(env)

    # 모델 저장 경로 확인 및 생성
    os.makedirs(MODEL_SAVE_PATH, exist_ok=True)
    model_file = os.path.join(MODEL_SAVE_PATH, policy.get("rl_model_name", "mtd_agent.zip"))

    # PPO 모델 생성 및 훈련
    model = PPO("MlpPolicy", env, verbose=1, tensorboard_log="./mtd_tensorboard/")
    
    print("\n--- 강화학습 에이전트 훈련 시작 ---")
    # total_timesteps: 총 훈련 스텝 수. 높을수록 학습이 더 잘 되지만 오래 걸림.
    model.learn(total_timesteps=20000, progress_bar=True)
    print("--- 훈련 완료 ---")

    # 훈련된 모델 저장
    model.save(model_file)
    print(f"\n[성공] 훈련된 모델이 다음 경로에 저장되었습니다: {model_file}")

    # 훈련된 에이전트 테스트
    print("\n--- 훈련된 에이전트 성능 테스트 ---")
    obs, _ = env.reset()
    for i in range(100):
        action, _states = model.predict(obs, deterministic=True)
        obs, reward, terminated, _, info = env.step(action)
        env.render()
        if terminated:
            obs, _ = env.reset()

    env.close()

if __name__ == "__main__":
    main()