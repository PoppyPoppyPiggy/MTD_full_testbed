#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MTD Seeker (Test Script)
- MTD 시스템이 실제로 iptables 규칙을 변경하는지 nmap을 통해 외부에서 검증합니다.
- 'rl_driven_deception_manager.py'와 별개의 터미널에서 실행해야 합니다.
- (참고: 이 스크립트가 nmap을 사용하므로 sudo 권한이 필요할 수 있습니다.)
"""

import subprocess
import time
import argparse
import yaml
import sys
import os

def load_mtd_config(config_path):
    """MTD 설정 파일에서 public_host_ip와 public_port를 로드합니다."""
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
            host = config.get('public_host_ip', '127.0.0.1')
            port = config.get('public_port', 14550)
            return host, port
    except FileNotFoundError:
        print(f"오류: MTD 설정 파일을 찾을 수 없습니다: {config_path}")
        print("rl_driven_deception_manager.py와 동일한 --config 인자를 사용하세요.")
        sys.exit(1)
    except Exception as e:
        print(f"설정 파일 로드 중 오류 발생: {e}")
        sys.exit(1)

def check_nmap_installed():
    """nmap이 설치되어 있는지 확인합니다."""
    try:
        subprocess.run(['nmap', '-V'], check=True, capture_output=True)
        print("[Seeker] nmap이 설치되어 있습니다.")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("[Seeker] 오류: 'nmap'이 설치되어 있지 않습니다.")
        print("          테스트를 위해 nmap을 설치해주세요. (예: sudo apt install nmap)")
        sys.exit(1)

def run_nmap_scan(host, port):
    """지정된 호스트와 UDP 포트에 대해 nmap 스캔을 실행합니다."""
    command = ['nmap', '-sU', '-p', str(port), host]
    print(f"\n[Seeker] 스캔 실행: {' '.join(command)}")
    
    try:
        # nmap은 루트 권한이 필요할 수 있습니다. 
        # 사용자가 sudo로 실행하지 않았다면 'sudo'를 앞에 추가하는 것을 고려할 수 있습니다.
        if os.geteuid() != 0:
            print("[Seeker] 경고: nmap은 sudo 권한으로 실행할 때 더 정확합니다.")
            print("          (예: sudo python3 mtd/seeker.py)")
            
        result = subprocess.run(command, check=True, capture_output=True, text=True, timeout=30)
        
        output = result.stdout
        
        # nmap 출력에서 포트 상태 파싱
        for line in output.split('\n'):
            if f"{port}/udp" in line:
                state = line.split()[1] # 예: 'open', 'open|filtered', 'filtered', 'closed'
                print(f"[Seeker] 스캔 결과: 포트 {port}/udp 상태는 [ {state} ] 입니다.")
                
                if state == "open":
                    print("          -> MTD가 트래픽을 Real/Decoy 서버로 DNAT하고 있습니다.")
                elif "filtered" in state:
                    print("          -> MTD가 'Block' (DROP) 액션을 실행 중이거나 방화벽에 막혔습니다.")
                elif "closed" in state:
                    print("          -> 포트가 닫혀있습니다. (서비스가 실행 중이지 않음)")
                return

    except subprocess.CalledProcessError as e:
        print(f"[Seeker] nmap 실행 중 오류 발생:\n{e.stderr}")
    except subprocess.TimeoutExpired:
        print("[Seeker] nmap 스캔 시간 초과. (네트워크 문제 또는 방화벽)")
    except Exception as e:
        print(f"[Seeker] 스캔 중 예외 발생: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MTD Seeker (nmap Test Tool)")
    parser.add_argument("--config", type=str, 
                        default="mtd/configs/iptables_mtd.yaml",
                        help="MTD 설정 파일 경로 (public_host_ip와 public_port를 읽기 위함)")
    parser.add_argument("--interval", type=int, default=15,
                        help="nmap 스캔 주기 (초)")
    args = parser.parse_args()

    # nmap 설치 확인
    check_nmap_installed()

    # 설정 파일에서 스캔 대상(호스트, 포트) 로드
    target_host, target_port = load_mtd_config(args.config)
    
    print(f"[Seeker] MTD 테스트 시작... (대상: {target_host}:{target_port})")
    print(f"[Seeker] {args.interval}초마다 nmap UDP 스캔을 실행합니다. (중지: Ctrl+C)")
    
    try:
        while True:
            run_nmap_scan(target_host, target_port)
            print(f"[Seeker] 다음 스캔까지 {args.interval}초 대기...")
            time.sleep(args.interval)
            
    except KeyboardInterrupt:
        print("\n[Seeker] 테스트 중지됨.")