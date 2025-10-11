# environment_torch.py
import torch
import config  # <-- 오류 수정: config 모듈 임포트 추가

class MTDSeekerEnvTorch:
    """
    모든 상태와 전이 로직이 PyTorch CUDA 텐서로 구현된 MTD 환경.
    CPU-GPU 데이터 복사 오버헤드 '제로'를 목표.
    """
    def __init__(self, n_envs, device):
        self.n_envs = n_envs
        self.dev = device
        
        # --- 행동 공간 정의 ---
        self.mtd_n = len(config.MTD_ACTIONS)
        self.seeker_n = len(config.SEEKER_ACTIONS)
        
        # --- 상태 공간 정의 ---
        # [IP노출, Port노출, AS변동성, 예산, IP셔플쿨타임, Port셔플쿨타임, BL활성, Decoy활성]
        self.state_dim = 8
        
        # --- 비용 텐서 ---
        self.t_cost_ip = torch.tensor(config.COST_IP_SHUFFLE, device=self.dev)
        self.t_cost_pt = torch.tensor(config.COST_PT_SHUFFLE, device=self.dev)
        self.t_cost_decoy = torch.tensor(config.COST_DECOY, device=self.dev)
        self.t_cost_bl = torch.tensor(config.COST_BL, device=self.dev)
        
        # --- 내부 상태 변수 (모두 CUDA 텐서) ---
        self.budget = torch.full((n_envs,), config.BUDGET, device=self.dev, dtype=torch.float32)
        self.as_exp = torch.ones((n_envs,), device=self.dev, dtype=torch.float32)
        self.as_var = torch.zeros((n_envs,), device=self.dev, dtype=torch.float32)
        self.steps_since_ip = torch.zeros((n_envs,), device=self.dev, dtype=torch.float32)
        self.steps_since_pt = torch.zeros((n_envs,), device=self.dev, dtype=torch.float32)
        self.bl_on = torch.zeros((n_envs,), device=self.dev, dtype=torch.bool)
        self.decoy_on = torch.zeros((n_envs,), device=self.dev, dtype=torch.bool)
        self.steps = 0
    
    def reset(self):
        self.budget.fill_(config.BUDGET)
        self.as_exp.fill_(1.0)
        self.as_var.zero_()
        self.steps_since_ip.zero_()
        self.steps_since_pt.zero_()
        self.bl_on.zero_()
        self.decoy_on.zero_()
        self.steps = 0
        return self._get_obs()

    def _get_obs(self):
        return torch.stack([
            self.as_exp,
            (self.as_exp * 0.7), # Port 노출은 IP 노출에 비례한다고 가정
            self.as_var,
            self.budget / config.BUDGET,
            torch.clamp(self.steps_since_ip / 20.0, 0, 1),
            torch.clamp(self.steps_since_pt / 20.0, 0, 1),
            self.bl_on.float(),
            self.decoy_on.float()
        ], dim=-1)

    def step(self, mtd_actions, seeker_actions):
        # --- 상태 업데이트 ---
        self.steps += 1
        self.steps_since_ip += 1
        self.steps_since_pt += 1
        
        # --- MTD 행동 처리 ---
        mtd_costs = torch.zeros_like(self.budget)
        mtd_costs = torch.where(mtd_actions == 1, self.t_cost_ip, mtd_costs)
        mtd_costs = torch.where(mtd_actions == 2, self.t_cost_pt, mtd_costs)
        mtd_costs = torch.where(mtd_actions == 3, self.t_cost_decoy, mtd_costs)
        mtd_costs = torch.where(mtd_actions == 4, self.t_cost_bl, mtd_costs)
        
        can_afford = (self.budget + mtd_costs) >= 0
        
        # IP 셔플링
        ip_shuffle_mask = (mtd_actions == 1) & can_afford
        self.as_exp = torch.where(ip_shuffle_mask, self.as_exp * 0.5 + 0.5, self.as_exp * 0.99 + 0.01)
        self.as_var = torch.where(ip_shuffle_mask, self.as_var + 0.2, self.as_var * 0.95)
        self.steps_since_ip[ip_shuffle_mask] = 0
        
        # Port 셔플링
        pt_shuffle_mask = (mtd_actions == 2) & can_afford
        self.as_var = torch.where(pt_shuffle_mask, self.as_var + 0.1, self.as_var)
        self.steps_since_pt[pt_shuffle_mask] = 0
        
        # 허니팟 & 블랙리스트
        self.decoy_on = (mtd_actions == 3) & can_afford
        self.bl_on = (mtd_actions == 4) & can_afford
        
        self.budget = torch.clamp(self.budget + mtd_costs, 0, config.BUDGET)

        # --- Seeker 행동 및 보상 계산 ---
        recon_prob = torch.clamp(1.0 - self.as_exp, 0.1, 0.9)
        recon_success = torch.rand_like(recon_prob) < recon_prob
        
        attack_prob = torch.clamp(1.0 - self.as_exp - self.as_var * 0.5, 0.05, 0.8)
        attack_prob[self.decoy_on] *= 0.1
        attack_success = (seeker_actions == 3) & (torch.rand_like(attack_prob) < attack_prob)
        
        mtd_rewards = config.W_EXP * self.as_exp + config.W_VAR * self.as_var + mtd_costs
        mtd_rewards = torch.where(attack_success, mtd_rewards - 50.0, mtd_rewards)
        
        seeker_rewards = torch.zeros_like(mtd_rewards)
        seeker_rewards = torch.where((seeker_actions == 0) & recon_success, seeker_rewards + 5.0, seeker_rewards - 1.0)
        seeker_rewards = torch.where(attack_success, seeker_rewards + 50.0, seeker_rewards)
        
        # --- 종료 조건 ---
        dones = (self.budget <= 0) | (attack_success)
        if self.steps >= config.MAX_STEPS_PER_EPISODE:
            dones.fill_(True)
        
        # 리셋
        if dones.any():
            self.budget[dones] = config.BUDGET
            self.as_exp[dones] = 1.0
            self.as_var[dones] = 0.0
            self.steps_since_ip[dones] = 0
            self.steps_since_pt[dones] = 0
            self.bl_on[dones] = False
            self.decoy_on[dones] = False
            if dones.all(): self.steps = 0

        return self._get_obs(), mtd_rewards, seeker_rewards, dones