import json
import os
import time
from logging import getLogger, FileHandler, Formatter, INFO

# 로그 파일이 저장될 기본 경로 (이 파일의 위치 기준)
BUS_DIR = os.path.abspath(os.path.dirname(__file__))

# --- 파일 핸들러 설정 ---
bus_log_handler = FileHandler(os.path.join(BUS_DIR, 'bus.log'))
bus_log_handler.setFormatter(Formatter('%(message)s'))

bus_dvd_log_handler = FileHandler(os.path.join(BUS_DIR, 'bus_dvd.log'))
bus_dvd_log_handler.setFormatter(Formatter('%(message)s'))

# --- 로거 객체 생성 (중복 생성을 막기 위한 로직 추가) ---
bus_logger = getLogger('bus_logger')
if not bus_logger.handlers:
    bus_logger.setLevel(INFO)
    bus_logger.addHandler(bus_log_handler)

dvd_logger = getLogger('dvd_logger')
if not dvd_logger.handlers:
    dvd_logger.setLevel(INFO)
    dvd_logger.addHandler(bus_dvd_log_handler)

def log_bus_event(event_type, event_data):
    """bus.log에 이벤트를 JSONL 형식으로 기록합니다."""
    log_entry = { "timestamp": time.time(), "event_type": event_type, "data": event_data }
    bus_logger.info(json.dumps(log_entry))

def log_dvd_event(source_container, metrics):
    """bus_dvd.log에 이벤트를 JSONL 형식으로 기록합니다."""
    log_entry = { "timestamp": time.time(), "source": source_container, "metrics": metrics }
    dvd_logger.info(json.dumps(log_entry))