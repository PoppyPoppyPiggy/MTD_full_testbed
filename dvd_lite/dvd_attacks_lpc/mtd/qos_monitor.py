# dvd_lite/dvd_attacks_lpc/mtd/qos_monitor.py
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from .old_ver.mtd_state_store import BlacklistEntry, MTDState, MTDStateStore


@dataclass
class QoSStats:
    latency_ms: float = 0.0
    loss_rate: float = 0.0
    attacker_blocked: bool = False
    src_ip: Optional[str] = None
    extra: Dict[str, float] = field(default_factory=dict)


class QoSMonitor:
    """
    - CTI 이벤트와 연계해서 src_ip를 blacklist에 등록
    - ban_window 동안 해당 src_ip는 attacker_blocked=True
    - RL 시뮬레이션에서는 손실/지연만 모델링하고,
      실제 배포에서는 별도 iptables DROP 규칙과 연계 가능
    """

    def __init__(self, state_store: MTDStateStore, ban_window_sec: int = 10):
        self.state_store = state_store
        self.ban_window = timedelta(seconds=ban_window_sec)

    def _now(self) -> datetime:
        return datetime.now(tz=timezone.utc)

    def _cleanup_blacklist(self, state: MTDState) -> None:
        now_ts = self._now().timestamp()
        state.blacklist = [b for b in state.blacklist if b.banned_until > now_ts]

    def register_attack(self, src_ip: str, severity: float = 1.0) -> QoSStats:
        """
        공격이 탐지되었을 때 호출.
        - src_ip를 ban_window 동안 blacklist에 추가
        - 매우 단순화된 QoS 모델: 차단 시 손실/지연 증가
        """
        state = self.state_store.load()
        self._cleanup_blacklist(state)
        banned_until = self._now().timestamp() + self.ban_window.total_seconds()
        state.blacklist.append(BlacklistEntry(src_ip=src_ip, banned_until=banned_until))
        self.state_store.save(state)

        loss = min(1.0, 0.2 + 0.3 * severity)
        latency = 20.0 + 30.0 * severity
        return QoSStats(
            latency_ms=latency,
            loss_rate=loss,
            attacker_blocked=True,
            src_ip=src_ip,
        )

    def sample(self, src_ip: Optional[str] = None) -> QoSStats:
        """
        평시 QoS 상태 조회.
        - src_ip가 blacklist에 있으면 공격자 입장에서 "MTD 때문에 막혀 있다"로 해석
        """
        state = self.state_store.load()
        self._cleanup_blacklist(state)
        blocked = False
        if src_ip:
            blocked = any(b.src_ip == src_ip for b in state.blacklist)

        loss = 0.0
        latency = 10.0
        if blocked:
            loss = 0.5
            latency = 50.0
        return QoSStats(latency_ms=latency, loss_rate=loss, attacker_blocked=blocked, src_ip=src_ip)
