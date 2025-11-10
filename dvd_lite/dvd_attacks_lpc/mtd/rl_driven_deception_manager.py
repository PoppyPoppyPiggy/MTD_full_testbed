#!/usr/bin/env python3
import argparse
import time
import torch
import numpy as np
import os
import sys
import json
import yaml
import torch.nn as nn
import torch.nn.functional as F

# --- Python 경로 수정 ---
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(script_dir)
sys.path.insert(0, parent_dir)
# ---------------------

from mtd.controller.iptables_mtd_controller import IPTablesMTDController
from mtd.mtd_state_reader import MTDStateReader 
from mtd.adapters.rl_export_hook import RLExportHook

# 에이전트의 상태 및 정책 공유 디렉터리
STATE_DIR = "mtd/shared_state"
POLICY_FILE = os.path.join(STATE_DIR, "mtd_policy.json") # RL 에이전트(Seeker)가 읽어갈 정책 파일
# [수정] RLExportHook가 None을 허용하도록 수정되었으므로, 더미 파일 대신 None 전달
# DUMMY_STATE_FILE = os.path.join(STATE_DIR, "mtd_state_dummy.json")

# 강화학습(RL) 정책을 위한 설정
DEFAULT_POLICY_PATH = "mtd/shared_state/defender_policy_L4.pth"
TESTBED_ACTION_DIM = 7  # 테스트베드에서 예상하는 행동 차원 (모델 분석: 7)
TESTBED_STATE_DIM = 8   # 테스트베드에서 예상하는 상태 차원 (모델 분석: 8)

# --- MTD_RL/ver_01/utils.py 에서 가져온 정책 모델 구조 ---
class PolicyNetwork(nn.Module):
    def __init__(self, state_dim, action_dim):
        super(PolicyNetwork, self).__init__()
        self.layer_1 = nn.Linear(state_dim, 64)
        self.layer_2 = nn.Linear(64, 64)
        self.layer_3 = nn.Linear(64, action_dim)

    def forward(self, state):
        x = F.relu(self.layer_1(state))
        x = F.relu(self.layer_2(x))
        return self.layer_3(x)
# ----------------------------------------------------

