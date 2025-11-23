#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mtd_scoring.py

PPO 기반 MTD 학습 및 테스트베드 평가에서 공통으로 사용하는
MTD/Seeker 지표 계산 모듈.

[모델 요약]

1) 공격자(Seeker) 모델
   - 행동 단계: Scan → Find → Exploit → Breach
   - 공격 유형: Loud vs Stealth (확률 분기: attack_bias)
   - 레벨:
       L0 (Naive)   : scan_effort=0.5, attack_bias=0.5
       L1 (Scanner) : scan_effort=2.0, attack_bias=0.8
       L2 (Stealth) : scan_effort=0.8, attack_bias=0.2
       L3 (ARL)     : RL이 scan_effort / attack_bias 적응 조정

2) 방어자(MTD) 모델
   - 메타 액션: ip_cd(셔플 주기), decoy_ratio, bl_level 조정
   - 보상/비용 구조(요지):
       * 보상: Exploit / Breach 차단(+), Decoy 유도(+)
       * 패널티: Exploit / Breach 성공(-), 잦은 노출(Find)(-), MTD 비용(-)

3) info 딕셔너리에서 기대하는 필드 (환경에서 채워줘야 함)
   - 기본 카운터/플래그:
       info["is_scan"]              : bool, 해당 스텝에서 Scan 수행
       info["is_find"]              : bool, Find 성공
       info["is_exploit_attempt"]   : bool, Exploit 시도
       info["is_exploit_success"]   : bool, Exploit 성공
       info["is_exploit_block"]     : bool, Exploit 차단
       info["is_breach_attempt"]    : bool, Breach 시도
       info["is_breach_success"]    : bool, Breach 성공
       info["is_breach_block"]      : bool, Breach 차단
       info["is_decoy"]             : bool, decoy로 흘려보낸 이벤트
   - 노출/체류 관련:
       info["exposure_steps"]               : float, 현재까지 노출 스텝
       info["exposure_at_find"]             : float, Find 시 노출 스텝
       info["exposure_at_exploit_block"]    : float, Exploit 차단 시 노출 스텝
       info["exposure_at_breach_success"]   : float, Breach 성공 시 노출 스텝
       info["dwell_steps"]                  : float, 동일 엔드포인트 체류 스텝
       info["is_known"]                     : bool, Seeker가 이 엔드포인트를 "알고 있음"
       info["is_exploited"]                 : bool, 1차 침투(Exploit) 상태
   - DRS / 엔드포인트:
       info["endpoint_id"]                  : 해시 가능한 엔드포인트 ID (예: ("ip", port))
       info["service_port"]                 : 서비스 포트 번호 (int)
       info["is_shuffle"]                   : bool, 해당 스텝에서 셔플 발생
   - CTI / 정책 파라미터:
       info["cti_events"]                   : int, 해당 스텝에서 반영된 CTI 이벤트 수
       info["ip_cd"]                        : float, ip change delay(셔플 주기) 메타 액션
       info["decoy_ratio"]                  : float, 0~1 사이 decoy 비율 메타 액션
       info["bl_level"]                     : float, 0~1 사이 blacklist 레벨 메타 액션
   - 비용/보상:
       info["cost"]                         : float, 이 스텝의 MTD 비용
       info["COST_MTD_ACTION"]              : float, 액션 자체 기본 비용
       info["COST_SHUFFLE"]                 : float, 셔플 비용 (있다면)
       info["COST_DECOY"]                   : float, decoy 유지/노출 비용
       info["COST_BL"]                      : float, blacklist 레벨 비용
   - Seeker(공격자) 파라미터:
       info["attack_bias"]                  : float, Loud vs Stealth 분기 (0~1)
       info["scan_effort"]                  : float, 스캔 강도/빈도
   - 시스템 상태 (테스트베드용):
       info["alternate_node_health"]        : float, 0~1 (대체 노드 헬스)
       info["service_uptime_ratio"]         : float, 0~1 (서비스 업타임)
       info["attack_orchestrator_running"]  : float, 0~1 (공격 오케스트레이터 정상 동작 여부)

