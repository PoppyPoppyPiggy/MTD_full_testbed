#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Seeker Agent v09 - 고급 공격자 시뮬레이션
==========================================

논문 Section IV 실험을 위한 현실적인 공격자 에이전트.

특징:
1. SEEKER_PROFILES (L0-L4) 완벽 호환
2. Nmap 스타일 스캔 시뮬레이션
3. Kill Chain 기반 공격 단계 (Recon → Discovery → Exploit → Breach)
4. CTI 탐지 정확도 반영 (Precision=0.66, Recall=0.85, F1=0.71)
5. MTD 효과에 따른 공격자 혼란/적응

공격자 레벨:
- L0 (Script Kiddie): 낮은 스캔율, 디코이에 잘 걸림
- L1 (Hobbyist): 중간 능력
- L2 (Professional): 높은 발견율, 적응력
- L3 (Expert): 스텔스, 디코이 회피
- L4 (APT): 최고 수준, 지속성

Author: MTD-RL Research Team
Version: 0.9.2
"""
from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np


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
# CTI Detection Model
# =============================================================================
@dataclass
class CTIDetectionModel:
    """
    CTI 탐지 모델 - 논문 Table 7 기반
    
    GPS Spoofing Detection (논문 결과):
    - Precision: 0.66
    - Recall: 0.85
    - F1-Score: 0.71
    """
    precision: float = 0.66
    recall: float = 0.85
    f1_score: float = 0.71
    
    def detect_attack(self, is_actual_attack: bool) -> Tuple[bool, float]:
        """
        공격 탐지 시뮬레이션
        
        Args:
            is_actual_attack: 실제 공격 여부
            
        Returns:
            (detected, confidence): 탐지 여부와 신뢰도
        """
        if is_actual_attack:
            # True Positive: Recall 확률로 탐지
            detected = random.random() < self.recall
            confidence = random.uniform(0.7, 0.95) if detected else random.uniform(0.3, 0.5)
        else:
            # False Positive: (1 - Precision) 확률로 오탐
            # FP_rate = FP / (FP + TN) ≈ 1 - Precision (근사)
            fp_rate = 1.0 - self.precision
            detected = random.random() < fp_rate * 0.5  # 실제 FP는 더 낮음
            confidence = random.uniform(0.4, 0.6) if detected else random.uniform(0.1, 0.3)
        
        return detected, confidence
    
    def get_threat_level(self, attack_indicators: Dict[str, float]) -> float:
        """
        공격 지표들을 종합하여 위협 레벨 계산
        
        Args:
            attack_indicators: {
                'scan_intensity': float,
                'exploit_attempts': float,
                'anomaly_score': float,
            }
        """
        base_threat = 0.0
        
        # 스캔 강도
        scan = attack_indicators.get('scan_intensity', 0)
        if scan > 0.1:
            detected, conf = self.detect_attack(True)
            if detected:
                base_threat += scan * conf * 0.4
        
        # 익스플로잇 시도
        exploit = attack_indicators.get('exploit_attempts', 0)
        if exploit > 0:
            detected, conf = self.detect_attack(True)
            if detected:
                base_threat += exploit * conf * 0.5
        
        # 이상 점수
        anomaly = attack_indicators.get('anomaly_score', 0)
        base_threat += anomaly * 0.1
        
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
    """공격 대상 서비스"""
    name: str
    real_ip: str
    real_port: int
    virtual_ip: str
    virtual_port: int
    is_critical: bool = False
    is_decoy: bool = False
    
    # 공격 진행 상태
    scan_progress: float = 0.0
    discovery_progress: float = 0.0
    exploit_progress: float = 0.0
    
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


# =============================================================================
# Nmap Scanner Simulation
# =============================================================================
class NmapScanner:
    """
    Nmap 스타일 스캔 시뮬레이션
    
    스캔 타입:
    - SYN Scan: 빠르지만 탐지됨
    - Service Scan: 느리지만 정보 많음
    - Stealth Scan: 느리고 탐지 회피
    """
    
    def __init__(self, attacker_level: int):
        self.level = attacker_level
        profile = SEEKER_PROFILES[attacker_level]
        
        self.scan_rate = profile["scan_rate"]
        self.stealth = profile["stealth"]
        
    def syn_scan(self, ip_range: List[str], detection_prob: float) -> Tuple[Set[str], bool]:
        """
        SYN 스캔 - 열린 포트 발견
        
        Returns:
            (discovered_ips, was_detected)
        """
        discovered = set()
        detected = False
        
        n_scan = int(len(ip_range) * self.scan_rate * 2)
        
        for _ in range(min(n_scan, len(ip_range))):
            ip = random.choice(ip_range)
            discovered.add(ip)
            
            # 탐지 확률 (스텔스가 높으면 탐지 회피)
            if random.random() < detection_prob * (1 - self.stealth):
                detected = True
        
        return discovered, detected
    
    def service_scan(self, target_ip: str, ports: List[int]) -> Dict[int, str]:
        """
        서비스 스캔 - 포트별 서비스 식별
        """
        services = {}
        
        for port in ports:
            if random.random() < self.scan_rate * 1.5:
                # 서비스 식별 (실제로는 배너 그래빙)
                if port == 14550:
                    services[port] = "mavlink"
                elif port == 5760:
                    services[port] = "sitl"
                elif port == 3000:
                    services[port] = "http"
                else:
                    services[port] = "unknown"
        
        return services


# =============================================================================
# Advanced Seeker Agent
# =============================================================================
class AdvancedSeekerAgent:
    """
    고급 공격자 에이전트 v09
    
    특징:
    - Kill Chain 기반 상태 전이
    - MTD 효과 반영
    - CTI 탐지 회피/적응
    - 레벨별 차별화된 행동
    """
    
    def __init__(
        self,
        level: int = 2,
        seed: int = 42,
        targets: Optional[List[ServiceTarget]] = None,
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
        
        # CTI 모델
        self.cti = CTIDetectionModel()
        
        # Nmap 스캐너
        self.scanner = NmapScanner(level)
        
        # 적응형 파라미터
        self.adaptive_scan_rate = self.profile["scan_rate"]
        self.adaptive_exploit_rate = self.profile["exploit_rate"]
        
    def reset(self, seed: Optional[int] = None):
        """상태 초기화"""
        if seed is not None:
            self.rng = np.random.default_rng(seed)
            random.seed(seed)
        
        self.phase = AttackPhase.INITIAL
        self.energy = self.profile["initial_energy"]
        self.confusion_level = 0.0
        self.step_count = 0
        
        self.scanned_ips.clear()
        self.discovered_services.clear()
        self.exploited_services.clear()
        self.known_mappings.clear()
        self.decoy_hits = 0
        self.suspicious_targets.clear()
        
        self.adaptive_scan_rate = self.profile["scan_rate"]
        self.adaptive_exploit_rate = self.profile["exploit_rate"]
        
        for target in self.targets:
            target.scan_progress = 0.0
            target.discovery_progress = 0.0
            target.exploit_progress = 0.0
    
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
    
    def _phase_transition(self, mtd_active: bool, defense_prob: float):
        """상태 전이 로직"""
        # MTD 활성 시 전이 확률 감소
        mtd_penalty = 0.3 if mtd_active else 0.0
        
        if self.phase == AttackPhase.INITIAL:
            # 항상 정찰 시작
            self.phase = AttackPhase.RECONNAISSANCE
            
        elif self.phase == AttackPhase.RECONNAISSANCE:
            # 충분히 스캔했으면 발견 단계로
            if len(self.scanned_ips) > 5:
                transition_prob = 0.3 * (1 - mtd_penalty)
                if random.random() < transition_prob:
                    self.phase = AttackPhase.DISCOVERY
                    
        elif self.phase == AttackPhase.DISCOVERY:
            # 서비스 발견하면 익스플로잇 단계로
            if len(self.discovered_services) >= 1:
                transition_prob = 0.4 * (1 - mtd_penalty) * (1 - defense_prob * 0.5)
                if random.random() < transition_prob:
                    self.phase = AttackPhase.EXPLOITATION
            
            # 방어 성공 시 정찰로 회귀
            if random.random() < defense_prob * 0.3:
                self.phase = AttackPhase.RECONNAISSANCE
                    
        elif self.phase == AttackPhase.EXPLOITATION:
            # 크리티컬 서비스 익스플로잇 성공하면 지속 단계로
            critical_exploited = any(
                t.is_critical and t.name in self.exploited_services
                for t in self.targets
            )
            
            if critical_exploited:
                transition_prob = 0.5 * (1 - mtd_penalty) * (1 - defense_prob * 0.6)
                if random.random() < transition_prob:
                    self.phase = AttackPhase.PERSISTENCE
            
            # 방어 성공 시 회귀
            if random.random() < defense_prob * 0.4:
                self.phase = AttackPhase.DISCOVERY
                
        elif self.phase == AttackPhase.PERSISTENCE:
            # 최종 침투
            breach_prob = 0.3 * (1 - mtd_penalty) * (1 - defense_prob * 0.7)
            if random.random() < breach_prob:
                self.phase = AttackPhase.BREACH
            
            # 방어 성공 시 회귀
            if random.random() < defense_prob * 0.5:
                self.phase = AttackPhase.EXPLOITATION
    
    def step(self, mtd_status: Dict[str, Any]) -> Dict[str, Any]:
        """
        한 스텝 실행
        
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
        
        if is_swap:
            self.confusion_level += swap_intensity * 0.4
            # 스왑된 서비스 재발견 필요
            for target in self.targets:
                if target.last_seen_ip and target.last_seen_ip != target.virtual_ip:
                    target.discovery_progress *= 0.5
                    self.discovered_services.discard(target.name)
        
        # 혼란도 감쇠
        self.confusion_level *= 0.92
        
        # 에너지 감소
        self.energy -= self.profile["energy_decay"]
        result["energy"] = self.energy
        
        # 에너지 고갈 시 종료
        if self.energy <= 0:
            self.phase = AttackPhase.DEFENDED
            result["phase"] = self.phase.value
            result["defended"] = True
            return result
        
        # 상태 전이
        mtd_active = is_shuffle or is_swap or mtd_status.get('decoy_ratio', 0) > 0.3
        self._phase_transition(mtd_active, defense_prob)
        
        # 단계별 행동
        if self.phase == AttackPhase.RECONNAISSANCE:
            result = self._do_reconnaissance(mtd_status, defense_prob, result)
            
        elif self.phase == AttackPhase.DISCOVERY:
            result = self._do_discovery(mtd_status, defense_prob, result)
            
        elif self.phase == AttackPhase.EXPLOITATION:
            result = self._do_exploitation(mtd_status, defense_prob, result)
            
        elif self.phase == AttackPhase.PERSISTENCE:
            result = self._do_persistence(mtd_status, defense_prob, result)
            
        elif self.phase == AttackPhase.BREACH:
            result["breach"] = True
            
        elif self.phase == AttackPhase.DEFENDED:
            result["defended"] = True
        
        # 위협 레벨 계산
        result["threat_level"] = self._calculate_threat_level(result)
        result["phase"] = self.phase.value
        
        return result
    
    def _do_reconnaissance(
        self, mtd_status: Dict, defense_prob: float, result: Dict
    ) -> Dict:
        """정찰 단계 - Nmap 스캔"""
        effective_scan_rate = self._get_effective_rate(self.adaptive_scan_rate)
        
        # IP 범위 생성
        ip_range = [f"10.13.0.{i}" for i in range(1, 255)]
        
        # 스캔 실행
        n_scan = int(len(ip_range) * effective_scan_rate)
        scan_detected = False
        
        for _ in range(n_scan):
            ip = random.choice(ip_range)
            
            # 방어 확률 적용
            if random.random() < defense_prob * 0.3:
                result["defended"] = True
                continue
            
            self.scanned_ips.add(ip)
            result["scan_count"] += 1
            
            # CTI 탐지
            detected, _ = self.cti.detect_attack(True)
            if detected:
                scan_detected = True
        
        result["scanned"] = result["scan_count"] > 0
        
        # 적응 (탐지되면 더 조심)
        if scan_detected and self.profile["adaptation"] > 0.3:
            self.adaptive_scan_rate *= 0.9
        
        return result
    
    def _do_discovery(
        self, mtd_status: Dict, defense_prob: float, result: Dict
    ) -> Dict:
        """발견 단계 - 서비스 식별"""
        effective_rate = self._get_effective_rate(self.profile["discovery_rate"])
        decoy_ratio = mtd_status.get('decoy_ratio', 0)
        
        for target in self.targets:
            if target.name in self.discovered_services:
                continue
            
            # 가상 IP가 스캔된 IP에 있는지 확인
            if target.virtual_ip not in self.scanned_ips:
                continue
            
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
                    # 디코이에 걸림
                    self.decoy_hits += 1
                    result["decoy_hit"] = True
                    self.energy -= 0.1  # 에너지 낭비
                    continue
            
            # 서비스 발견 시도
            discover_prob = effective_rate * (1 - decoy_ratio * 0.3)
            
            if random.random() < discover_prob:
                target.discovery_progress += 0.4
                
                if target.discovery_progress >= 0.8:
                    self.discovered_services.add(target.name)
                    self.known_mappings[target.name] = (target.virtual_ip, target.virtual_port)
                    target.last_seen_ip = target.virtual_ip
                    target.last_seen_port = target.virtual_port
                    result["discovered"] = True
                    result["discovered_service"] = target.name
        
        return result
    
    def _do_exploitation(
        self, mtd_status: Dict, defense_prob: float, result: Dict
    ) -> Dict:
        """익스플로잇 단계"""
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
                    continue
            
            # 방어 확률 적용 (익스플로잇은 더 어려움)
            if random.random() < defense_prob * 0.7:
                result["defended"] = True
                continue
            
            # 익스플로잇 시도
            exploit_prob = (
                effective_rate *
                self.profile["exploit_success"] *
                target.vulnerability_score
            )
            
            if random.random() < exploit_prob:
                target.exploit_progress += 0.5
                
                if target.exploit_progress >= 0.9:
                    self.exploited_services.add(target.name)
                    result["exploited"] = True
                    result["exploited_service"] = target.name
                    
                    # 적응 (성공하면 더 공격적)
                    if self.profile["adaptation"] > 0.3:
                        self.adaptive_exploit_rate = min(1.0, self.adaptive_exploit_rate * 1.1)
        
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
            return result
        
        # 최종 침투 시도
        persistence_prob = self.profile["persistence"]
        breach_prob = persistence_prob * (1 - defense_prob * 0.8)
        
        if random.random() < breach_prob:
            self.phase = AttackPhase.BREACH
            result["breach"] = True
        elif random.random() < defense_prob * 0.5:
            result["defended"] = True
        
        return result
    
    def _calculate_threat_level(self, result: Dict) -> float:
        """현재 위협 레벨 계산"""
        threat = 0.0
        
        # 단계별 기본 위협
        phase_threat = {
            AttackPhase.INITIAL: 0.0,
            AttackPhase.RECONNAISSANCE: 0.1,
            AttackPhase.DISCOVERY: 0.3,
            AttackPhase.EXPLOITATION: 0.6,
            AttackPhase.PERSISTENCE: 0.8,
            AttackPhase.BREACH: 1.0,
            AttackPhase.DEFENDED: 0.0,
        }
        threat += phase_threat.get(self.phase, 0)
        
        # 발견/익스플로잇 서비스 수
        threat += len(self.discovered_services) * 0.05
        threat += len(self.exploited_services) * 0.1
        
        # CTI 탐지 결과
        indicators = {
            'scan_intensity': len(self.scanned_ips) / 254,
            'exploit_attempts': len(self.exploited_services) / max(1, len(self.targets)),
            'anomaly_score': result.get('scan_count', 0) / 20,
        }
        cti_threat = self.cti.get_threat_level(indicators)
        threat += cti_threat * 0.2
        
        return min(1.0, threat)
    
    def handle_mtd_effect(self, effect_type: str, intensity: float):
        """MTD 효과 처리"""
        if effect_type == "shuffle":
            self.confusion_level += intensity * 0.3
            # 진행도 감소
            for target in self.targets:
                target.reset_progress()
                
        elif effect_type == "swap":
            self.confusion_level += intensity * 0.4
            
        elif effect_type == "decoy_activated":
            # 디코이 활성화 시 주의 필요
            pass
    
    def get_state_summary(self) -> Dict[str, Any]:
        """상태 요약"""
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
        }


