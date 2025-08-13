#!/usr/bin/env python3
# gen_effects_timeline.py v2
# 입력 자동 감지:
#   A) bus.log (epoch,act=...,key=val,...)  → rules.json 적용해 누적/감쇠 → t_sec,loss_pct,...
#   B) effects.csv (ts_ms,effect,value)     → 효과키 매핑 → t_sec,loss_pct,...
import csv, sys, json, math, os
from collections import defaultdict

BIN = 10  # seconds per bin

def try_json(path):
    try:
        with open(path) as f: return json.load(f)
    except Exception:
        return None

def load_rules(path_or_none):
    if path_or_none and os.path.exists(path_or_none):
        j = try_json(path_or_none)
        if j: return j
        print(f"[WARN] rules file is not JSON or unreadable: {path_or_none} — using built-in defaults", file=sys.stderr)
    # fallback defaults
    return {
        "telemetry_trickle_jam":{"low":{"loss_pct":3,"jitter_ms":2,"delay_ms":0,"dup_pct":0,"rate_limit_mbps":0},
                                 "mid":{"loss_pct":5,"jitter_ms":4,"delay_ms":1,"dup_pct":0,"rate_limit_mbps":0},
                                 "high":{"loss_pct":9,"jitter_ms":6,"delay_ms":2,"dup_pct":1,"rate_limit_mbps":0}},
        "mavlink_param_drift":{"any":{"delay_ms":1,"jitter_ms":1,"loss_pct":0,"dup_pct":0,"rate_limit_mbps":0}},
        "_decay":{"half_life_bins":6}
    }

def is_effect_csv(path):
    try:
        with open(path, newline="") as f:
            r=csv.reader(f)
            hdr=next(r)
            return hdr and hdr[:3]==["ts_ms","effect","value"]
    except Exception:
        return False

def parse_bus(path):
    rows=[]
    with open(path) as f:
        for line in f:
            line=line.strip()
            if not line or "," not in line: continue
            parts=line.split(",")
            try: t = int(parts[0])
            except: continue
            kv={"t":t}
            for p in parts[1:]:
                if "=" in p:
                    k,v=p.split("=",1); kv[k]=v
            rows.append(kv)
    return rows

def parse_effect_csv(path):
    # ts_ms,effect,value
    rows=[]
    with open(path, newline="") as f:
        r=csv.DictReader(f)
        for row in r:
            try:
                t_ms=int(row["ts_ms"])
                eff=row["effect"].strip()
                val=row["value"].strip()
            except: 
                continue
            rows.append({"t": t_ms//1000, "eff": eff, "val": val})
    return rows

def add(v,delta):
    for k in delta:
        v[k] = v.get(k,0) + delta.get(k,0)
    return v

def decay(prev, hl_bins):
    if not prev: return prev
    lam = math.log(2)/max(1,hl_bins)
    out={}
    for k,val in prev.items():
        out[k] = max(0, val*math.exp(-lam))
    return out

def clamp(v, lo, hi):
    out={}
    for k in ["loss_pct","delay_ms","jitter_ms","dup_pct","rate_limit_mbps"]:
        val=v.get(k,0)
        out[k]=max(lo.get(k,0), min(hi.get(k,1e9), val))
    return out

def bake_from_bus(rows, rules):
    _min=rules.get("_min", {"loss_pct":0,"delay_ms":0,"jitter_ms":0,"dup_pct":0,"rate_limit_mbps":0})
    _max=rules.get("_max", {"loss_pct":100,"delay_ms":200,"jitter_ms":200,"dup_pct":50,"rate_limit_mbps":1000})
    hl = rules.get("_decay",{}).get("half_life_bins",6)

    agg = defaultdict(lambda: {"loss_pct":0,"delay_ms":0,"jitter_ms":0,"dup_pct":0,"rate_limit_mbps":0})
    for r in rows:
        b=(r["t"]//BIN)*BIN
        act=r.get("act","")
        delta={}
        if act=="telemetry_trickle_jam":
            lvl=r.get("intensity","low")
            delta = rules.get(act,{}).get(lvl, {})
        elif act=="mavlink_param_drift":
            delta = rules.get(act,{}).get("any", {})
        agg[b]=add(agg[b], delta)

    out=[]; last=None
    for t in sorted(agg.keys()):
        decayed = decay(last, hl) if last else {"loss_pct":0,"delay_ms":0,"jitter_ms":0,"dup_pct":0,"rate_limit_mbps":0}
        cur=add(decayed, agg[t])
        cur=clamp(cur, _min, _max)
        out.append([t, cur["loss_pct"], cur["delay_ms"], cur["jitter_ms"], cur["dup_pct"], cur["rate_limit_mbps"]])
        last=cur
    return out

def bake_from_effect_csv(rows_csv):
    # effect 키를 표준 지표로 매핑
    def map_one(eff,val):
        eff=eff.lower()
        if eff in ("packet_loss","loss","loss_pct"):
            v = float(val.strip("%")) if isinstance(val,str) and "%" in val else float(val)
            return {"loss_pct": v}
        if eff in ("link_jitter","jitter","jitter_ms"):
            v = float(val.strip("ms")) if isinstance(val,str) and "ms" in val else float(val)
            return {"jitter_ms": v}
        if eff in ("queue_delay","delay","delay_ms","rtt_ms"):
            v = float(val.strip("ms")) if isinstance(val,str) and "ms" in val else float(val)
            return {"delay_ms": v}
        if eff in ("dup","dup_pct","duplicate"):
            v = float(val.strip("%")) if isinstance(val,str) and "%" in val else float(val)
            return {"dup_pct": v}
        if eff in ("rate","rate_limit_mbps","throughput_cap"):
            v = float(val.strip("mbps").strip().split()[0]) if isinstance(val,str) else float(val)
            return {"rate_limit_mbps": v}
        return {}
    agg = defaultdict(lambda: {"loss_pct":0,"delay_ms":0,"jitter_ms":0,"dup_pct":0,"rate_limit_mbps":0})
    for r in rows_csv:
        b=(r["t"]//BIN)*BIN
        delta=map_one(r["eff"], r["val"])
        agg[b]=add(agg[b], delta)

    out=[]
    last=None
    for t in sorted(agg.keys()):
        cur=agg[t]
        out.append([t, cur["loss_pct"], cur["delay_ms"], cur["jitter_ms"], cur["dup_pct"], cur["rate_limit_mbps"]])
        last=cur
    return out

def main():
    if len(sys.argv)<3:
        print("usage: gen_effects_timeline.py <in> <out> [rules.json]"); sys.exit(1)
    src=sys.argv[1]; out=sys.argv[2]; rules_path=sys.argv[3] if len(sys.argv)>3 else None
    if not os.path.exists(src):
        sys.exit(f"[ERR] input not found: {src}")
    rules = load_rules(rules_path)

    if is_effect_csv(src):
        rows_csv = parse_effect_csv(src)
        eff = bake_from_effect_csv(rows_csv)
    else:
        rows_bus = parse_bus(src)
        eff = bake_from_bus(rows_bus, rules)

    with open(out,"w",newline="") as f:
        w=csv.writer(f)
        w.writerow(["t_sec","loss_pct","delay_ms","jitter_ms","dup_pct","rate_limit_mbps"])
        w.writerows(eff)
    print(f"[OK] wrote {out} ({len(eff)} rows)")

if __name__=="__main__":
    main()
