# Configuration for the MTD Reinforcement Learning Agent and Environment (v06: Refined Metrics & Reward)
import os
import numpy as np
import math

# --- PATH SETTINGS ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MTD_STATE_PATH = os.path.join(BASE_DIR, "shared_state", "mtd_state.json")

# --- ENVIRONMENT CONSTANTS AND PARAMETERS ---
SIM_TIME_PER_STEP_SEC = 1.0
NUM_TARGET_ENDPOINTS = 5
NUM_DECOY_ENDPOINTS = 2
NUM_TOTAL_ENDPOINTS = NUM_TARGET_ENDPOINTS + NUM_DECOY_ENDPOINTS

# [IMPROVEMENT] Adjusted Thresholds for easier triggering
ACT_THRESHOLDS = {
    "SHUFFLE": 0.4,      # Lowered from 0.6 to encourage shuffling
    "DECOY_ACTIVE": 0.3, # Lowered from 0.4
    "BL_ACTIVE": 0.3     # Lowered from 0.3
}

# Seeker Attack Model Parameters
SEEKER_PROB_PARAMS = {
    "SCAN_PROB_FACTOR": 0.4,
    "SCAN_PROB_MIN": 0.05,
    "SCAN_PROB_MAX": 0.95,
    "FIND_EXP_FACTOR": 0.05,
    "EXPLOIT_BLOCK_LOUD_SLOPE": 0.9,
    "EXPLOIT_BLOCK_LOUD_SHIFT": -0.5,
    "EXPLOIT_BLOCK_STEALTH_SLOPE": 0.2,
    "EXPLOIT_BLOCK_STEALTH_SHIFT": -1.5,
    "BREACH_BLOCK_SLOPE": 0.3,
    "BREACH_BLOCK_SHIFT": -1.0,
    "EXPLOIT_SUCCESS_LOUD": 0.8,
    "EXPLOIT_SUCCESS_STEALTH": 0.5,
    "BREACH_ATTEMPT_PROB": 0.9,
}

# [IMPROVEMENT] Adjusted Costs & Rewards to incentivize defense
COST_MTD_ACTION = 0.001   # Reduced base cost
COST_SHUFFLE = 0.1        # Reduced from 0.5 (Shuffling shouldn't be too expensive)
COST_DECOY = 0.01         # Reduced from 0.05
COST_BL = 0.005           # Reduced from 0.01
COST_WEIGHT = 0.2         # Reduced total cost weight in reward calculation

REWARD_ATTACK_BLOCKED = 50.0   # Increased from 20.0 (Big reward for stopping breach)
REWARD_ATTACK_SUCCESS = -100.0 # Increased penalty from -50.0
REWARD_MTD_COST = -0.1
REWARD_NORMAL = 1.0            # Slight bonus for staying alive

# Blacklister Mapping
BLACKLIST_SENSITIVITY_MIN = 0.1
BLACKLIST_SENSITIVITY_MAX = 0.9
BLACKLIST_DURATION_MIN_STEPS = 10
BLACKLIST_DURATION_MAX_STEPS = 10000

# --- RL AGENT CONFIGURATION ---
FEATURE_KEYS = [
    "cti_alert_rate",
    "blacklist_size_ratio",
    "uptime_ratio",
    "breach_success_rate",
    "decoy_lure_rate",
    "current_exposure_mean",
    "r_known_ratio",
    "r_exploited_ratio",
    "seeker_scan_effort",
    "seeker_attack_bias",
    "last_action_dnat_target_focus",
    "last_action_dnat_decoy_focus",
    "last_action_shuffle_intensity",
    "last_action_blacklist_aggression",
    "last_action_blacklist_duration",
    "last_action_decoy_ratio"
]

ACTION_PARAM_KEYS = [
    "dnat_target_focus",
    "dnat_decoy_focus",
    "shuffle_intensity",
    "blacklist_aggression",
    "blacklist_duration",
    "decoy_ratio"
]

STATE_DIM = len(FEATURE_KEYS)
ACTION_DIM = len(ACTION_PARAM_KEYS)

FEATURE_NORM_METADATA = {
    "means": [0.5] * len(FEATURE_KEYS),
    "stds": [0.25] * len(FEATURE_KEYS)
}

# --- PPO Hyperparameters ---
LEARNING_RATE = 3e-4
GAMMA = 0.99
GAE_LAMBDA = 0.95
CLIP_EPSILON = 0.2
ENTROPY_COEF = 0.01
VALUE_LOSS_COEF = 0.5

BATCH_SIZE = 64
EPOCHS = 10

# --- LOGGING METRICS ---
LOG_METRICS_DEFENSE = ["R_succ", "C_def", "CostPerBlock", "S_MTD_overall"]
LOG_METRICS_DRS = ["D_bits", "R_redundancy", "S_shuffle"]
LOG_METRICS_ATTACK = ["r_scan", "r_find", "r_exploit_block", "r_exploit_success", "r_breach_block", "r_breach_success", "decoy_lure_rate"]
LOG_METRICS_TIME_TO_EVENT = ["TTF_mean", "TTEB_mean", "TTBr_mean"]

# --- Legacy Wrapper ---
class RL_CONFIG:
    FEATURE_KEYS = FEATURE_KEYS
    ACTION_PARAM_KEYS = ACTION_PARAM_KEYS
    STATE_DIM = STATE_DIM
    ACTION_DIM = ACTION_DIM
    MTD_STATE_PATH = MTD_STATE_PATH
    FEATURE_NORM_METADATA = FEATURE_NORM_METADATA
    ACT_THRESHOLDS = ACT_THRESHOLDS
    
    LEARNING_RATE = LEARNING_RATE
    GAMMA = GAMMA
    GAE_LAMBDA = GAE_LAMBDA
    CLIP_EPSILON = CLIP_EPSILON
    ENTROPY_COEF = ENTROPY_COEF
    VALUE_LOSS_COEF = VALUE_LOSS_COEF
    BATCH_SIZE = BATCH_SIZE
    EPOCHS = EPOCHS

    REWARD_ATTACK_BLOCKED = REWARD_ATTACK_BLOCKED
    REWARD_ATTACK_SUCCESS = REWARD_ATTACK_SUCCESS
    REWARD_MTD_COST = REWARD_MTD_COST
    REWARD_NORMAL = REWARD_NORMAL
    
    BASE_DIR = BASE_DIR
    NUM_TARGET_ENDPOINTS = NUM_TARGET_ENDPOINTS
    NUM_DECOY_ENDPOINTS = NUM_DECOY_ENDPOINTS