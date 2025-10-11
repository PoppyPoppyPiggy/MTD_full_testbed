# plots.py
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import config

def _save(fig, base):
    for ext in config.SAVE_FORMATS:
        fig.savefig(f"{base}.{ext}", bbox_inches="tight")
    plt.close(fig)

def plot_learning(hist):
    t = np.array(hist["t"], dtype=float) / 60.0
    fig = plt.figure(figsize=(9,5))
    plt.plot(t, hist["ema_m"], label="MTD EMA reward")
    plt.plot(t, hist["ema_s"], label="Seeker EMA reward")
    plt.xlabel("Time (minutes)"); plt.ylabel("EMA Reward")
    plt.title("Learning Curves")
    plt.grid(True, alpha=0.3); plt.legend()
    _save(fig, "fig_learning")

def plot_events(hist):
    t = np.array(hist["t"], dtype=float) / 60.0
    fig = plt.figure(figsize=(9,5))
    for k in ["breach","block","decoy","scan","stealth","probe","attack"]:
        if k in hist and len(hist[k])==len(t):
            plt.plot(t, hist[k], label=k)
    plt.xlabel("Time (minutes)"); plt.ylabel("Rate [0,1]")
    plt.title("Event Rates")
    plt.grid(True, alpha=0.3); plt.legend()
    _save(fig, "fig_events")

def plot_mtd_metrics(hist):
    t = np.array(hist["t"], dtype=float) / 60.0
    fig = plt.figure(figsize=(9,5))
    for k in ["D_entropy","S_score","R_score","eta_dec","C_def","R_succ"]:
        if k in hist and len(hist[k])==len(t):
            plt.plot(t, hist[k], label=k)
    plt.xlabel("Time (minutes)")
    plt.title("MTD Metrics (Diversity/Shuffle/Redundancy/Deception/Cost/Success)")
    plt.grid(True, alpha=0.3); plt.legend()
    _save(fig, "fig_mtd_metrics")

def plot_scores(hist):
    t = np.array(hist["t"], dtype=float) / 60.0
    fig = plt.figure(figsize=(9,5))
    for k in ["score_mtd","score_seeker"]:
        if k in hist and len(hist[k])==len(t):
            plt.plot(t, hist[k], label=k)
    plt.xlabel("Time (minutes)"); plt.ylabel("Composite Score")
    plt.title("Composite Scores")
    plt.grid(True, alpha=0.3); plt.legend()
    _save(fig, "fig_scores")

def plot_pareto(C, R, frontier):
    fig = plt.figure(figsize=(6,5))
    plt.scatter(C, R, s=10, alpha=0.6)
    plt.plot(frontier[0], frontier[1], linewidth=2, label="Pareto frontier")
    plt.xlabel("Defense Cost (proxy, C_def)"); plt.ylabel("Defense Success (R_succ)")
    plt.title("Cost–Effectiveness Pareto")
    plt.grid(True, alpha=0.3); plt.legend()
    _save(fig, "fig_pareto")

def plot_mttc_ecdf(x, y):
    fig = plt.figure(figsize=(6,5))
    plt.step(x, y, where="post")
    plt.xlabel("Steps-to-Compromise (MTTC)"); plt.ylabel("ECDF")
    plt.title("Empirical CDF of Time-to-Compromise")
    plt.grid(True, alpha=0.3)
    _save(fig, "fig_mttc_ecdf")
