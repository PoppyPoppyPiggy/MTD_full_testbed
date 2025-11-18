import gym
from gym import spaces
import numpy as np
import random
import logging
from collections import deque
from scipy.special import expit, logit # sigmoid and logit
import math
from .rl_config_v05 import (
    FEATURE_KEYS, ACTION_PARAM_KEYS, SIM_TIME_PER_STEP_SEC,
    NUM_TARGET_ENDPOINTS, NUM_DECOY_ENDPOINTS, NUM_TOTAL_ENDPOINTS,
    SEEKER_PROB_PARAMS, COST_MTD_ACTION, COST_SHUFFLE, COST_DECOY, COST_BL, COST_WEIGHT
)

# Set up logging
logger = logging.getLogger(__name__)

# --- Utility Functions ---
def _scale_action(action, lower_bound=0.0, upper_bound=1.0):
    """Rescales an action from [-1, 1] (tanh output) to [lower_bound, upper_bound]."""
    return lower_bound + (0.5 * (action + 1.0) * (upper_bound - lower_bound))

def _safe_divide(numerator, denominator):
    """Divides safely, returning 0 if the denominator is zero."""
    return numerator / denominator if denominator != 0 else 0.0

# --- Simulated Components (Simplified for brevity, focusing on the core logic changes) ---

class SimulatedPassiveCTI:
    """Simulates a passive CTI agent providing a raw alert rate metric."""
    def __init__(self, rng, window_size=100, detection_threshold=0.5):
        self.rng = rng
        # Note: Actual CTI threshold should be tuned to match real-world detection rate
        self.detection_threshold = detection_threshold 
        self.alert_history = deque([0] * window_size, maxlen=window_size)

    def process_traffic(self, is_suspicious):
        """Generates a CTI score and updates alert status."""
        # Score distribution: Suspicious traffic is more likely to score high
        if is_suspicious:
            score = self.rng.normal(loc=0.8, scale=0.1)
        else:
            score = self.rng.normal(loc=0.1, scale=0.1)
        
        score = np.clip(score, 0.0, 1.0)
        
        is_alert = score >= self.detection_threshold
        self.alert_history.append(1 if is_alert else 0)
        
        return score, is_alert

    def get_alert_rate(self):
        """Calculates the rolling alert rate."""
        return sum(self.alert_history) / self.alert_history.maxlen

class SimulatedBlacklister:
    """Simulates the blacklisting policy effect (BL)."""
    def __init__(self, rng):
        self.rng = rng
        self.blacklist_policy = {
            "aggression": 0.0,  # 0 to 1
            "duration": 0.0,    # 0 to 1
        }
        self.blocked_ips = {} # {ip: remaining_steps}

    def update_policy(self, aggression_param, duration_param):
        """Maps RL action parameters (0-1) to internal policy parameters."""
        from .rl_config_v05 import BLACKLIST_SENSITIVITY_MIN, BLACKLIST_SENSITIVITY_MAX, BLACKLIST_DURATION_MIN_STEPS, BLACKLIST_DURATION_MAX_STEPS
        
        # Aggression maps to CTI sensitivity/threshold
        sensitivity = aggression_param * (BLACKLIST_SENSITIVITY_MAX - BLACKLIST_SENSITIVITY_MIN) + BLACKLIST_SENSITIVITY_MIN
        # Duration maps to block time in steps
        duration_steps = int(duration_param * (BLACKLIST_DURATION_MAX_STEPS - BLACKLIST_DURATION_MIN_STEPS) + BLACKLIST_DURATION_MIN_STEPS)

        self.blacklist_policy.update({
            "aggression": sensitivity,
            "duration": duration_steps,
        })
        return self.blacklist_policy

    def apply_block(self, ip, cti_score):
        """Applies a block if CTI score is above the dynamic aggression threshold."""
        if cti_score >= self.blacklist_policy["aggression"]:
            self.blocked_ips[ip] = self.blacklist_policy["duration"]
            return True
        return False

    def step(self):
        """Decrements duration of all active blocks and clears expired ones."""
        expired_ips = [ip for ip, duration in self.blocked_ips.items() if duration <= 1]
        for ip in expired_ips:
            del self.blocked_ips[ip]
        
        for ip in list(self.blocked_ips.keys()): # Use list() for safe iteration during modification
            self.blocked_ips[ip] -= 1

    def is_blocked(self, ip):
        """Checks if a given IP is currently blocked."""
        return ip in self.blocked_ips

    def get_size_ratio(self):
        """Returns current blacklist size normalized by total endpoints (approximation)."""
        return min(1.0, len(self.blocked_ips) / NUM_TOTAL_ENDPOINTS)
        
    def get_current_level(self):
        """Returns the current Blacklist Level (aggression proxy) for cost calculation."""
        return self.blacklist_policy['aggression']

