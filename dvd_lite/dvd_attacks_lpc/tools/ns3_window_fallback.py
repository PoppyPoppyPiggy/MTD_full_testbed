#!/usr/bin/env python3
import sys, pandas as pd, numpy as np

ns3="attack_output/ns3_metrics.csv"
out="attack_output/window_features.csv"
WIN=int(os.environ.get("WIN","3"))
STRIDE=int(os.environ.get("STRIDE","1"))

df=pd.read_csv(ns3)
df.columns=[c.strip().lower() for c in df.columns]

# 시간 컬럼 탐색
for c in ["t","time","ts","timestamp","start_t"]:
    if c in df.columns:
        df[c]=pd.to_numeric(df[c],errors="coerce")
        df=df.dropna(subset=[c]).sort_values(c)
        tcol=c; break
else:
    df["t"]=np.arange(len(df),dtype=float); tcol="t"

t=df[tcol].to_numpy(float)
t0,t1=float(np.min(t)),float(np.max(t))
rows=[]; cur=t0

cols={
  "throughput":["throughput_mbps","rate","tx_rate"],
  "delay":["delay_ms","delay","latency","rtt"],
  "jitter":["jitter_ms","jitter"],
  "loss":["loss_pct","loss","packet_loss"],
  "dup":["dup_pct","dup","duplicates"]
}
def pick(cands): 
    for c in cands: 
        if c in df.columns: return c
    return None
colmap={k:pick(v) for k,v in cols.items()}

while cur<=t1:
    nxt=cur+WIN; w=df[(df[tcol]>=cur)&(df[tcol]<nxt)]
    if len(w)>0:
        rows.append({
          "start_t":cur,"end_t":nxt,
          "rate_mean":float(np.nanmean(pd.to_numeric(w[colmap["throughput"]],errors="coerce"))) if colmap["throughput"] else np.nan,
          "delay_mean":float(np.nanmean(pd.to_numeric(w[colmap["delay"]],errors="coerce"))) if colmap["delay"] else np.nan,
          "jitter_mean":float(np.nanmean(pd.to_numeric(w[colmap["jitter"]],errors="coerce"))) if colmap["jitter"] else np.nan,
          "loss_mean":float(np.nanmean(pd.to_numeric(w[colmap["loss"]],errors="coerce"))) if colmap["loss"] else np.nan,
          "dup_mean":float(np.nanmean(pd.to_numeric(w[colmap["dup"]],errors="coerce"))) if colmap["dup"] else np.nan,
        })
    cur+=STRIDE

pd.DataFrame(rows).to_csv(out,index=False)
print(f"[OK] synthesized {len(rows)} windows -> {out}")
