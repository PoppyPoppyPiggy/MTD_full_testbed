#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 파일명: run_monitors.py
# 설명: 여러 모니터 스크립트를 병렬로 실행하고 관리합니다. (PYTHONPATH 설정 추가)

import subprocess
import signal
import sys
import time
import os
import threading # threading 임포트 추가
from typing import List, Dict, Optional

# --- 설정 ---
MONITOR_SCRIPTS = [
    "dvd_telemetry_monitor.py",
    "network_traffic_monitor.py",
    "qos_monitor.py",
    "system_event_monitor.py",
    "dvd_container_monitor.py",
]

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
MONITORS_DIR = os.path.join(SCRIPT_DIR, 'monitors')

# --- 전역 변수 ---
processes: Dict[str, Optional[subprocess.Popen]] = {}

# --- 함수 정의 ---
def start_monitor(script_name: str) -> Optional[subprocess.Popen]:
    """지정된 모니터 스크립트를 백그라운드 프로세스로 실행합니다."""
    script_path = os.path.join(MONITORS_DIR, script_name)
    if not os.path.exists(script_path):
        print(f"❌ 오류: 모니터 스크립트를 찾을 수 없습니다: {script_path}", file=sys.stderr)
        return None

    try:
        print(f"[*] 모니터 시작 중: {script_name}...")

        # ⭐️ [수정] 자식 프로세스를 위한 환경 변수 설정
        env = os.environ.copy()
        # SCRIPT_DIR (dvd_attacks_lpc)을 PYTHONPATH의 맨 앞에 추가
        # 이렇게 하면 'from utils import ...' 나 'from mtd import ...' 가 가능해짐
        env['PYTHONPATH'] = f"{SCRIPT_DIR}{os.pathsep}{env.get('PYTHONPATH', '')}"

        proc = subprocess.Popen(
            [sys.executable, script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            errors='replace',
            preexec_fn=os.setsid,
            env=env # ⭐️ 수정된 환경 변수 전달
        )
        print(f"✅ '{script_name}' 시작됨 (PID: {proc.pid})")

        threading.Thread(target=stream_output, args=(proc.stdout, script_name, "stdout"), daemon=True).start()
        threading.Thread(target=stream_output, args=(proc.stderr, script_name, "stderr"), daemon=True).start()

        return proc
    except Exception as e:
        print(f"❌ '{script_name}' 시작 실패: {e}", file=sys.stderr)
        return None

def stream_output(pipe, script_name, stream_name):
    """자식 프로세스의 출력을 읽어 콘솔에 표시합니다."""
    try:
        for line in iter(pipe.readline, ''):
             print(f"[{script_name}:{stream_name}] {line.strip()}", flush=True)
    except ValueError: # Pipe closed
        pass
    except Exception as e:
         print(f"❌ 스트림 읽기 오류 ({script_name}:{stream_name}): {e}", file=sys.stderr)
    finally:
        if pipe:
            try: pipe.close()
            except Exception: pass


def terminate_all_monitors(reason: str):
    """실행 중인 모든 모니터 프로세스를 종료합니다."""
    print(f"\n[관리자] 모든 모니터 종료 시작 (사유: {reason})...")
    
    procs_to_terminate = list(processes.items()) 
    
    for script_name, proc in procs_to_terminate:
        if proc and proc.poll() is None:
            print(f"   - '{script_name}' (PID: {proc.pid}) 종료 중...")
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            except ProcessLookupError:
                print(f"     - 경고: 프로세스(PID: {proc.pid})가 이미 종료되었습니다.")
            except Exception as e:
                print(f"     - ❌ 오류: SIGTERM 전송 실패 (PID: {proc.pid}): {e}", file=sys.stderr)
                try:
                     os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                     print(f"     - SIGKILL 전송됨 (PID: {proc.pid})")
                except Exception as kill_err:
                     print(f"     - ❌ 오류: SIGKILL 전송 실패 (PID: {proc.pid}): {kill_err}", file=sys.stderr)

    time.sleep(1)

    all_terminated = True
    for script_name, proc in processes.items():
         if proc and proc.poll() is None:
              print(f"   - ⚠️ 경고: '{script_name}' (PID: {proc.pid})가 아직 종료되지 않았습니다.")
              all_terminated = False
              try: os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
              except Exception: pass

    if all_terminated:
        print("✅ 모든 모니터가 성공적으로 종료되었습니다.")
    else:
        print("⚠️ 일부 모니터가 정상적으로 종료되지 않았을 수 있습니다.")

    processes.clear()


def signal_handler(signum, frame):
    """종료 신호(SIGINT, SIGTERM)를 처리합니다."""
    # ⭐️ 중복 실행 방지
    if not hasattr(signal_handler, "terminating"):
        signal_handler.terminating = True # 종료 중 플래그 설정
        sig_name = signal.Signals(signum).name
        terminate_all_monitors(f"signal_{sig_name}_received")
        sys.exit(0)
    else:
        print("[관리자] 이미 종료 절차가 진행 중입니다.")

signal_handler.terminating = False # 플래그 초기화


# --- 메인 실행 로직 ---
if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    print("--- 다중 모니터 실행 관리자 시작 ---")
    print(f"[*] 프로젝트 루트 (PYTHONPATH에 추가됨): {SCRIPT_DIR}")
    print(f"[*] 모니터 디렉토리: {MONITORS_DIR}")

    # 각 모니터 스크립트 실행
    for script in MONITOR_SCRIPTS:
        proc = start_monitor(script)
        if proc:
            processes[script] = proc
        else:
            print(f"❌ '{script}' 시작 실패. 전체 모니터 실행을 중단합니다.")
            terminate_all_monitors("monitor_start_failure")
            sys.exit(1)

    print("\n[*] 모든 모니터가 백그라운드에서 실행 중입니다.")
    print("[*] Ctrl+C 를 눌러 모든 모니터를 종료합니다.")

    try:
        while True:
            all_running = True
            procs_to_remove = [] # 종료된 프로세스 이름 저장
            for name, p in processes.items():
                 if p is None: # 이미 제거된 경우
                      all_running = False
                      procs_to_remove.append(name) # 제거 목록에 추가
                      continue

                 poll_result = p.poll()
                 if poll_result is not None: # 프로세스가 종료됨
                      print(f"\n⚠️ 경고: 모니터 '{name}' (PID: {p.pid})가 예기치 않게 종료되었습니다 (Return Code: {poll_result}).")
                      # 자동 재시작 로직 필요 시 여기에 추가
                      # 예: proc = start_monitor(name); processes[name] = proc
                      procs_to_remove.append(name) # 제거 목록에 추가
                      all_running = False
            
            # 종료된 프로세스를 딕셔너리에서 제거
            if procs_to_remove:
                 for name in procs_to_remove:
                     # 딕셔너리에서 제거하기 전에 None으로 설정하는 것이 더 안전할 수 있음
                     # processes[name] = None 
                     if name in processes: # 방어 코드
                         del processes[name] 

            if not processes: # 관리할 프로세스가 없으면
                 print("[관리자] 모든 모니터 프로세스가 종료되었습니다. 관리자를 종료합니다.")
                 break

            time.sleep(5)

    except KeyboardInterrupt:
        print("\n[관리자] KeyboardInterrupt 감지. 종료 절차는 signal_handler에서 처리됩니다.")
    except Exception as e:
        print(f"\n❌ [관리자] 메인 루프에서 예기치 않은 오류 발생: {e}", file=sys.stderr)
        terminate_all_monitors("main_loop_exception")
    finally:
        if processes:
             terminate_all_monitors("final_cleanup")

    print("--- 다중 모니터 실행 관리자 종료 ---")

