#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MTD 성능 지표 분석 툴 (테스트베드 전용)
- 입력: baseline 디렉토리(공격만), mtd 디렉토리(공격+MTD)
  각 디렉토리에 ns3_metrics.csv 필수, effect_timeline.csv 권장
- 출력: summary/scorecard.csv 및 그래프 PNG

사용 예)
python compute_metrics.py \
  --baseline attack_output/ns3_eval/standard/baseline \
  --mtd      attack_output/ns3_eval/standard/mtd_ip_shuffle \
  --simTime 60 \
  --module  standard_ipshuffle \
  --out     attack_output/ns3_eval/standard/summary
"""
import argparse, os, math, re, json, csv
from pathlib import Path
from collections import defaultdict

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt


# ---------- I/O Helpers ----------

def read_ns3_metrics(path: Path) -> pd.DataFrame:
    p = Path(path) / "ns3_metrics.csv"
    if not p.exists():
        raise FileNotFoundError(f"ns3_metrics.csv not found in {path}")
    df = pd.read_csv(p)

    # 컬럼 소문자 맵
    colmap = {c.lower(): c for c in df.columns}
    # 표준 컬럼 별칭
    aliases = {
        "time":"time", "rx_pkts":"rx_pkts", "rx_bytes":"rx_bytes",
        "drop_pkts":"drop_pkts", "delay_ms":"delay_ms_avg", "delay_ms_avg":"delay_ms_avg",
        "jitter_ms":"jitter_ms_avg", "jitter_ms_avg":"jitter_ms_avg",
        "bridge":"bridge", "dst":"dst", "flow_id":"flow_id", "node":"node",
        "tx_bytes":"tx_bytes"
    }
    norm = {}
    for k,v in aliases.items():
        if k in colmap:
            norm[v] = colmap[k]
        elif v in colmap:
            norm[v] = colmap[v]

    # 표준명으로 리네임
    rename = {norm[k]:k for k in norm}
    df = df.rename(columns=rename)

    # 필수/옵션 채우기
    for req in ["time","rx_bytes"]:
        if req not in df.columns:
            raise ValueError(f"ns3_metrics.csv missing required column: {req}")
    if "rx_pkts" not in df.columns: df["rx_pkts"] = 0
    if "drop_pkts" not in df.columns: df["drop_pkts"] = 0
    if "delay_ms_avg" not in df.columns: df["delay_ms_avg"] = np.nan
    if "jitter_ms_avg" not in df.columns: df["jitter_ms_avg"] = np.nan
    if "bridge" not in df.columns: df["bridge"] = "unknown"
    if "dst" not in df.columns: df["dst"] = "unknown"
    if "flow_id" not in df.columns: df["flow_id"] = "f0"
    if "node" not in df.columns: df["node"] = "n0"
    if "tx_bytes" not in df.columns: df["tx_bytes"] = np.nan

    # 타입 보정
    df["time"] = pd.to_numeric(df["time"], errors="coerce").fillna(0).astype(int)
    df["rx_bytes"] = pd.to_numeric(df["rx_bytes"], errors="coerce").fillna(0)
    df["rx_pkts"] = pd.to_numeric(df["rx_pkts"], errors="coerce").fillna(0)
    df["drop_pkts"] = pd.to_numeric(df["drop_pkts"], errors="coerce").fillna(0)
    if "tx_bytes" in df.columns:
        df["tx_bytes"] = pd.to_numeric(df["tx_bytes"], errors="coerce").fillna(0)
    return df


def read_timeline(path: Path):
    p = Path(path) / "effect_timeline.csv"
    events, attack_windows = [], []
    if not p.exists():
        return events, attack_windows

    df = pd.read_csv(p)
    if "t" in df.columns and "time" not in df.columns:
        df = df.rename(columns={"t":"time"})
    if "tag" not in df.columns:
        df["tag"] = ""

    for _,r in df.iterrows():
        t = float(r.get("time", 0))
        tag = str(r.get("tag",""))
        duration = None
        m = re.search(r"\((\d+(?:\.\d+)?)s\)", tag)          # ... (3s)
        if m:
            duration = float(m.group(1))
        else:
            m2 = re.search(r"duration\s*=\s*(\d+(?:\.\d+)?)", tag)  # duration=3
            if m2: duration = float(m2.group(1))
        events.append({"time": t, "tag": tag, "duration": duration})

    # attack/ 로 시작하는 시점들을 1초 단위로 병합
    atk_times = sorted([int(e["time"]) for e in events if str(e["tag"]).startswith("attack/")])
    if atk_times:
        cur_s = atk_times[0]
        prev = cur_s
        for tt in atk_times[1:]:
            if tt == prev+1:
                prev = tt
            else:
                attack_windows.append((cur_s, prev+1))
                cur_s = tt
                prev = tt
        attack_windows.append((cur_s, prev+1))
    return events, attack_windows


# ---------- Core calc ----------

def resample_thr(df, sim_time):
    idx = pd.RangeIndex(0, int(sim_time)+1, 1)
    g = df.groupby("time")["rx_bytes"].sum()
    s = g.reindex(idx).fillna(0.0)
    thr = 8.0 * s / 1e6  # Mbps
    return thr


def rolling_median(series, win=5):
    return series.rolling(win, min_periods=1, center=True).median()


def area_positive(diff_series, start, end):
    sub = diff_series.loc[start:end-1]
    sub_pos = sub.where(sub>0, 0.0)
    return float(sub_pos.sum())  # Mbps*s (dt=1s)


def detect_cutovers(events):
    cut_tags = (
        "ip_shuffle_cutover", "bridge_hop", "port_hop_cutover", "service_migrate",
        "mtd/bridge_hop", "mtd/ip_shuffle_cutover", "mtd/port_hop_cutover", "mtd/service_migrate"
    )
    cutovers = []
    for e in events:
        tag = str(e["tag"])
        if any(x in tag for x in cut_tags):
            t0 = int(e["time"])
            dur = e["duration"] if e["duration"] is not None else 1.0
            cutovers.append((t0, t0 + math.ceil(dur)))
    cutovers.sort()

    # 병합
    merged = []
    for s,e in cutovers:
        if not merged or s > merged[-1][1]:
            merged.append([s,e])
        else:
            merged[-1][1] = max(merged[-1][1], e)
    return [(s,e) for s,e in merged]


def compute_diversity(df_mtd, attack_windows):
    df = df_mtd.copy()
    df["endpoint"] = df["dst"].astype(str) + "|" + df["bridge"].astype(str)
    grp = df.groupby("endpoint")["rx_bytes"].sum()
    total = float(grp.sum())
    if total <= 0 or len(grp)==0:
        return {"diversity": 0.0, "entropy": 0.0, "endpoints": {}}
    p = grp / total
    H = float(-(p * np.log(p)).sum())
    Hmax = math.log(len(grp))
    diversity = H / Hmax if Hmax>0 else 0.0
    return {"diversity": diversity, "entropy": H, "endpoints": grp.to_dict()}


def compute_shuffle_metrics(thr_base, thr_mtd, cutovers, attack_windows):
    if len(thr_base)==0 or len(thr_mtd)==0:
        return {"freq_per_min":0.0, "mean_t_rec":None, "sum_A_cut":0.0, "S_eff":0.0, "details":[]}

    simTime = len(thr_base)-1
    freq = len(cutovers) / (simTime/60.0) if simTime>0 else 0.0
    t_recs, a_cuts, details = [], [], []

    for (s,e) in cutovers:
        t0 = e  # cutover 창 끝 이후 회복 탐색
        # 회복: thr_mtd >= 0.9 * thr_base
        t_rec = None
        for t in range(t0, int(simTime)+1):
            if thr_mtd.loc[t] >= 0.9 * max(thr_base.loc[t], 1e-9):
                t_rec = t - t0
                break
        if t_rec is None:
            t_rec = float("inf")
        t_recs.append(t_rec if np.isfinite(t_rec) else simTime - t0)

        end_t = t0 + (0 if not np.isfinite(t_rec) else t_rec)
        end_t = min(end_t, int(simTime))
        a = area_positive(thr_base - thr_mtd, s, max(end_t, s+1))
        a_cuts.append(a)
        details.append({"window":[s,e], "t_rec":t_recs[-1], "A_cut":a})

    if not attack_windows:
        attack_windows = [(0, int(simTime))]
    a_mtd = 0.0
    for (s,e) in attack_windows:
        a_mtd += area_positive(thr_base - thr_mtd, s, e)

    delta_A_attack = -a_mtd
    sum_Ac   = float(np.nansum(a_cuts))
    sum_trec = float(np.nansum([x for x in t_recs if np.isfinite(x)]))
    denom = sum_Ac + 1.0 * sum_trec
    S_eff = (delta_A_attack/denom) if denom>0 else 0.0
    mean_trec = (sum_trec/len([x for x in t_recs if np.isfinite(x)]) 
                 if any(np.isfinite(x) for x in t_recs) else None)

    return {
        "freq_per_min":freq, "mean_t_rec":mean_trec, "sum_A_cut":sum_Ac,
        "S_eff":S_eff, "details":details, "A_attack_mtd":a_mtd
    }


def compute_redundancy(df_base, df_mtd, thr_base, thr_mtd, attack_windows):
    if not attack_windows:
        attack_windows = [(0, len(thr_base)-1)]
    ratios = []
    for (s,e) in attack_windows:
        b = float(thr_base.loc[s:e-1].mean()) if e>s else 0.0
        m = float(thr_mtd.loc[s:e-1].mean()) if e>s else 0.0
        ratios.append((m/b) if b>0 else 0.0)
    R_thr = float(np.median(ratios)) if ratios else 0.0

    shares = {}
    for (s,e) in attack_windows:
        sub = df_mtd[(df_mtd["time"]>=s)&(df_mtd["time"]<e)]
        total = float(sub["rx_bytes"].sum())
        if total<=0: continue
        for br, val in sub.groupby("bridge")["rx_bytes"].sum().items():
            shares[br] = shares.get(br, 0.0) + float(val)
    tot = sum(shares.values())
    if tot>0:
        shares = {k: v/tot for k,v in shares.items()}
    return {"R_thr":R_thr, "bridge_share":shares}


def compute_survivability(df_base, df_mtd, attack_windows, theta=0.7, require_ratio=0.8):
    # 정상 구간 중앙값 P0
    times = set(df_mtd["time"].unique().tolist())
    atkset = set()
    for (s,e) in attack_windows: atkset.update(range(s,e))
    normal = df_base[~df_base["time"].isin(list(atkset))]
    if len(normal)==0: normal = df_base.copy()
    if "rx_pkts" in normal.columns and normal["rx_pkts"].sum()>0:
        P0 = float(normal["rx_pkts"].median())
    else:
        P0 = float((normal["rx_bytes"]/1200).median())  # 근사
    thr = theta * P0

    alive_scores = []
    for (s,e) in attack_windows:
        sub = df_mtd[(df_mtd["time"]>=s)&(df_mtd["time"]<e)]
        if len(sub)==0:
            alive_scores.append(0)
            continue
        ok = (sub["rx_pkts"] >= thr).sum()
        rate = ok/len(sub)
        alive_scores.append(1 if rate>=require_ratio else 0)
    alive = int(round(np.mean(alive_scores))) if alive_scores else 1
    return {"alive":alive, "detail":alive_scores, "P0":P0, "threshold":thr}


def compute_energy(df_base, df_mtd, cutover_details, k1=1.0, k2=1.0, k3=0.1,
                   docker_cpu_base=None, docker_cpu_mtd=None):
    # 네트워크 델타 (rx 기준; 있으면 tx_bytes 활용 가능)
    b_rx = float(df_base["rx_bytes"].sum())
    m_rx = float(df_mtd["rx_bytes"].sum())
    delta_bytes = max(m_rx - b_rx, 0.0)
    E_net = k1 * (delta_bytes / max(len(df_mtd["time"].unique()),1))

    # 복구 비용
    sum_trec = sum([d["t_rec"] for d in cutover_details if np.isfinite(d["t_rec"])])
    E_rec = k2 * sum_trec

    # 시스템 CPU (옵션)
    E_sys = 0.0
    if docker_cpu_base is not None and docker_cpu_mtd is not None:
        E_sys = k3 * max(0.0, docker_cpu_mtd - docker_cpu_base)
    return {"E_net":E_net, "E_rec":E_rec, "E_sys":E_sys, "E_total":E_net+E_rec+E_sys}


# ---------- Plots / Scoring ----------

def make_plots(outdir, module, thr_base, thr_mtd, cutovers, attack_windows,
               diversity_info, redundancy_info):
    outdir = Path(outdir); outdir.mkdir(parents=True, exist_ok=True)

    # 1) Throughput compare
    plt.figure()
    plt.plot(thr_base.index, thr_base.values, label="baseline")
    plt.plot(thr_mtd.index,  thr_mtd.values,  label="mtd")
    # shade attack & cutover
    if attack_windows:
        for i,(s,e) in enumerate(attack_windows):
            plt.axvspan(s, e, alpha=0.18, color="#ff6b6b",
                        label="attack" if i==0 else None)
    if cutovers:
        for i,(s,e) in enumerate(cutovers):
            plt.axvspan(s, e, alpha=0.18, color="#4dabf7",
                        label="cutover" if i==0 else None)
    plt.xlabel("time (s)"); plt.ylabel("throughput (Mbps)")
    plt.title(f"{module}: throughput")
    plt.legend()
    plt.tight_layout()
    plt.savefig(Path(outdir) / f"throughput_compare_{module}.png", dpi=140)
    plt.close()

    # 2) Diversity histogram
    endpoints = diversity_info.get("endpoints", {})
    if endpoints:
        items = sorted(endpoints.items(), key=lambda x: -x[1])[:10]
        labels = [k for k,_ in items]
        vals   = [v for _,v in items]
        plt.figure()
        plt.bar(range(len(vals)), vals)
        plt.xticks(range(len(vals)), labels, rotation=45, ha="right")
        plt.title(f"{module}: endpoint bytes (top10)")
        plt.tight_layout()
        plt.savefig(Path(outdir) / f"diversity_hist_{module}.png", dpi=140)
        plt.close()

    # 3) Redundancy stack
    shares = redundancy_info.get("bridge_share", {})
    if shares:
        labs = list(shares.keys()); vals = [shares[k] for k in labs]
        plt.figure()
        plt.bar(labs, vals)
        plt.ylabel("share (bytes)")
        plt.title(f"{module}: bridge share during attacks")
        plt.tight_layout()
        plt.savefig(Path(outdir) / f"redundancy_stack_{module}.png", dpi=140)
        plt.close()


def normalize_and_score(metrics, E_ref=None):
    """
    metrics:
      {"diversity":D, "entropy":..., "shuffle":{"S_eff":...,"mean_t_rec":...,"sum_A_cut":...,"freq_per_min":...},
       "redundancy":{"R_thr":...}, "survivability":{"alive":0/1}, "energy":{"E_total":...}}
    """
    D = metrics.get("diversity",0.0)
    S_eff = metrics.get("shuffle",{}).get("S_eff",0.0)
    R_thr = metrics.get("redundancy",{}).get("R_thr",0.0)
    alive = metrics.get("survivability",{}).get("alive",1)
    E = metrics.get("energy",{}).get("E_total",0.0)

    D_norm = float(np.clip(D, 0, 1))
    S_norm = 1.0/(1.0+np.exp(-S_eff))       # sigmoid
    R_norm = float(np.clip(R_thr/1.5, 0, 1))
    A_norm = float(np.clip(alive, 0, 1))
    if E_ref is None:
        E_ref = max(1.0, E*1.2)
    En_norm = float(1.0 - np.clip(E/E_ref, 0, 1))

    score = 0.25*D_norm + 0.25*S_norm + 0.2*R_norm + 0.2*A_norm + 0.1*En_norm
    return {"D_norm":D_norm,"S_norm":S_norm,"R_norm":R_norm,"A_norm":A_norm,"E_norm":En_norm,"Score":score}


# ---------- CLI ----------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", required=True, help="baseline dir (attack only)")
    ap.add_argument("--mtd", required=True, help="mtd dir (attack + MTD)")
    ap.add_argument("--out", required=True, help="summary output dir")
    ap.add_argument("--module", default="module")
    ap.add_argument("--simTime", type=int, default=60)
    ap.add_argument("--w", type=float, default=1.0, help="recovery time weight (현재 S_eff 내부 상수)")
    args = ap.parse_args()

    base_dir = Path(args.baseline)
    mtd_dir  = Path(args.mtd)
    outdir   = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)

    # 로드
    df_base = read_ns3_metrics(base_dir)
    df_mtd  = read_ns3_metrics(mtd_dir)
    events, attack_windows = read_timeline(mtd_dir)  # MTD 타임라인 우선 사용
    cutovers = detect_cutovers(events)

    # 처리량 리샘플 & 기준선 스무딩
    thr_base = resample_thr(df_base, args.simTime)
    thr_mtd  = resample_thr(df_mtd,  args.simTime)
    thr_base_smooth = rolling_median(thr_base, 5)

    # 지표 계산
    div = compute_diversity(df_mtd, attack_windows)
    shf = compute_shuffle_metrics(thr_base_smooth, thr_mtd, cutovers, attack_windows)
    red = compute_redundancy(df_base, df_mtd, thr_base_smooth, thr_mtd, attack_windows)
    sru = compute_survivability(df_base, df_mtd, attack_windows, theta=0.7, require_ratio=0.8)
    eng = compute_energy(df_base, df_mtd, shf.get("details", []), k1=1.0, k2=1.0, k3=0.1)

    metrics = {
        "diversity": div.get("diversity",0.0),
        "entropy": div.get("entropy",0.0),
        "shuffle": shf,
        "redundancy": red,
        "survivability": sru,
        "energy": eng,
    }
    score = normalize_and_score(metrics)

    # scorecard.csv 저장
    card_path = outdir / "scorecard.csv"
    with open(card_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["module","diversity","entropy","S_eff","freq_per_min","mean_t_rec","sum_A_cut","R_thr","alive","E_total","Score"])
        w.writerow([args.module, metrics["diversity"], metrics["entropy"],
                    metrics["shuffle"]["S_eff"], metrics["shuffle"]["freq_per_min"], metrics["shuffle"]["mean_t_rec"],
                    metrics["shuffle"]["sum_A_cut"], metrics["redundancy"]["R_thr"],
                    metrics["survivability"]["alive"], metrics["energy"]["E_total"], score["Score"]])

    # 그래프
    make_plots(outdir, args.module, thr_base_smooth, thr_mtd, cutovers, attack_windows, div, red)

    # JSON 덤프
    with open(outdir/"metrics.json","w",encoding="utf-8") as jf:
        json.dump({"module":args.module, "metrics":metrics, "score":score}, jf, ensure_ascii=False, indent=2)

    print(f"[OK] metrics written to {outdir}")


if __name__ == "__main__":
    main()
