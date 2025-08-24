#!/usr/bin/env python3
import csv, re, json, sys, os
from collections import defaultdict

def parse_bus(path):
    ev=[]
    rx=re.compile(r'([A-Za-z0-9_]+)=([^\s]+)')
    with open(path,encoding="utf-8",errors="ignore") as f:
        for line in f:
            line=line.strip()
            if not line: continue
            parts=line.split("\t")
            if len(parts)<3: continue
            try:
                ts=float(parts[0])
                if ts>1e12: ts/=1000.0   # epoch ms -> s
            except: 
                continue
            tag=parts[1]
            kv=dict(rx.findall(" ".join(parts[2:])))
            ev.append((ts,tag,kv))
    ev.sort(key=lambda x:x[0])
    return ev

def parse_timeline(path):
    if not os.path.exists(path): return []
    rows=[]
    with open(path,newline="") as f:
        r=csv.DictReader(f)
        for row in r:
            try:
                t=float(row.get("t","0") or 0)
            except:
                continue
            vals={}
            for k in ["loss_pct","delay_ms","jitter_ms","dup_pct","rate_limit_mbps"]:
                v=row.get(k,"")
                try: vals[k]=float(v) if v!="" else 0.0
                except: vals[k]=0.0
            rows.append((t,vals))
    rows.sort(key=lambda x:x[0])
    return rows

def integral_from_hold(rows, key):
    if not rows: return 0.0, 0.0
    area=0.0
    end=rows[-1][0]
    for i,(t,vals) in enumerate(rows):
        t_next = rows[i+1][0] if i+1 < len(rows) else end
        dt = max(0.0, t_next - t)
        area += vals.get(key,0.0)*dt
    duration = end - rows[0][0] if end>=rows[0][0] else 0.0
    return area, duration

def first_after(ev, t0, filt):
    for ts,tag,kv in ev:
        if ts>=t0 and filt(tag,kv):
            return ts,tag,kv
    return None

def main(bus_path, tl_path, ns3_metrics_path=None, out_path=None):
    ev=parse_bus(bus_path)
    tl=parse_timeline(tl_path)

    # --- CTI 메트릭 ---
    mtd_times=[]
    for ts,tag,kv in ev:
        if tag!="mtd": continue
        act=kv.get("action","")
        if act in ("ip_shuffle","port_hop","bridge_hop","port_hop_socat"):
            mtd_times.append((ts,act,kv))

    cti_lat=[]; follow_lat=[]; ip_acc=[]; port_acc=[]
    latest_cti_ip=None

    for ts,tag,kv in ev:
        if tag=="cti" and kv.get("type")=="ip_change":
            latest_cti_ip=kv.get("new")

        if tag=="mtd" and kv.get("action")=="ip_shuffle":
            nxt=first_after(ev, ts, lambda t,kv2: t=="cti" and kv2.get("type")=="ip_change")
            if nxt: cti_lat.append(nxt[0]-ts)

        if tag=="attack" and kv.get("type","").startswith("follow_"):
            atk_ip=kv.get("ip")
            prev_cti=None
            for ts2,tag2,kv2 in reversed(ev):
                if ts2>ts: continue
                if tag2=="cti" and kv2.get("type")=="ip_change":
                    prev_cti=(ts2,kv2); break
            if prev_cti:
                follow_lat.append(ts - prev_cti[0])
                ip_acc.append(1.0 if atk_ip==prev_cti[1].get("new") else 0.0)

    for ts,tag,kv in ev:
        if tag=="mtd" and kv.get("action") in ("port_hop","port_hop_socat"):
            newp=kv.get("new")
            if not newp: continue
            nxt=first_after(ev, ts, lambda t,kv2: t=="attack" and kv2.get("type")=="follow_flood")
            if nxt: port_acc.append(1.0 if nxt[2].get("port")==newp else 0.0)

    loss_area, dur = integral_from_hold(tl, "loss_pct")
    delay_area, _  = integral_from_hold(tl, "delay_ms")
    jitter_area,_  = integral_from_hold(tl, "jitter_ms")

    metrics={
      "cti": {
        "events_mtd": len(mtd_times),
        "events_cti": sum(1 for ts,t,kv in ev if t=="cti" and kv.get("type")=="ip_change"),
        "detect_latency_mean_s": (sum(cti_lat)/len(cti_lat) if cti_lat else None),
        "followup_latency_mean_s": (sum(follow_lat)/len(follow_lat) if follow_lat else None),
        "ip_tracking_accuracy": (sum(ip_acc)/len(ip_acc) if ip_acc else None),
        "port_tracking_accuracy": (sum(port_acc)/len(port_acc) if port_acc else None)
      },
      "mtd": {
        "disruption_window_mean_s": (sum(
            first_after(ev, ts, lambda t,kv2: t=="attack" and kv2.get("type","").startswith("follow_"))[0]-ts
            for ts,act,kv in mtd_times
            if first_after(ev, ts, lambda t,kv2: t=="attack" and kv2.get("type","").startswith("follow_"))
        )/len(mtd_times) if mtd_times else None),
        "impair_loss_area_pct_x_s": loss_area,
        "impair_delay_area_ms_x_s": delay_area,
        "impair_jitter_area_ms_x_s": jitter_area
      }
    }

    # --- NS-3 메트릭(유연 파서: 열이 3개 이상이어도 앞 2~3개만 사용) ---
    if ns3_metrics_path and os.path.exists(ns3_metrics_path):
      ns3={}
      with open(ns3_metrics_path, newline="") as f:
        r=csv.reader(f)
        header=next(r, None)  # 기대: metric,value,unit
        for row in r:
          if not row: continue
          # 앞 2칸만 강제 사용(값), 단위는 선택
          k = row[0].strip()
          v = row[1].strip() if len(row)>1 else ""
          # unit = row[2].strip() if len(row)>2 else ""
          try: ns3[k]=float(v)
          except: ns3[k]=v
      metrics["ns3"]=ns3

    if out_path:
        with open(out_path,"w") as f: json.dump(metrics,f,indent=2,ensure_ascii=False)

    # 콘솔 요약
    def fmt(x):
        return "NA" if x is None else (f"{x:.3f}" if isinstance(x,float) else str(x))
    print("== CTI ==")
    print("MTD events:", metrics["cti"]["events_mtd"], "CTI ip_change:", metrics["cti"]["events_cti"])
    print("detect_latency_mean_s:", fmt(metrics["cti"]["detect_latency_mean_s"]))
    print("followup_latency_mean_s:", fmt(metrics["cti"]["followup_latency_mean_s"]))
    print("ip_tracking_accuracy:", fmt(metrics["cti"]["ip_tracking_accuracy"]))
    print("port_tracking_accuracy:", fmt(metrics["cti"]["port_tracking_accuracy"]))
    if "ns3" in metrics:
        print("== NS3 ==")
        for k,v in metrics["ns3"].items():
            print(k,":",v)

if __name__=="__main__":
    if len(sys.argv)<3:
        print("usage: score_cti_mtd.py <bus.log> <effect_timeline.csv> [--ns3 attack_output/ns3_metrics.csv] [-o score.json]")
        sys.exit(1)
    bus=sys.argv[1]; tl=sys.argv[2]; ns3=None; out=None
    args=sys.argv[3:]
    for i,a in enumerate(args):
        if a=="--ns3" and i+1<len(args): ns3=args[i+1]
        if a=="-o"   and i+1<len(args): out=args[i+1]
    main(bus, tl, ns3, out)
