#!/usr/bin/env python3
# bus.log → CSV(시간(ms), topic, k, v) + timeline(효과만)
import sys, csv, re, time, os

SRC = sys.argv[1] if len(sys.argv)>1 else "attack_output/bus.log"
CSV_OUT = sys.argv[2] if len(sys.argv)>2 else "attack_output/bus.csv"
TL_OUT  = sys.argv[3] if len(sys.argv)>3 else "attack_output/effect_timeline.csv"

os.makedirs(os.path.dirname(CSV_OUT), exist_ok=True)

def parse_msg(msg):
    # "key1=val1 key2=val2" or "word val"
    parts = re.findall(r'([A-Za-z0-9_]+)=([^\s]+)', msg)
    if not parts:
        return [("msg", msg)]
    return parts

rows=[]
timeline=[]
with open(SRC,'r') as f:
    for line in f:
        line=line.strip()
        if not line: continue
        # epoch\ttopic\tmessage
        try:
            ts_s, topic, msg = line.split('\t', 2)
        except ValueError:
            continue
        ts_ms = int(float(ts_s)*1000) if '.' in ts_s else int(ts_s)*1000
        kvs = parse_msg(msg)
        for k,v in kvs:
            rows.append((ts_ms, topic, k, v))
        if topic=="effect":
            # e.g., "link_jitter +2ms" → effect,value
            m=re.match(r'([A-Za-z0-9_]+)\s+(.+)', msg)
            if m:
                timeline.append((ts_ms, m.group(1), m.group(2)))

with open(CSV_OUT,'w',newline='') as f:
    w=csv.writer(f); w.writerow(["t_ms","topic","key","val"]); w.writerows(rows)
with open(TL_OUT,'w',newline='') as f:
    w=csv.writer(f); w.writerow(["t_ms","effect","value"]); w.writerows(timeline)

print(f"[bus2csv] wrote {CSV_OUT} and {TL_OUT}")
