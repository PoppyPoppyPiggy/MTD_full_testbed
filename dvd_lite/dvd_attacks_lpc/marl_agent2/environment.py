# environment.py
import numpy as np
import config
from nmap_emulator import NmapEmulator

class MTDSeekerEnv:
    """
    MTD–Seeker War Game (벡터화)
    상태: [active_ip_norm, active_pt_norm, decoy_on, decoy_ip_norm, decoy_pt_norm,
          last_mtd_norm, blacklist[NUM_IPS], decoy_ident, budget_norm,
          ip_cd_norm, pt_cd_norm, as_exposure]
    """
    def __init__(self, n_envs:int):
        self.n = n_envs
        self.num_ips = config.NUM_IPS
        self.num_pts = config.NUM_PORTS
        self.rng = np.random.default_rng()
        self.nmap = NmapEmulator(self.rng)

        # surface
        self.ip = np.zeros(self.n, dtype=np.int32)
        self.pt = np.zeros(self.n, dtype=np.int32)
        self.decoy = np.zeros(self.n, dtype=np.bool_)
        self.decoy_ip = np.full(self.n, -1, dtype=np.int32)
        self.decoy_pt = np.full(self.n, -1, dtype=np.int32)

        # MTD state
        self.blacklist = np.zeros((self.n, self.num_ips), dtype=np.float32)
        self.last_mtd = np.full(self.n, -1, dtype=np.int32)
        self.steps = np.zeros(self.n, dtype=np.int32)
        self.ip_cd = np.zeros(self.n, dtype=np.int32)
        self.pt_cd = np.zeros(self.n, dtype=np.int32)
        self.budget = np.zeros(self.n, dtype=np.float32)
        self.steps_since_ip = np.zeros(self.n, dtype=np.int32)
        self.steps_since_pt = np.zeros(self.n, dtype=np.int32)

        # Seeker beliefs & timers
        self.H_ip = np.full(self.n, config.LOG_N_IPS, dtype=np.float32)
        self.H_pt = np.full(self.n, config.LOG_N_PTS, dtype=np.float32)
        self.last_scan_ip = np.full(self.n, -1, dtype=np.int32)
        self.last_scan_pt = np.full(self.n, -1, dtype=np.int32)
        self.evade_timer = np.zeros(self.n, dtype=np.int32)

        # decoy identify memory
        self.decoy_ident = np.zeros(self.n, dtype=np.bool_)
        self.decoy_ident_t = np.zeros(self.n, dtype=np.int32)
        self.decoy_ident_s = np.zeros(self.n, dtype=np.float32)

        # metrics
        self.as_exp = np.ones(self.n, dtype=np.float32)
        self.as_exp_prev = np.ones(self.n, dtype=np.float32)
        self.as_var = np.zeros(self.n, dtype=np.float32)

        # telemetry
        self.t_cost_ip = np.zeros(self.n, dtype=np.float32)
        self.t_cost_pt = np.zeros(self.n, dtype=np.float32)
        self.t_cost_decoy = np.zeros(self.n, dtype=np.float32)
        self.t_cost_bl = np.zeros(self.n, dtype=np.float32)
        self.t_scan = np.zeros(self.n, dtype=np.int32)
        self.t_stealth = np.zeros(self.n, dtype=np.int32)
        self.t_probe = np.zeros(self.n, dtype=np.int32)
        self.t_evade = np.zeros(self.n, dtype=np.int32)
        self.t_attack = np.zeros(self.n, dtype=np.int32)
        self.t_breach = np.zeros(self.n, dtype=np.int32)
        self.t_block = np.zeros(self.n, dtype=np.int32)
        self.t_decoyhit = np.zeros(self.n, dtype=np.int32)

        # action spaces
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
        self.t_cost_ip[:] = 0.0; self.t_cost_pt[:] = 0.0; self.t_cost_decoy[:] = 0.0; self.t_cost_bl[:] = 0.0
        self.t_scan[:] = self.t_stealth[:] = self.t_probe[:] = self.t_evade[:] = 0
        self.t_attack[:] = self.t_breach[:] = self.t_block[:] = self.t_decoyhit[:] = 0
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

        # timers
        self.ip_cd = np.maximum(0, self.ip_cd-1)
        self.pt_cd = np.maximum(0, self.pt_cd-1)
        self.steps_since_ip += 1; self.steps_since_pt += 1
        self.evade_timer = np.maximum(0, self.evade_timer-1)

        # decay
        on = self.decoy_ident & (self.decoy_ident_t>0)
        self.decoy_ident_t[on] -= 1
        self.decoy_ident_s[on] *= 0.98
        off = self.decoy_ident_t<=0
        self.decoy_ident[off] = False; self.decoy_ident_s[off] = 0.0
        self.blacklist *= 0.9

        # --- MTD actions ---
        mask_ip = (mtd_a==1) & (self.ip_cd==0) & (self.budget>0)
        mask_pt = (mtd_a==2) & (self.pt_cd==0) & (self.budget>0)
        mask_dc = (mtd_a==3) & (self.budget>0)
        mask_bl = (mtd_a==4) & (self.budget>0)

        if mask_ip.any():
            idx = np.where(mask_ip)[0]
            prev = self.ip[idx].copy()
            self.ip[idx] = self._rand_ip(idx.size)
            dist = np.abs(self.ip[idx] - prev) / max(1, self.num_ips-1)
            extra = -config.SWITCH_COST * dist
            mtd_r[idx] += config.COST_MTD_IP + extra
            self.t_cost_ip[idx] += -(config.COST_MTD_IP + extra)
            self.budget[idx] -= config.BUDGET_FACTOR * (-config.COST_MTD_IP)
            self.ip_cd[idx] = config.MTD_IP_CD
            self.steps_since_ip[idx] = 0
            # 디코이 식별 무효화 확률
            reset = self.rng.random(idx.size) < 0.6
            ridx = idx[reset]; self.decoy_ident[ridx]=False; self.decoy_ident_t[ridx]=0; self.decoy_ident_s[ridx]=0.0

        if mask_pt.any():
            idx = np.where(mask_pt)[0]
            prev = self.pt[idx].copy()
            self.pt[idx] = self._rand_pt(idx.size)
            dist = np.abs(self.pt[idx] - prev) / max(1, self.num_pts-1)
            extra = -config.SWITCH_COST * dist
            mtd_r[idx] += config.COST_MTD_PORT + extra
            self.t_cost_pt[idx] += -(config.COST_MTD_PORT + extra)
            self.budget[idx] -= config.BUDGET_FACTOR * (-config.COST_MTD_PORT)
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
            self.t_cost_decoy[idx] += -config.COST_MTD_DECOY
            self.budget[idx] -= config.BUDGET_FACTOR * (-config.COST_MTD_DECOY)

        if mask_bl.any():
            idx = np.where(mask_bl)[0]
            valid = self.last_scan_ip[idx] >= 0
            if valid.any():
                sub = idx[valid]
                self.blacklist[sub, self.last_scan_ip[sub]] = 1.0
            mtd_r[idx] += config.COST_MTD_BL
            self.t_cost_bl[idx] += -config.COST_MTD_BL
            self.budget[idx] -= config.BUDGET_FACTOR * (-config.COST_MTD_BL)

        # --- Seeker actions (Nmap emulator 기반) ---
        a = seeker_a
        m_scan_ip   = (a==0)
        m_scan_pt   = (a==1)
        m_attack    = (a>=2) & (a<self.seeker_stealth)
        m_stealth   = (a==self.seeker_stealth)
        m_probe     = (a==self.seeker_probe)
        m_evade     = (a==self.seeker_evade)

        evade_fac = np.where(self.evade_timer>0, config.EVADE_EFFECT, 1.0)

        if m_scan_ip.any():
            idx = np.where(m_scan_ip)[0]
            post, info, detected = self.nmap.scan_ip(self.steps_since_ip[idx], self.H_ip[idx])
            self.H_ip[idx] = post; sk_det = detected
            sk_r = sk_r  # noqa: keeps reference
            sk_r[idx] += config.COST_SEEKER_SCAN_IP + 2.2*info
            mtd_r[idx] += config.REWARD_MTD_SCAN_DET * evade_fac[idx]
            self.last_scan_ip[idx] = self._rand_ip(idx.size)
            self.t_scan[idx] += 1

        if m_scan_pt.any():
            idx = np.where(m_scan_pt)[0]
            post, info, detected = self.nmap.scan_port(self.steps_since_pt[idx], self.H_pt[idx])
            self.H_pt[idx] = post
            sk_r[idx] += config.COST_SEEKER_SCAN_PT + 2.2*info
            mtd_r[idx] += config.REWARD_MTD_SCAN_DET * evade_fac[idx]
            self.last_scan_pt[idx] = self._rand_pt(idx.size)
            self.t_scan[idx] += 1

        if m_stealth.any():
            idx = np.where(m_stealth)[0]
            post, info, detected = self.nmap.stealth_scan(self.steps_since_ip[idx], self.H_ip[idx])
            self.H_ip[idx] = post
            sk_r[idx] += config.COST_SEEKER_STEALTH + 2.2*info
            if detected:
                mtd_r[idx] += config.REWARD_MTD_SCAN_DET * config.STEALTH_DET_FACTOR * evade_fac[idx]
            self.last_scan_ip[idx] = self._rand_ip(idx.size)
            self.t_stealth[idx] += 1

        if m_probe.any():
            idx = np.where(m_probe)[0]
            succ = self.nmap.decoy_probe(self.decoy[idx])
            ok = idx[succ]
            if ok.size>0:
                self.decoy_ident[ok]=True
                self.decoy_ident_t[ok]=40
                self.decoy_ident_s[ok]=1.0
                sk_r[ok] += config.REW_SEEKER_DECOY_ID
            sk_r[idx] += config.COST_SEEKER_PROBE
            self.t_probe[idx] += 1

        if m_evade.any():
            idx = np.where(m_evade)[0]
            self.evade_timer[idx] = config.EVADE_DUR
            sk_r[idx] += config.COST_SEEKER_EVADE
            self.t_evade[idx] += 1

        # 공격
        breached = np.zeros(self.n, dtype=bool)
        decoy_hit = np.zeros(self.n, dtype=bool)
        blocked = np.zeros(self.n, dtype=bool)
        if m_attack.any():
            idx = np.where(m_attack)[0]
            aa = a[idx]
            ip_sel = (aa>=self.seeker_base_ip) & (aa<self.seeker_base_ip+self.num_ips)
            pt_sel = (aa>=self.seeker_base_pt) & (aa<self.seeker_base_pt+self.num_pts)
            tgt_ip = np.empty_like(aa); tgt_pt = np.empty_like(aa)
            if ip_sel.any():
                ii = np.where(ip_sel)[0]
                tgt_ip[ii] = aa[ii] - self.seeker_base_ip
                tgt_pt[ii] = self.pt[idx[ii]]
            if pt_sel.any():
                pp = np.where(pt_sel)[0]
                tgt_ip[pp] = self.ip[idx[pp]]
                tgt_pt[pp] = aa[pp] - self.seeker_base_pt

            blv = self.blacklist[idx, tgt_ip]
            blk = blv > 0.5
            dcy = self.decoy[idx] & (tgt_ip==self.decoy_ip[idx]) & (tgt_pt==self.decoy_pt[idx])
            toblk = dcy & (self.decoy_ident_s[idx]>0.5)
            dcy[toblk] = False; blk[toblk] = True

            real = (~blk) & (~dcy) & (tgt_ip==self.ip[idx]) & (tgt_pt==self.pt[idx])
            H = (self.H_ip[idx] + self.H_pt[idx]) / max(1e-6, config.NORM_H)
            cert = np.exp(-config.BETA_UNC * H)
            p = config.ATTACK_BASE_P * cert
            rnd = self.rng.random(idx.size)
            br = real & (rnd < p)

            blocked[idx] = blk; decoy_hit[idx] = dcy; breached[idx] = br
            sk_r[idx] += config.COST_SEEKER_ATTACK
            self.t_attack[idx] += 1

        # 이벤트 보상
        mtd_r[blocked] += config.REWARD_MTD_BLOCK
        sk_r[blocked] += config.COST_SEEKER_BLK
        self.t_block[blocked] += 1
        mtd_r[decoy_hit] += config.REWARD_MTD_DECOY
        sk_r[decoy_hit] += -120.0
        self.t_decoyhit[decoy_hit] += 1
        mtd_r[breached] += config.REWARD_MTD_BREACH
        sk_r[breached] += config.REW_SEEKER_BREACH
        self.t_breach[breached] += 1

        # 표면 메트릭
        self._update_as()
        mtd_r += -1.0*self.as_exp + 0.40*self.as_var

        # 종료 & 리셋
        done = breached | (self.steps >= config.MAX_STEPS_PER_EP)
        if done.any():
            d = np.where(done)[0]
            self.ip[d] = self._rand_ip(d.size)
            self.pt[d] = self._rand_pt(d.size)
            self.decoy[d]=False; self.decoy_ip[d]=-1; self.decoy_pt[d]=-1
            self.blacklist[d,:]=0.0; self.last_mtd[d]=-1; self.steps[d]=0
            self.ip_cd[d]=0; self.pt_cd[d]=0; self.budget[d]=config.BUDGET_INIT
            self.steps_since_ip[d]=1000; self.steps_since_pt[d]=1000
            self.H_ip[d]=config.LOG_N_IPS; self.H_pt[d]=config.LOG_N_PTS
            self.last_scan_ip[d]=-1; self.last_scan_pt[d]=-1; self.evade_timer[d]=0
            self.as_exp[d]=1.0; self.as_exp_prev[d]=1.0; self.as_var[d]=0.0

        return self._state(), mtd_r, sk_r, done.astype(np.float32)
