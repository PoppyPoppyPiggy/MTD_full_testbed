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
SOURCE_BUS_LOG = os.path.join(BUS_DIR, 'bus.log') # الأصلي bus.log
LOG_FILE_PATH = os.path.join(BUS_DIR, 'bus_network.log') # ⭐️ 통합 로그 파일 경로

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
    if not os.path.exists(filepath):
        print(f"[System Event Monitor] 경고: 로그 파일이 없습니다: {filepath}. 생성을 기다립니다...")
        while not os.path.exists(filepath):
            time.sleep(1)
    try:
        proc = subprocess.Popen(['tail', '-F', '-n', '0', filepath], stdout=subprocess.PIPE, text=True)
        print(f"[System Event Monitor] '{os.path.basename(filepath)}' 실시간 모니터링 시작...")
        for line in iter(proc.stdout.readline, ''):
            yield line.strip()
    except Exception as e:
        print(f"❌ [System Event Monitor] 로그 파일 모니터링 오류: {e}", file=sys.stderr)

def write_jsonl(record: dict):
    """JSONL 형식으로 로그를 파일에 씁니다."""
    # ⭐️ 레코드에 공격 라벨 필드 추가
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