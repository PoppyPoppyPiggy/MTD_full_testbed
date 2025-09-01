#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DVD(bus.log) ↔ NS-3(ns3_metrics_summary_*.csv) 영향 리포트
- 시나리오별 legit 포트(5760,5000,8000) 기준 처리량/손실의 no_mtd↔mtd 차이를 표로 산출
- 입력: attack_output/<module>/(no_mtd|mtd)/level-*/ns3_metrics_summary_*.csv
- 출력: attack_output/impact_report.csv
"""
import os, glob, pandas as pd

LEGIT_PORTS = {5760,5000,8000}

def scan(root):
    base=os.path.join(root,"attack_output")
    rows=[]
    for module in sorted(next(os.walk(base))[1]):
        mdir=os.path.join(base,module)
        for leveldir in ("level-low","level-med","level-high"):
            no=os.path.join(mdir,"no_mtd",leveldir,"ns3_metrics_summary_{}_no_mtd_{}.csv".format(module,leveldir.split("-")[-1]))
            md=os.path.join(mdir,"mtd",leveldir,"ns3_metrics_summary_{}_mtd_{}.csv".format(module,leveldir.split("-")[-1]))
            if os.path.exists(no) and os.path.exists(md):
                rows.append((module, leveldir.split("-")[-1], no, md))
    return rows

def legit_throughput(df: pd.DataFrame) -> float:
    if "dstPort" not in df.columns: return 0.0
    return float(df[df["dstPort"].isin(LEGIT_PORTS)]["throughput_bps"].clip(lower=0).sum())

def loss_ratio(df: pd.DataFrame) -> float:
    tx=float(df["tx"].sum()); rx=float(df["rx"].sum())
    return 0.0 if tx<=0 else max(0.0,min(1.0,(tx-rx)/tx))

def main():
    import argparse
    ap=argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    args=ap.parse_args()

    pairs=scan(args.root)
    out=[]
    for mod, lvl, fno, fmd in pairs:
        df_no=pd.read_csv(fno)
        df_md=pd.read_csv(fmd)
        thr_no=legit_throughput(df_no)
        thr_md=legit_throughput(df_md)
        loss_no=loss_ratio(df_no)
        loss_md=loss_ratio(df_md)
        out.append({
            "module":mod,"level":lvl,
            "legit_thr_no_bps":thr_no,"legit_thr_mtd_bps":thr_md,
            "thr_improvement_ratio": (thr_md - thr_no)/max(thr_no,1e-9),
            "loss_no":loss_no,"loss_mtd":loss_md,"loss_delta":(loss_md - loss_no)
        })
    df=pd.DataFrame(out)
    outcsv=os.path.join(args.root,"attack_output","impact_report.csv")
    if not df.empty:
        df.sort_values(["module","level"]).to_csv(outcsv,index=False)
        print(df.to_string(index=False))
        print(f"[impact] saved: {outcsv}")
    else:
        print("[impact] no paired scenarios found.")

if __name__=="__main__":
    main()
