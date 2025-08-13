#!/usr/bin/env python3
import csv, sys, time
from collections import defaultdict

# Very simple rules (tune as needed)
INT2LOSS = {"low":3, "mid":7, "high":12}
BASE = {"loss_pct":0, "delay_ms":0, "jitter_ms":0, "dup_pct":0, "rate_limit_mbps":0}

def parse_bus(path):
    rows=[]
    with open(path) as f:
        for line in f:
            line=line.strip()
            if not line or "," not in line: continue
            # format: epoch,act=...,phase=...,target=...,k=v,...
            parts=line.split(",")
            t=int(parts[0])
            kv={"t":t}
            for p in parts[1:]:
                if "=" in p:
                    k,v=p.split("=",1); kv[k]=v
            rows.append(kv)
    return rows

def bake(rows):
    # group in 10s bins -> produce cumulative small effects
    bins=defaultdict(lambda: BASE.copy())
    for r in rows:
        t = int(r["t"]); bucket = (t//10)*10
        b = dict(bins[bucket])
        act = r.get("act","")
        if act=="telemetry_trickle_jam":
            loss = INT2LOSS.get(r.get("intensity","low"),3)
            b["loss_pct"] = min(100, b["loss_pct"] + loss//2)
            b["jitter_ms"] += 2
        elif act=="mavlink_param_drift":
            b["delay_ms"] += 1
        bins[bucket]=b
    # flatten & smooth
    out=[]
    acc={"loss_pct":0,"delay_ms":0,"jitter_ms":0,"dup_pct":0,"rate_limit_mbps":0}
    for t in sorted(bins.keys()):
        for k in acc:
            acc[k] = max(acc[k], bins[t][k])  # monotone non-decreasing (slow attack)
        out.append([t, acc["loss_pct"], acc["delay_ms"], acc["jitter_ms"], acc["dup_pct"], acc["rate_limit_mbps"]])
    return out

def main():
    bus = sys.argv[1]
    out = sys.argv[2]
    rows = parse_bus(bus)
    eff = bake(rows)
    with open(out,"w",newline="") as f:
        w=csv.writer(f)
        w.writerow(["t_sec","loss_pct","delay_ms","jitter_ms","dup_pct","rate_limit_mbps"])
        for r in eff:
            w.writerow(r)

if __name__=="__main__":
    if len(sys.argv)<3:
        print("usage: gen_effects_timeline.py bus.log effect_timeline.csv"); sys.exit(1)
    main()
