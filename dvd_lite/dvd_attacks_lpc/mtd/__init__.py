#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MTD Reinforcement Learning Package v07
"""

from .rl_config_v07 import (
    MTDConfig,
    AttackProgress,
    AttackPhase,
    EpisodeMetrics,
    FEATURE_KEYS,
    ACTION_PARAM_KEYS,
    STATE_DIM,
    ACTION_DIM,
    calculate_asp,
    calculate_defense_success_rate,
    calculate_entropy,
    get_seeker_profile,
    SEEKER_PROFILES,
    MTDConfig as RL_CONFIG,
)

from .rl_environment_v07 import (
    MTDEnvironment,
    Endpoint,
    StepOutcome,
    MTDActionResult,
)

__version__ = "0.7.0"
__author__ = "MTD Research Team"

__all__ = [
    "MTDConfig", "RL_CONFIG", "AttackProgress", "AttackPhase",
    "EpisodeMetrics", "FEATURE_KEYS", "ACTION_PARAM_KEYS",
    "STATE_DIM", "ACTION_DIM", "SEEKER_PROFILES",
    "calculate_asp", "calculate_defense_success_rate",
    "calculate_entropy", "get_seeker_profile",
    "MTDEnvironment", "Endpoint", "StepOutcome", "MTDActionResult",
]
