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
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(script_dir)
sys.path.insert(0, parent_dir)
# ---------------------

from mtd.controller.iptables_mtd_controller import IPTablesMTDController
from mtd.mtd_state_reader import MTDStateReader
from mtd.adapters.rl_export_hook import RLExportHook

# --- 상수 정의 ---
STATE_DIR = "mtd/shared_state"
POLICY_FILE = os.path.join(STATE_DIR, "mtd_policy.json") # RL 에이전트(Seeker)가 읽어갈 정책 파일
DEFAULT_POLICY_PATH = "mtd/shared_state/defender_policy_L4.pth"
DEFAULT_SCORING_CONFIG_PATH = "mtd/configs/mtd_scoring.yaml" # [MODIFIED] 스코어링 설정 경로

# CTI 및 Health 파일 경로 (Scoring 로직용)
CTI_ASSESSMENT_FILE = os.path.join(STATE_DIR, 'cti_threat_assessment.json')
SYSTEM_HEALTH_FILE = os.path.join(STATE_DIR, 'dvd_system_health.json') 
ACTION_STATE_FILE = os.path.join(STATE_DIR, 'mtd_action_state.json') # 컨트롤러가 이 파일을 씀

TESTBED_ACTION_DIM = 7
TESTBED_STATE_DIM = 8
# ---------------------

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

