#!/usr/bin/env python3
"""
bus.log -> effect_timeline.csv 생성기 (LPC 확장)
- 'effect' 라인 우선, 없으면 룰로 보강
- dup_pct 포함, action/intensity/level/grade 모두 인식
- epoch-ms/epoch-s 모두 인식
모드:
  sparse : 이벤트 시점만 1행
  hold   : 마지막 값 유지 스냅샷(권장)
  sample : 일정 Hz로 균일 샘플
"""
import argparse, csv, json, os, re, sys

FIELDS = ["loss_pct", "delay_ms", "jitter_ms", "dup_pct", "rate_limit_mbps"]

def parse_line(line: str):
    parts = line.rstrip("\n").split("\t")
    if len(parts) < 3:
        return None
    raw_ts = parts[0]
    try:
        ts = float(raw_ts)
        # epoch ms(13자리 이상) → 초로 변환
        if ts > 1e12:
            ts = ts / 1000.0
    except Exception:
        return None
    tag = parts[1]
    kv = dict(re.findall(r'([A-Za-z0-9_]+)=([^\s]+)', " ".join(parts[2:])))
    return ts, tag, kv

def _to_num(x):
    try:
        return float(str(x).replace("%",""))
    except Exception:
        return None

def apply_rules(tag: str, kv: dict, rules: dict):
    if not rules:
        return None
    r = None
    # 액션 키 다 인식
    action = kv.get("action") or kv.get("intensity") or kv.get("level") or kv.get("grade")
    if action == "mid":
        action = "medium"
    if tag in rules and isinstance(rules[tag], dict):
        if action and action in rules[tag]:
            r = rules[tag][action]
        elif "action" in kv and kv["action"] in rules[tag]:
            r = rules[tag][kv["action"]]
        elif "_default" in rules[tag]:
            r = rules[tag]["_default"]
    if not r and "_global" in rules and tag in rules["_global"]:
        r = rules["_global"][tag]
    if not r:
        return None
    out = {}
    for f in FIELDS:
        n = _to_num(r.get(f))
        if n is not None:
            out[f] = n
    return out or None

def load_rules(path: str):
    if not path:
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[WARN] rules load fail: {e}", file=sys.stderr)
        return {}

def write_csv(rows, out_path):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", newline="") as o:
        w = csv.writer(o)
        w.writerow(["t"] + FIELDS)
        for r in rows:
            w.writerow([r["t"]] + [r.get(f, "") for f in FIELDS])

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("buslog", help="path to bus.log")
    ap.add_argument("-o", "--out", default="attack_output/effect_timeline.csv")
    ap.add_argument("--rules", default=None, help="optional effects_rules.json")
    ap.add_argument("--mode", choices=["sparse","hold","sample"], default="hold")
    ap.add_argument("--rate", type=float, default=10.0, help="sample Hz for --mode sample")
    ap.add_argument("--duration", type=float, default=None, help="force end time (sec)")
    args = ap.parse_args()

    if not os.path.exists(args.buslog):
        print(f"[ERR] no bus.log at {args.buslog}", file=sys.stderr)
        sys.exit(2)

    rules = load_rules(args.rules)

    events = []  # (ts_abs, {field:value})
    with open(args.buslog, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            p = parse_line(line)
            if not p:
                continue
            ts, tag, kv = p

            if tag == "effect":
                eff = {}
                for k in FIELDS:
                    if k in kv:
                        n = _to_num(kv[k])
                        if n is not None:
                            eff[k] = n
                if eff:
                    events.append((ts, eff))
                continue

            eff2 = apply_rules(tag, kv, rules)
            if eff2:
                events.append((ts, eff2))

    if not events:
        write_csv([], args.out)
        print("[OK] effect timeline ->", args.out, "rows=0")
        return

    t0 = min(ts for ts, _ in events)
    events.sort(key=lambda x: x[0])
    events_rel = [(ts - t0, d) for ts, d in events]

    rows = []
    if args.mode == "sparse":
        for t, d in events_rel:
            row = {"t": round(float(t), 6)}
            row.update(d)
            rows.append(row)

    elif args.mode == "hold":
        state = {f: 0.0 for f in FIELDS}
        rows.append({"t": 0.0, **state})
        last_t = 0.0
        for t, d in events_rel:
            state.update(d)
            last_t = round(float(t), 6)
            rows.append({"t": last_t, **state})
        if args.duration is not None and args.duration > last_t:
            rows.append({"t": float(args.duration), **state})

    elif args.mode == "sample":
        dur = args.duration if args.duration is not None else events_rel[-1][0]
        dur = max(dur, events_rel[-1][0])
        hz = max(0.1, float(args.rate))
        dt = 1.0 / hz
        state = {f: 0.0 for f in FIELDS}
        idx = 0
        t = 0.0
        while t <= dur + 1e-9:
            while idx < len(events_rel) and events_rel[idx][0] <= t + 1e-9:
                state.update(events_rel[idx][1])
                idx += 1
            rows.append({"t": round(t, 6), **state})
            t += dt

    write_csv(rows, args.out)
    print(f"[OK] effect timeline -> {args.out} rows={len(rows)}")

if __name__ == "__main__":
    main()
