#!/usr/bin/env python3
import os, sys, time, json, socket, datetime
from threading import Thread

# --- 환경변수 ---
BUS_HOST = os.getenv("BUS_HOST", "172.17.0.1")   # host gateway (fanet_dvd_bind.sh가 세팅)
BUS_PORT = int(os.getenv("BUS_PORT", "5566"))
MAV_EP   = os.getenv("MAVLINK_ENDPOINT", "udp:0.0.0.0:14550")  # e.g., udp:0.0.0.0:14550

# pymavlink optional import
try:
    from pymavlink import mavutil
    HAVE_MAV = True
except Exception:
    HAVE_MAV = False

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
addr = (BUS_HOST, BUS_PORT)

def ts():
    return datetime.datetime.utcnow().isoformat() + "Z"

def send(obj):
    data = json.dumps(obj, separators=(",",":")).encode("utf-8")
    sock.sendto(data, addr)

def mavloop():
    if not HAVE_MAV:
        return
    try:
        m = mavutil.mavlink_connection(MAV_EP, source_system=255, dialect="ardupilotmega")
    except Exception as e:
        send({"type":"agent","severity":"error","ts":ts(),"msg":f"mavlink_connect_fail:{e}"})
        return
    send({"type":"agent","severity":"info","ts":ts(),"msg":f"mavlink_connected:{MAV_EP}"})
    while True:
        try:
            msg = m.recv_match(blocking=True, timeout=1)
            if not msg: 
                continue
            md = msg.to_dict()
            mtype = msg.get_type()
            if mtype in ("GLOBAL_POSITION_INT","GPS_RAW_INT","SYS_STATUS","HEARTBEAT"):
                payload = {
                    "type":"mavlink",
                    "ts": ts(),
                    "mtype": mtype,
                    "data": {k:md.get(k) for k in md.keys() if k not in ("mavpackettype",)},
                }
                send(payload)
        except Exception as e:
            send({"type":"agent","severity":"warn","ts":ts(),"msg":f"mav_read_err:{e}"})
            time.sleep(0.5)

def gzloop():
    # Gazebo 텔레메트리(선택): 컨테이너에 gz CLI가 존재하면 사용
    GZ_ENABLE = os.getenv("GZ_ENABLE", "0") == "1"
    if not GZ_ENABLE:
        return
    import subprocess, shlex
    cmd = os.getenv("GZ_CMD", "gz stats -p")
    try:
        p = subprocess.Popen(shlex.split(cmd), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        for line in p.stdout:
            line=line.strip()
            if not line: 
                continue
            send({"type":"gazebo","ts":ts(),"line":line})
    except Exception as e:
        send({"type":"agent","severity":"warn","ts":ts(),"msg":f"gz_err:{e}"})

def main():
    Thread(target=mavloop, daemon=True).start()
    Thread(target=gzloop,  daemon=True).start()
    while True:
        time.sleep(5)

if __name__ == "__main__":
    main()
