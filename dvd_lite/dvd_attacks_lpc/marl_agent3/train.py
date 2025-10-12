# train.py
import os, time, json, csv, signal, pathlib, datetime as dt
import numpy as np
import torch
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import config
from environment_torch import MTDSeekerEnvTorch
from ppo_agent import PPO, Buffer
from gameview import summarize_round

# --- Curriculum Learning을 위해 config에서 추가로 import ---
from config import load_scenario

# ------------------------- 유틸 -------------------------
def _get_int_env(name, default):
    try:
        return int(os.environ.get(name, default))
    except (ValueError, TypeError):
        return default

LOG_INTERVAL   = _get_int_env("LOG_INTERVAL", 10)
PLOT_INTERVAL  = _get_int_env("PLOT_INTERVAL", 50)
ROUND_INTERVAL = _get_int_env("ROUND_INTERVAL", 10)
MODE           = os.environ.get("MODE", "train")
ROUND_JSON_FN  = os.environ.get("ROUND_JSON", "rounds.json")

# ------------------------- 플롯 & CSV -------------------------
def plot_curves(hist, outdir: pathlib.Path):
    t = np.array(hist["t"]) / 60.0

    plt.figure(figsize=(12, 7))
    plt.plot(t, hist["ema_m"], label="MTD EMA Reward", color='blue', alpha=0.9)
    plt.plot(t, hist["ema_s"], label="Seeker EMA Reward", color='red', alpha=0.9)
    plt.xlabel("Time (minutes)")
    plt.ylabel("EMA Reward")
    plt.title("Learning Curves: MTD vs. Seeker")
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.legend()
    plt.tight_layout()
    outdir.mkdir(parents=True, exist_ok=True)
    plt.savefig(outdir / "lc_rewards.png")
    plt.close()

    plt.figure(figsize=(12, 7))
    event_keys = ["breach", "block", "decoy", "scan", "stealth", "probe", "attack"]
    for k in event_keys:
        if k in hist and len(hist[k]) > 0:
            plt.plot(t, hist[k], label=k.capitalize(), alpha=0.8)
    plt.xlabel("Time (minutes)")
    plt.ylabel("Rate (per step)")
    plt.title("Event Rates Over Time")
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.legend()
    plt.tight_layout()
    plt.savefig(outdir / "lc_events.png")
    plt.close()

    fig, ax1 = plt.subplots(figsize=(12, 7))
    if "as_exp" in hist and len(hist["as_exp"]) > 0:
        ax1.plot(t, hist["as_exp"], label="Attack Surface Exposure", color='green')
    if "as_var" in hist and len(hist["as_var"]) > 0:
        ax1.plot(t, hist["as_var"], label="Attack Surface Variance", color='orange', linestyle='--')
    ax1.set_xlabel("Time (minutes)")
    ax1.set_ylabel("Attack Surface Metrics")
    ax1.tick_params(axis='y')
    ax1.grid(True, linestyle='--', alpha=0.6)
    ax1.legend(loc='upper left')
    
    if "avg_budget" in hist and len(hist["avg_budget"]) > 0:
        ax2 = ax1.twinx()
        ax2.plot(t, hist["avg_budget"], label="MTD Avg. Budget", color='purple', alpha=0.6)
        ax2.set_ylabel("Average Budget")
        ax2.tick_params(axis='y')
        ax2.legend(loc='upper right')

    fig.tight_layout()
    plt.title("Attack Surface and MTD Budget")
    plt.savefig(outdir / "lc_surface_budget.png")
    plt.close()

