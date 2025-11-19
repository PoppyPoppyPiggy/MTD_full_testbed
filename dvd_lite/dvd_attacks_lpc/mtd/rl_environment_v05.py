# 파일: dvd_lite/dvd_attacks_lpc/mtd/rl_environment_v05.py
import gym
from gym import spaces

import numpy as np
import random
import logging
from collections import deque
from scipy.special import expit  # sigmoid
import math

from .rl_config_v05 import (
    FEATURE_KEYS,
    ACTION_PARAM_KEYS,
    SIM_TIME_PER_STEP_SEC,
    NUM_TARGET_ENDPOINTS,
    NUM_DECOY_ENDPOINTS,
    NUM_TOTAL_ENDPOINTS,
    SEEKER_PROB_PARAMS,
    COST_MTD_ACTION,
    COST_SHUFFLE,
    COST_DECOY,
    COST_BL,
    COST_WEIGHT,
)

logger = logging.getLogger(__name__)


def _scale_action(action, lower_bound=0.0, upper_bound=1.0):
    """[-1, 1] 범위(action)를 [lower_bound, upper_bound]로 선형 스케일."""
    return lower_bound + (0.5 * (action + 1.0) * (upper_bound - lower_bound))


def _safe_divide(numerator, denominator):
    return numerator / denominator if denominator != 0 else 0.0


class SimulatedPassiveCTI:
    """수동 CTI 에이전트 시뮬레이터: suspicious 여부에 따라 score, alert_rate 생성."""
    def __init__(self, rng, window_size=100, detection_threshold=0.5):
        self.rng = rng
        self.detection_threshold = detection_threshold
        self.alert_history = deque([0] * window_size, maxlen=window_size)

    def process_traffic(self, is_suspicious: bool):
        if is_suspicious:
            score = self.rng.normal(loc=0.8, scale=0.1)
        else:
            score = self.rng.normal(loc=0.1, scale=0.1)
        score = np.clip(score, 0.0, 1.0)

        is_alert = score >= self.detection_threshold
        self.alert_history.append(1 if is_alert else 0)
        return score, is_alert

    def get_alert_rate(self) -> float:
        return sum(self.alert_history) / self.alert_history.maxlen


class SimulatedBlacklister:
    """BL 정책 (aggression, duration)을 기반으로 IP 블랙리스트 동작 시뮬레이션."""
    def __init__(self, rng):
        self.rng = rng
        self.blacklist_policy = {
            "aggression": 0.0,
            "duration": 0,
        }
        self.blocked_ips = {}  # ip -> remaining_steps

    def update_policy(self, aggression_param: float, duration_param: float):
        from .rl_config_v05 import (
            BLACKLIST_SENSITIVITY_MIN,
            BLACKLIST_SENSITIVITY_MAX,
            BLACKLIST_DURATION_MIN_STEPS,
            BLACKLIST_DURATION_MAX_STEPS,
        )

        sensitivity = aggression_param * (BLACKLIST_SENSITIVITY_MAX - BLACKLIST_SENSITIVITY_MIN) + BLACKLIST_SENSITIVITY_MIN
        duration_steps = int(
            duration_param * (BLACKLIST_DURATION_MAX_STEPS - BLACKLIST_DURATION_MIN_STEPS)
            + BLACKLIST_DURATION_MIN_STEPS
        )

        self.blacklist_policy.update(
            {
                "aggression": sensitivity,
                "duration": duration_steps,
            }
        )
        return self.blacklist_policy

    def apply_block(self, ip: str, cti_score: float) -> bool:
        if cti_score >= self.blacklist_policy["aggression"]:
            self.blocked_ips[ip] = self.blacklist_policy["duration"]
            return True
        return False

    def step(self):
        # duration 감소 및 만료 IP 제거
        expired_ips = [ip for ip, duration in self.blocked_ips.items() if duration <= 1]
        for ip in expired_ips:
            del self.blocked_ips[ip]
        for ip in list(self.blocked_ips.keys()):
            self.blocked_ips[ip] -= 1

    def is_blocked(self, ip: str) -> bool:
        return ip in self.blocked_ips

    def get_size_ratio(self) -> float:
        return min(1.0, len(self.blocked_ips) / NUM_TOTAL_ENDPOINTS)

    def get_current_level(self) -> float:
        return self.blacklist_policy["aggression"]