class RLDrivenDeceptionManager:
    def __init__(self, policy_path, config_path):
        
        print("[Brain] RL 기반 기만 매니저 초기화 중...")
        
        self.config_path = os.path.abspath(config_path)
        
        self.state_reader = MTDStateReader(self.config_path)
        print(f"[Eyes] MTD 상태 리더 초기화. 규칙서 로드: {self.config_path}")
        self.controller = IPTablesMTDController(self.config_path)
        print(f"[Hands] MTD 컨트롤러 초기화. 규칙서 로드: {self.config_path}")
        
        # RL 정책 모델 로드
        self.policy = self.load_policy(policy_path, TESTBED_STATE_DIM, TESTBED_ACTION_DIM)
        if self.policy:
            print(f"[Brain] RL 정책 로드 완료: {policy_path}")
        else:
            print(f"[Brain] 치명적 오류: RL 정책 로드 실패. 종료합니다.")
            exit(1)
            
        # [수정] RLExportHook가 state_file_path=None을 처리하도록 수정되었음
        self.rl_export_hook = RLExportHook(
            state_file_path=None, # mtd_state.json을 쓰지 않음
            policy_file_path=POLICY_FILE
        )
        print("[Brain] RL 내보내기 후크 초기화 완료. (정책 파일만 관리)")

    def load_policy(self, policy_path, state_dim, action_dim):
        try:
            policy = PolicyNetwork(state_dim, action_dim)
            print(f"[Brain] PPO state_dict 로드 시도: {policy_path}")
            full_state_dict = torch.load(policy_path, map_location=torch.device('cpu'))
            print(f"[Brain] 전체 state_dict 로드 성공. 키: {list(full_state_dict.keys())[:5]}...")

            key_map = {
                'actor.0.weight': 'layer_1.weight', 'actor.0.bias': 'layer_1.bias',
                'actor.2.weight': 'layer_2.weight', 'actor.2.bias': 'layer_2.bias',
                'actor.4.weight': 'layer_3.weight', 'actor.4.bias': 'layer_3.bias',
            }
            
            actor_state_dict = {}
            missing_keys_in_file = []
            
            for ppo_key, policy_key in key_map.items():
                if ppo_key in full_state_dict:
                    actor_state_dict[policy_key] = full_state_dict[ppo_key]
                else:
                    missing_keys_in_file.append(ppo_key)

            if missing_keys_in_file:
                print(f"경고: PPO state_dict에서 다음의 예상 키를 찾을 수 없습니다: {missing_keys_in_file}")
                if len(actor_state_dict) == 0:
                     raise Exception("Actor 가중치를 하나도 찾을 수 없습니다. 키 매핑 실패.")

            print(f"[Brain] Actor 가중치 매핑 완료. PolicyNetwork에 로드 시도...")
            policy.load_state_dict(actor_state_dict)
            print(f"[Brain] Actor 가중치 로드 성공.")
            policy.eval()
            return policy
            
        except FileNotFoundError:
            print(f"오류: 정책 파일을 찾을 수 없습니다: {policy_path}")
            return None
        except Exception as e:
            print(f"정책 로드 중 치명적 오류 발생: {e}")
            return None


    def main(self, args):
        print("[Brain] MTD 컨트롤러(Hands) 초기화 완료.")
        
        if len(self.controller.action_map) != TESTBED_ACTION_DIM:
            print(f"경고: 컨트롤러의 행동 차원({len(self.controller.action_map)})이 "
                  f"예상되는 차원({TESTBED_ACTION_DIM})과 일치하지 않습니다.")
            if len(self.controller.action_map) == 0:
                print("     [!] mtd/configs/iptables_mtd.yaml 파일에 'mtd_rl_actions' 리스트가 올바르게 정의되었는지 확인하세요.")

        print("[Brain] RL 기반 기만 매니저 실행 중... (중지하려면 Ctrl+C)")
        
        try:
            while True:
                # 1. MTD 상태 읽기
                try:
                    state_vector = self.state_reader.get_rl_state()
                    if not isinstance(state_vector, np.ndarray):
                         print(f"오류: state_reader.get_rl_state()가 numpy 배열을 반환하지 않았습니다 (반환형: {type(state_vector)})")
                         state_vector = np.zeros(TESTBED_STATE_DIM)
                except Exception as e:
                    print(f"오류: state_reader.get_rl_state() 호출 중 예외 발생: {e}")
                    print("     mtd/mtd_state_reader.py를 확인하세요. 임시로 0벡터를 사용합니다.")
                    state_vector = np.zeros(TESTBED_STATE_DIM)
                
                # 2. RL 정책을 사용하여 MTD 결정
                if len(state_vector) != TESTBED_STATE_DIM:
                    print(f"경고: 상태 벡터 크기 불일치! "
                          f"StateReader 반환: {len(state_vector)}, "
                          f"모델 예상: {TESTBED_STATE_DIM}")
                    
                    if len(state_vector) > TESTBED_STATE_DIM:
                         print(f"상태 벡터를 {TESTBED_STATE_DIM} 크기로 자릅니다.")
                         state_vector = state_vector[:TESTBED_STATE_DIM]
                    elif len(state_vector) < TESTBED_STATE_DIM:
                         print(f"상태 벡터를 {TESTBED_STATE_DIM} 크기로 패딩합니다. (0으로)")
                         state_vector = np.pad(state_vector, (0, TESTBED_STATE_DIM - len(state_vector)), 'constant')

                action_id = self.get_action_from_policy(state_vector)
                
                # 3. MTD 전략 실행
                if self.controller.execute_mtd_action_by_id(action_id):
                    print(f"[Hands] MTD 행동 실행: {action_id}")
                    
                    # 4. RL 에이전트(Seeker)를 위한 *정책* 내보내기 (mtd_policy.json)
                    try:
                        # 컨트롤러에서 현재 적용된 룰(Redirection Target) 정보를 가져옴
                        current_mtd_target = self.controller.current_target_str
                        is_decoy = self.controller.current_target_is_decoy
                        public_entrypoint = f"{self.controller.public_ip}:{self.controller.public_port}"

                        policy_data_to_export = {
                            "mtd_policy_id": action_id,
                            "current_state_vector": state_vector.tolist(),
                            "mtd_config": {
                                "public_entrypoint": public_entrypoint,
                                "redirect_target": current_mtd_target,
                                "is_decoy": is_decoy
                            }
                        }
                        
                        # [최종 수정]
                        # RLExportHook가 (self, state_data, policy_data)를 받도록 수정되었으므로
                        # 올바른 키워드 인수로 호출합니다.
                        self.rl_export_hook.export_state_and_policy(
                            state_data=None, # mtd_state.json을 덮어쓰지 않음!
                            policy_data=policy_data_to_export
                        )
                    except Exception as e:
                        print(f"오류: 정책 내보내기 중 예기치 않은 오류 발생: {e}")

                else:
                    print(f"[Hands] MTD 행동 {action_id} 실행 실패. (컨트롤러가 Action ID를 찾지 못함. yaml 파일의 'mtd_rl_actions' 확인)")

                # 5. 다음 주기를 위해 대기
                time.sleep(args.interval)

        except KeyboardInterrupt:
            print("\n[Brain] 사용자에 의해 중지됨. 정리 중...")
            # self.controller.reset_to_default() # 컨트롤러에 reset 기능 필요
            print("[Hands] MTD 구성을 기본값으로 재설정 (수동).")
            print("[Brain] RL 기반 기만 매니저 종료.")

    def get_action_from_policy(self, state_vector):
        try:
            state_tensor = torch.tensor(state_vector, dtype=torch.float32).unsqueeze(0)
            with torch.no_grad():
                action_logits = self.policy(state_tensor)
                action_id = torch.argmax(action_logits).item()
            return action_id
        except Exception as e:
            print(f"정책에서 행동 결정 중 오류 발생: {e}")
            return 0 # 오류 발생 시 기본 행동

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RL 기반 MTD 기만 매니저")
    
    parser.add_argument("--policy", type=str, 
                        default=DEFAULT_POLICY_PATH,
                        help=f"로드할 RL 정책 파일 경로 (기본값: {DEFAULT_POLICY_PATH})")
    parser.add_argument("--config", type=str, 
                        default="mtd/configs/iptables_mtd.yaml",
                        help="MTD 컨트롤러 및 상태 리더를 위한 YAML 설정 파일 경로")
    parser.add_argument("--interval", type=int, default=30,
                        help="MTD 결정을 내리는 주기 (초)")
    args = parser.parse_args()

    manager = RLDrivenDeceptionManager(args.policy, args.config)
    manager.main(args)