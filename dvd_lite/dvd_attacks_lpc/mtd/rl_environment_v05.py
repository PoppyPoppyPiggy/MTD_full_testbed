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


# -------------------------
# 공통 유틸
# -------------------------
def _scale_action(action, lower_bound=0.0, upper_bound=1.0):
    """[-1, 1] -> [lower_bound, upper_bound]"""
    return lower_bound + (0.5 * (action + 1.0) * (upper_bound - lower_bound))


def _safe_divide(numerator, denominator):
    return numerator / denominator if denominator != 0 else 0.0


# -------------------------
# Simulated CTI
# -------------------------
class SimulatedPassiveCTI:
    """수동 CTI 에이전트 (alert_rate 제공)"""

    def __init__(self, rng, window_size=100, detection_threshold=0.5):
        self.rng = rng
        self.detection_threshold = detection_threshold
        self.alert_history = deque([0] * window_size, maxlen=window_size)

    def process_traffic(self, is_suspicious: bool):
        if is_suspicious:
            score = self.rng.normal(loc=0.8, scale=0.1)
        else:
            score = self.rng.normal(loc=0.1, scale=0.1)

        score = float(np.clip(score, 0.0, 1.0))
        is_alert = score >= self.detection_threshold
        self.alert_history.append(1 if is_alert else 0)
        return score, is_alert

    def get_alert_rate(self) -> float:
        return sum(self.alert_history) / self.alert_history.maxlen


# -------------------------
# Simulated Blacklister (BL)
# -------------------------
class SimulatedBlacklister:
    def __init__(self, rng):
        self.rng = rng
        self.blacklist_policy = {
            "aggression": 0.0,  # [0,1] -> CTI threshold
            "duration": 0,      # steps
        }
        self.blocked_ips = {}  # ip -> remaining_steps

    def update_policy(self, aggression_param, duration_param):
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
                "aggression": float(np.clip(sensitivity, 0.0, 1.0)),
                "duration": max(1, duration_steps),
            }
        )
        return self.blacklist_policy

    def apply_block(self, ip, cti_score: float) -> bool:
        if cti_score >= self.blacklist_policy["aggression"]:
            self.blocked_ips[ip] = self.blacklist_policy["duration"]
            return True
        return False

    def step(self):
        expired = [ip for ip, d in self.blocked_ips.items() if d <= 1]
        for ip in expired:
            del self.blocked_ips[ip]
        for ip in list(self.blocked_ips.keys()):
            self.blocked_ips[ip] -= 1

    def is_blocked(self, ip) -> bool:
        return ip in self.blocked_ips

    def get_size_ratio(self) -> float:
        return min(1.0, len(self.blocked_ips) / NUM_TOTAL_ENDPOINTS)

    def get_current_level(self) -> float:
        return self.blacklist_policy["aggression"]


