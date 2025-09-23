#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import yaml
import random
import socket
import subprocess

# --- 경로 설정 ---
LPC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if LPC_DIR not in sys.path:
    sys.path.insert(0, LPC_DIR)

from bus.logger import log_bus_event

class Seeker:
    def __init__(self, policy_path):
        self.policy = self._load_policy(policy_path)
        
        # LPC 규칙 및 공격 표면 정보
        self.lpc_rules = self.policy.get('lpc_rules', {})
        self.success_threshold = self.lpc_rules.get('attack_success_threshold', 3)
        self.attack_script = os.path.join(LPC_DIR, 'attack_orchestrator.py') # attack_orchestrator.py 경로 수정
        
        self.ip_pool = self.policy.get('decoy_pool', [])
        self.port_pool = self.policy.get('port_pool', [])
        self.real_target_ip = self.policy.get('real_target_ip')

        self.recon_success_count = 0
        self.last_found_target = None
        
        print("✅ Seeker (Intelligent Attacker) 초기화 완료")

    def _load_policy(self, path):
        print(f"[*] Seeker 정책 로드 중... (from {path})")
        with open(path, 'r') as f:
            return yaml.safe_load(f)

    def scan_target(self, ip, port):
        """단일 IP/Port에 대한 스캔(연결 시도)을 수행합니다."""
        try:
            # 실제 드론은 UDP를 사용하지만, 간단한 TCP 연결 시도로도 탐색을 시뮬레이션 가능
            # 실제 드론인지 확인하는 더 정교한 방법이 필요할 수 있음 (예: 특정 응답 확인)
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.2)
            result = sock.connect_ex((ip, port))
            sock.close()
            # companion-computer-lite (10.13.0.3)는 특정 포트가 열려있지 않으므로,
            # 실제 타겟 IP를 맞추는 것 자체를 성공으로 간주하는 로직으로 변경.
            # 이 부분은 실제 드론의 네트워크 특성에 맞게 수정해야 함.
            if ip == self.real_target_ip:
                return True
            return False
        except socket.error:
            return False

    def seek_and_destroy(self):
        """전체 공격 표면을 스캔하고, 임계치 도달 시 공격을 실행합니다."""
        search_space = [(ip, port) for ip in self.ip_pool for port in self.port_pool]
        random.shuffle(search_space)
        
        print("\n--- Seeker: 새로운 정찰 사이클 시작 ---")
        found = False
        for ip, port in search_space:
            print(f"[*] 정찰 시도 -> {ip}:{port}", end='\r')
            if self.scan_target(ip, port):
                found_target = f"{ip}:{port}"
                print(f"\n🎯 [Seeker] 실제 타겟으로 추정되는 위치 발견: {found_target}")
                log_bus_event('recon_found_target', {'target': found_target, 'seeker_ip': '10.13.0.204'})
                
                # 동일한 타겟을 연속으로 찾은 경우 카운트하지 않음
                if found_target != self.last_found_target:
                    self.recon_success_count += 1
                    self.last_found_target = found_target
                
                print(f"    - 정찰 성공 횟수: {self.recon_success_count} / {self.success_threshold}")
                found = True
                break # 타겟을 찾으면 이번 사이클은 종료
        
        if not found:
            print("\n[Seeker] 이번 정찰 사이클에서 타겟을 찾지 못함.")
            log_bus_event('recon_failed', {'seeker_ip': '10.13.0.204'})

        # 임계치 도달 시 공격 감행
        if self.recon_success_count >= self.success_threshold:
            print("\n" + "="*60)
            print(f"🔥 [Seeker] 공격 임계치 도달! '{self.last_found_target}'에 대해 실제 공격을 시작합니다.")
            print("="*60)
            log_bus_event('lpc_threshold_reached', {'threshold': self.success_threshold})
            
            try:
                # --run-all과 --duration을 사용하여 모든 공격을 30초씩 실행
                subprocess.Popen(
                    ['python3', self.attack_script, '--run-all', '--duration', '30', '-y'],
                    cwd=LPC_DIR
                )
            except Exception as e:
                print(f"❌ 공격 오케스트레이터 실행 실패: {e}")
            
            # 공격 실행 후 카운트 초기화
            self.recon_success_count = 0
            # 공격 후 잠시 대기
            time.sleep(120) 
            
    def start(self):
        print("🚀 Seeker 시작...")
        while True:
            self.seek_and_destroy()
            # 정찰 사이클 간 대기
            time.sleep(random.randint(5, 15))


if __name__ == "__main__":
    policy_path = os.path.join(LPC_DIR, 'configs', 'mtd_policy.yaml')
    seeker = Seeker(policy_path)
    try:
        seeker.start()
    except KeyboardInterrupt:
        print("\n🛑 Seeker 종료.")