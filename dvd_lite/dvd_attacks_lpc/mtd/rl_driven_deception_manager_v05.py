#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RL-driven MTD Decision Manager (Deploy, PPO_v07_SeekerL*)

- 학습된 PPO_v07_SeekerL0~L3 정책을 테스트베드에서 배포/평가하기 위한 매니저.
- 입력: CTI + MTD/Seeker 지표 (mtd_scoring, seeker_scoring, cti_status_reader 등에서 수집)
- 출력: iptables DNAT / 셔플 스크립트 / 블랙리스트 정책 실행
- ml/cti_agent_demo.py 에서 이 매니저를 불러 周期적으로 step() 호출하는 구조.

[중요 포인트]
- policy 로딩:
  - model_dir/
      ├─ final_policy.pth
      └─ norm_metadata.json
- norm_metadata.json 스키마:
  {
    "FEATURE_KEYS": [... 16개 ...],
    "ACTION_PARAM_KEYS": [... 6개 ...],
    "FEATURE_NORM_METADATA": {
        "means": [... 16개 ...],
        "stds":  [... 16개 ...]
    }
  }

- FEATURE_KEYS 예시:
    [
        "cti_alert_rate",
        "blacklist_size_ratio",
        "uptime_ratio",
        "breach_success_rate",
        "decoy_lure_rate",
        "current_exposure_mean",
        "r_known_ratio",
        "r_exploited_ratio",
        "seeker_scan_effort",
        "seeker_attack_bias",
        "last_action_dnat_target_focus",
        "last_action_dnat_decoy_focus",
        "last_action_shuffle_intensity",
        "last_action_blacklist_aggression",
        "last_action_blacklist_duration",
        "last_action_decoy_ratio"
    ]

- ACTION_PARAM_KEYS 예시:
    [
        "dnat_target_focus",
        "dnat_decoy_focus",
        "shuffle_intensity",
        "blacklist_aggression",
        "blacklist_duration",
        "decoy_ratio"
    ]
