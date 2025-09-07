#!/usr/bin/env python3
import re, json, csv, sys, time
from pathlib import Path

"""
입력:
  - bus.log (ATTACK_START/ATTACK_END 라인)
  - --dvd bus_dvd.log (선택) : 보조 지표와 오류 등은 향후 확장용

출력:
  CSV: t_start,t_end,attack_key,level,role,host,port,label,severity
"""

START_RE = re.compile(r'\[(\d+)\]\s+BUS ATK ATTACK_START\s+key=([^ ]+)\s+level=([^ ]+)\s+role=([^ ]+)\s+host=([^ ]+)\s+port=([0-9]+)')
END_RE   = re.compile(r'\[(\d+)\]\s+BUS ATK ATTACK_END\s+key=([^ ]+)\s+level=([^ ]+)\s+role=([^ ]+)')

SEV = {"low":1,"mid":2,"high":3}

def parse_bus(path: Path):
    starts = {}  # (key,level,role) -> list of {t, host, port}
    ends = []
    if not path.exists(): return [], []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        m = START_RE.search(line)
        if m:
            t,key,level,role,host,port = m.groups()
            starts.setdefault((key,level,role), []).append({"t":int(t), "host":host, "port":int(port)})
            continue
        m = END_RE.search(line)
        if m:
            t,key,level,role = m.groups()
            ends.append({"t":int(t), "key":key, "level":level, "role":role})
    return starts, ends

def build_rows(starts, ends):
    rows = []
    # 간단 매칭: 동일 (key,level,role)의 가장 이른 start와 가장 이른 end를 순서대로 매칭
    pend = {}
    for (k,lv,ro), lst in starts.items():
        pend[(k,lv,ro)] = [d for d in lst]  # shallow copy
    for e in sorted(ends, key=lambda x:x["t"]):
        sig = (e["key"], e["level"], e["role"])
        if sig in pend and pend[sig]:
            s = pend[sig].pop(0)
            rows.append({
                "t_start": s["t"], "t_end": e["t"],
                "key": e["key"], "level": e["level"], "role": e["role"],
                "host": s["host"], "port": s["port"],
                "label": f'{e["key"]}:{e["level"]}', "severity": SEV.get(e["level"],2)
            })
    return rows

def write_csv(rows, out_csv: Path):
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["t_start","t_end","attack_key","level","role","host","port","label","severity"])
        for r in rows:
            w.writerow([r["t_start"],r["t_end"],r["key"],r["level"],r["role"],r["host"],r["port"],r["label"],r["severity"]])

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("bus", help="path to bus.log")
    ap.add_argument("--dvd", help="path to bus_dvd.log (optional)")
    ap.add_argument("-o","--out", required=True)
    args = ap.parse_args()

    starts, ends = parse_bus(Path(args.bus))
    rows = build_rows(starts, ends)
    write_csv(rows, Path(args.out))
    print(f"[gen_effect_timestamp] wrote {args.out} rows={len(rows)}")

if __name__ == "__main__":
    main()
