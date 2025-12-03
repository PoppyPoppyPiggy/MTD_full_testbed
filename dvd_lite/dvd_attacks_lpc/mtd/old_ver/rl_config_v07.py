#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MTD RL v07 configuration - Balanced search space for realistic training."""
from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Set, Tuple

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class AttackPhase(Enum):
    SCANNING = auto()
    DISCOVERED = auto()
    EXPLOITING = auto()
    COMPROMISED = auto()


# ---------------------------------------------------------------------------
# DVD Testbed Configuration
# ---------------------------------------------------------------------------
@dataclass
class DVDTestbedConfig:
    subnet: str = "10.13.0.0/24"
    gateway: str = "10.13.0.1"
    real_targets: Dict[str, str] = field(default_factory=lambda: {
        "TARGET_FC": "10.13.0.2",
        "TARGET_CC": "10.13.0.3",
        "TARGET_GCS": "10.13.0.4",
        "TARGET_SIM": "10.13.0.5",
    })
    decoys: Dict[str, str] = field(default_factory=lambda: {
        "TARGET_DECOY_1": "10.13.0.7",
        "TARGET_DECOY_2": "10.13.0.8",
    })
    service_ports: Dict[str, int] = field(default_factory=lambda: {
        "PORT_MAVLINK": 14550,
        "PORT_SITL": 5760,
        "PORT_RTSP": 554,
        "PORT_WEB": 3000,
        "PORT_ROS": 11311,
    })
    critical_assets: Tuple[str, ...] = ("TARGET_FC", "TARGET_GCS")


# ---------------------------------------------------------------------------
# Search Space Configuration (현실적 크기로 조정)
# ---------------------------------------------------------------------------
@dataclass
class SearchSpaceConfig:
    """축소된 탐색 공간 - 학습 가능한 크기"""
    virtual_ip_start: int = 1
    virtual_ip_end: int = 50       # 50개 IP (100 → 50)
    virtual_port_start: int = 1024
    virtual_port_end: int = 1124   # 100개 Port (1000 → 100)

    @property
    def ip_pool_size(self) -> int:
        return self.virtual_ip_end - self.virtual_ip_start + 1

    @property
    def port_pool_size(self) -> int:
        return self.virtual_port_end - self.virtual_port_start + 1

    @property
    def total_search_space(self) -> int:
        return self.ip_pool_size * self.port_pool_size  # 50 × 100 = 5,000

    @property
    def max_entropy_bits(self) -> float:
        return math.log2(max(1, self.total_search_space))


# ---------------------------------------------------------------------------
# Service Mapping
# ---------------------------------------------------------------------------
@dataclass
class ServiceMapping:
    target_name: str
    real_ip: str
    real_port: int
    virtual_ip: int
    virtual_port: int
    is_decoy: bool = False
    is_critical: bool = False
    active: bool = True

    def get_virtual_address(self) -> Tuple[int, int]:
        return (self.virtual_ip, self.virtual_port)


# ---------------------------------------------------------------------------
# Attack Progress
# ---------------------------------------------------------------------------
@dataclass
class AttackProgress:
    discovery: float = 0.0
    exploitation: float = 0.0
    compromise: float = 0.0
    scanned_addresses: Set[Tuple[int, int]] = field(default_factory=set)
    discovered_services: Set[str] = field(default_factory=set)

    DISCOVERY_THRESHOLD: float = 0.7
    EXPLOITATION_THRESHOLD: float = 0.7
    COMPROMISE_THRESHOLD: float = 0.9

    def reset(self, partial: bool = False) -> None:
        if partial:
            self.discovery *= 0.3
            self.exploitation *= 0.1
            self.compromise = 0.0
            self.discovered_services.clear()
        else:
            self.discovery = self.exploitation = self.compromise = 0.0
            self.scanned_addresses.clear()
            self.discovered_services.clear()

    @property
    def compromised(self) -> bool:
        return self.compromise >= self.COMPROMISE_THRESHOLD

    @property
    def phase(self) -> AttackPhase:
        if self.compromise >= self.COMPROMISE_THRESHOLD:
            return AttackPhase.COMPROMISED
        elif self.exploitation >= self.EXPLOITATION_THRESHOLD:
            return AttackPhase.EXPLOITING
        elif self.discovery >= self.DISCOVERY_THRESHOLD:
            return AttackPhase.DISCOVERED
        return AttackPhase.SCANNING


