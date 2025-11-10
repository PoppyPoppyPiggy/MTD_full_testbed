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
# 스크립트의 상위 디렉토리(dvd_attacks_lpc)를 sys.path에 추가하여
# 'mtd' 패키지를 찾을 수 있도록 합니다.
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(script_dir)
sys.path.insert(0, parent_dir)
# ---------------------

from mtd.controller.iptables_mtd_controller import IPTablesMTDController
from mtd.mtd_state_reader import MTDStateReader
from mtd.adapters.rl_export_hook import RLExportHook

# 에이전트의 상태 및 정책 공유 디렉터리
STATE_DIR = "mtd/shared_state"
STATE_FILE = os.path.join(STATE_DIR, "mtd_state.json")
POLICY_FILE = os.path.join(STATE_DIR, "mtd_policy.json") # RL 에이전트가 선택한 MTD 정책

# 강화학습(RL) 정책을 위한 설정
DEFAULT_POLICY_PATH = "mtd/shared_state/defender_policy_L4.pth"
TESTBED_ACTION_DIM = 7  # 테스트베드에서 예상하는 행동 차원 (모델 분석: 7)
TESTBED_STATE_DIM = 8   # 테스트베드에서 예상하는 상태 차원 (모델 분석: 8)

# --- MTD_RL/ver_01/utils.py 에서 가져온 정책 모델 구조 ---
# state_dict를 로드하려면 모델의 아키텍처를 먼저 정의해야 합니다.
# 이 구조는 PPO 모델의 'Actor' 네트워크와 일치해야 합니다.
class PolicyNetwork(nn.Module):
    def __init__(self, state_dim, action_dim):
        super(PolicyNetwork, self).__init__()
        # PPO의 Actor 네트워크 구조 (Linear -> ReLU/Tanh -> Linear -> ReLU/Tanh -> Linear)
        self.layer_1 = nn.Linear(state_dim, 64)
        self.layer_2 = nn.Linear(64, 64)
        self.layer_3 = nn.Linear(64, action_dim)

    def forward(self, state):
        x = F.relu(self.layer_1(state))
        x = F.relu(self.layer_2(x))
        # 정책 출력이므로 마지막 레이어는 활성화 함수(softmax 등)를 거치지 않은 logits 반환
        return self.layer_3(x)
# ----------------------------------------------------

