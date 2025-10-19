# File: dvd_lite/dvd_attacks_lpc/mtd/deception_manager.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import json
import time
import yaml
# import docker # Docker API는 현재 네트워크 제어에 직접 사용되지 않으므로 필요 시 주석 해제
import threading
from typing import Dict, Any, Optional, Tuple, List
import datetime
import requests # ⭐️ Ryu REST API 통신을 위해 사용
import random
import re

# --- 경로 설정 ---
MONITORS_DIR = os.path.dirname(os.path.realpath(__file__))
LPC_DIR = os.path.dirname(MONITORS_DIR) # MTD 디렉토리 상위 경로
BUS_DIR = os.path.join(LPC_DIR, 'bus')
SHARED_STATE_PATH = os.path.join(LPC_DIR, 'mtd', 'shared_state', 'mtd_state.json')
POLICY_FILE = os.path.join(LPC_DIR, 'configs', 'mtd_policy.yaml')
RL_OUTPUT_PATH = os.path.join(LPC_DIR, 'ml', 'output', 'mtd_policy_params.json') # RL Agent의 정책 출력 파일 경로 (시뮬레이션)

# --- PYTHONPATH 자동 설정 (가장 중요) ---
if LPC_DIR not in sys.path:
    sys.path.insert(0, LPC_DIR)

try:
    from bus.logger import log_bus_event
except ImportError:
    # 로깅 실패 시 대체 함수
    def log_bus_event(type: str, data: Dict[str, Any], source_override: str = "deception_manager"):
        record = {"ts": time.time(), "source": source_override, "type": type, "data": data}
        print(json.dumps(record))

# --- 전역 변수 및 상수 ---
# ⭐️ SDN 컨트롤러 정보 (docker-compose.yaml에서 환경 변수로 주입)
RYU_IP = os.environ.get('RYU_CONTROLLER_IP', '10.13.0.10')
RYU_PORT = os.environ.get('RYU_CONTROLLER_PORT', '8080')
RYU_BASE_URL = f"http://{RYU_IP}:{RYU_PORT}"

# ⭐️ 디코이 IP (docker-compose.yaml에 정의된 고정 IP)
DECOY_IP = "10.13.0.6"

# MTD 정책 관련 상수 (RL 환경의 Config 클래스에서 가져올 것으로 가정)
MTD_SHUFFLE_PERIOD_MAX = 60.0
MTD_SHUFFLE_PERIOD_MIN = 5.0
MTD_ACTION_SPACE = ['IP_SHUFFLE', 'DECOY_ACTIVATE', 'FLOW_BLOCK', 'NONE']
INITIAL_TARGET = "10.13.0.3:14550" # Companion Computer

# ⭐️ 리얼 타겟 컨테이너 IP 목록 (docker-compose.yaml 기반)
REAL_TARGET_IPS = ["10.13.0.2", "10.13.0.3", "10.13.0.4", "10.13.0.5"]

# --- MTD 상태 관리 ---
class MTDState:
    def __init__(self):
        self.current_target = INITIAL_TARGET
        self.last_shuffle_time = time.time()
        # ⭐️ RL 정책에서 제어되는 동적 MTD 파라미터 (초기값)
        self.rl_params = {'ip_cd': 30.0, 'decoy_ratio': 0.1, 'bl_level': 1.0}
        self.is_mtd_active = False

    def load_or_initialize(self):
        """MTD 상태를 파일에서 로드하거나, 파일이 없으면 초기화하고 저장합니다."""
        os.makedirs(os.path.dirname(SHARED_STATE_PATH), exist_ok=True)
        if os.path.exists(SHARED_STATE_PATH):
            try:
                with open(SHARED_STATE_PATH, 'r') as f:
                    data = json.load(f)
                    self.current_target = data.get('current_target', INITIAL_TARGET)
                    self.last_shuffle_time = data.get('last_shuffle_time', time.time())
                    self.rl_params = data.get('rl_params', self.rl_params)
                    self.is_mtd_active = data.get('is_mtd_active', False)
                print(f"[*] MTD state loaded from {SHARED_STATE_PATH}")
            except Exception as e:
                print(f"[!] Error loading MTD state: {e}. Using initial values.")
        else:
            self.save()
            print(f"[*] MTD state initialized and saved to {SHARED_STATE_PATH}")

    def save(self):
        """현재 MTD 상태를 파일에 저장합니다."""
        data = {
            'current_target': self.current_target,
            'last_shuffle_time': self.last_shuffle_time,
            'rl_params': self.rl_params,
            'is_mtd_active': self.is_mtd_active
        }
        try:
            with open(SHARED_STATE_PATH, 'w') as f:
                json.dump(data, f, indent=4)
        except IOError as e:
            log_bus_event("mtd_error", {"message": f"Failed to save MTD state file: {e}"})

