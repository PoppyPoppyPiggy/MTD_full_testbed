# File: MTD_full_testbed/dvd_lite/dvd_attacks_lpc/mtd/rl_environment_v05.py
#
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[신규 4/11] MTD_RL v05 - 하이브리드 시뮬레이션 환경 (Task #4: Sim-to-Real)

- [v04 대비 변경점]
- `v05` 계약 파일(rl_config_v05.py)을 임포트합니다.
- `ml/cti_agent.py`가 수동 센서임을 반영하여, RL 에이전트의
  `blacklist_threshold`, `blacklist_duration` 파라미터로
  `SimulatedBlacklister`라는 모듈을 내부적으로 제어합니다.
"""

import numpy as np
import random
from collections import deque
from typing import Dict, Any, Tuple, List

# [v05] 계약 임포트
from mtd.rl_config_v05 import (
    FEATURE_KEYS, OBS_DIM, 
    ACTION_PARAM_KEYS, ACTION_DIM,
    METRIC_FEATURE_KEYS
)

# --- [v05] 시뮬레이션 모듈 ---

class SimulatedPassiveCTI:
    """ 
    [v05] 시뮬레이션된 '수동 센서' (ml/cti_agent.py 모방)
    - 제어 불가. 오직 `cti_alert_rate`만 출력.
    """
    def __init__(self):
        self.alert_rate_window = deque(maxlen=50)
        # [!] ml/cti_agent.py의 CONFIDENCE_THRESHOLD(0.7)와 유사하게 설정
        self.detection_threshold = 0.5 

    def process_traffic(self, is_suspicious: bool) -> float:
        """ 
        트래픽을 보고 경보만 울림 (차단 X)
        :return: (float) 0.0 (탐지실패) 또는 0.1~1.0 (탐지성공/신뢰도)
        """
        if is_suspicious and random.random() < self.detection_threshold:
            alert_score = random.uniform(0.5, 1.0) # 0.7이 아닌 0.5부터
            self.alert_rate_window.append(alert_score)
            return alert_score
        else:
            self.alert_rate_window.append(0.0) # 탐지 못함
            return 0.0
            
    def get_metrics(self) -> Dict[str, float]:
        return {
            # [v05] CTI Alert Rate = (경보 점수 합) / (윈도우 크기)
            "cti_alert_rate": np.sum(self.alert_rate_window) / len(self.alert_rate_window) if self.alert_rate_window else 0.0,
        }

class SimulatedBlacklister:
    """
    [v05] 시뮬레이션된 '블랙리스트 실행기' (IptablesController 모방)
    - '전략가(RL)'의 파라미터로 제어됨
    """
    def __init__(self):
        self.blacklist = {} # {ip: banned_until_step}
        self.threshold = 1.0 # (1.0 = 차단 안함)
        self.duration_steps = 10 # (10 스텝)
        
    def set_policy_parameters(self, threshold_param: float, duration_param: float):
        """ RL의 파라미터(0.0~1.0)를 받아 정책 갱신 """
        # (0.0=공격적 -> 0.1) ~ (1.0=느슨 -> 1.0)
        self.threshold = np.clip(0.1 + (threshold_param * 0.9), 0.1, 1.0)
        # (0.0=Timer -> 10스텝) ~ (1.0=Aggressive -> 99999스텝)
        self.duration_steps = int(np.clip(10 + (duration_param * 99989), 10, 99999))
        if duration_param > 0.95: self.duration_steps = 99999 # 영구

    def process_alert(self, seeker_ip: str, cti_alert_score: float, current_step: int) -> str:
        """ CTI 경보를 받아 차단 여부 결정 """
        # 1. 만료 처리
        for ip in list(self.blacklist.keys()):
            if self.blacklist[ip] < current_step:
                del self.blacklist[ip]
        
        # 2. 이미 차단됨
        if seeker_ip in self.blacklist:
            return "blocked"
            
        # 3. RL 임계값 기반 신규 차단
        if cti_alert_score > self.threshold:
            self.blacklist[seeker_ip] = current_step + self.duration_steps
            return "blocked"
            
        return "allowed"
        
    def get_metrics(self) -> Dict[str, float]:
        return {
             "blacklist_size": float(len(self.blacklist)),
        }

class SimulatedHeuristicSeeker:
    """ [v05] (Sim-to-Real 튜닝 포인트) """
    def __init__(self, level: int):
        # (scan_effort, attack_effort, ip_change_prob)
        params = {
            0: (0.1, 0.1, 0.05), # L0: 거의 활동 안함
            1: (0.3, 0.2, 0.1),  # L1: 스캔 위주
            2: (0.5, 0.5, 0.2),  # L2: 균형
            3: (0.7, 0.7, 0.3),  # L3: 공격적
            4: (0.6, 0.9, 0.5)   # L4: 침투 집중, IP 자주 변경
        }
        self.scan_effort, self.attack_effort, self.ip_change_prob = params[level]
        self.current_ip = f"100.10.1.{random.randint(1, 10)}"
        self.ip_change_rate_window = deque(maxlen=50)

    def act(self, current_step: int) -> Tuple[str, bool, str]:
        """ (action_type, is_suspicious, ip) 반환 """
        
        changed_ip = False
        if random.random() < self.ip_change_prob:
            self.current_ip = f"100.10.1.{random.randint(1, 10)}"
            changed_ip = True
            
        self.ip_change_rate_window.append(1.0 if changed_ip else 0.0)
            
        if random.random() < self.attack_effort:
            # Exploit은 항상 '의심스러운' 트래픽
            return "exploit", True, self.current_ip
        elif random.random() < self.scan_effort:
            # Scan은 20%만 '의심스러운' 트래픽 (CTI가 탐지하기 어렵게)
            return "scan", (random.random() < 0.2), self.current_ip
        
        return "pass", False, self.current_ip
        
    def get_metrics(self) -> Dict[str, float]:
        return {
            "seeker_ip_change_rate": np.mean(self.ip_change_rate_window) if self.ip_change_rate_window else 0.0,
        }

class NetworkEnv:
    """ v05 시뮬레이션 환경 (Continuous) """
    def __init__(self, cfg):
        self.obs_dim = OBS_DIM
        self.act_dim = ACTION_DIM
        self.cfg = cfg
        
        self.seeker = SimulatedHeuristicSeeker(cfg.seeker_level)
        self.passive_cti = SimulatedPassiveCTI()
        self.blacklister = SimulatedBlacklister()
        
        self.state_history = []
        self.current_step = 0
        self.metrics = {}
        self.current_action_params = np.zeros(ACTION_DIM, dtype=np.float32)
        
        self.current_dnat_target_type = "REAL"
        self.alternate_node_health = 1.0
        
        self.breach_window = deque(maxlen=50)
        self.decoy_lure_window = deque(maxlen=50)
        self.uptime_window = deque(maxlen=50)
        self.time_metrics = {"find": [], "breach": []}
        
        print(f"[NetworkEnv v05] 초기화. State: {self.obs_dim}D, Action: {self.act_dim}D (Continuous)")

    def reset(self) -> np.ndarray:
        self.current_step = 0
        self.seeker = SimulatedHeuristicSeeker(self.cfg.seeker_level)
        self.passive_cti = SimulatedPassiveCTI()
        self.blacklister = SimulatedBlacklister()
        
        self.current_action_params = np.zeros(ACTION_DIM, dtype=np.float32)
        self.current_action_params[0] = 1.0 # dnat_real_logit = 1.0 (기본값)
        
        self.current_dnat_target_type = "REAL"
        self.alternate_node_health = 1.0
        
        self.metrics = {}
        self.breach_window.clear(); self.decoy_lure_window.clear(); self.uptime_window.clear()
        self.time_metrics = {"find": [], "breach": []}
        
        for _ in range(50): 
            self.breach_window.append(0); self.decoy_lure_window.append(0); self.uptime_window.append(1.0)

        return self._get_state()

    def _apply_mtd_strategy(self, action_vector: np.ndarray):
        """ [v05] 6D 연속 파라미터(Actor 출력: -1.0~1.0)를 환경에 적용 """
        
        action_params = (action_vector + 1.0) / 2.0 # (0.0 ~ 1.0) 스케일링
        self.current_action_params = action_params 
        
        cost = 0.05
        
        # 1. DNAT 전략 (파라미터 0, 1, 2)
        dnat_logits = action_vector[0:3]
        dnat_probs = np.exp(dnat_logits) / np.sum(np.exp(dnat_logits))
        self.current_dnat_target_type = np.random.choice(["REAL", "DECOY", "ALTERNATE"], p=dnat_probs)
        
        if self.current_dnat_target_type == "DECOY": cost += 0.3
        elif self.current_dnat_target_type == "ALTERNATE":
            cost += 0.2
            self.alternate_node_health = 1.0 if random.random() < 0.5 else 0.2
        else: # REAL
            cost += 0.1
            self.alternate_node_health = 1.0

        # 2. 셔플 전략 (파라미터 3)
        shuffle_intensity = action_params[3]
        if shuffle_intensity > 0.75:
            cost += 5.0
            self.uptime_window.append(0.1)
        else:
            self.uptime_window.append(1.0)
            
        # 3. [v05] 블랙리스트 "실행기" 정책 적용 (파라미터 4, 5)
        bl_threshold = action_params[4]
        bl_duration = action_params[5]
        self.blacklister.set_policy_parameters(bl_threshold, bl_duration)
        cost += (bl_threshold + bl_duration) * 0.1 # BL 정책 유지 비용

        self.metrics["system_cost"] = cost

    def _run_seeker_turn(self):
        """ [v05] Seeker -> CTI (센서) -> Blacklister (실행기) 상호작용 """
        
        action_type, is_suspicious, seeker_ip = self.seeker.act(self.current_step)
        
        # 1. (수동 센서) CTI가 경보만 울림
        cti_alert_score = self.passive_cti.process_traffic(is_suspicious)

        # 2. (RL 실행기) Blacklister가 CTI 경보를 보고 차단 결정
        status = self.blacklister.process_alert(
            seeker_ip, 
            cti_alert_score, 
            self.current_step
        )
        
        if status == "blocked":
            self.breach_window.append(0); self.decoy_lure_window.append(0)
            return
            
        # 3. 차단 안된 트래픽이 MTD 전략에 의해 처리됨
        is_breach, is_lured = False, False
        if action_type == "exploit":
            if self.current_dnat_target_type == "DECOY": is_lured = True
            elif self.current_dnat_target_type == "ALTERNATE":
                is_breach = (random.random() > self.alternate_node_health)
            else: is_breach = True
        elif action_type == "scan":
            if self.current_dnat_target_type == "DECOY": is_lured = True
            
        self.breach_window.append(1 if is_breach else 0)
        self.decoy_lure_window.append(1 if is_lured else 0)
        
        if is_breach and not self.time_metrics["breach"]:
            self.time_metrics["breach"].append(self.current_step)
        if action_type == "scan" and not is_lured and not self.time_metrics["find"]:
            self.time_metrics["find"].append(self.current_step)

    def _update_metrics(self):
        """ [v05] 10D 메트릭으로 변환 """
        m = self.metrics
        
        m.update(self.passive_cti.get_metrics()) # cti_alert_rate
        m.update(self.seeker.get_metrics())      # seeker_ip_change_rate
        m.update(self.blacklister.get_metrics()) # blacklist_size
        
        # Scorer
        m["breach_success_rate"] = np.mean(self.breach_window) if self.breach_window else 0.0
        m["decoy_lure_rate"] = np.mean(self.decoy_lure_window) if self.decoy_lure_window else 0.0
        m["alternate_node_health"] = self.alternate_node_health
        m["service_uptime_ratio"] = np.mean(self.uptime_window) if self.uptime_window else 0.0
        m["attack_orchestrator_running"] = 1.0
        # m["system_cost"] (이미 계산됨)
        m["ttbr"] = np.mean(self.time_metrics["breach"]) if self.time_metrics["breach"] else self.cfg.max_episode_steps
        
    def _get_state(self) -> np.ndarray:
        """ [v05] 10D 메트릭 + 6D 이전 행동 = 16D 상태 벡터 생성 """
        self._update_metrics()
        
        metric_vec_list = []
        for key in METRIC_FEATURE_KEYS:
            metric_vec_list.append(self.metrics.get(key, 0.0))
            
        state_vec = np.concatenate([
            np.array(metric_vec_list, dtype=np.float32),
            self.current_action_params 
        ])
        
        self.state_history.append(state_vec)
        return state_vec

    def _calculate_reward(self) -> float:
        """ [v05] 보상 함수 (v04와 동일) """
        m = self.metrics
        reward = 0.0
        reward += (1.0 - m["breach_success_rate"]) * 10.0
        reward += m["decoy_lure_rate"] * 3.0
        reward += m["service_uptime_ratio"] * 2.0
        reward -= m["system_cost"] * 0.5
        if self.current_dnat_target_type == "ALTERNATE" and m["alternate_node_health"] < 0.5:
            reward -= 5.0
        reward -= (m["blacklist_size"] / 100.0) * 1.0
        return reward

    def step(self, action_vector: np.ndarray) -> Tuple[np.ndarray, float, bool, dict]:
        """ (6D,) Actor 출력(-1.0~1.0)을 받아 스텝 실행 """
        self.current_step += 1
        
        self._apply_mtd_strategy(action_vector)
        self._run_seeker_turn()
        
        next_state = self._get_state()
        reward = self._calculate_reward()
        done = self.current_step >= self.cfg.max_episode_steps
        
        info = {f"Metrics/{k}": v for k, v in self.metrics.items()}
        for i, key in enumerate(ACTION_PARAM_KEYS):
            info[f"Params/{key}"] = self.current_action_params[i]
        
        return next_state, reward, done, info

    def get_state_history(self) -> np.ndarray:
        return np.array(self.state_history, dtype=np.float32)