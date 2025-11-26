#!/usr/bin/env python3
"""
rl_driven_deception_manager.py
===============================

This module implements a more complete RL-driven Moving Target Defense (MTD)
manager for the DVD testbed.  It is designed to be invoked either as a
stand-alone service that continuously monitors CTI status and QoS metrics or
as a one-shot command from the CTI agent to execute a specific strategy.

Key features:

* **CTI Status Integration**: Uses ``CtiStatusReader`` to ingest
  ``cti_status.json`` and extract attack indicators (is_attack,
  threat_level, src_ip, attack_name).  These values are used to build an
  observation vector for the RL policy.
* **Simple RL Policy**: A placeholder policy is included which makes
  decisions based on the threat level.  In a production deployment this
  would be replaced by a trained PPO or other RL model.
* **Iptables Controller**: Supports IP banning, IP shuffling, port shuffling
  and service swap using ``IptablesController``.  Actions are executed by
  modifying the local firewall rules.  A ``dry_run`` mode allows safe
  testing.
* **MTD State Persistence**: When an action modifies the service attack
  surface (e.g., port shuffle), the state is recorded to ``mtd_state.json``
  so that other components (like the Seeker) can discover the new attack
  surface.
* **Command-line Interface**: Allows forcing a specific strategy via the
  ``--strategy`` option or running a single observe-select-act iteration
  with ``--oneshot``.

This script is not intended to implement the full RL training loop; it is
focused on the deployment-time decision logic and integration with CTI
status and iptables.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import random
import time
from dataclasses import dataclass
from typing import Dict, Any

from cti_status_reader import CtiStatusReader, CtiStatus
from iptables_controller import IptablesController

logger = logging.getLogger("RLDeceptionManager")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-7s] [RL-Manager] %(message)s",
)

# Paths for shared state
DEFAULT_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
DEFAULT_SHARED_STATE = os.path.join(DEFAULT_PROJECT_ROOT, "mtd", "shared_state")
DEFAULT_STATUS_PATH = os.path.join(DEFAULT_SHARED_STATE, "cti_status.json")
DEFAULT_MTD_STATE_PATH = os.path.join(DEFAULT_SHARED_STATE, "mtd_state.json")

# Service configuration
SERVICE_PORTS = {
    "mavlink": 14550,
    "sitl": 5760,
    "web": 3000,
    "rtsp": 554,
    "ros": 11311,
}

# Decoy IP used for service swap and IP shuffle
DECOY_IP = "10.13.0.7"


@dataclass
class ActionResult:
    """Encapsulates the result of an MTD action."""
    action: str
    details: Dict[str, Any]


class RLDrivenDeceptionManager:
    """RL-driven MTD manager with simple heuristic policy."""

    def __init__(self,
                 status_path: str = DEFAULT_STATUS_PATH,
                 mtd_state_path: str = DEFAULT_MTD_STATE_PATH,
                 dry_run: bool = False) -> None:
        self.status_reader = CtiStatusReader(status_path)
        self.mtd_state_path = mtd_state_path
        self.iptables = IptablesController(dry_run=dry_run)
        self.port_assignments: Dict[str, int] = SERVICE_PORTS.copy()

    # ------------------------------------------------------------------
    # Observation and policy
    # ------------------------------------------------------------------
    def build_observation(self) -> Dict[str, float]:
        """Construct an observation from CTI status."""
        status: CtiStatus = self.status_reader.read_status()
        return {
            'threat_level': status.threat_level,
            'is_attack': 1.0 if status.is_attack else 0.0,
        }

    def select_action(self, observation: Dict[str, float]) -> str:
        """Heuristic policy mapping threat level to an action."""
        threat = observation['threat_level']
        if threat > 0.8:
            return 'ip_shuffle'
        if threat > 0.5:
            return 'service_swap'
        if threat > 0.2:
            return 'port_shuffle'
        return 'no_action'

    # ------------------------------------------------------------------
    # Helper methods
    # ------------------------------------------------------------------
    def _choose_unused_port(self) -> int:
        """Select a random port not currently assigned to any service."""
        used_ports = set(self.port_assignments.values())
        while True:
            candidate = random.randint(20000, 30000)
            if candidate not in used_ports:
                return candidate

    def _save_mtd_state(self) -> None:
        """
        Write the current port assignment mapping to the MTD state file.  Other
        components (e.g., the Seeker) can consult this file to know which
        ports to target.
        """
        try:
            os.makedirs(os.path.dirname(self.mtd_state_path), exist_ok=True)
            with open(self.mtd_state_path, 'w', encoding='utf-8') as f:
                json.dump(self.port_assignments, f)
            logger.debug(f"Saved MTD state: {self.port_assignments}")
        except Exception as e:
            logger.error(f"Failed to write MTD state file: {e}")

    # ------------------------------------------------------------------
    # Action implementations
    # ------------------------------------------------------------------
    def perform_no_action(self) -> ActionResult:
        logger.info("No MTD action taken.")
        return ActionResult(action='no_action', details={})

    def perform_port_shuffle(self) -> ActionResult:
        """Shuffle the port for a randomly selected service."""
        service = random.choice(list(self.port_assignments.keys()))
        old_port = self.port_assignments[service]
        new_port = self._choose_unused_port()
        self.port_assignments[service] = new_port
        self.iptables.shuffle_port(old_port, new_port)
        logger.info(f"Shuffled {service} from port {old_port} to {new_port}")
        self._save_mtd_state()
        return ActionResult(action='port_shuffle', details={'service': service, 'old_port': old_port, 'new_port': new_port})

    def perform_ip_shuffle(self) -> ActionResult:
        """Redirect traffic for a service from its original IP to a decoy IP."""
        service = 'mavlink'
        original_ip = '10.13.0.2'
        self.iptables.shuffle_ip(original_ip, DECOY_IP)
        logger.info(f"Shuffled IP for {service} from {original_ip} to {DECOY_IP}")
        return ActionResult(action='ip_shuffle', details={'service': service, 'old_ip': original_ip, 'new_ip': DECOY_IP})

    def perform_service_swap(self) -> ActionResult:
        """Swap an existing service to a decoy implementation via DNAT."""
        service = 'web'
        port = self.port_assignments[service]
        self.iptables.swap_service(port, DECOY_IP)
        logger.info(f"Swapped {service} service on port {port} to decoy {DECOY_IP}")
        return ActionResult(action='service_swap', details={'service': service, 'port': port, 'decoy_ip': DECOY_IP})

    def perform_action(self, action: str) -> ActionResult:
        """Dispatch the selected action to its handler."""
        if action == 'port_shuffle':
            return self.perform_port_shuffle()
        if action == 'ip_shuffle':
            return self.perform_ip_shuffle()
        if action == 'service_swap':
            return self.perform_service_swap()
        return self.perform_no_action()

    # ------------------------------------------------------------------
    # Execution loop
    # ------------------------------------------------------------------
    def run_once(self) -> ActionResult:
        """Run one observe-select-act cycle and return the result."""
        obs = self.build_observation()
        action = self.select_action(obs)
        return self.perform_action(action)


def main() -> None:
    parser = argparse.ArgumentParser(description="RL-driven MTD manager")
    parser.add_argument('--status-path', type=str, default=DEFAULT_STATUS_PATH, help='Path to CTI status file')
    parser.add_argument('--mtd-state-path', type=str, default=DEFAULT_MTD_STATE_PATH, help='Path to MTD state file')
    parser.add_argument('--strategy', type=str, default=None, help='Force execution of a specific strategy')
    parser.add_argument('--dry-run', action='store_true', help='Log iptables commands instead of executing them')
    parser.add_argument('--oneshot', action='store_true', help='Execute a single cycle and exit')
    args = parser.parse_args()

    manager = RLDrivenDeceptionManager(status_path=args.status_path,
                                       mtd_state_path=args.mtd_state_path,
                                       dry_run=args.dry_run)
    if args.strategy:
        logger.info(f"Executing forced strategy: {args.strategy}")
        manager.perform_action(args.strategy)
        return
    if args.oneshot:
        manager.run_once()
        return
    logger.info("Starting RL MTD manager loop. Press Ctrl+C to exit.")
    try:
        while True:
            result = manager.run_once()
            logger.debug(f"Action result: {result}")
            time.sleep(5)
    except KeyboardInterrupt:
        logger.info("RL MTD manager terminated.")


if __name__ == '__main__':
    main()