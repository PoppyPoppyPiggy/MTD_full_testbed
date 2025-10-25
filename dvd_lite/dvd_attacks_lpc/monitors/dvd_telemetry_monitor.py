#!/usr/bin/env python3
import time
import json
import os
import logging
from pymavlink import mavutil
from datetime import datetime
import threading

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 환경 변수 또는 기본값 설정
BUS_LOG_PATH = os.environ.get('BUS_LOG_PATH', './bus.log')
MAVLINK_SOURCE = os.environ.get('MAVLINK_SOURCE', 'udp:0.0.0.0:14550') # MAVLink 연결 주소
CONNECTION_TIMEOUT = int(os.environ.get('MAVLINK_CONNECTION_TIMEOUT', 15)) # 연결 시도 타임아웃 (초)
HEARTBEAT_TIMEOUT = int(os.environ.get('MAVLINK_HEARTBEAT_TIMEOUT', 30)) # 하트비트 최대 대기 시간 (초)
RECONNECT_DELAY = int(os.environ.get('MAVLINK_RECONNECT_DELAY', 5)) # 재연결 시도 간격 (초)

# 모니터링할 MAVLink 메시지 타입 확장 (RL, MTD, 공격 탐지에 필요할 만한 정보 추가)
TARGET_MESSAGES = [
    # 기본 상태 정보
    'HEARTBEAT',            # 시스템 상태, 모드, 타입 등
    'SYS_STATUS',           # 배터리 전압/전류, 통신 오류 등
    'SYSTEM_TIME',          # 시스템 시간 동기화 정보
    'ATTITUDE',             # Roll, Pitch, Yaw
    'GLOBAL_POSITION_INT',  # 위도, 경도, 고도 (WGS84, 정수형)
    'LOCAL_POSITION_NED',   # 로컬 NED 좌표계 위치/속도
    'VFR_HUD',              # 고도, 속도, Heading, Climb rate 등 HUD 표시 정보
    'GPS_RAW_INT',          # GPS 상태 (fix type, 위성 수 등)
    'GPS_STATUS',           # 상세 GPS 위성 정보 (SNR 등) - 빈도가 낮을 수 있음

    # 센서 정보
    'SCALED_IMU',           # 가속도, 자이로 (스케일링됨)
    'RAW_IMU',              # 원시 IMU 데이터
    'SCALED_PRESSURE',      # 기압 센서 정보
    'SENSOR_OFFSETS',       # 센서 오프셋 정보

    # 제어 및 액추에이터 정보
    'SERVO_OUTPUT_RAW',     # 서보/모터 출력 값
    'RC_CHANNELS',          # RC 수신기 입력 값 (조종기 입력)
    'RC_CHANNELS_RAW',      # 원시 RC 채널 값
    'ATTITUDE_TARGET',      # 목표 자세 (자동 조종 시)
    'POSITION_TARGET_LOCAL_NED', # 목표 위치 (자동 조종 시)

    # 임무 및 상태 관련
    'MISSION_CURRENT',      # 현재 수행 중인 임무 번호
    'NAV_CONTROLLER_OUTPUT',# 항법 제어기 출력 (목표/현재 고도, 속도 등)
    'COMMAND_ACK',          # 명령 수신 확인 (오류 확인 가능)
    'STATUSTEXT',           # 시스템 메시지, 경고, 오류 (중요 이벤트 감지)

    # 파라미터 변경 감지
    'PARAM_VALUE',          # 파라미터 값 수신/변경 시 (요청 또는 변경 시 발생)

    # 확장/사용자 정의 (필요 시)
    # 'HIGH_LATENCY2',        # 장거리 통신용 요약 정보
]

# 스레드 종료 플래그
terminate_flag = threading.Event()

def connect_mavlink(source):
    """
    MAVLink 연결을 시도하고 connection 객체를 반환합니다.
    연결 실패 시 None을 반환합니다.
    """
    try:
        logger.info(f"{source}에 MAVLink 연결 시도 중 (타임아웃: {CONNECTION_TIMEOUT}초)...")
        # source_system 파라미터 추가 시 특정 시스템 ID로 연결 가능 (기본값 255)
        connection = mavutil.mavlink_connection(source, autoreconnect=True, heartbeat_timeout=HEARTBEAT_TIMEOUT)
        # 첫 하트비트 대기 (타임아웃 설정)
        logger.info("첫 하트비트 수신 대기 중...")
        connection.wait_heartbeat(timeout=CONNECTION_TIMEOUT)
        logger.info(f"MAVLink 연결 성공! Target System ID: {connection.target_system}, Component ID: {connection.target_component}")
        return connection
    except Exception as e:
        logger.error(f"MAVLink 연결 실패: {e}")
        return None

