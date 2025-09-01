#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MTD ns-3 분석/시각화/스코어링 도구
- 입력: attack_output/<module>/<no_mtd|mtd>/level-<level>/ns3_metrics_summary_*.csv
- 전역 타임라인: attack_output/effect_timeline.baseline.csv, effect_timeline.mtd.csv
- 출력:
  1) 각 시나리오 폴더에 PNG 차트 3종:
     - throughput_by_flow.png, delay_jitter_by_flow.png, loss_by_flow.png
  2) 전체 요약: attack_output/mtd_scoring.csv (모듈·레벨별 no_mtd vs mtd 비교 스코어)
  3) 비교 차트(존재 시): _charts/<module>_<level>_compare.png
가정:
- 합법(legit) 포트: {5760(Flight), 5000(Companion), 8000(Simulator)}
- 공격/스캔 등 비합법 포트는 기타로 분류
"""

import os, re, math, argparse, glob, csv
from dataclasses import dataclass
from typing import Dict, Tuple, List, Optional
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

LEGIT_PORTS = {5760, 5000, 8000}
CHART_DIRNAME = "_charts"

def safemkdir(p: str):
    os.makedirs(p, exist_ok=True)

def load_summary_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    # 기대 컬럼: flow,src,dst,proto,srcPort,dstPort,tx,rx,lost,throughput_bps,delay_avg_s,jitter_avg_s
    # 누락 방지
    req = {"dstPort","tx","rx","throughput_bps","delay_avg_s","jitter_avg_s"}
    if not req.issubset(set(df.columns)):
        raise ValueError(f"[mtd_analyzer] 잘못된 요약 CSV 형식: {path}")
    return df

def summarize_by_port(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("dstPort", as_index=False).agg({
        "tx":"sum","rx":"sum","throughput_bps":"sum",
        "delay_avg_s":"mean","jitter_avg_s":"mean"
    })
    g["loss_pkts"] = g["tx"] - g["rx"]
    return g

def shannon_diversity_throughput(df: pd.DataFrame) -> float:
    legit = df[df["dstPort"].isin(LEGIT_PORTS)].copy()
    if legit.empty:
        return 0.0
    thr = legit["throughput_bps"].clip(lower=0.0)
    total = float(thr.sum())
    if total <= 0.0:
        return 0.0
    p = (thr / total).values
    H = -sum(pi * math.log(pi + 1e-12) for pi in p)
    Hmax = math.log(len(p))
    return float(H / Hmax) if Hmax > 0 else 0.0

def redundancy_score(df: pd.DataFrame, thr_min_bps: float = 10_000.0) -> float:
    """합법 포트 중 의미있는(임계치 이상) 흐름이 몇 개 살아있는지 비율"""
    legit = df[df["dstPort"].isin(LEGIT_PORTS)].copy()
    if legit.empty:
        return 0.0
    alive = (legit["throughput_bps"] >= thr_min_bps).sum()
    return float(alive) / float(len(LEGIT_PORTS))

def survivability(df: pd.DataFrame) -> float:
    """합법 포트 총 처리량(bps)"""
    legit = df[df["dstPort"].isin(LEGIT_PORTS)].copy()
    return float(legit["throughput_bps"].clip(lower=0.0).sum())

def loss_ratio(df: pd.DataFrame) -> float:
    tx = float(df["tx"].sum())
    rx = float(df["rx"].sum())
    if tx <= 0: return 0.0
    return max(0.0, min(1.0, (tx - rx)/tx))

def read_timeline(path: str) -> Optional[pd.DataFrame]:
    if not os.path.exists(path): return None
    try:
        df = pd.read_csv(path)
        # 요구 헤더: t,loss_pct,delay_ms,jitter_ms,dup_pct,rate_limit_mbps
        if "t" not in df.columns: return None
        return df
    except Exception:
        return None

def count_shuffle_events(tl: Optional[pd.DataFrame]) -> Tuple[int,float]:
    """연속 시점 간 값 변화(어느 한 컬럼이라도 변화) 횟수와 전체 길이(초)"""
    if tl is None or tl.empty:
        return 0, 0.0
    cols = [c for c in tl.columns if c != "t"]
    if not cols:
        return 0, 0.0
    tl = tl.sort_values("t").reset_index(drop=True)
    changes = 0
    for i in range(1, len(tl)):
        prev = tl.loc[i-1, cols]
        cur  = tl.loc[i, cols]
        if (prev.values != cur.values).any():
            changes += 1
    duration = float(tl["t"].iloc[-1] - tl["t"].iloc[0]) if len(tl) >= 2 else 0.0
    return changes, duration

@dataclass
class Scenario:
    module: str
    mode: str     # "no_mtd" | "mtd"
    level: str
    dirpath: str
    csv_path: str

def scan_scenarios(root: str) -> Dict[Tuple[str,str,str], Scenario]:
    """attack_output/<module>/<mode>/level-<level>/ns3_metrics_summary_*.csv"""
    out: Dict[Tuple[str,str,str], Scenario] = {}
    base = os.path.join(root, "attack_output")
    for module in next(os.walk(base))[1]:
        mdir = os.path.join(base, module)
        for mode in ("no_mtd","mtd"):
            mm = os.path.join(mdir, mode)
            if not os.path.isdir(mm): continue
            for d in next(os.walk(mm))[1]:
                if not d.startswith("level-"): continue
                level = d.split("level-")[-1]
                sdir = os.path.join(mm, d)
                csvs = glob.glob(os.path.join(sdir, "ns3_metrics_summary_*.csv"))
                if not csvs: continue
                csv_path = max(csvs, key=os.path.getmtime)
                key = (module, mode, level)
                out[key] = Scenario(module, mode, level, sdir, csv_path)
    return out

def chart_throughput(df_by_port: pd.DataFrame, title: str, out_png: str):
    plt.figure()
    plt.bar(df_by_port["dstPort"].astype(str), df_by_port["throughput_bps"]/1e6)
    plt.ylabel("Throughput (Mbps)")
    plt.title(title)
    plt.tight_layout()
    plt.savefig(out_png); plt.close()

def chart_delay_jitter(df_by_port: pd.DataFrame, title: str, out_png: str):
    plt.figure()
    x = df_by_port["dstPort"].astype(str)
    plt.plot(x, df_by_port["delay_avg_s"], marker="o", label="delay_avg_s")
    plt.plot(x, df_by_port["jitter_avg_s"], marker="s", label="jitter_avg_s")
    plt.ylabel("Seconds")
    plt.title(title)
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_png); plt.close()

def chart_loss(df_by_port: pd.DataFrame, title: str, out_png: str):
    plt.figure()
    plt.bar(df_by_port["dstPort"].astype(str), (df_by_port["tx"]-df_by_port["rx"]))
    plt.ylabel("Lost Packets (pkts)")
    plt.title(title)
    plt.tight_layout()
    plt.savefig(out_png); plt.close()

def pair_compare_chart(module: str, level: str, thr_no: float, thr_mtd: float, out_png: str):
    plt.figure()
    plt.bar(["no_mtd","mtd"], [thr_no/1e6, thr_mtd/1e6])
    plt.ylabel("Legit Throughput (Mbps)")
    plt.title(f"{module} level-{level} legit throughput")
    plt.tight_layout()
    plt.savefig(out_png); plt.close()

def compute_scores(root: str, scenarios: Dict[Tuple[str,str,str], Scenario], save_charts: bool=True) -> pd.DataFrame:
    base = os.path.join(root, "attack_output")
    charts_root = os.path.join(base, CHART_DIRNAME)
    safemkdir(charts_root)

    # 전역 타임라인
    tl_base = read_timeline(os.path.join(base, "effect_timeline.baseline.csv"))
    tl_mtd  = read_timeline(os.path.join(base, "effect_timeline.mtd.csv"))
    chg_base, dur_base = count_shuffle_events(tl_base)
    chg_mtd,  dur_mtd  = count_shuffle_events(tl_mtd)
    rate_base = (chg_base / (dur_base/60.0)) if dur_base > 0 else 0.0
    rate_mtd  = (chg_mtd  / (dur_mtd /60.0)) if dur_mtd  > 0 else 0.0

    rows = []
    # 1) 각 시나리오별 기본 차트 생성
    for key, sc in scenarios.items():
        df = load_summary_csv(sc.csv_path)
        dfp = summarize_by_port(df)
        if save_charts:
            chart_throughput(dfp, f"{sc.module} {sc.mode} level-{sc.level}", os.path.join(sc.dirpath, "throughput_by_flow.png"))
            chart_delay_jitter(dfp, f"{sc.module} {sc.mode} level-{sc.level}", os.path.join(sc.dirpath, "delay_jitter_by_flow.png"))
            chart_loss(dfp, f"{sc.module} {sc.mode} level-{sc.level}", os.path.join(sc.dirpath, "loss_by_flow.png"))

    # 2) 모듈·레벨 페어 매칭(no_mtd vs mtd)
    keys = set((m,l) for (m,_mode,l) in scenarios.keys())
    for (module, level) in sorted(keys):
        no_key  = (module, "no_mtd", level)
        mtd_key = (module, "mtd",    level)
        if no_key not in scenarios or mtd_key not in scenarios:
            # 페어가 없으면 점수는 건너뛰되, 단일 요약은 남김
            continue

        sc_no  = scenarios[no_key]
        sc_mtd = scenarios[mtd_key]
        df_no  = summarize_by_port(load_summary_csv(sc_no.csv_path))
        df_mtd = summarize_by_port(load_summary_csv(sc_mtd.csv_path))

        # Metric 원시치
        div_no  = shannon_diversity_throughput(df_no)
        div_mtd = shannon_diversity_throughput(df_mtd)

        red_no  = redundancy_score(df_no)
        red_mtd = redundancy_score(df_mtd)

        thr_no  = survivability(df_no)   # legit throughput (bps)
        thr_mtd = survivability(df_mtd)

        loss_no  = loss_ratio(load_summary_csv(sc_no.csv_path))
        loss_mtd = loss_ratio(load_summary_csv(sc_mtd.csv_path))

        # Shuffle rate (전역 타임라인 사용: 실험 전체 공통 가정)
        srate_no, srate_mtd = rate_base, rate_mtd

        # ---- 스코어링 ----
        # SV(생존성): mtd가 no_mtd 대비 얼마나 유지/개선했는가 (0..1)
        sv = 0.0
        if thr_no <= 0 and thr_mtd > 0:
            sv = 1.0
        elif thr_no > 0:
            sv = max(0.0, min(1.0, thr_mtd / thr_no))

        # D(분산도): 샤논 엔트로피 정규화 (0..1)
        d_score = max(0.0, min(1.0, div_mtd))

        # R(대체경로): 임계치 이상 살아있는 합법 포트 비율 (0..1)
        r_score = max(0.0, min(1.0, red_mtd))

        # S(셔플 효율): 개선폭 / 셔플율 (셔플율이 0이면 개선 있으면 1, 없으면 0)
        improvement = max(0.0, sv - max(0.0, min(1.0, (thr_no / max(thr_no,1e-9)))))  # 보수적으로 0으로 귀결됨
        # 위 improvement 정의가 너무 보수적이므로 실제 개선율 = (thr_mtd - thr_no)/max(thr_no,1e-9)로 조정
        improvement = max(0.0, (thr_mtd - thr_no) / max(thr_no, 1e-9))
        if srate_mtd <= 1e-9:
            s_score = 1.0 if improvement > 0 else 0.0
        else:
            # 분모 폭주 방지: 분당 셔플율 기준
            s_score = max(0.0, min(1.0, improvement / (srate_mtd + 0.1)))

        # E(에너지): 셔플율 패널티 (낮을수록 좋음) → 1/(1+rate)
        e_score = 1.0 / (1.0 + srate_mtd)

        # 가중합 (합=1.0): D 0.20, S 0.25, R 0.20, SV 0.25, E 0.10
        total = 0.20*d_score + 0.25*s_score + 0.20*r_score + 0.25*sv + 0.10*e_score

        rows.append({
            "module": module, "level": level,
            "thr_legit_no_bps": thr_no, "thr_legit_mtd_bps": thr_mtd,
            "loss_no": loss_no, "loss_mtd": loss_mtd,
            "div_no": div_no, "div_mtd": div_mtd,
            "red_no": red_no, "red_mtd": red_mtd,
            "shuffle_rate_per_min_no": srate_no, "shuffle_rate_per_min_mtd": srate_mtd,
            "score_D": d_score, "score_S": s_score, "score_R": r_score, "score_SV": sv, "score_E": e_score,
            "score_total": total
        })

        # 비교 차트
        if save_charts:
            out_png = os.path.join(base, CHART_DIRNAME, f"{module}_level-{level}_compare.png")
            pair_compare_chart(module, level, thr_no, thr_mtd, out_png)

    df_scores = pd.DataFrame(rows)
    if not df_scores.empty:
        out_csv = os.path.join(base, "mtd_scoring.csv")
        df_scores.sort_values(["module","level"]).to_csv(out_csv, index=False)
    return pd.DataFrame(rows)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, help="ATK_DIR (e.g., /home/kali/.../dvd_attacks_lpc)")
    ap.add_argument("--module", default="", help="특정 모듈만(옵션)")
    ap.add_argument("--mode", default="", help="no_mtd|mtd (옵션)")
    ap.add_argument("--level", default="", help="low|med|high (옵션)")
    ap.add_argument("--save-charts", action="store_true", help="PNG 차트 저장")
    args = ap.parse_args()

    root = args.root
    base = os.path.join(root, "attack_output")
    safemkdir(os.path.join(base, CHART_DIRNAME))

    scenarios = scan_scenarios(root)

    # 필터링(옵션)
    if args.module:
        scenarios = {k:v for k,v in scenarios.items() if k[0]==args.module}
    if args.mode:
        scenarios = {k:v for k,v in scenarios.items() if k[1]==args.mode}
    if args.level:
        scenarios = {k:v for k,v in scenarios.items() if k[2]==args.level}

    if not scenarios:
        raise SystemExit("[mtd_analyzer] 분석할 시나리오(ns3_metrics_summary_*.csv)가 없습니다.")

    df_scores = compute_scores(root, scenarios, save_charts=args.save_charts)
    # 콘솔 요약
    if not df_scores.empty:
        print(df_scores.to_string(index=False))
    else:
        print("[mtd_analyzer] 페어(no_mtd vs mtd)가 없어 점수표는 생성되지 않았습니다. (단일 차트는 생성됨)")

if __name__ == "__main__":
    main()
