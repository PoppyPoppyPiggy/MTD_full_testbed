#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enhanced MTD RL Environment v09 - Real Testbed Integration + Enhanced CTI
=========================================================================

v08 → v09 주요 강화:
1. Enhanced Seeker Agent 통합 (CTI Table 12/13 + 시간 기반 공격 표면)
2. 실제 Attack Chain 상태 전이 (S0→S1→S2→S3→S4→S5)
3. CTI Agent F1 Score 효과 반영 (Table 12/13 성능)
4. 실제 서비스 구성 (6개 서비스 + 4개 디코이)  
5. 논문 수식 정확 구현 (p_def, CDI, NED, Redundancy)
6. 시간 기반 공격 진행 모델링
7. Enhanced Attack Surface (50,200 targets, 60초 스캔)

논문 구현:
- Eq. 19: p_def = (p_base + E_curr + E_recent + β_D·CDI + β_R·R) × κ_ℓ
- Eq. 21: E_recent = Σ γ^τ · E_curr^(t-τ), γ=0.7, W=3
- Eq. 11: CDI = Shannon Entropy / H_max
- Eq. 12: R_t = 0.6·(n_decoy/N_d) + 0.3·(n_swap/N_s) + 0.1
- Appendix A: NED = min(1.0, std(diversity_changes) × 5)
- Table 12/13: CTI 분류기 성능 지표

