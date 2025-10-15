#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import os
import subprocess
import time
import json
import signal
import threading
from typing import List, Dict, Any, Optional, Tuple
import sys
import socket
import re

# --- 경로 설정 ---
LPC_DIR = os.path.dirname(os.path.realpath(__file__))
ATTACKS_DIR = os.path.join(LPC_DIR, 'modules', 'attacks_wiki')
ATTACK_META_DIR = os.path.join(ATTACKS_DIR, 'json')

# ⭐️ MTD 상태 파일의 예상 경로를 추가
SHARED_STATE_DIR_FALLBACK = os.path.join(LPC_DIR, 'mtd', 'shared_state')

# --- PYTHONPATH 자동 설정 (가장 중요) ---
# 스크립트의 현재 위치를 sys.path에 추가하여 'bus' 모듈을 찾을 수 있도록 함
if LPC_DIR not in sys.path:
    sys.path.insert(0, LPC_DIR)

# 'bus/logger.py'가 필요합니다. (실제 환경에 따라 임포트 방식이 다를 수 있음)
try:
    from bus.logger import log_bus_event
except ImportError:
    print("WARNING: Could not import bus.logger. Events will be printed to stdout.", file=sys.stderr)
    def log_bus_event(type: str, data: Dict[str, Any], source_override: str = "orchestrator"):
        record = {"ts": time.time(), "source": source_override, "type": type, "data": data}
        print(json.dumps(record))
        

# --- 전역 변수 ---
attack_process: Optional[subprocess.Popen] = None
attack_lock = threading.RLock()
stop_event = threading.Event()
try:
    # 공격자 IP 주소 획득
    MY_IP_ADDRESS = subprocess.check_output(['hostname', '-I']).decode('utf-8').strip().split()[0]
except Exception:
    MY_IP_ADDRESS = '127.0.0.1'

# ==============================================================================
# 유틸리티 함수
# ==============================================================================
def default_state_file() -> str:
    """MTD 상태 파일의 우선순위 경로를 결정합니다."""
    # 1. 컨테이너 표준 공유 경로
    shared_path = "/shared/mtd_state.json"
    if os.path.exists(shared_path): return shared_path
    
    # 2. ⭐️ 사용자가 지정한 경로 (mtd/shared_state)
    local_shared_path = os.path.join(SHARED_STATE_DIR_FALLBACK, "mtd_state.json")
    if os.path.exists(local_shared_path): return local_shared_path
    
    # 3. 기본 로컬 경로
    return os.path.join("mtd/shared_state/mtd_state.json")

def read_mtd_target(state_file: str) -> Tuple[Optional[str], Optional[int]]:
    """MTD 상태 파일에서 현재 타겟 IP와 Port를 읽습니다."""
    try:
        with open(state_file, "r", encoding="utf-8") as f: state = json.load(f)
        target_str = state.get("current_target")
        if not target_str or ":" not in target_str: return None, None
        ip, port_str = target_str.split(":", 1)
        return ip, int(port_str)
    except Exception as e:
        # print(f"[디버그] MTD 상태 파일 읽기 오류: {e}", file=sys.stderr)
        return None, None

def get_available_attacks() -> List[str]:
    """사용 가능한 공격 스크립트 목록을 가져옵니다."""
    if not os.path.isdir(ATTACKS_DIR): return []
    return sorted([f for f in os.listdir(ATTACKS_DIR) if f.endswith('.sh')])

def get_attack_metadata(attack_name: str) -> Dict[str, Any]:
    """공격 스크립트 이름에서 메타데이터(카테고리, MITRE)를 추론합니다."""
    meta = {"mitre_tactics": [], "attack_category": "unknown"}
    base_name = attack_name.replace('.sh', '')

    if 'spoof' in base_name: meta['attack_category'] = 'spoofing'
    elif 'flood' in base_name or 'dos' in base_name: meta['attack_category'] = 'flooding'
    elif 'discovery' in base_name or 'scan' in base_name or 'sniff' in base_name: meta['attack_category'] = 'discovery'
    elif 'injection' in base_name: meta['attack_category'] = 'injection'
    elif 'eavesdrop' in base_name: meta['attack_category'] = 'eavesdropping'
    elif 'takeover' in base_name or 'brute' in base_name: meta['attack_category'] = 'takeover'
    elif 'extract' in base_name: meta['attack_category'] = 'exfiltration'

    json_path = os.path.join(ATTACK_META_DIR, f"{base_name}_attack_tree.json")
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r') as f: attack_tree = json.load(f)
            tactics = re.findall(r'TA\d{4}', json.dumps(attack_tree))
            meta['mitre_tactics'] = sorted(list(set(tactics)))
        except Exception: pass
    return meta

