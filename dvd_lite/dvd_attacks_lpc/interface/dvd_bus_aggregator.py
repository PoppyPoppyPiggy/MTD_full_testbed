#!/usr/bin/env python3
import os, sys, json, socket, threading, time
from pathlib import Path

OUT_DIR = Path(os.getenv("OUT_DIR", "./attack_output"))
OUT_DIR.mkdir(parents=True, exist_ok=True)
BUS_LOG = OUT_DIR / "bus.log"
STATE_CSV = OUT_DIR / "dvd_state.csv"

lock = threading.Lock()
state = {"t": None, "lat": None, "lon": None, "alt_m": None,
         "roll": None, "pitch": None, "yaw": None,
         "groundspeed": None, "airspeed": None, "throttle": None,
         "batt_pct": None, "batt_v": None}

def append_bus(module, **kvs):
    line = f"[{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}] [{module}] " + " ".join(f"{k}={v}" for k,v in kvs.items()) + "\n"
    with open(BUS_LOG, "a") as f: f.write(line)

def flush_state():
    if state["t"] is None or state["lat"] is None or state["lon"] is None: 
        return
    newfile = not STATE_CSV.exists()
    with open(STATE_CSV, "a") as w:
        if newfile:
            w.write("t,lat,lon,alt_m,roll,pitch,yaw,groundspeed,airspeed,throttle,batt_pct,batt_v\n")
        w.write(",".join(str(state.get(k,"")) for k in ["t","lat","lon","alt_m","roll","pitch","yaw","groundspeed","airspeed","throttle","batt_pct","batt_v"])+"\n")

def flusher():
    while True:
        time.sleep(0.5)
        with lock: flush_state()

def on_mav(obj):
    mt, d = obj.get("mtype"), obj.get("data",{})
    with lock:
        state["t"] = time.time()  # epoch(초)로 고정
        if mt == "GLOBAL_POSITION_INT":
            state["lat"] = (d.get("lat") or 0)/1e7
            state["lon"] = (d.get("lon") or 0)/1e7
            state["alt_m"] = (d.get("alt") or 0)/1000.0
        elif mt == "ATTITUDE":
            state["roll"],state["pitch"],state["yaw"] = d.get("roll"), d.get("pitch"), d.get("yaw")
        elif mt == "VFR_HUD":
            state["groundspeed"],state["airspeed"],state["throttle"] = d.get("groundspeed"), d.get("airspeed"), d.get("throttle")
        elif mt == "BATTERY_STATUS":
            vs = d.get("voltages") or []
            state["batt_v"] = vs[0] if vs else None
            state["batt_pct"] = d.get("battery_remaining")
        elif mt == "SYS_STATUS":
            drop = int(d.get("drop_rate_comm",0)); lvl = "high" if drop>50 else "mid" if drop>10 else "low"
            append_bus("mavlink_drop", drop=drop, level=lvl)
        elif mt == "GPS_RAW_INT":
            fix = int(d.get("fix_type",0)); sats = int(d.get("satellites_visible",0))
            lvl = "high" if fix<2 or sats<=4 else "mid" if fix<3 or sats<=7 else "low"
            append_bus("gps_quality_low", fix=fix, sats=sats, level=lvl)

def on_msg(data):
    try:
        obj=json.loads(data.decode("utf-8",errors="ignore"))
    except Exception as e:
        append_bus("bus_error", err=str(e)); return
    t=obj.get("type")
    if t=="mavlink": on_mav(obj)
    elif t=="gazebo": append_bus("gazebo_stats", raw=obj.get("line",""), level="low")
    elif t=="agent":  append_bus("agent", msg=obj.get("msg",""), severity=obj.get("severity","info"))

def main():
    threading.Thread(target=flusher, daemon=True).start()
    sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", int(os.getenv("BUS_PORT","5566"))))
    print(f"[bus] writing: {BUS_LOG} / {STATE_CSV}")
    while True:
        data,_=sock.recvfrom(65535); on_msg(data)

if __name__=="__main__": main()
