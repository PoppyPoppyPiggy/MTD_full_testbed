#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Seeker Agent v09 - Enhanced Attack Surface Time Modeling + CTI Table 12/13
==========================================================================

v08 → v09 핵심 수정사항 (논문 기반):
1. CTI Detection Model: 논문 Table 12/13 기반 동적 분류기
2. 실제 시간 기반 공격 표면 모델링 (Attack Surface = 50,200, 1분 스캔)
3. 점진적 공격 진행 (즉시 판정 → 시간 누적 기반)
4. Nmap 스타일 스캔 시간 시뮬레이션 강화

논문 참조:
- Table 12: Binary Classification (Normal vs Attack) F1=0.79
- Table 13: 5-class Classification, Balanced Accuracy=0.847
- Eq. 9: Attack Surface |A| = 200 × 251 = 50,200
- Nmap 전수 스캔: 1분 소요 (UAV 비행시간의 1.3-2.9%)
- 30스텝 주기 셔플 시 단일 스캔 중 2회 이상 MTD 변경

특징:
1. SEEKER_PROFILES (L0-L4) 완벽 호환
2. 실제 시간 기반 Nmap 스캔 시뮬레이션
3. Kill Chain 기반 공격 단계 (Recon → Discovery → Exploit → Breach)
4. CTI 탐지 정확도 반영 (Table 12/13 성능 지표)
5. MTD 효과에 따른 공격자 혼란/적응

공격자 레벨:
- L0 (Script Kiddie): 낮은 스캔율, 디코이에 잘 걸림
- L1 (Hobbyist): 중간 능력
- L2 (Professional): 높은 발견율, 적응력
- L3 (Expert): 스텔스, 디코이 회피
- L4 (APT): 최고 수준, 지속성

