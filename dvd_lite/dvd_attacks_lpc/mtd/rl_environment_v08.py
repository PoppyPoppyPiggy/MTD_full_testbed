#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MTD RL Environment v08 - 강화학습 환경 (학술적 지표 포함)

핵심 개선사항:
1. 학술적 MTD 지표 계산 (MTTC, ASR, CDI, NED, ASP, DES, CER)
2. Shannon Entropy 기반 다양성 계산
3. 적극적 방어 유도를 위한 보상 체계 개선
4. 공격자 시뮬레이션 현실성 개선

저자: MTD-RL Research Team
버전: 0.8.3
"""
from __future__ import annotations

import json
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
    MTD_METRICS,
    scale_action,
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
    known_mappings: Dict[str, Tuple[str, int]] = field(default_factory=dict)


# =============================================================================
# MTD Environment
# =============================================================================
class MTDEnvironment(gym.Env):
    """
    MTD 강화학습 환경 v08.3 - 학술적 지표 포함
    
    학술적 MTD 지표:
    - MTTC: Mean Time To Compromise
    - ASR: Attack Surface Reduction
    - CDI: Configuration Diversity Index (Shannon Entropy)
    - NED: Normalized Entropy of Defense
    - ASP: Attack Success Probability
    - DES: Defense Effectiveness Score
    - CER: Cost Efficiency Ratio
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

        # 에피소드 통계
        self.stats = EpisodeStats()
        self.step_count = 0
        self.max_steps = self.config.ppo.max_steps

        # MTD 메트릭 히스토리
        self.diversity_history: List[float] = []
        self.redundancy_history: List[float] = []
        self.action_history: List[np.ndarray] = []

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
        self.action_history = []
        self.last_action = np.zeros(ACTION_DIM)
        self.last_shuffle_step = 0
        self.last_swap_step = 0

        return self._get_state(), self._get_info()

    def step(self, action: np.ndarray) -> Tuple[np.ndarray, float, bool, bool, dict]:
        """환경 스텝"""
        self.step_count += 1
        self.last_action = action.copy()
        self.action_history.append(action.copy())

        # 1. MTD 액션 실행
        mtd_cost = self._execute_mtd_action(action)

        # 2. 공격자 행동 시뮬레이션
        attack_result = self._simulate_attacker()

        # 3. 메트릭 기록
        diversity = self._compute_cdi()  # Shannon Entropy 기반
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
        """MTD 액션 실행"""
        scaled = scale_action(action)
        total_cost = 0.0

        # 1. Network Shuffle
        shuffle_intensity = scaled[0]
        if shuffle_intensity > 0.25:
            cost = self._do_shuffle(shuffle_intensity)
            total_cost += cost
            self.last_shuffle_step = self.step_count

        # 2. Port Hop
        port_hop_intensity = scaled[1]
        if port_hop_intensity > 0.35:
            cost = self._do_port_hop(port_hop_intensity)
            total_cost += cost

        # 3. Decoy Activation
        decoy_ratio = scaled[2]
        if decoy_ratio > 0.4:
            cost = self._activate_decoys(decoy_ratio)
            total_cost += cost

        # 4. Blacklist
        blacklist_aggression = scaled[3]
        blacklist_duration = scaled[4]
        if blacklist_aggression > 0.6:
            cost = self._update_blacklist(blacklist_aggression, blacklist_duration)
            total_cost += cost

        # 5. Service Swap
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

            # 새 가상 IP/Port 할당
            svc.virtual_ip = f"10.13.0.{random.randint(100, 199)}"
            svc.virtual_port = random.randint(10000, 60000)
            svc.last_shuffle_step = self.step_count

            # 공격자 매핑 정보 무효화
            if svc_name in self.attacker.known_mappings:
                del self.attacker.known_mappings[svc_name]

            # 발견 상태 무효화
            if svc.is_discovered and random.random() < intensity * 0.8:
                svc.is_discovered = False
                self.attacker.discovered_services.discard(svc_name)
                self.attacker.confusion_level += 0.15

        self.stats.total_shuffles += 1
        return intensity * self.config.cost.shuffle * 0.7

    def _do_port_hop(self, intensity: float) -> float:
        """포트 호핑 실행"""
        critical_services = [s for s in self.services.values() if s.is_critical]

        hopped = 0
        for svc in critical_services:
            if random.random() < intensity:
                svc.virtual_port = random.randint(10000, 60000)
                hopped += 1

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

        # 스왑 기록
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
            to_block = random.sample(
                list(self.attacker.scanned_ips),
                min(n_block, len(self.attacker.scanned_ips))
            )
            self.blacklist.update(to_block)

        return aggression * duration * self.config.cost.blacklist * 0.5

    def _simulate_attacker(self) -> Dict[str, Any]:
        """공격자 행동 시뮬레이션"""
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
            self.attacker.scan_rate = profile["scan_rate"] * effective_rate

            # IP 스캔
            n_scan = int(self.config.search_space.ip_range * self.attacker.scan_rate)
            for _ in range(n_scan):
                ip = f"10.13.0.{random.randint(1, 254)}"
                if ip not in self.blacklist:
                    self.attacker.scanned_ips.add(ip)

            # 디코이 유인 체크
            for decoy in self.decoys.values():
                if decoy.is_active and decoy.ip in self.attacker.scanned_ips:
                    decoy_detection = profile.get("decoy_detection", 0.3)
                    if random.random() < profile["discovery_rate"] * (1.2 - decoy_detection):
                        decoy.hits += 1
                        self.stats.total_decoy_hits += 1
                        result["decoy_hit"] = True
                        self.attacker.energy -= 0.08

            # 실제 서비스 발견 시도
            for svc_name, svc in self.services.items():
                if svc.is_discovered:
                    continue

                if svc.virtual_ip in self.attacker.scanned_ips:
                    discover_prob = profile["discovery_rate"] * effective_rate
                    if random.random() < discover_prob:
                        svc.is_discovered = True
                        self.attacker.discovered_services.add(svc_name)
                        self.attacker.known_mappings[svc_name] = (svc.virtual_ip, svc.virtual_port)
                        result["discovered"] = True

            if len(self.attacker.discovered_services) >= 2:
                self.attacker.current_phase = "exploitation"

        elif self.attacker.current_phase == "exploitation":
            for svc_name in list(self.attacker.discovered_services):
                svc = self.services.get(svc_name)
                if not svc or svc.is_exploited:
                    continue

                # 매핑 정보 유효성 확인
                if svc_name in self.attacker.known_mappings:
                    known_ip, known_port = self.attacker.known_mappings[svc_name]
                    if known_ip != svc.virtual_ip or known_port != svc.virtual_port:
                        svc.is_discovered = False
                        self.attacker.discovered_services.discard(svc_name)
                        del self.attacker.known_mappings[svc_name]
                        continue

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
            exploited_critical = any(
                self.services[s].is_critical
                for s in self.attacker.exploited_services
                if s in self.services
            )

            if exploited_critical:
                result["breach"] = True

        self.attacker.energy -= 0.01
        return result

    # =========================================================================
    # 학술적 MTD 지표 계산
    # =========================================================================

    def _compute_mttc(self) -> int:
        """
        MTTC (Mean Time To Compromise)
        침투까지 걸린 시간 (step 수)
        Reference: Zhuang et al., IEEE TDSC 2014
        """
        if self.stats.breach_occurred:
            return self.step_count
        return self.max_steps

    def _compute_asr(self) -> float:
        """
        ASR (Attack Surface Reduction)
        공격 표면 감소율
        Reference: Jajodia et al., Springer 2011
        
        ASR = 1 - (exposed_services / total_potential_exposure)
        """
        total_services = len(self.services)
        discovered = len(self.attacker.discovered_services)
        exploited = len(self.attacker.exploited_services)

        # 노출된 공격 표면 계산
        exposed = discovered + exploited * 2
        max_exposure = total_services * 3

        asr = 1.0 - min(1.0, exposed / max_exposure)
        return asr

    def _compute_cdi(self) -> float:
        """
        CDI (Configuration Diversity Index)
        Shannon Entropy 기반 설정 다양성
        Reference: Evans et al., ACSAC 2011
        
        CDI = H(configs) / H_max
        H = -Σ p(x) * log2(p(x))
        """
        # 가상 설정 수집
        virtual_configs = []
        for svc in self.services.values():
            config = f"{svc.virtual_ip}:{svc.virtual_port}"
            virtual_configs.append(config)

        # 고유 설정 수
        unique_configs = len(set(virtual_configs))
        total_configs = len(virtual_configs)

        if unique_configs <= 1 or total_configs <= 1:
            return 0.0

        # Shannon Entropy 계산
        config_counts = {}
        for cfg in virtual_configs:
            config_counts[cfg] = config_counts.get(cfg, 0) + 1

        entropy = 0.0
        for count in config_counts.values():
            p = count / total_configs
            if p > 0:
                entropy -= p * np.log2(p)

        # 최대 엔트로피 (균등 분포)
        max_entropy = np.log2(total_configs)

        cdi = entropy / max_entropy if max_entropy > 0 else 0.0
        return cdi

    def _compute_ned(self) -> float:
        """
        NED (Normalized Entropy of Defense)
        방어 액션의 예측 불가능성
        Reference: Cho et al., IEEE CNS 2020
        
        방어 설정 변화량의 분산을 기반으로 계산
        """
        if len(self.diversity_history) < 2:
            return 0.0

        # 다양성 변화량
        diversity_changes = np.diff(self.diversity_history)

        if len(diversity_changes) == 0:
            return 0.0

        # 변화량의 표준편차 (높을수록 예측 불가능)
        std = np.std(diversity_changes)

        # 정규화 (0-1 범위)
        ned = min(1.0, std * 5)
        return ned

    def _compute_asp(self) -> float:
        """
        ASP (Attack Success Probability)
        공격 성공 확률
        Reference: Connell et al., IEEE S&P 2017
        
        ASP = exploited / discovered
        """
        discovered = len(self.attacker.discovered_services)

        if discovered == 0:
            return 0.0

        exploited = len(self.attacker.exploited_services)
        asp = exploited / discovered

        return asp

    def _compute_des(self) -> float:
        """
        DES (Defense Effectiveness Score)
        종합 방어 효과성 점수
        
        DES = 0.25*MTTC_norm + 0.20*ASR + 0.20*CDI + 0.15*NED + 0.10*(1-ASP) + 0.10*Redundancy
        """
        mttc = self._compute_mttc()
        mttc_norm = mttc / self.max_steps

        asr = self._compute_asr()
        cdi = self._compute_cdi()
        ned = self._compute_ned()
        asp = self._compute_asp()
        redundancy = self._get_redundancy_score()

        des = (
            0.25 * mttc_norm +
            0.20 * asr +
            0.20 * cdi +
            0.15 * ned +
            0.10 * (1.0 - asp) +
            0.10 * redundancy
        )

        return des

    def _compute_cer(self) -> float:
        """
        CER (Cost Efficiency Ratio)
        비용 대비 효과 비율
        Reference: Hong & Kim, IEEE TIFS 2016
        
        CER = DES / (Cost + epsilon)
        """
        des = self._compute_des()

        if self.stats.total_cost > 0:
            cer = des / (self.stats.total_cost + 0.1)
        else:
            cer = des

        return min(5.0, cer)  # 상한 설정

    def _get_redundancy_score(self) -> float:
        """중복성 점수 계산"""
        active_decoys = sum(1 for d in self.decoys.values() if d.is_active)
        decoy_ratio = active_decoys / len(self.decoys)

        swap_bonus = min(0.3, len(self.active_swaps) * 0.08)

        return min(1.0, decoy_ratio * 0.6 + swap_bonus + 0.1)

    # =========================================================================
    # 보상 및 상태
    # =========================================================================

    def _compute_reward(self, mtd_cost: float, attack_result: Dict) -> float:
        """보상 계산"""
        reward = 0.0
        cfg = self.config.reward

        # 1. 기본 생존 보상
        reward += cfg.survival_per_step * 1.5

        # 2. 비용 패널티 (완화)
        if mtd_cost > 0.5:
            reward -= (mtd_cost - 0.5) * cfg.cost_weight

        # 3. 공격 결과
        if attack_result["breach"]:
            reward -= cfg.breach_penalty
        elif attack_result["exploited"]:
            reward -= cfg.exploit_penalty
        elif attack_result["discovered"]:
            reward -= cfg.discovery_penalty * 0.5
        else:
            reward += 0.3

        # 4. 디코이 유인 보너스
        if attack_result["decoy_hit"]:
            reward += cfg.decoy_engagement_bonus * 2

        # 5. 다양성 보너스 (CDI 기반)
        cdi = self._compute_cdi()
        if cdi > 0.3:
            reward += cdi * cfg.diversity_bonus * 1.5

        # 6. 중복성 보너스
        redundancy = self._get_redundancy_score()
        reward += redundancy * cfg.redundancy_bonus

        # 7. 공격자 혼란 보너스
        reward += self.attacker.confusion_level * cfg.confusion_bonus * 2

        # 8. MTD 활동 보너스
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
        total_search = self.config.search_space.total_search_space
        scanned = len(self.attacker.scanned_ips) * self.config.search_space.port_range
        scanned_ratio = min(1.0, scanned / total_search)

        discovered_ratio = len(self.attacker.discovered_services) / len(self.services)

        critical_discovered = any(
            self.services[s].is_critical
            for s in self.attacker.discovered_services
            if s in self.services
        )

        exploit_progress = len(self.attacker.exploited_services) / len(self.services)

        phase_map = {"reconnaissance": 0.0, "exploitation": 0.5, "persistence": 1.0}
        compromise_progress = phase_map.get(self.attacker.current_phase, 0.0)

        diversity = self._compute_cdi()
        redundancy = self._get_redundancy_score()

        active_decoys = sum(1 for d in self.decoys.values() if d.is_active)
        total_hits = sum(d.hits for d in self.decoys.values())
        decoy_rate = total_hits / max(1, active_decoys * self.step_count) if active_decoys > 0 else 0

        energy = self.attacker.energy
        swap_active_ratio = min(1.0, len(self.active_swaps) / 3.0)
        steps_since_shuffle = min(1.0, (self.step_count - self.last_shuffle_step) / 50.0)
        steps_since_swap = min(1.0, (self.step_count - self.last_swap_step) / 50.0) if self.last_swap_step > 0 else 1.0
        scan_rate = min(1.0, self.attacker.scan_rate / 0.2)

        scaled_action = scale_action(self.last_action)

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
        """
        정보 딕셔너리 반환 - 학술적 MTD 지표 포함
        """
        # === 학술적 MTD 지표 ===
        mttc = self._compute_mttc()
        mttc_norm = mttc / self.max_steps
        asr = self._compute_asr()
        cdi = self._compute_cdi()
        ned = self._compute_ned()
        asp = self._compute_asp()
        des = self._compute_des()
        cer = self._compute_cer()

        # === 기존 메트릭 ===
        discovered_ratio = len(self.attacker.discovered_services) / len(self.services)
        exploit_ratio = len(self.attacker.exploited_services) / len(self.services)
        redundancy = self._get_redundancy_score()

        defense_success = 1.0 - (discovered_ratio * 0.3 + exploit_ratio * 0.5)
        cost_efficiency = 1.0 - min(1.0, self.stats.total_cost / 10.0)

        diversity_avg = np.mean(self.diversity_history) if self.diversity_history else cdi
        redundancy_avg = np.mean(self.redundancy_history) if self.redundancy_history else redundancy

        return {
            # === 학술적 MTD 지표 (Primary) ===
            "MTD/MTTC": mttc,
            "MTD/MTTC_Normalized": mttc_norm,
            "MTD/ASR": asr,
            "MTD/CDI": cdi,
            "MTD/NED": ned,
            "MTD/ASP": asp,
            "MTD/DES": des,
            "MTD/CER": cer,

            # === Defense 메트릭 ===
            "Defense/S_MTD": des,  # 호환성 유지 (DES로 대체)
            "Defense/Success": defense_success,
            "Defense/BreachPrevented": int(not self.stats.breach_occurred),
            "Defense/Diversity_Avg": diversity_avg,
            "Defense/Diversity_Current": cdi,
            "Defense/Redundancy_Avg": redundancy_avg,
            "Defense/Redundancy_Current": redundancy,

            # === Attack 메트릭 ===
            "Attack/ServicesFound": len(self.attacker.discovered_services),
            "Attack/ServicesExploited": len(self.attacker.exploited_services),
            "Attack/Phase": self.attacker.current_phase,
            "Attack/ConfusionLevel": self.attacker.confusion_level,
            "Attack/TimeToBreach": mttc,

            # === Cost 메트릭 ===
            "Cost/Total": self.stats.total_cost,
            "Cost/Efficiency": cost_efficiency,
            "Cost/PerStep": self.stats.total_cost / max(1, self.step_count),

            # === MTD 액션 메트릭 ===
            "MTD/ShuffleCount": self.stats.total_shuffles,
            "MTD/PortHopCount": self.stats.total_port_hops,
            "MTD/SwapCount": self.stats.total_swaps,
            "MTD/ActiveSwaps": len(self.active_swaps),

            # === Decoy 메트릭 ===
            "Decoy/Activations": self.stats.total_decoy_activations,
            "Decoy/Hits": self.stats.total_decoy_hits,
            "Decoy/ActiveCount": sum(1 for d in self.decoys.values() if d.is_active),
            "Decoy/HitRate": self.stats.total_decoy_hits / max(1, self.stats.total_decoy_activations),

            # === Episode 메트릭 ===
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
            print(f"DES (S_MTD): {info['MTD/DES']:.3f}")
            print(f"MTTC: {info['MTD/MTTC']} steps")
            print(f"ASR: {info['MTD/ASR']:.3f}")
            print(f"CDI: {info['MTD/CDI']:.3f}")
            print(f"Shuffles: {self.stats.total_shuffles}, Swaps: {self.stats.total_swaps}")
            print(f"Cost: {self.stats.total_cost:.2f}")


# =============================================================================
# Test
# =============================================================================
if __name__ == "__main__":
    print("=== MTD Environment v08.3 Test ===")
    print(f"STATE_DIM: {STATE_DIM}")
    print(f"ACTION_DIM: {ACTION_DIM}")

    env = MTDEnvironment(seeker_level=2)
    state, info = env.reset()

    print(f"\nInitial state shape: {state.shape}")
    print("\nMTD Metrics available:")
    for key in info:
        if key.startswith("MTD/"):
            print(f"  {key}: {info[key]:.4f}" if isinstance(info[key], float) else f"  {key}: {info[key]}")

    total_reward = 0
    for step in range(100):
        action = env.action_space.sample()
        state, reward, terminated, truncated, info = env.step(action)
        total_reward += reward

        if step % 25 == 0:
            print(f"\nStep {step}:")
            print(f"  Reward: {reward:.2f}")
            print(f"  DES: {info['MTD/DES']:.3f}")
            print(f"  MTTC: {info['MTD/MTTC']}")
            print(f"  ASR: {info['MTD/ASR']:.3f}")
            print(f"  CDI: {info['MTD/CDI']:.3f}")
            print(f"  NED: {info['MTD/NED']:.3f}")
            print(f"  Shuffles: {info['MTD/ShuffleCount']}")
            print(f"  Swaps: {info['MTD/SwapCount']}")

        if terminated or truncated:
            break

    print(f"\n=== Episode Complete ===")
    print(f"Total reward: {total_reward:.2f}")
    print(f"Final DES: {info['MTD/DES']:.3f}")
    print(f"Breach Prevented: {bool(info['Defense/BreachPrevented'])}")
