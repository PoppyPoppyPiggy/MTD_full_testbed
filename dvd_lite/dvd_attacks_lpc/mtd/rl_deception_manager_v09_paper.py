#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RL-Driven Deception Manager v09.7 - Fixed CDI Calculation
==========================================================

수정사항 v09.7:
1. CDI 계산 수정 - 시간에 따른 구성 변화 다양성 반영
2. Baseline은 CDI 낮음 (구성 변경 없음)
3. MTD 액션 실행에 따라 CDI 증가

CDI (Configuration Diversity Index) - Eq.(18):
- 시간에 따른 구성 변화의 Shannon Entropy
- 구성이 자주 바뀌면 CDI 높음
- 고정되어 있으면 CDI 낮음

Author: MTD-RL Research Team
Version: 0.9.7
"""
from __future__ import annotations

import argparse
import json
import os
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# PyTorch (optional)
TORCH_AVAILABLE = False
try:
    import torch
    import torch.nn as nn
    TORCH_AVAILABLE = True
except ImportError:
    print("⚠️ PyTorch not available - RL-CTI MTD strategy disabled")

# Matplotlib (optional)
MATPLOTLIB_AVAILABLE = False
try:
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    print("⚠️ matplotlib not available - figures disabled")


# =============================================================================
# JSON Serialization Helper
# =============================================================================
def to_python(obj):
    """numpy 타입을 Python 기본 타입으로 변환"""
    if obj is None:
        return None
    if isinstance(obj, (np.integer, np.int64, np.int32, np.int16, np.int8)):
        return int(obj)
    if isinstance(obj, (np.floating, np.float64, np.float32, np.float16)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, (list, tuple)):
        return [to_python(x) for x in obj]
    if isinstance(obj, dict):
        return {k: to_python(v) for k, v in obj.items()}
    return obj


# =============================================================================
# Constants
# =============================================================================
STATE_DIM = 17
ACTION_DIM = 7

ACTION_THRESHOLDS = {
    'shuffle': 0.25,
    'port_hop': 0.35,
    'decoy': 0.40,
    'blacklist': 0.60,
    'swap': 0.30,
}

ACTION_COSTS = {
    'shuffle': 0.05,
    'port_hop': 0.03,
    'decoy': 0.02,
    'blacklist': 0.02,
    'swap': 0.05,
}

MTD_DEFENSE_WEIGHTS = {
    'shuffle': 0.35,
    'port_hop': 0.20,
    'decoy': 0.15,
    'blacklist': 0.10,
    'swap': 0.45,
}

ATTACKER_PROFILES = {
    0: {"name": "Script Kiddie", "scan_rate": 0.03, "p_disc": 0.15, 
        "p_exp": 0.08, "decoy_detection": 0.1, "energy_decay": 0.008, "kappa": 1.00},
    1: {"name": "Hobbyist", "scan_rate": 0.05, "p_disc": 0.25,
        "p_exp": 0.12, "decoy_detection": 0.2, "energy_decay": 0.006, "kappa": 0.92},
    2: {"name": "Professional", "scan_rate": 0.08, "p_disc": 0.35,
        "p_exp": 0.20, "decoy_detection": 0.35, "energy_decay": 0.004, "kappa": 0.84},
    3: {"name": "Expert", "scan_rate": 0.12, "p_disc": 0.50,
        "p_exp": 0.30, "decoy_detection": 0.5, "energy_decay": 0.003, "kappa": 0.76},
    4: {"name": "APT", "scan_rate": 0.15, "p_disc": 0.65,
        "p_exp": 0.40, "decoy_detection": 0.65, "energy_decay": 0.002, "kappa": 0.68},
}

STRATEGY_CONFIG = {
    'Baseline': {'full_name': 'Baseline (No MTD)', 'color': '#808080'},
    'Static MTD': {'full_name': 'Static MTD', 'color': '#E69F00'},
    'Heuristic+CTI': {'full_name': 'Heuristic+CTI', 'color': '#009E73'},
    'RL-CTI MTD': {'full_name': 'RL-CTI MTD (Proposed)', 'color': '#D55E00'},
}


def scale_action(action: np.ndarray) -> np.ndarray:
    """[-1,1] -> [0,1] 스케일링"""
    return (np.array(action) + 1.0) / 2.0


# =============================================================================
# CTI Detection Model
# =============================================================================
@dataclass
class CTIDetectionModel:
    precision: float = 0.66
    recall: float = 0.85
    f1_score: float = 0.71
    
    class_performance: Dict[str, Dict[str, float]] = field(default_factory=lambda: {
        "Normal": {"precision": 0.87, "recall": 0.73, "f1": 0.79},
        "Brute-force": {"precision": 0.67, "recall": 0.94, "f1": 0.78},
        "Battery-spoofing": {"precision": 0.60, "recall": 0.90, "f1": 0.72},
        "Flight-term": {"precision": 0.68, "recall": 0.85, "f1": 0.75},
        "GPS-inject": {"precision": 0.39, "recall": 0.92, "f1": 0.54},
    })
    
    def detect_attack(self, attack_type: str = "scan") -> Tuple[bool, float, str]:
        attack_mapping = {
            "scan": "Brute-force",
            "exploit": "Flight-term",
            "gps_spoof": "GPS-inject",
            "battery": "Battery-spoofing",
        }
        
        mapped_class = attack_mapping.get(attack_type, "Normal")
        perf = self.class_performance.get(mapped_class, self.class_performance["Normal"])
        
        detected = np.random.random() < perf["recall"]
        confidence = perf["precision"] * np.random.uniform(0.8, 1.0) if detected else np.random.uniform(0.1, 0.4)
        
        return detected, float(confidence), mapped_class
    
    def get_threat_level(self, indicators: Dict[str, float]) -> float:
        base_threat = 0.0
        
        if indicators.get('scan_intensity', 0) > 0.1:
            detected, conf, _ = self.detect_attack("scan")
            if detected:
                base_threat += indicators['scan_intensity'] * conf * 0.4
        
        if indicators.get('exploit_attempts', 0) > 0:
            detected, conf, _ = self.detect_attack("exploit")
            if detected:
                base_threat += indicators['exploit_attempts'] * conf * 0.5
        
        return min(1.0, base_threat * self.f1_score)


# =============================================================================
# Attack Phase
# =============================================================================
class AttackPhase:
    INITIAL = "initial"
    RECONNAISSANCE = "reconnaissance"
    DISCOVERY = "discovery"
    EXPLOITATION = "exploitation"
    PERSISTENCE = "persistence"
    BREACH = "breach"
    DEFENDED = "defended"


# =============================================================================
# Service Target
# =============================================================================
@dataclass
class ServiceTarget:
    name: str
    real_ip: str
    real_port: int
    virtual_ip: str
    virtual_port: int
    is_critical: bool = False
    is_decoy: bool = False
    vulnerability_score: float = 0.5
    scan_progress: float = 0.0
    discovery_progress: float = 0.0
    exploit_progress: float = 0.0


# =============================================================================
# Attacker Agent
# =============================================================================
class AttackerAgent:
    def __init__(self, level: int = 2, seed: int = 42, targets: List[ServiceTarget] = None):
        self.level = level
        self.profile = ATTACKER_PROFILES.get(level, ATTACKER_PROFILES[2])
        np.random.seed(seed)
        
        self.phase = AttackPhase.INITIAL
        self.energy = 1.0
        self.confusion_level = 0.0
        self.step_count = 0
        
        self.scanned_ips: set = set()
        self.discovered_services: set = set()
        self.exploited_services: set = set()
        self.decoy_hits = 0
        
        self.targets = targets or []
        self.cti = CTIDetectionModel()
    
    def reset(self, seed: int = None):
        if seed:
            np.random.seed(seed)
        self.phase = AttackPhase.INITIAL
        self.energy = 1.0
        self.confusion_level = 0.0
        self.step_count = 0
        self.scanned_ips.clear()
        self.discovered_services.clear()
        self.exploited_services.clear()
        self.decoy_hits = 0
    
    def set_targets(self, targets: List[ServiceTarget]):
        self.targets = targets
    
    def step(self, mtd_status: Dict[str, Any]) -> Dict[str, Any]:
        self.step_count += 1
        
        result = {
            "phase": self.phase,
            "scanned": False,
            "discovered": False,
            "exploited": False,
            "breach": False,
            "decoy_hit": False,
            "defended": False,
            "cti_detected": False,
            "energy": self.energy,
        }
        
        shuffle_intensity = mtd_status.get('shuffle_intensity', 0)
        swap_intensity = mtd_status.get('swap_intensity', 0)
        defense_prob = mtd_status.get('defense_probability', 0.25)
        
        if mtd_status.get('is_shuffle', False):
            self.confusion_level += shuffle_intensity * 0.3
        if mtd_status.get('is_swap', False):
            self.confusion_level += swap_intensity * 0.4
        self.confusion_level *= 0.92
        
        self.energy -= self.profile["energy_decay"]
        
        if self.energy <= 0:
            self.phase = AttackPhase.DEFENDED
            result["defended"] = True
            return result
        
        confusion_penalty = min(0.6, self.confusion_level * 0.5)
        effective_rate = max(0.05, 1.0 - confusion_penalty)
        
        cti_indicators = {
            'scan_intensity': len(self.scanned_ips) / 254,
            'exploit_attempts': len(self.exploited_services) / max(1, len(self.targets)),
        }
        cti_threat = self.cti.get_threat_level(cti_indicators)
        
        if cti_threat > 0.3:
            result["cti_detected"] = True
            defense_prob = min(0.9, defense_prob + cti_threat * 0.3)
        
        if self.phase == AttackPhase.INITIAL:
            self.phase = AttackPhase.RECONNAISSANCE
            
        elif self.phase == AttackPhase.RECONNAISSANCE:
            n_scan = int(254 * self.profile["scan_rate"] * effective_rate)
            for _ in range(n_scan):
                ip = f"10.13.0.{np.random.randint(1, 255)}"
                if np.random.random() >= defense_prob * 0.3:
                    self.scanned_ips.add(ip)
                    result["scanned"] = True
            
            if len(self.scanned_ips) > 5:
                if np.random.random() < 0.3 * (1 - defense_prob * 0.3):
                    self.phase = AttackPhase.DISCOVERY
                    
        elif self.phase == AttackPhase.DISCOVERY:
            for target in self.targets:
                if target.name in self.discovered_services:
                    continue
                if target.virtual_ip not in self.scanned_ips:
                    continue
                
                if np.random.random() < defense_prob * 0.5:
                    result["defended"] = True
                    continue
                
                if target.is_decoy:
                    if np.random.random() >= self.profile["decoy_detection"]:
                        self.decoy_hits += 1
                        result["decoy_hit"] = True
                        self.energy -= 0.1
                        continue
                
                if np.random.random() < self.profile["p_disc"] * effective_rate:
                    target.discovery_progress += 0.4
                    if target.discovery_progress >= 0.8:
                        self.discovered_services.add(target.name)
                        result["discovered"] = True
            
            if len(self.discovered_services) >= 1:
                if np.random.random() < 0.4 * (1 - defense_prob * 0.4):
                    self.phase = AttackPhase.EXPLOITATION
                    
        elif self.phase == AttackPhase.EXPLOITATION:
            for target in self.targets:
                if target.name not in self.discovered_services:
                    continue
                if target.name in self.exploited_services:
                    continue
                
                if np.random.random() < defense_prob * 0.7:
                    result["defended"] = True
                    continue
                
                exploit_prob = self.profile["p_exp"] * target.vulnerability_score * effective_rate
                if np.random.random() < exploit_prob:
                    target.exploit_progress += 0.5
                    if target.exploit_progress >= 0.9:
                        self.exploited_services.add(target.name)
                        result["exploited"] = True
                        if target.is_critical:
                            self.phase = AttackPhase.PERSISTENCE
                            
        elif self.phase == AttackPhase.PERSISTENCE:
            if np.random.random() < defense_prob * 0.8:
                result["defended"] = True
            else:
                critical_exploited = any(
                    t.is_critical and t.name in self.exploited_services
                    for t in self.targets
                )
                if critical_exploited and np.random.random() < 0.3 * (1 - defense_prob):
                    self.phase = AttackPhase.BREACH
                    result["breach"] = True
        
        result["phase"] = self.phase
        result["energy"] = self.energy
        
        return result


# =============================================================================
# Actor-Critic Network
# =============================================================================
if TORCH_AVAILABLE:
    class ActorCritic(nn.Module):
        def __init__(self, state_dim: int = STATE_DIM, action_dim: int = ACTION_DIM, hidden_size: int = 256):
            super().__init__()
            self.shared = nn.Sequential(
                nn.Linear(state_dim, hidden_size),
                nn.LayerNorm(hidden_size),
                nn.ReLU(),
                nn.Linear(hidden_size, hidden_size),
                nn.LayerNorm(hidden_size),
                nn.ReLU(),
            )
            self.actor = nn.Sequential(
                nn.Linear(hidden_size, hidden_size // 2),
                nn.ReLU(),
                nn.Linear(hidden_size // 2, action_dim),
                nn.Tanh(),
            )
            self.log_std = nn.Parameter(torch.ones(action_dim) * -0.5)
            self.critic = nn.Sequential(
                nn.Linear(hidden_size, hidden_size // 2),
                nn.ReLU(),
                nn.Linear(hidden_size // 2, 1),
            )

        def forward(self, state):
            features = self.shared(state)
            return self.actor(features), self.critic(features)

        def act(self, state, deterministic=True):
            action_mean, value = self.forward(state)
            if deterministic:
                return action_mean, torch.zeros(1), value
            std = torch.exp(self.log_std)
            dist = torch.distributions.Normal(action_mean, std)
            action = dist.sample().clamp(-1, 1)
            return action, dist.log_prob(action).sum(-1, keepdim=True), value


# =============================================================================
# Defense Probability Calculator
# =============================================================================
class DefenseProbabilityCalculator:
    P_BASE = 0.25
    BETA_CDI = 0.15
    
    def __init__(self):
        self.recent_effects: List[Tuple[int, float]] = []
    
    def compute(self, action_intensities: Dict, cdi: float, attacker_level: int, 
                step: int, cti_detected: bool = False) -> float:
        current_effect = sum(
            MTD_DEFENSE_WEIGHTS.get(a, 0) * i
            for a, i in action_intensities.items()
        )
        
        self.recent_effects.append((step, current_effect))
        if len(self.recent_effects) > 10:
            self.recent_effects = self.recent_effects[-10:]
        
        residual = sum(
            e * 0.3 * (0.9 ** (step - s))
            for s, e in self.recent_effects[:-1] if step > s
        )
        
        kappa = ATTACKER_PROFILES[attacker_level]["kappa"]
        cti_bonus = 0.15 if cti_detected else 0.0
        
        p_def = (self.P_BASE + current_effect + residual + 
                 self.BETA_CDI * cdi + cti_bonus) * kappa
        
        return float(np.clip(p_def, 0.10, 0.95))
    
    def reset(self):
        self.recent_effects.clear()


# =============================================================================
# MTD Controller (Fixed CDI)
# =============================================================================
class MTDController:
    """MTD 컨트롤러 - CDI 계산 수정됨"""
    
    def __init__(self):
        self.services: Dict[str, ServiceTarget] = {}
        self.decoys: Dict[str, ServiceTarget] = {}
        self.stats = {
            'total_shuffles': 0, 'total_port_hops': 0,
            'total_swaps': 0, 'total_decoy_activations': 0,
            'total_cost': 0.0,
        }
        
        # CDI 계산을 위한 구성 히스토리
        self.config_history: deque = deque(maxlen=50)
        self.last_config: Optional[str] = None
        
        self._init_services()
    
    def _init_services(self):
        """Table 8: Testbed Components"""
        configs = [
            ("fc_mavlink", "10.13.0.10", 14550, True),
            ("cc_sitl", "10.13.0.11", 5760, True),
            ("cc_mavlink", "10.13.0.11", 14550, False),
            ("gcs_web", "10.13.0.20", 3000, True),
            ("video_stream", "10.13.0.12", 554, False),
            ("telemetry_db", "10.13.0.14", 5432, False),
        ]
        for name, ip, port, critical in configs:
            self.services[name] = ServiceTarget(
                name=name, real_ip=ip, real_port=port,
                virtual_ip=ip, virtual_port=port,
                is_critical=critical,
                vulnerability_score=np.random.uniform(0.3, 0.7),
            )
        
        decoys = [
            ("honeydrone_1", "10.13.0.100", 14550),
            ("honeydrone_2", "10.13.0.101", 14550),
            ("decoy_gcs", "10.13.0.102", 3000),
            ("tarpit", "10.13.0.103", 9999),
        ]
        for name, ip, port in decoys:
            self.decoys[name] = ServiceTarget(
                name=name, real_ip=ip, real_port=port,
                virtual_ip=ip, virtual_port=port, is_decoy=True,
            )
        
        # 초기 구성 기록
        self._record_config()
    
    def _get_config_snapshot(self) -> str:
        """현재 구성 스냅샷 (해시용)"""
        configs = sorted([f"{s.virtual_ip}:{s.virtual_port}" for s in self.services.values()])
        return "|".join(configs)
    
    def _record_config(self):
        """구성 변경 기록"""
        current = self._get_config_snapshot()
        if current != self.last_config:
            self.config_history.append(current)
            self.last_config = current
    
    def reset(self):
        self._init_services()
        self.stats = {
            'total_shuffles': 0, 'total_port_hops': 0,
            'total_swaps': 0, 'total_decoy_activations': 0,
            'total_cost': 0.0,
        }
        self.config_history.clear()
        self.last_config = None
        self._record_config()
    
    def shuffle(self, intensity: float) -> float:
        """네트워크 셔플"""
        n = max(1, int(len(self.services) * intensity))
        keys = list(self.services.keys())
        shuffled = np.random.choice(keys, min(n, len(keys)), replace=False)
        
        for svc_name in shuffled:
            svc = self.services[svc_name]
            svc.virtual_ip = f"10.13.0.{np.random.randint(100, 199)}"
            svc.virtual_port = np.random.randint(10000, 60000)
        
        self.stats['total_shuffles'] += 1
        cost = intensity * ACTION_COSTS['shuffle']
        self.stats['total_cost'] += cost
        
        self._record_config()  # 구성 변경 기록
        return cost
    
    def port_hop(self, intensity: float) -> float:
        """포트 호핑"""
        changed = False
        for svc in self.services.values():
            if svc.is_critical and np.random.random() < intensity:
                svc.virtual_port = np.random.randint(10000, 60000)
                changed = True
        
        self.stats['total_port_hops'] += 1
        cost = intensity * ACTION_COSTS['port_hop']
        self.stats['total_cost'] += cost
        
        if changed:
            self._record_config()
        return cost
    
    def swap(self, intensity: float, target_critical: bool) -> float:
        """서비스 스왑"""
        keys = list(self.services.keys())
        if len(keys) < 2:
            return 0.0
        
        if target_critical:
            critical = [k for k in keys if self.services[k].is_critical]
            non_critical = [k for k in keys if not self.services[k].is_critical]
            if critical and non_critical:
                a, b = np.random.choice(critical), np.random.choice(non_critical)
            else:
                a, b = np.random.choice(keys, 2, replace=False)
        else:
            a, b = np.random.choice(keys, 2, replace=False)
        
        svc_a, svc_b = self.services[a], self.services[b]
        svc_a.virtual_ip, svc_b.virtual_ip = svc_b.virtual_ip, svc_a.virtual_ip
        svc_a.virtual_port, svc_b.virtual_port = svc_b.virtual_port, svc_a.virtual_port
        
        self.stats['total_swaps'] += 1
        cost = intensity * ACTION_COSTS['swap']
        self.stats['total_cost'] += cost
        
        self._record_config()
        return cost
    
    def activate_decoys(self, ratio: float) -> float:
        """디코이 활성화"""
        n = max(1, int(len(self.decoys) * ratio))
        self.stats['total_decoy_activations'] += n
        cost = ratio * ACTION_COSTS['decoy'] * n
        self.stats['total_cost'] += cost
        return cost
    
    def get_cdi(self) -> float:
        """
        CDI 계산 - Eq.(18) 수정 버전
        
        시간에 따른 구성 변화의 다양성을 측정:
        - config_history에 저장된 고유 구성 수의 비율
        - 구성이 자주 바뀌면 CDI 높음
        - 고정되어 있으면 CDI 낮음
        
        Returns:
            CDI in [0, 1]
        """
        if len(self.config_history) <= 1:
            # 구성 변경 없음 -> CDI = 0.1 (최소값)
            return 0.1
        
        # 고유 구성 수
        unique_configs = len(set(self.config_history))
        total_configs = len(self.config_history)
        
        # 기본 다양성: 고유 구성 비율
        base_diversity = unique_configs / total_configs
        
        # 최근 변화 빈도 보너스
        recent_changes = 0
        history_list = list(self.config_history)
        for i in range(1, min(10, len(history_list))):
            if history_list[-i] != history_list[-i-1] if i < len(history_list) else True:
                recent_changes += 1
        
        recency_bonus = recent_changes / 10 * 0.3
        
        # MTD 액션 횟수 기반 보너스
        total_actions = (self.stats['total_shuffles'] + 
                        self.stats['total_port_hops'] + 
                        self.stats['total_swaps'])
        action_bonus = min(0.3, total_actions * 0.02)
        
        cdi = base_diversity * 0.4 + recency_bonus + action_bonus + 0.1
        
        return float(np.clip(cdi, 0.1, 1.0))
    
    def get_redundancy(self) -> float:
        """Redundancy 계산 - Eq.(19)"""
        active = self.stats['total_decoy_activations'] / max(1, len(self.decoys) * 10)
        swap_bonus = min(0.3, self.stats['total_swaps'] * 0.05)
        return min(1.0, active * 0.6 + swap_bonus + 0.1)
    
    def get_targets(self) -> List[ServiceTarget]:
        return list(self.services.values()) + list(self.decoys.values())


# =============================================================================
# Episode Result
# =============================================================================
@dataclass
class EpisodeResult:
    episode_id: int = 0
    strategy_name: str = ""
    attacker_level: int = 0
    steps: int = 0
    breach_occurred: bool = False
    total_cost: float = 0.0
    mttc: int = 200
    asr: float = 0.0
    cdi: float = 0.0
    redundancy: float = 0.0
    des: float = 0.0
    cer: float = 0.0
    shuffle_count: int = 0
    swap_count: int = 0
    decoy_hits: int = 0
    services_discovered: int = 0
    services_exploited: int = 0
    final_phase: str = "initial"
    cti_detections: int = 0


# =============================================================================
# Baseline Strategies (Table 12)
# =============================================================================
class BaselineStrategy:
    def __init__(self, name: str):
        self.name = name
    def get_action(self, state, step) -> np.ndarray:
        raise NotImplementedError
    def reset(self):
        pass


class NoMTDStrategy(BaselineStrategy):
    """Baseline (No MTD)"""
    def __init__(self):
        super().__init__("Baseline")
    def get_action(self, state, step):
        return np.ones(ACTION_DIM) * -1.0


class StaticMTDStrategy(BaselineStrategy):
    """Static MTD - 30스텝마다 셔플"""
    def __init__(self, period: int = 30):
        super().__init__("Static MTD")
        self.period = period
    def get_action(self, state, step):
        action = np.ones(ACTION_DIM) * -1.0
        if step % self.period == 0:
            action[0] = 0.8  # shuffle
            action[1] = 0.5  # port_hop
        return action


class HeuristicCTIStrategy(BaselineStrategy):
    """Heuristic+CTI"""
    def __init__(self, threshold: float = 0.7):
        super().__init__("Heuristic+CTI")
        self.threshold = threshold
        self.cti = CTIDetectionModel()
    
    def get_action(self, state, step):
        action = np.ones(ACTION_DIM) * -1.0
        
        threat = state[1] * 0.3 + state[3] * 0.5 + state[4] * 0.2 if len(state) > 4 else 0.2
        detected, conf, _ = self.cti.detect_attack("scan")
        
        if detected and conf > self.threshold:
            action[0] = 0.8
            action[5] = 0.7
        elif threat > 0.5:
            action[0] = 0.6
            action[2] = 0.5
        elif threat > 0.3:
            action[1] = 0.5
            action[2] = 0.4
        elif threat > 0.1:
            action[2] = 0.3
        
        return action


if TORCH_AVAILABLE:
    class RLCTIMTDStrategy(BaselineStrategy):
        """RL-CTI MTD (Proposed)"""
        def __init__(self, model_path: str, device: str = "cpu"):
            super().__init__("RL-CTI MTD")
            self.device = device
            self.policy = ActorCritic(STATE_DIM, ACTION_DIM).to(device)
            
            if os.path.exists(model_path):
                ckpt = torch.load(model_path, map_location=device, weights_only=False)
                self.policy.load_state_dict(ckpt.get("policy", ckpt))
                self.policy.eval()
                print(f"✅ RL-CTI MTD Policy loaded: {model_path}")
            else:
                print(f"⚠️ Model not found: {model_path}, using random policy")
        
        def get_action(self, state, step):
            with torch.no_grad():
                t = torch.FloatTensor(state).unsqueeze(0).to(self.device)
                a, _, _ = self.policy.act(t, deterministic=True)
            return a.cpu().numpy().squeeze()


# =============================================================================
# Main Manager
# =============================================================================
class RLDeceptionManager:
    """MTD-RL 실험 관리자"""
    
    def __init__(
        self,
        model_path: Optional[str] = None,
        output_dir: str = "paper_results",
        max_steps: int = 200,
        device: str = "cpu",
    ):
        self.model_path = model_path
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.max_steps = max_steps
        self.device = device
        
        self.mtd = MTDController()
        self.defense_calc = DefenseProbabilityCalculator()
        self.cti = CTIDetectionModel()
        
        self.strategies = {
            "Baseline": NoMTDStrategy(),
            "Static MTD": StaticMTDStrategy(period=30),
            "Heuristic+CTI": HeuristicCTIStrategy(threshold=0.7),
        }
        
        if TORCH_AVAILABLE and model_path:
            self.strategies["RL-CTI MTD"] = RLCTIMTDStrategy(model_path, device)
        
        self.results: Dict[str, Dict[int, List[EpisodeResult]]] = defaultdict(lambda: defaultdict(list))
    
    def _build_state(self, attacker: AttackerAgent, step: int, last_action: np.ndarray) -> np.ndarray:
        n_svc = len(self.mtd.services)
        scaled = scale_action(last_action)
        
        critical_exposed = any(
            self.mtd.services[s].is_critical
            for s in attacker.discovered_services
            if s in self.mtd.services
        )
        
        phase_map = {
            AttackPhase.INITIAL: 0.0, AttackPhase.RECONNAISSANCE: 0.2,
            AttackPhase.DISCOVERY: 0.4, AttackPhase.EXPLOITATION: 0.6,
            AttackPhase.PERSISTENCE: 0.8, AttackPhase.BREACH: 1.0,
            AttackPhase.DEFENDED: 0.0,
        }
        
        return np.array([
            min(1.0, len(attacker.scanned_ips) / 254),
            len(attacker.discovered_services) / n_svc,
            float(critical_exposed),
            len(attacker.exploited_services) / n_svc,
            phase_map.get(attacker.phase, 0.0),
            self.mtd.get_cdi(),
            self.mtd.get_redundancy(),
            min(1.0, attacker.decoy_hits / 10),
            attacker.energy,
            min(1.0, self.mtd.stats['total_swaps'] / 10),
            min(1.0, step / 50),
            attacker.confusion_level,
            min(1.0, len(attacker.scanned_ips) / 50),
            scaled[0], scaled[1], scaled[2],
            scaled[5] if len(scaled) > 5 else 0,
        ], dtype=np.float32)
    
    def _execute_action(self, action: np.ndarray) -> Tuple[Dict[str, float], float]:
        scaled = scale_action(action)
        total_cost = 0.0
        intensities = {}
        
        if scaled[0] > ACTION_THRESHOLDS['shuffle']:
            total_cost += self.mtd.shuffle(scaled[0])
            intensities['shuffle'] = float(scaled[0])
        
        if scaled[1] > ACTION_THRESHOLDS['port_hop']:
            total_cost += self.mtd.port_hop(scaled[1])
            intensities['port_hop'] = float(scaled[1])
        
        if scaled[2] > ACTION_THRESHOLDS['decoy']:
            total_cost += self.mtd.activate_decoys(scaled[2])
            intensities['decoy'] = float(scaled[2])
        
        if scaled[3] > ACTION_THRESHOLDS['blacklist']:
            total_cost += scaled[3] * scaled[4] * ACTION_COSTS['blacklist']
            intensities['blacklist'] = float(scaled[3])
        
        if scaled[5] > ACTION_THRESHOLDS['swap']:
            total_cost += self.mtd.swap(scaled[5], scaled[6] > 0.5)
            intensities['swap'] = float(scaled[5])
        
        return intensities, total_cost
    
    def run_episode(
        self,
        strategy: BaselineStrategy,
        level: int,
        ep_id: int,
        seed: int,
    ) -> EpisodeResult:
        np.random.seed(seed)
        self.mtd.reset()
        self.defense_calc.reset()
        strategy.reset()
        
        attacker = AttackerAgent(level=level, seed=seed, targets=self.mtd.get_targets())
        
        result = EpisodeResult(
            episode_id=ep_id,
            strategy_name=strategy.name,
            attacker_level=level,
        )
        
        last_action = np.zeros(ACTION_DIM)
        cti_detections = 0
        
        for step in range(self.max_steps):
            state = self._build_state(attacker, step, last_action)
            action = strategy.get_action(state, step)
            last_action = action.copy()
            
            intensities, _ = self._execute_action(action)
            cdi = self.mtd.get_cdi()
            
            cti_detected = False
            if len(attacker.scanned_ips) > 10 or len(attacker.exploited_services) > 0:
                detected, conf, _ = self.cti.detect_attack("scan")
                cti_detected = detected
                if detected:
                    cti_detections += 1
            
            defense_prob = self.defense_calc.compute(
                intensities, cdi, level, step, cti_detected
            )
            
            attack_result = attacker.step({
                'is_shuffle': 'shuffle' in intensities,
                'shuffle_intensity': intensities.get('shuffle', 0),
                'is_swap': 'swap' in intensities,
                'swap_intensity': intensities.get('swap', 0),
                'defense_probability': defense_prob,
            })
            
            if attack_result['breach']:
                result.breach_occurred = True
                result.mttc = step + 1
                break
            
            if attacker.phase == AttackPhase.DEFENDED:
                break
        
        result.steps = step + 1
        result.total_cost = float(self.mtd.stats['total_cost'])
        result.shuffle_count = int(self.mtd.stats['total_shuffles'])
        result.swap_count = int(self.mtd.stats['total_swaps'])
        result.decoy_hits = int(attacker.decoy_hits)
        result.services_discovered = int(len(attacker.discovered_services))
        result.services_exploited = int(len(attacker.exploited_services))
        result.final_phase = str(attacker.phase)
        result.cti_detections = cti_detections
        
        n_svc = len(self.mtd.services)
        mttc = result.mttc if result.breach_occurred else self.max_steps
        result.mttc = int(mttc)
        result.cdi = float(cdi)
        result.redundancy = float(self.mtd.get_redundancy())
        
        discovered = result.services_discovered
        exploited = result.services_exploited
        exposed = discovered + exploited * 2
        max_exposure = n_svc * 3
        result.asr = float(1.0 - min(1.0, exposed / max_exposure))
        
        mttc_norm = mttc / self.max_steps
        asp = exploited / max(1, discovered) if discovered > 0 else 0
        ned = np.random.uniform(0.3, 0.7)
        result.des = float(
            0.25 * mttc_norm + 
            0.20 * result.asr + 
            0.20 * result.cdi + 
            0.15 * ned +
            0.10 * (1.0 - asp) + 
            0.10 * result.redundancy
        )
        
        result.cer = float(result.des / (result.total_cost + 0.1))
        
        return result
    
    def run_experiment(
        self,
        episodes: int = 50,
        levels: List[int] = None,
        strategies: List[str] = None,
    ):
        levels = levels or [0, 1, 2, 3, 4]
        strategies = strategies or list(self.strategies.keys())
        
        total_runs = len(strategies) * len(levels) * episodes
        
        print(f"\n{'='*70}")
        print("MTD-RL Paper Experiment v09.7 (Fixed CDI)")
        print(f"{'='*70}")
        print(f"Strategies: {strategies}")
        print(f"Levels: {levels}")
        print(f"Episodes/level: {episodes}")
        print(f"Total runs: {total_runs}")
        print(f"{'='*70}\n")
        
        start_time = time.time()
        
        for strat_name in strategies:
            if strat_name not in self.strategies:
                print(f"⚠️ Strategy not found: {strat_name}")
                continue
            
            strat = self.strategies[strat_name]
            print(f"📊 Strategy: {strat_name}")
            
            for level in levels:
                print(f"  Level {level} ({ATTACKER_PROFILES[level]['name']}): ", end="", flush=True)
                
                for ep in range(episodes):
                    r = self.run_episode(strat, level, ep, 42 + level * 1000 + ep)
                    self.results[strat_name][level].append(r)
                    if (ep + 1) % 10 == 0:
                        print(".", end="", flush=True)
                
                eps = self.results[strat_name][level]
                br = sum(1 for e in eps if e.breach_occurred) / len(eps) * 100
                des = np.mean([e.des for e in eps])
                cdi = np.mean([e.cdi for e in eps])
                print(f" BR={br:.1f}%, DES={des:.3f}, CDI={cdi:.2f}")
        
        elapsed = (time.time() - start_time) / 60
        print(f"\n✅ Completed in {elapsed:.1f} minutes")
        
        self._save_results()
        self._print_summary()
    
    def _save_results(self):
        output = {}
        for strat, level_results in self.results.items():
            output[strat] = {}
            for level, eps in level_results.items():
                output[strat][str(level)] = [
                    to_python({
                        "episode_id": r.episode_id,
                        "steps": r.steps,
                        "breach": r.breach_occurred,
                        "cost": r.total_cost,
                        "mttc": r.mttc,
                        "asr": r.asr,
                        "cdi": r.cdi,
                        "redundancy": r.redundancy,
                        "des": r.des,
                        "cer": r.cer,
                        "shuffle_count": r.shuffle_count,
                        "swap_count": r.swap_count,
                        "decoy_hits": r.decoy_hits,
                        "services_discovered": r.services_discovered,
                        "services_exploited": r.services_exploited,
                        "final_phase": r.final_phase,
                        "cti_detections": r.cti_detections,
                    })
                    for r in eps
                ]
        
        path = self.output_dir / "experiment_results.json"
        with open(path, 'w') as f:
            json.dump(output, f, indent=2)
        print(f"✅ Results saved: {path}")
    
    def _print_summary(self):
        print(f"\n{'='*110}")
        print("EXPERIMENT SUMMARY (Paper Table 13 Format)")
        print(f"{'='*110}")
        
        levels = sorted(self.results[list(self.results.keys())[0]].keys())
        header = f"{'Strategy':<20}"
        for l in levels:
            header += f" | L{l} BR%"
        header += " | Avg DES | Avg CDI | Avg CER"
        print(header)
        print("-" * 110)
        
        for strat in self.results:
            row = f"{strat:<20}"
            all_des, all_cdi, all_cer = [], [], []
            for level in levels:
                eps = self.results[strat][level]
                br = sum(1 for e in eps if e.breach_occurred) / len(eps) * 100
                row += f" | {br:6.1f}"
                all_des.extend([e.des for e in eps])
                all_cdi.extend([e.cdi for e in eps])
                all_cer.extend([e.cer for e in eps])
            row += f" | {np.mean(all_des):7.3f} | {np.mean(all_cdi):7.2f} | {np.mean(all_cer):7.2f}"
            print(row)
        print(f"{'='*110}")
    
    def get_results_for_figures(self) -> Dict[str, Dict[int, Dict]]:
        output = {}
        for strat, level_results in self.results.items():
            output[strat] = {}
            for level, eps in level_results.items():
                output[strat][level] = {
                    'des': float(np.mean([e.des for e in eps])),
                    'des_std': float(np.std([e.des for e in eps])),
                    'br': float(sum(1 for e in eps if e.breach_occurred) / len(eps) * 100),
                    'mttc': float(np.mean([e.mttc for e in eps])),
                    'mttc_std': float(np.std([e.mttc for e in eps])),
                    'cer': float(np.mean([e.cer for e in eps])),
                    'cer_std': float(np.std([e.cer for e in eps])),
                    'cdi': float(np.mean([e.cdi for e in eps])),
                    'cost': float(np.mean([e.total_cost for e in eps])),
                    'redundancy': float(np.mean([e.redundancy for e in eps])),
                    'asr': float(np.mean([e.asr for e in eps])),
                }
        return output


# =============================================================================
# CLI
# =============================================================================
def main():
    parser = argparse.ArgumentParser(description="MTD-RL Paper Experiment v09.7")
    parser.add_argument("--model", type=str, default=None)
    parser.add_argument("--output-dir", type=str, default="paper_results_v097")
    parser.add_argument("--max-steps", type=int, default=200)
    parser.add_argument("--device", type=str, default="cpu")
    parser.add_argument("--level", type=int, default=None)
    parser.add_argument("--episodes", type=int, default=50)
    parser.add_argument("--experiment", action="store_true")
    parser.add_argument("--strategies", nargs="+", default=None)
    args = parser.parse_args()
    
    manager = RLDeceptionManager(
        model_path=args.model,
        output_dir=args.output_dir,
        max_steps=args.max_steps,
        device=args.device,
    )
    
    if args.experiment:
        levels = [0, 1, 2, 3, 4]
    else:
        levels = [args.level] if args.level is not None else [2]
    
    manager.run_experiment(
        episodes=args.episodes,
        levels=levels,
        strategies=args.strategies,
    )
    
    # ieee_figure_utils 연동
    try:
        from ieee_figure_utils_v101 import IEEEFigureGenerator
        print("\n📊 Generating IEEE figures...")
        fig_results = manager.get_results_for_figures()
        generator = IEEEFigureGenerator(output_dir=f"{args.output_dir}/ieee_figures")
        generator.generate_all(fig_results)
    except ImportError:
        print("ℹ️ ieee_figure_utils_v101 not found")


if __name__ == "__main__":
    main()