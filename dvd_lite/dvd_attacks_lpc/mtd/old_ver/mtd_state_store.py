# dvd_lite/dvd_attacks_lpc/mtd/mtd_state_store.py
from __future__ import annotations

import json
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class BlacklistEntry:
    src_ip: str
    banned_until: float  # POSIX timestamp


@dataclass
class MTDStepMetrics:
    step: int
    timestamp: float
    action_id: int
    is_real_target: bool
    is_decoy_target: bool
    # 공격 관련
    is_attack: bool = False
    is_breach: bool = False
    is_decoy_hit: bool = False
    # 비용 관련
    shuffle_cost: float = 0.0
    decoy_cost: float = 0.0
    channel_cost: float = 0.0
    # QoS/성능
    attacker_blocked: bool = False
    qos_latency_ms: Optional[float] = None
    qos_loss_rate: Optional[float] = None

    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MTDState:
    step: int = 0
    current_action_id: int = 0
    last_target: Optional[str] = None
    blacklist: List[BlacklistEntry] = field(default_factory=list)
    history: List[MTDStepMetrics] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step": self.step,
            "current_action_id": self.current_action_id,
            "last_target": self.last_target,
            "blacklist": [asdict(b) for b in self.blacklist],
            "history": [asdict(h) for h in self.history],
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "MTDState":
        bl = [BlacklistEntry(**b) for b in raw.get("blacklist", [])]
        hist = [MTDStepMetrics(**h) for h in raw.get("history", [])]
        return cls(
            step=raw.get("step", 0),
            current_action_id=raw.get("current_action_id", 0),
            last_target=raw.get("last_target"),
            blacklist=bl,
            history=hist,
        )


class MTDStateStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def load(self) -> MTDState:
        if not self.path.exists():
            return MTDState()
        with self.path.open("r", encoding="utf-8") as f:
            raw = json.load(f)
        return MTDState.from_dict(raw)

    def save(self, state: MTDState) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(state.to_dict(), f, indent=2, ensure_ascii=False)
        tmp.replace(self.path)

    def append_step_metrics(self, state: MTDState, metrics: MTDStepMetrics) -> None:
        state.history.append(metrics)
        self.save(state)

    @staticmethod
    def now_ts() -> float:
        return datetime.now(tz=timezone.utc).timestamp()
