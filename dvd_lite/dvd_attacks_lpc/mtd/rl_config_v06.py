# Configuration for the MTD Reinforcement Learning Agent and Environment (v06)
#
# This configuration refines the training environment to encourage more
# aggressive use of moving target defence (MTD) actions early in learning
# while still penalising unnecessary defence in the absence of attacks.  The
# thresholds for triggering shuffle and decoy behaviours have been lowered to
# promote exploration, and costs for these actions have been reduced so
# the agent can experiment without being overly punished.  Likewise,
# rewards for blocking attacks have been increased and penalties for
# successful breaches have been made more severe to emphasise the
# importance of preventing intrusions.

import os
import numpy as np

# --- PATH SETTINGS ---
# Base directory for locating shared state.  The environment will read
# mtd_state.json from this location to incorporate real-world state if
# available.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MTD_STATE_PATH = os.path.join(BASE_DIR, "shared_state", "mtd_state.json")

# --- ENVIRONMENT CONSTANTS AND PARAMETERS ---
# Simulation time for each environment step (in seconds).  Used for
# translating durations (e.g. blacklist durations) into step counts.
SIM_TIME_PER_STEP_SEC = 1.0  # 1 step = 1 second

# Number of endpoints (targets and decoys) present in the simulation.  If
# attacker_config.json does not define endpoints these fallbacks are used.
NUM_TARGET_ENDPOINTS = 5
NUM_DECOY_ENDPOINTS = 2
NUM_TOTAL_ENDPOINTS = NUM_TARGET_ENDPOINTS + NUM_DECOY_ENDPOINTS

# [IMPROVEMENT] Lower defence activation thresholds to encourage early
# exploration of MTD strategies.  These thresholds define the minimum
# intensity/ratio values (after scaling) required to trigger shuffle,
# decoy and blacklist actions.
ACT_THRESHOLDS = {
    # Further reduce activation thresholds to encourage the agent
    # to explore defensive actions earlier.  With these values,
    # moderate action intensities (>=0.2) will trigger shuffling,
    # decoy activation, or blacklisting.
    "SHUFFLE": 0.2,
    "DECOY_ACTIVE": 0.2,
    "BL_ACTIVE": 0.2,
}

# Seeker (attacker) model parameters.  These constants control the
# behaviour of the simulated heuristic attacker used during training.  See
# seeker_agent.py for details.
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

# --- COSTS AND REWARDS ---
# [IMPROVEMENT] Reduce the cost of MTD actions and increase the rewards
# for successful defence.  The cost constants determine how much
# penalisation is applied to the reward when the agent chooses to take
# defensive actions.  Lowering these values encourages the agent to
# experiment with MTD strategies.  Conversely, the rewards for blocking
# attacks and penalties for successful attacks have been enlarged to
# incentivise preventing intrusions.
COST_MTD_ACTION = 0.001    # base cost for performing any MTD action
COST_SHUFFLE = 0.05        # cost per unit shuffle intensity
COST_DECOY = 0.01          # cost per unit decoy ratio
COST_BL = 0.005            # cost per unit blacklist aggression
COST_WEIGHT = 0.2          # weighting applied to total cost in reward

REWARD_ATTACK_BLOCKED = 50.0   # reward when an attack is successfully blocked
REWARD_ATTACK_SUCCESS = -100.0 # penalty when an attack breaches the system
REWARD_MTD_COST = -0.1
REWARD_NORMAL = 0.5            # reward for a timestep with no attack or exploit

# Blacklister parameter bounds for mapping RL actions to discrete
# sensitivities and durations.
BLACKLIST_SENSITIVITY_MIN = 0.1
BLACKLIST_SENSITIVITY_MAX = 0.9
BLACKLIST_DURATION_MIN_STEPS = 10
BLACKLIST_DURATION_MAX_STEPS = 10000

# --- RL AGENT CONFIGURATION ---
# State features include CTI and defence metrics as well as last
# selected action parameters.  The agent will normalise these inputs
# using the provided mean and standard deviation metadata.
FEATURE_KEYS = [
    # Metrics (10D)
    "cti_alert_rate",            # CTI alert rate (recent)
    "blacklist_size_ratio",      # proportion of endpoints currently blacklisted
    "uptime_ratio",              # proportion of time system has been up without shuffle
    "breach_success_rate",       # ratio of successful breaches to attempts
    "decoy_lure_rate",           # ratio of decoy hits to exploit attempts
    "current_exposure_mean",     # mean exposure time of system (placeholder)
    "r_known_ratio",             # ratio of assets known to attacker (placeholder)
    "r_exploited_ratio",         # ratio of assets exploited by attacker (placeholder)
    "seeker_scan_effort",        # attacker's scanning effort
    "seeker_attack_bias",        # attacker's loud/stealth bias
    # Last Action Parameters (6D)
    "last_action_dnat_target_focus",
    "last_action_dnat_decoy_focus",
    "last_action_shuffle_intensity",
    "last_action_blacklist_aggression",
    "last_action_blacklist_duration",
    "last_action_decoy_ratio"
]

# Action parameters output by the RL policy.  These values are
# continuous in [-1,1] and will be scaled to [0,1] before being
# interpreted by the environment.
ACTION_PARAM_KEYS = [
    "dnat_target_focus",        # proportion of traffic sent to real targets
    "dnat_decoy_focus",         # proportion of traffic sent to decoys
    "shuffle_intensity",        # intensity of IP/port shuffle
    "blacklist_aggression",     # sensitivity of blacklist (lower threshold)
    "blacklist_duration",       # duration of blacklist entry
    "decoy_ratio"               # ratio of traffic redirected to decoys
]

STATE_DIM = len(FEATURE_KEYS)
ACTION_DIM = len(ACTION_PARAM_KEYS)

# Normalisation metadata for state features.  These values are used by
# the RL agent to standardise inputs.  The means and standard deviations
# reflect approximate baseline values (0.5 with std 0.25) assuming
# features lie roughly in [0,1].
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

# Logging metrics keys used for monitoring.  They are grouped into
# categories for clarity when visualising results.
LOG_METRICS_DEFENSE = ["R_succ", "C_def", "CostPerBlock", "S_MTD_overall"]
LOG_METRICS_DRS = ["D_bits", "R_redundancy", "S_shuffle"]
LOG_METRICS_ATTACK = [
    "r_scan", "r_find", "r_exploit_block", "r_exploit_success",
    "r_breach_block", "r_breach_success", "decoy_lure_rate"
]
LOG_METRICS_TIME_TO_EVENT = ["TTF_mean", "TTEB_mean", "TTBr_mean"]


# --- Legacy Wrapper (for backwards compatibility) ---
# To avoid refactoring older code that imports RL_CONFIG from
# rl_config_v05, we provide a wrapper class with the same attribute
# names.  New code should import RL_CONFIG directly from
# rl_config_v06.
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

    # Expose blacklist duration range so that rl_environment_v06 can
    # compute block durations without direct module-level access.  If
    # these constants are not present, the environment will raise an
    # AttributeError as seen in issue reports.
    BLACKLIST_DURATION_MIN_STEPS = BLACKLIST_DURATION_MIN_STEPS
    BLACKLIST_DURATION_MAX_STEPS = BLACKLIST_DURATION_MAX_STEPS