환경에서 위 키들을 적절히 채워주면, 아래 지표들을 PPO/W&B/테스트베드에서 그대로 사용 가능하다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import math


# ----------------------------------------------------------------------
# 헬퍼
# ----------------------------------------------------------------------


def _safe_div(n: float, d: float) -> float:
    return float(n) / float(d) if d not in (0, 0.0) else 0.0


# ----------------------------------------------------------------------
# Epoch 단위 집계기 (학습 / 오프라인 평가용)
# ----------------------------------------------------------------------


@dataclass
class EpochScoreAggregator:
    """한 Epoch (또는 많은 스텝 모음)에 대한 MTD/Seeker 지표 집계기."""

    # --- 카운터 기본 ---
    total_steps: int = 0

    # Scan / Find
    n_scan: int = 0
    n_find: int = 0
    sum_exposure_at_find: float = 0.0

    # Exploit
    n_exploit_attempt: int = 0
    n_exploit_success: int = 0
    n_exploit_block: int = 0
    sum_exposure_at_exploit_block: float = 0.0

    # Breach
    n_breach_attempt: int = 0
    n_breach_success: int = 0
    n_breach_block: int = 0
    sum_exposure_at_breach_success: float = 0.0

    # Decoy / Dwell / Known / Exploited
    n_decoy: int = 0
    n_known: int = 0
    n_exploited: int = 0
    sum_exposure_steps: float = 0.0
    sum_dwell_steps: float = 0.0

    # 비용 관련
    total_cost: float = 0.0

    # DRS 관련
    endpoint_visit_counts: Dict[Any, int] = field(default_factory=dict)
    distinct_ports: set = field(default_factory=set)
    n_shuffle: int = 0

    # CTI / 정책 평균
    sum_cti_events: float = 0.0
    sum_ip_cd: float = 0.0
    sum_decoy_ratio: float = 0.0
    sum_bl_level: float = 0.0
    count_policy_samples: int = 0

    # Seeker 파라미터 평균
    sum_attack_bias: float = 0.0
    sum_scan_effort: float = 0.0
    count_seeker_samples: int = 0

    # 시스템 상태 (테스트베드용)
    sum_alt_node_health: float = 0.0
    sum_service_uptime: float = 0.0
    count_system_samples: int = 0
    last_attack_orchestrator_running: float = 1.0

    def update(self, info: Dict[str, Any]) -> None:
        """한 step의 info를 받아 내부 카운터/합계를 업데이트한다."""
        self.total_steps += 1

        # --- Scan / Find ---
        if info.get("is_scan", False):
            self.n_scan += 1
        if info.get("is_find", False):
            self.n_find += 1
            self.sum_exposure_at_find += float(info.get("exposure_at_find", info.get("exposure_steps", 0.0)))

        # --- Exploit ---
        if info.get("is_exploit_attempt", False):
            self.n_exploit_attempt += 1
        if info.get("is_exploit_success", False):
            self.n_exploit_success += 1
        if info.get("is_exploit_block", False):
            self.n_exploit_block += 1
            self.sum_exposure_at_exploit_block += float(
                info.get("exposure_at_exploit_block", info.get("exposure_steps", 0.0))
            )

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

        # --- Decoy / Known / Exploited / Dwell / Exposure ---
        if info.get("is_decoy", False):
            self.n_decoy += 1
        if info.get("is_known", False):
            self.n_known += 1
        if info.get("is_exploited", False):
            self.n_exploited += 1

        self.sum_exposure_steps += float(info.get("exposure_steps", 0.0))
        self.sum_dwell_steps += float(info.get("dwell_steps", 0.0))

        # --- 비용 ---
        self.total_cost += float(info.get("cost", 0.0))

        # --- DRS ---
        endpoint_id = info.get("endpoint_id", None)
        if endpoint_id is not None:
            self.endpoint_visit_counts[endpoint_id] = self.endpoint_visit_counts.get(endpoint_id, 0) + 1

        service_port = info.get("service_port", None)
        if service_port is not None:
            self.distinct_ports.add(service_port)

        if info.get("is_shuffle", False):
            self.n_shuffle += 1

        # --- CTI / 정책 ---
        if "cti_events" in info or "ip_cd" in info or "decoy_ratio" in info or "bl_level" in info:
            self.sum_cti_events += float(info.get("cti_events", 0.0))
            self.sum_ip_cd += float(info.get("ip_cd", 0.0))
            self.sum_decoy_ratio += float(info.get("decoy_ratio", 0.0))
            self.sum_bl_level += float(info.get("bl_level", 0.0))
            self.count_policy_samples += 1

        # --- Seeker 파라미터 ---
        if "attack_bias" in info or "scan_effort" in info:
            self.sum_attack_bias += float(info.get("attack_bias", 0.0))
            self.sum_scan_effort += float(info.get("scan_effort", 0.0))
            self.count_seeker_samples += 1

        # --- 시스템 상태 ---
        if (
            "alternate_node_health" in info
            or "service_uptime_ratio" in info
            or "attack_orchestrator_running" in info
        ):
            self.sum_alt_node_health += float(info.get("alternate_node_health", 1.0))
            self.sum_service_uptime += float(info.get("service_uptime_ratio", 1.0))
            self.count_system_samples += 1
            self.last_attack_orchestrator_running = float(info.get("attack_orchestrator_running", 1.0))

    # ------------------------------------------------------------------
    # 메트릭 계산
    # ------------------------------------------------------------------
    def compute_epoch_metrics(self) -> Dict[str, float]:
        """
        Epoch 단위 지표를 계산하여 dict로 반환.

        2.x 섹션에서 정의한 대부분의 지표 + 일부 alias(breach_success_rate 등)를 포함한다.
        """

        metrics: Dict[str, float] = {}

        # --- 2.1 방어 성능/비용 코어 -------------------------------------
        # R_succ (Breach Stop Rate)
        # R_succ = 1 - (#BreachSuccess / #BreachAttempt)
        if self.n_breach_attempt > 0:
            r_breach_success = _safe_div(self.n_breach_success, self.n_breach_attempt)
            R_succ = 1.0 - r_breach_success
        else:
            r_breach_success = 0.0
            R_succ = 0.0
        metrics["R_succ"] = R_succ

        # C_def (Defense Cost, 평균)
        # C_def = E[cost] = total_cost / total_steps
        C_def = _safe_div(self.total_cost, self.total_steps)
        metrics["C_def"] = C_def

        # Cost_per_Block
        # CostPerBlock = total_cost / (#BlockExploit + #BlockBreach + #Decoy)
        n_block_total = self.n_exploit_block + self.n_breach_block + self.n_decoy
        CostPerBlock = _safe_div(self.total_cost, n_block_total)
        metrics["CostPerBlock"] = CostPerBlock

        # --- 2.2 다단계 성공률 -------------------------------------------
        # Exploit 단계
        r_exploit_success = _safe_div(self.n_exploit_success, self.n_exploit_attempt)
        r_exploit_block = _safe_div(self.n_exploit_block, self.n_exploit_attempt)
        metrics["r_exploit_success"] = r_exploit_success
        metrics["r_exploit_block"] = r_exploit_block

        # Breach 단계 (이미 r_breach_success 위에서 계산)
        r_breach_block = _safe_div(self.n_breach_block, self.n_breach_attempt)
        metrics["r_breach_success"] = r_breach_success
        metrics["r_breach_block"] = r_breach_block

        # 정찰
        r_scan = _safe_div(self.n_scan, self.total_steps)
        r_find = _safe_div(self.n_find, self.n_scan)
        metrics["r_scan"] = r_scan
        metrics["r_find"] = r_find

        # --- 2.3 Time-to-Event ------------------------------------------
        # TTF (Time-to-Find)
        TTF = _safe_div(self.sum_exposure_at_find, self.n_find)
        metrics["TTF"] = TTF

        # TTEB (Time-to-Exploit-Block)
        TTEB = _safe_div(self.sum_exposure_at_exploit_block, self.n_exploit_block)
        metrics["TTEB"] = TTEB

        # TTBr (Time-to-Breach, 성공 기준)
        TTBr = _safe_div(self.sum_exposure_at_breach_success, self.n_breach_success)
        metrics["TTBr"] = TTBr

        # alias: ttbr (소문자)도 함께 제공 (테스트베드에서 사용)
        metrics["ttbr"] = TTBr

        # --- 2.4 DRS (D_bits, R, S) --------------------------------------
        # Diversity D_bits = -sum_i p_i log2 p_i
        total_visits = sum(self.endpoint_visit_counts.values())
        if total_visits > 0:
            D_bits = 0.0
            for cnt in self.endpoint_visit_counts.values():
                p_i = float(cnt) / float(total_visits)
                if p_i > 0.0:
                    D_bits -= p_i * math.log2(p_i)
        else:
            D_bits = 0.0
        metrics["D_bits"] = D_bits

        # Redundancy R = max(0, #distinct_ports - 1)
        num_distinct_ports = len(self.distinct_ports)
        R_val = float(max(0, num_distinct_ports - 1))
        metrics["R"] = R_val

        # Shuffle S = (n_shuffle / total_steps) * log2(#endpoints)
        num_endpoints = len(self.endpoint_visit_counts)
        if num_endpoints > 1 and self.total_steps > 0:
            S_val = _safe_div(self.n_shuffle, self.total_steps) * math.log2(num_endpoints)
        else:
            S_val = 0.0
        metrics["S"] = S_val

        # --- 2.5 LPC 관련 평균 -------------------------------------------
        exposure_mean = _safe_div(self.sum_exposure_steps, self.total_steps)
        dwell_mean = _safe_div(self.sum_dwell_steps, self.total_steps)
        r_known = _safe_div(self.n_known, self.total_steps)
        r_exploited = _safe_div(self.n_exploited, self.total_steps)
        metrics["exposure_mean"] = exposure_mean
        metrics["dwell_mean"] = dwell_mean
        metrics["r_known"] = r_known
        metrics["r_exploited"] = r_exploited

        # --- 2.6 CTI / 정책 / Seeker 평균 ---------------------------------
        # r_cti: 단위시간 CTI 이벤트 반영률
        r_cti = _safe_div(self.sum_cti_events, self.total_steps)
        metrics["r_cti"] = r_cti

        # ip_cd_mean / decoy_ratio_mean / bl_level_mean
        ip_cd_mean = _safe_div(self.sum_ip_cd, self.count_policy_samples)
        decoy_ratio_mean = _safe_div(self.sum_decoy_ratio, self.count_policy_samples)
        bl_level_mean = _safe_div(self.sum_bl_level, self.count_policy_samples)
        metrics["ip_cd_mean"] = ip_cd_mean
        metrics["decoy_ratio_mean"] = decoy_ratio_mean
        metrics["bl_level_mean"] = bl_level_mean

        # Seeker attack_bias_mean / scan_effort_mean
        attack_bias_mean = _safe_div(self.sum_attack_bias, self.count_seeker_samples)
        scan_effort_mean = _safe_div(self.sum_scan_effort, self.count_seeker_samples)
        metrics["attack_bias_mean"] = attack_bias_mean
        metrics["scan_effort_mean"] = scan_effort_mean

        # --- Seeker/MTD 혼합 high-level 지표 ------------------------------
        # Decoy lure rate η_dec = #decoy / #exploit_attempt
        eta_dec = _safe_div(self.n_decoy, self.n_exploit_attempt)
        metrics["decoy_lure_rate"] = eta_dec

        # alias: breach_success_rate (테스트베드 MTD scorer 호환)
        metrics["breach_success_rate"] = r_breach_success

        # 시스템 상태 평균 (테스트베드용)
        alt_node_health = _safe_div(self.sum_alt_node_health, self.count_system_samples)
        service_uptime_ratio = _safe_div(self.sum_service_uptime, self.count_system_samples)
        metrics["alternate_node_health"] = alt_node_health if self.count_system_samples > 0 else 1.0
        metrics["service_uptime_ratio"] = service_uptime_ratio if self.count_system_samples > 0 else 1.0
        metrics["attack_orchestrator_running"] = self.last_attack_orchestrator_running

        # --- 요약 MTD 스코어 S_MTD (예: 방어성능 vs 비용 trade-off) --------
        # 논문에서 정의한 형태로 바꿀 수 있지만 일단:
        #   S_MTD = R_succ - alpha * C_def
        # alpha는 외부 config에서 조정해도 되지만, 일단 0.1로 고정 (placeholder)
        alpha = 0.1
        S_MTD = float(R_succ) - alpha * float(C_def)
        metrics["S_MTD"] = S_MTD

        # ------------------------------------------------------------------
        # 학습/배포 간 지표 명칭 일관성 정리
        # - 학습 환경(rl_environment_v05)에서는 Defense/..., Attack/..., Time/..., DRS/...로
        #   네임스페이스가 붙은 flat 키와 group 딕셔너리를 동시에 제공한다.
        # - 테스트베드 평가(RLDrivenDeceptionManager)에서는 MtdScorer.collect_metrics()의
        #   반환값을 그대로 eval_metric/* 로깅하므로, 동일한 키 구성을 추가로 제공한다.
        # ------------------------------------------------------------------
        defense_dict = {
            "R_succ": R_succ,
            "C_def": C_def,
            "CostPerBlock": CostPerBlock,
            # 학습 환경에서 사용하던 이름과 맞추기 위한 alias
            "S_MTD_overall": S_MTD,
        }

        attack_dict = {
            "r_exploit_success": r_exploit_success,
            "r_exploit_block": r_exploit_block,
            "r_breach_success": r_breach_success,
            "r_breach_block": r_breach_block,
            "r_scan": r_scan,
            "r_find": r_find,
            "decoy_lure_rate": eta_dec,
        }

        time_dict = {
            "TTF_mean": TTF,
            "TTEB_mean": TTEB,
            "TTBr_mean": TTBr,
        }

        drs_dict = {
            "D_bits": D_bits,
            # 학습 환경 alias: R_redundancy, S_shuffle
            "R_redundancy": R_val,
            "S_shuffle": S_val,
        }

        # flat prefix 버전 추가 (Defense/R_succ 등)
        prefixed_metrics = {}
        for key, val in defense_dict.items():
            prefixed_metrics[f"Defense/{key}"] = val
        for key, val in attack_dict.items():
            prefixed_metrics[f"Attack/{key}"] = val
        for key, val in time_dict.items():
            prefixed_metrics[f"Time/{key}"] = val
        for key, val in drs_dict.items():
            prefixed_metrics[f"DRS/{key}"] = val

        # 기존 flat 지표와 호환성을 유지하면서 학습용 네임스페이스를 함께 반환
        metrics.update(
            {
                **defense_dict,
                **attack_dict,
                **time_dict,
                **drs_dict,
                **prefixed_metrics,
                # 기존 alias 유지
                "R": metrics.get("R", R_val),
                "S": metrics.get("S", S_val),
                "R_redundancy": R_val,
                "S_shuffle": S_val,
                "TTF_mean": TTF,
                "TTEB_mean": TTEB,
                "TTBr_mean": TTBr,
                "S_MTD_overall": S_MTD,
            }
        )

        return metrics


