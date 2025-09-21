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
LPC_DIR = os.path.dirname(MONITORS_DIR)
BUS_DIR = os.path.join(LPC_DIR, 'bus')

# 입력 소스 및 출력 파일 경로
SOURCE_BUS_LOG = os.path.join(BUS_DIR, 'bus.log')
OUTPUT_LOG_FILE = os.path.join(BUS_DIR, 'bus_system_events.log')

# --- 모니터링할 핵심 이벤트 목록 ---
# 여기에 추적하고 싶은 이벤트 타입을 추가하세요.
INTERESTING_EVENTS = {
    # 공격 라이프사이클
    "attack_started",
    "attack_finished",
    "attack_terminating",
    
    # MTD 발동
    "mtd_triggered",
    
    # 정찰 및 재탐색 (Prober/Seeker 활동)
    "recon_started",
    "recon_found_target",
    "recon_failed",
}

def follow_log(filepath: str):
    """'tail -F'처럼 파일을 계속 따라가며 새로운 라인을 반환하는 제너레이터"""
    if not os.path.exists(filepath):
        print(f"[경고] 로그 파일이 아직 없습니다: {filepath}. 생성을 기다립니다...")
        # 파일이 생성될 때까지 대기
        while not os.path.exists(filepath):
            time.sleep(1)

    try:
        proc = subprocess.Popen(['tail', '-F', '-n', '0', filepath], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        print(f"✅ '{os.path.basename(filepath)}' 실시간 모니터링 시작...")
        
        for line in iter(proc.stdout.readline, ''):
            if not line:
                time.sleep(0.1)
                continue
            yield line.strip()

    except FileNotFoundError:
        print(f"❌ 'tail' 명령을 찾을 수 없습니다. 스크립트를 종료합니다.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"❌ 로그 파일 모니터링 중 오류 발생: {e}", file=sys.stderr)


def write_jsonl(record: dict):
    """JSONL 형식으로 로그를 파일에 씁니다."""
    try:
        with open(OUTPUT_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except IOError as e:
        print(f"❌ 이벤트 로그 파일 쓰기 오류: {e}", file=sys.stderr)

def main():
    """bus.log를 실시간으로 모니터링하며 핵심 시스템 이벤트를 별도 파일에 기록합니다."""
    os.makedirs(os.path.dirname(OUTPUT_LOG_FILE), exist_ok=True)
    print(f"핵심 시스템 이벤트 로깅 시작 -> {OUTPUT_LOG_FILE}")

    for line in follow_log(SOURCE_BUS_LOG):
        try:
            log_entry = json.loads(line)
            event_type = log_entry.get("type")

            if event_type in INTERESTING_EVENTS:
                # 핵심 정보만 추출하여 새로운 레코드 생성
                clean_record = {
                    "timestamp": log_entry.get("timestamp"),
                    "ts": log_entry.get("ts"),
                    "source": "system_bus",
                    "type": event_type,
                    "data": log_entry.get("data", {})
                }
                write_jsonl(clean_record)

        except json.JSONDecodeError:
            # JSON 파싱이 불가능한 라인은 무시
            continue
        except KeyboardInterrupt:
            print("\n사용자 요청으로 모니터링을 중지합니다.")
            break
        except Exception as e:
            print(f"❌ 로그 라인 처리 중 오류: {line} | 오류: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()