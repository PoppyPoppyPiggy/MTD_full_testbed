#!/usr/bin/env python3
import re, sys, csv, argparse, os, datetime

p = argparse.ArgumentParser()
p.add_argument("buslog")
p.add_argument("--dvd", default=None)
p.add_argument("-o","--out", required=True)
args = p.parse_args()

events=[]

def add(t,etype,target,desc,color="255,0,0",duration=2.0):
    # time_s,type,target,desc,color,duration_s
    events.append([t,etype,target,desc,color,duration])

ts_re = re.compile(r't=(\d+\.?\d*)')
def t_of(line):
    m=ts_re.search(line); 
    return float(m.group(1)) if m else None

with open(args.buslog,"r",errors="ignore") as f:
    for line in f:
        t=t_of(line)
        if t is None: continue
        s=line.lower()
        if "attack_start" in s or "lpc_start" in s:
            add(t,"NODE","GCS","ATTACK START","231,76,60",3.0)
        if "attack_end" in s or "lpc_end" in s:
            add(t,"NODE","GCS","ATTACK END","39,174,96",3.0)
        if "mtd_apply" in s or "tc_filter apply" in s:
            add(t,"LINK","FC-GCS","MTD APPLY","52,152,219",3.0)
        if "mtd_revert" in s or "tc_filter revert" in s:
            add(t,"LINK","FC-GCS","MTD REVERT","155,89,182",3.0)

if args.dvd and os.path.exists(args.dvd):
    with open(args.dvd,"r",errors="ignore") as f:
        for line in f:
            t=t_of(line)
            if t is None: continue
            s=line.lower()
            if "cpu%>" in s or "mem%>" in s:
                add(t,"NODE","CC","DVD load spike","241,196,15",2.0)

os.makedirs(os.path.dirname(args.out), exist_ok=True)
with open(args.out,"w",newline="") as f:
    w=csv.writer(f)
    w.writerow(["time_s","type","target","desc","color","duration_s"])
    w.writerows(sorted(events, key=lambda x:x[0]))
print("Wrote", args.out, "events:", len(events))
