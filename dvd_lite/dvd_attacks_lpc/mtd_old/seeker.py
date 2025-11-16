#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Heuristic Seeker (The "Attacker Brain") - v3 (W&B Logging)
- W&B 연동 기능 추가: 자신의 행동과 인지 상태를 로깅
- 레벨(L0, L1, L2) 기반의 휴리스틱 전략을 사용합니다.
- MTD State Reader (Eyes)로부터 8D 상태(State)를 주기적으로 읽어옵니다.
- 'attack_orchestrator'를 실제 호출하여 공격 셸 스크립트를 실행합니다.
"""

import os
import sys
import time
import argparse
import numpy as np
import subprocess
import random
import json
import wandb  # [W&B] Weights & Biases 임포트

# --- Python 경로 수정 ---
# ... (기존 코드와 동일) ...
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(script_dir)
sys.path.insert(0, parent_dir)
# ---------------------

try:
    from mtd.mtd_state_reader import MTDStateReader
except ImportError:
    # ... (기존 오류 처리 코드) ...
    print(f"오류: mtd_state_reader를 찾을 수 없습니다.", file=sys.stderr)
    print(f"현재 경로: {os.getcwd()}")
    print(f"Python 경로: {sys.path}", file=sys.stderr)
    print("이 스크립트는 'dvd_attacks_lpc' 디렉토리에서 실행되어야 합니다.", file=sys.stderr)
    print("예: python3 mtd/seeker.py --config mtd/configs/iptables_mtd.yaml", file=sys.stderr)
    sys.exit(1)


# --- 공격 행동 정의 ---
# ... (기존 코드와 동일) ...
ACTION_PASS = 0
ACTION_SCAN = 1
ACTION_EXPLOIT = 2
ACTION_BREACH = 3
ALL_ACTIONS = [ACTION_PASS, ACTION_SCAN, ACTION_EXPLOIT, ACTION_BREACH]
ATTACK_ACTIONS = [ACTION_SCAN, ACTION_EXPLOIT, ACTION_BREACH]

# --- Seeker의 손 (SeekerHands) ---
class SeekerHands:
    # ... (기존 코드와 동일) ...
    def __init__(self, attack_orchestrator_path):
        self.orchestrator = os.path.abspath(attack_orchestrator_path)
        if not os.path.exists(self.orchestrator):
             print(f"[Seeker-Hands] Error: Attack Orchestrator를 찾을 수 없습니다: {self.orchestrator}", file=sys.stderr)
             self.orchestrator = None
        else:
            print(f"[Seeker-Hands] Attack Orchestrator 경로: {self.orchestrator}")
        
    def execute_attack_action_by_id(self, action_id: int, interval_sec: int):
        action_name = "pass"
        cmd = None
        
        if not self.orchestrator:
            print(f"[Seeker-Hands] Error: Orchestrator가 없어 공격을 실행할 수 없습니다 (Action ID: {action_id}).", file=sys.stderr)
            return

        duration_arg = str(int(interval_sec * 0.8)) # 주기의 80%만 실행

        if action_id == ACTION_SCAN:
            action_name = "Scan (wifi_slow_scan)"
            cmd = ["python3", self.orchestrator, "start", "wifi_slow_scan", "-d", duration_arg]
        elif action_id == ACTION_EXPLOIT:
            action_name = "Exploit (gps_slow_spoof)"
            cmd = ["python3", self.orchestrator, "start", "gps_slow_spoof", "-d", duration_arg]
        elif action_id == ACTION_BREACH:
            action_name = "Breach (companion-computer-takeover)"
            cmd = ["python3", self.orchestrator, "start", "companion-computer-takeover", "-d", duration_arg]
            
        if cmd:
            print(f"[Seeker-Hands] 🚀 Action: {action_name} (ID: {action_id}) 실행... (지속시간: {duration_arg}s)")
            print(f"    -> CMD: {' '.join(cmd)}")
            try:
                subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                print("    -> [Seeker-Hands] 공격이 백그라운드에서 시작되었습니다.")
            except Exception as e:
                print(f"    -> [Seeker-Hands] Error: 공격 실행 실패: {e}", file=sys.stderr)
        else:
             print(f"[Seeker-Hands] 😴 Action: Pass (ID: {action_id}).")


# --- Seeker의 두뇌 (Heuristic Brain) ---

class HeuristicSeekerL0:
    # ... (기존 코드와 동일) ...
    def __init__(self):
        print("[Seeker-Brain] 🧠 레벨 0 (L0) - Random Seeker 활성화.")
        self.name = "L0 (Random)"
        self.level_id = 0

    def get_action(self, state_vector):
        if random.random() < 0.5:
            return ACTION_PASS, False, False
        return random.choice(ATTACK_ACTIONS), False, False

class HeuristicSeekerL1:
    # ... (기존 코드와 동일) ...
    def __init__(self):
        print("[Seeker-Brain] 🧠 레벨 1 (L1) - Simple Scan & Attack Seeker 활성화.")
        self.name = "L1 (Simple FSM)"
        self.level_id = 1
        self.attack_phase = 0 
        self.action_sequence = [ACTION_SCAN, ACTION_EXPLOIT, ACTION_BREACH]

    def get_action(self, state_vector):
        action = self.action_sequence[self.attack_phase]
        self.attack_phase = (self.attack_phase + 1) % len(self.action_sequence)
        return action, False, False

class HeuristicSeekerL2:
    # ... (기존 코드와 동일) ...
    def __init__(self):
        print("[Seeker-Brain] 🧠 레벨 2 (L2) - Decoy-Aware Seeker 활성화.")
        self.name = "L2 (Decoy Aware)"
        self.level_id = 2
        self.l1_seeker = HeuristicSeekerL1() 
        self.decoy_state_index = 6
        self.alert_state_index = 7

    def get_action(self, state_vector):
        saw_decoy = False
        saw_alert = False
        try:
            saw_decoy = state_vector[self.decoy_state_index] > 0.1
            saw_alert = state_vector[self.alert_state_index] > 0.1
            
            if saw_decoy or saw_alert:
                if saw_decoy: print("[Seeker-Brain] (L2) 🚨 디코이 활성화 감지! 공격 중지 (Pass).")
                if saw_alert: print("[Seeker-Brain] (L2) 🔔 CTI 알림 감지! 공격 중지 (Pass).")
                return ACTION_PASS, saw_decoy, saw_alert
            else:
                print("[Seeker-Brain] (L2) 🤫 위협 없음. L1 공격 수행.")
                action, _, _ = self.l1_seeker.get_action(state_vector)
                return action, saw_decoy, saw_alert
                
        except Exception as e:
            print(f"[Seeker-Brain] (L2) Error: 상태 분석 중 오류: {e}. L1 공격 수행.")
            action, _, _ = self.l1_seeker.get_action(state_vector)
            return action, saw_decoy, saw_alert

# --- [W&B] W&B 초기화 함수 ---
def init_wandb(project, group_name, level):
    try:
        run_name = f"Seeker_L{level}"
        wandb_run = wandb.init(
            project=project,
            group=group_name,
            job_type="seeker",
            name=run_name,
            config={
                "seeker_level": level
            }
        )
        print(f"[Seeker-Brain] W&B 연동 성공. (Project: {project}, Group: {group_name}, Run: {run_name})")
        wandb_run.define_metric("global_step_time", summary="max")
        return wandb_run
    except Exception as e:
        print(f"[Seeker-Brain] W&B 연동 실패: {e}", file=sys.stderr)
        return None

# --- 메인 실행 ---

def main(args):
    
    # 1. Seeker (Hands) 컨트롤러 초기화
    controller = SeekerHands(
        attack_orchestrator_path=args.orchestrator
    )
    
    # 2. MTD 상태 리더 (Eyes) 초기화
    print(f"[Seeker-Eyes] MTD 상태 리더 초기화 (Config: {args.config})")
    try:
        state_reader = MTDStateReader(config_path=args.config)
        print("[Seeker-Eyes] MTD 상태 리더(Eyes) 초기화 완료.")
    except Exception as e:
        print(f"[Seeker-Eyes] MTD 상태 리더 초기화 실패: {e}", file=sys.stderr)
        sys.exit(1)

    # 3. Seeker (Brain) 초기화
    if args.level == 'L0':
        seeker_agent = HeuristicSeekerL0()
    elif args.level == 'L1':
        seeker_agent = HeuristicSeekerL1()
    elif args.level == 'L2':
        seeker_agent = HeuristicSeekerL2()
    else:
        print(f"오류: 알 수 없는 레벨 '{args.level}'. L1을 사용합니다.")
        seeker_agent = HeuristicSeekerL1()

    # 4. [W&B] W&B 초기화
    start_time = time.time()
    wandb_run = init_wandb(args.wandb_project, args.wandb_group, seeker_agent.level_id)

    print(f"[Seeker-Brain] {seeker_agent.name} 브레인으로 실시간 공격 루프를 시작합니다...")
    
    # 5. 실시간 공격 루프 시작
    try:
        while True:
            print("-" * 30) # 주기 구분을 위한 라인
            current_step_time = int(time.time() - start_time)

            # 5a. [Eyes] 현재 MTD 시스템 상태 관측 (8D Vector)
            current_state = state_reader.get_rl_state()
            print(f"[Seeker-Eyes] MTD 상태 관측 (8D): {current_state.tolist()}")

            # 5b. [Brain] 휴리스틱 정책을 기반으로 공격 행동 결정
            action_id, saw_decoy, saw_alert = seeker_agent.get_action(current_state)

            # 5c. [Hands] 결정된 행동(Action ID)을 실제 시스템에 적용
            controller.execute_attack_action_by_id(action_id, args.interval)

            # 5d. [W&B] W&B에 로깅
            if wandb_run:
                logs = {
                    "global_step_time": current_step_time,
                    "Seeker/Action_ID": action_id,
                    "Seeker/Cognition/Saw_Decoy_Flag": 1 if saw_decoy else 0,
                    "Seeker/Cognition/Saw_Alert_Flag": 1 if saw_alert else 0
                }
                wandb_run.log(logs)

            # 5e. 공격 실행 주기에 따라 대기
            print(f"[Seeker-Brain] (t_sleep) 다음 주기까지 {args.interval}초 대기...")
            time.sleep(args.interval)

    except KeyboardInterrupt:
        print("\n[Seeker-Brain] Seeker 중지 신호 수신. 종료합니다.")
    except Exception as e:
        print(f"[Seeker-Brain] Seeker 루프 오류 발생: {e}", file=sys.stderr)
        time.sleep(args.interval)
    finally:
        if wandb_run:
            wandb_run.finish()
            print("[Seeker-Brain] W&B run 종료.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Heuristic Level-Based MTD Seeker (W&B)")
    
    parser.add_argument('--level', type=str, default='L1', 
                        help='Seeker의 휴리스틱 레벨 (L0, L1, L2 중 선택)')
    parser.add_argument('--config', type=str, 
                        default='mtd/configs/iptables_mtd.yaml', 
                        help='MTD 상태 리더(Eyes)를 위한 YAML 설정 파일 경로')
    parser.add_argument('--orchestrator', type=str, 
                        default='attack_orchestrator.py', 
                        help='Attack Orchestrator 스크립트 경로')
    parser.add_argument('--interval', type=int, default=10, 
                        help='공격 실행 주기 (초)')
    
    # [W&B] W&B 인자 추가
    parser.add_argument("--wandb_project", type=str,
                        default="mtd_testbed_live",
                        help="W&B 프로젝트 이름")
    parser.add_argument("--wandb_group", type=str,
                        required=True,
                        help="W&B 그룹 이름 (예: vs_L0_Seeker). MTD 매니저의 그룹과 동일해야 합니다.")

    args = parser.parse_args()
    
    main(args)