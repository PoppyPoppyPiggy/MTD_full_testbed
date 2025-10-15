#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import json
import datetime
import subprocess

# --- 경로 설정 ---
MONITORS_DIR = os.path.dirname(os.path.realpath(__file__))
BUS_DIR = os.path.join(os.path.dirname(MONITORS_DIR), 'bus')
SOURCE_BUS_LOG = os.path.join(BUS_DIR, 'bus.log') # Attack Orchestrator의 원본 로그 파일
LOG_FILE_PATH = os.path.join(BUS_DIR, 'bus_system_events.log') 

# ⭐️ 공격 상태를 식별하기 위한 환경 변수
CURRENT_ATTACK_LABEL = os.environ.get('ATTACK_NAME', 'normal')

# 모니터링할 핵심 이벤트 목록
INTERESTING_EVENTS = {
    "attack_started", "attack_finished", "attack_terminating",
    "mtd_triggered",
    "recon_started", "recon_found_target", "recon_failed",
}

def follow_log(filepath: str):
    """'tail -F'처럼 파일을 따라가며 새로운 라인을 반환하는 제너레이터"""
    
    # ⭐️ 수정: 파일이 존재하지 않으면 빈 파일을 생성하여 tail이 즉시 실패하는 것을 방지
    if not os.path.exists(filepath):
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        # 빈 파일 생성
        try:
            with open(filepath, 'a'):
                os.utime(filepath, None)
            print(f"[System Event Monitor] 정보: 로그 파일 '{os.path.basename(filepath)}'을 새로 생성했습니다.")
        except Exception as e:
            print(f"❌ [System Event Monitor] 오류: 파일 생성 실패: {e}", file=sys.stderr)
            return

    try:
        # tail -F -n 0 명령은 파일이 생성된 후의 새로운 내용만 실시간으로 출력합니다.
        proc = subprocess.Popen(['tail', '-F', '-n', '0', filepath], stdout=subprocess.PIPE, text=True)
        print(f"[System Event Monitor] '{os.path.basename(filepath)}' 실시간 모니터링 시작...")
        
        # subprocess 파이프에서 줄을 읽습니다.
        for line in iter(proc.stdout.readline, ''):
            yield line.strip()
    except Exception as e:
        print(f"❌ [System Event Monitor] 로그 파일 모니터링 오류: {e}", file=sys.stderr)

def write_jsonl(record: dict):
    """JSONL 형식으로 로그를 파일에 씁니다."""
    record['attack_label'] = CURRENT_ATTACK_LABEL
    try:
        with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except IOError as e:
        print(f"❌ [System Event Monitor] 로그 파일 쓰기 오류: {e}", file=sys.stderr)

def main():
    """bus.log를 모니터링하며 핵심 시스템 이벤트를 통합 로그에 기록합니다."""
    os.makedirs(os.path.dirname(LOG_FILE_PATH), exist_ok=True)
    print(f"[System Event Monitor] 핵심 시스템 이벤트 로깅 시작 -> {LOG_FILE_PATH}")
    print(f"✅ [System Event Monitor] 현재 공격 라벨: {CURRENT_ATTACK_LABEL}")

    for line in follow_log(SOURCE_BUS_LOG):
        try:
            log_entry = json.loads(line)
            event_type = log_entry.get("type")

            if event_type in INTERESTING_EVENTS:
                clean_record = {
                    "timestamp": log_entry.get("timestamp"),
                    "ts": log_entry.get("ts"),
                    "source": "system_event_monitor",
                    "type": f"event_{event_type}",
                    "data": log_entry.get("data", {})
                }
                write_jsonl(clean_record)

        except json.JSONDecodeError:
            continue
        except KeyboardInterrupt:
            print("\n[System Event Monitor] 사용자 요청으로 모니터링을 중지합니다.")
            break
        except Exception as e:
            print(f"❌ [System Event Monitor] 로그 처리 중 오류: {line} | 오류: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
