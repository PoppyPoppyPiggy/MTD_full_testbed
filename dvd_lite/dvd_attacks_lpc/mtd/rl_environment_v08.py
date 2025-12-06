#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MTD RL Environment v08 - 강화학습 환경 (수정본 v2)

수정사항 v2:
1. 보상 체계 개선 - 비용 패널티 완화, 방어 보상 강화
2. Diversity/Redundancy/Shuffle 메트릭 명확히 로깅
3. MTD 액션 임계값 조정 (더 적극적 방어 유도)
4. 공격자 시뮬레이션 개선

저자: MTD-RL Research Team
버전: 0.8.2
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from rl_config_v08 import (
    ACTION_DIM,
    ACTION_PARAM_KEYS,
    SEEKER_PROFILES,
    STATE_DIM,
    EpisodeStats,
    MTDConfig,
    FEATURE_KEYS,
)


# =============================================================================
# Service & Attack State
# =============================================================================
@dataclass
class ServiceState:
    """서비스 상태"""
    name: str
    real_ip: str
    real_port: int
    virtual_ip: str
    virtual_port: int
    is_critical: bool = False
    is_discovered: bool = False
    is_exploited: bool = False
    vulnerability_score: float = 0.5
    last_shuffle_step: int = 0
    last_swap_step: int = 0
    swapped_with: Optional[str] = None


@dataclass
class DecoyState:
    """디코이 상태"""
    name: str
    ip: str
    port: int
    mimics: str
    is_active: bool = False
    hits: int = 0


@dataclass
class AttackerState:
    """공격자 상태"""
    level: int = 1
    scanned_ips: set = field(default_factory=set)
    discovered_services: set = field(default_factory=set)
    exploited_services: set = field(default_factory=set)
    current_phase: str = "reconnaissance"
    energy: float = 1.0
    scan_rate: float = 0.0
    confusion_level: float = 0.0
    # 공격자의 서비스 매핑 정보 (MTD로 무효화됨)
    known_mappings: Dict[str, Tuple[str, int]] = field(default_factory=dict)


