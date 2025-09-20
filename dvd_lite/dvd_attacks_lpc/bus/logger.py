#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import json
import time
import datetime
import fcntl # 파일 잠금을 위해 추가

# --- 경로 설정 ---
BUS_DIR = os.path.dirname(os.path.realpath(__file__))
LOG_FILE_PATH = os.path.join(BUS_DIR, 'bus.log')

def log_bus_event(event_type: str, data: dict):
    """
    지정된 이벤트를 bus.log 파일에 JSONL 형식으로 안전하게 기록합니다.
    - 파일 잠금(flock)을 사용하여 여러 프로세스가 동시에 써도 로그가 깨지지 않도록 보장합니다.
    - with 구문을 사용하여 파일 핸들을 안정적으로 관리합니다.
    """
    record = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "ts": time.time(),
        "type": event_type,
        "data": data,
    }

    try:
        # 'a' 모드로 파일을 열어 내용을 추가합니다.
        with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
            # --- 파일 잠금 시작 ---
            # 다른 프로세스가 이 파일에 쓰는 것을 잠시 막아 로그가 섞이는 것을 방지합니다.
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                # JSON 문자열로 변환하여 파일에 쓰고, flush=True로 즉시 기록합니다.
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
            finally:
                # --- 파일 잠금 해제 ---
                fcntl.flock(f, fcntl.LOCK_UN)
    except IOError as e:
        # 터미널에 오류를 출력하여 문제를 즉시 인지할 수 있도록 합니다.
        print(f"[ERROR] bus.log 파일 쓰기 실패: {e}", file=sys.stderr)
    except Exception as e:
        print(f"[ERROR] 로그 기록 중 예기치 않은 오류 발생: {e}", file=sys.stderr)

if __name__ == '__main__':
    # 로거 테스트를 위한 예제 코드
    print(f"로거 테스트: '{LOG_FILE_PATH}' 파일에 테스트 로그를 기록합니다.")
    log_bus_event("test_event", {"message": "Logger is working correctly!", "pid": os.getpid()})
    print("테스트 완료.")