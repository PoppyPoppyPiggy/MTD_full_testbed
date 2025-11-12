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
import wandb  # [W&B] Weights & Biases 임포트

# --- Python 경로 수정 ---
# ... (기존 코드와 동일) ...
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(script_dir)
sys.path.insert(0, parent_dir)
# ---------------------

from mtd.controller.iptables_mtd_controller import IPTablesMTDController
from mtd.mtd_state_reader import MTDStateReader 
from mtd.adapters.rl_export_hook import RLExportHook

# ... (기존 코드와 동일) ...
STATE_DIR = "mtd/shared_state"
POLICY_FILE = os.path.join(STATE_DIR, "mtd_policy.json") # RL 에이전트(Seeker)가 읽어갈 정책 파일
DEFAULT_POLICY_PATH = "mtd/shared_state/defender_policy_L4.pth"
TESTBED_ACTION_DIM = 7
TESTBED_STATE_DIM = 8

# ... (PolicyNetwork 클래스 기존 코드와 동일) ...
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
    def __init__(self, policy_path, config_path, wandb_project):
        
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
            
        self.rl_export_hook = RLExportHook(
            state_file_path=None, # mtd_state.json을 쓰지 않음
            policy_file_path=POLICY_FILE
        )
        print("[Brain] RL 내보내기 후크 초기화 완료. (정책 파일만 관리)")

        # [W&B] W&B 초기화
        self.start_time = time.time() # [고도화] X축(시간) 기준점
        self.wandb_run = self.init_wandb(policy_path, wandb_project)
        self.policy_level_name = "Unknown_Level" # W&B 그룹명을 저장하기 위함
        if self.wandb_run:
            self.policy_level_name = self.wandb_run.group # 예: "vs_L0_Seeker"

    def init_wandb(self, policy_path, project):
        """Initialize Weights & Biases run."""
        try:
            # [고도화] W&B 그룹을 정책의 상위 폴더 이름(예: L0_Seeker)으로 자동 설정
            level_name = os.path.basename(os.path.dirname(policy_path))
            if not level_name or level_name == ".":
                level_name = "Unknown_Level"
            
            wandb_group = f"vs_{level_name}"
            run_name = "MTD_Manager" # 그룹 내에서 이 스크립트의 역할
            
            wandb_run = wandb.init(
                project=project,
                group=wandb_group,
                job_type="mtd_manager",
                name=run_name,
                config={
                    "policy_path": policy_path,
                    "mtd_config": self.config_path,
                }
            )
            print(f"[Brain] W&B 연동 성공. (Project: {project}, Group: {wandb_group}, Run: {run_name})")
            
            # [W&B] 공통 X축 정의
            wandb_run.define_metric("global_step_time", summary="max")
            
            return wandb_run
        except Exception as e:
            print(f"[Brain] W&B 연동 실패: {e}", file=sys.stderr)
            print("          'wandb login'을 실행했는지 확인하세요.", file=sys.stderr)
            return None

    def load_policy(self, policy_path, state_dim, action_dim):
        # ... (기존 코드와 동일) ...
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

        print(f"[Brain] RL 기반 기만 매니저 실행 중... (W&B Group: {self.policy_level_name})")
        
        try:
            while True:
                print("-" * 30) # 주기 구분을 위한 라인
                
                # [고도화] X축 (글로벌 스텝)을 경과 시간(초)으로 설정
                current_step_time = int(time.time() - self.start_time)
                
                # 1. MTD 상태 읽기
                try:
                    state_vector = self.state_reader.get_rl_state()
                    if not isinstance(state_vector, np.ndarray):
                         print(f"오류: state_reader.get_rl_state()가 numpy 배열을 반환하지 않았습니다 (반환형: {type(state_vector)})")
                         state_vector = np.zeros(TESTBED_STATE_DIM)
                except Exception as e:
                    print(f"오류: state_reader.get_rl_state() 호출 중 예외 발생: {e}")
                    state_vector = np.zeros(TESTBED_STATE_DIM)
                
                print(f"[Brain] (t_state) 현재 MTD 상태 벡터: {state_vector.tolist()}")

                # 2. RL 정책을 사용하여 MTD 결정
                if len(state_vector) != TESTBED_STATE_DIM:
                    print(f"경고: 상태 벡터 크기 불일치! (모델 예상: {TESTBED_STATE_DIM})")
                    state_vector = np.resize(state_vector, TESTBED_STATE_DIM)

                action_id, action_logits = self.get_action_from_policy(state_vector)
                
                print(f"[Brain] (t_act) 정책이 선택한 Action ID: {action_id}")
                print(f"[Brain] (t_act_detail) Action Logits: {action_logits.tolist()}")

                
                # 3. MTD 전략 실행
                if self.controller.execute_mtd_action_by_id(action_id):
                    action_name = self.controller.current_action_name
                    target = self.controller.current_target_str
                    print(f"[Brain] ✅ MTD 행동 실행 성공: ID={action_id}, 이름={action_name}, 타겟={target}")
                    
                    # 4. 정책 내보내기 (Seeker용)
                    try:
                        policy_data_to_export = {
                            "mtd_policy_id": action_id,
                            "current_state_vector": state_vector.tolist(),
                            "action_logits": action_logits.tolist(),
                            "mtd_config": {
                                "public_entrypoint": f"{self.controller.public_ip}:{self.controller.public_port}",
                                "redirect_target": self.controller.current_target_str,
                                "is_decoy": self.controller.current_target_is_decoy
                            }
                        }
                        self.rl_export_hook.export_state_and_policy(
                            state_data=None,
                            policy_data=policy_data_to_export
                        )
                        print(f"[Brain] (t_export) 정책 파일 '{POLICY_FILE}' 내보내기 완료.")
                    except Exception as e:
                        print(f"오류: 정책 내보내기 중 예기치 않은 오류 발생: {e}")

                else:
                    print(f"[Brain] ❗ MTD 행동 {action_id} 실행 실패. [Hands]의 로그(stderr)를 확인하세요.")
                
                # 5. [W&B] W&B에 현재 스텝 로깅
                if self.wandb_run:
                    logs = {
                        "global_step_time": current_step_time, # X축 (경과 시간)
                        "Manager/Action_ID": action_id, # Y축 (0-6)
                        "Manager/Action_Name": self.controller.current_action_name,
                    }
                    
                    # [W&B 업그레이드] 8D 상태 벡터 로깅
                    for i in range(TESTBED_STATE_DIM):
                        state_name = f"Manager/State/State_{i}"
                        if i == 6: state_name = "Manager/State/State_6_(Decoy_Flag)"
                        if i == 7: state_name = "Manager/State/State_7_(Alert_Flag)"
                        logs[state_name] = state_vector[i]
                        
                    # [W&B 업그레이드] 7D 행동 Logits 로깅
                    for i in range(TESTBED_ACTION_DIM):
                        logs[f"Manager/Logits/Logit_{i}"] = action_logits[i]

                    self.wandb_run.log(logs)
                    print(f"[Brain] (t_wandb) W&B [Step: {current_step_time}s, Action: {action_id}] 로깅 완료.")


                # 6. 다음 주기를 위해 대기
                print(f"[Brain] (t_sleep) 다음 주기까지 {args.interval}초 대기...")
                time.sleep(args.interval)

        except KeyboardInterrupt:
            print("\n[Brain] 사용자에 의해 중지됨. 정리 중...")
            self.controller.reset_to_default() 
            print("[Brain] RL 기반 기만 매니저 종료.")
        finally:
            # [W&B] W&B 실행 종료
            if self.wandb_run:
                self.wandb_run.finish()
                print("[Brain] W&B run 종료.")


    def get_action_from_policy(self, state_vector):
        # ... (기존 코드와 동일) ...
        try:
            state_tensor = torch.tensor(state_vector, dtype=torch.float32).unsqueeze(0)
            with torch.no_grad():
                action_logits = self.policy(state_tensor)
                action_id = torch.argmax(action_logits).item()
            return action_id, action_logits.squeeze(0)
        except Exception as e:
            print(f"정책에서 행동 결정 중 오류 발생: {e}")
            return 0, torch.zeros(TESTBED_ACTION_DIM) # 오류 발생 시 기본 행동

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RL 기반 MTD 기만 매니저 (W&B 연동)")
    
    parser.add_argument("--policy", type=str, 
                        default=DEFAULT_POLICY_PATH,
                        help=f"로드할 RL 정책 파일 경로 (기본값: {DEFAULT_POLICY_PATH})")
    parser.add_argument("--config", type=str, 
                        default="mtd/configs/iptables_mtd.yaml",
                        help="MTD 컨트롤러 및 상태 리더를 위한 YAML 설정 파일 경로")
    parser.add_argument("--interval", type=int, default=30,
                        help="MTD 결정을 내리는 주기 (초)")
    
    # [W&B] W&B 인자 추가
    parser.add_argument("--wandb_project", type=str,
                        default="mtd_testbed_live",
                        help="W&B 프로젝트 이름")

    args = parser.parse_args()

    manager = RLDrivenDeceptionManager(
        args.policy, 
        args.config,
        args.wandb_project
    )
    manager.main(args)