# =============================================================================
# MTD Environment
# =============================================================================
class MTDEnvironment(gym.Env):
    """
    MTD 강화학습 환경 v08.2
    
    핵심 개선:
    - 적극적 방어 유도 (낮은 임계값, 높은 방어 보상)
    - Diversity/Redundancy/Shuffle Count 명확히 추적
    - 공격자 시뮬레이션 현실성 개선
    """
    
    metadata = {"render_modes": ["human"]}
    
    def __init__(
        self,
        seed: int = 42,
        seeker_level: int = 1,
        config: Optional[MTDConfig] = None,
        render_mode: Optional[str] = None,
    ):
        super().__init__()
        
        self.seed_val = seed
        self.seeker_level = seeker_level
        self.config = config or MTDConfig()
        self.render_mode = render_mode
        
        # 공격자 프로파일
        self.attacker_profile = SEEKER_PROFILES.get(seeker_level, SEEKER_PROFILES[1])
        
        # 공간 정의
        self.observation_space = spaces.Box(
            low=0.0, high=1.0, shape=(STATE_DIM,), dtype=np.float32
        )
        self.action_space = spaces.Box(
            low=-1.0, high=1.0, shape=(ACTION_DIM,), dtype=np.float32
        )
        
        # 내부 상태
        self.services: Dict[str, ServiceState] = {}
        self.decoys: Dict[str, DecoyState] = {}
        self.attacker: AttackerState = AttackerState()
        self.blacklist: set = set()
        self.active_swaps: List[Dict] = []
        
        # 에피소드 통계 (명확한 추적)
        self.stats = EpisodeStats()
        self.step_count = 0
        self.max_steps = self.config.ppo.max_steps
        
        # MTD 메트릭 히스토리
        self.diversity_history: List[float] = []
        self.redundancy_history: List[float] = []
        
        # 보상 프로파일
        self.reward_profile = "balanced"
        
        # 마지막 액션 기록
        self.last_action = np.zeros(ACTION_DIM)
        self.last_shuffle_step = 0
        self.last_swap_step = 0
        
        # 초기화
        self._init_services()
        self._init_decoys()
    
    def _init_services(self):
        """서비스 초기화"""
        services_config = [
            ("fc_mavlink", "10.13.0.2", 14550, True),
            ("cc_sitl", "10.13.0.3", 5760, True),
            ("cc_mavlink", "10.13.0.3", 14550, False),
            ("cc_web", "10.13.0.3", 3000, False),
            ("gcs_mavlink", "10.13.0.4", 14550, True),
            ("sim_sitl", "10.13.0.5", 5501, False),
        ]
        
        self.services = {}
        for name, ip, port, critical in services_config:
            self.services[name] = ServiceState(
                name=name,
                real_ip=ip,
                real_port=port,
                virtual_ip=ip,
                virtual_port=port,
                is_critical=critical,
                vulnerability_score=random.uniform(0.3, 0.7),
            )
    
    def _init_decoys(self):
        """디코이 초기화"""
        decoy_configs = [
            ("decoy_fc_0", "10.13.0.200", 14550, "fc_mavlink"),
            ("decoy_fc_1", "10.13.0.201", 14550, "fc_mavlink"),
            ("decoy_gcs_0", "10.13.0.202", 14550, "gcs_mavlink"),
            ("decoy_cc_0", "10.13.0.203", 5760, "cc_sitl"),
        ]
        
        self.decoys = {}
        for name, ip, port, mimics in decoy_configs:
            self.decoys[name] = DecoyState(
                name=name,
                ip=ip,
                port=port,
                mimics=mimics,
            )
    
    def set_reward_profile(self, profile: str):
        """보상 프로파일 설정"""
        self.reward_profile = profile
    
    def reset(
        self, 
        seed: Optional[int] = None, 
        options: Optional[dict] = None
    ) -> Tuple[np.ndarray, dict]:
        """환경 리셋"""
        super().reset(seed=seed or self.seed_val)
        
        # 상태 초기화
        self._init_services()
        self._init_decoys()
        
        self.attacker = AttackerState(level=self.seeker_level)
        self.blacklist = set()
        self.active_swaps = []
        
        self.stats = EpisodeStats()
        self.step_count = 0
        self.diversity_history = []
        self.redundancy_history = []
        self.last_action = np.zeros(ACTION_DIM)
        self.last_shuffle_step = 0
        self.last_swap_step = 0
        
        return self._get_state(), self._get_info()
    
    def step(self, action: np.ndarray) -> Tuple[np.ndarray, float, bool, bool, dict]:
        """환경 스텝"""
        self.step_count += 1
        self.last_action = action.copy()
        
        # 1. MTD 액션 실행
        mtd_cost = self._execute_mtd_action(action)
        
        # 2. 공격자 행동 시뮬레이션
        attack_result = self._simulate_attacker()
        
        # 3. 메트릭 기록
        diversity = self._get_diversity_score()
        redundancy = self._get_redundancy_score()
        self.diversity_history.append(diversity)
        self.redundancy_history.append(redundancy)
        
        # 4. 보상 계산
        reward = self._compute_reward(mtd_cost, attack_result)
        
        # 5. 종료 조건 확인
        terminated = self._check_termination()
        truncated = self.step_count >= self.max_steps
        
        # 6. 통계 업데이트
        self._update_stats(mtd_cost, attack_result)
        
        return self._get_state(), reward, terminated, truncated, self._get_info()
    
    def _execute_mtd_action(self, action: np.ndarray) -> float:
        """
        MTD 액션 실행 (임계값 낮춤 → 적극적 방어)
        """
        # [-1, 1] → [0, 1]
        scaled = (action + 1) / 2
        
        total_cost = 0.0
        
        # 1. Network Shuffle (임계값: 0.3 → 0.25)
        shuffle_intensity = scaled[0]
        if shuffle_intensity > 0.25:
            cost = self._do_shuffle(shuffle_intensity)
            total_cost += cost
            self.last_shuffle_step = self.step_count
        
        # 2. Port Hop (임계값: 0.4 → 0.35)
        port_hop_intensity = scaled[1]
        if port_hop_intensity > 0.35:
            cost = self._do_port_hop(port_hop_intensity)
            total_cost += cost
        
        # 3. Decoy Activation (임계값: 0.5 → 0.4)
        decoy_ratio = scaled[2]
        if decoy_ratio > 0.4:
            cost = self._activate_decoys(decoy_ratio)
            total_cost += cost
        
        # 4. Blacklist (임계값 유지)
        blacklist_aggression = scaled[3]
        blacklist_duration = scaled[4]
        if blacklist_aggression > 0.6:
            cost = self._update_blacklist(blacklist_aggression, blacklist_duration)
            total_cost += cost
        
        # 5. Service Swap (임계값: 0.35 → 0.30)
        swap_intensity = scaled[5]
        swap_target = scaled[6]
        if swap_intensity > 0.30:
            cost = self._do_service_swap(swap_intensity, swap_target)
            total_cost += cost
            self.last_swap_step = self.step_count
        
        return total_cost
    
    def _do_shuffle(self, intensity: float) -> float:
        """네트워크 셔플 실행"""
        n_shuffle = max(1, int(len(self.services) * intensity))
        services_to_shuffle = random.sample(list(self.services.keys()), n_shuffle)
        
        for svc_name in services_to_shuffle:
            svc = self.services[svc_name]
            old_ip, old_port = svc.virtual_ip, svc.virtual_port
            
            # 새 가상 IP/Port 할당
            svc.virtual_ip = f"10.13.0.{random.randint(100, 199)}"
            svc.virtual_port = random.randint(10000, 60000)
            svc.last_shuffle_step = self.step_count
            
            # 공격자의 기존 매핑 정보 무효화
            if svc_name in self.attacker.known_mappings:
                del self.attacker.known_mappings[svc_name]
            
            # 발견 상태 무효화 (강도에 비례)
            if svc.is_discovered and random.random() < intensity * 0.8:
                svc.is_discovered = False
                self.attacker.discovered_services.discard(svc_name)
                self.attacker.confusion_level += 0.15
        
        self.stats.total_shuffles += 1
        
        # 비용 (완화됨)
        return intensity * self.config.cost.shuffle * 0.7
    
    def _do_port_hop(self, intensity: float) -> float:
        """포트 호핑 실행"""
        critical_services = [s for s in self.services.values() if s.is_critical]
        
        hopped = 0
        for svc in critical_services:
            if random.random() < intensity:
                svc.virtual_port = random.randint(10000, 60000)
                hopped += 1
                
                # 공격자 매핑 무효화
                if svc.name in self.attacker.known_mappings:
                    del self.attacker.known_mappings[svc.name]
                
                if svc.is_discovered:
                    self.attacker.confusion_level += 0.08
        
        if hopped > 0:
            self.stats.total_port_hops += 1
        
        return intensity * self.config.cost.port_hop * 0.7
    
    def _do_service_swap(self, intensity: float, target: float) -> float:
        """서비스 스왑 실행"""
        service_names = list(self.services.keys())
        
        if len(service_names) < 2:
            return 0.0
        
        # 스왑 대상 선택
        if target > 0.5:
            critical = [s for s in service_names if self.services[s].is_critical]
            non_critical = [s for s in service_names if not self.services[s].is_critical]
            
            if critical and non_critical:
                svc_a = random.choice(critical)
                svc_b = random.choice(non_critical)
            else:
                svc_a, svc_b = random.sample(service_names, 2)
        else:
            svc_a, svc_b = random.sample(service_names, 2)
        
        # 가상 주소 교환
        a = self.services[svc_a]
        b = self.services[svc_b]
        
        a.virtual_ip, b.virtual_ip = b.virtual_ip, a.virtual_ip
        a.virtual_port, b.virtual_port = b.virtual_port, a.virtual_port
        
        a.last_swap_step = self.step_count
        b.last_swap_step = self.step_count
        a.swapped_with = svc_b
        b.swapped_with = svc_a
        
        # 스왑 기록 (최대 5개 유지)
        self.active_swaps.append({
            "service_a": svc_a,
            "service_b": svc_b,
            "step": self.step_count,
            "intensity": intensity,
        })
        if len(self.active_swaps) > 5:
            self.active_swaps.pop(0)
        
        # 공격자 혼란
        self.attacker.confusion_level += intensity * 0.25
        
        # 매핑 정보 무효화
        for svc_name in [svc_a, svc_b]:
            if svc_name in self.attacker.known_mappings:
                del self.attacker.known_mappings[svc_name]
            svc = self.services[svc_name]
            if svc.is_discovered and random.random() < intensity * 0.6:
                svc.is_discovered = False
                self.attacker.discovered_services.discard(svc_name)
        
        self.stats.total_swaps += 1
        
        return intensity * self.config.cost.service_swap * 0.7
    
    def _activate_decoys(self, ratio: float) -> float:
        """디코이 활성화"""
        n_activate = max(1, int(len(self.decoys) * ratio))
        inactive_decoys = [d for d in self.decoys.values() if not d.is_active]
        
        activated = 0
        for decoy in random.sample(inactive_decoys, min(n_activate, len(inactive_decoys))):
            decoy.is_active = True
            activated += 1
            self.stats.total_decoy_activations += 1
        
        return ratio * self.config.cost.decoy * 0.7 * activated / max(1, len(self.decoys))
    
    def _update_blacklist(self, aggression: float, duration: float) -> float:
        """블랙리스트 업데이트"""
        n_block = int(len(self.attacker.scanned_ips) * aggression * 0.3)
        
        if n_block > 0 and self.attacker.scanned_ips:
            to_block = random.sample(list(self.attacker.scanned_ips), 
                                     min(n_block, len(self.attacker.scanned_ips)))
            self.blacklist.update(to_block)
        
        return aggression * duration * self.config.cost.blacklist * 0.5
    
    def _simulate_attacker(self) -> Dict[str, Any]:
        """
        공격자 행동 시뮬레이션 (개선됨)
        
        Returns:
            attack_result: 공격 결과 정보
        """
        profile = self.attacker_profile
        result = {
            "discovered": False,
            "exploited": False,
            "breach": False,
            "decoy_hit": False,
        }
        
        # 혼란도 감쇠
        self.attacker.confusion_level *= 0.92
        
        # 혼란도에 따른 효율 감소
        confusion_penalty = min(0.5, self.attacker.confusion_level * 0.4)
        effective_rate = max(0.1, 1.0 - confusion_penalty)
        
        if self.attacker.current_phase == "reconnaissance":
            # === 정찰 단계 ===
            self.attacker.scan_rate = profile["scan_rate"] * effective_rate
            
            # IP 스캔
            n_scan = int(self.config.search_space.ip_range * self.attacker.scan_rate)
            for _ in range(n_scan):
                ip = f"10.13.0.{random.randint(1, 254)}"
                if ip not in self.blacklist:
                    self.attacker.scanned_ips.add(ip)
            
            # 디코이 유인 체크 (먼저!)
            for decoy in self.decoys.values():
                if decoy.is_active and decoy.ip in self.attacker.scanned_ips:
                    if random.random() < profile["discovery_rate"] * 1.2:  # 디코이는 더 잘 발견됨
                        decoy.hits += 1
                        self.stats.total_decoy_hits += 1
                        result["decoy_hit"] = True
                        # 디코이에 시간 낭비
                        self.attacker.energy -= 0.08
            
            # 실제 서비스 발견 시도
            for svc_name, svc in self.services.items():
                if svc.is_discovered:
                    continue
                
                # 가상 IP가 스캔됨 + 발견 확률
                if svc.virtual_ip in self.attacker.scanned_ips:
                    discover_prob = profile["discovery_rate"] * effective_rate
                    if random.random() < discover_prob:
                        svc.is_discovered = True
                        self.attacker.discovered_services.add(svc_name)
                        self.attacker.known_mappings[svc_name] = (svc.virtual_ip, svc.virtual_port)
                        result["discovered"] = True
            
            # 충분히 발견하면 다음 단계
            if len(self.attacker.discovered_services) >= 2:
                self.attacker.current_phase = "exploitation"
        
        elif self.attacker.current_phase == "exploitation":
            # === 익스플로잇 단계 ===
            for svc_name in list(self.attacker.discovered_services):
                svc = self.services.get(svc_name)
                if not svc or svc.is_exploited:
                    continue
                
                # 매핑 정보가 무효화되었는지 확인
                if svc_name in self.attacker.known_mappings:
                    known_ip, known_port = self.attacker.known_mappings[svc_name]
                    # 매핑이 변경되었으면 재발견 필요
                    if known_ip != svc.virtual_ip or known_port != svc.virtual_port:
                        svc.is_discovered = False
                        self.attacker.discovered_services.discard(svc_name)
                        del self.attacker.known_mappings[svc_name]
                        continue
                
                # 익스플로잇 성공 확률
                exploit_prob = (
                    profile["exploit_success"] * 
                    svc.vulnerability_score *
                    effective_rate
                )
                
                if random.random() < exploit_prob:
                    svc.is_exploited = True
                    self.attacker.exploited_services.add(svc_name)
                    result["exploited"] = True
                    
                    if svc.is_critical:
                        self.attacker.current_phase = "persistence"
        
        elif self.attacker.current_phase == "persistence":
            # === 지속성 확보 단계 ===
            exploited_critical = any(
                self.services[s].is_critical 
                for s in self.attacker.exploited_services
                if s in self.services
            )
            
            if exploited_critical:
                result["breach"] = True
        
        # 에너지 소모
        self.attacker.energy -= 0.01
        
        return result
    
    def _compute_reward(self, mtd_cost: float, attack_result: Dict) -> float:
        """
        보상 계산 (개선됨 - 적극적 방어 장려)
        """
        reward = 0.0
        cfg = self.config.reward
        
        # 1. 기본 생존 보상 (증가)
        reward += cfg.survival_per_step * 1.5
        
        # 2. 비용 패널티 (대폭 완화)
        # 기존: cost_weight = 0.15
        # 수정: 낮은 비용에는 패널티 없음, 과도한 비용에만 패널티
        if mtd_cost > 0.5:
            reward -= (mtd_cost - 0.5) * cfg.cost_weight
        
        # 3. 공격 결과에 따른 보상/패널티
        if attack_result["breach"]:
            reward -= cfg.breach_penalty
        elif attack_result["exploited"]:
            reward -= cfg.exploit_penalty
        elif attack_result["discovered"]:
            reward -= cfg.discovery_penalty * 0.5  # 완화
        else:
            # 공격 실패 시 보너스!
            reward += 0.3
        
        # 4. 디코이 유인 보너스 (증가)
        if attack_result["decoy_hit"]:
            reward += cfg.decoy_engagement_bonus * 2
        
        # 5. 다양성 보너스 (증가)
        diversity = self._get_diversity_score()
        if diversity > 0.3:
            reward += diversity * cfg.diversity_bonus * 1.5
        
        # 6. 중복성 보너스
        redundancy = self._get_redundancy_score()
        reward += redundancy * cfg.redundancy_bonus
        
        # 7. 공격자 혼란 보너스 (증가)
        reward += self.attacker.confusion_level * cfg.confusion_bonus * 2
        
        # 8. MTD 활동 보너스 (새로 추가!)
        # 적극적인 방어 활동에 보상
        if self.stats.total_shuffles > 0:
            shuffle_bonus = min(0.2, self.stats.total_shuffles * 0.02)
            reward += shuffle_bonus
        
        if self.stats.total_swaps > 0:
            swap_bonus = min(0.15, self.stats.total_swaps * 0.03)
            reward += swap_bonus
        
        # 9. 프로파일 조정
        if self.reward_profile == "explore":
            action_var = np.var(self.last_action)
            reward += action_var * 0.15
        
        return reward
    
    def _get_diversity_score(self) -> float:
        """다양성 점수 계산"""
        virtual_ips = set(s.virtual_ip for s in self.services.values())
        virtual_ports = set(s.virtual_port for s in self.services.values())
        
        ip_diversity = len(virtual_ips) / len(self.services)
        port_diversity = len(virtual_ports) / len(self.services)
        
        # 최근 셔플 보너스
        steps_since_shuffle = self.step_count - self.last_shuffle_step
        shuffle_recency = max(0, 1 - steps_since_shuffle / 30) * 0.25
        
        # 스왑 보너스
        swap_bonus = min(0.2, len(self.active_swaps) * 0.05)
        
        return min(1.0, (ip_diversity + port_diversity) / 2 + shuffle_recency + swap_bonus)
    
    def _get_redundancy_score(self) -> float:
        """중복성 점수 계산"""
        active_decoys = sum(1 for d in self.decoys.values() if d.is_active)
        decoy_ratio = active_decoys / len(self.decoys)
        
        # 스왑 보너스
        swap_bonus = min(0.3, len(self.active_swaps) * 0.08)
        
        return min(1.0, decoy_ratio * 0.6 + swap_bonus + 0.1)
    
    def _check_termination(self) -> bool:
        """종료 조건 확인"""
        critical_exploited = all(
            self.services[s].is_exploited 
            for s in self.services 
            if self.services[s].is_critical
        )
        
        if critical_exploited:
            self.stats.breach_occurred = True
            return True
        
        if self.attacker.energy <= 0:
            return True
        
        return False
    
    def _update_stats(self, mtd_cost: float, attack_result: Dict):
        """통계 업데이트"""
        self.stats.total_cost += mtd_cost
        self.stats.total_steps = self.step_count
        
        if attack_result["breach"]:
            self.stats.breach_occurred = True
    
    def _get_state(self) -> np.ndarray:
        """상태 벡터 생성 (17차원)"""
        # 검색 공간 스캔 비율
        total_search = self.config.search_space.total_search_space
        scanned = len(self.attacker.scanned_ips) * self.config.search_space.port_range
        scanned_ratio = min(1.0, scanned / total_search)
        
        # 서비스 발견 비율
        discovered_ratio = len(self.attacker.discovered_services) / len(self.services)
        
        # 중요 서비스 발견 여부
        critical_discovered = any(
            self.services[s].is_critical 
            for s in self.attacker.discovered_services
            if s in self.services
        )
        
        # 익스플로잇 진행도
        exploit_progress = len(self.attacker.exploited_services) / len(self.services)
        
        # 침투 진행도
        phase_map = {"reconnaissance": 0.0, "exploitation": 0.5, "persistence": 1.0}
        compromise_progress = phase_map.get(self.attacker.current_phase, 0.0)
        
        # 다양성/중복성
        diversity = self._get_diversity_score()
        redundancy = self._get_redundancy_score()
        
        # 디코이 유인율
        active_decoys = sum(1 for d in self.decoys.values() if d.is_active)
        total_hits = sum(d.hits for d in self.decoys.values())
        decoy_rate = total_hits / max(1, active_decoys * self.step_count) if active_decoys > 0 else 0
        
        # 에너지
        energy = self.attacker.energy
        
        # 스왑 활성 비율
        swap_active_ratio = min(1.0, len(self.active_swaps) / 3.0)
        
        # 시간 특성
        steps_since_shuffle = min(1.0, (self.step_count - self.last_shuffle_step) / 50.0)
        steps_since_swap = min(1.0, (self.step_count - self.last_swap_step) / 50.0) if self.last_swap_step > 0 else 1.0
        
        # 스캔율
        scan_rate = min(1.0, self.attacker.scan_rate / 0.2)
        
        # 마지막 액션
        scaled_action = (self.last_action + 1) / 2
        
        state = np.array([
            scanned_ratio,
            discovered_ratio,
            float(critical_discovered),
            exploit_progress,
            compromise_progress,
            diversity,
            redundancy,
            min(1.0, decoy_rate),
            energy,
            swap_active_ratio,
            steps_since_shuffle,
            steps_since_swap,
            scan_rate,
            scaled_action[0],
            scaled_action[1],
            scaled_action[2],
            scaled_action[5] if len(scaled_action) > 5 else 0.0,
        ], dtype=np.float32)
        
        return state
    
    def _get_info(self) -> Dict[str, Any]:
        """정보 딕셔너리 반환 (모든 메트릭 포함)"""
        discovered_ratio = len(self.attacker.discovered_services) / len(self.services)
        exploit_ratio = len(self.attacker.exploited_services) / len(self.services)
        diversity = self._get_diversity_score()
        redundancy = self._get_redundancy_score()
        
        # Defense Success
        defense_success = 1.0 - (discovered_ratio * 0.3 + exploit_ratio * 0.5)
        cost_efficiency = 1.0 - min(1.0, self.stats.total_cost / 10.0)
        
        # S_MTD
        s_mtd = (
            defense_success * 0.35 +
            diversity * 0.20 +
            redundancy * 0.15 +
            cost_efficiency * 0.20 +
            (1.0 - int(self.stats.breach_occurred)) * 0.10
        )
        
        # 평균 계산
        diversity_avg = np.mean(self.diversity_history) if self.diversity_history else diversity
        redundancy_avg = np.mean(self.redundancy_history) if self.redundancy_history else redundancy
        
        return {
            # Defense 메트릭
            "Defense/S_MTD": s_mtd,
            "Defense/Success": defense_success,
            "Defense/BreachPrevented": int(not self.stats.breach_occurred),
            "Defense/Diversity_Avg": diversity_avg,
            "Defense/Diversity_Current": diversity,
            "Defense/Redundancy_Avg": redundancy_avg,
            "Defense/Redundancy_Current": redundancy,
            
            # Attack 메트릭
            "Attack/ServicesFound": len(self.attacker.discovered_services),
            "Attack/ServicesExploited": len(self.attacker.exploited_services),
            "Attack/Phase": self.attacker.current_phase,
            "Attack/ConfusionLevel": self.attacker.confusion_level,
            
            # Cost 메트릭
            "Cost/Total": self.stats.total_cost,
            "Cost/Efficiency": cost_efficiency,
            
            # MTD 액션 메트릭
            "MTD/ShuffleCount": self.stats.total_shuffles,
            "MTD/PortHopCount": self.stats.total_port_hops,
            "MTD/SwapCount": self.stats.total_swaps,
            "MTD/ActiveSwaps": len(self.active_swaps),
            
            # Decoy 메트릭
            "Decoy/Activations": self.stats.total_decoy_activations,
            "Decoy/Hits": self.stats.total_decoy_hits,
            "Decoy/ActiveCount": sum(1 for d in self.decoys.values() if d.is_active),
            
            # Episode 메트릭
            "Episode/Steps": self.step_count,
            "Episode/AttackerEnergy": self.attacker.energy,
        }
    
    def render(self):
        """렌더링"""
        if self.render_mode == "human":
            info = self._get_info()
            print(f"\n=== Step {self.step_count} ===")
            print(f"Phase: {self.attacker.current_phase}")
            print(f"Discovered: {len(self.attacker.discovered_services)}/{len(self.services)}")
            print(f"S_MTD: {info['Defense/S_MTD']:.3f}")
            print(f"Diversity: {info['Defense/Diversity_Current']:.3f}")
            print(f"Redundancy: {info['Defense/Redundancy_Current']:.3f}")
            print(f"Shuffles: {self.stats.total_shuffles}, Swaps: {self.stats.total_swaps}")
            print(f"Cost: {self.stats.total_cost:.2f}")


