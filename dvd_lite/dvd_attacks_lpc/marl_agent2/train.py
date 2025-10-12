# train.py
# 라운드(업데이트) 단위 JSON 기록 + 학습/시뮬레이션 공용 실행

import os, time, json, csv, signal, pathlib, datetime as dt
import numpy as np
import torch
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import config
from environment_torch import MTDSeekerEnvTorch
from ppo_agent import PPO, Buffer
from gameview import summarize_round  # ★ 신규 유틸

# ------------------------- 유틸: 안전한 설정 로딩 -------------------------
def _get_int_env(name, default):
    try:
        return int(os.environ.get(name, default))
    except:
        return default

def _get_float_env(name, default):
    try:
        return float(os.environ.get(name, default))
    except:
        return default

LOG_INTERVAL   = getattr(config, "LOG_INTERVAL", _get_int_env("LOG_INTERVAL", 20))
PLOT_INTERVAL  = _get_int_env("PLOT_INTERVAL", 200)      # 그림/CSV 찍는 주기(업데이트 기준)
ROUND_INTERVAL = _get_int_env("ROUND_INTERVAL", 1)       # JSON 스냅샷 주기(업데이트 기준)
MODE           = os.environ.get("MODE", "train")         # "train" | "sim"
ROUND_JSON_FN  = os.environ.get("ROUND_JSON", "rounds.json")

# ------------------------- 플롯 & CSV -------------------------
def plot_curves(hist, outdir: pathlib.Path):
    t = np.array(hist["t"], dtype=float)/60.0
    # EMA 보상
    plt.figure(figsize=(9,5))
    plt.plot(t, hist["ema_m"], label="MTD EMA reward")
    plt.plot(t, hist["ema_s"], label="Seeker EMA reward")
    plt.xlabel("Time (min)"); plt.ylabel("EMA Reward")
    plt.title("MTD–Seeker War Game: Learning Curves")
    plt.grid(True, alpha=0.3); plt.legend(); plt.tight_layout()
    (outdir/"lc_rewards.png").parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(outdir/"lc_rewards.png"); plt.close()

    # 이벤트 지표
    plt.figure(figsize=(9,5))
    for k in ["breach","block","decoy","scan","stealth","probe","attack"]:
        if k in hist and hist[k]:
            plt.plot(t, hist[k], label=k)
    plt.xlabel("Time (min)"); plt.ylabel("Rate (0–1)")
    plt.title("Event Rates")
    plt.grid(True, alpha=0.3); plt.legend(); plt.tight_layout()
    plt.savefig(outdir/"lc_events.png"); plt.close()

    # 공격면/예산
    plt.figure(figsize=(9,5))
    if hist["as_exp"]: plt.plot(t, hist["as_exp"], label="AS exposure")
    if hist["as_var"]: plt.plot(t, hist["as_var"], label="AS variance")
    if hist["avg_budget"]: plt.plot(t, hist["avg_budget"], label="Budget")
    plt.xlabel("Time (min)"); plt.ylabel("Value")
    plt.title("Surface & Budget")
    plt.grid(True, alpha=0.3); plt.legend(); plt.tight_layout()
    plt.savefig(outdir/"lc_surface_budget.png"); plt.close()

def write_csv(hist, out_csv: pathlib.Path):
    cols = ["time_sec","time_min","update_idx","ema_mtd","ema_seeker",
            "breach","block","decoy","scan","stealth","probe","attack",
            "ip_move","pt_move","avg_budget","as_exp","as_var",
            "H_ip","H_pt"]
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
                hist.get("H_ip",[None])[i] if "H_ip" in hist else None,
                hist.get("H_pt",[None])[i] if "H_pt" in hist else None,
            ]
            w.writerow(row)

