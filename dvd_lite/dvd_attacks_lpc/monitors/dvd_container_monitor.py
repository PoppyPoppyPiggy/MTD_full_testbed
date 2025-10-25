#!/usr/bin/env python3
import docker
import time
import json
import os
import logging
from datetime import datetime
import threading # 컨테이너 통계 수집을 위한 스레딩

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 환경 변수 또는 기본값 설정
BUS_LOG_PATH = os.environ.get('BUS_LOG_PATH', './bus.log')
MONITOR_INTERVAL = int(os.environ.get('DVD_CONTAINER_MONITOR_INTERVAL', 10)) # 초 단위 (통계 수집 고려하여 간격 조정)
CONTAINER_NAME_PATTERNS = os.environ.get('DVD_CONTAINER_NAME_PATTERNS', 'dvd,mtd,companion,sitl').split(',') # 모니터링할 컨테이너 이름 패턴

# Docker 클라이언트 초기화 함수
def init_docker_client():
    """Docker 클라이언트를 초기화하고 연결을 확인합니다."""
    try:
        client = docker.from_env()
        client.ping() # Docker 데몬 연결 확인
        logger.info("Docker 데몬에 성공적으로 연결되었습니다.")
        return client
    except docker.errors.DockerException as e:
        logger.error(f"Docker 데몬 연결 실패: {e}")
        logger.error("Docker가 실행 중이고 현재 사용자에게 권한이 있는지 확인하세요.")
        return None
    except Exception as e:
        logger.error(f"Docker 클라이언트 초기화 중 예상치 못한 오류: {e}")
        return None

def get_container_details(container):
    """주어진 컨테이너의 상세 정보를 추출합니다."""
    details = {}
    try:
        container.reload() # 최신 상태 반영
        attrs = container.attrs
        config = attrs.get('Config', {})
        state = attrs.get('State', {})
        network_settings = attrs.get('NetworkSettings', {})
        ports = network_settings.get('Ports', {})

        details = {
            'id': container.short_id,
            'name': container.name,
            'status': state.get('Status'),
            'running': state.get('Running'),
            'paused': state.get('Paused'),
            'restarting': state.get('Restarting'),
            'oom_killed': state.get('OOMKilled'),
            'pid': state.get('Pid'),
            'exit_code': state.get('ExitCode'),
            'error': state.get('Error'),
            'started_at': state.get('StartedAt'),
            'finished_at': state.get('FinishedAt'),
            'image': config.get('Image'),
            'labels': config.get('Labels', {}),
            'env': config.get('Env', []),
            'cmd': config.get('Cmd', []),
            'entrypoint': config.get('Entrypoint', []),
            'created': attrs.get('Created'),
            'ip_address': network_settings.get('IPAddress'),
            'ports': ports, # 포트 매핑 정보
        }
        # 네트워크 상세 정보 추가 (연결된 네트워크별 IP)
        networks = network_settings.get('Networks', {})
        details['networks'] = {}
        for net_name, net_info in networks.items():
            details['networks'][net_name] = {
                'network_id': net_info.get('NetworkID'),
                'endpoint_id': net_info.get('EndpointID'),
                'gateway': net_info.get('Gateway'),
                'ip_address': net_info.get('IPAddress'),
                'ip_prefix_len': net_info.get('IPPrefixLen'),
                'ipv6_gateway': net_info.get('IPv6Gateway'),
                'global_ipv6_address': net_info.get('GlobalIPv6Address'),
                'mac_address': net_info.get('MacAddress'),
            }

    except docker.errors.NotFound:
        logger.warning(f"컨테이너 '{container.name}'를 찾을 수 없습니다 (삭제되었을 수 있음).")
        return None
    except Exception as e:
        logger.error(f"컨테이너 '{container.name}' 상세 정보 추출 중 오류: {e}")
        # 기본 정보라도 반환 시도
        return {
            'id': getattr(container, 'short_id', 'N/A'),
            'name': getattr(container, 'name', 'N/A'),
            'error_message': str(e)
        }
    return details