class SimulatedHeuristicSeeker:
    """
    Scan -> Find -> Exploit -> Breach 단계로 움직이는 Seeker 모델.
    1.1 / 1.3에서 정의한 확률 모델 기반.
    """
    def __init__(self, rng, seeker_level, ip_list, decoy_ip_list):
        self.rng = rng
        self.ip_list = ip_list
        self.decoy_ip_list = decoy_ip_list
        self.seeker_level = seeker_level
        self.current_ip = self.rng.choice(self.ip_list + self.decoy_ip_list)

        # LPC: 0=unknown, 1=found, 2=exploited
        self.ip_knowledge = {ip: 0 for ip in self.ip_list + self.decoy_ip_list}
        self.current_exposure_steps = 0

        self.scan_effort, self.attack_bias, self.ip_change_prob = self._get_seeker_params(seeker_level)
        self.seeker_params = (self.scan_effort, self.attack_bias)

        # episode 카운터
        self.scan_attempts = 0
        self.find_events = 0
        self.exploit_attempts = 0
        self.exploit_block = 0
        self.exploit_success = 0
        self.breach_attempts = 0
        self.breach_block = 0
        self.breach_success = 0
        self.decoy_lures = 0

    def _get_seeker_params(self, level):
        if level == 0:
            return 0.5, 0.5, 0.05
        elif level == 1:
            return 2.0, 0.8, 0.02
        elif level == 2:
            return 0.8, 0.2, 0.01
        elif level == 3:
            return 1.0, 0.5, 0.03
        else:
            return 1.0, 0.5, 0.05

    def _update_ip_knowledge(self, ip, status_code):
        if status_code > self.ip_knowledge.get(ip, 0):
            self.ip_knowledge[ip] = status_code

    def _get_seeker_scan_prob(self) -> float:
        factor = SEEKER_PROB_PARAMS["SCAN_PROB_FACTOR"]
        min_p = SEEKER_PROB_PARAMS["SCAN_PROB_MIN"]
        max_p = SEEKER_PROB_PARAMS["SCAN_PROB_MAX"]
        return float(np.clip(factor * self.scan_effort, min_p, max_p))

    def _get_seeker_find_prob(self) -> float:
        if self.ip_knowledge.get(self.current_ip, 0) < 1:
            exp_factor = SEEKER_PROB_PARAMS["FIND_EXP_FACTOR"]
            p_find = 1.0 - math.exp(-exp_factor * self.current_exposure_steps)
            return float(np.clip(p_find, 0.0, 1.0))
        return 1.0

    def _get_exploit_block_prob(self, blacklist_level: float):
        is_loud = self.rng.random() < self.attack_bias
        if is_loud:
            slope = SEEKER_PROB_PARAMS["EXPLOIT_BLOCK_LOUD_SLOPE"]
            shift = SEEKER_PROB_PARAMS["EXPLOIT_BLOCK_LOUD_SHIFT"]
        else:
            slope = SEEKER_PROB_PARAMS["EXPLOIT_BLOCK_STEALTH_SLOPE"]
            shift = SEEKER_PROB_PARAMS["EXPLOIT_BLOCK_STEALTH_SHIFT"]
        p_block = expit(slope * blacklist_level + shift)
        return float(p_block), is_loud

    def _get_breach_block_prob(self, blacklist_level: float):
        slope = SEEKER_PROB_PARAMS["BREACH_BLOCK_SLOPE"]
        shift = SEEKER_PROB_PARAMS["BREACH_BLOCK_SHIFT"]
        return float(expit(slope * blacklist_level + shift))

    def step(self, blacklist_level: float, is_mtd_shuffle: bool):
        self.current_exposure_steps += 1

        if is_mtd_shuffle:
            self.current_exposure_steps = 1
            self.ip_knowledge[self.current_ip] = 0
            self.current_ip = self.rng.choice(self.ip_list + self.decoy_ip_list)

        did_ip_change = self.rng.random() < self.ip_change_prob and not is_mtd_shuffle
        if did_ip_change:
            self.current_ip = self.rng.choice(self.ip_list + self.decoy_ip_list)
            self.current_exposure_steps = 1
            self._update_ip_knowledge(self.current_ip, 0)

        # 플래그 초기화
        is_attack = False
        is_exploit = False
        is_breach = False
        is_find = False
        is_exploit_block = False
        is_exploit_success = False
        is_breach_block = False
        is_breach_success = False
        is_loud = False
        is_decoy = self.current_ip in self.decoy_ip_list
        exposure_at_found = 0
        exposure_at_exploit_block = 0
        exposure_at_breach_success = 0

        # 액션 타입 결정
        if self.ip_knowledge.get(self.current_ip, 0) < 1:
            action_type = "Scan"
        elif self.ip_knowledge.get(self.current_ip, 0) == 1:
            action_type = "Attack"
            is_exploit = True
        elif self.ip_knowledge.get(self.current_ip, 0) == 2:
            action_type = "Attack"
            is_breach = True
        else:
            action_type = "None"

        if action_type == "Scan":
            self.scan_attempts += 1
            if self.rng.random() < self._get_seeker_scan_prob():
                if self.rng.random() < self._get_seeker_find_prob():
                    is_find = True
                    self.find_events += 1
                    self._update_ip_knowledge(self.current_ip, 1)
                    exposure_at_found = self.current_exposure_steps

        elif action_type == "Attack":
            is_attack = True

            if is_exploit:
                self.exploit_attempts += 1
                p_block, is_loud = self._get_exploit_block_prob(blacklist_level)
                is_exploit_block = self.rng.random() < p_block

                if is_exploit_block:
                    self.exploit_block += 1
                    exposure_at_exploit_block = self.current_exposure_steps
                else:
                    p_success = (
                        SEEKER_PROB_PARAMS["EXPLOIT_SUCCESS_LOUD"]
                        if is_loud
                        else SEEKER_PROB_PARAMS["EXPLOIT_SUCCESS_STEALTH"]
                    )
                    if self.rng.random() < p_success:
                        is_exploit_success = True
                        self.exploit_success += 1
                        self._update_ip_knowledge(self.current_ip, 2)

            # Breach 시도(Exploit 성공 직후 또는 이미 Exploit 상태)
            if is_breach or (
                is_exploit_success and self.rng.random() < SEEKER_PROB_PARAMS["BREACH_ATTEMPT_PROB"]
            ):
                is_breach_attempt = True
                self.breach_attempts += 1
                p_block = self._get_breach_block_prob(blacklist_level)
                is_breach_block = self.rng.random() < p_block
                if is_breach_block:
                    self.breach_block += 1
                else:
                    is_breach_success = True
                    self.breach_success += 1
                    exposure_at_breach_success = self.current_exposure_steps
            else:
                is_breach_attempt = False

            if is_decoy and (is_exploit or is_breach_attempt):
                self.decoy_lures += 1

        else:
            is_breach_attempt = False

        return {
            "is_scan": action_type == "Scan",
            "is_find": is_find,
            "is_exploit_attempt": is_exploit,
            "is_exploit_block": is_exploit_block,
            "is_exploit_success": is_exploit_success,
            "is_breach_attempt": is_breach_attempt if is_attack else False,
            "is_breach_block": is_breach_block,
            "is_breach_success": is_breach_success,
            "is_decoy_hit": is_decoy and is_attack,
            "is_loud": is_loud,
            "exposure_at_found": exposure_at_found,
            "exposure_at_exploit_block": exposure_at_exploit_block,
            "exposure_at_breach_success": exposure_at_breach_success,
            "seeker_ip": self.current_ip,
            "seeker_knowledge": self.ip_knowledge,
        }

    def get_knowledge_ratios(self):
        total_ips = len(self.ip_list + self.decoy_ip_list)
        known_count = sum(1 for status in self.ip_knowledge.values() if status >= 1)
        exploited_count = sum(1 for status in self.ip_knowledge.values() if status == 2)
        return (
            _safe_divide(known_count, total_ips),
            _safe_divide(exploited_count, total_ips),
        )

    def get_current_exposure(self):
        return self.current_exposure_steps

    def get_seeker_params(self):
        return self.seeker_params


