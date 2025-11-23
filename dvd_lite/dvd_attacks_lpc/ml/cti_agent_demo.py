#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CTI Agent Demo (PPO_v07_SeekerL* 정책 배포 데모)

- 역할:
    - RLDrivenDeceptionManager 를 일정 주기(step_interval)로 호출
    - 실제 iptables 또는 Dry-Run 모드 선택
    - W&B로 eval_metric/*, eval_action/* 로깅
    - 테스트베드 없이도 "정책이 어떤 행동을 내는지"를 시각화하는 데모

- 실행 예시:

  (mtd_env)# cd /home/kali/MTD_full_testbed/dvd_lite/dvd_attacks_lpc

  (mtd_env)# python -m ml.cti_agent_demo \
      --model-dir ./mtd/rl_models/PPO_v07_SeekerL2 \
      --total-steps 120 \
      --step-interval 5 \
      --use-wandb \
      --wandb-project mtd_rl_v07_deploy_demo \
      --wandb-entity emforhsqhf29- \
      --run-name "MTD_v07L2_demo" \
      --wandb-group "Seeker_profile_L2" \
      --dry-run-iptables
"""

import os
import time
import argparse
import logging
from typing import Optional

try:
    import wandb
except ImportError:
    wandb = None

from mtd.rl_driven_deception_manager_v05 import (
    RLDrivenDeceptionManager,
    MtdScorer,
    IptablesController,
    CtiAgentStatus,
)
try:
    from mtd.cti_status_reader import CtiAgentStatus
except ImportError as e:
    print("[RL Manager] ImportError 발생(cti_status_reader):", e)

    class CtiAgentStatus:
        """
        Dummy CTI 상태 리더 (실제 mtd/cti_status_reader.py 미구현 시 사용)
        - logger 인자를 받아도 되도록 __init__ 정의
        - get_cti_metrics / get_current_alerts 인터페이스만 맞춰줌
        """
        def __init__(self, logger: logging.Logger | None = None):
            self.logger = logger or logging.getLogger("DummyCtiAgentStatus")
            self.logger.info("[DummyCtiAgentStatus] 실제 CTI 상태 리더 대신 더미 메트릭을 사용합니다.")

        def get_cti_metrics(self) -> dict[str, float]:
            # CTI 이벤트가 거의 없는 평온한 상황을 가정한 더미 값들
            return {
                "cti_alert_rate": 0.05,          # 단위 시간당 CTI 알람 비율
                "blacklist_size_ratio": 0.0,     # 블랙리스트에 올라간 IP 비율
                "uptime_ratio": 1.0,             # 서비스 가동률 (1.0 = 100%)
                "breach_success_rate": 0.0,      # 침해 성공률
                "decoy_lure_rate": 0.0,          # 디코이로 유도된 비율
                "current_exposure_mean": 0.0,    # 평균 노출 스텝
                "r_known_ratio": 0.0,            # 알려진 상태 비율
                "r_exploited_ratio": 0.0,        # 1차 침투 상태 비율
                "seeker_scan_effort": 1.0,       # 시커의 스캔 강도 (중간값)
                "seeker_attack_bias": 0.5,       # Loud vs Stealth 중간 정도
            }

        def get_current_alerts(self) -> dict[str, float]:
            """
            실제라면 bus.log 등에서 '현재 탐지된 공격자 IP들 + 위협 점수'를 읽어야 함.
            데모에서는 고정된 한 IP만 위협 점수 0.8로 가정.
            """
            return {
                "10.13.0.200": 0.8,
            }


# ----------------------------------------------------------------------
# Dry-Run iptables 컨트롤러 (실제 iptables 안 건드림)
# ----------------------------------------------------------------------
class DryRunIptablesController(IptablesController):
    def __init__(
        self,
        iptables_chain: str = "DOCKER-USER",
        blacklist_file: str = "./mtd/shared_state/blacklist.json",
        scripts_dir: str = "./mtd/scripts",
        logger: Optional[logging.Logger] = None,
    ):
        # IptablesController.__init__에서 self._run_cmd를 호출하는데,
        # 이 시점에서 이미 override된 _run_cmd가 사용됨 -> 실제 iptables X
        super().__init__(
            iptables_chain=iptables_chain,
            blacklist_file=blacklist_file,
            scripts_dir=scripts_dir,
            logger=logger,
        )

    def _run_cmd(self, cmd_list):
        # 부모 클래스에서 iptables 실행 전에 항상 이 메서드를 거침
        if self.logger:
            self.logger.info(
                "[DryRun] iptables 명령 (실행 안 함): %s",
                " ".join(cmd_list),
            )
        else:
            print(f"[DryRun] iptables: {' '.join(cmd_list)}")
        return True


# ----------------------------------------------------------------------
# 메인 데모 함수
# ----------------------------------------------------------------------
def run_cti_agent_demo(
    model_dir: str,
    total_steps: int,
    step_interval: float,
    dry_run_iptables: bool,
    log_dir: str,
    use_wandb: bool,
    wandb_project: str,
    wandb_entity: Optional[str],
    run_name: str,
    wandb_group: str,
    iptables_chain: str,
    blacklist_file: str,
    scripts_dir: str,
):
    logger = logging.getLogger("cti_agent_demo")
    logger.info("=" * 61)
    logger.info(" CTI Agent Demo 시작 (RLDrivenDeceptionManager, PPO_v07)")
    logger.info("=" * 61)
    logger.info("  - model_dir: %s", model_dir)
    logger.info("  - step_interval: %.1f sec", step_interval)
    logger.info("  - total_steps: %d", total_steps)
    logger.info("  - dry_run_iptables: %s", dry_run_iptables)
    logger.info("  - log_dir: %s", log_dir)

    os.makedirs(log_dir, exist_ok=True)

    # --- iptables 컨트롤러 선택 ---
    if dry_run_iptables:
        logger.info(
            "[DryRunIptablesController] 활성화: 실제 iptables는 변경하지 않습니다."
        )
        ipt = DryRunIptablesController(
            iptables_chain=iptables_chain,
            blacklist_file=blacklist_file,
            scripts_dir=scripts_dir,
            logger=logger,
        )
    else:
        logger.info(
            "[IptablesController] 실제 iptables 변경 모드 (privileged 필요)."
        )
        ipt = IptablesController(
            iptables_chain=iptables_chain,
            blacklist_file=blacklist_file,
            scripts_dir=scripts_dir,
            logger=logger,
        )

    # --- MTD Scorer / CTI AgentStatus 구성 ---
    mtd_scorer = MtdScorer(log_dir=log_dir, logger=logger) if hasattr(
        MtdScorer, "__init__"
    ) else MtdScorer()
    cti_status = CtiAgentStatus(logger=logger) if hasattr(
        CtiAgentStatus, "__init__"
    ) else CtiAgentStatus()

    # --- RL 전략 매니저 구성 ---
    manager = RLDrivenDeceptionManager(
        mtd_scorer=mtd_scorer,
        cti_status=cti_status,
        iptables_controller=ipt,
        model_dir=model_dir,
        logger=logger,
        enable_wandb=use_wandb,
        wandb_project=wandb_project,
        wandb_group=wandb_group,
    )

    # --- W&B Run 정보 보강 (옵션) ---
    if use_wandb and wandb is not None and wandb.run is not None:
        if wandb_entity:
            # entity는 wandb.init할 때 이미 들어갔을테니 여기서는 tags 등만
            pass
        wandb.run.name = run_name or wandb.run.name
        wandb.config.update(
            {
                "demo.total_steps": total_steps,
                "demo.step_interval": step_interval,
                "demo.model_dir": model_dir,
                "demo.dry_run_iptables": dry_run_iptables,
            },
            allow_val_change=True,
        )

    # --- 메인 루프 ---
    for t in range(total_steps):
        logger.info(
            "-------------------------------------------------------------"
        )
        logger.info("[CTI Agent Demo] Step %d / %d", t + 1, total_steps)

        out = manager.step()

        # out["metrics"], out["action_params"] 등 추가 csv 저장하고 싶으면 여기서 처리
        # 예: log_dir/cti_agent_metrics.log 등

        if t < total_steps - 1:
            time.sleep(step_interval)


# ----------------------------------------------------------------------
# CLI 엔트리포인트
# ----------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="CTI Agent Demo (PPO_v07_SeekerL* 배포 테스트)"
    )
    parser.add_argument(
        "--model-dir",
        type=str,
        default="./mtd/rl_models/PPO_v07_SeekerL2",
        help="학습된 PPO_v07_SeekerL* 디렉토리 (final_policy.pth + norm_metadata.json)",
    )
    parser.add_argument(
        "--total-steps",
        type=int,
        default=60,
        help="데모 스텝 수",
    )
    parser.add_argument(
        "--step-interval",
        type=float,
        default=5.0,
        help="각 step 사이 대기 시간(초)",
    )
    parser.add_argument(
        "--dry-run-iptables",
        action="store_true",
        help="실제 iptables 변경 없이 Dry-Run 모드로 실행",
    )
    parser.add_argument(
        "--log-dir",
        type=str,
        default="./runs/cti_agent_demo",
        help="로그/결과 저장 디렉토리",
    )

    # W&B 설정
    parser.add_argument(
        "--use-wandb",
        action="store_true",
        help="W&B에 eval_metric/*, eval_action/* 로깅",
    )
    parser.add_argument(
        "--wandb-project",
        type=str,
        default="mtd_rl_v07_deploy_demo",
    )
    parser.add_argument(
        "--wandb-entity",
        type=str,
        default=None,
    )
    parser.add_argument(
        "--run-name",
        type=str,
        default=None,
    )
    parser.add_argument(
        "--wandb-group",
        type=str,
        default="Seeker_profile_L2",
    )

    # iptables 설정
    parser.add_argument(
        "--iptables-chain",
        type=str,
        default="DOCKER-USER",
        help="iptables 체인 이름 (MTD 룰을 붙일 체인)",
    )
    parser.add_argument(
        "--blacklist-file",
        type=str,
        default="./mtd/shared_state/blacklist.json",
        help="블랙리스트 상태를 저장할 JSON 파일 경로",
    )
    parser.add_argument(
        "--scripts-dir",
        type=str,
        default="./mtd/scripts",
        help="MTD 셔플 스크립트가 위치한 디렉토리",
    )

    args = parser.parse_args()

    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)-7s] %(name)s - %(message)s",
    )

    # W&B 초기화 (선택)
    if args.use_wandb and wandb is not None:
        wandb_kwargs = {
            "project": args.wandb_project,
            "name": args.run_name or "cti_agent_demo",
            "group": args.wandb_group,
        }
        if args.wandb_entity:
            wandb_kwargs["entity"] = args.wandb_entity
        wandb.init(**wandb_kwargs)

    run_cti_agent_demo(
        model_dir=args.model_dir,
        total_steps=args.total_steps,
        step_interval=args.step_interval,
        dry_run_iptables=args.dry_run_iptables,
        log_dir=args.log_dir,
        use_wandb=args.use_wandb,
        wandb_project=args.wandb_project,
        wandb_entity=args.wandb_entity,
        run_name=args.run_name or "cti_agent_demo",
        wandb_group=args.wandb_group,
        iptables_chain=args.iptables_chain,
        blacklist_file=args.blacklist_file,
        scripts_dir=args.scripts_dir,
    )


if __name__ == "__main__":
    main()
