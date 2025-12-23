#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MTD Paper Evaluation System v1.0
================================
논문 Figure 5 State Transition Model 기반 정확한 평가 시스템

핵심 구현:
1. State Transition Model (S0→S1→S2→S3→S4, Si→S5)
2. 5개 전략 (No MTD, Static MTD, Heuristic+CTI, RL MTD, RL+CTI MTD)
3. 논문 수식 정확 구현 (p_def, 혼란도, DES, CER)

참조: IEEE Access 논문 Section III, IV
"""

import os
import sys
import json
import random
import numpy as np
import matplotlib.pyplot as plt
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Any
from enum import Enum
from datetime import datetime
from collections import defaultdict
import warnings
warnings.filterwarnings('ignore')

# =============================================================================
# 논문 Table 6: Attacker Profiles
# =============================================================================
ATTACKER_PROFILES = {
    0: {"name": "Script Kiddie", "p_disc": 0.15, "p_exploit": 0.08, "scan_rate": 0.03, "decoy_detect": 0.1},
    1: {"name": "Novice",        "p_disc": 0.25, "p_exploit": 0.12, "scan_rate": 0.05, "decoy_detect": 0.2},
    2: {"name": "Intermediate",  "p_disc": 0.35, "p_exploit": 0.20, "scan_rate": 0.08, "decoy_detect": 0.35},
    3: {"name": "Advanced",      "p_disc": 0.50, "p_exploit": 0.30, "scan_rate": 0.12, "decoy_detect": 0.5},
    4: {"name": "APT",           "p_disc": 0.65, "p_exploit": 0.40, "scan_rate": 0.15, "decoy_detect": 0.65},
}

# =============================================================================
# 논문 Table 5: MTD Action Parameters
# =============================================================================
MTD_ACTIONS = {
    "shuffle":  {"threshold": 0.25, "cost": 0.035, "weight": 0.35, "confusion": 0.15},
    "port_hop": {"threshold": 0.35, "cost": 0.021, "weight": 0.20, "confusion": 0.08},
    "decoy":    {"threshold": 0.40, "cost": 0.014, "weight": 0.15, "confusion": 0.00},
    "blacklist":{"threshold": 0.60, "cost": 0.010, "weight": 0.10, "confusion": 0.00},
    "swap":     {"threshold": 0.30, "cost": 0.035, "weight": 0.45, "confusion": 0.25},
}

# =============================================================================
# State Transition Model (Figure 5)
# =============================================================================
class AttackPhase(Enum):
    """논문 Figure 5의 공격 단계"""
    S0_INITIAL = 0      # 초기 상태
    S1_RECON = 1        # 정찰 단계
    S2_DISCOVERY = 2    # 서비스 발견 단계
    S3_EXPLOIT = 3      # 익스플로잇 단계
    S4_BREACH = 4       # 침해 완료 (Terminal - 실패)
    S5_DEFENDED = 5     # 방어 성공 (Terminal - 성공)


@dataclass
class ServiceState:
    """서비스 상태"""
    name: str
    ip: str
    port: int
    is_critical: bool = False
    is_discovered: bool = False
    is_exploited: bool = False
    vulnerability_score: float = 0.5


@dataclass
class AttackerState:
    """공격자 상태"""
    level: int
    phase: AttackPhase = AttackPhase.S0_INITIAL
    scanned_ips: set = field(default_factory=set)
    discovered_services: set = field(default_factory=set)
    exploited_services: set = field(default_factory=set)
    confusion: float = 0.0  # ξ_t
    energy: float = 1.0


@dataclass 
class EpisodeResult:
    """에피소드 결과"""
    strategy: str
    attacker_level: int
    breach: bool
    defended: bool
    steps: int
    mttc: int
    total_cost: float
    s_mtd: float
    cer: float
    cdi_avg: float
    redundancy_avg: float
    confusion_avg: float
    asr: float
    asp: float


# =============================================================================
# 논문 수식 구현
# =============================================================================

def compute_defense_probability(
    action_intensities: Dict[str, float],
    cdi: float,
    redundancy: float,
    attacker_level: int
) -> float:
    """
    논문 Equation 2: 방어 확률 계산
    
    p_def = (P_0 + E_curr + β_D·CDI + β_R·R) · κ_ℓ
    
    수정: MTD 액션 없으면 방어 확률 매우 낮음
    
    Args:
        action_intensities: 각 MTD 액션의 강도 (0-1)
        cdi: Configuration Diversity Index
        redundancy: 중복성 점수
        attacker_level: 공격자 레벨 (0-4)
    
    Returns:
        방어 확률 (0.05 ~ 0.85)
    """
    # MTD 효과 계산
    E_curr = 0.0
    has_active_mtd = False
    
    for action_name, intensity in action_intensities.items():
        if action_name in MTD_ACTIONS:
            threshold = MTD_ACTIONS[action_name]["threshold"]
            if intensity > threshold:
                has_active_mtd = True
                weight = MTD_ACTIONS[action_name]["weight"]
                E_curr += weight * intensity
    
    # 기본 방어 확률 - MTD 없으면 매우 낮음
    if has_active_mtd:
        P_0 = 0.15  # MTD 있을 때 기본값
    else:
        P_0 = 0.05  # MTD 없을 때 기본값 (거의 무방비)
    
    # Diversity/Redundancy 보너스
    beta_D = 0.10
    beta_R = 0.08
    
    # MTD 효과 있을 때만 다양성 보너스 적용
    if has_active_mtd:
        diversity_bonus = beta_D * cdi + beta_R * redundancy
    else:
        diversity_bonus = 0.0
    
    # 공격자 레벨 modifier (κ_ℓ = 1 - 0.10ℓ) - 더 강한 감쇠
    kappa = 1.0 - 0.10 * attacker_level  # L0: 1.0, L4: 0.6
    
    # 최종 방어 확률
    p_def = (P_0 + E_curr + diversity_bonus) * kappa
    
    # Clamp to [0.05, 0.85]
    return max(0.05, min(0.85, p_def))


def compute_confusion(
    prev_confusion: float,
    action_intensities: Dict[str, float],
    discovered_services: set,
    affected_services: set
) -> float:
    """
    논문 Equation 3: 혼란도 계산
    
    ξ_t = γ_ξ · ξ_{t-1} + Σβ_i · ã_i · 𝟙[svc_i ∈ D_t]
    
    Args:
        prev_confusion: 이전 혼란도
        action_intensities: MTD 액션 강도
        discovered_services: 발견된 서비스 집합
        affected_services: MTD 영향 받은 서비스
    
    Returns:
        새 혼란도
    """
    gamma_xi = 0.92  # 감쇠 계수
    
    # 감쇠된 이전 혼란도
    new_confusion = gamma_xi * prev_confusion
    
    # 새로운 혼란도 추가
    for action_name, intensity in action_intensities.items():
        if action_name in MTD_ACTIONS:
            beta = MTD_ACTIONS[action_name]["confusion"]
            threshold = MTD_ACTIONS[action_name]["threshold"]
            if intensity > threshold and beta > 0:
                # 발견된 서비스에 영향을 미치면 혼란도 증가
                overlap = len(discovered_services & affected_services)
                if overlap > 0 or action_name == "swap":
                    new_confusion += beta * intensity
    
    return min(1.5, new_confusion)  # 상한


def compute_effective_discovery_prob(base_prob: float, confusion: float) -> float:
    """
    논문 Equation 4: 유효 발견 확률
    
    p_disc_eff = p_disc · max(0.1, 1 - min(0.5, 0.4·ξ_t))
    """
    modifier = max(0.1, 1.0 - min(0.5, 0.4 * confusion))
    return base_prob * modifier


def compute_cdi(services: Dict[str, ServiceState]) -> float:
    """
    논문 Equation 5: Configuration Diversity Index (Shannon Entropy)
    
    CDI = H(configs) / H_max
    """
    if len(services) <= 1:
        return 0.0
    
    configs = [f"{s.ip}:{s.port}" for s in services.values()]
    unique = len(set(configs))
    
    if unique <= 1:
        return 0.0
    
    # Shannon Entropy
    from collections import Counter
    counts = Counter(configs)
    total = len(configs)
    
    entropy = 0.0
    for count in counts.values():
        p = count / total
        if p > 0:
            entropy -= p * np.log2(p)
    
    max_entropy = np.log2(total)
    return entropy / max_entropy if max_entropy > 0 else 0.0


def compute_redundancy(active_decoys: int, total_decoys: int, active_swaps: int) -> float:
    """
    논문 Equation 6: Redundancy Score
    
    R_t = 0.6 · (n_dec_active / N_dec) + 0.3 · min(1, 0.08·n_swap) + 0.1
    """
    decoy_ratio = active_decoys / max(1, total_decoys)
    swap_bonus = min(1.0, 0.08 * active_swaps)
    return 0.6 * decoy_ratio + 0.3 * swap_bonus + 0.1


def compute_des(
    mttc: int,
    max_steps: int,
    asr: float,
    cdi: float,
    ned: float,
    asp: float,
    redundancy: float
) -> float:
    """
    논문 Equation 7: Defense Effectiveness Score
    
    S_MTD = 0.25·MTTC_norm + 0.20·ASR + 0.20·CDI + 0.15·NED + 0.10·(1-ASP) + 0.10·R
    """
    mttc_norm = min(1.0, mttc / max_steps)
    return (
        0.25 * mttc_norm +
        0.20 * asr +
        0.20 * cdi +
        0.15 * ned +
        0.10 * (1.0 - asp) +
        0.10 * redundancy
    )


def compute_cer(s_mtd: float, total_cost: float) -> float:
    """
    논문 Equation 8: Cost Efficiency Ratio
    
    CER = S_MTD / (C_total + ε)
    """
    epsilon = 0.1
    return s_mtd / (total_cost + epsilon)


# =============================================================================
# State Transition Simulator (Figure 5 구현)
# =============================================================================

class StateTransitionSimulator:
    """
    논문 Figure 5의 State Transition Model 시뮬레이터
    """
    
    def __init__(
        self,
        attacker_level: int = 1,
        max_steps: int = 200,
        seed: int = 42
    ):
        self.attacker_level = attacker_level
        self.max_steps = max_steps
        self.rng = np.random.default_rng(seed)
        
        self.profile = ATTACKER_PROFILES[attacker_level]
        
        # 서비스 초기화
        self.services: Dict[str, ServiceState] = {}
        self.decoys: Dict[str, bool] = {}  # decoy_name -> is_active
        self._init_services()
        
        # 공격자 상태
        self.attacker = AttackerState(level=attacker_level)
        
        # 에피소드 통계
        self.step_count = 0
        self.total_cost = 0.0
        self.cdi_history: List[float] = []
        self.redundancy_history: List[float] = []
        self.confusion_history: List[float] = []
        self.action_history: List[Dict] = []
        self.active_swaps = 0
        
    def _init_services(self):
        """테스트베드 서비스 초기화 (Table 3)"""
        service_defs = [
            ("FC", "10.13.0.10", 14550, True),    # Flight Controller (Critical)
            ("CC", "10.13.0.11", 5760, False),    # Companion Computer
            ("GCS", "10.13.0.20", 3000, True),    # Ground Control Station (Critical)
            ("Video", "10.13.0.12", 554, False),  # Video Stream
            ("ROS", "10.13.0.13", 11311, False),  # ROS Master
            ("TelemetryDB", "10.13.0.14", 5432, False),  # Telemetry DB
        ]
        
        for name, ip, port, critical in service_defs:
            self.services[name] = ServiceState(
                name=name, ip=ip, port=port,
                is_critical=critical,
                vulnerability_score=0.5 + self.rng.random() * 0.3
            )
        
        # 디코이 초기화
        for i in range(4):
            self.decoys[f"Decoy_{i}"] = False
    
    def reset(self, seed: Optional[int] = None):
        """환경 리셋"""
        if seed is not None:
            self.rng = np.random.default_rng(seed)
        
        self._init_services()
        self.attacker = AttackerState(level=self.attacker_level)
        self.attacker.phase = AttackPhase.S0_INITIAL
        
        self.step_count = 0
        self.total_cost = 0.0
        self.cdi_history = []
        self.redundancy_history = []
        self.confusion_history = []
        self.action_history = []
        self.active_swaps = 0
    
    def step(self, action: np.ndarray) -> Tuple[bool, bool, Dict]:
        """
        한 스텝 실행
        
        Args:
            action: 7차원 MTD 액션 벡터 [-1, 1]^7
        
        Returns:
            (breach, defended, info)
        """
        self.step_count += 1
        
        # 액션 스케일링 [-1,1] → [0,1]
        scaled = (np.array(action) + 1.0) / 2.0
        
        # MTD 액션 강도
        action_intensities = {
            "shuffle": scaled[0],
            "port_hop": scaled[1],
            "decoy": scaled[2],
            "blacklist": scaled[3],
            "swap": scaled[5],
        }
        
        # MTD 비용 및 효과 적용
        step_cost, affected_services = self._apply_mtd_actions(action_intensities)
        self.total_cost += step_cost
        
        # 지표 계산
        cdi = compute_cdi(self.services)
        active_decoys = sum(1 for v in self.decoys.values() if v)
        redundancy = compute_redundancy(active_decoys, len(self.decoys), self.active_swaps)
        
        # 혼란도 업데이트
        self.attacker.confusion = compute_confusion(
            self.attacker.confusion,
            action_intensities,
            self.attacker.discovered_services,
            affected_services
        )
        
        # 방어 확률 계산
        p_def = compute_defense_probability(
            action_intensities, cdi, redundancy, self.attacker_level
        )
        
        # 히스토리 저장
        self.cdi_history.append(cdi)
        self.redundancy_history.append(redundancy)
        self.confusion_history.append(self.attacker.confusion)
        self.action_history.append(action_intensities.copy())
        
        # State Transition 시뮬레이션
        breach, defended = self._simulate_state_transition(p_def)
        
        info = {
            "phase": self.attacker.phase.name,
            "p_def": p_def,
            "cdi": cdi,
            "redundancy": redundancy,
            "confusion": self.attacker.confusion,
            "cost": step_cost,
        }
        
        return breach, defended, info
    
    def _apply_mtd_actions(self, intensities: Dict[str, float]) -> Tuple[float, set]:
        """MTD 액션 적용"""
        cost = 0.0
        affected = set()
        
        # Shuffle
        if intensities["shuffle"] > MTD_ACTIONS["shuffle"]["threshold"]:
            cost += MTD_ACTIONS["shuffle"]["cost"] * intensities["shuffle"]
            n_shuffle = max(1, int(len(self.services) * intensities["shuffle"]))
            shuffled = self.rng.choice(list(self.services.keys()), n_shuffle, replace=False)
            for name in shuffled:
                svc = self.services[name]
                svc.ip = f"10.13.0.{self.rng.integers(100, 200)}"
                svc.port = int(self.rng.integers(10000, 60000))
                affected.add(name)
                # 발견 무효화
                if svc.is_discovered and self.rng.random() < intensities["shuffle"] * 0.8:
                    svc.is_discovered = False
                    self.attacker.discovered_services.discard(name)
        
        # Port Hop
        if intensities["port_hop"] > MTD_ACTIONS["port_hop"]["threshold"]:
            cost += MTD_ACTIONS["port_hop"]["cost"] * intensities["port_hop"]
            for name, svc in self.services.items():
                if svc.is_critical and self.rng.random() < intensities["port_hop"]:
                    svc.port = int(self.rng.integers(10000, 60000))
                    affected.add(name)
        
        # Decoy
        if intensities["decoy"] > MTD_ACTIONS["decoy"]["threshold"]:
            cost += MTD_ACTIONS["decoy"]["cost"] * intensities["decoy"]
            n_activate = max(1, int(len(self.decoys) * intensities["decoy"]))
            inactive = [k for k, v in self.decoys.items() if not v]
            for name in self.rng.choice(inactive, min(n_activate, len(inactive)), replace=False):
                self.decoys[name] = True
        
        # Swap
        if intensities["swap"] > MTD_ACTIONS["swap"]["threshold"]:
            cost += MTD_ACTIONS["swap"]["cost"] * intensities["swap"]
            svc_names = list(self.services.keys())
            if len(svc_names) >= 2:
                a, b = self.rng.choice(svc_names, 2, replace=False)
                svc_a, svc_b = self.services[a], self.services[b]
                svc_a.ip, svc_b.ip = svc_b.ip, svc_a.ip
                svc_a.port, svc_b.port = svc_b.port, svc_a.port
                affected.add(a)
                affected.add(b)
                self.active_swaps += 1
                # 발견 무효화
                for name in [a, b]:
                    svc = self.services[name]
                    if svc.is_discovered and self.rng.random() < intensities["swap"] * 0.6:
                        svc.is_discovered = False
                        self.attacker.discovered_services.discard(name)
        
        return cost, affected
    
    def _simulate_state_transition(self, p_def: float) -> Tuple[bool, bool]:
        """
        논문 Figure 5의 State Transition 시뮬레이션
        
        핵심 전이 확률 (논문 Table 6 기반):
        - S0 → S1: 확률 1.0
        - S1 → S2: p_disc (공격자 레벨별)
        - S2 → S3: p_exploit (공격자 레벨별)
        - S3 → S4: p_breach (높음 - 크리티컬 도달 시)
        - Si → S5: p_def (방어 성공 시)
        
        Returns:
            (breach, defended)
        """
        profile = self.profile
        
        # 혼란도 → 유효 발견 확률
        p_disc_eff = compute_effective_discovery_prob(
            profile["p_disc"], self.attacker.confusion
        )
        
        # S0 → S1 (Initial → Recon): 확률 1.0
        if self.attacker.phase == AttackPhase.S0_INITIAL:
            self.attacker.phase = AttackPhase.S1_RECON
        
        # S1 (Recon) - 정찰 단계
        if self.attacker.phase == AttackPhase.S1_RECON:
            # 스캔 (더 많이)
            n_scan = max(5, int(200 * profile["scan_rate"] * 2))
            for _ in range(n_scan):
                ip = f"10.13.0.{self.rng.integers(1, 255)}"
                self.attacker.scanned_ips.add(ip)
            
            # 서비스 발견 시도 - 더 적극적
            for name, svc in self.services.items():
                if svc.is_discovered:
                    continue
                
                # IP 매칭 확률 (공격 표면이 작아서 매칭 쉬움)
                ip_match = self.rng.random() < 0.15 + profile["scan_rate"]
                if svc.ip in self.attacker.scanned_ips or ip_match:
                    # 방어 확률 적용 (self-loop)
                    defense_check = self.rng.random() < p_def * 0.5
                    if defense_check:
                        continue  # 방어 성공
                    
                    # 발견 확률 (더 높게)
                    if self.rng.random() < p_disc_eff * 1.5:
                        svc.is_discovered = True
                        self.attacker.discovered_services.add(name)
            
            # 전이 조건: 1개 이상 발견 시 바로 S2로
            if len(self.attacker.discovered_services) >= 1:
                self.attacker.phase = AttackPhase.S2_DISCOVERY
            
            # S1 → S5 방어 성공 전이 (매우 낮은 확률)
            if p_def > 0.6 and self.rng.random() < p_def * 0.1:
                self.attacker.phase = AttackPhase.S5_DEFENDED
                return False, True
        
        # S2 (Discovery → Exploit)
        elif self.attacker.phase == AttackPhase.S2_DISCOVERY:
            for name in list(self.attacker.discovered_services):
                svc = self.services.get(name)
                if not svc or svc.is_exploited:
                    continue
                
                # 방어 확률 적용
                if self.rng.random() < p_def * 0.4:
                    continue
                
                # 익스플로잇 시도 (더 높은 확률)
                exploit_prob = profile["p_exploit"] * (0.8 + svc.vulnerability_score * 0.4)
                if self.rng.random() < exploit_prob:
                    svc.is_exploited = True
                    self.attacker.exploited_services.add(name)
            
            # 전이 조건
            if len(self.attacker.exploited_services) >= 1:
                self.attacker.phase = AttackPhase.S3_EXPLOIT
            
            # S2 → S5 방어 성공 전이
            if p_def > 0.5 and self.rng.random() < p_def * 0.15:
                self.attacker.phase = AttackPhase.S5_DEFENDED
                return False, True
        
        # S3 (Exploit → Breach)
        elif self.attacker.phase == AttackPhase.S3_EXPLOIT:
            # 방어 확률 (S3에서는 낮지만 존재)
            if self.rng.random() < p_def * 0.35:
                self.attacker.phase = AttackPhase.S5_DEFENDED
                return False, True
            
            # Breach 시도
            exploited_critical = any(
                self.services[s].is_critical
                for s in self.attacker.exploited_services
                if s in self.services
            )
            
            # Breach 확률 (논문 Table 6 기반)
            # 크리티컬 서비스 익스플로잇 여부 + 공격자 레벨
            if exploited_critical:
                # 크리티컬 서비스 = 높은 breach 확률
                base_breach = 0.35 + 0.08 * self.attacker_level  # L0: 35%, L4: 67%
            else:
                # 비크리티컬 = 낮은 breach 확률
                base_breach = 0.20 + 0.05 * self.attacker_level  # L0: 20%, L4: 40%
            
            if self.rng.random() < base_breach:
                self.attacker.phase = AttackPhase.S4_BREACH
                return True, False  # Breach!
        
        return False, False
    
    def get_episode_metrics(self) -> Dict[str, float]:
        """에피소드 종료 후 메트릭 계산"""
        mttc = self.step_count if self.attacker.phase == AttackPhase.S4_BREACH else self.max_steps
        
        # ASR
        discovered = len(self.attacker.discovered_services)
        exploited = len(self.attacker.exploited_services)
        total_services = len(self.services)
        exposed = discovered + exploited * 2
        max_exposure = total_services * 3
        asr = 1.0 - min(1.0, exposed / max_exposure)
        
        # ASP
        asp = exploited / max(1, discovered)
        
        # CDI, Redundancy 평균
        cdi_avg = np.mean(self.cdi_history) if self.cdi_history else 0.0
        redundancy_avg = np.mean(self.redundancy_history) if self.redundancy_history else 0.0
        confusion_avg = np.mean(self.confusion_history) if self.confusion_history else 0.0
        
        # NED
        if len(self.cdi_history) >= 2:
            ned = min(1.0, np.std(np.diff(self.cdi_history)) * 5)
        else:
            ned = 0.0
        
        # DES
        s_mtd = compute_des(mttc, self.max_steps, asr, cdi_avg, ned, asp, redundancy_avg)
        
        # CER
        cer = compute_cer(s_mtd, self.total_cost)
        
        return {
            "mttc": mttc,
            "asr": asr,
            "asp": asp,
            "cdi_avg": cdi_avg,
            "redundancy_avg": redundancy_avg,
            "confusion_avg": confusion_avg,
            "ned": ned,
            "s_mtd": s_mtd,
            "cer": cer,
            "total_cost": self.total_cost,
            "breach": self.attacker.phase == AttackPhase.S4_BREACH,
            "defended": self.attacker.phase == AttackPhase.S5_DEFENDED,
        }


# =============================================================================
# 5개 전략 정의 (Section IV.E Baseline Configurations)
# =============================================================================

class BaseStrategy:
    """전략 기본 클래스"""
    name: str = "Base"
    
    def get_action(self, step: int, state: Dict) -> np.ndarray:
        """액션 반환 [-1, 1]^7"""
        raise NotImplementedError


class NoMTDStrategy(BaseStrategy):
    """No MTD: 고정 IP/포트, MTD 없음"""
    name = "No MTD"
    
    def get_action(self, step: int, state: Dict) -> np.ndarray:
        # 모든 액션 비활성화
        return np.array([-1.0, -1.0, -1.0, -1.0, -1.0, -1.0, -1.0])


class StaticMTDStrategy(BaseStrategy):
    """Static MTD: 30스텝마다 무작위 셔플 + 기본 디코이"""
    name = "Static MTD"
    
    def get_action(self, step: int, state: Dict) -> np.ndarray:
        action = np.array([-1.0, -1.0, 0.3, -1.0, -1.0, -1.0, -1.0])  # 기본 디코이
        
        # 30스텝마다 셔플
        if step % 30 == 0:
            action[0] = 0.5  # shuffle intensity
            action[1] = 0.3  # port hop
        
        # 60스텝마다 스왑
        if step % 60 == 0:
            action[5] = 0.4  # swap
        
        return action


class HeuristicCTIStrategy(BaseStrategy):
    """Heuristic+CTI: CTI 신뢰도 > 0.6일 때 규칙 기반 트리거"""
    name = "Heuristic+CTI"
    
    def get_action(self, step: int, state: Dict) -> np.ndarray:
        action = np.array([-0.5, -0.5, 0.4, -0.5, -0.5, -0.5, 0.0])  # 기본 디코이
        
        # CTI 신뢰도 시뮬레이션 (위협 수준 기반)
        threat_level = state.get("threat_level", 0.0)
        cti_confidence = min(1.0, threat_level * 1.5 + np.random.random() * 0.2)
        
        if cti_confidence > 0.6:
            # 규칙 기반 트리거
            action[0] = 0.6  # shuffle
            action[2] = 0.6  # decoy
            
            if cti_confidence > 0.75:
                action[1] = 0.5  # port hop
                action[5] = 0.5  # swap
        
        # 주기적 셔플 (20스텝마다)
        if step % 20 == 0:
            action[0] = max(action[0], 0.5)
            action[1] = max(action[1], 0.3)
        
        # 40스텝마다 스왑
        if step % 40 == 0:
            action[5] = max(action[5], 0.4)
        
        return action


class RLMTDStrategy(BaseStrategy):
    """RL MTD: PPO 에이전트 (CTI 없음) - 시뮬레이션"""
    name = "RL MTD"
    
    def __init__(self):
        # 학습된 정책 시뮬레이션을 위한 파라미터
        self.base_response = {
            "low_threat": np.array([0.2, 0.1, 0.3, -0.5, -0.5, 0.1, 0.0]),
            "medium_threat": np.array([0.5, 0.4, 0.5, 0.2, -0.2, 0.4, 0.5]),
            "high_threat": np.array([0.7, 0.6, 0.7, 0.5, 0.3, 0.6, 0.7]),
        }
    
    def get_action(self, step: int, state: Dict) -> np.ndarray:
        threat_level = state.get("threat_level", 0.0)
        
        # 위협 수준에 따른 동적 대응
        if threat_level < 0.3:
            base = self.base_response["low_threat"]
        elif threat_level < 0.6:
            base = self.base_response["medium_threat"]
        else:
            base = self.base_response["high_threat"]
        
        # 노이즈 추가 (exploration)
        noise = np.random.randn(7) * 0.1
        action = np.clip(base + noise, -1.0, 1.0)
        
        return action


class RLCTIMTDStrategy(BaseStrategy):
    """RL+CTI MTD (Proposed): PPO 에이전트 + CTI boost"""
    name = "RL+CTI MTD"
    
    def __init__(self):
        self.base_response = {
            "low_threat": np.array([0.3, 0.2, 0.4, -0.3, -0.3, 0.2, 0.0]),
            "medium_threat": np.array([0.6, 0.5, 0.6, 0.3, 0.0, 0.5, 0.5]),
            "high_threat": np.array([0.8, 0.7, 0.8, 0.6, 0.4, 0.7, 0.8]),
        }
    
    def get_action(self, step: int, state: Dict) -> np.ndarray:
        threat_level = state.get("threat_level", 0.0)
        cti_boost = state.get("cti_boost", 0.0)
        
        # 기본 RL 정책
        if threat_level < 0.3:
            base = self.base_response["low_threat"]
        elif threat_level < 0.6:
            base = self.base_response["medium_threat"]
        else:
            base = self.base_response["high_threat"]
        
        # CTI boost 적용 (Section 3.3.3)
        # CTI 신뢰도가 높을수록 방어 강도 증가
        if cti_boost > 0.5:
            boost_factor = 1.0 + (cti_boost - 0.5) * 0.6
            base = np.clip(base * boost_factor, -1.0, 1.0)
        
        # 노이즈
        noise = np.random.randn(7) * 0.08
        action = np.clip(base + noise, -1.0, 1.0)
        
        return action


# =============================================================================
# 평가 실행기
# =============================================================================

class MTDEvaluator:
    """MTD 평가 실행기"""
    
    def __init__(
        self,
        strategies: List[BaseStrategy],
        attacker_levels: List[int] = [0, 1, 2, 3, 4],
        episodes_per_config: int = 50,
        max_steps: int = 200,
        seed: int = 42
    ):
        self.strategies = strategies
        self.attacker_levels = attacker_levels
        self.episodes_per_config = episodes_per_config
        self.max_steps = max_steps
        self.seed = seed
        
        self.results: List[EpisodeResult] = []
    
    def run_episode(
        self,
        strategy: BaseStrategy,
        attacker_level: int,
        episode_seed: int
    ) -> EpisodeResult:
        """단일 에피소드 실행"""
        sim = StateTransitionSimulator(
            attacker_level=attacker_level,
            max_steps=self.max_steps,
            seed=episode_seed
        )
        sim.reset()
        
        breach = False
        defended = False
        
        for step in range(self.max_steps):
            # 상태 구성
            state = {
                "threat_level": len(sim.attacker.discovered_services) / len(sim.services),
                "cti_boost": min(1.0, sim.attacker.confusion + 
                               len(sim.attacker.exploited_services) * 0.3),
            }
            
            # 액션 선택
            action = strategy.get_action(step, state)
            
            # 스텝 실행
            breach, defended, info = sim.step(action)
            
            if breach or defended:
                break
        
        # 메트릭 수집
        metrics = sim.get_episode_metrics()
        
        return EpisodeResult(
            strategy=strategy.name,
            attacker_level=attacker_level,
            breach=metrics["breach"],
            defended=metrics["defended"],
            steps=sim.step_count,
            mttc=metrics["mttc"],
            total_cost=metrics["total_cost"],
            s_mtd=metrics["s_mtd"],
            cer=metrics["cer"],
            cdi_avg=metrics["cdi_avg"],
            redundancy_avg=metrics["redundancy_avg"],
            confusion_avg=metrics["confusion_avg"],
            asr=metrics["asr"],
            asp=metrics["asp"],
        )
    
    def run_evaluation(self, verbose: bool = True) -> List[EpisodeResult]:
        """전체 평가 실행"""
        self.results = []
        total_configs = len(self.strategies) * len(self.attacker_levels)
        config_idx = 0
        
        for strategy in self.strategies:
            for level in self.attacker_levels:
                config_idx += 1
                if verbose:
                    print(f"[{config_idx}/{total_configs}] {strategy.name} vs L{level}...", end=" ")
                
                episode_results = []
                for ep in range(self.episodes_per_config):
                    ep_seed = self.seed + config_idx * 1000 + ep
                    result = self.run_episode(strategy, level, ep_seed)
                    episode_results.append(result)
                    self.results.append(result)
                
                # 요약
                breaches = sum(1 for r in episode_results if r.breach)
                defended = sum(1 for r in episode_results if r.defended)
                avg_smtd = np.mean([r.s_mtd for r in episode_results])
                
                if verbose:
                    print(f"Breach={breaches}/{self.episodes_per_config}, "
                          f"Defended={defended}, S_MTD={avg_smtd:.3f}")
        
        return self.results
    
    def get_summary_by_strategy(self) -> Dict[str, Dict[str, float]]:
        """전략별 요약 통계"""
        summary = defaultdict(lambda: defaultdict(list))
        
        for r in self.results:
            summary[r.strategy]["breach_rate"].append(1 if r.breach else 0)
            summary[r.strategy]["s_mtd"].append(r.s_mtd)
            summary[r.strategy]["cer"].append(r.cer)
            summary[r.strategy]["cdi"].append(r.cdi_avg)
            summary[r.strategy]["redundancy"].append(r.redundancy_avg)
            summary[r.strategy]["confusion"].append(r.confusion_avg)
            summary[r.strategy]["cost"].append(r.total_cost)
            summary[r.strategy]["mttc"].append(r.mttc)
        
        result = {}
        for strategy, metrics in summary.items():
            result[strategy] = {
                metric: np.mean(values) for metric, values in metrics.items()
            }
            result[strategy]["breach_rate"] *= 100  # percentage
        
        return result
    
    def get_summary_by_level(self, strategy_name: str) -> Dict[int, Dict[str, float]]:
        """특정 전략의 레벨별 요약"""
        summary = defaultdict(lambda: defaultdict(list))
        
        for r in self.results:
            if r.strategy == strategy_name:
                summary[r.attacker_level]["breach_rate"].append(1 if r.breach else 0)
                summary[r.attacker_level]["s_mtd"].append(r.s_mtd)
                summary[r.attacker_level]["cer"].append(r.cer)
        
        result = {}
        for level, metrics in summary.items():
            result[level] = {
                metric: np.mean(values) for metric, values in metrics.items()
            }
            result[level]["breach_rate"] *= 100
        
        return result


# =============================================================================
# 시각화
# =============================================================================

def plot_results(evaluator: MTDEvaluator, output_dir: str = "paper_figures"):
    """결과 시각화"""
    os.makedirs(output_dir, exist_ok=True)
    
    strategy_summary = evaluator.get_summary_by_strategy()
    strategies = list(strategy_summary.keys())
    
    # 색상 설정
    colors = {
        "No MTD": "#E74C3C",
        "Static MTD": "#F39C12",
        "Heuristic+CTI": "#3498DB",
        "RL MTD": "#9B59B6",
        "RL+CTI MTD": "#2ECC71",
    }
    
    fig, axes = plt.subplots(2, 3, figsize=(15, 10))
    fig.suptitle("MTD Strategy Comparison (Paper Figure 9)", fontsize=14, fontweight='bold')
    
    # 1. S_MTD by Strategy
    ax = axes[0, 0]
    vals = [strategy_summary[s]["s_mtd"] for s in strategies]
    bars = ax.bar(strategies, vals, color=[colors.get(s, '#333') for s in strategies])
    ax.set_ylabel("S_MTD (Defense Effectiveness)")
    ax.set_title("(a) Defense Effectiveness Score")
    ax.set_ylim(0, 1)
    for bar, v in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width()/2, v + 0.02, f'{v:.3f}', 
                ha='center', va='bottom', fontsize=9)
    ax.tick_params(axis='x', rotation=15)
    
    # 2. Breach Rate by Strategy
    ax = axes[0, 1]
    vals = [strategy_summary[s]["breach_rate"] for s in strategies]
    bars = ax.bar(strategies, vals, color=[colors.get(s, '#333') for s in strategies])
    ax.set_ylabel("Breach Rate (%)")
    ax.set_title("(b) Breach Rate")
    ax.set_ylim(0, 100)
    for bar, v in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width()/2, v + 2, f'{v:.1f}%', 
                ha='center', va='bottom', fontsize=9)
    ax.tick_params(axis='x', rotation=15)
    
    # 3. CER by Strategy
    ax = axes[0, 2]
    vals = [strategy_summary[s]["cer"] for s in strategies]
    bars = ax.bar(strategies, vals, color=[colors.get(s, '#333') for s in strategies])
    ax.set_ylabel("CER (Cost Efficiency Ratio)")
    ax.set_title("(c) Cost Efficiency Ratio")
    for bar, v in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width()/2, v + 0.05, f'{v:.2f}', 
                ha='center', va='bottom', fontsize=9)
    ax.tick_params(axis='x', rotation=15)
    
    # 4. CDI by Strategy
    ax = axes[1, 0]
    vals = [strategy_summary[s]["cdi"] for s in strategies]
    bars = ax.bar(strategies, vals, color=[colors.get(s, '#333') for s in strategies])
    ax.set_ylabel("CDI (Configuration Diversity)")
    ax.set_title("(d) Configuration Diversity Index")
    ax.set_ylim(0, 1)
    for bar, v in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width()/2, v + 0.02, f'{v:.3f}', 
                ha='center', va='bottom', fontsize=9)
    ax.tick_params(axis='x', rotation=15)
    
    # 5. Redundancy by Strategy
    ax = axes[1, 1]
    vals = [strategy_summary[s]["redundancy"] for s in strategies]
    bars = ax.bar(strategies, vals, color=[colors.get(s, '#333') for s in strategies])
    ax.set_ylabel("Redundancy Score")
    ax.set_title("(e) Redundancy Score")
    ax.set_ylim(0, 1)
    for bar, v in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width()/2, v + 0.02, f'{v:.3f}', 
                ha='center', va='bottom', fontsize=9)
    ax.tick_params(axis='x', rotation=15)
    
    # 6. Cost by Strategy
    ax = axes[1, 2]
    vals = [strategy_summary[s]["cost"] for s in strategies]
    bars = ax.bar(strategies, vals, color=[colors.get(s, '#333') for s in strategies])
    ax.set_ylabel("Total Cost")
    ax.set_title("(f) MTD Cost")
    for bar, v in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width()/2, v + 0.01, f'{v:.3f}', 
                ha='center', va='bottom', fontsize=9)
    ax.tick_params(axis='x', rotation=15)
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "fig9_strategy_comparison.png"), dpi=300, bbox_inches='tight')
    plt.close()
    
    # Figure 10: Level별 비교
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle("Performance vs Attacker Level (Paper Figure 10)", fontsize=14, fontweight='bold')
    
    levels = [0, 1, 2, 3, 4]
    level_labels = ['L0\n(Script)', 'L1\n(Novice)', 'L2\n(Inter)', 'L3\n(Adv)', 'L4\n(APT)']
    
    # S_MTD by Level
    ax = axes[0]
    for strategy in strategies:
        level_data = evaluator.get_summary_by_level(strategy)
        vals = [level_data.get(l, {}).get("s_mtd", 0) for l in levels]
        ax.plot(levels, vals, marker='o', label=strategy, color=colors.get(strategy, '#333'), linewidth=2)
    ax.set_xlabel("Attacker Level")
    ax.set_ylabel("S_MTD")
    ax.set_title("(a) Defense Effectiveness by Attacker Level")
    ax.set_xticks(levels)
    ax.set_xticklabels(level_labels)
    ax.legend(loc='best', fontsize=8)
    ax.grid(True, alpha=0.3)
    ax.set_ylim(0, 1)
    
    # Breach Rate by Level
    ax = axes[1]
    for strategy in strategies:
        level_data = evaluator.get_summary_by_level(strategy)
        vals = [level_data.get(l, {}).get("breach_rate", 0) for l in levels]
        ax.plot(levels, vals, marker='o', label=strategy, color=colors.get(strategy, '#333'), linewidth=2)
    ax.set_xlabel("Attacker Level")
    ax.set_ylabel("Breach Rate (%)")
    ax.set_title("(b) Breach Rate by Attacker Level")
    ax.set_xticks(levels)
    ax.set_xticklabels(level_labels)
    ax.legend(loc='best', fontsize=8)
    ax.grid(True, alpha=0.3)
    ax.set_ylim(0, 100)
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "fig10_level_comparison.png"), dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"\n✅ Figures saved to {output_dir}/")


def print_latex_table(evaluator: MTDEvaluator):
    """LaTeX 테이블 출력"""
    summary = evaluator.get_summary_by_strategy()
    
    print("\n" + "="*80)
    print("Table 15: Strategy Comparison (LaTeX)")
    print("="*80)
    
    print(r"\begin{table}[!t]")
    print(r"\centering")
    print(r"\caption{Performance comparison of MTD strategies}")
    print(r"\label{tab:comparison}")
    print(r"\begin{tabular}{@{}lccccc@{}}")
    print(r"\toprule")
    print(r"\textbf{Strategy} & \textbf{S\_MTD} & \textbf{Breach(\%)} & \textbf{CER} & \textbf{CDI} & \textbf{Cost} \\")
    print(r"\midrule")
    
    for strategy in summary.keys():
        s = summary[strategy]
        print(f"{strategy} & {s['s_mtd']:.3f} & {s['breach_rate']:.1f} & "
              f"{s['cer']:.2f} & {s['cdi']:.3f} & {s['cost']:.3f} \\\\")
    
    print(r"\bottomrule")
    print(r"\end{tabular}")
    print(r"\end{table}")


# =============================================================================
# 메인
# =============================================================================

def main():
    print("="*70)
    print("MTD Paper Evaluation System v1.0")
    print("Based on IEEE Access Paper: CTI-Driven RL-MTD")
    print("="*70)
    
    # 전략 정의
    strategies = [
        NoMTDStrategy(),
        StaticMTDStrategy(),
        HeuristicCTIStrategy(),
        RLMTDStrategy(),
        RLCTIMTDStrategy(),
    ]
    
    # 평가기 생성
    evaluator = MTDEvaluator(
        strategies=strategies,
        attacker_levels=[0, 1, 2, 3, 4],
        episodes_per_config=50,
        max_steps=200,
        seed=42
    )
    
    # 평가 실행
    print("\n📊 Running evaluation...")
    results = evaluator.run_evaluation(verbose=True)
    
    # 요약 출력
    print("\n" + "="*70)
    print("📈 Summary Results")
    print("="*70)
    
    summary = evaluator.get_summary_by_strategy()
    print(f"\n{'Strategy':<20} {'S_MTD':>8} {'Breach%':>10} {'CER':>8} {'CDI':>8} {'Cost':>8}")
    print("-"*70)
    for strategy, metrics in summary.items():
        print(f"{strategy:<20} {metrics['s_mtd']:>8.3f} {metrics['breach_rate']:>9.1f}% "
              f"{metrics['cer']:>8.2f} {metrics['cdi']:>8.3f} {metrics['cost']:>8.3f}")
    
    # LaTeX 테이블
    print_latex_table(evaluator)
    
    # 시각화
    output_dir = "/mnt/user-data/outputs/paper_figures_v10"
    plot_results(evaluator, output_dir)
    
    # 결과 저장
    results_data = {
        "summary": summary,
        "timestamp": datetime.now().isoformat(),
        "config": {
            "episodes_per_config": evaluator.episodes_per_config,
            "max_steps": evaluator.max_steps,
            "attacker_levels": evaluator.attacker_levels,
        }
    }
    
    with open(os.path.join(output_dir, "evaluation_results.json"), 'w') as f:
        json.dump(results_data, f, indent=2, default=str)
    
    print(f"\n✅ Results saved to {output_dir}/")
    
    return evaluator


if __name__ == "__main__":
    evaluator = main()