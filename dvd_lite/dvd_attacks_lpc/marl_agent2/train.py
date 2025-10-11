# train.py
import os, time, csv, signal, math
from datetime import datetime
from pathlib import Path
import numpy as np
import torch
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import config
from environment_torch import MTDSeekerEnvTorch
from ppo_agent import PPO, Buffer

# ------------------------------ 콘솔 TUI: rich 우선, 실패 시 단순 로그 ------------------------------
_USE_RICH = False
try:
    from rich.live import Live
    from rich.table import Table
    from rich.panel import Panel
    from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn, TimeRemainingColumn
    from rich.console import Group
    _USE_RICH = True
except Exception:
    _USE_RICH = False

def _fmt_pct(x): return f"{100.0*float(x):.1f}%"
def _safe(d, k, default=0.0):
    v = d.get(k, default) if d else default
    try: return float(v)
    except: return default

# ------------------------------ 플롯 스타일(논문용) ------------------------------
def set_pub_style():
    plt.rcParams.update({
        "figure.figsize": (9,5),
        "figure.dpi": 180,
        "savefig.dpi": 300,
        "font.size": 12,
        "axes.titlesize": 14,
        "axes.labelsize": 12,
        "axes.titleweight": "bold",
        "axes.grid": True,
        "grid.alpha": 0.3,
        "lines.linewidth": 2.2,
        "legend.frameon": False,
        "legend.fontsize": 11,
        "axes.prop_cycle": plt.cycler(color=[
            "#4E79A7","#F28E2B","#E15759","#76B7B2","#59A14F",
            "#EDC948","#B07AA1","#FF9DA7","#9C755F","#BAB0AC"
        ])
    })

def _save(fig, out_dir: Path, name: str):
    exts = getattr(config, "SAVE_FORMATS", ["png"])
    fig.tight_layout()
    for ext in exts:
        fig.savefig(out_dir / f"{name}.{ext}", bbox_inches="tight")
    plt.close(fig)

def plot_all(hist, out_dir: Path, level: int):
    set_pub_style()
    t_min = np.array(hist["t"], dtype=float) / 60.0

    # 1) Rewards
    fig, ax = plt.subplots()
    ax.plot(t_min, hist["ema_m"], label="MTD EMA reward")
    ax.plot(t_min, hist["ema_s"], label="Seeker EMA reward")
    ax.set_xlabel("Time (minutes)"); ax.set_ylabel("EMA Reward")
    ax.set_title(f"Learning Curves — PPO (Level {level}, N={config.N_ENVS})")
    ax.legend()
    _save(fig, out_dir, "lc_rewards")

    # 2) Events
    fig, ax = plt.subplots()
    for k, lab in [
        ("breach","breach"), ("block","block"), ("decoy","decoy"),
        ("scan","scan"), ("stealth","stealth"), ("probe","probe"), ("attack","attack")
    ]:
        if k in hist and len(hist[k]) == len(t_min):
            ax.plot(t_min, hist[k], label=lab)
    ax.set_xlabel("Time (minutes)"); ax.set_ylabel("Rate (0–1)")
    ax.set_title(f"Event Rates (Level {level})")
    ax.legend()
    _save(fig, out_dir, "lc_events")

    # 3) Attack-surface
    fig, ax = plt.subplots()
    if "as_exp" in hist: ax.plot(t_min, hist["as_exp"], label="AS exposure")
    if "as_var" in hist: ax.plot(t_min, hist["as_var"], label="AS variance")
    ax.set_xlabel("Time (minutes)"); ax.set_ylabel("Normalized index")
    ax.set_title(f"Attack-Surface Dynamics (Level {level})")
    ax.legend()
    _save(fig, out_dir, "lc_surface")

    # 4) Budget
    fig, ax = plt.subplots()
    if "avg_budget" in hist: ax.plot(t_min, hist["avg_budget"], label="MTD avg budget")
    ax.set_xlabel("Time (minutes)"); ax.set_ylabel("Budget")
    ax.set_title(f"Defender Budget Trajectory (Level {level})")
    ax.legend()
    _save(fig, out_dir, "lc_budget")

    # 5) MTD action distribution
    fig, ax = plt.subplots()
    for k, lab in [
        ("mtd_wait","wait"), ("mtd_ip","ip-shuffle"), ("mtd_pt","port-shuffle"),
        ("mtd_decoy","decoy"), ("mtd_bl","blacklist")
    ]:
        if k in hist and len(hist[k]) == len(t_min):
            ax.plot(t_min, hist[k], label=lab)
    ax.set_xlabel("Time (minutes)"); ax.set_ylabel("Share (0–1)")
    ax.set_title(f"MTD Action Distribution (Level {level})")
    ax.legend()
    _save(fig, out_dir, "lc_actions_mtd")

    # 6) Seeker action distribution
    fig, ax = plt.subplots()
    for k, lab in [
        ("seek_scan","scan"), ("seek_stealth","stealth"),
        ("seek_probe","probe"), ("seek_evade","evade"),
        ("seek_attack_ip","attack-ip"), ("seek_attack_pt","attack-port")
    ]:
        if k in hist and len(hist[k]) == len(t_min):
            ax.plot(t_min, hist[k], label=lab)
    ax.set_xlabel("Time (minutes)"); ax.set_ylabel("Share (0–1)")
    ax.set_title(f"Seeker Action Distribution (Level {level})")
    ax.legend()
    _save(fig, out_dir, "lc_actions_seeker")

