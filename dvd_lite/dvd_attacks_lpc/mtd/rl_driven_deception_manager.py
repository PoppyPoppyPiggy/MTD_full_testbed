#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 파일명: dvd_lite/mtd/rl_driven_deception_manager.py
# 설명: train.py에서 학습된 RL 모델을 사용하여 MTD를 지능적으로 제어 (CTI 로그 분석 & 실시간 성능 Scoring 기능 추가 v1.2)

import os
import docker
import subprocess
import time
import json
import random
import signal
import sys
import argparse
import math # D_bits 계산 위해 추가
from collections import deque, Counter # Scorer 위해 추가
from typing import Deque, Dict, Any, Optional, Tuple, List # List 추가

import numpy as np
import torch
import torch.nn as nn
from torch.distributions import Categorical
import yaml # Scoring 설정 위해 추가

# --- 기본 MTD 제어기와 설정 공유 ---
try:
    # deception_manager가 같은 디렉토리에 있다고 가정
    from deception_manager import MTDController, LPC_DIR, SHARED_STATE_DIR, STATE_FILE, \
                                    TARGET_CONTAINER_NAME, DECOY_CONTAINER_NAME, NETWORK_NAME, AVAILABLE_PORTS
except ImportError as e:
    print(f"ERROR: deception_manager.py 임포트 실패: {e}", file=sys.stderr)
    print("      이 스크립트는 deception_manager.py와 같은 디렉토리에 있어야 합니다.", file=sys.stderr)
    sys.exit(1)

# --- 경로 및 로거 설정 ---
# LPC_DIR은 deception_manager에서 가져옴
sys.path.insert(0, LPC_DIR)
BUS_DIR = os.path.join(LPC_DIR, 'bus') # CTI 로그 파일이 저장되는 경로
CONFIG_DIR = os.path.join(LPC_DIR, 'mtd', 'configs') # 설정 파일 경로
try:
    from bus.logger import log_bus_event
except ImportError:
    print("WARNING: bus.logger를 임포트할 수 없습니다. 이벤트는 stdout으로 출력됩니다.", file=sys.stderr)
    def log_bus_event(type: str, data: dict, source_override: str = "rl_deception_manager"):
        record = {"ts": time.time(), "source": source_override, "type": type, "data": data}
        print(json.dumps(record))

# --- RL 모델 관련 설정 ---
MODEL_PATH = os.path.join(LPC_DIR, 'rl', 'models', 'defender_policy.pth') # 학습된 모델 경로
DECISION_INTERVAL_SECONDS = 10 # RL 에이전트가 다음 행동을 결정하는 주기

# --- Scoring 관련 설정 ---
SCORING_INTERVAL_SECONDS = 60 # 성능 점수 계산 주기
SCORING_WINDOW_SECONDS = 300 # 점수 계산 시 고려할 최근 로그 시간 범위 (5분)
SCORING_CONFIG_PATH = os.path.join(CONFIG_DIR, 'mtd_scoring.yaml') # 점수 가중치 설정 파일

# ======================================================================================
# train.py의 ActorCritic 모델 클래스 (기존과 동일)
# ======================================================================================
# === rl_driven_deception_manager.py 수정 필요한 부분 ===
class ActorCritic(nn.Module):
    def __init__(self, state_dim: int, action_dim: int):
        super().__init__()
        # ⭐️ 레이어 이름을 train.py v15.2 와 동일하게 'shared'로 수정
        self.shared = nn.Sequential(nn.Linear(state_dim,128), nn.Tanh(), nn.Linear(128,128), nn.Tanh())
        self.actor = nn.Linear(128, action_dim)
        self.critic = nn.Linear(128, 1)

    def forward(self, s):
        x = self.shared(s) # ⭐️ shared_layer -> shared
        return Categorical(logits=self.actor(x)), self.critic(x).squeeze(-1)

    def act(self, s):
        dist, v = self.forward(s)
        a = dist.sample()
        return a, dist.log_prob(a), v
# ==================================================

