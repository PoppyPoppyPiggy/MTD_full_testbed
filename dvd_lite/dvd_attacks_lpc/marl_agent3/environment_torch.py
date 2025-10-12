# environment_torch.py
import torch
from environment import MTDSeekerEnv

class MTDSeekerEnvTorch:
    def __init__(self, n_envs: int, device: torch.device):
        self.env = MTDSeekerEnv(n_envs)
        self.device = device
        self.state_dim = self.env.state_dim
        self.mtd_n = self.env.mtd_n
        self.seeker_n = self.env.seeker_n

    def reset(self):
        s = self.env.reset()
        return torch.from_numpy(s).to(self.device)

    def step(self, mtd_a: torch.Tensor, seeker_a: torch.Tensor):
        mtd_a_np = mtd_a.cpu().numpy()
        seeker_a_np = seeker_a.cpu().numpy()

        s_next, mtd_r, sk_r, done = self.env.step(mtd_a_np, seeker_a_np)

        s_next_pt = torch.from_numpy(s_next).to(self.device)
        mtd_r_pt = torch.from_numpy(mtd_r).to(self.device)
        sk_r_pt = torch.from_numpy(sk_r).to(self.device)
        done_pt = torch.from_numpy(done).to(self.device)

        return s_next_pt, mtd_r_pt, sk_r_pt, done_pt

    @property
    def last_stats(self):
        return self.env.last_stats
    
    @property
    def H_ip(self):
        return torch.from_numpy(self.env.H_ip).to(self.device)

    @property
    def H_pt(self):
        return torch.from_numpy(self.env.H_pt).to(self.device)