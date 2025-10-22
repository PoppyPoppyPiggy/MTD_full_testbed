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
ATTACK_META_DIR = os.path.join(ATTACKS_DIR, 'json') # MITRE 정보용 JSON 경로
# ⭐️ MTD 상태 파일 위치 명확화 (컨테이너 내부 경로 우선)
SHARED_STATE_CONTAINER_PATH = "/shared/mtd_state.json"
SHARED_STATE_HOST_FALLBACK = os.path.join(LPC_DIR, 'mtd', 'shared_state', 'mtd_state.json')

# --- PYTHONPATH 자동 설정 ---
if LPC_DIR not in sys.path:
    sys.path.insert(0, LPC_DIR)

# --- 로거 설정 ---
# bus.logger 임포트 시도 및 실패 시 stdout 로깅
# ⭐️ log_bus_event가 bus.log 파일에 기록한다고 가정
try:
    from bus.logger import log_bus_event
    print("[Attack Orchestrator] bus.logger 로드 성공. 이벤트는 bus.log에 기록됩니다.")
except ImportError:
    print("WARNING: bus.logger를 임포트할 수 없습니다. 이벤트는 stdout으로 출력됩니다.", file=sys.stderr)
    # Fallback 로거 정의
    def log_bus_event(type: str, data: Dict[str, Any], source_override: str = "orchestrator"):
        record = {"ts": time.time(), "source": source_override, "type": type, "data": data}
        # 표준 출력으로 JSON 로그 출력
        print(json.dumps(record))

# --- 전역 변수 ---
attack_process: Optional[subprocess.Popen] = None
attack_lock = threading.RLock() # 재진입 가능한 락 사용
stop_event = threading.Event()
try:
    # 컨테이너의 IP 주소 자동 감지 시도
    MY_IP_ADDRESS = subprocess.check_output(['hostname', '-I']).decode('utf-8').strip().split()[0]
except Exception:
    # 실패 시 docker-compose에 정의된 고정 IP 사용
    MY_IP_ADDRESS = '10.13.0.200'

# ==============================================================================
# 유틸리티 함수
# ==============================================================================
def get_mtd_state_file_path() -> str:
    """MTD 상태 파일의 실제 경로를 결정합니다."""
    if os.path.exists(SHARED_STATE_CONTAINER_PATH):
        return SHARED_STATE_CONTAINER_PATH
    elif os.path.exists(SHARED_STATE_HOST_FALLBACK):
        print(f"[정보] 컨테이너 경로({SHARED_STATE_CONTAINER_PATH}) 없음. 호스트 경로({SHARED_STATE_HOST_FALLBACK}) 사용.")
        return SHARED_STATE_HOST_FALLBACK
    else:
        # 두 경로 모두 없으면 기본값 반환 (오류 발생 가능성 있음)
        print(f"[경고] MTD 상태 파일을 찾을 수 없음: {SHARED_STATE_CONTAINER_PATH} 또는 {SHARED_STATE_HOST_FALLBACK}", file=sys.stderr)
        return SHARED_STATE_HOST_FALLBACK # 일단 기본 경로 반환

def read_mtd_target(state_file: str) -> Tuple[Optional[str], Optional[int]]:
    """MTD 상태 파일에서 현재 타겟 IP와 Port를 읽습니다."""
    try:
        with open(state_file, "r", encoding="utf-8") as f:
            state = json.load(f)
        target_str = state.get("current_target")
        if not target_str or ":" not in target_str:
            print(f"[경고] MTD 상태 파일({state_file})에 유효한 'current_target' 없음.", file=sys.stderr)
            return None, None
        ip, port_str = target_str.split(":", 1)
        return ip, int(port_str)
    except FileNotFoundError:
        print(f"[경고] MTD 상태 파일({state_file})을 찾을 수 없음.", file=sys.stderr)
        return None, None
    except (json.JSONDecodeError, ValueError, Exception) as e:
        print(f"[경고] MTD 상태 파일({state_file}) 읽기/파싱 오류: {e}", file=sys.stderr)
        return None, None

