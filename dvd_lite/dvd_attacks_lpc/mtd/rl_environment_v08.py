#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MTD RL Environment v08 - Complete Redesign

핵심 개선사항:
1. 세 가지 정답지 명시적 모델링 (Real/Virtual/Attacker Belief)
2. 공격자 Belief 기반 공격 로직
3. MTD 셔플 시 공격자 Belief 무효화
4. 레벨별 차별화된 공격 전략
5. 개선된 보상 계산

저자: MTD-RL Research Team
버전: 0.8.0
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from rl_config_v08 import (
    ACTION_DIM,
    STATE_DIM,
    SEEKER_PROFILES,
    AttackPhase,
    AttackProgress,
    AttackerBelief,
    DefenseOutcome,
    EpisodeStats,
    MTDConfig,
    ServiceMapping,
    get_seeker_profile,
    load_seeker_profiles,
)


class MTDEnvironment(gym.Env):
    """
    MTD 강화학습 환경 v08
    
    핵심 구조:
    1. Real Answer Sheet: testbed 설정 (고정)
    2. Virtual Answer Sheet: 서비스 매핑 (MTD가 변경)
    3. Attacker Belief: 공격자의 추정 (스캔으로 업데이트, 셔플로 무효화)
    
    공격 성공 조건:
    - 공격자의 Belief가 Virtual Answer Sheet와 일치해야 함
    - 일치해도 내부 MTD (service swap, blacklist)로 방어 가능
    """
    
    metadata = {"render_modes": ["human"]}
    
    def __init__(
        self,
        seed: int = 42,
        seeker_level: int = 1,
        seeker_profiles_path: Optional[str] = None,
        config: Optional[MTDConfig] = None,
    ):
        super().__init__()
        
        self.cfg = config or MTDConfig()
        self.rng = np.random.default_rng(seed)
        self.seed_value = seed
        
        # Gymnasium spaces
        self.observation_space = spaces.Box(
            low=-1.0, high=1.0, 
            shape=(STATE_DIM,), 
            dtype=np.float32
        )
        self.action_space = spaces.Box(
            low=-1.0, high=1.0, 
            shape=(ACTION_DIM,), 
            dtype=np.float32
        )
        
        # Seeker (공격자) 설정
        self.profiles = load_seeker_profiles(seeker_profiles_path)
        self.seeker_level = seeker_level
        self.profile = get_seeker_profile(seeker_level)
        
        # === 세 가지 정답지 초기화 ===
        # 1. Real Answer Sheet (testbed 설정에서 고정)
        self.real_services: Dict[str, Tuple[str, int]] = {}  # {service_id: (real_ip, real_port)}
        
        # 2. Virtual Answer Sheet (MTD가 관리하는 매핑)
        self.service_mappings: List[ServiceMapping] = []
        self.address_to_service: Dict[Tuple[int, int], ServiceMapping] = {}
        
        # 3. Attacker Belief (공격자의 추정)
        self.attacker_belief = AttackerBelief()
        
        # 공격 진행 상황
        self.attack_progress = AttackProgress()
        
        # 환경 상태
        self.step_count = 0
        self.energy_used = 0.0
        self.blacklist_ips: Set[int] = set()
        self.last_action = np.zeros(ACTION_DIM)
        self.last_shuffle_step = 0
        self.stats = EpisodeStats()
        self.cost_weight = self.cfg.reward_model.cost_weight_explore
        
        # 다양성 추적
        self.config_history: List[Set[Tuple[int, int]]] = []
        self.current_diversity = 1.0
        
        # 카운터
        self._total_scans = 0
        self._blocked_scans = 0
        self._decoy_hits = 0
        self._first_discovery_step = 0
        self._mtd_actions_taken = 0
        
        # 초기화
        self._init_service_mappings()
    
    # =========================================================================
    # 초기화 메서드
    # =========================================================================
    def _init_service_mappings(self):
        """
        서비스 매핑 초기화
        
        Real → Virtual 매핑 생성:
        - 4개 실제 타겟 × 5개 포트 = 20개 실제 서비스
        - 4개 디코이 × 5개 포트 = 20개 디코이 서비스
        """
        self.service_mappings = []
        self.real_services = {}
        
        ss = self.cfg.search_space
        tb = self.cfg.testbed
        
        # 1. 실제 타겟 서비스 매핑
        for target_name, real_ip in tb.real_targets.items():
            for port_name, real_port in tb.service_ports.items():
                service_id = f"{target_name}:{port_name}"
                
                # 가상 주소 랜덤 할당
                virt_ip, virt_port = ss.get_random_address(self.rng)
                
                self.service_mappings.append(ServiceMapping(
                    service_id=service_id,
                    target_name=target_name,
                    real_ip=real_ip,
                    real_port=real_port,
                    virtual_ip=virt_ip,
                    virtual_port=virt_port,
                    is_decoy=False,
                    is_critical=(target_name in tb.critical_assets),
                    active=True,
                ))
                
                # Real Answer Sheet 저장
                self.real_services[service_id] = (real_ip, real_port)
        
        # 2. 디코이 서비스 매핑
        for decoy_name, decoy_ip in tb.decoys.items():
            for port_name, real_port in tb.service_ports.items():
                service_id = f"{decoy_name}:{port_name}"
                
                virt_ip, virt_port = ss.get_random_address(self.rng)
                
                self.service_mappings.append(ServiceMapping(
                    service_id=service_id,
                    target_name=decoy_name,
                    real_ip=decoy_ip,
                    real_port=real_port,
                    virtual_ip=virt_ip,
                    virtual_port=virt_port,
                    is_decoy=True,
                    is_critical=False,
                    active=False,  # 디코이는 기본 비활성
                ))
        
        self._update_address_map()
    
    def _update_address_map(self):
        """가상 주소 → 서비스 매핑 업데이트"""
        self.address_to_service = {}
        for svc in self.service_mappings:
            if svc.active:
                addr = svc.get_virtual_address()
                self.address_to_service[addr] = svc
    
    # =========================================================================
    # MTD 액션 메서드
    # =========================================================================
    def _shuffle_addresses(self, intensity: float) -> Tuple[int, Set[str]]:
        """
        IP/Port 셔플 - Virtual Answer Sheet 업데이트
        
        Args:
            intensity: 셔플 강도 (0~1)
        
        Returns:
            (셔플된 서비스 수, 셔플된 서비스 이름 집합)
        """
        ss = self.cfg.search_space
        
        # 셔플할 서비스 수 결정
        num_to_shuffle = max(1, int(len(self.service_mappings) * intensity))
        
        # 활성 서비스 중에서 선택
        active_services = [svc for svc in self.service_mappings 
                          if svc.active and not svc.is_decoy]
        if not active_services:
            return 0, set()
        
        services_to_shuffle = self.rng.choice(
            active_services,
            min(num_to_shuffle, len(active_services)),
            replace=False
        )
        
        shuffled_names = set()
        for svc in services_to_shuffle:
            # 새로운 가상 주소 할당
            new_ip, new_port = ss.get_random_address(self.rng)
            svc.shuffle(new_ip, new_port, self.step_count)
            shuffled_names.add(svc.service_id)
        
        self._update_address_map()
        self.last_shuffle_step = self.step_count
        self.stats.shuffle_count += 1
        
        # 공격자 Belief 무효화
        self.attacker_belief.invalidate_by_shuffle(shuffled_names, decay=0.3)
        
        # 공격 진행도 감소
        shuffle_effect = len(shuffled_names) / max(1, len(active_services))
        self.attack_progress.discovery *= (1.0 - shuffle_effect * 0.7)
        self.attack_progress.exploitation *= (1.0 - shuffle_effect * 0.9)
        
        # 발견된 서비스에서 셔플된 것 제거
        self.attack_progress.discovered_services -= shuffled_names
        
        return len(shuffled_names), shuffled_names
    
    def _apply_port_hop(self, intensity: float) -> int:
        """Port Hop 수행"""
        ss = self.cfg.search_space
        hop_count = 0
        hopped_services = set()
        
        for svc in self.service_mappings:
            if svc.active and self.rng.random() < intensity:
                old_port = svc.virtual_port
                svc.virtual_port = self.rng.integers(
                    ss.virtual_port_start, 
                    ss.virtual_port_end + 1
                )
                if svc.virtual_port != old_port:
                    hop_count += 1
                    hopped_services.add(svc.service_id)
        
        if hop_count > 0:
            self._update_address_map()
            self.stats.port_hop_count += 1
            
            # Port Hop도 Belief에 영향
            self.attacker_belief.invalidate_by_shuffle(hopped_services, decay=0.5)
            self.attack_progress.discovery *= (1.0 - intensity * 0.3)
        
        return hop_count
    
    def _activate_decoys(self, ratio: float) -> int:
        """디코이 활성화"""
        decoys = [svc for svc in self.service_mappings if svc.is_decoy]
        if not decoys:
            return 0
        
        num_activate = max(1, int(len(decoys) * ratio))
        
        for i, svc in enumerate(decoys):
            svc.active = (i < num_activate)
        
        self._update_address_map()
        active_count = sum(1 for svc in decoys if svc.active)
        self.stats.decoy_activations = active_count
        
        return active_count
    
    def _update_blacklist(self, aggression: float) -> int:
        """블랙리스트 업데이트"""
        if aggression < self.cfg.thresholds.blacklist:
            return 0
        
        # 최근 스캔된 주소에서 공격자 IP 추정
        num_to_block = max(1, int(aggression * 10))
        recent_scans = list(self.attacker_belief.scanned_addresses)[-100:]
        
        blocked_count = 0
        for addr in recent_scans[:num_to_block]:
            ip = addr[0]
            if ip not in self.blacklist_ips:
                self.blacklist_ips.add(ip)
                self.attacker_belief.blocked_ips.add(ip)
                blocked_count += 1
        
        self.stats.blacklist_additions += blocked_count
        return blocked_count
    
    def _apply_mtd(self, scaled_action: np.ndarray) -> Dict[str, float]:
        """
        MTD 액션 적용
        
        Args:
            scaled_action: [0, 1] 범위로 스케일링된 액션
        
        Returns:
            비용 정보 딕셔너리
        """
        shuffle, port_hop, decoy_ratio, bl_aggr, bl_dur, swap = scaled_action
        th = self.cfg.thresholds
        costs = {"total": 0.0, "latency_ms": 0.0, "energy": 0.0}
        
        mtd_applied = False
        
        # 1. IP Shuffle
        if shuffle >= th.shuffle:
            num_shuffled, _ = self._shuffle_addresses(shuffle)
            shuffle_cost = self.cfg.cost_model.calculate_shuffle_cost(
                shuffle, num_shuffled
            )
            costs["latency_ms"] += shuffle_cost["latency_ms"]
            costs["energy"] += shuffle_cost["energy"]
            costs["total"] += shuffle_cost["total"]
            self.energy_used += shuffle_cost["energy"]
            mtd_applied = True
        
        # 2. Port Hop
        if port_hop >= th.port_hop:
            hop_count = self._apply_port_hop(port_hop)
            costs["total"] += self.cfg.cost_model.port_hop_cpu * port_hop
            if hop_count > 0:
                mtd_applied = True
        
        # 3. Decoy Activation
        if decoy_ratio >= th.decoy_activate:
            active_count = self._activate_decoys(decoy_ratio)
            decoy_cost = self.cfg.cost_model.calculate_decoy_cost(active_count)
            costs["total"] += decoy_cost["total"]
            mtd_applied = True
        
        # 4. Blacklist
        if bl_aggr >= th.blacklist:
            blocked = self._update_blacklist(bl_aggr)
            costs["total"] += self.cfg.cost_model.blacklist_update_cost * bl_aggr
            if blocked > 0:
                mtd_applied = True
        
        if mtd_applied:
            self._mtd_actions_taken += 1
        
        return costs
    
    # =========================================================================
    # 공격자 시뮬레이션
    # =========================================================================
    def _attacker_step(self) -> DefenseOutcome:
        """
        공격자 행동 시뮬레이션
        
        핵심 로직:
        1. 스캔 → Virtual Answer Sheet에서 서비스 찾기
        2. 발견 → Attacker Belief 업데이트
        3. Belief와 Virtual가 일치하면 → 공격 시도
        4. 내부 MTD로 추가 방어
        """
        prof = self.profile
        ss = self.cfg.search_space
        
        # Time boost 계산
        time_factor = 1.0
        if prof.get("time_boost"):
            max_boost = prof.get("time_boost_max", 1.5)
            boost_rate = prof.get("time_boost_rate", 0.002)
            time_factor = min(max_boost, 1.0 + boost_rate * self.step_count)
        
        # Adaptive boost 계산
        if prof.get("adaptive") and self._total_scans > 30:
            success_rate = len(self.attack_progress.discovered_services) / max(1, self._total_scans / 50)
            if prof.get("adapt_on_success") and success_rate > 0.1:
                time_factor *= (1.0 + 0.1 * success_rate)
        
        # 스텝당 스캔 수
        base_scans = int(prof["scans_per_step"] * time_factor)
        effective_scans = max(1, int(base_scans * prof["scan_efficiency"]))
        
        self._total_scans += base_scans
        self.stats.total_scans = self._total_scans
        
        outcome = DefenseOutcome.NOTHING
        
        # === 스캔 단계 ===
        for _ in range(effective_scans):
            outcome = self._perform_single_scan(prof, ss)
            
            # 서비스 발견 시 즉시 공격 시도 가능
            if outcome in [DefenseOutcome.SCAN_FOUND_SERVICE, 
                          DefenseOutcome.SCAN_FOUND_DECOY]:
                break
        
        # === 공격 단계 (발견한 서비스가 있으면) ===
        if self.attack_progress.discovered_services:
            outcome = self._attempt_exploit(outcome)
        
        return outcome
    
    def _perform_single_scan(
        self, 
        prof: Dict[str, Any], 
        ss
    ) -> DefenseOutcome:
        """단일 스캔 수행"""
        
        # 스캔 주소 결정
        if (self.rng.random() < prof["smart_scan"] and 
            self.attacker_belief.discovered_addresses):
            # Smart scan: 발견한 주소 근처 스캔
            scan_ip, scan_port = self._smart_scan(prof, ss)
        else:
            # Random scan
            scan_ip, scan_port = ss.get_random_address(self.rng)
        
        scan_addr = (scan_ip, scan_port)
        
        # 블랙리스트 체크
        if scan_ip in self.blacklist_ips:
            self._blocked_scans += 1
            self.stats.scans_blocked = self._blocked_scans
            return DefenseOutcome.SCAN_BLOCKED
        
        # 이미 스캔한 주소 스킵
        if scan_addr in self.attacker_belief.scanned_addresses:
            return DefenseOutcome.NOTHING
        
        # 스캔 기록
        self.attacker_belief.scanned_addresses.add(scan_addr)
        self.attack_progress.scanned_count += 1
        self.stats.effective_scans = len(self.attacker_belief.scanned_addresses)
        
        # === Virtual Answer Sheet와 대조 ===
        if scan_addr in self.address_to_service:
            svc = self.address_to_service[scan_addr]
            
            if svc.is_decoy:
                # 디코이 탐지 확률
                if self.rng.random() < prof["decoy_detect"]:
                    # 디코이임을 인식
                    return DefenseOutcome.NOTHING
                
                # 디코이에 속음
                self._decoy_hits += 1
                self.stats.decoy_hits = self._decoy_hits
                
                # Belief에 디코이 추가 (공격자는 실제 서비스로 인식)
                self.attacker_belief.add_discovery(scan_addr, svc.service_id)
                
                return DefenseOutcome.SCAN_FOUND_DECOY
            else:
                # 실제 서비스 발견
                svc.times_discovered += 1
                
                if svc.service_id not in self.attack_progress.discovered_services:
                    self.attack_progress.discovered_services.add(svc.service_id)
                    self.attacker_belief.add_discovery(scan_addr, svc.service_id)
                    self.stats.services_found = len(self.attack_progress.discovered_services)
                    
                    # Critical 자산 발견 체크
                    if svc.is_critical:
                        self.stats.critical_found += 1
                    
                    # 첫 발견 시간 기록
                    if self._first_discovery_step == 0:
                        self._first_discovery_step = self.step_count
                        self.stats.time_to_first_discovery = self._first_discovery_step
                    
                    return DefenseOutcome.SCAN_FOUND_SERVICE
                
                return DefenseOutcome.NOTHING
        
        return DefenseOutcome.SCAN_MISS
    
    def _smart_scan(self, prof: Dict[str, Any], ss) -> Tuple[int, int]:
        """지능적 스캔 - 발견한 주소 근처 스캔"""
        known_addrs = list(self.attacker_belief.discovered_addresses)
        if not known_addrs:
            return ss.get_random_address(self.rng)
        
        # 우선 타겟이 있으면 해당 영역 집중
        if prof.get("target_priority"):
            for target in prof["target_priority"]:
                for svc_name, addr in self.attacker_belief.estimated_locations.items():
                    if target in svc_name:
                        base_addr = addr
                        break
                else:
                    continue
                break
            else:
                base_addr = known_addrs[self.rng.integers(len(known_addrs))]
        else:
            base_addr = known_addrs[self.rng.integers(len(known_addrs))]
        
        # 근처 주소 생성
        scan_ip = base_addr[0] + self.rng.integers(-15, 16)
        scan_port = base_addr[1] + self.rng.integers(-30, 31)
        
        # 범위 제한
        scan_ip = max(ss.virtual_ip_start, min(ss.virtual_ip_end, scan_ip))
        scan_port = max(ss.virtual_port_start, min(ss.virtual_port_end, scan_port))
        
        return (scan_ip, scan_port)
    
    def _attempt_exploit(self, current_outcome: DefenseOutcome) -> DefenseOutcome:
        """
        익스플로잇/침투 시도
        
        핵심: Attacker Belief가 현재 Virtual Answer Sheet와 일치해야 공격 가능
        """
        prof = self.profile
        prog = self.attack_progress
        
        # 셔플 이후 시간에 따른 보호 효과
        steps_since_shuffle = self.step_count - self.last_shuffle_step
        shuffle_protection = max(0, 1.0 - steps_since_shuffle / 25)
        
        # Belief 기반 공격 가능 여부 체크
        valid_targets = []
        for svc_name, estimated_addr in self.attacker_belief.estimated_locations.items():
            # 현재 Virtual Answer Sheet와 일치하는지 확인
            if estimated_addr in self.address_to_service:
                actual_svc = self.address_to_service[estimated_addr]
                if actual_svc.service_id == svc_name and not actual_svc.is_decoy:
                    valid_targets.append(actual_svc)
        
        if not valid_targets:
            # Belief가 무효화됨 - 공격 실패
            return current_outcome
        
        # === Exploitation 단계 ===
        if prog.exploitation < AttackProgress.EXPLOITATION_THRESHOLD:
            # Shuffle protection으로 차단
            if self.rng.random() < shuffle_protection * 0.6:
                return DefenseOutcome.EXPLOIT_BLOCKED
            
            # 익스플로잇 시도
            if self.rng.random() < prof["exploit_prob"]:
                # 성공
                progress_gain = self.rng.uniform(0.05, 0.12)
                prog.exploitation += progress_gain
                
                # 디코이 타겟 체크
                decoy_targets = [
                    svc for svc in valid_targets 
                    if svc.service_id in self.attacker_belief.estimated_locations
                ]
                if any(svc.is_decoy for svc in decoy_targets):
                    return DefenseOutcome.EXPLOIT_DECOY
                
                return DefenseOutcome.EXPLOIT_SUCCESS
        
        # === Breach 단계 ===
        elif prog.compromise < AttackProgress.COMPROMISE_THRESHOLD:
            # Shuffle protection으로 차단
            if self.rng.random() < shuffle_protection * 0.4:
                return DefenseOutcome.BREACH_BLOCKED
            
            # 침투 시도
            if self.rng.random() < prof["breach_prob"]:
                progress_gain = self.rng.uniform(0.06, 0.15)
                prog.compromise += progress_gain
                
                if prog.compromised:
                    self.stats.time_to_breach = self.step_count
                    return DefenseOutcome.BREACH_SUCCESS
        
        return current_outcome
    
    # =========================================================================
    # 보상 계산
    # =========================================================================
    def _calculate_reward(
        self, 
        outcome: DefenseOutcome, 
        costs: Dict[str, float]
    ) -> float:
        """
        보상 계산
        
        설계 원칙:
        1. 수동적 방어 방지 (survival 최소화)
        2. 적극적 방어 보상 (차단, 디코이 유인)
        3. 비용 효율성
        4. 다양성 유지
        """
        rm = self.cfg.reward_model
        
        # 기본 생존 보상 (매우 작음)
        reward = rm.reward_survival
        
        # === Outcome별 보상/페널티 ===
        outcome_rewards = {
            DefenseOutcome.SCAN_BLOCKED: rm.reward_scan_blocked,
            DefenseOutcome.SCAN_FOUND_SERVICE: rm.penalty_service_found,
            DefenseOutcome.SCAN_FOUND_DECOY: rm.reward_decoy_scan,
            DefenseOutcome.EXPLOIT_BLOCKED: rm.reward_exploit_blocked,
            DefenseOutcome.EXPLOIT_SUCCESS: rm.penalty_exploit,
            DefenseOutcome.EXPLOIT_DECOY: rm.reward_decoy_exploit,
            DefenseOutcome.BREACH_BLOCKED: rm.reward_breach_blocked,
            DefenseOutcome.BREACH_SUCCESS: rm.penalty_breach,
            DefenseOutcome.SCAN_MISS: 0.0,
            DefenseOutcome.NOTHING: 0.0,
        }
        reward += outcome_rewards.get(outcome, 0.0)
        
        # Critical 자산 발견 추가 페널티
        if (outcome == DefenseOutcome.SCAN_FOUND_SERVICE and 
            self.stats.critical_found > 0):
            reward += rm.penalty_critical_found
        
        # === 비용 페널티 ===
        reward -= self.cost_weight * costs["total"]
        
        # === 다양성 보너스 ===
        reward += rm.diversity_bonus_weight * self.current_diversity
        
        # === 조기 탐지 보너스 ===
        if outcome in [DefenseOutcome.SCAN_BLOCKED, 
                      DefenseOutcome.EXPLOIT_BLOCKED,
                      DefenseOutcome.BREACH_BLOCKED]:
            if self.step_count < rm.early_detection_window:
                early_factor = 1.0 - (self.step_count / rm.early_detection_window)
                reward += rm.early_detection_bonus * early_factor
        
        # === MTD 활동 보너스/페널티 ===
        steps_since_mtd = self.step_count - self.last_shuffle_step
        if steps_since_mtd <= 5:
            reward += rm.mtd_activity_bonus
        elif steps_since_mtd > rm.mtd_inactivity_threshold:
            # 장기 미활동 + 위협 상황이면 페널티
            if self.attack_progress.discovery > 0.3:
                reward += rm.mtd_inactivity_penalty
        
        return reward
    
    # =========================================================================
    # 다양성/통계 계산
    # =========================================================================
    def _calculate_diversity(self) -> float:
        """
        다양성 계산 (Jaccard Distance 기반)
        
        현재 구성이 이전 구성들과 얼마나 다른지 측정
        """
        current_config = set(
            svc.get_virtual_address() 
            for svc in self.service_mappings 
            if svc.active and not svc.is_decoy
        )
        
        if not self.config_history:
            self.config_history.append(current_config)
            return 1.0
        
        # 최근 5개 구성과 비교
        total_distance = 0.0
        compare_count = min(5, len(self.config_history))
        
        for prev_config in self.config_history[-compare_count:]:
            if len(current_config) == 0 and len(prev_config) == 0:
                distance = 0.0
            else:
                intersection = len(current_config.intersection(prev_config))
                union = len(current_config.union(prev_config))
                jaccard_sim = intersection / max(1, union)
                distance = 1.0 - jaccard_sim
            total_distance += distance
        
        diversity = total_distance / max(1, compare_count)
        
        # 히스토리 업데이트
        self.config_history.append(current_config)
        if len(self.config_history) > 10:
            self.config_history.pop(0)
        
        return min(1.0, diversity)
    
    def _calculate_redundancy(self) -> float:
        """Redundancy 계산 (활성 디코이 비율)"""
        decoys = [svc for svc in self.service_mappings if svc.is_decoy]
        if not decoys:
            return 0.0
        active_decoys = sum(1 for svc in decoys if svc.active)
        return active_decoys / len(decoys)
    
    def _update_stats(self, costs: Dict[str, float], terminated: bool):
        """에피소드 통계 업데이트"""
        real_services = [svc for svc in self.service_mappings if not svc.is_decoy]
        
        # 방어 성공률
        total_threats = self._blocked_scans + len(self.attack_progress.discovered_services)
        if total_threats > 0:
            self.stats.defense_success_rate = self._blocked_scans / total_threats
        
        self.stats.breach_prevented = not terminated
        self.stats.services_found = len(self.attack_progress.discovered_services)
        self.stats.decoy_hits = self._decoy_hits
        self.stats.scans_blocked = self._blocked_scans
        
        # 다양성 통계
        self.stats.avg_diversity = (
            (self.stats.avg_diversity * (self.step_count - 1) + self.current_diversity) 
            / self.step_count
        ) if self.step_count > 0 else self.current_diversity
        self.stats.min_diversity = min(self.stats.min_diversity, self.current_diversity)
        self.stats.avg_redundancy = self._calculate_redundancy()
        
        # 비용 통계
        self.stats.total_cost += costs["total"]
        self.stats.total_latency_ms += costs.get("latency_ms", 0)
        self.stats.total_energy = self.energy_used
        
        # S_MTD 계산
        self.stats.compute_s_mtd()
    
    # =========================================================================
    # Gymnasium Interface
    # =========================================================================
    def set_reward_profile(self, profile: str):
        """보상 프로파일 설정 (explore/exploit)"""
        if profile == "explore":
            self.cost_weight = self.cfg.reward_model.cost_weight_explore
        else:
            self.cost_weight = self.cfg.reward_model.cost_weight_exploit
    
    def reset(
        self, 
        *, 
        seed: Optional[int] = None, 
        options: Optional[Dict] = None
    ) -> Tuple[np.ndarray, Dict]:
        """환경 리셋"""
        if seed is not None:
            self.rng = np.random.default_rng(seed)
        
        # 서비스 매핑 재초기화
        self._init_service_mappings()
        
        # 상태 초기화
        self.attacker_belief.reset()
        self.attack_progress.reset()
        
        self.step_count = 0
        self.energy_used = 0.0
        self.blacklist_ips.clear()
        self.last_action = np.zeros(ACTION_DIM)
        self.last_shuffle_step = 0
        self.config_history.clear()
        self.current_diversity = 1.0
        self.stats = EpisodeStats()
        
        self._total_scans = 0
        self._blocked_scans = 0
        self._decoy_hits = 0
        self._first_discovery_step = 0
        self._mtd_actions_taken = 0
        
        # 초기 상태 샘플링
        init_mode = self._sample_initial_state()
        
        return self._get_observation(), {"init_mode": init_mode}
    
    def _sample_initial_state(self) -> str:
        """초기 상태 샘플링"""
        init_cfg = self.cfg.initial_state
        
        if init_cfg.mode == "sample":
            mode = self.rng.choice(
                ["clean", "partial", "discovered"], 
                p=init_cfg.mode_probs
            )
        else:
            mode = init_cfg.mode
        
        if mode == "partial":
            # 일부 스캔된 상태
            ss = self.cfg.search_space
            pre_scans = int(ss.total_search_space * init_cfg.pre_scanned_ratio)
            for _ in range(pre_scans):
                addr = ss.get_random_address(self.rng)
                self.attacker_belief.scanned_addresses.add(addr)
        
        elif mode == "discovered":
            # 서비스 발견된 상태
            real_services = [svc for svc in self.service_mappings if not svc.is_decoy]
            if init_cfg.pre_discovered_services > 0 and real_services:
                discovered = self.rng.choice(
                    real_services,
                    min(init_cfg.pre_discovered_services, len(real_services)),
                    replace=False
                )
                for svc in discovered:
                    addr = svc.get_virtual_address()
                    self.attacker_belief.add_discovery(addr, svc.service_id)
                    self.attack_progress.discovered_services.add(svc.service_id)
                    self.attack_progress.discovery = 0.3
                    self._first_discovery_step = 1
        
        return mode
    
    def step(
        self, 
        action: np.ndarray
    ) -> Tuple[np.ndarray, float, bool, bool, Dict]:
        """환경 스텝"""
        self.step_count += 1
        
        # 액션 클리핑 및 스케일링
        action = np.clip(action, -1, 1)
        scaled_action = (action + 1) / 2  # [-1, 1] → [0, 1]
        
        # MTD 액션 적용
        mtd_cost = self._apply_mtd(scaled_action)
        
        # 다양성 업데이트
        self.current_diversity = self._calculate_diversity()
        
        # 공격자 스텝
        outcome = self._attacker_step()
        
        # 보상 계산
        reward = self._calculate_reward(outcome, mtd_cost)
        self.last_action = action
        
        # 종료 조건 확인
        terminated = self.attack_progress.compromised
        truncated = self.step_count >= self.cfg.ppo.max_steps
        
        # 통계 업데이트
        self._update_stats(mtd_cost, terminated)
        
        # Info
        info = self.stats.as_dict()
        info["outcome"] = outcome.name
        info["mtd_actions_taken"] = self._mtd_actions_taken
        info["attacker_confidence"] = self.attacker_belief.confidence
        
        return self._get_observation(), reward, terminated, truncated, info
    
    def _get_observation(self) -> np.ndarray:
        """관측 벡터 생성"""
        ss = self.cfg.search_space
        real_services = [svc for svc in self.service_mappings if not svc.is_decoy]
        
        # 탐색 공간 스캔 비율 (정규화)
        scanned_ratio = len(self.attacker_belief.scanned_addresses) / ss.total_search_space
        scanned_normalized = min(1.0, scanned_ratio * 20)  # 5%까지 스캔하면 1.0
        
        # 서비스 발견 비율
        discovered_ratio = len(self.attack_progress.discovered_services) / max(len(real_services), 1)
        
        # Critical 자산 발견 여부
        critical_names = set(self.cfg.testbed.critical_assets)
        critical_discovered = any(
            any(cn in svc_name for cn in critical_names)
            for svc_name in self.attack_progress.discovered_services
        )
        
        # 공격자 스캔 속도 추정
        scan_rate = self._total_scans / max(1, self.step_count)
        scan_rate_normalized = min(1.0, scan_rate / 30)
        
        # Shuffle 이후 스텝 (정규화)
        steps_since_shuffle = min(1.0, (self.step_count - self.last_shuffle_step) / 30)
        
        obs = np.array([
            scanned_normalized,
            discovered_ratio,
            float(critical_discovered),
            self.attack_progress.exploitation,
            self.attack_progress.compromise,
            self.current_diversity,
            self._calculate_redundancy(),
            self._decoy_hits / max(1, self._total_scans) * 10,
            1 - (self.energy_used / self.cfg.cost_model.energy_budget_joule),
            steps_since_shuffle,
            scan_rate_normalized,
            self.last_action[0] if len(self.last_action) > 0 else 0,
            self.last_action[1] if len(self.last_action) > 1 else 0,
            self.last_action[2] if len(self.last_action) > 2 else 0,
            self.last_action[3] if len(self.last_action) > 3 else 0,
        ], dtype=np.float32)
        
        return np.clip(obs, -1, 1)
    
    def render(self, mode: str = "human"):
        """환경 시각화"""
        if mode != "human":
            return
        
        print(f"\n{'='*60}")
        print(f"Step: {self.step_count}")
        print(f"Attack Phase: {self.attack_progress.phase.name}")
        print(f"Discovered Services: {len(self.attack_progress.discovered_services)}")
        print(f"Exploitation: {self.attack_progress.exploitation:.2%}")
        print(f"Compromise: {self.attack_progress.compromise:.2%}")
        print(f"Diversity: {self.current_diversity:.2f}")
        print(f"MTD Actions: {self._mtd_actions_taken}")
        print(f"S_MTD: {self.stats.s_mtd:.3f}")
        print(f"{'='*60}")


# =============================================================================
# Test
# =============================================================================
if __name__ == "__main__":
    # 환경 테스트
    env = MTDEnvironment(seed=42, seeker_level=2)
    
    print("Testing MTD Environment v08...")
    print(f"Observation Space: {env.observation_space}")
    print(f"Action Space: {env.action_space}")
    
    obs, info = env.reset()
    print(f"Initial observation shape: {obs.shape}")
    print(f"Initial info: {info}")
    
    total_reward = 0
    for step in range(100):
        action = env.action_space.sample()
        obs, reward, terminated, truncated, info = env.step(action)
        total_reward += reward
        
        if step % 20 == 0:
            env.render()
        
        if terminated or truncated:
            print(f"\nEpisode ended at step {step}")
            print(f"Total reward: {total_reward:.2f}")
            print(f"Terminated: {terminated}, Truncated: {truncated}")
            break
    
    print("\n✅ Environment test passed!")