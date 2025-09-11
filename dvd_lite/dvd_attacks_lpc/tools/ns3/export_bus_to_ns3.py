#!/usr/bin/env python3
import argparse, json, csv, os
from pathlib import Path

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bus", required=True, help="bus.log(JSONL)")
    ap.add_argument("--dvd", required=True, help="bus_dvd.log(JSONL)")
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--t0", type=float, default=None, help="기준시각(초). None이면 첫 이벤트")
    args = ap.parse_args()

    Path(args.outdir).mkdir(parents=True, exist_ok=True)
    # 1) 액션 이벤트(포트 셔플) 추출 → events.csv(time_s, action, port)
    events = []
    t0 = args.t0
    with open(args.dvd,"r",encoding="utf-8") as f:
        for line in f:
            try:
                j=json.loads(line)
                if j.get("event")=="action" and j.get("type")=="port_shuffle":
                    ts=j["ts"]
                    if t0 is None: t0=ts
                    events.append({"time_s": ts - t0, "action":"port_shuffle", "port": int(j["to"])})
            except Exception: pass
    events.sort(key=lambda x:x["time_s"])
    with open(f"{args.outdir}/events.csv","w",newline="") as f:
        w=csv.DictWriter(f, fieldnames=["time_s","action","port"]); w.writeheader()
        for e in events: w.writerow(e)

    # 2) 흐름 요약 → flows.csv(start_s,end_s,dst_port,pps)
    #    간단히 구간별 dport 기준 pps 평균 (데모)
    bins={}
    with open(args.bus,"r",encoding="utf-8") as f:
        for line in f:
            try:
                j=json.loads(line)
                ts=j["ts"]; dport=int(j.get("dport",0)); is_mav=j.get("is_mav_target",False)
                if not is_mav: continue
                if t0 is None: t0=ts
                t = ts - t0
                key=(int(t), dport)  # 1초 bin
                bins[key]=bins.get(key,0)+1
            except Exception: pass
    # 축약 저장
    with open(f"{args.outdir}/flows.csv","w",newline="") as f:
        w=csv.DictWriter(f, fieldnames=["sec","dst_port","pps"]); w.writeheader()
        for (sec,port),cnt in sorted(bins.items()):
            w.writerow({"sec":sec,"dst_port":port,"pps":cnt})

    print(f"[✓] wrote {args.outdir}/events.csv and flows.csv")

if __name__ == "__main__":
    main()
