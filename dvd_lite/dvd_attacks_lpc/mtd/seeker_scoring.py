#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
seeker_scoring.py

공격자(Seeker) RL 학습/평가용 지표 모듈.

환경에서 제공해야 하는 info 필드는 mtd_scoring.EpochScoreAggregator와 동일하다.
(Scan / Find / Exploit / Breach / Decoy / DRS / Time-to-event / CTI / 정책 / 공격자 파라미터)

이 모듈은 같은 info 스트림을
 - 방어자(MTD) 관점이 아니라
 - 공격자(Seeker) 관점에서 해석한 지표로 재정리한다.

예시 사용:

    from mtd.seeker_scoring import SeekerEpochAggregator, calc_seeker_metrics_from_infos

    agg = SeekerEpochAggregator()
    for info in infos:
        agg.update(info)
    metrics = agg.compute_epoch_metrics()
    wandb.log({f"seeker/{k}": v for k, v in metrics.items()}, step=global_step)

"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Any, List
import math


# ----------------------------------------------------------------------
# 내부 헬퍼
# ----------------------------------------------------------------------


def _safe_div(n: float, d: float) -> float:
    return float(n) / float(d) if d not in (0, 0.0) else 0.0


# ----------------------------------------------------------------------
# Epoch 단위 집계기 (Seeker 관점)
# ----------------------------------------------------------------------


