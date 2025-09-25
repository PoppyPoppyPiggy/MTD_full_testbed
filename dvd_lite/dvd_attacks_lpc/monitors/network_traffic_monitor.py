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
LOG_FILE_PATH = os.path.join(BUS_DIR, 'bus_network.log') # ⭐️ 통합 로그 파일 경로

# ⭐️ 공격 상태를 식별하기 위한 환경 변수
CURRENT_ATTACK_LABEL = os.environ.get('ATTACK_NAME', 'normal')

# 캡처할 네트워크 인터페이스
SNIFF_INTERFACE = os.environ.get('SNIFF_INTERFACE', 'eth0')

def write_jsonl(record: dict):
    """JSONL 형식으로 로그를 파일에 씁니다."""
    # ⭐️ 레코드에 공격 라벨 필드 추가
    record['attack_label'] = CURRENT_ATTACK_LABEL
    try:
        with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except IOError as e:
        print(f"❌ [Network Monitor] 로그 파일 쓰기 오류: {e}", file=sys.stderr)

def packet_handler(packet):
    """scapy가 캡처한 각 패킷을 처리하는 콜백 함수"""
    if not packet.haslayer(IP):
        return

    ip_layer = packet.getlayer(IP)
    proto, src_port, dst_port = "UNKNOWN", None, None

    if packet.haslayer(TCP):
        tcp_layer = packet.getlayer(TCP)
        proto, src_port, dst_port = "TCP", tcp_layer.sport, tcp_layer.dport
    elif packet.haslayer(UDP):
        udp_layer = packet.getlayer(UDP)
        proto, src_port, dst_port = "UDP", udp_layer.sport, udp_layer.dport

    log_data = {
        "src_ip": ip_layer.src, "dst_ip": ip_layer.dst,
        "protocol": proto, "src_port": src_port, "dst_port": dst_port,
        "length": len(packet),
    }

    record = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "ts": time.time(),
        "source": "network_monitor",
        "type": "packet_capture",
        "data": log_data
    }
    write_jsonl(record)

def main():
    """네트워크 인터페이스의 패킷을 캡처하여 통합 로그에 기록합니다."""
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