# ======================================================================================
# TestbedScorer 클래스 (신규 추가)
# ======================================================================================
class TestbedScorer:
    """테스트베드 환경 로그를 분석하여 MTD 성능 점수를 계산합니다."""
    def __init__(self, config_path: str = SCORING_CONFIG_PATH):
        self.weights = self._load_scoring_weights(config_path)
        self.last_log_ts: Dict[str, float] = {} # 로그 타입별 마지막 처리 타임스탬프
        self.recent_mtd_actions: Deque[Dict] = deque(maxlen=100) # 최근 MTD 액션 기록 (비용 계산용)
        self.recent_endpoints: Deque[str] = deque(maxlen=100) # 최근 활성 엔드포인트 기록 (D_bits 계산용)
        self.log_file_paths = { # 분석 대상 로그 파일 경로
            "attack": os.path.join(BUS_DIR, 'bus_system.log'), # attack_started, attack_finished
            "mtd": os.path.join(BUS_DIR, 'bus.log'), # mtd_switch, mtd_decision 등
        }

    def _load_scoring_weights(self, path: str) -> Dict[str, float]:
        """점수 계산 가중치를 YAML 파일에서 로드합니다."""
        default_weights = {
            "r_succ_weight": 5.0, # 방어 성공률 가중치
            "c_def_weight": -1.0, # 방어 비용 가중치 (음수 = 페널티)
            "d_bits_weight": 0.5, # 다양성 가중치
        }
        try:
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    config_weights = yaml.safe_load(f)
                    # 설정 파일에 정의된 값만 업데이트
                    for key in default_weights:
                        if key in config_weights:
                            default_weights[key] = float(config_weights[key])
                print(f"✅ Scoring 가중치 로드 완료: {path}")
            else:
                print(f"[정보] Scoring 설정 파일({path}) 없음. 기본 가중치 사용.")
                # 기본 가중치 파일 생성 (선택 사항)
                # with open(path, 'w', encoding='utf-8') as f:
                #     yaml.dump(default_weights, f, default_flow_style=False)
        except Exception as e:
            print(f"❌ Scoring 가중치 로드 실패: {e}. 기본 가중치 사용.", file=sys.stderr)
        return default_weights

    def _read_logs_since(self, log_type: str, since_ts: float) -> Tuple[List[Dict], float]:
        """특정 시간 이후의 로그만 읽어옵니다."""
        log_path = self.log_file_paths.get(log_type)
        if not log_path or not os.path.exists(log_path):
            return [], since_ts

        new_logs = []
        max_ts = since_ts
        try:
            with open(log_path, 'r', encoding='utf-8') as f:
                # 파일 끝에서부터 효율적으로 읽는 방법은 복잡하므로, 일단 전체 읽기로 구현
                lines = f.readlines()
                for line in reversed(lines):
                    try:
                        log_entry = json.loads(line)
                        ts = log_entry.get("ts", 0)
                        if ts > since_ts:
                            new_logs.append(log_entry)
                            max_ts = max(max_ts, ts)
                        elif ts <= since_ts:
                            break # 이미 처리한 로그 도달
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            print(f"[경고] 로그 파일 읽기 오류 ({log_path}): {e}", file=sys.stderr)
        return list(reversed(new_logs)), max_ts # 시간 순 정렬

    def record_mtd_action(self, action_info: Dict):
        """MTD 컨트롤러가 수행한 액션을 기록합니다 (비용 계산용)."""
        action_info['ts'] = time.time() # 실행 시점 기록
        self.recent_mtd_actions.append(action_info)
        # 활성 엔드포인트 변경 기록 (D_bits 계산용)
        if action_info.get("type") == "mtd_switch":
            self.recent_endpoints.append(action_info.get("data", {}).get("to"))

    def calculate_score(self) -> Optional[Dict[str, Any]]:
        """최근 로그를 분석하여 성능 지표 및 종합 점수를 계산합니다."""
        now = time.time()
        start_time = now - SCORING_WINDOW_SECONDS

        # --- 1. 데이터 수집 ---
        attack_logs, self.last_log_ts['attack'] = self._read_logs_since('attack', self.last_log_ts.get('attack', start_time))
        mtd_logs, self.last_log_ts['mtd'] = self._read_logs_since('mtd', self.last_log_ts.get('mtd', start_time))

        # --- 2. 지표 계산 ---
        # 2.1 R_succ (Estimated)
        attacks_started = 0
        attacks_succeeded = 0 # 침해 성공 횟수 (예: return_code 0)
        for log in attack_logs:
            if log.get("ts", 0) < start_time: continue
            if log.get("type") == "attack_started":
                attacks_started += 1
            # 'attack_finished' 로그에서 성공 여부 판단 (return_code == 0 이 성공이라고 가정)
            elif log.get("type") == "attack_finished":
                 # 실제 attack_finished 로그 형식에 맞춰 수정 필요
                if log.get("data", {}).get("return_code") == 0:
                    attacks_succeeded += 1

        r_succ_estimated = 1.0 - (attacks_succeeded / attacks_started) if attacks_started > 0 else 1.0

        # 2.2 C_def (Actual Cost)
        total_cost = 0.0
        actions_in_window = 0
        # train.py의 비용 계수 사용
        cost_map = {
            "mtd_switch": config.COST_SHUFFLE, # 셔플 비용
            # 디코이 활성화 액션 로그 타입 정의 필요 (예: 'mtd_decoy_activated')
            "mtd_decoy_activated": config.COST_DECOY_RATIO * DECISION_INTERVAL_SECONDS, # 활성화된 시간만큼 비율 비용
            # 블랙리스트 레벨 변경 액션 로그 타입 정의 필요 (예: 'mtd_bl_changed')
            "mtd_bl_changed": config.COST_BL_LEVEL * DECISION_INTERVAL_SECONDS, # 레벨 유지 비용
            # 모든 결정 주기마다 기본 액션 비용 추가
            "rl_mtd_decision": config.COST_MTD_ACTION
        }
        for action in list(self.recent_mtd_actions): # deque 순회 중 변경 방지
            if action.get("ts", 0) >= start_time:
                actions_in_window += 1
                action_type = action.get("type")
                cost = cost_map.get(action_type, 0.0) # 기본 비용은 0

                # 비율 기반 비용 계산 (decoy, bl) - 실제 구현 시 더 정교화 필요
                if action_type == "rl_mtd_decision":
                     params = action.get("data", {}).get("new_params", {})
                     cost += params.get("decoy_ratio", 0) * config.COST_DECOY_RATIO
                     cost += params.get("bl_level", 0) * config.COST_BL_LEVEL

                total_cost += cost
            elif action.get("ts", 0) < start_time:
                 # 오래된 기록은 제거 (메모리 관리) - deque가 자동으로 처리
                 pass

        # 스텝(결정 주기)당 평균 비용으로 변환
        avg_steps_in_window = SCORING_WINDOW_SECONDS / DECISION_INTERVAL_SECONDS if DECISION_INTERVAL_SECONDS else 0
        c_def_actual = total_cost / avg_steps_in_window if avg_steps_in_window > 0 else 0.0

        # 2.3 D_bits (Estimated)
        endpoints_in_window = [ep for ep in list(self.recent_endpoints) if ep] # None 제거
        if len(endpoints_in_window) > 1:
            counts = Counter(endpoints_in_window)
            total = len(endpoints_in_window)
            probs = [count / total for count in counts.values()]
            d_bits_estimated = -sum(p * math.log2(p) for p in probs if p > 0)
        else:
            d_bits_estimated = 0.0

        # --- 3. 종합 점수 계산 ---
        score = (self.weights['r_succ_weight'] * r_succ_estimated +
                 self.weights['c_def_weight'] * c_def_actual +      # 비용은 페널티
                 self.weights['d_bits_weight'] * d_bits_estimated)

        calculated_metrics = {
            "score": score,
            "r_succ_estimated": r_succ_estimated,
            "c_def_actual": c_def_actual,
            "d_bits_estimated": d_bits_estimated,
            "attacks_in_window": attacks_started,
            "breaches_in_window": attacks_succeeded,
            "analysis_window_sec": SCORING_WINDOW_SECONDS,
            "weights": self.weights
        }
        return calculated_metrics