def get_available_attacks() -> List[str]:
    """사용 가능한 공격 스크립트(.sh) 목록을 가져옵니다."""
    if not os.path.isdir(ATTACKS_DIR):
        print(f"⛔ 오류: 공격 스크립트 디렉토리 '{ATTACKS_DIR}'를 찾을 수 없습니다.", file=sys.stderr)
        return []
    try:
        attacks = sorted([f for f in os.listdir(ATTACKS_DIR) if f.endswith('.sh') and os.path.isfile(os.path.join(ATTACKS_DIR, f))])
        if not attacks:
             print(f"⛔ 오류: '{ATTACKS_DIR}' 디렉토리에 실행 가능한 .sh 공격 스크립트가 없습니다.", file=sys.stderr)
        return attacks
    except OSError as e:
        print(f"⛔ 오류: 공격 스크립트 디렉토리 '{ATTACKS_DIR}' 접근 중 오류 발생: {e}", file=sys.stderr)
        return []


def get_attack_metadata(attack_name: str) -> Dict[str, Any]:
    """
    공격 스크립트 이름에서 메타데이터(카테고리=스크립트명, MITRE)를 추론합니다.
    """
    base_name = attack_name.replace('.sh', '')
    meta = {
        "mitre_tactics": [],
        "attack_category": base_name # ⭐️ ML 레이블로 사용할 고유 카테고리
    }

    # MITRE 정보는 부가적으로 JSON 파일에서 읽어옴
    json_path = os.path.join(ATTACK_META_DIR, f"{base_name}_attack_tree.json")
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                attack_tree = json.load(f)
            # JSON 내용 전체에서 'TAxxxx' 형식의 문자열 추출
            tactics = re.findall(r'TA\d{4}', json.dumps(attack_tree))
            meta['mitre_tactics'] = sorted(list(set(tactics))) # 중복 제거 및 정렬
        except Exception as e:
            # print(f"[디버그] MITRE 메타데이터 파일({json_path}) 로드/파싱 오류: {e}", file=sys.stderr)
            pass # 메타데이터 없어도 치명적 오류 아님

    return meta

# ==============================================================================
# 공격 프로세스 관리 (안정성 강화)
# ==============================================================================
def _kill_process_group(proc: subprocess.Popen):
    """프로세스 그룹을 안전하게 종료합니다 (SIGTERM -> SIGKILL)."""
    if proc and proc.poll() is None: # 프로세스가 실행 중일 때만
        pgid = 0
        try:
            pgid = os.getpgid(proc.pid)
            print(f"[프로세스 관리] 프로세스 그룹(PGID:{pgid}, PID:{proc.pid})에 SIGTERM 전송...")
            os.killpg(pgid, signal.SIGTERM)
            proc.wait(timeout=3) # 3초간 종료 대기
            print(f"[프로세스 관리] 프로세스 그룹(PGID:{pgid}) 정상 종료됨 (Return Code: {proc.returncode}).")
        except ProcessLookupError:
            print(f"[프로세스 관리] 경고: 프로세스(PID:{proc.pid})가 이미 종료되었습니다.")
        except subprocess.TimeoutExpired:
            print(f"[프로세스 관리] 경고: SIGTERM 후에도 프로세스 그룹(PGID:{pgid})이 종료되지 않음. SIGKILL 전송...")
            try:
                os.killpg(pgid, signal.SIGKILL)
                proc.wait(timeout=1) # SIGKILL 후 짧게 대기
                print(f"[프로세스 관리] 프로세스 그룹(PGID:{pgid}) 강제 종료됨.")
            except ProcessLookupError:
                print(f"[프로세스 관리] 경고: SIGKILL 시점에 프로세스(PID:{proc.pid})가 이미 종료되었습니다.")
            except Exception as kill_err:
                 print(f"❌ [프로세스 관리] SIGKILL 전송 중 오류 발생 (PGID:{pgid}): {kill_err}", file=sys.stderr)
        except Exception as e:
            print(f"❌ [프로세스 관리] 프로세스 그룹 종료 중 예외 발생 (PID:{proc.pid}): {e}", file=sys.stderr)

def cleanup_attack_process(reason: str):
    """현재 실행 중인 공격 프로세스를 정리합니다."""
    global attack_process
    # 락을 사용하여 동시에 cleanup이 호출되는 것 방지
    with attack_lock:
        proc_to_clean = attack_process
        if proc_to_clean:
            # attack_process를 먼저 None으로 설정하여 중복 cleanup 방지
            attack_process = None
            print(f"[정리] 공격 프로세스 정리 시작 (사유: {reason}, PID: {proc_to_clean.pid})")
            log_bus_event("attack_cleanup", {"reason": reason, "pid": proc_to_clean.pid}, source_override="attack_orchestrator")
            _kill_process_group(proc_to_clean)
            print(f"[정리] 공격 프로세스(PID: {proc_to_clean.pid}) 정리 완료.")