def write_csv(hist, out_csv: Path):
    cols = [
        "time_sec","time_min","update_idx",
        "ema_mtd","ema_seeker",
        "breach","block","decoy","scan","stealth","probe","attack",
        "ip_move","pt_move","avg_budget","as_exp","as_var",
        "mtd_wait","mtd_ip","mtd_pt","mtd_decoy","mtd_bl",
        "seek_scan","seek_stealth","seek_probe","seek_evade",
        "seek_attack_ip","seek_attack_pt"
    ]
    with open(out_csv, "w", newline="") as f:
        w = csv.writer(f); w.writerow(cols)
        for i in range(len(hist["t"])):
            row = [
                hist["t"][i], hist["t"][i]/60.0, hist["upd"][i],
                hist["ema_m"][i], hist["ema_s"][i],
                hist.get("breach",[None])[i] if "breach" in hist else None,
                hist.get("block",[None])[i] if "block" in hist else None,
                hist.get("decoy",[None])[i] if "decoy" in hist else None,
                hist.get("scan",[None])[i] if "scan" in hist else None,
                hist.get("stealth",[None])[i] if "stealth" in hist else None,
                hist.get("probe",[None])[i] if "probe" in hist else None,
                hist.get("attack",[None])[i] if "attack" in hist else None,
                hist.get("ip_move",[None])[i] if "ip_move" in hist else None,
                hist.get("pt_move",[None])[i] if "pt_move" in hist else None,
                hist.get("avg_budget",[None])[i] if "avg_budget" in hist else None,
                hist.get("as_exp",[None])[i] if "as_exp" in hist else None,
                hist.get("as_var",[None])[i] if "as_var" in hist else None,
                hist.get("mtd_wait",[None])[i] if "mtd_wait" in hist else None,
                hist.get("mtd_ip",[None])[i] if "mtd_ip" in hist else None,
                hist.get("mtd_pt",[None])[i] if "mtd_pt" in hist else None,
                hist.get("mtd_decoy",[None])[i] if "mtd_decoy" in hist else None,
                hist.get("mtd_bl",[None])[i] if "mtd_bl" in hist else None,
                hist.get("seek_scan",[None])[i] if "seek_scan" in hist else None,
                hist.get("seek_stealth",[None])[i] if "seek_stealth" in hist else None,
                hist.get("seek_probe",[None])[i] if "seek_probe" in hist else None,
                hist.get("seek_evade",[None])[i] if "seek_evade" in hist else None,
                hist.get("seek_attack_ip",[None])[i] if "seek_attack_ip" in hist else None,
                hist.get("seek_attack_pt",[None])[i] if "seek_attack_pt" in hist else None
            ]
            w.writerow(row)

