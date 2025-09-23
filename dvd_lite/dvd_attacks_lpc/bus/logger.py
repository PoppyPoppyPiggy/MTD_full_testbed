#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import time
import datetime
from typing import Dict, Any, Optional

# --- 전역 설정 ---
# 환경 변수에서 로그 파일 경로를 가져오거나 기본값을 사용합니다.
LOG_FILE_PATH = os.environ.get('LPC_BUS_LOG', '/home/kali/MTD_full_testbed/dvd_lite/dvd_attacks_lpc/bus/bus.log')
LOG_FILE_DVD_PATH = os.environ.get('LPC_BUS_DVD_LOG', '/home/kali/MTD_full_testbed/dvd_lite/dvd_attacks_lpc/bus/bus_dvd.log')

# 로그 파일이 위치할 디렉토리가 없으면 생성합니다.
os.makedirs(os.path.dirname(LOG_FILE_PATH), exist_ok=True)
os.makedirs(os.path.dirname(LOG_FILE_DVD_PATH), exist_ok=True)


def log_bus_event(event_type: str, data: Dict[str, Any], is_dvd_event: bool = False):
    """
    지정된 이벤트 타입과 데이터로 표준 로그 레코드를 생성하고 파일에 기록합니다.

    Args:
        event_type (str): 이벤트의 종류를 나타내는 문자열 (예: 'attack_started').
        data (Dict[str, Any]): 이벤트와 관련된 데이터를 담은 딕셔너리.
        is_dvd_event (bool): True이면 bus_dvd.log에, False이면 bus.log에 기록합니다.
    """
    # 표준 로그 구조 생성
    record = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "ts": time.time(),
        "type": event_type,
        "data": data
    }
    
    # 이벤트 종류에 따라 적절한 로그 파일 경로 선택
    log_path = LOG_FILE_DVD_PATH if is_dvd_event else LOG_FILE_PATH
    
    try:
        # JSONL 형식 (한 줄에 하나의 JSON)으로 파일에 추가합니다.
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except IOError as e:
        # 파일 쓰기 오류 발생 시 표준 에러로 출력
        print(f"CRITICAL: Could not write to bus log file '{log_path}'. Error: {e}", file=sys.stderr)

# --- 스크립트로 직접 실행될 때를 위한 간단한 테스트 로직 ---
if __name__ == '__main__':
    print("Logging a test event to the main bus...")
    log_bus_event(
        event_type='test_event',
        data={'message': 'This is a test from logger.py', 'module': 'bus.logger'}
    )
    
    print("Logging a test DVD event to the DVD bus...")
    log_bus_event(
        event_type='test_dvd_event',
        data={'message': 'This is a DVD test from logger.py'},
        is_dvd_event=True
    )
    
    print(f"Test events logged to '{LOG_FILE_PATH}' and '{LOG_FILE_DVD_PATH}'.")