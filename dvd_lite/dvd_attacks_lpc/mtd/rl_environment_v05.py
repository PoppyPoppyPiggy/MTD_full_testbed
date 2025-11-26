import gym
from gym import spaces
import numpy as np
import random
import logging
import json
import os
import subprocess
import time
from collections import deque

# [FIX] rl_config_v05에서 필요한 상수들 가져오기
from .rl_config_v05 import (
    RL_CONFIG,
    FEATURE_KEYS,
    ACTION_PARAM_KEYS,
    ACT_THRESHOLDS, # [NEW] 복합 행동 임계값
    COST_MTD_ACTION,
    COST_SHUFFLE,
    COST_DECOY,
    COST_BL,
    COST_WEIGHT,
    REWARD_ATTACK_BLOCKED,
    REWARD_ATTACK_SUCCESS,
    REWARD_MTD_COST,
    REWARD_NORMAL,
    MTD_STATE_PATH
)

logger = logging.getLogger("RLEnv")

# -------------------------
# Utils
# -------------------------
def _scale_action(action, lower_bound=0.0, upper_bound=1.0):
    return lower_bound + (0.5 * (action + 1.0) * (upper_bound - lower_bound))

def _safe_divide(numerator, denominator):
    return numerator / denominator if denominator != 0 else 0.0

# -------------------------
# Endpoint Class
# -------------------------
class Endpoint:
    def __init__(self, ip, name="Unknown", is_decoy=False):
        self.ip = ip
        self.name = name
        self.is_decoy = is_decoy
        self.scan_progress = 0.0
        self.exploit_progress = 0.0
        self.breach_progress = 0.0
        self.state = 0 # 0: Safe, 1: Scanned, 2: Exploited, 3: Breached

    def reset_progress(self):
        self.scan_progress = 0.0
        self.exploit_progress = 0.0
        self.breach_progress = 0.0
        self.state = 0

# -------------------------
# Simulated Components
# -------------------------
class HybridCTI:
    """
    CTI Agent: 실제 mtd_state.json과 시뮬레이션 데이터를 혼합하여 위협 수준 판단
    """
    def __init__(self, rng):
        self.rng = rng
        self.alert_history = deque([0] * 100, maxlen=100)

    def get_real_state(self):
        if os.path.exists(MTD_STATE_PATH):
            try:
                with open(MTD_STATE_PATH, 'r') as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def process_traffic(self, is_suspicious_sim):
        # 1. 실제 상태 확인
        real_state = self.get_real_state()
        real_alert = real_state.get("attack_detected", False)
        real_score = real_state.get("risk_score", 0.0)

        # 2. 시뮬레이션 값 (Fallback)
        if is_suspicious_sim:
            sim_score = self.rng.normal(loc=0.8, scale=0.1)
        else:
            sim_score = self.rng.normal(loc=0.1, scale=0.1)
        
        # 3. 병합 (실제 탐지가 우선)
        if real_alert:
            final_score = max(real_score, sim_score)
            is_alert = True
        else:
            final_score = float(np.clip(sim_score, 0.0, 1.0))
            is_alert = final_score >= 0.5

        self.alert_history.append(1 if is_alert else 0)
        return final_score, is_alert

    def get_alert_rate(self):
        if not self.alert_history: return 0.0
        return sum(self.alert_history) / self.alert_history.maxlen