def terminate_orchestrator(reason: str):
    """오케스트레이터 자체를 종료하기 위해 정리 작업을 수행합니다."""
    print(f"\n[종료] 오케스트레이터 종료 시작 (사유: {reason})")
    if not stop_event.is_set(): # 중복 실행 방지
        stop_event.set() # 다른 스레드/루프 종료 플래그 설정
        cleanup_attack_process(f"orchestrator_shutdown_{reason}")
        print("[종료] 오케스트레이터 종료 완료.")
        # sys.exit(0) # 필요 시 여기서 스크립트 강제 종료 가능


def stream_reader(pipe, stream_name: str, attack_name: str):
    """공격 스크립트의 stdout/stderr 스트림을 읽어 로그 버스에 기록합니다."""
    if not pipe: return
    try:
        # iter(pipe.readline, '') 방식은 pipe가 닫힐 때까지 블록될 수 있음
        # 비동기 방식이나 select 사용이 더 좋지만, 여기서는 간단하게 유지
        for line in iter(pipe.readline, ''):
            if stop_event.is_set(): # 종료 플래그 확인
                 break
            line_stripped = line.strip()
            if line_stripped: # 빈 줄은 로깅하지 않음
                 log_bus_event(f"attack_{stream_name}", {"attack": attack_name, "output": line_stripped}, source_override="attack_script")
                 # print(f"[{attack_name}:{stream_name}] {line_stripped}") # 디버깅용 콘솔 출력
    except ValueError:
         # 파일 디스크립터가 이미 닫힌 경우 등 발생 가능
         print(f"[스트림 리더] 경고: '{attack_name}'의 {stream_name} 스트림 읽기 중 오류 발생 (파이프 닫힘?).", file=sys.stderr)
    except Exception as e:
         print(f"❌ [스트림 리더] 예외 발생 ({attack_name}:{stream_name}): {e}", file=sys.stderr)
    finally:
        if pipe:
            try:
                pipe.close()
            except Exception:
                pass # 이미 닫혔을 수 있음

