import gymnasium as gym
from gymnasium import spaces
import numpy as np

class AdversarialDroneEnv(gym.Env):
    """
    MTD Engine과 Seeker가 적대적으로 학습하는 환경.
    한 에이전트를 학습시키는 동안 상대방 에이전트의 정책은 고정됩니다.
    """
    def __init__(self, opponent_agent, training_mtd):
        super(AdversarialDroneEnv, self).__init__()
        self.opponent_agent = opponent_agent
        self.training_mtd = training_mtd  # True이면 MTD 에이전트, False이면 Seeker 에이전트를 학습

        # 공격 표면의 상태 공간 (예: 5개의 설정, 각 설정은 on/off)
        self.attack_surface_space = spaces.MultiBinary(5)
        # MTD Engine (방어자)의 행동 공간 (5개의 설정을 on/off)
        self.mtd_action_space = spaces.MultiBinary(5)
        # Seeker (공격자)의 행동 공간 (5개의 설정 중 하나를 공격)
        self.seeker_action_space = spaces.Discrete(5)

        # 에이전트별 관찰/행동 공간 설정
        if self.training_mtd:
            self.action_space = self.mtd_action_space
            self.observation_space = spaces.Dict({
                "attack_surface": self.attack_surface_space,
                "last_seeker_action": spaces.Discrete(6)
            })
        else:
            self.action_space = self.seeker_action_space
            self.observation_space = self.attack_surface_space
        
        self.max_steps = 100
        self.current_step = 0

    def _get_mtd_obs(self):
        return {"attack_surface": self.attack_surface, "last_seeker_action": self.last_seeker_action}

    def _get_seeker_obs(self):
        return self.attack_surface

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.attack_surface = self.attack_surface_space.sample()
        self.last_seeker_action = 0
        self.current_step = 0
        
        if self.training_mtd:
            return self._get_mtd_obs(), {}
        else:
            return self._get_seeker_obs(), {}

    def step(self, action):
        seeker_obs_before_mtd = self._get_seeker_obs()
        
        if self.training_mtd:
            mtd_action = action
            seeker_action, _ = self.opponent_agent.predict(seeker_obs_before_mtd, deterministic=True)
        else:
            seeker_action = action
            mtd_obs = self._get_mtd_obs()
            mtd_action, _ = self.opponent_agent.predict(mtd_obs, deterministic=True)
            
        # 1. MTD Engine이 공격 표면을 변경
        self.attack_surface = mtd_action
        
        # 2. Seeker가 공격 수행
        self.last_seeker_action = seeker_action + 1

        # 3. 보상 계산 (Zero-Sum Game)
        if self.attack_surface[seeker_action] == 1:
            seeker_reward = 1
            mtd_reward = -1
        else:
            seeker_reward = -1
            mtd_reward = 1

        self.current_step += 1
        done = self.current_step >= self.max_steps
        
        if self.training_mtd:
            obs = self._get_mtd_obs()
            reward = mtd_reward
        else:
            obs = self._get_seeker_obs()
            reward = seeker_reward
            
        return obs, reward, done, False, {}