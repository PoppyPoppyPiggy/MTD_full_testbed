# 파일 경로: dvd_lite/dvd_attacks_lpc/monitors/dvd_telemetry_monitor.py
# 설명: MTD 환경에서 올바른 수신(udpin) 방식으로 MAVLink Telemetry를 안정적으로 수집하도록 수정한 최종 버전입니다.

import os
import sys
import time
import json
import datetime
from typing import Dict, Any, Optional, Callable

from pymavlink import mavutil

# --- 경로 설정 및 유틸리티 임포트 ---
MONITORS_DIR = os.path.dirname(os.path.realpath(__file__))
LPC_DIR = os.path.dirname(MONITORS_DIR)
BUS_DIR = os.path.join(LPC_DIR, 'bus')
LOG_FILE_PATH = os.path.join(BUS_DIR, 'bus_telemetry.log')
CURRENT_ATTACK_LABEL = os.environ.get('ATTACK_NAME', 'normal')

if LPC_DIR not in sys.path:
    sys.path.insert(0, LPC_DIR)

# mtd_state_reader 임포트 (utils/mtd_state_reader.py 가정)
try:
    from utils import mtd_state_reader
except ImportError:
    print("Error: mtd_state_reader.py not found. Please ensure 'utils/mtd_state_reader.py' exists.")
    # Fallback: mtd_state_reader가 없으면 MTD 필터링 없이 실행
    class mtd_state_reader:
        @staticmethod
        def get_current_target(): return None, None
        @staticmethod
        def stop_monitor(): pass
    print("Warning: MTD state reader not found, running without MTD filtering.")


# --- MAVLink 설정 ---
HEARTBEAT_TIMEOUT_SEC = 15.0
LOGGING_INTERVAL_SEC = 0.2
# ⭐️ MAVLink 수신 포트를 고정합니다. 이 포트로 들어오는 모든 데이터를 수신 대기합니다.
MAVLINK_LISTEN_PORT = 14550

# ==============================================================================
# MAVLink Message Handlers (이전과 동일, 변경 없음)
# ==============================================================================
def handle_heartbeat(msg, drone_state: Dict[str, Any]) -> Dict[str, Any]:
    status = getattr(msg, 'system_status', 0)
    mode_name = mavutil.mode_string_v10(msg)
    drone_state['mode'] = mode_name
    return {
        'armed': (msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED) != 0,
        'mode': mode_name,
        'system_status': mavutil.mavlink.enums['MAV_STATE'][status].name if status in mavutil.mavlink.enums['MAV_STATE'] else 'UNKNOWN'
    }

def handle_battery_status(msg, drone_state: Dict[str, Any]) -> Dict[str, Any]:
    voltages = getattr(msg, 'voltages', [])
    return {
        'battery_v': voltages[0] / 1000.0 if voltages and voltages[0] < 65535 else None,
        'battery_pct': getattr(msg, 'battery_remaining', -1),
    }

def handle_global_position_int(msg, drone_state: Dict[str, Any]) -> Dict[str, Any]:
    return {
        'lat': getattr(msg, "lat", 0) / 1e7,
        'lon': getattr(msg, "lon", 0) / 1e7,
        'alt_m': getattr(msg, "alt", 0) / 1000.0,
        'relative_alt_m': getattr(msg, "relative_alt", 0) / 1000.0,
        'vx': getattr(msg, "vx", 0) / 100.0,
        'vy': getattr(msg, "vy", 0) / 100.0,
        'vz': getattr(msg, "vz", 0) / 100.0,
    }

def handle_attitude(msg, drone_state: Dict[str, Any]) -> Dict[str, Any]:
    return {
        'pitch_deg': getattr(msg, 'pitch', 0) * 180.0 / 3.14159,
        'roll_deg': getattr(msg, 'roll', 0) * 180.0 / 3.14159,
        'yaw_deg': getattr(msg, 'yaw', 0) * 180.0 / 3.14159,
    }

def handle_vfr_hud(msg, drone_state: Dict[str, Any]) -> Dict[str, Any]:
    return {
        'groundspeed_ms': getattr(msg, 'groundspeed', 0),
        'heading_deg': getattr(msg, 'heading', 0),
        'throttle_pct': getattr(msg, 'throttle', 0),
    }

def handle_raw_imu(msg, drone_state: Dict[str, Any]) -> Dict[str, Any]:
    return {
        'xacc': getattr(msg, 'xacc', 0) / 1000.0,
        'yacc': getattr(msg, 'yacc', 0) / 1000.0,
        'zacc': getattr(msg, 'zacc', 0) / 1000.0,
        'xgyro': getattr(msg, 'xgyro', 0) / 1000.0,
        'ygyro': getattr(msg, 'ygyro', 0) / 1000.0,
        'zgyro': getattr(msg, 'zgyro', 0) / 1000.0,
    }

