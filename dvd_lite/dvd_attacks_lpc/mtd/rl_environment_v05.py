import gym
from gym import spaces
import numpy as np
import random
import logging
import json
import os
from collections import deque

from .rl_config_v05 import (
    RL_CONFIG,
    FEATURE_KEYS,
    ACTION_PARAM_KEYS,
    ACT_THRESHOLDS,
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
# seeker_agent.py에서 클래스 import
from .seeker_agent import Endpoint, SimulatedHeuristicSeeker

logger = logging.getLogger("RLEnv")

# -------------------------
# Utils
# -------------------------
def _scale_action(action, lower_bound=0.0, upper_bound=1.0):
    return lower_bound + (0.5 * (action + 1.0) * (upper_bound - lower_bound))

def _safe_divide(numerator, denominator):
    return numerator / denominator if denominator != 0 else 0.0

# -------------------------
# Simulated Components
# -------------------------
class HybridCTI:
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
        real_state = self.get_real_state()
        real_alert = real_state.get("attack_detected", False)
        real_score = real_state.get("risk_score", 0.0)

        if is_suspicious_sim:
            sim_score = self.rng.normal(loc=0.8, scale=0.1)
        else:
            sim_score = self.rng.normal(loc=0.1, scale=0.1)
        
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
    def __init__(self, rng):
        self.rng = rng
        self.blacklist_policy = {"aggression": 0.0, "duration": 0}
        self.blocked_ips = {}

    def update_policy(self, aggression, duration):
        self.blacklist_policy["aggression"] = float(np.clip(aggression, 0.0, 1.0))
        self.blacklist_policy["duration"] = int(duration * 1000)

    def apply_block(self, ip, cti_score):
        # Aggression이 높을수록(1.0) 임계값이 낮아져(0.2) 더 쉽게 차단됨
        threshold = 1.0 - (self.blacklist_policy["aggression"] * 0.8) 
        if cti_score >= threshold:
            self.blocked_ips[ip] = max(10, self.blacklist_policy["duration"])
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

# -------------------------
# MTD Environment
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

        self.action_space = spaces.Box(low=-1.0, high=1.0, shape=(len(ACTION_PARAM_KEYS),), dtype=np.float32)
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
        
        if not endpoints:
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
        # 에피소드마다 Seeker 초기화
        self.seeker = SimulatedHeuristicSeeker(self.rng, self.seeker_level, self.endpoints)
        
        return self._get_state(), self._get_current_metrics()

    def _update_mtd_state(self, state_update: dict):
        """ mtd_state.json 파일에 현재 방어 상태 기록 (가상) """
        # 실제 파일 쓰기는 I/O 부하 때문에 생략하거나 필요시 구현
        # 여기서는 메모리 상의 상태만 관리한다고 가정
        pass

    def _apply_mtd_strategy(self, action):
        """
        RL 액션을 해석하여 실제 방어 전략(셔플, 디코이, 블랙리스트) 상태를 업데이트하고
        그 결과를 반환함.
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
        
        # 1. 블랙리스트 정책 업데이트 (실제 차단 기준 변경)
        self.blacklister.update_policy(params["blacklist_aggression"], params["blacklist_duration"])

        # 2. 활성 방어 여부 결정 (임계값 기반)
        is_shuffle = params["shuffle_intensity"] >= ACT_THRESHOLDS["SHUFFLE"]
        is_decoy_active = params["decoy_ratio"] >= ACT_THRESHOLDS["DECOY_ACTIVE"]
        
        # [IMPROVEMENT] 셔플링의 실질적 효과 구현
        if is_shuffle:
            self.ep_shuffle_count += 1
            # (가상) 포트 변경: mtd_state 업데이트
            new_port = self.rng.integers(10000, 60000)
            self._update_mtd_state({"target_service_port": new_port})
            
            # (중요) Seeker의 모든 공격 진행도 초기화 (연결 끊김 시뮬레이션)
            for ep in self.endpoints:
                ep.reset_progress()
            
            # Seeker 강제 타겟 재설정 (reorient 유도)
            self.seeker.current_target = self.rng.choice(self.endpoints)

        # [IMPROVEMENT] 디코이 활성화 효과 구현
        if is_decoy_active:
            # 현재 Seeker의 타겟이 실제 자산이라면, decoy_ratio 확률로 디코이로 납치
            current_t = self.seeker.current_target
            if not current_t.is_decoy and self.rng.random() < params["decoy_ratio"]:
                decoys = [ep for ep in self.endpoints if ep.is_decoy]
                if decoys:
                    self.seeker.current_target = self.rng.choice(decoys)
                    # (선택) 로그 메시지: "Redirected attacker to Decoy"

        # 비용 계산 (비용은 줄이되, 행동에 대한 피드백은 확실하게)
        cost = COST_MTD_ACTION
        if is_shuffle: cost += COST_SHUFFLE * params["shuffle_intensity"]
        if is_decoy_active: cost += COST_DECOY * params["decoy_ratio"]
        cost += COST_BL * params["blacklist_aggression"]
        
        self.ep_total_cost += cost
        
        return {
            "cost": cost,
            "is_shuffle": is_shuffle,
            "is_decoy_active": is_decoy_active,
            "decoy_ratio": params["decoy_ratio"],
            "params": params
        }

    def step(self, action):
        self.current_step += 1
        self.ep_total_steps += 1
        terminated = self.current_step >= self.max_episode_steps
        truncated = False

        # 1. Defender Action (환경 변화 발생)
        mtd_res = self._apply_mtd_strategy(action)

        # 2. Seeker Step (변경된 환경을 인지하고 의도 반환)
        seeker_status = {
            "is_shuffle": mtd_res["is_shuffle"],
            "is_decoy_active": mtd_res["is_decoy_active"],
            "decoy_ratio": mtd_res["decoy_ratio"]
        }
        seeker_intent = self.seeker.step(seeker_status)
        
        # 3. 상호작용 판정 (Conflict Resolution)
        # (A) 블랙리스트에 의한 사전 차단 확인
        is_blocked_by_list = self.blacklister.is_blocked(seeker_intent["seeker_ip"])
        
        outcome = "continue"
        is_exploit_success = False
        is_breach_success = False
        is_decoy_hit = False
        
        # [IMPROVEMENT] 블랙리스트 정책에 의한 즉각적 차단 시도 (List에 없어도 정책이 강하면 차단)
        # Seeker가 공격(Exploit/Breach)을 시도할 때 방어 민감도가 높으면 차단 확률 증가
        is_policy_blocked = False
        if (seeker_intent["is_exploit_attempt"] or seeker_intent["is_breach_attempt"]):
            block_prob = mtd_res["params"]["blacklist_aggression"] * 0.8 # 최대 80% 확률로 즉시 차단
            if self.rng.random() < block_prob:
                is_policy_blocked = True
                # 차단된 IP 등록 (실제 효과)
                self.blacklister.blocked_ips[seeker_intent["seeker_ip"]] = \
                    max(10, mtd_res["params"]["blacklist_duration"] * 1000)

        final_blocked = is_blocked_by_list or is_policy_blocked

        if seeker_intent["target_ep"]:
            # (B) 디코이 히트 판정
            if seeker_intent["target_ep"].is_decoy and seeker_intent["is_exploit_attempt"]:
                is_decoy_hit = True
                outcome = "decoy_hit"
            
            # (C) 차단 판정
            elif final_blocked:
                outcome = "blocked"
            
            # (D) 공격 성공 판정
            elif seeker_intent["is_exploit_attempt"]:
                # 차단되지 않았다면 성공
                outcome = "exploit_success"
                is_exploit_success = True
            
            elif seeker_intent["is_breach_attempt"]:
                # Breach는 최후의 방어선이므로 한번 더 확률 체크 (운 좋게 막을 수도 있음)
                # 하지만 여기선 간단히 성공으로 처리하여 방어의 중요성 강조
                outcome = "breach_success"
                is_breach_success = True
        
        # 4. Seeker에게 결과 피드백 (Seeker 상태 업데이트)
        self.seeker.handle_outcome(outcome)

        # 5. CTI & 블랙리스트 업데이트 (사후 탐지 및 차단)
        cti_score, is_alert = self.cti.process_traffic(seeker_intent["is_scan"])
        if is_alert:
            self.blacklister.apply_block(seeker_intent["seeker_ip"], cti_score)
        self.blacklister.step()

        # 6. 통계 카운터 업데이트 [CRITICAL FIX]
        if seeker_intent["is_exploit_attempt"]: self.ep_exploit_attempts += 1
        if seeker_intent["is_breach_attempt"]: self.ep_breach_attempts += 1
        
        if is_breach_success: self.ep_breach_success += 1
        if is_decoy_hit: self.ep_decoy_hits += 1
        
        # 차단 성공 카운트 (방어 지표용)
        is_exploit_block = (outcome == "blocked" and seeker_intent["is_exploit_attempt"])
        is_breach_block = (outcome == "blocked" and seeker_intent["is_breach_attempt"])
        
        if is_breach_block: self.ep_breach_block += 1
        
        if not mtd_res["is_shuffle"]: self.ep_uptime_steps += 1

        # 7. 보상 및 정보 생성
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
        info.update({
            "cost": mtd_res["cost"],
            "raw_reward": reward,
            "applied_mtd": mtd_res["is_shuffle"]
        })
        
        # 상세 파라미터 로깅
        for k, v in mtd_res["params"].items():
            info[f"Params/{k}"] = v

        return obs, reward, terminated, truncated, info

    def _calculate_reward(self, mtd_res, r_info):
        reward = 0.0
        
        # 1. 공격 결과에 따른 페널티 (매우 큼)
        if r_info["is_breach_success"]: 
            reward += REWARD_ATTACK_SUCCESS # -100.0
        elif r_info["is_exploit_success"]: 
            reward += (REWARD_ATTACK_SUCCESS * 0.3) # -30.0
        
        # 2. 방어 성공 보상 (매우 큼)
        if r_info["is_breach_block"]: 
            reward += REWARD_ATTACK_BLOCKED # +50.0
        elif r_info["is_exploit_block"]: 
            reward += (REWARD_ATTACK_BLOCKED * 0.4) # +20.0

        # 3. 디코이 유인 보상
        if r_info["is_decoy_hit"]: 
            reward += 10.0
        
        # 4. 비용 차감 (비중 축소)
        reward -= (mtd_res["cost"] * COST_WEIGHT)
        
        # 5. 생존 보상 (조금 줄임, 방어 행동 독려를 위해)
        if not r_info["is_breach_success"] and not r_info["is_exploit_success"]:
            reward += (REWARD_NORMAL * 0.8) # +0.4

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
        # R_succ: 침해 시도 대비 차단 횟수
        r_succ = _safe_divide(self.ep_breach_block, self.ep_breach_attempts) if self.ep_breach_attempts > 0 else 0.0
        c_def = _safe_divide(self.ep_total_cost, max(1, self.ep_total_steps))
        decoy_rate = _safe_divide(self.ep_decoy_hits, max(1, self.ep_exploit_attempts))
        
        # S_MTD 공식: 차단률과 디코이 유인률을 합산하고 비용을 뺌
        s_mtd = (0.5 * r_succ) + (0.3 * decoy_rate) - (0.1 * c_def)
        
        # WandB 로깅을 위한 중첩 구조
        return {
            "Defense/R_succ": r_succ, 
            "Defense/S_MTD_overall": s_mtd,
            "Attack/decoy_lure_rate": decoy_rate,
            "Metrics": {
                "Defense": {"R_succ": r_succ, "MTD_Rate": c_def}, # MTD_Rate로 비용 대용
                "Attack": {"decoy_lure_rate": decoy_rate}
            }
        }