#!/usr/bin/env python3
import argparse, socket, time, os, json, random

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--host", required=True)
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--pps", type=float, required=True)          # packets per second
    ap.add_argument("--duration", type=float, default=10.0)
    ap.add_argument("--payload", type=int, default=256)          # bytes
    ap.add_argument("--proto", choices=["udp"], default="udp")
    ap.add_argument("--flowlog", type=str, default="")
    args=ap.parse_args()

    if args.flowlog:
        j={"ts":time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "evt":"flow_hint","proto":args.proto,"dst_ip":args.host,"dst_port":args.port,
           "pps":args.pps,"duration_s":args.duration,"payload":args.payload}
        with open(args.flowlog,"a",encoding="utf-8") as f: f.write(json.dumps(j)+"\n")

    sock=socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    payload=os.urandom(args.payload)

    interval=1.0/max(args.pps,1e-6)
    t_end=time.time()+args.duration
    sent=0
    next_t=time.time()
    while time.time()<t_end:
        now=time.time()
        if now<next_t:
            time.sleep(min(0.001, next_t-now))
            continue
        sock.sendto(payload,(args.host,args.port))
        sent+=1
        next_t+=interval
    # flush
    sock.close()
    print(json.dumps({"sent":sent,"duration":args.duration,"pps":sent/max(args.duration,1e-6)}))

if __name__=="__main__":
    main()