# ----------------------------------------------------------------------
# RealTime Metrics (bin 단위, W&B 실시간 그래프용)
# ----------------------------------------------------------------------


@dataclass
class RealTimeMetricsAggregator:
    """
    일정 step(bin_size_steps)마다 실시간 지표를 계산하는 집계기.

    학습 루프에서:
        rt = RealTimeMetricsAggregator(bin_size_steps=1000)
        for step, info in enumerate(infos):
            bin_metrics = rt.update(info)
            if bin_metrics is not None:
                wandb.log({ f"rt/{k}": v for k, v in bin_metrics.items() }, step=global_step)
    """

    bin_size_steps: int = 1000

    # 현재 bin 카운터들
    steps_in_bin: int = 0

    n_scan: int = 0
    n_find: int = 0

    n_exploit_attempt: int = 0
    n_exploit_success: int = 0
    n_exploit_block: int = 0

    n_breach_attempt: int = 0
    n_breach_success: int = 0
    n_breach_block: int = 0

    n_decoy: int = 0

    sum_exposure_at_find: float = 0.0
    sum_exposure_at_exploit_block: float = 0.0
    sum_exposure_at_breach_success: float = 0.0

    # DRS
    endpoint_visit_counts: Dict[Any, int] = field(default_factory=dict)
    distinct_ports: set = field(default_factory=set)
    n_shuffle: int = 0

    # CTI / 정책
    sum_cti_events: float = 0.0
    sum_ip_cd: float = 0.0
    count_policy_samples: int = 0

    def update(self, info: Dict[str, Any]) -> Optional[Dict[str, float]]:
        """
        한 step의 info를 반영하고,
        bin_size_steps에 도달하면 bin 지표를 반환하고 내부 상태 리셋.
        """
        self.steps_in_bin += 1

        # Scan / Find
        if info.get("is_scan", False):
            self.n_scan += 1
        if info.get("is_find", False):
            self.n_find += 1
            self.sum_exposure_at_find += float(info.get("exposure_at_find", info.get("exposure_steps", 0.0)))

        # Exploit
        if info.get("is_exploit_attempt", False):
            self.n_exploit_attempt += 1
        if info.get("is_exploit_success", False):
            self.n_exploit_success += 1
        if info.get("is_exploit_block", False):
            self.n_exploit_block += 1
            self.sum_exposure_at_exploit_block += float(
                info.get("exposure_at_exploit_block", info.get("exposure_steps", 0.0))
            )

        # Breach
        if info.get("is_breach_attempt", False):
            self.n_breach_attempt += 1
        if info.get("is_breach_success", False):
            self.n_breach_success += 1
            self.sum_exposure_at_breach_success += float(
                info.get("exposure_at_breach_success", info.get("exposure_steps", 0.0))
            )
        if info.get("is_breach_block", False):
            self.n_breach_block += 1

        # Decoy
        if info.get("is_decoy", False):
            self.n_decoy += 1

        # DRS
        endpoint_id = info.get("endpoint_id", None)
        if endpoint_id is not None:
            self.endpoint_visit_counts[endpoint_id] = self.endpoint_visit_counts.get(endpoint_id, 0) + 1
        service_port = info.get("service_port", None)
        if service_port is not None:
            self.distinct_ports.add(service_port)
        if info.get("is_shuffle", False):
            self.n_shuffle += 1

        # CTI / 정책
        if "cti_events" in info or "ip_cd" in info:
            self.sum_cti_events += float(info.get("cti_events", 0.0))
            self.sum_ip_cd += float(info.get("ip_cd", 0.0))
            self.count_policy_samples += 1

        # bin 완료 체크
        if self.steps_in_bin >= self.bin_size_steps:
            metrics = self._compute_bin_metrics()
            self._reset_bin()
            return metrics
        return None

    def _compute_bin_metrics(self) -> Dict[str, float]:
        """현재 bin에 대해 3.x 섹션의 RealTime 지표들을 계산."""
        m: Dict[str, float] = {}
        steps = max(1, self.steps_in_bin)

        # r_scan, r_find
        m["r_scan"] = _safe_div(self.n_scan, steps)
        m["r_find"] = _safe_div(self.n_find, max(1, self.n_scan))

        # Exploit 레벨
        m["r_exploit_attempt_per_step"] = _safe_div(self.n_exploit_attempt, steps)
        m["r_exploit_success"] = _safe_div(self.n_exploit_success, self.n_exploit_attempt)
        m["r_exploit_block"] = _safe_div(self.n_exploit_block, self.n_exploit_attempt)
        m["eta_dec"] = _safe_div(self.n_decoy, self.n_exploit_attempt)  # decoy / exploit

        # Breach 레벨
        m["r_breach_attempt_per_step"] = _safe_div(self.n_breach_attempt, steps)
        m["r_breach_success"] = _safe_div(self.n_breach_success, self.n_breach_attempt)
        m["r_breach_block"] = _safe_div(self.n_breach_block, self.n_breach_attempt)

        # TTF / TTEB / TTBr (bin 평균)
        m["TTF"] = _safe_div(self.sum_exposure_at_find, self.n_find)
        m["TTEB"] = _safe_div(self.sum_exposure_at_exploit_block, self.n_exploit_block)
        m["TTBr"] = _safe_div(self.sum_exposure_at_breach_success, self.n_breach_success)

        # D_bits, R, S (bin)
        total_visits = sum(self.endpoint_visit_counts.values())
        if total_visits > 0:
            D_bits = 0.0
            for cnt in self.endpoint_visit_counts.values():
                p_i = float(cnt) / float(total_visits)
                if p_i > 0.0:
                    D_bits -= p_i * math.log2(p_i)
        else:
            D_bits = 0.0
        m["D_bits"] = D_bits

        num_ports = len(self.distinct_ports)
        m["R"] = float(max(0, num_ports - 1))

        num_endpoints = len(self.endpoint_visit_counts)
        if num_endpoints > 1:
            m["S"] = _safe_div(self.n_shuffle, steps) * math.log2(num_endpoints)
        else:
            m["S"] = 0.0

        # r_cti + ip_cd_mean
        m["r_cti"] = _safe_div(self.sum_cti_events, steps)
        m["ip_cd_mean"] = _safe_div(self.sum_ip_cd, self.count_policy_samples)

        return m

    def _reset_bin(self) -> None:
        self.steps_in_bin = 0

        self.n_scan = 0
        self.n_find = 0

        self.n_exploit_attempt = 0
        self.n_exploit_success = 0
        self.n_exploit_block = 0

        self.n_breach_attempt = 0
        self.n_breach_success = 0
        self.n_breach_block = 0

        self.n_decoy = 0

        self.sum_exposure_at_find = 0.0
        self.sum_exposure_at_exploit_block = 0.0
        self.sum_exposure_at_breach_success = 0.0

        self.endpoint_visit_counts.clear()
        self.distinct_ports.clear()
        self.n_shuffle = 0

        self.sum_cti_events = 0.0
        self.sum_ip_cd = 0.0
        self.count_policy_samples = 0


