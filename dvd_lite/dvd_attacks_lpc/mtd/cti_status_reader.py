"""
Improved CTI status reader for the MTD RL manager.

This module provides a ``CtiStatusReader`` class that reads the CTI
status from a JSON file (typically ``cti_status.json`` under the
``mtd/shared_state`` directory) and returns a ``CtiStatus`` dataclass.

Enhancements over the original implementation:
  * Gracefully handles missing or malformed files by returning a
    default ``CtiStatus`` instance and logging a warning.
  * Records the last modification timestamp to detect staleness.
  * Allows custom status file paths.

Usage:
    reader = CtiStatusReader('/path/to/cti_status.json')
    status = reader.read_status()
    if status.is_attack:
        ...
"""

from __future__ import annotations

import json
import os
import logging
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class CtiStatus:
    """Represents the current CTI status for the RL manager."""
    is_attack: bool = False
    threat_level: float = 0.0
    src_ip: str = "0.0.0.0"
    attack_label: int | None = None
    attack_name: str | None = None
    timestamp: str | None = None

    def is_stale(self, max_age_sec: int = 30) -> bool:
        """Return True if the status is older than max_age_sec seconds."""
        if not self.timestamp:
            return True
        try:
            ts = datetime.fromisoformat(self.timestamp.replace('Z', ''))
            age = (datetime.utcnow() - ts).total_seconds()
            return age > max_age_sec
        except Exception:
            return True


class CtiStatusReader:
    """Reads the CTI status JSON file and returns a CtiStatus object."""
    def __init__(self, status_path: str):
        self.status_path = status_path
        self.last_mtime: float | None = None

    def read_status(self) -> CtiStatus:
        """Read the status file and return a ``CtiStatus`` instance."""
        if not os.path.exists(self.status_path):
            logger.debug(f"CTI status file not found: {self.status_path}")
            return CtiStatus()
        try:
            mtime = os.path.getmtime(self.status_path)
            if self.last_mtime is not None and mtime == self.last_mtime:
                # file unchanged; return previous value (caller may cache it)
                return CtiStatus()
            with open(self.status_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.last_mtime = mtime
            return CtiStatus(
                is_attack=bool(data.get('is_attack', False)),
                threat_level=float(data.get('threat_level', 0.0)),
                src_ip=data.get('src_ip', "0.0.0.0"),
                attack_label=data.get('attack_label'),
                attack_name=data.get('attack_name'),
                timestamp=data.get('timestamp'),
            )
        except Exception as e:
            logger.warning(f"Failed to parse CTI status file: {e}")
            return CtiStatus()