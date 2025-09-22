#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import time
import subprocess
import re

MONITOR_DIR = os.path.dirname(os.path.realpath(__file__))
LPC_ROOT = os.path.abspath(os.path.join(MONITOR_DIR, '..'))
if LPC_ROOT not in sys.path:
    sys.path.insert(0, LPC_ROOT)
from bus.logger import log_bus_event

TARGET_IP = "10.13.0.3"
SOURCE_IP = "10.13.0.4"

def get_ping_stats(target_ip: str) -> (float, float):
    """지정된 IP로 ping을 보내 RTT와 패킷 손실률을 반환합니다."""
    try:
        result = subprocess.run(
            ["ping", "-c", "5", "-i", "1", target_ip],
            capture_output=True, text=True, timeout=10
        )
        output = result.stdout
        rtt_match = re.search(r"rtt min/avg/max/mdev = [\d.]+/([\d.]+)/", output)
        avg_rtt = float(rtt_match.group(1)) if rtt_match else -1.0
        loss_match = re.search(r"(\d+)% packet loss", output)
        packet_loss = float(loss_match.group(1)) if loss_match else 100.0
        return avg_rtt, packet_loss
    except (subprocess.TimeoutExpired, Exception):
        return -1.0, 100.0

def run_qos_monitor():
    print("[QoS Monitor] GCS-드론 간 네트워크 품질 측정을 시작합니다.")
    while True:
        avg_rtt, packet_loss = get_ping_stats(TARGET_IP)
        log_bus_event(
            "qos_metric_update",
            {"source": SOURCE_IP, "target": TARGET_IP, "avg_rtt_ms": avg_rtt, "packet_loss_pct": packet_loss}
        )
        print(f"[QoS] Target: {TARGET_IP}, RTT: {avg_rtt:.2f} ms, Loss: {packet_loss:.1f}%")
        time.sleep(10)

if __name__ == "__main__":
    run_qos_monitor()