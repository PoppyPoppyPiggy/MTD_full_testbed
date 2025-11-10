#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MTD State Reader (The "Eyes") - 완성본 (YAML 기반)
- [수정] mtd_state.json (Hands가 쓴 파일)을 읽어 현재 활성 타겟을 파악합니다.
- [수정] bus.log (모니터가 쓴 파일)을 읽어 실시간 위협 알림을 파악합니다.
- Colab 시뮬레이터(environment.py)와 동일한 6D 상태 벡터(State)를 생성합니다.
"""

import numpy as np
import time
import json
import os
import sys
import yaml # YAML 설정을 읽기 위해 추가

# --- 경로 설정 ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE_PATH = os.path.join(BASE_DIR, 'shared_state', 'mtd_state.json')
BUS_LOG_PATH = os.path.join(BASE_DIR, '..', 'bus', 'bus.log')
CONFIG_PATH = os.path.join(BASE_DIR, 'configs', 'iptables_mtd.yaml')

class MTDStateReader:
    def __init__(self, config_path=CONFIG_PATH):
        print(f"[Eyes] MTD 상태 리더 초기화. 규칙서 로드: {config_path}")
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
                
            self.real_targets = config.get('real_targets', [])
            
            # [중요] 시뮬레이터와 State/Action 차원 일치 확인
            self.obs_dim = len(self.real_targets) + 1 + 1 # (real + decoy + alert)
            self.act_dim = len(self.real_targets) + 1 + 1 # (real + decoy + pass)
            
            if self.obs_dim != 6 or self.act_dim != 6:
                print(f"Warning: 시뮬레이터(6D/6D)와 차원 불일치! (State: {self.obs_dim}D, Action: {self.act_dim}D)")
                
        except Exception as e:
            print(f"[Eyes] Error: MTD 규칙서({config_path}) 로드 실패: {e}", file=sys.stderr)
            sys.exit(1)

    def _read_current_mtd_state(self) -> dict:
        """mtd_state.json 파일에서 현재 MTD 상태를 읽어옴"""
        try:
            with open(STATE_FILE_PATH, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"[Eyes] Error: {STATE_FILE_PATH} 읽기 실패, 기본값 반환: {e}", file=sys.stderr)
            return {"active_target": "", "decoy_active": False}

    def _read_recent_alerts(self, log_file=BUS_LOG_PATH, window_sec=10) -> float:
        """bus.log 파일에서 최근 'window_sec'초간의 알림을 집계 (단일 알림 플래그 반환)"""
        alert_detected = 0.0
        current_time = time.time()
        cutoff_time = current_time - window_sec

        if not os.path.exists(log_file):
            return 0.0

        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                for line in reversed(lines):
                    if not line.strip(): continue
                    try:
                        log_entry = json.loads(line)
                        log_time = log_entry.get('ts', 0)
                        
                        if log_time < cutoff_time:
                            break 
                        
                        log_type = log_entry.get('type', '')
                        if 'detected' in log_type or 'alert' in log_type:
                            alert_detected = 1.0
                            break
                            
                    except json.JSONDecodeError:
                        continue 
        except Exception as e:
            print(f"[Eyes] Error: {log_file} 파싱 실패: {e}", file=sys.stderr)

        return alert_detected

    def get_rl_state(self) -> np.ndarray:
        """
        MTD RL 에이전트를 위한 6D 상태 벡터(State)를 반환합니다.
        (Colab의 environment.py _get_state()와 100% 호환되어야 함)
        """
        state = np.zeros(self.obs_dim, dtype=np.float32)
        
        # 1. 현재 MTD 상태 읽기
        current_state_json = self._read_current_mtd_state()
        active_target = current_state_json.get('active_target')
        decoy_active = current_state_json.get('decoy_active', False)

        # 2. State [0-3]: One-hot (Active Real Target)
        if not decoy_active and active_target in self.real_targets:
            try:
                idx = self.real_targets.index(active_target)
                state[idx] = 1.0
            except ValueError:
                pass # active_target이 real_targets 목록에 없음 (오류 상태)

        # 3. State [4]: Decoy Active (Boolean)
        if decoy_active:
            state[len(self.real_targets)] = 1.0 # (인덱스 4)

        # 4. State [5]: Threat Alert (Boolean)
        state[len(self.real_targets) + 1] = self._read_recent_alerts(window_sec=10) # (인덱스 5)
        
        # print(f"[Eyes] State Read: {state}") # (디버그 시 주석 해제)
        return state

# --- 전역 인스턴스 ---
# rl_driven_deception_manager.py가 쉽게 import하여 사용할 수 있도록
# 전역 인스턴스를 생성합니다.
try:
    GlobalStateReader = MTDStateReader()
except Exception:
    print("[Eyes] Error: MTDStateReader 전역 인스턴스 생성 실패.", file=sys.stderr)
    GlobalStateReader = None

def get_rl_state() -> np.ndarray:
    """
    (Brain을 위한 헬퍼 함수)
    전역 인스턴스를 사용하여 6D 상태 벡터를 쉽게 가져옵니다.
    """
    if GlobalStateReader:
        return GlobalStateReader.get_rl_state()
    # 비상시, 6D 0벡터 반환
    return np.zeros(6, dtype=np.float32) 

if __name__ == "__main__":
    print("--- MTD State Reader (Eyes) 테스트 ---")
    state_vector = get_rl_state()
    print(f"반환된 State Vector (Dim: {len(state_vector)}):")
    print(state_vector)
    print("\n테스트 성공.")