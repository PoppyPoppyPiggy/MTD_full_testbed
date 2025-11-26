import os

# --- PATH SETTINGS ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MTD_STATE_PATH = os.path.join(BASE_DIR, "shared_state", "mtd_state.json")

# --- PARAMETERS ---
SIM_TIME_PER_STEP_SEC = 1.0
NUM_TARGET_ENDPOINTS = 5
NUM_DECOY_ENDPOINTS = 2
NUM_TOTAL_ENDPOINTS = NUM_TARGET_ENDPOINTS + NUM_DECOY_ENDPOINTS

# [ADJUSTED] 임계값 하향: 초기 학습 시 행동 발현 유도
ACT_THRESHOLDS = {
    "SHUFFLE": 0.3,      # 30% 이상이면 셔플
    "DECOY_ACTIVE": 0.2, # 20% 이상이면 디코이
    "BL_ACTIVE": 0.2     # 20% 이상이면 블랙리스트 강화
}

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

# [ADJUSTED] 비용 감소 및 보상 강화
COST_MTD_ACTION = 0.001
COST_SHUFFLE = 0.05
COST_DECOY = 0.01
COST_BL = 0.005
COST_WEIGHT = 0.2 

REWARD_ATTACK_BLOCKED = 50.0   # 차단 성공 시 큰 이득
REWARD_ATTACK_SUCCESS = -100.0 # 뚫리면 큰 손해
REWARD_MTD_COST = -0.1
REWARD_NORMAL = 0.5

BLACKLIST_SENSITIVITY_MIN = 0.1
BLACKLIST_SENSITIVITY_MAX = 0.9
BLACKLIST_DURATION_MIN_STEPS = 10
BLACKLIST_DURATION_MAX_STEPS = 10000

# --- RL CONFIG ---
FEATURE_KEYS = [
    "cti_alert_rate", "blacklist_size_ratio", "uptime_ratio", "breach_success_rate",
    "decoy_lure_rate", "current_exposure_mean", "r_known_ratio", "r_exploited_ratio",
    "seeker_scan_effort", "seeker_attack_bias",
    "last_action_dnat_target_focus", "last_action_dnat_decoy_focus",
    "last_action_shuffle_intensity", "last_action_blacklist_aggression",
    "last_action_blacklist_duration", "last_action_decoy_ratio"
]

ACTION_PARAM_KEYS = [
    "dnat_target_focus", "dnat_decoy_focus", "shuffle_intensity",
    "blacklist_aggression", "blacklist_duration", "decoy_ratio"
]

STATE_DIM = len(FEATURE_KEYS)
ACTION_DIM = len(ACTION_PARAM_KEYS)

FEATURE_NORM_METADATA = {
    "means": [0.5] * len(FEATURE_KEYS),
    "stds": [0.25] * len(FEATURE_KEYS)
}

# --- Hyperparameters ---
LEARNING_RATE = 3e-4
GAMMA = 0.99
GAE_LAMBDA = 0.95
CLIP_EPSILON = 0.2
ENTROPY_COEF = 0.01
VALUE_LOSS_COEF = 0.5

BATCH_SIZE = 64
EPOCHS = 10

# --- LOGGING ---
LOG_METRICS_DEFENSE = ["R_succ", "C_def", "CostPerBlock", "S_MTD_overall"]
LOG_METRICS_DRS = ["D_bits", "R_redundancy", "S_shuffle"]
LOG_METRICS_ATTACK = ["r_scan", "r_find", "r_exploit_block", "r_exploit_success", "r_breach_block", "r_breach_success", "decoy_lure_rate"]
LOG_METRICS_TIME_TO_EVENT = ["TTF_mean", "TTEB_mean", "TTBr_mean"]

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