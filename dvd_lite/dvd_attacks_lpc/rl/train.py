#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MTD vs Seeker ARL Framework — v15.2 (Incentive & Bugfix)
- [수정] 기만(Decoy)에 대한 보상(REW_MTD_DECOY) 추가
- [수정] 기만 비용(COST_DECOY_RATIO) 하향 조정 (0.30 -> 0.15)
- [수정] Matplotlib 메모리 누수(RuntimeWarning) 버그 수정
- [수정] 상세 분석용 training_summary.json 생성 기능 탑재
"""

import os, sys, csv, math, json, time, argparse, random, pathlib, datetime as dt
from typing import Dict, Any, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torch.distributions import Categorical

# Matplotlib backend 설정
import matplotlib
SHOW = ("--show" in sys.argv or "--show" in os.environ.get("ARGV", ""))
if not SHOW:
    matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

# ===============================
# 1) Config
# ===============================
class Config:
    SEED = 42
    DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    LEVEL = "L15_Thesis_Optimized_v2" # 버전업 명시

    # 학습/검증 파라미터
    META_UPDATES = 500
    ROLLOUT_STEPS = 256
    VALIDATION_STEPS = 4096
    N_ENVS = 64

    # PPO
    LR = 3e-4; GAMMA = 0.99; GAE_LAMBDA = 0.95; K_EPOCHS = 10; EPS_CLIP = 0.2; MAX_GRAD_NORM = 0.5
    ENTROPY_COEF = 0.01

    # 환경: IP/Port 공간
    NUM_IPS = 16
    SCENARIO = {"COMMON_PORTS": [14550, 14551, 5760, 5600, 7777, 8888, 9000]}
    NUM_ENDPOINTS = NUM_IPS * len(SCENARIO["COMMON_PORTS"])

    # 동적 파라미터(Defender/Seeker)
    DYN_PARAMS = {
        "ip_cd":       {"base": 15.0, "min": 5.0,   "max": 60.0},
        "decoy_ratio": {"base": 0.10, "min": 0.0,   "max": 0.50},
        "bl_level":   {"base": 1.0,  "min": 0.0,   "max": 5.0},
    }
    SEEKER_PARAMS = {
        "attack_bias": {"base": 1.0,  "min": 0.5,  "max": 2.0},
        "scan_effort": {"base": 1.0,  "min": 0.5,  "max": 2.0},
    }

    # === [수정 1] Reward/Cost 가중치 ===
    COST_WEIGHT = 0.25
    REW_MTD_BLOCK = 1.0
    REW_MTD_DECOY = 1.0  # <-- [신설] 기만 성공 시 보상
    PENALTY_MTD_BREACH = -5.0
    PENALTY_MTD_KNOWLEDGE_LEAK = -2.0
    
    COST_MTD_ACTION = 0.05
    COST_SHUFFLE = 0.20
    COST_DECOY_RATIO = 0.15 # <-- [수정] 비용 하향 (0.30 -> 0.15)
    COST_BL_LEVEL = 0.15
    # ==================================

    KNOWLEDGE_ATTACK_P = 0.85
    BLIND_ATTACK_P = 0.05

    # 메타 액션(Defender/Seeker)
    MTD_META_ACTIONS = {
        0: ("ip_cd", 1.2),  1: ("ip_cd", 0.8),
        2: ("decoy_ratio", 1.2), 3: ("decoy_ratio", 0.8),
        4: ("bl_level", 1.0), 5: ("bl_level", -1.0),
        6: ("none", 1.0),
    }
    SEEKER_META_ACTIONS = {
        0: ("attack_bias", 1.2), 1: ("attack_bias", 0.8),
        2: ("scan_effort", 1.2), 3: ("scan_effort", 0.8),
        4: ("none", 1.0),
    }
    MTD_META_ACTION_DIM = len(MTD_META_ACTIONS)
    SEEKER_META_ACTION_DIM = len(SEEKER_META_ACTIONS)

    # 정적 MTD 레벨(비교 실험용)
    STATIC_MTD_LEVELS = {
        0: {"name": "L0 (Passive)",    "ip_cd": 60.0, "decoy_ratio": 0.00, "bl_level": 0.0},
        1: {"name": "L1 (Low)",        "ip_cd": 45.0, "decoy_ratio": 0.05, "bl_level": 1.0},
        2: {"name": "L2 (Medium)",     "ip_cd": 30.0, "decoy_ratio": 0.15, "bl_level": 2.0},
        3: {"name": "L3 (High)",       "ip_cd": 15.0, "decoy_ratio": 0.25, "bl_level": 3.0},
        4: {"name": "L4 (Very High)",  "ip_cd":  7.5, "decoy_ratio": 0.35, "bl_level": 4.0},
        5: {"name": "L5 (Max)",        "ip_cd":  5.0, "decoy_ratio": 0.50, "bl_level": 5.0},
    }
    SEEKER_BEHAVIOR_LEVELS = {
        0: {"name": "L0 (Naive)",      "scan_effort": 0.5, "attack_bias": 0.5},
        1: {"name": "L1 (Scanner)",    "scan_effort": 2.0, "attack_bias": 0.8},
        2: {"name": "L2 (Aggressive)", "scan_effort": 0.8, "attack_bias": 2.0},
        3: {"name": "L3 (ARL)",        "mode": "arl"},
    }

config = Config()

# ===============================
# 2) Utils / PPO
# ===============================
def set_seed(seed: int):
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed); torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True; torch.backends.cudnn.benchmark = False

def make_outdir(level: str) -> pathlib.Path:
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    outdir = pathlib.Path("results") / f"{ts}_{level}"
    (outdir / "figs").mkdir(parents=True, exist_ok=True)
    (outdir / "models").mkdir(parents=True, exist_ok=True)
    return outdir

class Buffer:
    def __init__(self, n_envs: int, rollout_steps: int, state_dim: int, device: torch.device):
        self.states = torch.zeros((rollout_steps, n_envs, state_dim), device=device)
        self.actions = torch.zeros((rollout_steps, n_envs), dtype=torch.long, device=device)
        self.log_probs = torch.zeros((rollout_steps, n_envs), device=device)
        self.rewards = torch.zeros((rollout_steps, n_envs), device=device)
        self.dones = torch.zeros((rollout_steps, n_envs), device=device)
        self.values = torch.zeros((rollout_steps, n_envs), device=device)
        self.rollout_steps, self.n_envs, self.device = rollout_steps, n_envs, device
        self.ptr = 0
    
    def add(self, s,a,r,d,logp,v):
        self.states[self.ptr] = s; self.actions[self.ptr] = a; self.rewards[self.ptr] = r
        self.dones[self.ptr] = d; self.log_probs[self.ptr] = logp; self.values[self.ptr] = v
        self.ptr = (self.ptr + 1) % self.rollout_steps
    
    def compute_returns_and_advantages(self, last_value, gamma, gae_lambda):
        advantages = torch.zeros_like(self.rewards)
        last_gae_lam = 0
        for t in reversed(range(self.rollout_steps)):
            if t == self.rollout_steps - 1:
                next_non_terminal, next_values = 1.0 - self.dones[t], last_value
            else:
                next_non_terminal, next_values = 1.0 - self.dones[t], self.values[t+1]
            delta = self.rewards[t] + gamma*next_values*next_non_terminal - self.values[t]
            advantages[t] = last_gae_lam = delta + gamma*gae_lambda*next_non_terminal*last_gae_lam
        returns = advantages + self.values
        return returns, advantages
    
    def get(self):
        return self.states.view(-1, self.states.size(-1)), self.actions.flatten(), self.log_probs.flatten()

class ActorCritic(nn.Module):
    def __init__(self, state_dim: int, action_dim: int):
        super().__init__()
        self.shared = nn.Sequential(nn.Linear(state_dim,128), nn.Tanh(), nn.Linear(128,128), nn.Tanh())
        self.actor = nn.Linear(128, action_dim)
        self.critic = nn.Linear(128, 1)
    
    def forward(self, s):
        x = self.shared(s)
        return Categorical(logits=self.actor(x)), self.critic(x).squeeze(-1)
    
    def act(self, s):
        dist, v = self.forward(s)
        a = dist.sample()
        return a, dist.log_prob(a), v

class PPO:
    def __init__(self, state_dim, action_dim, device, lr, eps_clip, entropy_coef):
        self.device, self.eps_clip, self.entropy_coef = device, eps_clip, entropy_coef
        self.policy = ActorCritic(state_dim, action_dim).to(device)
        self.opt = optim.Adam(self.policy.parameters(), lr=lr)
    
    def update(self, buf, returns, adv, k_epochs, max_grad_norm):
        s, a, old_lp = buf.get()
        returns, adv = returns.flatten(), adv.flatten()
        adv = (adv - adv.mean()) / (adv.std() + 1e-8)
        pl, vl, ent = 0.,0.,0.
        for _ in range(k_epochs):
            dist, values = self.policy(s)
            lp = dist.log_prob(a); entropy = dist.entropy().mean()
            ratios = torch.exp(lp - old_lp)
            s1, s2 = ratios*adv, torch.clamp(ratios, 1-self.eps_clip, 1+self.eps_clip)*adv
            policy_loss = -torch.min(s1, s2).mean()
            value_loss = F.mse_loss(values, returns)
            loss = policy_loss + 0.5*value_loss - self.entropy_coef*entropy
            self.opt.zero_grad(); loss.backward(); nn.utils.clip_grad_norm_(self.policy.parameters(), max_grad_norm); self.opt.step()
            pl += policy_loss.item(); vl += value_loss.item(); ent += entropy.item()
        return [pl/k_epochs, vl/k_epochs, ent/k_epochs]

# ===============================
# 3) 환경 (MTD/Seeker 상호작용)
# ===============================
class MTDSeekerEnvTorch:
    def __init__(self, n_envs, device, mtd_mode='arl', seeker_mode='arl', mtd_level=None, seeker_level=None, cti_params=None):
        self.n, self.device = int(n_envs), device
        self.mtd_mode, self.seeker_mode = mtd_mode, seeker_mode
        self.mtd_level, self.seeker_level = mtd_level, seeker_level
        self.cti_params = cti_params

        self.ip_vals = torch.arange(config.NUM_IPS, device=device)
        self.port_vals = torch.tensor(sorted(config.SCENARIO["COMMON_PORTS"]), device=device)
        self.num_ports = self.port_vals.numel()

        # 관측 차원
        self.state_dim_def, self.state_dim_seek = 6, 5
        self.reset()

    def reset(self):
        dp, sp = config.DYN_PARAMS, config.SEEKER_PARAMS
        self.ip_cd = torch.full((self.n,), dp["ip_cd"]["base"], device=self.device)
        self.decoy_ratio = torch.full((self.n,), dp["decoy_ratio"]["base"], device=self.device)
        self.bl_level = torch.full((self.n,), dp["bl_level"]["base"], device=self.device)
        self.attack_bias = torch.full((self.n,), sp["attack_bias"]["base"], device=self.device)
        self.scan_effort = torch.full((self.n,), sp["scan_effort"]["base"], device=self.device)

        self.service_ip = torch.randint(0, config.NUM_IPS, (self.n,), device=self.device)
        self.service_port = self.port_vals[torch.randint(0, self.num_ports, (self.n,), device=self.device)]
        self.exposure_steps = torch.zeros((self.n,), dtype=torch.long, device=self.device)
        self.dwell_steps = torch.zeros((self.n,), dtype=torch.long, device=self.device)
        self.known = torch.zeros((self.n,), dtype=torch.bool, device=self.device)
        self.recent_attacks_ema = torch.zeros((self.n,), device=self.device)
        self.observed_shuffle_ema = torch.zeros((self.n,), device=self.device)
        return self._obs_def(), self._obs_seek(torch.zeros((self.n,), dtype=torch.bool, device=self.device))

    def step(self, a_def, a_seek):
        # 1) Defender meta-action
        if self.mtd_mode == 'arl' and a_def is not None:
            for i, (name, val) in config.MTD_META_ACTIONS.items():
                m = (a_def == i)
                if not m.any():
                    continue
                if name != "none":
                    cur = getattr(self, name)
                    upd = cur + val if name == "bl_level" else cur * val
                    lo, hi = config.DYN_PARAMS[name]["min"], config.DYN_PARAMS[name]["max"]
                    setattr(self, name, torch.where(m, torch.clamp(upd, lo, hi), cur))
        elif self.mtd_mode == 'static':
            p = config.STATIC_MTD_LEVELS[self.mtd_level]
            self.ip_cd.fill_(p["ip_cd"]) ; self.decoy_ratio.fill_(p["decoy_ratio"]) ; self.bl_level.fill_(p["bl_level"])

        # 2) Seeker meta-action
        if self.seeker_mode == 'arl' and a_seek is not None:
            for i, (name, val) in config.SEEKER_META_ACTIONS.items():
                m = (a_seek == i)
                if not m.any():
                    continue
                if name != "none":
                    cur = getattr(self, name)
                    upd = cur * val
                    lo, hi = config.SEEKER_PARAMS[name]["min"], config.SEEKER_PARAMS[name]["max"]
                    setattr(self, name, torch.where(m, torch.clamp(upd, lo, hi), cur))
        elif self.seeker_mode == 'static_behavior':
            p = config.SEEKER_BEHAVIOR_LEVELS[self.seeker_level]
            self.scan_effort.fill_(p.get("scan_effort", self.scan_effort.mean()))
            self.attack_bias.fill_(p.get("attack_bias", self.attack_bias.mean()))

        # 3) Shuffle dynamics
        p_shuffle = 0.6 / torch.clamp(self.ip_cd, min=1e-6)
        did_shuffle = torch.rand(self.n, device=self.device) < p_shuffle
        self.dwell_steps += 1
        if did_shuffle.any():
            k = did_shuffle.sum()
            self.service_ip[did_shuffle] = torch.randint(0, config.NUM_IPS, (k,), device=self.device)
            self.service_port[did_shuffle] = self.port_vals[torch.randint(0, self.num_ports, (k,), device=self.device)]
            self.known[did_shuffle] = False
            self.exposure_steps[did_shuffle] = 0
            self.dwell_steps[did_shuffle] = 0
        self.exposure_steps += 1

        # 4) Attacker behavior
        if self.cti_params:
            # (CTI 로직은 동일)
            target_ips = self.cti_params.get('target_ips')
            target_ports = self.cti_params.get('target_ports')
            if target_ips is not None and target_ports is not None:
                is_target = torch.any(self.service_ip.unsqueeze(1) == target_ips.to(self.device), dim=1) \
                          & torch.any(self.service_port.unsqueeze(1) == target_ports.to(self.device), dim=1)
            else:
                is_target = torch.zeros(self.n, dtype=torch.bool, device=self.device)
            attack_prob = torch.full((self.n,), config.BLIND_ATTACK_P, device=self.device)
            attack_prob[is_target] = self.cti_params.get('attack_prob', 0.9)
            do_attack = torch.rand(self.n, device=self.device) < attack_prob
            do_scan = torch.rand(self.n, device=self.device) < 0.5
            found = do_scan & is_target
        else:
            p_scan = torch.clamp(0.4 * self.scan_effort, 0.05, 0.95)
            do_scan = torch.rand(self.n, device=self.device) < p_scan
            p_find = torch.clamp(0.1 + 0.02 * self.exposure_steps.float(), 0.05, 0.9)
            found = do_scan & (torch.rand(self.n, device=self.device) < p_find)
            p_attack_base = torch.where(self.known, config.KNOWLEDGE_ATTACK_P, config.BLIND_ATTACK_P)
            p_attack = torch.clamp(p_attack_base * self.attack_bias, 0.01, 0.95)
            do_attack = torch.rand(self.n, device=self.device) < p_attack
        self.known.logical_or_(found)

        # 5) Defense resolution
        decoy_attack = do_attack & (torch.rand(self.n, device=self.device) < self.decoy_ratio)
        p_block = torch.sigmoid(-0.5 + 0.6 * self.bl_level)
        block = do_attack & (~decoy_attack) & (torch.rand(self.n, device=self.device) < p_block)
        success = do_attack & (~decoy_attack) & (~block)  # breach

        # 6) Costs & Rewards
        cost = config.COST_MTD_ACTION \
             + config.COST_SHUFFLE * did_shuffle.float() \
             + config.COST_DECOY_RATIO * self.decoy_ratio \
             + config.COST_BL_LEVEL * self.bl_level

        # === [수정 2] 방어자 보상(r_def)에 기만(Decoy) 보상 추가 ===
        r_def = (config.REW_MTD_BLOCK * block.float()) \
              + (config.REW_MTD_DECOY * decoy_attack.float()) \
              + (config.PENALTY_MTD_BREACH * success.float()) \
              + (config.PENALTY_MTD_KNOWLEDGE_LEAK * found.float()) \
              - (config.COST_WEIGHT * cost)
        # =======================================================

        r_seek = (2.5*success.float()) + (0.5*found.float()) \
               - (0.05*do_scan.float()) + (-0.3*(do_attack & ~success).float())

        self.recent_attacks_ema = 0.9*self.recent_attacks_ema + 0.1*do_attack.float()
        self.observed_shuffle_ema = 0.9*self.observed_shuffle_ema + 0.1*did_shuffle.float()

        info = {
            "did_shuffle": did_shuffle.float(),
            "attacks": do_attack.float(),
            "successes": success.float(),
            "founds": found.float(),
            "blocks": block.float(),
            "decoys": decoy_attack.float(),
            "cost": cost,
            "exposure": self.exposure_steps.float(),
            "dwell": self.dwell_steps.float(),
            "service_id": self._endpoint_id(self.service_ip, self.service_port),
            "scans": do_scan.float(),
            "known": self.known.float(),
            "p_shuffle": p_shuffle,
            # params snapshot
            "ip_cd": self.ip_cd.clone(),
            "decoy_ratio": self.decoy_ratio.clone(),
            "bl_level": self.bl_level.clone(),
            "attack_bias": self.attack_bias.clone(),
            "scan_effort": self.scan_effort.clone(),
        }
        return self._obs_def(), self._obs_seek(did_shuffle), r_def, r_seek, torch.zeros(self.n, dtype=torch.bool, device=self.device), info

    def _endpoint_id(self, ip, port):
        port_idx = (port.unsqueeze(-1) == self.port_vals).nonzero(as_tuple=True)[1]
        return ip * self.num_ports + port_idx

    def _obs_def(self):
        # [Def] recent attack intensity, known ratio (global), exposure mean, normalized params
        return torch.stack([
            torch.clamp(self.recent_attacks_ema, 0, 1),
            self.known.float().mean().expand(self.n),
            (self.exposure_steps.float().mean().expand(self.n) / 100.0),
            (self.ip_cd - config.DYN_PARAMS["ip_cd"]["min"]) / (config.DYN_PARAMS["ip_cd"]["max"] - config.DYN_PARAMS["ip_cd"]["min"]),
            self.decoy_ratio / config.DYN_PARAMS["decoy_ratio"]["max"],
            self.bl_level / config.DYN_PARAMS["bl_level"]["max"],
        ], dim=1)

    def _obs_seek(self, observed_move):
        return torch.stack([
            self.known.float(),
            observed_move.float(),
            torch.clamp(self.observed_shuffle_ema, 0, 1),
            (self.attack_bias - config.SEEKER_PARAMS["attack_bias"]["min"]) / (config.SEEKER_PARAMS["attack_bias"]["max"] - config.SEEKER_PARAMS["attack_bias"]["min"]),
            (self.scan_effort - config.SEEKER_PARAMS["scan_effort"]["min"]) / (config.SEEKER_PARAMS["scan_effort"]["max"] - config.SEEKER_PARAMS["scan_effort"]["min"]),
        ], dim=1)

# ===============================
# 4) Metrics & Plotting
# ===============================

def calculate_metrics_from_infos(all_infos, total_steps) -> Dict[str, float]:
    t = {k: torch.stack([d[k] for d in all_infos]) for k in all_infos[0].keys()}

    # Defender metrics
    num_attacks = t["attacks"].sum().item()
    if num_attacks > 0:
        num_breaches = t["successes"].sum().item()
        num_blocks = t["blocks"].sum().item()
        num_decoys = t["decoys"].sum().item()
        r_succ = 1.0 - (num_breaches / num_attacks)
        r_breach = num_breaches / num_attacks
        eta_dec = num_decoys / num_attacks  # η_dec
        r_block = num_blocks / num_attacks
        cost_per_block = t["cost"].sum().item() / (num_blocks + num_decoys) if (num_blocks + num_decoys) > 0 else float('inf')
    else:
        r_succ, r_breach, eta_dec, r_block, cost_per_block = 1.0, 0.0, 0.0, 0.0, 0.0

    # Diversity
    service_ids = t["service_id"].flatten().cpu().numpy()
    visit_counts = np.bincount(service_ids, minlength=config.NUM_ENDPOINTS)
    probs = visit_counts / visit_counts.sum() if visit_counts.sum() > 0 else np.zeros_like(visit_counts, dtype=float)
    d_bits = -np.sum(probs[probs>0] * np.log2(probs[probs>0]))

    # Seeker
    num_scans = t["scans"].sum().item(); num_founds = t["founds"].sum().item()

    return {
        "R_succ": r_succ,
        "C_def": t["cost"].mean().item(),
        "Cost_per_Block": cost_per_block,
        "D_bits": d_bits,
        "S_shuffle": (t["did_shuffle"].sum().item() / total_steps) * math.log2(config.NUM_ENDPOINTS),
        "eta_dec": eta_dec,
        "exposure_mean": t["exposure"].mean().item(),
        "dwell_mean": t["dwell"].mean().item(),
        "r_breach": r_breach,
        "r_find": num_founds/num_scans if num_scans>0 else 0.0,
        "r_block": r_block,
        "r_known": t["known"].sum().item() / total_steps,
        "r_atk": num_attacks / total_steps,
        "r_scan": num_scans / total_steps,
        "wasted_scan_rate": 1.0 - (num_founds/num_scans) if num_scans>0 else 0.0,
        # parameters (avg)
        "ip_cd_mean": t["ip_cd"].mean().item(),
        "decoy_ratio_mean": t["decoy_ratio"].mean().item(),
        "bl_level_mean": t["bl_level"].mean().item(),
        "attack_bias_mean": t["attack_bias"].mean().item(),
        "scan_effort_mean": t["scan_effort"].mean().item(),
    }


# === [수정 3] 요청하신 상세 JSON 리포트 생성 함수 ===
def save_training_summary(outdir: pathlib.Path, history: Dict[str, list], args: argparse.Namespace):
    def tail_avg(key):
        arr = [v for v in history.get(key, []) if v is not None]
        if not arr: return 0.0
        n = max(1, len(arr)//10) # 마지막 10% 평균
        return float(np.mean(arr[-n:]))

    # 최종 메트릭
    metrics = {
        "R_succ": tail_avg("R_succ"),
        "C_def": tail_avg("C_def"),
        "D_bits": tail_avg("D_bits"),
        "eta_dec": tail_avg("eta_dec"),
        "r_breach": tail_avg("r_breach"),
        "r_known": tail_avg("r_known"),
    }
    
    # 최종 정책
    def_policy = {
        "ip_cd": tail_avg("ip_cd_mean"),
        "decoy_ratio": tail_avg("decoy_ratio_mean"),
        "bl_level": tail_avg("bl_level_mean"),
    }
    seek_policy = {
        "attack_bias": tail_avg("attack_bias_mean"),
        "scan_effort": tail_avg("scan_effort_mean"),
    }
    
    # 학습 상태 진단
    status = "UNKNOWN"
    diagnosis = "N/A"
    recommendation = "N/A"

    if metrics["eta_dec"] < 0.01 and metrics["C_def"] > 0.5:
        status = "STUCK_LOCAL_OPTIMUM (NO_DECOY)"
        diagnosis = "기만 효율(eta_dec)이 0%입니다. 에이전트가 기만 전략을 학습하지 않고 차단(bl_level)에만 의존하고 있습니다."
        recommendation = "Config의 REW_MTD_DECOY 보상을 높이거나 COST_DECOY_RATIO 비용을 낮추는 것을 고려하십시오."
    elif metrics["R_succ"] > 0.9 and metrics["eta_dec"] > 0.1:
        status = "CONVERGED_SUCCESS"
        diagnosis = "에이전트가 차단과 기만을 모두 활용하는 비용 효율적인 균형점을 찾았습니다."
        recommendation = "None"
    elif metrics["R_succ"] < 0.8:
        status = "CONVERGED_POOR"
        diagnosis = "학습이 수렴했으나 방어 성공률(R_succ)이 낮습니다. Seeker가 MTD를 압도했습니다."
        recommendation = "PENALTY_MTD_BREACH를 높이거나, 학습 파라미터(lr, updates)를 재조정하십시오."
        
    # 최종 JSON 구조
    summary = {
      "run_parameters": {
        "level": args.level,
        "meta_updates": args.meta_updates,
        "seeker_level": args.seeker_level,
        "cost_weight": args.cost_weight,
        "entropy_coef": args.entropy_coef,
        "reward_incentives": {
          "REW_MTD_BLOCK": config.REW_MTD_BLOCK,
          "REW_MTD_DECOY": config.REW_MTD_DECOY,
          "PENALTY_MTD_BREACH": config.PENALTY_MTD_BREACH,
          "PENALTY_MTD_KNOWLEDGE_LEAK": config.PENALTY_MTD_KNOWLEDGE_LEAK
        },
        "cost_structure": {
          "COST_MTD_ACTION": config.COST_MTD_ACTION,
          "COST_SHUFFLE": config.COST_SHUFFLE,
          "COST_DECOY_RATIO": config.COST_DECOY_RATIO,
          "COST_BL_LEVEL": config.COST_BL_LEVEL
        }
      },
      "final_metrics": metrics,
      "final_policy_defender": def_policy,
      "final_policy_seeker": seek_policy if args.seeker_level == 3 else "Static",
      "interpretation": {
        "status": status,
        "diagnosis": diagnosis,
        "recommendation": recommendation
      }
    }
    
    # JSON 파일로 저장
    with open(outdir/"models"/"training_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
# =======================================================


def plot_and_save(history: Dict[str, list], visit_heatmap, attack_heatmap, outdir: pathlib.Path, 
                  fig=None, final_save=True): # <-- [수정 4] fig 인자 추가
    updates = history.get("update", [])
    if not updates: return

    # 1) 개별 PNG 저장(요청 반영)
    def simple_plot(x, ys, labels, title, ylabel, path):
        plt.figure(figsize=(10,6))
        for y,l in zip(ys,labels): plt.plot(x,y,label=l)
        plt.title(title); plt.xlabel('Update'); plt.ylabel(ylabel); plt.grid(True, linestyle='--'); plt.legend()
        plt.tight_layout(); plt.savefig(path, dpi=200); plt.close() # 개별 닫기

    if final_save: # 최종 저장 시에만 개별 PNG 생성 (속도 향상)
        figs = outdir/"figs"
        simple_plot(updates, [history['R_def_ema'], history['R_seek_ema']], ["Def(EMA)", "Seek(EMA)"],
                    "1. Agent Rewards", "Reward", figs/"01_rewards.png")
        simple_plot(updates, [history['def_policy_loss'], history['def_value_loss']], ["PolicyLoss","ValueLoss"],
                    "2. PPO Loss", "Loss", figs/"02_ppo_loss.png")

        # Trade-off (쌍축)
        plt.figure(figsize=(10,6))
        ax = plt.gca(); ax2 = ax.twinx()
        ax.plot(updates, history['R_succ'], label='R_succ', linewidth=2)
        ax2.plot(updates, history['C_def'], label='C_def', linewidth=2, linestyle='--')
        ax.set_title('3. Performance vs Cost'); ax.set_xlabel('Update'); ax.set_ylabel('R_succ'); ax2.set_ylabel('C_def')
        ax.grid(True, linestyle='--'); ax.legend(loc='upper left'); ax2.legend(loc='upper right')
        plt.tight_layout(); plt.savefig(figs/"03_tradeoff.png", dpi=200); plt.close()

        simple_plot(updates, [history['D_bits'], history['r_atk']], ["D_bits","AttackRate"],
                    "4. Diversity vs Attack", "Metric", figs/"04_diversity_attack.png")
        simple_plot(updates, [history['r_known'], history['r_breach']], ["r_known","r_breach"],
                    "5. LPC: Knowledge vs Breach", "Rate", figs/"05_lpc_knowledge_breach.png")
        simple_plot(updates, [history['scan_effort_mean'], history['attack_bias_mean']], ["scan_effort","attack_bias"],
                    "6. Seeker Params", "Value", figs/"06_seeker_params.png")
        simple_plot(updates, [history['ip_cd_mean'], history['decoy_ratio_mean'], history['bl_level_mean']], ["ip_cd","decoy","BL"],
                    "7. MTD Params", "Value", figs/"07_mtd_params.png")

        # Heatmaps
        for name, data in [("08_visit_heatmap.png", visit_heatmap),("09_attack_heatmap.png", attack_heatmap)]:
            plt.figure(figsize=(12,5))
            im = plt.imshow(data, aspect='auto', interpolation='nearest')
            plt.title(name[:-4]); plt.xlabel('Port Index'); plt.ylabel('IP Index')
            plt.xticks(np.arange(len(config.SCENARIO["COMMON_PORTS"])), [str(p) for p in config.SCENARIO["COMMON_PORTS"]], rotation=45, ha="right")
            plt.yticks(np.arange(config.NUM_IPS))
            if data.sum()>0: plt.colorbar(im, label='count')
            plt.tight_layout(); plt.savefig(figs/name, dpi=200); plt.close()

    # 2) 대시보드(한 장)
    
    # === [수정 4] 메모리 누수 방지 로직 ===
    if fig is None:
        # final_save=True 이거나 SHOW=False일 때 (새 그림 생성)
        fig = plt.figure(figsize=(24,28))
    else:
        # SHOW=True이고 final_save=False일 때 (기존 그림 재사용)
        fig.clf() # 그림 초기화
    # ====================================

    gs = gridspec.GridSpec(7, 2, figure=fig, height_ratios=[1,1,1,1,1,1.5,1.5])
    
    # (Matplotlib grid() 버그 수정: linestyle='--' 명시)
    ax1 = fig.add_subplot(gs[0,0]); ax1.plot(updates, history['R_def_ema'], label='Def'); ax1.plot(updates, history['R_seek_ema'], label='Seek'); ax1.set_title('1. Rewards'); ax1.legend(); ax1.grid(True, linestyle='--')
    ax2 = fig.add_subplot(gs[0,1]); ax2.plot(updates, history['def_policy_loss'], label='Policy'); ax2.plot(updates, history['def_value_loss'], label='Value'); ax2.set_title('2. PPO Loss'); ax2.legend(); ax2.grid(True, linestyle='--')
    ax3 = fig.add_subplot(gs[1,0]); ax3.plot(updates, history['R_succ'], label='R_succ'); ax3_t = ax3.twinx(); ax3_t.plot(updates, history['C_def'], label='C_def', linestyle='--'); ax3.set_title('3. Trade-off'); ax3.grid(True, linestyle='--')
    ax4 = fig.add_subplot(gs[1,1]); ax4.plot(updates, history['D_bits'], label='D_bits'); ax4_t = ax4.twinx(); ax4_t.plot(updates, history['r_atk'], label='AttackRate', linestyle=':'); ax4.set_title('4. Diversity vs Attack'); ax4.grid(True, linestyle='--')
    ax5 = fig.add_subplot(gs[2,0]); ax5.plot(updates, history['r_known'], label='r_known'); ax5_t = ax5.twinx(); ax5_t.plot(updates, history['r_breach'], label='r_breach', linestyle='--'); ax5.set_title('5. LPC'); ax5.grid(True, linestyle='--')
    ax6 = fig.add_subplot(gs[2,1]); ax6.plot(updates, history['scan_effort_mean'], label='scan'); ax6.plot(updates, history['attack_bias_mean'], label='attack'); ax6.set_title('6. Seeker Params'); ax6.legend(); ax6.grid(True, linestyle='--')
    ax7 = fig.add_subplot(gs[3,:]); ax7.plot(updates, history['ip_cd_mean'], label='ip_cd'); ax7.plot(updates, history['decoy_ratio_mean'], label='decoy'); ax7.plot(updates, history['bl_level_mean'], label='BL'); ax7.set_title('7. MTD Params'); ax7.legend(); ax7.grid(True, linestyle='--')
    ax8 = fig.add_subplot(gs[4,:]); im8 = ax8.imshow(visit_heatmap, aspect='auto'); ax8.set_title('8. Visit Heatmap'); ax8.set_xlabel('Port'); ax8.set_ylabel('IP'); fig.colorbar(im8, ax=ax8)
    ax9 = fig.add_subplot(gs[5,:]); im9 = ax9.imshow(attack_heatmap, aspect='auto'); ax9.set_title('9. Attack Heatmap'); ax9.set_xlabel('Port'); ax9.set_ylabel('IP'); fig.colorbar(im9, ax=ax9)
    
    fig.suptitle(f'Thesis Dashboard (Update: {updates[-1]})', fontsize=24)
    plt.tight_layout(rect=[0,0.03,1,0.98]);
    
    if final_save:
        plt.savefig(outdir/"training_dashboard_optimized.png", dpi=300); plt.close(fig)
    elif SHOW:
        # SHOW=True이고 final_save=False일 때 (실시간 표시)
        try:
            from IPython.display import display, clear_output
            display(fig)
            clear_output(wait=True)
        except ImportError:
            plt.pause(0.1) # IPython이 없을 경우

# ===============================
# 5) Train / Validate
# ===============================

def train(args):
    set_seed(args.seed); outdir = make_outdir(level=args.level)

    seeker_info = config.SEEKER_BEHAVIOR_LEVELS[args.seeker_level]
    seeker_mode = seeker_info.get("mode", "static_behavior")

    env = MTDSeekerEnvTorch(n_envs=config.N_ENVS, device=config.DEVICE, mtd_mode='arl', seeker_mode=seeker_mode, seeker_level=args.seeker_level)

    def_agent = PPO(env.state_dim_def, config.MTD_META_ACTION_DIM, config.DEVICE, args.lr, config.EPS_CLIP, args.entropy_coef)
    buf_def = Buffer(config.N_ENVS, config.ROLLOUT_STEPS, env.state_dim_def, config.DEVICE)

    seek_agent, buf_seek = None, None
    if seeker_mode == 'arl':
        seek_agent = PPO(env.state_dim_seek, config.SEEKER_META_ACTION_DIM, config.DEVICE, args.lr, config.EPS_CLIP, config.ENTROPY_COEF)
        buf_seek = Buffer(config.N_ENVS, config.ROLLOUT_STEPS, env.state_dim_seek, config.DEVICE)

    # CSV
    header = [
        "update","R_def_ema","R_seek_ema","def_policy_loss","def_value_loss","def_entropy",
        "R_succ","C_def","D_bits","S_shuffle","eta_dec","r_breach","r_known","r_atk","r_scan",
        "ip_cd_mean","decoy_ratio_mean","bl_level_mean","attack_bias_mean","scan_effort_mean",
    ]
    with open(outdir/"training_log.csv","w",newline="") as f: csv.writer(f).writerow(header)
    hist = {k: [] for k in header}
    R_def_ema = None; R_seek_ema = None

    visit_heatmap = np.zeros((config.NUM_IPS, len(config.SCENARIO["COMMON_PORTS"])))
    attack_heatmap = np.zeros_like(visit_heatmap)

    print(f"####### ARL 학습 시작 (vs Seeker {seeker_info['name']}) #######\nDevice={config.DEVICE}, Level={args.level}\n결과 디렉토리: {outdir}")
    obs_def, obs_seek = env.reset()

    # === [수정 4] 실시간 플로팅을 위한 Figure 객체 생성 ===
    fig = None
    if SHOW:
        fig = plt.figure(figsize=(24,28))
    # ===============================================

    for update in range(1, args.meta_updates+1):
        infos = []
        for _ in range(config.ROLLOUT_STEPS):
            with torch.no_grad():
                a_def, lp_def, v_def = def_agent.policy.act(obs_def)
                if seek_agent:
                    a_seek, lp_seek, v_seek = seek_agent.policy.act(obs_seek)
                else:
                    a_seek, lp_seek, v_seek = None, None, None
                next_obs_def, next_obs_seek, r_def, r_seek, done, info = env.step(a_def, a_seek)
            infos.append(info)
            buf_def.add(obs_def, a_def, r_def, done, lp_def, v_def)
            if seek_agent: buf_seek.add(obs_seek, a_seek, r_seek, done, lp_seek, v_seek)
            obs_def, obs_seek = next_obs_def, next_obs_seek

        with torch.no_grad(): _, last_v_def = def_agent.policy(next_obs_def)
        ret_def, adv_def = buf_def.compute_returns_and_advantages(last_v_def, config.GAMMA, config.GAE_LAMBDA)
        losses_def = def_agent.update(buf_def, ret_def, adv_def, config.K_EPOCHS, config.MAX_GRAD_NORM)

        if seek_agent:
            with torch.no_grad(): _, last_v_seek = seek_agent.policy(next_obs_seek)
            ret_seek, adv_seek = buf_seek.compute_returns_and_advantages(last_v_seek, config.GAMMA, config.GAE_LAMBDA)
            _ = seek_agent.update(buf_seek, ret_seek, adv_seek, config.K_EPOCHS, config.MAX_GRAD_NORM)

        metrics = calculate_metrics_from_infos(infos, config.N_ENVS*config.ROLLOUT_STEPS)

        # Heatmap 누적
        t = {k: torch.stack([d[k] for d in infos]) for k in infos[0].keys()}
        service_ids = t["service_id"].flatten().cpu().numpy()
        visit_counts = np.bincount(service_ids, minlength=config.NUM_ENDPOINTS)
        visit_heatmap += visit_counts.reshape(visit_heatmap.shape)
        atk_mask = t["attacks"].flatten().cpu().numpy().astype(bool)
        atk_loc = service_ids[atk_mask]
        if len(atk_loc)>0:
            attack_heatmap += np.bincount(atk_loc, minlength=config.NUM_ENDPOINTS).reshape(attack_heatmap.shape)

        # EMA
        R_def_ema = 0.9*R_def_ema + 0.1*buf_def.rewards.mean().item() if R_def_ema is not None else buf_def.rewards.mean().item()
        if seek_agent:
            R_seek_ema = 0.9*(R_seek_ema if R_seek_ema is not None else 0.0) + 0.1*buf_seek.rewards.mean().item()

        row = {
            "update": update,
            "R_def_ema": R_def_ema,
            "R_seek_ema": R_seek_ema or 0.0,
            "def_policy_loss": losses_def[0],
            "def_value_loss": losses_def[1],
            "def_entropy": losses_def[2],
            **metrics,
        }
        for k in header: hist[k].append(row.get(k, 0.0))
        with open(outdir/"training_log.csv","a",newline="") as f:
            csv.writer(f).writerow([row.get(k,"") for k in header])

        if update % 20 == 0:
            print(f"Upd {update:4d}/{args.meta_updates} | R_def {R_def_ema:.3f} | R_succ {metrics['R_succ']:.3f} | C_def {metrics['C_def']:.3f} | D_bits {metrics['D_bits']:.3f} | η_dec {metrics['eta_dec']:.3f}")
            # [수정 4] 실시간 표시는 fig 객체를 전달
            plot_and_save(hist, visit_heatmap, attack_heatmap, outdir, fig=fig, final_save=False)

    # 모델 저장 & 정책 카드
    torch.save(def_agent.policy.state_dict(), outdir/"models"/"defender_policy.pth")
    if seek_agent: torch.save(seek_agent.policy.state_dict(), outdir/"models"/"seeker_policy.pth")
    
    # [수정 3] 새로운 요약 JSON 저장
    save_training_summary(outdir, hist, args) 

    # 최종본 저장 (fig=None으로 새 그림 생성)
    plot_and_save(hist, visit_heatmap, attack_heatmap, outdir, fig=None, final_save=True)
    print(f"\n학습 완료. 결과: {outdir}")
    if SHOW: plt.close('all') # 모든 그림 닫기


def validate_static(args):
    set_seed(args.seed); outdir = make_outdir(level=args.level)

    # Learned
    env = MTDSeekerEnvTorch(n_envs=config.N_ENVS, device=config.DEVICE, mtd_mode='arl', seeker_mode='static_behavior', seeker_level=0)
    def_pol = ActorCritic(env.state_dim_def, config.MTD_META_ACTION_DIM).to(config.DEVICE)
    def_pol.load_state_dict(torch.load(args.load_policy, map_location=config.DEVICE)); def_pol.eval()
    infos, obs_def, _ = [], *env.reset()
    for _ in range(config.VALIDATION_STEPS):
        with torch.no_grad(): a_def,_,_ = def_pol.act(obs_def)
        obs_def, _, _, _, _, info = env.step(a_def, None); infos.append(info)
    results = { 'Learned ARL (vs Naive)': calculate_metrics_from_infos(infos, config.N_ENVS*config.VALIDATION_STEPS) }

    # Static levels
    for lvl, p in config.STATIC_MTD_LEVELS.items():
        env_s = MTDSeekerEnvTorch(n_envs=config.N_ENVS, device=config.DEVICE, mtd_mode='static', mtd_level=lvl, seeker_mode='static_behavior', seeker_level=0)
        infos, _, _ = [], *env_s.reset()
        for _ in range(config.VALIDATION_STEPS):
            _, _, _, _, _, info = env_s.step(None, None); infos.append(info)
        results[p['name']] = calculate_metrics_from_infos(infos, config.N_ENVS*config.VALIDATION_STEPS)

    # 표 출력
    print("\n===== [정적 정책 비교] =====")
    for name, m in results.items():
        print(f"{name:22s} | R_succ={m['R_succ']:.2%} | r_breach={m['r_breach']:.2%} | C_def={m['C_def']:.3f} | D_bits={m['D_bits']:.3f} | S={m['S_shuffle']:.3f} | η_dec={m['eta_dec']:.3f}")


def validate_naive(args):
    print("\n####### 학습된 정책 vs Naive 공격자 #######")
    set_seed(args.seed); outdir = make_outdir(level=args.level)
    env = MTDSeekerEnvTorch(n_envs=config.N_ENVS, device=config.DEVICE, mtd_mode='arl', seeker_mode='static_behavior', seeker_level=args.seeker_level)
    pol = ActorCritic(env.state_dim_def, config.MTD_META_ACTION_DIM).to(config.DEVICE)
    pol.load_state_dict(torch.load(args.load_policy, map_location=config.DEVICE)); pol.eval()
    infos, obs_def, _ = [], *env.reset()
    for _ in range(config.VALIDATION_STEPS):
        with torch.no_grad(): a_def,_,_ = pol.act(obs_def)
        obs_def, _, _, _, _, info = env.step(a_def, None); infos.append(info)
    m = calculate_metrics_from_infos(infos, config.N_ENVS*config.VALIDATION_STEPS)
    print(f"▶ R_succ={m['R_succ']:.2%} | C_def={m['C_def']:.4f} | η_dec={m['eta_dec']:.3f}")


def validate_policy(args):
    set_seed(args.seed)
    print("\n####### 정책 쇼다운 #######")
    env = MTDSeekerEnvTorch(n_envs=config.N_ENVS, device=config.DEVICE, mtd_mode='arl', seeker_mode='arl')
    def_v1 = ActorCritic(6, config.MTD_META_ACTION_DIM).to(config.DEVICE); def_v1.load_state_dict(torch.load(args.load_def_v1, map_location=config.DEVICE)); def_v1.eval()
    seek_v1 = ActorCritic(5, config.SEEKER_META_ACTION_DIM).to(config.DEVICE); seek_v1.load_state_dict(torch.load(args.load_seek_v1, map_location=config.DEVICE)); seek_v1.eval()
    def_v2 = ActorCritic(6, config.MTD_META_ACTION_DIM).to(config.DEVICE); def_v2.load_state_dict(torch.load(args.load_def_v2, map_location=config.DEVICE)); def_v2.eval()
    seek_v2 = ActorCritic(5, config.SEEKER_META_ACTION_DIM).to(config.DEVICE); seek_v2.load_state_dict(torch.load(args.load_seek_v2, map_location=config.DEVICE)); seek_v2.eval()

    scenarios = {
        "New Defender (v2) vs Old Seeker (v1)": (def_v2, seek_v1),
        "Old Defender (v1) vs New Seeker (v2)": (def_v1, seek_v2),
    }
    results = {}
    for name,(dpol, spol) in scenarios.items():
        infos, obs_def, obs_seek = [], *env.reset()
        for _ in range(config.VALIDATION_STEPS):
            with torch.no_grad(): a_def,_,_ = dpol.act(obs_def); a_seek,_,_ = spol.act(obs_seek)
            obs_def, obs_seek, _, _, _, info = env.step(a_def, a_seek); infos.append(info)
        results[name] = calculate_metrics_from_infos(infos, config.N_ENVS*config.VALIDATION_STEPS)

    print("\n===== [쇼다운 결과] =====")
    for name,m in results.items():
        print(f"{name:38s} | Defender Win={m['R_succ']:.2%} | Seeker Breach={m['r_breach']:.2%} | Cost={m['C_def']:.3f} | η_dec={m['eta_dec']:.3f}")

# ===============================
# 6) Main
# ===============================
if __name__ == '__main__':
    p = argparse.ArgumentParser(description="Ultimate MTD vs Seeker ARL Framework.")
    p.add_argument("--mode", type=str, default="train", choices=['train','validate-static','validate-naive','validate-policy','validate-cti'])
    p.add_argument("--level", type=str, default=config.LEVEL)
    p.add_argument("--seed", type=int, default=config.SEED)

    g = p.add_argument_group('Training')
    g.add_argument("--seeker-level", type=int, default=3, choices=list(config.SEEKER_BEHAVIOR_LEVELS.keys()))
    g.add_argument("--cost-weight", type=float, default=config.COST_WEIGHT)
    g.add_argument("--entropy-coef", type=float, default=config.ENTROPY_COEF)
    g.add_argument("--meta-updates", type=int, default=config.META_UPDATES)
    g.add_argument("--lr", type=float, default=config.LR)

    v = p.add_argument_group('Validation')
    v.add_argument("--load-policy", type=str)
    v.add_argument("--seeker-level-validate", type=int, default=0)

    s = p.add_argument_group('Showdown')
    s.add_argument("--load-def-v1", type=str); s.add_argument("--load-seek-v1", type=str)
    s.add_argument("--load-def-v2", type=str); s.add_argument("--load-seek-v2", type=str)

    args, _ = p.parse_known_args()

    # 반영
    config.LEVEL = args.level; config.COST_WEIGHT = args.cost_weight; config.ENTROPY_COEF = args.entropy_coef
    config.META_UPDATES = args.meta_updates; config.LR = args.lr; config.SEED = args.seed

    if args.mode == 'train':
        train(args)
    elif args.mode == 'validate-static':
        if not args.load_policy: raise ValueError("--load-policy 필요")
        validate_static(args)
    elif args.mode == 'validate-naive':
        if not args.load_policy: raise ValueError("--load-policy 필요")
        args.seeker_level = args.seeker_level_validate
        validate_naive(args)
    elif args.mode == 'validate-policy':
        # === [BUGFIX] args.load_def-v1 -> args.load_def_v1 ===
        need = [args.load_def_v1, args.load_seek_v1, args.load_def_v2, args.load_seek_v2]
        if not all(need): raise ValueError("--load-def/seek-* 인자 4개 모두 필요")
        validate_policy(args)
    else:
        print("[validate-cti]는 자리표시자입니다.")