#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MTD Controller (The "Hands") - v2 (Full Implementation)
- 'Brain'(rl_driven_deception_manager)으로부터 Action ID (0~6)를 받습니다.
- 'Rulebook'(iptables_mtd.yaml)을 참조하여,
- 실제 Docker 네트워크에 iptables 셸 명령어를 실행합니다.
"""

import yaml
import subprocess
import time
import sys
import os

class IPTablesMTDController:
    def __init__(self, config_path='mtd/configs/iptables_mtd.yaml'):
        print(f"[Hands] MTD 컨트롤러 초기화. 규칙서 로드: {config_path}")
        
        # 1. Sudo 권한 확인 (iptables는 root 권한 필요)
        if os.geteuid() != 0:
            print("[Hands] Error: iptables를 제어하려면 root 권한이 필요합니다.", file=sys.stderr)
            print("          'sudo python3 mtd/rl_driven_deception_manager.py ...'로 실행하세요.", file=sys.stderr)
            sys.exit(1)
            
        try:
            # 2. 설정 파일 로드
            with open(config_path, 'r') as f:
                self.config = yaml.safe_load(f)
            
            # 3. 주요 설정값 저장
            self.chain_name = self.config.get('iptables_chain', 'MTD_SERVICE_CHAIN')
            self.public_port = self.config.get('public_port', 14550)
            self.protocol = self.config.get('protocol', 'udp')
            self.public_ip = self.config.get('public_host_ip', '127.0.0.1')
            self.conntrack_drop = self.config.get('conntrack_drop_on_switch', True)

            # 4. Action ID (0~6)와 YAML의 'mtd_rl_actions' 매핑
            self.action_map = {
                action['id']: action 
                for action in self.config.get('mtd_rl_actions', [])
            }
            
            if len(self.action_map) != 7:
                print(f"Warning: mtd_rl_actions 개수가 7개가 아닙니다 ({len(self.action_map)}개).")
                if len(self.action_map) == 0:
                     print("     [!] YAML 파일에 'mtd_rl_actions' 리스트가 정의되지 않았거나 파싱에 실패했습니다.")
            
            # 5. iptables 체인 초기화
            self.initialize_chain()

        except FileNotFoundError:
            print(f"Error: MTD 규칙서({config_path})를 찾을 수 없습니다!", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"Error: MTD 규칙서 로드 실패: {e}", file=sys.stderr)
            sys.exit(1)

    def _run_shell_command(self, command: str, suppress_errors=False):
        """(내부 함수) 셸 명령어를 실행 (예: iptables ...), 성공 시 True 반환"""
        # print(f"    -> Executing: {command}") # 디버깅 시 주석 해제
        try:
            subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
            return True
        except subprocess.CalledProcessError as e:
            if not suppress_errors:
                print(f"    -> [Hands] Error: 셸 명령어 실행 실패: {e.stderr}", file=sys.stderr)
            return False

    def initialize_chain(self):
        """MTD를 위한 iptables NAT 체인을 생성하고 PREROUTING에 연결합니다."""
        print(f"[Hands] iptables NAT 체인 '{self.chain_name}' 초기화 중...")
        
        # 1. MTD 체인 생성 (이미 존재하면 -N은 실패하지만 괜찮음)
        self._run_shell_command(f"iptables -t nat -N {self.chain_name}", suppress_errors=True)
        
        # 2. MTD 체인 비우기 (기존 규칙 제거)
        self._run_shell_command(f"iptables -t nat -F {self.chain_name}")

        # 3. PREROUTING -> MTD 체인으로 트래픽 점프 규칙 설정
        # 대상 IP가 0.0.0.0이면 모든 IP를 의미하므로 -d 플래그 생략
        ip_match = f"-d {self.public_ip}" if self.public_ip != "0.0.0.0" else ""
        
        jump_rule = f"iptables -t nat -A PREROUTING {ip_match} -p {self.protocol} --dport {self.public_port} -j {self.chain_name}"
        check_rule = jump_rule.replace("-A", "-C")

        # 4. 점프 규칙이 이미 있는지 확인하고, 없으면 추가
        if not self._run_shell_command(check_rule, suppress_errors=True):
            print(f"[Hands] PREROUTING에 MTD 점프 규칙 추가...")
            if not self._run_shell_command(jump_rule):
                print(f"[Hands] Error: PREROUTING 점프 규칙 설정 실패!", file=sys.stderr)
                sys.exit(1)
        
        print(f"[Hands] iptables 체인 초기화 완료.")

    def execute_mtd_action_by_id(self, action_id: int):
        """[핵심] 'Brain'으로부터 Action ID를 받아 실제 MTD를 실행"""
        
        action = self.action_map.get(action_id)
        
        if not action:
            print(f"[Hands] Error: 알 수 없는 Action ID {action_id} 수신.", file=sys.stderr)
            return False

        action_name = action.get('name', 'unknown')
        action_type = action.get('type', 'Pass')
        
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
            cmd = f"iptables -t nat -A {self.chain_name} -j DNAT --to-destination {target}"
            rule_applied = self._run_shell_command(cmd)

        elif action_type == "Drop":
            print(f"[Hands] Action: {action_name} (ID: {action_id}) 실행... -> DROP")
            cmd = f"iptables -t nat -A {self.chain_name} -j DROP"
            rule_applied = self._run_shell_command(cmd)

        elif action_type == "Pass":
            print(f"[Hands] Action: {action_name} (ID: {action_id}) 실행... -> Pass (규칙 없음)")
            # 체인을 비웠으므로 아무 규칙도 추가하지 않으면 자동으로 Pass (PREROUTING의 다음 규칙으로 넘어감)
            rule_applied = True
        
        else:
            print(f"[Hands] Error: 알 수 없는 Action Type '{action_type}' (ID: {action_id})", file=sys.stderr)
            return False

        # 3. (선택적) 기존 연결 제거 (conntrack)
        if rule_applied and self.conntrack_drop:
            # UDP 연결은 conntrack 제거가 덜 중요할 수 있지만, TCP의 경우 필수적입니다.
            ip_match = f"-d {self.public_ip}" if self.public_ip != "0.0.0.0" else ""
            self._run_shell_command(f"conntrack -D -p {self.protocol} --dport {self.public_port} {ip_match}", suppress_errors=True)

        return rule_applied

    def reset_to_default(self):
        """MTD 규칙을 기본값(모두 차단 또는 모두 비우기)으로 초기화합니다."""
        print("[Hands] MTD 구성을 기본값(Block)으로 재설정...")
        # 안전한 기본값은 ID 6 (Block_Traffic)을 실행하는 것입니다.
        self.execute_mtd_action_by_id(6)