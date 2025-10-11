# environment_torch.py
import torch
import config

DTYPE = torch.float32

def _rand_ip(n_env, device):
    return torch.randint(low=0, high=config.NUM_IPS, size=(n_env,), device=device)

def _rand_port(n_env, device):
    return torch.randint(low=0, high=config.NUM_PORTS, size=(n_env,), device=device)

class TorchNmapEmulator:
    def __init__(self, device): self.device = device

    @torch.no_grad()
    def scan_ip(self, steps_since_ip, H_ip):
        recent_w = torch.clamp(steps_since_ip / max(1, config.RECENT_WIN), 0.0, 1.0)
        reduction = config.SCAN_BASE_REDUCTION_IP * (config.SCAN_REDUCTION_AT0 + (1.0 - config.SCAN_REDUCTION_AT0) * recent_w)
        prior = H_ip
        post = torch.clamp(prior - reduction, min=0.0)
        info = prior - post
        detected = torch.ones_like(info, dtype=torch.bool, device=info.device)
        return post, info, detected

    @torch.no_grad()
    def scan_port(self, steps_since_pt, H_pt):
        recent_w = torch.clamp(steps_since_pt / max(1, config.RECENT_WIN), 0.0, 1.0)
        reduction = config.SCAN_BASE_REDUCTION_PT * (config.SCAN_REDUCTION_AT0 + (1.0 - config.SCAN_REDUCTION_AT0) * recent_w)
        prior = H_pt
        post = torch.clamp(prior - reduction, min=0.0)
        info = prior - post
        detected = torch.ones_like(info, dtype=torch.bool, device=info.device)
        return post, info, detected

    @torch.no_grad()
    def stealth_scan(self, steps_since_ip, H_ip):
        recent_w = torch.clamp(steps_since_ip / max(1, config.RECENT_WIN), 0.0, 1.0)
        reduction = config.STEALTH_REDUCTION * (config.SCAN_REDUCTION_AT0 + (1.0 - config.SCAN_REDUCTION_AT0) * recent_w)
        prior = H_ip
        post = torch.clamp(prior - reduction, min=0.0)
        info = prior - post
        detected = (torch.rand_like(info) < config.STEALTH_DET_FACTOR)
        return post, info, detected

    @torch.no_grad()
    def decoy_probe(self, decoy_on):
        base = config.DECOY_PROBE_P
        p_succ = torch.where(
            decoy_on.bool(),
            torch.full_like(decoy_on, base * (1.0 - config.DECOY_FN), dtype=DTYPE),
            torch.full_like(decoy_on, config.DECOY_FP, dtype=DTYPE),
        )
        return (torch.rand_like(decoy_on) < p_succ).bool()

