#!/usr/bin/env python3
"""
Multi‑action RL‑driven deception manager.

This module extends the basic MTD manager by allowing multiple
defensive actions to be executed simultaneously in response to a
threat.  Instead of choosing a single action such as IP shuffle or
port shuffle, the manager computes a multi‑binary action vector and
performs all actions indicated.  This better reflects the moving
target defense philosophy of concurrently changing several aspects of
the attack surface (IP, port, service) to maximize attacker
confusion.

The manager reads the current threat status from a CTI status JSON
file, applies a simple heuristic mapping from threat level to
multi‑action vector, and then invokes the appropriate iptables
commands via ``IptablesController``.  It also writes the updated
service port assignments to an MTD state file so that other modules
(e.g. monitoring, logging) can discover the current configuration.

This implementation is intentionally lightweight and rule‑based; in a
full RL setting, the multi‑action vector would come from a policy
network.  Nonetheless, it demonstrates how to carry out multiple
defensive actions in a single decision step.
"""

from __future__ import annotations

import json
import logging
import os
import random
import time
from dataclasses import dataclass
from typing import Dict, List, Tuple

from .cti_status_reader import CtiStatusReader
from .iptables_controller import IptablesController

logger = logging.getLogger("MultiActionMTDManager")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-7s] [MTDManager] %(message)s",
)


@dataclass
class ServiceConfig:
    """Configuration for a protected service."""
    name: str
    original_ip: str
    original_port: int
    decoy_ip: str
    port_pool: List[int]


