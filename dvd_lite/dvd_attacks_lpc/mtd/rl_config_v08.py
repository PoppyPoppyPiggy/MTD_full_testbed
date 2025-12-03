#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MTD RL v08 Configuration - Complete Redesign for Effective Learning

주요 개선사항:
1. 세 가지 정답지(Real/Virtual/Attacker Belief) 명시적 모델링
2. 탐색 공간 확대 (5,000 → 50,000) 및 스캔 효율 하향
3. 보상 함수 완전 재설계 (survival 축소, 방어 보상 확대)
4. Actor-Critic 역할 명확화를 위한 상태/액션 재정의
5. Level별 공격자 전략 세분화

저자: MTD-RL Research Team
버전: 0.8.0
"""
from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Set, Tuple, Any

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# =============================================================================
# 열거형 정의
# =============================================================================
class AttackPhase(Enum):
    """공격 진행 단계"""
    RECONNAISSANCE = auto()  # 정찰 단계
    SCANNING = auto()        # 스캐닝 단계
    DISCOVERY = auto()       # 서비스 발견 단계
    EXPLOITATION = auto()    # 익스플로잇 단계
    BREACH = auto()          # 침투 단계
    COMPROMISED = auto()     # 시스템 장악


class MTDActionType(Enum):
    """MTD 액션 유형"""
    IP_SHUFFLE = auto()
    PORT_HOP = auto()
    DECOY_ACTIVATE = auto()
    DECOY_DEACTIVATE = auto()
    BLACKLIST_ADD = auto()
    SERVICE_SWAP = auto()
    HONEYPOT_DEPLOY = auto()


class DefenseOutcome(Enum):
    """방어 결과"""
    NOTHING = auto()
    SCAN_MISS = auto()
    SCAN_BLOCKED = auto()
    SCAN_FOUND_SERVICE = auto()
    SCAN_FOUND_DECOY = auto()
    EXPLOIT_BLOCKED = auto()
    EXPLOIT_SUCCESS = auto()
    EXPLOIT_DECOY = auto()
    BREACH_BLOCKED = auto()
    BREACH_SUCCESS = auto()
    MTD_SHUFFLE_SUCCESS = auto()
    DECOY_ENGAGED = auto()


# =============================================================================
# DVD Testbed Configuration (실제 정답지)
# =============================================================================
@dataclass
class DVDTestbedConfig:
    """
    실제 테스트베드 구성 - Real Answer Sheet
    공격자는 이 정보를 직접 알 수 없음
    """
    subnet: str = "10.13.0.0/24"
    gateway: str = "10.13.0.1"
    
    # 실제 타겟 (Critical Assets)
    real_targets: Dict[str, str] = field(default_factory=lambda: {
        "TARGET_FC": "10.13.0.2",    # Flight Controller - CRITICAL
        "TARGET_CC": "10.13.0.3",    # Companion Computer
        "TARGET_GCS": "10.13.0.4",   # Ground Control Station - CRITICAL
        "TARGET_SIM": "10.13.0.5",   # Simulator
    })
    
    # 디코이 (Decoy Assets)
    decoys: Dict[str, str] = field(default_factory=lambda: {
        "DECOY_FC": "10.13.0.7",     # FC 디코이
        "DECOY_GCS": "10.13.0.8",    # GCS 디코이
        "DECOY_HONEY_1": "10.13.0.9",  # 하니팟 1
        "DECOY_HONEY_2": "10.13.0.10", # 하니팟 2
    })
    
    # 서비스 포트
    service_ports: Dict[str, int] = field(default_factory=lambda: {
        "PORT_MAVLINK": 14550,
        "PORT_SITL": 5760,
        "PORT_RTSP": 554,
        "PORT_WEB": 3000,
        "PORT_ROS": 11311,
    })
    
    # 중요 자산 정의
    critical_assets: Tuple[str, ...] = ("TARGET_FC", "TARGET_GCS")
    
    # 서비스-포트 매핑
    service_port_map: Dict[str, List[str]] = field(default_factory=lambda: {
        "TARGET_FC": ["PORT_MAVLINK"],
        "TARGET_CC": ["PORT_WEB", "PORT_MAVLINK"],
        "TARGET_GCS": ["PORT_MAVLINK", "PORT_WEB"],
        "TARGET_SIM": ["PORT_SITL", "PORT_ROS"],
    })


# =============================================================================
# Search Space Configuration (가상 주소 공간)
# =============================================================================
@dataclass
class SearchSpaceConfig:
    """
    가상 탐색 공간 설정 - Virtual Answer Sheet의 범위
    
    설계 원칙:
    - 탐색 공간이 충분히 커야 MTD의 효과가 있음
    - 너무 크면 공격자가 서비스를 찾기 어려워 학습 신호 부족
    - 50,000 = 200 IP × 250 Port (적절한 균형점)
    """
    # 가상 IP 범위 (200개)
    virtual_ip_start: int = 1
    virtual_ip_end: int = 200
    
    # 가상 Port 범위 (250개)
    virtual_port_start: int = 10000
    virtual_port_end: int = 10250
    
    @property
    def ip_pool_size(self) -> int:
        return self.virtual_ip_end - self.virtual_ip_start + 1  # 200
    
    @property
    def port_pool_size(self) -> int:
        return self.virtual_port_end - self.virtual_port_start + 1  # 251
    
    @property
    def total_search_space(self) -> int:
        return self.ip_pool_size * self.port_pool_size  # ~50,000
    
    @property
    def max_entropy_bits(self) -> float:
        """최대 엔트로피 (비트)"""
        return math.log2(max(1, self.total_search_space))  # ~15.6 bits
    
    def get_random_address(self, rng) -> Tuple[int, int]:
        """랜덤 가상 주소 생성"""
        ip = rng.integers(self.virtual_ip_start, self.virtual_ip_end + 1)
        port = rng.integers(self.virtual_port_start, self.virtual_port_end + 1)
        return (ip, port)


# =============================================================================
# Service Mapping (Real ↔ Virtual 매핑)
# =============================================================================
@dataclass
class ServiceMapping:
    """
    단일 서비스의 Real ↔ Virtual 매핑
    
    이것이 MTD의 핵심: 
    - 공격자는 virtual_ip:virtual_port를 스캔
    - iptables DNAT가 real_ip:real_port로 연결
    - MTD는 virtual 주소를 주기적으로 변경
    """
    service_id: str
    target_name: str
    real_ip: str
    real_port: int
    virtual_ip: int
    virtual_port: int
    is_decoy: bool = False
    is_critical: bool = False
    active: bool = True
    
    # 추적 정보
    shuffle_count: int = 0
    last_shuffle_step: int = 0
    times_discovered: int = 0
    
    def get_virtual_address(self) -> Tuple[int, int]:
        return (self.virtual_ip, self.virtual_port)
    
    def shuffle(self, new_ip: int, new_port: int, current_step: int):
        """가상 주소 변경"""
        self.virtual_ip = new_ip
        self.virtual_port = new_port
        self.shuffle_count += 1
        self.last_shuffle_step = current_step


# =============================================================================
# Attacker Belief Model (공격자가 생각하는 정답지)
# =============================================================================
@dataclass
class AttackerBelief:
    """
    공격자가 추정하는 서비스 위치 (Belief State)
    
    핵심 개념:
    - 공격자는 스캔을 통해 서비스 위치를 '추정'함
    - MTD가 셔플하면 이 추정이 무효화됨
    - 공격자의 belief와 실제 virtual mapping이 일치해야 공격 가능
    """
    # 발견한 주소들
    discovered_addresses: Set[Tuple[int, int]] = field(default_factory=set)
    
    # 서비스별 추정 위치 {service_name: (estimated_ip, estimated_port)}
    estimated_locations: Dict[str, Tuple[int, int]] = field(default_factory=dict)
    
    # 스캔한 주소들 (중복 스캔 방지)
    scanned_addresses: Set[Tuple[int, int]] = field(default_factory=set)
    
    # 확신도 (최근 스캔에서 얼마나 많이 발견했는지)
    confidence: float = 0.0
    
    # 블랙리스트로 차단된 IP들 (공격자 관점)
    blocked_ips: Set[int] = field(default_factory=set)
    
    def add_discovery(self, address: Tuple[int, int], service_name: str):
        """서비스 발견 시 belief 업데이트"""
        self.discovered_addresses.add(address)
        self.estimated_locations[service_name] = address
        self.confidence = min(1.0, self.confidence + 0.1)
    
    def invalidate_by_shuffle(self, shuffled_services: Set[str], decay: float = 0.5):
        """MTD 셔플 시 belief 무효화"""
        for svc in shuffled_services:
            if svc in self.estimated_locations:
                addr = self.estimated_locations[svc]
                self.discovered_addresses.discard(addr)
                del self.estimated_locations[svc]
        self.confidence *= decay
    
    def reset(self):
        """belief 초기화"""
        self.discovered_addresses.clear()
        self.estimated_locations.clear()
        self.scanned_addresses.clear()
        self.blocked_ips.clear()
        self.confidence = 0.0


# =============================================================================
# Attack Progress Tracking
# =============================================================================
@dataclass
class AttackProgress:
    """
    공격 진행 상황 추적
    
    각 단계별 진행도:
    - discovery: 서비스 발견 정도 (0~1)
    - exploitation: 취약점 공격 진행도 (0~1)
    - compromise: 시스템 장악 진행도 (0~1)
    """
    discovery: float = 0.0
    exploitation: float = 0.0
    compromise: float = 0.0
    
    # 상세 추적
    scanned_count: int = 0
    discovered_services: Set[str] = field(default_factory=set)
    exploited_services: Set[str] = field(default_factory=set)
    
    # 임계값 (상향 조정 - 공격 성공을 어렵게)
    DISCOVERY_THRESHOLD: float = 0.8
    EXPLOITATION_THRESHOLD: float = 0.85
    COMPROMISE_THRESHOLD: float = 0.95
    
    @property
    def phase(self) -> AttackPhase:
        """현재 공격 단계 반환"""
        if self.compromise >= self.COMPROMISE_THRESHOLD:
            return AttackPhase.COMPROMISED
        elif self.compromise > 0:
            return AttackPhase.BREACH
        elif self.exploitation >= self.EXPLOITATION_THRESHOLD:
            return AttackPhase.EXPLOITATION
        elif len(self.discovered_services) > 0:
            return AttackPhase.DISCOVERY
        elif self.scanned_count > 0:
            return AttackPhase.SCANNING
        return AttackPhase.RECONNAISSANCE
    
    @property
    def compromised(self) -> bool:
        return self.compromise >= self.COMPROMISE_THRESHOLD
    
    def reset(self, partial: bool = False):
        """진행 상황 리셋"""
        if partial:
            # MTD 셔플 시 부분 리셋
            self.discovery *= 0.2
            self.exploitation *= 0.05
            self.compromise = 0.0
            self.discovered_services.clear()
        else:
            # 완전 리셋
            self.discovery = 0.0
            self.exploitation = 0.0
            self.compromise = 0.0
            self.scanned_count = 0
            self.discovered_services.clear()
            self.exploited_services.clear()


# =============================================================================
# Seeker Profiles (Level별 공격자 전략)
# =============================================================================
"""
공격자 레벨 설계 원칙:
- Level 0: 기초적인 스캔, 디코이에 쉽게 속음
- Level 1: 휴리스틱 기반, 약간의 디코이 인식
- Level 2: 시간 인식, 장기전에 강함
- Level 3: 적응형, MTD 패턴 학습
- Level 4: 전문가, 높은 성공률과 디코이 회피

