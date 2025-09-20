#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
import os
import sys
import time
import random
import socket
import subprocess # 공격 스크립트 실행을 위해 추가
from scapy.all import sniff, UDP, IP
from threading import Thread, Event
from typing import Optional, Tuple, List, Dict, Any

# --- 경로 설정 및 로거 import (오류 수정) ---
# prober.py의 위치(modules/probe)에서 두 단계 위로 올라가야 bus 폴더를 찾을 수 있음
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
from bus.logger import log_bus_event

# --- 상수 및 설정 ---
POLICY_FILE_PATH = os.path.join(PROJECT_ROOT, "mtd", "shared_state", "mtd_policy.yaml")
INTERFACE = os.environ.get("PROBER_INTERFACE", "eth0")
MY_IP = os.environ.get("PROBER_BIND_IP", "10.13.0.201")

class ProberState:
    PASSIVE_ANALYSIS = "PASSIVE_ANALYSIS"
    PRIORITIZED_SCAN = "PRIORITIZED_SCAN"
    TARGET_LOCKED = "TARGET_LOCKED"
    ATTACK_PHASE = "ATTACK_PHASE" # 공격 페이즈 추가

class LpcStealthyProber:
    # __init__ 생성자 인자 수정 (TypeError 해결)
    def __init__(self, policy_path: str, interval: float, scan_interval: float):
        self.state = ProberState.PASSIVE_ANALYSIS
        self.policy = self._load_policy(policy_path)
        
        self.candidates: Dict[Tuple[str, int], Dict[str, Any]] = {
            (ip, port): {'score': 1.0, 'last_seen': 0}
            for ip in self.policy.get('decoy_pool', [])
            for port in self.policy.get('port_pool', [])
        }
        self.locked_target: Optional[Tuple[str, int]] = None
        self.successful_hits = 0
        
        # LPC 규칙 및 공격 트리거 설정
        self.lpc_rules = self.policy.get('lpc_rules', {})
        self.success_threshold = self.lpc_rules.get('attack_success_threshold', 3)
        self.attack_process: Optional[subprocess.Popen] = None

        self.stop_event = Event()
        self.interval = interval
        self.scan_interval = scan_interval

    def _load_policy(self, path: str) -> Dict[str, Any]:
        try:
            import yaml
            with open(path, 'r') as f: return yaml.safe_load(f)
        except (ImportError, FileNotFoundError):
            print("[경고] 정책 파일 없음. 기본값 사용.", file=sys.stderr)
            return {'decoy_pool': ['10.13.0.3'], 'port_pool': [14550], 'real_target_ip': '10.13.0.3'}

    def _passive_packet_handler(self, packet: IP):
        if self.state != ProberState.PASSIVE_ANALYSIS: return
        if IP in packet and UDP in packet and packet[IP].src == '10.13.0.4':
            target_cand = (packet[IP].dst, packet[UDP].dport)
            if target_cand in self.candidates:
                self.candidates[target_cand]['score'] += 10.0
                print(f"\n[Prober] 유력 후보 발견(Passive): {target_cand[0]}:{target_cand[1]} (Score: {self.candidates[target_cand]['score']:.1f})")

    def _update_target_state(self, new_target: Tuple[str, int], method: str):
        if new_target != self.locked_target:
            print(f"\n[Prober] 타겟 확정 ({method}): {new_target[0]}:{new_target[1]}")
            self.locked_target = new_target
            self.successful_hits = 0
        
        self.state = ProberState.TARGET_LOCKED
        self.candidates[new_target]['score'] = 100.0
        log_bus_event("prober_activity", {"source_ip": MY_IP, "target_ip": new_target[0], "method": "target_locked"})
        
        if new_target[0] == self.policy.get('real_target_ip'):
            self.successful_hits += 1
            print(f"\033[96m[Prober] 진짜 타겟 명중! (연속 {self.successful_hits}/{self.success_threshold}회)\033[0m")
            if self.successful_hits >= self.success_threshold and not self.attack_process:
                self._trigger_attack()

    def _trigger_attack(self):
        """LPC 임계치 달성 시 실제 공격을 개시합니다."""
        print(f"\n\033[91m[PROBER] ★★★ MTD 방어 돌파! 공격 페이즈를 시작합니다! ★★★\033[0m")
        self.state = ProberState.ATTACK_PHASE
        log_bus_event("lpc_attack_start", {"prober_ip": MY_IP, "target": f"{self.locked_target[0]}:{self.locked_target[1]}"})
        
        script_path = self.lpc_rules.get('attack_script_path')
        script_args = self.lpc_rules.get('attack_script_args', "").split()
        
        if not script_path:
            print("[오류] 정책 파일에 'attack_script_path'가 정의되지 않았습니다.", file=sys.stderr)
            return

        command = ['python3', script_path] + script_args
        print(f"[Prober] 공격 명령 실행: {' '.join(command)}")
        try:
            self.attack_process = subprocess.Popen(command)
        except Exception as e:
            print(f"[오류] 공격 스크립트 실행 실패: {e}", file=sys.stderr)

    def _stop_attack(self):
        """실행 중인 공격을 중단시킵니다."""
        if self.attack_process and self.attack_process.poll() is None:
            print("\n\033[93m[Prober] MTD 셔플링으로 타겟 상실! 실행 중인 공격을 강제 중단합니다.\033[0m")
            log_bus_event("lpc_attack_stop", {"reason": "mtd_shuffle_interrupt"})
            self.attack_process.terminate()
            try:
                self.attack_process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.attack_process.kill()
        self.attack_process = None

    def run(self):
        sniffer = Thread(target=lambda: sniff(iface=INTERFACE, filter="udp", prn=self._passive_packet_handler, store=0, stop_filter=lambda p: self.stop_event.is_set()), daemon=True)
        sniffer.start()
        
        while not self.stop_event.is_set():
            if self.state == ProberState.PASSIVE_ANALYSIS:
                print(f"\r[Prober] [Phase 1] PASSIVE ANALYSIS (네트워크 감청 및 분석 중...)", end="")
                time.sleep(5); self.state = ProberState.PRIORITIZED_SCAN

            elif self.state == ProberState.PRIORITIZED_SCAN:
                sorted_candidates = sorted(self.candidates.items(), key=lambda item: item[1]['score'], reverse=True)
                found = False
                for target_cand, data in sorted_candidates[:5]:
                    print(f"\r[Prober] [Phase 2] PRIORITIZED SCAN (후보 스캔: {target_cand[0]}:{target_cand[1]})", end="")
                    if self._check_target_alive(target=target_cand):
                        self._update_target_state(target_cand, "actively")
                        found = True; break
                    else: self.candidates[target_cand]['score'] *= 0.5
                    time.sleep(self.scan_interval)
                if not found: self.state = ProberState.PASSIVE_ANALYSIS

            elif self.state == ProberState.TARGET_LOCKED or self.state == ProberState.ATTACK_PHASE:
                phase_str = "[Phase 3] TARGET LOCKED"
                if self.state == ProberState.ATTACK_PHASE:
                    phase_str = "\033[91m[Phase 4] ATTACK IN PROGRESS\033[0m"

                print(f"\r[Prober] {phase_str} ({self.locked_target[0]}:{self.locked_target[1]}) | 연속 성공: {self.successful_hits}/{self.success_threshold}", end="")
                time.sleep(self.interval)
                
                if not self._check_target_alive():
                    print(f"\n[Prober] 타겟 응답 없음 (MTD SHUFFLE 추정)")
                    log_bus_event("prober_target_lost", {"lost_target": f"{self.locked_target[0]}:{self.locked_target[1]}"})
                    self.candidates[self.locked_target]['score'] = 0.1
                    self.locked_target = None
                    self.successful_hits = 0
                    self._stop_attack() # 타겟을 잃었으므로 공격 중단
                    self.state = ProberState.PRIORITIZED_SCAN
            
            time.sleep(0.1)

    def _check_target_alive(self, target: Optional[Tuple[str, int]] = None) -> bool:
        check_target = target or self.locked_target
        if not check_target: return False
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_GRAM) as s:
                s.settimeout(0.2); s.sendto(b'PING', check_target); s.recvfrom(1024)
                return True
        except (socket.timeout, ConnectionRefusedError): return False
        except Exception: return False

def main():
    parser = argparse.ArgumentParser(description="LPC-based Stealthy Prober with Attack Trigger")
    parser.add_argument("--interval", type=float, default=1.5, help="TARGET_LOCKED 확인 주기(초). 시연을 위해 짧게 설정.")
    parser.add_argument("--scan-interval", type=float, default=0.3, help="PRIORITIZED_SCAN 스캔 간격(초)")
    args = parser.parse_args()
    
    # __init__ 호출부 수정 (TypeError 해결)
    prober = LpcStealthyProber(POLICY_FILE_PATH, args.interval, args.scan_interval)
    try:
        prober.run()
    except KeyboardInterrupt:
        print("\n[Prober] 사용자 요청으로 종료합니다.")
        prober._stop_attack()
        prober.stop_event.set()

if __name__ == "__main__":
    main()