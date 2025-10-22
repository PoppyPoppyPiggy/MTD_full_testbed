#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 파일명: dvd_lite/mtd/rl_driven_deception_manager.py
# 설명: train.py에서 학습된 RL 모델을 사용하여 MTD를 지능적으로 제어
import os
import docker
import subprocess
import time
import json
import random
import signal
import sys
import threading
import numpy as np
import torch
import torch.nn as nn
from torch.distributions import Categorical

# --- 기본 MTD 제어기와 설정 공유 ---
from deception_manager import MTDController, LPC_DIR, SHARED_STATE_DIR, STATE_FILE, \
                              TARGET_CONTAINER_NAME, DECOY_CONTAINER_NAME, NETWORK_NAME, AVAILABLE_PORTS

# --- 로거 설정 ---
sys.path.insert(0, LPC_DIR)
try:
    from bus.logger import log_bus_event
except ImportError:
    print("WARNING: bus.logger를 임포트할 수 없습니다.", file=sys.stderr)
    def log_bus_event(type: str, data: dict, source_override: str = "rl_deception_manager"):
        record = {"ts": time.time(), "source": source_override, "type": type, "data": data}
        print(json.dumps(record))

# --- RL 모델 관련 설정 ---
MODEL_PATH = os.path.join(LPC_DIR, 'rl', 'models', 'defender_policy.pth') # 학습된 모델 경로
DECISION_INTERVAL_SECONDS = 10 # RL 에이전트가 다음 행동을 결정하는 주기

# ======================================================================================
# train.py의 ActorCritic 모델 클래스를 그대로 가져옴 (의존성 최소화)
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