# ==============================================================================
# 공격 프로세스 관리
# ==============================================================================
def _kill_process_group(proc: subprocess.Popen):
    """프로세스 그룹을 종료합니다 (공격 프로세스의 모든 서브 프로세스 포함)."""
    if proc and proc.poll() is None:
        try:
            pgid = os.getpgid(proc.pid)
            os.killpg(pgid, signal.SIGTERM)
            proc.wait(timeout=2)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except ProcessLookupError: pass
        except Exception as e:
            print(f"[오류] 프로세스 종료 중 오류 발생: {e}", file=sys.stderr)

def cleanup_attack_process(reason: str):
    """현재 공격 프로세스를 정리합니다."""
    global attack_process
    with attack_lock:
        if attack_process:
            log_bus_event("attack_cleanup", {"reason": reason, "pid": attack_process.pid}, source_override="attack_orchestrator")
            _kill_process_group(attack_process)
            attack_process = None

def terminate_attack_process(reason: str):
    """스크립트를 종료하기 위해 공격 프로세스를 정리하고 플래그를 설정합니다."""
    cleanup_attack_process(reason)
    stop_event.set()

def stream_reader(pipe, stream_name: str, attack_name: str):
    """공격 스크립트의 stdout/stderr을 읽어 로그 버스에 기록합니다."""
    try:
        for line in iter(pipe.readline, ''):
            log_bus_event(f"attack_{stream_name}", {"attack": attack_name, "output": line.strip()}, source_override="attack_script")
    finally:
        if pipe: pipe.close()

# ==============================================================================
# 메인 실행 로직
# ==============================================================================
def run_single_attack(attack_to_run: str, state_file: str) -> Optional[subprocess.Popen]:
    """단일 공격 스크립트를 실행하고 로그 스트리밍을 설정합니다."""
    global attack_process
    
    with attack_lock:
        if attack_process and attack_process.poll() is None:
            cleanup_attack_process("new_attack_request")
    
    attack_script_path = os.path.join(ATTACKS_DIR, attack_to_run)
    if not os.path.exists(attack_script_path):
        print(f"⛔ 스크립트를 찾을 수 없습니다: {attack_script_path}")
        return None

    target_ip, target_port = read_mtd_target(state_file)
    target_file_used = state_file
    
    # MTD 타겟 정보를 찾지 못했을 때 디버깅 정보 제공
    if not target_ip or not target_port:
        target_ip, target_port = "127.0.0.1", 14550
        print(f"  [정보] MTD 타겟을 찾을 수 없어 기본 타겟({target_ip}:{target_port})을 사용합니다.")
        print(f"  [디버그] 확인된 MTD 상태 파일: {target_file_used}") # 사용자가 확인해야 할 파일 경로 출력

    print(f"  -> 현재 공격 타겟: {target_ip}:{target_port}")
    
    attack_base_name = attack_to_run.replace('.sh', '')
    attack_meta = get_attack_metadata(attack_to_run)
    
    # ⭐️ 공격 스크립트 실행 환경 변수 설정 (Python 가상 환경 경로 포함)
    process_env = os.environ.copy()
    process_env['TARGET_IP'] = target_ip
    process_env['TARGET_PORT'] = str(target_port)
    process_env['ATTACK_NAME'] = attack_base_name
    
    # 가상 환경 경로를 PATH에 추가하여 .sh 스크립트 내 Python 실행 오류 방지
    v_env_path = os.path.dirname(sys.executable)
    process_env['PATH'] = f"{v_env_path}:{os.environ.get('PATH', '')}"
    process_env['VIRTUAL_ENV_PATH'] = os.path.dirname(v_env_path)


    try:
        print("\n" + "="*23 + " 공격 시작 " + "="*24)
        print(f"  - 공격자 IP      : {MY_IP_ADDRESS}")
        print(f"  - 스크립트       : {attack_to_run}")
        print(f"  - 타        겟   : {target_ip}:{target_port}")
        print(f"  - 공격 카테고리    : {attack_meta['attack_category']}")
        print("="*58)
        
        # 공격 시작 로그 기록
        log_bus_event("attack_started", {
            "attack": attack_to_run,
            "target": f"{target_ip}:{target_port}",
            "source_ip": MY_IP_ADDRESS,
            "attack_category": attack_meta['attack_category'],
            "mitre_tactics": attack_meta['mitre_tactics']
        }, source_override="attack_orchestrator")
        
        proc = subprocess.Popen(
            ['/bin/bash', attack_script_path],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding='utf-8', errors='replace',
            preexec_fn=os.setsid, env=process_env
        )
        with attack_lock: attack_process = proc
            
        threading.Thread(target=stream_reader, args=(proc.stdout, "stdout", attack_to_run), daemon=True).start()
        threading.Thread(target=stream_reader, args=(proc.stderr, "stderr", attack_to_run), daemon=True).start()

    except Exception as e:
        print(f"❌ 공격 실행 중 오류 발생: {e}", file=sys.stderr)
        log_bus_event("attack_exception", {"attack": attack_to_run, "error": str(e)}, source_override="attack_orchestrator")
        with attack_lock: attack_process = None
        return None
    
    return proc

