import gym
from gym import spaces
import numpy as np
import random
import logging
import json
import os
from collections import deque

from .rl_config_v05 import (
    RL_CONFIG,
    FEATURE_KEYS,
    ACTION_PARAM_KEYS,
    ACT_THRESHOLDS,
    COST_MTD_ACTION,
    COST_SHUFFLE,
    COST_DECOY,
    COST_BL,
    COST_WEIGHT,
    REWARD_ATTACK_BLOCKED,
    REWARD_ATTACK_SUCCESS,
    REWARD_MTD_COST,
    REWARD_NORMAL,
    MTD_STATE_PATH
)
from .seeker_agent import Endpoint, SimulatedHeuristicSeeker

logger = logging.getLogger("RLEnv")

# -------------------------
# Utils
# -------------------------
def _scale_action(action, lower_bound=0.0, upper_bound=1.0):
    return lower_bound + (0.5 * (action + 1.0) * (upper_bound - lower_bound))

def _safe_divide(numerator, denominator):
    return numerator / denominator if denominator != 0 else 0.0

# -------------------------
# Simulated Components
# -------------------------
class HybridCTI:
    def __init__(self, rng):
        self.rng = rng
        self.alert_history = deque([0] * 100, maxlen=100)

    def get_real_state(self):
        if os.path.exists(MTD_STATE_PATH):
            try:
                with open(MTD_STATE_PATH, 'r') as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def process_traffic(self, is_suspicious_sim):
        real_state = self.get_real_state()
        real_alert = real_state.get("attack_detected", False)
        real_score = real_state.get("risk_score", 0.0)

        if is_suspicious_sim:
            sim_score = self.rng.normal(loc=0.8, scale=0.1)
        else:
            sim_score = self.rng.normal(loc=0.1, scale=0.1)
        
        if real_alert:
            final_score = max(real_score, sim_score)
            is_alert = True
        else:
            final_score = float(np.clip(sim_score, 0.0, 1.0))
            is_alert = final_score >= 0.5

        self.alert_history.append(1 if is_alert else 0)
        return final_score, is_alert

    def get_alert_rate(self):
        if not self.alert_history: return 0.0
        return sum(self.alert_history) / self.alert_history.maxlen

class SimulatedBlacklister:
    def __init__(self, rng):
        self.rng = rng
        self.blacklist_policy = {"aggression": 0.0, "duration": 0}
        self.blocked_ips = {}

    def update_policy(self, aggression, duration):
        self.blacklist_policy["aggression"] = float(np.clip(aggression, 0.0, 1.0))
        self.blacklist_policy["duration"] = int(duration * 1000)

    def apply_block(self, ip, cti_score):
        # Threshold decreases as aggression increases
        threshold = 1.0 - (self.blacklist_policy["aggression"] * 0.8) # Max aggression -> 0.2 threshold
        if cti_score >= threshold:
            self.blocked_ips[ip] = max(10, self.blacklist_policy["duration"])
            return True
        return False

    def is_blocked(self, ip):
        return ip in self.blocked_ips

    def step(self):
        for ip in list(self.blocked_ips.keys()):
            self.blocked_ips[ip] -= 1
            if self.blocked_ips[ip] <= 0:
                del self.blocked_ips[ip]

    def get_size_ratio(self, total):
        return min(1.0, len(self.blocked_ips) / max(1, total))

