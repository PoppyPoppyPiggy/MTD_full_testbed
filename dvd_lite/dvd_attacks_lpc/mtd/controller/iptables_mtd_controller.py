#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MTD Controller (The "Hands") - v3 (Advanced JSON Output)
- ...
- [수정] mtd_action_state.json 파일에 상세한 행동 상태를 기록합니다.
"""

import yaml
# ... (기존 import) ...
import sys
import os
import json
from collections import deque # [신규] Action History를 위함
import subprocess
import time

class IPTablesMTDController:
    def __init__(self, config_path='mtd/configs/iptables_mtd.yaml'):
        # ... (기존: Sudo 권한 확인) ...
        if os.geteuid() != 0:
            print("[Hands] Error: iptables를 제어하려면 root 권한이 필요합니다.", file=sys.stderr)
            print("          'sudo python3 mtd/rl_driven_deception_manager.py ...'로 실행하세요.", file=sys.stderr)
            sys.exit(1)
            
        try:
            # 2. 설정 파일 로드
            with open(config_path, 'r') as f:
                self.config = yaml.safe_load(f)
            
            # ... (기존: 주요 설정값 저장) ...
            self.chain_name = self.config.get('iptables_chain', 'MTD_SERVICE_CHAIN')
            self.public_port = self.config.get('public_port', 14550)
            self.protocol = self.config.get('protocol', 'udp')
            self.public_ip = self.config.get('public_host_ip', '127.0.0.1')
            self.conntrack_drop = self.config.get('conntrack_drop_on_switch', True)

            # [신규 수정] 3-1. Scorer가 읽을 mtd_action_state.json 파일 경로
            # (참고: 기존 'state_file'은 mtd_state_reader.py의 설정으로 이동됨)
            self.state_dir = os.path.join(os.path.dirname(config_path), '..', 'shared_state')
            os.makedirs(self.state_dir, exist_ok=True) # shared_state 디렉토리 생성
            
            # mtd_scoring.yaml의 'shared_files' 설정과 일치시킴
            self.action_state_file = os.path.join(self.state_dir, 'mtd_action_state.json') 
            print(f"[Hands] MTD 행동 상태 파일 경로: {self.action_state_file}")

            # [신규] 3-2. Decoy 식별 키워드
            self.decoy_keyword = self.config.get('decoy_keyword', 'DECOY')

            # 4. Action ID (0~6)와 YAML의 'mtd_rl_actions' 매핑
            # ... (기존 코드와 동일) ...
            self.action_map = {
                action['id']: action 
                for action in self.config.get('mtd_rl_actions', [])
            }
            
            if len(self.action_map) != 7:
                 print(f"Warning: mtd_rl_actions 개수가 7개가 아닙니다 ({len(self.action_map)}개).")
            
            # 5. iptables 체인 초기화
            self.initialize_chain()
            
            # [신규 수정] 6. 현재 MTD 상태 변수
            self.current_target_str = "None (Initialized)"
            self.current_target_is_decoy = False
            self.current_action_id = -1
            self.current_action_name = "None"
            self.last_applied_rule = "None"
            self.action_history = deque(maxlen=10) # 최근 10개 행동 기록
            
            # [신규 수정] 7. 시작 시 mtd_action_state.json 파일 초기화
            self._update_state_file(status="INITIALIZING")

        except FileNotFoundError:
            # ... (기존 오류 처리) ...
            print(f"Error: MTD 규칙서({config_path})를 찾을 수 없습니다!", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"Error: MTD 규칙서 로드 실패: {e}", file=sys.stderr)
            sys.exit(1)

    def _run_shell_command(self, command: str, suppress_errors=False):
        """(내부 함수) 셸 명령어를 실행 (v3 - 로깅 강화)"""
        # print(f"    -> Executing: {command}") # 디버깅 시 주석 해제
        self.last_applied_rule = command # [신규] 마지막 실행 명령어 저장
        try:
            subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
            return True
        except subprocess.CalledProcessError as e:
            if not suppress_errors:
                print(f"    -> [Hands] Error: 셸 명령어 실행 실패. \n    -> CMD: {command} \n    -> ERR: {e.stderr.strip()}", file=sys.stderr)
            return False

    def initialize_chain(self):
        # ... (기존 코드와 동일) ...
        print(f"[Hands] iptables NAT 체인 '{self.chain_name}' 초기화 중...")
        self._run_shell_command(f"iptables -t nat -N {self.chain_name}", suppress_errors=True)
        self._run_shell_command(f"iptables -t nat -F {self.chain_name}")

        ip_match = f"-d {self.public_ip}" if self.public_ip != "0.0.0.0" else ""
        jump_rule = f"iptables -t nat -A PREROUTING {ip_match} -p {self.protocol} --dport {self.public_port} -j {self.chain_name}"
        check_rule = jump_rule.replace("-A", "-C")

        if not self._run_shell_command(check_rule, suppress_errors=True):
            print(f"[Hands] PREROUTING에 MTD 점프 규칙 추가...")
            if not self._run_shell_command(jump_rule):
                print(f"[Hands] Error: PREROUTING 점프 규칙 설정 실패!", file=sys.stderr)
                sys.exit(1)
        
        print(f"[Hands] iptables 체인 초기화 완료.")


    # [!!! 핵심 수정 !!!]
    def _update_state_file(self, status="RUNNING", conntrack_cleared=False):
        """(내부 함수) 현재 MTD 상태를 mtd_action_state.json 파일에 기록 (Scorer가 읽음)"""
        
        state_data = {
            "last_update_timestamp": time.time(),
            "controller_status": status,
            "public_entrypoint": f"{self.public_ip}:{self.public_port}",
            "current_action": {
                "action_id": self.current_action_id,
                "action_name": self.current_action_name,
                "active_target": self.current_target_str,
                "is_decoy": self.current_target_is_decoy
            },
            "last_applied_rule": self.last_applied_rule,
            "conntrack_cleared": conntrack_cleared,
            "action_history": list(self.action_history) # deque를 list로 변환
        }
        
        try:
            with open(self.action_state_file, 'w') as f:
                json.dump(state_data, f, indent=4)
        except Exception as e:
            print(f"[Hands] Error: mtd_action_state.json 파일 쓰기 실패: {e}", file=sys.stderr)


    def execute_mtd_action_by_id(self, action_id: int):
        """[핵심] 'Brain'으로부터 Action ID를 받아 실제 MTD를 실행"""
        
        action = self.action_map.get(action_id)
        
        if not action:
            print(f"[Hands] Error: 알 수 없는 Action ID {action_id} 수신.", file=sys.stderr)
            return False

        action_name = action.get('name', 'unknown')
        action_type = action.get('type', 'Pass')
        
        # [신규] 속성 저장을 위해 기본값 설정
        target_str = "N/A"
        is_decoy = False
        conntrack_cleared = False
        self.last_applied_rule = "None" # 룰 실행 전 초기화

        # 1. 기존 MTD 규칙 제거 (체인 비우기)
        if not self._run_shell_command(f"iptables -t nat -F {self.chain_name}"):
            print(f"[Hands] Error: MTD 체인 비우기 실패.", file=sys.stderr)
            return False

        # 2. 새 MTD 규칙 적용
        rule_applied = False
        if action_type == "DNAT":
            target = action.get('target')
            if not target:
                print(f"[Hands] Error: Action {action_id}에 'target'이 없습니다.", file=sys.stderr)
                return False
            
            print(f"[Hands] Action: {action_name} (ID: {action_id}) 실행... -> {target}")
            
            cmd = f"iptables -t nat -A {self.chain_name} -p {self.protocol} -j DNAT --to-destination {target}"
            rule_applied = self._run_shell_command(cmd)

            target_str = target
            is_decoy = self.decoy_keyword.upper() in action_name.upper()

        elif action_type == "Drop":
            print(f"[Hands] Action: {action_name} (ID: {action_id}) 실행... -> DROP")
            cmd = f"iptables -t nat -A {self.chain_name} -p {self.protocol} --dport {self.public_port} -j DROP"
            rule_applied = self._run_shell_command(cmd)

            target_str = "DROP"
            is_decoy = False

        elif action_type == "Pass":
            print(f"[Hands] Action: {action_name} (ID: {action_id}) 실행... -> Pass (규칙 없음)")
            # 체인을 비웠으므로 아무 규칙도 추가하지 않으면 자동으로 Pass
            rule_applied = True
            self.last_applied_rule = "Pass (No Rule)"

            target_str = "Pass"
            is_decoy = False
        
        else:
            print(f"[Hands] Error: 알 수 없는 Action Type '{action_type}' (ID: {action_id})", file=sys.stderr)
            return False

        # 3. (선택적) 기존 연결 제거 (conntrack)
        if rule_applied and self.conntrack_drop:
            ip_match = f"-d {self.public_ip}" if self.public_ip != "0.0.0.0" else ""
            self._run_shell_command(f"conntrack -D -p {self.protocol} --dport {self.public_port} {ip_match}", suppress_errors=True)
            conntrack_cleared = True # [신규] 상태 기록

        # 4. MTD 상태를 클래스 속성으로 저장
        if rule_applied:
            self.current_target_str = target_str
            self.current_target_is_decoy = is_decoy
            self.current_action_id = action_id
            self.current_action_name = action_name
            
            # [신규] Action History 기록
            self.action_history.appendleft({
                "id": action_id,
                "name": action_name,
                "target": target_str,
                "time": time.time()
            })
            
            # 5. MTD 상태를 JSON 파일에 기록 (Scorer가 읽을 수 있도록)
            self._update_state_file(status="RUNNING", conntrack_cleared=conntrack_cleared)

        return rule_applied

    def reset_to_default(self):
        """MTD 규칙을 기본값(Pass)으로 초기화합니다."""
        print("[Hands] MTD 구성을 기본값(Pass)으로 재설정...")
        self._run_shell_command(f"iptables -t nat -F {self.chain_name}")
        
        # [신규 수정] reset 상태도 JSON에 기록
        self.current_target_str = "Pass"
        self.current_target_is_decoy = False
        self.current_action_id = -1 # Reset ID
        self.current_action_name = "Reset"
        self.last_applied_rule = f"iptables -t nat -F {self.chain_name}"
        self._update_state_file(status="RESETTING")