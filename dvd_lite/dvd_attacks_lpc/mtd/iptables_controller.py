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
        """
        Redirect traffic from ``original_port`` to ``new_port`` using NAT.

        In a production environment, this sets up a REDIRECT rule so that
        incoming TCP traffic on the original port is sent to the new port on
        the same host.  If ``dry_run`` is True, the command is only logged.
        """
        cmd = [
            "iptables", "-t", "nat", "-A", "PREROUTING",
            "-p", "tcp", "--dport", str(original_port),
            "-j", "REDIRECT", "--to-port", str(new_port)
        ]
        self._run_cmd(cmd)

    def shuffle_address(self, original_ip: str, original_port: int,
                        new_ip: str, new_port: int) -> None:
        """
        Shuffle both the destination IP and port of an incoming connection.

        This helper performs a combined IP/port shuffle by first
        redirecting traffic arriving on ``original_port`` to ``new_port`` on the local
        host and then rewriting the destination IP to ``new_ip``.  In effect,
        it makes services appear to have moved to a completely different network
        location.

        :param original_ip: The old VIP or service IP to match.
        :param original_port: The original port number for the service.
        :param new_ip: The new IP address to redirect traffic to.
        :param new_port: The new port number to redirect traffic to.
        """
        # Shuffle the port: change incoming traffic on original_port to new_port
        self.shuffle_port(original_port, new_port)
        # Shuffle the IP: rewrite traffic destined for original_ip to the new_ip
        self.shuffle_ip(original_ip, new_ip)

    def shuffle_ip(self, src_ip: str, dest_ip: str) -> None:
        """
        Redirect all traffic destined for ``src_ip`` to ``dest_ip``.

        This uses DNAT to change the destination IP of incoming packets.
        Only applicable on systems where iptables NAT table is enabled.
        """
        cmd = [
            "iptables", "-t", "nat", "-A", "PREROUTING",
            "-d", src_ip, "-j", "DNAT", "--to-destination", dest_ip
        ]
        self._run_cmd(cmd)

    def swap_service(self, port: int, decoy_ip: str, decoy_port: int | None = None) -> None:
        """
        Swap a service running on ``port`` to a decoy service.

        For example, if the main web server listens on port 3000 and a decoy
        service is available on ``decoy_ip:decoy_port`` (or the same port if
        ``decoy_port`` is None), this method installs a DNAT rule to forward
        all traffic hitting the original port to the decoy container.  When
        ``dry_run`` is True, the command is logged instead of executed.

        :param port: The original service port on the host.
        :param decoy_ip: The IP address of the decoy container.
        :param decoy_port: The port on the decoy service; if None, uses
                           ``port``.
        """
        target_port = decoy_port or port
        cmd = [
            "iptables", "-t", "nat", "-A", "PREROUTING",
            "-p", "tcp", "--dport", str(port),
            "-j", "DNAT", "--to-destination", f"{decoy_ip}:{target_port}"
        ]
        self._run_cmd(cmd)