class SimulatedHeuristicSeeker:
    """
    Simulates the multi-stage attack process (Scan -> Find -> Exploit -> Breach).
    Seeker is not an RL agent itself, but follows heuristic probability model.
    """
    def __init__(self, rng, seeker_level, ip_list, decoy_ip_list):
        self.rng = rng
        self.ip_list = ip_list
        self.decoy_ip_list = decoy_ip_list
        self.seeker_level = seeker_level
        self.current_ip = self.rng.choice(self.ip_list + self.decoy_ip_list)
        
        # Internal Seeker state for LPC (Low-level Persistent Cache)
        # 0=unknown, 1=found, 2=exploited
        self.ip_knowledge = {ip: 0 for ip in self.ip_list + self.decoy_ip_list} 
        self.current_exposure_steps = 0 # Steps since last IP change/shuffle
        
        # Attack Parameters based on Level (L0-L2 fixed, L3 uses adaptive parameters)
        self.scan_effort, self.attack_bias, self.ip_change_prob = self._get_seeker_params(seeker_level)
        self.seeker_params = (self.scan_effort, self.attack_bias) # For feature logging

        # Counters for metrics (resets per episode)
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
        """Sets fixed parameters for seeker levels L0-L2. L3 uses a fixed value for simplicity here."""
        if level == 0:  # Naive
            return 0.5, 0.5, 0.05
        elif level == 1: # Scanner (High scan, Loud bias)
            return 2.0, 0.8, 0.02
        elif level == 2: # Stealthy (Low scan, Stealth bias)
            return 0.8, 0.2, 0.01
        elif level == 3: # ARL (Adaptive - simulated via hardcoded medium)
            return 1.0, 0.5, 0.03 
        else: # Default/Custom
            return 1.0, 0.5, 0.05

    def _update_ip_knowledge(self, ip, status_code):
        """Updates knowledge of an IP (1=Found, 2=Exploited)."""
        if status_code > self.ip_knowledge.get(ip, 0):
            self.ip_knowledge[ip] = status_code

    def _get_seeker_scan_prob(self):
        """Calculates scan probability based on effort and clamping. p_scan = clamp(0.4*scan_effort, 0.05, 0.95)"""
        factor = SEEKER_PROB_PARAMS["SCAN_PROB_FACTOR"]
        min_p = SEEKER_PROB_PARAMS["SCAN_PROB_MIN"]
        max_p = SEEKER_PROB_PARAMS["SCAN_PROB_MAX"]
        return np.clip(factor * self.scan_effort, min_p, max_p)

    def _get_seeker_find_prob(self):
        """Calculates find probability based on accumulated exposure time. p_find = 1 - exp(-0.05 * exposure_steps)"""
        if self.ip_knowledge.get(self.current_ip, 0) < 1:
            exp_factor = SEEKER_PROB_PARAMS["FIND_EXP_FACTOR"]
            p_find = 1.0 - math.exp(-exp_factor * self.current_exposure_steps)
            return np.clip(p_find, 0.0, 1.0)
        return 1.0 # Already found/exploited

    def _get_exploit_block_prob(self, blacklist_level):
        """
        Calculates exploit block probability based on BL level and attack type.
        Loud: sigmoid(0.9*BL - 0.5), Stealth: sigmoid(0.2*BL - 1.5)
        """
        is_loud = self.rng.random() < self.attack_bias # High bias -> Loud
        
        if is_loud:
            slope = SEEKER_PROB_PARAMS["EXPLOIT_BLOCK_LOUD_SLOPE"]
            shift = SEEKER_PROB_PARAMS["EXPLOIT_BLOCK_LOUD_SHIFT"]
        else: # Stealth
            slope = SEEKER_PROB_PARAMS["EXPLOIT_BLOCK_STEALTH_SLOPE"]
            shift = SEEKER_PROB_PARAMS["EXPLOIT_BLOCK_STEALTH_SHIFT"]
            
        p_block = expit(slope * blacklist_level + shift)
        return p_block, is_loud

    def _get_breach_block_prob(self, blacklist_level):
        """Calculates breach block probability based on BL level. sigmoid(0.3*BL - 1.0)"""
        slope = SEEKER_PROB_PARAMS["BREACH_BLOCK_SLOPE"]
        shift = SEEKER_PROB_PARAMS["BREACH_BLOCK_SHIFT"]
        return expit(slope * blacklist_level + shift)

    def step(self, blacklist_level, is_mtd_shuffle):
        """
        Executes one seeker turn (Scan/Attack/IP Change) and determines outcomes.
        Returns a dictionary of outcomes for environment reward calculation.
        """
        
        # --- 1. MTD/Time Update ---
        self.current_exposure_steps += 1
        
        # If MTD shuffle occurred
        if is_mtd_shuffle:
            self.current_exposure_steps = 1 # Reset exposure time (new IP)
            # Seeker loses knowledge of the current IP and moves to a random one
            self.ip_knowledge[self.current_ip] = 0
            self.current_ip = self.rng.choice(self.ip_list + self.decoy_ip_list) 
            
        # Determine if IP change occurs (Independent of Scan/Attack)
        did_ip_change = self.rng.random() < self.ip_change_prob and not is_mtd_shuffle # MTD shuffle overrides
        if did_ip_change:
            self.current_ip = self.rng.choice(self.ip_list + self.decoy_ip_list)
            self.current_exposure_steps = 1 
            self._update_ip_knowledge(self.current_ip, 0)
            
        # --- 2. Attack Stage Simulation ---
        
        # Reset current step flags
        is_attack, is_exploit, is_breach = False, False, False
        is_find, is_exploit_block, is_breach_block = False, False, False
        is_exploit_success, is_breach_success = False, False
        is_decoy = self.current_ip in self.decoy_ip_list
        exposure_at_found = 0
        exposure_at_exploit_block = 0
        exposure_at_breach_success = 0
        is_loud = False # Flag for exploit type

        
        # Determine Seeker action (Scan vs Attack)
        if self.ip_knowledge.get(self.current_ip, 0) < 1: # Unknown -> Scan
            action_type = "Scan"
        elif self.ip_knowledge.get(self.current_ip, 0) == 1: # Found -> Exploit Attempt
            action_type = "Attack"
            is_exploit = True
        elif self.ip_knowledge.get(self.current_ip, 0) == 2: # Exploited -> Breach Attempt
            action_type = "Attack"
            is_breach = True
        else:
            action_type = "None"
            
        if action_type == "Scan":
            self.scan_attempts += 1
            # Check for Find (Probabilistic and depends on accumulated exposure)
            if self.rng.random() < self._get_seeker_scan_prob():
                if self.rng.random() < self._get_seeker_find_prob():
                    is_find = True
                    self.find_events += 1
                    self._update_ip_knowledge(self.current_ip, 1) # Found
                    exposure_at_found = self.current_exposure_steps
                
        elif action_type == "Attack":
            is_attack = True
            
            if is_exploit:
                self.exploit_attempts += 1
                
                # Exploit Block Check
                p_block, is_loud = self._get_exploit_block_prob(blacklist_level)
                is_exploit_block = self.rng.random() < p_block
                
                if is_exploit_block:
                    self.exploit_block += 1
                    exposure_at_exploit_block = self.current_exposure_steps
                else:
                    # Exploit Success Check (if not blocked)
                    p_success = SEEKER_PROB_PARAMS["EXPLOIT_SUCCESS_LOUD"] if is_loud else SEEKER_PROB_PARAMS["EXPLOIT_SUCCESS_STEALTH"]
                    
                    if self.rng.random() < p_success:
                        is_exploit_success = True
                        self.exploit_success += 1
                        self._update_ip_knowledge(self.current_ip, 2) # Exploited
                    
            if is_breach or (is_exploit_success and self.rng.random() < SEEKER_PROB_PARAMS["BREACH_ATTEMPT_PROB"]):
                # Breach Attempt (either starting from exploited state or immediately after exploit success)
                is_breach_attempt = True
                self.breach_attempts += 1
                
                # Breach Block Check
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
        
            # Decoy check (Decoy counts as a lure only if an attack/exploit attempt occurred)
            if is_decoy and (is_exploit or is_breach_attempt):
                self.decoy_lures += 1
                
        
        return {
            "is_scan": action_type == "Scan",
            "is_find": is_find,
            "is_exploit_attempt": is_exploit,
            "is_exploit_block": is_exploit_block,
            "is_exploit_success": is_exploit_success,
            "is_breach_attempt": is_breach_attempt if is_attack else False,
            "is_breach_block": is_breach_block,
            "is_breach_success": is_breach_success,
            "is_decoy_hit": is_decoy and is_attack, # Attack hit a decoy
            "is_loud": is_loud,
            "exposure_at_found": exposure_at_found,
            "exposure_at_exploit_block": exposure_at_exploit_block,
            "exposure_at_breach_success": exposure_at_breach_success,
            "seeker_ip": self.current_ip,
            "seeker_knowledge": self.ip_knowledge
        }

    def get_knowledge_ratios(self):
        """Returns the ratios of known and exploited IPs."""
        total_ips = len(self.ip_list + self.decoy_ip_list)
        known_count = sum(1 for status in self.ip_knowledge.values() if status >= 1)
        exploited_count = sum(1 for status in self.ip_knowledge.values() if status == 2)
        return _safe_divide(known_count, total_ips), _safe_divide(exploited_count, total_ips)

    def get_current_exposure(self):
        return self.current_exposure_steps

    def get_seeker_params(self):
        return self.seeker_params


