#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MTD State Reader (The "Eyes") - 완성본 (YAML 기반)
- [수정] mtd_state.json (Hands가 쓴 파일)을 읽어 현재 활성 타겟을 파악합니다.
- [수정] bus.log (모니터가 쓴 파일)을 읽어 실시간 위협 알림을 파악합니다.
- [수정] Colab 시뮬레이터(6D)와 달리, 테스트베드 매니저(8D)에 맞는 상태 벡터를 생성합니다.
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
# [수정] config_path는 manager가 인자로 전달해주는 것을 기본으로 함
# CONFIG_PATH = os.path.join(BASE_DIR, 'configs', 'iptables_mtd.yaml')

# [수정] 매니저가 예상하는 차원 (8D State, 7D Action)
TESTBED_STATE_DIM = 8
TESTBED_ACTION_DIM = 7

class MTDStateReader:
    def __init__(self, config_path): # 기본값 제거, 매니저가 전달하는 경로 사용
        print(f"[Eyes] MTD 상태 리더 초기화. 규칙서 로드: {config_path}")
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            # [중요] YAML 파일에서 'real_targets' 리스트를 읽어옴
            self.real_targets = config.get('real_targets', [])
            
            # [중요] 시뮬레이터와 State/Action 차원 일치 확인
            # (real 6개 + decoy 1개 + alert 1개 = 8D)
            self.obs_dim = len(self.real_targets) + 1 + 1 
            
            # [수정] 경고 로직을 8D 기준으로 변경
            if self.obs_dim != TESTBED_STATE_DIM:
                print(f"Warning: 매니저 예상({TESTBED_STATE_DIM}D)과 차원 불일치! (State: {self.obs_dim}D)")
                print(f"         'real_targets'가 {TESTBED_STATE_DIM - 2}개({len(self.real_targets)}개)인지 {config_path}에서 확인하세요.")
            else:
                 print(f"[Eyes] {len(self.real_targets)}개의 Real Targets 로드. {self.obs_dim}D 상태 벡터 사용.")

        except Exception as e:
            print(f"[Eyes] Error: MTD 규칙서({config_path}) 로드 실패: {e}", file=sys.stderr)
            sys.exit(1)

    def _read_current_mtd_state(self) -> dict:
        """mtd_state.json 파일에서 현재 MTD 상태를 읽어옴"""
        try:
            with open(STATE_FILE_PATH, 'r') as f:
                return json.load(f)
        except Exception as e:
            # print(f"[Eyes] Error: {STATE_FILE_PATH} 읽기 실패, 기본값 반환: {e}", file=sys.stderr) # 너무 많은 로그 방지
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
        MTD RL 에이전트를 위한 8D 상태 벡터(State)를 반환합니다.
        (rl_driven_deception_manager.py가 8D를 예상)
        [구성] Real Targets (6) + Decoy (1) + Alert (1)
        """
        # [수정] self.obs_dim (YAML 기반) 또는 8D 중 작은 값으로 초기화 (방어 코드)
        # YAML이 6개가 아니어도 8D 벡터는 생성되어야 함
        state = np.zeros(TESTBED_STATE_DIM, dtype=np.float32) 
        
        # 1. 현재 MTD 상태 읽기 (컨트롤러가 쓴 파일)
        current_state_json = self._read_current_mtd_state()
        active_target = current_state_json.get('active_target') # 예: "10.13.0.2:14550"
        decoy_active = current_state_json.get('decoy_active', False)

        # 2. State [0-5]: One-hot (Active Real Target)
        # [수정] real_targets 리스트가 비어있지 않은지 확인
        if not decoy_active and active_target and self.real_targets:
            try:
                # YAML에 정의된 real_targets 리스트에서 현재 active_target의 인덱스를 찾음
                idx = self.real_targets.index(active_target)
                if idx < (TESTBED_STATE_DIM - 2): # 6개 인덱스(0-5) 내에 있는지 확인
                    state[idx] = 1.0
            except ValueError:
                pass # active_target이 real_targets 목록에 없음 (정상, Decoy일 수 있음)
            except Exception as e:
                print(f"[Eyes] Error: real_targets 인덱싱 오류: {e}")

        # 3. State [6]: Decoy Active (Boolean)
        if decoy_active:
            state[TESTBED_STATE_DIM - 2] = 1.0 # (인덱스 6)

        # 4. State [7]: Threat Alert (Boolean)
        state[TESTBED_STATE_DIM - 1] = self._read_recent_alerts(window_sec=10) # (인덱스 7)
        
        # print(f"[Eyes] State Read: {state}") # (디버그 시 주석 해제)
        return state

# --- 전역 인스턴스 ---
# rl_driven_deception_manager.py가 쉽게 import하여 사용할 수 있도록
# 전역 인스턴스를 생성합니다.
# [수정] 매니저가 경로를 지정하여 직접 생성하므로 전역 인스턴스 불필요
# try:
#     GlobalStateReader = MTDStateReader()
# except Exception:
#     print("[Eyes] Error: MTDStateReader 전역 인스턴스 생성 실패.", file=sys.stderr)
#     GlobalStateReader = None

# def get_rl_state() -> np.ndarray:
#     """
#     (Brain을 위한 헬퍼 함수)
#     전역 인스턴스를 사용하여 8D 상태 벡터를 쉽게 가져옵니다.
#     """
#     if GlobalStateReader:
#         return GlobalStateReader.get_rl_state()
#     # 비상시, 8D 0벡터 반환
#     return np.zeros(TESTBED_STATE_DIM, dtype=np.float32) 

if __name__ == "__main__":
    print("--- MTD State Reader (Eyes) 테스트 ---")
    # 테스트 시에는 YAML 경로를 하드코딩해야 함
    try:
        TEST_CONFIG_PATH = os.path.join(BASE_DIR, 'configs', 'iptables_mtd.yaml')
        reader = MTDStateReader(config_path=TEST_CONFIG_PATH)
        state_vector = reader.get_rl_state()
        print(f"반환된 State Vector (Dim: {len(state_vector)}):")
        print(state_vector)
        print("\n테스트 성공.")
    except Exception as e:
        print(f"\n테스트 실패: {e}")
        print("iptables_mtd.yaml 파일이 있는지, 'real_targets' 키가 있는지 확인하세요.")