import gym
from gym import spaces
import numpy as np
import random
import logging
import json
import os
import subprocess
import time
from collections import deque

# [FIX] Correctly import module-level constants from rl_config_v05
from .rl_config_v05 import (
    RL_CONFIG,
    FEATURE_KEYS,
    ACTION_PARAM_KEYS,
    SEEKER_PROB_PARAMS,
    COST_MTD_ACTION,
    COST_SHUFFLE,
    COST_DECOY,
    COST_BL,
    COST_WEIGHT,
    REWARD_ATTACK_BLOCKED,
    REWARD_ATTACK_SUCCESS,
    REWARD_MTD_COST,
    REWARD_NORMAL,
    MTD_STATE_PATH,
    BASE_DIR
)

logger = logging.getLogger("RLEnv")

# -------------------------
# Utils
# -------------------------
def _scale_action(action, lower_bound=0.0, upper_bound=1.0):
    return lower_bound + (0.5 * (action + 1.0) * (upper_bound - lower_bound))

def _safe_divide(numerator, denominator):
    return numerator / denominator if denominator != 0 else 0.0

# -------------------------
# Endpoint Class
# -------------------------
class Endpoint:
    def __init__(self, ip, name="Unknown", is_decoy=False):
        self.ip = ip
        self.name = name
        self.is_decoy = is_decoy
        self.open_ports = [14550, 5760, 554] # Default ports
        self.scan_progress = 0.0
        self.exploit_progress = 0.0
        self.breach_progress = 0.0
        self.state = 0

    def reset_progress(self):
        self.scan_progress = 0.0
        self.exploit_progress = 0.0
        self.breach_progress = 0.0
        self.state = 0

# -------------------------
# Simulated Components (Hybrid Mode)
# -------------------------
class HybridCTI:
    """CTI Agent combining real mtd_state.json data and simulation"""
    def __init__(self, rng):
        self.rng = rng
        self.alert_history = deque([0] * 100, maxlen=100)

    def get_real_state(self):
        """Reads real attack information from mtd_state.json"""
        if os.path.exists(MTD_STATE_PATH):
            try:
                with open(MTD_STATE_PATH, 'r') as f:
                    data = json.load(f)
                    # e.g., {"attack_detected": true, "risk_score": 0.8}
                    return data
            except Exception:
                pass
        return {}

    def process_traffic(self, is_suspicious_sim):
        # 1. Check Real State
        real_state = self.get_real_state()
        real_alert = real_state.get("attack_detected", False)
        real_score = real_state.get("risk_score", 0.0)

        # 2. Simulated Value (Fallback)
        if is_suspicious_sim:
            sim_score = self.rng.normal(loc=0.8, scale=0.1)
        else:
            sim_score = self.rng.normal(loc=0.1, scale=0.1)
        
        # 3. Merge (Real detection takes priority)
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
        return self.blacklist_policy

    def apply_block(self, ip, cti_score):
        if cti_score >= self.blacklist_policy["aggression"]:
            self.blocked_ips[ip] = self.blacklist_policy["duration"]
            return True
        return False

    def step(self):
        for ip in list(self.blocked_ips.keys()):
            self.blocked_ips[ip] -= 1
            if self.blocked_ips[ip] <= 0:
                del self.blocked_ips[ip]

    def get_size_ratio(self, total):
        return min(1.0, len(self.blocked_ips) / max(1, total))
    
    def get_current_level(self):
        return self.blacklist_policy["aggression"]