# ----------------------------------------------------------------------
# 편의 함수 및 RLDrivenDeceptionManager / 학습에서 사용할 인터페이스
# ----------------------------------------------------------------------


def calculate_metrics_from_infos(infos: List[Dict[str, Any]]) -> Dict[str, float]:
    """
    PPO 학습 한 Epoch에서 수집된 info 리스트를 받아
    Epoch 단위 지표를 계산하는 편의 함수.

    사용 예:
        metrics = calculate_metrics_from_infos(epoch_infos)
        wandb.log({ f"mtd/{k}": v for k, v in metrics.items() }, step=global_step)
    """
    agg = EpochScoreAggregator()
    for info in infos:
        agg.update(info)
    return agg.compute_epoch_metrics()


class MtdScorer:
    """
    테스트베드 / 배포 환경에서 사용할 간단 스코어러.

    RLDrivenDeceptionManager v05에서:
        scorer = MtdScorer()
        ...
        metrics = scorer.collect_metrics()

    실제론 CTI/로그/환경에서 적절한 info들을 update()로 집계한 뒤
    collect_metrics()를 호출해야 한다.
    """

    def __init__(self):
        self._agg = EpochScoreAggregator()

    def update(self, info: Dict[str, Any]) -> None:
        """외부에서 step 단위 info를 밀어 넣어주는 경우."""
        self._agg.update(info)

    def collect_metrics(self) -> Dict[str, float]:
        """
        현재까지 누적된 info를 기반으로 Epoch 지표를 계산.
        (테스트베드에서는 일정 시간 윈도우마다 reset()을 해주는 식으로 운용 가능)
        """
        return self._agg.compute_epoch_metrics()

    def reset(self) -> None:
        """집계 상태 초기화."""
        self._agg = EpochScoreAggregator()