def get_container_stats(container):
    """주어진 컨테이너의 리소스 사용 통계를 스트림에서 한번 읽어옵니다."""
    stats = {}
    try:
        # stream=False: 현재 시점의 통계 한번만 가져옴
        # decode=True: JSON 객체로 받음
        stat_data = container.stats(stream=False, decode=True)

        # CPU 사용량 계산
        cpu_delta = stat_data['cpu_stats']['cpu_usage']['total_usage'] - stat_data['precpu_stats']['cpu_usage']['total_usage']
        system_cpu_delta = stat_data['cpu_stats']['system_cpu_usage'] - stat_data['precpu_stats']['system_cpu_usage']
        number_cpus = stat_data['cpu_stats'].get('online_cpus', len(stat_data['cpu_stats']['cpu_usage'].get('percpu_usage', [0]))) # CPU 코어 수

        cpu_percent = 0.0
        if system_cpu_delta > 0 and cpu_delta > 0 and number_cpus > 0:
            cpu_percent = (cpu_delta / system_cpu_delta) * number_cpus * 100.0

        # 메모리 사용량
        mem_usage = stat_data['memory_stats'].get('usage', 0)
        mem_limit = stat_data['memory_stats'].get('limit', 0)
        mem_percent = 0.0
        if mem_limit > 0:
            mem_percent = (mem_usage / mem_limit) * 100.0

        # 네트워크 IO
        net_io = {'rx_bytes': 0, 'tx_bytes': 0, 'rx_packets': 0, 'tx_packets': 0, 'rx_errors': 0, 'tx_errors': 0, 'rx_dropped': 0, 'tx_dropped': 0}
        if 'networks' in stat_data:
            for if_name, data in stat_data['networks'].items():
                net_io['rx_bytes'] += data.get('rx_bytes', 0)
                net_io['tx_bytes'] += data.get('tx_bytes', 0)
                net_io['rx_packets'] += data.get('rx_packets', 0)
                net_io['tx_packets'] += data.get('tx_packets', 0)
                net_io['rx_errors'] += data.get('rx_errors', 0)
                net_io['tx_errors'] += data.get('tx_errors', 0)
                net_io['rx_dropped'] += data.get('rx_dropped', 0)
                net_io['tx_dropped'] += data.get('tx_dropped', 0)

        # 디스크 IO (Block IO)
        blkio_stats = stat_data.get('blkio_stats', {}).get('io_service_bytes_recursive', [])
        disk_read_bytes = 0
        disk_write_bytes = 0
        for item in blkio_stats:
            if item.get('op') == 'Read':
                disk_read_bytes += item.get('value', 0)
            elif item.get('op') == 'Write':
                disk_write_bytes += item.get('value', 0)

        stats = {
            'read_time': stat_data.get('read'),
            'cpu_percent': round(cpu_percent, 2),
            'memory_usage_bytes': mem_usage,
            'memory_limit_bytes': mem_limit,
            'memory_percent': round(mem_percent, 2),
            'network_io': net_io,
            'disk_read_bytes': disk_read_bytes,
            'disk_write_bytes': disk_write_bytes,
            'pids': stat_data.get('pids_stats', {}).get('current', 0) # 현재 프로세스/스레드 수
        }

    except KeyError as e:
        logger.debug(f"컨테이너 '{container.name}' 통계 데이터 파싱 중 키 오류: {e}")
        stats['error_message'] = f"KeyError: {e}"
    except Exception as e:
        logger.error(f"컨테이너 '{container.name}' 통계 가져오기 중 오류: {e}")
        stats['error_message'] = str(e)
    return stats


