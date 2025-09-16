# monitors/container_monitor.py

import os
import time
import json
import shutil
import datetime
from typing import Dict, Any

from pymavlink import mavutil

# --- 경로 및 설정 ---
MONITORS_DIR = os.path.dirname(os.path.realpath(__file__))
BUS_DIR = os.path.join(os.path.dirname(MONITORS_DIR), 'bus')
LOG_FILE_PATH = os.path.join(BUS_DIR, 'bus_dvd.log')

# 환경 변수로 연결 문자열 우선 지정
MAVLINK_CONNECTION_STRING = os.environ.get('MAVLINK_CONNECTION_STRING', "udpin:0.0.0.0:14550")
HEARTBEAT_TIMEOUT_SEC = float(os.environ.get('HEARTBEAT_TIMEOUT_SEC', 10))

def try_connect(uri: str):
    """지정된 URI로 MAVLink 연결을 시도합니다."""
    try:
        print(f"MAVLink 연결 시도 중: {uri}...")
        master = mavutil.mavlink_connection(uri, robust_parsing=True)
        master.wait_heartbeat(timeout=8)
        print(f"✅ MAVLink 연결 성공: {uri}")
        return master
    except Exception as e:
        print(f"❌ MAVLink 연결 실패: {e}")
        return None

def main():
    """
    상세 MAVLink 텔레메트리를 수집하여 bus_dvd.log에 기록하는 메인 함수
    """
    os.makedirs(os.path.dirname(LOG_FILE_PATH), exist_ok=True)
    master = try_connect(MAVLINK_CONNECTION_STRING)
    if not master:
        print("연결 실패. 스크립트를 종료합니다.")
        return

    print(f"드론 상세 상태 로깅 시작 -> {LOG_FILE_PATH}")

    # 모든 메시지 타입에 대한 최신 데이터를 저장하는 딕셔너리
    latest_data: Dict[str, Any] = {}

    while True:
        try:
            msg = master.recv_match(blocking=True, timeout=HEARTBEAT_TIMEOUT_SEC)
            
            if msg is None:
                print(f"⚠️ MAVLink 하트비트 타임아웃 (> {HEARTBEAT_TIMEOUT_SEC}초). 재연결 시도...")
                master.close()
                master = try_connect(MAVLINK_CONNECTION_STRING)
                if not master: return
                continue

            msg_type = msg.get_type()

            # --- 상세 메시지 파싱 ---
            if msg_type == 'HEARTBEAT':
                status = getattr(msg, 'system_status', 0)
                latest_data.update({
                    'armed': (msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED) != 0,
                    'mode_name': mavutil.mode_string_v10(msg),
                    'base_mode_raw': int(getattr(msg, 'base_mode', 0)),
                    'custom_mode_raw': int(getattr(msg, 'custom_mode', 0)),
                    'system_status_raw': int(status),
                    'system_status_name': mavutil.mavlink.enums['MAV_STATE'][status].name if status in mavutil.mavlink.enums['MAV_STATE'] else 'UNKNOWN'
                })

            elif msg_type == 'BATTERY_STATUS':
                # SYS_STATUS보다 훨씬 상세한 배터리 정보
                voltages = getattr(msg, 'voltages', [])
                latest_data.update({
                    'battery_voltages_v': [v / 1000.0 for v in voltages if v < 65535], # 유효한 값만 변환
                    'battery_current_a': getattr(msg, 'current_battery', -1) / 100.0,
                    'battery_remaining_pct': getattr(msg, 'battery_remaining', -1),
                })
            
            elif msg_type == 'GLOBAL_POSITION_INT':
                latest_data.update({
                    'lat_deg': getattr(msg, "lat", 0) / 1e7,
                    'lon_deg': getattr(msg, "lon", 0) / 1e7,
                    'alt_m': getattr(msg, "alt", 0) / 1000.0,
                })

            elif msg_type == 'EKF_STATUS_REPORT':
                # 위치 추정 품질(Localization Quality) 확인
                flags = getattr(msg, 'flags', 0)
                latest_data['ekf_status'] = {
                    'attitude': (flags & mavutil.mavlink.EKF_ATTITUDE) > 0,
                    'velocity_horiz': (flags & mavutil.mavlink.EKF_VELOCITY_HORIZ) > 0,
                    'velocity_vert': (flags & mavutil.mavlink.EKF_VELOCITY_VERT) > 0,
                    'pos_horiz_rel': (flags & mavutil.mavlink.EKF_POS_HORIZ_REL) > 0,
                    'pos_horiz_abs': (flags & mavutil.mavlink.EKF_POS_HORIZ_ABS) > 0,
                    'pos_vert_abs': (flags & mavutil.mavlink.EKF_POS_VERT_ABS) > 0,
                    'flags_raw': int(flags)
                }

            elif msg_type == 'GPS_RAW_INT':
                latest_data.update({
                    'gps_fix_type': int(getattr(msg, 'fix_type', 0)),
                    'gps_satellites_visible': int(getattr(msg, 'satellites_visible', 0))
                })

            elif msg_type == 'VFR_HUD':
                latest_data.update({
                    'airspeed_ms': getattr(msg, 'airspeed', 0.0),
                    'groundspeed_ms': getattr(msg, 'groundspeed', 0.0),
                    'heading_deg': int(getattr(msg, 'heading', 0)),
                    'throttle_pct': int(getattr(msg, 'throttle', 0)),
                    'climb_ms': getattr(msg, 'climb', 0.0)
                })

            elif msg_type == 'STATUSTEXT':
                # FCU가 보내는 중요한 텍스트 메시지 (경고/오류 등)
                text = getattr(msg, 'text', '').rstrip('\x00')
                print(f"FCU STATUSTEXT: {text}")
                # STATUSTEXT는 일회성 이벤트이므로 직접 로그 기록
                write_jsonl({
                    'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    'source': 'flight_controller',
                    'type': 'fcu_statustext',
                    'severity': mavutil.mavlink.enums['MAV_SEVERITY'][msg.severity].name if msg.severity in mavutil.mavlink.enums['MAV_SEVERITY'] else 'UNKNOWN',
                    'text': text
                })

            # 모든 수신된 데이터를 모아 하나의 레코드로 파일에 기록
            record = {
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "source": "flight_controller",
                "type": "drone_state_detailed",
                "data": latest_data
            }
            write_jsonl(record)

        except KeyboardInterrupt:
            print("\n사용자 요청으로 모니터링을 중지합니다.")
            break
        except Exception as e:
            print(f"❌ 처리 중 예외 발생: {e}")
            time.sleep(2) # 예외 발생 시 잠시 대기 후 계속

    if master:
        master.close()

def write_jsonl(record: dict):
    """JSONL 형식으로 로그를 파일에 씁니다."""
    try:
        with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    except IOError as e:
        print(f"❌ 로그 파일 쓰기 오류: {e}")

if __name__ == "__main__":
    main()