def handle_scaled_pressure(msg, drone_state: Dict[str, Any]) -> Dict[str, Any]:
    return {
        'abs_pressure_hpa': getattr(msg, 'press_abs', 0),
    }

def handle_sys_status(msg, drone_state: Dict[str, Any]) -> Dict[str, Any]:
    return {
        'cpu_load_pct': getattr(msg, 'load', 0) / 10.0,
        'errors_count1': getattr(msg, 'errors_count1', 0),
        'errors_count2': getattr(msg, 'errors_count2', 0),
    }

MESSAGE_HANDLERS: Dict[str, Callable[[Any, Dict[str, Any]], Dict[str, Any]]] = {
    'HEARTBEAT': handle_heartbeat,
    'BATTERY_STATUS': handle_battery_status,
    'GLOBAL_POSITION_INT': handle_global_position_int,
    'ATTITUDE': handle_attitude,
    'VFR_HUD': handle_vfr_hud,
    'SYS_STATUS': handle_sys_status,
    'RAW_IMU': handle_raw_imu,
    'SCALED_PRESSURE': handle_scaled_pressure,
}

# ==============================================================================
# Main Logic (수정됨)
# ==============================================================================
def write_jsonl(record: dict):
    record['attack_label'] = CURRENT_ATTACK_LABEL
    try:
        with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    except IOError as e:
        print(f"[!] 로그 파일 쓰기 오류: {e}", file=sys.stderr)

def main():
    os.makedirs(os.path.dirname(LOG_FILE_PATH), exist_ok=True)
    
    # ⭐️ 1. MAVLink 연결 방식을 'udpin' (수신 대기)으로 변경합니다.
    connection_string = f"udpin:0.0.0.0:{MAVLINK_LISTEN_PORT}"
    master = None
    
    while master is None:
        try:
            print(f"[*] MAVLink 수신 대기 시작: {connection_string}...")
            master = mavutil.mavlink_connection(connection_string, robust_parsing=True)
            print(f"[*] MAVLink 포트({MAVLINK_LISTEN_PORT})가 성공적으로 열렸습니다. Telemetry 수신 대기 중...")
        except Exception as e:
            print(f"[!] MAVLink 포트를 여는 데 실패했습니다: {e}. 5초 후 재시도...", file=sys.stderr)
            time.sleep(5)

    latest_data: Dict[str, Any] = {}
    drone_state: Dict[str, Any] = {'mode': 'UNKNOWN'}
    last_log_time = time.monotonic()

    while True:
        try:
            # ⭐️ 2. MTD 상태 리더로부터 현재 '진짜' 타겟 IP가 무엇인지 확인합니다.
            current_target_ip, _ = mtd_state_reader.get_current_target()
            
            msg = master.recv_match(blocking=True, timeout=1)
            if not msg:
                continue

            # ⭐️ 3. 수신된 메시지의 발신지 IP가 현재 '진짜' 타겟 IP와 일치하는지 확인합니다.
            source_addr = master.recv_addr
            if current_target_ip and source_addr and source_addr[0] != current_target_ip:
                # print(f"[DEBUG] Ignored packet from {source_addr[0]}, expected {current_target_ip}")
                continue
            
            msg_type = msg.get_type()
            
            if msg_type in MESSAGE_HANDLERS:
                update = MESSAGE_HANDLERS[msg_type](msg, drone_state)
                latest_data.update(update)
            
            elif msg_type == 'STATUSTEXT':
                text = getattr(msg, 'text', '').rstrip('\x00')
                display_ip = source_addr[0] if source_addr else "UNKNOWN_IP"
                print(f"[*] [FCU STATUSTEXT from {display_ip}] {text}")
                write_jsonl({
                    'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    'ts': time.time(),
                    'source': 'flight_controller',
                    'type': 'fcu_statustext',
                    'data': {'severity': mavutil.mavlink.enums['MAV_SEVERITY'][msg.severity].name, 'text': text}
                })

            current_time = time.monotonic()
            if (current_time - last_log_time) >= LOGGING_INTERVAL_SEC and latest_data:
                log_entry = {
                    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "ts": time.time(),
                    "source": "flight_controller",
                    "type": "drone_state_detailed",
                    "data": {**latest_data, "mode": drone_state.get('mode', 'UNKNOWN')}
                }
                write_jsonl(log_entry)
                latest_data = {} # 로그 기록 후 초기화
                last_log_time = current_time

        except KeyboardInterrupt:
            print("\n[*] 사용자 요청으로 모니터링 중지.")
            break
        except Exception as e:
            print(f"[!] 처리 중 예외 발생: {e}", file=sys.stderr)
            time.sleep(2)

    if master:
        master.close()
    mtd_state_reader.stop_monitor()
    print("[*] Telemetry 모니터링 종료.")

if __name__ == "__main__":
    main()