class NetworkEnv(gym.Env):
    """Custom Environment for MTD RL policy learning using Gym API."""
    metadata = {'render_modes': ['human'], 'render_fps': 4}

    def __init__(self, seed=None, seeker_level=2, log_dir=None):
        super(NetworkEnv, self).__init__()
        
        self.rng = np.random.default_rng(seed)
        self.seeker_level = seeker_level
        self.ip_list = [f"192.168.1.{i}" for i in range(NUM_TARGET_ENDPOINTS)]
        self.decoy_ip_list = [f"10.0.0.{i}" for i in range(NUM_DECOY_ENDPOINTS)]
        self.max_episode_steps = 1000 # Default max steps
        self.current_step = 0
        self.log_dir = log_dir

        # Initialize components (will be reset in reset())
        self.cti = None
        self.blacklister = None
        self.seeker = None

        # Define action and observation space
        self.action_space = spaces.Box(low=-1.0, high=1.0, shape=(len(ACTION_PARAM_KEYS),), dtype=np.float32)
        self.observation_space = spaces.Box(low=-100.0, high=100.0, shape=(len(FEATURE_KEYS),), dtype=np.float32) # Using float to allow normalized features

        # Episode-level counters (for end-of-episode metric calculation)
        self.ep_total_steps = 0
        self.ep_total_cost = 0
        self.ep_shuffle_count = 0
        self.ep_uptime_steps = 0
        
        # New counters for detailed metrics (resets per episode)
        self.ep_scan_attempts = 0
        self.ep_find_events = 0
        self.ep_exploit_attempts = 0
        self.ep_exploit_block = 0
        self.ep_exploit_success = 0
        self.ep_breach_attempts = 0
        self.ep_breach_block = 0
        self.ep_breach_success = 0
        self.ep_decoy_hits = 0 # Decoy lure during attack/exploit
        
        # Time-to-Event accumulators
        self.tte_find_accum = []
        self.tte_exploit_block_accum = []
        self.tte_breach_success_accum = []
        
        # Policy tracking for DRS (Diversity, Redundancy, Shuffle)
        self.endpoint_visits = {ip: 0 for ip in self.ip_list + self.decoy_ip_list}
        self.policy_history = [] # Stores (dnat_focus, decoy_ratio, bl) for analysis

    def reset(self, seed=None, options=None):
        """Resets the environment for a new episode."""
        if seed is not None:
            self.rng = np.random.default_rng(seed)
            # Gym compatibility:
            super().reset(seed=seed)

        # Re-initialize components
        self.cti = SimulatedPassiveCTI(self.rng)
        self.blacklister = SimulatedBlacklister(self.rng)
        self.seeker = SimulatedHeuristicSeeker(self.rng, self.seeker_level, self.ip_list, self.decoy_ip_list)
        
        # Reset episode counters
        self.current_step = 0
        self.ep_total_steps = 0
        self.ep_total_cost = 0
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

        # Initial dummy action (to populate 'last_action_...' features)
        self.last_actions = {key: 0.5 for key in ACTION_PARAM_KEYS}
        
        observation = self._get_state()
        info = self._get_current_metrics() # Initial metrics also calculated
        info["last_action"] = self.last_actions
        
        return observation, info

    def _apply_mtd_strategy(self, action):
        """
        Translates RL action into MTD parameters and updates system state.
        
        Args:
            action (np.array): 6D continuous action from the RL agent.
        
        Returns:
            dict: {cost_total, bl_level, decoy_ratio, is_shuffle}
        """
        
        # Rescale actions from [-1, 1] to [0, 1]
        action_params = {
            "dnat_target_focus": _scale_action(action[0]),
            "dnat_decoy_focus": _scale_action(action[1]),
            "shuffle_intensity": _scale_action(action[2]),
            "blacklist_aggression": _scale_action(action[3]),
            "blacklist_duration": _scale_action(action[4]),
            "decoy_ratio": _scale_action(action[5]),
        }
        self.last_actions = action_params # Store for next state features

        # --- 1. Blacklisting Policy Update ---
        bl_policy = self.blacklister.update_policy(
            action_params["blacklist_aggression"],
            action_params["blacklist_duration"]
        )
        
        # --- 2. DNAT/Shuffle Logic (Simplified) ---
        is_shuffle = action_params["shuffle_intensity"] > 0.75 # High intensity triggers a shuffle
        
        if is_shuffle:
            self.ep_shuffle_count += 1
        
        # --- 3. Cost Calculation (Based on Cdef formula in Section 2.1) ---
        
        bl_level = self.blacklister.get_current_level() # Get aggression as BL level proxy
        
        # cost = COST_MTD_ACTION + COST_SHUFFLE*1_shuffle + COST_DECOY*decoy_ratio + COST_BL*BL
        cost_mtd = COST_MTD_ACTION
        cost_shuffle = COST_SHUFFLE if is_shuffle else 0.0
        cost_decoy = COST_DECOY * action_params["decoy_ratio"]
        cost_bl = COST_BL * bl_level
        
        total_cost = cost_mtd + cost_shuffle + cost_decoy + cost_bl
        self.ep_total_cost += total_cost
        
        # Track policy for overall metrics
        self.policy_history.append({
            "decoy_ratio": action_params["decoy_ratio"],
            "bl": bl_level,
            "cost": total_cost,
            "is_shuffle": is_shuffle
        })
        
        return {
            "cost": total_cost, 
            "bl_level": bl_level,
            "decoy_ratio": action_params["decoy_ratio"],
            "is_shuffle": is_shuffle,
        }

    def step(self, action):
        self.current_step += 1
        self.ep_total_steps += 1
        terminated = self.current_step >= self.max_episode_steps
        truncated = False
        
        # --- 1. Defender MTD Phase ---
        mtd_results = self._apply_mtd_strategy(action)
        is_shuffle = mtd_results["is_shuffle"]
        bl_level = mtd_results["bl_level"]
        
        # --- 2. Seeker Phase ---
        seeker_outcomes = self.seeker.step(bl_level, is_shuffle)
        current_ip = seeker_outcomes["seeker_ip"]
        self.endpoint_visits[current_ip] += 1
        
        # --- 3. CTI/Blacklister Update ---
        is_suspicious = seeker_outcomes["is_scan"] or seeker_outcomes["is_exploit_attempt"]
        cti_score, is_alert = self.cti.process_traffic(is_suspicious)
        
        # Blacklister attempts block if CTI raises alarm
        if is_alert:
            self.blacklister.apply_block(current_ip, cti_score)
        
        self.blacklister.step() # Decrement block durations
        
        # --- 4. Update Detailed Counters and Uptime ---
        
        is_breach_success = seeker_outcomes["is_breach_success"]
        
        # Update episode-level raw counts
        if seeker_outcomes["is_scan"]: self.ep_scan_attempts += 1
        if seeker_outcomes["is_find"]: 
            self.ep_find_events += 1
            if seeker_outcomes["exposure_at_found"] > 0:
                self.tte_find_accum.append(seeker_outcomes["exposure_at_found"])
                
        if seeker_outcomes["is_exploit_attempt"]: self.ep_exploit_attempts += 1
        if seeker_outcomes["is_exploit_block"]: 
            self.ep_exploit_block += 1
            if seeker_outcomes["exposure_at_exploit_block"] > 0:
                 self.tte_exploit_block_accum.append(seeker_outcomes["exposure_at_exploit_block"])
                 
        if seeker_outcomes["is_exploit_success"]: self.ep_exploit_success += 1
        
        if seeker_outcomes["is_breach_attempt"]: self.ep_breach_attempts += 1
        if seeker_outcomes["is_breach_block"]: self.ep_breach_block += 1
        if is_breach_success: 
            self.ep_breach_success += 1
            if seeker_outcomes["exposure_at_breach_success"] > 0:
                self.tte_breach_success_accum.append(seeker_outcomes["exposure_at_breach_success"])
                
        if seeker_outcomes["is_decoy_hit"]: self.ep_decoy_hits += 1
        
        # Uptime (Simplified: Shuffle causes downtime)
        is_downtime = is_shuffle 
        if not is_downtime:
            self.ep_uptime_steps += 1
        
        # --- 5. Reward Calculation ---
        reward = self._calculate_reward(mtd_results, seeker_outcomes)

        # --- 6. Next State and Info ---
        observation = self._get_state()
        
        # Get comprehensive episode metrics (DRS, TTF, etc.) and update info dict
        info = self._get_current_metrics()
        info.update({
            # Essential flags/values for PPO logging
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
            # Parameters (Action/Policy means)
            "Params/bl_level": bl_level,
            "Params/decoy_ratio": mtd_results["decoy_ratio"],
            "Params/shuffle_intensity": self.last_actions["shuffle_intensity"],
        })
        
        # Check termination condition
        if is_breach_success:
            terminated = True # Stop episode on successful breach

        return observation, reward, terminated, truncated, info

    def _calculate_reward(self, mtd_results, seeker_outcomes):
        """Calculates the Defender's reward based on the specified formula (Section 5.1)."""
        
        cost = mtd_results["cost"]

        # Indicator functions (1 or 0)
        exploit_block = 1.0 if seeker_outcomes["is_exploit_block"] else 0.0
        decoy = 1.0 if seeker_outcomes["is_decoy_hit"] else 0.0 # Decoy is counted if hit by attack
        exploit_success = 1.0 if seeker_outcomes["is_exploit_success"] else 0.0
        breach_block = 1.0 if seeker_outcomes["is_breach_block"] else 0.0
        breach_success = 1.0 if seeker_outcomes["is_breach_success"] else 0.0
        find = 1.0 if seeker_outcomes["is_find"] else 0.0 # Note: Find is penalized (-0.1)
        
        # Reward calculation:
        # r_def = (+1.0)*1_ExploitBlock + (+1.0)*1_Decoy + (-2.0)*1_ExploitSuccess + 
        #         (+2.0)*1_BreachBlock + (-5.0)*1_BreachSuccess + (-0.1)*1_Find - COST_WEIGHT*cost
        r_def = (
              (+1.0) * exploit_block
            + (+1.0) * decoy
            + (-2.0) * exploit_success
            + (+2.0) * breach_block
            + (-5.0) * breach_success
            + (-0.1) * find
            - COST_WEIGHT * cost
        )
        return r_def

    def _get_state(self):
        """Builds the 16D observation vector (Metrics + Last Actions)."""
        
        # Calculate windowed/cumulative metrics needed for the state
        current_breach_rate = _safe_divide(self.ep_breach_success, self.ep_breach_attempts)
        current_decoy_lure_rate = _safe_divide(self.ep_decoy_hits, self.ep_exploit_attempts)
        
        metrics = {
            "cti_alert_rate": self.cti.get_alert_rate(),
            "blacklist_size_ratio": self.blacklister.get_size_ratio(),
            "uptime_ratio": _safe_divide(self.ep_uptime_steps, self.ep_total_steps) if self.ep_total_steps > 0 else 1.0,
            "breach_success_rate": current_breach_rate,
            "decoy_lure_rate": current_decoy_lure_rate,
            "current_exposure_mean": self.seeker.get_current_exposure(),
            "r_known_ratio": self.seeker.get_knowledge_ratios()[0],
            "r_exploited_ratio": self.seeker.get_knowledge_ratios()[1],
            "seeker_scan_effort": self.seeker.get_seeker_params()[0],
            "seeker_attack_bias": self.seeker.get_seeker_params()[1],
        }
        
        # Construct the state vector (10 metrics + 6 last actions)
        state_vector = [metrics.get(key, 0.0) for key in FEATURE_KEYS[:10]]
        state_vector.extend([self.last_actions.get(key, 0.5) for key in ACTION_PARAM_KEYS])
        
        return np.array(state_vector, dtype=np.float32)

    def _get_current_metrics(self):
        """
        Calculates and returns all derived metrics (for logging, not for state).
        This includes the final DRS, Time-to-Event metrics, and Success Rates.
        """
        info = {}
        
        # Recalculate based on episode-wide counters (can use self.ep_* directly)
        
        # R_succ (Breach Stop Rate) = 1 - (#BreachSuccess / #BreachAttempts)
        breach_attempts = self.ep_breach_attempts
        breach_success = self.ep_breach_success
        r_succ = 1.0 - _safe_divide(breach_success, breach_attempts)
        
        # C_def (Avg. Defense Cost per Step)
        c_def = _safe_divide(self.ep_total_cost, self.ep_total_steps)
        
        # CostPerBlock (Total Cost / Total Blocks)
        total_blocks = self.ep_exploit_block + self.ep_breach_block + self.ep_decoy_hits
        cost_per_block = _safe_divide(self.ep_total_cost, total_blocks)
        
        # S_MTD (Composite Score)
        decoy_lure_rate = _safe_divide(self.ep_decoy_hits, self.ep_exploit_attempts)
        s_mtd_overall = (0.5 * decoy_lure_rate) + (0.5 * r_succ) - (0.1 * c_def)
        
        # Metric Dictionaries (for logging structure in rl_train_v05.py)
        info["Metrics"] = {
            # --- 1. Core Defense Metrics ---
            "Defense/R_succ": r_succ,
            "Defense/C_def": c_def,
            "Defense/CostPerBlock": cost_per_block,
            "Defense/S_MTD_overall": s_mtd_overall,
            
            # --- 2. Multi-stage Success/Block Ratios ---
            "Attack/r_exploit_success": _safe_divide(self.ep_exploit_success, self.ep_exploit_attempts),
            "Attack/r_exploit_block": _safe_divide(self.ep_exploit_block, self.ep_exploit_attempts),
            "Attack/r_breach_success": _safe_divide(breach_success, breach_attempts),
            "Attack/r_breach_block": _safe_divide(self.ep_breach_block, breach_attempts),
            "Attack/r_scan": _safe_divide(self.ep_scan_attempts, self.ep_total_steps),
            "Attack/r_find": _safe_divide(self.ep_find_events, self.ep_scan_attempts),
            "Attack/decoy_lure_rate": decoy_lure_rate,

            # --- 3. Time-to-Event (TTF/TTEB/TTBr) ---
            "Time/TTF_mean": np.mean(self.tte_find_accum) if self.tte_find_accum else 0.0,
            "Time/TTEB_mean": np.mean(self.tte_exploit_block_accum) if self.tte_exploit_block_accum else 0.0,
            "Time/TTBr_mean": np.mean(self.tte_breach_success_accum) if self.tte_breach_success_accum else 0.0,
            
            # --- 4. DRS Metrics ---
            # D_bits (Diversity): Entropy of endpoint visitation (simulated)
            "DRS/D_bits": self._calculate_diversity(),
            # R (Redundancy): Simplified to target endpoints count
            "DRS/R_redundancy": NUM_TARGET_ENDPOINTS, 
            # S (Shuffle): Normalized Shuffle Frequency
            "DRS/S_shuffle": self._calculate_shuffle_score(),
        }
        
        return info

    def _calculate_diversity(self):
        """Calculates Entropy of endpoint visitation D_bits = -sum(p_i * log2(p_i))."""
        visit_counts = np.array(list(self.endpoint_visits.values()))
        total_visits = np.sum(visit_counts)
        if total_visits > 0:
            probabilities = visit_counts / total_visits
            # Filter out zero probabilities for log calculation
            probabilities = probabilities[probabilities > 0]
            d_bits = -np.sum(probabilities * np.log2(probabilities))
            return d_bits
        return 0.0

    def _calculate_shuffle_score(self):
        """Calculates Normalized Shuffle Frequency S = (#shuffle / total_steps) * log2(#endpoints)."""
        shuffle_freq = _safe_divide(self.ep_shuffle_count, self.ep_total_steps)
        s_shuffle = shuffle_freq * math.log2(NUM_TOTAL_ENDPOINTS)
        return s_shuffle