class SimulatedHeuristicSeeker:
    def __init__(self, rng, level, endpoints):
        self.rng = rng
        self.endpoints = endpoints
        self.current_target = self.rng.choice(endpoints)
        self.attack_speed = 0.1 + (level * 0.05)
        
        # Stats
        self.ep_breach_success = 0
        self.ep_breach_attempts = 0
        self.ep_breach_block = 0
        self.ep_exploit_attempts = 0
        self.ep_exploit_success = 0
        self.ep_exploit_block = 0
        self.ep_decoy_hits = 0
        
        self.seeker_params = (0.5, 0.5) # scan_effort, bias

    def get_knowledge_ratios(self):
        return 0.5, 0.2 # Dummy for now

    def step(self, bl_level, is_mtd_shuffle):
        # Shuffle -> Reset Progress
        if is_mtd_shuffle:
            for ep in self.endpoints:
                ep.reset_progress()
            self.current_target = self.rng.choice(self.endpoints)

        t = self.current_target
        
        # Simple Attack Logic Simulation
        is_breach_success = False
        is_exploit_success = False
        is_decoy_hit = False
        
        # Progress update
        t.exploit_progress += self.attack_speed
        if t.exploit_progress >= 1.0:
            self.ep_exploit_attempts += 1
            if self.rng.random() > bl_level:
                is_exploit_success = True
                self.ep_exploit_success += 1
                t.breach_progress += self.attack_speed
            else:
                self.ep_exploit_block += 1
                t.exploit_progress = 0.5

        if t.breach_progress >= 1.0:
            self.ep_breach_attempts += 1
            if self.rng.random() > bl_level:
                is_breach_success = True
                self.ep_breach_success += 1
                t.state = 3 # Breached
            else:
                self.ep_breach_block += 1
                t.breach_progress = 0.5

        if t.is_decoy and (t.exploit_progress > 0.5):
            is_decoy_hit = True
            self.ep_decoy_hits += 1

        return {
            "seeker_ip": t.ip,
            "is_scan": True,
            "is_exploit_attempt": t.exploit_progress >= 1.0,
            "is_exploit_success": is_exploit_success,
            "is_exploit_block": not is_exploit_success and t.exploit_progress >= 1.0,
            "is_breach_attempt": t.breach_progress >= 1.0,
            "is_breach_success": is_breach_success,
            "is_breach_block": not is_breach_success and t.breach_progress >= 1.0,
            "is_decoy_hit": is_decoy_hit
        }

