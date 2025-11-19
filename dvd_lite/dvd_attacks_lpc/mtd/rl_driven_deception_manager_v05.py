# File: MTD_full_testbed/dvd_lite/dvd_attacks_lpc/mtd/rl_driven_deception_manager_v05.py
#
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[핵심 수정 8/8] RL 기반 MTD 의사결정 매니저 (실전 배포용 v05 - Passive CTI)

- '전략가(Commander)' 역할. mtd_policy_v05.pth와 meta.json 로드.
- [v04 대비 변경점]
- CtiPolicyController (제어용) -> CtiAgentStatus (관측용)로 변경
- RL 에이전트가 `ml/cti_agent.py`의 "경보율"을 입력받아,
- "직접" `IptablesController`의 `apply_blacklist_ip`를 호출하여 차단 실행
"""

import os
import json
import logging
import time
import random
from typing import Dict, Any, List

import torch
import torch.nn as nn
import numpy as np
try:
    import wandb
except ImportError:
    wandb = None

# --- [1] RL 정책 네트워크 (rl_model_v05.py와 동일한 구조) ---
class MTDPolicyNet(nn.Module):
    def __init__(self, obs_dim: int, act_dim: int):
        super().__init__()
        self.body = nn.Sequential(
            nn.Linear(obs_dim, 128), nn.Tanh(),
            nn.Linear(128, 128), nn.Tanh(),
        )
        self.actor_mean = nn.Sequential(
            nn.Linear(128, act_dim), nn.Tanh()
        )
        self.actor_log_std = nn.Parameter(torch.zeros(1, act_dim))

    def forward(self, x: torch.Tensor):
        body_out = self.body(x)
        mean = self.actor_mean(body_out)
        log_std = self.actor_log_std.expand_as(mean)
        std = torch.exp(log_std)
        return torch.distributions.normal.Normal(mean, std)

    def act_greedy(self, obs_vec: np.ndarray) -> np.ndarray:
        self.eval() 
        with torch.no_grad():
            x = torch.from_numpy(obs_vec).float().unsqueeze(0)
            body_out = self.body(x)
            mean = self.actor_mean(body_out)
            return mean.squeeze(0).cpu().numpy()

# --- [2] MTD Scorer/Controller/CTI 인터페이스 (임포트) ---
try:
    # [Solve #1] mtd/mtd_scoring.py (신규 생성)
    from mtd.mtd_scoring import MtdScorer
    # [Solve #3] mtd/controller/iptables_mtd_controller.py (신규 생성)
    from mtd.controller.iptables_mtd_controller import IptablesController
    
    # [User Task #2] mtd/cti_status_reader.py (사용자가 구현 가정)
    # [!] 이 파일은 사용자가 직접 구현해야 합니다. (v04 한계점 #2)
    #     ml/cti_agent.py의 bus.log(ai_cti_alert)를 파싱하여 
    #     `get_cti_metrics()` (cti_alert_rate 등 3개)를 반환해야 합니다.
    from mtd.cti_status_reader import CtiAgentStatus 
    
    # [v05] RL 계약 임포트
    from mtd.rl_config_v05 import (
        FEATURE_KEYS, OBS_DIM, ACTION_PARAM_KEYS, ACTION_DIM,
        REAL_TARGETS, DECOY_TARGETS, ALTERNATE_NODE_TARGETS,
        METRIC_FEATURE_KEYS
    )
except ImportError as e:
    print(f"[RL Manager v05] 치명적 오류: 필요한 모듈 임포트 실패. {e}")
    print("       (MtdScorer, IptablesController, CtiAgentStatus, rl_config_v05)")
    # (v05 테스트용 Placeholder)
    class MtdScorer:
        def collect_metrics(self) -> Dict[str, float]:
            return {"breach_success_rate": 0.1, "decoy_lure_rate": 0.1, "alternate_node_health": 1.0, "system_cost": 0.1, "ttbr": 200.0, "service_uptime_ratio": 1.0, "attack_orchestrator_running": 1.0}
    class IptablesController:
        def apply_dnat_redirect(self, ip, port): print(f"DUMMY: DNAT -> {ip}:{port}")
        def run_script(self, script_name): print(f"DUMMY: RUN {script_name}")
        def update_blacklist(self, alerts, threshold, duration): print(f"DUMMY: BLACKLIST (Th:{threshold:.2f}, Dur:{duration}s)")
    class CtiAgentStatus:
        def get_cti_metrics(self) -> Dict[str, float]:
            return {"cti_alert_rate": 0.1, "blacklist_size": 1.0, "seeker_ip_change_rate": 0.1}
        def get_current_alerts(self) -> Dict[str, float]:
            # [v05] CTI가 탐지한 <IP, 위협 점수> 딕셔너리 반환 (가정)
            return {"10.13.0.200": 0.85, "10.13.0.201": 0.3}
            
    from mtd.rl_config_v05 import (
        FEATURE_KEYS, OBS_DIM, ACTION_PARAM_KEYS, ACTION_DIM,
        REAL_TARGETS, DECOY_TARGETS, ALTERNATE_NODE_TARGETS,
        METRIC_FEATURE_KEYS
    )
# ----------------------------------------------------

# --- [3] RL 의사결정 매니저 (v05) ---
class RLDrivenDeceptionManager:
    """
    MTD Scorer, CTI (수동 센서), MTD Controller, RL Policy를 연결하는 '전략가' (v05)
    """
    def __init__(self,
                 mtd_scorer: MtdScorer,
                 cti_status: CtiAgentStatus,
                 iptables_controller: IptablesController,
                 model_dir: str = None,
                 logger: logging.Logger = None,
                 enable_wandb: bool = False,
                 wandb_project: str = "MTD_Testbed_Deploy",
                 wandb_group: str = "RL_Managed_v05"):
        
        self.mtd_scorer = mtd_scorer
        self.cti_status = cti_status
        self.iptables_controller = iptables_controller
        
        self.logger = logger
        self.enable_wandb = enable_wandb if wandb is not None else False
        
        self._log("RLDrivenDeceptionManager (v05 - Passive CTI) 초기화 시작...")

        # 1. 모델 경로 설정
        if model_dir is None:
            model_dir = os.environ.get("MTD_RL_MODEL_DIR", "/opt/mtd/rl_models/ver_05") # [v05]
        self._log(f"  - RL 모델 디렉토리: {model_dir}")

        # 2. 메타파일(.json) 로드
        meta_path = os.path.join(model_dir, "mtd_policy_ver_05_meta.json") # [v05]
        if not os.path.exists(meta_path):
            self._log(f"  [치명적 오류] RL 메타 파일 없음: {meta_path}", level="error")
            raise FileNotFoundError(f"필수 메타 파일이 없습니다: {meta_path}")
        with open(meta_path, "r", encoding="utf-8") as f: meta = json.load(f)
        
        # 3. 메타 정보 파싱 (rl_config_v05.py와 동일해야 함)
        self.version: str = meta.get("version", "unknown_v05")
        self.feature_keys: List[str] = meta["feature_keys"]
        self.feature_mean: np.ndarray = np.array(meta["feature_norm"]["mean"], dtype=np.float32)
        self.feature_std: np.ndarray = np.array(meta["feature_norm"]["std"], dtype=np.float32)
        self.action_param_keys: List[str] = meta["action_param_keys"]
        obs_dim: int = meta["obs_dim"]
        act_dim: int = meta["act_dim"]
        
        if obs_dim != OBS_DIM or act_dim != ACTION_DIM:
            self._log(f"[경고] 메타파일과 rl_config_v05.py의 차원 불일치!", level="warning")

        self._log(f"  - RL 정책 버전: {self.version} (Continuous, Passive CTI)")
        self._log(f"  - 상태 벡터({obs_dim}D): {self.feature_keys}")
        self._log(f"  - 행동 파라미터({act_dim}D): {self.action_param_keys}")
        
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
        except Exception as e:
            self.policy = None
            self._log(f"  [치명적 오류] RL 모델 로드 실패: {e}", level="error")

        # 5. W&B (Eval 모드) 초기화
        if self.enable_wandb:
            try:
                wandb.init(
                    project=wandb_project, group=wandb_group,
                    name=f"deploy_run_{self.version}_{int(time.time())}",
                    config=meta
                )
                self._log("  - W&B (Eval 모드) 초기화 완료.")
            except Exception as e:
                self._log(f"  [경고] W&B 초기화 실패: {e}", level="warning")
                self.enable_wandb = False
        
        self._log("RLDrivenDeceptionManager (v05) 초기화 완료.")

    def step(self) -> Dict[str, Any]:
        """ [v05 메인 함수] MTD 의사결정 1 사이클 실행 (예: 60초마다 호출) """
        self._log("-" * 30)
        
        if self.policy is None:
            self._log("[오류] 정책망이 로드되지 않아 MTD를 실행할 수 없습니다.", level="error")
            return {}

        # 1. (Scorer/CTI) [관측] 현재 전장 상황 메트릭 수집
        metrics_scorer = self.mtd_scorer.collect_metrics()
        metrics_cti = self.cti_status.get_cti_metrics()
        metrics = {**metrics_scorer, **metrics_cti}
        
        # 2. (Manager) [상태 변환] 메트릭(10D) + 이전 행동(6D) -> 16D 정규화 상태 벡터
        state_vec_normed = self._build_state_from_metrics(metrics)
        self._log(f"[RL-MTD] 수집 메트릭: breach_rate={metrics.get('breach_success_rate', 0):.2f}, cti_alert_rate={metrics.get('cti_alert_rate', 0):.2f}")

        # 3. (Policy) [정책 결정] 상태 -> 6D 행동 평균(Mean) 결정
        action_vector_mean = self.policy.act_greedy(state_vec_normed)
        
        # 4. (Manager) [행동 변환] ( -1.0~1.0 ) -> ( 0.0~1.0 ) 스케일링
        action_params = (action_vector_mean + 1.0) / 2.0
        self.current_action_params = action_params
        
        # 5. (Controller) [행동 실행] 6D 파라미터를 실제 MTD 행동으로 변환
        try:
            self._execute_strategy(action_params, metrics_cti)
        except Exception as e:
            self.logger.error(f"[오류] MTD 컨트롤러 실행 중 예외 발생: {e}", exc_info=True)
            
        log_msg = f"[RL-MTD] 최종 실행 파라미터 (0.0~1.0): {np.round(action_params, 2).tolist()}"
        self._log(log_msg)
        
        # 6. (Logger) [로깅] 결과 로깅 (wandb 포함)
        if self.enable_wandb and wandb.run:
            log_data = {}
            for k, v in metrics.items(): log_data[f"eval_metric/{k}"] = float(v)
            for i, key in enumerate(ACTION_PARAM_KEYS):
                 log_data[f"eval_action/{key}"] = float(action_params[i])
            wandb.log(log_data)

        return {"metrics": metrics, "action_params": action_params}
        
    def _execute_strategy(self, action_params: np.ndarray, cti_metrics: Dict[str, float]):
        """ [v05] 6D (0.0~1.0) 파라미터를 실제 컨트롤러 메소드로 변환 """
        
        # --- 1. DNAT 전략 (파라미터 0, 1, 2) ---
        dnat_logits = action_params[0:3]
        dnat_probs = np.exp(dnat_logits) / np.sum(np.exp(dnat_logits))
        dnat_target_type = np.random.choice(["REAL", "DECOY", "ALTERNATE"], p=dnat_probs)
        self._log(f"[RL-MTD] DNAT 전략: Probs(R/D/A)={np.round(dnat_probs, 2)} -> 선택={dnat_target_type}")

        if dnat_target_type == "REAL": target = random.choice(REAL_TARGETS)
        elif dnat_target_type == "DECOY": target = random.choice(DECOY_TARGETS)
        else: target = random.choice(ALTERNATE_NODE_TARGETS)
        
        self.iptables_controller.apply_dnat_redirect(target["ip"], target["port"])

        # --- 2. 셔플 전략 (파라미터 3) ---
        if action_params[3] > 0.75: # shuffle_intensity
            self._log(f"[RL-MTD] 셔플 전략: 강도 {action_params[3]:.2f} > 0.75. 'Aggressive_Shuffle' 실행.")
            self.iptables_controller.run_script("mtd_service_swap.sh")
        
        # --- 3. [V05] 블랙리스트 "직접" 실행 (파라미터 4, 5) ---
        bl_threshold = self._map_value(action_params[4], 1.0, 0.1) # (0.0=1.0, 1.0=0.1) (역방향)
        bl_duration = int(self._map_value(action_params[5], 300, -1)) # (0.0=300s, 1.0=-1)
        if action_params[5] > 0.95: bl_duration = -1 # 영구
        
        self._log(f"[RL-MTD] BLK 정책: CTI 경보 > {bl_threshold:.2f} 이면 {bl_duration}초 차단.")
        
        # [!] CtiAgentStatus에서 "현재 경보" 목록을 가져와야 함 (User Task #2)
        # (가정) get_current_alerts()가 {"ip": score} 딕셔너리를 반환
        current_alerts = self.cti_status.get_current_alerts()
        
        # [실행] IptablesController의 블랙리스트 모듈에 (경보, 임계값, 기간) 전달
        self.iptables_controller.update_blacklist(current_alerts, bl_threshold, bl_duration)

    def _map_value(self, val_0_to_1: float, range_min: float, range_max: float) -> float:
        """ (0.0~1.0) 사이의 val 값을 (min~max) 범위로 선형 보간 """
        return range_min + (range_max - range_min) * val_0_to_1

    # ... (이하 _build_state_from_metrics, _log, __main__은 v04와 동일) ...
    def _build_state_from_metrics(self, metrics: Dict[str, float]) -> np.ndarray:
        vals_metrics = []
        for key in METRIC_FEATURE_KEYS:
            val = metrics.get(key)
            if val is None:
                self._log(f"[경고] 상태 벡터 키 '{key}'가 메트릭에 없습니다! 0.0으로 대체.", level="warning")
                val = 0.0
            vals_metrics.append(float(val))
        state = np.concatenate([
            np.array(vals_metrics, dtype=np.float32),
            self.current_action_params
        ])
        normed_state = (state - self.feature_mean) / (self.feature_std + 1e-8)
        return normed_state

    def _log(self, msg: str, level: str = "info") -> None:
        if self.logger:
            if level == "info": self.logger.info(msg)
            elif level == "warning": self.logger.warning(msg)
            elif level == "error": self.logger.error(msg)
        else:
            print(f"[{level.upper()}] {msg}")

if __name__ == "__main__":
    print("--- RLDrivenDeceptionManager (v05) 테스트 시작 ---")
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    main_logger = logging.getLogger("MTD_RL_Deploy_Test_v05")

    MODEL_DIRECTORY = "./rl_models/ver_05"
    CTI_POLICY_FILE = "./shared_state/cti_policy.json" # (v05에선 안 쓰지만 경로 유지)
    os.makedirs(os.path.dirname(CTI_POLICY_FILE), exist_ok=True)
    os.makedirs(MODEL_DIRECTORY, exist_ok=True)

    try:
        from mtd.rl_config_v05 import ACTION_PARAM_KEYS, ACTION_DIM, FEATURE_KEYS, OBS_DIM
        from mtd.rl_model_v05 import MTDPolicyNet

        fake_meta_path = os.path.join(MODEL_DIRECTORY, "mtd_policy_ver_05_meta.json")
        fake_meta = {
            "model_file": "mtd_policy_v05.pth", "version": "ver_05_dummy",
            "action_space_type": "continuous",
            "obs_dim": OBS_DIM, "act_dim": ACTION_DIM,
            "feature_keys": FEATURE_KEYS,
            "feature_norm": {"mean": [0.0]*OBS_DIM, "std": [1.0]*OBS_DIM},
            "action_param_keys": ACTION_PARAM_KEYS
        }
        with open(fake_meta_path, "w") as f: json.dump(fake_meta, f)
        
        fake_ckpt_path = os.path.join(MODEL_DIRECTORY, "mtd_policy_v05.pth")
        dummy_net = MTDPolicyNet(obs_dim=OBS_DIM, act_dim=ACTION_DIM)
        torch.save(dummy_net.state_dict(), fake_ckpt_path)
        print(f"테스트용 가짜 v05 모델/메타 파일 생성 완료: {MODEL_DIRECTORY}")
        
    except Exception as e:
        print(f"테스트용 파일 생성 실패: {e}. 기존 파일로 테스트합니다.")

    try:
        scorer = MtdScorer()
        cti_status = CtiAgentStatus()
        controller_ipt = IptablesController()
        # [v05] CtiPolicyController는 더 이상 필요 없음
        # controller_cti = CtiPolicyController(policy_file_path=CTI_POLICY_FILE, logger=main_logger) 
        
        manager = RLDrivenDeceptionManager(
            mtd_scorer=scorer,
            cti_status=cti_status,
            iptables_controller=controller_ipt,
            cti_policy_controller=None, # [v05] CTI 제어 안함
            model_dir=MODEL_DIRECTORY,
            logger=main_logger,
            enable_wandb=False
        )
        
        for i in range(3):
            print(f"\n===== MTD 의사결정 사이클 {i+1} =====")
            result = manager.step()
            time.sleep(5)
            
    except FileNotFoundError as e:
        print(f"\n[테스트 실패] 모델 파일을 찾을 수 없습니다. (경로: '{MODEL_DIRECTORY}')")
    except Exception as e:
        print(f"\n[테스트 실패] 예기치 않은 오류 발생: {e}")