class RLDrivenDeceptionManager:
    def __init__(self, policy_path, config_path, scoring_config_path, wandb_project):
        
        print("[Brain] RL 기반 기만 매니저 초기화 중...")
        
        self.config_path = os.path.abspath(config_path)
        self.scoring_config_path = os.path.abspath(scoring_config_path)
        
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
            sys.exit(1)
            
        self.rl_export_hook = RLExportHook(
            state_file_path=None, # mtd_state.json을 쓰지 않음
            policy_file_path=POLICY_FILE
        )
        print("[Brain] RL 내보내기 후크 초기화 완료. (정책 파일만 관리)")

        # --- [MODIFIED] mtd_scoring.py 로직 병합 ---
        print(f"[Brain] 스코어링 로직 초기화 중... (Config: {self.scoring_config_path})")
        self.scoring_config = self.load_yaml(self.scoring_config_path)
        
        # 스코어링 가중치 로드
        weights_config = self.scoring_config.get('weights', {})
        self.w_s_d = weights_config.get('w_deception_success', 0.5)
        self.w_r_a = weights_config.get('w_attack_resilience', 0.3)
        self.w_c_m = weights_config.get('w_mtd_cost', 0.2)
        
        cost_weights_config = self.scoring_config.get('cost_metric_weights', {})
        self.w_cost_latency = cost_weights_config.get('w_latency', 0.7)
        self.w_cost_packet_loss = cost_weights_config.get('w_packet_loss', 0.3)
        
        # QoS 기준점 로드
        baseline_qos_config = self.scoring_config.get('baseline_qos', {})
        self.baseline_latency = baseline_qos_config.get('latency_ms', 50.0)
        self.baseline_packet_loss = baseline_qos_config.get('packet_loss_percent', 0.1)
        
        # 스코어링 상태 변수 초기화
        self.start_time = time.time() # [고도화] X축(시간) 기준점
        self.total_attack_time = 0.0
        self.total_decoy_time = 0.0
        self.total_reconfigurations = 0
        self.total_successful_attacks = 0
        self.last_mtd_action_id_for_scoring = -1 # mtd_scoring.py의 'last_mtd_action_id'
        self.attack_start_times = {} # { "gps_spoof": 16788... }
        self.decoy_active_start_time = None
        self.processed_breach_timestamps = set() # N_A 중복 계산 방지
        # ---------------------------------------------

        # [W&B] W&B 초기화
        self.wandb_run = self.init_wandb(policy_path, wandb_project)
        self.policy_level_name = "Unknown_Level" # W&B 그룹명을 저장하기 위함
        if self.wandb_run:
            self.policy_level_name = self.wandb_run.group # 예: "vs_L0_Seeker"

    def load_yaml(self, config_path):
        """Loads a YAML config file."""
        try:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            print(f"Error: YAML 설정 파일({config_path})을 찾을 수 없습니다!", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"Error: YAML 설정 파일 로드 실패: {e}", file=sys.stderr)
            sys.exit(1)

    def init_wandb(self, policy_path, project):
        """Initialize Weights & Biases run."""
        try:
            # [고도화] W&B 그룹을 정책의 상위 폴더 이름(예: L0_Seeker)으로 자동 설정
            level_name = os.path.basename(os.path.dirname(policy_path))
            if not level_name or level_name == ".":
                level_name = "Unknown_Level"
            
            wandb_group = f"vs_{level_name}"
            # [MODIFIED] MTD_Manager와 MTD_Scorer 역할을 통합
            run_name = "MTD_Manager_with_Scoring"
            
            wandb_run = wandb.init(
                project=project,
                group=wandb_group,
                job_type="mtd_manager_scorer", # 통합 역할
                name=run_name,
                config={
                    "policy_path": policy_path,
                    "mtd_config": self.config_path,
                    "scoring_config": self.scoring_config_path,
                    "scoring_weights": self.scoring_config.get('weights', {})
                }
            )
            print(f"[Brain] W&B 연동 성공. (Project: {project}, Group: {wandb_group}, Run: {run_name})")
            
            # [W&B] 공통 X축 정의 (train_mtd_only.py와 일치시킴)
            wandb_run.define_metric("General/global_step", summary="max")
            
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

    # --- [MODIFIED] mtd_scoring.py의 헬퍼 함수들 병합 ---
    
    def load_json_state(self, file_path):
        """Safely loads a JSON state file."""
        try:
            if os.path.exists(file_path):
                file_age = time.time() - os.path.getmtime(file_path)
                if file_age > 30: # 30초 이상된 파일은 무시
                    return None
                
                with open(file_path, 'r') as f:
                    return json.load(f)
        except json.JSONDecodeError:
            print(f"Warning: JSON 파일 파싱 오류: {file_path}", file=sys.stderr)
        except Exception as e:
            print(f"Warning: JSON 파일 읽기 오류 ({file_path}): {e}", file=sys.stderr)
        return None

    def calculate_deception_success(self, cti_data, action_data, current_time, interval):
        """S_D = T_D / T_A (기만 성공률)"""
        is_attack_detected = False
        if cti_data and cti_data.get('alert_detected', False):
            is_attack_detected = True
            active_attacks = cti_data.get('active_attack_types', [])
            for attack in active_attacks:
                if attack not in self.attack_start_times:
                    self.attack_start_times[attack] = current_time

        # T_A (Total Attack Time) 계산
        self.total_attack_time = 0.0
        for attack, start_time in self.attack_start_times.items():
            self.total_attack_time += (current_time - start_time)

        # T_D (Time on Decoy) 누적
        is_decoy_active = False
        if action_data:
            is_decoy_active = action_data.get('current_action', {}).get('is_decoy', False)

        if is_attack_detected and is_decoy_active:
            if self.decoy_active_start_time is None:
                self.decoy_active_start_time = current_time
            # [MODIFIED] 루프 주기(interval)만큼 디코이 시간 누적
            self.total_decoy_time += interval 
        else:
            self.decoy_active_start_time = None

        if self.total_attack_time == 0:
            return 0.0
        s_d = self.total_decoy_time / self.total_attack_time
        return min(s_d, 1.0)

    def calculate_attack_resilience(self, cti_data, action_data):
        """R_A = N_R / N_A (공격 탄력성)"""
        # N_R (Number of Reconfigurations) 누적
        if action_data:
            current_action_id = action_data.get('current_action', {}).get('action_id', -1)
            if current_action_id != self.last_mtd_action_id_for_scoring:
                if self.last_mtd_action_id_for_scoring != -1:
                    self.total_reconfigurations += 1
                self.last_mtd_action_id_for_scoring = current_action_id

        # N_A (Number of Successful Attacks) 누적
        if cti_data and cti_data.get('attack_stage_assessment', '') == 'Breach' and action_data:
            is_decoy = action_data.get('current_action', {}).get('is_decoy', False)
            breach_timestamp = cti_data.get('last_analysis_timestamp')
            if not is_decoy:
                if breach_timestamp not in self.processed_breach_timestamps:
                    self.total_successful_attacks += 1
                    self.processed_breach_timestamps.add(breach_timestamp)
                    print(f"[Scoring] ❗ 신규 침해(Breach) 감지! (N_A: {self.total_successful_attacks})")

        n_r = self.total_reconfigurations
        n_a = self.total_successful_attacks
        if n_a == 0:
            return min(n_r, 10.0)
        return n_r / n_a

    def calculate_mtd_cost(self, health_data, metric_type='all'):
        """C_M = w_lat * Cost(lat) + w_loss * Cost(loss) (MTD 비용)"""
        if not health_data:
            return 0.0
        
        p_n_latency = health_data.get('qos_metrics', {}).get('latency_ms', self.baseline_latency)
        p_o_latency = self.baseline_latency
        cost_latency = 0.0
        if p_o_latency > 0:
            cost_latency = (p_n_latency - p_o_latency) / p_o_latency
        cost_latency = max(0, cost_latency)
        if metric_type == 'latency':
            return cost_latency

        p_n_loss = health_data.get('qos_metrics', {}).get('packet_loss_percent', self.baseline_packet_loss)
        p_o_loss = self.baseline_packet_loss
        cost_packet_loss = 0.0
        if p_o_loss > 0:
            cost_packet_loss = (p_n_loss - p_o_loss) / p_o_loss
        cost_packet_loss = max(0, cost_packet_loss)
        if metric_type == 'packet_loss':
            return cost_packet_loss

        c_m = (self.w_cost_latency * cost_latency) + (self.w_cost_packet_loss * cost_packet_loss)
        return c_m
    # --- [MODIFIED] 헬퍼 함수 병합 완료 ---


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
                current_time = time.time()
                current_step_time = int(current_time - self.start_time)
                
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
                
                # --- [MODIFIED] 5. 스코어링 및 W&B 로깅 (통합) ---
                if self.wandb_run:
                    # 5a. 스코어링에 필요한 데이터 로드
                    cti_data = self.load_json_state(CTI_ASSESSMENT_FILE)
                    health_data = self.load_json_state(SYSTEM_HEALTH_FILE)
                    # action_data는 컨트롤러가 방금 쓴 mtd_action_state.json을 읽어옴
                    action_data = self.load_json_state(ACTION_STATE_FILE) 

                    # 5b. 스코어 계산
                    s_d = self.calculate_deception_success(cti_data, action_data, current_time, args.interval)
                    r_a = self.calculate_attack_resilience(cti_data, action_data)
                    c_m = self.calculate_mtd_cost(health_data, 'all')
                    cost_latency = self.calculate_mtd_cost(health_data, 'latency')
                    cost_packet_loss = self.calculate_mtd_cost(health_data, 'packet_loss')
                    s_mtd = (self.w_s_d * s_d) + (self.w_r_a * r_a) - (self.w_c_m * c_m)
                    
                    # 5c. 통합 로그 생성
                    logs = {
                        # X축 (train_mtd_only.py와 일치)
                        "General/global_step": current_step_time,
                        
                        # Manager 로그 (General 그룹으로 이동)
                        "General/Manager/Action_ID": action_id,
                        "General/Manager/Action_Name": self.controller.current_action_name,
                        "General/CTI_Threat_Level": cti_data.get('current_threat_level', 'NONE') if cti_data else 'UNKNOWN',
                        "General/CTI_Active_Attacks": ", ".join(cti_data.get('active_attack_types', [])) if cti_data else "NONE",
                        
                        # Scoring Metrics (train_mtd_only.py와 키 이름 일치)
                        "Metric/MTD_Score_Overall": s_mtd,
                        "Metric/Metric_Deception_Success (S_D)": s_d,
                        "Metric/Metric_Attack_Resilience (R_A)": r_a,
                        "Metric/Metric_MTD_Cost (C_M)": c_m,
                        "Metric/Detail_Total_Attack_Steps (T_A)": self.total_attack_time,
                        "Metric/Detail_Total_Decoy_Steps (T_D)": self.total_decoy_time,
                        "Metric/Detail_Reconfigurations (N_R)": self.total_reconfigurations,
                        "Metric/Detail_Successful_Attacks (N_A)": self.total_successful_attacks,
                        "Metric/QoS_Latency_Cost": cost_latency,
                        "Metric/QoS_Packet_Loss_Cost": cost_packet_loss,
                    }
                    
                    # 8D 상태 벡터 로깅 (General 그룹으로 이동)
                    for i in range(TESTBED_STATE_DIM):
                        state_name = f"General/Manager/State/State_{i}"
                        if i == 6: state_name = "General/Manager/State/State_6_(Decoy_Flag)"
                        if i == 7: state_name = "General/Manager/State/State_7_(Alert_Flag)"
                        logs[state_name] = state_vector[i]
                        
                    # 7D 행동 Logits 로깅 (General 그룹으로 이동)
                    for i in range(TESTBED_ACTION_DIM):
                        logs[f"General/Manager/Logits/Logit_{i}"] = action_logits[i]

                    self.wandb_run.log(logs)
                    print(f"[Brain] (t_wandb) W&B [Step: {current_step_time}s, Action: {action_id}, S_MTD: {s_mtd:.2f}] 로깅 완료.")
                # --- [MODIFIED] 로깅 종료 ---

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
    parser = argparse.ArgumentParser(description="RL 기반 MTD 기만 매니저 (W&B 통합 로깅)")
    
    parser.add_argument("--policy", type=str,
                        default=DEFAULT_POLICY_PATH,
                        help=f"로드할 RL 정책 파일 경로 (기본값: {DEFAULT_POLICY_PATH})")
    parser.add_argument("--config", type=str,
                        default="mtd/configs/iptables_mtd.yaml",
                        help="MTD 컨트롤러 및 상태 리더를 위한 YAML 설정 파일 경로")
    # [MODIFIED] 스코어링 설정 인자 추가
    parser.add_argument("--scoring_config", type=str,
                        default=DEFAULT_SCORING_CONFIG_PATH,
                        help=f"MTD 스코어링 로직을 위한 YAML 설정 파일 경로 (기본값: {DEFAULT_SCORING_CONFIG_PATH})")
    parser.add_argument("--interval", type=int, default=5, # [MODIFIED] 기본 주기를 5초로 변경
                        help="MTD 결정을 내리는 주기 (초) (스코어링 주기와 일치 권장)")
    
    # [W&B] W&B 인자 추가
    parser.add_argument("--wandb_project", type=str,
                        default="mtd_testbed_live",
                        help="W&B 프로젝트 이름")

    args = parser.parse_args()
    
    # [MODIFIED] scoring_config 인자 전달
    manager = RLDrivenDeceptionManager(
        args.policy,
        args.config,
        args.scoring_config, 
        args.wandb_project
    )
    manager.main(args)