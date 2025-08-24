# dvd_lite/dvd_attacks_lpc/tools/gen_effects_timeline.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bus.log -> effect_timeline.csv (LPC 표준/강도 매핑)
- tools/effects_rules.json 하나만 사용(네가 준 구조 유지)
- event 우선순위: 'effect' 직접값 > rules[kind] > rules[tag][action] > rules[tag]['_default']
- 강도 키: intensity|level|grade|severity|lvl (문자/숫자 모두 허용)
- 출력: t,loss_pct,delay_ms,jitter_ms,dup_pct,rate_limit_mbps
"""
import os, sys, json, csv, argparse

FIELDS = ["loss_pct","delay_ms","jitter_ms","dup_pct","rate_limit_mbps"]

def _norm_intensity(ev):
    cand = (ev.get("intensity") or ev.get("level") or ev.get("grade") or ev.get("severity") or ev.get("lvl") or "").strip().lower()
    if cand in ("mid","med"): return "medium"
    if cand in ("low","medium","high"): return cand
    # 숫자도 허용
    try:
        n = int(cand)
        return {1:"low",2:"medium",3:"high"}.get(n,"low")
    except: return "low"

def _parse_bus(bus_path):
    ev=[]
    if not os.path.isfile(bus_path): return ev
    with open(bus_path,"r",encoding="utf-8",errors="ignore") as f:
        for line in f:
            line=line.strip()
            if not line: continue
            # 탭 우선, 없으면 스페이스
            parts=line.split("\t")
            if len(parts)<2:
                parts=line.split(" ",2)
            if len(parts)<2: continue
            ts, tag = parts[0], parts[1]
            rest = parts[2] if len(parts)>2 else ""
            try:
                ts_ms = int(ts)
            except: 
                # epoch-sec도 지원
                try:
                    ts_ms = int(float(ts)*1000)
                except: continue
            kv={}
            for tok in rest.split():
                if "=" in tok:
                    k,v=tok.split("=",1)
                    kv[k]=v
            kv["ts_ms"]=ts_ms; kv["tag"]=tag
            ev.append(kv)
    return ev

def _load_rules(tools_dir):
    p=os.path.join(tools_dir,"effects_rules.json")
    if not os.path.isfile(p):
        return {}
    with open(p,"r",encoding="utf-8") as f:
        return json.load(f)

def _merge(dst, src):
    for k in FIELDS:
        dst[k]=dst.get(k,0.0)+float(src.get(k,0.0))

def _apply_rules(events, rules, horizon=300):
    if not events: return []
    t0 = min(e["ts_ms"] for e in events)//1000
    t1 = min(t0+horizon, max(e["ts_ms"] for e in events)//1000 + 60)
    # 초기화
    base=[{"t":float(t),"loss_pct":0.0,"delay_ms":0.0,"jitter_ms":0.0,"dup_pct":0.0,"rate_limit_mbps":0.0} 
          for t in range(int(t0), int(t1)+1)]
    # 이벤트 반영
    for e in events:
        tag=e.get("tag","")
        kind=e.get("kind","")
        action=e.get("action","")
        inten=_norm_intensity(e)

        # 1) effect 직접값
        if tag=="effect":
            val={k:float(e.get(k,0.0)) for k in FIELDS}
            # 즉시 시점 t에 합산
            t= int(e["ts_ms"]//1000)
            if t < base[0]["t"] or t > base[-1]["t"]: continue
            _merge(base[t-int(t0)], val)
            continue

        # 2) 룰 탐색
        # 2-1) rules[kind] 에 강도맵이 있으면 우선
        spec=None
        rk=rules.get(kind) if kind else None
        if isinstance(rk, dict) and any(x in rk for x in ("low","medium","mid","high")):
            spec = rk.get(inten) or rk.get("mid") if inten=="medium" else None
        # 2-2) rules[tag][action] 또는 rules[tag]["_default"]
        if spec is None:
            sec = rules.get(tag) if tag in rules else None
            if isinstance(sec, dict):
                if action and isinstance(sec.get(action), dict):
                    spec = sec.get(action)
                elif isinstance(sec.get("_default"), dict):
                    spec = sec.get("_default")
        if spec is None: 
            continue

        hold = int(e.get("hold_s", spec.get("hold_s", 10)))
        decay= int(spec.get("decay_s", 5))
        start = int(e["ts_ms"]//1000)
        end   = start + hold + decay

        for b in base:
            t = int(b["t"])
            if t < start: 
                continue
            if t <= start + hold:
                w = 1.0
            elif t <= end:
                rem=end - t
                w = max(0.0, rem/float(decay) if decay>0 else 0.0)
            else:
                continue
            for k in FIELDS:
                b[k]+= w*float(spec.get(k,0.0))

    # sanitize
    for b in base:
        for k in ("loss_pct","dup_pct","rate_limit_mbps"):
            if b[k] < 0.0: b[k]=0.0
    return base

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("bus_log")
    ap.add_argument("-o","--out", default=None)
    ap.add_argument("--tools-dir", default=os.path.dirname(__file__))
    ap.add_argument("--horizon", type=int, default=300)
    args=ap.parse_args()

    rules=_load_rules(args.tools_dir)
    ev=_parse_bus(args.bus_log)
    rows=_apply_rules(ev, rules, horizon=args.horizon)

    out=args.out or os.path.join(os.path.dirname(args.bus_log), "effect_timeline.csv")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out,"w",newline="",encoding="utf-8") as f:
        w=csv.writer(f); w.writerow(["t"]+FIELDS)
        for r in rows: w.writerow([r["t"]]+[r[k] for k in FIELDS])
    print(f"[OK] wrote {out} rows={len(rows)}")

if __name__=="__main__":
    main()
