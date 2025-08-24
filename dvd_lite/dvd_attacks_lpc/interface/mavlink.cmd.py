#!/usr/bin/env python3
import argparse, time
from pymavlink import mavutil

def connect(host="127.0.0.1", port=14550, timeout=5):
  m = mavutil.mavlink_connection(f'udpout:{host}:{port}')
  m.wait_heartbeat(timeout=timeout)
  return m

def set_param(m, name, value, ptype=mavutil.mavlink.MAV_PARAM_TYPE_REAL32):
  m.mav.param_set_send(m.target_system, m.target_component, name.encode(), float(value), ptype)

def command_long(m, cmd, params):
  p = list(map(float, params)) + [0.0]*7
  m.mav.command_long_send(m.target_system, m.target_component, int(cmd), 0, *p[:7])

def set_mode(m, mode):
  m.mav.set_mode_send(m.target_system, mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED, int(mode))

if __name__ == "__main__":
  ap = argparse.ArgumentParser()
  ap.add_argument("--host", default="127.0.0.1")
  ap.add_argument("--port", type=int, default=14550)
  sub = ap.add_subparsers(dest="op", required=True)
  sp = sub.add_parser("set-param"); sp.add_argument("name"); sp.add_argument("value", type=float)
  sm = sub.add_parser("set-mode");  sm.add_argument("mode", type=int)
  sc = sub.add_parser("cmd-long");  sc.add_argument("cmd", type=int); sc.add_argument("p", nargs="*", default=[])
  args = ap.parse_args()

  m = connect(args.host, args.port)
  if args.op=="set-param": set_param(m, args.name, args.value)
  elif args.op=="set-mode": set_mode(m, args.mode)
  elif args.op=="cmd-long": command_long(m, args.cmd, args.p)
  time.sleep(0.2)
