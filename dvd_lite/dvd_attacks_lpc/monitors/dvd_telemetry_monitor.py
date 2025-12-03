#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
DVD Telemetry Monitor (Fixed)
- MAVLink 텔레메트리 메시지 수신
- CTI 에이전트가 읽는 bus_telemetry.log로 로깅
- Python 3.12+ 호환 (deprecated utcfromtimestamp 수정)
"""

import time
import json
import os
import logging
from pymavlink import mavutil
from datetime import datetime, timezone
import threading

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ⭐️ cti_agent.py가 읽는 'bus_telemetry.log'로 경로 고정
BUS_LOG_PATH = os.environ.get(
    'BUS_LOG_PATH',
    os.path.join(os.path.dirname(__file__), '..', 'bus', 'bus_telemetry.log')
)

MAVLINK_SOURCE = os.environ.get('MAVLINK_SOURCE', 'udp:0.0.0.0:14550')
CONNECTION_TIMEOUT = int(os.environ.get('MAVLINK_CONNECTION_TIMEOUT', 15))
HEARTBEAT_TIMEOUT = int(os.environ.get('MAVLINK_HEARTBEAT_TIMEOUT', 30))
RECONNECT_DELAY = int(os.environ.get('MAVLINK_RECONNECT_DELAY', 5))

# 모니터링할 MAVLink 메시지 타입
TARGET_MESSAGES = [
    'HEARTBEAT',
    'SYS_STATUS',
    'SYSTEM_TIME',
    'ATTITUDE',
    'GLOBAL_POSITION_INT',
    'LOCAL_POSITION_NED',
    'VFR_HUD',
    'GPS_RAW_INT',
    'GPS_STATUS',
    'SCALED_IMU',
    'RAW_IMU',
    'SCALED_PRESSURE',
    'SENSOR_OFFSETS',
    'SERVO_OUTPUT_RAW',
    'RC_CHANNELS',
    'RC_CHANNELS_RAW',
    'ATTITUDE_TARGET',
    'POSITION_TARGET_LOCAL_NED',
    'MISSION_CURRENT',
    'NAV_CONTROLLER_OUTPUT',
    'COMMAND_ACK',
    'STATUSTEXT',
    'PARAM_VALUE',
]

# 종료 플래그
terminate_flag = threading.Event()


def connect_mavlink(source: str):
    """
    MAVLink 연결을 시도하고 connection 객체를 반환.
    실패 시 None.
    """
    try:
        logger.info(f"{source}에 MAVLink 연결 시도 중 (타임아웃: {CONNECTION_TIMEOUT}초)...")
        connection = mavutil.mavlink_connection(
            source,
            autoreconnect=True,
            heartbeat_timeout=HEARTBEAT_TIMEOUT,
        )
        logger.info("첫 하트비트 수신 대기 중...")
        connection.wait_heartbeat(timeout=CONNECTION_TIMEOUT)
        logger.info(
            "MAVLink 연결 성공! Target System ID: %s, Component ID: %s",
            connection.target_system,
            connection.target_component,
        )
        return connection
    except Exception as e:
        logger.error(f"MAVLink 연결 실패: {e}")
        return None


def log_to_bus(message_type: str, data: dict):
    """
    지정된 형식으로 MAVLink 메시지 데이터를 bus 로그 파일에 기록.
    """
    sanitized_data = {}
    for key, value in data.items():
        if isinstance(value, bytes):
            sanitized_data[key] = value.decode('utf-8', errors='replace')
        elif key == 'mavpackettype':
            continue
        else:
            sanitized_data[key] = value

    current_time = time.time()
    # ✅ Python 3.12+ 호환: utcfromtimestamp → fromtimestamp with timezone.utc
    current_time_dt = datetime.fromtimestamp(current_time, timezone.utc)
    
    log_entry = {
        "timestamp": current_time_dt.isoformat().replace('+00:00', 'Z'),
        "ts": current_time,  # Unix timestamp
        "source": "dvd_telemetry_monitor",
        "type": f"mavlink_{message_type.lower()}",
        "data": sanitized_data,
    }
    try:
        os.makedirs(os.path.dirname(BUS_LOG_PATH), exist_ok=True)
        with open(BUS_LOG_PATH, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
    except IOError as e:
        logger.error(f"Bus 로그 파일 '{BUS_LOG_PATH}'에 쓰기 실패: {e}")
    except Exception as e:
        logger.error(f"로그 기록 중 예상치 못한 오류 발생: {e}")


def request_data_stream(conn, stream_id, frequency_hz, start_stop=1):
    """
    특정 데이터 스트림을 요청하는 함수.
    """
    try:
        if hasattr(conn, 'mav') and conn.mav is not None:
            conn.mav.request_data_stream_send(
                conn.target_system,
                conn.target_component,
                stream_id,
                frequency_hz,
                start_stop,
            )
            logger.debug(
                "MAV_DATA_STREAM %s 요청 (Freq: %sHz, Start/Stop: %s)",
                stream_id,
                frequency_hz,
                start_stop,
            )
        else:
            logger.warning("MAVLink 연결이 유효하지 않아 데이터 스트림을 요청할 수 없습니다.")
    except Exception as e:
        logger.error(f"데이터 스트림 요청 중 오류 발생: {e}")


def setup_data_streams(conn):
    """
    필요한 데이터 스트림 요청.
    (ArduPilot 기준, 환경에 따라 조정 가능)
    """
    logger.info("필요한 데이터 스트림 설정 요청 중...")
    request_data_stream(conn, mavutil.mavlink.MAV_DATA_STREAM_RAW_SENSORS, 5)
    request_data_stream(conn, mavutil.mavlink.MAV_DATA_STREAM_EXTENDED_STATUS, 2)
    request_data_stream(conn, mavutil.mavlink.MAV_DATA_STREAM_RC_CHANNELS, 5)
    request_data_stream(conn, mavutil.mavlink.MAV_DATA_STREAM_POSITION, 5)
    request_data_stream(conn, mavutil.mavlink.MAV_DATA_STREAM_EXTRA1, 5)
    request_data_stream(conn, mavutil.mavlink.MAV_DATA_STREAM_EXTRA2, 2)
    request_data_stream(conn, mavutil.mavlink.MAV_DATA_STREAM_EXTRA3, 2)


def mavlink_receive_loop(connection):
    """MAVLink 메시지를 수신하고 처리하는 루프."""
    last_heartbeat_time = time.time()

    while not terminate_flag.is_set():
        try:
            msg = connection.recv_match(
                type=TARGET_MESSAGES,
                blocking=True,
                timeout=1.0,
            )

            if msg is None:
                current_time = time.time()
                if current_time - last_heartbeat_time > HEARTBEAT_TIMEOUT:
                    logger.warning(
                        f"하트비트가 {HEARTBEAT_TIMEOUT}초 이상 수신되지 않았습니다. "
                        "연결 상태 확인 필요."
                    )
                    raise ConnectionError("Heartbeat timeout")
                continue

            msg_type = msg.get_type()

            if msg_type == 'HEARTBEAT':
                last_heartbeat_time = time.time()

            msg_data = msg.to_dict()
            log_data = {}

            if msg_type == 'GLOBAL_POSITION_INT':
                log_data['lat'] = msg_data.get('lat') / 1e7
                log_data['lon'] = msg_data.get('lon') / 1e7
                log_data['alt_m'] = msg_data.get('alt') / 1000.0
                log_data['relative_alt_m'] = msg_data.get('relative_alt') / 1000.0
                log_data['vx'] = msg_data.get('vx') / 100.0
                log_data['vy'] = msg_data.get('vy') / 100.0
                log_data['vz'] = msg_data.get('vz') / 100.0

            elif msg_type == 'ATTITUDE':
                log_data['pitch_deg'] = msg_data.get('pitch') * 180.0 / 3.1415926535
                log_data['roll_deg'] = msg_data.get('roll') * 180.0 / 3.1415926535
                log_data['yaw_deg'] = msg_data.get('yaw') * 180.0 / 3.1415926535

            elif msg_type == 'VFR_HUD':
                log_data['groundspeed_ms'] = msg_data.get('groundspeed')

            elif msg_type == 'SYS_STATUS':
                log_data['battery_v'] = msg_data.get('voltage_battery') / 1000.0
                log_data['battery_pct'] = msg_data.get('battery_remaining')

            elif msg_type == 'HEARTBEAT':
                log_data['mode'] = mavutil.mode_string_v10(msg)

            elif msg_type == 'SCALED_IMU':
                log_data['xacc'] = msg_data.get('xacc') / 1000.0
                log_data['yacc'] = msg_data.get('yacc') / 1000.0
                log_data['zacc'] = msg_data.get('zacc') / 1000.0

            else:
                log_data = msg_data

            if msg_type in ['RAW_IMU', 'SCALED_IMU', 'SERVO_OUTPUT_RAW']:
                logger.debug(f"수신 메시지 [{msg_type}]: {log_data}")
            else:
                logger.info(f"수신 메시지 [{msg_type}]: {log_data}")

            log_to_bus(msg_type, log_data)

        except ConnectionError as ce:
            logger.error(f"MAVLink 연결 오류: {ce}. 재연결 시도...")
            break
        except mavutil.mavlink.MAVError as me:
            logger.error(f"MAVLink 프로토콜 오류: {me}")
            break
        except Exception as e:
            logger.error(
                f"메시지 수신/처리 중 예상치 못한 오류 발생: {e}",
                exc_info=True
            )
            time.sleep(0.1)


def main():
    """
    MAVLink 연결을 관리하고, 텔레메트리 데이터를 수신하여 로그를 기록.
    연결이 끊어지면 주기적으로 재연결을 시도.
    """
    logger.info(f"DVD 텔레메트리 모니터 시작. 로그 경로: {BUS_LOG_PATH}")
    connection = None

    while not terminate_flag.is_set():
        if (
            connection is None
            or not getattr(connection, 'mav', None)
            or getattr(connection, 'socket', None) is None
        ):
            connection = connect_mavlink(MAVLINK_SOURCE)
            if connection is None:
                logger.warning(
                    f"{RECONNECT_DELAY}초 후 MAVLink 재연결 시도..."
                )
                terminate_flag.wait(RECONNECT_DELAY)
                continue

            setup_data_streams(connection)

        mavlink_receive_loop(connection)

        logger.warning(
            "MAVLink 수신 루프 종료됨. 연결 정리 및 재연결 시도."
        )
        if connection:
            try:
                connection.close()
            except Exception as close_err:
                logger.error(f"MAVLink 연결 종료 중 오류: {close_err}")
        connection = None
        logger.info(f"{RECONNECT_DELAY}초 후 재연결 시도...")
        terminate_flag.wait(RECONNECT_DELAY)

    if connection:
        try:
            connection.close()
            logger.info("MAVLink 연결 종료됨.")
        except Exception as e:
            logger.error(f"종료 시 MAVLink 연결 종료 중 오류: {e}")
    logger.info("DVD 텔레메트리 모니터 종료.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("사용자에 의해 모니터링 중단 신호 수신...")
        terminate_flag.set()
    finally:
        logger.info("프로그램 종료 처리 완료.")