#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import json
import datetime
import subprocess
from typing import Set # Set 타입 임포트

# --- 경로 설정 ---
MONITORS_DIR = os.path.dirname(os.path.realpath(__file__))
LPC_DIR = os.path.dirname(MONITORS_DIR) # 상위 디렉토리 (dvd_attacks_lpc)
BUS_DIR = os.path.join(LPC_DIR, 'bus')

# ⭐️ [수정] Attack Orchestrator 와 RL-Driven MTD Manager의 로그를 모두 감시
# bus.log는 일반 이벤트용으로 가정하고, rl_mtd_decision은 별도 파일로 가정하지 않음 (rl_manager가 bus.log에 쓴다고 가정)
SOURCE_BUS_LOG = os.path.join(BUS_DIR, 'bus.log') # Attack Orchestrator 및 RL Manager의 통합 로그 파일 가정
LOG_FILE_PATH = os.path.join(BUS_DIR, 'bus_system_events.log') # 이 모니터의 출력 파일

# 공격 상태를 식별하기 위한 환경 변수
CURRENT_ATTACK_LABEL = os.environ.get('ATTACK_NAME', 'normal')

# 모니터링할 핵심 이벤트 타입 목록 (Set으로 변경하여 검색 속도 향상)
INTERESTING_EVENTS: Set[str] = {
    "attack_started", "attack_finished", "attack_cleanup", "attack_exception",
    "mtd_shuffle_executed", # deception_manager.py 에서 로깅하는 이벤트
    "rl_mtd_decision",      # rl_driven_deception_manager.py 에서 로깅하는 이벤트
    # "recon_started", "recon_found_target", "recon_failed", # recon 모듈 사용 시 추가
}

def follow_log(filepath: str):
    """'tail -F'처럼 파일을 따라가며 새로운 라인을 반환하는 제너레이터"""

    # 파일이 존재하지 않으면 빈 파일을 생성
    if not os.path.exists(filepath):
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        try:
            with open(filepath, 'a'):
                os.utime(filepath, None)
            print(f"[System Event Monitor] 정보: 로그 파일 '{os.path.basename(filepath)}'을 새로 생성했습니다.")
        except Exception as e:
            print(f"❌ [System Event Monitor] 오류: 파일 생성 실패 '{filepath}': {e}", file=sys.stderr)
            # 파일 생성 실패 시, 해당 소스 모니터링 불가
            return # 제너레이터 종료

    process = None
    try:
        # tail -F : 파일 이름 변경/삭제 후 재생성되어도 계속 추적
        # tail -n 0 : 시작 시점 이후의 새로운 라인만 읽음
        process = subprocess.Popen(['tail', '-F', '-n', '0', filepath],
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, # stderr도 캡처
                                   text=True, encoding='utf-8', errors='replace')
        print(f"[System Event Monitor] '{os.path.basename(filepath)}' 실시간 모니터링 시작...")

        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None: # tail 프로세스가 종료되면 루프 종료
                 break
            if line:
                 yield line.strip()
            else:
                 # stderr에 내용이 있는지 확인 (tail 자체의 오류 등)
                 err_line = process.stderr.readline()
                 if err_line:
                     print(f"[System Event Monitor] 경고: tail 프로세스 오류: {err_line.strip()}", file=sys.stderr)
                 # 라인이 없으면 잠시 대기 (CPU 사용량 줄이기)
                 time.sleep(0.05)

    except FileNotFoundError:
         print(f"❌ [System Event Monitor] 오류: 'tail' 명령어를 찾을 수 없습니다. 시스템에 tail이 설치되어 있는지 확인하세요.", file=sys.stderr)
    except KeyboardInterrupt: # Ctrl+C 처리
         print("\n[System Event Monitor] 사용자 요청으로 모니터링 중지 (tail 종료).")
    except Exception as e:
        print(f"❌ [System Event Monitor] 로그 파일 모니터링 중 예외 발생: {e}", file=sys.stderr)
    finally:
        if process and process.poll() is None:
             print(f"[System Event Monitor] tail 프로세스(PID: {process.pid}) 종료 중...")
             process.terminate()
             try:
                 process.wait(timeout=2)
             except subprocess.TimeoutExpired:
                 process.kill()
             print("[System Event Monitor] tail 프로세스 종료 완료.")


def write_jsonl(record: dict):
    """JSONL 형식으로 로그를 파일에 씁니다."""
    record['attack_label'] = CURRENT_ATTACK_LABEL
    try:
        with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    except IOError as e:
        print(f"❌ [System Event Monitor] 로그 파일 쓰기 오류 ({LOG_FILE_PATH}): {e}", file=sys.stderr)

def main():
    """bus.log를 모니터링하며 핵심 시스템 이벤트를 통합 로그에 기록합니다."""
    os.makedirs(os.path.dirname(LOG_FILE_PATH), exist_ok=True)
    print(f"[System Event Monitor] 핵심 시스템 이벤트 로깅 시작 -> {LOG_FILE_PATH}")
    print(f"✅ [System Event Monitor] 현재 공격 라벨: {CURRENT_ATTACK_LABEL}")
    print(f"[*] 모니터링 대상 로그 파일: {SOURCE_BUS_LOG}")
    print(f"[*] 필터링할 이벤트 타입: {', '.join(sorted(list(INTERESTING_EVENTS)))}")

    processed_lines = 0
    try:
        for line in follow_log(SOURCE_BUS_LOG):
            processed_lines += 1
            if not line: # 빈 줄은 무시
                 continue
            try:
                log_entry = json.loads(line)
                event_type = log_entry.get("type")

                # INTERESTING_EVENTS 목록에 있는 타입만 처리
                if event_type in INTERESTING_EVENTS:
                    # 원본 로그 구조를 최대한 유지하되, source만 변경
                    clean_record = {
                        "timestamp": log_entry.get("timestamp", datetime.datetime.now(datetime.timezone.utc).isoformat()), # 타임스탬프 없으면 현재 시간
                        "ts": log_entry.get("ts", time.time()), # ts 없으면 현재 시간
                        "source": "system_event_monitor", # 이 모니터가 기록했음을 명시
                        "original_source": log_entry.get("source", "unknown"), # 원본 소스 기록
                        "type": event_type, # 원본 타입 유지
                        "data": log_entry.get("data", {})
                    }
                    write_jsonl(clean_record)
                    # print(f"  -> Relayed event: {event_type}") # 디버깅용 출력

            except json.JSONDecodeError:
                # print(f"[System Event Monitor] 경고: JSON 파싱 실패 - {line[:100]}...", file=sys.stderr) # 너무 많은 로그 방지
                continue
            except Exception as e:
                print(f"❌ [System Event Monitor] 로그 처리 중 오류 발생: {line[:100]}... | 오류: {e}", file=sys.stderr)

    except KeyboardInterrupt:
         print("\n[System Event Monitor] 사용자 요청으로 메인 루프 종료.")
    finally:
        print(f"[System Event Monitor] 모니터링 종료. 총 {processed_lines} 라인 처리됨.")


if __name__ == "__main__":
    main()