class MultiActionDeceptionManager:
    """
    RL‑driven deception manager that can perform multiple MTD actions
    simultaneously.
    """

    def __init__(self,
                 services: Dict[str, ServiceConfig],
                 cti_status_path: str,
                 mtd_state_path: str,
                 dry_run: bool = True,
                 sleep_sec: float = 5.0) -> None:
        """
        :param services: Mapping of service names to ``ServiceConfig``
                         specifying original IP/port, decoy IP and
                         available port pool.
        :param cti_status_path: Path to the CTI status JSON file.
        :param mtd_state_path: Path where the current service port
                               assignments will be written.
        :param dry_run: If True, iptables commands are logged only.
        :param sleep_sec: Time to wait between checks of CTI status.
        """
        self.services = services
        self.cti_reader = CtiStatusReader(cti_status_path)
        self.mtd_state_path = mtd_state_path
        self.controller = IptablesController(dry_run=dry_run)
        self.sleep_sec = sleep_sec
        # Track the current port assignment for each service
        self.current_ports: Dict[str, int] = {
            name: cfg.original_port for name, cfg in services.items()
        }
        # Track used ports per service to avoid collisions
        self.used_ports: Dict[str, List[int]] = {
            name: [cfg.original_port] for name, cfg in services.items()
        }

    # ------------------------------------------------------------------
    # Action selection logic
    # ------------------------------------------------------------------
    def select_actions(self, threat_level: float, is_breach: bool) -> Dict[str, bool]:
        """
        Determine which MTD actions to perform given the threat level and breach flag.

        This heuristic maps a continuous threat level (0.0–1.0) to a
        dictionary of boolean flags indicating which actions should be
        executed.  If a breach has occurred, all actions are enabled.

        Actions include:
          * ip_shuffle: change the destination IP of the service to its decoy.
          * port_shuffle: change the destination port for the service.
          * service_swap: forward traffic to a decoy service at a decoy IP/port.
          * blacklist: block the attacker IP.

        Additional actions (e.g. decoy deployment) could be added later.
        """
        actions = {
            'ip_shuffle': False,
            'port_shuffle': False,
            'service_swap': False,
            'blacklist': False,
        }
        if is_breach:
            # If a breach has been detected, throw everything we have.
            for k in actions:
                actions[k] = True
            return actions
        # Otherwise decide based on threat level
        if threat_level > 0.7:
            # High threat: execute all defensive actions
            for k in actions:
                actions[k] = True
        elif threat_level > 0.4:
            # Medium threat: change IP and port, and blacklist attacker
            actions['ip_shuffle'] = True
            actions['port_shuffle'] = True
            actions['blacklist'] = True
        elif threat_level > 0.2:
            # Low threat: change port only
            actions['port_shuffle'] = True
        # else threat too low: no action
        return actions

    # ------------------------------------------------------------------
    # Action execution
    # ------------------------------------------------------------------
    def _choose_new_port(self, service_name: str) -> int:
        """Select an unused port for the given service from its pool."""
        cfg = self.services[service_name]
        available = [p for p in cfg.port_pool if p not in self.used_ports[service_name]]
        if not available:
            # reset used port list except the current one
            self.used_ports[service_name] = [self.current_ports[service_name]]
            available = [p for p in cfg.port_pool if p not in self.used_ports[service_name]]
        new_port = random.choice(available)
        self.used_ports[service_name].append(new_port)
        return new_port

    def _write_mtd_state(self) -> None:
        """Persist the current port assignments to the mtd_state file."""
        try:
            state = {name: port for name, port in self.current_ports.items()}
            os.makedirs(os.path.dirname(self.mtd_state_path), exist_ok=True)
            with open(self.mtd_state_path, 'w', encoding='utf-8') as f:
                json.dump(state, f)
        except Exception as e:
            logger.warning(f"Failed to write mtd_state.json: {e}")

    def perform_actions(self, actions: Dict[str, bool], status) -> None:
        """
        Execute the selected actions across all services.

        :param actions: Dictionary of action flags from select_actions().
        :param status: The current CTI status (used for blacklist).
        """
        for name, cfg in self.services.items():
            if actions.get('ip_shuffle'):
                # Map traffic destined for the service IP to the decoy IP
                logger.info(f"[Action] IP shuffle for {name}: {cfg.original_ip} -> {cfg.decoy_ip}")
                self.controller.shuffle_ip(cfg.original_ip, cfg.decoy_ip)
            if actions.get('port_shuffle'):
                new_port = self._choose_new_port(name)
                logger.info(f"[Action] Port shuffle for {name}: {self.current_ports[name]} -> {new_port}")
                # Redirect the old port to the new one
                self.controller.shuffle_port(self.current_ports[name], new_port)
                self.current_ports[name] = new_port
            if actions.get('service_swap'):
                # Swap the service to the decoy IP and port (if provided)
                decoy_port = None
                if cfg.decoy_ip:
                    logger.info(f"[Action] Service swap for {name}: port {self.current_ports[name]} to decoy {cfg.decoy_ip}")
                    self.controller.swap_service(self.current_ports[name], cfg.decoy_ip, decoy_port)
        # Write the new state
        self._write_mtd_state()
        # Apply blacklist after port/IP changes so the attacker cannot follow easily
        if actions.get('blacklist') and status.src_ip and status.src_ip != '0.0.0.0':
            logger.info(f"[Action] Blacklisting attacker IP: {status.src_ip}")
            self.controller.add_drop_rule(status.src_ip)

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------
    def run(self) -> None:
        """Continuously read CTI status and apply selected MTD actions."""
        logger.info("MultiAction MTD manager starting. Press Ctrl+C to stop.")
        try:
            while True:
                status = self.cti_reader.read_status()
                # Determine actions to take
                actions = self.select_actions(status.threat_level, status.is_attack and status.is_attack)
                # Only perform actions if any flag is True
                if any(actions.values()):
                    logger.info(f"[Decision] Executing actions {actions}")
                    self.perform_actions(actions, status)
                else:
                    logger.debug("[Decision] No action taken this cycle.")
                time.sleep(self.sleep_sec)
        except KeyboardInterrupt:
            logger.info("MultiAction MTD manager terminated.")


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Run the multi‑action RL MTD manager")
    parser.add_argument('--cti-status', type=str, default='mtd/shared_state/cti_status.json',
                        help='Path to CTI status JSON file')
    parser.add_argument('--mtd-state', type=str, default='mtd/shared_state/mtd_state.json',
                        help='Path to output MTD state JSON file')
    parser.add_argument('--dry-run', action='store_true', help='Log iptables commands instead of executing them')
    parser.add_argument('--sleep', type=float, default=5.0, help='Seconds between status checks')
    args = parser.parse_args()
    # Define service configurations.  In a real setup this would be loaded from a config file.
    services = {
        'mavlink': ServiceConfig(
            name='mavlink',
            original_ip='10.13.0.2',
            original_port=14550,
            decoy_ip='10.13.0.7',
            port_pool=list(range(14550, 14570))
        ),
        'web': ServiceConfig(
            name='web',
            original_ip='10.13.0.3',
            original_port=3000,
            decoy_ip='10.13.0.7',
            port_pool=list(range(3000, 3010))
        ),
    }
    manager = MultiActionDeceptionManager(
        services=services,
        cti_status_path=args.cti_status,
        mtd_state_path=args.mtd_state,
        dry_run=args.dry_run,
        sleep_sec=args.sleep
    )
    manager.run()


if __name__ == '__main__':
    main()