#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 파일명: dvd_lite/mtd/rl_driven_deception_manager.py
# 설명: train.py에서 학습된 RL 모델을 사용하여 MTD를 지능적으로 제어 (CTI 로그 분석 기능 추가 v1.1)

import os
import docker
import subprocess
import time
import json
import random
import signal
import sys
import argparse
from collections import deque
from typing import Deque, Dict, Any, Optional, Tuple # Optional, Tuple 추가

import numpy as np
import torch
import torch.nn as nn
from torch.distributions import Categorical

# --- 기본 MTD 제어기와 설정 공유 ---
try:
    # deception_manager가 같은 디렉토리에 있다고 가정
    from deception_manager import MTDController, LPC_DIR, SHARED_STATE_DIR, STATE_FILE, \
                                  TARGET_CONTAINER_NAME, DECOY_CONTAINER_NAME, NETWORK_NAME, AVAILABLE_PORTS
except ImportError as e:
    print(f"ERROR: deception_manager.py 임포트 실패: {e}", file=sys.stderr)
    print("       이 스크립트는 deception_manager.py와 같은 디렉토리에 있어야 합니다.", file=sys.stderr)
    sys.exit(1)

# --- 경로 및 로거 설정 ---
# LPC_DIR은 deception_manager에서 가져옴
sys.path.insert(0, LPC_DIR)
BUS_DIR = os.path.join(LPC_DIR, 'bus') # CTI 로그 파일이 저장되는 경로
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

# ======================================================================================
# train.py의 ActorCritic 모델 클래스 (기존과 동일)
# ======================================================================================
class ActorCritic(nn.Module):
    def __init__(self, state_dim: int, action_dim: int):
        super(ActorCritic, self).__init__()
        self.shared_layer = nn.Sequential(nn.Linear(state_dim, 128), nn.Tanh(), nn.Linear(128, 128), nn.Tanh())
        self.actor = nn.Linear(128, action_dim)
        self.critic = nn.Linear(128, 1)

    def forward(self, state):
        x = self.shared_layer(state)
        return Categorical(logits=self.actor(x)), self.critic(x).squeeze(-1)

    def act(self, state):
        dist, value = self.forward(state)
        action = dist.sample()
        return action, dist.log_prob(action), value

