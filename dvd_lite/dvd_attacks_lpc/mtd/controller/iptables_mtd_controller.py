#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# File: dvd_lite/dvd_attacks_lpc/mtd/controller/iptables_mtd_controller.py
"""
Iptables 기반 MTD 컨트롤러 (v05, Testbed Deploy용)

- deception_manager 컨테이너 내부에서 실행되는 실제 iptables 조작기.
- RL 전략가(RLDrivenDeceptionManager)가 결정한 DNAT / Shuffle / Blacklist 액션을 수행한다.
- 블랙리스트 상태는 JSON 파일로 유지하여 CTI Agent(cti_status_reader.py)에서 재사용할 수 있다.

[2025-11-19 Upgrade]
- 환경변수로 체인/스크립트/블랙리스트 경로를 오버라이드 가능
    * MTD_IPTABLES_CHAIN
    * MTD_BLACKLIST_FILE
    * MTD_SCRIPTS_DIR
- 테스트베드 초기화 시 기존 규칙을 플러시하는 옵션(MTD_FLUSH_ON_START=1) 추가
- get_active_blacklist() 제공: CTI Agent demo에서 바로 사용 가능
"""

import os
import subprocess
import logging
import json
import time
from typing import Dict, Any, List, Set


class IptablesController:
    """
    RL 매니저의 결정을 받아 실제 MTD 조치를 수행하는 실행기.

    Parameters
    ----------
    iptables_chain : str
        관리할 체인 이름 (기본: DOCKER-USER).
        환경변수 MTD_IPTABLES_CHAIN 으로 오버라이드 가능.
    blacklist_file : str
        블랙리스트 상태를 저장할 JSON 파일 경로.
        환경변수 MTD_BLACKLIST_FILE 으로 오버라이드 가능.
    scripts_dir : str
        MTD 셔플 스크립트가 존재하는 디렉토리.
        환경변수 MTD_SCRIPTS_DIR 으로 오버라이드 가능.
    flush_on_start : bool
        True 이면 초기화 시 해당 체인의 규칙을 모두 플러시.
        환경변수 MTD_FLUSH_ON_START=1 이면 자동 활성화.
    """

    def __init__(
        self,
        iptables_chain: str = "DOCKER-USER",
        blacklist_file: str = "/shared/blacklist.json",
        scripts_dir: str = "/mtd_full_testbed/dvd_lite/dvd_attacks_lpc/mtd/scripts/",
        logger: logging.Logger = None,
        flush_on_start: bool = False,
    ):
        # 환경변수로 경로/체인 오버라이드
        env_chain = os.getenv("MTD_IPTABLES_CHAIN")
        if env_chain:
            iptables_chain = env_chain

        env_blacklist = os.getenv("MTD_BLACKLIST_FILE")
        if env_blacklist:
            blacklist_file = env_blacklist

        env_scripts = os.getenv("MTD_SCRIPTS_DIR")
        if env_scripts:
            scripts_dir = env_scripts

        self.logger = logger or logging.getLogger(__name__)
        self.chain = iptables_chain
        self.blacklist_file = blacklist_file
        self.scripts_dir = scripts_dir

        # 블랙리스트 상태: { "ip": "10.13.0.200", "banned_until": 1234567890.0, ... }
        self.blacklist_state: List[Dict[str, Any]] = []
        self.dnat_target_ip: str = ""
        self.dnat_target_port: int = 0

        self.flush_on_start = flush_on_start or os.getenv("MTD_FLUSH_ON_START", "0") == "1"

        os.makedirs(os.path.dirname(self.blacklist_file), exist_ok=True)

        self._load_blacklist()
        self._check_iptables_chain()
        if self.flush_on_start:
            self._clear_all_rules()

        self.logger.info(
            "IptablesController(v05) 초기화. "
            f"Chain={self.chain}, BlacklistFile={self.blacklist_file}, ScriptsDir={self.scripts_dir}"
        )

    # ------------------------------------------------------------------
    # 내부 유틸
    # ------------------------------------------------------------------
    def _run_cmd(self, cmd_list: List[str]) -> bool:
        """쉘 명령어 실행 헬퍼."""
        try:
            subprocess.run(
                cmd_list,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            return True
        except subprocess.CalledProcessError as e:
            self.logger.error(f"명령어 실행 실패: {' '.join(cmd_list)}")
            self.logger.error(f"  - STDOUT: {e.stdout.decode(errors='ignore')}")
            self.logger.error(f"  - STDERR: {e.stderr.decode(errors='ignore')}")
            return False
        except Exception as e:  # pragma: no cover - OS 예외
            self.logger.error(f"명령어 실행 중 예외: {e}")
            return False

    def _check_iptables_chain(self):
        """관리 대상 체인이 존재하는지 확인, 없으면 생성."""
        # iptables -L <CHAIN> -n
        if not self._run_cmd(["iptables", "-L", self.chain, "-n"]):
            self.logger.warning(f"iptables 체인 '{self.chain}' 없음. 새로 생성 시도...")
            # iptables -N <CHAIN>
            if not self._run_cmd(["iptables", "-N", self.chain]):
                self.logger.error(f"'{self.chain}' 체인 생성 실패. 'privileged' 권한 확인 필요.")
            # iptables -I DOCKER 1 -j <CHAIN> (DOCKER 체인 최상단에 연결)
            elif not self._run_cmd(["iptables", "-I", "DOCKER", "1", "-j", self.chain]):
                self.logger.error(f"'{self.chain}'을 DOCKER 체인에 연결 실패.")
            else:
                self.logger.info(f"'{self.chain}' 체인 생성 및 DOCKER에 연결 완료.")

    def _load_blacklist(self):
        """blacklist_file 에서 차단 목록 로드."""
        try:
            if os.path.exists(self.blacklist_file):
                with open(self.blacklist_file, "r", encoding="utf-8") as f:
                    self.blacklist_state = json.load(f)
            self.logger.info(f"{len(self.blacklist_state)}개의 블랙리스트 항목 로드 완료.")
        except Exception as e:  # pragma: no cover - 파일 손상 등
            self.logger.warning(f"블랙리스트 파일 로드 실패: {e}")
            self.blacklist_state = []

    def _save_blacklist(self):
        """현재 차단 목록을 JSON 파일에 저장."""
        try:
            with open(self.blacklist_file, "w", encoding="utf-8") as f:
                json.dump(self.blacklist_state, f, ensure_ascii=False, indent=2)
        except Exception as e:  # pragma: no cover
            self.logger.error(f"블랙리스트 파일 저장 실패: {e}")

    def _clear_all_rules(self):
        """이 컨트롤러가 관리하는 체인의 모든 규칙(DNAT, DROP)을 플러시."""
        self.logger.info(f"'{self.chain}' 체인의 모든 MTD 규칙 플러시(Flush) 중...")
        self._run_cmd(["iptables", "-F", self.chain])

        # 블랙리스트 상태도 초기화
        self.blacklist_state = []
        self._save_blacklist()

    # ------------------------------------------------------------------
    # 공개 API
    # ------------------------------------------------------------------
    # --- [1] DNAT 제어 ---
    def apply_dnat_redirect(self, target_ip: str, target_port: int, attacker_ip: str = "10.13.0.200"):
        """
        [핵심 실행 1] Seeker(Attacker)의 트래픽을 지정된 타겟으로 DNAT 리디렉션.

        Parameters
        ----------
        target_ip : str
            DNAT 대상 IP (예: "10.13.0.2")
        target_port : int
            DNAT 대상 포트 (예: 14550)
        attacker_ip : str
            공격자 컨테이너 IP (docker-compose-lite.yaml 상에서 정의)
        """
        if self.dnat_target_ip == target_ip and self.dnat_target_port == target_port:
            self.logger.info(f"DNAT 규칙이 이미 {target_ip}:{target_port}로 설정되어 있어 변경 없음.")
            return

        # 1. 기존 DNAT 규칙 삭제 (존재할 경우)
        if self.dnat_target_ip:
            self._run_cmd(
                [
                    "iptables",
                    "-D",
                    self.chain,
                    "-s",
                    attacker_ip,
                    "-j",
                    "DNAT",
                    "--to-destination",
                    f"{self.dnat_target_ip}:{self.dnat_target_port}",
                ]
            )
            self.logger.info(f"기존 DNAT 규칙 삭제: -> {self.dnat_target_ip}:{self.dnat_target_port}")

        # 2. 신규 DNAT 규칙 추가
        success = self._run_cmd(
            [
                "iptables",
                "-A",
                self.chain,
                "-s",
                attacker_ip,
                "-j",
                "DNAT",
                "--to-destination",
                f"{target_ip}:{target_port}",
            ]
        )

        if success:
            self.dnat_target_ip = target_ip
            self.dnat_target_port = target_port
            self.logger.info(f"신규 DNAT 규칙 적용: Attacker({attacker_ip}) -> {target_ip}:{target_port}")
        else:
            self.logger.error(f"신규 DNAT 규칙 적용 실패: {target_ip}:{target_port}")

    # --- [2] 셔플 스크립트 실행 ---
    def run_script(self, script_name: str):
        """
        [핵심 실행 2] mtd/scripts/ 하위의 쉘 스크립트를 실행.
        (예: mtd_service_swap.sh)
        """
        script_path = os.path.join(self.scripts_dir, script_name)
        if not os.path.exists(script_path):
            self.logger.error(f"실행할 스크립트 없음: {script_path}")
            return

        self.logger.info(f"MTD 스크립트 실행: {script_name}")
        # DNAT 규칙과 충돌할 수 있으므로, 셔플 전 DNAT 규칙 비활성화
        # (테스트베드에서는 루프백으로 임시 리디렉션)
        if self.dnat_target_ip:
            self.apply_dnat_redirect("127.0.0.1", 1)

        self._run_cmd(["bash", script_path])

        self.logger.info(f"스크립트 실행 완료: {script_name}")
        # 셔플 후 DNAT 상태가 불확실하므로, 다음 step에서 RL이 다시 결정하도록 초기화
        self.dnat_target_ip = ""
        self.dnat_target_port = 0

    # --- [3] 블랙리스트 제어 (RL v05) ---
    def update_blacklist(self, attacker_alerts: Dict[str, float], threshold: float, duration_sec: int):
        """
        [핵심 실행 3] CTI 경보 딕셔너리를 받아, RL의 임계값/기간 정책에 따라
        블랙리스트를 업데이트한다.

        Parameters
        ----------
        attacker_alerts : Dict[str, float]
            예: {"10.13.0.200": 0.8, "10.13.0.201": 0.3} (CTI가 탐지한 IP별 위협 점수)
        threshold : float
            (0.0~1.0) RL이 결정한 차단 임계값 (이 점수 *초과* 시 차단)
        duration_sec : int
            (초) RL이 결정한 차단 시간
            -1 이면 영구 차단 (테스트베드에서는 실험이 끝날 때까지 DROP 유지)
        """
        now = time.time()
        current_banned_ips: Set[str] = {entry["ip"] for entry in self.blacklist_state}
        newly_banned_ips: Set[str] = set()

        # 1. 신규 차단 IP 결정
        for ip, alert_score in attacker_alerts.items():
            if alert_score > threshold and ip not in current_banned_ips:
                ban_until = (now + duration_sec) if duration_sec != -1 else -1
                entry = {
                    "ip": ip,
                    "banned_until": ban_until,
                    "banned_at": now,
                    "reason_score": float(alert_score),
                }
                self.blacklist_state.append(entry)
                newly_banned_ips.add(ip)
                self.logger.warning(
                    f"블랙리스트 추가: IP={ip} (Score {alert_score:.2f} > Th {threshold:.2f}), "
                    f"Duration: {duration_sec}s (테스트베드 동안 공격 불가)"
                )

        # 2. 만료된 IP 제거
        expired_ips: Set[str] = set()
        active_blacklist: List[Dict[str, Any]] = []
        for entry in self.blacklist_state:
            ip = entry["ip"]
            banned_until = entry.get("banned_until", -1)
            if banned_until == -1 or banned_until > now:
                active_blacklist.append(entry)  # 유지
            else:
                expired_ips.add(ip)
                self.logger.info(f"블랙리스트 만료: IP={ip}")

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

        # 5. 상태 요약 로그
        self.logger.info(
            f"현재 활성 블랙리스트 IP 수: {len(self.blacklist_state)} "
            f"(추가={len(newly_banned_ips)}, 만료={len(expired_ips)})"
        )

    # ------------------------------------------------------------------
    # CTI/모니터링용 헬퍼
    # ------------------------------------------------------------------
    def get_active_blacklist(self) -> List[Dict[str, Any]]:
        """
        현재 활성화된(만료되지 않은) 블랙리스트 엔트리 목록을 반환.

        CtiAgentStatus 구현에서 이 메서드 또는 blacklist_file(JSON)을 읽어
        blacklist_size / 평균 차단시간 / 평균 공격 점수 등의 지표를 만들 수 있다.
        """
        now = time.time()
        active: List[Dict[str, Any]] = []
        for entry in self.blacklist_state:
            banned_until = entry.get("banned_until", -1)
            if banned_until == -1 or banned_until > now:
                active.append(entry)
        return active
