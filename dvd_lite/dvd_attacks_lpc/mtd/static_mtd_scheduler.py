#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
디렉토리: dvd_lite/dvd_attacks_lpc/mtd
파일명  : static_mtd_scheduler.py

설명:
    - "정적(Static) MTD"를 시간 기반으로 수행하는 스케줄러.
    - CTI / RL 없이, 순수하게 일정 주기로 IP/Port 셔플 + 디코이 활성화를 수행한다.
    - 동일 Seeker 공격에 대해 다음 4가지 방어전략을 비교할 때 사용:
        1) No-MTD            : 아무것도 실행 X
        2) Static-MTD        : 이 스크립트만 실행
        3) CTI-Rule MTD      : CTI Agent + CTI_DEFENSE_MODE=cti_rule
        4) RL+CTI MTD        : CTI Agent + CTI_DEFENSE_MODE=rl + RLDM

사용 예:
    # 10분 동안(600초), 5초마다 모든 서비스에 정적 MTD 수행 (dry-run)
    python3 static_mtd_scheduler.py \
        --policy mixed \
        --interval-sec 5.0 \
        --total-duration-sec 600 \
        --dry-run

정책(policy):
    - ip_shuffle : IP/Port 셔플만 수행 (디코이 X)
    - decoy      : 디코이만 활성화 (셔플 X)
    - mixed      : 셔플 + 디코이 병행 (기본값)
"""

import argparse
import logging
import time
from typing import Dict, Tuple

from .iptables_mtd_controller import IptablesMTDController

logger = logging.getLogger("StaticMTD")


# 실험에 사용할 서비스 집합 (CTI-Agent와 동일 네이밍)
#   service_name : (target_key, port_idx)
STATIC_SERVICES: Dict[str, Tuple[str, int]] = {
    "fc_mavlink": ("FC", 0),     # FC MAVLink (10.13.0.2:14550)
    "cc_web": ("CC", 0),         # Companion Web (10.13.0.3:3000)
    "cc_mavlink": ("CC", 1),     # Companion MAVLink (10.13.0.3:14550)
    "gcs_mavlink": ("GCS", 0),   # GCS MAVLink (10.13.0.4:14550)
    # 필요 시 SIM/ROS 등도 추가 가능:
    # "sim_sitl": ("SIM", 0),
    # "sim_ros": ("SIM", 1),
}


def run_static_mtd(
    policy: str = "mixed",
    interval_sec: float = 5.0,
    total_duration_sec: float = 600.0,
    dry_run: bool = True,
) -> None:
    """
    정적 MTD 스케줄러 메인 루프.

    Args:
        policy: "ip_shuffle" / "decoy" / "mixed"
        interval_sec: MTD 수행 주기 (초)
        total_duration_sec: 전체 실험 시간 (초)
        dry_run: True이면 실제 iptables 적용 없이 명령만 로그로 기록
    """
    logger.info(
        f"[StaticMTD] Starting static MTD scheduler: "
        f"policy={policy}, interval_sec={interval_sec}, total_duration_sec={total_duration_sec}, dry_run={dry_run}"
    )

    ctl = IptablesMTDController(dry_run=dry_run)

    # 서비스 등록
    for svc_name, (target_key, port_idx) in STATIC_SERVICES.items():
        ctl.register_service(svc_name, target_key, port_idx)
        logger.info(f"[StaticMTD] Service registered: {svc_name} -> {target_key}[{port_idx}]")

    start_time = time.time()
    step = 0

    while True:
        now = time.time()
        elapsed = now - start_time
        if elapsed >= total_duration_sec:
            logger.info("[StaticMTD] Total duration reached. Stopping scheduler.")
            break

        step += 1
        logger.info(f"[StaticMTD] ===== Step {step} (elapsed={elapsed:.1f}s) =====")

        try:
            for svc_name in STATIC_SERVICES.keys():
                if policy in ("ip_shuffle", "mixed"):
                    # 정적 MTD baseline: 항상 고정 intensity로 셔플
                    ctl.shuffle_network(svc_name, intensity=0.8)

                if policy in ("decoy", "mixed"):
                    # 디코이는 항상 on 상태로 유지 (idempotent)
                    ctl.enable_decoy(svc_name)

        except Exception as e:
            logger.error(f"[StaticMTD] Error while applying MTD actions: {e}")

        time.sleep(interval_sec)

    logger.info("[StaticMTD] Scheduler finished. Final mapping:")
    logger.info("\n" + ctl.get_mapping_info())


def parse_args():
    parser = argparse.ArgumentParser(
        description="Static MTD Scheduler (time-based baseline)"
    )
    parser.add_argument(
        "--policy",
        type=str,
        choices=["ip_shuffle", "decoy", "mixed"],
        default="mixed",
        help="정적 MTD 정책 유형 (기본: mixed)",
    )
    parser.add_argument(
        "--interval-sec",
        type=float,
        default=5.0,
        help="MTD 수행 주기 (초, 기본: 5.0)",
    )
    parser.add_argument(
        "--total-duration-sec",
        type=float,
        default=600.0,
        help="전체 수행 시간 (초, 기본: 600=10분)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="실제 iptables 변경 없이 명령만 로그로 출력",
    )
    return parser.parse_args()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)-7s] [StaticMTD] %(message)s",
    )

    args = parse_args()

    run_static_mtd(
        policy=args.policy,
        interval_sec=args.interval_sec,
        total_duration_sec=args.total_duration_sec,
        dry_run=args.dry_run,
    )