"""

import os
import json
import logging
import time
import random
from typing import Dict, Any, List

import numpy as np
import torch
import torch.nn as nn

try:
    import wandb
except ImportError:
    wandb = None


# ---------------------------------------------------------------------
# 1. PPO_v07 정책 네트워크 정의 (학습 시 사용한 네트워크와 동일한 구조)
# ---------------------------------------------------------------------
class MTDPolicyNet(nn.Module):
    """
    PPO_v07 학습 시 사용한 Actor-Critic 네트워크와 key 이름을 맞춘 버전.

    state_dict 키 예:
      - "feature_extractor.0.weight", "feature_extractor.0.bias", ...
      - "actor_mean.weight", "actor_mean.bias"
      - "log_std"
      - "critic.weight", "critic.bias"
    """
    def __init__(self, obs_dim: int, act_dim: int):
        super().__init__()
        self.feature_extractor = nn.Sequential(
            nn.Linear(obs_dim, 128),
            nn.Tanh(),
            nn.Linear(128, 128),
            nn.Tanh(),
        )
        self.actor_mean = nn.Linear(128, act_dim)
        # PPO_v07 학습 모델에서 사용하는 이름: "log_std"
        self.log_std = nn.Parameter(torch.zeros(act_dim))
        # critic은 여기서 사용하지 않지만, state_dict 맞추기 위해 정의
        self.critic = nn.Linear(128, 1)

    def forward(self, x: torch.Tensor):
        """
        배포 단계에서는 정책(행동)만 필요하지만,
        state_dict 로딩을 위해 critic까지 함께 정의.
        """
        feat = self.feature_extractor(x)
        mean = self.actor_mean(feat)
        std = torch.exp(self.log_std)
        dist = torch.distributions.Normal(mean, std)
        value = self.critic(feat)
        return dist, value

    def act_greedy(self, obs_vec: np.ndarray) -> np.ndarray:
        """
        관측 벡터(obs_vec)를 받아 deterministic mean action 반환.
        - obs_vec: (obs_dim,) numpy array
        - return : (act_dim,) numpy array, [-∞, +∞] continuous 값 (PPO raw mean)
        """
        self.eval()
        with torch.no_grad():
            x = torch.from_numpy(obs_vec).float().unsqueeze(0)  # (1, obs_dim)
            feat = self.feature_extractor(x)
            mean = self.actor_mean(feat)  # (1, act_dim)
            return mean.squeeze(0).cpu().numpy()


# ---------------------------------------------------------------------
# 2. MTD Scorer / CTI Status / iptables Controller 로딩 (없으면 Dummy)
# ---------------------------------------------------------------------
try:
    from mtd.mtd_scoring import MtdScorer  # 너가 만든 학습/배포 공통 지표 모듈
except Exception as e:
    print(f"[RL Manager] ImportError 발생(MtdScorer): {e}")
    print("  -> Dummy MtdScorer 사용 (지표는 전부 상수로 고정됨).")

    class MtdScorer:
        """
        아주 단순한 데모용 Dummy Scorer.
        실제 테스트베드에서는 log 기반으로 지표를 계산해야 함.
        """
        def collect_metrics(self) -> Dict[str, float]:
            return {
                "cti_alert_rate": 0.1,
                "blacklist_size_ratio": 0.0,
                "uptime_ratio": 1.0,
                "breach_success_rate": 0.1,
                "decoy_lure_rate": 0.1,
                "current_exposure_mean": 10.0,
                "r_known_ratio": 0.05,
                "r_exploited_ratio": 0.02,
                "seeker_scan_effort": 1.0,
                "seeker_attack_bias": 0.5,
            }

try:
    from mtd.controller.iptables_mtd_controller import IptablesController
except Exception as e:
    print(f"[RL Manager] ImportError 발생(IptablesController): {e}")
    print("  -> Dummy IptablesController 사용 (iptables 실제 변경 없음).")

    class IptablesController:
        def __init__(self, *args, **kwargs):
            self.logger = kwargs.get("logger", logging.getLogger("DummyIptables"))

        def apply_dnat_redirect(self, ip: str, port: int, attacker_ip: str = "10.13.0.200"):
            self.logger.info(f"[DummyIptables] DNAT: {attacker_ip} -> {ip}:{port}")

        def run_script(self, script_name: str):
            self.logger.info(f"[DummyIptables] RUN SCRIPT: {script_name}")

        def update_blacklist(self, attacker_alerts: Dict[str, float], threshold: float, duration_sec: int):
            self.logger.info(
                f"[DummyIptables] UPDATE BL: threshold={threshold:.2f}, duration={duration_sec}, alerts={attacker_alerts}"
            )

try:
    from mtd.cti_status_reader import CtiAgentStatus
except Exception as e:
    print(f"[RL Manager] ImportError 발생(cti_status_reader): {e}")
    print("  -> Dummy CtiAgentStatus 사용 (CTI 지표/경보 값 고정).")

    class CtiAgentStatus:
        def get_cti_metrics(self) -> Dict[str, float]:
            # 실제 구현에서는 ml/cti_agent.py 또는 bus.log 기반으로 계산
            return {
                "cti_alert_rate": 0.1,
                "blacklist_size_ratio": 0.0,
                "uptime_ratio": 1.0,
                "breach_success_rate": 0.1,
                "decoy_lure_rate": 0.1,
                "current_exposure_mean": 10.0,
                "r_known_ratio": 0.05,
                "r_exploited_ratio": 0.02,
                "seeker_scan_effort": 1.0,
                "seeker_attack_bias": 0.5,
            }

        def get_current_alerts(self) -> Dict[str, float]:
            # 예시: 현재 CTI가 탐지한 공격자 IP별 threat score
            return {
                "10.13.0.200": 0.9,
                "10.13.0.201": 0.3,
            }

# RL-config에서 엔드포인트 목록만 가져다 씀 (없으면 fallback)
try:
    from mtd.rl_config_v05 import REAL_TARGETS, DECOY_TARGETS, ALTERNATE_NODE_TARGETS
except Exception as e:
    print(f"[RL Manager] ImportError 발생(rl_config_v05): {e}")
    print("  -> REAL/DECOY/ALT 타깃 목록을 기본값으로 설정합니다.")
    REAL_TARGETS = [
        {"name": "Real_1", "ip": "10.13.0.2", "port": 14550},
        {"name": "Real_2", "ip": "10.13.0.3", "port": 14550},
        {"name": "Real_3", "ip": "10.13.0.4", "port": 14550},
    ]
    DECOY_TARGETS = [
        {"name": "Decoy_1", "ip": "10.13.0.10", "port": 14550},
        {"name": "Decoy_2", "ip": "10.13.0.11", "port": 14550},
    ]
    ALTERNATE_NODE_TARGETS = [
        {"name": "Alt_1", "ip": "10.13.0.20", "port": 14550},
        {"name": "Alt_2", "ip": "10.13.0.21", "port": 14550},
    ]


# ---------------------------------------------------------------------
# 3. RLDrivenDeceptionManager (PPO_v07_SeekerL*)
# ---------------------------------------------------------------------
class RLDrivenDeceptionManager:
    """
    PPO_v07_SeekerL* 정책을 이용해:
      - MtdScorer → (MTD/Seeker 지표)
      - CtiAgentStatus → (CTI 지표 + 현재 알림 IP)
      - IptablesController → (DNAT / 셔플 / 블랙리스트 실제 적용)

    를 묶어 주는 '전략가(Commander)' 역할 매니저.
    ml/cti_agent_demo.py 에서 주기적으로 step() 호출.
    """

    def __init__(
        self,
        mtd_scorer: MtdScorer,
        cti_status: CtiAgentStatus,
        iptables_controller: IptablesController,
        model_dir: str,
        logger: logging.Logger = None,
        enable_wandb: bool = False,
        wandb_project: str = "mtd_rl_v07_deploy_demo",
        wandb_group: str = "PPO_v07_SeekerL",
    ):
        self.mtd_scorer = mtd_scorer
        self.cti_status = cti_status
        self.iptables_controller = iptables_controller

        self.logger = logger or logging.getLogger("RLDrivenDeceptionManager")
        self.enable_wandb = enable_wandb and (wandb is not None)

        self.model_dir = model_dir
        self.policy = None

        # PPO_v07: norm_metadata.json + final_policy.pth
        self.logger.info("RLDrivenDeceptionManager (PPO_v07_SeekerL*) 초기화 시작...")
        self.logger.info(f"  - RL 모델 디렉토리: {model_dir}")

        # 3.1 norm_metadata.json 로드
        meta_path = os.path.join(model_dir, "norm_metadata.json")
        if not os.path.exists(meta_path):
            self.logger.error(f"  [치명적 오류] norm_metadata.json 없음: {meta_path}")
            raise FileNotFoundError(f"norm_metadata.json not found: {meta_path}")

        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)

        feature_keys: List[str] = meta["FEATURE_KEYS"]
        action_param_keys: List[str] = meta["ACTION_PARAM_KEYS"]
        norm_meta = meta["FEATURE_NORM_METADATA"]

        self.feature_keys: List[str] = feature_keys
        self.action_param_keys: List[str] = action_param_keys
        self.feature_mean: np.ndarray = np.array(norm_meta["means"], dtype=np.float32)
        self.feature_std: np.ndarray = np.array(norm_meta["stds"], dtype=np.float32)

        self.obs_dim: int = len(self.feature_keys)
        self.act_dim: int = len(self.action_param_keys)

        self.logger.info(f"  - RL 정책 버전: {os.path.basename(model_dir)}")
        self.logger.info(f"  - 상태 벡터({self.obs_dim}D): {self.feature_keys}")
        self.logger.info(f"  - 행동 파라미터({self.act_dim}D): {self.action_param_keys}")

        # FEATURE_KEYS 중 last_action_* 인 것과 metric에 해당하는 것 나누기
        self.last_action_prefix = "last_action_"
        self.metric_feature_keys: List[str] = [
            k for k in self.feature_keys if not k.startswith(self.last_action_prefix)
        ]
        self.last_action_feature_keys: List[str] = [
            k for k in self.feature_keys if k.startswith(self.last_action_prefix)
        ]

        # 이전 step에서 사용된 행동 파라미터 (초기값: 0)
        self.current_action_params: np.ndarray = np.zeros(self.act_dim, dtype=np.float32)

        # 3.2 정책 네트워크 로드
        ckpt_path = os.path.join(model_dir, "final_policy.pth")
        if not os.path.exists(ckpt_path):
            self.logger.error(f"  [치명적 오류] RL 모델 파일 없음: {ckpt_path}")
            raise FileNotFoundError(f"final_policy.pth not found: {ckpt_path}")

        self.policy = MTDPolicyNet(self.obs_dim, self.act_dim)
        try:
            state_dict = torch.load(ckpt_path, map_location="cpu")
            # strict=True로 맞춰도 되지만, 혹시 모를 key mismatch를 방지하려면 strict=False도 가능
            self.policy.load_state_dict(state_dict, strict=True)
            self.policy.eval()
            self.logger.info(f"  - RL 모델 가중치 로드 완료: {ckpt_path}")
        except Exception as e:
            self.logger.error(f"  [치명적 오류] RL 모델 로드 실패: {e}")
            self.policy = None

        # 3.3 W&B 초기화 (Eval 모드)
        if self.enable_wandb:
            try:
                wandb.init(
                    project=wandb_project,
                    group=wandb_group,
                    name=f"deploy_{os.path.basename(model_dir)}_{int(time.time())}",
                    config={"model_dir": model_dir, "feature_keys": self.feature_keys, "action_param_keys": self.action_param_keys},
                    reinit=True,
                )
                self.logger.info("  - W&B (Eval 모드) 초기화 완료.")
            except Exception as e:
                self.logger.warning(f"  [경고] W&B 초기화 실패: {e}")
                self.enable_wandb = False

        self.logger.info("RLDrivenDeceptionManager 초기화 완료.")

    # -----------------------------------------------------------------
    # 3.1 메인 Step
    # -----------------------------------------------------------------
    def step(self) -> Dict[str, Any]:
        """
        1회 MTD 의사결정 사이클 수행.
        - mtd_scorer / cti_status에서 메트릭 수집
        - 상태 벡터 구성 및 정규화
        - 정책 네트워크로부터 행동 mean 추론
        - [0,1] 범위 파라미터로 매핑하여 컨트롤러에 실행
        - 결과/지표를 dict로 반환 (필요 시 상위에서 CSV 등으로 저장)
        """
        if self.policy is None:
            self.logger.error("[오류] 정책망이 로드되지 않아 MTD를 실행할 수 없습니다.")
            return {}

        self.logger.info("-" * 60)

        # 1) 메트릭 수집
        metrics_scorer = self.mtd_scorer.collect_metrics()
        metrics_cti = self.cti_status.get_cti_metrics()
        metrics: Dict[str, float] = {**metrics_scorer, **metrics_cti}

        # 2) 상태 벡터 구성 + 정규화
        state_vec = self._build_state_from_metrics(metrics)
        self.logger.info(
            f"[RL-MTD] 메트릭 일부: breach_success_rate={metrics.get('breach_success_rate', 0):.3f}, "
            f"cti_alert_rate={metrics.get('cti_alert_rate', 0):.3f}"
        )

        # 3) 정책망 추론 (mean action)
        raw_action = self.policy.act_greedy(state_vec)  # [-∞, +∞]
        # [-1,+1]로 제한 후 [0,1]로 맵핑 (학습 환경 설정에 맞춰 조정 가능)
        raw_clipped = np.tanh(raw_action)
        action_params = (raw_clipped + 1.0) / 2.0  # [0,1]
        self.current_action_params = action_params

        # 4) 컨트롤러에 실제 MTD 전략 실행
        try:
            self._execute_strategy(action_params)
        except Exception as e:
            self.logger.error(f"[오류] MTD 컨트롤러 실행 중 예외 발생: {e}", exc_info=True)

        self.logger.info(
            f"[RL-MTD] 최종 실행 파라미터 (0.0~1.0): {np.round(action_params, 3).tolist()}"
        )

        # 5) W&B 로깅
        if self.enable_wandb and wandb.run is not None:
            log_data = {}
            for k, v in metrics.items():
                log_data[f"eval_metric/{k}"] = float(v)
            for i, key in enumerate(self.action_param_keys):
                log_data[f"eval_action/{key}"] = float(action_params[i])
            wandb.log(log_data)

        return {"metrics": metrics, "action_params": action_params.tolist()}

    # -----------------------------------------------------------------
    # 3.2 상태 벡터 구성
    # -----------------------------------------------------------------
    def _build_state_from_metrics(self, metrics: Dict[str, float]) -> np.ndarray:
        """
        FEATURE_KEYS 순서를 그대로 맞춰서 상태 벡터를 구성한다.
        - metric feature: metrics 딕셔너리에서 값 가져옴 (없으면 0.0)
        - last_action_* feature: 현재 self.current_action_params에서 가져옴

        state (numpy): shape (obs_dim,)
        """
        vals: List[float] = []

        for key in self.feature_keys:
            if key.startswith(self.last_action_prefix):
                # last_action_xxx → action_param_keys에서 대응 index 찾기
                param_name = key[len(self.last_action_prefix) :]
                if param_name in self.action_param_keys:
                    idx = self.action_param_keys.index(param_name)
                    vals.append(float(self.current_action_params[idx]))
                else:
                    # 혹시 모를 mismatch 대비
                    self.logger.warning(
                        f"[경고] FEATURE_KEY '{key}'에 대응하는 action_param를 찾을 수 없음. 0.0 사용."
                    )
                    vals.append(0.0)
            else:
                # metric feature
                v = metrics.get(key, 0.0)
                vals.append(float(v))

        state = np.array(vals, dtype=np.float32)  # (obs_dim,)
        normed_state = (state - self.feature_mean) / (self.feature_std + 1e-8)
        return normed_state

    # -----------------------------------------------------------------
    # 3.3 행동 파라미터 → 실제 전략
    # -----------------------------------------------------------------
    def _execute_strategy(self, action_params: np.ndarray) -> None:
        """
        action_params: [0,1] 범위 6D
        순서: [dnat_target_focus, dnat_decoy_focus, shuffle_intensity,
               blacklist_aggression, blacklist_duration, decoy_ratio]
        """

        # ---- 1) DNAT 전략 (Real/Decoy/Alternate 분기) ----
        # 두 파라미터를 기반으로 real, decoy, alternate에 대한 "가중치" 구성
        f_real = float(action_params[0])  # dnat_target_focus
        f_decoy = float(action_params[1])  # dnat_decoy_focus
        # 나머지(ALT)는 1 - max(real, decoy) 정도로 직관적 설정
        f_alt = max(0.0, 1.0 - max(f_real, f_decoy))

        logits = np.array([f_real, f_decoy, f_alt], dtype=np.float32)
        # softmax
        exps = np.exp(logits - np.max(logits))
        probs = exps / (np.sum(exps) + 1e-8)

        choice = np.random.choice(["REAL", "DECOY", "ALT"], p=probs)
        self.logger.info(f"[RL-MTD] DNAT 전략: Probs(R/D/A)={np.round(probs, 3)} -> 선택={choice}")

        if choice == "REAL":
            target = random.choice(REAL_TARGETS)
        elif choice == "DECOY":
            target = random.choice(DECOY_TARGETS)
        else:
            target = random.choice(ALTERNATE_NODE_TARGETS)

        self.iptables_controller.apply_dnat_redirect(target["ip"], target["port"])

        # ---- 2) 셔플 전략 ----
        shuffle_intensity = float(action_params[2])  # [0,1]
        if shuffle_intensity > 0.75:
            self.logger.info(
                f"[RL-MTD] 셔플 전략: intensity={shuffle_intensity:.3f} > 0.75, 'mtd_service_swap.sh' 실행."
            )
            self.iptables_controller.run_script("mtd_service_swap.sh")

        # ---- 3) 블랙리스트 전략 ----
        # bl_aggr: [0,1] -> threshold (1.0 ~ 0.1) 역방향
        bl_aggr = float(action_params[3])
        bl_dur_param = float(action_params[4])

        bl_threshold = self._map_value(1.0 - bl_aggr, 0.1, 1.0)  # aggression↑ → threshold↓
        # duration: [0,1] -> [30초, 600초], 0.99↑는 영구
        if bl_dur_param > 0.99:
            bl_duration = -1  # 영구
        else:
            bl_duration = int(self._map_value(bl_dur_param, 30, 600))

        self.logger.info(
            f"[RL-MTD] BLK 정책: score>{bl_threshold:.3f} 이면 duration={bl_duration}초 차단."
        )

        current_alerts = self.cti_status.get_current_alerts()
        self.iptables_controller.update_blacklist(current_alerts, bl_threshold, bl_duration)

        # ---- 4) Decoy Ratio 정책 (지금은 로그만 찍고, honeypot/decoy 컨트롤러 연동 시 사용) ----
        decoy_ratio = float(action_params[5])
        self.logger.info(f"[RL-MTD] Decoy Ratio 정책 (미사용): decoy_ratio={decoy_ratio:.3f}")

    @staticmethod
    def _map_value(val_0_to_1: float, v_min: float, v_max: float) -> float:
        """
        [0,1] → [v_min, v_max] 선형 맵핑
        """
        return v_min + (v_max - v_min) * float(val_0_to_1)


# ---------------------------------------------------------------------
# 4. 단독 실행 테스트 (로컬 quick test 용도)
# ---------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)7s] %(name)s - %(message)s",
    )
    logger = logging.getLogger("RLDrivenDeceptionManager_MainTest")

    # 예시: mtd/rl_models/PPO_v07_SeekerL2 사용
    model_dir = "./mtd/rl_models/PPO_v07_SeekerL2"
    logger.info("=== RLDrivenDeceptionManager 단독 테스트 시작 ===")

    scorer = MtdScorer()
    cti_status = CtiAgentStatus()
    ipt = IptablesController(logger=logger)

    mgr = RLDrivenDeceptionManager(
        mtd_scorer=scorer,
        cti_status=cti_status,
        iptables_controller=ipt,
        model_dir=model_dir,
        logger=logger,
        enable_wandb=False,
    )

    for i in range(5):
        logger.info(f"\n===== Step {i+1} =====")
        out = mgr.step()
        time.sleep(2.0)

    logger.info("=== RLDrivenDeceptionManager 단독 테스트 종료 ===")