# ==============================================================================
# ⭐️ RL 정책 연동 및 SDN 컨트롤 플레인 인터페이스
# ==============================================================================

def _get_rl_params_from_agent(state: MTDState, rl_agent_ip: str) -> Dict[str, float]:
    """
    RL Agent의 출력을 시뮬레이션하거나 실제 로드하여 최신 MTD 정책 파라미터를 반환합니다.
    (RL_OUTPUT_PATH 파일을 확인하여 정책을 로드한다고 가정)
    """
    if os.path.exists(RL_OUTPUT_PATH):
        try:
            with open(RL_OUTPUT_PATH, 'r') as f:
                params = json.load(f)
                
                # RL Agent가 생성한 최신 파라미터만 추출
                ip_cd = float(params.get('ip_cd_mean', 30.0))
                decoy_ratio = float(params.get('decoy_ratio_mean', 0.1))
                bl_level = float(params.get('bl_level_mean', 1.0))
                
                # 유효 범위 클램프
                ip_cd = max(MTD_SHUFFLE_PERIOD_MIN, min(MTD_SHUFFLE_PERIOD_MAX, ip_cd))

                return {
                    'ip_cd': ip_cd,
                    'decoy_ratio': max(0.0, min(0.5, decoy_ratio)),
                    'bl_level': max(0.0, min(5.0, bl_level)) # bl_level의 가정을 0~5로 설정
                }
        except Exception as e:
            log_bus_event("rl_agent_error", {"message": f"Failed to load RL params from file: {e}. Using current state."})
    
    # 파일이 없거나 로드 실패 시 현재 상태의 파라미터를 유지
    return state.rl_params


def get_datapath_ids(max_retries=5) -> Optional[str]:
    """Ryu REST API를 통해 OpenFlow 스위치(Datapath) ID를 조회합니다."""
    url = f"{RYU_BASE_URL}/stats/switches"
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=1)
            # Ryu가 연결된 Datapath ID 목록을 반환
            if response.status_code == 200 and response.json():
                # Docker OVS 환경에서는 하나의 Datapath ID만 있을 가능성이 높음
                return str(response.json()[0]) 
            time.sleep(2)
        except requests.exceptions.RequestException as e:
            # print(f"Ryu Controller 연결 실패 (시도 {attempt+1}/{max_retries}): {e}") # Debugging
            time.sleep(2)
    log_bus_event("sdn_error", {"message": "Ryu Controller에 연결할 수 없습니다. OVS 설정 확인 필요."})
    return None

