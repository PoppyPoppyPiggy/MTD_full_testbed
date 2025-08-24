#!/usr/bin/env python3
import argparse, random, time
from pymavlink import mavutil

def connect(host="127.0.0.1", port=14550, timeout=5):
  m = mavutil.mavlink_connection(f'udpout:{host}:{port}')
  m.wait_heartbeat(timeout=timeout)
  return m

def noisy_burst(m, count=200, sleep_ms=10):
  for _ in range(count):
    m.mav.heartbeat_send(
      mavutil.mavlink.MAV_TYPE_GCS,
      mavutil.mavlink.MAV_AUTOPILOT_INVALID,
      0,0,0
    )
    r = random.random()
    if r < 0.2:
      m.mav.param_set_send(m.target_system, m.target_component, b"FAKE_PARAM",
                           random.uniform(-1,1), mavutil.mavlink.MAV_PARAM_TYPE_REAL32)
    elif r < 0.35:
      m.mav.command_long_send(m.target_system, m.target_component, 400, 0, 0,0,0,0,0,0,0)
    time.sleep(sleep_ms/1000.0)

if __name__ == "__main__":
  ap = argparse.ArgumentParser()
  ap.add_argument("--host", default="127.0.0.1")
  ap.add_argument("--port", type=int, default=14550)
  ap.add_argument("--count", type=int, default=300)
  ap.add_argument("--sleep-ms", type=int, default=10)
  args = ap.parse_args()
  m = connect(args.host, args.port)
  noisy_burst(m, count=args.count, sleep_ms=args.sleep_ms)
