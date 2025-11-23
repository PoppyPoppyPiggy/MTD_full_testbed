# dvd_lite/dvd_attacks_lpc/mtd/mtd_scoring.py
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Iterable, List, Tuple

from .mtd_state_store import MTDState, MTDStateStore, MTDStepMetrics


class MTDScoring:
    """
    v02 스타일 MTD 지표:
      - S_D : 방어 성공도 (decoy hit, breach 회피 등)
      - C_M : MTD 비용 (shuffle, decoy, channel 변경)
      - R_A^norm : 공격 위험도 정규화
      - S_MTD^norm : 종합 MTD 스코어
    """

    def __init__(self, state_store: MTDStateStore, metrics_log: Path):
        self.state_store = state_store
        self.metrics_log = metrics_log

    def _iter_steps(self, state: MTDState) -> Iterable[MTDStepMetrics]:
        return state.history

    def compute_sd(self, state: MTDState) -> float:
        decoy_hits = sum(1 for s in self._iter_steps(state) if s.is_decoy_hit)
        breaches = sum(1 for s in self._iter_steps(state) if s.is_breach)
        attacks = sum(1 for s in self._iter_steps(state) if s.is_attack)

        if attacks == 0:
            return 0.0
        score = (decoy_hits - breaches) / attacks  # [-1,1]
        return 0.5 * (score + 1.0)  # [0,1]

    def compute_cm(self, state: MTDState) -> float:
        total_cost = 0.0
        for s in self._iter_steps(state):
            total_cost += s.shuffle_cost + s.decoy_cost + s.channel_cost
        if not state.history:
            return 0.0
        # step당 평균 비용
        return total_cost / len(state.history)

    def compute_ra_norm(self, state: MTDState) -> float:
        attacks = sum(1 for s in self._iter_steps(state) if s.is_attack)
        breaches = sum(1 for s in self._iter_steps(state) if s.is_breach)
        if attacks == 0:
            return 0.0
        breach_ratio = breaches / attacks
        return breach_ratio  # [0,1]

    def compute_s_mtd_norm(
        self,
        sd: float,
        cm: float,
        ra_norm: float,
        alpha: float = 0.6,
        beta: float = 0.2,
        gamma: float = 0.2,
    ) -> float:
        """
        S_MTD^norm = alpha * S_D - beta * C_M - gamma * R_A^norm
        """
        raw = alpha * sd - beta * cm - gamma * ra_norm
        return max(0.0, min(1.0, raw))

    def export_last_episode(self) -> Tuple[dict, List[dict]]:
        state = self.state_store.load()
        sd = self.compute_sd(state)
        cm = self.compute_cm(state)
        ra = self.compute_ra_norm(state)
        s_mtd = self.compute_s_mtd_norm(sd, cm, ra)

        summary = {
            "S_D": sd,
            "C_M": cm,
            "R_A_norm": ra,
            "S_MTD_norm": s_mtd,
            "num_steps": len(state.history),
        }
        steps = [asdict(s) for s in state.history]

        self.metrics_log.parent.mkdir(parents=True, exist_ok=True)
        with self.metrics_log.open("a", encoding="utf-8") as f:
            line = json.dumps({"summary": summary, "steps": steps}, ensure_ascii=False)
            f.write(line + "\n")

        return summary, steps
