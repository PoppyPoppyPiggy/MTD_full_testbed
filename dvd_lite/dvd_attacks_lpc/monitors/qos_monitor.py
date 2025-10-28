#!/usr/bin/env python3
import time
import json
import os
import logging
import psutil # 시스템 리소스 사용량 측정을 위해 psutil 사용
from datetime import datetime, timezone # [수정] timezone 추가
import subprocess # ping 실행용
import threading
import platform # platform 모듈 import 추가

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# [수정] BASE_DIR 정의
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 환경 변수 또는 기본값 설정
# [수정] 모든 로그를 단일 '../bus/bus.log' 파일로 통합합니다.
DEFAULT_BUS_LOG_PATH = os.path.abspath(os.path.join(BASE_DIR, '../bus/bus.log'))
BUS_LOG_PATH = os.environ.get('BUS_LOG_PATH', DEFAULT_BUS_LOG_PATH) 

MONITOR_INTERVAL = int(os.environ.get('QOS_MONITOR_INTERVAL', 5)) # 초 단위 모니터링 간격
PING_TARGET = os.environ.get('QOS_PING_TARGET', '8.8.8.8') # 네트워크 지연 시간 측정을 위한 대상 IP
PING_COUNT = int(os.environ.get('QOS_PING_COUNT', 3)) # ping 횟수
PING_TIMEOUT = int(os.environ.get('QOS_PING_TIMEOUT', 5)) # ping 명령 타임아웃 (초)

# 스레드 종료 플래그
terminate_flag = threading.Event()

def get_system_resource_usage():
    """
    시스템의 CPU, 메모리, 디스크, 네트워크 사용량 등 상세 정보를 측정합니다.
    """
    try:
        # CPU
        # interval=None 또는 0: non-blocking, 이전 호출 이후 사용량 반환 / interval > 0: blocking, 해당 시간 동안 측정
        cpu_percent_overall = psutil.cpu_percent(interval=0.5) # 전체 CPU 사용률 (0.5초 측정)
        cpu_percent_per_core = psutil.cpu_percent(interval=None, percpu=True) # 코어별 사용률 (non-blocking)
        cpu_times = psutil.cpu_times_percent(interval=None) # CPU 시간 사용 비율 (user, system, idle 등)
        load_avg = psutil.getloadavg() # 시스템 부하 평균 (1분, 5분, 15분) - Linux/macOS only

        # Memory
        memory_info = psutil.virtual_memory()
        swap_info = psutil.swap_memory()

        # Disk
        disk_usage_root = psutil.disk_usage('/') # 루트 디스크 기준
        disk_io = psutil.disk_io_counters() # 누적 Disk IO 카운터

        # Network (전체 인터페이스 합산)
        net_io = psutil.net_io_counters() # 누적 Net IO 카운터

        # Processes
        process_count = len(psutil.pids())

        return {
            'cpu_percent_overall': cpu_percent_overall,
            'cpu_percent_per_core': cpu_percent_per_core,
            'cpu_times_percent': cpu_times._asdict() if cpu_times else None,
            'load_avg': load_avg if hasattr(psutil, 'getloadavg') else None,

            'memory_percent': memory_info.percent,
            'memory_total_gb': round(memory_info.total / (1024**3), 2),
            'memory_used_gb': round(memory_info.used / (1024**3), 2),
            'memory_available_gb': round(memory_info.available / (1024**3), 2),

            'swap_percent': swap_info.percent,
            'swap_total_gb': round(swap_info.total / (1024**3), 2),
            'swap_used_gb': round(swap_info.used / (1024**3), 2),

            'disk_percent_root': disk_usage_root.percent,
            'disk_total_gb_root': round(disk_usage_root.total / (1024**3), 2),
            'disk_used_gb_root': round(disk_usage_root.used / (1024**3), 2),
            'disk_read_count': disk_io.read_count,
            'disk_write_count': disk_io.write_count,
            'disk_read_bytes': disk_io.read_bytes,
            'disk_write_bytes': disk_io.write_bytes,
            'disk_read_time_ms': getattr(disk_io, 'read_time', None), # 디스크 읽기 시간 (ms)
            'disk_write_time_ms': getattr(disk_io, 'write_time', None), # 디스크 쓰기 시간 (ms)

            'net_bytes_sent': net_io.bytes_sent,
            'net_bytes_recv': net_io.bytes_recv,
            'net_packets_sent': net_io.packets_sent,
            'net_packets_recv': net_io.packets_recv,
            'net_errin': net_io.errin,
            'net_errout': net_io.errout,
            'net_dropin': net_io.dropin,
            'net_dropout': net_io.dropout,

            'process_count': process_count,
            'boot_time_timestamp': psutil.boot_time() # 시스템 부팅 시간 (Unix timestamp)
        }
    except Exception as e:
        logger.error(f"시스템 리소스 측정 중 오류 발생: {e}", exc_info=True)
        return None

