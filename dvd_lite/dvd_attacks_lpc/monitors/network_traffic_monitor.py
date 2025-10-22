#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import time
import json
import datetime
# ⭐️ scapy.all 대신 필요한 모듈만 임포트 (잠재적 충돌 방지)
from scapy.all import sniff, IP, TCP, UDP, ARP, Ether

# --- Path Configuration ---
MONITORS_DIR = os.path.dirname(os.path.realpath(__file__))
BUS_DIR = os.path.join(os.path.dirname(MONITORS_DIR), 'bus')
LOG_FILE_PATH = os.path.join(BUS_DIR, 'bus_network.log') # 네트워크 전용 로그

# --- Environment Variables ---
CURRENT_ATTACK_LABEL = os.environ.get('ATTACK_NAME', 'normal')
SNIFF_INTERFACE = os.environ.get('SNIFF_INTERFACE', None) # 기본값 None으로 변경

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
        flags = packet[TCP].flags
        # scapy 2.4.5 기준 플래그 문자열 사용 (더 직관적)
        flag_str = str(flags) # 예: "SA", "FPA", "S", "A"
        return flag_str
        # 이전 방식 (비트마스크)
        # return {
        #     'FIN': bool(flags & 0x01), 'SYN': bool(flags & 0x02),
        #     'RST': bool(flags & 0x04), 'PSH': bool(flags & 0x08),
        #     'ACK': bool(flags & 0x10), 'URG': bool(flags & 0x20),
        # }
    return None

def packet_handler(packet):
    global last_packet_time

    current_time = time.time()
    inter_arrival_time = (current_time - (last_packet_time or current_time)) * 1000
    last_packet_time = current_time

    log_data = {
        "length": len(packet),
        "inter_arrival_time_ms": round(inter_arrival_time, 4),
        "src_mac": None, # MAC 주소 필드 추가
        "dst_mac": None,
    }

    # L2 정보 (MAC 주소) 추출
    if packet.haslayer(Ether):
         eth_layer = packet.getlayer(Ether)
         log_data["src_mac"] = eth_layer.src
         log_data["dst_mac"] = eth_layer.dst

    # ARP 패킷 처리
    if packet.haslayer(ARP):
        arp_layer = packet.getlayer(ARP)
        log_data.update({
            "src_ip": arp_layer.psrc, "dst_ip": arp_layer.pdst,
            # ARP에서는 hwsrc/hwdst가 MAC 주소이므로 L2 정보와 중복될 수 있음 (필요시 제거)
            #"src_mac": arp_layer.hwsrc, "dst_mac": arp_layer.hwdst,
            "protocol": "ARP",
            "arp_op": arp_layer.op # 1 for request, 2 for reply
        })

    # IP 패킷 처리
    elif packet.haslayer(IP):
        ip_layer = packet.getlayer(IP)
        proto, src_port, dst_port = "IP", None, None # 기본 프로토콜 IP로 설정
        tcp_flags = None

        if packet.haslayer(TCP):
            tcp_layer = packet.getlayer(TCP)
            proto, src_port, dst_port = "TCP", tcp_layer.sport, tcp_layer.dport
            tcp_flags = get_tcp_flags(packet)
        elif packet.haslayer(UDP):
            udp_layer = packet.getlayer(UDP)
            proto, src_port, dst_port = "UDP", udp_layer.sport, udp_layer.dport
        # 다른 프로토콜(ICMP 등) 추가 가능
        elif ip_layer.proto == 1: # ICMP
             proto = "ICMP"
             # ICMP 타입/코드 추가 가능
             # icmp_layer = packet.getlayer(ICMP)
             # log_data["icmp_type"] = icmp_layer.type
             # log_data["icmp_code"] = icmp_layer.code

        log_data.update({
            "src_ip": ip_layer.src, "dst_ip": ip_layer.dst,
            "protocol": proto, "src_port": src_port, "dst_port": dst_port,
            "tcp_flags": tcp_flags,
            "ip_ttl": ip_layer.ttl, # TTL 정보 추가
            "ip_len": ip_layer.len, # IP 헤더 포함 길이
        })
    else:
        # L2 프레임이지만 ARP/IP가 아닌 경우 (예: LLDP, STP 등) - 필요 시 로깅
        # print(f"Non IP/ARP packet: {packet.summary()}")
        return # 일단 무시

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

    # 인터페이스 자동 감지 또는 명시적 지정
    global SNIFF_INTERFACE
    if SNIFF_INTERFACE is None:
        # Docker 환경 등에서 기본 인터페이스 찾기 시도 (예: eth0)
        # 좀 더 견고한 방법 필요 시 get_if_list() 등 사용
        possible_interfaces = ['eth0', 'ensp0s3', 'enp1s0'] # 일반적인 인터페이스 이름
        found = False
        from scapy.arch import get_if_list
        available_interfaces = get_if_list()
        for iface in possible_interfaces:
            if iface in available_interfaces:
                SNIFF_INTERFACE = iface
                found = True
                break
        if not found and available_interfaces:
             SNIFF_INTERFACE = available_interfaces[0] # 첫 번째 인터페이스 사용
             print(f"[Network Monitor] 경고: 기본 인터페이스를 찾을 수 없어 '{SNIFF_INTERFACE}'를 사용합니다.")
        elif not found:
             print("❌ [Network Monitor] 오류: 사용 가능한 네트워크 인터페이스를 찾을 수 없습니다. SNIFF_INTERFACE 환경 변수를 설정해주세요.")
             sys.exit(1)

    print(f"[Network Monitor] 네트워크 패킷 모니터링 시작 (iface: {SNIFF_INTERFACE}) -> {LOG_FILE_PATH}")
    print(f"✅ [Network Monitor] 현재 공격 라벨: {CURRENT_ATTACK_LABEL}")

    try:
        # filter="ip or arp" 로 IP와 ARP 패킷만 캡처
        sniff(iface=SNIFF_INTERFACE, filter="ip or arp", prn=packet_handler, store=0)
    except PermissionError:
        print(f"❌ [Network Monitor] 권한 오류: 패킷 스니핑을 위해 root 권한이 필요합니다.", file=sys.stderr)
        sys.exit(1)
    except OSError as e:
        # 인터페이스 찾기 실패 또는 다른 OS 수준 오류
        if "No such device" in str(e) or "not found" in str(e):
             print(f"❌ [Network Monitor] OS 오류: 인터페이스 '{SNIFF_INTERFACE}'를 찾을 수 없습니다.", file=sys.stderr)
             print("   사용 가능한 인터페이스 목록:", get_if_list())
             print("   SNIFF_INTERFACE 환경 변수를 올바른 값으로 설정해주세요.")
        else:
             print(f"❌ [Network Monitor] OS 오류 발생: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n[Network Monitor] 사용자 요청으로 모니터링 중지.")
    except Exception as e:
         print(f"❌ [Network Monitor] 예기치 않은 오류 발생: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
