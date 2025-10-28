#!/usr/bin/env python3
import docker
import time
import json
import os
import logging
from datetime import datetime, timezone
import threading
import pathlib

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)-7s] %(name)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger("DVDContainerMonitor")

# --- 로그 파일 경로 설정 ---
script_dir = pathlib.Path(__file__).parent.resolve()
bus_dir_name = os.environ.get('BUS_DIR', '../bus')
bus_dir_path = (script_dir / bus_dir_name).resolve()

# [수정] 모든 로그를 단일 'bus.log' 파일로 통합합니다.
BUS_LOG_FILENAME = 'bus.log' 
BUS_LOG_PATH = bus_dir_path / BUS_LOG_FILENAME
# --- 경로 설정 끝 ---

MONITOR_INTERVAL = int(os.environ.get('DVD_CONTAINER_MONITOR_INTERVAL', 10)) # 초 단위
# 모니터링할 컨테이너 이름 패턴 (docker-compose.yml 서비스 이름 기반)
# 환경 변수 또는 기본값 사용
CONTAINER_NAME_PATTERNS_STR = os.environ.get(
    'DVD_MONITORED_CONTAINERS', # DockerEventMonitor와 동일한 환경 변수 사용
    'flight-controller-lite,companion-computer-lite,ground-control-station-lite,'
    'simulator-lite,decoy-gateway,attacker,deception_manager,observer,rl-agent,'
    'seeker,virtual-drone'
)
CONTAINER_NAME_PATTERNS = [name.strip() for name in CONTAINER_NAME_PATTERNS_STR.split(',') if name.strip()]

# 스레드 종료 플래그
stop_event = threading.Event()

# Docker 클라이언트 초기화 함수
def init_docker_client():
    """Docker 클라이언트를 초기화하고 연결을 확인합니다."""
    try:
        client = docker.from_env()
        client.ping()
        logger.info("Docker 데몬에 성공적으로 연결되었습니다.")
        return client
    except docker.errors.DockerException as e:
        logger.critical(f"Docker 데몬 연결 실패: {e}")
        logger.critical("Docker가 실행 중이고 접근 권한이 있는지 확인하세요.")
        return None
    except Exception as e:
        logger.critical(f"Docker 클라이언트 초기화 중 예상치 못한 오류: {e}", exc_info=True)
        return None

def get_container_details(container):
    """주어진 컨테이너의 상세 정보를 추출합니다 (리소스 통계 제외)."""
    details = {}
    container_name = getattr(container, 'name', 'N/A')
    try:
        container.reload() # 최신 상태 반영
        attrs = container.attrs
        if not attrs:
            logger.warning(f"컨테이너 '{container_name}'의 속성(attrs)을 가져올 수 없습니다.")
            return None

        config = attrs.get('Config', {})
        state = attrs.get('State', {})
        network_settings = attrs.get('NetworkSettings', {})
        ports_dict = network_settings.get('Ports', {})

        port_mappings = {}
        if ports_dict:
            for container_port_proto, host_bindings in ports_dict.items():
                if host_bindings:
                    port_mappings[container_port_proto] = [f"{binding.get('HostIp', 'N/A')}:{binding.get('HostPort', 'N/A')}" for binding in host_bindings]

        details = {
            'id': container.short_id,
            'name': container_name,
            'status': state.get('Status', 'unknown'),
            'running': state.get('Running', False),
            'paused': state.get('Paused', False),
            'restarting': state.get('Restarting', False),
            'oom_killed': state.get('OOMKilled', False),
            'pid': state.get('Pid', 0),
            'exit_code': state.get('ExitCode', None),
            'error': state.get('Error', ''),
            'started_at': state.get('StartedAt', None),
            'finished_at': state.get('FinishedAt', None),
            'image': config.get('Image', 'N/A'),
            'labels': config.get('Labels', {}),
            'created': attrs.get('Created', None),
            'port_mappings': port_mappings,
        }

        # 네트워크 정보 추가
        networks = network_settings.get('Networks', {})
        details['networks'] = {}
        for net_name, net_info in networks.items():
            if net_info:
                details['networks'][net_name] = {
                    'ip_address': net_info.get('IPAddress'),
                    'mac_address': net_info.get('MacAddress'),
                }

    except docker.errors.NotFound:
        logger.warning(f"컨테이너 '{container_name}'를 찾는 중 NotFound 오류 (삭제됨?).")
        return None
    except docker.errors.APIError as api_err:
        logger.error(f"컨테이너 '{container_name}' 상세 정보 추출 중 Docker API 오류: {api_err}")
        return {'id': getattr(container, 'short_id', 'N/A'), 'name': container_name, 'status': 'api_error', 'error_message': str(api_err)}
    except Exception as e:
        logger.error(f"컨테이너 '{container_name}' 상세 정보 추출 중 예외: {e}", exc_info=True)
        return {'id': getattr(container, 'short_id', 'N/A'), 'name': container_name, 'status': 'error', 'error_message': str(e)}
    return details

