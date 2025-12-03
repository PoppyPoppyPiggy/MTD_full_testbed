#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rl_driven_deception_manager.py
==============================

- 학습된 PPO 정책(final_policy.pth)을 로드
- 실시간 CTI/모니터링 메트릭을 상태 벡터로 변환
- IptablesMTDController를 사용해 실제 MTD/Decoy 정책 적용
- 외부에서 실행되는 실제 seeker.py와 배틀을 수행하면서 로그를 남김

CLI 모드에서는 기본적으로 SimpleMTDRuntimeSource를 사용하여
의사(시뮬레이션) 메트릭으로 정책이 정상 작동하는지만 검증한다.

실제 배포 시에는 RuntimeMetricsSourceBase를 상속한 커스텀 런타임 소스를 구현하고
코드 레벨에서 RLDrivenDeceptionManager.run_episode(runtime_source, ...) 를 직접 호출하는 것을 권장한다.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import time
from typing import Dict, Any, Optional, List

import numpy as np
import torch

from .iptables_mtd_controller import IptablesMTDController
from .rl_model_v05 import PPOAgent
from .rl_config_v06 import (
    RL_CONFIG,
    FEATURE_KEYS,
    ACTION_PARAM_KEYS,
    STATE_DIM,
    ACTION_DIM,
)

# 로거 설정
logger = logging.getLogger("RLDrivenDeceptionManager")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    _handler.setFormatter(_fmt)
    logger.addHandler(_handler)
logger.setLevel(logging.INFO)


# ----------------------------------------------------------------------
# 유틸 함수
# ----------------------------------------------------------------------
def _load_attacker_config(path: str) -> Dict[str, Any]:
    """
    attacker_config.json 로더.
    존재하지 않으면 경고를 남기고 빈 dict 반환.
    """
    if not path:
        logger.warning("attacker_config path가 비어 있습니다. 빈 설정을 사용합니다.")
        return {}

    if not os.path.exists(path):
        logger.warning(f"attacker_config.json not found at {path}. Using empty default.")
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        logger.info(f"Loaded attacker_config from {path}")
        return data
    except Exception as e:
        logger.warning(f"Failed to load attacker_config.json from {path}: {e}")
        return {}


def _scale_action(x: float) -> float:
    """
    PPO 정책이 출력한 연속값(raw_action)을 [0,1] 스케일로 변환.
    Env(v06)에서 사용하던 방식과 맞추기 위해 단순히 (x + 1) / 2 사용.
    (학습 시에도 같은 방식이 사용되었다는 전제)
    """
    return float((x + 1.0) / 2.0)


# ----------------------------------------------------------------------
# 런타임 메트릭 소스 추상 클래스 및 간단 구현
# ----------------------------------------------------------------------
class RuntimeMetricsSourceBase:
    """
    실시간 CTI / 모니터링 데이터를 가져오는 인터페이스.
    실제 배포 시에는 이 클래스를 상속하여 get_metrics()를 구현한다.
    """

    def get_metrics(self, step: Optional[int] = None) -> Dict[str, float]:
        """
        step: 에피소드 내 step index (선택적)
        반환 예:
            {
              "cti_alert_rate": 0.3,
              "blacklist_size_ratio": 0.1,
              "uptime_ratio": 0.9,
              "breach_success_rate": 0.0,
              "decoy_lure_rate": 0.5,
              ...
            }
        """
        raise NotImplementedError


class SimpleMTDRuntimeSource(RuntimeMetricsSourceBase):
    """
    데모/테스트용 간단한 메트릭 소스.
    - 시간이 지날수록 cti_alert_rate, blacklist_size_ratio 등을 조금씩 증가시켜
      RL 정책이 다양한 상태를 보도록 한다.
    """

    def __init__(self) -> None:
        self.t = 0

    def get_metrics(self, step: Optional[int] = None) -> Dict[str, float]:
        if step is not None:
            self.t = step
        else:
            self.t += 1

        # 간단한 삼각파/사인파 기반 의사 메트릭
        cti_alert_rate = min(1.0, max(0.0, (self.t % 50) / 50.0))
        blacklist_ratio = min(1.0, max(0.0, (self.t % 30) / 30.0))
        uptime_ratio = 1.0 - 0.01 * (self.t % 10)
        breach_rate = 0.1 * ((self.t % 20) / 20.0)
        decoy_lure_rate = min(1.0, max(0.0, (self.t % 40) / 40.0))

        return {
            "cti_alert_rate": float(cti_alert_rate),
            "blacklist_size_ratio": float(blacklist_ratio),
            "uptime_ratio": float(max(0.0, uptime_ratio)),
            "breach_success_rate": float(breach_rate),
            "decoy_lure_rate": float(decoy_lure_rate),
        }


