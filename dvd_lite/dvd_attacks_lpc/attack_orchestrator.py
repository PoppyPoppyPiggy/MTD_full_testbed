#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import os
import subprocess
import time
import json
import signal
import threading
import datetime
from typing import List, Dict, Any, Optional, Tuple
import sys
import socket

# --- 경로 설정 ---
# attack_orchestrator.py의 위치를 기준으로 프로젝트 루트를 정확히 찾습니다.
LPC_DIR = os.path.dirname(os.path.realpath(__file__))
ATTACKS_DIR = os.path.join(LPC_DIR, 'modules', 'attacks_wiki')
BUS_LOG_PATH = os.path.join(LPC_DIR, 'bus', 'bus.log')

# --- PYTHONPATH 자동 설정 ---
if LPC_DIR not in sys.path:
    sys.path.insert(0, LPC_DIR)

# --- bus 모듈 import ---
from bus.logger import log_bus_event

# --- 전역 변수 ---
attack_process: Optional[subprocess.Popen] = None
attack_lock = threading.RLock()
stop_event = threading.Event()
try:
    MY_IP_ADDRESS = socket.gethostbyname(socket.gethostname())
except socket.gaierror:
    MY_IP_ADDRESS = subprocess.check_output(['hostname', '-I']).decode('utf-8').strip()

# ==============================================================================
# 섹션 1: 유틸리티 함수
# ==============================================================================
def default_state_file() -> str:
    """컨테이너 환경을 우선으로 mtd_state.json 파일의 경로를 찾습니다."""
    shared_path = "/shared/mtd_state.json"
    if os.path.exists(shared_path):
        return shared_path
    return os.path.join(LPC_DIR, "mtd", "shared_state", "mtd_state.json")

def read_mtd_target(state_file: str) -> Tuple[Optional[str], Optional[int]]:
    """mtd_state.json 파일에서 현재 MTD 타겟을 읽어옵니다."""
    try:
        with open(state_file, "r", encoding="utf-8") as f:
            state = json.load(f)
        target_str = state.get("current_target")
        if not target_str or ":" not in target_str: return None, None
        ip, port_str = target_str.split(":", 1)
        return ip, int(port_str)
    except (FileNotFoundError, json.JSONDecodeError, ValueError):
        print(f"[경고] MTD 상태 파일 '{state_file}' 읽기 실패.", file=sys.stderr)
        return None, None

def get_available_attacks() -> List[str]:
    """실행 가능한 공격 스크립트 목록을 가져옵니다."""
    if not os.path.isdir(ATTACKS_DIR): return []
    return sorted([f for f in os.listdir(ATTACKS_DIR) if f.endswith('.sh')])

def choose_attack_interactively(attacks: List[str]) -> Optional[str]:
    """사용자에게 공격 선택 메뉴를 보여줍니다."""
    if not attacks:
        print("⛔ 실행 가능한 공격 스크립트가 없습니다.")
        return None
    print("\n" + "="*20 + " 공격 선택 메뉴 " + "="*20)
    for i, name in enumerate(attacks, 1):
        print(f"  [{i:2d}] {name}")
    print("="*58)
    while True:
        try:
            sel = input("실행할 공격의 번호를 입력하세요 (q=취소): ").strip().lower()
            if sel in ("q", "quit"): return None
            idx = int(sel)
            if 1 <= idx <= len(attacks): return attacks[idx - 1]
            else: print("잘못된 번호입니다.")
        except ValueError:
            print("숫자 또는 'q'를 입력해주세요.")

# ==============================================================================
# 섹션 2: 공격 프로세스 관리
# ==============================================================================
def terminate_attack_process(reason: str):
    """실행 중인 공격 프로세스를 안전하게 종료합니다."""
    global attack_process
    with attack_lock:
        if attack_process and attack_process.poll() is None:
            print(f"\n[알림] 공격 프로세스를 종료합니다 (사유: {reason})...")
            log_bus_event("attack_terminating", {"reason": reason, "pid": attack_process.pid, "source_ip": MY_IP_ADDRESS})
            try:
                os.killpg(os.getpgid(attack_process.pid), signal.SIGTERM)
                attack_process.wait(timeout=2)
            except (ProcessLookupError, subprocess.TimeoutExpired):
                try: os.killpg(os.getpgid(attack_process.pid), signal.SIGKILL)
                except ProcessLookupError: pass
            except Exception as e:
                print(f"[오류] 프로세스 종료 중 오류 발생: {e}", file=sys.stderr)
            attack_process = None
    stop_event.set()

