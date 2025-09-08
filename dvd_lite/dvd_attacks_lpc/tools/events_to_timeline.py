import csv, sys, re, os, argparse
def parse_imp(s,k,default=0.0):
    m=re.search(rf"{k}\s*=\s*([0-9]+(?:\.[0-9]+)?)",s,re.I); return float(m.group(1)) if m else default
ap=argparse.ArgumentParser()
ap.add_argument("--events"); ap.add_argument("--scn"); ap.add_argument("-o","--out"); ap.add_argument("--sim",type=float,default=40.0)
a=ap.parse_args()
ev=a.events or (f"bus/events_{a.scn}.csv" if a.scn else None)
assert ev and os.path.exists(ev), f"events csv not found: {ev}"
rows=[]; 
with open(ev, newline="") as f:
    head=f.readline(); f.seek(0)
    delim="," if head.count(",")>=head.count(";") else ";"
    R=csv.reader(f, delimiter=delim); header=None
    for i,cols in enumerate(R):
        if i==0: header=[c.strip().lower() for c in cols]; continue
        d={header[j]: cols[j] if j<len(cols) else "" for j in range(len(header))}
        rows.append(d)
out=a.out or f"bus/effect_timeline_{os.path.basename(ev).split('events_')[-1]}"
with open(out,"w",newline="") as f:
    w=csv.writer(f); w.writerow(["t_apply_s","loss_pct","delay_ms","jitter_ms","dup_pct"])
    for d in rows:
        j=" ".join(f"{k}={v}" for k,v in d.items()); up=j.upper()
        if "MTD" in up and "APPLY" in up:
            t=float(d.get("t_s") or d.get("time_s") or d.get("t") or 0.0)
            w.writerow([t, parse_imp(j,"loss_pct"), parse_imp(j,"delay_ms"), parse_imp(j,"jitter_ms"), parse_imp(j,"dup_pct")])
    # revert(0) 기록
    for d in rows:
        j=" ".join(f"{k}={v}" for k,v in d.items()); up=j.upper()
        if "MTD" in up and "REVERT" in up:
            t=float(d.get("t_s") or d.get("time_s") or d.get("t") or 0.0)
            w.writerow([t,0,0,0,0])
    w.writerow([a.sim,0,0,0,0])
print("WROTE", out)