def main():
    signal.signal(signal.SIGINT, lambda s, f: terminate_attack_process("user_interrupt"))
    signal.signal(signal.SIGTERM, lambda s, f: terminate_attack_process("system_terminate"))

    parser = argparse.ArgumentParser(description="DVD 공격 오케스트레이터 v2.3 (Final Path & CTI Fixed)")
    parser.add_argument('-a', '--attack', help="실행할 공격 스크립트(.sh 파일)")
    parser.add_argument('-y', '--yes', action='store_true', help="확인 프롬프트에 자동으로 'yes'로 응답합니다.")
    parser.add_argument('--run-all', action='store_true', help="사용 가능한 모든 공격을 순차적으로 실행합니다.")
    parser.add_argument('--duration', type=int, default=60, help="--run-all 모드에서 각 공격을 실행할 시간(초)")
    
    args = parser.parse_args()
    state_file = default_state_file()
    all_attacks = get_available_attacks()

    if not all_attacks:
        print(f"⛔ 오류: '{ATTACKS_DIR}' 경로에 공격 스크립트(.sh)가 없습니다.")
        sys.exit(1)

    if args.run_all:
        for i, attack_name in enumerate(all_attacks, 1):
            if stop_event.is_set(): break
            
            attack_meta = get_attack_metadata(attack_name) # 메타데이터 미리 가져오기
            
            print(f"\n--- [{i}/{len(all_attacks)}] '{attack_name}' 공격 시작 ---")
            proc = run_single_attack(attack_name, state_file)
            if proc:
                try:
                    proc.wait(timeout=args.duration)
                except subprocess.TimeoutExpired:
                    cleanup_attack_process(f"duration_limit ({args.duration}s)")
                
                return_code = proc.poll() if proc.poll() is not None else -1
                # ⭐️ CTI 일관성 개선: attack_finished 로그에 attack_category 추가
                log_bus_event("attack_finished", {
                    "attack": attack_name, 
                    "return_code": return_code, 
                    "attack_category": attack_meta['attack_category']
                }, source_override="attack_orchestrator")
            else:
                print(f"'{attack_name}' 공격 실행에 실패하여 다음으로 넘어갑니다.")

            if not stop_event.is_set() and i < len(all_attacks):
                time.sleep(5)
        return

    attack_to_run = args.attack or "gps-spoofing.sh" # 기본값 예시
    attack_meta = get_attack_metadata(attack_to_run)

    if not args.yes:
        # 대화형 모드 로직 (필요 시 구현)
        pass

    try:
        proc = run_single_attack(attack_to_run, state_file)
        if proc:
            proc.wait()
            # ⭐️ CTI 일관성 개선: attack_finished 로그에 attack_category 추가
            log_bus_event("attack_finished", {
                "attack": attack_to_run,
                "attack_category": attack_meta['attack_category']
            }, source_override="attack_orchestrator")
    finally:
        terminate_attack_process("interactive_mode_finished")


if __name__ == "__main__":
    main()
