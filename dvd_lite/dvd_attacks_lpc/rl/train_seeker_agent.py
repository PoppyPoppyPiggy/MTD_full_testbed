#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
from stable_baselines3 import PPO
from environment import MTDvsSeekerEnv

RL_DIR = os.path.dirname(os.path.realpath(__file__))
MODELS_DIR = os.path.join(RL_DIR, "models")
os.makedirs(MODELS_DIR, exist_ok=True)

DUMMY_STATE_PATH = "/shared/mtd_state.json"
DUMMY_CTI_PATH = "/shared/cti_info.json"

def train_seeker():
    """Seeker 공격 RL 에이전트를 훈련시키는 함수"""
    print("1. [Seeker] 강화학습 환경 생성...")
    env = MTDvsSeekerEnv(mtd_state_path=DUMMY_STATE_PATH, cti_info_path=DUMMY_CTI_PATH)
    print("2. [Seeker] PPO 모델 초기화...")
    model = PPO("MultiInputPolicy", env, verbose=1, tensorboard_log=os.path.join(RL_DIR, "seeker_tensorboard/"))
    print("3. [Seeker] 모델 훈련 시작...")
    for i in range(2):
        model.learn(total_timesteps=10000, reset_num_timesteps=False, tb_log_name="PPO_Seeker")
        model_path = os.path.join(MODELS_DIR, f"seeker_agent_{i+1}.zip")
        model.save(model_path)
        print(f"--- [Seeker] 중간 모델 저장 완료: {model_path} ---")
    print("4. [Seeker] 최종 모델 저장이 완료되었습니다.")

if __name__ == '__main__':
    train_seeker()