def write_csv(hist, out_csv: pathlib.Path):
    keys = list(hist.keys())
    with open(out_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(keys)
        writer.writerows(zip(*[hist[k] for k in keys]))

# ------------------------- TUI 패널 -------------------------
def render_panel(upd, total_updates, elapsed_min, ema_m, ema_s, stats, a_mtd_hist, a_sk_hist, num_ips, num_ports, n_envs, level):
    a_mtd = np.array(a_mtd_hist); a_sk = np.array(a_sk_hist)
    mtd_pct = [100.0 * (a_mtd == i).mean() for i in range(5)]
    sk_macro = map_seeker_macro(a_sk, num_ips, num_ports)
    sk_pct = [100.0 * (sk_macro == i).mean() for i in range(6)]

    print(f"╭── MTD–Seeker War Game (Lvl {level}, N={n_envs}) {'─'*45}╮")
    print(f"│ Update {upd}/{total_updates:<5d} │ Elapsed {elapsed_min:5.1f} min │ EMA MTD: {ema_m:+.3f} │ EMA Seeker: {ema_s:+.3f} │")
    print(f"├─ Events ─ Breach: {stats.get('breach_rate',0):.3f} │ Block: {stats.get('block_rate',0):.3f} │ Decoy Hit: {stats.get('decoy_rate',0):.3f} ┤")
    print(f"├─ MTD ──── IP Move: {stats.get('ip_move_rate',0):.3f} │ Port Move: {stats.get('pt_move_rate',0):.3f} │ Budget: {int(stats.get('avg_budget',0))} ┤")
    print(f"├─ Surface ─ AS Exp: {stats.get('as_exp',0):.3f} │ AS Var: {stats.get('as_var',0):.3f} {'─'*25}┤")
    print(f"├─ MTD Acts: Wait {mtd_pct[0]:.1f}% | IP {mtd_pct[1]:.1f}% | Port {mtd_pct[2]:.1f}% | Decoy {mtd_pct[3]:.1f}% | BL {mtd_pct[4]:.1f}% ┤")
    print(f"╰─ SK Acts: Scan {sk_pct[0]+sk_pct[1]:.1f}% | Probe {sk_pct[2]:.1f}% | Evade {sk_pct[3]:.1f}% | Atk {sk_pct[4]+sk_pct[5]:.1f}% {'─'*12}╯")

# ------------------------- 메인 루프 -------------------------
def train():
    dev = config.DEVICE
    torch.manual_seed(config.SEED)
    np.random.seed(config.SEED)

    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    outdir = pathlib.Path(f"runs/level{config.ARGS.level}_dynamic/{stamp}") # 초기 레벨 기록
    outdir.mkdir(parents=True, exist_ok=True)
    rounds_path = outdir / ROUND_JSON_FN
    csv_path    = outdir / "learning_log.csv"

    env = MTDSeekerEnvTorch(config.N_ENVS, device=dev)
    S = env.reset()
    mtd = PPO(env.state_dim, env.mtd_n, dev)
    sk  = PPO(env.state_dim, env.seeker_n, dev)
    mbuf = Buffer(config.ROLLOUT_STEPS * config.N_ENVS, env.state_dim, dev)
    sbuf = Buffer(config.ROLLOUT_STEPS * config.N_ENVS, env.state_dim, dev)
    
    current_level = config.LEVEL
    breach_rate_history = []
    breach_window_size = 50
    level_up_threshold = 0.30
    level_down_threshold = 0.05

    ema_m, ema_s, alpha = 0.0, 0.0, 0.02
    print(f"####### MTD–Seeker War Game: device={dev.type}, n_envs={config.N_ENVS}, initial_level={current_level} #######")
    
    start = time.monotonic()
    hist = {k: [] for k in ["t", "upd", "ema_m", "ema_s", "breach", "block", "decoy", "scan", "stealth", "probe", "attack", "ip_move", "pt_move", "avg_budget", "as_exp", "as_var", "H_ip", "H_pt", "level"]}
    rounds = []

    stop = {"flag": False}
    signal.signal(signal.SIGINT, lambda s, f: stop.update({"flag": True}))

    for upd in range(1, config.TOTAL_UPDATES + 1):
        if stop["flag"]: break
        
        mbuf.ptr, sbuf.ptr = 0, 0
        a_mtd_list, a_sk_list, r_mtd_list, r_sk_list = [], [], [], []

        for _ in range(config.ROLLOUT_STEPS):
            with torch.no_grad():
                am, lm = mtd.act(S)
                as_, ls = sk.act(S)
                _, vm, _ = mtd.old.evaluate(S, am)
                _, vs, _ = sk.old.evaluate(S, as_)
            
            S_next, mr, sr, d = env.step(am, as_)
            mbuf.add_batch(S, am, lm, mr, vm, d)
            sbuf.add_batch(S, as_, ls, sr, vs, d)
            a_mtd_list.extend(am.cpu().numpy())
            a_sk_list.extend(as_.cpu().numpy())
            r_mtd_list.append(mr.mean().item())
            r_sk_list.append(sr.mean().item())
            S = S_next

        if MODE == "train":
            mtd.update(mbuf); sk.update(sbuf)

        ema_m = (1-alpha)*ema_m + alpha*np.mean(r_mtd_list)
        ema_s = (1-alpha)*ema_s + alpha*np.mean(r_sk_list)

        now = time.monotonic()
        hist["t"].append(now - start); hist["upd"].append(upd); hist["ema_m"].append(ema_m); hist["ema_s"].append(ema_s); hist["level"].append(current_level)
        
        st = env.last_stats or {}
        for k in ["breach", "block", "decoy", "scan", "stealth", "probe", "attack", "ip_move", "pt_move", "avg_budget", "as_exp", "as_var"]:
            hist[k].append(st.get(f"{k}_rate", st.get(k, 0.0)))
        hist["H_ip"].append(env.H_ip.mean().item()); hist["H_pt"].append(env.H_pt.mean().item())

        # Curriculum Learning Logic
        breach_rate_history.append(st.get("breach_rate", 0.0))
        if len(breach_rate_history) > breach_window_size: breach_rate_history.pop(0)
        
        avg_breach_rate = np.mean(breach_rate_history)
        level_changed = False
        if upd > breach_window_size: # 충분한 데이터가 쌓인 후 조절 시작
            if avg_breach_rate < level_down_threshold and current_level > 0:
                current_level -= 1; level_changed = True
                print(f"\n[CURRICULUM] Breach rate ({avg_breach_rate:.3f}) is low. Decreasing difficulty to Level {current_level}")
            elif avg_breach_rate > level_up_threshold and current_level < 3:
                current_level += 1; level_changed = True
                print(f"\n[CURRICULUM] Breach rate ({avg_breach_rate:.3f}) is high. Increasing difficulty to Level {current_level}")

        if level_changed:
            new_scenario = load_scenario(current_level)
            config.LEVEL, config.NUM_IPS, config.NUM_PORTS = current_level, len(range(new_scenario["IP_RANGE"][0], new_scenario["IP_RANGE"][1] + 1)), len(set(new_scenario["COMMON_PORTS"]))
            env = MTDSeekerEnvTorch(config.N_ENVS, device=dev)
            S = env.reset()
            # Note: A more robust implementation might re-initialize agents if state/action spaces change. Here we assume they don't.
            breach_rate_history.clear()

        if upd % LOG_INTERVAL == 0:
            render_panel(upd, config.TOTAL_UPDATES, (now-start)/60.0, ema_m, ema_s, st, a_mtd_list, a_sk_list, config.NUM_IPS, config.NUM_PORTS, config.N_ENVS, current_level)

        if upd % ROUND_INTERVAL == 0:
            rounds.append(summarize_round(upd, now-start, ema_m, ema_s, np.array(a_mtd_list), np.array(a_sk_list), r_mtd_list, r_sk_list, st, config.NUM_IPS, config.NUM_PORTS))

        if upd % PLOT_INTERVAL == 0 and upd > 1:
            plot_curves(hist, outdir); write_csv(hist, csv_path)

    plot_curves(hist, outdir); write_csv(hist, csv_path)
    with open(rounds_path, "w") as f: json.dump({"meta": {"level": config.ARGS.level, "n_envs": config.N_ENVS, "mode": MODE}, "rounds": rounds}, f, indent=2)
    
    print(f"\n[SAVE] Training results saved to: {outdir}")
    print("훈련 종료.")

if __name__ == "__main__":
    train()