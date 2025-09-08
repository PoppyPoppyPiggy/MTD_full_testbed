#!/usr/bin/env python3
import os, sys, csv, json, subprocess, time, argparse, math
from pathlib import Path

def sh(cmd):
    return subprocess.check_output(cmd, shell=True, text=True).strip()

def find_tlog(container: str) -> str:
    cands = ["/mav.tlog","/root/mav.tlog","/home/root/mav.tlog","/root/.mavproxy/mav.tlog"]
    for p in cands:
        if subprocess.run(f'docker exec {container} sh -lc "[ -f {p} ]"', shell=True).returncode == 0:
            return p
    out = sh(f"docker exec {container} sh -lc \"find / -name '*.tlog' 2>/dev/null | head -n1\"")
    if out: return out.splitlines()[0]
    raise SystemExit(f"tlog file not found in {container}")

def docker_cp(container: str, src: str, dst: Path):
    dst.parent.mkdir(parents=True, exist_ok=True)
    subprocess.check_call(["docker","cp",f"{container}:{src}",str(dst)])

def parse_tlog(tlog_path: Path):
    from pymavlink import mavutil
    m = mavutil.mavlink_connection(str(tlog_path))
    rows = []
    last_pos = {"lat":None,"lon":None,"alt":None}
    last_batt = {"pct":None,"V":None,"A":None}
    counts = {}
    param_names = set()
    t_first = None; t_last = None
    while True:
        msg = m.recv_match(blocking=False)
        if msg is None:
            # EOF reached
            break
        t = getattr(msg,"_timestamp",None)
        if t is None: 
            continue
        t_first = t if t_first is None else min(t_first,t)
        t_last  = t if t_last  is None else max(t_last,t)
        name = msg.get_type()
        counts[name] = counts.get(name,0)+1
        if name == "GLOBAL_POSITION_INT":
            last_pos["lat"] = getattr(msg,"lat",0)/1e7
            last_pos["lon"] = getattr(msg,"lon",0)/1e7
            last_pos["alt"] = getattr(msg,"alt",0)/1000.0
        elif name == "SYS_STATUS":
            last_batt["pct"] = getattr(msg,"battery_remaining",-1)
            if hasattr(msg,"voltage_battery"): last_batt["V"] = getattr(msg,"voltage_battery",0)/1000.0
            if hasattr(msg,"current_battery"): last_batt["A"] = getattr(msg,"current_battery",0)/100.0
        elif name == "BATTERY_STATUS":
            try:
                arr = getattr(msg,"voltages",[])
                arr = [v for v in arr if v>0]
                if arr: last_batt["V"] = sum(arr)/len(arr)/1000.0
            except Exception: pass
        elif name == "PARAM_VALUE":
            try:
                pname = msg.param_id.decode('ascii','ignore').strip('\x00')
            except Exception:
                pname = str(getattr(msg,"param_id","")).strip()
            if pname: param_names.add(pname)
        rows.append((t,name))
    return {
        "t_first": t_first, "t_last": t_last,
        "last_pos": last_pos, "last_batt": last_batt,
        "counts": counts, "param_seen": len(param_names),
        "rows": rows
    }

def calc_rates(rows, window_s=10.0):
    if not rows: return {}
    t_end = rows[-1][0]
    t_start = max(rows[0][0], t_end - window_s)
    bucket = {}
    for t,name in rows:
        if t < t_start: continue
        bucket[name] = bucket.get(name,0)+1
    dur = max(1e-3, (t_end - t_start))
    return {k: v/float(dur) for k,v in bucket.items()}  # per second

def write_csv(rows, out_csv: Path):
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["time_s","msg"])
        for t,name in rows:
            w.writerow([t,name])

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--container", required=True)
    ap.add_argument("--out", required=True, help="CSV path to write basic timeline (msg types)")
    ap.add_argument("--summary_json_to", help="Append one JSON summary line to this file")
    ap.add_argument("--window_s", type=float, default=10.0, help="msg rate window seconds")
    args = ap.parse_args()

    base = Path(__file__).resolve().parents[1]  # dvd_attacks_lpc/
    out_dir = Path(os.environ.get("OUT_DIR", str(base/"bus")))
    out_dir.mkdir(parents=True, exist_ok=True)

    tlog_in = find_tlog(args.container)
    ts = int(time.time())
    local_tlog = out_dir/"snapshots"/f"mav_{ts}.tlog"
    docker_cp(args.container, tlog_in, local_tlog)

    parsed = parse_tlog(local_tlog)
    write_csv(parsed["rows"], Path(args.out))

    if args.summary_json_to:
        rates = calc_rates(parsed["rows"], args.window_s)
        summ = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "evt": "mav_snapshot",
            "source": args.container,
            "t_first": parsed["t_first"], "t_last": parsed["t_last"],
            "pos": parsed["last_pos"], "battery": parsed["last_batt"],
            "param_seen": parsed["param_seen"],
            "rates_ps": {k: round(v,3) for k,v in sorted(rates.items())}
        }
        with open(args.summary_json_to, "a", encoding="utf-8") as f:
            f.write(json.dumps(summ, ensure_ascii=False)+"\n")
        print(f"[extract] wrote summary → {args.summary_json_to}")

if __name__ == "__main__":
    main()