def stream_reader(pipe, stream_name: str, attack_name: str):
    """공격 스크립트의 출력을 실시간으로 읽어 bus.log에 기록합니다."""
    try:
        for line in iter(pipe.readline, ''):
            log_bus_event(f"attack_{stream_name}", {"attack": attack_name, "output": line.strip(), "source_ip": MY_IP_ADDRESS})
    finally:
        if pipe: pipe.close()

# ==============================================================================
# 섹션 3: 메인 실행 로직
# ==============================================================================
def main():
    signal.signal(signal.SIGINT, lambda s, f: terminate_attack_process("user_interrupt"))
    signal.signal(signal.SIGTERM, lambda s, f: terminate_attack_process("system_terminate"))

    parser = argparse.ArgumentParser(description="공격 오케스트레이터")
    parser.add_argument('-a', '--attack', help="실행할 공격 스크립트(.sh 파일)")
    parser.add_argument('-y', '--yes', action='store_true', help="확인 프롬프트에 자동으로 'yes'로 응답합니다.")
    args = parser.parse_args()

    attack_to_run = args.attack or choose_attack_interactively(get_available_attacks())
    if not attack_to_run:
        print("[알림] 공격 실행이 취소되었습니다."); return

    attack_script_path = os.path.join(ATTACKS_DIR, attack_to_run)
    if not os.path.exists(attack_script_path):
        print(f"⛔ 스크립트를 찾을 수 없습니다: {attack_script_path}"); return

    state_file = default_state_file()
    print(f"\n[준비] 현재 MTD 타겟을 확인합니다 (from {state_file})...")
    target_ip, target_port = read_mtd_target(state_file)
    if not target_ip or not target_port:
        print("⛔ MTD 상태 파일에서 유효한 타겟을 읽어올 수 없습니다."); return
    
    print(f"  -> 현재 공격 타겟: {target_ip}:{target_port}")
    
    process_env = os.environ.copy()
    process_env['TARGET_IP'] = target_ip
    process_env['TARGET_PORT'] = str(target_port)

    if not args.yes:
        confirm = input(f"\n'{attack_to_run}' 공격을 타겟({target_ip}:{target_port})에 대해 시작하시겠습니까? (y/n): ").lower()
        if confirm not in ['y', 'yes']:
            print("[알림] 공격 실행이 취소되었습니다."); return

    global attack_process
    try:
        print("\n" + "="*23 + " 공격 시작 " + "="*24)
        print(f"  - 공격자 IP   : {MY_IP_ADDRESS}")
        print(f"  - 스크립트    : {attack_to_run}")
        print(f"  - 타    겟    : {target_ip}:{target_port}")
        print("="*58)
        
        log_bus_event("attack_started", {"attack": attack_to_run, "target": f"{target_ip}:{target_port}", "source_ip": MY_IP_ADDRESS})
        
        proc = subprocess.Popen(
            ['/bin/bash', attack_script_path],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding='utf-8', errors='replace',
            preexec_fn=os.setsid, env=process_env
        )
        with attack_lock: attack_process = proc
            
        threading.Thread(target=stream_reader, args=(proc.stdout, "stdout", attack_to_run), daemon=True).start()
        threading.Thread(target=stream_reader, args=(proc.stderr, "stderr", attack_to_run), daemon=True).start()

        return_code = proc.wait()
        
        print("\n" + "="*23 + " 공격 종료 " + "="*24)
        print(f"  - 종료 코드: {return_code}")
        print("="*58)
        
        log_bus_event("attack_finished", {"attack": attack_to_run, "return_code": return_code, "source_ip": MY_IP_ADDRESS})

    except Exception as e:
        print(f"❌ 공격 실행 중 오류 발생: {e}", file=sys.stderr)
        log_bus_event("attack_exception", {"attack": attack_to_run, "error": str(e), "source_ip": MY_IP_ADDRESS})
    finally:
        terminate_attack_process("finalize")

if __name__ == "__main__":
    main()