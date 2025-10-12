# environment.py
import numpy as np
import config
from nmap_emulator import NmapEmulator

class MTDSeekerEnv:
    def __init__(self, n_envs:int):
        self.n = n_envs
        self.num_ips = config.NUM_IPS
        self.num_pts = config.NUM_PORTS
        self.rng = np.random.default_rng(config.SEED)
        self.nmap = NmapEmulator(self.rng)

        self.ip = np.zeros(self.n, dtype=np.int32)
        self.pt = np.zeros(self.n, dtype=np.int32)
        self.decoy = np.zeros(self.n, dtype=np.bool_)
        self.decoy_ip = np.full(self.n, -1, dtype=np.int32)
        self.decoy_pt = np.full(self.n, -1, dtype=np.int32)

        self.blacklist = np.zeros((self.n, self.num_ips), dtype=np.float32)
        self.last_mtd = np.full(self.n, -1, dtype=np.int32)
        self.steps = np.zeros(self.n, dtype=np.int32)
        self.ip_cd = np.zeros(self.n, dtype=np.int32)
        self.pt_cd = np.zeros(self.n, dtype=np.int32)
        self.budget = np.zeros(self.n, dtype=np.float32)
        self.steps_since_ip = np.zeros(self.n, dtype=np.int32)
        self.steps_since_pt = np.zeros(self.n, dtype=np.int32)

        self.H_ip = np.full(self.n, config.LOG_N_IPS, dtype=np.float32)
        self.H_pt = np.full(self.n, config.LOG_N_PTS, dtype=np.float32)
        self.last_scan_ip = np.full(self.n, -1, dtype=np.int32)
        self.last_scan_pt = np.full(self.n, -1, dtype=np.int32)
        self.evade_timer = np.zeros(self.n, dtype=np.int32)

        self.decoy_ident = np.zeros(self.n, dtype=np.bool_)
        self.decoy_ident_t = np.zeros(self.n, dtype=np.int32)
        self.decoy_ident_s = np.zeros(self.n, dtype=np.float32)

        self.as_exp = np.ones(self.n, dtype=np.float32)
        self.as_exp_prev = np.ones(self.n, dtype=np.float32)
        self.as_var = np.zeros(self.n, dtype=np.float32)
        
        self.last_stats = {}

        self.mtd_n = 5
        self.seeker_base_ip = 2
        self.seeker_base_pt = 2 + self.num_ips
        self.seeker_stealth = 2 + self.num_ips + self.num_pts
        self.seeker_probe = self.seeker_stealth + 1
        self.seeker_evade = self.seeker_probe + 1
        self.seeker_n = self.seeker_evade + 1

        self.state_dim = 11 + self.num_ips
        self.reset()

    def _rand_ip(self, k): return self.rng.integers(0, self.num_ips, size=k)
    def _rand_pt(self, k): return self.rng.integers(0, self.num_pts, size=k)

    def _compute_as(self):
        base = np.ones(self.n, dtype=np.float32)
        decoy_red = np.where(self.decoy, config.AS_DECOY_REDUCE, 0.0)
        bl = self.blacklist.mean(axis=1) * config.AS_BL_FACTOR
        exp = base - decoy_red - bl
        return np.clip(exp, 0.0, 1.0)

    def _update_as(self):
        self.as_exp_prev = self.as_exp
        self.as_exp = self._compute_as()
        delta = np.abs(self.as_exp - self.as_exp_prev)
        self.as_var = (1-config.AS_ALPHA)*self.as_var + config.AS_ALPHA*delta

    def reset(self):
        self.ip[:] = self._rand_ip(self.n)
        self.pt[:] = self._rand_pt(self.n)
        self.decoy[:] = False; self.decoy_ip[:] = -1; self.decoy_pt[:] = -1
        self.blacklist[:, :] = 0.0; self.last_mtd[:] = -1
        self.steps[:] = 0; self.ip_cd[:] = 0; self.pt_cd[:] = 0
        self.budget[:] = config.BUDGET_INIT
        self.steps_since_ip[:] = 1000; self.steps_since_pt[:] = 1000
        self.H_ip[:] = config.LOG_N_IPS; self.H_pt[:] = config.LOG_N_PTS
        self.last_scan_ip[:] = -1; self.last_scan_pt[:] = -1
        self.evade_timer[:] = 0
        self.decoy_ident[:] = False; self.decoy_ident_t[:] = 0; self.decoy_ident_s[:] = 0.0
        self.as_exp[:] = 1.0; self.as_exp_prev[:] = 1.0; self.as_var[:] = 0.0
        return self._state()

    def _state(self):
        s = np.zeros((self.n, self.state_dim), dtype=np.float32)
        s[:,0] = self.ip / self.num_ips
        s[:,1] = self.pt / self.num_pts
        s[:,2] = self.decoy.astype(np.float32)
        s[:,3] = np.where(self.decoy, self.decoy_ip / self.num_ips, -1.0)
        s[:,4] = np.where(self.decoy, self.decoy_pt / self.num_pts, -1.0)
        s[:,5] = np.where(self.last_mtd>=0, self.last_mtd/self.mtd_n, -1.0)
        s[:,6:6+self.num_ips] = self.blacklist
        s[:,6+self.num_ips] = self.decoy_ident.astype(np.float32)
        s[:,7+self.num_ips] = np.clip(self.budget/config.BUDGET_INIT,0.0,1.0)
        s[:,8+self.num_ips] = np.clip(self.ip_cd/max(1,config.MTD_IP_CD),0.0,1.0)
        s[:,9+self.num_ips]  = np.clip(self.pt_cd/max(1,config.MTD_PT_CD),0.0,1.0)
        s[:,10+self.num_ips] = self.as_exp
        return s

    def step(self, mtd_a: np.ndarray, seeker_a: np.ndarray):
        self.steps += 1
        self.last_mtd = mtd_a.copy()
        mtd_r = np.full(self.n, config.COST_MTD_STEP, dtype=np.float32)
        sk_r  = np.zeros(self.n, dtype=np.float32)

        self.ip_cd = np.maximum(0, self.ip_cd-1)
        self.pt_cd = np.maximum(0, self.pt_cd-1)
        self.steps_since_ip += 1; self.steps_since_pt += 1
        self.evade_timer = np.maximum(0, self.evade_timer-1)

        on = self.decoy_ident & (self.decoy_ident_t>0)
        self.decoy_ident_t[on] -= 1
        self.decoy_ident_s[on] *= 0.98
        off = self.decoy_ident_t<=0
        self.decoy_ident[off] = False; self.decoy_ident_s[off] = 0.0
        self.blacklist *= 0.9

        mask_ip = (mtd_a==1) & (self.ip_cd==0) & (self.budget > -config.COST_MTD_IP)
        mask_pt = (mtd_a==2) & (self.pt_cd==0) & (self.budget > -config.COST_MTD_PORT)
        mask_dc = (mtd_a==3) & (self.budget > -config.COST_MTD_DECOY)
        mask_bl = (mtd_a==4) & (self.budget > -config.COST_MTD_BL)

        ip_moved = np.zeros(self.n, dtype=bool)
        pt_moved = np.zeros(self.n, dtype=bool)

        if mask_ip.any():
            idx = np.where(mask_ip)[0]
            ip_moved[idx] = True
            prev = self.ip[idx].copy()
            self.ip[idx] = self._rand_ip(idx.size)
            dist = np.abs(self.ip[idx] - prev) / max(1, self.num_ips-1)
            extra = -config.SWITCH_COST * dist
            cost = config.COST_MTD_IP + extra
            mtd_r[idx] += cost
            self.budget[idx] += cost * config.BUDGET_FACTOR
            self.ip_cd[idx] = config.MTD_IP_CD
            self.steps_since_ip[idx] = 0
            reset = self.rng.random(idx.size) < 0.6
            ridx = idx[reset]; self.decoy_ident[ridx]=False; self.decoy_ident_t[ridx]=0; self.decoy_ident_s[ridx]=0.0

        if mask_pt.any():
            idx = np.where(mask_pt)[0]
            pt_moved[idx] = True
            prev = self.pt[idx].copy()
            self.pt[idx] = self._rand_pt(idx.size)
            dist = np.abs(self.pt[idx] - prev) / max(1, self.num_pts-1)
            extra = -config.SWITCH_COST * dist
            cost = config.COST_MTD_PORT + extra
            mtd_r[idx] += cost
            self.budget[idx] += cost * config.BUDGET_FACTOR
            self.pt_cd[idx] = config.MTD_PT_CD
            self.steps_since_pt[idx] = 0

        if mask_dc.any():
            idx = np.where(mask_dc)[0]
            no = idx[~self.decoy[idx]]
            if no.size>0:
                off_ip = self._rand_ip(no.size); off_pt = self._rand_pt(no.size)
                self.decoy[no]=True
                self.decoy_ip[no]=(self.ip[no]+off_ip)%self.num_ips
                self.decoy_pt[no]=(self.pt[no]+off_pt)%self.num_pts
            mtd_r[idx] += config.COST_MTD_DECOY
            self.budget[idx] += config.COST_MTD_DECOY * config.BUDGET_FACTOR

        if mask_bl.any():
            idx = np.where(mask_bl)[0]
            valid = self.last_scan_ip[idx] >= 0
            if valid.any():
                sub = idx[valid]
                self.blacklist[sub, self.last_scan_ip[sub]] = 1.0
            mtd_r[idx] += config.COST_MTD_BL
            self.budget[idx] += config.COST_MTD_BL * config.BUDGET_FACTOR

        a = seeker_a
        m_scan_ip   = (a==0)
        m_scan_pt   = (a==1)
        m_attack_ip = (a >= self.seeker_base_ip) & (a < self.seeker_base_pt)
        m_attack_pt = (a >= self.seeker_base_pt) & (a < self.seeker_stealth)
        m_attack    = m_attack_ip | m_attack_pt
        m_stealth   = (a==self.seeker_stealth)
        m_probe     = (a==self.seeker_probe)
        m_evade     = (a==self.seeker_evade)
        
        scanned = np.zeros(self.n, dtype=bool)
        stealthed = np.zeros(self.n, dtype=bool)
        probed = np.zeros(self.n, dtype=bool)
        attacked = np.zeros(self.n, dtype=bool)

        evade_fac = np.where(self.evade_timer>0, config.EVADE_EFFECT, 1.0)

        if m_scan_ip.any():
            idx = np.where(m_scan_ip)[0]; scanned[idx] = True
            post, info, detected = self.nmap.scan_ip(self.steps_since_ip[idx], self.H_ip[idx])
            self.H_ip[idx] = post
            sk_r[idx] += config.COST_SEEKER_SCAN_IP + 2.2*info
            if detected.any():
                det_idx = idx[detected]
                mtd_r[det_idx] += config.REWARD_MTD_SCAN_DET * evade_fac[det_idx]
            self.last_scan_ip[idx] = self._rand_ip(idx.size)

        if m_scan_pt.any():
            idx = np.where(m_scan_pt)[0]; scanned[idx] = True
            post, info, detected = self.nmap.scan_port(self.steps_since_pt[idx], self.H_pt[idx])
            self.H_pt[idx] = post
            sk_r[idx] += config.COST_SEEKER_SCAN_PT + 2.2*info
            if detected.any():
                det_idx = idx[detected]
                mtd_r[det_idx] += config.REWARD_MTD_SCAN_DET * evade_fac[det_idx]
            self.last_scan_pt[idx] = self._rand_pt(idx.size)

        if m_stealth.any():
            idx = np.where(m_stealth)[0]; stealthed[idx] = True
            post, info, detected = self.nmap.stealth_scan(self.steps_since_ip[idx], self.H_ip[idx])
            self.H_ip[idx] = post
            sk_r[idx] += config.COST_SEEKER_STEALTH + 2.2*info
            if detected.any():
                det_idx = idx[detected]
                mtd_r[det_idx] += config.REWARD_MTD_SCAN_DET * config.STEALTH_DET_FACTOR * evade_fac[det_idx]
            self.last_scan_ip[idx] = self._rand_ip(idx.size)

        if m_probe.any():
            idx = np.where(m_probe)[0]; probed[idx] = True
            succ = self.nmap.decoy_probe(self.decoy[idx])
            ok = idx[succ]
            if ok.size>0:
                self.decoy_ident[ok]=True
                self.decoy_ident_t[ok]=40
                self.decoy_ident_s[ok]=1.0
                sk_r[ok] += config.REW_SEEKER_DECOY_ID
            sk_r[idx] += config.COST_SEEKER_PROBE

        if m_evade.any():
            idx = np.where(m_evade)[0]
            self.evade_timer[idx] = config.EVADE_DUR
            sk_r[idx] += config.COST_SEEKER_EVADE

        breached = np.zeros(self.n, dtype=bool)
        decoy_hit = np.zeros(self.n, dtype=bool)
        blocked = np.zeros(self.n, dtype=bool)

        if m_attack.any():
            idx = np.where(m_attack)[0]; attacked[idx] = True
            aa = a[idx]
            tgt_ip = np.zeros_like(aa); tgt_pt = np.zeros_like(aa)

            ip_sel_mask = m_attack_ip[idx]
            if ip_sel_mask.any():
                ii = np.where(ip_sel_mask)[0]
                tgt_ip[ii] = aa[ii] - self.seeker_base_ip
                tgt_pt[ii] = self.pt[idx[ii]]

            pt_sel_mask = m_attack_pt[idx]
            if pt_sel_mask.any():
                pp = np.where(pt_sel_mask)[0]
                tgt_ip[pp] = self.ip[idx[pp]]
                tgt_pt[pp] = aa[pp] - self.seeker_base_pt

            blv = self.blacklist[idx, tgt_ip]
            is_blocked = blv * evade_fac[idx] > self.rng.random(idx.size)
            
            is_decoy_hit = self.decoy[idx] & (tgt_ip == self.decoy_ip[idx]) & (tgt_pt == self.decoy_pt[idx])
            is_decoy_hit[is_blocked] = False

            is_real_hit = (~is_blocked) & (~is_decoy_hit) & (tgt_ip == self.ip[idx]) & (tgt_pt == self.pt[idx])
            
            H = (self.H_ip[idx] + self.H_pt[idx]) / max(1e-6, config.NORM_H)
            cert = np.exp(-config.BETA_UNC * H)
            p = config.ATTACK_BASE_P * cert
            rnd = self.rng.random(idx.size)
            is_breached = is_real_hit & (rnd < p)

            blocked[idx] = is_blocked
            decoy_hit[idx] = is_decoy_hit
            breached[idx] = is_breached
            sk_r[idx] += config.COST_SEEKER_ATTACK

        if blocked.any():
            mtd_r[blocked] += config.REWARD_MTD_BLOCK
            sk_r[blocked] += config.COST_SEEKER_BLK
        if decoy_hit.any():
            mtd_r[decoy_hit] += config.REWARD_MTD_DECOY
            sk_r[decoy_hit] += -120.0
        if breached.any():
            mtd_r[breached] += config.REWARD_MTD_BREACH
            sk_r[breached] += config.REW_SEEKER_BREACH

        self._update_as()
        mtd_r += -1.0*self.as_exp + 0.40*self.as_var

        done = breached | (self.steps >= config.MAX_STEPS_PER_EP)
        if done.any():
            d_idx = np.where(done)[0]
            self.ip[d_idx] = self._rand_ip(d_idx.size)
            self.pt[d_idx] = self._rand_pt(d_idx.size)
            self.decoy[d_idx]=False; self.decoy_ip[d_idx]=-1; self.decoy_pt[d_idx]=-1
            self.blacklist[d_idx,:]=0.0; self.last_mtd[d_idx]=-1; self.steps[d_idx]=0
            self.ip_cd[d_idx]=0; self.pt_cd[d_idx]=0; self.budget[d_idx]=config.BUDGET_INIT
            self.steps_since_ip[d_idx]=1000; self.steps_since_pt[d_idx]=1000
            self.H_ip[d_idx]=config.LOG_N_IPS; self.H_pt[d_idx]=config.LOG_N_PTS
            self.last_scan_ip[d_idx]=-1; self.last_scan_pt[d_idx]=-1; self.evade_timer[d_idx]=0
            self.as_exp[d_idx]=1.0; self.as_exp_prev[d_idx]=1.0; self.as_var[d_idx]=0.0

        self.last_stats = {
            "breach_rate": breached.mean(), "block_rate": blocked.mean(), "decoy_rate": decoy_hit.mean(),
            "scan_rate": scanned.mean(), "stealth_rate": stealthed.mean(), "probe_rate": probed.mean(),
            "attack_rate": attacked.mean(), "ip_move_rate": ip_moved.mean(), "pt_move_rate": pt_moved.mean(),
            "avg_budget": self.budget.mean(), "as_exp": self.as_exp.mean(), "as_var": self.as_var.mean()
        }

        return self._state(), mtd_r, sk_r, done.astype(np.float32)