def get_network_latency(target=PING_TARGET, count=PING_COUNT, timeout=PING_TIMEOUT):
    """
    지정된 대상 IP로 ping을 실행하여 네트워크 지연 시간(RTT) 및 패킷 손실률을 측정합니다.
    {'avg_rtt_ms': float, 'packet_loss_percent': float} 딕셔너리를 반환합니다. 실패 시 None 또는 부분 정보 반환.
    """
    result_data = {'avg_rtt_ms': None, 'packet_loss_percent': None}
    try:
        # 운영체제별 ping 명령어 조정
        if platform.system() == 'Windows':
            # -w: timeout in ms
            command = ['ping', '-n', str(count), '-w', str(timeout * 1000), target]
        else: # Linux/macOS
            # -W: timeout in seconds
            # -i: interval (optional)
            command = ['ping', '-c', str(count), '-W', str(timeout), target]

        logger.debug(f"Executing ping command: {' '.join(command)}")
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout + 2) # 명령어 자체 타임아웃 추가

        stdout = result.stdout.strip()
        stderr = result.stderr.strip()
        logger.debug(f"Ping stdout:\n{stdout}")
        if stderr:
            logger.debug(f"Ping stderr:\n{stderr}")

        # --- 패킷 손실률 파싱 ---
        loss_percent = None
        if platform.system() == 'Windows':
            # 예: Packets: Sent = 3, Received = 3, Lost = 0 (0% loss),
            for line in stdout.split('\n'):
                if 'loss' in line and '%' in line:
                    try:
                        loss_str = line.split('(')[1].split('%')[0]
                        loss_percent = float(loss_str)
                        result_data['packet_loss_percent'] = loss_percent
                        break
                    except (IndexError, ValueError) as e:
                        logger.warning(f"Windows ping 손실률 파싱 오류: {e} - line: {line}")
        else: # Linux/macOS
            # 예: 3 packets transmitted, 3 received, 0% packet loss, time 2003ms
            for line in stdout.split('\n'):
                if 'packet loss' in line:
                    try:
                        loss_str = line.split('%')[0].split(',')[-1].strip()
                        loss_percent = float(loss_str)
                        result_data['packet_loss_percent'] = loss_percent
                        break
                    except (IndexError, ValueError) as e:
                        logger.warning(f"Linux/macOS ping 손실률 파싱 오류: {e} - line: {line}")

        if loss_percent is None:
            logger.warning(f"'{target}' ping 결과에서 패킷 손실률 파싱 실패.")

        # --- 평균 RTT 파싱 ---
        avg_rtt = None
        if result.returncode == 0 or loss_percent is not None and loss_percent < 100: # 성공 또는 부분 성공 시 RTT 파싱 시도
            if platform.system() == 'Windows':
                # 예: Minimum = 11ms, Maximum = 12ms, Average = 11ms
                for line in stdout.split('\n'):
                    if 'Average =' in line:
                        try:
                            avg_rtt_str = line.split('Average =')[1].strip().split('ms')[0]
                            avg_rtt = float(avg_rtt_str)
                            result_data['avg_rtt_ms'] = avg_rtt
                            break
                        except (IndexError, ValueError) as e:
                            logger.warning(f"Windows ping RTT 파싱 오류: {e} - line: {line}")
            else: # Linux/macOS
                # 예: rtt min/avg/max/mdev = 10.123/11.456/12.789/0.987 ms
                # 예: round-trip min/avg/max/stddev = 10.123/11.456/12.789/0.987 ms
                for line in stdout.split('\n'):
                    if 'rtt min/avg/max' in line or 'round-trip min/avg/max' in line:
                        try:
                            parts = line.split('=')[1].strip().split('/')
                            if len(parts) >= 4:
                                avg_rtt = float(parts[1]) # 평균값
                                result_data['avg_rtt_ms'] = avg_rtt
                                break
                        except (IndexError, ValueError) as e:
                            logger.warning(f"Linux/macOS ping RTT 파싱 오류: {e} - line: {line}")

            if avg_rtt is None:
                logger.warning(f"'{target}' ping 결과에서 평균 RTT 파싱 실패 (출력 확인 필요).")
        else:
             logger.warning(f"'{target}' ping 실패 (returncode={result.returncode}, loss={loss_percent}%). RTT 측정 불가.")

        return result_data

    except subprocess.TimeoutExpired:
        logger.warning(f"'{target}' ping 시간 초과 ({timeout}초).")
        result_data['packet_loss_percent'] = 100.0 # 타임아웃은 100% 손실로 간주
        return result_data
    except FileNotFoundError:
        logger.error(f"'ping' 명령을 찾을 수 없습니다. PATH를 확인하세요.")
        return result_data # 빈 결과 반환
    except Exception as e:
        logger.error(f"네트워크 지연 시간 측정 중 오류 발생: {e}", exc_info=True)
        return result_data # 빈 결과 반환

