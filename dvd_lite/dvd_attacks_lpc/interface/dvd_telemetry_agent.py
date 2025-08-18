#!/usr/bin/env python3
import os, time, json, socket, datetime

BUS_HOST = os.getenv("BUS_HOST", "172.17.0.1")
BUS_PORT = int(os.getenv("BUS_PORT", "5566"))
MAV_EP   = os.getenv("MAVLINK_ENDPOINT", "udp:0.0.0.0:14550")

try:
    from pymavlink import mavutil
    HAVE_MAV = True
except Exception as e:
    HAVE_MAV = False

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
addr = (BUS_HOST, BUS_PORT)

def ts_iso(): return datetime.datetime.utcnow().isoformat() + "Z"

def send(obj):
    sock.sendto(json.dumps(obj,separators=(",",":")).encode("utf-8"), addr)

def mavloop():
    if not HAVE_MAV:
        send({"type":"agent","severity":"error","ts":ts_iso(),"msg":"pymavlink_not_available"})
        return
    try:
        m = mavutil.mavlink_connection(MAV_EP, source_system=255, dialect="ardupilotmega")
    except Exception as e:
        send({"type":"agent","severity":"error","ts":ts_iso(),"msg":f"mav_connect_fail:{e}"})
        return
    send({"type":"agent","severity":"info","ts":ts_iso(),"msg":f"mav_connected:{MAV_EP}"})
    wanted = {"GLOBAL_POSITION_INT","GPS_RAW_INT","SYS_STATUS","HEARTBEAT","ATTITUDE","VFR_HUD","BATTERY_STATUS"}
    while True:
        try:
            msg = m.recv_match(blocking=True, timeout=1)
            if not msg: 
                continue
            mtype = msg.get_type()
            if mtype in wanted:
                md = msg.to_dict()
                md.pop("mavpackettype", None)
                send({"type":"mavlink","ts":ts_iso(),"mtype":mtype,"data":md})
        except Exception as e:
            send({"type":"agent","severity":"warn","ts":ts_iso(),"msg":f"mav_read_err:{e}"})
            time.sleep(0.2)

if __name__ == "__main__":
    mavloop()
