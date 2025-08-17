#!/usr/bin/env python3
# ml/attach_attack_score.py
import pandas as pd, numpy as np, sys
inp=sys.argv[1]; out=sys.argv[2]
df=pd.read_parquet(inp) if inp.endswith(".parquet") else pd.read_csv(inp)

# QoS 기반 점수(가중합): loss, delay, jitter, dup, throughput cap
w = dict(loss=0.30, delay=0.25, jitter=0.15, dup=0.10, rate=0.20)
def nz(x): return 0.0 if x is None or np.isnan(x) else float(x)

def row_score(r):
    # 값 스케일링(대략): loss(0~100), delay/jitter(ms)→/100, dup(0~100), rate cap(% 감소)
    loss = nz(r.get("loss_mean"))                          # %
    delay = nz(r.get("delay_mean"))/100.0*100.0            # 100ms=100점
    jitter = nz(r.get("jitter_mean"))/100.0*100.0
    dup = nz(r.get("dup_mean"))                            # %
    # rate_limit_mbps가 있으면 cap%로 환산, 없으면 throughput 기준 역비
    cap = r.get("rate_limit_mbps")
    if cap is not None and not np.isnan(cap) and cap>0:
        # cap이 작을수록 가혹 →  (ref 50Mbps) 기준
        rate_penalty = min(100.0, (1.0 - cap/50.0)*100.0)
    else:
        thr = r.get("rate_mean")
        rate_penalty = 0.0 if thr is None or np.isnan(thr) else min(100.0, (1.0 - min(thr,50.0)/50.0)*100.0)
    s = (w["loss"]*loss + w["delay"]*delay + w["jitter"]*jitter +
         w["dup"]*dup + w["rate"]*rate_penalty)
    return max(0.0, min(100.0, s))

df["attack_score"] = df.apply(row_score, axis=1)

# 로그 강도 보정(옵션): module/level 있으면 구간 가점
if "level" in df.columns:
    gain=dict(low=0, medium=5, high=10)
    df["attack_score"]=df["attack_score"]+df["level"].map(lambda x: gain.get(str(x).lower(),0))

if out.endswith(".parquet"): df.to_parquet(out, index=False)
else: df.to_csv(out, index=False)
print("[OK] attack_score attached ->", out)