@dataclass
class SeekerEpochAggregator:
    """
    한 Epoch(또는 롤아웃) 동안의 info들을 기반으로
    '공격자(Seeker) 관점' 지표를 집계하는 클래스.

    - MTD 관점의 R_succ, C_def 등과는 별도로,
      Seeker의 공격 성공률, decoy에 속은 정도, 탐색 효율성 등을 본다.
    """

    # 공통 카운터
    total_steps: int = 0

    # Scan / Find
    n_scan: int = 0
    n_find: int = 0
    sum_exposure_at_find: float = 0.0

    # Exploit
    n_exploit_attempt: int = 0
    n_exploit_success: int = 0
    n_exploit_block: int = 0
    sum_exposure_at_exploit_success: float = 0.0  # 필요하면 환경에서 채워도 됨

    # Breach
    n_breach_attempt: int = 0
    n_breach_success: int = 0
    n_breach_block: int = 0
    sum_exposure_at_breach_success: float = 0.0

    # Decoy / Known / Exploited / 노출/체류
    n_decoy: int = 0
    n_known: int = 0
    n_exploited: int = 0
    sum_exposure_steps: float = 0.0
    sum_dwell_steps: float = 0.0

    # Seeker cost (있다면)
    total_attack_cost: float = 0.0

    # DRS
    endpoint_visit_counts: Dict[Any, int] = field(default_factory=dict)
    distinct_ports: set = field(default_factory=set)
    n_shuffle: int = 0

    # 공격자 행동 파라미터 평균
    sum_attack_bias: float = 0.0
    sum_scan_effort: float = 0.0
    count_seeker_samples: int = 0

    def update(self, info: Dict[str, Any]) -> None:
        """한 step의 info를 받아 공격자 관점 카운터를 업데이트."""
        self.total_steps += 1

        # --- Scan / Find ---
        if info.get("is_scan", False):
            self.n_scan += 1
        if info.get("is_find", False):
            self.n_find += 1
            self.sum_exposure_at_find += float(
                info.get("exposure_at_find", info.get("exposure_steps", 0.0))
            )

        # --- Exploit ---
        if info.get("is_exploit_attempt", False):
            self.n_exploit_attempt += 1
        if info.get("is_exploit_success", False):
            self.n_exploit_success += 1
            # 공격자 입장에서 "Exploit 성공 시점의 노출시간"도 보고 싶으면 여기에 누적
            self.sum_exposure_at_exploit_success += float(
                info.get("exposure_at_exploit_success", info.get("exposure_steps", 0.0))
            )
        if info.get("is_exploit_block", False):
            self.n_exploit_block += 1

        # --- Breach ---
        if info.get("is_breach_attempt", False):
            self.n_breach_attempt += 1
        if info.get("is_breach_success", False):
            self.n_breach_success += 1
            self.sum_exposure_at_breach_success += float(
                info.get("exposure_at_breach_success", info.get("exposure_steps", 0.0))
            )
        if info.get("is_breach_block", False):
            self.n_breach_block += 1

        # --- Decoy / 노출 / 체류 / 상태 ---
        if info.get("is_decoy", False):
            self.n_decoy += 1
        if info.get("is_known", False):
            self.n_known += 1
        if info.get("is_exploited", False):
            self.n_exploited += 1

        self.sum_exposure_steps += float(info.get("exposure_steps", 0.0))
        self.sum_dwell_steps += float(info.get("dwell_steps", 0.0))

        # --- 공격자 cost (있다면) ---
        # (예: 공격 패킷 송신 비용, 스캔 비용 등을 info["seeker_cost"]로 넣을 수 있음)
        self.total_attack_cost += float(info.get("seeker_cost", 0.0))

        # --- DRS (공격자가 실제로 방문한 엔드포인트 히스토리) ---
        endpoint_id = info.get("endpoint_id", None)
        if endpoint_id is not None:
            self.endpoint_visit_counts[endpoint_id] = self.endpoint_visit_counts.get(endpoint_id, 0) + 1

        service_port = info.get("service_port", None)
        if service_port is not None:
            self.distinct_ports.add(service_port)

        if info.get("is_shuffle", False):
            self.n_shuffle += 1

        # --- 공격자(Seeker) 파라미터 ---
        if "attack_bias" in info or "scan_effort" in info:
            self.sum_attack_bias += float(info.get("attack_bias", 0.0))
            self.sum_scan_effort += float(info.get("scan_effort", 0.0))
            self.count_seeker_samples += 1

    # ------------------------------------------------------------------
    # Metric 계산
    # ------------------------------------------------------------------
    def compute_epoch_metrics(self) -> Dict[str, float]:
        """
        공격자 관점의 고급 지표들을 계산하여 반환.

        - p_scan, p_find
        - p_exploit_success, p_exploit_block
        - p_breach_success, p_breach_block
        - eta_decoy (decoy에 속는 비율)
        - ttf / ttexploit / ttbr
        - D_bits, R, S (공격자가 실제로 탐색한 엔드포인트 기준)
        - exposure_mean, dwell_mean
        - attack_bias_mean, scan_effort_mean
        - 공격 성공 기반 score: S_seeker
        """
        m: Dict[str, float] = {}

        steps = max(1, self.total_steps)

        # --- 확률 지표 ---------------------------------------------------
        # 정찰
        p_scan = _safe_div(self.n_scan, steps)
        p_find = _safe_div(self.n_find, self.n_scan)

        # Exploit
        p_exploit_success = _safe_div(self.n_exploit_success, self.n_exploit_attempt)
        p_exploit_block = _safe_div(self.n_exploit_block, self.n_exploit_attempt)

        # Breach
        p_breach_success = _safe_div(self.n_breach_success, self.n_breach_attempt)
        p_breach_block = _safe_div(self.n_breach_block, self.n_breach_attempt)

        # Decoy lure rate (공격자 입장에서 decoy에 빨려 들어간 비율)
        eta_dec = _safe_div(self.n_decoy, max(1, self.n_exploit_attempt))

        m["p_scan"] = p_scan
        m["p_find"] = p_find
        m["p_exploit_success"] = p_exploit_success
        m["p_exploit_block"] = p_exploit_block
        m["p_breach_success"] = p_breach_success
        m["p_breach_block"] = p_breach_block
        m["eta_decoy"] = eta_dec

        # --- Time-to-Event ----------------------------------------------
        # TTF: Find까지 걸린 평균 노출 스텝
        ttf = _safe_div(self.sum_exposure_at_find, self.n_find)
        # TTexploit: Exploit 성공까지 걸린 평균 노출 스텝 (환경에서 exposure_at_exploit_success 넣을 때만 사용)
        ttexploit = _safe_div(self.sum_exposure_at_exploit_success, self.n_exploit_success)
        # TTBr: Breach 성공까지 걸린 평균 노출 스텝
        ttbr = _safe_div(self.sum_exposure_at_breach_success, self.n_breach_success)

        m["ttf"] = ttf
        m["ttexploit"] = ttexploit
        m["ttbr"] = ttbr

        # --- DRS (공격자가 실제 방문한 히스토리 기준) --------------------
        total_visits = sum(self.endpoint_visit_counts.values())
        if total_visits > 0:
            D_bits = 0.0
            for cnt in self.endpoint_visit_counts.values():
                p_i = float(cnt) / float(total_visits)
                if p_i > 0.0:
                    D_bits -= p_i * math.log2(p_i)
        else:
            D_bits = 0.0

        num_ports = len(self.distinct_ports)
        R_val = float(max(0, num_ports - 1))

        num_endpoints = len(self.endpoint_visit_counts)
        if num_endpoints > 1:
            S_val = _safe_div(self.n_shuffle, steps) * math.log2(num_endpoints)
        else:
            S_val = 0.0

        m["D_bits"] = D_bits
        m["R"] = R_val
        m["S"] = S_val

        # --- 평균 노출/체류/상태 ----------------------------------------
        exposure_mean = _safe_div(self.sum_exposure_steps, steps)
        dwell_mean = _safe_div(self.sum_dwell_steps, steps)
        r_known = _safe_div(self.n_known, steps)
        r_exploited = _safe_div(self.n_exploited, steps)

        m["exposure_mean"] = exposure_mean
        m["dwell_mean"] = dwell_mean
        m["r_known"] = r_known
        m["r_exploited"] = r_exploited

        # --- 공격자 파라미터 평균 ---------------------------------------
        attack_bias_mean = _safe_div(self.sum_attack_bias, self.count_seeker_samples)
        scan_effort_mean = _safe_div(self.sum_scan_effort, self.count_seeker_samples)

        m["attack_bias_mean"] = attack_bias_mean
        m["scan_effort_mean"] = scan_effort_mean

        # --- 공격자 관점 종합 스코어 (예시) ------------------------------
        # S_seeker = p_breach_success - beta * (eta_decoy)
        #   - Breach 성공률이 높을수록 +
        #   - decoy에 속을수록 -
        beta = 0.5
        S_seeker = float(p_breach_success) - beta * float(eta_dec)
        m["S_seeker"] = S_seeker

        # 공격자 cost를 포함한 score도 원하면 여기서 확장 가능:
        #   S_seeker_cost = p_breach_success - beta * eta_dec - gamma * avg_attack_cost
        avg_attack_cost = _safe_div(self.total_attack_cost, steps)
        gamma = 0.0  # 일단 0으로 두고, 필요하면 외부 config에서 바꿔도 됨
        S_seeker_cost = float(S_seeker) - gamma * float(avg_attack_cost)
        m["avg_attack_cost"] = avg_attack_cost
        m["S_seeker_cost"] = S_seeker_cost

        return m


# ----------------------------------------------------------------------
# 편의 함수
# ----------------------------------------------------------------------


def calc_seeker_metrics_from_infos(infos: List[Dict[str, Any]]) -> Dict[str, float]:
    """
    PPO 학습에서 Seeker 에이전트의 rollout infos 리스트를 받아
    공격자 관점 지표를 계산하는 편의 함수.

    예시:

        seeker_metrics = calc_seeker_metrics_from_infos(seeker_infos)
        wandb.log({f"seeker/{k}": v for k, v in seeker_metrics.items()}, step=global_step)
    """
    agg = SeekerEpochAggregator()
    for info in infos:
        agg.update(info)
    return agg.compute_epoch_metrics()
