#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
import json
import os
import socket
import sys
import time
from typing import Tuple

# ── 프로젝트 루트 경로 및 버스 로거 import ─────────────────────────────────────
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

try:
    from bus.logger import log_bus_event
except Exception:
    def log_bus_event(event_type, data):
        print(json.dumps({"type": event_type, "data": data, "ts": time.time()}), flush=True)

DEFAULT_STATE = os.path.join(PROJECT_ROOT, "mtd", "shared_state", "mtd_state.json")

def read_target(state_file: str) -> Tuple[str, int]:
    try:
        with open(state_file, "r", encoding="utf-8") as f:
            st = json.load(f)
        cur = st.get("current_target") or "10.13.0.3:14550"
        ip, port = cur.split(":")[0], int(cur.split(":")[1])
        return ip, port
    except Exception:
        return "10.13.0.3", 14550

def send_udp_probe(dst_ip: str, dst_port: int, payload: bytes = b"PROBE", bind_ip: str = "") -> Tuple[str, int]:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(0.2)
    try:
        if bind_ip:
            s.bind((bind_ip, 0))
        s.connect((dst_ip, dst_port))
        s.send(payload)
        src_ip, src_port = s.getsockname()
        return src_ip, src_port
    except Exception:
        try:
            src_ip, src_port = s.getsockname()
        except Exception:
            src_ip, src_port = "0.0.0.0", 0
        return src_ip, src_port
    finally:
        s.close()

def main():
    p = argparse.ArgumentParser(description="Lightweight UDP prober that logs hits to bus.log")
    p.add_argument("--interval", type=float, default=1.0, help="probe 주기(초)")
    p.add_argument("--state-file", type=str, default=DEFAULT_STATE, help="mtd_state.json 경로")
    p.add_argument("--bind-ip", type=str, default="", help="지정 시 해당 소스 IP로 UDP 바인드")
    p.add_argument("--payload", type=str, default="PROBE", help="보낼 페이로드(문자열)")
    args = p.parse_args()

    print(f"[PROBER] start | state_file={args.state_file} | interval={args.interval:.1f}s")
    last_ip, last_port = None, None

    while True:
        dst_ip, dst_port = read_target(args.state_file)
        if (dst_ip, dst_port) != (last_ip, last_port):
            print(f"[PROBER] target -> {dst_ip}:{dst_port}")
            log_bus_event("prober_target_changed", {"target": f"{dst_ip}:{dst_port}"})
            last_ip, last_port = dst_ip, dst_port

        src_ip, src_port = send_udp_probe(dst_ip, dst_port, args.payload.encode("utf-8"), bind_ip=args.bind_ip)
        print(f"[PROBER] hit -> {src_ip}:{src_port} => {dst_ip}:{dst_port}")

        # orchestrator 게이트가 인식하는 표준 UDP 이벤트
        log_bus_event("udp_packet", {
            "proto": "UDP",
            "src_ip": src_ip,
            "src_port": src_port,
            "dst_ip": dst_ip,
            "dst_port": dst_port
        })

        time.sleep(args.interval)

if __name__ == "__main__":
    main()
