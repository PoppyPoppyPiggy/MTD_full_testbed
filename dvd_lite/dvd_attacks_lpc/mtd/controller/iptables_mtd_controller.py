#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MTD Controller (The "Hands")
- 'Brain'(rl_driven_deception_manager)으로부터 Action ID (0~6)를 받습니다.
- 'Rulebook'(iptables_mtd.yaml)을 참조하여,
- 실제 Docker 네트워크에 iptables/nft 셸 명령어를 실행합니다.
"""

import yaml
import subprocess
import time
import sys

class IPTablesMTDController:
    def __init__(self, config_path='mtd/configs/iptables_mtd.yaml'):
        print(f"[Hands] MTD 컨트롤러 초기화. 규칙서 로드: {config_path}")
        try:
            with open(config_path, 'r') as f:
                self.config = yaml.safe_load(f)
                
            # [중요] 시뮬레이터의 7D Action ID (0~6)와
            #        Rulebook의 mtd_rl_actions (id: 0~6)를 매핑합니다.
            self.action_map = {
                action['id']: action 
                for action in self.config.get('mtd_rl_actions', [])
            }
            
            if len(self.action_map) != 7:
                print(f"Warning: mtd_rl_actions 개수가 7개가 아닙니다 ({len(self.action_map)}개). 시뮬레이터와 호환되지 않을 수 있습니다.")
                
        except FileNotFoundError:
            print(f"Error: MTD 규칙서({config_path})를 찾을 수 없습니다!", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"Error: MTD 규칙서 로드 실패: {e}", file=sys.stderr)
            sys.exit(1)

    def execute_mtd_action_by_id(self, action_id: int):
        """[핵심] 'Brain'으로부터 Action ID를 받아 실제 MTD를 실행"""
        
        action = self.action_map.get(action_id)
        
        if not action:
            print(f"[Hands] Error: 알 수 없는 Action ID {action_id} 수신.", file=sys.stderr)
            return

        action_name = action.get('name', 'unknown')
        
        # 1. 'Pass' 액션 (아무것도 안 함)
        if action_name == 'none':
            print(f"[Hands] Action: Pass (ID: {action_id}). 아무것도 실행하지 않음.")
            # (중요) 'Eyes'(mtd_state_reader)에게 현재 파라미터가 변경되지 않았음을 알려야 함
            # (예: mtd/shared_state/mtd_state.json 파일 업데이트)
            return

        print(f"[Hands] Action: {action_name} (ID: {action_id}) 실행...")

        # 2. 'Rulebook'(YAML)에 정의된 실제 MTD 실행
        # (예시: 'ip_cd_up' (id=0) 또는 'decoy_up' (id=2))
        
        # TODO: 여기에 실제 MTD 실행 로직이 들어가야 합니다.
        # 이 로직은 'Rulebook'(YAML)의 'target_script' 또는 'command'를 참조하여
        # mtd/scripts/mtd_service_swap.sh 등을 subprocess로 실행해야 합니다.
        
        # --- (설계 예시 Stub) ---
        if action_name == 'ip_cd_up':
            self._run_shell_command("mtd/scripts/set_ip_cd.sh fast")
            # (중요) 'Eyes'(mtd_state_reader)가 참조할 수 있도록 
            # MOCK_CURRENT_PARAMS["ip_cd"] 값을 업데이트해야 함
            
        elif action_name == 'ip_cd_down':
            self._run_shell_command("mtd/scripts/set_ip_cd.sh slow")
            
        elif action_name == 'decoy_up':
            self._run_shell_command("mtd/scripts/set_decoy_ratio.sh 0.3") # 예시 값
            
        elif action_name == 'decoy_down':
            self._run_shell_command("mtd/scripts/set_decoy_ratio.sh 0.1") # 예시 값
            
        elif action_name == 'bl_up':
            self._run_shell_command("mtd/scripts/set_bl_level.sh 3") # 예시 값
            
        elif action_name == 'bl_down':
            self._run_shell_command("mtd/scripts/set_bl_level.sh 1") # 예시 값
        # --- (설계 예시 Stub 끝) ---

    def _run_shell_command(self, command_str: str):
        """(내부 함수) 셸 명령어를 실행 (예: mtd/scripts/...)"""
        print(f"    -> Executing: {command_str}")
        try:
            # (실제 배포 시)
            # subprocess.run(command_str.split(), check=True, capture_output=True, text=True)
            pass # (현재는 stub이므로 통과)
        except Exception as e:
            print(f"    -> [Hands] Error: 셸 명령어 실행 실패: {e}", file=sys.stderr)