#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import time
import json
import datetime
from scapy.all import sniff, IP, TCP, UDP

# --- Path Configuration ---
MONITORS_DIR = os.path.dirname(os.path.realpath(__file__))
BUS_DIR = os.path.join(os.path.dirname(MONITORS_DIR), 'bus')
LOG_FILE_PATH = os.path.join(BUS_DIR, 'bus_network.log')

# --- Environment Variables ---
CURRENT_ATTACK_LABEL = os.environ.get('ATTACK_NAME', 'normal')
SNIFF_INTERFACE = os.environ.get('SNIFF_INTERFACE', 'eth0')

# Global variable to track the last packet arrival time for IAT calculation
last_packet_time = None

def write_jsonl(record: dict):
    record['attack_label'] = CURRENT_ATTACK_LABEL
    try:
        with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    except IOError as e:
        print(f"❌ [Network Monitor] Error writing to log file: {e}", file=sys.stderr)

def get_tcp_flags(packet):
    """Extracts TCP flags from a packet."""
    if TCP in packet:
        # FSRPAU
        flags = packet[TCP].flags
        return {
            'FIN': bool(flags & 0x01),
            'SYN': bool(flags & 0x02),
            'RST': bool(flags & 0x04),
            'PSH': bool(flags & 0x08),
            'ACK': bool(flags & 0x10),
            'URG': bool(flags & 0x20),
        }
    return None

def packet_handler(packet):
    global last_packet_time
    
    if not packet.haslayer(IP):
        return

    current_time = time.time()
    # Calculate Inter-Arrival Time (IAT)
    inter_arrival_time = (current_time - (last_packet_time or current_time)) * 1000 
    last_packet_time = current_time
    

    ip_layer = packet.getlayer(IP)
    proto, src_port, dst_port = "UNKNOWN", None, None
    tcp_flags = None

    if packet.haslayer(TCP):
        tcp_layer = packet.getlayer(TCP)
        proto, src_port, dst_port = "TCP", tcp_layer.sport, tcp_layer.dport
        tcp_flags = get_tcp_flags(packet) 
    elif packet.haslayer(UDP):
        udp_layer = packet.getlayer(UDP)
        proto, src_port, dst_port = "UDP", udp_layer.sport, udp_layer.dport

    log_data = {
        "src_ip": ip_layer.src, "dst_ip": ip_layer.dst,
        "protocol": proto, "src_port": src_port, "dst_port": dst_port,
        "length": len(packet),
        "tcp_flags": tcp_flags, 
        "inter_arrival_time_ms": round(inter_arrival_time, 4) 
    }

    record = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "ts": current_time,
        "source": "network_monitor",
        "type": "packet_capture",
        "data": log_data
    }
    write_jsonl(record)

def main():
    os.makedirs(os.path.dirname(LOG_FILE_PATH), exist_ok=True)
    print(f"[Network Monitor] Starting network packet monitoring (iface: {SNIFF_INTERFACE}) -> {LOG_FILE_PATH}")
    print(f"✅ [Network Monitor] Current attack label: {CURRENT_ATTACK_LABEL}")
    
    try:
        sniff(iface=SNIFF_INTERFACE, prn=packet_handler, store=0)
    except PermissionError:
        print(f"❌ [Network Monitor] Permission Error: Root privileges are required.", file=sys.stderr)
        sys.exit(1)
    except OSError as e:
        print(f"❌ [Network Monitor] OS Error: Could not find interface '{SNIFF_INTERFACE}'. ({e})", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n[Network Monitor] Monitoring stopped by user.")

if __name__ == "__main__":
    main()