# -------------------------
# MTD Environment
# -------------------------
class MTDEnvironment(gym.Env):
    metadata = {"render_modes": ["human"], "render_fps": 4}
    max_episode_steps = 200

    def __init__(self, seed=None, seeker_level=2, log_dir=None):
        super().__init__()
        self.rng = np.random.default_rng(seed)
        self.seeker_level = seeker_level
        self.current_step = 0

        self.endpoints = self._load_endpoints_from_config()
        self.decoy_ips = [ep.ip for ep in self.endpoints if ep.is_decoy]
        self.target_ips = [ep.ip for ep in self.endpoints if not ep.is_decoy]

        self.cti = HybridCTI(self.rng)
        self.blacklister = SimulatedBlacklister(self.rng)
        self.seeker = SimulatedHeuristicSeeker(self.rng, seeker_level, self.endpoints)

        self.action_space = spaces.Box(low=-1.0, high=1.0, shape=(len(ACTION_PARAM_KEYS),), dtype=np.float32)
        self.observation_space = spaces.Box(low=-100.0, high=100.0, shape=(len(FEATURE_KEYS),), dtype=np.float32)

        self._reset_counters()

    def _load_endpoints_from_config(self):
        endpoints = []
        try:
            config_path = os.path.join(RL_CONFIG.BASE_DIR, "config", "attacker_config.json")
            if os.path.exists(config_path):
                with open(config_path, "r") as f:
                    config = json.load(f)
                    for name, ip in config.get("targets", {}).items():
                        is_decoy = "DECOY" in name.upper()
                        endpoints.append(Endpoint(ip, name, is_decoy))
        except Exception:
            pass
        
        if not endpoints:
            for i in range(5): endpoints.append(Endpoint(f"10.13.0.{10+i}", f"Target_{i}", False))
            for i in range(2): endpoints.append(Endpoint(f"10.13.0.{20+i}", f"Decoy_{i}", True))
        return endpoints

    def _reset_counters(self):
        self.ep_total_steps = 0
        self.ep_total_cost = 0.0
        self.ep_shuffle_count = 0
        self.ep_uptime_steps = 0
        self.ep_breach_success = 0
        self.ep_breach_attempts = 0
        self.ep_breach_block = 0
        self.ep_decoy_hits = 0
        self.ep_exploit_attempts = 0
        self.last_actions = {key: 0.5 for key in ACTION_PARAM_KEYS}

    def reset(self, seed=None, options=None):
        if seed is not None:
            self.rng = np.random.default_rng(seed)
            super().reset(seed=seed)
        
        for ep in self.endpoints: ep.reset_progress()
        self.current_step = 0
        self._reset_counters()
        self.cti = HybridCTI(self.rng)
        self.blacklister = SimulatedBlacklister(self.rng)
        self.seeker = SimulatedHeuristicSeeker(self.rng, self.seeker_level, self.endpoints)
        
        return self._get_state(), self._get_current_metrics()

    def _apply_mtd_strategy(self, action):
        params = {
            "dnat_target_focus": _scale_action(action[0]),
            "dnat_decoy_focus": _scale_action(action[1]),
            "shuffle_intensity": _scale_action(action[2]),
            "blacklist_aggression": _scale_action(action[3]),
            "blacklist_duration": _scale_action(action[4]),
            "decoy_ratio": _scale_action(action[5]),
        }
        self.last_actions = params
        
        # 1. Update Blacklist Policy
        self.blacklister.update_policy(params["blacklist_aggression"], params["blacklist_duration"])

        # 2. Determine Active Defenses
        is_shuffle = params["shuffle_intensity"] >= ACT_THRESHOLDS["SHUFFLE"]
        is_decoy_active = params["decoy_ratio"] >= ACT_THRESHOLDS["DECOY_ACTIVE"]
        
        if is_shuffle:
            self.ep_shuffle_count += 1

        # Cost Calculation
        cost = COST_MTD_ACTION
        if is_shuffle: cost += COST_SHUFFLE * params["shuffle_intensity"]
        if is_decoy_active: cost += COST_DECOY * params["decoy_ratio"]
        # Blacklist cost proportional to aggression (risk of false positives)
        cost += COST_BL * params["blacklist_aggression"]
        
        self.ep_total_cost += cost
        
        return {
            "cost": cost,
            "is_shuffle": is_shuffle,
            "is_decoy_active": is_decoy_active,
            "decoy_ratio": params["decoy_ratio"],
            "params": params
        }

    def step(self, action):
        self.current_step += 1
        self.ep_total_steps += 1
        terminated = self.current_step >= self.max_episode_steps
        truncated = False

        # 1. Defender Action
        mtd_res = self._apply_mtd_strategy(action)

        # 2. Seeker Step
        # Pass defense status to Seeker
        seeker_status = {
            "is_shuffle": mtd_res["is_shuffle"],
            "is_decoy_active": mtd_res["is_decoy_active"],
            "decoy_ratio": mtd_res["decoy_ratio"]
        }
        seeker_intent = self.seeker.step(seeker_status)
        
        # 3. Environment Logic (Outcome Determination)
        is_blocked = self.blacklister.is_blocked(seeker_intent["seeker_ip"])
        
        outcome = "continue"
        is_exploit_success = False
        is_breach_success = False
        is_decoy_hit = False
        
        if seeker_intent["target_ep"]:
            # Check Decoy Hit
            if seeker_intent["target_ep"].is_decoy and seeker_intent["is_exploit_attempt"]:
                is_decoy_hit = True
                outcome = "decoy_hit"
            
            # Check Blocking
            elif is_blocked:
                outcome = "blocked"
            
            # Attack Resolution
            elif seeker_intent["is_exploit_attempt"]:
                # Probability of block by policy even if not explicitly in list yet
                block_prob = mtd_res["params"]["blacklist_aggression"] * 0.5
                if self.rng.random() > block_prob:
                    outcome = "exploit_success"
                    is_exploit_success = True
                else:
                    outcome = "blocked"
            
            elif seeker_intent["is_breach_attempt"]:
                block_prob = mtd_res["params"]["blacklist_aggression"] * 0.7
                if self.rng.random() > block_prob:
                    outcome = "breach_success"
                    is_breach_success = True
                else:
                    outcome = "blocked"
        
        # Feedback to Seeker
        self.seeker.handle_outcome(outcome)

        # 4. CTI & Blacklist Update
        cti_score, is_alert = self.cti.process_traffic(seeker_intent["is_scan"])
        if is_alert:
            self.blacklister.apply_block(seeker_intent["seeker_ip"], cti_score)
        self.blacklister.step()

        # 5. Update Counters
        if seeker_intent["is_exploit_attempt"]: self.ep_exploit_attempts += 1
        if seeker_intent["is_breach_attempt"]: self.ep_breach_attempts += 1
        if is_breach_success: self.ep_breach_success += 1
        if is_decoy_hit: self.ep_decoy_hits += 1
        
        is_exploit_block = (outcome == "blocked" and seeker_intent["is_exploit_attempt"])
        is_breach_block = (outcome == "blocked" and seeker_intent["is_breach_attempt"])
        
        if is_breach_block: self.ep_breach_block += 1
        
        if not mtd_res["is_shuffle"]: self.ep_uptime_steps += 1

        # 6. Reward & Info
        reward_info = {
            "is_exploit_success": is_exploit_success,
            "is_breach_success": is_breach_success,
            "is_exploit_block": is_exploit_block,
            "is_breach_block": is_breach_block,
            "is_decoy_hit": is_decoy_hit,
            "is_shuffle": mtd_res["is_shuffle"],
            "is_breach_attempt": seeker_intent.get("is_breach_attempt", False)
        }
        
        reward = self._calculate_reward(mtd_res, reward_info)

        obs = self._get_state()
        info = self._get_current_metrics()
        info.update({
            "cost": mtd_res["cost"],
            "raw_reward": reward,
            "applied_mtd": mtd_res["is_shuffle"]
        })
        
        for k, v in mtd_res["params"].items():
            info[f"Params/{k}"] = v

        return obs, reward, terminated, truncated, info

    def _calculate_reward(self, mtd_res, r_info):
        reward = 0.0
        
        # 1. Attack Outcomes (Big Penalties)
        if r_info["is_breach_success"]: 
            reward += REWARD_ATTACK_SUCCESS # -100
        elif r_info["is_exploit_success"]: 
            reward += (REWARD_ATTACK_SUCCESS * 0.3) # -30
        
        # 2. Defense Outcomes (Big Rewards)
        if r_info["is_breach_block"]: 
            reward += REWARD_ATTACK_BLOCKED # +50
        elif r_info["is_exploit_block"]: 
            reward += (REWARD_ATTACK_BLOCKED * 0.4) # +20

        if r_info["is_decoy_hit"]: 
            reward += 10.0 # Decoy bonus
        
        # 3. Cost Penalty (Reduced weight)
        reward -= (mtd_res["cost"] * COST_WEIGHT)
        
        # 4. Normal State (Bonus for surviving without breach)
        if not r_info["is_breach_success"] and not r_info["is_exploit_success"]:
            reward += REWARD_NORMAL

        return float(reward)

    def _get_state(self):
        breach_rate = _safe_divide(self.ep_breach_success, max(1, self.ep_breach_attempts))
        decoy_rate = _safe_divide(self.ep_decoy_hits, max(1, self.ep_exploit_attempts))
        
        metrics = {
            "cti_alert_rate": self.cti.get_alert_rate(),
            "blacklist_size_ratio": self.blacklister.get_size_ratio(len(self.endpoints)),
            "uptime_ratio": _safe_divide(self.ep_uptime_steps, self.ep_total_steps),
            "breach_success_rate": breach_rate,
            "decoy_lure_rate": decoy_rate,
            "current_exposure_mean": 0.5, 
            "r_known_ratio": 0.5,
            "r_exploited_ratio": 0.5,
            "seeker_scan_effort": self.seeker.seeker_params[0],
            "seeker_attack_bias": self.seeker.seeker_params[1],
        }
        
        state_vec = [metrics.get(k, 0.0) for k in FEATURE_KEYS[:10]]
        state_vec.extend([self.last_actions.get(k, 0.5) for k in ACTION_PARAM_KEYS])
        return np.array(state_vec, dtype=np.float32)

    def _get_current_metrics(self):
        r_succ = _safe_divide(self.ep_breach_block, self.ep_breach_attempts) if self.ep_breach_attempts > 0 else 0.0
        c_def = _safe_divide(self.ep_total_cost, max(1, self.ep_total_steps))
        decoy_rate = _safe_divide(self.ep_decoy_hits, max(1, self.ep_exploit_attempts))
        
        # Improved S_MTD formula
        s_mtd = (0.5 * r_succ) + (0.3 * decoy_rate) - (0.1 * c_def)
        
        return {
            "Defense/R_succ": r_succ, 
            "Defense/S_MTD_overall": s_mtd,
            "Metrics": {"Defense": {"R_succ": r_succ}, "Attack": {"decoy_lure_rate": decoy_rate}}
        }