# ---------------------------------------------------------------------------
# Seeker Profiles (스캔 효율 대폭 증가)
# ---------------------------------------------------------------------------
DEFAULT_SEEKER_PROFILES: Dict[int, Dict] = {
    0: {
        "name": "Script Kiddie",
        "scans_per_step": 20,       # 5→20 증가
        "scan_efficiency": 0.5,
        "exploit_prob": 0.35,
        "breach_prob": 0.20,
        "decoy_detect": 0.10,
        "smart_scan": 0.0,
    },
    1: {
        "name": "Mainstream",
        "scans_per_step": 40,
        "scan_efficiency": 0.6,
        "exploit_prob": 0.55,
        "breach_prob": 0.35,
        "decoy_detect": 0.25,
        "smart_scan": 0.2,
    },
    2: {
        "name": "Time-Aware",
        "scans_per_step": 60,
        "scan_efficiency": 0.7,
        "exploit_prob": 0.70,
        "breach_prob": 0.50,
        "decoy_detect": 0.40,
        "smart_scan": 0.4,
        "time_boost": True,
    },
    3: {
        "name": "Adaptive",
        "scans_per_step": 80,
        "scan_efficiency": 0.8,
        "exploit_prob": 0.80,
        "breach_prob": 0.65,
        "decoy_detect": 0.60,
        "smart_scan": 0.6,
        "adaptive": True,
    },
    4: {
        "name": "Expert APT",
        "scans_per_step": 100,
        "scan_efficiency": 0.9,
        "exploit_prob": 0.90,
        "breach_prob": 0.80,
        "decoy_detect": 0.80,
        "smart_scan": 0.8,
        "time_boost": True,
        "adaptive": True,
    },
}


def load_seeker_profiles(path: str | None) -> Dict[int, Dict]:
    if path and os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {int(k): v for k, v in data.get("levels", {}).items()}
    return DEFAULT_SEEKER_PROFILES


# ---------------------------------------------------------------------------
# Cost Model
# ---------------------------------------------------------------------------
@dataclass
class MTDCostModel:
    shuffle_latency_ms: float = 50.0
    shuffle_bandwidth_loss: float = 0.002
    shuffle_sync_overhead: float = 0.01
    port_hop_cpu: float = 0.05
    port_hop_connection_reset: float = 0.05
    decoy_high_interaction: float = 0.5
    decoy_low_interaction: float = 0.1
    decoy_memory_mb: float = 128.0
    blacklist_fp_rate: float = 0.02
    blacklist_update: float = 0.001
    energy_per_shuffle_joule: float = 0.05
    energy_budget_joule: float = 100.0

    def calculate_shuffle_cost(self, intensity: float, num_services: int) -> Dict[str, float]:
        latency = self.shuffle_latency_ms * intensity * num_services
        bandwidth = self.shuffle_bandwidth_loss * intensity
        sync = self.shuffle_sync_overhead * intensity * num_services
        energy = self.energy_per_shuffle_joule * intensity
        return {
            "latency_ms": latency,
            "bandwidth_loss": bandwidth,
            "sync_overhead": sync,
            "energy": energy,
            "total": latency / 1000 + bandwidth + sync + energy
        }

    def calculate_decoy_cost(self, active_decoys: int, high_interaction: bool = True) -> Dict[str, float]:
        base = (self.decoy_high_interaction if high_interaction else self.decoy_low_interaction) * active_decoys
        memory = self.decoy_memory_mb * active_decoys / 1024
        return {"compute": base, "memory_gb": memory, "total": base + memory * 0.1}


# ---------------------------------------------------------------------------
# Reward Model
# ---------------------------------------------------------------------------
@dataclass
class RewardModel:
    reward_scan_blocked: float = 10.0
    reward_exploit_blocked: float = 40.0
    reward_breach_blocked: float = 80.0
    penalty_service_found: float = -15.0
    penalty_exploit: float = -30.0
    penalty_breach: float = -150.0
    reward_decoy_scan: float = 12.0
    reward_decoy_exploit: float = 25.0
    reward_survival: float = 0.2
    cost_weight_explore: float = 0.1
    cost_weight_exploit: float = 0.25


# ---------------------------------------------------------------------------
# Thresholds & Initial State
# ---------------------------------------------------------------------------
@dataclass
class MTDThresholds:
    shuffle: float = 0.3
    port_hop: float = 0.3
    decoy_activate: float = 0.2
    blacklist: float = 0.25


@dataclass
class InitialStateConfig:
    mode: str = "sample"
    mode_probs: Tuple[float, float, float] = (0.3, 0.5, 0.2)
    pre_scanned_ratio: float = 0.1
    pre_discovered_services: int = 1


# ---------------------------------------------------------------------------
# PPO Config
# ---------------------------------------------------------------------------
@dataclass
class PPOConfig:
    learning_rate: float = 3e-4
    gamma: float = 0.99
    gae_lambda: float = 0.95
    clip_epsilon: float = 0.2
    entropy_coef_start: float = 0.01
    entropy_coef_final: float = 0.001
    value_loss_coef: float = 0.5
    max_grad_norm: float = 0.5
    batch_size: int = 64
    update_epochs: int = 4
    total_episodes: int = 500
    max_steps: int = 200