# ------------------------------ rich 대시보드 ------------------------------
def _make_live_panel(upd, total_updates, hist, env, t_start):
    table = Table.grid(expand=True)
    table.add_column(justify="left")
    table.add_column(justify="right")
    now = time.monotonic()
    elap = now - t_start
    ema_m = hist["ema_m"][-1] if hist["ema_m"] else 0.0
    ema_s = hist["ema_s"][-1] if hist["ema_s"] else 0.0
    st = getattr(env, "last_stats", {}) or {}

    table.add_row(f"[bold]Update[/] {upd}/{total_updates}",
                  f"[bold]Elapsed[/] {elap/60.0:5.1f} min")

    table.add_row(f"EMA MTD: [cyan]{ema_m:+.3f}[/],  EMA Seeker: [magenta]{ema_s:+.3f}[/]",
                  f"AS(exp,var): { _safe(st,'as_exp'):0.3f} / { _safe(st,'as_var'):0.3f}")

    table.add_row(
        "Events — breach {0:.3f}  block {1:.3f}  decoy {2:.3f}".format(
            _safe(st,"breach_rate"), _safe(st,"block_rate"), _safe(st,"decoy_rate")),
        "Moves — ip {0:.3f}  pt {1:.3f} | budget {2:.0f}".format(
            _safe(st,"ip_move_rate"), _safe(st,"pt_move_rate"), _safe(st,"avg_budget"))
    )

    # 액션 분포 최근치
    def last_of(k): return hist[k][-1] if k in hist and hist[k] else 0.0
    table.add_row(
        "MTD — wait {0}  ip {1}  pt {2}  decoy {3}  bl {4}".format(
            _fmt_pct(last_of("mtd_wait")), _fmt_pct(last_of("mtd_ip")),
            _fmt_pct(last_of("mtd_pt")), _fmt_pct(last_of("mtd_decoy")),
            _fmt_pct(last_of("mtd_bl"))
        ),
        "SK — scan {0}  stealth {1}  probe {2}  evade {3}  atk-ip {4}  atk-pt {5}".format(
            _fmt_pct(last_of("seek_scan")), _fmt_pct(last_of("seek_stealth")),
            _fmt_pct(last_of("seek_probe")), _fmt_pct(last_of("seek_evade")),
            _fmt_pct(last_of("seek_attack_ip")), _fmt_pct(last_of("seek_attack_pt"))
        )
    )
    return Panel(table, title=f"MTD–Seeker War Game (Level {config.LEVEL}, N={config.N_ENVS})", border_style="white")

