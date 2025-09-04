#!/usr/bin/env python3
import sys, time, os
from pymavlink import mavutil

host=sys.argv[1]; port=int(sys.argv[2]); param=sys.argv[3]; cnt=int(sys.argv[4]); delta=float(sys.argv[5])

m = mavutil.mavlink_connection(f'udpout:{host}:{port}')
m.wait_heartbeat(timeout=5)
for _ in range(cnt):
    # 기존 값 조회
    m.param_fetch_all()
    time.sleep(1.5)
    cur = m.param_get(param)
    try: curv = float(cur) if cur is not None else 0.0
    except: curv = 0.0
    newv = curv + delta
    m.param_set_send(param.encode('ascii'), newv, mavutil.mavlink.MAV_PARAM_TYPE_REAL32)
    time.sleep(1.5)
m.close()
