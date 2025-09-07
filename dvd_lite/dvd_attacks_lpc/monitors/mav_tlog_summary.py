#!/usr/bin/env python3
import sys, time, json
from pymavlink import mavutil

def summarize(tlog_path):
    m = mavutil.mavlink_connection(tlog_path)
    last = {}
    counts = {}
    t_first = None; t_last = None
    while True:
        msg = m.recv_match(blocking=False)
        if msg is None: break
        if t_first is None: t_first = msg._timestamp
        t_last = msg._timestamp
        name = msg.get_type()
        counts[name] = counts.get(name, 0) + 1
        if name in ("GLOBAL_POSITION_INT","GPS_RAW_INT","VFR_HUD","SYS_STATUS","BATTERY_STATUS"):
            last[name] = msg.to_dict()
    pos = {}
    if "GLOBAL_POSITION_INT" in last:
        g = last["GLOBAL_POSITION_INT"]
        pos = {"lat": g.get("lat",0)/1e7, "lon": g.get("lon",0)/1e7, "alt": g.get("alt",0)/1000.0}
    bat = {}
    if "BATTERY_STATUS" in last:
        b = last["BATTERY_STATUS"]; bat = {"pct": b.get("battery_remaining", -1), "V": None, "A": None}
    rates = {k: round(v/max(1,(t_last - t_first)),2) for k,v in counts.items()}
    return {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "evt": "mav_snapshot",
        "t_first": t_first, "t_last": t_last,
        "pos": pos, "battery": bat, "rates_ps": rates
    }

if __name__=="__main__":
    p = sys.argv[1]
    print(json.dumps(summarize(p)))