저자: MTD-RL Research Team  
버전: 0.9.1 (Enhanced CTI + Time-based Attack Surface)
"""
from __future__ import annotations

import random
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np

# Enhanced Seeker Agent with CTI Table 12/13 + Time-based Attack Surface
try:
    from seeker_agent_v09 import (
        AdvancedSeekerAgent,
        ServiceTarget,
        AttackPhase,
        CTIDetectionModel,
        SEEKER_PROFILES,
        ATTACK_SURFACE,
        NMAP_FULL_SCAN_TIME,
        UAV_MISSION_TIME_MIN,
        UAV_MISSION_TIME_MAX
    )
    SEEKER_AGENT_AVAILABLE = True
except ImportError:
    print("⚠️ seeker_agent_v09.py not found. Using fallback implementation.")
    SEEKER_AGENT_AVAILABLE = False

# Gym compatibility
try:
    import gymnasium as gym
    from gymnasium import spaces
    GYM_AVAILABLE = True
except ImportError:
    try:
        import gym
        from gym import spaces
        GYM_AVAILABLE = True
    except ImportError:
        GYM_AVAILABLE = False
        print("⚠️ OpenAI Gym/Gymnasium not available. Using basic interface.")


# =============================================================================
# Fallback Implementation (if seeker_agent_v09.py not available)
# =============================================================================
if not SEEKER_AGENT_AVAILABLE:
    from enum import Enum
    
    # Fallback constants
    ATTACK_SURFACE = 50200
    NMAP_FULL_SCAN_TIME = 60.0
    UAV_MISSION_TIME_MIN = 2100
    UAV_MISSION_TIME_MAX = 4500
    
    class AttackPhase(Enum):
        INITIAL = "initial"
        RECONNAISSANCE = "reconnaissance"
        DISCOVERY = "discovery"
        EXPLOITATION = "exploitation"
        PERSISTENCE = "persistence"
        BREACH = "breach"
        DEFENDED = "defended"
    
    @dataclass
    class ServiceTarget:
        name: str
        real_ip: str
        real_port: int
        virtual_ip: str
        virtual_port: int
        protocol: str = "tcp"
        is_critical: bool = False
        is_decoy: bool = False
        scan_progress: float = 0.0
        discovery_progress: float = 0.0
        exploit_progress: float = 0.0
        
        def reset_progress(self):
            self.scan_progress *= 0.3
            self.discovery_progress *= 0.2
            self.exploit_progress *= 0.1
    
    SEEKER_PROFILES = {
        0: {"name": "Script Kiddie", "scan_rate": 0.03, "discovery_rate": 0.15, "exploit_rate": 0.08},
        1: {"name": "Hobbyist", "scan_rate": 0.05, "discovery_rate": 0.25, "exploit_rate": 0.12},
        2: {"name": "Professional", "scan_rate": 0.08, "discovery_rate": 0.35, "exploit_rate": 0.20},
        3: {"name": "Expert", "scan_rate": 0.12, "discovery_rate": 0.50, "exploit_rate": 0.30},
        4: {"name": "APT", "scan_rate": 0.15, "discovery_rate": 0.65, "exploit_rate": 0.40},
    }
    
    class AdvancedSeekerAgent:
        def __init__(self, level, seed, targets, step_duration=1.0):
            self.level = level
            self.phase = AttackPhase.INITIAL
            self.energy = 1.0
            self.targets = targets
            self.total_time_elapsed = 0.0
            self.mission_duration = 3000
            self.discovered_services = set()
            self.exploited_services = set()
            self.decoy_interactions = []
            self.attack_features = {'scan_intensity': 0, 'exploit_attempts': 0, 'energy_drain': 0, 'gps_anomaly': 0}
            
        def step(self, defense_info):
            self.total_time_elapsed += 1.0
            return {
                'phase': self.phase.value,
                'breach': False,
                'defended': False,
                'attack_type': 'general',
                'threat_level': 0.3
            }
        
        def get_threat_level(self):
            return 0.3
    
    class CTIDetectionModel:
        def __init__(self):
            self.balanced_accuracy = 0.847
        
        def classify_attack_type(self, features):
            return "general", 0.7
        
        def detect_attack(self, is_attack, attack_type="general"):
            return True, 0.8


# =============================================================================
# Paper Constants (논문 기반 + Enhanced)
# =============================================================================

# 상태/액션 차원 (논문 Table 4, 5)
STATE_DIM = 17
ACTION_DIM = 7

# 논문 Eq. 19, 21 파라미터 
P_BASE = 0.25       # Base defense probability
BETA_CDI = 0.15     # CDI coefficient (β_D)
BETA_R = 0.10       # Redundancy coefficient (β_R)
GAMMA_DECAY = 0.7   # γ_decay (Eq. 21)
WINDOW_W = 3        # W (Eq. 21)

# 논문 Table 5: MTD Action Configuration
ACTION_CONFIG = {
    'shuffle':   {'idx': 0, 'theta': 0.25, 'cost': 0.05, 'alpha': 0.35},
    'port_hop':  {'idx': 1, 'theta': 0.35, 'cost': 0.03, 'alpha': 0.20},
    'decoy':     {'idx': 2, 'theta': 0.40, 'cost': 0.02, 'alpha': 0.15},
    'blacklist': {'idx': 3, 'theta': 0.60, 'cost': 0.02, 'alpha': 0.10},
    'swap':      {'idx': 4, 'theta': 0.30, 'cost': 0.05, 'alpha': 0.45},
}

# 논문 Table 6: Testbed Services (실제 구성)
SERVICES_CONFIG = {
    "fc_mavlink":    {"real_ip": "10.13.0.10", "real_port": 14550, "protocol": "udp", "is_critical": True},
    "cc_sitl":       {"real_ip": "10.13.0.11", "real_port": 5760,  "protocol": "tcp", "is_critical": True},
    "gcs_web":       {"real_ip": "10.13.0.20", "real_port": 3000,  "protocol": "tcp", "is_critical": True},
    "video_stream":  {"real_ip": "10.13.0.12", "real_port": 554,   "protocol": "tcp", "is_critical": False},
    "ros_master":    {"real_ip": "10.13.0.13", "real_port": 11311, "protocol": "tcp", "is_critical": False},
    "telemetry_db":  {"real_ip": "10.13.0.14", "real_port": 5432,  "protocol": "tcp", "is_critical": False},
}

DECOYS_CONFIG = {
    "honeydrone_1": {"real_ip": "10.13.0.100", "real_port": 14550, "protocol": "udp"},
    "honeydrone_2": {"real_ip": "10.13.0.101", "real_port": 14550, "protocol": "udp"},
    "decoy_gcs":    {"real_ip": "10.13.0.102", "real_port": 3000,  "protocol": "tcp"},
    "tarpit":       {"real_ip": "10.13.0.103", "real_port": 9999,  "protocol": "tcp"},
}

# 논문 Table 7: Attacker Profiles
ATTACKER_PROFILES = SEEKER_PROFILES


# =============================================================================
# Enhanced MTD Controller (시간 기반 통합)
# =============================================================================
class EnhancedMTDController:
    """
    강화된 MTD 컨트롤러 - Enhanced CTI + 시간 기반 공격 표면 지원
    """
    
    def __init__(self, seed: int = 42, step_duration: float = 1.0):
        self.rng = np.random.default_rng(seed)
        self.step_duration = step_duration  # 스텝당 시간 (초)
        
        self.services: Dict[str, ServiceTarget] = {}
        self.decoys: Dict[str, ServiceTarget] = {}
        
        # MTD 통계
        self.stats = {
            'shuffles': 0, 'port_hops': 0, 'decoys': 0, 
            'blacklists': 0, 'swaps': 0, 'total_cost': 0.0
        }
        
        # CDI & NED 계산용
        self.config_history: List[str] = []
        self.diversity_history: List[float] = []
        
        # 시간 기반 MTD 효과 추적
        self.mtd_activation_times: Dict[str, float] = {}
        self.total_time_elapsed: float = 0.0
        
        self._init_services()
    
    def _init_services(self):
        """서비스 초기화"""
        self.services.clear()
        self.decoys.clear()
        
        # 실제 서비스 생성
        for name, cfg in SERVICES_CONFIG.items():
            self.services[name] = ServiceTarget(
                name=name,
                real_ip=cfg["real_ip"],
                real_port=cfg["real_port"],
                virtual_ip=f"10.13.0.{self.rng.integers(200, 250)}",
                virtual_port=int(self.rng.integers(10000, 60000)),
                protocol=cfg["protocol"],
                is_critical=cfg.get("is_critical", False),
            )
        
        # 디코이 생성
        for name, cfg in DECOYS_CONFIG.items():
            self.decoys[name] = ServiceTarget(
                name=name,
                real_ip=cfg["real_ip"],
                real_port=cfg["real_port"],
                virtual_ip=f"10.13.0.{self.rng.integers(180, 199)}",
                virtual_port=int(self.rng.integers(8000, 9999)),
                protocol=cfg["protocol"],
                is_decoy=True,
            )
        
        self._record_config()
    
    def _record_config(self):
        """현재 설정 기록 (CDI & NED 계산용)"""
        cfg_parts = []
        for svc in self.services.values():
            cfg_parts.append(f"{svc.name}:{svc.virtual_ip}:{svc.virtual_port}")
        cfg_hash = hash(tuple(sorted(cfg_parts)))
        
        self.config_history.append(str(cfg_hash))
        
        # Diversity ratio for NED
        unique_ratio = len(set(self.config_history)) / max(1, len(self.config_history))
        self.diversity_history.append(unique_ratio)
        
        # 히스토리 제한
        if len(self.config_history) > 100:
            self.config_history = self.config_history[-100:]
            self.diversity_history = self.diversity_history[-100:]
    
    def reset(self, seed: Optional[int] = None):
        """상태 리셋"""
        if seed is not None:
            self.rng = np.random.default_rng(seed)
        
        self.stats = {k: 0 if isinstance(v, int) else 0.0 for k, v in self.stats.items()}
        self.config_history.clear()
        self.diversity_history.clear()
        self.mtd_activation_times.clear()
        self.total_time_elapsed = 0.0
        self._init_services()
    
    def step(self):
        """시간 진행"""
        self.total_time_elapsed += self.step_duration
    
    # =========================================================================
    # MTD Actions (논문 Table 5 기반 + 시간 추적)
    # =========================================================================
    
    def shuffle(self, intensity: float) -> float:
        """네트워크 셔플 (IP/포트 변경) - 시간 기반 효과"""
        cfg = ACTION_CONFIG['shuffle']
        if intensity < cfg['theta']:
            return 0.0
        
        n = max(1, int(len(self.services) * intensity))
        keys = self.rng.choice(list(self.services.keys()), size=min(n, len(self.services)), replace=False)
        
        for svc_name in keys:
            svc = self.services[svc_name]
            svc.virtual_ip = f"10.13.0.{self.rng.integers(200, 250)}"
            svc.virtual_port = int(self.rng.integers(10000, 60000))
        
        self.stats['shuffles'] += 1
        cost = intensity * cfg['cost']
        self.stats['total_cost'] += cost
        self.mtd_activation_times['shuffle'] = self.total_time_elapsed
        self._record_config()
        return cost
    
    def port_hop(self, intensity: float) -> float:
        """포트 홉핑 - 크리티컬 서비스 대상"""
        cfg = ACTION_CONFIG['port_hop']
        if intensity < cfg['theta']:
            return 0.0
        
        for svc in self.services.values():
            if svc.is_critical and self.rng.random() < intensity:
                svc.virtual_port = int(self.rng.integers(10000, 60000))
        
        self.stats['port_hops'] += 1
        cost = intensity * cfg['cost']
        self.stats['total_cost'] += cost
        self.mtd_activation_times['port_hop'] = self.total_time_elapsed
        self._record_config()
        return cost
    
    def activate_decoys(self, ratio: float) -> float:
        """디코이 활성화"""
        cfg = ACTION_CONFIG['decoy']
        if ratio < cfg['theta']:
            return 0.0
        
        n = max(1, int(len(self.decoys) * ratio))
        self.stats['decoys'] += n
        cost = ratio * cfg['cost'] * n
        self.stats['total_cost'] += cost
        self.mtd_activation_times['decoy'] = self.total_time_elapsed
        return cost
    
    def blacklist_update(self, aggression: float, duration: float) -> float:
        """블랙리스트 업데이트"""
        cfg = ACTION_CONFIG['blacklist']
        if aggression < cfg['theta']:
            return 0.0
        
        self.stats['blacklists'] += 1
        cost = aggression * duration * cfg['cost']
        self.stats['total_cost'] += cost
        self.mtd_activation_times['blacklist'] = self.total_time_elapsed
        return cost
    
    def swap(self, intensity: float, target_critical: bool = True) -> float:
        """서비스 스왑"""
        cfg = ACTION_CONFIG['swap']
        if intensity < cfg['theta']:
            return 0.0
        
        keys = list(self.services.keys())
        if len(keys) < 2:
            return 0.0
        
        if target_critical:
            critical = [k for k in keys if self.services[k].is_critical]
            non_critical = [k for k in keys if not self.services[k].is_critical]
            if critical and non_critical:
                a, b = self.rng.choice(critical), self.rng.choice(non_critical)
            else:
                a, b = self.rng.choice(keys, size=2, replace=False)
        else:
            a, b = self.rng.choice(keys, size=2, replace=False)
        
        # 스왑 실행
        svc_a, svc_b = self.services[a], self.services[b]
        svc_a.virtual_ip, svc_b.virtual_ip = svc_b.virtual_ip, svc_a.virtual_ip
        svc_a.virtual_port, svc_b.virtual_port = svc_b.virtual_port, svc_a.virtual_port
        
        self.stats['swaps'] += 1
        cost = intensity * cfg['cost']
        self.stats['total_cost'] += cost
        self.mtd_activation_times['swap'] = self.total_time_elapsed
        self._record_config()
        return cost
    
    # =========================================================================
    # 논문 메트릭 계산 (Enhanced)
    # =========================================================================
    
    def get_cdi(self) -> float:
        """CDI (Configuration Diversity Index) - Eq. 11"""
        if len(self.config_history) <= 1:
            return 0.1
        
        unique = len(set(self.config_history))
        total = len(self.config_history)
        
        if unique <= 1:
            return 0.1
        
        # Shannon entropy
        counts = {}
        for cfg in self.config_history:
            counts[cfg] = counts.get(cfg, 0) + 1
        
        entropy = 0.0
        for count in counts.values():
            p = count / total
            if p > 0:
                entropy -= p * np.log2(p)
        
        max_entropy = np.log2(total)
        cdi = entropy / max_entropy if max_entropy > 0 else 0
        
        return float(np.clip(cdi, 0.1, 1.0))
    
    def get_ned(self) -> float:
        """NED (Normalized Entropy of Defense) - Appendix A"""
        if len(self.diversity_history) < 2:
            return 0.3
        
        diversity_changes = np.diff(self.diversity_history)
        
        if len(diversity_changes) == 0:
            return 0.3
        
        std = np.std(diversity_changes)
        ned = min(1.0, std * 5)
        
        return float(np.clip(ned, 0.1, 1.0))
    
    def get_redundancy(self) -> float:
        """Redundancy Score - Eq. 12"""
        # n_active_decoy / N_decoy
        n_decoy = len(self.decoys)
        decoy_ratio = self.stats['decoys'] / max(1, n_decoy * 10)
        decoy_term = 0.6 * min(1.0, decoy_ratio)
        
        # n_swap / N_s (N_s = 6, total services)
        n_services = len(self.services)
        swap_ratio = self.stats['swaps'] / max(1, n_services)
        swap_term = 0.3 * min(1.0, swap_ratio)
        
        redundancy = decoy_term + swap_term + 0.1
        
        return float(np.clip(redundancy, 0.1, 1.0))
    
    def get_targets(self) -> List[ServiceTarget]:
        """모든 타겟 반환 (서비스 + 디코이)"""
        return list(self.services.values()) + list(self.decoys.values())


# =============================================================================
# Defense Probability Calculator (논문 Eq. 19, 21 + Enhanced CTI)
# =============================================================================
class DefenseProbabilityCalculator:
    """
    논문 Eq. 19 구현 + Enhanced CTI 지원:
    p_def = (p_base + E_curr + E_recent + β_D·CDI + β_R·R) × κ_ℓ
    """
    
    def __init__(self, mtd_controller: EnhancedMTDController):
        self.mtd = mtd_controller
        self.recent_effects: List[Tuple[int, float]] = []
    
    def compute(
        self,
        action_intensities: Dict[str, float],
        cdi: float,
        attacker_level: int,
        step: int,
        cti_effects: Optional[Dict[str, float]] = None,
    ) -> float:
        """방어 확률 계산 (Enhanced CTI 지원)"""
        # E_curr = Σ α_i · ã_i
        current_effect = 0.0
        for action_name, intensity in action_intensities.items():
            if action_name in ACTION_CONFIG:
                alpha = ACTION_CONFIG[action_name]['alpha']
                current_effect += alpha * intensity
        
        # CTI 효과 추가 (Enhanced)
        if cti_effects:
            cti_bonus = 0.0
            for effect_type, confidence in cti_effects.items():
                if effect_type == "attack_detected":
                    cti_bonus += confidence * 0.15  # CTI 탐지 시 방어력 증가
                elif effect_type == "attack_classified":
                    cti_bonus += confidence * 0.10  # 공격 분류 시 추가 효과
            current_effect += cti_bonus
        
        # E_recent (Eq. 21): γ=0.7, W=3
        self.recent_effects.append((step, current_effect))
        if len(self.recent_effects) > WINDOW_W:
            self.recent_effects = self.recent_effects[-WINDOW_W:]
        
        residual = 0.0
        for tau, (s, e) in enumerate(self.recent_effects[:-1], 1):
            decay = GAMMA_DECAY ** tau
            residual += e * decay * 0.3
        
        # κ_ℓ (Eq. 10)
        kappa = 1.0 - 0.08 * attacker_level
        
        # Redundancy (Eq. 12)
        redundancy = self.mtd.get_redundancy()
        
        # p_def = (p_base + E_curr + E_recent + β_D·CDI + β_R·R) × κ_ℓ
        p_def = (P_BASE + current_effect + residual + BETA_CDI * cdi + BETA_R * redundancy) * kappa
        
        return float(np.clip(p_def, 0.10, 0.95))
    
    def reset(self):
        self.recent_effects.clear()


# =============================================================================
# State Builder (논문 Table 4 + Enhanced)
# =============================================================================
def build_state(
    seeker: AdvancedSeekerAgent,
    mtd: EnhancedMTDController,
    step: int,
    last_action: np.ndarray,
    max_steps: int,
) -> np.ndarray:
    """17차원 상태 벡터 구성 (논문 Table 4 + Enhanced CTI)"""
    
    state = np.zeros(STATE_DIM, dtype=np.float32)
    
    # [0-4] Attack Phase one-hot (5-dim)
    phase_mapping = {
        AttackPhase.INITIAL: 0,
        AttackPhase.RECONNAISSANCE: 1, 
        AttackPhase.DISCOVERY: 2,
        AttackPhase.EXPLOITATION: 3,
        AttackPhase.PERSISTENCE: 4,
        AttackPhase.BREACH: 4,  # BREACH도 4로 매핑
        AttackPhase.DEFENDED: 0,  # DEFENDED는 0으로 매핑
    }
    phase_idx = phase_mapping.get(seeker.phase, 0)
    state[phase_idx] = 1.0
    
    # [5] Threat level (Enhanced CTI 기반)
    state[5] = seeker.get_threat_level()
    
    # [6] Services exposed ratio
    n_discovered = len(seeker.discovered_services)
    state[6] = n_discovered / max(1, len(mtd.services))
    
    # [7] Critical services at risk
    critical_exposed = sum(1 for t in seeker.targets 
                         if hasattr(t, 'name') and t.name in seeker.discovered_services and 
                         hasattr(t, 'is_critical') and t.is_critical and not getattr(t, 'is_decoy', False))
    n_critical = sum(1 for s in mtd.services.values() if s.is_critical)
    state[7] = critical_exposed / max(1, n_critical)
    
    # [8] Attacker energy
    state[8] = getattr(seeker, 'energy', 1.0)
    
    # [9] CDI
    state[9] = mtd.get_cdi()
    
    # [10] Time remaining ratio (Enhanced)
    if hasattr(seeker, 'total_time_elapsed') and hasattr(seeker, 'mission_duration'):
        mission_progress = seeker.total_time_elapsed / seeker.mission_duration
        state[10] = max(0.0, 1.0 - mission_progress)
    else:
        state[10] = 1.0 - (step / max_steps)
    
    # [11] Decoy effectiveness (Enhanced)
    if hasattr(seeker, 'decoy_interactions'):
        total_decoy_interactions = len(seeker.decoy_interactions)
        undetected_hits = len([d for d in seeker.decoy_interactions if not d.detected])
        if total_decoy_interactions > 0:
            decoy_effectiveness = undetected_hits / total_decoy_interactions
        else:
            decoy_effectiveness = 0.0
    else:
        decoy_effectiveness = 0.0
    state[11] = decoy_effectiveness
    
    # [12-16] Last action (5-dim for main actions)
    state[12:17] = last_action[:5]
    
    return state


# =============================================================================
# Enhanced MTD Environment
# =============================================================================
class MTDEnvironment:
    """
    강화된 MTD 환경 - Enhanced CTI + 시간 기반 공격 표면 통합
    """
    
    def __init__(
        self,
        seed: int = 42,
        seeker_level: int = 2,
        max_steps: int = 200,
        config: Optional[Any] = None,
        curriculum_phase: int = 0,
        step_duration: float = 1.0,  # 스텝당 시간 (초)
    ):
        self.seed = seed
        self.seeker_level = seeker_level
        self.max_steps = max_steps
        self.curriculum_phase = curriculum_phase
        self.step_duration = step_duration
        
        self.rng = np.random.default_rng(seed)
        
        # Enhanced MTD 컨트롤러
        self.mtd = EnhancedMTDController(seed, step_duration)
        self.defense_calc = DefenseProbabilityCalculator(self.mtd)
        
        # Enhanced CTI 모델
        self.cti = CTIDetectionModel()
        
        # Enhanced 공격자 (Seeker)
        self.seeker = None
        
        # 상태
        self.step_count = 0
        self.total_cost = 0.0
        self.last_action = np.zeros(ACTION_DIM)
        self.reward_profile = "balanced"
        
        # Enhanced 메트릭 추적
        self.episode_metrics = {
            'breach_occurred': False,
            'mttc': self.max_steps,
            'total_cost': 0.0,
            'services_discovered': 0,
            'services_exploited': 0,
            'decoy_hits': 0,
            'final_phase': 'INITIAL',
            'mission_time_used': 0.0,
            'scan_progress': 0.0,
            'cti_detections': 0,
            'cti_classifications': 0,
        }
        
        # Gym compatibility
        if GYM_AVAILABLE:
            self.action_space = spaces.Box(
                low=-1.0, high=1.0, shape=(ACTION_DIM,), dtype=np.float32
            )
            self.observation_space = spaces.Box(
                low=0.0, high=1.0, shape=(STATE_DIM,), dtype=np.float32
            )
    
    def reset(self, seed: Optional[int] = None) -> Tuple[np.ndarray, Dict]:
        """환경 리셋"""
        if seed is not None:
            self.seed = seed
            self.rng = np.random.default_rng(seed)
        
        # 컨트롤러 리셋
        self.mtd.reset(self.seed)
        self.defense_calc.reset()
        
        # Enhanced 공격자 생성
        self.seeker = AdvancedSeekerAgent(
            level=self.seeker_level,
            seed=self.seed + 1000,
            targets=self.mtd.get_targets(),
            step_duration=self.step_duration
        )
        
        # 상태 초기화
        self.step_count = 0
        self.total_cost = 0.0
        self.last_action = np.zeros(ACTION_DIM)
        
        self.episode_metrics = {
            'breach_occurred': False,
            'mttc': self.max_steps,
            'total_cost': 0.0,
            'services_discovered': 0,
            'services_exploited': 0,
            'decoy_hits': 0,
            'final_phase': 'INITIAL',
            'mission_time_used': 0.0,
            'scan_progress': 0.0,
            'cti_detections': 0,
            'cti_classifications': 0,
        }
        
        # 초기 상태 구성
        state = build_state(self.seeker, self.mtd, 0, self.last_action, self.max_steps)
        
        info = {
            'seeker_level': self.seeker_level,
            'curriculum_phase': self.curriculum_phase,
            'mtd_services': len(self.mtd.services),
            'mtd_decoys': len(self.mtd.decoys),
            'mission_duration': getattr(self.seeker, 'mission_duration', 3000),
            'attack_surface': ATTACK_SURFACE,
            'expected_scan_time': NMAP_FULL_SCAN_TIME,
        }
        
        return state, info
    
    def step(self, action: np.ndarray) -> Tuple[np.ndarray, float, bool, bool, Dict]:
        """한 스텝 실행 (Enhanced)"""
        self.step_count += 1
        self.last_action = action.copy()
        
        # MTD 시간 진행
        self.mtd.step()
        
        # 액션을 [0, 1] 범위로 변환
        action_scaled = (action + 1.0) / 2.0
        
        # MTD 액션 실행
        intensities, step_cost = self._execute_mtd_actions(action_scaled)
        self.total_cost += step_cost
        
        # 방어 확률 계산
        cdi = self.mtd.get_cdi()
        
        # Enhanced CTI 효과 계산
        cti_effects = self._calculate_cti_effects()
        
        p_def = self.defense_calc.compute(
            intensities, cdi, self.seeker_level, self.step_count, cti_effects
        )
        
        # Enhanced 공격자 스텝
        defense_info = {
            'defense_probability': p_def,
            'cdi': cdi,
            'mtd_active': len(intensities) > 0,
            'is_shuffle': 'shuffle' in intensities,
            'shuffle_intensity': intensities.get('shuffle', 0),
            'is_swap': 'swap' in intensities,
            'swap_intensity': intensities.get('swap', 0),
            'decoy_ratio': intensities.get('decoy', 0),
        }
        attack_result = self.seeker.step(defense_info)
        
        # MTD 효과로 공격자 진행도 감소
        if intensities and hasattr(self.seeker, 'handle_mtd_effect'):
            avg_intensity = sum(intensities.values()) / len(intensities)
            self.seeker.handle_mtd_effect("general", avg_intensity)
        
        # Enhanced 상태 업데이트
        next_state = build_state(self.seeker, self.mtd, self.step_count, self.last_action, self.max_steps)
        
        # Enhanced 보상 계산
        reward = self._calculate_enhanced_reward(attack_result, intensities, step_cost, cti_effects)
        
        # 종료 조건
        terminated = (
            self.seeker.phase == AttackPhase.BREACH or
            self.seeker.phase == AttackPhase.DEFENDED or
            (hasattr(self.seeker, 'total_time_elapsed') and hasattr(self.seeker, 'mission_duration') and
             self.seeker.total_time_elapsed >= self.seeker.mission_duration)
        )
        truncated = self.step_count >= self.max_steps
        
        # Enhanced 메트릭 업데이트
        self._update_enhanced_metrics(attack_result, cti_effects)
        
        # Enhanced 정보 구성
        info = self._build_enhanced_info(attack_result, intensities, p_def, step_cost, cti_effects)
        
        return next_state, reward, terminated, truncated, info
    
    def _execute_mtd_actions(self, action: np.ndarray) -> Tuple[Dict[str, float], float]:
        """MTD 액션 실행"""
        intensities = {}
        total_cost = 0.0
        
        # 주요 액션들
        if len(action) >= 5:
            # Shuffle
            if action[0] > ACTION_CONFIG['shuffle']['theta']:
                intensities['shuffle'] = float(action[0])
                cost = self.mtd.shuffle(action[0])
                total_cost += cost
            
            # Port Hop
            if action[1] > ACTION_CONFIG['port_hop']['theta']:
                intensities['port_hop'] = float(action[1])
                cost = self.mtd.port_hop(action[1])
                total_cost += cost
            
            # Decoy
            if action[2] > ACTION_CONFIG['decoy']['theta']:
                intensities['decoy'] = float(action[2])
                cost = self.mtd.activate_decoys(action[2])
                total_cost += cost
            
            # Blacklist
            if action[3] > ACTION_CONFIG['blacklist']['theta']:
                intensities['blacklist'] = float(action[3])
                duration = action[5] if len(action) > 5 else 0.5
                cost = self.mtd.blacklist_update(action[3], duration)
                total_cost += cost
            
            # Swap
            if action[4] > ACTION_CONFIG['swap']['theta']:
                intensities['swap'] = float(action[4])
                target_critical = action[6] > 0.5 if len(action) > 6 else True
                cost = self.mtd.swap(action[4], target_critical)
                total_cost += cost
        
        return intensities, total_cost
    
    def _calculate_cti_effects(self) -> Dict[str, float]:
        """Enhanced CTI 효과 계산"""
        effects = {}
        
        if self.seeker and hasattr(self.seeker, 'attack_features'):
            # 공격 탐지 여부
            is_attack = any(v > 0.1 for v in self.seeker.attack_features.values())
            if is_attack:
                # CTI 공격 탐지
                attack_type, type_confidence = self.cti.classify_attack_type(self.seeker.attack_features)
                detected, detect_confidence = self.cti.detect_attack(True, attack_type)
                
                if detected:
                    effects['attack_detected'] = detect_confidence
                    self.episode_metrics['cti_detections'] += 1
                    
                    if attack_type != "unknown":
                        effects['attack_classified'] = type_confidence
                        self.episode_metrics['cti_classifications'] += 1
        
        return effects
    
    def _calculate_enhanced_reward(
        self, 
        attack_result: Dict, 
        intensities: Dict[str, float], 
        step_cost: float,
        cti_effects: Dict[str, float],
    ) -> float:
        """Enhanced 보상 계산 (CTI + 시간 기반)"""
        reward = 0.0
        
        # 기본 생존 보상
        if self.seeker.phase != AttackPhase.BREACH:
            reward += 10.0
        
        # 침해 방지 보상 (강화)
        if attack_result.get('breach', False):
            reward -= 50.0
        
        # 디코이 효과 보상
        if attack_result.get('decoy_hit', False):
            reward += 15.0
        
        # 방어 성공 보상
        if self.seeker.phase == AttackPhase.DEFENDED:
            reward += 30.0
        
        # Enhanced CTI 보상
        if 'attack_detected' in cti_effects:
            reward += cti_effects['attack_detected'] * 20.0  # CTI 탐지 보상
        if 'attack_classified' in cti_effects:
            reward += cti_effects['attack_classified'] * 15.0  # 분류 정확도 보상
        
        # 시간 효율성 보상 (Enhanced)
        if hasattr(self.seeker, 'total_time_elapsed') and hasattr(self.seeker, 'mission_duration'):
            mission_progress = self.seeker.total_time_elapsed / self.seeker.mission_duration
            time_efficiency_bonus = (1.0 - mission_progress) * 10.0
            reward += time_efficiency_bonus
        
        # 스캔 진행 억제 보상
        if hasattr(self.seeker, 'scanner'):
            scan_progress = getattr(self.seeker.scanner, 'scanned_targets', 0) / ATTACK_SURFACE
            scan_suppression_bonus = (1.0 - scan_progress) * 12.0
            reward += scan_suppression_bonus
        
        # 효율성 보상 (Enhanced DES)
        des = self._calculate_des()
        reward += des * 25.0
        
        # 비용 패널티 (완화)
        reward -= step_cost * 4.0
        
        # 커리큘럼 기반 보상 조정
        if self.reward_profile == "explore":
            reward += self.rng.normal(0, 5)  # 탐색 장려
        elif self.reward_profile == "exploit":
            reward *= 1.2 if reward > 0 else 0.8  # 성능 최적화
        
        return float(reward)
    
    def _calculate_des(self) -> float:
        """Enhanced DES (Defense Effectiveness Score) 계산 - 논문 Eq. 14"""
        # MTTC normalization (시간 기반)
        if hasattr(self.seeker, 'total_time_elapsed') and hasattr(self.seeker, 'mission_duration'):
            actual_time = self.seeker.total_time_elapsed
            max_time = min(self.seeker.mission_duration, self.max_steps * self.step_duration)
            mttc_norm = min(actual_time, max_time) / max_time
        else:
            mttc_norm = self.step_count / self.max_steps
        
        # ASR (Attack Surface Reduction) - Enhanced
        if hasattr(self.seeker, 'scanner'):
            scan_progress = getattr(self.seeker.scanner, 'scanned_targets', 0) / ATTACK_SURFACE
        else:
            scan_progress = 0.1
        asr = 1.0 - scan_progress
        
        # CDI, NED, Redundancy
        cdi = self.mtd.get_cdi()
        ned = self.mtd.get_ned()
        redundancy = self.mtd.get_redundancy()
        
        # ASP (Attack Success Probability)
        n_discovered = len(self.seeker.discovered_services)
        n_exploited = len(self.seeker.exploited_services)
        asp = n_exploited / max(1, n_discovered)
        
        # Enhanced DES 계산 (Eq. 14)
        des = (
            0.25 * mttc_norm +
            0.20 * asr +
            0.20 * cdi +
            0.15 * ned +
            0.10 * (1.0 - asp) +
            0.10 * redundancy
        )
        
        return float(np.clip(des, 0.0, 1.0))
    
    def _update_enhanced_metrics(self, attack_result: Dict, cti_effects: Dict):
        """Enhanced 에피소드 메트릭 업데이트"""
        if attack_result.get('breach', False) or self.seeker.phase == AttackPhase.BREACH:
            self.episode_metrics['breach_occurred'] = True
            if self.episode_metrics['mttc'] == self.max_steps:
                if hasattr(self.seeker, 'total_time_elapsed'):
                    self.episode_metrics['mttc'] = self.seeker.total_time_elapsed
                else:
                    self.episode_metrics['mttc'] = self.step_count
        
        self.episode_metrics['total_cost'] = self.total_cost
        self.episode_metrics['services_discovered'] = len(self.seeker.discovered_services)
        self.episode_metrics['services_exploited'] = len(self.seeker.exploited_services)
        
        if hasattr(self.seeker, 'decoy_interactions'):
            self.episode_metrics['decoy_hits'] = len([d for d in self.seeker.decoy_interactions if not d.detected])
        
        self.episode_metrics['final_phase'] = self.seeker.phase.name
        
        if hasattr(self.seeker, 'total_time_elapsed'):
            self.episode_metrics['mission_time_used'] = self.seeker.total_time_elapsed
        
        if hasattr(self.seeker, 'scanner'):
            self.episode_metrics['scan_progress'] = getattr(self.seeker.scanner, 'scanned_targets', 0) / ATTACK_SURFACE
    
    def _build_enhanced_info(
        self, 
        attack_result: Dict, 
        intensities: Dict[str, float], 
        p_def: float, 
        step_cost: float,
        cti_effects: Dict[str, float],
    ) -> Dict:
        """Enhanced 정보 딕셔너리 구성"""
        des = self._calculate_des()
        
        # 기본 정보
        info = {
            # Enhanced MTD Metrics
            'MTD/DES': des,
            'MTD/CDI': self.mtd.get_cdi(),
            'MTD/NED': self.mtd.get_ned(),
            'MTD/Redundancy': self.mtd.get_redundancy(),
            'MTD/CER': des / (self.total_cost + 0.01),
            
            # Enhanced Defense metrics
            'Defense/BreachPrevented': 1 if self.seeker.phase != AttackPhase.BREACH else 0,
            'Defense/Probability': p_def,
            
            # Enhanced Attack metrics
            'Attack/Phase': self.seeker.phase.name,
            'Attack/ThreatLevel': self.seeker.get_threat_level(),
            'Attack/ServicesFound': len(self.seeker.discovered_services),
            'Attack/ServicesExploited': len(self.seeker.exploited_services),
            'Attack/Energy': getattr(self.seeker, 'energy', 1.0),
            
            # Enhanced CTI metrics
            'CTI/DetectionsCount': self.episode_metrics['cti_detections'],
            'CTI/ClassificationsCount': self.episode_metrics['cti_classifications'],
            'CTI/CurrentDetected': 'attack_detected' in cti_effects,
            'CTI/CurrentClassified': 'attack_classified' in cti_effects,
            'CTI/BalancedAccuracy': self.cti.balanced_accuracy,
            
            # Cost metrics
            'Cost/Total': self.total_cost,
            'Cost/Step': step_cost,
            
            # Action metrics
            'MTD/ShuffleCount': self.mtd.stats['shuffles'],
            'MTD/SwapCount': self.mtd.stats['swaps'],
        }
        
        # 시간 관련 정보 추가
        if hasattr(self.seeker, 'total_time_elapsed') and hasattr(self.seeker, 'mission_duration'):
            info.update({
                'MTD/MTTC': min(self.seeker.total_time_elapsed, self.seeker.mission_duration),
                'MTD/MTTC_Normalized': min(self.seeker.total_time_elapsed, self.seeker.mission_duration) / self.seeker.mission_duration,
                'Attack/MissionProgress': self.seeker.total_time_elapsed / self.seeker.mission_duration,
                'Time/Elapsed': self.seeker.total_time_elapsed,
                'Time/Remaining': max(0, self.seeker.mission_duration - self.seeker.total_time_elapsed),
            })
        else:
            info.update({
                'MTD/MTTC': self.step_count,
                'MTD/MTTC_Normalized': self.step_count / self.max_steps,
                'Time/Elapsed': self.step_count * self.step_duration,
            })
        
        # 스캔 관련 정보 추가
        if hasattr(self.seeker, 'scanner'):
            scanner = self.seeker.scanner
            info.update({
                'Attack/ScanProgress': getattr(scanner, 'scanned_targets', 0) / ATTACK_SURFACE,
                'Attack/ScanEfficiency': getattr(scanner, 'get_scan_efficiency', lambda: 1.0)(),
            })
        else:
            info.update({
                'Attack/ScanProgress': 0.1,
                'Attack/ScanEfficiency': 1.0,
            })
        
        # 디코이 관련 정보 추가
        if hasattr(self.seeker, 'decoy_interactions'):
            info['Decoy/Hits'] = len([d for d in self.seeker.decoy_interactions if not d.detected])
        else:
            info['Decoy/Hits'] = 0
        
        # 상수 정보
        info.update({
            'Time/ExpectedScanTime': NMAP_FULL_SCAN_TIME,
            'mission_duration': getattr(self.seeker, 'mission_duration', 3000),
        })
        
        # Final episode metrics (if terminated)
        info.update(self.episode_metrics)
        
        return info
    
    def set_reward_profile(self, profile: str):
        """보상 프로파일 설정"""
        self.reward_profile = profile


# =============================================================================
# Export Constants
# =============================================================================
__all__ = [
    'MTDEnvironment',
    'STATE_DIM',
    'ACTION_DIM', 
    'GAMMA_DECAY',
    'WINDOW_W',
    'BETA_CDI', 
    'BETA_R',
    'SERVICES_CONFIG',
    'DECOYS_CONFIG',
    'ATTACKER_PROFILES',
]


# =============================================================================
# Test
# =============================================================================
if __name__ == "__main__":
    print("=== Enhanced MTD Environment v09 Test (CTI Table 12/13 + Time-based) ===")
    
    # 환경 생성
    env = MTDEnvironment(seed=42, seeker_level=2, step_duration=1.0)
    
    print(f"State dim: {STATE_DIM}, Action dim: {ACTION_DIM}")
    print(f"Services: {len(env.mtd.services)}, Decoys: {len(env.mtd.decoys)}")
    print(f"Attack Surface: {ATTACK_SURFACE:,} targets")
    print(f"Expected Scan Time: {NMAP_FULL_SCAN_TIME} seconds")
    print(f"CTI Balanced Accuracy: {env.cti.balanced_accuracy}")
    
    # 에피소드 실행
    state, info = env.reset()
    print(f"\nInitial state shape: {state.shape}")
    print(f"Initial seeker phase: {env.seeker.phase.name}")
    print(f"Mission duration: {info.get('mission_duration', 3000):.1f} seconds")
    
    total_reward = 0
    for step in range(50):
        # 랜덤 액션 (더 적극적)
        action = env.rng.uniform(-0.5, 1, ACTION_DIM)
        
        next_state, reward, terminated, truncated, info = env.step(action)
        total_reward += reward
        
        if step % 10 == 0:
            print(f"Step {step}: Phase={info['Attack/Phase']}, "
                  f"Time={info.get('Time/Elapsed', step):.1f}s, "
                  f"Scan={info.get('Attack/ScanProgress', 0)*100:.1f}%, "
                  f"Reward={reward:.1f}, "
                  f"DES={info['MTD/DES']:.3f}, "
                  f"CTI_Det={info['CTI/DetectionsCount']}")
        
        if terminated or truncated:
            print(f"\nEpisode terminated at step {step}")
            break
    
    print(f"\n=== Episode Results ===")
    print(f"Total reward: {total_reward:.1f}")
    print(f"Final phase: {info['Attack/Phase']}")
    print(f"Mission time used: {info.get('Time/Elapsed', step):.1f}s")
    print(f"Scan progress: {info.get('Attack/ScanProgress', 0)*100:.1f}%")
    print(f"Scan efficiency: {info.get('Attack/ScanEfficiency', 1.0):.2f}")
    print(f"Breach prevented: {info['Defense/BreachPrevented']}")
    print(f"Final DES: {info['MTD/DES']:.3f}")
    print(f"CTI detections: {info['CTI/DetectionsCount']}")
    print(f"CTI classifications: {info['CTI/ClassificationsCount']}")
    print(f"Services discovered/exploited: {info['Attack/ServicesFound']}/{info['Attack/ServicesExploited']}")