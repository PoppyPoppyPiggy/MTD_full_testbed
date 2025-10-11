# ppo_agent.py
import torch, torch.nn as nn
from torch.optim import Adam
import config
from networks import ActorCritic

class Buffer:
    def __init__(self, cap, state_dim, device):
        self.device = device
        self.s = torch.zeros((cap, state_dim), dtype=torch.float32, device=device)
        self.a = torch.zeros((cap,), dtype=torch.long,   device=device)
        self.l = torch.zeros((cap,), dtype=torch.float32, device=device)
        self.r = torch.zeros((cap,), dtype=torch.float32, device=device)
        self.v = torch.zeros((cap,), dtype=torch.float32, device=device)
        self.d = torch.zeros((cap,), dtype=torch.float32, device=device)
        self.ptr = 0

    def add_batch(self, S, A, LOGP, R, V, D):
        B = A.shape[0]
        end = self.ptr + B
        self.s[self.ptr:end].copy_(S)
        self.a[self.ptr:end].copy_(A)
        self.l[self.ptr:end].copy_(LOGP)
        self.r[self.ptr:end].copy_(R)
        self.v[self.ptr:end].copy_(V)
        self.d[self.ptr:end].copy_(D)
        self.ptr = end

    def slice(self):
        return self.s[:self.ptr], self.a[:self.ptr], self.l[:self.ptr], self.r[:self.ptr], self.v[:self.ptr], self.d[:self.ptr]

class PPO:
    def __init__(self, state_dim, action_dim, device):
        self.device = device

        # 1) base / old 생성 및 동기화
        self.base = ActorCritic(state_dim, action_dim).to(device)   # 학습 대상
        self.old  = ActorCritic(state_dim, action_dim).to(device)   # 타깃(행동 샘플링)
        self.old.load_state_dict(self.base.state_dict())

        # 2) forward 가속용 컴파일 래퍼(exec)
        if config.USE_COMPILE and hasattr(torch, "compile"):
            try:
                self.exec = torch.compile(self.base, mode="max-autotune")
            except Exception:
                self.exec = self.base
        else:
            self.exec = self.base

        # 3) 옵티마이저는 base 파라미터에 연결
        self.opt = Adam(self.base.parameters(), lr=config.LR)
        self.vloss = nn.MSELoss()
        self.scaler = torch.amp.GradScaler('cuda', enabled=(config.USE_AMP and device.type=="cuda"))

    @torch.no_grad()
    def act(self, s):
        return self.old.act(s)

    def update(self, buf: Buffer):
        s,a,logp_old,r,v_old,d = buf.slice()

        # --------- GAE ----------
        with torch.no_grad():
            adv = torch.zeros_like(r, device=self.device)
            gae = 0.0
            for t in reversed(range(len(r))):
                not_done = (d[t] < 0.5)
                next_v = v_old[t+1] if (t+1 < len(r) and (d[t] < 0.5)) else 0.0
                delta = r[t] + config.GAMMA * next_v - v_old[t]
                gae = delta + config.LAMBDA * config.GAMMA * (1.0 if not_done else 0.0) * gae
                adv[t] = gae
            ret = adv + v_old
            adv = (adv - adv.mean())/(adv.std()+1e-8)

        idx = torch.randperm(len(r), device=self.device)
        for _ in range(config.EPOCHS):
            for i in range(0, len(r), config.MB_SIZE):
                b = idx[i:i+config.MB_SIZE]
                with torch.amp.autocast(
                    device_type="cuda", dtype=torch.float16,
                    enabled=(config.USE_AMP and self.device.type=="cuda")
                ):
                    # forward는 exec(컴파일 래퍼)로 수행
                    logp, v, ent = self.exec.evaluate(s[b], a[b])
                    ratio = torch.exp(logp - logp_old[b])
                    surr1 = ratio * adv[b]
                    surr2 = torch.clamp(ratio, 1-config.EPS_CLIP, 1+config.EPS_CLIP) * adv[b]
                    pol_loss = -torch.min(surr1, surr2).mean()
                    val_loss = self.vloss(v, ret[b]).mean()
                    loss = pol_loss + config.VAL_COEF*val_loss - config.ENT_COEF*ent.mean()

                self.opt.zero_grad(set_to_none=True)
                self.scaler.scale(loss).backward()
                nn.utils.clip_grad_norm_(self.base.parameters(), config.MAX_GRAD_NORM)
                self.scaler.step(self.opt)
                self.scaler.update()

        # 4) base → old 로 가중치 동기화
        self.old.load_state_dict(self.base.state_dict())
        buf.ptr = 0