def send_openflow_command(datapath_id: str, flow_entry: Dict[str, Any], command_type: str):
    """Ryu REST API를 통해 플로우 규칙을 주입/삭제합니다."""
    url_map = {'add': '/stats/flowentry/add', 'delete': '/stats/flowentry/delete'}
    url = f"{RYU_BASE_URL}{url_map.get(command_type)}"
    
    # ⭐️ Ryu API는 OpenFlow 스위치(OVS)를 제어하기 위한 표준 REST 인터페이스를 제공
    payload = { "dpid": int(datapath_id), "cookie": 1, "cookie_mask": 1, **flow_entry }
    
    try:
        response = requests.post(url, json=payload, timeout=2)
        if response.status_code != 200:
            log_bus_event("sdn_error", {"message": f"Flow {command_type} 실패", "status": response.status_code, "response": response.text, "payload": payload})
        else:
            log_bus_event("sdn_flow_update", {"type": command_type, "target": flow_entry.get('match', {}).get('ipv4_dst', 'N/A')})
    except requests.exceptions.RequestException as e:
        log_bus_event("sdn_error", {"message": f"Flow {command_type} API 통신 오류", "error": str(e)})


def _remove_old_mtd_flows(dpid: str, old_ip: str):
    """이전 타겟 IP에 대해 설정된 MTD 플로우 규칙을 제거합니다."""
    
    flow_match = {"eth_type": 2048, "ipv4_dst": old_ip}
    
    # 이전에 추가한 규칙과 동일한 조건으로 삭제 (priority=1000, cookie=1)
    delete_flow_entry = {
        "priority": 1000, 
        "match": flow_match
    }
    
    url = f"{RYU_BASE_URL}/stats/flowentry/delete"
    # cookie_mask를 사용하여 cookie가 1인 규칙만 정확히 삭제
    payload = { "dpid": int(dpid), "cookie": 1, "cookie_mask": 0xFFFFFFFFFFFFFFFF, **delete_flow_entry }
    
    try:
        response = requests.post(url, json=payload, timeout=2)
        if response.status_code == 200:
            log_bus_event("sdn_flow_update", {"type": "DELETE_OLD_IP_FLOW", "ip": old_ip})
            print(f"[*] SDN Cleanup: 이전 타겟 IP {old_ip}에 대한 MTD 플로우 규칙을 제거했습니다.")
        else:
             # 삭제 실패는 경고 수준으로 기록
            log_bus_event("sdn_warning", {"message": f"Flow delete (cleanup) 실패", "status": response.status_code, "ip": old_ip})
            
    except requests.exceptions.RequestException as e:
        log_bus_event("sdn_error", {"message": f"Flow delete API 통신 오류 (Cleanup)", "error": str(e)})


def apply_mtd_flows(old_ip: str, new_ip: str, decoy_ip: str, action: str, dpid: str):
    """MTD 정책에 따라 OpenFlow 규칙을 적용합니다."""
    
    # 1. 이전 타겟 IP에 대한 차단/리다이렉션 규칙 (탐지된 경우)
    if action == 'BLOCK' or action == 'DECOY':
        # 공격자가 이전 IP로 보내는 트래픽을 처리하는 Flow Entry 생성
        # 공격자 IP를 매칭에 포함하면 더 정확한 방어가 가능하지만, 현재는 목적지 IP만으로 통일
        flow_match = {"eth_type": 2048, "ipv4_dst": old_ip} 
        
        if action == 'BLOCK':
            # DROP 규칙 (우선순위 높게)
            flow_entry = {"priority": 1000, "match": flow_match, "actions": []} # actions: [] == DROP
            send_openflow_command(dpid, flow_entry, 'add')
            log_bus_event("mtd_action", {"action": "BLOCK_OLD_IP", "ip": old_ip})
            
        elif action == 'DECOY':
            # 리다이렉션 규칙 (목적지 IP를 디코이 IP로 변경)
            flow_entry = {
                "priority": 1000, 
                "match": flow_match, 
                "actions": [
                    {"type": "SET_FIELD", "field": "ipv4_dst", "value": decoy_ip}, 
                    {"type": "OUTPUT", "port": "NORMAL"}
                ]
            } 
            send_openflow_command(dpid, flow_entry, 'add')
            log_bus_event("mtd_action", {"action": "REDIRECT_TO_DECOY", "old_ip": old_ip, "decoy_ip": decoy_ip})

    # 2. 새로운 타겟 IP에 대한 기본 허용 규칙은 일반적으로 OpenFlow 스위치의
    # Controller/Normal 플로우에 의해 처리되므로 별도의 추가는 생략합니다.