# ------------------------- TUI 패널 -------------------------
def render_panel(upd, total_updates, elapsed_min, ema_m, ema_s, stats, a_mtd_hist, a_sk_hist, num_ips, num_ports, n_envs):
    # 액션 분포 집계(최근 라운드; %로 보기 쉽게)
    a_mtd = np.array(a_mtd_hist, dtype=np.int64)
    a_sk  = np.array(a_sk_hist, dtype=np.int64)
    # MTD 5개
    mtd_pct = [100.0*float((a_mtd==i).mean()) if a_mtd.size>0 else 0.0 for i in range(5)]
    # Seeker 매크로 6개
    from gameview import map_seeker_macro
    sk_macro = map_seeker_macro(a_sk, num_ips, num_ports)
    sk_pct = [100.0*float((sk_macro==i).mean()) if sk_macro.size>0 else 0.0 for i in range(6)]

    print(f"╭──────────────────────────── MTD–Seeker War Game (Level {config.LEVEL}, N={n_envs}) ─────────────────────────────╮")
    print(f"│ Update {upd}/{total_updates:<5d}                                                     Elapsed {elapsed_min:5.1f} min │")
    print(f"│ EMA MTD: {ema_m:+.3f},  EMA Seeker: {ema_s:+.3f}                        AS(exp,var): {stats.get('as_exp',0):.3f} / {stats.get('as_var',0):.3f} │")
    print(f"│ Events — breach {stats.get('breach_rate',0):.3f}  block {stats.get('block_rate',0):.3f}  decoy {stats.get('decoy_rate',0):.3f}       Moves — ip {stats.get('ip_move_rate',0):.3f}  pt {stats.get('pt_move_rate',0):.3f} | budget {int(stats.get('avg_budget',0))} │")
    print(f"│ MTD — wait {mtd_pct[0]:.1f}%  ip {mtd_pct[1]:.1f}%  pt {mtd_pct[2]:.1f}%  decoy {mtd_pct[3]:.1f}%  bl {mtd_pct[4]:.1f}%   SK — scan {sk_pct[0]:.1f}%  stealth {sk_pct[1]:.1f}%  probe {sk_pct[2]:.1f}%  evade {sk_pct[3]:.1f}%  atk-ip {sk_pct[4]:.1f}%  atk-pt {sk_pct[5]:.1f}% │")
    print( "╰────────────────────────────────────────────────────────────────────────────────────────────────╯")

