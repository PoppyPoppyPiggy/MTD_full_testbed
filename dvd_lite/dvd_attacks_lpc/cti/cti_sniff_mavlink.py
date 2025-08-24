#!/usr/bin/env python3
# UDP 트래픽을 가볍게 스니핑해 빈도가 높은 포트를 MAVLink 포트 후보로 기록
import argparse, os, time, socket
from collections import Counter
from scapy.all import sniff, IP, UDP

def load_store(path):
    kv = {}
    if os.path.exists(path):
        with open(path,'r') as f:
            for line in f:
                if '=' in line:
                    k,v = line.strip().split('=',1); kv[k]=v
    return kv

def save_store(path, kv):
    tmp = path + ".tmp"
    with open(tmp,'w') as f:
        for k,v in kv.items():
            f.write(f"{k}={v}\n")
    os.replace(tmp, path)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--iface", required=True, help="sniff할 호스트 인터페이스 (예: br-XXXX)")
    ap.add_argument("--target-ip", default=None, help="타깃 컨테이너 IP(알면 정확도↑)")
    ap.add_argument("--interval", type=float, default=2.0)
    ap.add_argument("--store", default=None, help="CTI env 경로 (기본: LPC_LOG_DIR/cti_targets.env)")
    args = ap.parse_args()

    lpc_dir = os.environ.get("LPC_LOG_DIR", "./attack_output")
    store_path = args.store or os.path.join(lpc_dir, "cti_targets.env")

    counter = Counter()
    last_update = 0

    def cb(pkt):
        nonlocal counter, last_update
        if IP in pkt and UDP in pkt:
            ip = pkt[IP]
            udp = pkt[UDP]
            if args.target_ip and not (ip.src == args.target_ip or ip.dst == args.target_ip):
                return
            # MAVLink는 작은 주기성 UDP가 많음 → 포트 빈도 누적
            if udp.sport and udp.dport:
                counter.update([udp.sport, udp.dport])

        now = time.time()
        if now - last_update >= args.interval:
            last_update = now
            if counter:
                port, _ = counter.most_common(1)[0]
                kv = load_store(store_path)
                kv["MAVLINK_PORT"] = str(port)
                save_store(store_path, kv)
                print(f"[cti_sniff_mavlink] MAVLINK_PORT={port} (to {store_path})")
                counter.clear()

    sniff(iface=args.iface, prn=cb, store=False)
