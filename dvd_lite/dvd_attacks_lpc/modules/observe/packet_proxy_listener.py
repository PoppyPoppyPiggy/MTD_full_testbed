#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
from scapy.all import sniff, UDP, IP

# --- ANSI 컬러 코드 ---
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'

# --- 경로 설정 및 로거 import ---
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from bus.logger import log_bus_event

# --- 설정 ---
INTERFACE = os.environ.get("PROXY_INTERFACE", "eth0")
ATTACKER_IP = os.environ.get("ATTACKER_IP", "10.13.0.200")

def packet_callback(packet):
    """
    공격자 IP로부터 오는 UDP 패킷을 필터링하여 bus.log에 기록하고, 터미널에 시각적 피드백을 제공합니다.
    """
    if IP in packet and UDP in packet and packet[IP].src == ATTACKER_IP:
        src_ip = packet[IP].src
        dst_ip = packet[IP].dst
        dst_port = packet[UDP].dport
        
        # 1. 터미널에 시각적 피드백 출력
        log_line = (
            f"[{Colors.YELLOW}PROXY{Colors.RESET}] "
            f"Attacker Packet Forwarded to ns-3: "
            f"{Colors.GREEN}{src_ip}{Colors.RESET} -> "
            f"{Colors.BLUE}{dst_ip}:{dst_port}{Colors.RESET}"
        )
        print(log_line)
        
        # 2. ns-3 시뮬레이터가 인지할 수 있도록 bus.log에 이벤트 기록
        log_bus_event("external_packet_detected", {
            "src_ip": src_ip,
            "dst_ip": dst_ip,
            "dst_port": dst_port
        })

def main():
    print("="*52)
    print(" Packet Proxy Listener for ns-3 (v2.0 - Live Feed)")
    print("="*52)
    print(f" 감시 인터페이스 : {INTERFACE}")
    print(f" 공격자 IP 필터 : {ATTACKER_IP}")
    print(" 외부 공격 패킷 감지를 시작합니다... (Ctrl+C로 종료)")
    
    try:
        sniff(iface=INTERFACE, filter="udp", prn=packet_callback, store=0)
    except Exception as e:
        print(f"❌ 스니핑 시작 오류: {e}", file=sys.stderr)
        print("   -> 네트워크 인터페이스 이름을 확인하세요.", file=sys.stderr)
        print("   -> 'observer' 컨테이너가 'privileged: true' 또는 'cap_add: [NET_ADMIN, NET_RAW]'로 실행 중인지 확인하세요.", file=sys.stderr)

if __name__ == "__main__":
    main()