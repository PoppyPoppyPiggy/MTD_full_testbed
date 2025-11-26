"""
Reinforcement learning environment for Moving Target Defence (MTD) training.

This v06 version refines the behaviour of the environment to better
incorporate the effects of defensive actions on the attacker and to
encourage meaningful exploration by the RL agent.  When a shuffle is
triggered the environment now resets the progress of all endpoints,
forcing the attacker to rescan.  Decoy activation influences the
attacker via the seeker agent, and blacklist aggression can cause
proactive blocking.  Costs and rewards are configured via
rl_config_v06.py to provide stronger incentives for blocking attacks
and less punishment for experimenting with MTD actions.
"""

import gym
from gym import spaces
import numpy as np
import random
import logging
import json
import os
from collections import deque

from .rl_config_v06 import (
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
    """Scale an action value in [-1,1] to [lower_bound, upper_bound]."""
    return lower_bound + (0.5 * (action + 1.0) * (upper_bound - lower_bound))


def _safe_divide(numerator, denominator):
    """Safely divide two numbers, returning 0 if the denominator is zero."""
    return numerator / denominator if denominator != 0 else 0.0


# -------------------------
# Simulated Components
# -------------------------
class HybridCTI:
    """
    Hybrid CTI agent that combines simulated anomaly scores with
    observations of the real MTD state.  If mtd_state.json exists and
    indicates an attack, that state is prioritised over simulated
    scores.  Otherwise a Gaussian noise around either 0.8 (suspicious)
    or 0.1 (normal) is used to produce a CTI score.
    """
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
        """
        Produce a CTI score and alert flag.  If the real MTD state indicates
        an attack, return that score; otherwise generate a simulated score.
        """
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
        """Return the rolling average of alerts over the last 100 timesteps."""
        return sum(self.alert_history) / self.alert_history.maxlen if self.alert_history else 0.0


class SimulatedBlacklister:
    """
    Simulated blacklist controller that adds IPs to a blocklist for a
    duration determined by the RL policy.  The aggression parameter
    controls the threshold at which CTI scores trigger blocks.
    """
    def __init__(self, rng):
        self.rng = rng
        self.blacklist_policy = {"aggression": 0.0, "duration": 0}
        self.blocked_ips = {}

    def update_policy(self, aggression, duration):
        self.blacklist_policy["aggression"] = float(np.clip(aggression, 0.0, 1.0))
        # duration is scaled to milliseconds later; store raw float for now
        self.blacklist_policy["duration"] = float(np.clip(duration, 0.0, 1.0))

    def apply_block(self, ip, cti_score):
        """
        Attempt to block an IP based on the CTI score.  The threshold
        decreases as aggression increases, making it easier to block
        suspicious IPs.  The block duration is scaled by the RL action.
        """
        # more aggressive means a lower threshold: aggression 1.0 -> threshold 0.2
        threshold = 1.0 - (self.blacklist_policy["aggression"] * 0.8)
        if cti_score >= threshold:
            # duration scale: map 0..1 to min..max steps
            duration_steps = int(
                RL_CONFIG.BLACKLIST_DURATION_MIN_STEPS +
                self.blacklist_policy["duration"] * (RL_CONFIG.BLACKLIST_DURATION_MAX_STEPS - RL_CONFIG.BLACKLIST_DURATION_MIN_STEPS)
            )
            self.blocked_ips[ip] = max(RL_CONFIG.BLACKLIST_DURATION_MIN_STEPS, duration_steps)
            return True
        return False

    def is_blocked(self, ip):
        return ip in self.blocked_ips

    def step(self):
        """Decrement timers and remove expired entries from the blocklist."""
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
    """
    Reinforcement learning environment for training an MTD policy.  This
    environment exposes a continuous action space of six parameters
    controlling how aggressively the system will shuffle IP/ports,
    redirect traffic to decoys, and blacklist IPs.  The observation
    returned to the agent includes threat metrics from a CTI module,
    current defence statistics, and the last chosen action parameters.
    """
    metadata = {"render_modes": ["human"], "render_fps": 4}
    max_episode_steps = 200

    def __init__(self, seed=None, seeker_level=2, log_dir=None,
                 seeker_profiles_path: str | None = None):
        super().__init__()
        self.rng = np.random.default_rng(seed)
        self.seeker_level = seeker_level
        self.current_step = 0
        self.seeker_profiles_path = seeker_profiles_path  # NEW

        # Load endpoints from attacker_config.json or fall back to defaults
        self.endpoints = self._load_endpoints_from_config()
        self.decoy_ips = [ep.ip for ep in self.endpoints if ep.is_decoy]
        self.target_ips = [ep.ip for ep in self.endpoints if not ep.is_decoy]

        # Components
        self.cti = HybridCTI(self.rng)
        self.blacklister = SimulatedBlacklister(self.rng)
        # 여기서 seeker_level + profiles_path 전달
        self.seeker = SimulatedHeuristicSeeker(
            self.rng, seeker_level, self.endpoints, profiles_path=self.seeker_profiles_path
        )

        # Action and observation spaces ...
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
            # fallback dummy endpoints
            for i in range(RL_CONFIG.NUM_TARGET_ENDPOINTS):
                endpoints.append(Endpoint(f"10.13.0.{10+i}", f"Target_{i}", False))
            for i in range(RL_CONFIG.NUM_DECOY_ENDPOINTS):
                endpoints.append(Endpoint(f"10.13.0.{20+i}", f"Decoy_{i}", True))
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
        
        for ep in self.endpoints:
            ep.reset_progress()
        self.current_step = 0
        self._reset_counters()
        self.cti = HybridCTI(self.rng)
        self.blacklister = SimulatedBlacklister(self.rng)
        # 현재 self.seeker_level 값으로 새 seeker 재생성
        self.seeker = SimulatedHeuristicSeeker(
            self.rng, self.seeker_level, self.endpoints, profiles_path=self.seeker_profiles_path
        )
        return self._get_state(), self._get_current_metrics()

    def _apply_mtd_strategy(self, action):
        """
        Interpret the agent's continuous action vector and determine the
        corresponding defensive behaviours.  Returns a dictionary with
        flags and cost details used later for reward calculation and
        logging.
        """
        # Scale each action dimension from [-1,1] to [0,1]
        params = {
            "dnat_target_focus": _scale_action(action[0]),
            "dnat_decoy_focus": _scale_action(action[1]),
            "shuffle_intensity": _scale_action(action[2]),
            "blacklist_aggression": _scale_action(action[3]),
            "blacklist_duration": _scale_action(action[4]),
            "decoy_ratio": _scale_action(action[5]),
        }
        # Store last actions for state representation
        self.last_actions = params

        # Update blacklister policy with raw aggression/duration values
        self.blacklister.update_policy(params["blacklist_aggression"], params["blacklist_duration"])

        # Determine whether shuffle/decoy actions should be active
        is_shuffle = params["shuffle_intensity"] >= ACT_THRESHOLDS["SHUFFLE"]
        is_decoy_active = params["decoy_ratio"] >= ACT_THRESHOLDS["DECOY_ACTIVE"]

        # On shuffle, reset progress of all endpoints to simulate the attacker
        # losing track of services (requires rescan).  This creates an
        # explicit cost (by way of time delay) for the attacker.
        if is_shuffle:
            self.ep_shuffle_count += 1
            for ep in self.endpoints:
                ep.reset_progress()
            # Optionally update a shared mtd_state.json with new port mappings
            # This is left as a no-op in the simulation for simplicity.

        # Compute action cost
        cost = COST_MTD_ACTION
        if is_shuffle:
            cost += COST_SHUFFLE * params["shuffle_intensity"]
        if is_decoy_active:
            cost += COST_DECOY * params["decoy_ratio"]
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
        """
        Execute one environment step with the given RL action.  Returns
        (observation, reward, terminated, truncated, info).
        """
        self.current_step += 1
        self.ep_total_steps += 1
        terminated = self.current_step >= self.max_episode_steps
        truncated = False

        # 1. Apply defender (agent) action
        mtd_res = self._apply_mtd_strategy(action)

        # 2. Get the seeker (attacker) intent given current defence status
        seeker_status = {
            "is_shuffle": mtd_res["is_shuffle"],
            "is_decoy_active": mtd_res["is_decoy_active"],
            "decoy_ratio": mtd_res["decoy_ratio"],
        }
        seeker_intent = self.seeker.step(seeker_status)

        # 3. Determine outcome of the seeker's action
        # Evaluate if the IP is currently blocked
        is_blocked = self.blacklister.is_blocked(seeker_intent["seeker_ip"])
        outcome = "continue"
        is_exploit_success = False
        is_breach_success = False
        is_decoy_hit = False

        if seeker_intent["target_ep"]:
            # (A) Decoy hit: attacker targeted a decoy during an exploit attempt
            if seeker_intent["target_ep"].is_decoy and seeker_intent["is_exploit_attempt"]:
                is_decoy_hit = True
                outcome = "decoy_hit"
            # (B) If the IP is blocked, then the attack attempt fails
            elif is_blocked:
                outcome = "blocked"
            # (C) If an exploit attempt, decide whether it succeeds based on blacklist aggression
            elif seeker_intent["is_exploit_attempt"]:
                # Aggressive blacklist means higher chance of block
                block_prob = mtd_res["params"]["blacklist_aggression"] * 0.6
                if self.rng.random() > block_prob:
                    outcome = "exploit_success"
                    is_exploit_success = True
                else:
                    outcome = "blocked"
            # (D) If a breach attempt, treat similarly but with a higher block probability
            elif seeker_intent["is_breach_attempt"]:
                block_prob = mtd_res["params"]["blacklist_aggression"] * 0.8
                if self.rng.random() > block_prob:
                    outcome = "breach_success"
                    is_breach_success = True
                else:
                    outcome = "blocked"

        # 4. Provide feedback to seeker so it can update its internal state
        self.seeker.handle_outcome(outcome)

        # 5. Update CTI and blacklist using the CTI score.  If CTI
        # indicates suspicious behaviour or RL aggression is high,
        # attempt to block the IP proactively.
        cti_score, is_alert = self.cti.process_traffic(seeker_intent["is_scan"])
        if is_alert:
            self.blacklister.apply_block(seeker_intent["seeker_ip"], cti_score)
        # Proactive block based on RL aggression even if CTI didn't alert
        elif mtd_res["params"]["blacklist_aggression"] >= ACT_THRESHOLDS["BL_ACTIVE"]:
            self.blacklister.apply_block(seeker_intent["seeker_ip"], mtd_res["params"]["blacklist_aggression"])
        self.blacklister.step()

        # 6. Update counters for metrics
        if seeker_intent["is_exploit_attempt"]:
            self.ep_exploit_attempts += 1
        if seeker_intent.get("is_breach_attempt", False):
            self.ep_breach_attempts += 1
        if is_breach_success:
            self.ep_breach_success += 1
        if is_decoy_hit:
            self.ep_decoy_hits += 1

        is_exploit_block = (outcome == "blocked" and seeker_intent["is_exploit_attempt"])
        is_breach_block = (outcome == "blocked" and seeker_intent.get("is_breach_attempt", False))
        if is_breach_block:
            self.ep_breach_block += 1
        # uptime_steps counts timesteps where the system did not shuffle
        if not mtd_res["is_shuffle"]:
            self.ep_uptime_steps += 1

        # 7. Calculate reward
        reward_info = {
            "is_exploit_success": is_exploit_success,
            "is_breach_success": is_breach_success,
            "is_exploit_block": is_exploit_block,
            "is_breach_block": is_breach_block,
            "is_decoy_hit": is_decoy_hit,
            "is_shuffle": mtd_res["is_shuffle"],
            "is_breach_attempt": seeker_intent.get("is_breach_attempt", False),
        }
        reward = self._calculate_reward(mtd_res, reward_info)

        # 8. Build observation and info
        obs = self._get_state()
        info = self._get_current_metrics()
        info.update({
            "cost": mtd_res["cost"],
            "raw_reward": reward,
            "applied_mtd": mtd_res["is_shuffle"],
        })
        for k, v in mtd_res["params"].items():
            info[f"Params/{k}"] = v

        return obs, reward, terminated, truncated, info

    def _calculate_reward(self, mtd_res, r_info):
        """
        Compute the reward for the current step based on the outcome of
        attacks and the cost of defence actions.  Rewards are structured
        to heavily penalise successful breaches and to reward blocking
        attacks while keeping the cost of defences in check.
        """
        reward = 0.0
        # Attack outcomes: large negative when breach succeeds, moderate
        # negative when exploit succeeds but breach fails
        if r_info["is_breach_success"]:
            reward += REWARD_ATTACK_SUCCESS
        elif r_info["is_exploit_success"]:
            reward += (REWARD_ATTACK_SUCCESS * 0.3)
        # Defence outcomes: positive reward for blocking exploit or breach
        if r_info["is_breach_block"]:
            reward += REWARD_ATTACK_BLOCKED
        elif r_info["is_exploit_block"]:
            reward += (REWARD_ATTACK_BLOCKED * 0.4)
        # Decoy lure reward: encourage sending attacker to decoys
        if r_info["is_decoy_hit"]:
            reward += 10.0
        # Cost penalty: scaled by COST_WEIGHT
        reward -= (mtd_res["cost"] * COST_WEIGHT)
        # Normal state reward: if no successful exploit or breach, small bonus
        if not r_info["is_breach_success"] and not r_info["is_exploit_success"]:
            reward += REWARD_NORMAL
        return float(reward)

    def _get_state(self):
        """Construct the observation vector for the RL agent."""
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
        """
        Return high-level metrics for logging and evaluation.

        In addition to counting how many breach attempts were blocked, we
        consider decoy hits as successful defensive outcomes.  A decoy
        hit means the attacker spent effort on a honeypot rather than
        the real service.  The defence success rate therefore
        includes both blocked breaches and decoy hits divided by the
        total number of breach attempts plus decoy hits.  The combined
        MTD score balances defence success, decoy usage and defence cost.
        """
        # Total successful defensive events (breach blocks + decoy hits)
        successes = self.ep_breach_block + self.ep_decoy_hits
        # Total opportunities (breach attempts + decoy hits).  Use 1 to avoid div zero
        total_attempts = max(1, self.ep_breach_attempts + self.ep_decoy_hits)
        r_succ = _safe_divide(successes, total_attempts)
        # Average defence cost per step
        c_def = _safe_divide(self.ep_total_cost, max(1, self.ep_total_steps))
        # Decoy lure rate (decoy hits per exploit attempt)
        decoy_rate = _safe_divide(self.ep_decoy_hits, max(1, self.ep_exploit_attempts))
        # Combined MTD score: emphasise success and decoy usage, penalise cost
        s_mtd = (0.5 * r_succ) + (0.3 * decoy_rate) - (0.1 * c_def)
        return {
            "Defense/R_succ": r_succ,
            "Defense/S_MTD_overall": s_mtd,
            "Metrics": {
                "Defense": {"R_succ": r_succ},
                "Attack": {"decoy_lure_rate": decoy_rate},
            },
        }