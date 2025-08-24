#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
score_cti_mtd.py
- bus.log + effect_timeline.csv + (optional) ns3_metrics.csv -> score.json
- 지표: diversity, redundancy, shuffle_efficiency_s, energy_units, survivability_idx (+ ns3 raw)
"""
import json, csv, math, argparse, time
from pathlib import Path
from collections import Counter

def read_lines(p: Path):
  if not p.exists(): return []
  return [l.rstrip("\n") for l in p.open("r", errors="ignore").readlines()]

def parse_bus(path: Path):
  ev=[]
  for raw in read_lines(path):
    if not raw.strip(): continue
    parts = raw.replace("\t"," ").split()
    if len(parts) < 2: continue
    try:
      ts = int(parts[0]); tag = parts[1]
    except: continue
    kv={}
    for tok in parts[2:]:
      if "=" in tok:
        k,v = tok.split("=",1); kv[k]=v
    ev.append((ts,tag,kv))
  ev.sort(key=lambda x:x[0]); return ev

def read_ns3_metrics(p: Path):
  res={}
  if not p.exists(): return res
  with p.open() as f:
    rdr=csv.reader(f); next(rdr,None)
    for row in rdr:
      if not row: continue
      m=row[0]; v=row[1] if len(row)>1 else ""
      try: res[m]=float(v)
      except: res[m]=v
  return res

def compute_metrics(ev, ns3):
  # Diversity: entropy of (ip:port) states sequence
  states=[]; last=None
  for _,tag,kv in ev:
    ip = kv.get("ip") or kv.get("target") or (kv.get("value") if (tag=="cti_set" and kv.get("key")=="TARGET_IP") else "")
    port = kv.get("port") or kv.get("new") or (kv.get("value") if (tag=="cti_set" and kv.get("key")=="MAVLINK_PORT") else "")
    if tag in ("mtd","mtd_done","mtd_porthop","cti_set","attack"):
      st=f"{ip}:{port}"
      if st and st!=last: states.append(st); last=st
  cnt=Counter(states)
  probs=[c/sum(cnt.values()) for c in cnt.values()] if cnt else []
  H = -sum(p*math.log(p+1e-12,2) for p in probs) if probs else 0.0
  Hmax = math.log(len(probs),2) if probs else 1.0
  diversity=(H/Hmax) if Hmax>0 else 0.0

  # Redundancy: repeated same MTD action in short succession (windowed)
  mtd_actions=[]
  for ts,tag,kv in ev:
    if tag in ("mtd","mtd_done","mtd_porthop"):
      a = kv.get("action") or kv.get("what") or "unknown"
      mtd_actions.append((ts,a))
  redundant=0; total=len(mtd_actions)
  for i in range(1, len(mtd_actions)):
    if mtd_actions[i][1] == mtd_actions[i-1][1] and (mtd_actions[i][0]-mtd_actions[i-1][0]) < 5000:
      redundant += 1
  redundancy = (redundant/max(1,total-1)) if total>1 else 0.0

  # Shuffle efficiency: avg time defender buys before next follow_* attack
  last_mtd=None; gaps=[]
  for ts,tag,kv in ev:
    if tag in ("mtd","mtd_done","mtd_porthop"): last_mtd = ts
    if tag=="attack" and kv.get("type","").startswith("follow_") and last_mtd:
      gaps.append((ts-last_mtd)/1000.0); last_mtd=None
  shuffle_eff = sum(gaps)/len(gaps) if gaps else 0.0

  # Energy cost proxy
  weights={"ip_shuffle":1.0,"port_hop":0.5,"port_hop_socat":0.6}
  e_sum=0.0
  for _,tag,kv in ev:
    if tag in ("mtd","mtd_done"):
      a=kv.get("action") or kv.get("what") or ""
      if a in weights: e_sum+=weights[a]

  # Survivability from ns3
  thr=float(ns3.get("throughput_avg",0.0)); delay=float(ns3.get("delay_avg",0.0))
  lost=float(ns3.get("lost_packets",0.0)); rx=float(ns3.get("rx_bytes",0.0))+1e-9
  sig=1.0/(1.0+math.exp(-(thr/10.0 - 1.0)))
  loss_ratio=min(1.0, lost/(lost + (rx/250.0)))
  survivability = sig * math.exp(-delay/0.2) * (1.0 - loss_ratio)

  return {
    "diversity": diversity,
    "redundancy": redundancy,
    "shuffle_efficiency_s": shuffle_eff,
    "energy_units": e_sum,
    "survivability_idx": survivability
  }

def main():
  ap=argparse.ArgumentParser()
  ap.add_argument("bus", help="attack_output/bus.log")
  ap.add_argument("timeline", help="attack_output/effect_timeline.csv")
  ap.add_argument("--ns3", default="attack_output/ns3_metrics.csv")
  ap.add_argument("-o","--out", default="attack_output/score.json")
  args=ap.parse_args()

  bus = Path(args.bus); tl = Path(args.timeline)
  ns3 = read_ns3_metrics(Path(args.ns3))
  ev = parse_bus(bus)

  score = {
    "version": "1.1",
    "timestamp": int(time.time()),
    "files": {"bus": str(bus), "timeline": str(tl), "ns3": args.ns3},
    "ns3_metrics": ns3,
  }
  score.update(compute_metrics(ev, ns3))

  Path(args.out).parent.mkdir(parents=True, exist_ok=True)
  with Path(args.out).open("w", encoding="utf-8") as f:
    json.dump(score, f, ensure_ascii=False, indent=2)

if __name__=="__main__":
  main()