def log_to_bus(message_type, data):
    """
    지정된 형식으로 MAVLink 메시지 데이터를 bus 로그 파일에 기록합니다.
    """
    # to_dict() 결과에서 바이트 문자열 처리
    sanitized_data = {}
    for key, value in data.items():
        if isinstance(value, bytes):
            try:
                # UTF-8 디코딩 시도, 실패 시 repr() 사용
                sanitized_data[key] = value.decode('utf-8', errors='replace')
            except UnicodeDecodeError:
                 sanitized_data[key] = repr(value) # 바이트 문자열 표현으로 저장
        elif key == 'mavpackettype': # mavpackettype은 불필요하므로 제외
            continue
        else:
            sanitized_data[key] = value

    log_entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "source": "dvd_telemetry_monitor",
        "type": f"mavlink_{message_type.lower()}", # 타입을 소문자로 통일
        "data": sanitized_data
    }
    try:
        with open(BUS_LOG_PATH, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
    except IOError as e:
        logger.error(f"Bus 로그 파일 '{BUS_LOG_PATH}'에 쓰기 실패: {e}")
    except Exception as e:
        logger.error(f"로그 기록 중 예상치 못한 오류 발생: {e}")

def request_data_stream(conn, stream_id, frequency_hz, start_stop=1):
    """
    특정 데이터 스트림을 요청하는 함수.
    Args:
        conn: MAVLink connection 객체
        stream_id: 요청할 MAV_DATA_STREAM ID (mavutil.mavlink.MAV_DATA_STREAM_*)
        frequency_hz: 요청 빈도 (Hz)
        start_stop: 1이면 시작, 0이면 중지
    """
    try:
        if hasattr(conn, 'mav') and conn.mav is not None:
             conn.mav.request_data_stream_send(
                 conn.target_system,
                 conn.target_component,
                 stream_id,
                 frequency_hz,
                 start_stop
             )
             logger.debug(f"MAV_DATA_STREAM {stream_id} 요청 (Freq: {frequency_hz}Hz, Start/Stop: {start_stop})")
        else:
            logger.warning("MAVLink 연결이 유효하지 않아 데이터 스트림을 요청할 수 없습니다.")
    except Exception as e:
        logger.error(f"데이터 스트림 요청 중 오류 발생: {e}")


def setup_data_streams(conn):
    """
    필요한 데이터 스트림들을 설정합니다. (ArduPilot/PX4 및 버전에 따라 ID가 다를 수 있음)
    """
    logger.info("필요한 데이터 스트림 설정 요청 중...")
    # 예시: ArduPilot 기준 (자주 사용되는 스트림 위주)
    # 실제 환경과 필요한 데이터에 맞게 조정 필요
    request_data_stream(conn, mavutil.mavlink.MAV_DATA_STREAM_RAW_SENSORS, 5) # IMU, 기압 등
    request_data_stream(conn, mavutil.mavlink.MAV_DATA_STREAM_EXTENDED_STATUS, 2) # GPS, 배터리, CPU 부하 등
    request_data_stream(conn, mavutil.mavlink.MAV_DATA_STREAM_RC_CHANNELS, 5) # RC 채널 값
    request_data_stream(conn, mavutil.mavlink.MAV_DATA_STREAM_POSITION, 5) # 위치 정보 (Global, Local)
    request_data_stream(conn, mavutil.mavlink.MAV_DATA_STREAM_EXTRA1, 5) # 자세(Attitude) 정보
    request_data_stream(conn, mavutil.mavlink.MAV_DATA_STREAM_EXTRA2, 2) # VFR_HUD 정보
    request_data_stream(conn, mavutil.mavlink.MAV_DATA_STREAM_EXTRA3, 2) # AHRS, 하드웨어 상태 등
    # 모든 스트림 요청 (과부하 주의)
    # request_data_stream(conn, mavutil.mavlink.MAV_DATA_STREAM_ALL, 1)


def mavlink_receive_loop(connection):
    """MAVLink 메시지를 수신하고 처리하는 루프"""
    last_heartbeat_time = time.time()
    while not terminate_flag.is_set():
        try:
            # 메시지 수신 (blocking=True, timeout 설정)
            # timeout을 짧게 설정하여 종료 플래그를 더 자주 확인할 수 있도록 함
            msg = connection.recv_match(type=TARGET_MESSAGES, blocking=True, timeout=1.0)

            if msg is None:
                # 타임아웃 발생 시 하트비트 확인
                current_time = time.time()
                if current_time - last_heartbeat_time > HEARTBEAT_TIMEOUT:
                     logger.warning(f"하트비트가 {HEARTBEAT_TIMEOUT}초 이상 수신되지 않았습니다. 연결 상태 확인 필요.")
                     # 연결 강제 종료 및 재연결 로직 트리거
                     raise ConnectionError("Heartbeat timeout")
                continue # 다음 메시지 대기

            msg_type = msg.get_type()

            # 하트비트 메시지 수신 시 마지막 수신 시간 업데이트
            if msg_type == 'HEARTBEAT':
                last_heartbeat_time = time.time()
                # logger.debug(f"Heartbeat 수신: type={msg.type}, autopilot={msg.autopilot}, base_mode={msg.base_mode}, custom_mode={msg.custom_mode}, system_status={msg.system_status}")

            msg_data = msg.to_dict()

            # 너무 많은 로그 방지를 위해 특정 메시지는 DEBUG 레벨로 로깅 (예: RAW_IMU)
            if msg_type in ['RAW_IMU', 'SCALED_IMU', 'SERVO_OUTPUT_RAW']:
                 logger.debug(f"수신 메시지 [{msg_type}]: {msg_data}")
            else:
                 logger.info(f"수신 메시지 [{msg_type}]: {msg_data}")

            log_to_bus(msg_type, msg_data)

        except ConnectionError as ce: # 하트비트 타임아웃 또는 연결 관련 오류
            logger.error(f"MAVLink 연결 오류: {ce}. 재연결 시도...")
            break # 내부 루프 종료하여 외부에서 재연결 시도
        except mavutil.mavlink.MAVError as me:
            logger.error(f"MAVLink 프로토콜 오류: {me}")
            # 프로토콜 오류는 연결 자체의 문제일 수 있으므로 재연결 시도
            break
        except Exception as e:
            # 예상치 못한 오류 발생 시 로깅 후 계속 시도 (연결 문제는 아닐 수 있음)
            logger.error(f"메시지 수신/처리 중 예상치 못한 오류 발생: {e}", exc_info=True)
            # 짧은 지연 후 계속 진행
            time.sleep(0.1)


def main():
    """
    MAVLink 연결을 관리하고, 텔레메트리 데이터를 수신하여 로그를 기록합니다.
    연결이 끊어지면 주기적으로 재연결을 시도합니다.
    """
    logger.info("DVD 텔레메트리 모니터 시작.")
    connection = None

    while not terminate_flag.is_set():
        if connection is None or not getattr(connection, 'mav', None) or connection.socket is None:
            connection = connect_mavlink(MAVLINK_SOURCE)
            if connection is None:
                logger.warning(f"{RECONNECT_DELAY}초 후 MAVLink 재연결 시도...")
                terminate_flag.wait(RECONNECT_DELAY) # 종료 신호 대기하며 sleep
                continue # 루프 처음으로 돌아가 재연결 시도
            else:
                 # 연결 성공 시 데이터 스트림 설정
                 setup_data_streams(connection)
                 last_heartbeat_time = time.time() # 연결 직후 하트비트 시간 초기화

        # 메시지 수신 루프 실행
        mavlink_receive_loop(connection)

        # mavlink_receive_loop가 종료되면 연결 문제 발생으로 간주
        logger.warning("MAVLink 수신 루프 종료됨. 연결 정리 및 재연결 시도.")
        if connection:
            try:
                connection.close()
            except Exception as close_err:
                logger.error(f"MAVLink 연결 종료 중 오류: {close_err}")
        connection = None
        logger.info(f"{RECONNECT_DELAY}초 후 재연결 시도...")
        terminate_flag.wait(RECONNECT_DELAY) # 종료 신호 대기하며 sleep

    # 종료 시 최종 정리
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
        terminate_flag.set() # 모든 스레드에 종료 신호 전달
    finally:
        # main 함수가 정상 종료되거나 예외 발생 시에도 종료 메시지 로깅
        logger.info("프로그램 종료 처리 완료.")

