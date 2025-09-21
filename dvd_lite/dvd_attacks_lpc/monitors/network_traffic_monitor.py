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
LPC_DIR = os.path.dirname(MONITORS_DIR)
BUS_DIR = os.path.join(LPC_DIR, 'bus')

# 출력 파일 경로
OUTPUT_LOG_FILE = os.path.join(BUS_DIR, 'bus_network.log')

# 캡처할 네트워크 인터페이스 (Docker 내부에서는 보통 'eth0')
SNIFF_INTERFACE = os.environ.get('SNIFF_INTERFACE', 'eth0')

def write_jsonl(record: dict):
    """JSONL 형식으로 로그를 파일에 씁니다."""
    try:
        with open(OUTPUT_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except IOError as e:
        print(f"❌ 네트워크 로그 파일 쓰기 오류: {e}", file=sys.stderr)

def packet_handler(packet):
    """scapy가 캡처한 각 패킷을 처리하는 콜백 함수"""
    
    # IP 레이어가 없는 패킷은 무시 (예: ARP)
    if not packet.haslayer(IP):
        return

    ip_layer = packet.getlayer(IP)
    proto = "UNKNOWN"
    src_port, dst_port = None, None

    if packet.haslayer(TCP):
        tcp_layer = packet.getlayer(TCP)
        proto = "TCP"
        src_port = tcp_layer.sport
        dst_port = tcp_layer.dport
    elif packet.haslayer(UDP):
        udp_layer = packet.getlayer(UDP)
        proto = "UDP"
        src_port = udp_layer.sport
        dst_port = udp_layer.dport

    # 로그로 기록할 데이터 구조
    log_data = {
        "src_ip": ip_layer.src,
        "dst_ip": ip_layer.dst,
        "protocol": proto,
        "src_port": src_port,
        "dst_port": dst_port,
        "length": len(packet),
        "summary": packet.summary()
    }

    # 전체 로그 레코드 생성
    record = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "ts": time.time(),
        "source": "network_sniffer",
        "type": "packet_captured",
        "data": log_data
    }
    
    write_jsonl(record)


def main():
    """네트워크 인터페이스의 모든 패킷을 캡처하여 bus_network.log에 기록합니다."""
    os.makedirs(os.path.dirname(OUTPUT_LOG_FILE), exist_ok=True)
    print(f"네트워크 패킷 모니터링 시작 (iface: {SNIFF_INTERFACE}) -> {OUTPUT_LOG_FILE}")
    
    try:
        # 'prn' 인자에 핸들러 함수를 지정하여 패킷이 캡처될 때마다 호출
        # 'store=0'은 메모리에 패킷을 저장하지 않도록 하여 성능을 확보
        sniff(iface=SNIFF_INTERFACE, prn=packet_handler, store=0)

    except PermissionError:
        print(f"❌ 권한 오류: 패킷 스니핑을 위해 root 권한이 필요합니다.", file=sys.stderr)
        print("    'sudo python3 network_traffic_monitor.py' 또는 privileged Docker 컨테이너에서 실행하세요.", file=sys.stderr)
        sys.exit(1)
    except OSError as e:
        print(f"❌ 오류: '{SNIFF_INTERFACE}' 인터페이스를 찾을 수 없습니다. ({e})", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n사용자 요청으로 모니터링을 중지합니다.")
    except Exception as e:
        print(f"❌ 알 수 없는 오류 발생: {e}", file=sys.stderr)

if __name__ == "__main__":
    # scapy 라이브러리 설치 확인
    try:
        from scapy.all import IP
    except ImportError:
        print("scapy 라이브러리가 설치되지 않았습니다. 'pip install scapy'를 실행해주세요.", file=sys.stderr)
        sys.exit(1)
        
    main()