# ======================================================================================
# RLDrivenMTDController (핵심 로직 수정)
# ======================================================================================
class RLDrivenMTDController(MTDController):
    """
    기본 MTDController를 상속받아, RL 에이전트의 결정에 따라 MTD를 수행하는 지능형 제어기.
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
        # 최근 로그 타임스탬프를 저장하여 중복 처리를 방지
        self.last_log_ts: Dict[str, float] = {"system": 0.0, "network": 0.0}

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
                    # 파일 끝에서부터 읽기 시작 (최신 로그 우선 처리) - 효율성은 떨어질 수 있음
                    # 또는 파일 크기 기반으로 새로 추가된 부분만 읽도록 최적화 가능
                    lines = f.readlines() # 전체 파일을 읽는 대신, 변경된 부분만 읽는 로직 필요 (복잡도 증가)
                    for line in reversed(lines): # 최신 로그부터 확인
                        try:
                            log_entry = json.loads(line)
                            ts = log_entry.get("ts", 0)
                            if ts > last_read_ts:
                                new_logs.append(log_entry)
                                max_ts = max(max_ts, ts)
                            else:
                                break # 이미 처리한 로그이므로 중단
                        except json.JSONDecodeError:
                            continue
            except Exception as e:
                print(f"[경고] 로그 파일 읽기 오류 ({log_path}): {e}", file=sys.stderr)
        return list(reversed(new_logs)), max_ts # 시간 순서대로 다시 뒤집어서 반환

    def _update_observations_from_logs(self):
        """
        [⭐️ 핵심 구현부 v1.1] bus/ 디렉토리의 로그 파일들을 파싱하여 위협 지표를 업데이트합니다. (중복 처리 개선)
        """
        now = time.time()

        # 1. 최근 공격 빈도 계산 (recent_attacks_ema)
        attack_count = 0
        log_path_system = os.path.join(BUS_DIR, 'bus_system.log') # attack_orchestrator 로그
        new_system_logs, self.last_log_ts["system"] = self._read_recent_logs(log_path_system, self.last_log_ts["system"])

        for log_entry in new_system_logs:
            if log_entry.get("type") == "attack_started":
                attack_count += 1

        # EMA(Exponential Moving Average) 업데이트 (최근 N초 간의 평균 비율로 근사)
        # DECISION_INTERVAL_SECONDS 동안의 평균 공격 발생률
        current_attack_rate = attack_count / DECISION_INTERVAL_SECONDS if DECISION_INTERVAL_SECONDS > 0 else 0
        self.recent_attacks_ema = 0.8 * self.recent_attacks_ema + 0.2 * current_attack_rate

        # 2. 공격자 정보 획득률 추정 (known_rate_approx)
        unique_ips_in_interval = set()
        log_path_network = os.path.join(BUS_DIR, 'bus_network.log')
        new_network_logs, self.last_log_ts["network"] = self._read_recent_logs(log_path_network, self.last_log_ts["network"])

        # 현재 타겟 IP 확인 (MTDController의 속성 사용)
        current_target_ip_local, _ = self.get_target_info() # MTDController 내부 함수 호출

        if current_target_ip_local: # 타겟 IP가 설정된 경우에만 계산
            for log_entry in new_network_logs:
                 # 최근 60초 로그만 고려 (더 긴 시간 창 필요 시 조정)
                 if (now - log_entry.get("ts", 0)) <= 60:
                    data = log_entry.get("data", {})
                    # 타겟 IP로 향하는 트래픽의 소스 IP 수집
                    if data.get("dst_ip") == current_target_ip_local:
                        src_ip = data.get("src_ip")
                        # GCS나 자기 자신 등 내부 IP는 제외 (필요 시 추가)
                        if src_ip and src_ip not in ["10.13.0.4", "10.13.0.250", self.host_ip]:
                             unique_ips_in_interval.add(src_ip)

            # 유니크 IP 수에 따라 0.0 ~ 1.0 사이로 정규화 (최대 10개 IP 도달 시 1.0)
            self.known_rate_approx = min(len(unique_ips_in_interval) / 10.0, 1.0)
        else:
             self.known_rate_approx = 0.0 # 타겟 IP 없으면 0으로 초기화


    def _observe_environment(self) -> torch.Tensor:
        """
        실제 테스트베드 환경(로그 파일)을 관찰하여 RL 에이전트의 입력 상태 벡터를 생성합니다.
        """
        # 1. 로그 파일로부터 최신 위협 지표 업데이트
        self._update_observations_from_logs()

        # 2. 내부 상태 업데이트
        self.exposure_steps += 1

        # 3. train.py의 _obs_def() 형식과 동일하게 상태 벡터 구성
        # 각 값의 범위를 확인하고 0~1 사이로 클리핑/정규화
        norm_ip_cd = np.clip((self.dyn_params["ip_cd"]["val"] - self.dyn_params["ip_cd"]["min"]) / (self.dyn_params["ip_cd"]["max"] - self.dyn_params["ip_cd"]["min"]), 0, 1)
        norm_decoy = np.clip(self.dyn_params["decoy_ratio"]["val"] / self.dyn_params["decoy_ratio"]["max"], 0, 1)
        norm_bl = np.clip(self.dyn_params["bl_level"]["val"] / self.dyn_params["bl_level"]["max"], 0, 1)
        norm_exposure = np.clip(self.exposure_steps / 100.0, 0, 1) # 최대 100 스텝(1000초)까지 고려

        state_values = [
            np.clip(self.recent_attacks_ema, 0, 1),
            np.clip(self.known_rate_approx, 0, 1),
            norm_exposure,
            norm_ip_cd,
            norm_decoy,
            norm_bl
        ]

        # NaN 값 방지
        state_values = [0.0 if np.isnan(v) else v for v in state_values]

        state = torch.tensor(state_values, dtype=torch.float32)

        return state.unsqueeze(0) # 배치 차원 추가

    def _apply_action(self, action_idx: int):
        """RL 에이전트가 선택한 행동을 실제 MTD 파라미터 변경으로 적용합니다."""
        action = self.mtd_meta_actions.get(action_idx)
        if not action or action[0] == "none":
            print("    - 행동: 유지 (None)")
            return

        param_name, value = action
        current_val = self.dyn_params[param_name]["val"]

        if param_name == "bl_level":
            new_val = current_val + value
        else:
            new_val = current_val * value

        p_min = self.dyn_params[param_name]["min"]
        p_max = self.dyn_params[param_name]["max"]
        # np.clip 결과가 numpy float일 수 있으므로 파이썬 float으로 변환
        self.dyn_params[param_name]["val"] = float(np.clip(new_val, p_min, p_max))

        print(f"    - 행동: {param_name} -> {self.dyn_params[param_name]['val']:.2f}")

    def execute_intelligent_mtd(self):
        """RL 에이전트의 결정에 따라 MTD를 수행합니다."""
        print("\n" + "="*18 + " RL-MTD Decision Cycle " + "="*18)

        # 1. 환경 관찰 및 상태 벡터 생성
        current_state = self._observe_environment()
        print(f"  [관찰] 현재 상태: {np.round(current_state.numpy(), 3)}")

        # 2. 정책 모델을 통해 행동 결정
        try:
            with torch.no_grad():
                action_tensor, _, _ = self.policy.act(current_state)
                action_idx = action_tensor.item()
        except Exception as e:
            print(f"❌ 정책 모델 실행 오류: {e}", file=sys.stderr)
            print("   입력 상태 벡터 값 확인:", current_state.numpy())
            action_idx = 6 # 오류 발생 시 기본 행동 'none' 선택

        print(f"  [결정] 선택된 행동 인덱스: {action_idx}")

        # 3. 결정된 행동을 MTD 파라미터에 적용
        self._apply_action(action_idx)

        # 4. 결정된 파라미터에 따라 실제 MTD 실행 (IP 셔플링)
        # ip_cd 값이 너무 작아지는 경우 (0 또는 음수) 방지
        current_ip_cd = max(self.dyn_params["ip_cd"]["val"], 1e-6) # 최소값 보장
        p_shuffle = 0.6 / current_ip_cd
        if random.random() < p_shuffle:
            print("  [실행] IP Cooldown 조건 충족. MTD 셔플링을 실행합니다.")
            self.exposure_steps = 0 # 셔플링 시 노출 시간 초기화
            # execute_mtd_shuffle() 실패 시 예외 처리 추가
            try:
                super().execute_mtd_shuffle()
            except Exception as e:
                print(f"❌ MTD 셔플링 실행 중 오류: {e}", file=sys.stderr)
                # 오류 발생 시 복구 로직 또는 로깅 추가 가능
        else:
            print("  [실행] IP Cooldown 조건 미충족. 현재 엔드포인트를 유지합니다.")

        # 상태 벡터 로깅 시 squeeze() 제거 (unsqueeze(0) 했으므로)
        log_bus_event("rl_mtd_decision", {
            "state": current_state.tolist()[0], # 리스트로 변환
            "action_idx": action_idx,
            "applied_action": self.mtd_meta_actions.get(action_idx),
            "new_params": {k: v['val'] for k, v in self.dyn_params.items()}
        })
        print("="*58)

    def run(self):
        """주기적으로 RL 에이전트의 결정을 받아 MTD를 실행합니다."""
        if not self.initialize() or not self.policy:
            print("초기화 실패 또는 정책 로드 실패. 컨트롤러를 시작할 수 없습니다.")
            return

        try:
            self._clear_all_redirections()
            super().execute_mtd_shuffle() # 초기 MTD 1회 실행
        except Exception as e:
             print(f"❌ 초기 MTD 실행 중 오류: {e}", file=sys.stderr)
             # 초기화 실패 시 종료 또는 다른 처리
             return

        while not self.stop_event.is_set():
            try:
                wait_time = DECISION_INTERVAL_SECONDS
                # stop_event.wait()는 중간에 인터럽트될 수 있으므로 루프 사용
                start_wait = time.time()
                while time.time() - start_wait < wait_time:
                    if self.stop_event.wait(0.5): # 0.5초마다 종료 이벤트 체크
                        break
                if self.stop_event.is_set():
                     break

                self.execute_intelligent_mtd()
            except Exception as e:
                 print(f"❌ 메인 루프 실행 중 예기치 않은 오류 발생: {e}", file=sys.stderr)
                 # 심각한 오류 시 관리자에게 알림 또는 재시작 로직 추가 가능
                 time.sleep(5) # 잠시 대기 후 재시도

        print("\n🛑 RL-Driven MTD Controller를 종료합니다.")
        self._clear_all_redirections()

def main():
    parser = argparse.ArgumentParser(description="RL-Driven MTD Controller v1.1 (Improved Observation & Stability)")
    parser.add_argument("--model", type=str, default=MODEL_PATH, help="사용할 defender_policy.pth 모델 파일의 경로")
    args = parser.parse_args()

    controller = RLDrivenMTDController(model_path=args.model)

    # Graceful shutdown signal handling
    def shutdown_handler(signum, frame):
        print(f"\n[메인] 종료 신호 ({signal.Signals(signum).name}) 수신. 컨트롤러를 안전하게 종료합니다...")
        if not controller.stop_event.is_set(): # 중복 호출 방지
             controller.shutdown(signum, frame) # MTDController의 shutdown 메소드 호출

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    controller.run()

if __name__ == "__main__":
    main()