# ======================================================================================
# RLDrivenMTDController (Scoring 기능 통합)
# ======================================================================================
class RLDrivenMTDController(MTDController):
    """
    기본 MTDController를 상속받아, RL 에이전트의 결정에 따라 MTD를 수행하고,
    실시간 성능 점수를 계산하는 지능형 제어기 v1.2.
    """
    def __init__(self, model_path):
        super().__init__()
        self.state_dim = 6
        self.action_dim = 7
        self.policy = self._load_policy(model_path)

        # MTD 동적 파라미터 (train.py와 동일)
        self.dyn_params = {
            "ip_cd": {"val": 15.0, "min": 5.0, "max": 60.0},
            "decoy_ratio": {"val": 0.1, "min": 0.0, "max": 0.5},
            "bl_level": {"val": 1.0, "min": 0.0, "max": 5.0}
        }
        self.mtd_meta_actions = {
            0: ("ip_cd", 1.2), 1: ("ip_cd", 0.8), 2: ("decoy_ratio", 1.2),
            3: ("decoy_ratio", 0.8), 4: ("bl_level", 1.0), 5: ("bl_level", -1.0), 6: ("none", 1.0)
        }

        # 실제 환경 관찰을 위한 변수
        self.recent_attacks_ema = 0.0
        self.known_rate_approx = 0.0
        self.exposure_steps = 0
        self.last_log_ts: Dict[str, float] = {"system": 0.0, "network": 0.0}

        # Scorer 객체 생성
        self.scorer = TestbedScorer()
        self.last_score_time = 0.0

    def _load_policy(self, path):
        """학습된 Pytorch 모델(.pth) 파일을 로드합니다."""
        if not os.path.exists(path):
            print(f"❌ RL 정책 모델을 찾을 수 없습니다: {path}", file=sys.stderr)
            print("  먼저 rl/train.py를 실행하여 모델을 학습시키고, 올바른 경로에 배치해야 합니다.")
            sys.exit(1)

        print(f"🤖 RL 정책 모델 로드 중: {path}")
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        policy = ActorCritic(self.state_dim, self.action_dim).to(device)
        try:
            policy.load_state_dict(torch.load(path, map_location=device))
        except Exception as e:
            print(f"❌ RL 정책 모델 로드 실패: {e}", file=sys.stderr)
            print("   모델 파일이 손상되었거나 ActorCritic 구조와 호환되지 않을 수 있습니다.")
            sys.exit(1)
        policy.eval()
        print("✅ RL 정책 모델 로드 완료.")
        return policy

    def _read_recent_logs(self, log_path: str, last_read_ts: float) -> Tuple[List[Dict], float]:
        """주어진 시간 이후의 로그만 읽어옵니다."""
        new_logs = []
        max_ts = last_read_ts
        if os.path.exists(log_path):
            try:
                with open(log_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    for line in reversed(lines):
                        try:
                            log_entry = json.loads(line)
                            ts = log_entry.get("ts", 0)
                            if ts > last_read_ts:
                                new_logs.append(log_entry)
                                max_ts = max(max_ts, ts)
                            else:
                                break
                        except json.JSONDecodeError:
                            continue
            except Exception as e:
                print(f"[경고] 로그 파일 읽기 오류 ({log_path}): {e}", file=sys.stderr)
        return list(reversed(new_logs)), max_ts

    def _update_observations_from_logs(self):
        """로그 파일들을 파싱하여 위협 지표를 업데이트합니다."""
        now = time.time()

        # 1. 최근 공격 빈도 계산
        attack_count = 0
        log_path_system = os.path.join(BUS_DIR, 'bus_system.log')
        new_system_logs, self.last_log_ts["system"] = self._read_recent_logs(log_path_system, self.last_log_ts.get("system", 0.0))

        for log_entry in new_system_logs:
            if log_entry.get("type") == "attack_started":
                attack_count += 1
        current_attack_rate = attack_count / DECISION_INTERVAL_SECONDS if DECISION_INTERVAL_SECONDS > 0 else 0
        self.recent_attacks_ema = 0.8 * self.recent_attacks_ema + 0.2 * current_attack_rate

        # 2. 공격자 정보 획득률 추정
        unique_ips_in_interval = set()
        log_path_network = os.path.join(BUS_DIR, 'bus_network.log')
        new_network_logs, self.last_log_ts["network"] = self._read_recent_logs(log_path_network, self.last_log_ts.get("network", 0.0))
        current_target_ip_local, _ = self.get_target_info()

        if current_target_ip_local:
            for log_entry in new_network_logs:
                if (now - log_entry.get("ts", 0)) <= 60:
                    data = log_entry.get("data", {})
                    if data.get("dst_ip") == current_target_ip_local:
                        src_ip = data.get("src_ip")
                        if src_ip and src_ip not in ["10.13.0.4", "10.13.0.250", self.host_ip]:
                            unique_ips_in_interval.add(src_ip)
            self.known_rate_approx = min(len(unique_ips_in_interval) / 10.0, 1.0)
        else:
            self.known_rate_approx = 0.0

    def _observe_environment(self) -> torch.Tensor:
        """실제 환경을 관찰하여 RL 에이전트의 입력 상태 벡터를 생성합니다."""
        self._update_observations_from_logs()
        self.exposure_steps += 1

        norm_ip_cd = np.clip((self.dyn_params["ip_cd"]["val"] - self.dyn_params["ip_cd"]["min"]) / (self.dyn_params["ip_cd"]["max"] - self.dyn_params["ip_cd"]["min"]), 0, 1)
        norm_decoy = np.clip(self.dyn_params["decoy_ratio"]["val"] / self.dyn_params["decoy_ratio"]["max"], 0, 1)
        norm_bl = np.clip(self.dyn_params["bl_level"]["val"] / self.dyn_params["bl_level"]["max"], 0, 1)
        norm_exposure = np.clip(self.exposure_steps / 100.0, 0, 1)

        state_values = [
            np.clip(self.recent_attacks_ema, 0, 1), np.clip(self.known_rate_approx, 0, 1),
            norm_exposure, norm_ip_cd, norm_decoy, norm_bl
        ]
        state_values = [0.0 if np.isnan(v) else v for v in state_values]
        state = torch.tensor(state_values, dtype=torch.float32)
        return state.unsqueeze(0)

    def _apply_action(self, action_idx: int) -> Dict:
        """RL 행동을 MTD 파라미터에 적용하고, 액션 정보를 반환합니다."""
        action = self.mtd_meta_actions.get(action_idx)
        applied_action_info = {"type": "mtd_action_applied", "action_idx": action_idx, "action": action}
        if not action or action[0] == "none":
            print("     - 행동: 유지 (None)")
            return applied_action_info # 액션 정보만 반환

        param_name, value = action
        current_val = self.dyn_params[param_name]["val"]
        new_val = current_val + value if param_name == "bl_level" else current_val * value
        p_min = self.dyn_params[param_name]["min"]
        p_max = self.dyn_params[param_name]["max"]
        self.dyn_params[param_name]["val"] = float(np.clip(new_val, p_min, p_max))
        print(f"     - 행동: {param_name} -> {self.dyn_params[param_name]['val']:.2f}")

        # 적용된 파라미터 정보 추가
        applied_action_info["param_changed"] = param_name
        applied_action_info["new_value"] = self.dyn_params[param_name]['val']
        return applied_action_info

    def execute_intelligent_mtd(self):
        """RL 에이전트의 결정에 따라 MTD를 수행합니다."""
        print("\n" + "="*18 + " RL-MTD Decision Cycle " + "="*18)
        current_state = self._observe_environment()
        print(f"  [관찰] 현재 상태: {np.round(current_state.numpy(), 3)}")

        action_idx = 6 # 기본 'none'
        try:
            with torch.no_grad():
                action_tensor, _, _ = self.policy.act(current_state)
                action_idx = action_tensor.item()
        except Exception as e:
            print(f"❌ 정책 모델 실행 오류: {e}", file=sys.stderr)
        print(f"  [결정] 선택된 행동 인덱스: {action_idx}")

        applied_action_info = self._apply_action(action_idx) # 파라미터 업데이트

        # 업데이트된 파라미터로 MTD 실행 결정
        current_ip_cd = max(self.dyn_params["ip_cd"]["val"], 1e-6)
        p_shuffle = 0.6 / current_ip_cd
        performed_shuffle = False
        if random.random() < p_shuffle:
            print("  [실행] IP Cooldown 조건 충족. MTD 셔플링을 실행합니다.")
            self.exposure_steps = 0
            try:
                # execute_mtd_shuffle 내부에서 mtd_switch 로그를 남긴다고 가정
                super().execute_mtd_shuffle()
                performed_shuffle = True
            except Exception as e:
                print(f"❌ MTD 셔플링 실행 중 오류: {e}", file=sys.stderr)
                log_bus_event("mtd_error", {"msg": "shuffle_failed", "err": str(e)})
        else:
            print("  [실행] IP Cooldown 조건 미충족. 현재 엔드포인트를 유지합니다.")

        # Scorer에 MTD 액션 기록 (결정 정보 + 실제 셔플 여부)
        decision_log_data = {
                "state": current_state.tolist()[0],
                "action_idx": action_idx,
                "applied_action": applied_action_info.get("action"),
                "param_changed": applied_action_info.get("param_changed"),
                "new_value": applied_action_info.get("new_value"),
                "new_params": {k: v['val'] for k, v in self.dyn_params.items()},
                "performed_shuffle": performed_shuffle # 실제 셔플 실행 여부 추가
            }
        log_bus_event("rl_mtd_decision", decision_log_data)
        # 비용 계산을 위해 Scorer에도 기록
        self.scorer.record_mtd_action({"type": "rl_mtd_decision", "data": decision_log_data})
        if performed_shuffle:
            # mtd_switch 로그가 execute_mtd_shuffle에서 찍힌다고 가정하고, Scorer에도 알림
            # 실제 로그 형식을 보고 맞춰야 함
            current_target_ip, current_target_port = self.get_target_info()
            self.scorer.record_mtd_action({
                "type": "mtd_switch",
                "data": {"to": f"{current_target_ip}:{current_target_port}"} # 예시 데이터
            })
        print("="*58)

    def run(self):
        """주기적으로 RL 결정을 받아 MTD를 실행하고, 성능 점수를 계산합니다."""
        if not self.initialize() or not self.policy:
            print("초기화 실패 또는 정책 로드 실패. 컨트롤러를 시작할 수 없습니다.")
            return

        try:
            self._clear_all_redirections()
            super().execute_mtd_shuffle() # 초기 MTD 1회 실행
            current_target_ip, current_target_port = self.get_target_info()
            if current_target_ip and current_target_port:
                 self.scorer.record_mtd_action({
                    "type": "mtd_switch", # 초기화도 스위치로 간주
                    "data": {"to": f"{current_target_ip}:{current_target_port}"}
                })
        except Exception as e:
             print(f"❌ 초기 MTD 실행 중 오류: {e}", file=sys.stderr)
             return

        self.last_score_time = time.time() # 점수 계산 타이머 초기화

        while not self.stop_event.is_set():
            decision_start_time = time.time()
            try:
                self.execute_intelligent_mtd() # RL 기반 MTD 결정 및 실행

                # 주기적으로 성능 점수 계산 및 로깅
                if decision_start_time - self.last_score_time >= SCORING_INTERVAL_SECONDS:
                    print(f"\n--- ⏱️ MTD 성능 점수 계산 (최근 {SCORING_WINDOW_SECONDS}초 분석) ---")
                    score_results = self.scorer.calculate_score()
                    if score_results:
                        print(f"  📊 계산된 점수: {score_results['score']:.3f}")
                        print(f"     (R_succ: {score_results['r_succ_estimated']:.2%}, C_def: {score_results['c_def_actual']:.4f}, D_bits: {score_results['d_bits_estimated']:.3f})")
                        log_bus_event("mtd_performance_score", score_results)
                    else:
                        print("  📊 점수 계산 실패 (데이터 부족 등)")
                    self.last_score_time = decision_start_time
                    print("--- ⏱️ 점수 계산 완료 ---")

            except Exception as e:
                print(f"❌ 메인 루프 실행 중 예기치 않은 오류 발생: {e}", file=sys.stderr)
                log_bus_event("mtd_error", {"msg":"controller_loop", "err": str(e)})
                time.sleep(5) # 잠시 대기 후 재시도

            # 다음 결정까지 대기
            elapsed_time = time.time() - decision_start_time
            wait_time = max(0, DECISION_INTERVAL_SECONDS - elapsed_time)
            interrupted = self.stop_event.wait(timeout=wait_time)
            if interrupted:
                break

        print("\n🛑 RL-Driven MTD Controller를 종료합니다.")
        self._clear_all_redirections()


def main():
    parser = argparse.ArgumentParser(description="RL-Driven MTD Controller v1.2 (with Real-time Scoring)")
    parser.add_argument("--model", type=str, default=MODEL_PATH, help="사용할 defender_policy.pth 모델 파일의 경로")
    # Scoring 관련 인자 추가 가능 (예: --scoring-config)
    args = parser.parse_args()

    controller = RLDrivenMTDController(model_path=args.model)

    def shutdown_handler(signum, frame):
        print(f"\n[메인] 종료 신호 ({signal.Signals(signum).name}) 수신. 컨트롤러를 안전하게 종료합니다...")
        if not controller.stop_event.is_set():
            controller.shutdown(signum, frame)

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    controller.run()

if __name__ == "__main__":
    main()