# ------------------------- 메인 루프 -------------------------
def train():
    dev = config.DEVICE
    minutes = _get_float_env("MINUTES", 0.0) or None

    # 출력 디렉토리 구성
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    outdir = pathlib.Path(f"runs/level{config.LEVEL}/{stamp}")
    outdir.mkdir(parents=True, exist_ok=True)
    rounds_path = outdir/ROUND_JSON_FN
    csv_path    = outdir/"learning_log.csv"

    # 환경/정책/버퍼
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

    # 워밍업: 몇 스텝
    with torch.no_grad():
        for _ in range(3):
            am, lm = mtd.act(S); as_, ls = sk.act(S)
            mtd.old.evaluate(S, am); sk.old.evaluate(S, as_)
            S, _, _, _ = env.step(am, as_)

    start = time.monotonic()
    deadline = start + (minutes*60.0) if minutes else None

    # 히스토리/라운드 저장 구조
    hist = {"t":[], "ema_m":[], "ema_s":[], "upd":[],
            "breach":[], "block":[], "decoy":[], "scan":[], "stealth":[], "probe":[], "attack":[],
            "ip_move":[], "pt_move":[], "avg_budget":[], "as_exp":[], "as_var":[],
            "H_ip":[], "H_pt":[]}
    rounds = []

    stop = {"flag": False}
    def _sigint(*_): stop["flag"] = True; print("\n[INTERRUPT] Save & exit soon…")
    signal.signal(signal.SIGINT, _sigint)

    upd = 0
    while upd < config.TOTAL_UPDATES:
        upd += 1
        mbuf.ptr = 0; sbuf.ptr = 0

        # 라운드 원시 기록(이 업데이트 동안의 모든 스텝)
        a_mtd_list, a_sk_list = [], []
        r_mtd_list, r_sk_list = [], []

        # 롤아웃 수집
        for _ in range(config.ROLLOUT_STEPS):
            with torch.no_grad():
                am, lm = mtd.act(S)
                as_, ls = sk.act(S)
                vm = mtd.old.evaluate(S, am)[1]
                vs = sk.old.evaluate(S, as_)[1]
            S_next, mr, sr, d = env.step(am, as_)

            # 버퍼(학습용)
            mbuf.add_batch(S, am, lm, mr, vm, d)
            sbuf.add_batch(S, as_, ls, sr, vs, d)

            # 라운드 원시 기록(시각화/게임요약용)
            a_mtd_list.extend(am.detach().cpu().tolist())
            a_sk_list.extend(as_.detach().cpu().tolist())
            r_mtd_list.extend(mr.detach().cpu().tolist())
            r_sk_list.extend(sr.detach().cpu().tolist())

            S = S_next

        # 학습/시뮬레이션 분기
        if MODE == "train":
            mtd.update(mbuf); sk.update(sbuf)
        # MODE=="sim"이면 업데이트 생략(정책 고정 시뮬)

        # EMA 갱신(마지막 스텝 평균 사용)
        ema_m = (1-alpha)*ema_m + alpha*float(np.mean(r_mtd_list))
        ema_s = (1-alpha)*ema_s + alpha*float(np.mean(r_sk_list))

        # 시간/히스토리 축적
        now = time.monotonic()
        hist["t"].append(now - start)
        hist["ema_m"].append(ema_m); hist["ema_s"].append(ema_s); hist["upd"].append(upd)

        # 이벤트 스냅샷(from env.last_stats)
        st = env.last_stats or {}
        for k_src, k_dst in [
            ("breach_rate","breach"), ("block_rate","block"), ("decoy_rate","decoy"),
            ("scan_rate","scan"), ("stealth_rate","stealth"), ("probe_rate","probe"),
            ("attack_rate","attack"), ("ip_move_rate","ip_move"), ("pt_move_rate","pt_move"),
            ("avg_budget","avg_budget"), ("as_exp","as_exp"), ("as_var","as_var"),
        ]:
            hist[k_dst].append(st.get(k_src, 0.0))
        # 힌트 평균
        try:
            hist["H_ip"].append(float(env.H_ip.mean().item()))
            hist["H_pt"].append(float(env.H_pt.mean().item()))
        except:
            hist["H_ip"].append(None); hist["H_pt"].append(None)

        # 터미널 패널
        if upd % LOG_INTERVAL == 0:
            render_panel(upd, config.TOTAL_UPDATES, (now-start)/60.0, ema_m, ema_s, st,
                         a_mtd_list, a_sk_list, config.NUM_IPS, config.NUM_PORTS, config.N_ENVS)

        # 라운드 JSON 스냅샷
        if upd % ROUND_INTERVAL == 0:
            meta = {
                "breach_rate": st.get("breach_rate", 0.0),
                "block_rate":  st.get("block_rate", 0.0),
                "decoy_rate":  st.get("decoy_rate", 0.0),
                "scan_rate":   st.get("scan_rate", 0.0),
                "stealth_rate":st.get("stealth_rate", 0.0),
                "probe_rate":  st.get("probe_rate", 0.0),
                "attack_rate": st.get("attack_rate", 0.0),
                "ip_move_rate":st.get("ip_move_rate", 0.0),
                "pt_move_rate":st.get("pt_move_rate", 0.0),
                "avg_budget":  st.get("avg_budget", 0.0),
                "as_exp":      st.get("as_exp", 0.0),
                "as_var":      st.get("as_var", 0.0),
                "H_ip":        hist["H_ip"][-1],
                "H_pt":        hist["H_pt"][-1],
                "NUM_IPS":     config.NUM_IPS,
                "NUM_PORTS":   config.NUM_PORTS,
            }
            snap = summarize_round(
                upd_idx=upd,
                elapsed_sec=(now-start),
                ema_mtd=ema_m, ema_sk=ema_s,
                a_mtd=np.asarray(a_mtd_list, dtype=np.int64),
                a_sk =np.asarray(a_sk_list,  dtype=np.int64),
                r_mtd=np.asarray(r_mtd_list, dtype=np.float32),
                r_sk =np.asarray(r_sk_list,  dtype=np.float32),
                meta=meta, num_ips=config.NUM_IPS, num_ports=config.NUM_PORTS
            )
            rounds.append(snap)
            # 증분 저장(안전)
            with open(rounds_path, "w") as f:
                json.dump({"meta":{"level":config.LEVEL,"n_envs":config.N_ENVS,"mode":MODE},
                           "rounds":rounds}, f, ensure_ascii=False, indent=2)

        # 시간 예산/중단
        if (deadline and now >= deadline) or stop["flag"]:
            print("[TIME] Time budget reached; stopping training loop.")
            break

        # 그림/CSV 저장(주기)
        if upd % PLOT_INTERVAL == 0:
            plot_curves(hist, outdir)
            write_csv(hist, csv_path)

    # 종료 저장
    plot_curves(hist, outdir)
    write_csv(hist, csv_path)
    with open(rounds_path, "w") as f:
        json.dump({"meta":{"level":config.LEVEL,"n_envs":config.N_ENVS,"mode":MODE},
                   "rounds":rounds}, f, ensure_ascii=False, indent=2)
    print(f"[SAVE] Figures/CSV/JSON → {outdir}")
    print("훈련 종료.")

if __name__ == "__main__":
    train()