def calculate_rates(current_stats, last_stats, time_diff):
    """ 이전 통계와 현재 통계를 비교하여 변화율(per second)을 계산합니다. """
    rates = {}
    if not last_stats or time_diff <= 0:
        return rates # 이전 데이터 없거나 시간 차이 없으면 계산 불가

    # Disk IO Rates (Bytes per second)
    rates['disk_read_bps'] = round((current_stats.get('disk_read_bytes', 0) - last_stats.get('disk_read_bytes', 0)) / time_diff)
    rates['disk_write_bps'] = round((current_stats.get('disk_write_bytes', 0) - last_stats.get('disk_write_bytes', 0)) / time_diff)
    # Disk IO Rates (Operations per second)
    rates['disk_read_iops'] = round((current_stats.get('disk_read_count', 0) - last_stats.get('disk_read_count', 0)) / time_diff)
    rates['disk_write_iops'] = round((current_stats.get('disk_write_count', 0) - last_stats.get('disk_write_count', 0)) / time_diff)

    # Network Rates (Bytes per second -> Bits per second)
    rates['net_sent_bps'] = round((current_stats.get('net_bytes_sent', 0) - last_stats.get('net_bytes_sent', 0)) * 8 / time_diff)
    rates['net_recv_bps'] = round((current_stats.get('net_bytes_recv', 0) - last_stats.get('net_bytes_recv', 0)) * 8 / time_diff)
    # Network Rates (Packets per second)
    rates['net_sent_pps'] = round((current_stats.get('net_packets_sent', 0) - last_stats.get('net_packets_sent', 0)) / time_diff)
    rates['net_recv_pps'] = round((current_stats.get('net_packets_recv', 0) - last_stats.get('net_packets_recv', 0)) / time_diff)

    # Network Error Rates (Errors/Drops per second)
    rates['net_errin_rate'] = round((current_stats.get('net_errin', 0) - last_stats.get('net_errin', 0)) / time_diff)
    rates['net_errout_rate'] = round((current_stats.get('net_errout', 0) - last_stats.get('net_errout', 0)) / time_diff)
    rates['net_dropin_rate'] = round((current_stats.get('net_dropin', 0) - last_stats.get('net_dropin', 0)) / time_diff)
    rates['net_dropout_rate'] = round((current_stats.get('net_dropout', 0) - last_stats.get('net_dropout', 0)) / time_diff)

    # 음수 값 방지 (카운터 리셋 등 고려)
    for key, value in rates.items():
        if value < 0:
            rates[key] = 0

    return rates