# ----------------------------------------------------------------------
# RLDrivenDeceptionManager 본체
# ----------------------------------------------------------------------
class RLDrivenDeceptionManager:
    def __init__(
        self,
        model_path: str,
        norm_meta_path: str,
        attacker_config_path: Optional[str] = None,
        service_name: str = "fc_mavlink",
        dry_run: bool = True,
        log_file: Optional[str] = None,
    ) -> None:
        # 디바이스 설정
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        # PPOAgent 초기화 & 정책 로드
        # (rl_model_v05.PPOAgent 시그니처에 맞춰 사용)
        self.agent = PPOAgent(
            state_dim=STATE_DIM,
            action_dim=ACTION_DIM,
            hidden_size=128,
            lr=3e-4,
            gamma=0.99,
            gae_lambda=0.95,
            clip_coef=0.2,
            max_grad_norm=0.5,
            ent_coef=0.01,
            vf_coef=0.5,
            ppo_epochs=10,
            minibatch_size=64,
            target_kl=0.015,
            device=self.device,
        )
        # 이전 에러: load_policy(map_location=...) → map_location 제거
        self.agent.load_policy(model_path)

        # eval 모드
        if hasattr(self.agent, "policy") and hasattr(self.agent.policy, "eval"):
            self.agent.policy.eval()
        if hasattr(self.agent, "value_net") and hasattr(self.agent.value_net, "eval"):
            self.agent.value_net.eval()

        # 정규화 메타데이터 로드
        with open(norm_meta_path, "r", encoding="utf-8") as f:
            self.norm_meta = json.load(f)
        self.feature_norm_meta = self.norm_meta.get("FEATURE_NORM_METADATA", None)

        # iptables 기반 MTD 컨트롤러
        self.controller = IptablesMTDController(dry_run=dry_run)

        # 공격자/서비스 설정
        if attacker_config_path is None:
            default_path = os.path.join(RL_CONFIG.BASE_DIR, "config", "attacker_config.json")
            attacker_config_path = default_path

        attacker_cfg = _load_attacker_config(attacker_config_path)
        self.service_name = service_name

        # real_ip, real_port, decoy_ip 멤버 저장 + 1차 등록
        self.real_ip: str = "10.13.0.2"
        self.real_port: int = 14550
        self.decoy_ip: Optional[str] = None
        self._register_service_from_attacker_config(attacker_cfg)

        # 마지막 액션 파라미터 기록 (상태 벡터 뒤쪽에 포함)
        self.last_actions: Dict[str, float] = {k: 0.5 for k in ACTION_PARAM_KEYS}

        # 배틀 로그 파일 설정
        self.log_file = log_file
        if self.log_file:
            try:
                with open(self.log_file, "a", encoding="utf-8") as f:
                    f.write("# RLDrivenDeceptionManager battle log\n")
            except Exception as e:
                logger.warning(f"Failed to open log file {self.log_file} for append: {e}")
                self.log_file = None

    # ------------------------------------------------------------------
    # attacker_config → 서비스 등록
    # ------------------------------------------------------------------
    def _register_service_from_attacker_config(self, attacker_cfg: Dict[str, Any]) -> None:
        """
        attacker_config.json의 TARGET_FC, TARGET_DECOY, PORT_MAVLINK를 가져와
        IptablesMTDController에 서비스 등록 + RLDM 멤버에 저장.
        """
        targets = attacker_cfg.get("targets", {})
        ports = attacker_cfg.get("ports", {})

        real_ip = targets.get("TARGET_FC", None)
        decoy_ip = targets.get("TARGET_DECOY", None)
        mav_port_str = ports.get("PORT_MAVLINK", "14550")

        try:
            real_port = int(mav_port_str)
        except ValueError:
            real_port = 14550

        if not real_ip:
            logger.warning("TARGET_FC not found in attacker_config.json; using default 10.13.0.2:14550")
            real_ip = "10.13.0.2"

        # 멤버 필드에 저장 (apply_action에서 재등록용으로 사용)
        self.real_ip = real_ip
        self.real_port = real_port
        self.decoy_ip = decoy_ip

        logger.info(
            f"Registering service [{self.service_name}] -> real={real_ip}:{real_port}, decoy={decoy_ip}"
        )

        try:
            # iptables_mtd_controller.register_service(name, target_key, port_idx)
            # 여기서는 직접 IP/Port를 쓰는 것이 아니라 FC/DECOY 키를 써도 되지만,
            # 이미 DEFAULT_TARGETS에 FC/DECOY가 정의되어 있으므로 target_key="FC" 고정으로 사용 가능.
            # 다만 현재 컨트롤러 구현은 target_key 기반이므로, 여기서는 예외 처리만 수행.
            # (실제 ip만 사용하는 버전으로 확장하려면 컨트롤러 구현 변경 필요)
            self.controller.register_service(self.service_name, "FC", 0)
        except Exception as e:
            logger.warning(f"register_service initial call failed: {e}")

    # ------------------------------------------------------------------
    # 상태 벡터 구성
    # ------------------------------------------------------------------
    def build_state_from_runtime_metrics(self, metrics: Dict[str, Any]) -> np.ndarray:
        """
        runtime_metrics → FEATURE_KEYS + ACTION_PARAM_KEYS 순서로 상태 벡터를 만든다.
        FEATURE_KEYS: CTI/모니터링 기반 관측값
        ACTION_PARAM_KEYS: 직전 액션 파라미터 (policy의 자기참조 효과)
        """
        state_vec: List[float] = []

        # 1) 관측 피처
        for key in FEATURE_KEYS:
            v = float(metrics.get(key, 0.0))
            # 정규화 메타가 있다면 여기서 적용 가능 (선택)
            if self.feature_norm_meta and key in self.feature_norm_meta:
                # 예: {"mean": ..., "std": ...} 형태라고 가정
                meta = self.feature_norm_meta[key]
                mean = meta.get("mean", 0.0)
                std = meta.get("std", 1.0) or 1.0
                v = (v - mean) / std
            state_vec.append(v)

        # 2) 직전 액션 파라미터들
        for key in ACTION_PARAM_KEYS:
            state_vec.append(float(self.last_actions.get(key, 0.5)))

        # STATE_DIM과 길이를 맞춰야 하면 패딩/트렁크 처리
        if len(state_vec) < STATE_DIM:
            state_vec.extend([0.0] * (STATE_DIM - len(state_vec)))
        elif len(state_vec) > STATE_DIM:
            state_vec = state_vec[:STATE_DIM]

        return np.array(state_vec, dtype=np.float32)

    # ------------------------------------------------------------------
    # RL 액션 → 실제 MTD/Decoy 매핑
    # ------------------------------------------------------------------
    def apply_action(self, raw_action: np.ndarray) -> Dict[str, float]:
        """
        RL 정책이 출력한 연속값 액션(raw_action)을 Env(v06) 스타일로 스케일링하고,
        실제 iptables MTD/Decoy에 매핑. 서비스가 등록 안 되어 있으면 매 스텝 재등록.
        """
        # --- 0) 안전하게 서비스 재등록 시도 ---
        try:
            services = getattr(self.controller, "state", None)
            if isinstance(services, dict):
                if self.service_name not in services:
                    logger.info(
                        f"Service [{self.service_name}] not found in controller; "
                        f"re-registering with FC target key (ip={self.real_ip}, port={self.real_port})"
                    )
                    try:
                        self.controller.register_service(self.service_name, "FC", 0)
                    except Exception as e:
                        logger.warning(f"Service re-registration failed: {e}")
            else:
                # state 속성이 없으면 그냥 매번 등록 시도
                try:
                    self.controller.register_service(self.service_name, "FC", 0)
                except Exception as e:
                    logger.warning(f"Service registration safeguard (no state) failed: {e}")
        except Exception as e:
            logger.warning(f"Service registration safeguard failed: {e}")

        # --- 1) 액션 차원 체크 ---
        if raw_action.shape[0] != len(ACTION_PARAM_KEYS):
            raise ValueError(
                f"Expected action dim {len(ACTION_PARAM_KEYS)}, got {raw_action.shape[0]}"
            )

        # --- 2) [-1,1] → [0,1] 스케일링 (Env와 동일) ---
        scaled_params: Dict[str, float] = {}
        for i, key in enumerate(ACTION_PARAM_KEYS):
            scaled_params[key] = _scale_action(float(raw_action[i]))

        self.last_actions.update(scaled_params)

        shuffle_intensity = scaled_params.get("shuffle_intensity", 0.0)
        decoy_ratio = scaled_params.get("decoy_ratio", 0.0)
        blacklist_aggr = scaled_params.get("blacklist_aggression", 0.0)

        # --- 3) MTD 액션 매핑 ---
        if shuffle_intensity >= 0.6:
            self.controller.shuffle_network(
                self.service_name,
                intensity=shuffle_intensity,
            )

        if decoy_ratio >= 0.5:
            self.controller.enable_decoy(self.service_name)
        else:
            self.controller.disable_decoy(self.service_name)

        if blacklist_aggr >= 0.5:
            logger.info(
                f"[RLDM] High blacklist aggression={blacklist_aggr:.2f} -> "
                "external IDS/fw와 연동하여 proactive blocking 가능."
            )

        return scaled_params

    # ------------------------------------------------------------------
    # 로그 출력
    # ------------------------------------------------------------------
    def _log_step(self, step: int, metrics: Dict[str, Any], params: Dict[str, float]) -> None:
        msg = (
            f"[RLDM] step={step} metrics[cti_alert_rate]={metrics.get('cti_alert_rate', 0.0):.3f}, "
            f"params={params}"
        )
        logger.info(msg)

        if self.log_file:
            try:
                with open(self.log_file, "a", encoding="utf-8") as f:
                    f.write(msg + "\n")
            except Exception as e:
                logger.warning(f"Failed to write to log file {self.log_file}: {e}")

    # ------------------------------------------------------------------
    # 에피소드 실행
    # ------------------------------------------------------------------
    def run_episode(
        self,
        runtime_source: RuntimeMetricsSourceBase,
        max_steps: int = 200,
        interval_sec: float = 1.0,
    ) -> None:
        logger.info(
            f"Starting RL-driven deception episode: max_steps={max_steps}, interval={interval_sec}s"
        )

        for step in range(max_steps):
            # 1. 런타임 메트릭 수집
            metrics = runtime_source.get_metrics(step=step)

            # 2. 상태 벡터 구성
            state = self.build_state_from_runtime_metrics(metrics)
            state_tensor = torch.as_tensor(
                state, dtype=torch.float32, device=self.device
            ).unsqueeze(0)

            # 3. 정책에서 액션 샘플링 (deterministic 인자 없음)
            with torch.no_grad():
                action_tensor, _, _ = self.agent.get_action_and_value(state_tensor)

            action_np = action_tensor.cpu().numpy().squeeze(0)

            # 4. MTD/Decoy 적용
            applied_params = self.apply_action(action_np)

            # 5. 로그
            self._log_step(step, metrics, applied_params)

            time.sleep(interval_sec)


