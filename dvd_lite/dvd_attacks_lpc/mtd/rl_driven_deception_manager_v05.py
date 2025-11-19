#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# File: dvd_lite/dvd_attacks_lpc/mtd/rl_driven_deception_manager_v05.py
"""
RL 기반 MTD 의사결정 매니저 (실전 배포용 v05 - Passive CTI)

[2025-11-19 Upgrade 요약]
- 학습 시 사용한 mtd_scoring.MtdScorer 지표들을 그대로 가져와 테스트베드에서 평가용으로 사용
- wandb에 eval_metric/*, eval_action/* 형태로 모든 지표를 로깅 (PNG 없이도 대시보드에서 비교 가능)
- WANDB_PROJECT / WANDB_ENTITY / WANDB_GROUP / WANDB_RUN_NAME / SEEKER_LEVEL 환경변수를 읽어
  실제 학습 run과 동일한 프로젝트/엔티티 아래에서 비교 가능
- 블랙리스트 정책은 IptablesController.update_blacklist()를 통해
  "일정 시간 동안 공격 DROP" 형태로 구현 (테스트베드에서 출발 IP를 바꾸기 어려운 상황 가정)
"""

import os
import json
import logging
import time
import random
from typing import Dict, Any, List, Optional

import torch
import torch.nn as nn
import numpy as np

try:
    import wandb  # type: ignore
except ImportError:  # pragma: no cover - 배포 환경에서만 사용
    wandb = None  # type: ignore


# --- [1] RL 정책 네트워크 (rl_model_v05.py와 동일 구조 가정) --------------------
class MTDPolicyNet(nn.Module):
    def __init__(self, obs_dim: int, act_dim: int):
        super().__init__()
        self.body = nn.Sequential(
            nn.Linear(obs_dim, 128),
            nn.Tanh(),
            nn.Linear(128, 128),
            nn.Tanh(),
        )
        self.actor_mean = nn.Sequential(
            nn.Linear(128, act_dim),
            nn.Tanh(),
        )
        self.actor_log_std = nn.Parameter(torch.zeros(1, act_dim))

    def forward(self, x: torch.Tensor):
        body_out = self.body(x)
        mean = self.actor_mean(body_out)
        log_std = self.actor_log_std.expand_as(mean)
        std = torch.exp(log_std)
        return torch.distributions.normal.Normal(mean, std)

    def act_greedy(self, obs_vec: np.ndarray) -> np.ndarray:
        """배포용: 평균(mean)만 사용하는 deterministic policy."""
        self.eval()
        with torch.no_grad():
            x = torch.from_numpy(obs_vec).float().unsqueeze(0)
            body_out = self.body(x)
            mean = self.actor_mean(body_out)
            return mean.squeeze(0).cpu().numpy()


# --- [2] MTD Scorer / Controller / CTI 인터페이스 임포트 -------------------------
try:
    # 학습과 동일한 지표/상태 구성을 위해 필수
    from mtd.mtd_scoring import MtdScorer  # type: ignore
    from mtd.controller.iptables_mtd_controller import IptablesController  # type: ignore
    from mtd.cti_status_reader import CtiAgentStatus  # 사용자가 구현해야 하는 CTI Reader  # type: ignore

    from mtd.rl_config_v05 import (  # type: ignore
        FEATURE_KEYS,
        OBS_DIM,
        ACTION_PARAM_KEYS,
        ACTION_DIM,
        REAL_TARGETS,
        DECOY_TARGETS,
        ALTERNATE_NODE_TARGETS,
        METRIC_FEATURE_KEYS,
    )
