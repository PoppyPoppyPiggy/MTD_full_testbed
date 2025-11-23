# dvd_lite/dvd_attacks_lpc/mtd/cti_status_reader.py
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict


@dataclass
class CtiStatus:
    is_attack: bool = False
    is_breach: bool = False
    threat_level: float = 0.0  # 0~1
    src_ip: str | None = None
    extra: Dict[str, Any] | None = None


class CtiStatusReader:
    def __init__(self, path: str | Path | None):
        self.path = Path(path) if path else None

    def read(self) -> CtiStatus:
        if not self.path or not self.path.exists():
            return CtiStatus()
        try:
            with self.path.open("r", encoding="utf-8") as f:
                raw = json.load(f)
        except Exception:
            return CtiStatus()
        return CtiStatus(
            is_attack=bool(raw.get("is_attack", False)),
            is_breach=bool(raw.get("is_breach", False)),
            threat_level=float(raw.get("threat_level", 0.0)),
            src_ip=raw.get("src_ip"),
            extra={
                k: v
                for k, v in raw.items()
                if k not in {"is_attack", "is_breach", "threat_level", "src_ip"}
            },
        )
