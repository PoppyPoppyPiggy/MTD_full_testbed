#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import json
import time
import numpy as np

try:
    from stable_baselines3 import PPO
except ImportError:
    PPO = None

def get_shared_path(filename: str) -> str:
    container_path = os.path.join("/shared", filename)
    if os.path.exists(container_path): return container_path
    mtd_dir = os.path.join(os.path.dirname(__file__), '..', 'mtd')
    return os.path.join(mtd_dir, "shared_state", filename)

STATE_FILE_PATH = get_shared_path("mtd_state.json")

class SeekerAgent:
    """RL 기반 지능형 공격 에이전트 (v2.0)"""
    def __init__(self, model_path: str):
        self.run_flag = True
        self.mtd_state = {}
        self.seeker_agent = self.load_rl_agent(model_path)

    def load_rl_agent(self, model_path: str):
        if PPO is not None and os.path.exists(model_path):
            print(f"[Seeker] RL 에이전트 모델 로드: {model_path}")
            return PPO.load(model_path)
        print("[Seeker] RL 모델을 찾을 수 없어 랜덤 행동 모드로 동작합니다.")
        return None

    def read_mtd_state(self):
        try:
            with open(STATE_FILE_PATH, 'r') as f:
                self.mtd_state = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.mtd_state = {}

    def get_observation(self):
        # MTD Agent와 동일한 관측 공간을 사용 (상대방의 입장에서)
        is_dummy_active = self.mtd_state.get('dummy_active', True)
        obs = {
            "mtd_config": np.array([1.0 if is_dummy_active else 0.0, 0.0, 0.0, 0.0], dtype=np.float32),
            "cti_threat_level": np.zeros(3, dtype=np.float32), # Seeker는 CTI 정보를 모름
            "seeker_activity": np.array([0], dtype=np.float32), # 자기 자신의 활동이므로 0
            "network_qos": np.zeros(2, dtype=np.float32)
        }
        return obs

    def run(self):
        print("[Seeker] 지능형 공격 에이전트 시작...")
        while self.run_flag:
            self.read_mtd_state()
            
            if self.seeker_agent:
                obs = self.get_observation()
                action, _ = self.seeker_agent.predict(obs, deterministic=True)
                print(f"\r[Seeker] MTD 타겟: {self.mtd_state.get('current_target', 'N/A')}, AI 결정: PROBE {action}   ", end="")
            else:
                action = random.randint(0, 5)
                print(f"\r[Seeker] MTD 타겟: {self.mtd_state.get('current_target', 'N/A')}, 랜덤 행동: PROBE {action}", end="")

            # TODO: 결정된 action(프로빙)을 실제로 네트워크에 실행하는 로직 추가
            
            time.sleep(5)

if __name__ == "__main__":
    model_path = os.path.join(os.path.dirname(__file__), "models", "seeker_agent.zip")
    agent = SeekerAgent(model_path)
    agent.run()