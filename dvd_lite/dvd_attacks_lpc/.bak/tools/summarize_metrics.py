import csv, glob, os, sys
from collections import defaultdict

def parse_name(path):
    b=os.path.basename(path)[:-4]  # drop .csv
    if not b.startswith("ns3_metrics_"): return None
    rest=b[len("ns3_metrics_"):]
    # robust: split from the right into 4 fields
    try:
        atk, lv, mtd, scn = rest.rsplit("_", 3)
    except ValueError:
        return None
    # normalize boolean-ish mtd
    if mtd.lower() in ("true","on"): mtd="on"
    if mtd.lower() in ("false","off"): mtd="off"
    return atk, lv, mtd, scn

rows=[]
for f in sorted(glob.glob("bus/ns3_metrics_*.csv")):
    meta=parse_name(f)
    if not meta: continue
    atk,lv,mtd,scn=meta
    with open(f, newline="") as fh:
        r=csv.DictReader(fh)
        r=list(r)
        if not r: continue
        d=r[-1]
        try:
            t=float(d.get("time_s",0) or 0)
            rx=int(d.get("rx_bytes",0) or 0)
            drop=int(d.get("drop_cnt",0) or 0)
            dup=int(d.get("dup_cnt",0) or 0)
        except: 
            continue
        thr_mbps = (rx*8.0)/(t*1e6) if t>0 else 0.0
        rows.append({
            "atk":atk,"lv":lv,"mtd":mtd,"scn":scn,
            "time_s":t,"rx_bytes":rx,"drop_cnt":drop,"dup_cnt":dup,
            "throughput_mbps":thr_mbps,
            "file":f
        })

# write flat report
os.makedirs("bus", exist_ok=True)
out="bus/impact_report.csv"
with open(out,"w",newline="") as fh:
    w=csv.DictWriter(fh, fieldnames=[
        "scn","atk","lv","mtd","time_s","rx_bytes","drop_cnt","dup_cnt","throughput_mbps","file"
    ])
    w.writeheader()
    for r in sorted(rows, key=lambda x: x["scn"]):
        w.writerow(r)

# quick on/off compare if onoff-* present (pair by prefix onoff-on vs onoff-off)
pairs=defaultdict(dict)
for r in rows:
    if r["scn"].startswith("onoff-on-"):
        key="on"
        base="on"
    elif r["scn"].startswith("onoff-off-"):
        key="off"
        base="off"
    else:
        continue
    pairs["onoff"][key]=r

# print console summary
def fmt(v): 
    return f"{v:.4f}" if isinstance(v,float) else str(v)

print("=== impact_report.csv written:", out)
print("=== latest few rows ===")
for r in sorted(rows, key=lambda x: x["file"])[-6:]:
    print(f"- {r['file']}  thr={fmt(r['throughput_mbps'])} Mb/s  rx={r['rx_bytes']}  drop={r['drop_cnt']} dup={r['dup_cnt']}")

# on/off compare (if both exist)
off=pairs.get("onoff",{}).get("off")
on =pairs.get("onoff",{}).get("on")
if off and on:
    delta = on["throughput_mbps"] - off["throughput_mbps"]
    ratio = (on["throughput_mbps"]/off["throughput_mbps"]) if off["throughput_mbps"]>0 else 0.0
    print("\n=== ON/OFF quick compare (by last onoff-* runs) ===")
    print(f"OFF: thr={fmt(off['throughput_mbps'])} Mb/s, rx={off['rx_bytes']} (scn={off['scn']})")
    print(f" ON: thr={fmt(on ['throughput_mbps'])} Mb/s, rx={on ['rx_bytes']} (scn={on ['scn']})")
    print(f" Δthr={fmt(delta)} Mb/s, ratio={fmt(ratio)}x")
else:
    print("\n(no onoff-* pair found; run scenarios/run_onoff_compare.sh to generate)")