except ImportError as e:  # pragma: no cover - 개발/테스트용 더미
    print(f"[RL Manager v05] ImportError 발생: {e}")
    print("  -> MtdScorer / IptablesController / CtiAgentStatus / rl_config_v05 더미 클래스로 대체합니다.")

    class MtdScorer:  # type: ignore
        """테스트용 더미 Scorer. 실제 테스트베드에선 mtd.mtd_scoring.MtdScorer 사용."""

        def collect_metrics(self) -> Dict[str, float]:
            return {
                "S_MTD": 0.5,
                "R_succ": 0.2,
                "R_A_norm": 0.3,
                "C_M": 0.1,
                "breach_success_rate": 0.2,
                "decoy_lure_rate": 0.4,
                "alternate_node_health": 0.9,
                "system_cost": 0.1,
                "ttbr": 120.0,
                "service_uptime_ratio": 0.99,
                "attack_orchestrator_running": 1.0,
            }

    class IptablesController:  # type: ignore
        def apply_dnat_redirect(self, ip: str, port: int):
            print(f"[DUMMY IPTABLES] DNAT -> {ip}:{port}")

        def run_script(self, script_name: str):
            print(f"[DUMMY IPTABLES] run_script: {script_name}")

        def update_blacklist(self, alerts: Dict[str, float], threshold: float, duration_sec: int):
            print(f"[DUMMY IPTABLES] update_blacklist: threshold={threshold:.2f}, duration={duration_sec}s, alerts={alerts}")

    class CtiAgentStatus:  # type: ignore
        def get_cti_metrics(self) -> Dict[str, float]:
            # 예시: CTI agent demo 버전에서 쓸 수 있는 최소 메트릭
            return {
                "cti_alert_rate": 0.1,
                "blacklist_size": 1.0,
                "seeker_ip_change_rate": 0.0,
            }

        def get_current_alerts(self) -> Dict[str, float]:
            # {"공격자 IP": 공격 위험도}
            return {
                "10.13.0.200": 0.85,
            }

    # rl_config_v05 더미 값
    FEATURE_KEYS = [
        "breach_success_rate",
        "decoy_lure_rate",
        "alternate_node_health",
        "system_cost",
        "ttbr",
        "service_uptime_ratio",
        "attack_orchestrator_running",
        "cti_alert_rate",
        "blacklist_size",
        "seeker_ip_change_rate",
    ]
    METRIC_FEATURE_KEYS = FEATURE_KEYS[:]  # 실제 코드와 동일한 순서여야 함
    OBS_DIM = len(METRIC_FEATURE_KEYS) + 6  # (메트릭 10개 + 직전 action 6개) 예시
    ACTION_PARAM_KEYS = [
        "p_DNAT_real",
        "p_DNAT_decoy",
        "p_DNAT_alternate",
        "shuffle_intensity",
        "blacklist_threshold",
        "blacklist_duration",
    ]
    ACTION_DIM = len(ACTION_PARAM_KEYS)
    REAL_TARGETS = [{"ip": "10.13.0.2", "port": 14550}]
    DECOY_TARGETS = [{"ip": "10.13.0.10", "port": 14550}]
    ALTERNATE_NODE_TARGETS = [{"ip": "10.13.0.20", "port": 14550}]