class SimulatedBlacklister:
    """
    Blacklister: CTI 점수에 따라 IP 차단 수행
    """
    def __init__(self, rng):
        self.rng = rng
        self.blacklist_policy = {"aggression": 0.0, "duration": 0}
        self.blocked_ips = {}

    def update_policy(self, aggression, duration):
        self.blacklist_policy["aggression"] = float(np.clip(aggression, 0.0, 1.0))
        self.blacklist_policy["duration"] = int(duration * 1000)

    def apply_block(self, ip, cti_score):
        # CTI 점수가 방어자의 민감도 설정보다 높으면 차단
        # aggression이 높을수록(1.0) 작은 점수에도 차단 (threshold가 낮아짐)
        threshold = 1.0 - self.blacklist_policy["aggression"]
        if cti_score >= threshold:
            self.blocked_ips[ip] = self.blacklist_policy["duration"]
            return True
        return False

    def is_blocked(self, ip):
        return ip in self.blocked_ips

    def step(self):
        for ip in list(self.blocked_ips.keys()):
            self.blocked_ips[ip] -= 1
            if self.blocked_ips[ip] <= 0:
                del self.blocked_ips[ip]

    def get_size_ratio(self, total):
        return min(1.0, len(self.blocked_ips) / max(1, total))

class SimulatedHeuristicSeeker:
    """
    [IMPROVEMENT] Realistic Seeker (공격자)
    - 방어자의 상태(bl_level 등)를 알지 못함.
    - 오직 자신의 의도(Intent)와 진행 상황(Progress)만 관리.
    - 외부 환경(Environment)이 성공/실패 여부를 결정하여 알려줌.
    """
    def __init__(self, rng, level, endpoints):
        self.rng = rng
        self.endpoints = endpoints
        self.current_target = self.rng.choice(endpoints)
        
        # Seeker Level에 따른 파라미터 설정 (스캔 노력, 공격 속도, IP 변경 확률)
        # Level 0~4 mapping
        params = {
            0: (0.1, 0.1, 0.05),
            1: (0.3, 0.2, 0.1),
            2: (0.5, 0.5, 0.2),
            3: (0.7, 0.7, 0.3),
            4: (0.9, 0.9, 0.5)
        }
        p = params.get(level, params[2])
        self.scan_effort = p[0]
        self.attack_speed = p[1]
        self.ip_change_prob = p[2]
        
        self.seeker_ip = "192.168.1.100" # 초기 공격자 IP
        self.seeker_params = (self.scan_effort, 0.5) # (scan, bias)

    def step(self, is_mtd_shuffle):
        """
        Seeker의 한 스텝 행동 결정.
        결과값은 Seeker의 '의도'일 뿐이며, 실제 성공 여부는 Env에서 판정함.
        """
        # 1. MTD Shuffle 발생 시: 연결 끊김, 재설정 필요
        if is_mtd_shuffle:
            for ep in self.endpoints:
                ep.reset_progress()
            self.current_target = self.rng.choice(self.endpoints)
            
            # [CRITICAL FIX] 셔플 상황에서도 모든 키를 반환해야 KeyError 방지
            return {
                "seeker_ip": self.seeker_ip,
                "is_scan": True, # 재탐색 중
                "intent": "reorient",
                "target_ep": None,
                "is_exploit_attempt": False, 
                "is_breach_attempt": False
            }

        t = self.current_target
        intent = "scan"
        
        # 2. 공격 진행 (Intent 생성)
        # 공격 속도만큼 진행도 증가
        t.exploit_progress += self.attack_speed
        
        is_exploit_attempt = False
        is_breach_attempt = False
        
        if t.exploit_progress >= 1.0:
            intent = "exploit"
            is_exploit_attempt = True
            
        if t.breach_progress >= 1.0:
            intent = "breach"
            is_breach_attempt = True
        
        return {
            "seeker_ip": self.seeker_ip,
            "is_scan": True,
            "intent": intent,
            "target_ep": t,
            "is_exploit_attempt": is_exploit_attempt,
            "is_breach_attempt": is_breach_attempt
        }

    def handle_outcome(self, outcome):
        """
        환경으로부터 행동의 결과를 피드백 받음.
        """
        t = self.current_target
        if outcome == "blocked":
            # 차단당함: 진행도 후퇴 또는 IP 변경 시도
            t.exploit_progress = max(0.0, t.exploit_progress - 0.5)
            t.breach_progress = max(0.0, t.breach_progress - 0.5)
            
            # 고난도 Seeker는 IP 변경 시도 (회피)
            if self.rng.random() < self.ip_change_prob:
                self.seeker_ip = f"192.168.1.{self.rng.integers(101, 200)}"
                
        elif outcome == "exploit_success":
            t.breach_progress += self.attack_speed # 침투 단계로 이동
        elif outcome == "breach_success":
            t.state = 3 # 장악 완료