class RLDrivenMTDController(MTDController):
    """
    기본 MTDController를 상속받아, RL 에이전트의 결정에 따라 MTD를 수행하는 지능형 제어기.
    """
    def __init__(self, model_path):
        super().__init__()
        self.state_dim = 6  # train.py의 _obs_def() 상태 벡터 차원
        self.action_dim = 7 # train.py의 MTD_META_ACTIONS 개수
        self.policy = self._load_policy(model_path)
        
        # MTD 동적 파라미터 (train.py의 Config와 유사하게 관리)
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

    def _load_policy(self, path):
        """학습된 Pytorch 모델(.pth) 파일을 로드합니다."""
        if not os.path.exists(path):
            print(f"❌ RL 정책 모델을 찾을 수 없습니다: {path}", file=sys.stderr)
            print("   먼저 train.py를 실행하여 모델을 학습시키고, 올바른 경로에 배치해야 합니다.")
            sys.exit(1)
            
        print(f"🤖 RL 정책 모델 로드 중: {path}")
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        policy = ActorCritic(self.state_dim, self.action_dim).to(device)
        policy.load_state_dict(torch.load(path, map_location=device))
        policy.eval()
        print("✅ RL 정책 모델 로드 완료.")
        return policy

    def _observe_environment(self) -> torch.Tensor:
        """
        실제 테스트베드 환경(로그 파일 등)을 관찰하여 RL 에이전트의 입력 상태 벡터를 생성합니다.
        (이 부분은 실제 CTI 로그 포맷에 맞춰 정교하게 구현해야 합니다)
        """
        # --- Placeholder Implementation ---
        # TODO: bus/*.log 파일을 파싱하여 실제 위협 지표를 계산해야 합니다.
        # 예: attack_started 로그 빈도를 바탕으로 self.recent_attacks_ema 업데이트
        # 예: network_traffic 로그에서 알려지지 않은 소스 IP 비율로 self.known_rate_approx 업데이트
        
        self.exposure_steps += 1 # 간단한 예시로 시간 경과만 반영

        # train.py의 _obs_def() 형식과 동일하게 상태 벡터 구성
        state = torch.tensor([
            np.clip(self.recent_attacks_ema, 0, 1),
            self.known_rate_approx,
            self.exposure_steps / 100.0,
            (self.dyn_params["ip_cd"]["val"] - self.dyn_params["ip_cd"]["min"]) / (self.dyn_params["ip_cd"]["max"] - self.dyn_params["ip_cd"]["min"]),
            self.dyn_params["decoy_ratio"]["val"] / self.dyn_params["decoy_ratio"]["max"],
            self.dyn_params["bl_level"]["val"] / self.dyn_params["bl_level"]["max"]
        ], dtype=torch.float32)
        
        return state.unsqueeze(0) # 배치 차원 추가

    def _apply_action(self, action_idx: int):
        """RL 에이전트가 선택한 행동을 실제 MTD 파라미터 변경으로 적용합니다."""
        action = self.mtd_meta_actions.get(action_idx)
        if not action or action[0] == "none":
            print("   - 행동: 유지 (None)")
            return

        param_name, value = action
        current_val = self.dyn_params[param_name]["val"]
        
        if param_name == "bl_level":
            new_val = current_val + value
        else:
            new_val = current_val * value
            
        # 파라미터 값 범위 제한
        p_min = self.dyn_params[param_name]["min"]
        p_max = self.dyn_params[param_name]["max"]
        self.dyn_params[param_name]["val"] = np.clip(new_val, p_min, p_max)
        
        print(f"   - 행동: {param_name} -> {self.dyn_params[param_name]['val']:.2f}")

    def execute_intelligent_mtd(self):
        """RL 에이전트의 결정에 따라 MTD를 수행합니다."""
        print("\n" + "="*18 + " RL-MTD Decision Cycle " + "="*18)
        
        # 1. 환경 관찰 및 상태 벡터 생성
        current_state = self._observe_environment()
        print(f"  [관찰] 현재 상태: {np.round(current_state.numpy(), 3)}")
        
        # 2. 정책 모델을 통해 행동 결정
        with torch.no_grad():
            action_tensor, _, _ = self.policy.act(current_state)
            action_idx = action_tensor.item()
        
        print(f"  [결정] 선택된 행동 인덱스: {action_idx}")
        
        # 3. 결정된 행동을 MTD 파라미터에 적용
        self._apply_action(action_idx)

        # 4. 결정된 파라미터에 따라 실제 MTD 실행 (예: IP 셔플링)
        # ip_cd (cooldown) 값을 확률로 변환하여 셔플링 결정
        p_shuffle = 0.6 / self.dyn_params["ip_cd"]["val"]
        if random.random() < p_shuffle:
            print("  [실행] IP Cooldown 조건 충족. MTD 셔플링을 실행합니다.")
            self.exposure_steps = 0 # 셔플링 시 노출 시간 초기화
            super().execute_mtd_shuffle()
        else:
            print("  [실행] IP Cooldown 조건 미충족. 현재 엔드포인트를 유지합니다.")
        
        log_bus_event("rl_mtd_decision", {
            "state": current_state.squeeze().tolist(),
            "action_idx": action_idx,
            "applied_action": self.mtd_meta_actions.get(action_idx),
            "new_params": {k: v['val'] for k, v in self.dyn_params.items()}
        })
        print("="*58)
        
    def run(self):
        """주기적으로 RL 에이전트의 결정을 받아 MTD를 실행합니다."""
        if not self.initialize() or not self.policy:
            return
            
        self._clear_all_redirections()
        super().execute_mtd_shuffle() # 초기 MTD 1회 실행

        while not self.stop_event.is_set():
            self.stop_event.wait(DECISION_INTERVAL_SECONDS)
            if not self.stop_event.is_set():
                self.execute_intelligent_mtd()
        
        print("\n🛑 RL-Driven MTD Controller를 종료합니다.")
        self._clear_all_redirections()

def main():
    # 학습된 모델 경로를 인자로 받을 수 있도록 수정
    parser = argparse.ArgumentParser(description="RL-Driven MTD Controller")
    parser.add_argument("--model", type=str, default=MODEL_PATH, help="사용할 defender_policy.pth 모델 파일의 경로")
    args = parser.parse_args()

    controller = RLDrivenMTDController(model_path=args.model)
    signal.signal(signal.SIGINT, controller.shutdown)
    signal.signal(signal.SIGTERM, controller.shutdown)
    controller.run()

if __name__ == "__main__":
    main()
