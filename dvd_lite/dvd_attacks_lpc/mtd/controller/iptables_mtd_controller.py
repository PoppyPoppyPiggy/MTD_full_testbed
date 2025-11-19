# File: MTD_full_testbed/dvd_lite/dvd_attacks_lpc/mtd/controller/iptables_mtd_controller.py
#
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[신규 3/8] Iptables MTD 컨트롤러 (v05)

- [!] 이 파일은 'deception_manager' Docker 컨테이너 내부에서 실행됩니다.
- [!] 'privileged: true' 권한이 필요합니다.
- '전략가(RL)'의 결정을 받아 실제 `iptables` 규칙을 수정하고 쉘 스크립트를 실행합니다.
- 블랙리스트 상태를 `blacklist.json` 파일로 관리합니다.
"""

import os
import subprocess
import logging
import json
import time
from typing import Dict, Any, List, Set

class IptablesController:
    """
    RL 매니저의 결정을 받아 실제 MTD 조치를 수행하는 실행기
    """
    def __init__(self,
                 iptables_chain: str = "DOCKER-USER",
                 blacklist_file: str = "/shared/blacklist.json",
                 scripts_dir: str = "/mtd_full_testbed/dvd_lite/dvd_attacks_lpc/mtd/scripts/",
                 logger: logging.Logger = None):
        
        self.logger = logger or logging.getLogger(__name__)
        self.chain = iptables_chain
        self.blacklist_file = blacklist_file
        self.scripts_dir = scripts_dir
        
        # { "ip": "10.13.0.200", "banned_until": 1234567890.0 }
        self.blacklist_state: List[Dict[str, Any]] = []
        self.dnat_target_ip: str = ""
        self.dnat_target_port: int = 0

        self._load_blacklist()
        self._check_iptables_chain()
        self.logger.info(f"IptablesController(v05) 초기화. Chain: {self.chain}, Blacklist: {self.blacklist_file}")

    def _run_cmd(self, cmd_list: List[str]) -> bool:
        """ 쉘 명령어 실행 헬퍼 """
        try:
            # self.logger.debug(f"Executing command: {' '.join(cmd_list)}")
            subprocess.run(cmd_list, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return True
        except subprocess.CalledProcessError as e:
            self.logger.error(f"명령어 실행 실패: {' '.join(cmd_list)}")
            self.logger.error(f"  - STDOUT: {e.stdout.decode(errors='ignore')}")
            self.logger.error(f"  - STDERR: {e.stderr.decode(errors='ignore')}")
            return False
        except Exception as e:
            self.logger.error(f"명령어 실행 중 예외: {e}")
            return False

    def _check_iptables_chain(self):
        """ DOCKER-USER 체인이 존재하는지 확인, 없으면 생성 시도 """
        # iptables -L DOCKER-USER -n
        if not self._run_cmd(["iptables", "-L", self.chain, "-n"]):
            self.logger.warning(f"iptables 체인 '{self.chain}' 없음. 새로 생성 시도...")
            # iptables -N DOCKER-USER
            if not self._run_cmd(["iptables", "-N", self.chain]):
                self.logger.error(f"'{self.chain}' 체인 생성 실패. 'privileged' 권한 확인 필요.")
            # iptables -I DOCKER 1 -j DOCKER-USER (DOCKER 체인 최상단에 연결)
            elif not self._run_cmd(["iptables", "-I", "DOCKER", "1", "-j", self.chain]):
                 self.logger.error(f"'{self.chain}'을 DOCKER 체인에 연결 실패.")
            else:
                 self.logger.info(f"'{self.chain}' 체인 생성 및 DOCKER에 연결 완료.")

    def _load_blacklist(self):
        """ shared_state/blacklist.json 에서 차단 목록 로드 """
        try:
            if os.path.exists(self.blacklist_file):
                with open(self.blacklist_file, 'r') as f:
                    self.blacklist_state = json.load(f)
            self.logger.info(f"{len(self.blacklist_state)}개의 블랙리스트 항목 로드 완료.")
        except Exception as e:
            self.logger.warning(f"블랙리스트 파일 로드 실패: {e}")
            self.blacklist_state = []

    def _save_blacklist(self):
        """ 현재 차단 목록을 .json 파일에 저장 """
        try:
            with open(self.blacklist_file, 'w') as f:
                json.dump(self.blacklist_state, f, indent=2)
        except Exception as e:
            self.logger.error(f"블랙리스트 파일 저장 실패: {e}")

    def _clear_all_rules(self):
        """ (안전장치) 이 컨트롤러가 관리하는 모든 규칙(DNAT, BLACKLIST)을 초기화 """
        self.logger.info(f"'{self.chain}' 체인의 모든 MTD 규칙 플러시(Flush) 중...")
        self._run_cmd(["iptables", "-F", self.chain])
        
        # 로드된 블랙리스트 상태도 초기화
        self.blacklist_state = []
        self._save_blacklist()

    # --- [1] DNAT 제어 ---
    def apply_dnat_redirect(self, target_ip: str, target_port: int, attacker_ip: str = "10.13.0.200"):
        """
        [핵심 실행 1] Seeker(Attacker)의 트래픽을 지정된 타겟으로 DNAT 리디렉션합니다.
        
        :param target_ip: DNAT 대상 IP (예: "10.13.0.2")
        :param target_port: DNAT 대상 포트 (예: 14550)
        :param attacker_ip: 공격자 컨테이너 IP (docker-compose-lite.yaml)
        """
        if self.dnat_target_ip == target_ip and self.dnat_target_port == target_port:
            self.logger.info(f"DNAT 규칙이 이미 {target_ip}:{target_port}로 설정되어 있어 변경 없음.")
            return

        # 1. 기존 DNAT 규칙 삭제 (존재할 경우)
        if self.dnat_target_ip:
            self._run_cmd([
                "iptables", "-D", self.chain,
                "-s", attacker_ip,
                "-j", "DNAT",
                "--to-destination", f"{self.dnat_target_ip}:{self.dnat_target_port}"
            ])
            self.logger.info(f"기존 DNAT 규칙 삭제: -> {self.dnat_target_ip}:{self.dnat_target_port}")

        # 2. 신규 DNAT 규칙 추가
        success = self._run_cmd([
            "iptables", "-A", self.chain,
            "-s", attacker_ip,
            "-j", "DNAT",
            "--to-destination", f"{target_ip}:{target_port}"
        ])
        
        if success:
            self.dnat_target_ip = target_ip
            self.dnat_target_port = target_port
            self.logger.info(f"신규 DNAT 규칙 적용: Attacker({attacker_ip}) -> {target_ip}:{target_port}")
        else:
            self.logger.error(f"신규 DNAT 규칙 적용 실패: {target_ip}:{target_port}")

    # --- [2] 셔플 스크립트 실행 ---
    def run_script(self, script_name: str):
        """
        [핵심 실행 2] mtd/scripts/ 하위의 쉘 스크립트를 실행합니다.
        (예: mtd_service_swap.sh)
        """
        script_path = os.path.join(self.scripts_dir, script_name)
        if not os.path.exists(script_path):
            self.logger.error(f"실행할 스크립트 없음: {script_path}")
            return
            
        self.logger.info(f"MTD 스크립트 실행: {script_name}")
        # (중요) DNAT 규칙과 충돌할 수 있으므로, 셔플 전 DNAT 규칙 비활성화
        self.apply_dnat_redirect("127.0.0.1", 1) # (임시) 루프백으로 돌려 충돌 방지
        
        self._run_cmd(["bash", script_path])
        
        self.logger.info(f"스크립트 실행 완료: {script_name}")
        # (셔플 후 DNAT 상태가 불확실하므로, 다음 step에서 RL이 다시 결정하도록 함)
        self.dnat_target_ip = "" 
        self.dnat_target_port = 0

    # --- [3] 블랙리스트 제어 (RL v05) ---
    def update_blacklist(self, attacker_alerts: Dict[str, float], threshold: float, duration_sec: int):
        """
        [핵심 실행 3] CTI 경보 딕셔너리를 받아, RL의 임계값/기간 정책에 따라
        블랙리스트를 업데이트합니다.
        
        :param attacker_alerts: {"10.13.0.200": 0.8, "10.13.0.201": 0.3} (CTI가 탐지한 IP별 위협 점수)
        :param threshold: (0.0~1.0) RL이 결정한 차단 임계값 (이 점수 *초과* 시 차단)
        :param duration_sec: (초) RL이 결정한 차단 시간 (-1 = 영구)
        """
        now = time.time()
        current_banned_ips: Set[str] = {entry["ip"] for entry in self.blacklist_state}
        newly_banned_ips: Set[str] = set()

        # 1. 신규 차단 IP 결정
        for ip, alert_score in attacker_alerts.items():
            if alert_score > threshold and ip not in current_banned_ips:
                # [신규 차단]
                ban_until = (now + duration_sec) if duration_sec != -1 else -1
                entry = {"ip": ip, "banned_until": ban_until, "banned_at": now, "reason_score": alert_score}
                self.blacklist_state.append(entry)
                newly_banned_ips.add(ip)
                self.logger.info(f"블랙리스트 추가 (v05): IP={ip} (Score: {alert_score:.2f} > {threshold:.2f}), Duration: {duration_sec}s")

        # 2. 만료된 IP 제거
        expired_ips: Set[str] = set()
        active_blacklist: List[Dict[str, Any]] = []
        for entry in self.blacklist_state:
            ip = entry["ip"]
            if entry["banned_until"] == -1 or entry["banned_until"] > now:
                active_blacklist.append(entry) # 유지
            else:
                expired_ips.add(ip) # 만료
                self.logger.info(f"블랙리스트 만료 (v05): IP={ip}")
        
        self.blacklist_state = active_blacklist
        
        # 3. iptables 규칙 동기화
        # (A) 신규 차단 규칙 추가
        for ip in newly_banned_ips:
            self._run_cmd(["iptables", "-A", self.chain, "-s", ip, "-j", "DROP"])
            
        # (B) 만료된 차단 규칙 삭제
        for ip in expired_ips:
            self._run_cmd(["iptables", "-D", self.chain, "-s", ip, "-j", "DROP"])
            
        # 4. JSON 파일 저장 (상태 유지를 위해)
        if newly_banned_ips or expired_ips:
            self._save_blacklist()