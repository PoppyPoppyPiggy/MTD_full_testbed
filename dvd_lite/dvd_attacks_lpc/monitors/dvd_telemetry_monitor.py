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
LOGGING_INTERVAL_SEC = 0.2  # 5Hz logging

# ==============================================================================
# MAVLink Message Handlers
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
    
### <<< CHANGED ###
# IMU 및 기압계 데이터 핸들러 추가
def handle_raw_imu(msg, drone_state: Dict[str, Any]) -> Dict[str, Any]:
    """Handles RAW_IMU message for accelerometer and gyroscope data."""
    return {
        'xacc': getattr(msg, 'xacc', 0) / 1000.0, # mG to G
        'yacc': getattr(msg, 'yacc', 0) / 1000.0,
        'zacc': getattr(msg, 'zacc', 0) / 1000.0,
        'xgyro': getattr(msg, 'xgyro', 0) / 1000.0, # mrad/s to rad/s
        'ygyro': getattr(msg, 'ygyro', 0) / 1000.0,
        'zgyro': getattr(msg, 'zgyro', 0) / 1000.0,
    }

def handle_scaled_pressure(msg, drone_state: Dict[str, Any]) -> Dict[str, Any]:
    """Handles SCALED_PRESSURE message for barometer data."""
    return {
        'abs_pressure_hpa': getattr(msg, 'press_abs', 0),
    }
### <<< END CHANGED ###

def handle_sys_status(msg, drone_state: Dict[str, Any]) -> Dict[str, Any]:
    return {
        'cpu_load_pct': getattr(msg, 'load', 0) / 10.0,
        'errors_count1': getattr(msg, 'errors_count1', 0),
        'errors_count2': getattr(msg, 'errors_count2', 0),
    }

# Mapping of MAVLink message types to their handler functions
MESSAGE_HANDLERS: Dict[str, Callable[[Any, Dict[str, Any]], Dict[str, Any]]] = {
    'HEARTBEAT': handle_heartbeat,
    'BATTERY_STATUS': handle_battery_status,
    'GLOBAL_POSITION_INT': handle_global_position_int,
    'ATTITUDE': handle_attitude,
    'VFR_HUD': handle_vfr_hud,
    'SYS_STATUS': handle_sys_status,
    ### <<< CHANGED ###
    'RAW_IMU': handle_raw_imu,
    'SCALED_PRESSURE': handle_scaled_pressure,
    ### <<< END CHANGED ###
}

# ==============================================================================
# Main Logic
# ==============================================================================
def try_connect(uri: str) -> Optional[mavutil.mavlink_connection]:
    try:
        print(f"[*] Attempting MAVLink connection to: {uri}...")
        master = mavutil.mavlink_connection(uri, robust_parsing=True, source_system=255)
        master.wait_heartbeat(timeout=8)
        print(f"[*] MAVLink connection successful: {uri} (SysID: {master.target_system}, CompID: {master.target_component})")
        return master
    except Exception as e:
        print(f"[!] MAVLink connection failed: {e}", file=sys.stderr)
        return None

def write_jsonl(record: dict):
    try:
        with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    except IOError as e:
        print(f"[!] Error writing to log file: {e}", file=sys.stderr)

def main():
    os.makedirs(os.path.dirname(LOG_FILE_PATH), exist_ok=True)
    master = try_connect(MAVLINK_CONNECTION_STRING)
    if not master:
        print("[!] Connection failed. Retrying in 5 seconds...")
        time.sleep(5)
        main()
        return

    print(f"[*] Starting drone telemetry logging to -> {LOG_FILE_PATH} (Interval: {LOGGING_INTERVAL_SEC}s)")

    latest_data: Dict[str, Any] = {}
    drone_state: Dict[str, Any] = {'mode': 'UNKNOWN'}
    last_log_time = time.monotonic()
    last_hb_seen = time.monotonic()

    while True:
        try:
            msg = master.recv_match(blocking=False)
            if msg:
                msg_type = msg.get_type()
                
                if msg_type == 'HEARTBEAT':
                    last_hb_seen = time.monotonic()

                if msg_type in MESSAGE_HANDLERS:
                    update = MESSAGE_HANDLERS[msg_type](msg, drone_state)
                    latest_data.update(update)

                elif msg_type == 'STATUSTEXT':
                    text = getattr(msg, 'text', '').rstrip('\x00')
                    print(f"[*] [FCU STATUSTEXT] {text}")
                    write_jsonl({
                        'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                        'ts': time.time(),
                        'source': 'flight_controller',
                        'type': 'fcu_statustext',
                        'data': {'severity': mavutil.mavlink.enums['MAV_SEVERITY'][msg.severity].name, 'text': text}
                    })
            
            current_time = time.monotonic()
            if (current_time - last_log_time) >= LOGGING_INTERVAL_SEC:
                if latest_data:
                    log_entry = {
                        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                        "ts": time.time(),
                        "source": "flight_controller",
                        "type": "drone_state_detailed",
                        "data": {
                            **latest_data,
                            "mode": drone_state.get('mode', 'UNKNOWN')
                        }
                    }
                    write_jsonl(log_entry)
                last_log_time = current_time

            if (current_time - last_hb_seen) > HEARTBEAT_TIMEOUT_SEC:
                print(f"[!] MAVLink heartbeat timeout (> {HEARTBEAT_TIMEOUT_SEC}s). Reconnecting...")
                master.close()
                main()
                return

            time.sleep(0.01)

        except KeyboardInterrupt:
            print("\n[*] Monitoring stopped by user.")
            break
        except Exception as e:
            print(f"[!] An exception occurred during processing: {e}", file=sys.stderr)
            time.sleep(2)

    if master:
        master.close()

if __name__ == "__main__":
    main()