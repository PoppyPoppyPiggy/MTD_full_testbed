# File: MTD_full_testbed/dvd_lite/dvd_attacks_lpc/mtd/rl_environment_v04.py
#
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[신규 4/8] MTD_RL v04 - 하이브리드 시뮬레이션 환경 (Continuous)

- '전략가(RL)'의 6D 연속 행동(Action)이 '전술가(CTI)'와 환경에 영향을 미칩니다.
"""

import numpy as np
import random
from collections import deque
from typing import Dict, Any, Tuple, List

# 학습/배포 "계약" 임포트
from mtd.rl_config import (
    FEATURE_KEYS, OBS_DIM, 
    ACTION_PARAM_KEYS, ACTION_DIM,
    REAL_TARGETS, DECOY_TARGETS, ALTERNATE_NODE_TARGETS
)

# --- v03 (이산적) 시뮬레이터 로직 상속 (수정용) ---
class SimulatedCTIAgent:
    """ [v04] set_policy_parameters로 파라미터를 직접 받음 """
    def __init__(self):
        self.blacklist = {} # {ip: banned_until_step}
        self.alert_rate_window = deque(maxlen=50)
        self.detection_threshold = 0.5
        self.ban_duration_sec = -1

    def set_policy_parameters(self, aggression: float, duration: float):
        # (0.0=느슨 -> 0.7) ~ (1.0=공격적 -> 0.1)
        self.detection_threshold = np.clip(0.7 - (aggression * 0.6), 0.1, 0.7)
        # (0.0=Timer -> 300s) ~ (1.0=Aggressive -> -1s)
        self.ban_duration_sec = int(np.clip(300 - (duration * 301), -1, 300))
        if self.ban_duration_sec > 290: self.ban_duration_sec = -1

    def process_traffic(self, seeker_ip: str, is_suspicious: bool, current_step: int) -> Tuple[str, float]:
        for ip in list(self.blacklist.keys()):
            if self.blacklist[ip] != -1 and self.blacklist[ip] < current_step:
                del self.blacklist[ip]
        if seeker_ip in self.blacklist:
            self.alert_rate_window.append(0.0)
            return "blocked", 0.0
        if is_suspicious and random.random() < self.detection_threshold:
            self.alert_rate_window.append(1.0)
            ban_steps = self.ban_duration_sec if self.ban_duration_sec != -1 else 99999
            self.blacklist[seeker_ip] = current_step + ban_steps
            return "blocked", 1.0
        self.alert_rate_window.append(0.0)
        return "allowed", 0.0
        
    def get_metrics(self) -> Dict[str, float]:
        return {
            "cti_alert_rate": np.mean(self.alert_rate_window) if self.alert_rate_window else 0.0,
            "blacklist_size": float(len(self.blacklist)),
        }

class SimulatedHeuristicSeeker:
    """ (v03 코드와 동일) """
    def __init__(self, level: int):
        params = {
            0: (0.1, 0.1, 0.05), 1: (0.3, 0.2, 0.1), 2: (0.5, 0.5, 0.2),
            3: (0.7, 0.7, 0.3), 4: (0.6, 0.9, 0.5)
        }
        self.scan_effort, self.attack_effort, self.ip_change_prob = params[level]
        self.current_ip = f"100.10.1.{random.randint(1, 10)}"
        self.ip_change_rate_window = deque(maxlen=50)

    def act(self, cti_agent: SimulatedCTIAgent, current_step: int) -> Tuple[str, bool]:
        if random.random() < self.ip_change_prob:
            self.current_ip = f"100.10.1.{random.randint(1, 10)}"
            self.ip_change_rate_window.append(1.0)
        else:
            self.ip_change_rate_window.append(0.0)
        status, _ = cti_agent.process_traffic(self.current_ip, False, current_step)
        if status == "blocked": return "pass_blocked", False
        if random.random() < self.attack_effort: return "exploit", True
        elif random.random() < self.scan_effort: return "scan", (random.random() < 0.2)
        return "pass", False
        
    def get_metrics(self) -> Dict[str, float]:
        return {
            "seeker_ip_change_rate": np.mean(self.ip_change_rate_window) if self.ip_change_rate_window else 0.0,
        }

class NetworkEnv:
    """
    MTD RL 학습을 위한 하이브리드 시뮬레이션 환경 (ver_04 - Continuous)
    """
    def __init__(self, cfg):
        self.obs_dim = OBS_DIM
        self.act_dim = ACTION_DIM
        self.cfg = cfg
        
        self.seeker = SimulatedHeuristicSeeker(cfg.seeker_level)
        self.cti_agent = SimulatedCTIAgent()
        
        self.state_history = []
        self.current_step = 0
        self.metrics = {}
        
        # [v04] 현재 적용된 6D 액션 파라미터 (상태 피드백용)
        # (0.0~1.0 사이로 정규화된 값)
        self.current_action_params = np.zeros(ACTION_DIM, dtype=np.float32)
        
        self.current_dnat_target_type = "REAL" # REAL, DECOY, ALTERNATE
        self.alternate_node_health = 1.0
        
        self.breach_window = deque(maxlen=50)
        self.decoy_lure_window = deque(maxlen=50)
        self.uptime_window = deque(maxlen=50)
        self.time_metrics = {"find": [], "breach": []}
        
        print(f"[NetworkEnv v04] 초기화. State: {self.obs_dim}D, Action: {self.act_dim}D (Continuous)")

    def reset(self) -> np.ndarray:
        self.current_step = 0
        self.cti_agent = SimulatedCTIAgent()
        self.seeker = SimulatedHeuristicSeeker(self.cfg.seeker_level)
        
        # [v04] 6D 액션 파라미터 초기화
        self.current_action_params = np.zeros(ACTION_DIM, dtype=np.float32)
        self.current_action_params[0] = 1.0 # dnat_real_focus_prob = 1.0 (기본값)
        
        self.current_dnat_target_type = "REAL"
        self.alternate_node_health = 1.0
        
        self.metrics = {}
        self.breach_window.clear(); self.decoy_lure_window.clear(); self.uptime_window.clear()
        self.time_metrics = {"find": [], "breach": []}
        
        for _ in range(50): 
            self.breach_window.append(0)
            self.decoy_lure_window.append(0)
            self.uptime_window.append(1.0)

        return self._get_state()

    def _apply_mtd_strategy(self, action_vector: np.ndarray):
        """ 
        [v04 핵심] 6D 연속 파라미터(Actor 출력: -1.0~1.0)를 환경에 적용
        """
        
        # 1. PPO Actor 출력(-1.0 ~ 1.0) -> (0.0 ~ 1.0) 범위로 스케일링
        action_params = (action_vector + 1.0) / 2.0
        self.current_action_params = action_params # 상태 피드백을 위해 저장
        
        cost = 0.05 # 기본 유지 비용

        # 2. DNAT 전략 적용 (파라미터 0, 1, 2)
        dnat_logits = action_vector[0:3] # [-1, 1] 스케일의 값을 logit으로 사용
        dnat_probs = np.exp(dnat_logits) / np.sum(np.exp(dnat_logits)) # Softmax
        
        # [랜덤성/시드 기반] 확률분포에 따라 DNAT 타겟 타입을 *선택*
        self.current_dnat_target_type = np.random.choice(
            ["REAL", "DECOY", "ALTERNATE"], 
            p=dnat_probs
        )
        
        if self.current_dnat_target_type == "DECOY":
            cost += 0.3
        elif self.current_dnat_target_type == "ALTERNATE":
            cost += 0.2
            # 대체 노드 품질 저하 (랜덤)
            self.alternate_node_health = 1.0 if random.random() < 0.5 else 0.2
        else: # REAL
            cost += 0.1
            self.alternate_node_health = 1.0

        # 3. 셔플 전략 적용 (파라미터 3)
        shuffle_intensity = action_params[3]
        if shuffle_intensity > 0.75: # 임계값 0.75 초과 시 셔플 실행
            cost += 5.0 # 매우 비싼 행동
            self.uptime_window.append(0.1) # 셔플 중 서비스 다운타임
        else:
            self.uptime_window.append(1.0)
            
        # 4. CTI 정책 적용 (파라미터 4, 5)
        bl_aggression = action_params[4]
        bl_duration = action_params[5]
        self.cti_agent.set_policy_parameters(bl_aggression, bl_duration)
        cost += (bl_aggression + bl_duration) * 0.1 # CTI 정책 유지 비용

        self.metrics["system_cost"] = cost

    def _run_seeker_turn(self):
        """ 1 스텝(분) 동안 Seeker와 CTI가 상호작용 (v03와 동일) """
        
        action_type, is_suspicious = self.seeker.act(self.cti_agent, self.current_step)
        if action_type == "pass_blocked":
            self.breach_window.append(0); self.decoy_lure_window.append(0),
            return

        status, _ = self.cti_agent.process_traffic(
            self.seeker.current_ip, is_suspicious, self.current_step
        )
        if status == "blocked":
            self.breach_window.append(0); self.decoy_lure_window.append(0)
            return
            
        is_breach = False
        is_lured = False
        
        if action_type == "exploit":
            if self.current_dnat_target_type == "DECOY":
                is_lured = True
            elif self.current_dnat_target_type == "ALTERNATE":
                is_breach = (random.random() > self.alternate_node_health)
            else: # REAL
                is_breach = True # CTI 뚫림
                
        elif action_type == "scan":
            if self.current_dnat_target_type == "DECOY":
                is_lured = True
            
        self.breach_window.append(1 if is_breach else 0)
        self.decoy_lure_window.append(1 if is_lured else 0)
        
        if is_breach and not self.time_metrics["breach"]:
            self.time_metrics["breach"].append(self.current_step)
        if action_type == "scan" and not is_lured and not self.time_metrics["find"]:
            self.time_metrics["find"].append(self.current_step)

    def _update_metrics(self):
        """ 내부 상태 변수 -> 10D 메트릭으로 변환 """
        m = self.metrics
        
        m.update(self.cti_agent.get_metrics())
        m.update(self.seeker.get_metrics())
        
        m["breach_success_rate"] = np.mean(self.breach_window) if self.breach_window else 0.0
        m["decoy_lure_rate"] = np.mean(self.decoy_lure_window) if self.decoy_lure_window else 0.0
        m["alternate_node_health"] = self.alternate_node_health
        m["service_uptime_ratio"] = np.mean(self.uptime_window) if self.uptime_window else 0.0
        m["attack_orchestrator_running"] = 1.0
        
        # m["system_cost"] (이미 계산됨)
        
        m["ttbr"] = np.mean(self.time_metrics["breach"]) if self.time_metrics["breach"] else self.cfg.max_episode_steps
        # (v04에서는 ttf는 단순화)
        m["ttf"] = m["ttbr"] 

    def _get_state(self) -> np.ndarray:
        """ [v04 핵심] 10D 메트릭 + 6D 이전 행동 = 16D 상태 벡터 생성 """
        self._update_metrics()
        
        metric_vec_list = []
        for key in METRIC_FEATURE_KEYS: # 10D 메트릭
            metric_vec_list.append(self.metrics.get(key, 0.0))
            
        # [v04] 10D 메트릭 + 6D 이전 행동 파라미터 (0.0~1.0)
        state_vec = np.concatenate([
            np.array(metric_vec_list, dtype=np.float32),
            self.current_action_params 
        ])
        
        self.state_history.append(state_vec)
        return state_vec

    def _calculate_reward(self) -> float:
        """ [v04] MTD 스코어링 지표 기반 보상 함수 (v03와 동일) """
        m = self.metrics
        
        reward = 0.0
        reward += (1.0 - m["breach_success_rate"]) * 10.0 # 침투 방지
        reward += m["decoy_lure_rate"] * 3.0             # 디코이 유인
        reward += m["service_uptime_ratio"] * 2.0        # 서비스 품질
        reward -= m["system_cost"] * 0.5                 # 비용
        if self.current_dnat_target_type == "ALTERNATE" and m["alternate_node_health"] < 0.5:
            reward -= 5.0 # 나쁜 대체 노드 선택 페널티
        reward -= (m["blacklist_size"] / 100.0) * 1.0    # DoS 방지
            
        return reward

    def step(self, action_vector: np.ndarray) -> Tuple[np.ndarray, float, bool, dict]:
        """
        환경 스텝 실행
        :param action_vector: (6,) 크기의 PPO Actor 출력 (범위: -1.0 ~ 1.0)
        """
        self.current_step += 1
        
        # 1. '전략가(RL)'의 6D 연속 파라미터 적용
        self._apply_mtd_strategy(action_vector)
        
        # 2. '전술가(CTI)'와 '적(Seeker)'의 상호작용
        self._run_seeker_turn()
        
        # 3. 상태/보상/종료 계산
        next_state = self._get_state()
        reward = self._calculate_reward()
        done = self.current_step >= self.cfg.max_episode_steps
        
        # 4. Info (wandb 로깅용)
        info = {f"Metrics/{k}": v for k, v in self.metrics.items()}
        # (v04) 현재 적용된 6D 파라미터(0.0~1.0)도 로깅
        for i, key in enumerate(ACTION_PARAM_KEYS):
            info[f"Params/{key}"] = self.current_action_params[i]
        
        return next_state, reward, done, info

    def get_state_history(self) -> np.ndarray:
        return np.array(self.state_history, dtype=np.float32)