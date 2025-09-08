#!/usr/bin/env python3
import argparse, socket, time

p = argparse.ArgumentParser()
p.add_argument("--host", required=True)
p.add_argument("--port", type=int, required=True)
p.add_argument("--count", type=int, default=50)
p.add_argument("--interval", type=float, default=0.03)
p.add_argument("--payload", default="lpctest")
args = p.parse_args()

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
data = args.payload.encode()

for i in range(args.count):
    sock.sendto(data, (args.host, args.port))
    time.sleep(args.interval)

print(f"sent {args.count} packets")
