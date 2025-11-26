#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
seeker.py
==========

Heuristic (blind) attacker for the MTD testbed.

이 모듈은 Moving Target Defense(MTD) 환경에서 동작하는
간단한 휴리스틱 공격자(Seeker)를 구현합니다. 강화학습 기반
공격자와 달리, 이 Seeker는 고정된 전략에 따라 포트를 스캔하고
MAVLink 서비스에 연결을 시도하는 역할만 수행합니다.

주요 특징
--------

* 설정 파일 인식 (Configuration aware)
  - ``attacker_config.json`` 에서 기본 타겟 IP/포트를 읽어옵니다.
* 블라인드 포트 스캔 (Blind port scan)
  - MTD 상태 파일(mtd_state.json)을 읽지 않고, 지정된 범위 내에서
    무작위 포트 스캔으로 서비스 포트를 찾습니다.
* 안전한 개발용 공격자
  - 실제 익스플로잇 코드를 실행하지 않고, TCP 연결 시도 및 로그 기록만
    수행하므로 개발/테스트 환경에서 안전하게 사용할 수 있습니다.

사용 예시
--------

독립 실행형으로 사용:

    python3 seeker.py --config ../../config/attacker_config.json \
        --scan-start 1024 --scan-end 65535
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import socket
import time
from dataclasses import dataclass
from typing import Dict, Optional, Range

logger = logging.getLogger("HeuristicSeeker")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-7s] [Seeker] %(message)s",
)


@dataclass
class TargetService:
    name: str
    ip: str
    port: int


class HeuristicSeeker:
    """A simple blind heuristic attacker for the MTD testbed."""

    def __init__(
        self,
        config_path: str = "attacker_config.json",
        service_name: str = "mavlink",
        scan_range: range = range(1024, 65536),
        connect_timeout: float = 1.0,
    ) -> None:
        self.config_path = config_path
        self.service_name = service_name
        self.scan_range = scan_range
        self.connect_timeout = connect_timeout

        self.targets: Dict[str, TargetService] = {}
        self.current_port: Optional[int] = None

        # 내부 통계 (필요하면 RL/로그에 활용 가능)
        self.scan_attempts: int = 0
        self.connect_success: int = 0
        self.connect_fail: int = 0

        self._load_config()

    # ------------------------------------------------------------------
    # 설정 로딩
    # ------------------------------------------------------------------
    def _load_config(self) -> None:
        """Load attacker configuration from JSON."""
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            tgt_ip = data["targets"].get("TARGET_FC", "10.13.0.2")
            mav_port = int(data["ports"].get("PORT_MAVLINK", 14550))
            self.targets[self.service_name] = TargetService(
                self.service_name, tgt_ip, mav_port
            )
            logger.info(
                f"Loaded config: {self.service_name} -> {tgt_ip}:{mav_port} (baseline)"
            )
        except Exception as e:
            logger.warning(
                f"Failed to load attacker_config.json: {e}; using defaults 10.13.0.2:14550"
            )
            self.targets[self.service_name] = TargetService(
                self.service_name, "10.13.0.2", 14550
            )
        self.current_port = self.targets[self.service_name].port

    # ------------------------------------------------------------------
    # 네트워크 동작
    # ------------------------------------------------------------------
    def _attempt_connect(self, ip: str, port: int) -> bool:
        """Attempt to open a TCP connection to the given (ip, port)."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(self.connect_timeout)
            try:
                sock.connect((ip, port))
                return True
            except Exception:
                return False

    def scan_ports(self, ip: str) -> Optional[int]:
        """
        Scan a range of ports and return the first responsive port.

        NOTE:
        - MTD 상태 파일을 사용하지 않고, 순수 포트 스캔에만 의존합니다.
        - scan_range 기본값은 1024~65535이며, CLI 인자로 재정의할 수 있습니다.
        """
        random_ports = list(self.scan_range)
        random.shuffle(random_ports)

        for port in random_ports:
            self.scan_attempts += 1
            if self._attempt_connect(ip, port):
                logger.info(f"[Scan] Found open port {port} on {ip}")
                return port
        return None

    # ------------------------------------------------------------------
    # 공격 루프
    # ------------------------------------------------------------------
    def attack_service(self) -> None:
        """
        Attempt to connect to the service, updating the port if necessary.

        - 현재 알고 있는 포트(self.current_port)로 먼저 시도
        - 실패하면 scan_range 내에서 블라인드 포트 스캔 수행
        """
        target = self.targets[self.service_name]
        port = self.current_port or target.port

        success = self._attempt_connect(target.ip, port)
        if success:
            self.connect_success += 1
            logger.info(
                f"[Attack] Successfully connected to {target.name} on {target.ip}:{port}"
            )
        else:
            self.connect_fail += 1
            logger.warning(
                f"[Attack] Connection to {target.ip}:{port} failed; scanning for new port"
            )
            new_port = self.scan_ports(target.ip)
            if new_port:
                logger.info(f"[Attack] Updated target port to {new_port}")
                self.current_port = new_port
            else:
                logger.error(
                    "[Attack] Could not find open port in scan range "
                    f"({self.scan_range.start}-{self.scan_range.stop - 1})"
                )

    def run(self, interval: float = 5.0) -> None:
        """Main loop: repeatedly attempt to attack the target service."""
        logger.info("Starting blind heuristic seeker. Press Ctrl+C to stop.")
        try:
            while True:
                self.attack_service()
                time.sleep(interval)
        except KeyboardInterrupt:
            logger.info(
                f"Heuristic seeker terminated. "
                f"Stats: success={self.connect_success}, fail={self.connect_fail}, scans={self.scan_attempts}"
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Blind heuristic seeker for MTD testbed")
    parser.add_argument(
        "--config",
        type=str,
        default="attacker_config.json",
        help="Path to attacker configuration JSON file",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=5.0,
        help="Seconds between attack attempts",
    )
    parser.add_argument(
        "--scan-start",
        type=int,
        default=1024,
        help="Start of scan port range",
    )
    parser.add_argument(
        "--scan-end",
        type=int,
        default=65536,
        help="End of scan port range (exclusive)",
    )
    args = parser.parse_args()

    seeker = HeuristicSeeker(
        config_path=args.config,
        scan_range=range(args.scan_start, args.scan_end),
    )
    seeker.run(interval=args.interval)


if __name__ == "__main__":
    main()
