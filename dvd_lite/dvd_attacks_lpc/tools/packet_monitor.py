#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
import os
import sys
from scapy.all import sniff, IP, UDP, TCP
from datetime import datetime
from collections import OrderedDict
import threading
import time

# --- ANSI 컬러 코드 ---
class Colors:
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    RESET = '\033[0m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'

# --- docker-compose-lite.yaml 기반 호스트 이름 매핑 ---
KNOWN_HOSTS = {
    "10.13.0.1": "GATEWAY",
    "10.13.0.2": "FC-LITE",
    "10.13.0.3": "CC-LITE",
    "10.13.0.4": "GCS-LITE",
    "10.13.0.5": "SIM-LITE",
    "10.13.0.100": "DECOY",
    "10.13.0.200": "ATTACKER",
    "10.13.0.202": "OBSERVER",
    "10.13.0.250": "MTD-ENGINE",
    "10.13.0.203": "RL-AGENT",
}

# --- 실시간 흐름 관리를 위한 전역 변수 ---
active_flows = OrderedDict()
lock = threading.Lock()

def get_host_name(ip):
    return KNOWN_HOSTS.get(ip, ip)

def get_flow_key(packet):
    """패킷을 기반으로 고유한 '흐름' 키를 생성합니다."""
    key = None
    if IP in packet:
        proto = packet[IP].proto
        src_ip = packet[IP].src
        dst_ip = packet[IP].dst
        if UDP in packet:
            proto = "UDP"
            sport = packet[UDP].sport
            dport = packet[UDP].dport
            key = (src_ip, dst_ip, proto, sport, dport)
        elif TCP in packet:
            proto = "TCP"
            sport = packet[TCP].sport
            dport = packet[TCP].dport
            key = (src_ip, dst_ip, proto, sport, dport)
    return key

def is_mavlink_heartbeat(payload):
    """
    주어진 페이로드가 MAVLink HEARTBEAT 메시지인지 간단하게 확인합니다.
    - MAVLink v1.0 (시작 바이트 0xFE), HEARTBEAT (MSG ID: 0)
    - MAVLink v2.0 (시작 바이트 0xFD), HEARTBEAT (MSG ID: 0)
    """
    try:
        # MAVLink v1 (STX, LEN, SEQ, SYS, COMP, MSG_ID, ...)
        if len(payload) >= 8 and payload[0] == 0xFE and payload[5] == 0:
            return True
        # MAVLink v2 (STX, LEN, INC_FLAGS, CMP_FLAGS, SEQ, SYS, COMP, MSG_ID_3B, ...)
        if len(payload) >= 10 and payload[0] == 0xFD and payload[7] == 0 and payload[8] == 0 and payload[9] == 0:
            return True
    except IndexError:
        pass
    return False

def update_and_print_flows():
    """터미널 화면을 지우고 현재 활성화된 모든 흐름 정보를 출력합니다."""
    sys.stdout.write("\033[H\033[J") # 화면 지우기
    
    print("="*95)
    print(f"{Colors.BOLD} Docker Network Real-time Flow Monitor (v5.0 - MAVLink Aware){Colors.RESET}")
    print("="*95)
    print(f"{'Source':<18} -> {'Destination':<18} | {'Proto':<5} | {'Port Flow':<18} | {'Packets':>8} | {'Total Bytes':>12} | {'MAVLink HB':>10}")
    print("-"*95)
    
    with lock:
        for key, data in active_flows.items():
            src_ip, dst_ip, proto, sport, dport = key
            
            src_name = get_host_name(src_ip)
            dst_name = get_host_name(dst_ip)
            
            # 공격자 트래픽 강조
            if src_ip == "10.13.0.200":
                src_name = f"{Colors.RED}{src_name}{Colors.RESET}"

            # MAVLink 하트비트 카운트 표시
            heartbeat_count = data.get('heartbeats', 0)
            hb_display = f"{Colors.CYAN}{heartbeat_count}{Colors.RESET}" if heartbeat_count > 0 else str(heartbeat_count)

            line = (
                f"{src_name:<25} -> {dst_name:<25} | "
                f"{Colors.GREEN if proto == 'UDP' else Colors.YELLOW}{proto:<5}{Colors.RESET} | "
                f"{str(sport) + ' -> ' + str(dport):<18} | "
                f"{data['count']:>8} | {data['bytes']:>12} | {hb_display:>18}"
            )
            print(line)
    sys.stdout.flush()

def packet_callback(packet):
    """캡처된 패킷을 분석하여 흐름 정보를 업데이트합니다."""
    flow_key = get_flow_key(packet)
    if not flow_key:
        return

    with lock:
        packet_size = len(packet)
        
        # setdefault를 사용하여 키가 없으면 기본값으로 생성
        flow_data = active_flows.setdefault(flow_key, {'count': 0, 'bytes': 0, 'heartbeats': 0})
        
        # 카운트와 바이트 증가
        flow_data['count'] += 1
        flow_data['bytes'] += packet_size

        # MAVLink 하트비트인지 확인
        if UDP in packet:
            payload = bytes(packet[UDP].payload)
            if is_mavlink_heartbeat(payload):
                flow_data['heartbeats'] += 1

def main():
    # 1초마다 화면을 갱신하는 별도의 스레드
    def print_loop():
        while True:
            update_and_print_flows()
            time.sleep(1)
            
    print_thread = threading.Thread(target=print_loop, daemon=True)
    print_thread.start()

    try:
        sniff(iface=args.interface, prn=packet_callback, store=0)
    except Exception as e:
        print(f"❌ 스니핑 시작 오류: {e}", file=sys.stderr)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Docker 네트워크 실시간 흐름 모니터링 도구 (MAVLink 감지 기능 포함)")
    parser.add_argument('-i', '--interface', required=True, help="감시할 네트워크 인터페이스 이름 (예: br-xxxxxxxxxxxx)")
    args = parser.parse_args()
    
    try:
        import scapy
    except ImportError:
        print("[오류] 'scapy'가 설치되지 않았습니다. 'pip install scapy'를 실행해주세요.", file=sys.stderr)
        sys.exit(1)

    main()