# dvd_lite/dvd_attacks_lpc/mtd/iptables_mtd_controller.py
from __future__ import annotations

import logging
import shlex
import subprocess
from dataclasses import dataclass
from typing import Optional

from .mtd_config import MTDConfig, ActionDef
from .mtd_state_store import MTDState, MTDStateStore, MTDStepMetrics


log = logging.getLogger(__name__)


def _run(cmd: str, dry_run: bool = False) -> subprocess.CompletedProcess:
    log.debug("run: %s", cmd)
    if dry_run:
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=b"", stderr=b"")
    return subprocess.run(shlex.split(cmd), capture_output=True)


@dataclass
class IPTablesMTDController:
    config: MTDConfig
    state_store: MTDStateStore
    dry_run: bool = False

    def _reset_chain(self) -> None:
        c = self.config
        _run(
            f"iptables -t {c.nat_backend.nat_table} -F {c.nat_backend.mtd_chain}",
            dry_run=self.dry_run,
        )

    def _apply_dnat(self, target: str) -> None:
        c = self.config
        self._reset_chain()
        _run(
            f"iptables -t {c.nat_backend.nat_table} -A {c.nat_backend.mtd_chain} "
            f"-p {c.service.protocol} --dport {c.service.public_port} "
            f"-j DNAT --to-destination {target}",
            dry_run=self.dry_run,
        )
        log.info("Applied DNAT -> %s", target)

    def apply_action(
        self, action: ActionDef, state: Optional[MTDState] = None
    ) -> MTDStepMetrics:
        """
        하나의 RL step 또는 MTD 재구성 step에서 호출.
        - DNAT 적용
        - 기본적인 메트릭(어떤 타겟으로 갔는지)만 채워서 반환
        나머지 공격/비용/성능 플래그는 상위 레이어에서 채움.
        """
        if state is None:
            state = self.state_store.load()

        is_real = action.params.get("role", "real") == "real"
        is_decoy = action.params.get("role", "real") == "decoy"

        if action.type == "DNAT" and action.target:
            self._apply_dnat(action.target)
            state.current_action_id = action.id
            state.last_target = action.target

        metrics = MTDStepMetrics(
            step=state.step,
            timestamp=self.state_store.now_ts(),
            action_id=action.id,
            is_real_target=is_real,
            is_decoy_target=is_decoy,
        )
        self.state_store.append_step_metrics(state, metrics)
        return metrics