# --- [3] RL 의사결정 매니저 ---------------------------------------------------
class RLDrivenDeceptionManager:
    """
    MTD Scorer, CTI Agent, Iptables Controller, RL Policy를 연결하는 '전략가'(Commander) 역할.

    - 학습 시 사용한 v05 정책(mtd_policy_ver_05.pth)을 로드하여
      테스트베드에서 주기적으로 MTD 행동(DNAT, Shuffle, Blacklist)을 수행.
    - 각 step 마다 mtd_scoring.MtdScorer 지표 + CTI 지표를 수집해서 wandb에 eval_metric/* 으로 로깅.
    """

    def __init__(
        self,
        mtd_scorer: MtdScorer,
        cti_status: CtiAgentStatus,
        iptables_controller: IptablesController,
        model_dir: Optional[str] = None,
        logger: Optional[logging.Logger] = None,
        enable_wandb: bool = False,
        wandb_project: Optional[str] = None,
        wandb_group: Optional[str] = None,
        wandb_entity: Optional[str] = None,
        seeker_level: Optional[str] = None,
    ):
        self.mtd_scorer = mtd_scorer
        self.cti_status = cti_status
        self.iptables_controller = iptables_controller

        self.logger = logger or logging.getLogger(__name__)
        self.enable_wandb = bool(enable_wandb and wandb is not None)
        self.seeker_level = seeker_level or os.getenv("SEEKER_LEVEL", "unknown")

        self._log("RLDrivenDeceptionManager (v05 - Passive CTI) 초기화 시작...")

        # 1. 모델 디렉토리 설정
        if model_dir is None:
            model_dir = os.environ.get("MTD_RL_MODEL_DIR", "/opt/mtd/rl_models/ver_05")
        self.model_dir = model_dir
        self._log(f"  - RL 모델 디렉토리: {model_dir}")

        # 2. 메타파일(.json) 로드
        meta_path = os.path.join(model_dir, "mtd_policy_ver_05_meta.json")
        if not os.path.exists(meta_path):
            self._log(f"  [치명적 오류] RL 메타 파일 없음: {meta_path}", level="error")
            raise FileNotFoundError(f"필수 메타 파일이 없습니다: {meta_path}")
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        self.meta = meta

        # 3. 메타 정보 파싱 (rl_config_v05.py와 동일해야 함)
        self.version: str = meta.get("version", "unknown_v05")
        self.feature_keys: List[str] = meta["feature_keys"]
        feature_norm = meta.get("feature_norm", {"mean": [0.0] * meta["obs_dim"], "std": [1.0] * meta["obs_dim"]})
        self.feature_mean: np.ndarray = np.array(feature_norm["mean"], dtype=np.float32)
        self.feature_std: np.ndarray = np.array(feature_norm["std"], dtype=np.float32)
        self.action_param_keys: List[str] = meta["action_param_keys"]
        obs_dim: int = meta["obs_dim"]
        act_dim: int = meta["act_dim"]

        if obs_dim != OBS_DIM or act_dim != ACTION_DIM:
            self._log(
                f"[경고] 메타파일 차원(obs={obs_dim}, act={act_dim})과 rl_config_v05(OBS_DIM={OBS_DIM}, ACTION_DIM={ACTION_DIM}) 불일치!",
                level="warning",
            )

        self._log(f"  - RL 정책 버전: {self.version} (Continuous, Passive CTI)")
        self._log(f"  - 상태 벡터({obs_dim}D): {self.feature_keys}")
        self._log(f"  - 행동 파라미터({act_dim}D): {self.action_param_keys}")

        # 직전 행동 파라미터 (obs에 포함됨)
        self.current_action_params = np.zeros(act_dim, dtype=np.float32)

        # 4. 정책 네트워크(.pth) 로드
        ckpt_path = os.path.join(model_dir, meta["model_file"])
        if not os.path.exists(ckpt_path):
            self._log(f"  [치명적 오류] RL 모델 파일 없음: {ckpt_path}", level="error")
            raise FileNotFoundError(f"필수 모델 파일이 없습니다: {ckpt_path}")

        self.policy = MTDPolicyNet(obs_dim, act_dim)
        try:
            state_dict = torch.load(ckpt_path, map_location="cpu")
            self.policy.load_state_dict(state_dict)
            self.policy.eval()
            self._log(f"  - RL 모델 가중치 로드 완료: {ckpt_path}")
        except Exception as e:  # pragma: no cover - IO 문제
            self.policy = None
            self._log(f"  [치명적 오류] RL 모델 로드 실패: {e}", level="error")

        # 5. wandb (Eval 모드) 초기화
        if self.enable_wandb:
            try:
                project = wandb_project or os.getenv("WANDB_PROJECT", "mtd_rl_v06_comparison")
                entity = wandb_entity or os.getenv("WANDB_ENTITY", None)
                group = wandb_group or os.getenv("WANDB_GROUP", "RL_Deploy_v05")
                run_name = os.getenv(
                    "WANDB_RUN_NAME",
                    f"deploy_MTD_v05_L{self.seeker_level}_{int(time.time())}",
                )

                wb_config = dict(meta)
                wb_config.update(
                    {
                        "deploy_mode": "testbed",
                        "seeker_level": self.seeker_level,
                        "model_dir": model_dir,
                    }
                )

                wandb.init(
                    project=project,
                    entity=entity,
                    group=group,
                    name=run_name,
                    config=wb_config,
                )
                self._log(
                    f"  - W&B 초기화 완료: project={project}, entity={entity}, group={group}, run={run_name}"
                )
            except Exception as e:  # pragma: no cover - 네트워크 문제 등
                self._log(f"  [경고] W&B 초기화 실패: {e}", level="warning")
                self.enable_wandb = False

        self._log("RLDrivenDeceptionManager (v05) 초기화 완료.")

    # ------------------------------------------------------------------
    # 메인 스텝: 테스트베드에서 일정 주기(예: 30~60초)마다 호출
    # ------------------------------------------------------------------
    def step(self) -> Dict[str, Any]:
        """
        MTD 의사결정 1 사이클 실행.

        1) mtd_scoring.MtdScorer로부터 공격/방어 지표 수집
        2) CtiAgentStatus로부터 CTI 지표 수집
        3) (지표 + 직전 행동) -> 정규화된 상태 벡터 생성
        4) RL Policy로부터 6D 행동 파라미터 결정
        5) IptablesController를 통해 DNAT / Shuffle / Blacklist 실행
        6) 모든 지표와 행동 파라미터를 wandb에 eval_metric/*, eval_action/* 으로 로깅
        """
        self._log("-" * 40)

        if self.policy is None:
            self._log("[오류] 정책망이 로드되지 않아 MTD를 실행할 수 없습니다.", level="error")
            return {}

        # 1. (Scorer/CTI) 현재 전장 상황 메트릭 수집
        metrics_scorer = self.mtd_scorer.collect_metrics()
        metrics_cti = self.cti_status.get_cti_metrics()
        metrics: Dict[str, float] = {**metrics_scorer, **metrics_cti}

        # 2. (Manager) 메트릭 + 직전 행동 -> 정규화 상태 벡터
        state_vec_normed = self._build_state_from_metrics(metrics)

        # 디버깅용 핵심 지표 로그 (예: S_MTD, R_succ, breach_success_rate 등)
        s_mtd = metrics.get("S_MTD", 0.0)
        r_succ = metrics.get("R_succ", metrics.get("breach_success_rate", 0.0))
        self._log(
            f"[RL-MTD] 수집 메트릭: S_MTD={s_mtd:.3f}, R_succ={r_succ:.3f}, "
            f"cti_alert_rate={metrics.get('cti_alert_rate', 0.0):.3f}"
        )

        # 3. (Policy) 상태 -> 행동 평균 결정
        action_vector_mean = self.policy.act_greedy(state_vec_normed)

        # 4. (Manager) [-1,1] -> [0,1] 스케일링
        action_params = (action_vector_mean + 1.0) / 2.0
        self.current_action_params = action_params

        # 5. (Controller) 실제 iptables / 스크립트 / 블랙리스트 조작
        try:
            self._execute_strategy(action_params)
        except Exception as e:  # pragma: no cover
            self._log(f"[오류] MTD 컨트롤러 실행 중 예외 발생: {e}", level="error")

        self._log(f"[RL-MTD] 최종 실행 파라미터 (0~1): {np.round(action_params, 3).tolist()}")

        # 6. (Logger) wandb 로깅
        if self.enable_wandb and wandb is not None and wandb.run is not None:
            log_data: Dict[str, Any] = {}

            # (1) MTD/CTI 지표: 학습에서 사용한 지표와 동일한 키를 eval_metric/* 로 로깅
            for k, v in metrics.items():
                try:
                    log_data[f"eval_metric/{k}"] = float(v)
                except (TypeError, ValueError):
                    continue

            # (2) 행동 파라미터
            for i, key in enumerate(ACTION_PARAM_KEYS):
                log_data[f"eval_action/{key}"] = float(action_params[i])

            # (3) 편의상 seeker_level, version 정보도 함께 로깅
            log_data["eval_meta/seeker_level"] = self.seeker_level
            log_data["eval_meta/version"] = self.version

            wandb.log(log_data)

        return {"metrics": metrics, "action_params": action_params}

    # ------------------------------------------------------------------
    # RL 행동 벡터 -> 실제 iptables / 스크립트 / 블랙리스트 실행
    # ------------------------------------------------------------------
    def _execute_strategy(self, action_params: np.ndarray):
        """6D (0.0~1.0) 파라미터를 실제 컨트롤러 메소드로 변환."""

        # --- 1. DNAT 전략 (파라미터 0, 1, 2) ---
        dnat_logits = action_params[0:3]
        # softmax
        exp_logits = np.exp(dnat_logits - np.max(dnat_logits))
        dnat_probs = exp_logits / np.sum(exp_logits + 1e-8)
        dnat_target_type = np.random.choice(["REAL", "DECOY", "ALTERNATE"], p=dnat_probs)
        self._log(f"[RL-MTD] DNAT 전략: Probs(R/D/A)={np.round(dnat_probs, 3)} -> 선택={dnat_target_type}")

        if dnat_target_type == "REAL":
            target = random.choice(REAL_TARGETS)
        elif dnat_target_type == "DECOY":
            target = random.choice(DECOY_TARGETS)
        else:
            target = random.choice(ALTERNATE_NODE_TARGETS)

        self.iptables_controller.apply_dnat_redirect(target["ip"], target["port"])

        # --- 2. 셔플 전략 (파라미터 3) ---
        shuffle_intensity = float(action_params[3])
        if shuffle_intensity > 0.75:
            self._log(
                f"[RL-MTD] 셔플 전략: 강도={shuffle_intensity:.3f} > 0.75. 'mtd_service_swap.sh' 실행."
            )
            self.iptables_controller.run_script("mtd_service_swap.sh")
        else:
            self._log(f"[RL-MTD] 셔플 전략: 강도={shuffle_intensity:.3f} (임계값 이하, 셔플 미실행)")

        # --- 3. 블랙리스트 전략 (파라미터 4, 5) ---
        bl_param_threshold = float(action_params[4])
        bl_param_duration = float(action_params[5])

        # threshold: (val=0 -> 1.0), (val=1 -> 0.1) 역방향 매핑
        bl_threshold = self._map_value(bl_param_threshold, 1.0, 0.1)
        # duration: (val=0 -> 300초), (val=1 -> -1[영구]) 선형 매핑
        bl_duration = int(self._map_value(bl_param_duration, 300.0, -1.0))
        if bl_param_duration > 0.95:
            bl_duration = -1  # 거의 1.0이면 영구 차단

        self._log(
            f"[RL-MTD] 블랙리스트 정책: CTI 경보 > {bl_threshold:.2f} 이면 {bl_duration}s 동안 DROP."
            " (테스트베드에서는 이 기간 동안 Seeker 트래픽이 차단됨)"
        )

        # CTI Agent 가 보고한 현재 경보 목록 (예: {"10.13.0.200": 0.87, ...})
        current_alerts = self.cti_status.get_current_alerts()

        # 실제 iptables DROP 규칙 적용
        self.iptables_controller.update_blacklist(current_alerts, bl_threshold, bl_duration)

    # ------------------------------------------------------------------
    # 유틸
    # ------------------------------------------------------------------
    def _map_value(self, val_0_to_1: float, range_min: float, range_max: float) -> float:
        """(0.0~1.0) 값을 [range_min, range_max] 범위로 선형 보간."""
        return range_min + (range_max - range_min) * float(val_0_to_1)

    def _build_state_from_metrics(self, metrics: Dict[str, float]) -> np.ndarray:
        """
        METRIC_FEATURE_KEYS 순서대로 메트릭을 뽑고,
        직전 행동 파라미터(self.current_action_params)를 붙여서
        feature_norm(mean/std) 기준으로 정규화한 상태 벡터를 만든다.
        """
        vals_metrics: List[float] = []
        for key in METRIC_FEATURE_KEYS:
            val = metrics.get(key)
            if val is None:
                self._log(f"[경고] 상태 벡터 키 '{key}'가 메트릭에 없습니다! 0.0으로 대체.", level="warning")
                val = 0.0
            vals_metrics.append(float(val))

        state = np.concatenate(
            [
                np.array(vals_metrics, dtype=np.float32),
                self.current_action_params.astype(np.float32),
            ]
        )

        if state.shape[0] != self.feature_mean.shape[0]:
            self._log(
                f"[경고] 상태 벡터 차원 불일치: state={state.shape[0]}, norm_mean={self.feature_mean.shape[0]}",
                level="warning",
            )

        normed_state = (state - self.feature_mean) / (self.feature_std + 1e-8)
        return normed_state.astype(np.float32)

    def _log(self, msg: str, level: str = "info") -> None:
        if self.logger:
            if level == "info":
                self.logger.info(msg)
            elif level == "warning":
                self.logger.warning(msg)
            elif level == "error":
                self.logger.error(msg)
            else:
                self.logger.debug(msg)
        else:
            print(f"[{level.upper()}] {msg}")


