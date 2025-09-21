#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import time
import json
import datetime
from typing import Dict, Any, Optional, Callable

from pymavlink import mavutil

# --- 경로 및 설정 ---
MONITORS_DIR = os.path.dirname(os.path.realpath(__file__))
LPC_DIR = os.path.dirname(MONITORS_DIR)
BUS_DIR = os.path.join(LPC_DIR, 'bus')
LOG_FILE_PATH = os.path.join(BUS_DIR, 'bus_dvd.log')

if LPC_DIR not in sys.path:
    sys.path.insert(0, LPC_DIR)

# --- MAVLink 연결 설정 ---
MAVLINK_CONNECTION_STRING = os.environ.get('MAVLINK_CONNECTION_STRING', "udpin:0.0.0.0:14550")
HEARTBEAT_TIMEOUT_SEC = float(os.environ.get('HEARTBEAT_TIMEOUT_SEC', 15))
LOGGING_INTERVAL_SEC = 0.2  # 0.2초 (5Hz) 주기로 집계된 상태를 로깅

# ==============================================================================
# MAVLink 메시지 핸들러
# - 각 메시지 타입에 맞는 파싱 함수를 정의합니다.
# - 새로운 메시지를 추가하려면 여기에 함수를 추가하고 MESSAGE_HANDLERS에 등록하세요.
# ==============================================================================
def handle_heartbeat(msg) -> Dict[str, Any]:
    status = getattr(msg, 'system_status', 0)
    return {
        'armed': (msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED) != 0,
        'mode': mavutil.mode_string_v10(msg),
        'system_status': mavutil.mavlink.enums['MAV_STATE'][status].name if status in mavutil.mavlink.enums['MAV_STATE'] else 'UNKNOWN'
    }

def handle_battery_status(msg) -> Dict[str, Any]:
    voltages = getattr(msg, 'voltages', [])
    return {
        'battery_v': voltages[0] / 1000.0 if voltages and voltages[0] < 65535 else None,
        'battery_pct': getattr(msg, 'battery_remaining', -1),
    }

def handle_global_position_int(msg) -> Dict[str, Any]:
    return {
        'lat': getattr(msg, "lat", 0) / 1e7,
        'lon': getattr(msg, "lon", 0) / 1e7,
        'alt_m': getattr(msg, "alt", 0) / 1000.0,
        'relative_alt_m': getattr(msg, "relative_alt", 0) / 1000.0,
        'vx': getattr(msg, "vx", 0) / 100.0,
        'vy': getattr(msg, "vy", 0) / 100.0,
        'vz': getattr(msg, "vz", 0) / 100.0,
    }

def handle_attitude(msg) -> Dict[str, Any]:
    return {
        'pitch_deg': getattr(msg, 'pitch', 0) * 180.0 / 3.14159,
        'roll_deg': getattr(msg, 'roll', 0) * 180.0 / 3.14159,
        'yaw_deg': getattr(msg, 'yaw', 0) * 180.0 / 3.14159,
    }

def handle_vfr_hud(msg) -> Dict[str, Any]:
    return {
        'groundspeed_ms': getattr(msg, 'groundspeed', 0),
        'heading_deg': getattr(msg, 'heading', 0),
        'throttle_pct': getattr(msg, 'throttle', 0),
    }

def handle_sys_status(msg) -> Dict[str, Any]:
    return {
        'cpu_load_pct': getattr(msg, 'load', 0) / 10.0,
        'errors_count1': getattr(msg, 'errors_count1', 0),
        'errors_count2': getattr(msg, 'errors_count2', 0),
    }

# 처리할 MAVLink 메시지 타입과 핸들러 함수를 매핑합니다.
MESSAGE_HANDLERS: Dict[str, Callable[[Any], Dict[str, Any]]] = {
    'HEARTBEAT': handle_heartbeat,
    'BATTERY_STATUS': handle_battery_status,
    'GLOBAL_POSITION_INT': handle_global_position_int,
    'ATTITUDE': handle_attitude,
    'VFR_HUD': handle_vfr_hud,
    'SYS_STATUS': handle_sys_status,
}

# ==============================================================================
# 메인 로직
# ==============================================================================
def try_connect(uri: str) -> Optional[mavutil.mavlink_connection]:
    """지정된 URI로 MAVLink 연결을 시도하고, 성공 시 master 객체를 반환합니다."""
    try:
        print(f"MAVLink 연결 시도 중: {uri}...")
        master = mavutil.mavlink_connection(uri, robust_parsing=True, source_system=255)
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
        print("연결 실패. 5초 후 재시도합니다...")
        time.sleep(5)
        main() # 재귀 호출로 재시도
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

                # 핸들러가 등록된 메시지인 경우, 상태를 업데이트
                if msg_type in MESSAGE_HANDLERS:
                    latest_data.update(MESSAGE_HANDLERS[msg_type](msg))

                # STATUSTEXT는 중요하므로 즉시 별도 이벤트로 기록
                elif msg_type == 'STATUSTEXT':
                    text = getattr(msg, 'text', '').rstrip('\x00')
                    print(f"[FCU STATUSTEXT] {text}")
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
                print(f"⚠️ MAVLink 하트비트 타임아웃 (> {HEARTBEAT_TIMEOUT_SEC}초). 재연결합니다...")
                master.close()
                main() # 재귀 호출로 재연결
                return

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