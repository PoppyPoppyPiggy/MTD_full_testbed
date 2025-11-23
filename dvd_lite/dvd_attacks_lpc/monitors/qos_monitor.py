#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
QoS Monitor
- 시스템 CPU/메모리/디스크/네트워크 + ping 기반 QoS 수집
- bus_qos.log 에 'system_qos' 타입으로 로깅
"""

import time
import json
import os
import logging
import psutil
from datetime import datetime, timezone
import subprocess
import threading
import platform

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ⭐️ cti_agent.py가 읽는 'bus_qos.log' 경로
BUS_LOG_PATH = os.environ.get(
    'BUS_LOG_PATH',
    os.path.join(os.path.dirname(__file__), '..', 'bus', 'bus_qos.log')
)

MONITOR_INTERVAL = int(os.environ.get('QOS_MONITOR_INTERVAL', 5))
PING_TARGET = os.environ.get('QOS_PING_TARGET', '8.8.8.8')
PING_COUNT = int(os.environ.get('QOS_PING_COUNT', 3))
PING_TIMEOUT = int(os.environ.get('QOS_PING_TIMEOUT', 5))

terminate_flag = threading.Event()


def get_system_resource_usage():
    """시스템 리소스 사용량 측정."""
    try:
        cpu_percent_overall = psutil.cpu_percent(interval=0.5)
        cpu_percent_per_core = psutil.cpu_percent(interval=None, percpu=True)
        cpu_times = psutil.cpu_times_percent(interval=None)

        load_avg = None
        if hasattr(psutil, 'getloadavg'):
            try:
                load_avg = psutil.getloadavg()
            except Exception:
                load_avg = None

        memory_info = psutil.virtual_memory()
        swap_info = psutil.swap_memory()

        disk_usage_root = psutil.disk_usage('/')
        disk_io = psutil.disk_io_counters()

        net_io = psutil.net_io_counters()
        process_count = len(psutil.pids())

        return {
            'cpu_percent_overall': cpu_percent_overall,
            'cpu_percent_per_core': cpu_percent_per_core,
            'cpu_times_percent': cpu_times._asdict() if cpu_times else None,
            'load_avg': load_avg,

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
            'disk_read_time_ms': getattr(disk_io, 'read_time', None),
            'disk_write_time_ms': getattr(disk_io, 'write_time', None),

            'net_bytes_sent': net_io.bytes_sent,
            'net_bytes_recv': net_io.bytes_recv,
            'net_packets_sent': net_io.packets_sent,
            'net_packets_recv': net_io.packets_recv,
            'net_errin': net_io.errin,
            'net_errout': net_io.errout,
            'net_dropin': net_io.dropin,
            'net_dropout': net_io.dropout,

            'process_count': process_count,
            'boot_time_timestamp': psutil.boot_time(),
        }
    except Exception as e:
        logger.error(f"시스템 리소스 측정 중 오류 발생: {e}", exc_info=True)
        return None


def get_network_latency(
    target=PING_TARGET,
    count=PING_COUNT,
    timeout=PING_TIMEOUT,
):
    """
    ping 기반 네트워크 지연/손실률 측정.
    {'avg_rtt_ms': float, 'packet_loss_percent': float}
    """
    result_data = {'avg_rtt_ms': None, 'packet_loss_percent': None}
    try:
        if platform.system() == 'Windows':
            command = [
                'ping',
                '-n',
                str(count),
                '-w',
                str(timeout * 1000),
                target,
            ]
        else:
            command = [
                'ping',
                '-c',
                str(count),
                '-W',
                str(timeout),
                target,
            ]

        logger.debug("Executing ping command: %s", ' '.join(command))
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout + 2,
        )

        stdout = result.stdout.strip()
        stderr = result.stderr.strip()
        logger.debug("Ping stdout:\n%s", stdout)
        if stderr:
            logger.debug("Ping stderr:\n%s", stderr)

        # 패킷 손실률
        loss_percent = None
        if platform.system() == 'Windows':
            for line in stdout.split('\n'):
                if 'loss' in line and '%' in line:
                    try:
                        loss_str = line.split('(')[1].split('%')[0]
                        loss_percent = float(loss_str)
                        result_data['packet_loss_percent'] = loss_percent
                        break
                    except (IndexError, ValueError) as e:
                        logger.warning(
                            "Windows ping 손실률 파싱 오류: %s - line: %s",
                            e,
                            line,
                        )
        else:
            for line in stdout.split('\n'):
                if 'packet loss' in line:
                    try:
                        loss_str = line.split('%')[0].split(',')[-1].strip()
                        loss_percent = float(loss_str)
                        result_data['packet_loss_percent'] = loss_percent
                        break
                    except (IndexError, ValueError) as e:
                        logger.warning(
                            "Linux/macOS ping 손실률 파싱 오류: %s - line: %s",
                            e,
                            line,
                        )

        if loss_percent is None:
            logger.warning(
                "'%s' ping 결과에서 패킷 손실률 파싱 실패.",
                target
            )

        # 평균 RTT
        avg_rtt = None
        if result.returncode == 0 or (
            loss_percent is not None and loss_percent < 100
        ):
            if platform.system() == 'Windows':
                for line in stdout.split('\n'):
                    if 'Average =' in line:
                        try:
                            avg_rtt_str = (
                                line.split('Average =')[1]
                                .strip()
                                .split('ms')[0]
                            )
                            avg_rtt = float(avg_rtt_str)
                            result_data['avg_rtt_ms'] = avg_rtt
                            break
                        except (IndexError, ValueError) as e:
                            logger.warning(
                                "Windows ping RTT 파싱 오류: %s - line: %s",
                                e,
                                line,
                            )
            else:
                for line in stdout.split('\n'):
                    if (
                        'rtt min/avg/max' in line
                        or 'round-trip min/avg/max' in line
                    ):
                        try:
                            parts = line.split('=')[1].strip().split('/')
                            if len(parts) >= 4:
                                avg_rtt = float(parts[1])
                                result_data['avg_rtt_ms'] = avg_rtt
                                break
                        except (IndexError, ValueError) as e:
                            logger.warning(
                                "Linux/macOS ping RTT 파싱 오류: %s - line: %s",
                                e,
                                line,
                            )

            if avg_rtt is None:
                logger.warning(
                    "'%s' ping 결과에서 평균 RTT 파싱 실패.",
                    target
                )
        else:
            logger.warning(
                "'%s' ping 실패 (returncode=%s, loss=%s). RTT 측정 불가.",
                target,
                result.returncode,
                loss_percent,
            )

        return result_data

    except subprocess.TimeoutExpired:
        logger.warning("'%s' ping 시간 초과 (%s초).", target, timeout)
        result_data['packet_loss_percent'] = 100.0
        return result_data
    except FileNotFoundError:
        logger.error("'ping' 명령을 찾을 수 없습니다. PATH를 확인하세요.")
        return result_data
    except Exception as e:
        logger.error(
            f"네트워크 지연 시간 측정 중 오류 발생: {e}",
            exc_info=True
        )
        return result_data


def calculate_rates(current_stats, last_stats, time_diff):
    """이전 통계와 현재 통계를 비교하여 변화율(per second) 계산."""
    rates = {}
    if not last_stats or time_diff <= 0:
        return rates

    rates['disk_read_bps'] = round(
        (
            current_stats.get('disk_read_bytes', 0)
            - last_stats.get('disk_read_bytes', 0)
        ) / time_diff
    )
    rates['disk_write_bps'] = round(
        (
            current_stats.get('disk_write_bytes', 0)
            - last_stats.get('disk_write_bytes', 0)
        ) / time_diff
    )
    rates['disk_read_iops'] = round(
        (
            current_stats.get('disk_read_count', 0)
            - last_stats.get('disk_read_count', 0)
        ) / time_diff
    )
    rates['disk_write_iops'] = round(
        (
            current_stats.get('disk_write_count', 0)
            - last_stats.get('disk_write_count', 0)
        ) / time_diff
    )

    rates['net_sent_bps'] = round(
        (
            current_stats.get('net_bytes_sent', 0)
            - last_stats.get('net_bytes_sent', 0)
        ) * 8 / time_diff
    )
    rates['net_recv_bps'] = round(
        (
            current_stats.get('net_bytes_recv', 0)
            - last_stats.get('net_bytes_recv', 0)
        ) * 8 / time_diff
    )
    rates['net_sent_pps'] = round(
        (
            current_stats.get('net_packets_sent', 0)
            - last_stats.get('net_packets_sent', 0)
        ) / time_diff
    )
    rates['net_recv_pps'] = round(
        (
            current_stats.get('net_packets_recv', 0)
            - last_stats.get('net_packets_recv', 0)
        ) / time_diff
    )

    rates['net_errin_rate'] = round(
        (
            current_stats.get('net_errin', 0)
            - last_stats.get('net_errin', 0)
        ) / time_diff
    )
    rates['net_errout_rate'] = round(
        (
            current_stats.get('net_errout', 0)
            - last_stats.get('net_errout', 0)
        ) / time_diff
    )
    rates['net_dropin_rate'] = round(
        (
            current_stats.get('net_dropin', 0)
            - last_stats.get('net_dropin', 0)
        ) / time_diff
    )
    rates['net_dropout_rate'] = round(
        (
            current_stats.get('net_dropout', 0)
            - last_stats.get('net_dropout', 0)
        ) / time_diff
    )

    for key, value in list(rates.items()):
        if value < 0:
            rates[key] = 0

    return rates


def log_to_bus(qos_data: dict):
    """QoS 데이터를 bus 로그 파일에 기록."""
    current_time_dt = datetime.now(timezone.utc)
    current_time_unix = current_time_dt.timestamp()

    log_entry = {
        "timestamp": current_time_dt.isoformat().replace('+00:00', 'Z'),
        "ts": current_time_unix,
        "source": "qos_monitor",
        "type": "system_qos",
        "data": qos_data,
    }
    try:
        os.makedirs(os.path.dirname(BUS_LOG_PATH), exist_ok=True)
        with open(BUS_LOG_PATH, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
    except IOError as e:
        logger.error(f"Bus 로그 파일 '{BUS_LOG_PATH}'에 쓰기 실패: {e}")
    except Exception as e:
        logger.error(f"로그 기록 중 예상치 못한 오류 발생: {e}")


def main():
    """주기적으로 시스템 리소스 및 네트워크 QoS 모니터링."""
    logger.info(f"QoS 모니터 시작. 로그 경로: {BUS_LOG_PATH}")
    last_resource_stats = None
    last_timestamp = time.time()

    while not terminate_flag.is_set():
        current_timestamp = time.time()
        time_diff = current_timestamp - last_timestamp

        current_resource_stats = get_system_resource_usage()
        network_quality = get_network_latency()

        if current_resource_stats:
            rates = calculate_rates(current_resource_stats, last_resource_stats, time_diff)

            qos_data = {
                'interval_seconds': round(time_diff, 2),
                'avg_rtt_ms': network_quality.get('avg_rtt_ms'),
                'packet_loss_pct': network_quality.get('packet_loss_percent'),
                'ping_target': PING_TARGET,
                'cpu_load_pct': current_resource_stats.get('cpu_percent_overall'),
                'system_resources_cumulative': current_resource_stats,
                'system_resources_rates': rates,
            }

            logger.debug(
                "현재 QoS 상태: CPU=%s%% Mem=%s%% RTT=%sms Loss=%s%%",
                qos_data.get('cpu_load_pct'),
                qos_data['system_resources_cumulative'].get('memory_percent'),
                qos_data.get('avg_rtt_ms'),
                qos_data.get('packet_loss_pct'),
            )
            log_to_bus(qos_data)

            last_resource_stats = current_resource_stats
            last_timestamp = current_timestamp
        else:
            logger.warning(
                "시스템 리소스 정보를 가져오지 못했습니다. "
                "일부 비율 계산이 부정확할 수 있습니다."
            )
            if network_quality:
                log_to_bus({
                    'avg_rtt_ms': network_quality.get('avg_rtt_ms'),
                    'packet_loss_pct': network_quality.get('packet_loss_percent'),
                    'ping_target': PING_TARGET,
                })

        elapsed_time = time.time() - current_timestamp
        sleep_time = max(0, MONITOR_INTERVAL - elapsed_time)
        logger.debug("다음 QoS 측정까지 %.2f초 대기...", sleep_time)
        terminate_flag.wait(sleep_time)

    logger.info("QoS 모니터 종료.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("사용자에 의해 모니터링 중단 신호 수신...")
        terminate_flag.set()
    finally:
        logger.info("프로그램 종료 처리 완료.")