핵심 파라미터:
- scans_per_step: 스텝당 스캔 횟수 (대폭 하향)
- scan_efficiency: 유효 스캔 비율
- exploit_prob: 발견 후 익스플로잇 성공 확률
- breach_prob: 익스플로잇 후 침투 성공 확률
- decoy_detect: 디코이 식별 확률
- smart_scan: 지능적 스캔 비율 (발견한 주소 근처 스캔)
"""

SEEKER_PROFILES: Dict[int, Dict[str, Any]] = {
    0: {
        "name": "Script Kiddie",
        "description": "기초적인 자동화 도구 사용, 디코이에 쉽게 속음",
        "mode": "random",
        
        # 스캔 능력 (대폭 하향)
        "scans_per_step": 5,          # 20 → 5
        "scan_efficiency": 0.3,       # 0.5 → 0.3
        "smart_scan": 0.0,
        
        # 공격 능력
        "exploit_prob": 0.20,         # 0.35 → 0.20
        "breach_prob": 0.10,          # 0.20 → 0.10
        "exploit_cooldown": 5,        # 익스플로잇 시도 간격
        
        # 방어 회피
        "decoy_detect": 0.05,         # 디코이 인식 확률 (낮음)
        "ip_change_prob": 0.02,       # IP 변경 확률
        "stealth_factor": 0.0,
        
        # 특수 능력
        "time_boost": False,
        "adaptive": False,
        "target_priority": None,
    },
    
    1: {
        "name": "Mainstream Hacker",
        "description": "휴리스틱 기반 공격, 중간 수준 능력",
        "mode": "heuristic",
        
        "scans_per_step": 8,
        "scan_efficiency": 0.4,
        "smart_scan": 0.1,
        
        "exploit_prob": 0.35,
        "breach_prob": 0.20,
        "exploit_cooldown": 4,
        
        "decoy_detect": 0.15,
        "ip_change_prob": 0.05,
        "stealth_factor": 0.1,
        
        "time_boost": False,
        "adaptive": False,
        "target_priority": None,
    },
    
    2: {
        "name": "Time-Aware Attacker",
        "description": "시간에 따라 공격 강도 조절, 장기전에 강함",
        "mode": "time_aware",
        
        "scans_per_step": 12,
        "scan_efficiency": 0.5,
        "smart_scan": 0.2,
        
        "exploit_prob": 0.45,
        "breach_prob": 0.30,
        "exploit_cooldown": 3,
        
        "decoy_detect": 0.25,
        "ip_change_prob": 0.08,
        "stealth_factor": 0.2,
        
        # 시간 부스트: 시간이 지날수록 공격력 증가
        "time_boost": True,
        "time_boost_rate": 0.002,     # 스텝당 증가율
        "time_boost_max": 1.5,        # 최대 배율
        
        "adaptive": False,
        "target_priority": None,
    },
    
    3: {
        "name": "Adaptive APT",
        "description": "결과에 따라 전략 조정, MTD 패턴 학습",
        "mode": "adaptive",
        
        "scans_per_step": 18,
        "scan_efficiency": 0.6,
        "smart_scan": 0.4,
        
        "exploit_prob": 0.55,
        "breach_prob": 0.40,
        "exploit_cooldown": 2,
        
        "decoy_detect": 0.40,
        "ip_change_prob": 0.12,
        "stealth_factor": 0.5,
        
        "time_boost": True,
        "time_boost_rate": 0.001,
        "time_boost_max": 1.3,
        
        # 적응형: 실패 시 전략 변경
        "adaptive": True,
        "adapt_on_failure": True,
        "adapt_on_success": True,
        
        "target_priority": None,
    },
    
    4: {
        "name": "Expert APT",
        "description": "전문가 수준, 높은 성공률과 디코이 회피",
        "mode": "expert",
        
        "scans_per_step": 25,
        "scan_efficiency": 0.7,
        "smart_scan": 0.6,
        
        "exploit_prob": 0.65,
        "breach_prob": 0.50,
        "exploit_cooldown": 1,
        
        "decoy_detect": 0.60,
        "ip_change_prob": 0.15,
        "stealth_factor": 0.7,
        
        "time_boost": True,
        "time_boost_rate": 0.0015,
        "time_boost_max": 1.4,
        
        "adaptive": True,
        "adapt_on_failure": True,
        "adapt_on_success": True,
        
        # 우선 타겟 (Critical Assets 먼저 공격)
        "target_priority": ["TARGET_FC", "TARGET_GCS"],
    },
}


def load_seeker_profiles(path: Optional[str] = None) -> Dict[int, Dict]:
    """외부 파일에서 Seeker 프로파일 로드"""
    if path and os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return {int(k): v for k, v in data.get("levels", {}).items()}
        except Exception as e:
            print(f"Warning: Failed to load seeker profiles from {path}: {e}")
    return SEEKER_PROFILES


# =============================================================================
# Cost Model (MTD 비용 모델)
# =============================================================================
@dataclass
class MTDCostModel:
    """
    MTD 액션별 비용 모델
    
    Trade-off 핵심:
    - 셔플은 보안성↑ but 지연↑, 에너지↑
    - 디코이는 탐지↑ but 리소스↑
    - 블랙리스트는 차단↑ but 오탐↑
    """
    # IP Shuffle 비용
    shuffle_latency_ms: float = 50.0
    shuffle_bandwidth_loss: float = 0.002
    shuffle_sync_overhead: float = 0.01
    shuffle_energy_joule: float = 0.05
    
    # Port Hop 비용
    port_hop_cpu: float = 0.03
    port_hop_connection_reset: float = 0.05
    
    # Decoy 비용
    decoy_high_interaction: float = 0.5
    decoy_low_interaction: float = 0.1
    decoy_memory_mb: float = 128.0
    
    # Blacklist 비용
    blacklist_fp_rate: float = 0.02   # 오탐률
    blacklist_update_cost: float = 0.001
    
    # 에너지 예산
    energy_budget_joule: float = 100.0
    
    def calculate_shuffle_cost(
        self, 
        intensity: float, 
        num_services: int
    ) -> Dict[str, float]:
        """셔플 비용 계산"""
        latency = self.shuffle_latency_ms * intensity * num_services
        bandwidth = self.shuffle_bandwidth_loss * intensity
        sync = self.shuffle_sync_overhead * intensity * num_services
        energy = self.shuffle_energy_joule * intensity
        
        return {
            "latency_ms": latency,
            "bandwidth_loss": bandwidth,
            "sync_overhead": sync,
            "energy": energy,
            "total": latency / 1000 + bandwidth + sync + energy
        }
    
    def calculate_decoy_cost(
        self, 
        active_decoys: int, 
        high_interaction: bool = True
    ) -> Dict[str, float]:
        """디코이 비용 계산"""
        base = (self.decoy_high_interaction if high_interaction 
                else self.decoy_low_interaction) * active_decoys
        memory = self.decoy_memory_mb * active_decoys / 1024
        
        return {
            "compute": base, 
            "memory_gb": memory, 
            "total": base + memory * 0.1
        }


# =============================================================================
# Reward Model (보상 함수 - 완전 재설계)
# =============================================================================
@dataclass
class RewardModel:
    """
    보상 함수 설계 원칙:
    
    1. Survival 보상 최소화: 수동적 방어 방지
    2. 방어 성공 보상 확대: 적극적 방어 유도
    3. 공격 성공 페널티 확대: 실패 비용 명확화
    4. 다양성 보너스: MTD 핵심 지표
    5. 비용 효율성: Trade-off 학습
    """
    
    # === 방어 성공 보상 (상향) ===
    reward_scan_blocked: float = 20.0       # 스캔 차단
    reward_exploit_blocked: float = 80.0    # 익스플로잇 차단
    reward_breach_blocked: float = 150.0    # 침투 차단
    
    # === 공격 성공 페널티 (대폭 상향) ===
    penalty_service_found: float = -40.0    # 서비스 발견
    penalty_critical_found: float = -80.0   # Critical 자산 발견 (추가)
    penalty_exploit: float = -80.0          # 익스플로잇 성공
    penalty_breach: float = -300.0          # 침투 성공
    
    # === 디코이 효과 보상 ===
    reward_decoy_scan: float = 25.0         # 디코이 스캔 유도
    reward_decoy_exploit: float = 50.0      # 디코이 익스플로잇 유도
    reward_decoy_time_absorbed: float = 2.0 # 스텝당 디코이 시간 소모
    
    # === 생존 보상 (대폭 축소) ===
    reward_survival: float = 0.01           # 0.2 → 0.01 (20배 축소!)
    
    # === 다양성/엔트로피 보너스 ===
    diversity_bonus_weight: float = 1.0     # 다양성 보너스 가중치
    entropy_bonus_weight: float = 0.5       # 엔트로피 보너스 가중치
    
    # === 조기 탐지 보너스 ===
    early_detection_bonus: float = 15.0     # 공격 초기 차단 시 추가 보상
    early_detection_window: int = 50        # 초기로 간주하는 스텝 수
    
    # === 비용 가중치 ===
    cost_weight_explore: float = 0.03       # 탐색 단계 비용 가중치 (낮음)
    cost_weight_exploit: float = 0.10       # 활용 단계 비용 가중치 (높음)
    
    # === MTD 활동 보너스 ===
    mtd_activity_bonus: float = 0.5         # MTD 액션 수행 시 소량 보너스
    mtd_inactivity_penalty: float = -0.3    # 장기 미활동 페널티
    mtd_inactivity_threshold: int = 25      # 미활동 임계 스텝


# =============================================================================
# MTD Thresholds (액션 활성화 임계값)
# =============================================================================
@dataclass
class MTDThresholds:
    """
    액션 활성화 임계값
    - 연속 액션 값이 이 임계값 이상이면 해당 MTD 수행
    """
    shuffle: float = 0.25          # IP 셔플 임계값
    port_hop: float = 0.25         # Port Hop 임계값
    decoy_activate: float = 0.15   # 디코이 활성화 임계값
    blacklist: float = 0.20        # 블랙리스트 추가 임계값
    service_swap: float = 0.30     # 서비스 스왑 임계값


# =============================================================================
# Initial State Configuration
# =============================================================================
@dataclass
class InitialStateConfig:
    """
    에피소드 초기 상태 설정
    
    mode:
    - "clean": 완전 초기 상태
    - "partial": 일부 스캔된 상태
    - "discovered": 서비스 발견된 상태
    - "sample": 확률적 샘플링
    """
    mode: str = "sample"
    mode_probs: Tuple[float, float, float] = (0.5, 0.35, 0.15)  # clean, partial, discovered
    
    # partial 모드 파라미터
    pre_scanned_ratio: float = 0.03     # 사전 스캔 비율
    
    # discovered 모드 파라미터
    pre_discovered_services: int = 0    # 사전 발견 서비스 수


# =============================================================================
# PPO Configuration
# =============================================================================
@dataclass
class PPOConfig:
    """PPO 알고리즘 하이퍼파라미터"""
    
    # Learning
    learning_rate: float = 3e-4
    gamma: float = 0.99
    gae_lambda: float = 0.95
    
    # PPO specific
    clip_epsilon: float = 0.2
    entropy_coef_start: float = 0.02    # 초기 엔트로피 계수 (탐색 강화)
    entropy_coef_final: float = 0.002   # 최종 엔트로피 계수
    entropy_decay_episodes: int = 300   # 엔트로피 감소 에피소드
    
    value_loss_coef: float = 0.5
    max_grad_norm: float = 0.5
    
    # Training
    batch_size: int = 64
    update_epochs: int = 4
    total_episodes: int = 500
    max_steps: int = 200
    
    # Network
    hidden_size: int = 256
    num_layers: int = 2


# =============================================================================
# State/Action Dimensions
# =============================================================================
"""
상태 벡터 설계 (15차원):
- Actor가 MTD 전략을 결정하는 데 필요한 정보
- Critic이 상태 가치를 추정하는 데 필요한 정보
"""
FEATURE_KEYS: List[str] = [
    # 공격 상황 인식 (5개)
    "search_space_scanned_ratio",    # 탐색 공간 스캔 비율
    "services_discovered_ratio",      # 서비스 발견 비율
    "critical_discovered",            # Critical 자산 발견 여부
    "exploitation_progress",          # 익스플로잇 진행도
    "compromise_progress",            # 침투 진행도
    
    # 방어 상태 (4개)
    "current_diversity",              # 현재 다양성 지표
    "current_redundancy",             # 디코이 활성화 비율
    "decoy_engagement_rate",          # 디코이 유인 비율
    "energy_remaining_ratio",         # 잔여 에너지 비율
    
    # 시간/행동 컨텍스트 (6개)
    "steps_since_shuffle",            # 마지막 셔플 후 스텝
    "attacker_scan_rate",             # 공격자 스캔 속도 추정
    "last_shuffle_intensity",         # 직전 셔플 강도
    "last_port_hop_intensity",        # 직전 Port Hop 강도
    "last_decoy_ratio",               # 직전 디코이 비율
    "last_blacklist_aggression",      # 직전 블랙리스트 공격성
]

"""
액션 벡터 설계 (6차원):
- 연속 값 [-1, 1] → 환경에서 [0, 1]로 스케일링
- 각 값이 임계값 이상이면 해당 MTD 액션 수행
"""
ACTION_PARAM_KEYS: List[str] = [
    "shuffle_intensity",       # IP 셔플 강도 (0: 비활성, 1: 전체 셔플)
    "port_hop_intensity",      # Port Hop 강도
    "decoy_ratio",             # 디코이 활성화 비율
    "blacklist_aggression",    # 블랙리스트 공격성
    "blacklist_duration",      # 블랙리스트 지속 시간 (0: 짧음, 1: 길음)
    "service_swap_rate",       # 서비스 스왑 비율
]

STATE_DIM = len(FEATURE_KEYS)   # 15
ACTION_DIM = len(ACTION_PARAM_KEYS)  # 6


# =============================================================================
# Episode Statistics
# =============================================================================
@dataclass
class EpisodeStats:
    """에피소드 통계 (로깅 및 평가용)"""
    
    # 방어 지표
    defense_success_rate: float = 0.0
    breach_prevented: bool = True
    
    # 다양성 지표
    avg_diversity: float = 0.0
    min_diversity: float = 1.0
    avg_redundancy: float = 0.0
    
    # 비용 지표
    total_cost: float = 0.0
    total_latency_ms: float = 0.0
    total_energy: float = 0.0
    
    # 공격 지표
    services_found: int = 0
    critical_found: int = 0
    decoy_hits: int = 0
    scans_blocked: int = 0
    time_to_first_discovery: int = 0
    time_to_breach: int = 0
    total_scans: int = 0
    effective_scans: int = 0
    
    # MTD 액션 지표
    shuffle_count: int = 0
    port_hop_count: int = 0
    decoy_activations: int = 0
    blacklist_additions: int = 0
    
    # 종합 점수
    s_mtd: float = 0.0
    
    def compute_s_mtd(self) -> float:
        """
        S_MTD 종합 점수 계산
        
        공식:
        S_MTD = 0.4 * defense_rate 
              + 0.25 * decoy_effectiveness 
              + 0.15 * diversity 
              + 0.1 * survival_bonus 
              - 0.1 * cost_penalty
        """
        decoy_rate = self.decoy_hits / max(1, self.total_scans)
        cost_penalty = min(self.total_cost / 15.0, 1.0)
        survival_bonus = 1.0 if self.breach_prevented else 0.0
        
        self.s_mtd = (
            0.40 * self.defense_success_rate +
            0.25 * decoy_rate +
            0.15 * self.avg_diversity +
            0.10 * survival_bonus -
            0.10 * cost_penalty
        )
        return self.s_mtd
    
    def as_dict(self) -> Dict[str, float]:
        """딕셔너리로 변환 (로깅용)"""
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
            "Attack/CriticalFound": float(self.critical_found),
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


# =============================================================================
# Curriculum Learning Configuration
# =============================================================================
@dataclass
class CurriculumConfig:
    """
    Curriculum Learning 설정
    
    점진적으로 어려운 공격자와 대결:
    - Phase 0: Level 0만 (Script Kiddie)
    - Phase 1: Level 0, 1
    - Phase 2: Level 1, 2
    - Phase 3: Level 2, 3
    - Phase 4: 모든 레벨
    """
    phases: Tuple[Tuple[int, ...], ...] = (
        (0,),           # Phase 0: 쉬운 공격자만
        (0, 1),         # Phase 1: 약간 어려운 공격자 추가
        (1, 2),         # Phase 2: 중급 공격자
        (2, 3),         # Phase 3: 고급 공격자
        (0, 1, 2, 3, 4) # Phase 4: 전체
    )
    
    phase_episodes: Tuple[int, ...] = (100, 100, 100, 100, 100)
    entropy_schedule: Tuple[float, ...] = (0.02, 0.015, 0.01, 0.005, 0.002)
    
    @property
    def total_episodes(self) -> int:
        return sum(self.phase_episodes)


# =============================================================================
# Main Configuration Class
# =============================================================================
class MTDConfig:
    """전체 설정 통합 클래스"""
    
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


# Global config instance
RL_CONFIG = MTDConfig


# =============================================================================
# Utility Functions
# =============================================================================
def get_seeker_profile(level: int) -> Dict[str, Any]:
    """레벨별 공격자 프로파일 반환"""
    return SEEKER_PROFILES.get(level, SEEKER_PROFILES[1])


def print_config_summary():
    """설정 요약 출력"""
    cfg = MTDConfig()
    print("\n" + "=" * 60)
    print("MTD RL v08 Configuration Summary")
    print("=" * 60)
    print(f"Search Space: {cfg.search_space.total_search_space:,} "
          f"({cfg.search_space.ip_pool_size} IPs × {cfg.search_space.port_pool_size} Ports)")
    print(f"Max Entropy: {cfg.search_space.max_entropy_bits:.2f} bits")
    print(f"State Dim: {STATE_DIM}, Action Dim: {ACTION_DIM}")
    print(f"Episode Length: {cfg.ppo.max_steps} steps")
    print(f"Curriculum Phases: {len(cfg.curriculum.phases)}")
    print(f"Total Episodes: {cfg.curriculum.total_episodes}")
    print("=" * 60)
    
    print("\nSeeker Profiles:")
    for level, profile in SEEKER_PROFILES.items():
        print(f"  Level {level}: {profile['name']}")
        print(f"    - Scans/step: {profile['scans_per_step']}, "
              f"Efficiency: {profile['scan_efficiency']}")
        print(f"    - Exploit: {profile['exploit_prob']}, "
              f"Breach: {profile['breach_prob']}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    print_config_summary()