def log_to_bus(qos_data):
    """QoS 데이터를 bus 로그 파일에 기록합니다."""
    log_entry = {
        # [수정] DataBuilder와 CTI Agent가 'ts' 필드를 사용할 수 있도록 POSIX 타임스탬프 추가
        "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        "ts": time.time(),
        "source": "qos_monitor",
        "type": "system_qos",
        "data": qos_data
    }
    try:
        # [수정] 로그 디렉토리 존재 확인
        os.makedirs(os.path.dirname(BUS_LOG_PATH), exist_ok=True)
        with open(BUS_LOG_PATH, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
    except IOError as e:
        logger.error(f"Bus 로그 파일 '{BUS_LOG_PATH}'에 쓰기 실패: {e}")
    except Exception as e:
        logger.error(f"로그 기록 중 예상치 못한 오류 발생: {e}")

def main():
    """주기적으로 시스템 리소스 및 네트워크 품질(QoS)을 모니터링하고 로그를 기록합니다."""
    logger.info("QoS 모니터 시작.")
    logger.info(f"Logging to: {BUS_LOG_PATH}") # [추가] 로그 경로 로깅
    
    # [추가] 로그 디렉토리 생성
    try:
        os.makedirs(os.path.dirname(BUS_LOG_PATH), exist_ok=True)
    except Exception as dir_err:
        logger.critical(f"로그 디렉토리 생성 실패 '{os.path.dirname(BUS_LOG_PATH)}': {dir_err}")
        return

    last_resource_stats = None
    last_timestamp = time.time()

    while not terminate_flag.is_set():
        current_timestamp = time.time()
        time_diff = current_timestamp - last_timestamp

        # 시스템 리소스 측정
        current_resource_stats = get_system_resource_usage()
        # 네트워크 지연 시간/손실률 측정
        network_quality = get_network_latency()

        if current_resource_stats:
            # 변화율 계산
            rates = calculate_rates(current_resource_stats, last_resource_stats, time_diff)

            # 로그 데이터 구성
            qos_data = {
                'interval_seconds': round(time_diff, 2),
                'system_resources_cumulative': current_resource_stats, # 현재 누적값
                'system_resources_rates': rates, # 계산된 변화율 (per second)
                'network_quality': network_quality, # ping 결과 (avg RTT, loss)
                'ping_target': PING_TARGET
            }
            logger.debug(f"현재 QoS 상태: CPU={qos_data['system_resources_cumulative'].get('cpu_percent_overall')}% Mem={qos_data['system_resources_cumulative'].get('memory_percent')}% RTT={qos_data['network_quality'].get('avg_rtt_ms')}ms Loss={qos_data['network_quality'].get('packet_loss_percent')}%")
            log_to_bus(qos_data)

            # 다음 계산을 위해 현재 상태 저장
            last_resource_stats = current_resource_stats
            last_timestamp = current_timestamp
        else:
            logger.warning("시스템 리소스 정보를 가져오지 못했습니다. 일부 비율 계산이 부정확할 수 있습니다.")
            # 리소스 정보 없이 네트워크 품질만 로깅 (선택적)
            if network_quality:
                log_to_bus({'network_quality': network_quality, 'ping_target': PING_TARGET})


        # 다음 모니터링까지 대기 (종료 플래그 확인하며)
        elapsed_time = time.time() - current_timestamp
        sleep_time = max(0, MONITOR_INTERVAL - elapsed_time)
        logger.debug(f"다음 QoS 측정까지 {sleep_time:.2f}초 대기...")
        terminate_flag.wait(sleep_time) # sleep 대신 wait 사용

    logger.info("QoS 모니터 종료.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("사용자에 의해 모니터링 중단 신호 수신...")
        terminate_flag.set()
    finally:
        logger.info("프로그램 종료 처리 완료.")
