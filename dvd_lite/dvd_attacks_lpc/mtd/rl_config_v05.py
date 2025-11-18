# Configuration for the MTD Reinforcement Learning Agent and Environment (v06: Refined Metrics & Reward)
import numpy as np
import math

# --- ENVIRONMENT CONSTANTS AND PARAMETERS ---

# Time constants
SIM_TIME_PER_STEP_SEC = 1.0  # Time represented by a single simulation step (1 second)

# Network Endpoints Configuration (Used for Diversity/Shuffle metrics)
NUM_TARGET_ENDPOINTS = 5
NUM_DECOY_ENDPOINTS = 2
NUM_TOTAL_ENDPOINTS = NUM_TARGET_ENDPOINTS + NUM_DECOY_ENDPOINTS

# Seeker Attack Model Parameters (based on user specification)
SEEKER_PROB_PARAMS = {
    # Scan probability clamping
    "SCAN_PROB_FACTOR": 0.4,
    "SCAN_PROB_MIN": 0.05,
    "SCAN_PROB_MAX": 0.95,
    # Find probability exponential decay factor
    "FIND_EXP_FACTOR": 0.05,
    # Exploit/Breach block success sigmoid parameters (BL = blacklist level [0, 1])
    "EXPLOIT_BLOCK_LOUD_SLOPE": 0.9,
    "EXPLOIT_BLOCK_LOUD_SHIFT": -0.5,
    "EXPLOIT_BLOCK_STEALTH_SLOPE": 0.2,
    "EXPLOIT_BLOCK_STEALTH_SHIFT": -1.5,
    "BREACH_BLOCK_SLOPE": 0.3,
    "BREACH_BLOCK_SHIFT": -1.0,
    # Exploit/Breach success probabilities (if not blocked)
    "EXPLOIT_SUCCESS_LOUD": 0.8,
    "EXPLOIT_SUCCESS_STEALTH": 0.5,
    "BREACH_ATTEMPT_PROB": 0.9,
}

# Cost Weights for Defender (based on user specification - Section 5.1)
COST_MTD_ACTION = 0.005  # Base cost per MTD policy change
COST_SHUFFLE = 0.5       # Cost multiplier for shuffle operation
COST_DECOY = 0.05        # Cost multiplier for decoy ratio
COST_BL = 0.01           # Cost multiplier for blacklist level
COST_WEIGHT = 0.5        # Multiplier for total calculated cost term in reward function

# Blacklister Mapping (Used in SimulatedBlacklister)
BLACKLIST_SENSITIVITY_MIN = 0.1
BLACKLIST_SENSITIVITY_MAX = 0.9
BLACKLIST_DURATION_MIN_STEPS = 10
BLACKLIST_DURATION_MAX_STEPS = 10000

# --- RL AGENT CONFIGURATION ---

# Observation State Features (FEATURE_KEYS - 16 dimensions)
# NOTE: The first 10 are dynamic metrics, the last 6 are the last actions taken.
FEATURE_KEYS = [
    # Metrics (10D)
    "cti_alert_rate",           # (1) CTI passive detection rate (0..1)
    "blacklist_size_ratio",     # (2) Current Blacklist size / Max size (0..1)
    "uptime_ratio",             # (3) Overall network uptime/availability (0..1)
    "breach_success_rate",      # (4) Breach events / Total attack steps (0..1) - Cumulative/Windowed
    "decoy_lure_rate",          # (5) Decoy attack steps / Total attack steps (0..1) - Cumulative/Windowed
    "current_exposure_mean",    # (6) LPC: Average steps seeker has been exposed to the current IP
    "r_known_ratio",            # (7) LPC: Ratio of known IPs (Seeker's knowledge)
    "r_exploited_ratio",        # (8) LPC: Ratio of exploited IPs
    "seeker_scan_effort",       # (9) Seeker's current/last known scan effort (0..1)
    "seeker_attack_bias",       # (10) Seeker's current/last known attack bias (0..1)
    # Last Action Parameters (6D)
    "last_action_dnat_target_focus",
    "last_action_dnat_decoy_focus",
    "last_action_shuffle_intensity",
    "last_action_blacklist_aggression",
    "last_action_blacklist_duration",
    "last_action_decoy_ratio"
]

# Action Space Definition (ACTION_PARAM_KEYS - 6 dimensions)
# Output is continuous [-1, 1], mapped to [0, 1] for environment use.
ACTION_PARAM_KEYS = [
    "dnat_target_focus",        # Target redirection priority (0=low, 1=high)
    "dnat_decoy_focus",         # Decoy redirection priority (0=low, 1=high)
    "shuffle_intensity",        # Frequency/Force of MTD shuffle (0=none, 1=max)
    "blacklist_aggression",     # Sensitivity of blacklisting (0=min, 1=max)
    "blacklist_duration",       # Duration of blacklisting (0=min, 1=max)
    "decoy_ratio"               # Proportion of traffic to decoy targets (0=min, 1=max)
]

# State Normalization Metadata (Placeholders - MUST be determined by pre-training or consistent with testbed)
# The actual normalization should occur based on data collected, but placeholders are included
# for consistency with a typical RL config file structure.
FEATURE_NORM_METADATA = {
    "means": [0.5] * len(FEATURE_KEYS),
    "stds": [0.25] * len(FEATURE_KEYS)
}

# --- LOGGING AND EVALUATION METRICS (New DRS/TTE/Cost Metrics) ---
# These are the derived metrics for plotting/logging in rl_train_v05.py

LOG_METRICS_DEFENSE = [
    "R_succ",             # Breach Stop Rate (1 - Breach Success / Breach Attempts)
    "C_def",              # Avg. Defense Cost per Step
    "CostPerBlock",       # Total Cost / Total Blocks (Exploit + Breach + Decoy)
    "S_MTD_overall"       # Composite Score (e.g., 0.5*R_succ + 0.5*Decoy_Rate - 0.1*C_def)
]

LOG_METRICS_DRS = [
    "D_bits",             # Diversity (Entropy of endpoint visitation)
    "R_redundancy",       # Redundancy (Number of distinct ports - simplified)
    "S_shuffle",          # Shuffle (Normalized Shuffle Frequency)
]

LOG_METRICS_ATTACK = [
    "r_scan",             # Scan attempts / Total Steps
    "r_find",             # Find events / Scan attempts
    "r_exploit_block",    # Exploit Block / Exploit Attempts
    "r_exploit_success",  # Exploit Success / Exploit Attempts
    "r_breach_block",     # Breach Block / Breach Attempts
    "r_breach_success",   # Breach Success / Breach Attempts
    "decoy_lure_rate"
]

LOG_METRICS_TIME_TO_EVENT = [
    "TTF_mean",           # Time-to-Find (Avg Exposure Steps at Find)
    "TTEB_mean",          # Time-to-Exploit-Block (Avg Exposure Steps at Exploit Block)
    "TTBr_mean",          # Time-to-Breach (Avg Exposure Steps at Breach Success)
]