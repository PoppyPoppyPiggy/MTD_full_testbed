#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import gym
from gym import spaces
import numpy as np
import random
import json

# --- 상수 정의 ---
MTD_ACTIONS = {
    0: "NOOP",
    1: "SHUFFLE_IP_PORT",
    2: "SWAP_TO_VIRTUAL",
    3: "SWAP_TO_DUMMY"
}
SEEKER_ACTIONS = 6  # 0~4 후보 정찰, 5 광역 스캔

class MTDvsSeekerEnv(gym.Env):
    """
    MTD 방어 에이전트와 Seeker 공격 에이전트가 경쟁하는 강화학습 환경.
    (MTD 에이전트 관점)
    """
    metadata = {"render.modes": ["human"]}

    def __init__(self, mtd_state_path, cti_info_path):
        super(MTDvsSeekerEnv, self).__init__()

        self.mtd_state_path = mtd_state_path
        self.cti_info_path = cti_info_path

        # --- 행동 공간 ---
        self.action_space = spaces.Discrete(len(MTD_ACTIONS))

        # --- 관측 공간 ---
        self.observation_space = spaces.Dict({
            "mtd_config": spaces.Box(low=0, high=1, shape=(4,), dtype=np.float32),
            "cti_threat_level": spaces.Box(low=0, high=1, shape=(3,), dtype=np.float32),
            "seeker_activity": spaces.Box(low=0, high=5, shape=(1,), dtype=np.float32),
            "network_qos": spaces.Box(low=0, high=1, shape=(2,), dtype=np.float32)
        })

        # 내부 상태
        self.is_dummy_active = True
        self.is_dummy_drone_compromised = False
        self.steps_survived = 0

        self.reset()

    def _read_json_safe(self, path: str):
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except Exception:
            return {}

    def _get_observation(self):
        # (실제 구현 시) 외부 상태 반영
        # m = self._read_json_safe(self.mtd_state_path)
        # c = self._read_json_safe(self.cti_info_path)
        # 여기서는 시뮬레이션 값 사용
        cti_vec = np.clip(np.random.rand(3).astype(np.float32), 0.0, 1.0)
        seeker_pm = np.array([random.randint(0, 5)], dtype=np.float32)
        qos = np.clip(np.random.rand(2).astype(np.float32), 0.0, 1.0)

        mtd_config = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32) if self.is_dummy_active \
                     else np.array([0.0, 1.0, 0.0, 0.0], dtype=np.float32)

        return {
            "mtd_config": mtd_config,
            "cti_threat_level": cti_vec,
            "seeker_activity": seeker_pm,
            "network_qos": qos
        }

    def reset(self):
        self.is_dummy_active = random.choice([True, False])
        self.is_dummy_drone_compromised = False
        self.steps_survived = 0
        print("\n--- 새로운 전투 시작 ---")
        return self._get_observation()

    def step(self, action):
        self.steps_survived += 1
        mtd_action_name = MTD_ACTIONS.get(int(action), "UNKNOWN")

        # (간단 시뮬) Seeker 행동
        seeker_action = random.randint(0, SEEKER_ACTIONS - 1)

        # 기본 생존 보상
        reward = 1.0

        # MTD 행동 비용
        if mtd_action_name == "SHUFFLE_IP_PORT":
            reward -= 5.0
        elif mtd_action_name in ["SWAP_TO_VIRTUAL", "SWAP_TO_DUMMY"]:
            reward -= 3.0

        # 행동에 따른 상태 변화 (간단 규칙)
        if mtd_action_name == "SWAP_TO_VIRTUAL":
            self.is_dummy_active = False
        elif mtd_action_name == "SWAP_TO_DUMMY":
            self.is_dummy_active = True

        # 공격 성공 확률(시뮬): 더미 활성 시 성공 확률 상승(예시)
        hit_prob = 0.3 if self.is_dummy_active else 0.15
        is_hit = (random.random() < hit_prob)

        if is_hit:
            self.is_dummy_drone_compromised = True
            reward -= 100.0
            print(f"[결과] MTD 행동: {mtd_action_name} -> 💥 실제 드론 피격!")
        else:
            print(f"[결과] MTD 행동: {mtd_action_name} -> ✅ 방어 성공!")

        done = self.is_dummy_drone_compromised or (self.steps_survived >= 100)
        obs = self._get_observation()
        info = {"seeker_action": seeker_action, "hit": is_hit}

        return obs, reward, done, info

    def render(self, mode='human'):
        pass
