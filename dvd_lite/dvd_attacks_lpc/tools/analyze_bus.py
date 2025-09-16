#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Analyze bus.log / bus_dvd.log for MTD and attack effectiveness.
- Robustly parses events where fields may appear at top-level or under "data"/"net".
- Computes key metrics:
  * MTD shuffle count & intervals
  * Target occupancy share (drone vs decoy)
  * Retarget lag after each ip_shuffle
  * Decoy/Real hit rates (udp_packet to 14550)
  * Gate stats (gate waiting/open/start)
  * Sanity checks for docker_net_snapshot filters
- Emits: summary.json, hits.csv, shuffles.csv, retarget_lag.csv, gate.csv, metrics.md
"""

import os, sys, json, argparse, math, statistics, csv
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

# ---------- Defaults (edit as needed)
DEFAULT_BUS = "/home/kali/MTD_full_testbed/dvd_lite/dvd_attacks_lpc/bus/bus.log"
DEFAULT_BUS_DVD = "/home/kali/MTD_full_testbed/dvd_lite/dvd_attacks_lpc/bus/bus_dvd.log"
DEFAULT_OUTDIR = "/home/kali/MTD_full_testbed/test_output/latest"
# Drone/Decoy/Port
DRONE_IP = "10.13.0.3"
DECOY_IP = "10.13.0.100"
TARGET_PORT = 14550

# ---------- Utilities
def parse_iso(ts: str) -> Optional[float]:
    """Parse ISO timestamp -> epoch seconds (float)."""
    try:
        # allow "2025-09-16T06:30:29.4+00:00" or "2025-09-16T06:30:29+00:00"
        return datetime.fromisoformat(ts.replace("Z","+00:00")).timestamp()
    except Exception:
        return None

def get(d,*ks,default=None):
    cur = d
    for k in ks:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur

def to_float_ts(ev: Dict[str,Any]) -> Optional[float]:
    # Prefer numeric 'ts'
    ts = ev.get("ts")
    if isinstance(ts,(int,float)): return float(ts)
    # Maybe 'timestamp' is float
    t2 = ev.get("timestamp")
    if isinstance(t2,(int,float)): return float(t2)
    if isinstance(t2,str):
        v = parse_iso(t2)
        if v is not None: return v
    # Some logs use 'timestamp' at top-level but string without tz: try again
    return None

def norm_event(line: str) -> Optional[Dict[str,Any]]:
    """Return normalized event dict with fields:
       - type
       - ts (float)
       - src_ip, src_port, dst_ip, dst_port (if present anywhere)
       - action, new_target, target
       - component/source
    """
    try:
        ev = json.loads(line)
    except Exception:
        return None

    # unify 'type'
    etype = ev.get("type") or ev.get("event_type")
    if not etype:
        # try to peek inside "data" but we still keep as unknown
        etype = "unknown"
    ev["_type"] = etype

    # unify ts
    ts = to_float_ts(ev)
    if ts is None:
        return None
    ev["_ts"] = ts

    # flatten common fields
    # component/source
    ev["_who"] = ev.get("component") or ev.get("source") or ""

    # ip/port lookup across multiple nests
    nests = [ev, ev.get("data") or {}, ev.get("net") or {}]
    def find_first(keys):
        for o in nests:
            for k in keys:
                if k in o: return o[k]
        return None

    ev["_src_ip"]  = find_first(["src_ip","sip","source_ip"])
    ev["_dst_ip"]  = find_first(["dst_ip","dip","dest_ip","destination_ip"])
    ev["_src_port"]= find_first(["src_port","sport"])
    ev["_dst_port"]= find_first(["dst_port","dport"])
    # action/new_target/target
    ev["_action"] = find_first(["action"])
    ev["_new_target"] = find_first(["new_target"])
    ev["_target"] = find_first(["target"])

    # normalize ports to int when possible
    for k in ("_src_port","_dst_port"):
        if isinstance(ev.get(k), str):
            try: ev[k] = int(ev[k])
            except: pass
    return ev

def pct(x):
    return round(x*100.0,2)

def pXX(values: List[float], q: float) -> Optional[float]:
    if not values: return None
    values = sorted(values)
    idx = max(0, min(len(values)-1, int(round((len(values)-1)*q))))
    return values[idx]

# ---------- Metrics
class Metrics:
    def __init__(self):
        self.lines_total = 0
        self.events = 0
        self.udp_hits_drone = 0
        self.udp_hits_decoy = 0
        self.udp_hits_other = 0

        self.shuffle_ts: List[float] = []            # ts of ip_shuffle
        self.shuffle_to: List[str] = []              # ip:port

        self.retarget_lags: List[float] = []         # seconds to first udp to new target
        self._pending_shuffle: Optional[Tuple[float,str,int]] = None  # (ts, ip, port)

        self.target_timeline: List[Tuple[float,str,int]] = []  # (ts, ip, port) assignment changes

        self.gate_waiting = 0
        self.gate_open = 0
        self.gate_started = 0
        self.gate_time_to_open: List[float] = []
        self._last_gate_wait_ts: Optional[float] = None

        self.snapshots_nonempty = 0
        self.snapshots_empty = 0

        self.hits_csv: List[Tuple[float,str,int]] = []
        self.shuf_csv: List[Tuple[float,str]] = []
        self.retarget_csv: List[Tuple[float,str,float]] = []   # (shuffle_ts, to, lag)
        self.gate_csv: List[Tuple[str,float]] = []             # (phase, ts)

    def on_event(self, E: Dict[str,Any]):
        self.events += 1
        t = E["_type"]; ts = E["_ts"]

        # docker snapshots sanity
        if t == "docker_net_snapshot":
            containers = E.get("containers")
            # Some logs have in 'data', but orchestrator writes at top level
            if containers is None:
                containers = get(E,"data","containers", default=None)
            if isinstance(containers, list) and len(containers)>0:
                self.snapshots_nonempty += 1
            else:
                self.snapshots_empty += 1

        # Gate
        if t == "attack_gate_waiting":
            self.gate_waiting += 1
            self._last_gate_wait_ts = ts
            self.gate_csv.append(("waiting", ts))
        elif t == "attack_gate_open":
            self.gate_open += 1
            self.gate_csv.append(("open", ts))
            if self._last_gate_wait_ts is not None:
                self.gate_time_to_open.append(ts - self._last_gate_wait_ts)
                self._last_gate_wait_ts = None
        elif t == "attack_started_by_orchestrator":
            self.gate_started += 1
            self.gate_csv.append(("started", ts))

        # ip_shuffle
        if (t == "mtd_action" and E.get("_action") == "ip_shuffle"):
            newt = E.get("_new_target") or ""
            self.shuffle_ts.append(ts)
            self.shuffle_to.append(newt)
            self.shuf_csv.append((ts, newt))
            # parse ip:port
            ip, port = None, None
            if isinstance(newt, str) and ":" in newt:
                ip, pp = newt.split(":",1)
                try: port = int(pp)
                except: port = TARGET_PORT
            if not port: port = TARGET_PORT
            self._pending_shuffle = (ts, ip or "", port)
            self.target_timeline.append((ts, ip or "", port))

        # udp hits (count + possibly retarget lag completion)
        if t in ("udp_packet","udp_packet_rx","udp_packet_tx","net_packet"):
            dip = E.get("_dst_ip"); dpo = E.get("_dst_port")
            if dip and dpo == TARGET_PORT:
                self.hits_csv.append((ts, dip, dpo))
                if dip == DRONE_IP:
                    self.udp_hits_drone += 1
                elif dip == DECOY_IP:
                    self.udp_hits_decoy += 1
                else:
                    self.udp_hits_other += 1

                if self._pending_shuffle:
                    sh_ts, sh_ip, sh_port = self._pending_shuffle
                    if sh_ip and dip == sh_ip and (dpo == sh_port or sh_port is None):
                        lag = max(0.0, ts - sh_ts)
                        self.retarget_lags.append(lag)
                        self.retarget_csv.append((sh_ts, f"{sh_ip}:{sh_port}", lag))
                        self._pending_shuffle = None

    def finalize(self):
        # compute shuffle intervals
        self.shuffle_intervals = []
        for i in range(1,len(self.shuffle_ts)):
            self.shuffle_intervals.append(self.shuffle_ts[i]-self.shuffle_ts[i-1])

    def as_dict(self) -> Dict[str,Any]:
        self.finalize()
        total_hits = self.udp_hits_drone + self.udp_hits_decoy + self.udp_hits_other
        def safe_avg(v): 
            return (sum(v)/len(v)) if v else None
        def fmt(x):
            if x is None: return None
            return round(float(x),3)

        d = {
            "lines_total": self.lines_total,
            "events_parsed": self.events,

            "hits": {
                "total": total_hits,
                "drone": self.udp_hits_drone,
                "decoy": self.udp_hits_decoy,
                "other": self.udp_hits_other,
                "decoy_hit_rate": fmt(self.udp_hits_decoy/total_hits) if total_hits>0 else None,
                "real_hit_rate":  fmt(self.udp_hits_drone/total_hits) if total_hits>0 else None,
            },

            "mtd": {
                "shuffle_count": len(self.shuffle_ts),
                "interval_avg_s": fmt(safe_avg(self.shuffle_intervals)),
                "interval_med_s": fmt(statistics.median(self.shuffle_intervals)) if self.shuffle_intervals else None,
                "interval_p95_s": fmt(pXX(self.shuffle_intervals,0.95)) if self.shuffle_intervals else None,
            },

            "retarget": {
                "samples": len(self.retarget_lags),
                "lag_avg_s": fmt(safe_avg(self.retarget_lags)),
                "lag_med_s": fmt(statistics.median(self.retarget_lags)) if self.retarget_lags else None,
                "lag_p95_s": fmt(pXX(self.retarget_lags,0.95)) if self.retarget_lags else None,
            },

            "gate": {
                "waiting": self.gate_waiting,
                "open": self.gate_open,
                "started": self.gate_started,
                "time_to_open_med_s": fmt(statistics.median(self.gate_time_to_open)) if self.gate_time_to_open else None,
                "time_to_open_avg_s": fmt(safe_avg(self.gate_time_to_open)),
            },

            "snapshots": {
                "nonempty": self.snapshots_nonempty,
                "empty": self.snapshots_empty,
                "note": "If 'empty' >> 0, check orchestrator --name-prefix/--label filters."
            },

            "assumptions": {
                "drone_ip": DRONE_IP,
                "decoy_ip": DECOY_IP,
                "target_port": TARGET_PORT
            }
        }
        return d

# ---------- Runner
def read_file(path: str):
    if not path or not os.path.exists(path): 
        return []
    with open(path,"r",encoding="utf-8",errors="replace") as f:
        return f.readlines()

def write_csv(path: str, rows: List[List[Any]], header: Optional[List[str]]=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path,"w",newline="",encoding="utf-8") as f:
        w = csv.writer(f)
        if header: w.writerow(header)
        for r in rows: w.writerow(r)

def main():
    ap = argparse.ArgumentParser(description="Analyze MTD/attack effectiveness from bus logs.")
    ap.add_argument("--bus", default=DEFAULT_BUS)
    ap.add_argument("--bus-dvd", default=DEFAULT_BUS_DVD)
    ap.add_argument("--outdir", default=DEFAULT_OUTDIR)
    ap.add_argument("--drone-ip", default=DRONE_IP)
    ap.add_argument("--decoy-ip", default=DECOY_IP)
    ap.add_argument("--port", type=int, default=TARGET_PORT)
    args = ap.parse_args()

    global DRONE_IP, DECOY_IP, TARGET_PORT
    DRONE_IP = args.drone_ip
    DECOY_IP = args.decoy_ip
    TARGET_PORT = int(args.port)

    os.makedirs(args.outdir, exist_ok=True)

    M = Metrics()
    all_lines = []
    for p in [args.bus, args.bus_dvd]:
        all_lines += read_file(p)
    M.lines_total = len(all_lines)

    # parse each line
    for ln in all_lines:
        ev = norm_event(ln)
        if not ev: continue
        # only consider our time window? (optional)
        M.on_event(ev)

    S = M.as_dict()

    # outputs
    with open(os.path.join(args.outdir,"summary.json"),"w",encoding="utf-8") as f:
        json.dump(S,f,ensure_ascii=False,indent=2)

    # CSVs
    write_csv(os.path.join(args.outdir,"hits.csv"), 
              [[t,ip,po] for (t,ip,po) in M.hits_csv], 
              header=["ts","dst_ip","dst_port"])
    write_csv(os.path.join(args.outdir,"shuffles.csv"), 
              [[t,to] for (t,to) in M.shuf_csv],
              header=["ts","new_target"])
    write_csv(os.path.join(args.outdir,"retarget_lag.csv"),
              [[t,to,lag] for (t,to,lag) in M.retarget_csv],
              header=["shuffle_ts","to","lag_s"])
    write_csv(os.path.join(args.outdir,"gate.csv"),
              [[phase,ts] for (phase,ts) in M.gate_csv],
              header=["phase","ts"])

    # Markdown quick report
    md = []
    md.append("# MTD / Attack Analysis Summary\n")
    md.append(f"- Logs parsed: {M.events} events from {M.lines_total} lines\n")
    md.append("## Hits\n")
    total = S["hits"]["total"] or 0
    md.append(f"- total={total}, drone={S['hits']['drone']}, decoy={S['hits']['decoy']}, other={S['hits']['other']}\n")
    if total>0:
        md.append(f"- decoy_hit_rate={S['hits']['decoy_hit_rate']}, real_hit_rate={S['hits']['real_hit_rate']}\n")
    md.append("## MTD\n")
    md.append(f"- shuffle_count={S['mtd']['shuffle_count']}, interval_avg_s={S['mtd']['interval_avg_s']}, "
              f"med={S['mtd']['interval_med_s']}, p95={S['mtd']['interval_p95_s']}\n")
    md.append("## Retarget\n")
    md.append(f"- samples={S['retarget']['samples']}, lag_avg_s={S['retarget']['lag_avg_s']}, "
              f"med={S['retarget']['lag_med_s']}, p95={S['retarget']['lag_p95_s']}\n")
    md.append("## Gate\n")
    md.append(f"- waiting={S['gate']['waiting']}, open={S['gate']['open']}, started={S['gate']['started']}\n")
    md.append(f"- time_to_open_med_s={S['gate']['time_to_open_med_s']}, avg={S['gate']['time_to_open_avg_s']}\n")
    md.append("## Snapshots\n")
    md.append(f"- docker_net_snapshot nonempty={S['snapshots']['nonempty']}, empty={S['snapshots']['empty']}\n")
    md.append("> NOTE: If 'empty' >> 0, remove --name-prefix filter or ensure labels match.\n")
    md.append("\n")
    with open(os.path.join(args.outdir,"metrics.md"),"w",encoding="utf-8") as f:
        f.write("".join(md))

    print(f"✅ Wrote {os.path.join(args.outdir,'summary.json')}")
    print(f"✅ Wrote {os.path.join(args.outdir,'hits.csv')}")
    print(f"✅ Wrote {os.path.join(args.outdir,'shuffles.csv')}")
    print(f"✅ Wrote {os.path.join(args.outdir,'retarget_lag.csv')}")
    print(f"✅ Wrote {os.path.join(args.outdir,'gate.csv')}")
    print(f"✅ Wrote {os.path.join(args.outdir,'metrics.md')}")
    print("done.")

if __name__ == "__main__":
    main()
