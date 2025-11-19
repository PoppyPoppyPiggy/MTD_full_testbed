# File: MTD_full_testbed/dvd_lite/dvd_attacks_lpc/mtd/config_v05.py
#
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[신규 2/11] MTD_RL v05 학습용 설정 파일 (argparse)

- rl_train_v05.py가 이 파일을 임포트하여 하이퍼파라미터를 로드합니다.
"""

import argparse
import torch
import time

def get_args():
    parser = argparse.ArgumentParser(description="MTD_RL v05 - PPO Trainer (Hybrid, Passive CTI)")

    # --- Wandb 설정 ---
    parser.add_argument('--wandb-project', type=str, default="MTD_RL_v05_Passive_CTI",
                        help="Wandb 프로젝트 이름")
    parser.add_argument('--wandb-entity', type=str, default=None,
                        help="Wandb 엔티티 (팀/개인)")
    parser.add_argument('--disable-wandb', action='store_true',
                        help="Wandb 로깅을 비활성화합니다.")
    parser.add_argument('--run-name', type=str, default=f"ppo_v05_{int(time.time())}",
                        help="Wandb 실행 이름")

    # --- 학습 파라미터 ---
    parser.add_argument('--seed', type=int, default=42, help="랜덤 시드")
    parser.add_argument('--device', type=str, default="cuda" if torch.cuda.is_available() else "cpu",
                        help="학습 장치 (cuda 또는 cpu)")
    parser.add_argument('--updates', type=int, default=1000,
                        help="총 학습 업데이트 횟수 (에포크 아님)")

    # --- PPO 하이퍼파라미터 (Continuous) ---
    parser.add_argument('--lr', type=float, default=3e-4, help="학습률 (Adam)")
    parser.add_argument('--gamma', type=float, default=0.99, help="할인 계수 (Discount factor)")
    parser.add_argument('--gae-lambda', type=float, default=0.95,
                        help="GAE(Generalized Advantage Estimation) Lambda")
    parser.add_argument('--clip-eps', type=float, default=0.2,
                        help="PPO 클리핑 (Epsilon)")
    parser.add_argument('--n-epochs', type=int, default=10,
                        help="1회 업데이트 시 PPO 학습 에포크 수")
    parser.add_argument('--batch-size', type=int, default=2048,
                        help="1회 업데이트(Rollout)에 사용할 총 스텝 수")
    parser.add_argument('--minibatch-size', type=int, default=64,
                        help="PPO 1 에포크 내 미니배치 크기")
    parser.add_argument('--ent-coef', type=float, default=0.01,
                        help="엔트로피 보너스 계수")
    parser.add_argument('--vf-coef', type=float, default=0.5,
                        help="Value Function (Critic) 손실 계수")
    parser.add_argument('--max-grad-norm', type=float, default=0.5,
                        help="Gradient clipping 최대치")

    # --- 시뮬레이션 환경 파라미터 ---
    parser.add_argument('--max-episode-steps', type=int, default=200,
                        help="시뮬레이션 1 에피소드의 최대 스텝 수 (1스텝=1분 가정시 200분)")
    parser.add_argument('--seeker-level', type=int, default=3, choices=[0, 1, 2, 3, 4],
                        help="Seeker 레벨 (0=Naive, 4=Aggressive). 환경 난이도 조절.")
    
    # --- 내보내기 설정 ---
    parser.add_argument('--export-dir', type=str, default="./mtd/rl_models/ver_05",
                        help="학습 완료 후 .pth와 meta.json을 저장할 디렉토리")

    args = parser.parse_args()
    
    # 파생 변수 계산
    args.num_minibatches = args.batch_size // args.minibatch_size
    
    return args