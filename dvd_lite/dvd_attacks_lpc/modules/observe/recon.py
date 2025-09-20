#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import time
import json
from scapy.all import sniff, UDP, IP
from threading import Event

# --- 경로 설정 및 로거 import ---
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from bus.logger import log_bus_event

# --- 설정 ---
INTERFACE = os.environ.get("RECON_INTERFACE", "eth0")
TARGET_INFO_FILE = "/shared/target.info"
# GCS의 IP 주소
GCS_IP = "10.13.0.4" 
# 감청 타임아웃 (이 시간 안에 타겟을 못 찾으면 실패)
LISTEN_TIMEOUT_SEC = 120 

class Recon:
    def __init__(self):
        self.target_found = Event()
        self.discovered_target = None

    def packet_handler(self, packet):
        """GCS가 보내는 패킷을 감청하여 드론의 실제 위치를 찾아냅니다."""
        if IP in packet and UDP in packet and packet[IP].src == GCS_IP:
            # GCS가 보내는 패킷의 목적지가 바로 드론의 현재 위치
            self.discovered_target = f"{packet[IP].dst}:{packet[UDP].dport}"
            self.target_found.set() # 찾았다는 신호 보내기

    def run(self):
        print("[RECON] 시작: GCS와 드론 간의 통신을 감청합니다...")
        log_bus_event("recon_started", {"method": "passive_listening"})

        try:
            sniff(iface=INTERFACE, filter="udp", prn=self.packet_handler, stop_filter=lambda p: self.target_found.is_set(), timeout=LISTEN_TIMEOUT_SEC)

            if self.discovered_target:
                print(f"[RECON] 성공: 타겟 '{self.discovered_target}' 발견.")
                log_bus_event("recon_succeeded", {"target": self.discovered_target})
                # 발견한 타겟 정보를 파일에 기록하여 오케스트레이터가 사용할 수 있도록 함
                with open(TARGET_INFO_FILE, 'w') as f:
                    f.write(self.discovered_target)
            else:
                print(f"[RECON] 실패: {LISTEN_TIMEOUT_SEC}초 내에 타겟을 찾지 못했습니다.")
                log_bus_event("recon_failed", {"reason": "timeout"})

        except Exception as e:
            print(f"❌ [RECON] 오류: {e}", file=sys.stderr)
            log_bus_event("recon_error", {"error": str(e)})

if __name__ == "__main__":
    # 이전 정보를 삭제하고 새로 시작
    if os.path.exists(TARGET_INFO_FILE):
        os.remove(TARGET_INFO_FILE)
    
    recon = Recon()
    recon.run()
    print("[RECON] 정찰 임무 완료. 종료합니다.")