# =============================================================================
# Test
# =============================================================================
if __name__ == "__main__":
    print("=== Seeker Agent v09 Test ===\n")
    
    # 타겟 생성
    targets = [
        ServiceTarget("fc_mavlink", "10.13.0.2", 14550, "10.13.0.2", 14550, is_critical=True),
        ServiceTarget("cc_sitl", "10.13.0.3", 5760, "10.13.0.3", 5760, is_critical=True),
        ServiceTarget("gcs_mavlink", "10.13.0.4", 14550, "10.13.0.4", 14550, is_critical=True),
        ServiceTarget("decoy_fc", "10.13.0.200", 14550, "10.13.0.200", 14550, is_decoy=True),
    ]
    
    # 각 레벨 테스트
    for level in [0, 2, 4]:
        print(f"\n--- Level {level} ({SEEKER_PROFILES[level]['name']}) ---")
        
        agent = AdvancedSeekerAgent(level=level, seed=42, targets=targets)
        
        breach = False
        defended = False
        
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
                print(f"  BREACH at step {step}!")
                break
            
            if result["defended"] and agent.energy <= 0:
                defended = True
                print(f"  DEFENDED at step {step}")
                break
        
        summary = agent.get_state_summary()
        print(f"  Final phase: {summary['phase']}")
        print(f"  Discovered: {summary['discovered_services']}, Exploited: {summary['exploited_services']}")
        print(f"  Decoy hits: {summary['decoy_hits']}")
        print(f"  Energy: {summary['energy']:.2f}")
    
    print("\n=== Test Complete ===")