# -------------------------
# Simulated Heuristic Seeker
# -------------------------
class SimulatedHeuristicSeeker:
    """
    Scan → Find → Exploit → Breach
    L0~L2: 고정 파라미터, L3: ARL 대략치
    """

    def __init__(self, rng, seeker_level, ip_list, decoy_ip_list):
        self.rng = rng
        self.ip_list = ip_list
        self.decoy_ip_list = decoy_ip_list
        self.seeker_level = seeker_level
        self.current_ip = self.rng.choice(self.ip_list + self.decoy_ip_list)

        # 0=unknown, 1=found, 2=exploited
        self.ip_knowledge = {ip: 0 for ip in self.ip_list + self.decoy_ip_list}
        self.current_exposure_steps = 0

        self.scan_effort, self.attack_bias, self.ip_change_prob = self._get_seeker_params(seeker_level)
        self.seeker_params = (self.scan_effort, self.attack_bias)

        # episode counters
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
        if level == 0:  # Naive
            return 0.5, 0.5, 0.05
        elif level == 1:  # Scanner
            return 2.0, 0.8, 0.02
        elif level == 2:  # Stealth
            return 0.8, 0.2, 0.01
        elif level == 3:  # ARL dummy
            return 1.0, 0.5, 0.03
        else:
            return 1.0, 0.5, 0.05

    def _update_ip_knowledge(self, ip, status_code):
        if status_code > self.ip_knowledge.get(ip, 0):
            self.ip_knowledge[ip] = status_code

    def _get_seeker_scan_prob(self):
        factor = SEEKER_PROB_PARAMS["SCAN_PROB_FACTOR"]
        min_p = SEEKER_PROB_PARAMS["SCAN_PROB_MIN"]
        max_p = SEEKER_PROB_PARAMS["SCAN_PROB_MAX"]
        return float(np.clip(factor * self.scan_effort, min_p, max_p))

    def _get_seeker_find_prob(self):
        if self.ip_knowledge.get(self.current_ip, 0) < 1:
            exp_factor = SEEKER_PROB_PARAMS["FIND_EXP_FACTOR"]
            p_find = 1.0 - math.exp(-exp_factor * self.current_exposure_steps)
            return float(np.clip(p_find, 0.0, 1.0))
        return 1.0

    def _get_exploit_block_prob(self, blacklist_level):
        is_loud = self.rng.random() < self.attack_bias
        if is_loud:
            slope = SEEKER_PROB_PARAMS["EXPLOIT_BLOCK_LOUD_SLOPE"]
            shift = SEEKER_PROB_PARAMS["EXPLOIT_BLOCK_LOUD_SHIFT"]
        else:
            slope = SEEKER_PROB_PARAMS["EXPLOIT_BLOCK_STEALTH_SLOPE"]
            shift = SEEKER_PROB_PARAMS["EXPLOIT_BLOCK_STEALTH_SHIFT"]
        p_block = expit(slope * blacklist_level + shift)
        return float(p_block), is_loud

    def _get_breach_block_prob(self, blacklist_level):
        slope = SEEKER_PROB_PARAMS["BREACH_BLOCK_SLOPE"]
        shift = SEEKER_PROB_PARAMS["BREACH_BLOCK_SHIFT"]
        return float(expit(slope * blacklist_level + shift))

    def step(self, blacklist_level, is_mtd_shuffle):
        """
        한 스텝 동안의 공격/정찰/침투 진행.
        반환 dict는 NetworkEnv에서 reward/metric 계산에 사용.
        """
        self.current_exposure_steps += 1

        # MTD 셔플이면 IP/노출 초기화
        if is_mtd_shuffle:
            self.current_exposure_steps = 1
            self.ip_knowledge[self.current_ip] = 0
            self.current_ip = self.rng.choice(self.ip_list + self.decoy_ip_list)

        # Seeker 자체 IP 변경
        if (not is_mtd_shuffle) and (self.rng.random() < self.ip_change_prob):
            self.current_ip = self.rng.choice(self.ip_list + self.decoy_ip_list)
            self.current_exposure_steps = 1
            self._update_ip_knowledge(self.current_ip, 0)

        # flag 초기화
        is_attack = False
        is_exploit = False
        is_breach = False
        is_breach_attempt = False
        is_find = False
        is_exploit_block = False
        is_exploit_success = False
        is_breach_block = False
        is_breach_success = False
        exposure_at_found = 0
        exposure_at_exploit_block = 0
        exposure_at_breach_success = 0
        is_loud = False

        is_decoy = self.current_ip in self.decoy_ip_list

        # 현재 knowledge에 따라 행동 단계 결정
        knowledge = self.ip_knowledge.get(self.current_ip, 0)
        if knowledge < 1:
            action_type = "Scan"
        elif knowledge == 1:
            action_type = "Exploit"
            is_exploit = True
        else:
            action_type = "Breach"
            is_breach = True

        if action_type == "Scan":
            self.scan_attempts += 1
            if self.rng.random() < self._get_seeker_scan_prob():
                if self.rng.random() < self._get_seeker_find_prob():
                    is_find = True
                    self.find_events += 1
                    self._update_ip_knowledge(self.current_ip, 1)
                    exposure_at_found = self.current_exposure_steps

        else:
            is_attack = True

            # Exploit 단계
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

            # Breach 단계 (Exploit 성공 이후 or 기존 exploited)
            if is_breach or (is_exploit_success and self.rng.random() < SEEKER_PROB_PARAMS["BREACH_ATTEMPT_PROB"]):
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

            if is_decoy and (is_exploit or is_breach_attempt):
                self.decoy_lures += 1

        return {
            "is_scan": action_type == "Scan",
            "is_find": is_find,
            "is_exploit_attempt": is_exploit,
            "is_exploit_block": is_exploit_block,
            "is_exploit_success": is_exploit_success,
            "is_breach_attempt": is_breach_attempt,
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
        known_count = sum(1 for s in self.ip_knowledge.values() if s >= 1)
        exploited_count = sum(1 for s in self.ip_knowledge.values() if s == 2)
        return _safe_divide(known_count, total_ips), _safe_divide(exploited_count, total_ips)

    def get_current_exposure(self):
        return self.current_exposure_steps

    def get_seeker_params(self):
        return self.seeker_params


# -------------------------
# Gym Environment
# -------------------------
class NetworkEnv(gym.Env):
    metadata = {"render_modes": ["human"], "render_fps": 4}

    # 외부에서 클래스 속성으로 덮어쓸 수 있게
    max_episode_steps = 1000

    def __init__(self, seed=None, seeker_level=2, log_dir=None):
        super().__init__()

        self.rng = np.random.default_rng(seed)
        self.seeker_level = seeker_level
        self.ip_list = [f"192.168.1.{i}" for i in range(1, NUM_TARGET_ENDPOINTS + 1)]
        self.decoy_ip_list = [f"10.0.0.{i}" for i in range(1, NUM_DECOY_ENDPOINTS + 1)]

        # 클래스 속성으로부터 가져옴 (train 코드에서 NetworkEnv.max_episode_steps 세팅)
        self.max_episode_steps = getattr(NetworkEnv, "max_episode_steps", 1000)
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

        # episode counters
        self._reset_counters()

    # ---- 내부 카운터 리셋 ----
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

    # ---- Gym reset ----
    def reset(self, seed=None, options=None):
        if seed is not None:
            self.rng = np.random.default_rng(seed)
            super().reset(seed=seed)

        self.cti = SimulatedPassiveCTI(self.rng)
        self.blacklister = SimulatedBlacklister(self.rng)
        self.seeker = SimulatedHeuristicSeeker(
            self.rng, self.seeker_level, self.ip_list, self.decoy_ip_list
        )

        self.current_step = 0
        self._reset_counters()

        self.last_actions = {key: 0.5 for key in ACTION_PARAM_KEYS}

        obs = self._get_state()
        info = self._get_current_metrics()
        info["last_action"] = self.last_actions
        return obs, info

    # ---- MTD 전략 적용 ----
    def _apply_mtd_strategy(self, action):
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

    # ---- Gym step ----
    def step(self, action):
        self.current_step += 1
        self.ep_total_steps += 1
        terminated = self.current_step >= self.max_episode_steps
        truncated = False

        # 1) Defender MTD
        mtd_results = self._apply_mtd_strategy(action)
        is_shuffle = mtd_results["is_shuffle"]
        bl_level = mtd_results["bl_level"]

        # 2) Seeker
        seeker_outcomes = self.seeker.step(bl_level, is_shuffle)
        current_ip = seeker_outcomes["seeker_ip"]
        self.endpoint_visits[current_ip] += 1

        # 3) CTI & Blacklister
        is_suspicious = seeker_outcomes["is_scan"] or seeker_outcomes["is_exploit_attempt"]
        cti_score, is_alert = self.cti.process_traffic(is_suspicious)
        if is_alert:
            self.blacklister.apply_block(current_ip, cti_score)
        self.blacklister.step()

        # 4) episode counter/시간 지표
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
                self.tte_exploit_block_accum.append(
                    seeker_outcomes["exposure_at_exploit_block"]
                )
        if seeker_outcomes["is_exploit_success"]:
            self.ep_exploit_success += 1

        if seeker_outcomes["is_breach_attempt"]:
            self.ep_breach_attempts += 1
        if seeker_outcomes["is_breach_block"]:
            self.ep_breach_block += 1
        if seeker_outcomes["is_breach_success"]:
            self.ep_breach_success += 1
            if seeker_outcomes["exposure_at_breach_success"] > 0:
                self.tte_breach_success_accum.append(
                    seeker_outcomes["exposure_at_breach_success"]
                )

        if seeker_outcomes["is_decoy_hit"]:
            self.ep_decoy_hits += 1

        is_downtime = is_shuffle
        if not is_downtime:
            self.ep_uptime_steps += 1

        # 5) Reward
        reward = self._calculate_reward(mtd_results, seeker_outcomes)

        # 6) Next state + metrics
        obs = self._get_state()
        metrics_info = self._get_current_metrics()

        info = metrics_info
        info.update(
            {
                "cost": mtd_results["cost"],
                "is_shuffle": is_shuffle,
                "Params/bl_level": bl_level,
                "Params/decoy_ratio": mtd_results["decoy_ratio"],
                "Params/shuffle_intensity": self.last_actions["shuffle_intensity"],
            }
        )

        if seeker_outcomes["is_breach_success"]:
            terminated = True

        return obs, reward, terminated, truncated, info

    # ---- Reward ----
    def _calculate_reward(self, mtd_results, seeker_outcomes):
        cost = mtd_results["cost"]

        exploit_block = 1.0 if seeker_outcomes["is_exploit_block"] else 0.0
        decoy_hit = 1.0 if seeker_outcomes["is_decoy_hit"] else 0.0
        exploit_success = 1.0 if seeker_outcomes["is_exploit_success"] else 0.0
        breach_block = 1.0 if seeker_outcomes["is_breach_block"] else 0.0
        breach_success = 1.0 if seeker_outcomes["is_breach_success"] else 0.0
        find = 1.0 if seeker_outcomes["is_find"] else 0.0

        r_def = (
            +1.0 * exploit_block
            + 1.0 * decoy_hit
            - 2.0 * exploit_success
            + 2.0 * breach_block
            - 5.0 * breach_success
            - 0.1 * find
            - COST_WEIGHT * cost
        )
        return r_def

    # ---- Observation ----
    def _get_state(self):
        breach_rate = _safe_divide(self.ep_breach_success, self.ep_breach_attempts)
        decoy_lure_rate = _safe_divide(self.ep_decoy_hits, self.ep_exploit_attempts)

        known_ratio, exploited_ratio = self.seeker.get_knowledge_ratios()
        scan_effort, attack_bias = self.seeker.get_seeker_params()

        metrics = {
            "cti_alert_rate": self.cti.get_alert_rate(),
            "blacklist_size_ratio": self.blacklister.get_size_ratio(),
            "uptime_ratio": _safe_divide(self.ep_uptime_steps, self.ep_total_steps)
            if self.ep_total_steps > 0
            else 1.0,
            "breach_success_rate": breach_rate,
            "decoy_lure_rate": decoy_lure_rate,
            "current_exposure_mean": float(self.seeker.get_current_exposure()),
            "r_known_ratio": known_ratio,
            "r_exploited_ratio": exploited_ratio,
            "seeker_scan_effort": scan_effort,
            "seeker_attack_bias": attack_bias,
        }

        state_vec = [metrics.get(k, 0.0) for k in FEATURE_KEYS[:10]]
        state_vec.extend([self.last_actions.get(k, 0.5) for k in ACTION_PARAM_KEYS])
        return np.array(state_vec, dtype=np.float32)

    # ---- Episode-level metrics (Metrics dict) ----
    def _get_current_metrics(self):
        """
        Metrics 구조:
        info["Metrics"] = {
            "Defense": {...},
            "Attack": {...},
            "Time": {...},
            "DRS": {...},
            # 그리고 평평한 키들도 함께 넣어둠 (호환용)
            "Defense/R_succ": ...,
            ...
        }
        """
        info = {}

        # 1) Core
        breach_attempts = self.ep_breach_attempts
        breach_success = self.ep_breach_success

        r_succ = 1.0 - _safe_divide(breach_success, breach_attempts)
        c_def = _safe_divide(self.ep_total_cost, self.ep_total_steps)
        total_blocks = self.ep_exploit_block + self.ep_breach_block + self.ep_decoy_hits
        cost_per_block = _safe_divide(self.ep_total_cost, total_blocks)

        decoy_lure_rate = _safe_divide(self.ep_decoy_hits, self.ep_exploit_attempts)
        s_mtd_overall = 0.5 * decoy_lure_rate + 0.5 * r_succ - 0.1 * c_def

        # 2) Multi-step ratios
        r_exploit_success = _safe_divide(self.ep_exploit_success, self.ep_exploit_attempts)
        r_exploit_block = _safe_divide(self.ep_exploit_block, self.ep_exploit_attempts)
        r_breach_success = _safe_divide(breach_success, breach_attempts)
        r_breach_block = _safe_divide(self.ep_breach_block, breach_attempts)
        r_scan = _safe_divide(self.ep_scan_attempts, self.ep_total_steps)
        r_find = _safe_divide(self.ep_find_events, self.ep_scan_attempts)

        # 3) Time-to-Event
        ttf_mean = float(np.mean(self.tte_find_accum)) if self.tte_find_accum else 0.0
        tteb_mean = float(np.mean(self.tte_exploit_block_accum)) if self.tte_exploit_block_accum else 0.0
        ttbr_mean = float(np.mean(self.tte_breach_success_accum)) if self.tte_breach_success_accum else 0.0

        # 4) DRS
        d_bits = self._calculate_diversity()
        s_shuffle = self._calculate_shuffle_score()
        redundancy = NUM_TARGET_ENDPOINTS  # 간이 지표

        defense_dict = {
            "R_succ": r_succ,
            "C_def": c_def,
            "CostPerBlock": cost_per_block,
            "S_MTD_overall": s_mtd_overall,
        }
        attack_dict = {
            "r_exploit_success": r_exploit_success,
            "r_exploit_block": r_exploit_block,
            "r_breach_success": r_breach_success,
            "r_breach_block": r_breach_block,
            "r_scan": r_scan,
            "r_find": r_find,
            "decoy_lure_rate": decoy_lure_rate,
        }
        time_dict = {
            "TTF_mean": ttf_mean,
            "TTEB_mean": tteb_mean,
            "TTBr_mean": ttbr_mean,
        }
        drs_dict = {
            "D_bits": d_bits,
            "R_redundancy": redundancy,
            "S_shuffle": s_shuffle,
        }

        flat = {}
        for k, v in defense_dict.items():
            flat[f"Defense/{k}"] = v
        for k, v in attack_dict.items():
            flat[f"Attack/{k}"] = v
        for k, v in time_dict.items():
            flat[f"Time/{k}"] = v
        for k, v in drs_dict.items():
            flat[f"DRS/{k}"] = v

        info["Metrics"] = {
            **flat,
            "Defense": defense_dict,
            "Attack": attack_dict,
            "Time": time_dict,
            "DRS": drs_dict,
        }
        return info

    def _calculate_diversity(self):
        visit_counts = np.array(list(self.endpoint_visits.values()), dtype=np.float32)
        total = float(np.sum(visit_counts))
        if total <= 0:
            return 0.0
        p = visit_counts / total
        p = p[p > 0]
        return float(-np.sum(p * np.log2(p)))

    def _calculate_shuffle_score(self):
        freq = _safe_divide(self.ep_shuffle_count, self.ep_total_steps)
        return float(freq * math.log2(NUM_TOTAL_ENDPOINTS))