# ----------------------------------------------------------------------
# CLI 엔트리 포인트
# ----------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="RL-driven MTD/Decoy Deception Manager (Deployment)")

    parser.add_argument(
        "--model-path",
        type=str,
        required=True,
        help="학습된 PPO 정책 파일 경로 (예: ./runs/.../final_policy.pth)",
    )
    parser.add_argument(
        "--norm-meta-path",
        type=str,
        required=True,
        help="정규화 메타데이터 JSON 경로 (예: ./runs/.../norm_metadata.json)",
    )
    parser.add_argument(
        "--attacker-config",
        type=str,
        default=None,
        help="attacker_config.json 경로 (기본: BASE_DIR/config/attacker_config.json)",
    )
    parser.add_argument(
        "--service-name",
        type=str,
        default="fc_mavlink",
        help="IptablesMTDController에서 사용할 서비스 이름 (예: fc_mavlink, cc_web 등)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="iptables 명령을 실제로 적용하지 않고 로그만 남김",
    )
    parser.add_argument(
        "--log-file",
        type=str,
        default=None,
        help="배틀 로그를 기록할 파일 경로 (옵션)",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=200,
        help="에피소드 내 최대 step 수",
    )
    parser.add_argument(
        "--interval-sec",
        type=float,
        default=1.0,
        help="step 간 대기 시간 (초)",
    )
    parser.add_argument(
        "--use-simple-runtime",
        action="store_true",
        help="내장 SimpleMTDRuntimeSource를 사용하여 의사 메트릭 기반 테스트 실행",
    )

    args = parser.parse_args()

    # 런타임 소스 선택
    if args.use_simple_runtime:
        runtime_source: RuntimeMetricsSourceBase = SimpleMTDRuntimeSource()
    else:
        logger.error(
            "현재 CLI에서는 --use-simple-runtime 옵션으로 SimpleMTDRuntimeSource만 제공됩니다.\n"
            "실제 배포 시에는 RuntimeMetricsSourceBase를 상속한 클래스를 구현하여 "
            "직접 RLDrivenDeceptionManager.run_episode()를 호출하세요."
        )
        logger.info("Falling back to SimpleMTDRuntimeSource (since no custom runtime source is wired).")
        runtime_source = SimpleMTDRuntimeSource()

    # 매니저 생성
    manager = RLDrivenDeceptionManager(
        model_path=args.model_path,
        norm_meta_path=args.norm_meta_path,
        attacker_config_path=args.attacker_config,
        service_name=args.service_name,
        dry_run=args.dry_run,
        log_file=args.log_file,
    )

    # 에피소드 실행
    manager.run_episode(runtime_source, max_steps=args.max_steps, interval_sec=args.interval_sec)


if __name__ == "__main__":
    main()