# ==============================================================================
# 메인 실행 로직
# ==============================================================================
def run_single_attack(attack_to_run: str, state_file: str) -> Optional[subprocess.Popen]:
    """단일 공격 스크립트를 실행하고 로그 스트리밍 스레드를 시작합니다."""
    global attack_process

    # 이전 공격이 여전히 실행 중이면 정리
    with attack_lock:
        if attack_process and attack_process.poll() is None:
            cleanup_attack_process("new_attack_request")

    attack_script_path = os.path.join(ATTACKS_DIR, attack_to_run)
    if not (os.path.exists(attack_script_path) and os.access(attack_script_path, os.X_OK)):
        print(f"⛔ 스크립트를 찾을 수 없거나 실행 권한이 없습니다: {attack_script_path}", file=sys.stderr)
        log_bus_event("attack_exception", {"attack": attack_to_run, "error": "Script not found or not executable"}, source_override="attack_orchestrator")
        return None

    target_ip, target_port = read_mtd_target(state_file)
    target_file_used = state_file # 디버깅용으로 어떤 파일 사용했는지 기록

    # MTD 타겟 정보 없으면 기본값(Companion Computer) 사용
    if not target_ip or not target_port:
        target_ip, target_port = "10.13.0.3", 14550
        print(f"  [정보] MTD 타겟 정보를 읽을 수 없어 기본 타겟({target_ip}:{target_port}) 사용 (Companion Computer).")
        print(f"  [디버그] 확인된 MTD 상태 파일 경로: {target_file_used}")

    print(f"  -> 현재 공격 타겟 설정: {target_ip}:{target_port}")

    attack_base_name = attack_to_run.replace('.sh', '')
    attack_meta = get_attack_metadata(attack_to_run) # 카테고리, MITRE 정보 가져오기

    # 공격 스크립트 실행을 위한 환경 변수 설정
    process_env = os.environ.copy()
    process_env['TARGET_IP'] = target_ip
    process_env['TARGET_PORT'] = str(target_port)
    process_env['ATTACK_NAME'] = attack_base_name # ML 레이블로 사용될 이름
    process_env['MY_IP'] = MY_IP_ADDRESS # 공격자 자신의 IP 전달

    # Python 가상 환경 경로 자동 설정 (스크립트 내 python 호출 시 필요)
    # 현재 실행 중인 파이썬의 경로를 사용
    python_executable_dir = os.path.dirname(sys.executable)
    process_env['PATH'] = f"{python_executable_dir}:{os.environ.get('PATH', '')}"
    # VIRTUAL_ENV 환경 변수가 있다면 사용, 없다면 상위 디렉토리 추정
    process_env['VIRTUAL_ENV'] = os.environ.get('VIRTUAL_ENV', os.path.dirname(python_executable_dir))

    proc = None # Popen 객체 초기화
    try:
        print("\n" + "="*23 + " 공격 시작 " + "="*24)
        print(f"  - 공격자 IP        : {MY_IP_ADDRESS}")
        print(f"  - 스크립트         : {attack_to_run}")
        print(f"  - 타겟             : {target_ip}:{target_port}")
        print(f"  - 공격 카테고리    : {attack_meta['attack_category']}") # 고유 이름 출력
        if attack_meta['mitre_tactics']:
             print(f"  - MITRE Tactic(s) : {', '.join(attack_meta['mitre_tactics'])}")
        print("="*58)

        # 공격 시작 이벤트 로깅 (ML 레이블 포함)
        log_bus_event("attack_started", {
            "attack": attack_to_run,
            "target": f"{target_ip}:{target_port}",
            "source_ip": MY_IP_ADDRESS,
            "attack_category": attack_meta['attack_category'], # 고유 레이블 기록
            "mitre_tactics": attack_meta['mitre_tactics']
        }, source_override="attack_orchestrator")

        # 프로세스 그룹 생성(preexec_fn=os.setsid)하여 자식 프로세스까지 제어
        proc = subprocess.Popen(
            ['/bin/bash', attack_script_path],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding='utf-8', errors='replace',
            preexec_fn=os.setsid, # 중요: 프로세스 그룹 ID 설정
            env=process_env
        )

        # 전역 변수 업데이트 (락 사용)
        with attack_lock:
            attack_process = proc

        # stdout/stderr 스트림 리더 스레드 시작
        threading.Thread(target=stream_reader, args=(proc.stdout, "stdout", attack_to_run), daemon=True).start()
        threading.Thread(target=stream_reader, args=(proc.stderr, "stderr", attack_to_run), daemon=True).start()

    except Exception as e:
        print(f"❌ 공격 스크립트 실행 중 예외 발생 ({attack_to_run}): {e}", file=sys.stderr)
        log_bus_event("attack_exception", {"attack": attack_to_run, "error": str(e)}, source_override="attack_orchestrator")
        with attack_lock:
            attack_process = None # 실패 시 전역 변수 초기화
        # proc 객체가 생성되었으나 오류가 발생한 경우 정리 시도
        if proc and proc.poll() is None:
            _kill_process_group(proc)
        return None

    return proc

