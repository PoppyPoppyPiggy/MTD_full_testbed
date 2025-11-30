#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
seeker_agent.py

- Endpoint: 타겟/디코이 엔드포인트 표현
- SimulatedHeuristicSeeker: 강화학습 환경에서 사용되는 시뮬레이션 공격자
  * seeker_level 별 설정(seeker_levels.json)을 읽어서 파라미터를 다르게 사용
  * seeker_params[0] = scan_effort
  * seeker_params[1] = attack_bias

레벨/모드 요약:
- random   (level 0): 균등 샘플링으로 타깃 선택, 낮은 scan_effort, 낮은 decoy 회피.
- heuristic(level 1): 정해진 scan_effort/attack_bias로 디코이 회피 경향, IP 변경 확률 소폭 증가.
- time_aware(level 2): 시간이 지날수록 scan_effort, breach_prob를 증가시켜 장기전에 강함.
- adaptive (level 3): outcome에 따라 scan_effort/attack_bias/breach_prob/ exploit_prob를 가감하며
  차단·디코이 후에는 스텔스하게, 성공 후에는 더욱 공격적으로 행동.
"""

from __future__ import annotations
import json
import os
from dataclasses import dataclass
from typing import List, Optional, Dict, Any

import numpy as np


@dataclass
class Endpoint:
    ip: str
    name: str
    is_decoy: bool = False

    # 공격 진행도 (scan / exploit / breach)
    scan_progress: float = 0.0
    exploit_progress: float = 0.0
    breach_progress: float = 0.0

    def reset_progress(self) -> None:
        self.scan_progress = 0.0
        self.exploit_progress = 0.0
        self.breach_progress = 0.0


class SimulatedHeuristicSeeker:
    """
    강화학습 환경용 휴리스틱 공격자.

    - level 프로파일(seeker_levels.json)을 기반으로 파라미터 설정
    - MTDEnvironment에서 seeker_level을 바꾸면 같은 엔드포인트라도 더 강한/약한 공격자로 시뮬레이션 가능
    """

    def __init__(
        self,
        rng: np.random.Generator,
        seeker_level: int,
        endpoints: List[Endpoint],
        profiles_path: Optional[str] = None,
    ) -> None:
        self.rng = rng
        self.endpoints = endpoints
        self.level = seeker_level
        self.profiles_path = profiles_path or os.path.join(
            os.path.dirname(__file__), "config", "seeker_levels.json"
        )

        # level 프로파일 로딩
        self.level_profile = self._load_level_profile(self.level)
        self.mode = self.level_profile.get("mode", "heuristic")
        # state: scan_effort, attack_bias 등
        self.seeker_params = [
            float(self.level_profile.get("scan_effort", 0.5)),
            float(self.level_profile.get("attack_bias", 0.5)),
        ]

        self.ip_change_prob = float(self.level_profile.get("ip_change_prob", 0.1))
        self.breach_prob = float(self.level_profile.get("breach_prob", 0.3))
        self.exploit_prob = float(self.level_profile.get("exploit_prob", 0.5))

        # 내부 상태
        self.current_ip_idx: int = 0  # 어떤 엔드포인트를 주로 노리는지
        self.step_count: int = 0

    # -------------------------
    # Config / Profile
    # -------------------------
    def _load_level_profile(self, level: int) -> Dict[str, Any]:
        try:
            if os.path.exists(self.profiles_path):
                with open(self.profiles_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                levels = data.get("levels", {})
                if str(level) in levels:
                    return levels[str(level)]
        except Exception:
            pass
        # fallback 기본값
        return {
            "mode": "heuristic",
            "scan_effort": 0.5,
            "attack_bias": 0.5,
            "ip_change_prob": 0.1,
            "breach_prob": 0.3,
            "exploit_prob": 0.5,
        }

    # -------------------------
    # Core Logic
    # -------------------------
    def _pick_target_endpoint(self, status: Dict[str, float]) -> Optional[Endpoint]:
        """
        MTD 상태(is_shuffle, is_decoy_active, decoy_ratio)를 고려해서
        어떤 엔드포인트를 다음 공격 대상으로 삼을지 결정.
        - attack_bias가 높을수록 디코이를 좀 더 잘 회피한다 (혹은 반대로 혼동하도록 조정 가능)
        """
        if not self.endpoints:
            return None

        # decoy_ratio가 높으면 디코이가 더 많이 노출되는 상황
        decoy_bias = status.get("decoy_ratio", 0.0)

        # 간단한 예:
        # - attack_bias가 낮으면 디코이에도 잘 걸린다.
        # - attack_bias가 높으면 decoy는 피하고 real target만 골라가려 한다.
        # Random attacker는 모든 엔드포인트를 균등하게 선택한다.
        if self.mode == "random":
            idx = int(self.rng.integers(0, len(self.endpoints)))
            self.current_ip_idx = idx
            return self.endpoints[idx]

        # Heuristic/Time-aware/Adaptive 공통: decoy 회피 성향을 attack_bias로 모델링
        probs = []
        for ep in self.endpoints:
            if ep.is_decoy:
                # decoy를 얼마나 잘 피하는지 (attack_bias가 높을수록 피함)
                base = 0.5 + (decoy_bias * 0.5)
                p = base * (1.0 - self.seeker_params[1])
            else:
                base = 1.0
                p = base * (0.5 + self.seeker_params[1] * 0.5)
            probs.append(max(1e-3, p))

        probs_arr = np.array(probs, dtype=float)
        probs_arr /= probs_arr.sum()
        idx = self.rng.choice(len(self.endpoints), p=probs_arr)
        self.current_ip_idx = idx
        return self.endpoints[idx]

    def _maybe_change_ip(self) -> None:
        """
        블랙리스트 회피를 위한 IP 변경.
        level이 높을수록 ip_change_prob가 큼.
        """
        if not self.endpoints:
            return
        if self.rng.random() < self.ip_change_prob:
            self.current_ip_idx = self.rng.integers(0, len(self.endpoints))

    def step(self, mtd_status: Dict[str, float]) -> Dict[str, Any]:
        """
        환경에서 한 스텝 수행.
        반환:
            {
              "seeker_ip": <공격자 IP (심볼릭)>,
              "target_ep": Endpoint or None,
              "is_scan": bool,
              "is_exploit_attempt": bool,
              "is_breach_attempt": bool,
            }
        """
        self.step_count += 1

        # MTD 셔플이 강하게 걸리면 공격자는 진행도를 많이 잃는다 (env에서 reset_progress() 호출)
        is_shuffle = mtd_status.get("is_shuffle", False)

        # 공격자 IP 변경 시도 (블랙리스트 회피)
        self._maybe_change_ip()

        # 스캔/공격/브리치 시도 결정
        scan_effort = self.seeker_params[0]
        # time-aware 모드는 시간이 지날수록 스캔 빈도를 높인다.
        if self.mode == "time_aware":
            scan_effort = min(1.0, scan_effort + 0.002 * self.step_count)
        # scan_effort 클수록 더 자주 스캔 시도
        is_scan = self.rng.random() < scan_effort

        target_ep = self._pick_target_endpoint(mtd_status) if is_scan else None

        is_exploit_attempt = False
        is_breach_attempt = False

        if target_ep:
            exploit_prob = self.exploit_prob
            breach_prob = self.breach_prob

            # adaptive 모드는 직전 outcome에 따라 확률을 바꾼다 (handle_outcome에서 업데이트)
            # time-aware 모드는 일정 시간이 지나면 더 과감하게 breach를 시도
            if self.mode == "time_aware" and self.step_count > 50:
                breach_prob = min(1.0, breach_prob + 0.1)

            # scan 후 exploit 시도 여부
            if self.rng.random() < exploit_prob:
                is_exploit_attempt = True
                target_ep.exploit_progress += 0.3

                # exploit 진행도가 높아지면 breach 시도
                if target_ep.exploit_progress >= 0.7 and self.rng.random() < breach_prob:
                    is_breach_attempt = True
                    target_ep.breach_progress += 0.5

        return {
            "seeker_ip": f"ATTACKER_{self.current_ip_idx}",
            "target_ep": target_ep,
            "is_scan": is_scan,
            "is_exploit_attempt": is_exploit_attempt,
            "is_breach_attempt": is_breach_attempt,
        }

    def handle_outcome(self, outcome: str) -> None:
        """
        환경이 결정한 outcome을 보고, 공격자 내부 상태를 조정.
        outcome: "continue" | "decoy_hit" | "blocked" | "exploit_success" | "breach_success"
        """
        # 간단한 휴리스틱: 차단/디코이에 많이 걸리면 scan_effort를 좀 높이거나,
        # IP를 바꾸는 경향을 늘리는 등의 동작을 넣을 수 있음.
        # 여기서는 일단 최소 로직만 유지.
        if outcome in ("blocked", "decoy_hit"):
            # 다음엔 다른 엔드포인트로 옮길 가능성 증가
            self._maybe_change_ip()

        if self.mode == "adaptive":
            # 성공 시 공격성 유지, 실패 시 더 은신/우회하려 함
            if outcome in ("breach_success", "exploit_success"):
                self.seeker_params[0] = min(1.0, self.seeker_params[0] + 0.05)
                self.seeker_params[1] = min(1.0, self.seeker_params[1] + 0.05)
                self.breach_prob = min(1.0, self.breach_prob + 0.05)
            else:
                # 차단/디코이 시도를 줄이고 stealth하게 변경
                self.seeker_params[0] = max(0.1, self.seeker_params[0] - 0.05)
                self.seeker_params[1] = max(0.0, self.seeker_params[1] - 0.05)
                self.exploit_prob = max(0.1, self.exploit_prob - 0.05)