class NetworkEnv(gym.Env):
    """MTD RL 학습용 환경. Seeker 확률 모델 + MTD 메타 액션 + DRS/TTF 등 지표 계산."""
    metadata = {"render_modes": ["human"], "render_fps": 4}
    max_episode_steps = 1000  # 클래스 레벨 기본값

    def __init__(self, seed=None, seeker_level=2, log_dir=None):
        super().__init__()
        self.rng = np.random.default_rng(seed)
        self.seeker_level = seeker_level
        self.ip_list = [f"192.168.1.{i}" for i in range(NUM_TARGET_ENDPOINTS)]
        self.decoy_ip_list = [f"10.0.0.{i}" for i in range(NUM_DECOY_ENDPOINTS)]
        self.max_episode_steps = self.__class__.max_episode_steps
        self.current_step = 0
        self.log_dir = log_dir

        self.cti = None
        self.blacklister = None
        self.seeker = None

        self.action_space = spaces.Box(
            low=-1.0, high=1.0, shape=(len(ACTION_PARAM_KEYS),), dtype=np.float32
        )
        self.observation_space = spaces.Box(
            low=-100.0, high=100.0, shape=(len(FEATURE_KEYS),), dtype=np.float32
        )

        self._reset_counters()

    def _reset_counters(self):
        self.ep_total_steps = 0
        self.ep_total_cost = 0.0
        self.ep_shuffle_count = 0
        self.ep_uptime_steps = 0

        self.ep_scan_attempts = 0
        self.ep_find_events = 0
        self.ep_exploit_attempts = 0
        self.ep_exploit_block = 0
        self.ep_exploit_success = 0
        self.ep_breach_attempts = 0
        self.ep_breach_block = 0
        self.ep_breach_success = 0
        self.ep_decoy_hits = 0

        self.tte_find_accum = []
        self.tte_exploit_block_accum = []
        self.tte_breach_success_accum = []

        self.endpoint_visits = {ip: 0 for ip in self.ip_list + self.decoy_ip_list}
        self.policy_history = []

    def reset(self, seed=None, options=None):
        if seed is not None:
            self.rng = np.random.default_rng(seed)
            super().reset(seed=seed)

        self.cti = SimulatedPassiveCTI(self.rng)
        self.blacklister = SimulatedBlacklister(self.rng)
        self.seeker = SimulatedHeuristicSeeker(self.rng, self.seeker_level, self.ip_list, self.decoy_ip_list)

        self.current_step = 0
        self._reset_counters()

        self.last_actions = {key: 0.5 for key in ACTION_PARAM_KEYS}

        observation = self._get_state()
        info = self._get_current_metrics()
        info["last_action"] = self.last_actions

        return observation, info

    def _apply_mtd_strategy(self, action: np.ndarray):
        action_params = {
            "dnat_target_focus": _scale_action(action[0]),
            "dnat_decoy_focus": _scale_action(action[1]),
            "shuffle_intensity": _scale_action(action[2]),
            "blacklist_aggression": _scale_action(action[3]),
            "blacklist_duration": _scale_action(action[4]),
            "decoy_ratio": _scale_action(action[5]),
        }
        self.last_actions = action_params

        bl_policy = self.blacklister.update_policy(
            action_params["blacklist_aggression"],
            action_params["blacklist_duration"],
        )

        is_shuffle = action_params["shuffle_intensity"] > 0.75
        if is_shuffle:
            self.ep_shuffle_count += 1

        bl_level = self.blacklister.get_current_level()

        cost_mtd = COST_MTD_ACTION
        cost_shuffle = COST_SHUFFLE if is_shuffle else 0.0
        cost_decoy = COST_DECOY * action_params["decoy_ratio"]
        cost_bl = COST_BL * bl_level

        total_cost = cost_mtd + cost_shuffle + cost_decoy + cost_bl
        self.ep_total_cost += total_cost

        self.policy_history.append(
            {
                "decoy_ratio": action_params["decoy_ratio"],
                "bl": bl_level,
                "cost": total_cost,
                "is_shuffle": is_shuffle,
            }
        )

        return {
            "cost": total_cost,
            "bl_level": bl_level,
            "decoy_ratio": action_params["decoy_ratio"],
            "is_shuffle": is_shuffle,
        }

    def step(self, action: np.ndarray):
        self.current_step += 1
        self.ep_total_steps += 1
        terminated = self.current_step >= self.max_episode_steps
        truncated = False

        mtd_results = self._apply_mtd_strategy(action)
        is_shuffle = mtd_results["is_shuffle"]
        bl_level = mtd_results["bl_level"]

        seeker_outcomes = self.seeker.step(bl_level, is_shuffle)
        current_ip = seeker_outcomes["seeker_ip"]
        self.endpoint_visits[current_ip] += 1

        is_suspicious = seeker_outcomes["is_scan"] or seeker_outcomes["is_exploit_attempt"]
        cti_score, is_alert = self.cti.process_traffic(is_suspicious)
        if is_alert:
            self.blacklister.apply_block(current_ip, cti_score)
        self.blacklister.step()

        is_breach_success = seeker_outcomes["is_breach_success"]

        # 카운터/TTF 누적
        if seeker_outcomes["is_scan"]:
            self.ep_scan_attempts += 1
        if seeker_outcomes["is_find"]:
            self.ep_find_events += 1
            if seeker_outcomes["exposure_at_found"] > 0:
                self.tte_find_accum.append(seeker_outcomes["exposure_at_found"])

        if seeker_outcomes["is_exploit_attempt"]:
            self.ep_exploit_attempts += 1
        if seeker_outcomes["is_exploit_block"]:
            self.ep_exploit_block += 1
            if seeker_outcomes["exposure_at_exploit_block"] > 0:
                self.tte_exploit_block_accum.append(seeker_outcomes["exposure_at_exploit_block"])

        if seeker_outcomes["is_exploit_success"]:
            self.ep_exploit_success += 1

        if seeker_outcomes["is_breach_attempt"]:
            self.ep_breach_attempts += 1
        if seeker_outcomes["is_breach_block"]:
            self.ep_breach_block += 1
        if is_breach_success:
            self.ep_breach_success += 1
            if seeker_outcomes["exposure_at_breach_success"] > 0:
                self.tte_breach_success_accum.append(seeker_outcomes["exposure_at_breach_success"])

        if seeker_outcomes["is_decoy_hit"]:
            self.ep_decoy_hits += 1

        is_downtime = is_shuffle
        if not is_downtime:
            self.ep_uptime_steps += 1

        reward = self._calculate_reward(mtd_results, seeker_outcomes)

        observation = self._get_state()
        info = self._get_current_metrics()
        info.update(
            {
                "cost": mtd_results["cost"],
                "is_shuffle": is_shuffle,
                "is_find": seeker_outcomes["is_find"],
                "is_exploit_block": seeker_outcomes["is_exploit_block"],
                "is_breach_block": seeker_outcomes["is_breach_block"],
                "is_exploit_success": seeker_outcomes["is_exploit_success"],
                "is_breach_success": is_breach_success,
                "is_decoy_hit": seeker_outcomes["is_decoy_hit"],
                "exposure_at_found": seeker_outcomes["exposure_at_found"],
                "exposure_at_exploit_block": seeker_outcomes["exposure_at_exploit_block"],
                "exposure_at_breach_success": seeker_outcomes["exposure_at_breach_success"],
                "Params/bl_level": bl_level,
                "Params/decoy_ratio": mtd_results["decoy_ratio"],
                "Params/shuffle_intensity": self.last_actions["shuffle_intensity"],
            }
        )

        if is_breach_success:
            terminated = True

        return observation, reward, terminated, truncated, info

    def _calculate_reward(self, mtd_results, seeker_outcomes):
        cost = mtd_results["cost"]

        exploit_block = 1.0 if seeker_outcomes["is_exploit_block"] else 0.0
        decoy = 1.0 if seeker_outcomes["is_decoy_hit"] else 0.0
        exploit_success = 1.0 if seeker_outcomes["is_exploit_success"] else 0.0
        breach_block = 1.0 if seeker_outcomes["is_breach_block"] else 0.0
        breach_success = 1.0 if seeker_outcomes["is_breach_success"] else 0.0
        find = 1.0 if seeker_outcomes["is_find"] else 0.0

        r_def = (
            (+1.0) * exploit_block
            + (+1.0) * decoy
            + (-2.0) * exploit_success
            + (+2.0) * breach_block
            + (-5.0) * breach_success
            + (-0.1) * find
            - COST_WEIGHT * cost
        )
        return float(r_def)

    def _get_state(self):
        known_ratio, exploited_ratio = self.seeker.get_knowledge_ratios()

        metrics = {
            "cti_alert_rate": self.cti.get_alert_rate(),
            "blacklist_size_ratio": self.blacklister.get_size_ratio(),
            "uptime_ratio": _safe_divide(self.ep_uptime_steps, self.ep_total_steps) if self.ep_total_steps > 0 else 1.0,
            "breach_success_rate": _safe_divide(self.ep_breach_success, self.ep_breach_attempts),
            "decoy_lure_rate": _safe_divide(self.ep_decoy_hits, self.ep_exploit_attempts),
            "current_exposure_mean": self.seeker.get_current_exposure(),
            "r_known_ratio": known_ratio,
            "r_exploited_ratio": exploited_ratio,
            "seeker_scan_effort": self.seeker.get_seeker_params()[0],
            "seeker_attack_bias": self.seeker.get_seeker_params()[1],
        }

        state_vector = [metrics.get(key, 0.0) for key in FEATURE_KEYS[:10]]
        state_vector.extend([self.last_actions.get(key, 0.5) for key in ACTION_PARAM_KEYS])

        return np.array(state_vector, dtype=np.float32)

    def _get_current_metrics(self):
        info = {}

        breach_attempts = self.ep_breach_attempts
        breach_success = self.ep_breach_success

        r_succ = 1.0 - _safe_divide(breach_success, breach_attempts)
        c_def = _safe_divide(self.ep_total_cost, self.ep_total_steps)
        total_blocks = self.ep_exploit_block + self.ep_breach_block + self.ep_decoy_hits
        cost_per_block = _safe_divide(self.ep_total_cost, total_blocks)

        decoy_lure_rate = _safe_divide(self.ep_decoy_hits, self.ep_exploit_attempts)
        s_mtd_overall = (0.5 * decoy_lure_rate) + (0.5 * r_succ) - (0.1 * c_def)

        metrics = {
            "Defense/R_succ": r_succ,
            "Defense/C_def": c_def,
            "Defense/CostPerBlock": cost_per_block,
            "Defense/S_MTD_overall": s_mtd_overall,
            "Attack/r_exploit_success": _safe_divide(self.ep_exploit_success, self.ep_exploit_attempts),
            "Attack/r_exploit_block": _safe_divide(self.ep_exploit_block, self.ep_exploit_attempts),
            "Attack/r_breach_success": _safe_divide(breach_success, breach_attempts),
            "Attack/r_breach_block": _safe_divide(self.ep_breach_block, breach_attempts),
            "Attack/r_scan": _safe_divide(self.ep_scan_attempts, self.ep_total_steps),
            "Attack/r_find": _safe_divide(self.ep_find_events, self.ep_scan_attempts),
            "Attack/decoy_lure_rate": decoy_lure_rate,
            "Time/TTF_mean": float(np.mean(self.tte_find_accum)) if self.tte_find_accum else 0.0,
            "Time/TTEB_mean": float(np.mean(self.tte_exploit_block_accum)) if self.tte_exploit_block_accum else 0.0,
            "Time/TTBr_mean": float(np.mean(self.tte_breach_success_accum)) if self.tte_breach_success_accum else 0.0,
            "DRS/D_bits": self._calculate_diversity(),
            "DRS/S_shuffle": self._calculate_shuffle_score(),
            # R(중복성)는 간단히 target endpoint 개수로 표현
            "DRS/R_redundancy": float(NUM_TARGET_ENDPOINTS),
        }

        info["Metrics"] = metrics
        return info

    def _calculate_diversity(self):
        visit_counts = np.array(list(self.endpoint_visits.values()), dtype=float)
        total_visits = np.sum(visit_counts)
        if total_visits > 0:
            p = visit_counts / total_visits
            p = p[p > 0]
            return float(-np.sum(p * np.log2(p)))
        return 0.0

    def _calculate_shuffle_score(self):
        shuffle_freq = _safe_divide(self.ep_shuffle_count, self.ep_total_steps)
        return float(shuffle_freq * math.log2(NUM_TOTAL_ENDPOINTS))