# ==============================================================================
# 메인 루프 및 MTD 로직
# ==============================================================================

def mtd_main_loop(state: MTDState):
    """MTD Engine의 메인 실행 루프."""
    
    # ⭐️ SDN 컨트롤러 DPID 획득 시도 (MTD 셔플 시작 전에 미리 시도)
    dpid = get_datapath_ids()
    if not dpid:
        print("[!] SDN Control Plane이 작동하지 않아 네트워크 제어 기능이 비활성화됩니다. MTD 흐름 적용이 불가능합니다.")
        
    # client = docker.from_env() # Docker 클라이언트 제거 또는 주석 처리 유지
    
    while True:
        try:
            # 1. RL Agent에게서 MTD 정책 파라미터 획득 및 상태 업데이트
            new_params = _get_rl_params_from_agent(state, "10.13.0.203") 
            state.rl_params.update(new_params)
            ip_cd_threshold = state.rl_params['ip_cd']
            
            # 2. MTD 실행 결정
            time_since_shuffle = time.time() - state.last_shuffle_time
            
            if time_since_shuffle >= ip_cd_threshold:
                # 3. 새로운 타겟 IP/Port 결정
                old_ip, old_port = state.current_target.split(':')
                
                # 이전 IP를 제외하고 무작위로 선택
                potential_new_ips = [ip for ip in REAL_TARGET_IPS if ip != old_ip]
                
                if not potential_new_ips:
                    print("[!] 모든 리얼 타겟 IP가 현재 타겟과 동일합니다. 셔플을 건너뜁니다.")
                    time.sleep(1)
                    continue

                new_ip = random.choice(potential_new_ips)
                new_target = f"{new_ip}:{old_port}" 

                # 4. SDN 컨트롤러에 네트워크 플로우 명령 전달
                if dpid:
                    # 4-1. 이전 타겟 IP에 설정된 MTD 플로우 규칙 제거 (Cleanup)
                    _remove_old_mtd_flows(dpid, old_ip) 
                    
                    # 4-2. 새로운 MTD 액션 결정 및 플로우 적용 (RL 정책 기반)
                    action_type = 'DECOY' if random.random() < state.rl_params['decoy_ratio'] else 'BLOCK'
                    apply_mtd_flows(old_ip, new_ip, DECOY_IP, action_type, dpid)
                else:
                    log_bus_event("mtd_warning", {"message": "SDN 제어 플레인이 비활성화되어 MTD 셔플만 로직적으로 적용됨."})
                
                # 5. MTD 상태 업데이트 (공격 타겟 변경 기록)
                state.current_target = new_target
                state.last_shuffle_time = time.time()
                state.save()
                
                log_bus_event("mtd_triggered", {"old_target": f"{old_ip}:{old_port}", "new_target": new_target, "shuffle_period": ip_cd_threshold, "mtd_action": action_type, "rl_params": state.rl_params})
                
                print(f"[MTD Engine] MTD 셔플 실행: {old_ip} -> {new_ip} | 액션: {action_type} (다음 셔플까지 {ip_cd_threshold:.1f}s)")

            # 6. 다음 루프까지 대기
            wait_time = max(1, min(10, ip_cd_threshold - time_since_shuffle))
            time.sleep(wait_time)

        except KeyboardInterrupt:
            print("\n[MTD Engine] 사용자 요청으로 종료.")
            break
        except Exception as e:
            print(f"[MTD Engine] 치명적인 오류 발생: {e}", file=sys.stderr)
            time.sleep(5)

def main():
    state = MTDState()
    state.load_or_initialize()
    log_bus_event("mtd_engine_start", {"target": state.current_target, "ryu_api": RYU_BASE_URL})
    mtd_main_loop(state)
    log_bus_event("mtd_engine_stop", {"reason": "termination"})

if __name__ == "__main__":
    main()