# -------------------------
# MTD Environment (Main)
# -------------------------
class MTDEnvironment(gym.Env):
    metadata = {"render_modes": ["human"], "render_fps": 4}
    max_episode_steps = 200

    def __init__(self, seed=None, seeker_level=2, log_dir=None):
        super().__init__()
        self.rng = np.random.default_rng(seed)
        self.seeker_level = seeker_level
        self.current_step = 0

        self.endpoints = self._load_endpoints_from_config()
        self.decoy_ips = [ep.ip for ep in self.endpoints if ep.is_decoy]
        self.target_ips = [ep.ip for ep in self.endpoints if not ep.is_decoy]

        self.cti = HybridCTI(self.rng)
        self.blacklister = SimulatedBlacklister(self.rng)
        self.seeker = SimulatedHeuristicSeeker(self.rng, seeker_level, self.endpoints)

        # Action Space: 6개의 연속 파라미터
        self.action_space = spaces.Box(low=-1.0, high=1.0, shape=(len(ACTION_PARAM_KEYS),), dtype=np.float32)
        # Observation Space: 16개의 특징 벡터
        self.observation_space = spaces.Box(low=-100.0, high=100.0, shape=(len(FEATURE_KEYS),), dtype=np.float32)

        self._reset_counters()

    def _load_endpoints_from_config(self):
        endpoints = []
        try:
            config_path = os.path.join(RL_CONFIG.BASE_DIR, "config", "attacker_config.json")
            if os.path.exists(config_path):
                with open(config_path, "r") as f:
                    config = json.load(f)
                    for name, ip in config.get("targets", {}).items():
                        is_decoy = "DECOY" in name.upper()
                        endpoints.append(Endpoint(ip, name, is_decoy))
        except Exception:
            pass
        
        if not endpoints: # Fallback
            for i in range(5): endpoints.append(Endpoint(f"10.13.0.{10+i}", f"Target_{i}", False))
            for i in range(2): endpoints.append(Endpoint(f"10.13.0.{20+i}", f"Decoy_{i}", True))
        return endpoints

    def _reset_counters(self):
        self.ep_total_steps = 0
        self.ep_total_cost = 0.0
        self.ep_shuffle_count = 0
        self.ep_uptime_steps = 0
        self.ep_breach_success = 0
        self.ep_breach_attempts = 0
        self.ep_breach_block = 0
        self.ep_decoy_hits = 0
        self.ep_exploit_attempts = 0
        self.last_actions = {key: 0.5 for key in ACTION_PARAM_KEYS}

    def reset(self, seed=None, options=None):
        if seed is not None:
            self.rng = np.random.default_rng(seed)
            super().reset(seed=seed)
        
        for ep in self.endpoints: ep.reset_progress()
        self.current_step = 0
        self._reset_counters()
        self.cti = HybridCTI(self.rng)
        self.blacklister = SimulatedBlacklister(self.rng)
        self.seeker = SimulatedHeuristicSeeker(self.rng, self.seeker_level, self.endpoints)
        
        return self._get_state(), self._get_current_metrics()

    def _apply_mtd_strategy(self, action):
        """
        [IMPROVEMENT] 복합 MTD 전략 적용
        RL의 연속 출력을 기반으로 Shuffle, Decoy, Blacklist 정책을 동시에 결정
        """
        params = {
            "dnat_target_focus": _scale_action(action[0]),
            "dnat_decoy_focus": _scale_action(action[1]),
            "shuffle_intensity": _scale_action(action[2]),
            "blacklist_aggression": _scale_action(action[3]),
            "blacklist_duration": _scale_action(action[4]),
            "decoy_ratio": _scale_action(action[5]),
        }
        self.last_actions = params
        
        # 1. 블랙리스트 정책 업데이트
        self.blacklister.update_policy(params["blacklist_aggression"], params["blacklist_duration"])

        # 2. 동시 행동 결정 (Threshold 기반)
        is_shuffle = params["shuffle_intensity"] >= ACT_THRESHOLDS.get("SHUFFLE", 0.6)
        is_decoy_active = params["decoy_ratio"] >= ACT_THRESHOLDS.get("DECOY_ACTIVE", 0.4)
        
        if is_shuffle:
            self.ep_shuffle_count += 1
            # 실제 환경이라면 여기서 ./scripts/ip_port_swap.sh 실행

        # 비용 계산
        cost = COST_MTD_ACTION
        if is_shuffle: cost += COST_SHUFFLE * params["shuffle_intensity"]
        if is_decoy_active: cost += COST_DECOY * params["decoy_ratio"]
        cost += COST_BL * params["blacklist_aggression"]
        
        self.ep_total_cost += cost
        
        return {
            "cost": cost,
            "is_shuffle": is_shuffle,
            "is_decoy_active": is_decoy_active,
            "params": params
        }

    def step(self, action):
        self.current_step += 1
        self.ep_total_steps += 1
        terminated = self.current_step >= self.max_episode_steps
        truncated = False

        # 1. Defender Action (Multi-Action)
        mtd_res = self._apply_mtd_strategy(action)

        # 2. Seeker Intent (방어 상태를 모른 채 의도만 전달)
        seeker_intent = self.seeker.step(mtd_res["is_shuffle"])
        
        # 3. Environment Interaction (성공/실패 판정)
        # 블랙리스트 차단 여부 확인
        is_blocked = self.blacklister.is_blocked(seeker_intent["seeker_ip"])
        
        outcome = "continue"
        is_exploit_success = False
        is_breach_success = False
        is_decoy_hit = False
        
        if seeker_intent["target_ep"]:
             # 디코이 여부 확인
            if seeker_intent["target_ep"].is_decoy and seeker_intent["is_exploit_attempt"]:
                is_decoy_hit = True
            
            # 공격 결과 판정
            if is_blocked:
                outcome = "blocked"
            elif seeker_intent["is_exploit_attempt"]:
                # 방어자가 디코이에 집중하거나 블랙리스트가 약하면 뚫림
                # 간단한 확률 모델: 블랙리스트 강도가 낮을수록 성공 확률 높음
                if self.rng.random() > mtd_res["params"]["blacklist_aggression"]:
                    outcome = "exploit_success"
                    is_exploit_success = True
                else:
                    outcome = "blocked" # 확률적 차단
            elif seeker_intent["is_breach_attempt"]:
                if self.rng.random() > mtd_res["params"]["blacklist_aggression"]:
                    outcome = "breach_success"
                    is_breach_success = True
                else:
                    outcome = "blocked"
        
        # Seeker에게 결과 피드백
        self.seeker.handle_outcome(outcome)

        # 4. CTI 업데이트
        cti_score, is_alert = self.cti.process_traffic(seeker_intent["is_scan"])
        if is_alert:
            self.blacklister.apply_block(seeker_intent["seeker_ip"], cti_score)
        self.blacklister.step()

        # 5. 카운터 업데이트
        # [FIX] seeker_intent에 'is_exploit_attempt' 키가 항상 존재하도록 수정되었으므로 안전함
        if seeker_intent["is_exploit_attempt"]: self.ep_exploit_attempts += 1
        if seeker_intent["is_breach_attempt"]: self.ep_breach_attempts += 1
        if is_breach_success: self.ep_breach_success += 1
        if is_decoy_hit: self.ep_decoy_hits += 1
        
        is_exploit_block = (outcome == "blocked" and seeker_intent["is_exploit_attempt"])
        is_breach_block = (outcome == "blocked" and seeker_intent["is_breach_attempt"])
        
        if is_breach_block: self.ep_breach_block += 1
        
        if not mtd_res["is_shuffle"]: self.ep_uptime_steps += 1

        # 6. Reward & Info 계산
        reward_info = {
            "is_exploit_success": is_exploit_success,
            "is_breach_success": is_breach_success,
            "is_exploit_block": is_exploit_block,
            "is_breach_block": is_breach_block,
            "is_decoy_hit": is_decoy_hit,
            "is_shuffle": mtd_res["is_shuffle"],
            "is_breach_attempt": seeker_intent.get("is_breach_attempt", False)
        }
        
        reward = self._calculate_reward(mtd_res, reward_info)

        obs = self._get_state()
        info = self._get_current_metrics()
        info["cost"] = mtd_res["cost"]
        info["raw_reward"] = reward
        info["applied_mtd"] = mtd_res["is_shuffle"]
        
        # Params 로깅
        for k, v in mtd_res["params"].items():
            info[f"Params/{k}"] = v

        return obs, reward, terminated, truncated, info

    def _calculate_reward(self, mtd_res, r_info):
        reward = 0.0
        
        # 공격 성공 시 큰 페널티
        if r_info["is_breach_success"]: reward += REWARD_ATTACK_SUCCESS
        elif r_info["is_exploit_success"]: reward += (REWARD_ATTACK_SUCCESS * 0.2)
        
        # 방어 성공 시 보상
        if r_info["is_breach_block"]: reward += REWARD_ATTACK_BLOCKED
        elif r_info["is_exploit_block"]: reward += (REWARD_ATTACK_BLOCKED * 0.5)

        # 디코이 유인 성공 보상
        if r_info["is_decoy_hit"]: reward += 5.0
        
        # 비용 차감
        reward -= (mtd_res["cost"] * COST_WEIGHT)
        
        # 정상 상태 유지 보상 (공격도 없고 셔플도 안할 때)
        real_state = self.cti.get_real_state()
        is_real_attack = real_state.get("attack_detected", False)
        if not is_real_attack and not r_info["is_breach_attempt"] and not mtd_res["is_shuffle"]:
            reward += REWARD_NORMAL

        return float(reward)

    def _get_state(self):
        breach_rate = _safe_divide(self.ep_breach_success, max(1, self.ep_breach_attempts))
        decoy_rate = _safe_divide(self.ep_decoy_hits, max(1, self.ep_exploit_attempts))
        
        metrics = {
            "cti_alert_rate": self.cti.get_alert_rate(),
            "blacklist_size_ratio": self.blacklister.get_size_ratio(len(self.endpoints)),
            "uptime_ratio": _safe_divide(self.ep_uptime_steps, self.ep_total_steps),
            "breach_success_rate": breach_rate,
            "decoy_lure_rate": decoy_rate,
            "current_exposure_mean": 0.5, 
            "r_known_ratio": 0.5,
            "r_exploited_ratio": 0.5,
            "seeker_scan_effort": self.seeker.seeker_params[0],
            "seeker_attack_bias": self.seeker.seeker_params[1],
        }
        
        state_vec = [metrics.get(k, 0.0) for k in FEATURE_KEYS[:10]]
        state_vec.extend([self.last_actions.get(k, 0.5) for k in ACTION_PARAM_KEYS])
        return np.array(state_vec, dtype=np.float32)

    def _get_current_metrics(self):
        r_succ = _safe_divide(self.ep_breach_block, self.ep_breach_attempts) if self.ep_breach_attempts > 0 else 0.0
        c_def = _safe_divide(self.ep_total_cost, max(1, self.ep_total_steps))
        decoy_rate = _safe_divide(self.ep_decoy_hits, max(1, self.ep_exploit_attempts))
        s_mtd = (0.5 * r_succ) + (0.3 * decoy_rate) - (0.2 * c_def)
        return {
            "Defense/R_succ": r_succ, 
            "Defense/S_MTD_overall": s_mtd,
            "Metrics": {"Defense": {"R_succ": r_succ}, "Attack": {"decoy_lure_rate": decoy_rate}}
        }