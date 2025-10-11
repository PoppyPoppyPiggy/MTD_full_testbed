# environment.py
import numpy as np
import config
from nmap_emulator import NmapEmulator

class BatchedMTDEnvironment:
    """
    [v11] 정보이론 기반 MTD-Seeker 환경
    """
    def __init__(self, n_envs: int):
        self.n = n_envs
        self.rng = np.random.default_rng()
        self.nmap_emulator = NmapEmulator(self.rng)

        # 상태: [H_ip, H_port, decoy_on, MTD예산비율, 비활동수준, 스텝비율]
        self.state_dim = 6
        self.mtd_action_space_n = len(config.MTD_ACTIONS)
        self.seeker_action_space_n = len(config.SEEKER_ACTIONS)

        self._reset_internal_states()

    def _reset_internal_states(self):
        self.steps = np.zeros(self.n, dtype=np.int32)
        # 불확실성 (Entropy) 상태
        self.H_ip = np.ones(self.n, dtype=np.float32)
        self.H_port = np.ones(self.n, dtype=np.float32)
        # MTD 셔플 후 경과 시간
        self.steps_since_ip_shuffle = np.zeros(self.n, dtype=np.int32)
        self.steps_since_port_shuffle = np.zeros(self.n, dtype=np.int32)
        # MTD 상태
        self.decoy_on = np.zeros(self.n, dtype=np.bool_)
        self.mtd_budget = np.full(self.n, 200.0, dtype=np.float32)
        self.mtd_inaction_counter = np.zeros(self.n, dtype=np.int32)

    def reset(self):
        self._reset_internal_states()
        return self._get_obs()

    def _get_obs(self):
        obs = np.zeros((self.n, self.state_dim), dtype=np.float32)
        obs[:, 0] = self.H_ip
        obs[:, 1] = self.H_port
        obs[:, 2] = self.decoy_on.astype(np.float32)
        obs[:, 3] = self.mtd_budget / 200.0
        obs[:, 4] = self.mtd_inaction_counter / config.MAX_INACTION_STEPS
        obs[:, 5] = self.steps / config.MAX_STEPS_PER_EPISODE
        return obs

    def step(self, mtd_actions: np.ndarray, seeker_actions: np.ndarray):
        self.steps += 1
        self.steps_since_ip_shuffle += 1
        self.steps_since_port_shuffle += 1
        
        mtd_rewards = np.zeros(self.n, dtype=np.float32)
        seeker_rewards = np.zeros(self.n, dtype=np.float32)
        breach = np.zeros(self.n, dtype=np.bool_)

        # --- 비활동 페널티 처리 ---
        is_waiting = mtd_actions == config.MTD_ACTIONS["대기"]
        self.mtd_inaction_counter[is_waiting] += 1
        self.mtd_inaction_counter[~is_waiting] = 0
        inaction_level = np.clip(self.mtd_inaction_counter / config.MAX_INACTION_STEPS, 0, 1)
        mtd_rewards += inaction_level * config.INACTION_PENALTY

        # --- Seeker 행동 처리 ---
        for i in range(self.n):
            action = seeker_actions[i]
            if action == config.SEEKER_ACTIONS["IP 스캔"]:
                self.H_ip[i:i+1], info_gain, detected = self.nmap_emulator.scan_ip(self.steps_since_ip_shuffle[i:i+1], self.H_ip[i:i+1])
                seeker_rewards[i] += info_gain * config.REWARD_SEEKER_INFO_GAIN_MULTIPLIER
                if detected: seeker_rewards[i] += config.PENALTY_SEEKER_DETECTED
            
            elif action == config.SEEKER_ACTIONS["Port 스캔"]:
                self.H_port[i:i+1], info_gain, detected = self.nmap_emulator.scan_port(self.steps_since_port_shuffle[i:i+1], self.H_port[i:i+1])
                seeker_rewards[i] += info_gain * config.REWARD_SEEKER_INFO_GAIN_MULTIPLIER
                if detected: seeker_rewards[i] += config.PENALTY_SEEKER_DETECTED

            elif action == config.SEEKER_ACTIONS["스텔스 스캔"]:
                self.H_ip[i:i+1], info_gain, detected = self.nmap_emulator.stealth_scan(self.steps_since_ip_shuffle[i:i+1], self.H_ip[i:i+1])
                seeker_rewards[i] += info_gain * config.REWARD_SEEKER_INFO_GAIN_MULTIPLIER
                if detected: seeker_rewards[i] += config.PENALTY_SEEKER_DETECTED

            elif action == config.SEEKER_ACTIONS["디코이 프로브"]:
                probe_success = self.nmap_emulator.decoy_probe(self.decoy_on[i:i+1])
                if probe_success and self.decoy_on[i]: # 디코이를 성공적으로 찾아냄
                    mtd_rewards[i] += config.PENALTY_SEEKER_DETECTED # MTD에게 페널티
                elif not probe_success and not self.decoy_on[i]: # 없는 디코이를 찾으려다 실패 (정상)
                    pass
                else: # 헛된 프로브 (FN 또는 FP)
                    seeker_rewards[i] += config.PENALTY_SEEKER_WASTED_PROBE

            elif action == config.SEEKER_ACTIONS["자산 공격"]:
                total_uncertainty = self.H_ip[i] + self.H_port[i]
                if self.decoy_on[i] and self.rng.random() < 0.7: # 70% 확률로 허니팟에 유인됨
                    seeker_rewards[i] += config.PENALTY_SEEKER_DECOY_ENGAGED
                    mtd_rewards[i] += config.REWARD_MTD_DECOY_SUCCESS
                elif total_uncertainty < config.ATTACK_UNCERTAINTY_THRESHOLD:
                    breach[i] = True
                    seeker_rewards[i] += config.REWARD_SEEKER_ATTACK_SUCCESS
                    mtd_rewards[i] += config.PENALTY_MTD_BREACHED
                else:
                    seeker_rewards[i] += config.PENALTY_SEEKER_ATTACK_FAIL
                    mtd_rewards[i] += config.REWARD_MTD_DEFENSE_SUCCESS

        # --- MTD 행동 처리 ---
        for i in range(self.n):
            action = mtd_actions[i]
            cost = config.COST_MTD_ACTION
            if action == config.MTD_ACTIONS["IP 셔플링"]:
                cost += config.COST_MTD_HIGH_TECH
                if self.mtd_budget[i] + cost >= 0:
                    self.H_ip[i] = 1.0
                    self.steps_since_ip_shuffle[i] = 0
                    self.mtd_budget[i] += cost
            elif action == config.MTD_ACTIONS["Port 셔플링"]:
                cost += config.COST_MTD_HIGH_TECH
                if self.mtd_budget[i] + cost >= 0:
                    self.H_port[i] = 1.0
                    self.steps_since_port_shuffle[i] = 0
                    self.mtd_budget[i] += cost
            elif action == config.MTD_ACTIONS["허니팟 배포"]:
                if self.mtd_budget[i] + cost >= 0:
                    self.decoy_on[i] = True
                    self.mtd_budget[i] += cost

        done = breach | (self.steps >= config.MAX_STEPS_PER_EPISODE)
        if np.any(done): self.reset()
        
        return self._get_obs(), mtd_rewards, seeker_rewards, done, {}