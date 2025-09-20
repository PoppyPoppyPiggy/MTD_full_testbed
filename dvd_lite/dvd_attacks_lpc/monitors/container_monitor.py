#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import time
import json
import datetime
from typing import Dict, Any

from pymavlink import mavutil

# --- 경로 및 설정 ---
MONITORS_DIR = os.path.dirname(os.path.realpath(__file__))
BUS_DIR = os.path.join(os.path.dirname(MONITORS_DIR), 'bus')
LOG_FILE_PATH = os.path.join(BUS_DIR, 'bus_dvd.log')

# 환경 변수로 설정값 우선 지정
MAVLINK_CONNECTION_STRING = os.environ.get('MAVLINK_CONNECTION_STRING', "udpin:0.0.0.0:14550")
HEARTBEAT_TIMEOUT_SEC = float(os.environ.get('HEARTBEAT_TIMEOUT_SEC', 10))
LOGGING_INTERVAL_SEC = 0.3 # 0.3초 (10Hz) 주기로 집계된 상태를 로깅

def try_connect(uri: str):
    """지정된 URI로 MAVLink 연결을 시도하고, 성공 시 master 객체를 반환합니다."""
    try:
        print(f"MAVLink 연결 시도 중: {uri}...")
        master = mavutil.mavlink_connection(uri, robust_parsing=True)
        # 8초 타임아웃으로 첫 하트비트 대기
        master.wait_heartbeat(timeout=8)
        print(f"✅ MAVLink 연결 성공: {uri} (System ID: {master.target_system}, Component ID: {master.target_component})")
        return master
    except Exception as e:
        print(f"❌ MAVLink 연결 실패: {e}", file=sys.stderr)
        return None

def write_jsonl(record: dict):
    """JSONL 형식으로 로그를 파일에 씁니다."""
    try:
        with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    except IOError as e:
        print(f"❌ 로그 파일 쓰기 오류: {e}", file=sys.stderr)

def main():
    """상세 MAVLink 텔레메트리를 수집하여 주기적으로 bus_dvd.log에 기록하는 메인 함수."""
    os.makedirs(os.path.dirname(LOG_FILE_PATH), exist_ok=True)
    master = try_connect(MAVLINK_CONNECTION_STRING)
    if not master:
        print("연결 실패. 스크립트를 종료합니다.")
        return

    print(f"드론 상세 상태 로깅 시작 -> {LOG_FILE_PATH} (주기: {LOGGING_INTERVAL_SEC}초)")

    latest_data: Dict[str, Any] = {}
    last_log_time = time.monotonic()
    last_hb_seen = time.monotonic()

    while True:
        try:
            # 1. 메시지 수신 및 최신 상태 업데이트 (논블로킹)
            msg = master.recv_match(blocking=False)
            if msg:
                msg_type = msg.get_type()
                
                if msg_type == 'HEARTBEAT':
                    last_hb_seen = time.monotonic()
                    status = getattr(msg, 'system_status', 0)
                    latest_data.update({
                        'armed': (msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED) != 0,
                        'mode': mavutil.mode_string_v10(msg),
                        'system_status': mavutil.mavlink.enums['MAV_STATE'][status].name if status in mavutil.mavlink.enums['MAV_STATE'] else 'UNKNOWN'
                    })

                elif msg_type == 'BATTERY_STATUS':
                    voltages = getattr(msg, 'voltages', [])
                    latest_data.update({
                        'battery_v': voltages[0] / 1000.0 if voltages and voltages[0] < 65535 else None,
                        'battery_pct': getattr(msg, 'battery_remaining', -1),
                    })
                
                elif msg_type == 'GLOBAL_POSITION_INT':
                    latest_data.update({
                        'lat': getattr(msg, "lat", 0) / 1e7,
                        'lon': getattr(msg, "lon", 0) / 1e7,
                        'alt_m': getattr(msg, "alt", 0) / 1000.0,
                    })

                elif msg_type == 'STATUSTEXT':
                    text = getattr(msg, 'text', '').rstrip('\x00')
                    print(f"[FCU STATUSTEXT] {text}")
                    # STATUSTEXT는 중요하므로 즉시 별도 이벤트로 기록
                    write_jsonl({
                        'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                        'ts': time.time(),
                        'source': 'flight_controller',
                        'type': 'fcu_statustext',
                        'data': {'severity': mavutil.mavlink.enums['MAV_SEVERITY'][msg.severity].name, 'text': text}
                    })
            
            # 2. 주기적 로그 기록
            current_time = time.monotonic()
            if (current_time - last_log_time) >= LOGGING_INTERVAL_SEC:
                if latest_data:
                    write_jsonl({
                        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                        "ts": time.time(),
                        "source": "flight_controller",
                        "type": "drone_state_detailed",
                        "data": latest_data
                    })
                last_log_time = current_time

            # 3. 하트비트 타임아웃 검사
            if (current_time - last_hb_seen) > HEARTBEAT_TIMEOUT_SEC:
                print(f"⚠️ MAVLink 하트비트 타임아웃 (> {HEARTBEAT_TIMEOUT_SEC}초). 재연결 시도...")
                master.close()
                master = try_connect(MAVLINK_CONNECTION_STRING)
                if not master: return
                last_hb_seen = time.monotonic()

            time.sleep(0.01)

        except KeyboardInterrupt:
            print("\n사용자 요청으로 모니터링을 중지합니다.")
            break
        except Exception as e:
            print(f"❌ 처리 중 예외 발생: {e}", file=sys.stderr)
            time.sleep(2)

    if master:
        master.close()

if __name__ == "__main__":
    main()