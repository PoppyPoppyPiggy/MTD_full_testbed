#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
from stable_baselines3 import PPO
# from stable_baselines3.common.env_checker import check_env
from environment import MTDvsSeekerEnv

# --- 경로 설정 ---
RL_DIR = os.path.dirname(os.path.realpath(__file__))
MODELS_DIR = os.path.join(RL_DIR, "models")
os.makedirs(MODELS_DIR, exist_ok=True)

# (임시) MTD 및 CTI 상태 파일 경로
DUMMY_STATE_PATH = "/shared/mtd_state.json"
DUMMY_CTI_PATH = "/shared/cti_info.json"

def train():
    """MTD RL 에이전트를 훈련시키는 메인 함수"""
    print("1. 강화학습 환경 생성...")
    env = MTDvsSeekerEnv(mtd_state_path=DUMMY_STATE_PATH, cti_info_path=DUMMY_CTI_PATH)
    
    # Gym 호환성 점검(환경 구현 확정 후 사용 권장)
    # check_env(env) 

    print("2. PPO 모델 초기화...")
    model = PPO("MultiInputPolicy", env, verbose=1, tensorboard_log=os.path.join(RL_DIR, "mtd_tensorboard"))

    print("3. 모델 훈련 시작...")
    for i in range(2):
        model.learn(total_timesteps=10000, reset_num_timesteps=False, tb_log_name="PPO_MTD")
        model_path = os.path.join(MODELS_DIR, f"mtd_agent_{i+1}.zip")
        model.save(model_path)
        print(f"--- 중간 모델 저장 완료: {model_path} ---")

    print("4. 최종 모델 저장 완료.")

if __name__ == '__main__':
    # 필요 패키지: pip install stable-baselines3[extra] tensorboard
    train()
