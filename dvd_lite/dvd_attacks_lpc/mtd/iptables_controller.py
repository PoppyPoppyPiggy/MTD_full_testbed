"""
Minimal iptables controller for demonstration purposes.

This controller abstracts basic iptables operations used by the MTD
manager.  In a production system, this module would build and execute
actual iptables commands via subprocess.  For safety and portability
during development, the default implementation logs intended actions
instead of modifying the system firewall.
"""

import logging
from typing import List

logger = logging.getLogger(__name__)


class IptablesController:
    """Controller for managing iptables rules."""
    def __init__(self, dry_run: bool = True) -> None:
        self.dry_run = dry_run

    def _run_cmd(self, cmd: List[str]) -> None:
        """Run or log the iptables command depending on dry_run."""
        if self.dry_run:
            logger.info(f"[DryRun] iptables command: {' '.join(cmd)}")
        else:
            import subprocess
            subprocess.run(cmd, check=True)

    def add_drop_rule(self, ip: str) -> None:
        """Add a rule to drop traffic from the specified IP."""
        cmd = ["iptables", "-A", "INPUT", "-s", ip, "-j", "DROP"]
        self._run_cmd(cmd)

    def remove_drop_rule(self, ip: str) -> None:
        """Remove a previously added drop rule for the specified IP."""
        cmd = ["iptables", "-D", "INPUT", "-s", ip, "-j", "DROP"]
        self._run_cmd(cmd)

    def shuffle_port(self, original_port: int, new_port: int) -> None:
        """Redirect traffic from original_port to new_port (DNAT)."""
        cmd = ["iptables", "-t", "nat", "-A", "PREROUTING",
               "-p", "tcp", "--dport", str(original_port),
               "-j", "REDIRECT", "--to-port", str(new_port)]
        self._run_cmd(cmd)

    def shuffle_ip(self, src_ip: str, dest_ip: str) -> None:
        """Redirect traffic from src_ip to dest_ip (DNAT)."""
        cmd = ["iptables", "-t", "nat", "-A", "PREROUTING",
               "-s", src_ip, "-j", "DNAT", "--to-destination", dest_ip]
        self._run_cmd(cmd)