class MTDSeekerEnvTorch:
    """GPU-only 환경 + 메트릭용 상세 지표(last_stats, last_masks, step_costs)"""
    def __init__(self, n_envs: int, device=None):
        self.device = device or config.DEVICE
        self.n = n_envs
        self.nmap = TorchNmapEmulator(self.device)

        # 상태
        self.active_ip   = _rand_ip(self.n, self.device)
        self.active_port = _rand_port(self.n, self.device)
        self.decoy_on    = torch.zeros(self.n, device=self.device, dtype=torch.bool)
        self.decoy_ip    = torch.zeros(self.n, device=self.device, dtype=torch.long)
        self.decoy_pt    = torch.zeros(self.n, device=self.device, dtype=torch.long)

        self.bl_ips      = torch.zeros((self.n, config.NUM_IPS), device=self.device, dtype=DTYPE)
        self.last_mtd    = torch.full((self.n,), -1, device=self.device, dtype=torch.long)

        self.steps_since_ip = torch.zeros(self.n, device=self.device, dtype=DTYPE)
        self.steps_since_pt = torch.zeros(self.n, device=self.device, dtype=DTYPE)

        self.H_ip  = torch.full((self.n,), 1.0, device=self.device, dtype=DTYPE)
        self.H_pt  = torch.full((self.n,), 1.0, device=self.device, dtype=DTYPE)

        self.budget = torch.full((self.n,), config.BUDGET_INIT, device=self.device, dtype=DTYPE)
        self.t_cost_ip = torch.zeros(self.n, device=self.device, dtype=DTYPE)
        self.t_cost_pt = torch.zeros(self.n, device=self.device, dtype=DTYPE)
        self.t_cost_decoy = torch.zeros(self.n, device=self.device, dtype=DTYPE)
        self.t_cost_bl = torch.zeros(self.n, device=self.device, dtype=DTYPE)

        self.as_exp = torch.zeros(self.n, device=self.device, dtype=DTYPE)
        self.as_var = torch.zeros(self.n, device=self.device, dtype=DTYPE)

        self.mtd_n = 5
        self.seeker_n = 5 + config.NUM_IPS + config.NUM_PORTS
        self.state_dim = 11 + config.NUM_IPS

        self.last_stats = {}
        self.last_masks = {}   # breach/block/decoy bool mask 보관

    @torch.no_grad()
    def _state(self):
        ip_norm = self.active_ip.float() / max(1, config.NUM_IPS-1)
        pt_norm = self.active_port.float() / max(1, config.NUM_PORTS-1)
        decoy = self.decoy_on.float()
        last = (self.last_mtd + 1).float() / self.mtd_n
        s_ip = torch.clamp(self.steps_since_ip / 16.0, 0, 1)
        s_pt = torch.clamp(self.steps_since_pt / 16.0, 0, 1)
        budget_n = torch.clamp(self.budget / (config.BUDGET_INIT * 2.0), 0.0, 1.0)
        core = torch.stack(
            [ip_norm, pt_norm, decoy, last, s_ip, s_pt, self.H_ip, self.H_pt,
             self.as_exp, self.as_var, budget_n],
            dim=1,
        )
        return torch.cat([core, self.bl_ips], dim=1)

    @torch.no_grad()
    def reset(self):
        self.active_ip[:]   = _rand_ip(self.n, self.device)
        self.active_port[:] = _rand_port(self.n, self.device)
        self.decoy_on.zero_(); self.decoy_ip.zero_(); self.decoy_pt.zero_()
        self.bl_ips.zero_(); self.last_mtd.fill_(-1)
        self.steps_since_ip.zero_(); self.steps_since_pt.zero_()
        self.H_ip.fill_(1.0); self.H_pt.fill_(1.0)
        self.budget.fill_(config.BUDGET_INIT)
        self.t_cost_ip.zero_(); self.t_cost_pt.zero_(); self.t_cost_decoy.zero_(); self.t_cost_bl.zero_()
        self.as_exp.zero_(); self.as_var.zero_()
        self.last_stats = {}; self.last_masks = {}
        return self._state()

    @torch.no_grad()
    def _do_mtd(self, a_mtd: torch.Tensor):
        self.steps_since_ip += 1.0
        self.steps_since_pt += 1.0
        self.t_cost_ip.zero_(); self.t_cost_pt.zero_(); self.t_cost_decoy.zero_(); self.t_cost_bl.zero_()

        mask1 = (a_mtd == 1)
        if mask1.any():
            n1 = mask1.sum().item()
            self.active_ip[mask1] = _rand_ip(n1, self.device)
            self.steps_since_ip[mask1] = 0.0
            self.budget[mask1] += config.COST_MTD_IP
            self.t_cost_ip[mask1] = -config.COST_MTD_IP

        mask2 = (a_mtd == 2)
        if mask2.any():
            n2 = mask2.sum().item()
            self.active_port[mask2] = _rand_port(n2, self.device)
            self.steps_since_pt[mask2] = 0.0
            self.budget[mask2] += config.COST_MTD_PORT
            self.t_cost_pt[mask2] = -config.COST_MTD_PORT

        mask3 = (a_mtd == 3)
        if mask3.any():
            self.decoy_on[mask3] = True
            self.decoy_ip[mask3] = (self.active_ip[mask3] + torch.randint_like(self.active_ip[mask3], low=1, high=max(2, config.NUM_IPS))) % config.NUM_IPS
            self.decoy_pt[mask3] = (self.active_port[mask3] + torch.randint_like(self.active_port[mask3], low=1, high=max(2, config.NUM_PORTS))) % config.NUM_PORTS
            self.budget[mask3] += config.COST_MTD_DECOY
            self.t_cost_decoy[mask3] = -config.COST_MTD_DECOY

        mask4 = (a_mtd == 4)
        if mask4.any():
            topk = torch.randint(low=0, high=config.NUM_IPS, size=(mask4.sum(),), device=self.device)
            self.bl_ips[mask4, topk] = torch.clamp(self.bl_ips[mask4, topk] + 1.0, max=1.0)
            self.budget[mask4] += config.COST_MTD_BL
            self.t_cost_bl[mask4] = -config.COST_MTD_BL

        self.last_mtd = a_mtd
        self.bl_ips.mul_(0.98)

    @torch.no_grad()
    def _do_seeker(self, a_seek: torch.Tensor):
        n = self.n
        breach  = torch.zeros(n, device=self.device, dtype=torch.bool)
        d_hit   = torch.zeros(n, device=self.device, dtype=torch.bool)
        blocked = torch.zeros(n, device=self.device, dtype=torch.bool)
        cost    = torch.zeros(n, device=self.device, dtype=DTYPE)

        m0 = (a_seek == 0)
        if m0.any():
            H_post, _, _ = self.nmap.scan_ip(self.steps_since_ip[m0], self.H_ip[m0])
            self.H_ip[m0] = H_post
            cost[m0] += config.COST_SEEKER_SCAN_IP

        m1 = (a_seek == 1)
        if m1.any():
            H_post, _, _ = self.nmap.scan_port(self.steps_since_pt[m1], self.H_pt[m1])
            self.H_pt[m1] = H_post
            cost[m1] += config.COST_SEEKER_SCAN_PT

        m2 = (a_seek == 2)
        if m2.any():
            H_post, _, _ = self.nmap.stealth_scan(self.steps_since_ip[m2], self.H_ip[m2])
            self.H_ip[m2] = H_post
            cost[m2] += config.COST_SEEKER_STEALTH

        m3 = (a_seek == 3)
        if m3.any():
            succ = self.nmap.decoy_probe(self.decoy_on[m3].float())
            self.H_ip[m3] = torch.clamp(self.H_ip[m3] - succ.float()*0.1, min=0.0)
            self.H_pt[m3] = torch.clamp(self.H_pt[m3] - succ.float()*0.1, min=0.0)
            cost[m3] += config.COST_SEEKER_PROBE

        m4 = (a_seek == 4)
        if m4.any(): cost[m4] += config.COST_SEEKER_EVADE

        base = 5
        m_ip = (a_seek >= base) & (a_seek < base + config.NUM_IPS)
        if m_ip.any():
            tgt_ip = a_seek[m_ip] - base
            tgt_pt = self.active_port[m_ip]
            bl = self.bl_ips[m_ip, tgt_ip] > 0.5
            blocked[m_ip] |= bl
            not_bl = ~bl
            is_decoy = not_bl & self.decoy_on[m_ip] & (tgt_ip == self.decoy_ip[m_ip]) & (tgt_pt == self.decoy_pt[m_ip])
            d_hit[m_ip] |= is_decoy
            real = not_bl & ~is_decoy & (tgt_ip == self.active_ip[m_ip]) & (tgt_pt == self.active_port[m_ip])
            p = torch.clamp(torch.full_like(self.H_ip[m_ip], config.ATTACK_BASE_P) + 0.25*(1.0 - self.H_ip[m_ip]), 0.01, 0.99)
            succ = (torch.rand_like(p) < p) & real
            breach[m_ip] |= succ
            cost[m_ip] += config.COST_SEEKER_ATTACK

        base2 = base + config.NUM_IPS
        m_pt = (a_seek >= base2) & (a_seek < base2 + config.NUM_PORTS)
        if m_pt.any():
            tgt_ip = self.active_ip[m_pt]
            tgt_pt = a_seek[m_pt] - base2
            bl = self.bl_ips[m_pt, tgt_ip] > 0.5
            blocked[m_pt] |= bl
            not_bl = ~bl
            is_decoy = not_bl & self.decoy_on[m_pt] & (tgt_ip == self.decoy_ip[m_pt]) & (tgt_pt == self.decoy_pt[m_pt])
            d_hit[m_pt] |= is_decoy
            real = not_bl & ~is_decoy & (tgt_ip == self.active_ip[m_pt]) & (tgt_pt == self.active_port[m_pt])
            p = torch.clamp(torch.full_like(self.H_pt[m_pt], config.ATTACK_BASE_P) + 0.25*(1.0 - self.H_pt[m_pt]), 0.01, 0.99)
            succ = (torch.rand_like(p) < p) & real
            breach[m_pt] |= succ
            cost[m_pt] += config.COST_SEEKER_ATTACK

        return breach, d_hit, blocked, cost

    @torch.no_grad()
    def step(self, a_mtd: torch.Tensor, a_seek: torch.Tensor):
        mtd_reward = torch.full((self.n,), config.COST_MTD_STEP, device=self.device, dtype=DTYPE)

        # 1) MTD
        self._do_mtd(a_mtd)

        # 2) Seeker
        breach, d_hit, blocked, s_cost = self._do_seeker(a_seek)

        # 3) 보상
        seeker_reward = -s_cost.clone()
        mtd_reward += torch.where(blocked, torch.tensor(config.REWARD_MTD_BLOCK, device=self.device), torch.tensor(0.0, device=self.device))
        seeker_reward += torch.where(blocked, torch.tensor(config.COST_SEEKER_BLK, device=self.device), torch.tensor(0.0, device=self.device))

        mtd_reward += torch.where(d_hit, torch.tensor(config.REWARD_MTD_DECOY, device=self.device), torch.tensor(0.0, device=self.device))
        seeker_reward += torch.where(d_hit, torch.tensor(-config.COST_SEEKER_PROBE, device=self.device), torch.tensor(0.0, device=self.device))

        mtd_reward += torch.where(breach, torch.tensor(config.REWARD_MTD_BREACH, device=self.device), torch.tensor(0.0, device=self.device))
        seeker_reward += torch.where(breach, torch.tensor(config.REW_SEEKER_BREACH, device=self.device), torch.tensor(0.0, device=self.device))

        # 4) Attack-surface 지표
        self.as_exp = 0.9*self.as_exp + 0.1*(1.0 - 0.5*(self.H_ip + self.H_pt))
        moved_ip = (self.steps_since_ip == 0.0).float()
        moved_pt = (self.steps_since_pt == 0.0).float()
        self.as_var = 0.9*self.as_var + 0.1*(0.5*moved_ip + 0.5*moved_pt)

        # 5) 지표/마스크/비용 집계
        scans   = ((a_seek == 0) | (a_seek == 1))
        stealth = (a_seek == 2)
        probe   = (a_seek == 3)
        attacks = (a_seek >= 5)

        cost_total = (self.t_cost_ip + self.t_cost_pt + self.t_cost_decoy + self.t_cost_bl + config.COST_MTD_STEP)

        self.last_stats = dict(
            breach_rate=float(breach.float().mean().item()),
            block_rate=float(blocked.float().mean().item()),
            decoy_rate=float(d_hit.float().mean().item()),
            scan_rate=float(scans.float().mean().item()),
            stealth_rate=float(stealth.float().mean().item()),
            probe_rate=float(probe.float().mean().item()),
            attack_rate=float(attacks.float().mean().item()),
            ip_move_rate=float((self.steps_since_ip==0).float().mean().item()),
            pt_move_rate=float((self.steps_since_pt==0).float().mean().item()),
            avg_budget=float(self.budget.mean().item()),
            as_exp=float(self.as_exp.mean().item()),
            as_var=float(self.as_var.mean().item()),
            cost_ip=float(self.t_cost_ip.mean().item()),
            cost_pt=float(self.t_cost_pt.mean().item()),
            cost_decoy=float(self.t_cost_decoy.mean().item()),
            cost_bl=float(self.t_cost_bl.mean().item()),
            cost_total=float(cost_total.mean().item()),
        )
        self.last_masks = dict(breach=breach.detach().clone(), block=blocked.detach().clone(), decoy=d_hit.detach().clone())

        done = breach.clone().float()
        return self._state(), mtd_reward, seeker_reward, done
