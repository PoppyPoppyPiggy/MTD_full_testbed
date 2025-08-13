#!/usr/bin/env python3
import argparse, csv, statistics as stats, os, sys

# 시간 컬럼 후보에 ts_ms 추가 (ms면 s로 변환)
CAND_TIME = ["t_sec", "t", "time", "timestamp", "ts_ms"]
METRICS   = ["loss_pct", "delay_ms", "jitter_ms", "dup_pct", "rate_limit_mbps"]

def read_csv_rows(path):
    if not os.path.exists(path):
        sys.exit(f"[ERR] timeline not found: {path}")
    rows=[]
    with open(path, newline="") as f:
        r=csv.DictReader(f)
        if not r.fieldnames:
            sys.exit(f"[ERR] empty CSV or no header: {path}")
        time_key=None
        for k in CAND_TIME:
            if k in r.fieldnames:
                time_key=k; break
        if not time_key:
            sys.exit(f"[ERR] time column not found in {r.fieldnames}")
        for row in r:
            raw=row.get(time_key,"")
            try:
                t=float(raw)
                # ts_ms면 초로 변환
                if time_key=="ts_ms": t = t/1000.0
            except:
                continue
            row["_t"]=t
            rows.append(row)
    if not rows:
        sys.exit("[ERR] no valid rows after parsing timeline")
    rows.sort(key=lambda x: x["_t"])
    return rows

def to_float(x):
    try: return float(x)
    except: return None

def window_rows(rows, size):
    out=[]; n=len(rows)
    for i in range(0, n, size):
        out.append(rows[i:i+size])
    return out

def agg_chunk(chunk):
    d = {"win_idx": None, "start": f"{chunk[0]['_t']:.3f}", "end": f"{chunk[-1]['_t']:.3f}"}
    for m in METRICS:
        vals=[to_float(r.get(m)) for r in chunk]
        vals=[v for v in vals if v is not None]
        if vals:
            mean=sum(vals)/len(vals)
            std=stats.pstdev(vals) if len(vals)>1 else 0.0
            d[f"{m}_mean"]=round(mean,3)
            d[f"{m}_std"]=round(std,3)
    return d

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--timeline", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--win", type=int, default=6)
    args=ap.parse_args()
    rows=read_csv_rows(args.timeline)
    chunks=window_rows(rows, args.win)
    feats=[]
    for i,ch in enumerate(chunks):
        d=agg_chunk(ch); d["win_idx"]=i; feats.append(d)
    base=["win_idx","start","end"]
    cols=[]
    for m in METRICS:
        k1=f"{m}_mean"; k2=f"{m}_std"
        if k1 in feats[0]: cols.extend([k1,k2])
    header=base+cols
    with open(args.out,"w",newline="") as f:
        w=csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        for r in feats: w.writerow({k:r.get(k,"") for k in header})
    print(f"[OK] wrote {args.out} ({len(feats)} windows)")

if __name__=="__main__":
    main()
