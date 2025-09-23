#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# v2.1 - Hotfix for AttributeError

import os
import sys
import time
import json
import math  # math 라이브러리 임포트
import datetime
from typing import Dict, Any, Optional

from pymavlink import mavutil

# --- 경로 및 설정 ---
MONITORS_DIR = os.path.dirname(os.path.realpath(__file__))
BUS_DIR = os.path.join(os.path.dirname(MONITORS_DIR), 'bus')
LOG_FILE_PATH = os.path.join(BUS_DIR, 'bus_dvd.log')

# 환경 변수 또는 기본값 사용
MAVLINK_CONNECTION_STRING = os.environ.get('MAVLINK_CONNECTION_STRING', "udpin:0.0.0.0:14550")
HEARTBEAT_TIMEOUT_SEC = float(os.environ.get('HEARTBEAT_TIMEOUT_SEC', 10))
LOGGING_INTERVAL_SEC = 0.1  # 10Hz, 더 빠른 데이터 갱신을 위해 0.1초로 변경

def try_connect(uri: str) -> Optional[mavutil.mavlink_connection]:
    """지정된 URI로 MAVLink 연결을 시도하고, 성공 시 master 객체를 반환합니다."""
    try:
        print(f"MAVLink 연결 시도 중: {uri}...")
        master = mavutil.mavlink_connection(uri, robust_parsing=True, source_system=255)
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

def get_default_telemetry_data() -> Dict[str, Any]:
    """모든 필드를 None 또는 기본값으로 초기화한 딕셔너리를 반환합니다."""
    return {
        'pitch_deg': None, 'roll_deg': None, 'yaw_deg': None,
        'lat': None, 'lon': None, 'alt_m': None, 'relative_alt_m': None,
        'vx': None, 'vy': None, 'vz': None,
        'cpu_load_pct': None, 'errors_count1': 0, 'errors_count2': 0,
        'groundspeed_ms': None, 'heading_deg': None, 'throttle_pct': None,
        'battery_v': None, 'battery_pct': -1,
        'armed': False, 'mode': 'UNKNOWN', 'system_status': 'UNINIT'
    }

def main():
    """요청된 모든 MAVLink 텔레메트리를 수집하여 bus_dvd.log에 종합적으로 기록하는 메인 함수."""
    os.makedirs(os.path.dirname(LOG_FILE_PATH), exist_ok=True)
    master = try_connect(MAVLINK_CONNECTION_STRING)
    if not master:
        print("연결 실패. 5초 후 재시도합니다.")
        time.sleep(5)
        sys.exit(1)

    print(f"드론 종합 상태 로깅 시작 -> {LOG_FILE_PATH} (주기: {LOGGING_INTERVAL_SEC}초)")

    latest_data = get_default_telemetry_data()
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

                elif msg_type == 'ATTITUDE':
                    # *** FIX: mavutil.degrees -> math.degrees 로 수정 ***
                    latest_data.update({
                        'pitch_deg': round(math.degrees(msg.pitch), 2),
                        'roll_deg': round(math.degrees(msg.roll), 2),
                        'yaw_deg': round(math.degrees(msg.yaw), 2)
                    })

                elif msg_type == 'GLOBAL_POSITION_INT':
                    latest_data.update({
                        'lat': msg.lat / 1e7,
                        'lon': msg.lon / 1e7,
                        'alt_m': msg.alt / 1000.0,
                        'relative_alt_m': msg.relative_alt / 1000.0,
                        'vx': msg.vx / 100.0,
                        'vy': msg.vy / 100.0,
                        'vz': msg.vz / 100.0,
                        'heading_deg': msg.hdg / 100
                    })
                
                elif msg_type == 'VFR_HUD':
                    latest_data.update({
                        'groundspeed_ms': round(msg.groundspeed, 2),
                        'throttle_pct': msg.throttle
                    })

                elif msg_type == 'SYS_STATUS':
                    voltages = getattr(msg, 'voltage_battery', 0)
                    latest_data.update({
                        'cpu_load_pct': msg.load / 10.0,
                        'battery_v': msg.voltage_battery / 1000.0,
                        'battery_pct': msg.battery_remaining,
                        'errors_count1': msg.errors_count1,
                        'errors_count2': msg.errors_count2
                    })
                
                elif msg_type == 'BATTERY_STATUS':
                     # SYS_STATUS가 없을 경우를 대비한 백업
                    if latest_data.get('battery_v') is None:
                        voltages = getattr(msg, 'voltages', [])
                        latest_data.update({
                            'battery_v': voltages[0] / 1000.0 if voltages and voltages[0] < 65535 else None,
                            'battery_pct': getattr(msg, 'battery_remaining', -1),
                        })

                elif msg_type == 'STATUSTEXT':
                    text = getattr(msg, 'text', '').rstrip('\x00')
                    print(f"[FCU STATUSTEXT] {text}")
                    write_jsonl({
                        'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                        'ts': time.time(), 'source': 'flight_controller', 'type': 'fcu_statustext',
                        'data': {'severity': mavutil.mavlink.enums['MAV_SEVERITY'][msg.severity].name, 'text': text}
                    })

            # 2. 주기적 로그 기록
            current_time = time.monotonic()
            if (current_time - last_log_time) >= LOGGING_INTERVAL_SEC:
                if latest_data['lat'] is not None: # GPS 수신이 되었을 때만 로깅
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
                if not master:
                    print("재연결 실패. 스크립트를 종료합니다.")
                    return
                last_hb_seen = time.monotonic()

            time.sleep(0.005) # CPU 사용량 감소를 위한 짧은 대기

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