#!/usr/bin/env python3
import argparse, json, os, time, ipaddress, re, sys
from datetime import datetime
from pathlib import Path

# scapy는 venv에 설치됨(이미 있음). root 권한 필요
from scapy.all import sniff, UDP, IP

def detect_bridge():
    # 첫 번째 br-* 인터페이스 자동 선택
    try:
        out = os.popen("ip -brief link | awk '/^br-/{print $1}' | head -n1").read().strip()
        return out or None
    except Exception:
        return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iface", default="auto")
    ap.add_argument("--listen-cidr", default="10.13.0.0/24")
    ap.add_argument("--out", default=None)
    ap.add_argument("--gcs", default="10.13.0.4:14550")
    args = ap.parse_args()

    base = os.environ.get("BASE", os.getcwd())
    out_path = args.out or f"{base}/attack_output/bus.log"
    Path(os.path.dirname(out_path)).mkdir(parents=True, exist_ok=True)

    if args.iface == "auto":
        iface = detect_bridge()
        if not iface:
            print("[ERR] br-* 인터페이스 자동탐지 실패. --iface 로 지정하세요.", file=sys.stderr); sys.exit(1)
    else:
        iface = args.iface

    net = ipaddress.ip_network(args.listen_cidr, strict=False)
    gcs_ip, gcs_port = args.gcs.split(":")
    gcs_port = int(gcs_port)

    print(f"[i] sniff iface={iface} net={net} gcs={gcs_ip}:{gcs_port}")
    f = open(out_path, "a", encoding="utf-8")

    def on_pkt(pkt):
        try:
            if not (IP in pkt and UDP in pkt): return
            ip = pkt[IP]; udp = pkt[UDP]
            # 대상 네트만 로깅
            if ipaddress.ip_address(ip.src) not in net and ipaddress.ip_address(ip.dst) not in net:
                return
            d = {
                "ts": time.time(),
                "ts_iso": datetime.utcnow().isoformat()+"Z",
                "src": ip.src, "dst": ip.dst,
                "sport": int(udp.sport), "dport": int(udp.dport),
                "len": int(len(pkt)),
                "proto": "UDP",
                "is_mav_target": (ip.dst == gcs_ip and int(udp.dport) == gcs_port),
            }
            f.write(json.dumps(d, ensure_ascii=False)+"\n"); f.flush()
        except Exception as e:
            pass

    sniff(iface=iface, filter="udp", prn=on_pkt, store=False)

if __name__ == "__main__":
    main()