# ------------------------------ 학습 본문 ------------------------------
def train():
    dev = config.DEVICE
    minutes = float(os.environ.get("MINUTES", "0") or 0) or None
    out_dir = Path("runs") / f"level{config.LEVEL}" / datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=True)

    env = MTDSeekerEnvTorch(config.N_ENVS, device=dev)
    S = env.reset()

    mtd = PPO(env.state_dim, env.mtd_n, dev)
    sk  = PPO(env.state_dim, env.seeker_n, dev)

    cap = config.ROLLOUT_STEPS * config.N_ENVS
    mbuf = Buffer(cap, env.state_dim, dev)
    sbuf = Buffer(cap, env.state_dim, dev)

    ema_m = 0.0; ema_s = 0.0; alpha = 0.02

    print(f"####### MTD–Seeker War Game: device={dev.type}, n_envs={config.N_ENVS}, level={config.LEVEL} #######")
    print(f"State:{env.state_dim}, MTD actions:{env.mtd_n}, Seeker actions:{env.seeker_n} | IPs={config.NUM_IPS}, Ports={config.NUM_PORTS}")
    if minutes: print(f"[RUN] Time budget: {minutes:.1f} minutes")

    # warmup
    with torch.no_grad():
        for _ in range(3):
            am, lm = mtd.act(S); as_, ls = sk.act(S)
            mtd.old.evaluate(S, am)[1]; sk.old.evaluate(S, as_)[1]
            S, _, _, _ = env.step(am, as_)

    start = time.monotonic()
    deadline = start + (minutes*60.0) if minutes else None

    hist = {k:[] for k in [
        "t","ema_m","ema_s","upd",
        "breach","block","decoy","scan","stealth","probe","attack",
        "ip_move","pt_move","avg_budget","as_exp","as_var",
        "mtd_wait","mtd_ip","mtd_pt","mtd_decoy","mtd_bl",
        "seek_scan","seek_stealth","seek_probe","seek_evade","seek_attack_ip","seek_attack_pt"
    ]}

    stop = {"flag": False}
    def _sigint(*_): stop["flag"] = True; print("\n[INTERRUPT] Save & exit soon…")
    signal.signal(signal.SIGINT, _sigint)

    LOGI = getattr(config, "LOG_INTERVAL", 50)
    PLOT_EVERY = getattr(config, "PLOT_EVERY", 100)
    THROTTLE = getattr(config, "TUI_THROTTLE_SEC", 0.2)
    upd = 0

    # rich 진행바
    if _USE_RICH:
        progress = Progress(
            TextColumn("[bold]Update[/]"),
            BarColumn(bar_width=None),
            TextColumn("{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            expand=True
        )
        task_upd = progress.add_task("training", total=config.TOTAL_UPDATES)
        inner = Progress(TextColumn("rollout"), BarColumn(), TextColumn("{task.completed}/{task.total}"), expand=True)
        task_roll = inner.add_task("roll", total=config.ROLLOUT_STEPS)
        live = Live(Group(progress, inner), refresh_per_second=12)
        live.start()
    else:
        live = None
        last_tick = 0.0

    try:
        while upd < config.TOTAL_UPDATES:
            upd += 1
            if _USE_RICH:
                progress.update(task_upd, completed=upd-1)
                inner.reset(task_roll)
            mbuf.ptr = 0; sbuf.ptr = 0

            # 이번 업데이트에서의 액션 분포 집계
            mtd_cnt = np.zeros(env.mtd_n, dtype=np.int64)
            seek_cnt = dict(scan=0, stealth=0, probe=0, evade=0, atk_ip=0, atk_pt=0)

            for step_i in range(config.ROLLOUT_STEPS):
                with torch.no_grad():
                    am, lm = mtd.act(S)
                    as_, ls = sk.act(S)
                    vm = mtd.old.evaluate(S, am)[1]
                    vs = sk.old.evaluate(S, as_)[1]
                S_next, mr, sr, d = env.step(am, as_)
                mbuf.add_batch(S, am,  lm, mr, vm, d)
                sbuf.add_batch(S, as_, ls, sr, vs, d)
                S = S_next

                # 액션 카운트
                mtd_np = am.detach().cpu().numpy()
                for a in mtd_np: mtd_cnt[int(a)] += 1
                a_np = as_.detach().cpu().numpy()
                base = 5
                for a in a_np:
                    if a == 0 or a == 1: seek_cnt["scan"] += 1
                    elif a == 2:         seek_cnt["stealth"] += 1
                    elif a == 3:         seek_cnt["probe"] += 1
                    elif a == 4:         seek_cnt["evade"] += 1
                    elif base <= a < base + config.NUM_IPS: seek_cnt["atk_ip"] += 1
                    elif base + config.NUM_IPS <= a < base + config.NUM_IPS + config.NUM_PORTS: seek_cnt["atk_pt"] += 1

                # TUI 롤아웃 진행 업데이트(과도한 업데이트 방지)
                if _USE_RICH:
                    inner.update(task_roll, completed=step_i+1)
                else:
                    now = time.monotonic()
                    if now - last_tick > THROTTLE and step_i % 16 == 0:
                        print(f"  rollout {step_i+1}/{config.ROLLOUT_STEPS} …", end="\r")
                        last_tick = now

            # PPO 업데이트
            mtd.update(mbuf); sk.update(sbuf)

            # EMA 보상 갱신
            ema_m = (1-0.02)*ema_m + 0.02*float(mr.mean().item())
            ema_s = (1-0.02)*ema_s + 0.02*float(sr.mean().item())

            now = time.monotonic()
            hist["t"].append(now - start)
            hist["ema_m"].append(ema_m); hist["ema_s"].append(ema_s); hist["upd"].append(upd)

            # 이벤트 스냅샷
            st = getattr(env, "last_stats", {}) or {}
            for k_src, k_dst in [
                ("breach_rate","breach"), ("block_rate","block"), ("decoy_rate","decoy"),
                ("scan_rate","scan"), ("stealth_rate","stealth"), ("probe_rate","probe"),
                ("attack_rate","attack"), ("ip_move_rate","ip_move"), ("pt_move_rate","pt_move"),
                ("avg_budget","avg_budget"), ("as_exp","as_exp"), ("as_var","as_var")
            ]:
                hist[k_dst].append(_safe(st, k_src, 0.0))

            # 액션 분포(비율)
            tot_mtd = mtd_cnt.sum() if mtd_cnt.sum() > 0 else 1
            hist["mtd_wait"].append(mtd_cnt[0]/tot_mtd)
            hist["mtd_ip"].append(mtd_cnt[1]/tot_mtd)
            hist["mtd_pt"].append(mtd_cnt[2]/tot_mtd)
            hist["mtd_decoy"].append(mtd_cnt[3]/tot_mtd)
            hist["mtd_bl"].append(mtd_cnt[4]/tot_mtd)

            tot_sk = sum(seek_cnt.values()) if sum(seek_cnt.values()) > 0 else 1
            hist["seek_scan"].append(seek_cnt["scan"]/tot_sk)
            hist["seek_stealth"].append(seek_cnt["stealth"]/tot_sk)
            hist["seek_probe"].append(seek_cnt["probe"]/tot_sk)
            hist["seek_evade"].append(seek_cnt["evade"]/tot_sk)
            hist["seek_attack_ip"].append(seek_cnt["atk_ip"]/tot_sk)
            hist["seek_attack_pt"].append(seek_cnt["atk_pt"]/tot_sk)

            # 콘솔
            if upd % config.LOG_INTERVAL == 0:
                print(f"[Update {upd}/{config.TOTAL_UPDATES}] "
                      f"EMA(MTD,SK)=({ema_m:+.3f},{ema_s:+.3f}) | "
                      f"events: br {hist['breach'][-1]:.3f}  bl {hist['block'][-1]:.3f}  dc {hist['decoy'][-1]:.3f} | "
                      f"AS(exp,var)=({hist['as_exp'][-1]:.3f},{hist['as_var'][-1]:.3f})")

            # rich 라이브 패널 업데이트
            if _USE_RICH:
                live.update(_make_live_panel(upd, config.TOTAL_UPDATES, hist, env, start))

            # 중간 플롯 저장
            if config.PLOT_EVERY and (upd % config.PLOT_EVERY == 0):
                plot_all(hist, out_dir, config.LEVEL)

            # 타임박스 종료
            if (deadline and now >= deadline) or stop["flag"]:
                print("[TIME] Time budget reached; stopping training loop.")
                break
    finally:
        if _USE_RICH and live is not None:
            live.stop()

    # 최종 저장
    plot_all(hist, out_dir, config.LEVEL)
    write_csv(hist, out_dir / "learning_log.csv")
    print(f"[SAVE] Figures/CSV → {out_dir}")
    print("훈련 종료.")

if __name__ == "__main__":
    train()
