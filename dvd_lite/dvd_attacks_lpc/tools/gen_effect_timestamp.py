#!/usr/bin/env python3
"""
bus.log(JSONL) + bus_dvd.log(JSONL) -> effect_timeline.csv
- bus.log의 impair 객체를 기본 소스로 사용
- bus_dvd.log의 stats/net_change 이벤트를 휴리스틱으로 반영(지연/지터 가중)
- 겹치는 영향은 max 합성(지연/지터/손실/dup), rate_limit은 min(0=무제한)
"""
import argparse, csv, json, time
from pathlib import Path

def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("bus_log", help="bus.log(JSONL)")
    ap.add_argument("--dvd", default="", help="bus_dvd.log(JSONL)")
    ap.add_argument("-o","--out", default="attack_output/effect_timeline.csv")
    ap.add_argument("--resolution", type=float, default=1.0, help="seconds per tick")
    ap.add_argument("--h_cpu_delay_ms", type=float, default=0.4, help="CPU>80% 지연 가중(ms)")
    ap.add_argument("--h_net_jitter_ms", type=float, default=0.7, help="net_change 지터 가중(ms)")
    return ap.parse_args()

def load_jsonl(path):
    out=[]
    if not path or not Path(path).exists(): return out
    with open(path,"r",encoding="utf-8") as f:
        for line in f:
            line=line.strip()
            if not line: continue
            try: out.append(json.loads(line))
            except: pass
    return out

def epoch_from_iso(ts):
    # very lenient parse
    try:
        import datetime
        return datetime.datetime.fromisoformat(ts.replace("Z","+00:00")).timestamp()
    except Exception:
        return time.time()

def build_segments(bus):
    segs=[]
    for ev in bus:
        impair = ev.get("impair")
        if not impair: continue
        t0 = impair.get("t_apply_s") or ev.get("t") or epoch_from_iso(ev.get("ts",""))
        dur = float(impair.get("t_duration_s") or 0)
        if dur <= 0: continue
        segs.append(dict(
            t0=float(t0), t1=float(t0)+dur,
            loss=float(impair.get("loss_pct") or 0.0),
            delay=float(impair.get("delay_ms") or 0.0),
            jitter=float(impair.get("jitter_ms") or 0.0),
            dup=float(impair.get("dup_pct") or 0.0),
            rate=float(impair.get("rate_limit_mbps") or 0.0)  # 0=무제한
        ))
    return segs

def apply_dvd_hints(dvd_events, grid, t0, res, h_cpu_delay_ms, h_net_jitter_ms):
    for ev in dvd_events:
        t = float(ev.get("t") or epoch_from_iso(ev.get("ts","")))
        idx = int((t - t0)/res)
        if idx < 0 or idx >= len(grid): continue
        e = ev.get("evt")
        if e == "stats":
            # CPUPerc like "84.13%"
            data = ev.get("data") or ev.get("stats") or {}
            cpu_str = (data.get("CPUPerc") or "0").replace("%","")
            try: cpu = float(cpu_str)
            except: cpu = 0.0
            if cpu >= 80.0:
                grid[idx]["delay_ms"] += h_cpu_delay_ms
        elif e in ("net_change","docker_event"):
            grid[idx]["jitter_ms"] += h_net_jitter_ms

def compose(segs, res=1.0, dvd_events=None, h_cpu_delay_ms=0.4, h_net_jitter_ms=0.7):
    if not segs:
        return [], 0.0
    t0 = min(s["t0"] for s in segs)
    t1 = max(s["t1"] for s in segs)
    n  = int((t1 - t0) / res) + 1
    grid = [dict(t=t0 + i*res, loss_pct=0.0, delay_ms=0.0, jitter_ms=0.0, dup_pct=0.0, rate_limit_mbps=0.0) for i in range(n)]
    def merge(dst, s):
        # max-merge for loss/delay/jitter/dup, min for rate (0=무제한 -> 큰값으로 취급)
        for i in range(int((s["t0"]-t0)/res), int((s["t1"]-t0)/res)+1):
            if i<0 or i>=n: continue
            dst[i]["loss_pct"]   = max(dst[i]["loss_pct"], s["loss"])
            dst[i]["delay_ms"]   = max(dst[i]["delay_ms"], s["delay"])
            dst[i]["jitter_ms"]  = max(dst[i]["jitter_ms"], s["jitter"])
            dst[i]["dup_pct"]    = max(dst[i]["dup_pct"], s["dup"])
            # rate limit: 0은 제한없음(= +inf). 0이 아닌 값들 중 최소값을 취함.
            cur = dst[i]["rate_limit_mbps"]
            if (cur == 0.0) and (s["rate"] != 0.0):
                dst[i]["rate_limit_mbps"] = s["rate"]
            elif (cur != 0.0) and (s["rate"] != 0.0):
                dst[i]["rate_limit_mbps"] = min(cur, s["rate"])
    for s in segs: merge(grid, s)

    if dvd_events:
        apply_dvd_hints(dvd_events, grid, t0, res, h_cpu_delay_ms, h_net_jitter_ms)

    return grid, t0

def write_csv(grid, out_path):
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path,"w",newline="",encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["t","loss_pct","delay_ms","jitter_ms","dup_pct","rate_limit_mbps"])
        for row in grid:
            w.writerow([f'{row["t"]:.3f}', f'{row["loss_pct"]:.6f}', f'{row["delay_ms"]:.6f}',
                        f'{row["jitter_ms"]:.6f}', f'{row["dup_pct"]:.6f}', f'{row["rate_limit_mbps"]:.6f}'])

def main():
    args = parse_args()
    bus = load_jsonl(args.bus_log)
    dvd = load_jsonl(args.dvd)
    segs = build_segments(bus)
    grid, t0 = compose(segs, args.resolution, dvd, args.h_cpu_delay_ms, args.h_net_jitter_ms)
    write_csv(grid, args.out)
    print(f"[gen_effect_timestamp] wrote {args.out} rows={len(grid)}")

if __name__ == "__main__":
    main()
