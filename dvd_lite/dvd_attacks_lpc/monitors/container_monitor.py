#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import time
import json
import datetime
from typing import Dict, Any

from pymavlink import mavutil

# --- 경로 및 설정 ---
MONITORS_DIR = os.path.dirname(os.path.realpath(__file__))
BUS_DIR = os.path.join(os.path.dirname(MONITORS_DIR), 'bus')
LOG_FILE_PATH = os.path.join(BUS_DIR, 'bus_unified.log') # ⭐️ 통합 로그 파일 경로

# ⭐️ 공격 상태를 식별하기 위한 환경 변수 (없으면 'normal'로 간주)
CURRENT_ATTACK_LABEL = os.environ.get('ATTACK_NAME', 'normal')

# 환경 변수로 설정값 우선 지정
MAVLINK_CONNECTION_STRING = os.environ.get('MAVLINK_CONNECTION_STRING', "udpin:0.0.0.0:14550")
HEARTBEAT_TIMEOUT_SEC = float(os.environ.get('HEARTBEAT_TIMEOUT_SEC', 10))
LOGGING_INTERVAL_SEC = 0.3 # 0.3초 (10Hz) 주기로 집계된 상태를 로깅

def try_connect(uri: str):
    """지정된 URI로 MAVLink 연결을 시도하고, 성공 시 master 객체를 반환합니다."""
    try:
        print(f"[Container Monitor] MAVLink 연결 시도 중: {uri}...")
        master = mavutil.mavlink_connection(uri, robust_parsing=True)
        master.wait_heartbeat(timeout=8)
        print(f"✅ [Container Monitor] MAVLink 연결 성공 (System ID: {master.target_system})")
        return master
    except Exception as e:
        print(f"❌ [Container Monitor] MAVLink 연결 실패: {e}", file=sys.stderr)
        return None

def write_jsonl(record: dict):
    """JSONL 형식으로 로그를 파일에 씁니다."""
    # ⭐️ 레코드에 공격 라벨 필드 추가
    record['attack_label'] = CURRENT_ATTACK_LABEL
    try:
        with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    except IOError as e:
        print(f"❌ [Container Monitor] 로그 파일 쓰기 오류: {e}", file=sys.stderr)

def main():
    """상세 MAVLink 텔레메트리를 수집하여 주기적으로 통합 로그 파일에 기록합니다."""
    os.makedirs(os.path.dirname(LOG_FILE_PATH), exist_ok=True)
    master = try_connect(MAVLINK_CONNECTION_STRING)
    if not master:
        print("[Container Monitor] 연결 실패. 스크립트를 종료합니다.")
        return

    print(f"[Container Monitor] 드론 상세 상태 로깅 시작 -> {LOG_FILE_PATH}")
    print(f"✅ [Container Monitor] 현재 공격 라벨: {CURRENT_ATTACK_LABEL}")

    latest_data: Dict[str, Any] = {}
    last_log_time = time.monotonic()
    last_hb_seen = time.monotonic()

    while True:
        try:
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
                    print(f"[Container Monitor][FCU STATUSTEXT] {text}")
                    write_jsonl({
                        'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                        'ts': time.time(),
                        'source': 'container_monitor',
                        'type': 'fcu_statustext',
                        'data': {'severity': mavutil.mavlink.enums['MAV_SEVERITY'][msg.severity].name, 'text': text}
                    })
            
            current_time = time.monotonic()
            if (current_time - last_log_time) >= LOGGING_INTERVAL_SEC:
                if latest_data:
                    write_jsonl({
                        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                        "ts": time.time(),
                        "source": "container_monitor",
                        "type": "drone_state",
                        "data": latest_data
                    })
                last_log_time = current_time

            if (current_time - last_hb_seen) > HEARTBEAT_TIMEOUT_SEC:
                print(f"⚠️ [Container Monitor] MAVLink 하트비트 타임아웃. 재연결 시도...")
                master.close()
                master = try_connect(MAVLINK_CONNECTION_STRING)
                if not master: return
                last_hb_seen = time.monotonic()

            time.sleep(0.01)

        except KeyboardInterrupt:
            print("\n[Container Monitor] 사용자 요청으로 모니터링을 중지합니다.")
            break
        except Exception as e:
            print(f"❌ [Container Monitor] 처리 중 예외 발생: {e}", file=sys.stderr)
            time.sleep(2)

    if master:
        master.close()

if __name__ == "__main__":
    main()