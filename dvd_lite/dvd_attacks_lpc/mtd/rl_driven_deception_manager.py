# dvd_lite/dvd_attacks_lpc/mtd/rl_driven_deception_manager.py
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict

from .mtd_config import MTDConfig
from .mtd_state_store import MTDStateStore, MTDState
from .iptables_mtd_controller import IPTablesMTDController
from .cti_status_reader import CtiStatusReader
from .qos_monitor import QoSMonitor
from .mtd_scoring import MTDScoring


log = logging.getLogger(__name__)


class RLPolicyInterface:
    """
    실제 PPO 정책은 ml/ 또는 rl/ 디렉터리에서 구현.
    여기서는 (obs_dict) -> action_id 인터페이스만 정의.
    """

    def __init__(self, action_space_size: int):
        self.action_space_size = action_space_size

    def select_action(self, obs: Dict[str, float]) -> int:
        # TODO: PPO 정책으로 교체
        # 현재는 placeholder (항상 0번 액션)
        return 0


class RLDrivenDeceptionManager:
    """
    - CTI 상태 + QoS 상태 + MTDState -> observation 벡터 구성
    - RL 정책(PPO 등)에 action_id 요청
    - config.actions[action_id] 를 iptables를 통해 적용
    - MTDState.history에 step 메트릭 기록
    - 에피소드 끝나면 MTDScoring으로 S_D, C_M, R_A, S_MTD 계산
    """

    def __init__(self, config_path: str | Path, dry_run: bool = True):
        self.config = MTDConfig.load(config_path)
        self.state_store = MTDStateStore(self.config.state_file)
        self.iptables = IPTablesMTDController(
            config=self.config,
            state_store=self.state_store,
            dry_run=dry_run,
        )
        self.cti_reader = CtiStatusReader(self.config.cti_status_file)
        self.qos_monitor = QoSMonitor(self.state_store)
        self.scoring = MTDScoring(self.state_store, self.config.metrics_log)

        action_space = len(self.config.actions)
        self.policy = RLPolicyInterface(action_space)

    def _build_observation(self, state: MTDState, cti, qos) -> Dict[str, float]:
        return {
            "step": float(state.step),
            "current_action_id": float(state.current_action_id),
            "threat_level": float(cti.threat_level),
            "is_attack": 1.0 if cti.is_attack else 0.0,
            "is_breach": 1.0 if cti.is_breach else 0.0,
            "latency_ms": float(qos.latency_ms),
            "loss_rate": float(qos.loss_rate),
            "attacker_blocked": 1.0 if qos.attacker_blocked else 0.0,
            "blacklist_size": float(len(state.blacklist)),
        }

    def step(self):
        """
        한 step마다 호출 (예: 5초마다 cron, 혹은 RL 환경에서 매 step).

        1) CTI 상태 읽기
        2) QoS/blacklist 업데이트
        3) observation 생성
        4) RL 정책으로부터 action 선택
        5) iptables DNAT 적용
        6) 메트릭 기록
        """
        state = self.state_store.load()
        cti = self.cti_reader.read()

        # 공격 발생 시: src_ip를 blacklist에 등록하고 QoS 모형 업데이트
        if cti.is_attack and cti.src_ip:
            qos = self.qos_monitor.register_attack(cti.src_ip, cti.threat_level)
        else:
            qos = self.qos_monitor.sample(cti.src_ip)

        obs = self._build_observation(state, cti, qos)
        action_id = self.policy.select_action(obs)
        action = self.config.actions[action_id]

        metrics = self.iptables.apply_action(action, state)
        # CTI/QoS 기반 플래그 보강 (RL reward 설계에 사용 가능)
        metrics.is_attack = cti.is_attack
        metrics.is_breach = cti.is_breach
        metrics.attacker_blocked = qos.attacker_blocked
        metrics.qos_latency_ms = qos.latency_ms
        metrics.qos_loss_rate = qos.loss_rate

        state.step += 1
        self.state_store.save(state)
        return metrics

    def finalize_episode(self) -> Dict[str, Any]:
        """
        에피소드 종료 시 호출.
        - 전체 step history 기반으로 S_D, C_M, R_A_norm, S_MTD_norm 계산
        - wandb / tensorboard에 올릴 요약 딕셔너리 반환
        """
        summary, _ = self.scoring.export_last_episode()
        log.info("Episode summary: %s", summary)
        return summary