def get_container_stats(container):
    """주어진 컨테이너의 리소스 사용 통계를 스트림에서 한번 읽어옵니다."""
    stats = {}
    container_name = getattr(container, 'name', 'N/A')
    try:
        # stream=False: 현재 시점 통계 한번만 가져옴
        stat_result = container.stats(stream=False)

        if not isinstance(stat_result, dict):
            logger.error(f"컨테이너 '{container_name}' 에서 예기치 않은 통계 데이터 타입 수신: {type(stat_result)}")
            return {'error_message': f'Unexpected stats data type: {type(stat_result)}'}

        stat_data = stat_result # dict 타입이므로 바로 사용

        # --- 통계 데이터 추출 및 계산 ---
        cpu_stats = stat_data.get('cpu_stats', {})
        precpu_stats = stat_data.get('precpu_stats', {})
        memory_stats = stat_data.get('memory_stats', {})
        pids_stats = stat_data.get('pids_stats', {})
        blkio_stats_data = stat_data.get('blkio_stats', {})
        networks_data = stat_data.get('networks', {})

        # CPU 사용량 계산
        cpu_percent = None
        if cpu_stats and precpu_stats and 'cpu_usage' in cpu_stats and 'system_cpu_usage' in cpu_stats \
                and 'cpu_usage' in precpu_stats and 'system_cpu_usage' in precpu_stats:
            cpu_delta = cpu_stats['cpu_usage']['total_usage'] - precpu_stats['cpu_usage']['total_usage']
            system_cpu_delta = cpu_stats['system_cpu_usage'] - precpu_stats['system_cpu_usage']

            online_cpus = cpu_stats.get('online_cpus')
            if online_cpus is None: # online_cpus가 없으면 코어 수 계산 시도
                percpu = cpu_stats['cpu_usage'].get('percpu_usage')
                number_cpus = len(percpu) if isinstance(percpu, list) else 0
            else:
                number_cpus = online_cpus

            if system_cpu_delta > 0 and cpu_delta >= 0 and number_cpus > 0:
                cpu_percent = round((cpu_delta / system_cpu_delta) * number_cpus * 100.0, 2)
            elif cpu_delta >= 0 and number_cpus > 0: # system_cpu_delta가 0이하인 경우
                 cpu_percent = 0.0 # 0%로 간주
            else:
                logger.debug(f"CPU % calc error: sys_delta={system_cpu_delta}, cpu_delta={cpu_delta}, cpus={number_cpus}")
        else:
             logger.debug(f"컨테이너 '{container_name}' CPU 통계 필드 부족.")

        # 메모리 사용량 계산
        mem_usage = memory_stats.get('usage')
        mem_limit = memory_stats.get('limit')
        mem_percent = None
        if isinstance(mem_usage, int) and isinstance(mem_limit, int) and mem_limit > 0:
            # cache 제외 계산 (cgroup v1/v2 고려)
            mem_stats_inner = memory_stats.get('stats', {})
            inactive_file = mem_stats_inner.get('total_inactive_file', mem_stats_inner.get('inactive_file', 0)) # v1 우선
            cache = mem_stats_inner.get('cache', 0)
            # 좀 더 일반적인 계산: usage - inactive_file (파일 캐시 포함된 값)
            # usage_without_cache = mem_usage - inactive_file if isinstance(inactive_file, int) else mem_usage
            # 또는 usage - cache (순수 페이지 캐시만 제외) - 이 방식이 더 일반적일 수 있음
            usage_actual = mem_usage - cache if isinstance(cache, int) else mem_usage

            mem_percent = round((max(0, usage_actual) / mem_limit) * 100.0, 2)
        elif isinstance(mem_limit, int) and mem_limit <= 0:
             logger.debug(f"컨테이너 '{container_name}' 메모리 제한 없음.")
        else:
             logger.debug(f"컨테이너 '{container_name}' 메모리 값 오류: usage={mem_usage}, limit={mem_limit}")


        # 네트워크 IO 집계
        net_io = {'rx_bytes': 0, 'tx_bytes': 0} # 필요한 필드만
        if networks_data and isinstance(networks_data, dict):
            for if_name, data in networks_data.items():
                if isinstance(data, dict):
                    net_io['rx_bytes'] += data.get('rx_bytes', 0)
                    net_io['tx_bytes'] += data.get('tx_bytes', 0)

        # 디스크 IO 집계
        blkio_stats_list = blkio_stats_data.get('io_service_bytes_recursive', [])
        disk_read_bytes = 0
        disk_write_bytes = 0
        if isinstance(blkio_stats_list, list):
            for item in blkio_stats_list:
                if isinstance(item, dict):
                    op = item.get('op','').lower()
                    value = item.get('value', 0)
                    if op == 'read': disk_read_bytes += value
                    elif op == 'write': disk_write_bytes += value

        # 최종 통계 데이터 구성
        stats = {
            'read_time': stat_data.get('read'),
            'cpu_percent': cpu_percent,
            'memory_usage_bytes': mem_usage,
            'memory_limit_bytes': mem_limit,
            'memory_percent': mem_percent,
            'network_rx_bytes': net_io['rx_bytes'],
            'network_tx_bytes': net_io['tx_bytes'],
            'disk_read_bytes': disk_read_bytes,
            'disk_write_bytes': disk_write_bytes,
            'pids': pids_stats.get('current')
        }

    except KeyError as e:
        logger.warning(f"컨테이너 '{container_name}' 통계 파싱 중 키 누락: {e}")
        stats['error_message'] = f"Missing key in stats data: {e}"
        if 'stat_data' in locals(): logger.debug(f"Problematic stats data: {stat_data}")
    except docker.errors.NotFound:
        logger.warning(f"통계 수집 중 컨테이너 '{container_name}' 없음 (삭제됨?).")
        stats['error_message'] = "Container not found during stats"
    except docker.errors.APIError as api_err:
        logger.error(f"컨테이너 '{container_name}' 통계 수집 중 API 오류: {api_err}")
        stats['error_message'] = f"Docker API error: {api_err}"
    except Exception as e:
        logger.error(f"컨테이너 '{container_name}' 통계 가져오기 중 예외: {e}", exc_info=True)
        stats['error_message'] = str(e)
    return stats


