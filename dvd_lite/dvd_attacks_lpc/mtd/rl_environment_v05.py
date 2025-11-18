#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rl_environment_v05.py

MTD 학습용 시뮬레이션 환경 (NetworkEnv v0.5)

- SimulatedHeuristicSeeker   : 공격자(Seeker) 행동 시뮬레이션
- SimulatedPassiveCTI        : CTI(수동 센서) 시뮬레이션
- SimulatedBlacklister       : 블랙리스트 정책 시뮬레이션
- NetworkEnv                 : PPO가 상호작용하는 Gym-like 환경

목표:
- 학습 중에 관측되는 state / info 구조를
  실제 테스트베드(CTI + MTD 컨트롤러 + Seeker 공격 로그)와 의미론적으로 맞춘다.
"""

from __future__ import annotations

import math
from collections import deque
from typing import Dict, Tuple, Any, Optional

import numpy as np

from rl_config_v05 import (
    ACTION_PARAM_KEYS,
    FEATURE_KEYS,
    OBS_DIM,
    ACTION_DIM,
    SIM_TIME_PER_STEP_SEC,
)


class SimulatedPassiveCTI:
    """
    간단한 수동 CTI 센서 시뮬레이터.
    - suspicious=True 인 트래픽에 대해 높은 점수를 내고,
      threshold 이상이면 경보로 처리.
    """

    def __init__(
        self,
        detection_threshold: float = 0.5,
        window_size: int = 200,
        rng: Optional[np.random.Generator] = None,
    ) -> None:
        self.detection_threshold = detection_threshold
        self.window_size = window_size
        self.rng = rng or np.random.default_rng()
        self._alert_history = deque(maxlen=window_size)
        self._score_history = deque(maxlen=window_size)

    def process_traffic(self, suspicious: bool) -> Tuple[float, bool]:
        if suspicious:
            score = float(self.rng.normal(loc=0.8, scale=0.15))
        else:
            score = float(self.rng.normal(loc=0.1, scale=0.05))
        score = max(0.0, min(1.0, score))
        is_alert = score >= self.detection_threshold

        self._score_history.append(score)
        self._alert_history.append(1.0 if is_alert else 0.0)

        return score, is_alert

    @property
    def alert_rate(self) -> float:
        if not self._alert_history:
            return 0.0
        return float(sum(self._alert_history) / len(self._alert_history))

    @property
    def last_score(self) -> float:
        if not self._score_history:
            return 0.0
        return float(self._score_history[-1])


class SimulatedBlacklister:
    """
    블랙리스트 정책 시뮬레이터.

    - blacklist_aggression (0~1):
        0.0 → threshold=0.1 (민감, 잘 막음)
        1.0 → threshold=0.9 (둔감, 거의 안 막음)

    - blacklist_duration (0~1):
        0.0 → 10 스텝
        1.0 → 10000 스텝 (사실상 매우 길게)
    """

    def __init__(
        self,
        rng: Optional[np.random.Generator] = None,
    ) -> None:
        self.rng = rng or np.random.default_rng()
        self.threshold: float = 0.5
        self.duration_steps: int = 100
        self._entries: Dict[str, int] = {}
        self.min_duration: int = 10
        self.max_duration: int = 10_000

    def set_policy_parameters(
        self,
        aggression: float,
        duration: float,
    ) -> None:
        agg = float(np.clip(aggression, 0.0, 1.0))
        dur = float(np.clip(duration, 0.0, 1.0))
        self.threshold = 0.1 + agg * 0.8
        self.duration_steps = int(self.min_duration + dur * (self.max_duration - self.min_duration))

    def process_alert(self, ip: str, cti_score: float) -> None:
        if cti_score >= self.threshold:
            self._entries[ip] = self.duration_steps

    def step_decay(self) -> None:
        to_delete = []
        for ip, ttl in self._entries.items():
            ttl -= 1
            if ttl <= 0:
                to_delete.append(ip)
            else:
                self._entries[ip] = ttl
        for ip in to_delete:
            del self._entries[ip]

    def is_blocked(self, ip: str) -> bool:
        return ip in self._entries

    @property
    def size(self) -> int:
        return len(self._entries)


class SimulatedHeuristicSeeker:
    """
    시뮬레이터용 Heuristic 공격자.

    level에 따라 scan / exploit / ip-change 패턴이 달라진다고 가정.
    실제 테스트베드 시커가 비슷한 통계를 가지도록 튜닝하면 됨.
    """

    def __init__(
        self,
        level: int = 2,
        rng: Optional[np.random.Generator] = None,
    ) -> None:
        self.level = level
        self.rng = rng or np.random.default_rng()
        self.current_ip: str = "100.10.1.1"
        self.ip_change_count: int = 0
        self.total_steps: int = 0

        # 레벨별 대략적인 행동 비율 설정
        if level == 0:
            self.scan_prob = 0.1
            self.attack_prob = 0.1
            self.ip_change_prob = 0.02
        elif level == 1:
            self.scan_prob = 0.2
            self.attack_prob = 0.2
            self.ip_change_prob = 0.05
        elif level == 2:
            self.scan_prob = 0.25
            self.attack_prob = 0.35
            self.ip_change_prob = 0.08
        elif level == 3:
            self.scan_prob = 0.3
            self.attack_prob = 0.45
            self.ip_change_prob = 0.12
        else:  # level >= 4
            self.scan_prob = 0.3
            self.attack_prob = 0.55
            self.ip_change_prob = 0.2

        # 나머지는 "휴식" (공격 없음)

    def _change_ip_if_needed(self) -> None:
        if self.rng.random() < self.ip_change_prob:
            last_octet = self.rng.integers(2, 254)
            self.current_ip = f"100.10.1.{int(last_octet)}"
            self.ip_change_count += 1

    def act(self) -> Tuple[str, str, bool]:
        """
        Returns:
            action_type: "none" | "scan" | "attack"
            ip: 현재 공격 IP
            suspicious: CTI 기준 '수상한' 트래픽인지 여부
        """
        self.total_steps += 1
        self._change_ip_if_needed()

        r = self.rng.random()
        if r < self.scan_prob:
            return "scan", self.current_ip, True
        elif r < self.scan_prob + self.attack_prob:
            return "attack", self.current_ip, True
        else:
            return "none", self.current_ip, False

    @property
    def ip_change_rate(self) -> float:
        if self.total_steps == 0:
            return 0.0
        return float(self.ip_change_count / self.total_steps)


class NetworkEnv:
    """
    PPO 학습용 MTD 환경.

    - 관찰: FEATURE_KEYS (16차원)
    - 행동: ACTION_PARAM_KEYS (6차원 연속 [-1, 1])

    step(...) 반환:
        obs, reward, done, info

    info에는 반드시 아래 필드가 포함됨:
        cost: float
        is_attack: bool
        is_attack_detected: bool
        is_decoy_action: bool
        is_breach: bool
        did_reconfigure: bool
        attack_stage: str ("idle"|"recon"|"exploit"|"breach")
      + Metrics/*, Params/*
    """

    def __init__(
        self,
        seeker_level: int = 2,
        seed: int = 0,
        max_episode_steps: int = 512,
    ) -> None:
        self.seeker_level = seeker_level
        self.max_episode_steps = max_episode_steps

        self.rng = np.random.default_rng(seed)
        self.cti = SimulatedPassiveCTI(rng=self.rng)
        self.blacklister = SimulatedBlacklister(rng=self.rng)
        self.seeker = SimulatedHeuristicSeeker(level=seeker_level, rng=self.rng)

        # 상태 / 통계
        self.step_count: int = 0
        self.episode_step: int = 0

        self.current_route_type: str = "REAL"  # "REAL" | "DECOY" | "ALTERNATE"
        self.last_action_params = np.full(ACTION_DIM, 0.5, dtype=np.float32)
        self.prev_action_params = self.last_action_params.copy()

        # 메트릭 누적
        self.metrics: Dict[str, float] = {}
        self._uptime_window = deque(maxlen=100)
        self._attack_window = deque(maxlen=100)    # bool is_attack
        self._breach_times: list[float] = []

        # 공격 스텝 집계 (에피소드 단위)
        self.reset_episode_counters()

    # --------------------------------------------------------------------- #
    # 내부 유틸
    # --------------------------------------------------------------------- #

    def reset_episode_counters(self) -> None:
        self.ep_return = 0.0
        self.ep_attack_steps = 0
        self.ep_detected_attack_steps = 0
        self.ep_decoy_attack_steps = 0
        self.ep_breach_events = 0
        self.ep_mtd_cost = 0.0
        self.ep_reconfig_steps = 0
        self.ep_first_attack_step: Optional[int] = None
        self.ep_first_breach_step: Optional[int] = None

    # --------------------------------------------------------------------- #
    # Gym-like API
    # --------------------------------------------------------------------- #

    def reset(self) -> np.ndarray:
        self.step_count += 1
        self.episode_step = 0

        # 새 시뮬레이터 인스턴스
        self.cti = SimulatedPassiveCTI(rng=self.rng)
        self.blacklister = SimulatedBlacklister(rng=self.rng)
        self.seeker = SimulatedHeuristicSeeker(level=self.seeker_level, rng=self.rng)

        self.current_route_type = "REAL"
        self.prev_action_params = np.full(ACTION_DIM, 0.5, dtype=np.float32)
        self.last_action_params = self.prev_action_params.copy()

        self.metrics = {
            "cti_alert_rate": 0.0,
            "blacklist_size": 0.0,
            "seeker_ip_change_rate": 0.0,
            "breach_success_rate": 0.0,
            "decoy_lure_rate": 0.0,
            "alternate_node_health": 1.0,
            "service_uptime_ratio": 1.0,
            "system_cost": 0.0,
            "recent_attack_flag": 0.0,
            "mean_time_to_breach": 0.0,
        }
        self._uptime_window.clear()
        self._attack_window.clear()
        self._breach_times.clear()
        self.reset_episode_counters()

        return self._get_state()

    def step(self, action: np.ndarray) -> Tuple[np.ndarray, float, bool, Dict[str, Any]]:
        self.episode_step += 1

        # 1) 액션 스케일링 [-1,1] -> [0,1]
        action = np.asarray(action, dtype=np.float32).reshape(-1)
        assert action.shape[0] == ACTION_DIM, f"expected {ACTION_DIM} actions, got {action.shape[0]}"
        raw_action = np.clip(action, -1.0, 1.0)
        scaled_action = (raw_action + 1.0) / 2.0  # 0~1
        self.prev_action_params = self.last_action_params.copy()
        self.last_action_params = scaled_action.copy()

        # 2) MTD 전략 적용
        step_cost, did_reconfigure = self._apply_mtd_strategy(scaled_action)

        # 3) 시커 턴 실행
        turn_info = self._run_seeker_turn()

        is_attack = turn_info["is_attack"]
        is_breach = turn_info["is_breach"]
        is_decoy_action = (self.current_route_type == "DECOY") and is_attack
        is_attack_detected = turn_info["is_attack_detected"]

        # 4) 메트릭 업데이트
        self._update_metrics(step_cost, is_attack, is_breach, is_decoy_action)

        # 5) 보상 계산
        reward = self._calculate_reward(step_cost)

        # 에피소드 통계
        self.ep_return += reward
        if is_attack:
            self.ep_attack_steps += 1
        if is_attack_detected:
            self.ep_detected_attack_steps += 1
        if is_decoy_action:
            self.ep_decoy_attack_steps += 1
        if is_breach:
            self.ep_breach_events += 1
        self.ep_mtd_cost += step_cost
        if did_reconfigure:
            self.ep_reconfig_steps += 1

        # 에피소드 종료 조건
        done = self.episode_step >= self.max_episode_steps

        # 6) 상태/정보 구성
        obs = self._get_state()
        info: Dict[str, Any] = {
            # PPO 학습에서 사용하는 핵심 플래그
            "cost": float(step_cost),
            "is_attack": bool(is_attack),
            "is_attack_detected": bool(is_attack_detected),
            "is_decoy_action": bool(is_decoy_action),
            "is_breach": bool(is_breach),
            "did_reconfigure": bool(did_reconfigure),
            "attack_stage": turn_info["attack_stage"],

            # Metrics/*
            "Metrics/cti_alert_rate": self.metrics["cti_alert_rate"],
            "Metrics/blacklist_size": self.metrics["blacklist_size"],
            "Metrics/seeker_ip_change_rate": self.metrics["seeker_ip_change_rate"],
            "Metrics/breach_success_rate": self.metrics["breach_success_rate"],
            "Metrics/decoy_lure_rate": self.metrics["decoy_lure_rate"],
            "Metrics/alternate_node_health": self.metrics["alternate_node_health"],
            "Metrics/service_uptime_ratio": self.metrics["service_uptime_ratio"],
            "Metrics/system_cost": self.metrics["system_cost"],
            "Metrics/recent_attack_flag": self.metrics["recent_attack_flag"],
            "Metrics/mean_time_to_breach": self.metrics["mean_time_to_breach"],

            # Params/*
            "Params/dnat_route_type": self.current_route_type,
            "Params/dnat_real_focus": float(self.last_action_params[0]),
            "Params/dnat_decoy_focus": float(self.last_action_params[1]),
            "Params/dnat_alternate_focus": float(self.last_action_params[2]),
            "Params/shuffle_intensity": float(self.last_action_params[3]),
            "Params/blacklist_aggression": float(self.last_action_params[4]),
            "Params/blacklist_duration": float(self.last_action_params[5]),
        }

        return obs, float(reward), bool(done), info

    # ------------------------------------------------------------------ #
    # 내부 로직
    # ------------------------------------------------------------------ #

    def _apply_mtd_strategy(self, scaled_action: np.ndarray) -> Tuple[float, bool]:
        """
        scaled_action: 0~1 범위 6차원

        Returns:
            step_cost: float
            did_reconfigure: bool
        """
        dnat_logits = np.array(scaled_action[:3], dtype=np.float64) + 1e-8
        dnat_probs = dnat_logits / dnat_logits.sum()
        route_idx = int(self.rng.choice(3, p=dnat_probs))
        new_route_type = ["REAL", "DECOY", "ALTERNATE"][route_idx]

        shuffle_intensity = float(scaled_action[3])
        blacklist_aggression = float(scaled_action[4])
        blacklist_duration = float(scaled_action[5])

        # 블랙리스트 정책 적용
        self.blacklister.set_policy_parameters(
            aggression=blacklist_aggression,
            duration=blacklist_duration,
        )

        # 셔플 → 가용성 / 비용 모델
        if shuffle_intensity > 0.75:
            uptime = 0.1
            shuffle_cost = 5.0 * shuffle_intensity
        elif shuffle_intensity > 0.3:
            uptime = 0.7
            shuffle_cost = 2.0 * shuffle_intensity
        else:
            uptime = 1.0
            shuffle_cost = 0.5 * shuffle_intensity

        self._uptime_window.append(uptime)

        # 대체 노드 health 모델
        if new_route_type == "ALTERNATE":
            alt_health = 0.4 + 0.2 * self.rng.random()  # 0.4~0.6
        else:
            alt_health = 1.0
        self.metrics["alternate_node_health"] = alt_health

        # 블랙리스트 유지 비용
        blacklist_cost = 0.05 * self.blacklister.size

        step_cost = shuffle_cost + blacklist_cost

        # 재구성 여부 체크
        did_reconfigure = (
            (new_route_type != self.current_route_type)
            or (np.abs(self.last_action_params - self.prev_action_params).max() > 1e-3)
        )
        self.current_route_type = new_route_type

        return float(step_cost), bool(did_reconfigure)

    def _run_seeker_turn(self) -> Dict[str, Any]:
        action_type, ip, suspicious = self.seeker.act()

        is_attack = action_type in ("scan", "attack")
        attack_stage = "idle"
        if action_type == "scan":
            attack_stage = "recon"
        elif action_type == "attack":
            attack_stage = "exploit"

        # CTI 처리
        cti_score, cti_alert = self.cti.process_traffic(suspicious=is_attack and suspicious)
        self.blacklister.process_alert(ip, cti_score)
        self.blacklister.step_decay()
        blocked = self.blacklister.is_blocked(ip)

        is_attack_detected = is_attack and (cti_alert or blocked)

        # 침투 / 디코이 판정
        is_breach = False
        is_decoy = False
        if action_type == "attack" and not blocked:
            if self.current_route_type == "DECOY":
                is_decoy = True
                attack_stage = "exploit"
            elif self.current_route_type in ("REAL", "ALTERNATE"):
                is_breach = True
                attack_stage = "breach"

        # TTB/TTBR 기록용
        if is_attack:
            if self.ep_first_attack_step is None:
                self.ep_first_attack_step = self.episode_step
        if is_breach:
            if self.ep_first_breach_step is None:
                self.ep_first_breach_step = self.episode_step
                ttb = (self.ep_first_breach_step - (self.ep_first_attack_step or 0)) * SIM_TIME_PER_STEP_SEC
                self._breach_times.append(float(max(ttb, 0.0)))

        return {
            "is_attack": bool(is_attack),
            "is_attack_detected": bool(is_attack_detected),
            "is_breach": bool(is_breach),
            "is_decoy": bool(is_decoy),
            "attack_stage": attack_stage,
        }

    def _update_metrics(
        self,
        step_cost: float,
        is_attack: bool,
        is_breach: bool,
        is_decoy_action: bool,
    ) -> None:
        # 공격 여부 윈도우
        self._attack_window.append(1.0 if is_attack else 0.0)

        # breach / decoy 통계 (에피소드 레벨은 self.* 로 따로 집계)
        # 여기서는 전체 에피소드 기준 비율만 기록
        attack_count = max(self.ep_attack_steps, 1)
        self.metrics["breach_success_rate"] = float(self.ep_breach_events / attack_count)
        self.metrics["decoy_lure_rate"] = float(self.ep_decoy_attack_steps / attack_count)

        # CTI / 블랙리스트 / 시커
        self.metrics["cti_alert_rate"] = self.cti.alert_rate
        self.metrics["blacklist_size"] = float(self.blacklister.size)
        self.metrics["seeker_ip_change_rate"] = self.seeker.ip_change_rate

        # 서비스 가동률
        if self._uptime_window:
            self.metrics["service_uptime_ratio"] = float(sum(self._uptime_window) / len(self._uptime_window))
        else:
            self.metrics["service_uptime_ratio"] = 1.0

        # 시스템 비용 (스텝 평균)
        self.ep_mtd_cost += step_cost
        total_steps = max(self.episode_step, 1)
        self.metrics["system_cost"] = float(self.ep_mtd_cost / total_steps)

        # 최근 공격 플래그 (윈도우 안에 1개라도 있으면 1)
        self.metrics["recent_attack_flag"] = 1.0 if any(self._attack_window) else 0.0

        # mean_time_to_breach
        if self._breach_times:
            self.metrics["mean_time_to_breach"] = float(
                sum(self._breach_times) / len(self._breach_times)
            )
        else:
            self.metrics["mean_time_to_breach"] = 0.0

    def _calculate_reward(self, step_cost: float) -> float:
        """
        직관적인 보상 설계:
        - 침투율 ↓ : 보상 +
        - 디코이율 ↑ : 보상 +
        - 가동률 ↑ : 보상 +
        - MTD 비용 ↑ : 보상 -
        """
        m = self.metrics
        breach_rate = m["breach_success_rate"]
        decoy_rate = m["decoy_lure_rate"]
        uptime = m["service_uptime_ratio"]

        reward = 0.0
        reward += (1.0 - breach_rate) * 10.0
        reward += decoy_rate * 3.0
        reward += uptime * 2.0
        reward -= step_cost * 0.5

        return float(reward)

    def _get_state(self) -> np.ndarray:
        state = np.zeros(OBS_DIM, dtype=np.float32)
        # BASE_FEATURE_KEYS + last_action
        for i, key in enumerate(FEATURE_KEYS[: len(self.metrics)]):
            state[i] = float(self.metrics.get(key, 0.0))
        state[len(self.metrics) :] = self.last_action_params.astype(np.float32)
        return state
