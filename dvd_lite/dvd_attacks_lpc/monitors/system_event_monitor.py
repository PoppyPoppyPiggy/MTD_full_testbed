#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Docker Event Monitor
- docker events 스트림을 읽어 주요 컨테이너 이벤트를 bus_system_events.log 로 로깅
"""

import time
import json
import os
import logging
from datetime import datetime, timezone
import threading
import pathlib
import docker  # Docker SDK

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)-7s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("DockerEventMonitor")

# --- 로그 파일 경로 설정 ---
script_dir = pathlib.Path(__file__).parent.resolve()
bus_dir_name = os.environ.get('BUS_DIR', '../bus')
bus_dir_path = (script_dir / bus_dir_name).resolve()

# ⭐️ cti_agent.py가 읽는 'bus_system_events.log'로 파일명 고정
BUS_LOG_FILENAME = 'bus_system_events.log'
BUS_LOG_PATH = bus_dir_path / BUS_LOG_FILENAME
# --- 경로 설정 끝 ---

MONITOR_INTERVAL = int(os.environ.get('DOCKER_EVENT_MONITOR_INTERVAL', 2))

RELEVANT_CONTAINER_NAMES_STR = os.environ.get(
    'DVD_MONITORED_CONTAINERS',
    'flight-controller-lite,companion-computer-lite,ground-control-station-lite,'
    'simulator-lite,decoy-gateway,attacker,deception_manager,observer,rl-agent,'
    'seeker,virtual-drone'
)
RELEVANT_CONTAINER_NAMES = [
    name.strip()
    for name in RELEVANT_CONTAINER_NAMES_STR.split(',')
    if name.strip()
]

terminate_flag = threading.Event()


def log_to_bus(event_data: dict):
    """Docker 이벤트를 지정된 bus 로그 파일에 기록."""
    if not event_data:
        return

    current_time_dt = datetime.now(timezone.utc)
    current_time_unix = current_time_dt.timestamp()

    log_entry = {
        "timestamp": current_time_dt.isoformat().replace('+00:00', 'Z'),
        "ts": current_time_unix,
        "source": "docker_event_monitor",
        "type": "docker_event",
        "data": event_data,
    }
    try:
        BUS_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(BUS_LOG_PATH, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
        logger.debug(
            "Logged Docker event to '%s': %s for %s",
            BUS_LOG_PATH,
            event_data.get('status'),
            event_data.get('name'),
        )
    except IOError as e:
        logger.error(f"Bus 로그 파일 '{BUS_LOG_PATH}' 쓰기 실패: {e}")
    except Exception as e:
        logger.error(
            f"로그 기록 중 예상치 못한 오류 발생: {e}",
            exc_info=True
        )


def monitor_docker_events():
    """Docker 데몬 이벤트를 스트리밍하고 관련 컨테이너 이벤트를 로깅."""
    try:
        client = docker.from_env()
        client.ping()
        logger.info("Docker 데몬에 성공적으로 연결되었습니다.")
    except docker.errors.DockerException as e:
        logger.critical(f"Docker 데몬 연결 실패: {e}")
        logger.critical("Docker가 실행 중이고 접근 권한이 있는지 확인하세요.")
        return
    except Exception as e:
        logger.critical(
            f"Docker 클라이언트 초기화 중 오류: {e}",
            exc_info=True
        )
        return

    logger.info(f"모니터링 대상 컨테이너 이름: {RELEVANT_CONTAINER_NAMES}")

    event_stream = None
    try:
        event_stream = client.events(decode=True)
        logger.info("Docker 이벤트 스트리밍 시작...")

        for event in event_stream:
            if terminate_flag.is_set():
                logger.info("종료 신호 수신. 이벤트 스트리밍 중단.")
                break

            try:
                event_type = event.get('Type')
                event_status = event.get('status')
                actor = event.get('Actor', {})
                attributes = actor.get('Attributes', {})
                container_name = attributes.get('name')

                if event_type == 'container' and container_name in RELEVANT_CONTAINER_NAMES:
                    logger.info(
                        "관련 컨테이너 이벤트 감지: Name='%s', Status='%s'",
                        container_name,
                        event_status,
                    )
                    simplified_event = {
                        'event_time': event.get('time'),
                        'timeNano': event.get('timeNano'),
                        'status': event_status,
                        'id': actor.get('ID'),
                        'image': attributes.get('image'),
                        'name': container_name,
                        'health_status': (
                            attributes.get('health_status')
                            if event_status == 'health_status'
                            else None
                        ),
                    }
                    log_to_bus(simplified_event)

            except Exception as e:
                logger.error(
                    f"이벤트 처리 중 오류 발생: {e}",
                    exc_info=True
                )
                logger.debug("처리 실패한 이벤트 원본: %s", event)

    except docker.errors.APIError as api_err:
        logger.error(f"Docker API 오류 발생: {api_err}. 이벤트 스트리밍 중단.")
    except Exception as e:
        logger.error(
            f"이벤트 스트림 처리 중 예외 발생: {e}",
            exc_info=True
        )
    finally:
        if event_stream and hasattr(event_stream, 'close'):
            try:
                event_stream.close()
                logger.info("Docker 이벤트 스트림 종료.")
            except Exception as close_err:
                logger.error("이벤트 스트림 종료 중 오류: %s", close_err)
        logger.info("Docker 이벤트 모니터링 루프 종료.")


def main():
    """Docker 이벤트 모니터링을 시작."""
    logger.info("Docker Event Monitor starting...")
    logger.info(f"Logging to: {BUS_LOG_PATH}")

    try:
        BUS_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        logger.info("Ensured bus log directory exists: %s", BUS_LOG_PATH.parent)
    except Exception as dir_err:
        logger.critical(
            "Failed to create bus log directory '%s': %s. Exiting.",
            BUS_LOG_PATH.parent,
            dir_err,
        )
        return

    monitor_docker_events()
    logger.info("Docker Event Monitor finished.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received. Initiating shutdown...")
        terminate_flag.set()
    finally:
        if not terminate_flag.is_set():
            terminate_flag.set()
        logger.info("Docker Event Monitor shutdown process complete.")
