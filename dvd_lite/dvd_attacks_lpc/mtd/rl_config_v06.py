#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rl_config_v06.py

Configuration for the MTD Reinforcement Learning Agent and Environment (v06)

- MTD 활성화 임계값(ACT_THRESHOLDS)을 낮춰 초반 탐색을 장려
- 방어 성공 보상 ↑, 침투 성공 패널티 ↑, 평상시 보상 ↓
- 비용 가중치(COST_WEIGHT) ↓로 인해 초반엔 적극적인 방어 전략을 더 많이 시도하도록 유도
"""

import os
import numpy as np

# --- PATH SETTINGS ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MTD_STATE_PATH = os.path.join(BASE_DIR, "shared_state", "mtd_state.json")

# --- ENVIRONMENT CONSTANTS AND PARAMETERS ---
SIM_TIME_PER_STEP_SEC = 1.0  # 1 step = 1 second

NUM_TARGET_ENDPOINTS = 5
NUM_DECOY_ENDPOINTS = 2
NUM_TOTAL_ENDPOINTS = NUM_TARGET_ENDPOINTS + NUM_DECOY_ENDPOINTS

# [TUNED] Activation thresholds for MTD behaviours
# 조금만 intensity를 올려도 방어 행동이 발동되도록 낮춤
ACT_THRESHOLDS = {
    "SHUFFLE": 0.15,       # 0.2 -> 0.15
    "DECOY_ACTIVE": 0.15,  # 0.2 -> 0.15
    "BL_ACTIVE": 0.15,     # 0.2 -> 0.15
}

# Seeker (attacker) behaviour parameters (그대로 유지)
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

# --- COSTS AND REWARDS (TUNED) ---
# 초반 적극 방어를 허용: 비용 가중치는 낮추고, 공격 차단 보상 / 침투 패널티는 크게
COST_MTD_ACTION = 0.001    # base cost for performing any MTD action
COST_SHUFFLE = 0.05        # cost per unit shuffle intensity
COST_DECOY = 0.01          # cost per unit decoy ratio
COST_BL = 0.005            # cost per unit blacklist aggression

# [TUNED] 비용 가중치 ↓ : 초반에 MTD 행동을 적극적으로 시도하도록 유도
COST_WEIGHT = 0.15         # 0.2 -> 0.15

# [TUNED] 방어 성공 보상/침투 패널티 강화
REWARD_ATTACK_BLOCKED = 80.0    # 50 -> 80
REWARD_ATTACK_SUCCESS = -150.0  # -100 -> -150
REWARD_MTD_COST = -0.1

# [TUNED] 평상시 보상 ↓ : 가만히 있어도 큰 보상이 안 들어오게
REWARD_NORMAL = 0.2             # 0.5 -> 0.2

# Blacklister bounds
BLACKLIST_SENSITIVITY_MIN = 0.1
BLACKLIST_SENSITIVITY_MAX = 0.9
BLACKLIST_DURATION_MIN_STEPS = 10
BLACKLIST_DURATION_MAX_STEPS = 10000

# --- RL AGENT CONFIGURATION ---
FEATURE_KEYS = [
    # Metrics (10D)
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
    # Last Action Parameters (6D)
    "last_action_dnat_target_focus",
    "last_action_dnat_decoy_focus",
    "last_action_shuffle_intensity",
    "last_action_blacklist_aggression",
    "last_action_blacklist_duration",
    "last_action_decoy_ratio",
]

ACTION_PARAM_KEYS = [
    "dnat_target_focus",
    "dnat_decoy_focus",
    "shuffle_intensity",
    "blacklist_aggression",
    "blacklist_duration",
    "decoy_ratio",
]

STATE_DIM = len(FEATURE_KEYS)
ACTION_DIM = len(ACTION_PARAM_KEYS)

FEATURE_NORM_METADATA = {
    "means": [0.5] * len(FEATURE_KEYS),
    "stds": [0.25] * len(FEATURE_KEYS),
}

# --- PPO Hyperparameters (기본 값, argparse에서 override 가능) ---
LEARNING_RATE = 3e-4
GAMMA = 0.99
GAE_LAMBDA = 0.95
CLIP_EPSILON = 0.2
ENTROPY_COEF = 0.01
VALUE_LOSS_COEF = 0.5
BATCH_SIZE = 64
EPOCHS = 10

LOG_METRICS_DEFENSE = ["R_succ", "C_def", "CostPerBlock", "S_MTD_overall"]
LOG_METRICS_DRS = ["D_bits", "R_redundancy", "S_shuffle"]
LOG_METRICS_ATTACK = [
    "r_scan", "r_find", "r_exploit_block", "r_exploit_success",
    "r_breach_block", "r_breach_success", "decoy_lure_rate",
]
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

    BLACKLIST_DURATION_MIN_STEPS = BLACKLIST_DURATION_MIN_STEPS
    BLACKLIST_DURATION_MAX_STEPS = BLACKLIST_DURATION_MAX_STEPS
