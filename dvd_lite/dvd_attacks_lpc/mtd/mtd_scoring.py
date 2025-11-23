# File: mtd/mtd_scoring.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MTD Scoring Module (Training + Deploy 공용 버전)

- PPO 학습 환경에서 env의 info[]들을 기반으로
  MTD 성능 지표를 계산하기 위한 유틸리티.
- 배포 / 데모 환경(ml.cti_agent_demo)에서는
  RLDrivenDeceptionManager가 사용할 수 있는
  간단한 MtdScorer 클래스를 제공.

핵심 지표(요약)
----------------
1) R_succ (Breach Stop Rate)
   R_succ = 1 - (#BreachSuccess / #BreachAttempt)

2) C_def (평균 방어 비용)
   C_def = E[ COST_MTD_ACTION
              + COST_SHUFFLE * 1_{shuffle}
              + COST_DECOY   * decoy_ratio
              + COST_BL      * BL ]

3) Cost_per_Block
   = sum(cost) / (#BlockExploit + #BlockBreach + #DecoyHit)

4) 단계별 성공/차단 비율
   - r_exploit_success, r_exploit_block
   - r_breach_success,  r_breach_block
   - r_scan, r_find

5) 시간 지표
   - TTF  (Time-to-Find)
   - TTEB (Time-to-Exploit-Block)
   - TTBr (Time-to-Breach)

6) DRS (D_bits, R, S)
   - D_bits: 엔드포인트 방문 히스토그램 엔트로피
   - R     : 포트 Redundancy (단순 지표)
   - S     : 셔플 빈도 정규화

7) LPC/CTI/정책 평균
   - exposure_mean, dwell_mean
   - r_known_ratio, r_exploited_ratio
   - r_cti, ip_cd_mean, decoy_ratio_mean, bl_level_mean
   - scan_effort_mean, attack_bias_mean

추가:
- PPO_v07용 feature alias:
  breach_success_rate, decoy_lure_rate,
  current_exposure_mean, r_known_ratio, r_exploited_ratio 등.
