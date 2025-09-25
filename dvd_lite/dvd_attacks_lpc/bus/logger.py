#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import json
import time
import datetime
import fcntl
import sys

# --- 기본 경로 설정 ---
BUS_DIR = os.path.dirname(os.path.realpath(__file__))
DEFAULT_LOG_FILE_PATH = os.path.join(BUS_DIR, 'bus.log')

def log_bus_event(event_type: str, data: dict, log_file_path: str = None, source_override: str = None):
    """
    지정된 이벤트를 지정된 로그 파일에 JSONL 형식으로 안전하게 기록합니다.
    - log_file_path가 None이면 기본 'bus.log'에 기록합니다.
    - source_override를 통해 로그 기록 주체를 명시할 수 있습니다.
    """
    record = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "ts": time.time(),
        "source": source_override or "default_event",
        "type": event_type,
        "data": data,
    }

    # 사용할 로그 파일 경로 결정
    path = log_file_path or DEFAULT_LOG_FILE_PATH

    try:
        with open(path, "a", encoding="utf-8") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)
    except IOError as e:
        print(f"[ERROR] 로그 파일 쓰기 실패 ({os.path.basename(path)}): {e}", file=sys.stderr)
    except Exception as e:
        print(f"[ERROR] 로그 기록 중 예기치 않은 오류 발생: {e}", file=sys.stderr)

if __name__ == '__main__':
    print(f"로거 테스트: '{DEFAULT_LOG_FILE_PATH}' 파일에 테스트 로그를 기록합니다.")
    log_bus_event("test_event", {"message": "Default logger test.", "pid": os.getpid()})
    
    # 다른 로그 파일에 쓰는 예제
    custom_log_path = os.path.join(BUS_DIR, 'bus_custom.log')
    print(f"로거 테스트: '{custom_log_path}' 파일에 커스텀 로그를 기록합니다.")
    log_bus_event("custom_type", {"value": 123}, log_file_path=custom_log_path, source_override="custom_source")
    
    print("테스트 완료.")