#!/usr/bin/env python3
"""
seeker.py
==========

This module implements a simple heuristic seeker (attacker) that
interacts with the Moving Target Defense (MTD) environment.  Unlike
reinforcement learning agents, this seeker follows a fixed set of
heuristics to discover the current attack surface and attempt to
penetrate the defended drone system.  It is intended for use both
within the simulated environment during RL training and in the
evaluation setting to stress test MTD strategies.

Key features
------------

* **Configuration aware**: Reads ``attacker_config.json`` to learn
  baseline target IPs and ports.  Supports default values when
  configuration is missing.
* **MTD state integration**: Consults ``mtd_state.json`` (produced by
  the MTD manager) to discover any port reassignments.  If the file
  is absent or stale, falls back to known defaults.
* **Heuristic attack loop**: Repeatedly attempts to connect to the
  MAVLink service on the current port.  On failure, performs a simple
  port scan over a candidate range and updates its internal state.
* **Logging and metrics**: Reports actions to the console or logger
  instead of executing real exploitation code.  This makes it safe to
  run in development environments without connecting to a real drone.

Usage
-----

The seeker can be invoked directly as a stand‑alone script.

::

    python3 seeker.py --config ../../config/attacker_config.json \
        --mtd-state ../../mtd/shared_state/mtd_state.json

In an RL training environment, the seeker would be instantiated by
the environment wrapper and its ``step()`` method called at each
time step.  In evaluation, the main loop runs until interrupted.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import random
import socket
import time
from dataclasses import dataclass
from typing import Dict, Optional

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
    """A simple heuristic attacker for the MTD testbed."""

    def __init__(self,
                 config_path: str = "attacker_config.json",
                 mtd_state_path: str = "mtd_state.json",
                 service_name: str = "mavlink",
                 scan_range: range = range(14500, 14600),
                 connect_timeout: float = 1.0,
                 use_mtd_state: bool = False) -> None:
        self.config_path = config_path
        self.mtd_state_path = mtd_state_path
        self.service_name = service_name
        self.scan_range = scan_range
        self.connect_timeout = connect_timeout
        self.use_mtd_state = use_mtd_state
        self.targets: Dict[str, TargetService] = {}
        self.current_port: Optional[int] = None
        self._load_config()

    def _load_config(self) -> None:
        """Load attacker configuration from JSON."""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            tgt_ip = data['targets'].get('TARGET_FC', '10.13.0.2')
            mav_port = int(data['ports'].get('PORT_MAVLINK', 14550))
            self.targets[self.service_name] = TargetService(self.service_name, tgt_ip, mav_port)
        except Exception as e:
            logger.warning(f"Failed to load attacker_config.json: {e}; using defaults")
            self.targets[self.service_name] = TargetService(self.service_name, '10.13.0.2', 14550)
        self.current_port = self.targets[self.service_name].port

    def _read_mtd_state(self) -> None:
        """Update the current port from the MTD state file if present."""
        try:
            if self.use_mtd_state and os.path.exists(self.mtd_state_path):
                with open(self.mtd_state_path, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                if self.service_name in state:
                    port = int(state[self.service_name])
                    if port != self.current_port:
                        logger.info(f"[MTD] Detected port change: {self.current_port} -> {port}")
                        self.current_port = port
        except Exception as e:
            logger.debug(f"Error reading MTD state: {e}")

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
        """Scan a range of ports and return the first responsive port."""
        random_ports = list(self.scan_range)
        random.shuffle(random_ports)
        for port in random_ports:
            if self._attempt_connect(ip, port):
                logger.info(f"[Scan] Found open port {port} on {ip}")
                return port
        return None

    def attack_service(self) -> None:
        """Attempt to connect to the service, updating port if necessary."""
        target = self.targets[self.service_name]
        self._read_mtd_state()
        port = self.current_port or target.port
        success = self._attempt_connect(target.ip, port)
        if success:
            logger.info(f"[Attack] Successfully connected to {target.name} on {target.ip}:{port}")
        else:
            logger.warning(f"[Attack] Connection to {target.ip}:{port} failed; scanning for new port")
            new_port = self.scan_ports(target.ip)
            if new_port:
                logger.info(f"[Attack] Updated target port to {new_port}")
                self.current_port = new_port
            else:
                logger.error(f"[Attack] Could not find open port in scan range")

    def run(self, interval: float = 5.0) -> None:
        """Main loop: repeatedly attempt to attack the target service."""
        logger.info("Starting heuristic seeker. Press Ctrl+C to stop.")
        try:
            while True:
                self.attack_service()
                time.sleep(interval)
        except KeyboardInterrupt:
            logger.info("Heuristic seeker terminated.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Heuristic seeker for MTD testbed")
    parser.add_argument('--config', type=str, default="attacker_config.json",
                        help='Path to attacker configuration JSON file')
    parser.add_argument('--mtd-state', type=str, default="mtd_state.json",
                        help='Path to MTD state JSON file')
    parser.add_argument('--interval', type=float, default=5.0, help='Seconds between attack attempts')
    parser.add_argument('--scan-start', type=int, default=14500, help='Start of scan port range')
    parser.add_argument('--scan-end', type=int, default=14600, help='End of scan port range (exclusive)')
    args = parser.parse_args()
    seeker = HeuristicSeeker(config_path=args.config,
                             mtd_state_path=args.mtd_state,
                             scan_range=range(args.scan_start, args.scan_end))
    seeker.run(interval=args.interval)


if __name__ == '__main__':
    main()