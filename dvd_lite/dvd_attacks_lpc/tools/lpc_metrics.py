#!/usr/bin/env python3
import csv, os, statistics

base = os.path.dirname(os.path.dirname(__file__))
outdir = os.path.join(base, "dvd_attacks_lpc", "attack_output")
src = os.path.join(outdir, "effect_timeline.csv")
dst = os.path.join(outdir, "window_features.csv")
WIN = int(os.environ.get("WIN","6"))

rows=[]
with open(src) as f:
    r=csv.DictReader(f)
    for x in r:
        rows.append({k:float(v) if k!="t_sec" else float(v) for k,v in x.items()})
rows.sort(key=lambda x:x["t_sec"])

features=[]
for i in range(0, len(rows), WIN):
    chunk = rows[i:i+WIN]
    if not chunk: continue
    def stat(k):
        vals=[c[k] for c in chunk]
        return statistics.fmean(vals), (statistics.pstdev(vals) if len(vals)>1 else 0.0)
    entry={"start":chunk[0]["t_sec"],"end":chunk[-1]["t_sec"]}
    for k in ["loss_pct","delay_ms","jitter_ms","dup_pct","rate_limit_mbps"]:
        m,s = stat(k); entry[f"{k}_mean"]=m; entry[f"{k}_std"]=s
    features.append(entry)

with open(dst,"w",newline="") as f:
    cols=["start","end"]+[f"{k}_{s}" for k in ["loss_pct","delay_ms","jitter_ms","dup_pct","rate_limit_mbps"] for s in ("mean","std")]
    w=csv.DictWriter(f,fieldnames=cols); w.writeheader(); w.writerows(features)
print(dst)