"""

import math
import os
import json
import logging
from collections import Counter, defaultdict
from typing import Dict, Any, Iterable, List, Optional, Hashable


def _safe_div(num: float, den: float, default: float = 0.0) -> float:
    """0 나누기 방지용 안전한 나눗셈."""
    if den is None or den == 0:
        return default
    return float(num) / float(den)


def _entropy_bits(counts: Dict[Hashable, int]) -> float:
    """
    엔트로피 D_bits = -∑ p_i log2 p_i
    counts: {endpoint_id: visit_count}
    """
    total = sum(counts.values())
    if total <= 0:
        return 0.0
    ent = 0.0
    for c in counts.values():
        if c <= 0:
            continue
        p = c / total
        ent -= p * math.log2(p)
    return float(ent)


def calculate_metrics_from_infos(infos: Iterable[Dict[str, Any]]) -> Dict[str, float]:
    """
    PPO 학습 루프에서 env.step()의 info들을 모아
    한 epoch(또는 N-step roll-out)에 대한 MTD 지표를 계산.

    기대하는 info 키(없으면 0으로 처리):
    - 이벤트 플래그 (bool or 0/1):
      event_scan, event_find,
      event_exploit_attempt, event_exploit_success, event_exploit_block,
      event_breach_attempt,  event_breach_success,  event_breach_block,
      event_decoy_hit, event_shuffle

    - 비용/자원:
      cost

    - 타임라인 관련:
      exposure_at_found,
      exposure_at_exploit_block,
      exposure_at_breach_success

    - LPC 관련:
      endpoint_id, service_port(or endpoint_port),
      known_flag, exploited_flag

    - CTI/정책 관련:
      cti_event_count,
      ip_cd, decoy_ratio, bl_level,
      seeker_scan_effort, seeker_attack_bias
    """
    infos_list: List[Dict[str, Any]] = list(infos)
    total_steps = len(infos_list)

    # 아무 스텝도 없으면 전부 0 반환
    if total_steps == 0:
        return {
            "R_succ": 0.0,
            "C_def": 0.0,
            "Cost_per_Block": 0.0,
            "r_exploit_success": 0.0,
            "r_exploit_block": 0.0,
            "r_breach_success": 0.0,
            "r_breach_block": 0.0,
            "r_scan": 0.0,
            "r_find": 0.0,
            "TTF": 0.0,
            "TTEB": 0.0,
            "TTBr": 0.0,
            "D_bits": 0.0,
            "R": 0.0,
            "S": 0.0,
            "exposure_mean": 0.0,
            "dwell_mean": 0.0,
            "r_known_ratio": 0.0,
            "r_exploited_ratio": 0.0,
            "r_cti": 0.0,
            "ip_cd_mean": 0.0,
            "decoy_ratio_mean": 0.0,
            "bl_level_mean": 0.0,
            "scan_effort_mean": 0.0,
            "attack_bias_mean": 0.0,
            "breach_success_rate": 0.0,
            "decoy_lure_rate": 0.0,
            "current_exposure_mean": 0.0,
            "uptime_ratio": 1.0,
        }

    # -----------------------------
    # 1) 기본 카운터 및 합계
    # -----------------------------
    ev = Counter()
    cost_sum = 0.0
    shuffle_count = 0

    # 엔드포인트 방문/포트 다양성/체류시간
    endpoint_visits = Counter()      # endpoint_id -> count
    distinct_ports = set()
    dwell_sum = 0.0
    dwell_count = 0
    last_endpoint: Optional[Hashable] = None
    current_dwell = 0

    # 노출 관련
    exposure_at_found_sum = 0.0
    exposure_at_exploit_block_sum = 0.0
    exposure_at_breach_success_sum = 0.0

    # LPC/CTI/정책 관련 합
    known_sum = 0.0
    exploited_sum = 0.0
    cti_event_sum = 0.0
    ip_cd_sum = 0.0
    decoy_ratio_sum = 0.0
    bl_level_sum = 0.0
    scan_effort_sum = 0.0
    attack_bias_sum = 0.0

    for info in infos_list:
        # 비용
        cost_sum += float(info.get("cost", 0.0))

        # 이벤트 카운트
        if info.get("event_scan"):
            ev["scan"] += 1
        if info.get("event_find"):
            ev["find"] += 1
            exposure_at_found_sum += float(info.get("exposure_at_found", 0.0))

        if info.get("event_exploit_attempt"):
            ev["exploit_attempt"] += 1
        if info.get("event_exploit_success"):
            ev["exploit_success"] += 1
        if info.get("event_exploit_block"):
            ev["exploit_block"] += 1
            exposure_at_exploit_block_sum += float(info.get("exposure_at_exploit_block", 0.0))

        if info.get("event_breach_attempt"):
            ev["breach_attempt"] += 1
        if info.get("event_breach_success"):
            ev["breach_success"] += 1
            exposure_at_breach_success_sum += float(info.get("exposure_at_breach_success", 0.0))
        if info.get("event_breach_block"):
            ev["breach_block"] += 1

        if info.get("event_decoy_hit"):
            ev["decoy_hit"] += 1

        if info.get("event_shuffle"):
            shuffle_count += 1

        # 엔드포인트 / 포트
        endpoint = info.get("endpoint_id", None)
        if endpoint is not None:
            endpoint_visits[endpoint] += 1

            if last_endpoint is None:
                # 첫 방문
                last_endpoint = endpoint
                current_dwell = 1
            elif endpoint == last_endpoint:
                # 같은 엔드포인트에 계속 체류
                current_dwell += 1
            else:
                # 다른 엔드포인트로 이동 -> 이전 dwell 종료
                dwell_sum += current_dwell
                dwell_count += 1
                last_endpoint = endpoint
                current_dwell = 1

        port = info.get("service_port", None)
        if port is None:
            port = info.get("endpoint_port", None)
        if port is not None:
            try:
                distinct_ports.add(int(port))
            except Exception:
                # 포트값이 숫자가 아닐 경우 그냥 무시
                pass

        # LPC 플래그
        if "known_flag" in info:
            known_sum += float(info.get("known_flag", 0.0))
        if "exploited_flag" in info:
            exploited_sum += float(info.get("exploited_flag", 0.0))

        # CTI/정책 관련
        cti_event_sum += float(info.get("cti_event_count", 0.0))
        ip_cd_sum += float(info.get("ip_cd", 0.0))
        decoy_ratio_sum += float(info.get("decoy_ratio", 0.0))
        bl_level_sum += float(info.get("bl_level", 0.0))
        scan_effort_sum += float(info.get("seeker_scan_effort", 0.0))
        attack_bias_sum += float(info.get("seeker_attack_bias", 0.0))

    # 마지막 엔드포인트에 대한 dwell 마무리
    if current_dwell > 0:
        dwell_sum += current_dwell
        dwell_count += 1

    # -----------------------------
    # 2) 코어 방어 지표
    # -----------------------------
    total_exploit = ev["exploit_attempt"]
    total_breach = ev["breach_attempt"]

    metrics: Dict[str, float] = {}

    # Breach Stop Rate
    metrics["R_succ"] = 1.0 - _safe_div(ev["breach_success"], total_breach, default=0.0)

    # 평균 방어 비용
    metrics["C_def"] = _safe_div(cost_sum, total_steps, default=0.0)

    # 차단 1건당 비용
    block_total = ev["exploit_block"] + ev["breach_block"] + ev["decoy_hit"]
    metrics["Cost_per_Block"] = _safe_div(cost_sum, block_total, default=0.0)

    # Exploit / Breach 단계별 성공/차단 비율
    metrics["r_exploit_success"] = _safe_div(ev["exploit_success"], total_exploit, default=0.0)
    metrics["r_exploit_block"] = _safe_div(ev["exploit_block"], total_exploit, default=0.0)

    metrics["r_breach_success"] = _safe_div(ev["breach_success"], total_breach, default=0.0)
    metrics["r_breach_block"] = _safe_div(ev["breach_block"], total_breach, default=0.0)

    # 정찰 단계
    metrics["r_scan"] = _safe_div(ev["scan"], total_steps, default=0.0)
    metrics["r_find"] = _safe_div(ev["find"], ev["scan"], default=0.0)

    # -----------------------------
    # 3) Time-to-Event (TTF, TTEB, TTBr)
    # -----------------------------
    metrics["TTF"] = _safe_div(exposure_at_found_sum, ev["find"], default=0.0)
    metrics["TTEB"] = _safe_div(exposure_at_exploit_block_sum, ev["exploit_block"], default=0.0)
    metrics["TTBr"] = _safe_div(exposure_at_breach_success_sum, ev["breach_success"], default=0.0)

    # -----------------------------
    # 4) DRS (D_bits, R, S)
    # -----------------------------
    metrics["D_bits"] = _entropy_bits(endpoint_visits)

    # Redundancy: 단순히 "핵심 1개 + 백업 포트 수"
    metrics["R"] = float(max(0, len(distinct_ports) - 1))

    # Shuffle 지표
    num_endpoints = max(1, len(endpoint_visits))
    metrics["S"] = _safe_div(shuffle_count, total_steps, default=0.0) * math.log2(num_endpoints)

    # -----------------------------
    # 5) LPC 관련 평균량
    # -----------------------------
    # 노출 평균: 찾힘/블록/브리치 성공에 대한 노출 평균을 간단히 합쳐서 평균
    exposure_event_count = ev["find"] + ev["exploit_block"] + ev["breach_success"]
    exposure_total_sum = (
        exposure_at_found_sum
        + exposure_at_exploit_block_sum
        + exposure_at_breach_success_sum
    )
    metrics["exposure_mean"] = _safe_div(exposure_total_sum, exposure_event_count, default=0.0)

    # 동일 엔드포인트 체류 평균
    metrics["dwell_mean"] = _safe_div(dwell_sum, dwell_count, default=0.0)

    # 알려짐 / 1차 침투 상태 비율
    metrics["r_known_ratio"] = _safe_div(known_sum, total_steps, default=0.0)
    metrics["r_exploited_ratio"] = _safe_div(exploited_sum, total_steps, default=0.0)

    # -----------------------------
    # 6) CTI/정책 파라미터 평균
    # -----------------------------
    metrics["r_cti"] = _safe_div(cti_event_sum, total_steps, default=0.0)
    metrics["ip_cd_mean"] = _safe_div(ip_cd_sum, total_steps, default=0.0)
    metrics["decoy_ratio_mean"] = _safe_div(decoy_ratio_sum, total_steps, default=0.0)
    metrics["bl_level_mean"] = _safe_div(bl_level_sum, total_steps, default=0.0)
    metrics["scan_effort_mean"] = _safe_div(scan_effort_sum, total_steps, default=0.0)
    metrics["attack_bias_mean"] = _safe_div(attack_bias_sum, total_steps, default=0.0)

    # -----------------------------
    # 7) PPO_v07 feature alias (norm_metadata.json과 매핑)
    # -----------------------------
    # norm_metadata.json의 FEATURE_KEYS 예:
    # [
    #   "cti_alert_rate",
    #   "blacklist_size_ratio",
    #   "uptime_ratio",
    #   "breach_success_rate",
    #   "decoy_lure_rate",
    #   "current_exposure_mean",
    #   "r_known_ratio",
    #   "r_exploited_ratio",
    #   ...
    # ]
    # 여기서는 breach_success_rate, decoy_lure_rate, current_exposure_mean만 alias 제공.
    metrics["breach_success_rate"] = metrics["r_breach_success"]
    metrics["decoy_lure_rate"] = _safe_div(ev["decoy_hit"], max(1, total_exploit), default=0.0)
    metrics["current_exposure_mean"] = metrics["exposure_mean"]

    # 나머지 feature:
    # - cti_alert_rate, blacklist_size_ratio, uptime_ratio 등은
    #   실제 CTI/테스트베드에서 CtiAgentStatus 쪽에서 채워주는 것을 전제로 함.
    #   여기서는 값이 없으면 0/1 기본값 세팅으로만 처리.
    metrics.setdefault("cti_alert_rate", 0.0)
    metrics.setdefault("blacklist_size_ratio", 0.0)
    metrics.setdefault("uptime_ratio", 1.0)

    return metrics


class MtdScorer:
    """
    배포 / 데모 모드용 MTD Scorer 클래스.

    - ml.cti_agent_demo 에서는:
        mtd_scorer = MtdScorer(log_dir=..., logger=...)
        metrics = mtd_scorer.collect_metrics()
      형태로 사용.

    - 학습 코드에서는 굳이 인스턴스를 만들 필요 없이:
        from mtd.mtd_scoring import MtdScorer
        epoch_metrics = MtdScorer.calculate_metrics_from_infos(infos)
      로 static 메서드를 직접 호출하면 됨.
    """

    def __init__(self, log_dir: str = "./runs/mtd_scorer", logger: Optional[logging.Logger] = None):
        self.log_dir = log_dir
        os.makedirs(self.log_dir, exist_ok=True)
        self.logger = logger or logging.getLogger(__name__)
        self.last_metrics: Dict[str, float] = {
            # PPO_v07 feature 쪽 기본값
            "breach_success_rate": 0.0,
            "decoy_lure_rate": 0.0,
            "current_exposure_mean": 0.0,
            "r_known_ratio": 0.0,
            "r_exploited_ratio": 0.0,
            "cti_alert_rate": 0.0,
            "blacklist_size_ratio": 0.0,
            "uptime_ratio": 1.0,
            # 기타 코어 지표 기본값
            "R_succ": 0.0,
            "C_def": 0.0,
            "Cost_per_Block": 0.0,
        }

    def collect_metrics(self) -> Dict[str, float]:
        """
        배포/데모 모드에서 호출됨.
        - 현재는 self.last_metrics를 그대로 반환.
        - 나중에 원하면, shared_state나 로그 파일에서
          최신 metrics를 읽어와 갱신하도록 확장 가능.
        """
        # 추후 확장을 위해, log_dir에 저장된 json이 있으면 불러오는 옵션도 넣을 수 있음.
        metrics_path = os.path.join(self.log_dir, "mtd_metrics_latest.json")
        if os.path.exists(metrics_path):
            try:
                with open(metrics_path, "r", encoding="utf-8") as f:
                    self.last_metrics = json.load(f)
            except Exception as e:
                self.logger.warning(f"[MtdScorer] metrics 파일 로드 실패: {e}")

        return dict(self.last_metrics)

    def update_from_infos(self, infos: Iterable[Dict[str, Any]], save_json: bool = False) -> Dict[str, float]:
        """
        (선택) 학습/리플레이 등에서 info[]를 넘겨주면
        내부 last_metrics를 갱신하고, 필요시 json으로 저장.
        """
        metrics = calculate_metrics_from_infos(infos)
        self.last_metrics = metrics

        if save_json:
            try:
                metrics_path = os.path.join(self.log_dir, "mtd_metrics_latest.json")
                with open(metrics_path, "w", encoding="utf-8") as f:
                    json.dump(metrics, f, indent=2, ensure_ascii=False)
                self.logger.info(f"[MtdScorer] metrics 저장: {metrics_path}")
            except Exception as e:
                self.logger.warning(f"[MtdScorer] metrics 저장 실패: {e}")

        return metrics

    # static alias (편의용)
    @staticmethod
    def calculate_metrics_from_infos(infos: Iterable[Dict[str, Any]]) -> Dict[str, float]:
        return calculate_metrics_from_infos(infos)