def log_to_bus(message_type, data):
    """지정된 형식으로 메시지를 bus 로그 파일에 기록합니다."""
    log_entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "source": "dvd_container_monitor",
        "type": message_type,
        "data": data
    }
    try:
        with open(BUS_LOG_PATH, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
    except IOError as e:
        logger.error(f"Bus 로그 파일 '{BUS_LOG_PATH}'에 쓰기 실패: {e}")
    except Exception as e:
        logger.error(f"로그 기록 중 예상치 못한 오류 발생: {e}")

def monitor_containers(client, stop_event):
    """주기적으로 Docker 컨테이너 상태 및 통계를 모니터링하고 로그를 기록하는 메인 루프."""
    while not stop_event.is_set():
        start_time = time.time()
        all_containers_info = {}
        try:
            # 필터링 조건 없이 모든 컨테이너 목록 가져오기 (종료된 컨테이너 포함)
            containers = client.containers.list(all=True)
            monitored_count = 0
            for container in containers:
                # 지정된 이름 패턴과 일치하는지 확인
                if any(pattern in container.name for pattern in CONTAINER_NAME_PATTERNS):
                    details = get_container_details(container)
                    if details:
                         # 실행 중인 컨테이너에 대해서만 통계 수집 시도
                         if details.get('running'):
                              stats = get_container_stats(container)
                              details['stats'] = stats # 상세 정보에 통계 정보 추가
                         else:
                              details['stats'] = {'message': 'Container not running'}

                         all_containers_info[container.name] = details
                         monitored_count += 1

            if all_containers_info:
                logger.debug(f"현재 모니터링된 컨테이너 정보: {len(all_containers_info)}개")
                log_to_bus("container_status_details", all_containers_info)
            else:
                logger.warning(f"지정된 패턴 {CONTAINER_NAME_PATTERNS}과(와) 일치하는 컨테이너를 찾을 수 없습니다.")

        except docker.errors.APIError as e:
            logger.error(f"Docker API 오류 발생: {e}. Docker 데몬 상태 확인 필요.")
            # API 오류 발생 시 잠시 대기 후 재시도
            time.sleep(MONITOR_INTERVAL * 2)
            # 클라이언트 재 초기화 시도
            client = init_docker_client()
            if client is None:
                logger.error("Docker 클라이언트 재 초기화 실패. 모니터링 중단.")
                break # 루프 종료
            continue # 다음 루프 실행
        except Exception as e:
            logger.error(f"컨테이너 모니터링 루프 중 예상치 못한 오류 발생: {e}")
            # 오류 발생 시 잠시 대기
            time.sleep(MONITOR_INTERVAL)

        # 다음 모니터링까지 대기
        elapsed_time = time.time() - start_time
        sleep_time = max(0, MONITOR_INTERVAL - elapsed_time)
        logger.debug(f"다음 컨테이너 상태 확인까지 {sleep_time:.2f}초 대기...")
        # stop_event를 사용하여 sleep 중에도 종료 신호를 받을 수 있도록 함
        stop_event.wait(sleep_time)


def main():
    """메인 함수: Docker 클라이언트 초기화 및 모니터링 스레드 시작/관리."""
    logger.info("DVD 컨테이너 모니터 시작.")
    client = init_docker_client()

    if client is None:
        return # Docker 연결 실패 시 종료

    stop_event = threading.Event()
    monitor_thread = threading.Thread(target=monitor_containers, args=(client, stop_event), daemon=True)
    monitor_thread.start()

    try:
        # 메인 스레드는 모니터링 스레드가 종료될 때까지 대기
        monitor_thread.join()
    except KeyboardInterrupt:
        logger.info("사용자에 의해 모니터링이 중단되었습니다. 종료 신호 전송...")
        stop_event.set() # 스레드에 종료 신호 전달
        monitor_thread.join(timeout=5) # 스레드 종료 대기 (최대 5초)
    finally:
        logger.info("DVD 컨테이너 모니터 종료.")


if __name__ == "__main__":
    main()

