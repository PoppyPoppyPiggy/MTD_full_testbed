#!/usr/bin/env python3
import os, sys, json, socket, datetime, threading
from pathlib import Path

OUT_DIR = Path(os.getenv("OUT_DIR", "./attack_output"))
OUT_DIR.mkdir(parents=True, exist_ok=True)
BUS_LOG = OUT_DIR / "bus.log"

def iso(): 
    return datetime.datetime.utcnow().isoformat()+"Z"

def write_line(module, **kvs):
    # [ISO8601] [module] k=v ...
    items = " ".join(f"{k}={v}" for k,v in kvs.items())
    line  = f"[{iso()}] [{module}] {items}\n"
    BUS_LOG.write_text(BUS_LOG.read_text()+line if BUS_LOG.exists() else line)

def classify_and_log(obj):
    t = obj.get("ts", iso())
    if obj.get("type") == "mavlink":
        mtype = obj.get("mtype")
        data  = obj.get("data", {})
        if mtype == "GPS_RAW_INT":
            # ArduPilot: fix_type(0-6), eph/epv(cm*100), satellites_visible
            fix  = int(data.get("fix_type", 0))
            eph  = float(data.get("eph", 999999)) # cm*100 스케일 환경마다 다름 → 상대 비교
            sats = int(data.get("satellites_visible", 0))
            # 매우 단순 휴리스틱 (튜닝 가능)
            if fix < 2 or sats <= 4:
                level="high"
            elif fix < 3 or sats <= 7:
                level="mid"
            else:
                level="low"
            write_line("gps_quality_low", fix=fix, sats=sats, eph=eph, level=level)
        elif mtype == "HEARTBEAT":
            # 모드/arming 상태 이상시 telemetry 문제로 간주 (옵션)
            base_mode = int(data.get("base_mode", 0))
            write_line("telemetry_status", base_mode=base_mode, level="low")
        elif mtype == "SYS_STATUS":
            drop = int(data.get("drop_rate_comm", 0))  # 통신 드랍률(1/100 %)
            level = "high" if drop > 50 else "mid" if drop>10 else "low"
            write_line("mavlink_drop", drop=drop, level=level)
        elif mtype == "GLOBAL_POSITION_INT":
            lat, lon, alt = data.get("lat"), data.get("lon"), data.get("alt")
            write_line("gps_position", lat=lat, lon=lon, alt=alt, level="low")
    elif obj.get("type") == "gazebo":
        write_line("gazebo_stats", raw=obj.get("line",""), level="low")
    elif obj.get("type") == "agent":
        write_line("agent", msg=obj.get("msg",""), severity=obj.get("severity","info"))

def udp_server(host="0.0.0.0", port=5566):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((host, port))
    print(f"[bus] listening on {host}:{port}, writing to {BUS_LOG}")
    while True:
        data, _ = sock.recvfrom(65535)
        try:
            obj = json.loads(data.decode("utf-8", errors="ignore"))
            classify_and_log(obj)
        except Exception as e:
            write_line("bus_error", err=str(e))

if __name__ == "__main__":
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    udp_server()
