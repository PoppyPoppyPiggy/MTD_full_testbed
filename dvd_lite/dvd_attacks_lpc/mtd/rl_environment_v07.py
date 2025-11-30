#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rl_environment_v07.py

MTD Reinforcement Learning Environment (v07) - State-Based Deterministic Model

KEY CHANGES FROM v06:
1. PROBABILITY → STATE-BASED TRANSITIONS
2. 3-STAGE ATTACK MODEL (ASP = DSP × ESP × CSP)
3. INITIAL STATE: PARTIAL COMPROMISE
4. TESTBED-ALIGNED METRICS
"""

import os
import sys

# 현재 디렉토리를 path에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gymnasium as gym
from gymnasium import spaces
import numpy as np
import logging
import json
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from collections import deque
from enum import Enum

# 절대 import로 변경 (. 제거)
from rl_config_v07 import (
    MTDConfig,
    AttackProgress,
    AttackPhase,
    EpisodeMetrics,
    FEATURE_KEYS,
    ACTION_PARAM_KEYS,
    calculate_entropy,
    get_seeker_profile,
)

logger = logging.getLogger("MTDEnv_v07")


@dataclass
class Endpoint:
    ip: str
    name: str
    is_decoy: bool = False
    is_critical: bool = False
    attack_progress: AttackProgress = field(default_factory=AttackProgress)
    current_virtual_ip: Optional[str] = None
    current_virtual_port: Optional[int] = None
    is_online: bool = True
    last_shuffle_step: int = 0
    
    def reset_progress(self, partial: bool = False):
        self.attack_progress.reset(partial=partial)
    
    def get_phase(self) -> AttackPhase:
        return self.attack_progress.current_phase
    
    def is_compromised(self) -> bool:
        return self.attack_progress.is_compromised


@dataclass
class AttackerState:
    attacker_id: str = "ATTACKER_0"
    total_scans: int = 0
    total_exploits: int = 0
    total_breach_attempts: int = 0
    current_target_idx: Optional[int] = None
    is_scanning: bool = False
    is_exploiting: bool = False
    is_breaching: bool = False
    steps_on_current_target: int = 0
    is_blocked: bool = False
    block_remaining_steps: int = 0


@dataclass
class MTDActionResult:
    shuffle_applied: bool = False
    port_hop_applied: bool = False
    decoy_activated: bool = False
    blacklist_updated: bool = False
    costs: Dict[str, float] = field(default_factory=dict)
    total_cost: float = 0.0
    progress_reset_count: int = 0
    entropy_gained: float = 0.0
    params: Dict[str, float] = field(default_factory=dict)


class StepOutcome(Enum):
    NOTHING = "nothing"
    SCAN_BLOCKED = "scan_blocked"
    SCAN_SUCCESS = "scan_success"
    SCAN_DECOY = "scan_decoy"
    EXPLOIT_BLOCKED = "exploit_blocked"
    EXPLOIT_SUCCESS = "exploit_success"
    EXPLOIT_DECOY = "exploit_decoy"
    BREACH_BLOCKED = "breach_blocked"
    BREACH_SUCCESS = "breach_success"


class MTDEnvironment(gym.Env):
    metadata = {"render_modes": ["human"], "render_fps": 4}
    
    def __init__(
        self,
        seed: Optional[int] = None,
        seeker_level: int = 1,
        config: MTDConfig = None,
        initial_state_mode: str = "partial_compromise",
        log_dir: Optional[str] = None,
    ):
        super().__init__()
        
        self.config = config or MTDConfig()
        self.rng = np.random.default_rng(seed)
        self.seeker_level = seeker_level
        self.seeker_profile = get_seeker_profile(seeker_level)
        self.config.initial_state.mode = initial_state_mode
        
        self.current_step = 0
        self.max_episode_steps = self.config.ppo.max_steps_per_episode
        
        self.endpoints: List[Endpoint] = []
        self._initialize_endpoints()
        
        self.attacker = AttackerState()
        self.blacklist: Dict[str, int] = {}
        self.active_decoy_count = 0
        self.decoy_engagement_steps = 0
        self.episode_metrics = EpisodeMetrics()
        self.energy_consumed = 0.0
        self.energy_budget = self.config.cost_model.energy_budget_per_episode
        self.cost_weight = self.config.reward_model.cost_weight_explore
        self.last_actions = {key: 0.5 for key in ACTION_PARAM_KEYS}
        
        self.action_space = spaces.Box(
            low=-1.0, high=1.0, shape=(len(ACTION_PARAM_KEYS),), dtype=np.float32
        )
        self.observation_space = spaces.Box(
            low=-10.0, high=10.0, shape=(len(FEATURE_KEYS),), dtype=np.float32
        )
        
        self.alert_history = deque(maxlen=100)
    
    def _initialize_endpoints(self):
        self.endpoints = []
        for i, (name, ip) in enumerate(self.config.topology.real_targets.items()):
            is_critical = name in ["TARGET_FC", "TARGET_GCS"]
            ep = Endpoint(ip=ip, name=name, is_decoy=False, is_critical=is_critical)
            initial_progress = self.config.initial_state.get_initial_progress(
                endpoint_idx=i, is_decoy=False
            )
            ep.attack_progress = initial_progress
            self.endpoints.append(ep)
        
        for name, ip in self.config.topology.decoy_targets.items():
            ep = Endpoint(ip=ip, name=name, is_decoy=True, is_critical=False)
            self.endpoints.append(ep)
    
    def _reset_counters(self):
        self.episode_metrics = EpisodeMetrics()
        self.energy_consumed = 0.0
        self.blacklist.clear()
        self.alert_history.clear()
        self.active_decoy_count = 0
        self.decoy_engagement_steps = 0
        self.attacker = AttackerState()
        self.last_actions = {key: 0.5 for key in ACTION_PARAM_KEYS}
    
    def set_reward_profile(self, profile: str):
        if profile == "explore":
            self.cost_weight = self.config.reward_model.cost_weight_explore
        elif profile == "exploit":
            self.cost_weight = self.config.reward_model.cost_weight_exploit
    
    def set_seeker_level(self, level: int):
        self.seeker_level = level
        self.seeker_profile = get_seeker_profile(level)
    
    def reset(self, seed: Optional[int] = None, options: Optional[Dict] = None) -> Tuple[np.ndarray, Dict]:
        if seed is not None:
            self.rng = np.random.default_rng(seed)
            super().reset(seed=seed)
        
        self.current_step = 0
        self._reset_counters()
        self._initialize_endpoints()
        
        obs = self._get_observation()
        info = self._get_info()
        return obs, info
    
    def step(self, action: np.ndarray) -> Tuple[np.ndarray, float, bool, bool, Dict]:
        self.current_step += 1
        
        mtd_result = self._apply_mtd_strategy(action)
        attacker_action = self._determine_attacker_action()
        outcome = self._resolve_interaction(mtd_result, attacker_action)
        self._update_state(outcome, mtd_result, attacker_action)
        reward = self._calculate_reward(outcome, mtd_result)
        
        terminated = self._check_termination()
        truncated = self.current_step >= self.max_episode_steps
        
        obs = self._get_observation()
        info = self._get_info()
        info.update({
            "outcome": outcome.value,
            "mtd_result": {
                "shuffle": mtd_result.shuffle_applied,
                "port_hop": mtd_result.port_hop_applied,
                "decoy": mtd_result.decoy_activated,
                "blacklist": mtd_result.blacklist_updated,
                "cost": mtd_result.total_cost,
            },
            "attacker": {
                "action": self._get_attacker_action_str(attacker_action),
                "target": attacker_action.get("target_name", "None"),
                "blocked": self.attacker.is_blocked,
            },
            "reward": reward,
        })
        
        for k, v in mtd_result.params.items():
            info[f"Params/{k}"] = v
        
        return obs, reward, terminated, truncated, info
    
    def _apply_mtd_strategy(self, action: np.ndarray) -> MTDActionResult:
        result = MTDActionResult()
        
        params = {}
        for i, key in enumerate(ACTION_PARAM_KEYS):
            params[key] = self._scale_action(action[i])
        
        result.params = params
        self.last_actions = params
        
        thresholds = self.config.thresholds
        cost_model = self.config.cost_model
        
        if params["shuffle_intensity"] >= thresholds.shuffle_activation:
            result.shuffle_applied = True
            self.episode_metrics.shuffle_count += 1
            for ep in self.endpoints:
                if not ep.is_decoy:
                    ep.reset_progress(partial=True)
                    result.progress_reset_count += 1
                    ep.last_shuffle_step = self.current_step
            result.entropy_gained = calculate_entropy(
                self.config.topology.shuffle_space_size
            ) * params["shuffle_intensity"]
        
        if params["port_hop_intensity"] >= thresholds.port_hop_activation:
            result.port_hop_applied = True
            self.episode_metrics.port_hop_count += 1
            for ep in self.endpoints:
                if not ep.is_decoy:
                    ep.attack_progress.discovery_progress *= (
                        1.0 - params["port_hop_intensity"] * 0.5
                    )
        
        if params["decoy_activation_level"] >= thresholds.decoy_activation:
            result.decoy_activated = True
            decoy_count = len([ep for ep in self.endpoints if ep.is_decoy])
            self.active_decoy_count = int(decoy_count * params["decoy_activation_level"])
        else:
            self.active_decoy_count = 0
        
        if params["blacklist_aggression"] >= thresholds.blacklist_activation:
            result.blacklist_updated = True
            self.episode_metrics.blacklist_actions += 1
            if len(self.alert_history) > 0:
                alert_rate = sum(self.alert_history) / len(self.alert_history)
                if alert_rate > (1.0 - params["blacklist_aggression"]):
                    duration = int(10 + params["blacklist_duration"] * 190)
                    self.blacklist[self.attacker.attacker_id] = duration
                    self.attacker.is_blocked = True
                    self.attacker.block_remaining_steps = duration
        
        result.costs = cost_model.calculate_total_cost(
            shuffle_intensity=params["shuffle_intensity"] if result.shuffle_applied else 0,
            port_hop_intensity=params["port_hop_intensity"] if result.port_hop_applied else 0,
            decoy_ratio=params["decoy_activation_level"],
            blacklist_aggression=params["blacklist_aggression"],
            num_high_decoys=min(2, self.active_decoy_count),
            num_low_decoys=max(0, self.active_decoy_count - 2),
        )
        result.total_cost = result.costs["total"]
        
        self.episode_metrics.total_mtd_cost += result.total_cost
        self.energy_consumed += result.costs.get("energy", 0)
        
        return result
    
    def _determine_attacker_action(self) -> Dict[str, Any]:
        action = {
            "is_scan": False,
            "is_exploit": False,
            "is_breach": False,
            "target_idx": None,
            "target_name": None,
        }
        
        if self.attacker.is_blocked:
            self.attacker.block_remaining_steps -= 1
            if self.attacker.block_remaining_steps <= 0:
                self.attacker.is_blocked = False
                self._attacker_change_ip()
            return action
        
        profile = self.seeker_profile
        target_idx = self._select_target()
        if target_idx is None:
            return action
        
        target = self.endpoints[target_idx]
        action["target_idx"] = target_idx
        action["target_name"] = target.name
        
        progress = target.attack_progress
        
        scan_interval = max(1, int(5 / (profile["scan_effort"] + 0.1)))
        if self.current_step % scan_interval == 0:
            action["is_scan"] = True
            self.attacker.total_scans += 1
            self.episode_metrics.total_scan_attempts += 1
        
        if progress.discovery_progress >= progress.DISCOVERY_THRESHOLD * 0.7:
            exploit_threshold = 1.0 - profile["exploit_prob"]
            if progress.discovery_progress >= exploit_threshold:
                action["is_exploit"] = True
                self.attacker.total_exploits += 1
                self.episode_metrics.total_exploit_attempts += 1
        
        if progress.exploitation_progress >= progress.EXPLOITATION_THRESHOLD * 0.8:
            breach_threshold = 1.0 - profile["breach_prob"]
            if progress.exploitation_progress >= breach_threshold:
                action["is_breach"] = True
                self.attacker.total_breach_attempts += 1
                self.episode_metrics.total_breach_attempts += 1
        
        return action
    
    def _select_target(self) -> Optional[int]:
        if not self.endpoints:
            return None
        
        profile = self.seeker_profile
        attack_bias = profile["attack_bias"]
        
        scores = []
        for i, ep in enumerate(self.endpoints):
            score = 0.0
            if ep.is_decoy:
                if self.active_decoy_count > 0:
                    score = (1.0 - attack_bias) * 0.5
                else:
                    score = 0.0
            else:
                progress_score = (
                    ep.attack_progress.discovery_progress * 0.3 +
                    ep.attack_progress.exploitation_progress * 0.5 +
                    (1.0 if ep.is_critical else 0.5) * 0.2
                )
                score = 0.3 + progress_score * 0.7
            scores.append(max(0.01, score))
        
        scores = np.array(scores)
        probs = np.exp(scores * 3) / np.sum(np.exp(scores * 3))
        return int(self.rng.choice(len(self.endpoints), p=probs))
    
    def _attacker_change_ip(self):
        old_id = self.attacker.attacker_id
        new_idx = self.rng.integers(0, 100)
        self.attacker.attacker_id = f"ATTACKER_{new_idx}"
        if old_id in self.blacklist:
            del self.blacklist[old_id]
    
    def _resolve_interaction(self, mtd_result: MTDActionResult, attacker_action: Dict) -> StepOutcome:
        if self.attacker.is_blocked:
            if attacker_action["is_scan"]:
                return StepOutcome.SCAN_BLOCKED
            return StepOutcome.NOTHING
        
        target_idx = attacker_action.get("target_idx")
        if target_idx is None:
            return StepOutcome.NOTHING
        
        target = self.endpoints[target_idx]
        
        if target.is_decoy and self.active_decoy_count > 0:
            self.episode_metrics.decoy_engagement_count += 1
            self.decoy_engagement_steps += 1
            if attacker_action["is_exploit"]:
                return StepOutcome.EXPLOIT_DECOY
            elif attacker_action["is_scan"]:
                return StepOutcome.SCAN_DECOY
            return StepOutcome.NOTHING
        
        progress = target.attack_progress
        shuffle_recency = self.current_step - target.last_shuffle_step
        shuffle_protection = max(0, 1.0 - shuffle_recency / 10.0)
        block_threshold = self.last_actions.get("blacklist_aggression", 0) * 0.5
        
        if attacker_action["is_breach"]:
            self.episode_metrics.total_breach_attempts += 1
            effective_defense = shuffle_protection + block_threshold
            if progress.exploitation_progress >= progress.EXPLOITATION_THRESHOLD:
                if effective_defense < 0.3:
                    progress.compromise_progress += 0.4
                    if progress.is_compromised:
                        self.episode_metrics.successful_breaches += 1
                        return StepOutcome.BREACH_SUCCESS
                return StepOutcome.BREACH_BLOCKED
            return StepOutcome.BREACH_BLOCKED
        
        if attacker_action["is_exploit"]:
            if shuffle_protection > 0.5:
                return StepOutcome.EXPLOIT_BLOCKED
            progress_gain = self.seeker_profile["exploit_prob"] * 0.2
            progress.exploitation_progress = min(1.0, progress.exploitation_progress + progress_gain)
            if progress.exploitation_progress >= progress.EXPLOITATION_THRESHOLD:
                return StepOutcome.EXPLOIT_SUCCESS
            return StepOutcome.NOTHING
        
        if attacker_action["is_scan"]:
            if mtd_result.shuffle_applied:
                return StepOutcome.SCAN_BLOCKED
            progress_gain = self.seeker_profile["scan_effort"] * 0.15
            progress.discovery_progress = min(1.0, progress.discovery_progress + progress_gain)
            if progress.discovery_progress >= progress.DISCOVERY_THRESHOLD:
                return StepOutcome.SCAN_SUCCESS
            return StepOutcome.NOTHING
        
        return StepOutcome.NOTHING
    
    def _update_state(self, outcome: StepOutcome, mtd_result: MTDActionResult, attacker_action: Dict):
        is_suspicious = outcome in [
            StepOutcome.SCAN_SUCCESS,
            StepOutcome.EXPLOIT_SUCCESS,
            StepOutcome.BREACH_SUCCESS,
        ]
        self.alert_history.append(1 if is_suspicious else 0)
        
        expired_ips = []
        for ip, remaining in self.blacklist.items():
            self.blacklist[ip] = remaining - 1
            if self.blacklist[ip] <= 0:
                expired_ips.append(ip)
        for ip in expired_ips:
            del self.blacklist[ip]
        
        if outcome == StepOutcome.BREACH_SUCCESS:
            self.episode_metrics.successful_breaches += 1
        
        if outcome in [StepOutcome.SCAN_DECOY, StepOutcome.EXPLOIT_DECOY]:
            self.episode_metrics.decoy_time_absorbed += 1
    
    def _calculate_reward(self, outcome: StepOutcome, mtd_result: MTDActionResult) -> float:
        reward_model = self.config.reward_model
        reward = 0.0
        
        outcome_rewards = {
            StepOutcome.SCAN_BLOCKED: reward_model.reward_discovery_blocked,
            StepOutcome.EXPLOIT_BLOCKED: reward_model.reward_exploitation_blocked,
            StepOutcome.BREACH_BLOCKED: reward_model.reward_breach_blocked,
            StepOutcome.SCAN_SUCCESS: reward_model.penalty_discovery_success,
            StepOutcome.EXPLOIT_SUCCESS: reward_model.penalty_exploitation_success,
            StepOutcome.BREACH_SUCCESS: reward_model.penalty_breach_success,
            StepOutcome.SCAN_DECOY: reward_model.reward_decoy_scan,
            StepOutcome.EXPLOIT_DECOY: reward_model.reward_decoy_exploit,
            StepOutcome.NOTHING: reward_model.reward_survival_per_step,
        }
        
        reward += outcome_rewards.get(outcome, 0.0)
        reward -= mtd_result.total_cost * self.cost_weight
        
        if reward_model.enable_shaping and mtd_result.shuffle_applied:
            reward += reward_model.shaping_coefficient * mtd_result.progress_reset_count * 0.5
        
        return float(reward)
    
    def _get_observation(self) -> np.ndarray:
        obs = {}
        
        obs["cti_alert_rate"] = sum(self.alert_history) / max(1, len(self.alert_history))
        obs["blacklist_size_ratio"] = min(1.0, len(self.blacklist) / 20.0)
        obs["service_uptime_ratio"] = 1.0 - (
            self.episode_metrics.shuffle_count / max(1, self.current_step)
        )
        
        real_endpoints = [ep for ep in self.endpoints if not ep.is_decoy]
        if real_endpoints:
            obs["avg_discovery_progress"] = np.mean([
                ep.attack_progress.discovery_progress for ep in real_endpoints
            ])
            obs["avg_exploitation_progress"] = np.mean([
                ep.attack_progress.exploitation_progress for ep in real_endpoints
            ])
            obs["avg_compromise_progress"] = np.mean([
                ep.attack_progress.compromise_progress for ep in real_endpoints
            ])
            obs["max_compromise_progress"] = max([
                ep.attack_progress.compromise_progress for ep in real_endpoints
            ])
        else:
            obs["avg_discovery_progress"] = 0.0
            obs["avg_exploitation_progress"] = 0.0
            obs["avg_compromise_progress"] = 0.0
            obs["max_compromise_progress"] = 0.0
        
        total_attacks = max(1, self.episode_metrics.total_exploit_attempts)
        obs["decoy_engagement_rate"] = self.episode_metrics.decoy_engagement_count / total_attacks
        obs["decoy_time_absorbed_ratio"] = self.decoy_engagement_steps / max(1, self.current_step)
        
        obs["energy_remaining_ratio"] = max(0, 1.0 - (self.energy_consumed / self.energy_budget))
        obs["shuffle_entropy_bits"] = (
            self.config.topology.shuffle_entropy_bits * 
            self.last_actions.get("shuffle_intensity", 0)
        )
        
        obs["estimated_scan_rate"] = self.attacker.total_scans / max(1, self.current_step)
        obs["estimated_attack_sophistication"] = self.seeker_level / 4.0
        
        obs["last_shuffle_intensity"] = self.last_actions.get("shuffle_intensity", 0.5)
        obs["last_port_hop_intensity"] = self.last_actions.get("port_hop_intensity", 0.5)
        obs["last_decoy_ratio"] = self.last_actions.get("decoy_activation_level", 0.5)
        obs["last_blacklist_aggression"] = self.last_actions.get("blacklist_aggression", 0.5)
        
        obs_vec = [obs.get(key, 0.0) for key in FEATURE_KEYS]
        return np.array(obs_vec, dtype=np.float32)
    
    def _get_info(self) -> Dict:
        total_attacks = (
            self.episode_metrics.total_exploit_attempts +
            self.episode_metrics.total_breach_attempts
        )
        blocked = (
            self.episode_metrics.total_exploit_attempts -
            self.episode_metrics.successful_breaches
        )
        
        if total_attacks > 0:
            self.episode_metrics.defense_success_rate = blocked / total_attacks
            self.episode_metrics.breach_prevention_rate = 1.0 - (
                self.episode_metrics.successful_breaches / 
                max(1, self.episode_metrics.total_breach_attempts)
            )
        
        self.episode_metrics.avg_cost_per_step = (
            self.episode_metrics.total_mtd_cost / max(1, self.current_step)
        )
        self.episode_metrics.energy_consumed = self.energy_consumed
        self.episode_metrics.avg_config_entropy = (
            self.config.topology.shuffle_entropy_bits *
            self.last_actions.get("shuffle_intensity", 0)
        )
        
        return self.episode_metrics.to_dict()
    
    def _check_termination(self) -> bool:
        for ep in self.endpoints:
            if ep.is_critical and ep.is_compromised():
                return True
        if self.energy_consumed >= self.energy_budget:
            return True
        return False
    
    @staticmethod
    def _scale_action(action: float, low: float = 0.0, high: float = 1.0) -> float:
        return low + (action + 1.0) * 0.5 * (high - low)
    
    def _get_attacker_action_str(self, action: Dict) -> str:
        if action.get("is_breach"):
            return "Breach"
        elif action.get("is_exploit"):
            return "Exploit"
        elif action.get("is_scan"):
            return "Scan"
        return "None"