# -------------------------
# MTD Environment (Main)
# -------------------------
class MTDEnvironment(gym.Env):
    metadata = {"render_modes": ["human"], "render_fps": 4}
    max_episode_steps = 200

    def __init__(self, seed=None, seeker_level=2, log_dir=None):
        super().__init__()
        self.rng = np.random.default_rng(seed)
        self.seeker_level = seeker_level
        self.current_step = 0
        self.log_dir = log_dir

        self.endpoints = self._load_endpoints_from_config()
        
        # Decoy IP Pool (for swapping)
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
        config_path = os.path.join(RL_CONFIG.BASE_DIR, "config", "attacker_config.json")
        try:
            with open(config_path, "r") as f:
                config = json.load(f)
                for name, ip in config.get("targets", {}).items():
                    is_decoy = "DECOY" in name.upper()
                    endpoints.append(Endpoint(ip, name, is_decoy))
        except Exception:
            # Fallback
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
        self.cti = HybridCTI(self.rng) # Reset CTI history
        
        return self._get_state(), self._get_current_metrics()

    def _execute_ip_swap(self):
        """
        Modifies real network settings.
        Selects one target IP and changes its DNAT mapping to one of the decoy IPs.
        """
        if not self.target_ips or not self.decoy_ips:
            return

        # 1. Select target for swap (Random)
        target_ip = self.rng.choice(self.target_ips)
        new_dest_ip = self.rng.choice(self.decoy_ips)
        port = 14550 # MAVLink Port (Example)

        script_path = os.path.join(RL_CONFIG.BASE_DIR, "scripts", "ip_port_swap.sh")
        
        # 2. Execute shell script (iptables control)
        # [FIX] Call via /bin/bash explicitly to avoid exec format error
        try:
            os.chmod(script_path, 0o755)
            cmd = ["/bin/bash", script_path, "tcp", str(port), new_dest_ip, str(port)]
            
            # Actual execution (Root permission required inside Docker)
            subprocess.run(cmd, check=True, capture_output=True)
            # logger.info(f"[MTD Real Action] Swapped {target_ip}:{port} -> {new_dest_ip}:{port}")
            
        except Exception as e:
            # Log less verbosely or handle specific errors
            # logger.error(f"Failed to execute IP swap script: {e}")
            pass

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
        
        self.blacklister.update_policy(params["blacklist_aggression"], params["blacklist_duration"])

        # Shuffle Threshold Check & Execute
        is_shuffle = params["shuffle_intensity"] > 0.6
        if is_shuffle:
            self.ep_shuffle_count += 1
            self._execute_ip_swap() # <--- Execute Real Swap

        cost = COST_MTD_ACTION + (COST_SHUFFLE if is_shuffle else 0) + \
               (COST_DECOY * params["decoy_ratio"]) + \
               (COST_BL * self.blacklister.get_current_level())
        
        self.ep_total_cost += cost
        return {"cost": cost, "is_shuffle": is_shuffle, "bl_level": self.blacklister.get_current_level(), "decoy_ratio": params["decoy_ratio"]}

    def step(self, action):
        self.current_step += 1
        self.ep_total_steps += 1
        terminated = self.current_step >= self.max_episode_steps
        truncated = False

        # 1. Defender Action
        mtd_res = self._apply_mtd_strategy(action)

        # 2. Seeker Step (Simulated)
        seeker_out = self.seeker.step(mtd_res["bl_level"], mtd_res["is_shuffle"])

        # 3. CTI Update (Real + Sim)
        cti_score, is_alert = self.cti.process_traffic(seeker_out["is_scan"])
        if is_alert:
            self.blacklister.apply_block(seeker_out["seeker_ip"], cti_score)
        self.blacklister.step()

        # 4. Update Counters
        if seeker_out["is_breach_attempt"]: self.ep_breach_attempts += 1
        if seeker_out["is_breach_success"]: self.ep_breach_success += 1
        if seeker_out["is_breach_block"]: self.ep_breach_block += 1
        if seeker_out["is_decoy_hit"]: self.ep_decoy_hits += 1
        if seeker_out["is_exploit_attempt"]: self.ep_exploit_attempts += 1
        if not mtd_res["is_shuffle"]: self.ep_uptime_steps += 1

        # 5. Reward Calculation
        reward = self._calculate_reward(mtd_res, seeker_out)

        # 6. Info & Obs
        obs = self._get_state()
        info = self._get_current_metrics()
        info.update({
            "cost": mtd_res["cost"],
            "is_shuffle": mtd_res["is_shuffle"],
            "applied_mtd": mtd_res["is_shuffle"],
            "raw_reward": reward,
            "Params/bl_level": mtd_res["bl_level"],
            "Params/decoy_ratio": mtd_res["decoy_ratio"],
            "Params/shuffle_intensity": self.last_actions["shuffle_intensity"]
        })

        return obs, reward, terminated, truncated, info

    def _calculate_reward(self, mtd_res, seeker_out):
        reward = 0.0
        
        # Check Attack State (mtd_state.json takes priority)
        real_state = self.cti.get_real_state()
        is_real_attack = real_state.get("attack_detected", False)
        
        # Attack Situation
        if is_real_attack or seeker_out["is_breach_success"]:
            reward += REWARD_ATTACK_SUCCESS # -50.0
        elif seeker_out["is_exploit_success"]:
            reward += (REWARD_ATTACK_SUCCESS * 0.2) # -10.0
        
        # Defense Situation
        if seeker_out["is_breach_block"]:
            reward += REWARD_ATTACK_BLOCKED # +20.0
        elif seeker_out["is_exploit_block"]:
            reward += (REWARD_ATTACK_BLOCKED * 0.5) # +10.0

        # MTD Effect
        if seeker_out["is_decoy_hit"]:
            reward += 5.0
        
        # Cost
        reward -= (mtd_res["cost"] * COST_WEIGHT)
        
        # Normal State Reward
        if not is_real_attack and not seeker_out["is_breach_attempt"] and not mtd_res["is_shuffle"]:
            reward += REWARD_NORMAL

        return float(reward)

    def _get_state(self):
        # Feature Construction
        breach_rate = _safe_divide(self.ep_breach_success, max(1, self.ep_breach_attempts))
        decoy_rate = _safe_divide(self.ep_decoy_hits, max(1, self.ep_exploit_attempts))
        
        metrics = {
            "cti_alert_rate": self.cti.get_alert_rate(),
            "blacklist_size_ratio": self.blacklister.get_size_ratio(len(self.endpoints)),
            "uptime_ratio": _safe_divide(self.ep_uptime_steps, self.ep_total_steps),
            "breach_success_rate": breach_rate,
            "decoy_lure_rate": decoy_rate,
            "current_exposure_mean": 0.5, # Simplified
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
        s_mtd = (0.5 * r_succ) + (0.3 * decoy_rate) - (0.2 * c_def)

        return {
            "Defense/R_succ": r_succ,
            "Defense/S_MTD_overall": s_mtd,
            "Defense/C_def": c_def,
            "Attack/decoy_lure_rate": decoy_rate,
            "Metrics": {"Defense": {"R_succ": r_succ}, "Attack": {"decoy_lure_rate": decoy_rate}}
        }