def main():
    # 종료 신호 핸들러 설정
    def signal_handler(signum, frame):
        sig_name = signal.Signals(signum).name
        print(f"\n[메인] 종료 신호 ({sig_name}) 수신. 오케스트레이터 종료 중...")
        terminate_orchestrator(f"signal_{sig_name}")

    signal.signal(signal.SIGINT, signal_handler) # Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler) # kill 명령어

    parser = argparse.ArgumentParser(description="DVD 공격 오케스트레이터 v2.5 (Stability & Labeling)")
    parser.add_argument('-a', '--attack', help="실행할 특정 공격 스크립트(.sh 파일 이름)")
    parser.add_argument('--run-all', action='store_true', help="사용 가능한 모든 공격 스크립트를 순차적으로 실행합니다.")
    parser.add_argument('--duration', type=int, default=60, help="--run-all 모드에서 각 공격을 실행할 최대 시간(초)")
    parser.add_argument('--delay', type=int, default=5, help="--run-all 모드에서 공격 사이의 대기 시간(초)")
    # --yes 옵션 제거 (대화형 모드 불필요)

    args = parser.parse_args()
    state_file = get_mtd_state_file_path() # MTD 상태 파일 경로 가져오기
    all_attacks = get_available_attacks()

    if not all_attacks:
        sys.exit(1) # 사용 가능한 공격 없으면 종료

    if args.run_all:
        print(f"--- 전체 공격 순차 실행 모드 시작 ({len(all_attacks)}개 공격) ---")
        print(f"    각 공격 최대 실행 시간: {args.duration}초")
        print(f"    공격 간 대기 시간: {args.delay}초")
        for i, attack_name in enumerate(all_attacks, 1):
            if stop_event.is_set():
                print("[메인] 종료 신호 감지됨. 전체 실행 중단.")
                break

            attack_meta = get_attack_metadata(attack_name) # 메타데이터 미리 로드

            print(f"\n--- [{i}/{len(all_attacks)}] '{attack_name}' 공격 실행 ---")
            proc = run_single_attack(attack_name, state_file)

            if proc:
                return_code = None
                try:
                    # 지정된 시간 동안 대기, 끝나면 종료 코드 반환
                    proc.wait(timeout=args.duration)
                    return_code = proc.returncode
                    print(f"    '{attack_name}' 공격 정상 종료 (Return Code: {return_code}).")
                except subprocess.TimeoutExpired:
                    print(f"    '{attack_name}' 실행 시간 초과({args.duration}초). 프로세스 정리 중...")
                    cleanup_attack_process(f"duration_limit ({args.duration}s)")
                    return_code = -1 # 타임아웃 시 -1로 표시 (SIGTERM/SIGKILL로 종료됨)
                except Exception as wait_err:
                     print(f"❌ '{attack_name}' 대기 중 오류 발생: {wait_err}", file=sys.stderr)
                     cleanup_attack_process(f"wait_error_{type(wait_err).__name__}")
                     return_code = -2 # 대기 중 오류

                # 공격 종료 로그 기록 (return_code 추가)
                log_bus_event("attack_finished", {
                    "attack": attack_name,
                    "return_code": return_code,
                    "attack_category": attack_meta['attack_category'] # 고유 레이블
                }, source_override="attack_orchestrator")
            else:
                # run_single_attack 실패 시 (파일 없음 등)
                print(f"    '{attack_name}' 공격 실행 시작 실패.")
                log_bus_event("attack_exception", {
                    "attack": attack_name,
                    "error": "Failed to start attack process"
                }, source_override="attack_orchestrator")

            # 다음 공격 전 대기 (종료 신호 없으면)
            if not stop_event.is_set() and i < len(all_attacks) and args.delay > 0:
                print(f"    다음 공격까지 {args.delay}초 대기...")
                # time.sleep 대신 stop_event.wait 사용 (중간 종료 가능하도록)
                interrupted = stop_event.wait(timeout=args.delay)
                if interrupted:
                     print("[메인] 대기 중 종료 신호 감지됨. 전체 실행 중단.")
                     break
        print("--- 전체 공격 순차 실행 완료 ---")

    elif args.attack:
        # 특정 공격 1회 실행 모드
        if args.attack not in all_attacks:
             print(f"⛔ 오류: 지정된 공격 스크립트 '{args.attack}'를 찾을 수 없습니다.", file=sys.stderr)
             print("   사용 가능한 공격:", ", ".join(all_attacks))
             sys.exit(1)

        attack_meta = get_attack_metadata(args.attack)
        print(f"--- 단일 공격 실행 모드: '{args.attack}' ---")
        proc = run_single_attack(args.attack, state_file)

        if proc:
            # 프로세스가 끝날 때까지 대기 (KeyboardInterrupt로 중단 가능)
            try:
                 proc.wait()
                 return_code = proc.returncode
                 print(f"    '{args.attack}' 공격 종료됨 (Return Code: {return_code}).")
            except KeyboardInterrupt:
                 # Ctrl+C 누르면 signal_handler가 처리하므로 여기서는 별도 처리 불필요
                 print("\n[메인] 사용자 인터럽트 감지. 정리 작업 진행 중...")
                 return_code = -9 # 사용자 중단 시 코드 (임의)
                 # signal_handler가 terminate_orchestrator 호출 -> cleanup_attack_process 실행
            except Exception as wait_err:
                 print(f"❌ '{args.attack}' 대기 중 오류 발생: {wait_err}", file=sys.stderr)
                 cleanup_attack_process(f"wait_error_{type(wait_err).__name__}")
                 return_code = -2

            # 단일 실행 완료 후에도 종료 로그 기록
            log_bus_event("attack_finished", {
                 "attack": args.attack,
                 "return_code": return_code,
                 "attack_category": attack_meta['attack_category']
             }, source_override="attack_orchestrator")
        else:
             print(f"    '{args.attack}' 공격 실행 시작 실패.")

    else:
        # 실행할 공격이 지정되지 않은 경우 사용법 안내
        print("사용법: attack_orchestrator.py [-a <attack_script.sh> | --run-all]")
        print("\n사용 가능한 공격 스크립트:")
        for attack in all_attacks:
            print(f"  - {attack}")
        sys.exit(0)

    # 모든 작업 완료 후 정상 종료
    if not stop_event.is_set(): # 이미 종료된 상태가 아니면
        terminate_orchestrator("normal_completion")

if __name__ == "__main__":
    main()
