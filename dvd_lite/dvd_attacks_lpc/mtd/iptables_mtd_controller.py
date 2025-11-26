"""
iptables_mtd_controller.py
==========================

This module extends the base ``IptablesController`` with additional
Moving Target Defense (MTD) operations, including IP rotation, port
hopping and activation of an alternate communication channel.  These
methods are inspired by the original ``iptables_channel_switch.py``
example and expose a consistent API for the RL-driven deception
manager and other components.

The controller supports both dry‑run mode (for development) and
execution mode.  In dry‑run mode, commands are logged via the Python
``logging`` module instead of being executed.

Usage
-----

::

    from iptables_mtd_controller import IptablesMTDController
    ctl = IptablesMTDController(dry_run=False)
    ctl.rotate_ip(original_ip='10.13.0.2')
    ctl.rotate_port(old_port=14550, new_port=14560)
    ctl.activate_backup_channel(attacker_ip='10.13.0.200', gcs_ip='10.13.0.4', backup_ip='10.13.0.7')

"""

from __future__ import annotations

import logging
import random
from typing import List

from iptables_controller import IptablesController

logger = logging.getLogger(__name__)


class IptablesMTDController(IptablesController):
    """Extended iptables controller with additional MTD actions."""

    def __init__(self,
                 dry_run: bool = True,
                 target_ip: str = "10.13.0.2",
                 backup_ip: str = "10.13.0.7",
                 gcs_ip: str = "10.13.0.4",
                 attacker_ip_prefix: str = "10.13.0.200",
                 available_ports: List[int] | None = None) -> None:
        super().__init__(dry_run=dry_run)
        self.target_ip = target_ip
        self.backup_ip = backup_ip
        self.gcs_ip = gcs_ip
        self.attacker_ip_prefix = attacker_ip_prefix
        self.available_ports = available_ports or [14550, 14560, 14570, 14580]
        self.current_port = self.available_ports[0]

    # ------------------------------------------------------------------
    # High‑level MTD actions
    # ------------------------------------------------------------------
    def rotate_ip(self, original_ip: str | None = None, new_fake_last_octet: int | None = None) -> None:
        """
        Perform an IP shuffle by creating a new virtual IP (VIP) and
        forwarding traffic to the real target IP.  Optionally specify
        ``original_ip`` to flush only matching rules.  ``new_fake_last_octet``
        can be provided for deterministic testing; otherwise a random
        octet (10–90) is chosen.
        """
        vip_octet = new_fake_last_octet or random.randint(10, 90)
        vip_ip = f"10.13.0.{vip_octet}"
        logger.info(f"[MTD] Rotating IP: {original_ip or self.target_ip} -> {vip_ip}")
        # Flush NAT PREROUTING chain; in production, filter more selectively
        self._run_cmd(["iptables", "-t", "nat", "-F", "PREROUTING"])
        # DNAT: redirect traffic destined to VIP to the real target
        target = original_ip or self.target_ip
        self._run_cmd([
            "iptables", "-t", "nat", "-A", "PREROUTING",
            "-d", vip_ip, "-j", "DNAT", "--to-destination", target
        ])
        # SNAT: rewrite source of return packets
        self._run_cmd([
            "iptables", "-t", "nat", "-A", "POSTROUTING",
            "-s", target, "-j", "SNAT", "--to-source", vip_ip
        ])

    def rotate_port(self, old_port: int | None = None, new_port: int | None = None) -> None:
        """
        Perform a port hopping action by redirecting incoming traffic on
        ``new_port`` to the original service port (assumed 14550).  If
        ``old_port`` is provided, the PREROUTING chain is flushed before
        installing the new mapping.  When ``new_port`` is None, a random
        available port is chosen from ``available_ports`` that differs
        from the current port.
        """
        old_port = old_port or self.current_port
        if new_port is None:
            choices = [p for p in self.available_ports if p != self.current_port]
            new_port = random.choice(choices)
        logger.info(f"[MTD] Hopping port {old_port} -> {new_port}")
        # Flush existing PREROUTING rules
        self._run_cmd(["iptables", "-t", "nat", "-F", "PREROUTING"])
        # Redirect UDP traffic on new_port to the fixed service port (14550)
        self._run_cmd([
            "iptables", "-t", "nat", "-A", "PREROUTING",
            "-p", "udp", "--dport", str(new_port),
            "-j", "REDIRECT", "--to-port", "14550"
        ])
        self.current_port = new_port

    def activate_backup_channel(self,
                                attacker_ip: str | None = None,
                                gcs_ip: str | None = None,
                                backup_ip: str | None = None) -> None:
        """
        Activate an alternate communication channel when a critical threat
        is detected.  Drops all traffic from the attacker and redirects
        GCS traffic to a backup node.  You may override ``attacker_ip``,
        ``gcs_ip`` and ``backup_ip`` per invocation.
        """
        attacker = attacker_ip or self.attacker_ip_prefix
        gcs = gcs_ip or self.gcs_ip
        backup = backup_ip or self.backup_ip
        logger.warning("[MTD] Critical threat detected: activating backup channel")
        # Block attacker traffic
        self._run_cmd(["iptables", "-A", "INPUT", "-s", attacker, "-j", "DROP"])
        self._run_cmd(["iptables", "-A", "FORWARD", "-s", attacker, "-j", "DROP"])
        # Redirect GCS traffic to backup node
        self._run_cmd([
            "iptables", "-t", "nat", "-A", "PREROUTING",
            "-s", gcs, "-j", "DNAT", "--to-destination", backup
        ])
        logger.info(f"[MTD] GCS traffic from {gcs} redirected to backup node {backup}")