# ----------------------------------------------------------------------
# 단독 실행 테스트용 (실제 배포에선 사용 안 해도 됨)
# ----------------------------------------------------------------------
if __name__ == "__main__":  # pragma: no cover
    print("--- RLDrivenDeceptionManager (v05) 로컬 테스트 ---")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    main_logger = logging.getLogger("MTD_RL_Deploy_Test_v05")

    MODEL_DIRECTORY = "./rl_models/ver_05"
    os.makedirs(MODEL_DIRECTORY, exist_ok=True)

    try:
        # rl_config_v05와 동일한 구조의 더미 메타/모델 생성
        from mtd.rl_config_v05 import (  # type: ignore
            ACTION_PARAM_KEYS,
            ACTION_DIM,
            FEATURE_KEYS,
            OBS_DIM,
        )

        fake_meta_path = os.path.join(MODEL_DIRECTORY, "mtd_policy_ver_05_meta.json")
        fake_meta = {
            "model_file": "mtd_policy_v05.pth",
            "version": "ver_05_dummy",
            "action_space_type": "continuous",
            "obs_dim": OBS_DIM,
            "act_dim": ACTION_DIM,
            "feature_keys": FEATURE_KEYS,
            "feature_norm": {"mean": [0.0] * OBS_DIM, "std": [1.0] * OBS_DIM},
            "action_param_keys": ACTION_PARAM_KEYS,
        }
        with open(fake_meta_path, "w", encoding="utf-8") as f:
            json.dump(fake_meta, f, ensure_ascii=False, indent=2)

        fake_ckpt_path = os.path.join(MODEL_DIRECTORY, "mtd_policy_v05.pth")
        dummy_net = MTDPolicyNet(obs_dim=OBS_DIM, act_dim=ACTION_DIM)
        torch.save(dummy_net.state_dict(), fake_ckpt_path)
        print(f"[테스트] 더미 v05 모델/메타 파일 생성 완료: {MODEL_DIRECTORY}")
    except Exception as e:
        print(f"[테스트] 더미 파일 생성 실패: {e}. 기존 파일이 있다고 가정하고 진행합니다.")

    try:
        scorer = MtdScorer()
        cti_status = CtiAgentStatus()
        controller_ipt = IptablesController()

        manager = RLDrivenDeceptionManager(
            mtd_scorer=scorer,
            cti_status=cti_status,
            iptables_controller=controller_ipt,
            model_dir=MODEL_DIRECTORY,
            logger=main_logger,
            enable_wandb=False,
        )

        for i in range(3):
            print(f"\n===== MTD 의사결정 사이클 {i + 1} =====")
            result = manager.step()
            print("Result:", result)
            time.sleep(2)
    except FileNotFoundError as e:
        print(f"\n[테스트 실패] 모델 파일을 찾을 수 없습니다: {e}")
    except Exception as e:
        print(f"\n[테스트 실패] 예기치 않은 오류 발생: {e}")
