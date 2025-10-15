#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import time
import json
import datetime
import subprocess
import re
import numpy as np 

# --- Path Configuration ---
MONITORS_DIR = os.path.dirname(os.path.realpath(__file__))
BUS_DIR = os.path.join(os.path.dirname(MONITORS_DIR), 'bus')
# ⭐️ Changed log path to bus_qos.log to avoid conflicts
LOG_FILE_PATH = os.path.join(BUS_DIR, 'bus_qos.log')

# --- Environment Variables ---
CURRENT_ATTACK_LABEL = os.environ.get('ATTACK_NAME', 'normal')
TARGET_IP = os.environ.get('TARGET_IP', "10.13.0.3")
SOURCE_IP = os.environ.get('MY_IP_ADDRESS', "10.13.0.4")
PING_INTERVAL_SEC = 5

def write_jsonl(record: dict):
    record['attack_label'] = CURRENT_ATTACK_LABEL
    try:
        with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except IOError as e:
        print(f"❌ [QoS Monitor] Error writing to log file: {e}", file=sys.stderr)

def get_ping_stats(target_ip: str) -> (float, float, float):
    """Sends ping to the specified IP and returns RTT, packet loss, and jitter."""
    # Use 10 packets, 0.2s interval, 2s timeout
    try:
        result = subprocess.run(
            ["ping", "-c", "10", "-i", "0.2", "-W", "2", target_ip],
            capture_output=True, text=True, timeout=5
        )
        output = result.stdout
        
        # Extract RTT and packet loss
        rtt_match = re.search(r"rtt min/avg/max/mdev = [\d.]+/([\d.]+)/[\d.]+/([\d.]+)", output)
        
        # mdev (mean deviation) is used as a proxy for jitter
        avg_rtt = float(rtt_match.group(1)) if rtt_match else -1.0
        mdev_rtt = float(rtt_match.group(2)) if rtt_match else -1.0 

        loss_match = re.search(r"(\d+)% packet loss", output)
        packet_loss = float(loss_match.group(1)) if loss_match else 100.0

        return avg_rtt, packet_loss, mdev_rtt

    except (subprocess.TimeoutExpired, Exception):
        # Return default failure values
        return -1.0, 100.0, -1.0

def main():
    os.makedirs(os.path.dirname(LOG_FILE_PATH), exist_ok=True)
    print(f"[QoS Monitor] Starting network quality measurement -> {LOG_FILE_PATH}")
    print(f"✅ [QoS Monitor] Current attack label: {CURRENT_ATTACK_LABEL}")
    
    while True:
        try:
            avg_rtt, packet_loss, jitter = get_ping_stats(TARGET_IP) 
            
            record = {
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "ts": time.time(),
                "source": "qos_monitor",
                "type": "network_qos",
                "data": {
                    "target_ip": TARGET_IP,
                    "source_ip": SOURCE_IP,
                    "avg_rtt_ms": avg_rtt,
                    "packet_loss_pct": packet_loss,
                    "jitter_ms": jitter 
                }
            }
            write_jsonl(record)
            print(f"[QoS Monitor] Target: {TARGET_IP}, RTT: {avg_rtt:.2f} ms, Loss: {packet_loss:.1f}%, Jitter: {jitter:.2f} ms")
            
            time.sleep(PING_INTERVAL_SEC)
            
        except KeyboardInterrupt:
            print("\n[QoS Monitor] Monitoring stopped by user.")
            break
        except Exception as e:
            print(f"❌ [QoS Monitor] An exception occurred during processing: {e}", file=sys.stderr)
            time.sleep(2)

if __name__ == "__main__":
    main()
