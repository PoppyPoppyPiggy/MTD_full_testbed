#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rl_config_v07.py

MTD Reinforcement Learning Configuration (v07) - Academic Reference Based

=============================================================================
ACADEMIC REFERENCES FOR PARAMETERS
=============================================================================

1. REWARD FUNCTION DESIGN
   - Eghtesad et al. (GameSec 2020): Sigmoid-based defender utility
   - Li et al. (Scientific Reports 2025): DRD-PPO discrete rewards
     R_t = R_1 - c_d * n_d^t - c_v * n_v^t
     c_d = 0.5 (high-interaction honeypot), c_v = 0.1 (low-interaction)

2. COST MODELING
   - Chang et al. (IEEE TNSM 2018): SDN IP hopping overhead
   - Sandia National Labs (OSTI 2015): Bandwidth retention metrics

3. DEFENSE EFFECTIVENESS METRICS
   - Attack Success Probability: ASP = DSP × ESP × CSP
   - Zhuang et al.: MTD Entropy Hypothesis

4. IP×PORT SEARCH SPACE
   - Jafarian et al. (SIGCOMM HotSDN 2012): OF-RHM Class B networks

5. ATTACKER MODELING (BSS-Q Framework)
=============================================================================
"""

import os
import math
from dataclasses import dataclass, field
from typing import Dict, List, Tuple
from enum import IntEnum


# =============================================================================
# PATH SETTINGS
# =============================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MTD_STATE_PATH = os.path.join(BASE_DIR, "shared_state", "mtd_state.json")
CONFIG_DIR = os.path.join(BASE_DIR, "config")


# =============================================================================
# NETWORK TOPOLOGY DEFINITION
# =============================================================================
@dataclass
class NetworkTopology:
    ip_subnet: str = "10.13.0.0/24"
    ip_pool_size: int = 256
    port_pool_size: int = 1000
    privileged_ports: Tuple[int, ...] = (14550, 5760, 554, 3000, 11311)
    
    real_targets: Dict[str, str] = field(default_factory=lambda: {
        "TARGET_FC": "10.13.0.2",
        "TARGET_CC": "10.13.0.3",
        "TARGET_GCS": "10.13.0.4",
        "TARGET_SIM": "10.13.0.5",
    })
    
    decoy_targets: Dict[str, str] = field(default_factory=lambda: {
        "DECOY_FC": "10.13.0.7",
        "DECOY_GCS": "10.13.0.8",
    })
    
    @property
    def shuffle_space_size(self) -> int:
        return self.ip_pool_size * self.port_pool_size
    
    @property
    def shuffle_entropy_bits(self) -> float:
        return math.log2(self.shuffle_space_size)


# =============================================================================
# ATTACK PHASE MODEL (3-Stage Kill Chain)
# =============================================================================
class AttackPhase(IntEnum):
    RECONNAISSANCE = 0
    EXPLOITATION = 1
    COMPROMISE = 2


@dataclass
class AttackProgress:
    discovery_progress: float = 0.0
    exploitation_progress: float = 0.0
    compromise_progress: float = 0.0
    
    DISCOVERY_THRESHOLD: float = 0.7
    EXPLOITATION_THRESHOLD: float = 0.7
    COMPROMISE_THRESHOLD: float = 0.9
    
    @property
    def current_phase(self) -> AttackPhase:
        if self.compromise_progress >= self.COMPROMISE_THRESHOLD:
            return AttackPhase.COMPROMISE
        elif self.exploitation_progress >= self.EXPLOITATION_THRESHOLD:
            return AttackPhase.EXPLOITATION
        return AttackPhase.RECONNAISSANCE
    
    @property
    def is_compromised(self) -> bool:
        return self.compromise_progress >= self.COMPROMISE_THRESHOLD
    
    def reset(self, partial: bool = False):
        if partial:
            self.discovery_progress *= 0.3
            self.exploitation_progress *= 0.1
            self.compromise_progress *= 0.0
        else:
            self.discovery_progress = 0.0
            self.exploitation_progress = 0.0
            self.compromise_progress = 0.0


# =============================================================================
# COST MODEL (Academic Reference Based)
# =============================================================================
@dataclass
class MTDCostModel:
    ip_shuffle_bandwidth_cost: float = 0.002
    ip_shuffle_latency_ms: float = 20.0
    ip_shuffle_sync_cost: float = 0.01
    port_hop_cpu_cost: float = 0.05
    port_hop_connection_reset: float = 0.1
    decoy_high_interaction_cost: float = 0.5
    decoy_low_interaction_cost: float = 0.1
    decoy_maintenance_per_step: float = 0.01
    blacklist_false_positive_cost: float = 0.2
    blacklist_update_cost: float = 0.001
    energy_per_shuffle_joules: float = 0.05
    energy_budget_per_episode: float = 100.0
    
    def calculate_total_cost(
        self,
        shuffle_intensity: float,
        port_hop_intensity: float,
        decoy_ratio: float,
        blacklist_aggression: float,
        num_high_decoys: int = 0,
        num_low_decoys: int = 0,
    ) -> Dict[str, float]:
        costs = {}
        costs["ip_shuffle"] = (
            self.ip_shuffle_bandwidth_cost * shuffle_intensity +
            self.ip_shuffle_sync_cost * shuffle_intensity
        )
        costs["port_hop"] = (
            self.port_hop_cpu_cost * port_hop_intensity +
            self.port_hop_connection_reset * port_hop_intensity * 0.5
        )
        costs["decoy"] = (
            self.decoy_high_interaction_cost * num_high_decoys +
            self.decoy_low_interaction_cost * num_low_decoys +
            self.decoy_maintenance_per_step * decoy_ratio
        )
        costs["blacklist"] = (
            self.blacklist_update_cost * blacklist_aggression +
            self.blacklist_false_positive_cost * (blacklist_aggression ** 2) * 0.1
        )
        costs["energy"] = self.energy_per_shuffle_joules * shuffle_intensity
        costs["total"] = sum(costs.values())
        return costs


# =============================================================================
# REWARD MODEL (DRD-PPO Based)
# =============================================================================
@dataclass
class RewardModel:
    reward_discovery_blocked: float = 10.0
    reward_exploitation_blocked: float = 40.0
    reward_breach_blocked: float = 80.0
    penalty_discovery_success: float = -5.0
    penalty_exploitation_success: float = -30.0
    penalty_breach_success: float = -150.0
    reward_decoy_scan: float = 5.0
    reward_decoy_exploit: float = 15.0
    reward_decoy_time_waste: float = 2.0
    cost_weight_explore: float = 0.1
    cost_weight_exploit: float = 0.25
    reward_survival_per_step: float = 0.1
    enable_shaping: bool = True
    shaping_coefficient: float = 0.5
    
    def calculate_reward(
        self,
        event_type: str,
        mtd_cost: float,
        cost_weight: float,
        attack_progress_delta: float = 0.0,
    ) -> float:
        reward = 0.0
        event_rewards = {
            "discovery_blocked": self.reward_discovery_blocked,
            "exploitation_blocked": self.reward_exploitation_blocked,
            "breach_blocked": self.reward_breach_blocked,
            "discovery_success": self.penalty_discovery_success,
            "exploitation_success": self.penalty_exploitation_success,
            "breach_success": self.penalty_breach_success,
            "decoy_scan": self.reward_decoy_scan,
            "decoy_exploit": self.reward_decoy_exploit,
            "survival": self.reward_survival_per_step,
        }
        reward += event_rewards.get(event_type, 0.0)
        reward -= mtd_cost * cost_weight
        if self.enable_shaping and attack_progress_delta != 0.0:
            reward -= attack_progress_delta * self.shaping_coefficient
        return reward


# =============================================================================
# STATE SPACE DEFINITION
# =============================================================================
FEATURE_KEYS = [
    "cti_alert_rate",
    "blacklist_size_ratio",
    "service_uptime_ratio",
    "avg_discovery_progress",
    "avg_exploitation_progress",
    "avg_compromise_progress",
    "max_compromise_progress",
    "decoy_engagement_rate",
    "decoy_time_absorbed_ratio",
    "energy_remaining_ratio",
    "shuffle_entropy_bits",
    "estimated_scan_rate",
    "estimated_attack_sophistication",
    "last_shuffle_intensity",
    "last_port_hop_intensity",
    "last_decoy_ratio",
    "last_blacklist_aggression",
]

ACTION_PARAM_KEYS = [
    "shuffle_intensity",
    "port_hop_intensity",
    "decoy_activation_level",
    "blacklist_aggression",
    "blacklist_duration",
    "service_migration_rate",
]

STATE_DIM = len(FEATURE_KEYS)
ACTION_DIM = len(ACTION_PARAM_KEYS)


# =============================================================================
# MTD ACTION THRESHOLDS
# =============================================================================
@dataclass
class MTDThresholds:
    shuffle_activation: float = 0.3
    port_hop_activation: float = 0.3
    decoy_activation: float = 0.2
    blacklist_activation: float = 0.25
    shuffle_effect_scale: float = 1.0
    decoy_effect_scale: float = 1.0


# =============================================================================
# INITIAL STATE CONFIGURATION
# =============================================================================
@dataclass
class InitialStateConfig:
    mode: str = "partial_compromise"
    num_pre_discovered: int = 2
    num_pre_exploited: int = 1
    pre_discovery_progress: float = 0.5
    pre_exploitation_progress: float = 0.3
    attacker_knows_topology: bool = True
    attacker_knows_some_ips: int = 2
    decoys_initially_active: bool = True
    
    def get_initial_progress(self, endpoint_idx: int, is_decoy: bool) -> AttackProgress:
        progress = AttackProgress()
        if is_decoy:
            return progress
        if self.mode == "clean":
            return progress
        elif self.mode == "partial_compromise":
            if endpoint_idx < self.num_pre_discovered:
                progress.discovery_progress = self.pre_discovery_progress
            if endpoint_idx < self.num_pre_exploited:
                progress.exploitation_progress = self.pre_exploitation_progress
        elif self.mode == "random":
            import random
            progress.discovery_progress = random.uniform(0, 0.5)
            if random.random() < 0.3:
                progress.exploitation_progress = random.uniform(0, 0.3)
        return progress


# =============================================================================
# SEEKER (ATTACKER) LEVEL PROFILES
# =============================================================================
SEEKER_PROFILES = {
    0: {
        "name": "Script Kiddie",
        "mode": "random",
        "scan_effort": 0.3,
        "attack_bias": 0.2,
        "ip_change_prob": 0.05,
        "exploit_prob": 0.3,
        "breach_prob": 0.2,
        "learning_rate": 0.0,
    },
    1: {
        "name": "Mainstream Hacker",
        "mode": "heuristic",
        "scan_effort": 0.5,
        "attack_bias": 0.4,
        "ip_change_prob": 0.1,
        "exploit_prob": 0.5,
        "breach_prob": 0.4,
        "learning_rate": 0.01,
    },
    2: {
        "name": "Time-Aware Attacker",
        "mode": "time_aware",
        "scan_effort": 0.4,
        "attack_bias": 0.5,
        "ip_change_prob": 0.15,
        "exploit_prob": 0.6,
        "breach_prob": 0.5,
        "learning_rate": 0.02,
        "time_adaptation_rate": 0.005,
    },
    3: {
        "name": "Adaptive APT",
        "mode": "adaptive",
        "scan_effort": 0.6,
        "attack_bias": 0.7,
        "ip_change_prob": 0.2,
        "exploit_prob": 0.7,
        "breach_prob": 0.6,
        "learning_rate": 0.05,
        "stealth_factor": 0.8,
    },
    4: {
        "name": "Expert APT",
        "mode": "adaptive",
        "scan_effort": 0.8,
        "attack_bias": 0.9,
        "ip_change_prob": 0.3,
        "exploit_prob": 0.85,
        "breach_prob": 0.75,
        "learning_rate": 0.1,
        "stealth_factor": 0.9,
        "target_priority": ["TARGET_GCS", "TARGET_FC"],
    },
}


# =============================================================================
# PPO HYPERPARAMETERS
# =============================================================================
@dataclass
class PPOConfig:
    learning_rate: float = 3e-4
    gamma: float = 0.99
    gae_lambda: float = 0.95
    clip_epsilon: float = 0.2
    entropy_coef: float = 0.01
    entropy_coef_final: float = 0.001
    value_loss_coef: float = 0.5
    max_grad_norm: float = 0.5
    total_episodes: int = 1000
    max_steps_per_episode: int = 200
    batch_size: int = 64
    ppo_epochs: int = 10
    minibatch_size: int = 32
    curriculum_stages: int = 3
    stage_1_episodes: int = 300
    stage_2_episodes: int = 400
    stage_3_episodes: int = 300


# =============================================================================
# EPISODE METRICS
# =============================================================================
@dataclass
class EpisodeMetrics:
    defense_success_rate: float = 0.0
    breach_prevention_rate: float = 0.0
    exploit_block_rate: float = 0.0
    discovery_delay_steps: float = 0.0
    total_mtd_cost: float = 0.0
    avg_cost_per_step: float = 0.0
    energy_consumed: float = 0.0
    decoy_engagement_count: int = 0
    decoy_time_absorbed: int = 0
    shuffle_count: int = 0
    port_hop_count: int = 0
    blacklist_actions: int = 0
    total_scan_attempts: int = 0
    total_exploit_attempts: int = 0
    total_breach_attempts: int = 0
    successful_breaches: int = 0
    avg_config_entropy: float = 0.0
    
    def to_dict(self) -> Dict[str, float]:
        return {
            "Defense/R_succ": self.defense_success_rate,
            "Defense/BreachPreventionRate": self.breach_prevention_rate,
            "Cost/Total": self.total_mtd_cost,
            "Cost/PerStep": self.avg_cost_per_step,
            "Cost/Energy": self.energy_consumed,
            "Decoy/Engagements": float(self.decoy_engagement_count),
            "Decoy/TimeAbsorbed": float(self.decoy_time_absorbed),
            "MTD/ShuffleCount": float(self.shuffle_count),
            "MTD/PortHopCount": float(self.port_hop_count),
            "Attack/ScanAttempts": float(self.total_scan_attempts),
            "Attack/ExploitAttempts": float(self.total_exploit_attempts),
            "Attack/BreachAttempts": float(self.total_breach_attempts),
            "Attack/SuccessfulBreaches": float(self.successful_breaches),
            "Entropy/AvgConfig": self.avg_config_entropy,
        }


# =============================================================================
# MAIN CONFIG CLASS
# =============================================================================
class MTDConfig:
    topology = NetworkTopology()
    cost_model = MTDCostModel()
    reward_model = RewardModel()
    thresholds = MTDThresholds()
    initial_state = InitialStateConfig()
    ppo = PPOConfig()
    
    STATE_DIM = STATE_DIM
    ACTION_DIM = ACTION_DIM
    FEATURE_KEYS = FEATURE_KEYS
    ACTION_PARAM_KEYS = ACTION_PARAM_KEYS
    SEEKER_PROFILES = SEEKER_PROFILES
    BASE_DIR = BASE_DIR
    MTD_STATE_PATH = MTD_STATE_PATH
    CONFIG_DIR = CONFIG_DIR
    
    FEATURE_NORM_METADATA = {
        "means": [0.5] * STATE_DIM,
        "stds": [0.25] * STATE_DIM,
    }


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================
def calculate_asp(dsp: float, esp: float, csp: float) -> float:
    return dsp * esp * csp

def calculate_defense_success_rate(asp: float) -> float:
    return 1.0 - asp

def calculate_entropy(config_space_size: int) -> float:
    if config_space_size <= 0:
        return 0.0
    return math.log2(config_space_size)

def get_seeker_profile(level: int) -> dict:
    return SEEKER_PROFILES.get(level, SEEKER_PROFILES[1])

# Backward compatibility
RL_CONFIG = MTDConfig