# ---------------------------------------------------------------------------
# State/Action Dimensions
# ---------------------------------------------------------------------------
FEATURE_KEYS: List[str] = [
    "search_space_scanned_ratio",
    "services_discovered_ratio",
    "critical_discovered",
    "avg_exploitation_progress",
    "avg_compromise_progress",
    "current_diversity",
    "current_redundancy",
    "decoy_engagement_rate",
    "energy_remaining_ratio",
    "steps_since_shuffle",
    "attacker_scan_rate",
    "last_shuffle_intensity",
    "last_port_hop_intensity",
    "last_decoy_ratio",
    "last_blacklist_aggression",
]

ACTION_PARAM_KEYS: List[str] = [
    "shuffle_intensity",
    "port_hop_intensity",
    "decoy_ratio",
    "blacklist_aggression",
    "blacklist_duration",
    "service_swap_rate",
]

STATE_DIM = len(FEATURE_KEYS)
ACTION_DIM = len(ACTION_PARAM_KEYS)


# ---------------------------------------------------------------------------
# Episode Statistics (모든 지표 포함)
# ---------------------------------------------------------------------------
@dataclass
class EpisodeStats:
    defense_success_rate: float = 0.0
    breach_prevented: bool = True
    avg_diversity: float = 0.0
    min_diversity: float = 1.0
    avg_redundancy: float = 0.0
    total_cost: float = 0.0
    total_latency_ms: float = 0.0
    total_energy: float = 0.0
    services_found: int = 0
    decoy_hits: int = 0
    scans_blocked: int = 0
    time_to_first_discovery: int = 0
    time_to_breach: int = 0
    total_scans: int = 0
    effective_scans: int = 0
    s_mtd: float = 0.0
    # 추가 상세 지표
    shuffle_count: int = 0
    port_hop_count: int = 0
    decoy_activations: int = 0
    blacklist_additions: int = 0

    def compute_s_mtd(self) -> float:
        decoy_rate = self.decoy_hits / max(1, self.total_scans)
        self.s_mtd = (
            0.6 * self.defense_success_rate
            + 0.3 * decoy_rate
            - 0.05 * min(self.total_cost, 10.0)
            + 0.1 * self.avg_diversity
        )
        return self.s_mtd

    def as_dict(self) -> Dict[str, float]:
        return {
            "Defense/Success": self.defense_success_rate,
            "Defense/BreachPrevented": float(self.breach_prevented),
            "Defense/Diversity_Avg": self.avg_diversity,
            "Defense/Diversity_Min": self.min_diversity,
            "Defense/Redundancy": self.avg_redundancy,
            "Defense/S_MTD": self.s_mtd,
            "Cost/Total": self.total_cost,
            "Cost/Latency_ms": self.total_latency_ms,
            "Cost/Energy": self.total_energy,
            "Attack/ServicesFound": float(self.services_found),
            "Attack/TotalScans": float(self.total_scans),
            "Attack/EffectiveScans": float(self.effective_scans),
            "Attack/TimeToDiscovery": float(self.time_to_first_discovery),
            "Attack/TimeToBreach": float(self.time_to_breach),
            "Decoy/Hits": float(self.decoy_hits),
            "Decoy/BlockedScans": float(self.scans_blocked),
            "MTD/ShuffleCount": float(self.shuffle_count),
            "MTD/PortHopCount": float(self.port_hop_count),
            "MTD/DecoyActivations": float(self.decoy_activations),
            "MTD/BlacklistAdditions": float(self.blacklist_additions),
        }


# ---------------------------------------------------------------------------
# Curriculum Config
# ---------------------------------------------------------------------------
@dataclass
class CurriculumConfig:
    phases: Tuple[Tuple[int, ...], ...] = ((0,), (1,), (2,), (3,), (0, 1, 2, 3, 4))
    phase_episodes: Tuple[int, ...] = (100, 150, 200, 200, 250)
    entropy_schedule: Tuple[float, ...] = (0.01, 0.008, 0.005, 0.003, 0.001)


# ---------------------------------------------------------------------------
# Main Config
# ---------------------------------------------------------------------------
class MTDConfig:
    testbed = DVDTestbedConfig()
    search_space = SearchSpaceConfig()
    cost_model = MTDCostModel()
    reward_model = RewardModel()
    thresholds = MTDThresholds()
    initial_state = InitialStateConfig()
    ppo = PPOConfig()
    curriculum = CurriculumConfig()

    STATE_DIM = STATE_DIM
    ACTION_DIM = ACTION_DIM
    FEATURE_KEYS = FEATURE_KEYS
    ACTION_PARAM_KEYS = ACTION_PARAM_KEYS
    BASE_DIR = BASE_DIR


RL_CONFIG = MTDConfig