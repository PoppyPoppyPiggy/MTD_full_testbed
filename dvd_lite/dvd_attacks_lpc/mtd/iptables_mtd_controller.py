#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
iptables_mtd_controller.py
==========================
Advanced Network MTD Controller using Linux iptables.

이 컨트롤러는 실제 네트워크 환경(Docker, VM 등)에서 다음과 같은 MTD 기능을 수행합니다:
1. IP Shuffling (Virtual IP Mapping)
2. Port Hopping (Virtual Port Mapping)
3. Service Swapping (Decoy Redirection)

특징:
- 설정된 IP/Port 풀 내에서 무작위로 가상 주소를 할당합니다.
- 모든 변경 사항은 감사 로그(mtd_audit.log)에 "Real -> Virtual" 형식으로 기록됩니다.
- MTD 전용 체인(MTD-DNAT / MTD-SNAT)을 생성하여 기존 규칙과 분리 관리합니다.
"""

from __future__ import annotations

import logging
import random
import datetime
from typing import Dict, Optional, Tuple

from .iptables_controller import IptablesController

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("mtd_system.log", mode="a"),
    ],
)
logger = logging.getLogger("IptablesMTD")

# 기본 타겟 설정 (사용자가 제공한 정보 기반)
DEFAULT_TARGETS = {
    "FC": {"ip": "10.13.0.2", "ports": [14550]},          # Flight Controller (MAVLink)
    "CC": {"ip": "10.13.0.3", "ports": [3000, 14550]},    # Companion Computer (Web, MAVLink)
    "GCS": {"ip": "10.13.0.4", "ports": [14550]},         # Ground Control Station
    "SIM": {"ip": "10.13.0.5", "ports": [5760, 11311]},   # Simulator (SITL, ROS)
    "DECOY": {"ip": "10.13.0.7", "ports": [14550, 3000]}, # Decoy Container (MAVLink, Web)
}


class IptablesMTDController(IptablesController):
    """
    MTD 액션을 수행하고 상태를 관리하는 상위 컨트롤러.

    - register_service() 로 Real 서비스 등록
    - shuffle_network() 로 VIP/VPort 셔플
    - enable_decoy()/disable_decoy() 로 서비스 스왑(Decoy 리다이렉션)
    - block_attacker() 로 공격자 소스 IP 차단
    """

    def __init__(
        self,
        dry_run: bool = False,
        audit_file: str = "mtd_audit.log",
        vip_range: Tuple[str, int, int] = ("10.13.0", 100, 199),
        # 10.13.0.100 ~ 10.13.0.199
        vport_range: Tuple[int, int] = (20000, 21000),  # 20000 ~ 21000 (1000 ports)
    ) -> None:
        super().__init__(dry_run=dry_run)

        self.audit_file = audit_file
        self.vip_prefix, self.vip_start, self.vip_end = vip_range
        self.vport_start, self.vport_end = vport_range

        # 현재 매핑 상태 저장소
        # 구조: {
        #   "service_name": {
        #       "target_key": str,
        #       "real_ip": str, "real_port": int,
        #       "virtual_ip": str, "virtual_port": int,
        #       "decoy_active": bool
        #   }
        # }
        self.state: Dict[str, Dict] = {}

        # 초기화: 기존 MTD 규칙 제거 및 체인 생성
        self._initialize_chains()
        self._log_audit("MTD Controller Initialized. Chains prepared.")

    # ------------------------------------------------------------------
    # 내부 유틸
    # ------------------------------------------------------------------
    def _initialize_chains(self) -> None:
        """MTD 전용 iptables 체인을 생성하고 초기화합니다."""
        chains = ["MTD-DNAT", "MTD-SNAT"]

        for chain in chains:
            # 체인이 없으면 생성 (에러 무시) 후 플러시
            self._run_cmd(["iptables", "-t", "nat", "-N", chain], ignore_errors=True)
            self._run_cmd(["iptables", "-t", "nat", "-F", chain], ignore_errors=False)

        # PREROUTING에 MTD-DNAT 연결 (최상단)
        self._run_cmd(["iptables", "-t", "nat", "-I", "PREROUTING", "1", "-j", "MTD-DNAT"], ignore_errors=True)
        # POSTROUTING에 MTD-SNAT 연결
        self._run_cmd(["iptables", "-t", "nat", "-I", "POSTROUTING", "1", "-j", "MTD-SNAT"], ignore_errors=True)

        # 기본 SNAT/MASQUERADE 설정 (테스트 용도: 전체 트래픽에 대해 단순 Masquerade)
        self._run_cmd(["iptables", "-t", "nat", "-F", "MTD-SNAT"], ignore_errors=True)
        self._run_cmd(["iptables", "-t", "nat", "-A", "MTD-SNAT", "-j", "MASQUERADE"], ignore_errors=True)

    def _get_random_vip(self) -> str:
        """설정된 범위 내에서 사용 가능한 랜덤 가상 IP를 생성합니다."""
        octet = random.randint(self.vip_start, self.vip_end)
        return f"{self.vip_prefix}.{octet}"

    def _get_random_vport(self) -> int:
        """설정된 범위 내에서 랜덤 가상 포트를 생성합니다."""
        return random.randint(self.vport_start, self.vport_end)

    def _log_audit(self, message: str, mapping: Optional[Dict] = None) -> None:
        """사용자가 확인할 수 있는 감사 로그를 파일에 기록합니다."""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}"

        if mapping:
            log_entry += (
                f"\n    >> Real({mapping['real_ip']}:{mapping['real_port']})"
                f" <==> Virtual({mapping['virtual_ip']}:{mapping['virtual_port']})"
            )
            if mapping.get("decoy_active"):
                log_entry += " [⚠️ DECOY ACTIVE]"

        with open(self.audit_file, "a", encoding="utf-8") as f:
            f.write(log_entry + "\n")

        print(log_entry)

    # ------------------------------------------------------------------
    # 공개 API
    # ------------------------------------------------------------------
    def register_service(self, name: str, target_key: str, port_idx: int = 0) -> None:
        """
        관리할 서비스를 등록합니다.

        Args:
            name: 서비스 식별자 (예: "fc_mavlink")
            target_key: DEFAULT_TARGETS의 키 (예: "FC")
            port_idx: 해당 타겟의 포트 리스트 인덱스
        """
        if target_key not in DEFAULT_TARGETS:
            logger.error(f"Target key {target_key} not found in DEFAULT_TARGETS.")
            return

        target = DEFAULT_TARGETS[target_key]
        real_ip = target["ip"]
        real_port = target["ports"][port_idx]

        self.state[name] = {
            "target_key": target_key,
            "real_ip": real_ip,
            "real_port": real_port,
            "virtual_ip": real_ip,   # 초기에는 VIP 없음 (Passthrough)
            "virtual_port": real_port,
            "decoy_active": False,
        }
        logger.info(f"Service registered: {name} -> {real_ip}:{real_port}")

    def shuffle_network(self, name: str, intensity: float = 1.0) -> None:
        """
        지정된 서비스에 대해 IP 및 Port 셔플을 수행합니다.

        Args:
            name: 서비스 이름
            intensity: 셔플 강도 (0.0 ~ 1.0). 높을수록 IP와 Port가 모두 바뀔 확률이 큼.
        """
        if name not in self.state:
            logger.warning(f"Service {name} not registered.")
            return

        svc = self.state[name]

        new_vip = svc["virtual_ip"]
        new_vport = svc["virtual_port"]

        # IP 변경
        if random.random() < float(intensity):
            new_vip = self._get_random_vip()

        # Port 변경
        if random.random() < float(intensity):
            new_vport = self._get_random_vport()

        svc["virtual_ip"] = new_vip
        svc["virtual_port"] = new_vport

        self._apply_rules(name)
        self._log_audit(f"MTD Shuffle Executed for [{name}]", svc)

    def enable_decoy(self, name: str) -> None:
        """
        해당 서비스로 가는 트래픽을 디코이 컨테이너로 리다이렉션합니다 (Service Swap).
        """
        if name not in self.state:
            logger.warning(f"Service {name} not registered.")
            return

        svc = self.state[name]
        svc["decoy_active"] = True

        self._apply_rules(name)
        self._log_audit(f"⚠️ DECOY Activated for [{name}] - Traffic Hijacked!", svc)

    def disable_decoy(self, name: str) -> None:
        """디코이 해제, 정상 서비스로 복구."""
        if name not in self.state:
            logger.warning(f"Service {name} not registered.")
            return

        svc = self.state[name]
        svc["decoy_active"] = False

        self._apply_rules(name)
        self._log_audit(f"Decoy Deactivated for [{name}] - Service Restored", svc)

    def block_attacker(self, attacker_ip: str) -> None:
        """특정 공격자 IP 영구 차단."""
        self._run_cmd(["iptables", "-A", "INPUT", "-s", attacker_ip, "-j", "DROP"])
        self._log_audit(f"🚫 Attacker Blocked: {attacker_ip}")

    def get_mapping_info(self) -> str:
        """현재 매핑 정보를 문자열로 반환 (디버깅/RL 관측용)."""
        info = "Current MTD Mappings:\n"
        for name, data in self.state.items():
            target = "DECOY" if data["decoy_active"] else "REAL"
            info += (
                f" - {name}: {data['virtual_ip']}:{data['virtual_port']}"
                f" -> {data['real_ip']}:{data['real_port']} ({target})\n"
            )
        return info

    # ------------------------------------------------------------------
    # iptables 적용 로직
    # ------------------------------------------------------------------
    def _apply_rules(self, name: str) -> None:
        """
        현재 상태(self.state)를 기반으로 실제 iptables 규칙을 생성하여 적용합니다.

        간단한 프로토타입 구현:
        - MTD-DNAT 체인을 플러시하고
        - 해당 서비스의 VIP:VPort -> Real/Decoy 리다이렉션 규칙만 다시 추가.
        """
        svc = self.state[name]

        # 목적지 결정 (디코이 활성 여부에 따라)
        if svc["decoy_active"]:
            dest_ip = DEFAULT_TARGETS["DECOY"]["ip"]
        else:
            dest_ip = svc["real_ip"]

        dest_port = svc["real_port"]  # 디코이 포트도 동일하다고 가정
        vip = svc["virtual_ip"]
        vport = svc["virtual_port"]

        # 1. 이전 DNAT 규칙 초기화 (프로토타입: 체인 전체 플러시)
        self._run_cmd(["iptables", "-t", "nat", "-F", "MTD-DNAT"], ignore_errors=True)

        # 2. TCP DNAT Rule (Virtual -> Real/Decoy)
        dnat_cmd_tcp = [
            "iptables", "-t", "nat", "-A", "MTD-DNAT",
            "-p", "tcp",
            "-d", vip, "--dport", str(vport),
            "-j", "DNAT", "--to-destination", f"{dest_ip}:{dest_port}",
        ]
        self._run_cmd(dnat_cmd_tcp)

        # 3. UDP DNAT Rule (Virtual -> Real/Decoy)
        dnat_cmd_udp = [
            "iptables", "-t", "nat", "-A", "MTD-DNAT",
            "-p", "udp",
            "-d", vip, "--dport", str(vport),
            "-j", "DNAT", "--to-destination", f"{dest_ip}:{dest_port}",
        ]
        self._run_cmd(dnat_cmd_udp)


if __name__ == "__main__":
    # 간단 테스트 실행 (dry_run=True 이므로 iptables는 실제로는 변경되지 않음)
    ctl = IptablesMTDController(dry_run=True)

    # 서비스 등록: FC / MAVLink → fc_mavlink
    ctl.register_service("fc_mavlink", "FC", 0)

    print("\n--- [Test 1] Shuffling IP & Port ---")
    ctl.shuffle_network("fc_mavlink", intensity=1.0)

    print("\n--- [Test 2] Activating Decoy ---")
    ctl.enable_decoy("fc_mavlink")

    print("\n--- Current Status ---")
    print(ctl.get_mapping_info())