# =============================================================================
# Test
# =============================================================================
if __name__ == "__main__":
    print("=== MTD Environment v08.2 Test ===")
    print(f"STATE_DIM: {STATE_DIM}")
    print(f"ACTION_DIM: {ACTION_DIM}")
    
    env = MTDEnvironment(seeker_level=2)
    state, info = env.reset()
    
    print(f"\nInitial state shape: {state.shape}")
    
    total_reward = 0
    for step in range(100):
        action = env.action_space.sample()
        state, reward, terminated, truncated, info = env.step(action)
        total_reward += reward
        
        if step % 20 == 0:
            print(f"\nStep {step}:")
            print(f"  Reward: {reward:.2f}")
            print(f"  S_MTD: {info['Defense/S_MTD']:.3f}")
            print(f"  Diversity: {info['Defense/Diversity_Current']:.3f}")
            print(f"  Redundancy: {info['Defense/Redundancy_Current']:.3f}")
            print(f"  Shuffles: {info['MTD/ShuffleCount']}")
            print(f"  Swaps: {info['MTD/SwapCount']}")
        
        if terminated or truncated:
            break
    
    print(f"\n=== Episode Complete ===")
    print(f"Total reward: {total_reward:.2f}")
    print(f"Final info: {json.dumps({k: round(v, 3) if isinstance(v, float) else v for k, v in info.items()}, indent=2)}")