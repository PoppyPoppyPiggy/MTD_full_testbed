#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import json
import datetime
from scapy.all import sniff, IP, TCP, UDP

# --- 경로 설정 ---
MONITORS_DIR = os.path.dirname(os.path.realpath(__file__))
BUS_DIR = os.path.join(os.path.dirname(MONITORS_DIR), 'bus')
LOG_FILE_PATH = os.path.join(BUS_DIR, 'bus_network.log')

# --- 환경 변수 ---
CURRENT_ATTACK_LABEL = os.environ.get('ATTACK_NAME', 'normal')
SNIFF_INTERFACE = os.environ.get('SNIFF_INTERFACE', 'eth0')

# ### <<< CHANGED ###
# 마지막 패킷 도착 시간을 추적하기 위한 전역 변수
last_packet_time = None
# ### <<< END CHANGED ###

def write_jsonl(record: dict):
    record['attack_label'] = CURRENT_ATTACK_LABEL
    try:
        with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    except IOError as e:
        print(f"❌ [Network Monitor] 로그 파일 쓰기 오류: {e}", file=sys.stderr)

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

    ### <<< CHANGED ###
    current_time = time.time()
    inter_arrival_time = (current_time - last_packet_time) * 1000 if last_packet_time else 0.0
    last_packet_time = current_time
    ### <<< END CHANGED ###

    ip_layer = packet.getlayer(IP)
    proto, src_port, dst_port = "UNKNOWN", None, None
    tcp_flags = None

    if packet.haslayer(TCP):
        tcp_layer = packet.getlayer(TCP)
        proto, src_port, dst_port = "TCP", tcp_layer.sport, tcp_layer.dport
        tcp_flags = get_tcp_flags(packet) # ### <<< CHANGED ###
    elif packet.haslayer(UDP):
        udp_layer = packet.getlayer(UDP)
        proto, src_port, dst_port = "UDP", udp_layer.sport, udp_layer.dport

    log_data = {
        "src_ip": ip_layer.src, "dst_ip": ip_layer.dst,
        "protocol": proto, "src_port": src_port, "dst_port": dst_port,
        "length": len(packet),
        "tcp_flags": tcp_flags, # ### <<< CHANGED ###
        "inter_arrival_time_ms": round(inter_arrival_time, 4) # ### <<< CHANGED ###
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
    print(f"[Network Monitor] 네트워크 패킷 모니터링 시작 (iface: {SNIFF_INTERFACE}) -> {LOG_FILE_PATH}")
    print(f"✅ [Network Monitor] 현재 공격 라벨: {CURRENT_ATTACK_LABEL}")
    
    try:
        sniff(iface=SNIFF_INTERFACE, prn=packet_handler, store=0)
    except PermissionError:
        print(f"❌ [Network Monitor] 권한 오류: root 권한이 필요합니다.", file=sys.stderr)
        sys.exit(1)
    except OSError as e:
        print(f"❌ [Network Monitor] 오류: '{SNIFF_INTERFACE}' 인터페이스를 찾을 수 없습니다. ({e})", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n[Network Monitor] 사용자 요청으로 모니터링을 중지합니다.")

if __name__ == "__main__":
    main()