class RLDrivenDeceptionManager:
    """
    강화학습(RL) 에이전트에 의해 구동되는 MTD 매니저입니다.
    RL 에이전트의 정책 출력을 읽고, MTD 컨트롤러를 사용하여 
    선택된 MTD 전략을 실행합니다.
    """
    def __init__(self, policy_path, config_path):
        print("[Brain] RL 기반 기만 매니저 초기화 중...")
        self.state_reader = MTDStateReader(config_path)
        print(f"[Eyes] MTD 상태 리더 초기화. 규칙서 로드: {config_path}")
        self.controller = IPTablesMTDController(config_path)
        print(f"[Hands] MTD 컨트롤러 초기화. 규칙서 로드: {config_path}")
        
        # RL 정책 모델 로드
        self.policy = self.load_policy(policy_path, TESTBED_STATE_DIM, TESTBED_ACTION_DIM)
        if self.policy:
            print(f"[Brain] RL 정책 로드 완료: {policy_path}")
        else:
            print(f"[Brain] 치명적 오류: RL 정책 로드 실패. 종료합니다.")
            exit(1)
            
        self.rl_export_hook = RLExportHook(STATE_FILE, POLICY_FILE)
        print("[Brain] RL 내보내기 후크 초기화 완료.")

    def load_policy(self, policy_path, state_dim, action_dim):
        """
        Torch .pth 파일(PPO Actor-Critic state_dict)에서 Actor 정책만 로드합니다.
        """
        try:
            # 1. 정책 모델의 빈 구조를 생성합니다. (Actor와 동일한 구조)
            policy = PolicyNetwork(state_dim, action_dim)
            
            # 2. PPO (Actor-Critic) state_dict를 CPU로 로드합니다.
            print(f"[Brain] PPO state_dict 로드 시도: {policy_path}")
            full_state_dict = torch.load(policy_path, map_location=torch.device('cpu'))
            print(f"[Brain] 전체 state_dict 로드 성공. 키: {list(full_state_dict.keys())[:5]}...") # 샘플 키 출력

            # 3. PPO의 'actor' 키를 'PolicyNetwork'의 키로 매핑합니다.
            key_map = {
                'actor.0.weight': 'layer_1.weight',
                'actor.0.bias': 'layer_1.bias',
                'actor.2.weight': 'layer_2.weight',
                'actor.2.bias': 'layer_2.bias',
                'actor.4.weight': 'layer_3.weight',
                'actor.4.bias': 'layer_3.bias',
            }
            
            # Actor 가중치만 추출하여 새 state_dict를 만듭니다.
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

            # 4. 빈 모델 구조에 *새로 매핑된* 가중치를 로드합니다.
            print(f"[Brain] Actor 가중치 매핑 완료. PolicyNetwork에 로드 시도...")
            policy.load_state_dict(actor_state_dict)
            print(f"[Brain] Actor 가중치 로드 성공.")
            
            # 5. 모델을 평가 모드로 설정합니다.
            policy.eval()
            return policy
            
        except FileNotFoundError:
            print(f"오류: 정책 파일을 찾을 수 없습니다: {policy_path}")
            return None
        except Exception as e:
            print(f"정책 로드 중 치명적 오류 발생: {e}")
            return None


    def main(self, args):
        """
        RLDrivenDeceptionManager의 메인 루프입니다.
        """
        print("[Brain] MTD 컨트롤러(Hands) 초기화 완료.")
        
        # 컨트롤러의 행동 차원이 테스트베드와 일치하는지 확인
        if len(self.controller.action_map) != TESTBED_ACTION_DIM:
            print(f"경고: 컨트롤러의 행동 차원({len(self.controller.action_map)})이 "
                  f"예상되는 차원({TESTBED_ACTION_DIM})과 일치하지 않습니다.")
            if len(self.controller.action_map) == 0:
                print("     [!] mtd/configs/iptables_mtd.yaml 파일에 'mtd_rl_actions' 리스트가 올바르게 정의되었는지 확인하세요.")

        print("[Brain] RL 기반 기만 매니저 실행 중... (중지하려면 Ctrl+C)")
        
        try:
            while True:
                # 1. MTD 상태 읽기
                # [오류 수정] get_full_state, get_rl_state_vector -> get_rl_state()
                # (mtd_state_reader.py가 8차원 벡터를 반환해야 함)
                try:
                    state_vector = self.state_reader.get_rl_state()
                    if not isinstance(state_vector, np.ndarray):
                         # mtd_state_reader가 벡터가 아닌 다른 것을 반환할 경우를 대비
                         print(f"오류: state_reader.get_rl_state()가 numpy 배열을 반환하지 않았습니다 (반환형: {type(state_vector)})")
                         state_vector = np.zeros(TESTBED_STATE_DIM) # 임시로 0벡터 사용
                except Exception as e:
                    print(f"오류: state_reader.get_rl_state() 호출 중 예외 발생: {e}")
                    print("     mtd/mtd_state_reader.py를 확인하세요. 임시로 0벡터를 사용합니다.")
                    state_vector = np.zeros(TESTBED_STATE_DIM)
                
                # 2. RL 정책을 사용하여 MTD 결정
                
                # get_rl_state가 TESTBED_STATE_DIM과 동일한 크기의 벡터를 반환하는지 확인
                if len(state_vector) != TESTBED_STATE_DIM:
                    print(f"경고: 상태 벡터 크기 불일치! "
                          f"StateReader 반환: {len(state_vector)}, "
                          f"모델 예상: {TESTBED_STATE_DIM}")
                    
                    # [경고] 이것은 임시방편이며, MTD가 잘못된 결정을 내리게 만듭니다.
                    # [경고] 근본적으로 mtd_state_reader.py가 8차원 벡터를 반환해야 합니다.
                    if len(state_vector) > TESTBED_STATE_DIM:
                         print(f"상태 벡터를 {TESTBED_STATE_DIM} 크기로 자릅니다.")
                         state_vector = state_vector[:TESTBED_STATE_DIM]
                    elif len(state_vector) < TESTBED_STATE_DIM:
                         print(f"상태 벡터를 {TESTBED_STATE_DIM} 크기로 패딩합니다. (0으로)")
                         state_vector = np.pad(state_vector, (0, TESTBED_STATE_DIM - len(state_vector)), 'constant')

                action_id = self.get_action_from_policy(state_vector)
                
                # 3. MTD 전략 실행
                # [오류 수정] 'execute_action' -> 'execute_mtd_action_by_id'
                if self.controller.execute_mtd_action_by_id(action_id):
                    print(f"[Hands] MTD 행동 실행: {action_id}")
                    
                    # 4. RL 에이전트를 위한 상태 및 정책 내보내기
                    # [수정] current_state_data 대신 state_vector를 저장
                    self.rl_export_hook.export_state_and_policy(
                        state_vector.tolist(), # JSON 저장을 위해 list로 변환
                        action_id
                    )
                else:
                    print(f"[Hands] MTD 행동 {action_id} 실행 실패. (컨트롤러가 Action ID를 찾지 못함. yaml 파일의 'mtd_rl_actions' 확인)")

                # 5. 다음 주기를 위해 대기
                time.sleep(args.interval)

        except KeyboardInterrupt:
            print("\n[Brain] 사용자에 의해 중지됨. 정리 중...")
            # self.controller.reset_to_default() # reset_to_default 함수가 컨트롤러에 있는지 확인 필요
            print("[Hands] MTD 구성을 기본값으로 재설정 (수동).")
            print("[Brain] RL 기반 기만 매니저 종료.")

    def get_action_from_policy(self, state_vector):
        """
        현재 상태 벡터를 기반으로 RL 정책에서 행동을 결정합니다.
        """
        try:
            # 상태 벡터를 텐서로 변환
            state_tensor = torch.tensor(state_vector, dtype=torch.float32).unsqueeze(0)
            
            with torch.no_grad():
                # 정책 모델을 통해 행동 확률(logits) 얻기
                action_logits = self.policy(state_tensor)
                
                # 가장 확률이 높은 행동 선택 (argmax)
                action_id = torch.argmax(action_logits).item()
                
            return action_id
        except Exception as e:
            print(f"정책에서 행동 결정 중 오류 발생: {e}")
            return 0 # 오류 발생 시 기본 행동 (Pass 또는 Real_1)

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

    # MTD 매니저 초기화 및 실행
    manager = RLDrivenDeceptionManager(args.policy, args.config)
    manager.main(args)