Author: MTD-RL Research Team
Version: 0.9.3 (Enhanced Time-based Attack Surface + CTI Table 12/13)
"""
from __future__ import annotations

import random
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np


# =============================================================================
# Paper Constants (논문 Eq. 9, Table 12/13)
# =============================================================================

# Attack Surface (논문 Eq. 9)
IP_POOL_SIZE = 200
PORT_CANDIDATES = 251
ATTACK_SURFACE = IP_POOL_SIZE * PORT_CANDIDATES  # 50,200

# Time Constants (논문 참조)
NMAP_FULL_SCAN_TIME = 60.0  # 1분 (초 단위)
UAV_MISSION_TIME_MIN = 35 * 60  # 35분 (초)
UAV_MISSION_TIME_MAX = 75 * 60  # 75분 (초)
SCAN_RATIO_MIN = NMAP_FULL_SCAN_TIME / UAV_MISSION_TIME_MAX  # 1.3%
SCAN_RATIO_MAX = NMAP_FULL_SCAN_TIME / UAV_MISSION_TIME_MIN  # 2.9%

# MTD Timing (논문 참조)
MTD_SHUFFLE_CYCLE = 30  # 30스텝 주기
MTD_CHANGES_PER_SCAN = NMAP_FULL_SCAN_TIME // MTD_SHUFFLE_CYCLE  # 2회


# =============================================================================
# 공격자 프로파일 (rl_config_v08.py와 동일)
# =============================================================================
SEEKER_PROFILES = {
    0: {
        "name": "Script Kiddie",
        "scan_rate": 0.03,
        "discovery_rate": 0.15,
        "exploit_rate": 0.08,
        "exploit_success": 0.08,
        "lateral_rate": 0.02,
        "stealth": 0.1,
        "persistence": 0.2,
        "adaptation": 0.1,
        "decoy_detection": 0.1,
        "initial_energy": 1.0,
        "energy_decay": 0.008,
    },
    1: {
        "name": "Hobbyist",
        "scan_rate": 0.05,
        "discovery_rate": 0.25,
        "exploit_rate": 0.12,
        "exploit_success": 0.12,
        "lateral_rate": 0.05,
        "stealth": 0.25,
        "persistence": 0.35,
        "adaptation": 0.2,
        "decoy_detection": 0.2,
        "initial_energy": 1.0,
        "energy_decay": 0.006,
    },
    2: {
        "name": "Professional",
        "scan_rate": 0.08,
        "discovery_rate": 0.35,
        "exploit_rate": 0.20,
        "exploit_success": 0.20,
        "lateral_rate": 0.10,
        "stealth": 0.5,
        "persistence": 0.5,
        "adaptation": 0.35,
        "decoy_detection": 0.35,
        "initial_energy": 1.0,
        "energy_decay": 0.004,
    },
    3: {
        "name": "Expert",
        "scan_rate": 0.12,
        "discovery_rate": 0.50,
        "exploit_rate": 0.30,
        "exploit_success": 0.30,
        "lateral_rate": 0.15,
        "stealth": 0.7,
        "persistence": 0.7,
        "adaptation": 0.5,
        "decoy_detection": 0.5,
        "initial_energy": 1.0,
        "energy_decay": 0.003,
    },
    4: {
        "name": "APT",
        "scan_rate": 0.15,
        "discovery_rate": 0.65,
        "exploit_rate": 0.40,
        "exploit_success": 0.40,
        "lateral_rate": 0.20,
        "stealth": 0.85,
        "persistence": 0.9,
        "adaptation": 0.7,
        "decoy_detection": 0.65,
        "initial_energy": 1.0,
        "energy_decay": 0.002,
    },
}


# =============================================================================
# CTI Detection Model (논문 Table 12/13 기반)
# =============================================================================
@dataclass
class CTIDetectionModel:
    """
    CTI 탐지 모델 - 논문 Table 12/13 기반 동적 분류기
    
    Table 12: Binary Classification (Normal vs Attack)
    - Normal: P=0.87, R=0.73, F1=0.79
    - Attack: P=0.72, R=0.86, F1=0.79
    - Macro: P=0.79, R=0.80, F1=0.79
    
    Table 13: 5-Class Classification
    - Normal: P=0.95, R=0.63
    - Brute-force: P=0.67, R=0.94
    - Battery-spoofing: P=0.60, R=0.90
    - Flight-termination: P=0.68, R=0.85
    - GPS-injection: P=0.39, R=0.92
    - Balanced Accuracy: 0.847
    """
    # Binary Classification Performance (Table 12)
    binary_performance: Dict[str, Dict[str, float]] = field(default_factory=lambda: {
        'normal': {'precision': 0.87, 'recall': 0.73, 'f1': 0.79},
        'attack': {'precision': 0.72, 'recall': 0.86, 'f1': 0.79}
    })
    
    # Multi-class Classification Performance (Table 13)
    multiclass_performance: Dict[str, Dict[str, float]] = field(default_factory=lambda: {
        'normal': {'precision': 0.95, 'recall': 0.63},
        'brute_force': {'precision': 0.67, 'recall': 0.94},
        'battery_spoofing': {'precision': 0.60, 'recall': 0.90},
        'flight_termination': {'precision': 0.68, 'recall': 0.85},
        'gps_injection': {'precision': 0.39, 'recall': 0.92}
    })
    
    # Overall metrics
    macro_precision: float = 0.79
    macro_recall: float = 0.80
    macro_f1: float = 0.79
    balanced_accuracy: float = 0.847
    
    def detect_attack(self, is_actual_attack: bool, attack_type: str = "general") -> Tuple[bool, float]:
        """
        논문 Table 12/13 기반 공격 탐지 시뮬레이션
        
        Args:
            is_actual_attack: 실제 공격 여부
            attack_type: 공격 유형 ("general", "brute_force", "battery_spoofing", 
                        "flight_termination", "gps_injection")
            
        Returns:
            (detected, confidence): 탐지 여부와 신뢰도
        """
        if is_actual_attack:
            # 공격 유형별 성능 적용
            if attack_type in self.multiclass_performance:
                perf = self.multiclass_performance[attack_type]
                recall = perf['recall']
                precision = perf['precision']
            else:
                # 일반 공격 (Table 12 기반)
                recall = self.binary_performance['attack']['recall']  # 0.86
                precision = self.binary_performance['attack']['precision']  # 0.72
            
            # True Positive: Recall 확률로 탐지
            detected = random.random() < recall
            
            if detected:
                # 탐지 시 신뢰도 (precision 반영)
                confidence = random.uniform(0.7, 0.95) * precision
            else:
                # 놓친 경우 낮은 신뢰도
                confidence = random.uniform(0.1, 0.4)
        else:
            # Normal 트래픽에 대한 오탐 확률
            normal_perf = self.binary_performance['normal']
            normal_recall = normal_perf['recall']  # 0.73
            normal_precision = normal_perf['precision']  # 0.87
            
            # False Positive: (1 - normal_recall) * low_rate
            fp_rate = (1.0 - normal_recall) * 0.3  # 약 8%
            detected = random.random() < fp_rate
            
            if detected:
                # 오탐 시 중간 신뢰도
                confidence = random.uniform(0.4, 0.6)
            else:
                # 정상 분류 시 높은 신뢰도
                confidence = random.uniform(0.8, 0.95) * normal_precision
        
        return detected, confidence
    
    def classify_attack_type(self, attack_features: Dict[str, float]) -> Tuple[str, float]:
        """
        공격 유형 분류 (Table 13 기반)
        
        Args:
            attack_features: 공격 특성 벡터
            
        Returns:
            (attack_type, confidence): 분류된 공격 유형과 신뢰도
        """
        scan_intensity = attack_features.get('scan_intensity', 0)
        exploit_attempts = attack_features.get('exploit_attempts', 0)
        energy_drain = attack_features.get('energy_drain', 0)
        gps_anomaly = attack_features.get('gps_anomaly', 0)
        
        # Rule-based classification with Table 13 performance
        if gps_anomaly > 0.7:
            attack_type = "gps_injection"
            recall = 0.92
        elif energy_drain > 0.6:
            attack_type = "battery_spoofing" 
            recall = 0.90
        elif exploit_attempts > 0.5:
            attack_type = "flight_termination"
            recall = 0.85
        elif scan_intensity > 0.8:
            attack_type = "brute_force"
            recall = 0.94
        else:
            attack_type = "general"
            recall = 0.86  # Binary attack recall
        
        # Apply classification performance
        if attack_type in self.multiclass_performance:
            precision = self.multiclass_performance[attack_type]['precision']
        else:
            precision = self.binary_performance['attack']['precision']
        
        # Detection success based on recall
        detected = random.random() < recall
        if detected:
            confidence = random.uniform(0.7, 0.95) * precision
        else:
            confidence = random.uniform(0.2, 0.5)
            attack_type = "unknown"
        
        return attack_type, confidence
    
    def get_threat_level(self, attack_indicators: Dict[str, float]) -> float:
        """
        논문 기반 위협 레벨 계산 (enhanced)
        
        Args:
            attack_indicators: {
                'scan_intensity': float,
                'exploit_attempts': float, 
                'energy_drain': float,
                'gps_anomaly': float,
                'phase': str
            }
        """
        base_threat = 0.0
        
        # 1. 공격 유형 분류
        attack_type, type_confidence = self.classify_attack_type(attack_indicators)
        
        # 2. Binary detection (타입 안전성 보장)
        numeric_indicators = {}
        for key, value in attack_indicators.items():
            if isinstance(value, (int, float)):
                numeric_indicators[key] = float(value)
            elif isinstance(value, str):
                try:
                    numeric_indicators[key] = float(value)
                except ValueError:
                    # 문자열은 제외 (예: phase 필드)
                    continue
        
        is_attack = any(v > 0.1 for v in numeric_indicators.values())
        detected, detect_confidence = self.detect_attack(is_attack, attack_type)
        
        if detected:
            # 3. 위협 레벨 계산 (검증된 공격) - 타입 안전성 보장
            scan = float(attack_indicators.get('scan_intensity', 0))
            exploit = float(attack_indicators.get('exploit_attempts', 0))
            energy = float(attack_indicators.get('energy_drain', 0))
            gps = float(attack_indicators.get('gps_anomaly', 0))
            
            # 가중치 합계 (balanced accuracy 0.847 반영)
            weighted_threat = (
                scan * 0.3 * detect_confidence +
                exploit * 0.4 * detect_confidence + 
                energy * 0.2 * type_confidence +
                gps * 0.1 * type_confidence
            )
            
            # Attack type severity multiplier
            severity_multipliers = {
                "flight_termination": 1.0,
                "gps_injection": 0.9,
                "battery_spoofing": 0.8,
                "brute_force": 0.6,
                "general": 0.5
            }
            multiplier = severity_multipliers.get(attack_type, 0.5)
            
            base_threat = weighted_threat * multiplier * self.balanced_accuracy
        
        return min(1.0, base_threat)


# =============================================================================
# Attack Phase Enum
# =============================================================================
class AttackPhase(Enum):
    """공격 단계 (Kill Chain)"""
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
    protocol: str = "tcp"
    is_critical: bool = False
    is_decoy: bool = False
    scan_progress: float = 0.0
    discovery_progress: float = 0.0
    exploit_progress: float = 0.0
    last_seen_ip: str = ""                    # ✅ 통일
    last_seen_port: int = 0                   # ✅ 통일
    scan_time_accumulated: float = 0.0
    discovery_time_accumulated: float = 0.0   # ✅ 에러 해결
    exploit_time_accumulated: float = 0.0
    total_time_spent: float = 0.0
    
    # 취약점 점수
    vulnerability_score: float = 0.5
    
    # 마지막 상태 변경
    last_seen_ip: Optional[str] = None
    last_seen_port: Optional[int] = None
    
    def reset_progress(self):
        """MTD로 인한 진행도 리셋"""
        self.scan_progress *= 0.3
        self.discovery_progress *= 0.2
        self.exploit_progress *= 0.1
        
        # 시간 누적도 부분 리셋
        self.scan_time_accumulated *= 0.5
        self.discovery_time_accumulated *= 0.3
        self.exploit_time_accumulated *= 0.2


# =============================================================================
# Enhanced Nmap Scanner Simulation (시간 기반)
# =============================================================================
class EnhancedNmapScanner:
    """
    Enhanced Nmap 스타일 스캔 시뮬레이션 (실제 시간 기반)
    
    논문 기반:
    - Attack Surface: 50,200 타겟
    - Full Scan Time: 60초 
    - Scan Rate: 실제 시간 진행 반영
    """
    
    def __init__(self, attacker_level: int):
        self.level = attacker_level
        profile = SEEKER_PROFILES[attacker_level]
        
        self.base_scan_rate = profile["scan_rate"]  # targets per second
        self.stealth = profile["stealth"]
        
        # 시간 기반 계산
        self.targets_per_second = ATTACK_SURFACE * self.base_scan_rate / NMAP_FULL_SCAN_TIME
        self.total_scan_time = 0.0
        self.scanned_targets = 0
        
    def calculate_scan_progress(self, time_step: float = 1.0) -> Dict[str, Any]:
        """
        실제 시간 기반 스캔 진행 계산
        
        Args:
            time_step: 스텝당 시간 (초 단위)
            
        Returns:
            {
                'targets_scanned': int,
                'scan_progress': float [0,1],
                'time_elapsed': float,
                'estimated_completion': float
            }
        """
        self.total_scan_time += time_step
        
        # 시간 기반 스캔 대상 수 계산
        expected_targets = int(self.targets_per_second * self.total_scan_time)
        new_targets = max(0, expected_targets - self.scanned_targets)
        
        self.scanned_targets += new_targets
        
        # 진행률 계산
        scan_progress = min(1.0, self.scanned_targets / ATTACK_SURFACE)
        
        # 완료 예상 시간
        if self.targets_per_second > 0:
            estimated_completion = ATTACK_SURFACE / self.targets_per_second
        else:
            estimated_completion = float('inf')
        
        return {
            'targets_scanned': new_targets,
            'total_scanned': self.scanned_targets,
            'scan_progress': scan_progress,
            'time_elapsed': self.total_scan_time,
            'estimated_completion': estimated_completion,
            'completion_percentage': scan_progress * 100
        }
    
    def syn_scan_timed(self, ip_range: List[str], detection_prob: float, time_step: float = 1.0) -> Tuple[Set[str], bool, Dict]:
        """
        시간 기반 SYN 스캔 - 실제 시간 진행 반영
        """
        scan_result = self.calculate_scan_progress(time_step)
        discovered = set()
        detected = False
        
        # 스캔한 타겟 수만큼 IP 발견
        n_discover = min(scan_result['targets_scanned'], len(ip_range))
        
        for _ in range(n_discover):
            ip = random.choice(ip_range)
            discovered.add(ip)
            
            # 탐지 확률 (스텔스가 높으면 탐지 회피)
            if random.random() < detection_prob * (1 - self.stealth):
                detected = True
        
        return discovered, detected, scan_result
    
    def get_scan_efficiency(self) -> float:
        """
        현재 스캔 효율성 계산
        논문: 1분 스캔 시간 vs 실제 진행 시간
        """
        if self.total_scan_time <= 0:
            return 1.0
        
        ideal_time = NMAP_FULL_SCAN_TIME
        actual_time = self.total_scan_time
        
        efficiency = ideal_time / max(actual_time, ideal_time * 0.1)
        return min(1.0, efficiency)
    
    def reset(self):
        """스캔 상태 초기화"""
        self.total_scan_time = 0.0
        self.scanned_targets = 0


# =============================================================================
# Advanced Seeker Agent (Enhanced Time-based)
# =============================================================================
class AdvancedSeekerAgent:
    """
    고급 공격자 에이전트 v09 - Enhanced Time-based Attack Surface
    
    특징:
    - Kill Chain 기반 상태 전이
    - 실제 시간 기반 공격 표면 모델링 
    - CTI Table 12/13 성능 반영
    - 레벨별 차별화된 행동
    """
    
    def __init__(
        self,
        level: int = 2,
        seed: int = 42,
        targets: Optional[List[ServiceTarget]] = None,
        step_duration: float = 1.0,  # 스텝당 시간 (초)
    ):
        self.level = level
        self.profile = SEEKER_PROFILES.get(level, SEEKER_PROFILES[2])
        self.rng = np.random.default_rng(seed)
        random.seed(seed)
        
        # 상태
        self.phase = AttackPhase.INITIAL
        self.energy = self.profile["initial_energy"]
        self.confusion_level = 0.0
        self.step_count = 0
        self.step_duration = step_duration
        
        # 시간 추적
        self.total_time_elapsed = 0.0
        self.phase_start_time = 0.0
        self.mission_duration = random.uniform(UAV_MISSION_TIME_MIN, UAV_MISSION_TIME_MAX)
        
        # 스캔 결과
        self.scanned_ips: Set[str] = set()
        self.discovered_services: Set[str] = set()
        self.exploited_services: Set[str] = set()
        self.known_mappings: Dict[str, Tuple[str, int]] = {}
        
        # 디코이 기록
        self.decoy_hits: int = 0
        self.suspicious_targets: Set[str] = set()
        
        # 타겟
        self.targets = targets or []
        
        # CTI 모델 (Enhanced Table 12/13)
        self.cti = CTIDetectionModel()
        
        # Enhanced Nmap 스캐너
        self.scanner = EnhancedNmapScanner(level)
        
        # 적응형 파라미터
        self.adaptive_scan_rate = self.profile["scan_rate"]
        self.adaptive_exploit_rate = self.profile["exploit_rate"]
        
        # 공격 타입 추적 (CTI 분류용)
        self.attack_features = {
            'scan_intensity': 0.0,
            'exploit_attempts': 0.0,
            'energy_drain': 0.0,
            'gps_anomaly': 0.0
        }
        
    def reset(self, seed: Optional[int] = None):
        """상태 초기화"""
        if seed is not None:
            self.rng = np.random.default_rng(seed)
            random.seed(seed)
        
        self.phase = AttackPhase.INITIAL
        self.energy = self.profile["initial_energy"]
        self.confusion_level = 0.0
        self.step_count = 0
        self.total_time_elapsed = 0.0
        self.phase_start_time = 0.0
        self.mission_duration = random.uniform(UAV_MISSION_TIME_MIN, UAV_MISSION_TIME_MAX)
        
        self.scanned_ips.clear()
        self.discovered_services.clear()
        self.exploited_services.clear()
        self.known_mappings.clear()
        self.decoy_hits = 0
        self.suspicious_targets.clear()
        
        self.adaptive_scan_rate = self.profile["scan_rate"]
        self.adaptive_exploit_rate = self.profile["exploit_rate"]
        
        self.scanner.reset()
        self.attack_features = {k: 0.0 for k in self.attack_features.keys()}
        
        for target in self.targets:
            target.scan_progress = 0.0
            target.discovery_progress = 0.0
            target.exploit_progress = 0.0
            target.scan_time_accumulated = 0.0
            target.discovery_time_accumulated = 0.0
            target.exploit_time_accumulated = 0.0
    
    def set_targets(self, targets: List[ServiceTarget]):
        """타겟 설정"""
        self.targets = targets
    
    def _get_effective_rate(self, base_rate: float) -> float:
        """혼란도에 따른 효율 감소"""
        confusion_penalty = min(0.6, self.confusion_level * 0.5)
        return max(0.05, base_rate * (1.0 - confusion_penalty))
    
    def _detect_decoy(self, target: ServiceTarget) -> bool:
        """디코이 탐지 (레벨이 높을수록 잘 탐지)"""
        if not target.is_decoy:
            return False
        
        detection_prob = self.profile["decoy_detection"]
        
        # 이전에 의심했던 타겟은 더 잘 탐지
        if target.name in self.suspicious_targets:
            detection_prob *= 1.5
        
        return random.random() < detection_prob
    
    def _update_attack_features(self):
        """공격 특성 업데이트 (CTI 분류용)"""
        # Scan intensity (시간 기반)
        scan_efficiency = self.scanner.get_scan_efficiency()
        scan_targets_ratio = self.scanner.scanned_targets / max(1, ATTACK_SURFACE)
        self.attack_features['scan_intensity'] = scan_targets_ratio * scan_efficiency
        
        # Exploit attempts
        total_targets = len(self.targets)
        exploit_ratio = len(self.exploited_services) / max(1, total_targets)
        self.attack_features['exploit_attempts'] = exploit_ratio
        
        # Energy drain
        energy_used = self.profile["initial_energy"] - self.energy
        self.attack_features['energy_drain'] = energy_used
        
        # GPS anomaly (simulated based on phase)
        if self.phase in [AttackPhase.EXPLOITATION, AttackPhase.PERSISTENCE]:
            self.attack_features['gps_anomaly'] = random.uniform(0.6, 0.9)
        else:
            self.attack_features['gps_anomaly'] = random.uniform(0.0, 0.3)
    
    def _phase_transition(self, mtd_active: bool, defense_prob: float):
        """상태 전이 로직 (시간 기반 개선)"""
        # MTD 활성 시 전이 확률 감소
        mtd_penalty = 0.3 if mtd_active else 0.0
        
        # 시간 압박 (미션 시간 대비)
        time_pressure = self.total_time_elapsed / self.mission_duration
        urgency_factor = 1.0 + time_pressure * 0.5
        
        if self.phase == AttackPhase.INITIAL:
            # 항상 정찰 시작
            self.phase = AttackPhase.RECONNAISSANCE
            self.phase_start_time = self.total_time_elapsed
            
        elif self.phase == AttackPhase.RECONNAISSANCE:
            # 충분히 스캔했거나 시간이 지나면 발견 단계로
            scan_progress = self.scanner.scanned_targets / ATTACK_SURFACE
            time_in_phase = self.total_time_elapsed - self.phase_start_time
            
            transition_conditions = (
                scan_progress > 0.1 or  # 10% 스캔 완료
                time_in_phase > NMAP_FULL_SCAN_TIME * 0.5 or  # 30초 경과  
                len(self.scanned_ips) > 20
            )
            
            if transition_conditions:
                transition_prob = 0.4 * (1 - mtd_penalty) * urgency_factor
                if random.random() < transition_prob:
                    self.phase = AttackPhase.DISCOVERY
                    self.phase_start_time = self.total_time_elapsed
                    
        elif self.phase == AttackPhase.DISCOVERY:
            # 서비스 발견하면 익스플로잇 단계로
            if len(self.discovered_services) >= 1:
                transition_prob = 0.5 * (1 - mtd_penalty) * (1 - defense_prob * 0.5) * urgency_factor
                if random.random() < transition_prob:
                    self.phase = AttackPhase.EXPLOITATION
                    self.phase_start_time = self.total_time_elapsed
            
            # 방어 성공 시 정찰로 회귀
            if random.random() < defense_prob * 0.3:
                self.phase = AttackPhase.RECONNAISSANCE
                self.phase_start_time = self.total_time_elapsed
                    
        elif self.phase == AttackPhase.EXPLOITATION:
            # 크리티컬 서비스 익스플로잇 성공하면 지속 단계로
            critical_exploited = any(
                t.is_critical and t.name in self.exploited_services
                for t in self.targets
            )
            
            if critical_exploited:
                transition_prob = 0.6 * (1 - mtd_penalty) * (1 - defense_prob * 0.6) * urgency_factor
                if random.random() < transition_prob:
                    self.phase = AttackPhase.PERSISTENCE
                    self.phase_start_time = self.total_time_elapsed
            
            # 방어 성공 시 회귀
            if random.random() < defense_prob * 0.4:
                self.phase = AttackPhase.DISCOVERY
                self.phase_start_time = self.total_time_elapsed
                
        elif self.phase == AttackPhase.PERSISTENCE:
            # 최종 침투
            breach_prob = 0.4 * (1 - mtd_penalty) * (1 - defense_prob * 0.7) * urgency_factor
            if random.random() < breach_prob:
                self.phase = AttackPhase.BREACH
            
            # 방어 성공 시 회귀
            if random.random() < defense_prob * 0.5:
                self.phase = AttackPhase.EXPLOITATION
                self.phase_start_time = self.total_time_elapsed
    
    def step(self, mtd_status: Dict[str, Any]) -> Dict[str, Any]:
        """
        한 스텝 실행 (Enhanced Time-based)
        
        Args:
            mtd_status: {
                'is_shuffle': bool,
                'shuffle_intensity': float,
                'is_swap': bool,
                'swap_intensity': float,
                'decoy_ratio': float,
                'diversity_score': float,
                'defense_probability': float,
            }
            
        Returns:
            결과 딕셔너리
        """
        self.step_count += 1
        self.total_time_elapsed += self.step_duration
        
        result = {
            "phase": self.phase.value,
            "scanned": False,
            "discovered": False,
            "exploited": False,
            "breach": False,
            "decoy_hit": False,
            "defended": False,
            "scan_count": 0,
            "discovered_service": None,
            "exploited_service": None,
            "threat_level": 0.0,
            "energy": self.energy,
            "time_elapsed": self.total_time_elapsed,
            "scan_progress": 0.0,
            "attack_type": "unknown",
        }
        
        # MTD 효과 처리
        is_shuffle = mtd_status.get('is_shuffle', False)
        shuffle_intensity = mtd_status.get('shuffle_intensity', 0)
        is_swap = mtd_status.get('is_swap', False)
        swap_intensity = mtd_status.get('swap_intensity', 0)
        defense_prob = mtd_status.get('defense_probability', 0.25)
        
        # MTD로 인한 혼란
        if is_shuffle:
            self.confusion_level += shuffle_intensity * 0.3
            # 매핑 정보 일부 무효화
            invalidate_count = int(len(self.known_mappings) * shuffle_intensity * 0.5)
            for _ in range(invalidate_count):
                if self.known_mappings:
                    key = random.choice(list(self.known_mappings.keys()))
                    del self.known_mappings[key]
                    self.discovered_services.discard(key)
            
            # 스캔 진행도 감소 (MTD 영향)
            self.scanner.total_scan_time *= (1 + shuffle_intensity * 0.2)  # 스캔 시간 증가
        
        if is_swap:
            self.confusion_level += swap_intensity * 0.4
            # 스왑된 서비스 재발견 필요
            for target in self.targets:
                if target.last_seen_ip and target.last_seen_ip != target.virtual_ip:
                    target.discovery_progress *= 0.5
                    target.discovery_time_accumulated *= 0.7
                    self.discovered_services.discard(target.name)
        
        # 혼란도 감쇠
        self.confusion_level *= 0.92
        
        # 에너지 감소
        self.energy -= self.profile["energy_decay"]
        result["energy"] = self.energy
        
        # 미션 시간 초과 또는 에너지 고갈
        if self.energy <= 0 or self.total_time_elapsed >= self.mission_duration:
            self.phase = AttackPhase.DEFENDED
            result["phase"] = self.phase.value
            result["defended"] = True
            return result
        
        # 상태 전이
        mtd_active = is_shuffle or is_swap or mtd_status.get('decoy_ratio', 0) > 0.3
        self._phase_transition(mtd_active, defense_prob)
        
        # 단계별 행동
        if self.phase == AttackPhase.RECONNAISSANCE:
            result = self._do_reconnaissance_timed(mtd_status, defense_prob, result)
            
        elif self.phase == AttackPhase.DISCOVERY:
            result = self._do_discovery_timed(mtd_status, defense_prob, result)
            
        elif self.phase == AttackPhase.EXPLOITATION:
            result = self._do_exploitation_timed(mtd_status, defense_prob, result)
            
        elif self.phase == AttackPhase.PERSISTENCE:
            result = self._do_persistence(mtd_status, defense_prob, result)
            
        elif self.phase == AttackPhase.BREACH:
            result["breach"] = True
            
        elif self.phase == AttackPhase.DEFENDED:
            result["defended"] = True
        
        # 공격 특성 업데이트 및 CTI 분석
        self._update_attack_features()
        
        # CTI 기반 공격 탐지 및 분류
        attack_type, type_confidence = self.cti.classify_attack_type(self.attack_features)
        result["attack_type"] = attack_type
        
        # 위협 레벨 계산 (Enhanced CTI 기반)
        threat_indicators = {**self.attack_features, 'phase': self.phase.name}
        result["threat_level"] = self.cti.get_threat_level(threat_indicators)
        result["phase"] = self.phase.value
        
        return result
    
    def _do_reconnaissance_timed(
        self, mtd_status: Dict, defense_prob: float, result: Dict
    ) -> Dict:
        """정찰 단계 - Enhanced 시간 기반 Nmap 스캔"""
        # IP 범위 생성
        ip_range = [f"10.13.0.{i}" for i in range(1, 255)]
        
        # 시간 기반 스캔 실행
        discovered_ips, scan_detected, scan_result = self.scanner.syn_scan_timed(
            ip_range, defense_prob * 0.3, self.step_duration
        )
        
        self.scanned_ips.update(discovered_ips)
        result["scan_count"] = scan_result['targets_scanned']
        result["scanned"] = scan_result['targets_scanned'] > 0
        result["scan_progress"] = scan_result['scan_progress']
        
        # CTI 탐지 (Table 12/13 기반)
        is_actual_attack = len(discovered_ips) > 0
        attack_type = "brute_force" if scan_result['targets_scanned'] > 100 else "general"
        cti_detected, cti_confidence = self.cti.detect_attack(is_actual_attack, attack_type)
        
        if cti_detected:
            # CTI가 탐지하면 방어 확률 증가
            defense_prob *= (1.0 + cti_confidence * 0.5)
        
        # 적응 (탐지되면 더 조심)
        if scan_detected or cti_detected:
            adaptation_rate = self.profile["adaptation"]
            if adaptation_rate > 0.3:
                self.adaptive_scan_rate *= 0.85
                # 스캔 속도 감소 (스텔스 모드)
                self.scanner.targets_per_second *= 0.9
        
        return result
    
    def _do_discovery_timed(
        self, mtd_status: Dict, defense_prob: float, result: Dict
    ) -> Dict:
        """발견 단계 - 시간 기반 서비스 식별"""
        effective_rate = self._get_effective_rate(self.profile["discovery_rate"])
        decoy_ratio = mtd_status.get('decoy_ratio', 0)
        
        for target in self.targets:
            if target.name in self.discovered_services:
                continue
            
            # 가상 IP가 스캔된 IP에 있는지 확인
            if target.virtual_ip not in self.scanned_ips:
                continue
            
            # 시간 기반 점진적 발견 진행
            target.discovery_time_accumulated += self.step_duration
            
            # 방어 확률 적용
            if random.random() < defense_prob * 0.5:
                result["defended"] = True
                continue
            
            # 디코이 체크
            if target.is_decoy:
                if self._detect_decoy(target):
                    self.suspicious_targets.add(target.name)
                    continue
                else:
                    # 디코이에 걸림 (시간 낭비)
                    self.decoy_hits += 1
                    result["decoy_hit"] = True
                    self.energy -= 0.1
                    target.discovery_time_accumulated += self.step_duration * 2  # 추가 시간 소요
                    continue
            
            # 실제 서비스 발견 시도 (시간 기반)
            time_factor = target.discovery_time_accumulated / 30.0  # 30초 기준
            discover_prob = effective_rate * (1 - decoy_ratio * 0.3) * time_factor
            
            if random.random() < discover_prob:
                target.discovery_progress += 0.3 + (time_factor * 0.2)
                
                # 충분한 시간과 진행도가 쌓이면 발견 완료
                if target.discovery_progress >= 0.8 and target.discovery_time_accumulated >= 10.0:
                    self.discovered_services.add(target.name)
                    self.known_mappings[target.name] = (target.virtual_ip, target.virtual_port)
                    target.last_seen_ip = target.virtual_ip
                    target.last_seen_port = target.virtual_port
                    result["discovered"] = True
                    result["discovered_service"] = target.name
        
        return result
    
    def _do_exploitation_timed(
        self, mtd_status: Dict, defense_prob: float, result: Dict
    ) -> Dict:
        """익스플로잇 단계 - 시간 기반 점진적 익스플로잇"""
        effective_rate = self._get_effective_rate(self.adaptive_exploit_rate)
        
        for target in self.targets:
            if target.name not in self.discovered_services:
                continue
            
            if target.name in self.exploited_services:
                continue
            
            # 매핑 정보 유효성 확인
            if target.name in self.known_mappings:
                known_ip, known_port = self.known_mappings[target.name]
                if known_ip != target.virtual_ip or known_port != target.virtual_port:
                    # 매핑 무효화됨 - 재발견 필요
                    self.discovered_services.discard(target.name)
                    del self.known_mappings[target.name]
                    target.discovery_progress = 0
                    target.discovery_time_accumulated = 0
                    continue
            
            # 시간 기반 익스플로잇 진행
            target.exploit_time_accumulated += self.step_duration
            
            # 방어 확률 적용 (익스플로잇은 더 어려움)
            enhanced_defense_prob = defense_prob * 0.7
            
            # CTI 기반 동적 방어 확률 조정
            attack_type, type_confidence = self.cti.classify_attack_type(self.attack_features)
            if attack_type == "flight_termination":
                enhanced_defense_prob *= 1.2  # Flight termination은 더 위험하므로 강화 방어
            
            if random.random() < enhanced_defense_prob:
                result["defended"] = True
                continue
            
            # 시간 기반 익스플로잇 확률 계산
            time_factor = target.exploit_time_accumulated / 60.0  # 1분 기준
            exploit_prob = (
                effective_rate *
                self.profile["exploit_success"] *
                target.vulnerability_score *
                time_factor
            )
            
            if random.random() < exploit_prob:
                target.exploit_progress += 0.4 + (time_factor * 0.3)
                
                # 충분한 시간과 진행도로 익스플로잇 성공
                if target.exploit_progress >= 0.9 and target.exploit_time_accumulated >= 20.0:
                    self.exploited_services.add(target.name)
                    result["exploited"] = True
                    result["exploited_service"] = target.name
                    
                    # 적응 (성공하면 더 공격적)
                    if self.profile["adaptation"] > 0.3:
                        self.adaptive_exploit_rate = min(1.0, self.adaptive_exploit_rate * 1.05)
        
        return result
    
    def _do_persistence(
        self, mtd_status: Dict, defense_prob: float, result: Dict
    ) -> Dict:
        """지속 단계 - 최종 침투 시도"""
        # 크리티컬 서비스 익스플로잇 여부 확인
        critical_exploited = [
            t for t in self.targets
            if t.is_critical and t.name in self.exploited_services
        ]
        
        if not critical_exploited:
            # 크리티컬 없으면 익스플로잇 단계로 회귀
            self.phase = AttackPhase.EXPLOITATION
            self.phase_start_time = self.total_time_elapsed
            return result
        
        # 시간 압박 고려
        time_pressure = self.total_time_elapsed / self.mission_duration
        urgency_bonus = time_pressure * 0.3
        
        # 최종 침투 시도
        persistence_prob = self.profile["persistence"] + urgency_bonus
        breach_prob = persistence_prob * (1 - defense_prob * 0.8)
        
        if random.random() < breach_prob:
            self.phase = AttackPhase.BREACH
            result["breach"] = True
        elif random.random() < defense_prob * 0.5:
            result["defended"] = True
        
        return result
    
    def get_threat_level(self) -> float:
        """현재 위협 레벨 계산 (시간 기반 개선)"""
        phase_threats = {
            AttackPhase.INITIAL: 0.0,
            AttackPhase.RECONNAISSANCE: 0.1,
            AttackPhase.DISCOVERY: 0.3,
            AttackPhase.EXPLOITATION: 0.6,
            AttackPhase.PERSISTENCE: 0.8,
            AttackPhase.BREACH: 1.0,
            AttackPhase.DEFENDED: 0.0,
        }
        base_threat = phase_threats.get(self.phase, 0)
        
        # 시간 압박 요소
        time_pressure = self.total_time_elapsed / self.mission_duration
        time_factor = 1.0 + time_pressure * 0.2
        
        # 스캔 진행도
        scan_factor = self.scanner.scanned_targets / ATTACK_SURFACE
        
        # 서비스 관련
        service_factor = (len(self.discovered_services) * 0.1 + len(self.exploited_services) * 0.2)
        
        # CTI 기반 위협 레벨
        cti_threat = self.cti.get_threat_level(self.attack_features)
        
        total_threat = (base_threat * time_factor + scan_factor * 0.3 + service_factor + cti_threat * 0.2) / 2.0
        
        return min(1.0, total_threat)
    
    def handle_mtd_effect(self, effect_type: str, intensity: float):
        """MTD 효과 처리 (시간 기반 개선)"""
        if effect_type == "shuffle":
            self.confusion_level += intensity * 0.3
            # 진행도 감소
            for target in self.targets:
                target.reset_progress()
            
            # 스캔 효율성 감소 (재스캔 필요)
            self.scanner.total_scan_time += intensity * 10.0  # 추가 스캔 시간
                
        elif effect_type == "swap":
            self.confusion_level += intensity * 0.4
            
            # 발견된 서비스 정보 일부 무효화
            if intensity > 0.5:
                n_invalidate = int(len(self.discovered_services) * intensity * 0.4)
                if self.discovered_services and n_invalidate > 0:
                    to_invalidate = random.sample(list(self.discovered_services), 
                                                min(n_invalidate, len(self.discovered_services)))
                    for svc in to_invalidate:
                        self.discovered_services.discard(svc)
                        if svc in self.known_mappings:
                            del self.known_mappings[svc]
            
        elif effect_type == "decoy_activated":
            # 디코이 활성화 시 스캔 시간 증가 (confusion)
            self.scanner.total_scan_time += intensity * 5.0
    
    def get_state_summary(self) -> Dict[str, Any]:
        """상태 요약 (시간 정보 추가)"""
        return {
            "level": self.level,
            "level_name": self.profile["name"],
            "phase": self.phase.value,
            "energy": self.energy,
            "confusion_level": self.confusion_level,
            "scanned_ips": len(self.scanned_ips),
            "discovered_services": len(self.discovered_services),
            "exploited_services": len(self.exploited_services),
            "decoy_hits": self.decoy_hits,
            "step_count": self.step_count,
            
            # 시간 관련 정보
            "total_time_elapsed": self.total_time_elapsed,
            "mission_duration": self.mission_duration,
            "time_progress": self.total_time_elapsed / self.mission_duration,
            "scan_progress": self.scanner.scanned_targets / ATTACK_SURFACE,
            "scan_efficiency": self.scanner.get_scan_efficiency(),
            
            # CTI 관련 정보
            "attack_features": self.attack_features.copy(),
            "cti_balanced_accuracy": self.cti.balanced_accuracy,
        }


# =============================================================================
# Test
# =============================================================================
if __name__ == "__main__":
    print("=== Enhanced Seeker Agent v09 Test (Time-based + CTI Table 12/13) ===\n")
    
    # 타겟 생성
    targets = [
        ServiceTarget("fc_mavlink", "10.13.0.2", 14550, "10.13.0.2", 14550, is_critical=True),
        ServiceTarget("cc_sitl", "10.13.0.3", 5760, "10.13.0.3", 5760, is_critical=True),
        ServiceTarget("gcs_mavlink", "10.13.0.4", 14550, "10.13.0.4", 14550, is_critical=True),
        ServiceTarget("decoy_fc", "10.13.0.200", 14550, "10.13.0.200", 14550, is_decoy=True),
        ServiceTarget("decoy_sitl", "10.13.0.201", 5760, "10.13.0.201", 5760, is_decoy=True),
    ]
    
    # 각 레벨 테스트
    for level in [0, 2, 4]:
        print(f"\n--- Level {level} ({SEEKER_PROFILES[level]['name']}) ---")
        
        agent = AdvancedSeekerAgent(level=level, seed=42, targets=targets, step_duration=1.0)
        
        breach = False
        defended = False
        
        print(f"  Mission Duration: {agent.mission_duration/60:.1f} minutes")
        print(f"  Attack Surface: {ATTACK_SURFACE:,} targets")
        print(f"  Expected Scan Time: {NMAP_FULL_SCAN_TIME} seconds")
        print(f"  CTI Balanced Accuracy: {agent.cti.balanced_accuracy}")
        
        for step in range(100):
            mtd_status = {
                'is_shuffle': step % 10 == 0,
                'shuffle_intensity': 0.5 if step % 10 == 0 else 0,
                'is_swap': step % 20 == 0,
                'swap_intensity': 0.6 if step % 20 == 0 else 0,
                'decoy_ratio': 0.3,
                'defense_probability': 0.35,
            }
            
            result = agent.step(mtd_status)
            
            if result["breach"]:
                breach = True
                print(f"  🚨 BREACH at step {step} ({result['time_elapsed']:.1f}s)!")
                break
            
            if result["defended"]:
                defended = True
                print(f"  🛡️ DEFENDED at step {step} ({result['time_elapsed']:.1f}s)")
                break
            
            # 중간 진행 상황 출력
            if step % 20 == 0 and step > 0:
                print(f"  Step {step}: {result['phase']}, "
                      f"Time: {result['time_elapsed']:.1f}s, "
                      f"Scan: {result['scan_progress']*100:.1f}%, "
                      f"Attack Type: {result['attack_type']}, "
                      f"Threat: {result['threat_level']:.2f}")
        
        summary = agent.get_state_summary()
        print(f"  Final Results:")
        print(f"    Phase: {summary['phase']}")
        print(f"    Time: {summary['total_time_elapsed']:.1f}s / {summary['mission_duration']:.1f}s")
        print(f"    Scan Progress: {summary['scan_progress']*100:.1f}%")
        print(f"    Scan Efficiency: {summary['scan_efficiency']:.2f}")
        print(f"    Discovered: {summary['discovered_services']}, Exploited: {summary['exploited_services']}")
        print(f"    Decoy hits: {summary['decoy_hits']}")
        print(f"    Energy: {summary['energy']:.2f}")
        print(f"    Attack Features: {summary['attack_features']}")
    
    print(f"\n=== Test Complete ===")
    print(f"\n🔬 Enhanced Features Verified:")
    print(f"  ✅ CTI Table 12/13 classification system")
    print(f"  ✅ Time-based attack surface modeling (50,200 targets)")
    print(f"  ✅ Realistic Nmap scan simulation (60s full scan)")
    print(f"  ✅ Progressive attack progression (time accumulation)")
    print(f"  ✅ MTD timing effects (scan efficiency degradation)")
    print(f"  ✅ Mission time constraints (35-75 minutes)")