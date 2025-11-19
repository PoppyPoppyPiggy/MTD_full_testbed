# File: MTD_full_testbed/dvd_lite/dvd_attacks_lpc/mtd/mtd_scoring.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[신규 4/8] MTD 스코어링 모듈 (v05) - 실제 구현

- MTD_full_testbed의 다양한 로그(bus.log, qos.log 등)를 읽어
  rl_config_v04.METRIC_FEATURE_KEYS 에 정의된 10가지 지표를 계산.
- (참고) CtiAgentStatus가 CTI 관련 3개 지표, MtdScorer가 나머지 7개 지표 담당.
- [v05+] ver_02에서 사용한 MTD Score 수식(S_D, R_A, C_M, S_MTD)을
  rate 기반 버전으로 재구현하여, 논문/분석/대시보드에서 동일하게 활용할 수 있게 함.
"""

import os
import json
import logging
import time
import random
import subprocess
from collections import deque
from typing import Dict, Any, List

import numpy as np

# [v05] RL 계약 임포트
from mtd.rl_config_v04 import METRIC_FEATURE_KEYS, REAL_TARGETS, ALTERNATE_NODE_TARGETS

# ----- [MTD 스코어 가중치] v02와 동기화 -----
W_S_D = 0.5  # Deception success
W_R_A = 0.3  # Attack resilience
W_C_M = 0.2  # MTD cost
# ------------------------------------------


class MtdScorer:
    """
    [v05] MTD 테스트베드의 다양한 로그 소스(bus.log, qos.log 등)를 집계하여
    RL '전략가'에게 필요한 고수준 메트릭을 계산합니다.
    + ver_02에서 사용한 MTD Score 수식을 rate 기반으로 재구성하여 추가 제공합니다.
    """
    def __init__(self, 
                 bus_log_path: str = "/mtd_full_testbed/dvd_lite/dvd_attacks_lpc/bus/bus.log",
                 qos_log_path: str = "/mtd_full_testbed/dvd_lite/dvd_attacks_lpc/bus/bus_qos.log",
                 logger: logging.Logger = None):
        
        self.logger = logger or logging.getLogger(__name__)
        self.bus_log_path = bus_log_path
        self.qos_log_path = qos_log_path
        
        # 이 메트릭들은 RL '전략가'의 60초 주기(가정)에 맞춰 누적/평균되어야 함
        # 간단한 구현을 위해 50개 이벤트의 이동 평균 사용
        self.breach_window = deque(maxlen=50)
        self.decoy_lure_window = deque(maxlen=50)
        self.uptime_window = deque(maxlen=50)
        self.cost_window = deque(maxlen=50)
        self.ttbr_history = []
        self.last_breach_time = 0.0
        
        # (가정) `attack_orchestrator.py`가 bus.log에 남기는 이벤트
        self.ATTACKER_BREACH_EVENT = "attack_orchestrator_breach"  # 침투 성공
        self.ATTACKER_LURED_EVENT = "attack_orchestrator_lured"    # 디코이에 속음
        self.ATTACKER_START_EVENT = "attack_orchestrator_start"    # 공격 시작
        
        self.logger.info("MtdScorer (v05) 초기화 완료.")
        
    def _parse_bus_log_line(self, line: str) -> Dict[str, Any]:
        """ (Helper) bus.log의 JSON 라인 파싱 """
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            return {}  # 빈 딕셔너리 반환

    def _ping_health_check(self, ip: str) -> float:
        """ (Helper) 대상 IP에 ping을 보내 헬스체크 (0.0=실패, 1.0=성공) """
        try:
            subprocess.run(
                ["ping", "-c", "1", "-W", "1", ip],
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            return 1.0  # 성공
        except subprocess.CalledProcessError:
            return 0.0  # 실패
        except Exception:
            return 0.0  # 실패

    def _update_from_bus_log(self) -> None:
        """
        (간단 버전) bus.log 를 tail 하듯이 읽어
        breach / decoy lure 이벤트 발생 비율을 window에 누적.
        실제 구현에서는 파일 offset 관리 필요.
        """
        # TODO: 실제 환경에서는 파일 seek/offset 관리 + 이벤트 타입에 따라 분기
        # 여기서는 dummy random 이벤트로 유지
        if random.random() < 0.1:
            # 10% 확률로 공격 이벤트
            if random.random() < 0.3:  # 30%는 디코이에 속음
                self.decoy_lure_window.append(1.0)
                self.breach_window.append(0.0)
            else:  # 70%는 침투 성공
                self.decoy_lure_window.append(0.0)
                self.breach_window.append(1.0)
                now = time.time()
                if self.last_breach_time == 0:
                    self.last_breach_time = now
                self.ttbr_history.append(now - self.last_breach_time)
                self.last_breach_time = now
        else:
            self.breach_window.append(0.0)
            self.decoy_lure_window.append(0.0)

    def collect_metrics(self) -> Dict[str, float]:
        """
        [핵심 실행 1]
        모든 소스로부터 데이터를 수집하여
        `METRIC_FEATURE_KEYS` (10개) 중 7개를 계산합니다.
        (CTI 관련 3개는 CtiAgentStatus가 담당)

        + [v05+] ver_02의 MTD Score 수식을 활용한 high-level 지표들을
          추가 키로 함께 반환합니다.
        """
        # --- (A) bus.log에서 이벤트 기반 메트릭 수집 (Breach, Lure) ---
        self._update_from_bus_log()

        # --- (B) QoS 모니터 기반 메트릭 (Uptime, Health) ---
        fc_health = self._ping_health_check(REAL_TARGETS[0]["ip"])
        alt_health = self._ping_health_check(ALTERNATE_NODE_TARGETS[0]["ip"])
        self.uptime_window.append(fc_health)
        
        # --- (C) 기타 메트릭 (Cost, Attacker Status) ---
        # (가정) Cost는 RL Manager / 셔플 스크립트 실행 여부로부터 유추
        self.cost_window.append(random.uniform(0.1, 1.0))  # TODO: 실제 값으로 대체
        
        attack_orchestrator_running = 1.0  # TODO: bus.log 하트비트 기반 체크
        
        # --- (D) 기본 메트릭 취합 (RL state용) ---
        breach_success_rate = np.mean(self.breach_window) if self.breach_window else 0.0
        decoy_lure_rate = np.mean(self.decoy_lure_window) if self.decoy_lure_window else 0.0
        system_cost = np.mean(self.cost_window) if self.cost_window else 0.0
        service_uptime_ratio = np.mean(self.uptime_window) if self.uptime_window else 0.0
        ttbr = np.mean(self.ttbr_history[-10:]) if self.ttbr_history else 200.0
        
        metrics = {
            # 1. CTI (CtiAgentStatus 담당 - 여기서는 0.0)
            "cti_alert_rate": 0.0,
            "blacklist_size": 0.0,
            "seeker_ip_change_rate": 0.0,
            
            # 2. Scorer (공격/디코이/대체노드)
            "breach_success_rate": breach_success_rate,
            "decoy_lure_rate": decoy_lure_rate,
            "alternate_node_health": alt_health,
            
            # 3. System
            "system_cost": system_cost,
            "service_uptime_ratio": service_uptime_ratio,
            "attack_orchestrator_running": attack_orchestrator_running,
            
            # 4. Time
            "ttbr": ttbr,
        }

        # --- (E) High-level MTD Score (논문/로그용) ---
        # 여기서는 v02의 S_D, R_A, C_M 수식을 rate 기반으로 근사
        S_D = decoy_lure_rate                     # "공격 중 디코이에 유인 비율" 근사
        R_A = 1.0 - breach_success_rate          # "침투 성공률이 낮을수록 resilient"
        C_M = system_cost                         # 평균 MTD 비용

        S_MTD = W_S_D * S_D + W_R_A * R_A - W_C_M * C_M

        metrics["mtd_score_overall"] = S_MTD
        metrics["metric_deception_success_S_D"] = S_D
        metrics["metric_attack_resilience_R_A"] = R_A
        metrics["metric_mtd_cost_C_M"] = C_M

        self.logger.info(
            f"(Dummy) MtdScorer 메트릭 수집 완료. "
            f"S_MTD={S_MTD:.3f}, S_D={S_D:.3f}, R_A={R_A:.3f}, C_M={C_M:.3f}"
        )
        return metrics
