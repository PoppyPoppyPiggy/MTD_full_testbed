#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import json
import yaml
from collections import deque

# --- 경로 설정 ---
LPC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if LPC_DIR not in sys.path:
    sys.path.insert(0, LPC_DIR)

from bus.logger import log_bus_event
# from stable_baselines3 import PPO # 실제 RL 모델을 사용할 경우

class RLAgent:
    def __init__(self, policy_path, bus_log_path):
        self.policy = self._load_policy(policy_path)
        self.bus_log_path = bus_log_path
        
        # RL 에이전트 설정
        rl_config = self.policy.get('rl_agent', {})
        self.decision_interval = rl_config.get('rl_decision_interval_s', 5)
        self.postures = list(self.policy['defense_postures'].keys())
        
        # 시스템 상태 관찰을 위한 변수
        self.recon_events = deque(maxlen=50) # 최근 50개의 정찰 이벤트 타임스탬프 저장
        self.observation_window_s = 60 # 최근 1분간의 정찰 빈도를 계산

        # # 실제 RL 모델을 로드하는 부분 (현재는 주석 처리)
        # model_path = os.path.join(LPC_DIR, 'rl', 'models', rl_config.get('rl_model_name'))
        # try:
        #     self.model = PPO.load(model_path)
        #     print(f"✅ RL 모델 로드 완료: {model_path}")
        # except Exception as e:
        #     print(f"❌ RL 모델 로드 실패. 규칙 기반으로 동작합니다. 오류: {e}")
        #     self.model = None
        
        print("✅ RL Agent (Brain) 초기화 완료")

    def _load_policy(self, path):
        print(f"[*] RL 정책 로드 중... (from {path})")
        with open(path, 'r') as f:
            return yaml.safe_load(f)

    def observe_environment(self):
        """
        bus.log를 읽어 최근 정찰 빈도 등 시스템 상태를 관찰합니다.
        (실제 RL 환경에서는 더 복잡한 상태 벡터를 구성해야 함)
        """
        try:
            with open(self.bus_log_path, 'r') as f:
                lines = f.readlines()
            
            # 최근 이벤트만 처리하여 성능 확보
            recent_lines = lines[-200:]
            current_time = time.time()
            
            # 최근 정찰 이벤트 업데이트
            for line in recent_lines:
                try:
                    log = json.loads(line)
                    if log.get('type') == 'recon_found_target':
                        ts = log.get('ts')
                        if ts not in self.recon_events:
                            self.recon_events.append(ts)
                except json.JSONDecodeError:
                    continue
            
            # 관찰 윈도우 내의 이벤트 수 계산
            events_in_window = [ts for ts in self.recon_events if current_time - ts <= self.observation_window_s]
            
            # 분당 공격 빈도(APM: Attacks Per Minute)와 유사한 개념으로 정찰 빈도 계산
            recon_freq_apm = len(events_in_window)
            
            # 상태 벡터 반환 (현재는 정찰 빈도만 사용)
            return {"recon_freq_apm": recon_freq_apm}

        except FileNotFoundError:
            return {"recon_freq_apm": 0}

    def make_decision(self, state):
        """
        관찰된 상태(state)를 기반으로 최적의 방어 태세(posture)를 결정합니다.
        (현재는 간단한 규칙 기반으로, 실제로는 RL 모델의 predict()를 호출해야 함)
        """
        recon_freq = state["recon_freq_apm"]
        
        # if self.model:
        #     action, _ = self.model.predict(state)
        #     return self.postures[action]
        
        # --- 규칙 기반 Fallback 로직 ---
        if recon_freq >= 5: # 분당 5회 이상 정찰 탐지 시
            return 'ISOLATION'
        elif recon_freq >= 2: # 분당 2회 이상 정찰 탐지 시
            return 'ACTIVE_DECEPTION'
        else:
            return 'LOW_PROFILE'

    def start(self):
        print("🚀 RL Agent 시작...")
        while True:
            # 1. 환경 관찰
            current_state = self.observe_environment()
            
            # 2. 의사 결정
            chosen_posture = self.make_decision(current_state)
            
            print(f"[*] 상태 관찰: Recon Freq={current_state['recon_freq_apm']}/min -> 결정: '{chosen_posture}'")
            
            # 3. 결정된 전략을 이벤트 버스에 발행
            log_bus_event('mtd_strategy_decision', {'posture': chosen_posture})
            
            time.sleep(self.decision_interval)

if __name__ == "__main__":
    policy_path = os.path.join(LPC_DIR, 'configs', 'mtd_policy.yaml')
    bus_log = os.path.join(LPC_DIR, 'bus', 'bus.log')
    
    agent = RLAgent(policy_path, bus_log)
    try:
        agent.start()
    except KeyboardInterrupt:
        print("\n🛑 RL Agent 종료.")