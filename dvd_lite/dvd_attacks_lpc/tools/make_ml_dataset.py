#!/usr/bin/env python3
import csv, json, re, sys, os
from statistics import mean

def parse_bus(path):
    rx=re.compile(r'([A-Za-z0-9_]+)=([^\s]+)')
    ev=[]
    for line in open(path,encoding="utf-8",errors="ignore"):
        line=line.strip()
        if not line: continue
        p=line.split("\t")
        if len(p)<3: continue
        ts=float(p[0]); 
        if ts>1e12: ts/=1000.0
        tag=p[1]; kv=dict(rx.findall(" ".join(p[2:])))
        ev.append((ts,tag,kv))
    ev.sort(key=lambda x:x[0]); return ev

def load_ns3(path):
    ns3={}
    if os.path.exists(path):
        r=csv.reader(open(path)); next(r,None)
        for row in r:
            if not row: continue
            k=row[0]; v=row[1] if len(row)>1 else ""
            try: ns3[k]=float(v)
            except: ns3[k]=v
    return ns3

def last_effect_before(t, tl_rows):
    eff={"loss_pct":0.0,"delay_ms":0.0,"jitter_ms":0.0}
    for tt,vals in tl_rows:
        if tt<=t: 
            eff.update({k:float(vals.get(k,0.0)) for k in eff})
        else: break
    return eff

def parse_timeline(path):
    rows=[]
    if os.path.exists(path):
        R=csv.DictReader(open(path))
        for r in R:
            rows.append((float(r["t"]), r))
    rows.sort(key=lambda x:x[0]); return rows

def main(bus, tl, ns3, out_csv):
    ev=parse_bus(bus)
    tl_rows=parse_timeline(tl)
    ns3m=load_ns3(ns3) if ns3 else {}

    # 각 MTD 이벤트를 샘플로
    samples=[]
    for i,(ts,tag,kv) in enumerate(ev):
        if tag!="mtd": continue
        action=kv.get("action","")
        if action not in ("ip_shuffle","port_hop","port_hop_socat","bridge_hop"): 
            continue

        # 다음 follow 공격 시점/지연
        nxt=next(((ts2,kv2) for (ts2,tag2,kv2) in ev[i:] 
                  if tag2=="attack" and kv2.get("type","").startswith("follow_")), None)
        follow_latency = (nxt[0]-ts) if nxt else None

        # 다음 CTI ip_change 시점/지연
        cti=next(((ts2,kv2) for (ts2,tag2,kv2) in ev[i:] 
                  if tag2=="cti" and kv2.get("type")=="ip_change"), None)
        detect_latency = (cti[0]-ts) if cti else None

        # MTD 직전 상태(3초 윈도)
        t0=ts-3.0
        pre_loss=[]; pre_delay=[]; pre_jitter=[]
        for tt,row in tl_rows:
            if tt>ts: break
            if tt>=t0:
                pre_loss.append(float(row.get("loss_pct",0) or 0))
                pre_delay.append(float(row.get("delay_ms",0) or 0))
                pre_jitter.append(float(row.get("jitter_ms",0) or 0))
        feat_pre_loss = mean(pre_loss) if pre_loss else 0.0
        feat_pre_delay= mean(pre_delay) if pre_delay else 0.0
        feat_pre_jitter=mean(pre_jitter) if pre_jitter else 0.0

        # 라벨: disruption window (= follow_latency)
        # 보조 라벨: ns3 처리량/손실(있으면)
        sample={
            "t": ts,
            "mtd_action": action,
            "drop_old": kv.get("drop_old",""),
            "grace": kv.get("grace","").rstrip("s"),
            "feat_pre_loss": feat_pre_loss,
            "feat_pre_delay": feat_pre_delay,
            "feat_pre_jitter": feat_pre_jitter,
            "label_disruption_window": follow_latency if follow_latency is not None else "",
            "ns3_throughput_avg": ns3m.get("throughput_avg",""),
            "ns3_lost_packets": ns3m.get("lost_packets","")
        }
        samples.append(sample)

    # 쓰기
    os.makedirs(os.path.dirname(out_csv), exist_ok=True)
    fields=["t","mtd_action","drop_old","grace","feat_pre_loss","feat_pre_delay","feat_pre_jitter",
            "label_disruption_window","ns3_throughput_avg","ns3_lost_packets"]
    w=csv.DictWriter(open(out_csv,"w",newline=""), fieldnames=fields)
    w.writeheader(); [w.writerow(s) for s in samples]
    print(f"[OK] dataset rows={len(samples)} -> {out_csv}")

if __name__=="__main__":
    if len(sys.argv)<3:
        print("usage: make_ml_dataset.py <bus.log> <effect_timeline.csv> [--ns3 ns3_metrics.csv] -o dataset.csv")
        sys.exit(1)
    bus=sys.argv[1]; tl=sys.argv[2]; ns3=None; out="attack_output/dataset.csv"
    args=sys.argv[3:]
    for i,a in enumerate(args):
        if a=="--ns3" and i+1<len(args): ns3=args[i+1]
        if a=="-o"   and i+1<len(args): out=args[i+1]
    main(bus, tl, ns3, out)
