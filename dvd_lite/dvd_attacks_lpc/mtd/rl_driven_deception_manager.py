#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RL-Driven Deception Manager (The "Brain") - 완성본 (YAML 기반)
- [수정] YAML 기반의 6D State / 6D Action 정책을 로드합니다.
- 'Eyes'(mtd_state_reader)로부터 6D 상태(State)를 주기적으로 읽어옵니다.
- 'Hands'(iptables_mtd_controller)에게 6D 행동(Action)을 명령하여 iptables를 조작합니다.
"""

import os
import sys
import time
import argparse
import torch
import numpy as np

# [중요] rl/ppo.py 파일에서 ActorCritic 임포트
try:
    # `rl` 폴더가 아닌 상위 폴더(dvd_attacks_lpc)에서 실행될 경우를 대비
    sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
    from rl.ver_01.ppo import ActorCritic
except ImportError:
    print("Error: rl/ppo.py를 찾을 수 없습니다. 경로를 확인하세요.", file=sys.stderr)
    sys.exit(1)
    
# MTD (Eyes / Hands) 모듈 임포트
import mtd_state_reader # (Eyes - 전역 get_rl_state() 함수 임포트)
from controller import iptables_mtd_controller # (Hands)

# --- [중요] 시뮬레이터와 동일한 인터페이스 ---
# (참고: 이 값들은 mtd_state_reader와 iptables_mtd_controller에서 
#  YAML을 읽어 동적으로 결정되지만, 호환성 확인을 위해 하드코딩)
TESTBED_OBS_DIM = 6 
TESTBED_ACTION_DIM = 6
# ----------------------------------------

def main(args):
    device = torch.device(args.device)
    
    # 1. MTD (Hands) 컨트롤러 초기화 (YAML 로드)
    # (컨트롤러가 먼저 초기화되어야 YAML에서 Action/State Dim을 알 수 있음)
    controller = iptables_mtd_controller.IPTablesMTDController(
        config_path=args.mtd_config
    )
    print(f"[Brain] MTD 컨트롤러(Hands) 초기화 완료.")

    # [호환성 체크]
    if controller.action_dim != TESTBED_ACTION_DIM:
         print(f"Error: 컨트롤러 Action Dim({controller.action_dim}D)이 정책({TESTBED_ACTION_DIM}D)과 불일치!", file=sys.stderr)
         sys.exit(1)

    # 2. MTD (Eyes) 상태 리더 준비
    # (mtd_state_reader.py의 전역 인스턴스 GlobalStateReader가 사용됨)
    print(f"[Brain] MTD 상태 리더(Eyes) 준비 완료.")
    
    # 3. MTD 정책(신경망) 로드
    print(f"[Brain] MTD 정책 로딩 중: {args.policy}")
    
    # 시뮬레이터(Colab)와 동일한 State/Action 차원으로 모델 초기화
    policy = ActorCritic(TESTBED_OBS_DIM, TESTBED_ACTION_DIM).to(device)
    
    if not os.path.exists(args.policy):
        print(f"Error: 정책 파일({args.policy})을 찾을 수 없습니다!", file=sys.stderr)
        sys.exit(1)
        
    try:
        policy.load_state_dict(torch.load(args.policy, map_location=device))
        policy.eval() # 평가 모드로 설정 (중요)
        print(f"[Brain] MTD 정책 로드 완료.")
    except Exception as e:
        print(f"Error: 정책 파일 로드 실패. PPO 모델 구조(6D/6D)가 시뮬레이터와 동일한지 확인하세요. \n{e}", file=sys.stderr)
        sys.exit(1)

    # 4. 실시간 방어 루프 시작
    print("[Brain] 실시간 MTD 방어 루프를 시작합니다...")
    while True:
        try:
            # 4a. [Eyes] 현재 시스템 상태 관측 (6D Vector)
            current_state = mtd_state_reader.get_rl_state()
            state_tensor = torch.FloatTensor(current_state).to(device)

            # 4b. [Brain] 정책을 기반으로 MTD 행동 결정
            with torch.no_grad():
                action_id, _ = policy.act(state_tensor)

            # 4c. [Hands] 결정된 행동(Action ID)을 실제 시스템에 적용
            controller.execute_mtd_action_by_id(action_id)

            # 4d. MTD 실행 주기에 따라 대기
            time.sleep(args.interval)

        except KeyboardInterrupt:
            print("\n[Brain] MTD Manager 중지 신호 수신. 종료합니다.")
            break
        except Exception as e:
            print(f"[Brain] MTD 루프 오류 발생: {e}", file=sys.stderr)
            time.sleep(args.interval)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RL-Driven MTD Manager (YAML-based)")
    parser.add_argument('--policy', type=str, required=True, help='Colab에서 학습된 MTD 정책 파일 (.pth) 경로')
    parser.add_argument('--mtd_config', type=str, default='mtd/configs/iptables_mtd.yaml', help='MTD 행동 규칙서(Rulebook) YAML 파일 경로 (기준: dvd_attacks_lpc/)')
    parser.add_argument('--interval', type=int, default=10, help='MTD 실행 주기 (초)')
    parser.add_argument('--device', type=str, default="cuda" if torch.cuda.is_available() else "cpu", help='Device (cuda/cpu)')
    args = parser.parse_args()
    
    main(args)