def log_to_bus(message_type, data):
    """지정된 형식으로 메시지를 bus 로그 파일에 기록합니다."""
    log_entry = {
        # [수정] DataBuilder와 CTI Agent가 'ts' 필드를 사용할 수 있도록 POSIX 타임스탬프 추가
        "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        "ts": time.time(), 
        "source": "dvd_container_monitor",
        "type": message_type,
        "data": data
    }
    try:
        BUS_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(BUS_LOG_PATH, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
    except IOError as e:
        logger.error(f"Bus 로그 파일 '{BUS_LOG_PATH}' 쓰기 실패: {e}")
    except Exception as e:
        logger.error(f"로그 기록 중 예상치 못한 오류 발생: {e}", exc_info=True)

def monitor_containers(client):
    """주기적으로 대상 Docker 컨테이너 상태 및 통계를 모니터링하고 로그를 기록합니다."""
    logger.info(f"모니터링 대상 컨테이너 이름: {CONTAINER_NAME_PATTERNS}")
    while not stop_event.is_set():
        start_time = time.monotonic()
        logger.info("컨테이너 상태 및 통계 확인 시작...")

        all_containers_data = {}
        monitored_count = 0

        try:
            # all=True 로 모든 컨테이너 가져오기
            containers = client.containers.list(all=True)
            target_containers = []

            # 이름 기준으로 대상 컨테이너 필터링
            for container in containers:
                if container.name in CONTAINER_NAME_PATTERNS:
                    target_containers.append(container)

            logger.debug(f"확인 대상 컨테이너 {len(target_containers)}개 발견.")

            for container in target_containers:
                container_name = container.name
                logger.debug(f"Processing container: {container_name} ({container.short_id})")

                details = get_container_details(container)
                if details is None: # NotFound 등 상세 정보 가져오기 실패
                    continue
                if details.get('status') == 'api_error': # API 오류 시 로그만 남기고 통계 시도 안 함
                    logger.error(f"컨테이너 '{container_name}' 상세 정보 가져오기 실패 (API 오류): {details.get('error_message')}")
                    all_containers_data[container_name] = details # 오류 정보 포함하여 기록
                    continue

                # 실행 중인 컨테이너만 통계 수집
                if details.get('running'):
                    stats = get_container_stats(container)
                    if 'error_message' in stats:
                        logger.warning(f"컨테이너 '{container_name}' 통계 수집 실패: {stats['error_message']}")
                    # 통계 정보(오류 포함)를 상세 정보에 추가
                    details['stats'] = stats
                else:
                    details['stats'] = None # 실행 중 아닐 때는 stats=None

                # [수정] 개별 컨테이너 데이터를 즉시 로깅 (DataBuilder가 개별 로그로 처리)
                # all_containers_data[container_name] = details
                
                # 'container_stats_details' 타입을 사용하여 개별 컨테이너 로그 기록
                log_to_bus("container_stats_details", details)
                monitored_count += 1

            # [수정] 루프 종료 후 한꺼번에 로깅하는 로직 제거
            # if all_containers_data:
            #     logger.info(f"총 {monitored_count}개 컨테이너 정보 수집 완료. 로깅...")
            #     log_to_bus("container_stats_details", all_containers_data)
            
            if monitored_count > 0:
                logger.info(f"총 {monitored_count}개 컨테이너 정보 수집 및 로깅 완료.")
            else:
                logger.info(f"모니터링 대상 컨테이너를 찾을 수 없습니다: {CONTAINER_NAME_PATTERNS}")

        except docker.errors.APIError as e:
            logger.error(f"Docker API 오류 발생: {e}. 다음 주기에 재시도.")
        except Exception as e:
            logger.error(f"모니터링 루프 중 예외 발생: {e}", exc_info=True)

        # 다음 모니터링까지 대기
        elapsed_time = time.monotonic() - start_time
        sleep_time = max(0.1, MONITOR_INTERVAL - elapsed_time)
        logger.info(f"사이클 완료 ({elapsed_time:.2f}초 소요). {sleep_time:.2f}초 후 다음 확인...")
        interrupted = stop_event.wait(sleep_time)
        if interrupted:
            logger.info("종료 신호 수신. 모니터링 루프 종료.")
            break


def main():
    """메인 함수: Docker 클라이언트 초기화 및 모니터링 실행."""
    logger.info("DVD Container Monitor starting...")
    logger.info(f"Monitoring interval: {MONITOR_INTERVAL}s")
    logger.info(f"Container name patterns: {CONTAINER_NAME_PATTERNS}")
    logger.info(f"Logging to: {BUS_LOG_PATH}")

    try:
        BUS_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    except Exception as dir_err:
        logger.critical(f"로그 디렉토리 생성 실패 '{BUS_LOG_PATH.parent}': {dir_err}")
        return

    client = init_docker_client()
    if client is None:
        logger.critical("Docker 연결 실패. 종료.")
        return

    try:
        monitor_containers(client)
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt 수신. 모니터 중단...")
        stop_event.set()
    except Exception as main_err:
        logger.critical(f"메인 루프에서 처리되지 않은 예외: {main_err}", exc_info=True)
        stop_event.set() # 예외 발생 시에도 종료 시도
    finally:
        logger.info("DVD Container Monitor finished.")


if __name__ == "__main__":
    main()
