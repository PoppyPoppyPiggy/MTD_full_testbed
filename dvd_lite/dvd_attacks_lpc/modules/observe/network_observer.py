#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Network Observer:
- docker.sock 로 네트워크 맵 수집(mtd_network_snapshot 확장)
- scapy 로 udp/icmp/arp sniff → net_packet/udp_packet/icmp_packet/arp_packet
- 각 컨테이너 heartbeat, 라우팅 변화 감지
"""

import os, sys, time, json, threading
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

# 프로젝트 루트
MOD_DIR = os.path.dirname(os.path.realpath(__file__))
LPC_DIR = os.path.abspath(os.path.join(MOD_DIR, '..', '..'))
if LPC_DIR not in sys.path: sys.path.append(LPC_DIR)

try:
    from bus.logger import log_bus_event
except Exception:
    def log_bus_event(event_type, data):
        payload = {"event_type": event_type, "data": data, "timestamp": time.time()}
        print(json.dumps(payload, ensure_ascii=False), flush=True)

# docker / scapy 로딩
import docker
from scapy.all import sniff, IP, UDP, ICMP, ARP

BUS_SNAPSHOT_INTERVAL = float(os.getenv("OBS_SNAPSHOT_INTERVAL", "5"))
OBS_IFACE = os.getenv("OBS_IFACE", "eth0")
TARGET_PORTS = {14550, 5760, 3000}  # mavlink, SITL, http 등

def _iso_now():
    return datetime.now(timezone.utc).isoformat()

def docker_client():
    try:
        return docker.from_env()
    except Exception:
        return None

def snapshot_network_state(cli) -> Dict[str, Any]:
    out = {}
    try:
        nets = {n.name: n for n in cli.networks.list()}
        if "simulator" not in nets: return out
        net = nets["simulator"]
        net.reload()
        for c in net.containers:
            try:
                details = c.attrs.get("NetworkSettings", {}).get("Networks", {}).get("simulator", {})
                out[c.name] = {
                    "ip_address": details.get("IPAddress"),
                    "mac_address": details.get("MacAddress"),
                    "id": c.id[:12],
                    "image": c.attrs.get("Config",{}).get("Image"),
                    "labels": c.attrs.get("Config",{}).get("Labels",{})
                }
            except Exception:
                continue
    except Exception:
        pass
    return out

def snapshot_loop():
    cli = docker_client()
    if not cli:
        log_bus_event("observer_error", {"error": "docker_unavailable"})
        return
    last = {}
    while True:
        cur = snapshot_network_state(cli)
        if cur and cur != last:
            log_bus_event("mtd_network_snapshot", {"network": "simulator", "state": cur})
            last = cur
        time.sleep(BUS_SNAPSHOT_INTERVAL)

def pkt_emit(base_type: str, kv: Dict[str, Any]):
    # 통일감 있게 상위 "type" 도 넣어준다(Exporter가 둘 다 읽음).
    payload = dict(kv)
    payload["type"] = base_type
    payload["timestamp"] = _iso_now()
    payload["ts"] = time.time()
    # bus.logger 스타일
    log_bus_event(base_type, kv)

def pkt_sniffer():
    def _handler(pkt):
        try:
            if ARP in pkt:
                p = pkt[ARP]
                kv = {
                    "proto": "ARP",
                    "op": int(p.op),
                    "src_ip": p.psrc, "dst_ip": p.pdst,
                    "src_mac": p.hwsrc, "dst_mac": p.hwdst,
                }
                pkt_emit("arp_packet", kv)
                return
            if ICMP in pkt and IP in pkt:
                ip = pkt[IP]; ic = pkt[ICMP]
                kv = {
                    "proto": "ICMP",
                    "src_ip": ip.src, "dst_ip": ip.dst,
                    "type": int(ic.type), "code": int(ic.code)
                }
                pkt_emit("icmp_packet", kv)
                return
            if UDP in pkt and IP in pkt:
                ip = pkt[IP]; ud = pkt[UDP]
                kv = {
                    "proto": "UDP",
                    "src_ip": ip.src, "dst_ip": ip.dst,
                    "src_port": int(ud.sport), "dst_port": int(ud.dport)
                }
                pkt_emit("udp_packet", kv)
                # 일반화 이벤트
                if ud.dport in TARGET_PORTS:
                    pkt_emit("net_packet", {**kv})
                return
            # 기타 L3
            if IP in pkt:
                ip = pkt[IP]
                kv = {"proto": "IP", "src_ip": ip.src, "dst_ip": ip.dst}
                pkt_emit("net_packet", kv)
        except Exception as e:
            log_bus_event("observer_error", {"error": str(e)})

    # BPF 필터: 필요한 것만(너무 빡세게 걸면 못 잡을 수 있음)
    # 여기선 wide-open 으로 두고 Python에서 분기
    sniff(iface=OBS_IFACE, prn=_handler, store=False)

def heartbeat_loop():
    """관심 서비스 heartbeat."""
    while True:
        log_bus_event("observer_heartbeat", {"msg": "alive"})
        time.sleep(10)

def main():
    log_bus_event("observer_start", {"iface": OBS_IFACE, "targets": list(TARGET_PORTS)})
    t1 = threading.Thread(target=snapshot_loop, daemon=True)
    t2 = threading.Thread(target=pkt_sniffer, daemon=True)
    t3 = threading.Thread(target=heartbeat_loop, daemon=True)
    t1.start(); t2.start(); t3.start()
    # 포그라운드 유지
    while True:
        time.sleep(3600)

if __name__ == "__main__":
    main()
