#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MTD RL Environment v07 - Real IP×Port search space implementation.

Implements:
- Actual (IP, Port) → Service mapping
- Attacker scans through search space (Urn model)
- Dynamic Diversity/Redundancy metrics
- Level-based scan efficiency
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Set, Tuple

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from .rl_config_v07 import (
    ACTION_DIM,
    DEFAULT_SEEKER_PROFILES,
    STATE_DIM,
    AttackProgress,
    EpisodeStats,
    MTDConfig,
    ServiceMapping,
    load_seeker_profiles,
)


class Outcome(Enum):
    NOTHING = auto()
    SCAN_MISS = auto()           # 스캔했지만 아무것도 없음
    SCAN_BLOCKED = auto()        # 블랙리스트로 차단
    SCAN_FOUND_SERVICE = auto()  # 실제 서비스 발견!
    SCAN_FOUND_DECOY = auto()    # 디코이 발견
    EXPLOIT_BLOCKED = auto()
    EXPLOIT_SUCCESS = auto()
    EXPLOIT_DECOY = auto()
    BREACH_BLOCKED = auto()
    BREACH_SUCCESS = auto()


class MTDEnvironment(gym.Env):
    """MTD Environment with real search space implementation."""
    
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

        # Spaces
        self.observation_space = spaces.Box(-1, 1, shape=(STATE_DIM,), dtype=np.float32)
        self.action_space = spaces.Box(-1, 1, shape=(ACTION_DIM,), dtype=np.float32)

        # Seeker profile
        self.profiles = load_seeker_profiles(seeker_profiles_path)
        self.seeker_level = seeker_level
        self.profile = self.profiles.get(seeker_level, self.profiles[1])

        # Initialize service mappings
        self._init_service_mappings()
        
        # Attack state
        self.attack_progress = AttackProgress()
        
        # Environment state
        self.step_count = 0
        self.energy_used = 0.0
        self.blacklist_ips: Set[int] = set()
        self.last_action = np.zeros(ACTION_DIM)
        self.last_shuffle_step = 0
        self.shuffle_count = 0
        self.stats = EpisodeStats()
        self.cost_weight = self.cfg.reward_model.cost_weight_explore
        
        # Diversity tracking
        self.config_history: List[Set[Tuple[int, int]]] = []
        self.current_diversity = 1.0
        
        # Counters
        self._total_scans = 0
        self._blocked_scans = 0
        self._decoy_hits = 0
        self._first_discovery_step = 0

    def _init_service_mappings(self):
        """서비스 매핑 초기화 - 가상 (IP, Port) ↔ 실제 서비스"""
        self.service_mappings: List[ServiceMapping] = []
        
        ss = self.cfg.search_space
        tb = self.cfg.testbed
        
        # 실제 타겟 매핑 (4개 타겟 × 5개 포트 = 20개 서비스)
        port_list = list(tb.service_ports.values())
        
        for i, (name, real_ip) in enumerate(tb.real_targets.items()):
            for j, (port_name, real_port) in enumerate(tb.service_ports.items()):
                # 가상 주소 랜덤 할당
                virt_ip = self.rng.integers(ss.virtual_ip_start, ss.virtual_ip_end + 1)
                virt_port = self.rng.integers(ss.virtual_port_start, ss.virtual_port_end + 1)
                
                self.service_mappings.append(ServiceMapping(
                    target_name=f"{name}:{port_name}",
                    real_ip=real_ip,
                    real_port=real_port,
                    virtual_ip=virt_ip,
                    virtual_port=virt_port,
                    is_decoy=False,
                    is_critical=(name in tb.critical_assets),
                    active=True,
                ))
        
        # 디코이 매핑 (2개 디코이 × 5개 포트 = 10개 디코이 서비스)
        for name, real_ip in tb.decoys.items():
            for port_name, real_port in tb.service_ports.items():
                virt_ip = self.rng.integers(ss.virtual_ip_start, ss.virtual_ip_end + 1)
                virt_port = self.rng.integers(ss.virtual_port_start, ss.virtual_port_end + 1)
                
                self.service_mappings.append(ServiceMapping(
                    target_name=f"{name}:{port_name}",
                    real_ip=real_ip,
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
        self.address_to_service: Dict[Tuple[int, int], ServiceMapping] = {}
        for svc in self.service_mappings:
            if svc.active:
                addr = svc.get_virtual_address()
                self.address_to_service[addr] = svc

    def _shuffle_addresses(self, intensity: float):
        """IP/Port Shuffle - 가상 주소 재할당"""
        ss = self.cfg.search_space
        num_to_shuffle = int(len(self.service_mappings) * intensity)
        
        # 셔플할 서비스 선택
        services_to_shuffle = self.rng.choice(
            self.service_mappings, 
            min(num_to_shuffle, len(self.service_mappings)),
            replace=False
        )
        
        shuffled_count = 0
        for svc in services_to_shuffle:
            if not svc.is_decoy or svc.active:  # 활성 서비스만 셔플
                old_addr = svc.get_virtual_address()
                svc.virtual_ip = self.rng.integers(ss.virtual_ip_start, ss.virtual_ip_end + 1)
                svc.virtual_port = self.rng.integers(ss.virtual_port_start, ss.virtual_port_end + 1)
                shuffled_count += 1
        
        self._update_address_map()
        self.shuffle_count += 1
        self.last_shuffle_step = self.step_count
        
        # Shuffle 후 공격자가 발견한 서비스 중 셔플된 것은 무효화
        shuffled_names = {svc.target_name for svc in services_to_shuffle}
        self.attack_progress.discovered_services -= shuffled_names
        
        return shuffled_count

    def _calculate_diversity(self) -> float:
        """
        Diversity 계산 (Alavizadeh et al.)
        = 현재 구성이 이전 구성들과 얼마나 다른가
        """
        current_config = set(svc.get_virtual_address() for svc in self.service_mappings if svc.active)
        
        if not self.config_history:
            self.config_history.append(current_config)
            return 1.0
        
        # 이전 구성들과의 차이 계산
        total_diff = 0
        for prev_config in self.config_history[-5:]:  # 최근 5개와 비교
            diff = len(current_config.symmetric_difference(prev_config))
            total_diff += diff / max(len(current_config), 1)
        
        diversity = total_diff / max(len(self.config_history[-5:]), 1)
        
        # 현재 구성 저장
        self.config_history.append(current_config)
        if len(self.config_history) > 10:
            self.config_history.pop(0)
        
        return min(1.0, diversity)

    def _calculate_redundancy(self) -> float:
        """
        Redundancy 계산 (Alavizadeh et al.)
        = 활성 디코이 / 전체 디코이
        """
        decoys = [svc for svc in self.service_mappings if svc.is_decoy]
        if not decoys:
            return 0.0
        active_decoys = sum(1 for svc in decoys if svc.active)
        return active_decoys / len(decoys)

    def set_reward_profile(self, profile: str):
        if profile == "explore":
            self.cost_weight = self.cfg.reward_model.cost_weight_explore
        else:
            self.cost_weight = self.cfg.reward_model.cost_weight_exploit

    def reset(self, *, seed=None, options=None) -> Tuple[np.ndarray, Dict]:
        if seed is not None:
            self.rng = np.random.default_rng(seed)

        # 서비스 매핑 재초기화
        self._init_service_mappings()
        
        # 공격 진행 상태 리셋
        self.attack_progress = AttackProgress()
        
        # 환경 상태 리셋
        self.step_count = 0
        self.energy_used = 0.0
        self.blacklist_ips.clear()
        self.last_action = np.zeros(ACTION_DIM)
        self.last_shuffle_step = 0
        self.shuffle_count = 0
        self.config_history.clear()
        self.current_diversity = 1.0
        self.stats = EpisodeStats()
        
        self._total_scans = 0
        self._blocked_scans = 0
        self._decoy_hits = 0
        self._first_discovery_step = 0

        # === Initial State Sampling ===
        init_cfg = self.cfg.initial_state
        if init_cfg.mode == "sample":
            mode = self.rng.choice(["clean", "found", "near_breach"], p=init_cfg.mode_probs)
        else:
            mode = init_cfg.mode

        if mode == "found":
            # 이미 일부 탐색 공간을 스캔한 상태
            ss = self.cfg.search_space
            pre_scans = int(ss.total_search_space * init_cfg.pre_scanned_ratio)
            for _ in range(pre_scans):
                ip = self.rng.integers(ss.virtual_ip_start, ss.virtual_ip_end + 1)
                port = self.rng.integers(ss.virtual_port_start, ss.virtual_port_end + 1)
                self.attack_progress.scanned_addresses.add((ip, port))
            
            # 일부 서비스 이미 발견
            real_services = [svc for svc in self.service_mappings if not svc.is_decoy]
            discovered = self.rng.choice(real_services, min(init_cfg.pre_discovered_services, len(real_services)), replace=False)
            for svc in discovered:
                self.attack_progress.discovered_services.add(svc.target_name)
                self.attack_progress.scanned_addresses.add(svc.get_virtual_address())
            self.attack_progress.discovery = 0.5
            self._first_discovery_step = 1

        elif mode == "near_breach":
            # Breach 직전 상태
            real_services = [svc for svc in self.service_mappings if not svc.is_decoy]
            target = self.rng.choice(real_services)
            self.attack_progress.discovered_services.add(target.target_name)
            self.attack_progress.scanned_addresses.add(target.get_virtual_address())
            self.attack_progress.discovery = 1.0
            self.attack_progress.exploitation = 0.8
            self.attack_progress.compromise = self.rng.uniform(0.3, 0.6)
            self._first_discovery_step = 1

        return self._get_obs(), {"init_mode": mode}

    def step(self, action: np.ndarray) -> Tuple[np.ndarray, float, bool, bool, Dict]:
        self.step_count += 1
        action = np.clip(action, -1, 1)
        scaled = (action + 1) / 2  # [0, 1]

        # Apply MTD actions
        mtd_cost = self._apply_mtd(scaled)
        
        # Update diversity
        self.current_diversity = self._calculate_diversity()

        # Attacker step (실제 탐색)
        outcome = self._attacker_step()

        # Calculate reward
        reward = self._calc_reward(outcome, mtd_cost)
        self.last_action = action

        # Check termination
        terminated = self.attack_progress.compromised
        truncated = self.step_count >= self.cfg.ppo.max_steps

        # Update stats
        self._update_stats(mtd_cost, terminated)

        info = self.stats.as_dict()
        info["outcome"] = outcome.name

        return self._get_obs(), reward, terminated, truncated, info

    def _apply_mtd(self, scaled: np.ndarray) -> Dict[str, float]:
        shuffle, port_hop, decoy_ratio, bl_aggr, bl_dur, swap = scaled
        th = self.cfg.thresholds
        costs = {"total": 0.0, "latency_ms": 0.0, "energy": 0.0}

        # IP Shuffle
        if shuffle >= th.shuffle:
            num_shuffled = self._shuffle_addresses(shuffle)
            shuffle_cost = self.cfg.cost_model.calculate_shuffle_cost(shuffle, num_shuffled)
            costs["latency_ms"] += shuffle_cost["latency_ms"]
            costs["energy"] += shuffle_cost["energy"]
            costs["total"] += shuffle_cost["total"]
            self.energy_used += shuffle_cost["energy"]

        # Port Hop (shuffle과 유사하지만 포트만)
        if port_hop >= th.port_hop:
            ss = self.cfg.search_space
            for svc in self.service_mappings:
                if svc.active and self.rng.random() < port_hop:
                    svc.virtual_port = self.rng.integers(ss.virtual_port_start, ss.virtual_port_end + 1)
            self._update_address_map()
            costs["total"] += self.cfg.cost_model.port_hop_cpu * port_hop

        # Decoy activation
        if decoy_ratio >= th.decoy_activate:
            decoys = [svc for svc in self.service_mappings if svc.is_decoy]
            num_activate = int(len(decoys) * decoy_ratio)
            for i, svc in enumerate(decoys):
                svc.active = (i < num_activate)
            self._update_address_map()
            active_count = sum(1 for svc in decoys if svc.active)
            decoy_cost = self.cfg.cost_model.calculate_decoy_cost(active_count)
            costs["total"] += decoy_cost["total"]

        # Blacklist
        if bl_aggr >= th.blacklist:
            # 공격자가 스캔한 IP 중 일부를 블랙리스트에 추가
            num_to_block = int(bl_aggr * 10)
            recent_scans = list(self.attack_progress.scanned_addresses)[-50:]
            for addr in recent_scans[:num_to_block]:
                self.blacklist_ips.add(addr[0])
            costs["total"] += self.cfg.cost_model.blacklist_update * bl_aggr

        return costs

    def _attacker_step(self) -> Outcome:
        """공격자의 실제 탐색 단계 (Urn Model)"""
        prof = self.profile
        ss = self.cfg.search_space
        
        # Time boost for level 2+
        time_factor = 1.0
        if prof.get("time_boost"):
            time_factor = 1.0 + 0.3 * (self.step_count / self.cfg.ppo.max_steps)
        
        # Adaptive boost for level 3+
        if prof.get("adaptive") and self._total_scans > 20:
            success_rate = len(self.attack_progress.discovered_services) / max(1, self._total_scans / 100)
            time_factor *= (1.0 + 0.2 * success_rate)

        # 스텝당 스캔 수 결정
        scans_this_step = int(prof["scans_per_step"] * time_factor)
        effective_scans = int(scans_this_step * prof["scan_efficiency"])
        
        self._total_scans += scans_this_step
        self.stats.total_scans = self._total_scans

        outcome = Outcome.NOTHING
        
        for _ in range(effective_scans):
            # 스캔할 (IP, Port) 선택
            if self.rng.random() < prof["smart_scan"] and self.attack_progress.scanned_addresses:
                # Smart scan: 이전에 발견한 주소 근처 스캔
                known = list(self.attack_progress.scanned_addresses)
                base_addr = known[self.rng.integers(len(known))]
                scan_ip = base_addr[0] + self.rng.integers(-5, 6)
                scan_port = base_addr[1] + self.rng.integers(-50, 51)
                scan_ip = max(ss.virtual_ip_start, min(ss.virtual_ip_end, scan_ip))
                scan_port = max(ss.virtual_port_start, min(ss.virtual_port_end, scan_port))
            else:
                # Random scan
                scan_ip = self.rng.integers(ss.virtual_ip_start, ss.virtual_ip_end + 1)
                scan_port = self.rng.integers(ss.virtual_port_start, ss.virtual_port_end + 1)
            
            scan_addr = (scan_ip, scan_port)
            
            # 블랙리스트 체크
            if scan_ip in self.blacklist_ips:
                self._blocked_scans += 1
                outcome = Outcome.SCAN_BLOCKED
                continue
            
            # 이미 스캔한 주소인지 확인
            if scan_addr in self.attack_progress.scanned_addresses:
                continue
            
            self.attack_progress.scanned_addresses.add(scan_addr)
            self.stats.effective_scans = len(self.attack_progress.scanned_addresses)
            
            # 서비스 발견 여부 확인
            if scan_addr in self.address_to_service:
                svc = self.address_to_service[scan_addr]
                
                if svc.is_decoy:
                    # 디코이 탐지 확률
                    if self.rng.random() < prof["decoy_detect"]:
                        continue  # 디코이 인식하고 무시
                    self._decoy_hits += 1
                    outcome = Outcome.SCAN_FOUND_DECOY
                else:
                    # 실제 서비스 발견!
                    if svc.target_name not in self.attack_progress.discovered_services:
                        self.attack_progress.discovered_services.add(svc.target_name)
                        if self._first_discovery_step == 0:
                            self._first_discovery_step = self.step_count
                        outcome = Outcome.SCAN_FOUND_SERVICE
            else:
                outcome = Outcome.SCAN_MISS

        # Discovery progress 업데이트
        real_services = [svc for svc in self.service_mappings if not svc.is_decoy]
        discovered_ratio = len(self.attack_progress.discovered_services) / max(len(real_services), 1)
        self.attack_progress.discovery = discovered_ratio

        # 발견한 서비스에 대해 exploit/breach 시도
        if self.attack_progress.discovered_services:
            outcome = self._attempt_exploit(outcome)

        return outcome

    def _attempt_exploit(self, current_outcome: Outcome) -> Outcome:
        """발견한 서비스에 대해 exploit/breach 시도"""
        prof = self.profile
        prog = self.attack_progress
        
        # Shuffle 이후 시간에 따른 보호 효과
        steps_since_shuffle = self.step_count - self.last_shuffle_step
        shuffle_protection = max(0, 1 - steps_since_shuffle / 15)
        
        if prog.exploitation < AttackProgress.EXPLOITATION_THRESHOLD:
            # Exploitation 단계
            if self.rng.random() < shuffle_protection * 0.5:
                return Outcome.EXPLOIT_BLOCKED
            
            if self.rng.random() < prof["exploit_prob"]:
                prog.exploitation += self.rng.uniform(0.1, 0.25)
                # 디코이에 대한 exploit인지 확인
                discovered_decoys = [
                    svc for svc in self.service_mappings 
                    if svc.is_decoy and svc.target_name in prog.discovered_services
                ]
                if discovered_decoys and self.rng.random() < 0.5:
                    return Outcome.EXPLOIT_DECOY
                return Outcome.EXPLOIT_SUCCESS
        
        elif prog.compromise < AttackProgress.COMPROMISE_THRESHOLD:
            # Breach 단계
            if self.rng.random() < shuffle_protection * 0.3:
                return Outcome.BREACH_BLOCKED
            
            if self.rng.random() < prof["breach_prob"]:
                prog.compromise += self.rng.uniform(0.15, 0.35)
                if prog.compromised:
                    self.stats.time_to_breach = self.step_count
                    return Outcome.BREACH_SUCCESS
        
        return current_outcome

    def _calc_reward(self, outcome: Outcome, costs: Dict[str, float]) -> float:
        rm = self.cfg.reward_model
        reward = rm.reward_survival

        reward_map = {
            Outcome.SCAN_BLOCKED: rm.reward_scan_blocked,
            Outcome.SCAN_FOUND_SERVICE: rm.penalty_service_found,
            Outcome.SCAN_FOUND_DECOY: rm.reward_decoy_scan,
            Outcome.EXPLOIT_BLOCKED: rm.reward_exploit_blocked,
            Outcome.EXPLOIT_SUCCESS: rm.penalty_exploit,
            Outcome.EXPLOIT_DECOY: rm.reward_decoy_exploit,
            Outcome.BREACH_BLOCKED: rm.reward_breach_blocked,
            Outcome.BREACH_SUCCESS: rm.penalty_breach,
        }
        reward += reward_map.get(outcome, 0)

        # Cost penalty
        reward -= self.cost_weight * costs["total"]

        # Diversity bonus
        reward += 0.5 * self.current_diversity

        return reward

    def _update_stats(self, costs: Dict[str, float], terminated: bool):
        real_services = [svc for svc in self.service_mappings if not svc.is_decoy]
        
        self.stats.defense_success_rate = self._blocked_scans / max(1, self._total_scans)
        self.stats.breach_prevented = not terminated
        self.stats.services_found = len(self.attack_progress.discovered_services)
        self.stats.decoy_hits = self._decoy_hits
        self.stats.scans_blocked = self._blocked_scans
        self.stats.time_to_first_discovery = self._first_discovery_step
        
        self.stats.avg_diversity = self.current_diversity
        self.stats.min_diversity = min(self.stats.min_diversity, self.current_diversity)
        self.stats.avg_redundancy = self._calculate_redundancy()
        
        self.stats.total_cost += costs["total"]
        self.stats.total_latency_ms += costs.get("latency_ms", 0)
        self.stats.total_energy = self.energy_used
        
        self.stats.compute_s_mtd()

    def _get_obs(self) -> np.ndarray:
        ss = self.cfg.search_space
        real_services = [svc for svc in self.service_mappings if not svc.is_decoy]
        
        # 탐색 공간 중 스캔된 비율
        scanned_ratio = len(self.attack_progress.scanned_addresses) / ss.total_search_space
        
        # 서비스 발견 비율
        discovered_ratio = len(self.attack_progress.discovered_services) / max(len(real_services), 1)
        
        # 중요 자산 발견 여부
        critical_names = {f"{name}:" for name in self.cfg.testbed.critical_assets}
        critical_discovered = any(
            any(cn in svc_name for cn in critical_names) 
            for svc_name in self.attack_progress.discovered_services
        )
        
        # 공격자 스캔 속도 추정
        scan_rate = self._total_scans / max(1, self.step_count)
        
        obs = np.array([
            min(1.0, scanned_ratio * 100),  # 정규화 (탐색 공간이 크므로)
            discovered_ratio,
            float(critical_discovered),
            self.attack_progress.exploitation,
            self.attack_progress.compromise,
            self.current_diversity,
            self._calculate_redundancy(),
            self._decoy_hits / max(1, self._total_scans) * 10,
            1 - (self.energy_used / self.cfg.cost_model.energy_budget_joule),
            min(1.0, (self.step_count - self.last_shuffle_step) / 20),
            min(1.0, scan_rate / 50),
            self.last_action[0] if len(self.last_action) > 0 else 0,
            self.last_action[1] if len(self.last_action) > 1 else 0,
            self.last_action[2] if len(self.last_action) > 2 else 0,
            self.last_action[3] if len(self.last_action) > 3 else 0,
        ], dtype=np.float32)

        return np.clip(obs, -1, 1)


# Endpoint alias for backward compatibility
@dataclass
class Endpoint:
    name: str
    ip: str
    is_decoy: bool = False