#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Network Traffic Monitor (Pyshark 기반)
- Docker 브리지 인터페이스에서 패킷 캡처
- 개별 패킷을 bus_network.log 에 'network_packet' 타입으로 로깅
"""

import pyshark
import json
import time
import os
import logging
from datetime import datetime, timezone
import queue
import threading
import pathlib
import traceback
import subprocess
import signal

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)-7s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("NetworkTrafficMonitor")

# 경로/환경 변수
script_dir = pathlib.Path(__file__).parent.resolve()
bus_dir_name = os.environ.get('BUS_DIR', '../bus')
bus_dir_path = (script_dir / bus_dir_name).resolve()

# ⭐️ cti_agent.py가 읽는 'bus_network.log'로 파일명 고정
BUS_LOG_FILENAME = 'bus_network.log'
BUS_LOG_PATH = bus_dir_path / BUS_LOG_FILENAME

CAPTURE_INTERFACE = os.environ.get('NETWORK_CAPTURE_INTERFACE', 'br-simulator')
PACKET_BUFFER_SIZE = int(os.environ.get('NETWORK_PACKET_BUFFER_SIZE', 100))
LOGGING_INTERVAL = int(os.environ.get('NETWORK_LOGGING_INTERVAL', 5))
BPF_FILTER = os.environ.get('NETWORK_BPF_FILTER', None)

packet_queue = queue.Queue(maxsize=PACKET_BUFFER_SIZE * 2)
stop_event = threading.Event()
logging_thread = None


def log_to_bus(message_type: str, data):
    current_time_dt = datetime.now(timezone.utc)
    current_time_unix = current_time_dt.timestamp()

    log_entry = {
        "timestamp": current_time_dt.isoformat().replace('+00:00', 'Z'),
        "ts": current_time_unix,
        "source": "network_traffic_monitor",
        "type": message_type,
        "data": data,
    }
    try:
        BUS_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(BUS_LOG_PATH, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
    except IOError as e:
        logger.error(f"Bus 로그 파일 '{BUS_LOG_PATH}'에 쓰기 실패: {e}")
    except Exception as e:
        logger.error(
            f"로그 기록 중 예상치 못한 오류 발생: {e}",
            exc_info=True
        )


def extract_packet_details(packet):
    """cti_agent.py 기대 포맷에 맞게 패킷 정보 정제."""
    try:
        packet_timestamp = float(packet.sniff_timestamp)
    except Exception:
        packet_timestamp = time.time()

    details = {
        'ts': packet_timestamp,
        'capture_timestamp': datetime
        .fromtimestamp(packet_timestamp, timezone.utc)
        .isoformat()
        .replace('+00:00', 'Z'),
        'length': int(getattr(packet, 'length', 0) or 0),
        'highest_layer': getattr(packet, 'highest_layer', None),
    }

    # L3
    if hasattr(packet, 'ip'):
        details['ip_src'] = getattr(packet.ip, 'src', None)
        details['ip_dst'] = getattr(packet.ip, 'dst', None)
    elif hasattr(packet, 'ipv6'):
        details['ip_src'] = getattr(packet.ipv6, 'src', None)
        details['ip_dst'] = getattr(packet.ipv6, 'dst', None)

    # L4 / 기타
    if hasattr(packet, 'tcp'):
        t = packet.tcp
        details['protocol'] = 'TCP'
        details['src_port'] = int(getattr(t, 'srcport', 0) or 0)
        details['dst_port'] = int(getattr(t, 'dstport', 0) or 0)
        details['tcp_flags'] = str(getattr(t, 'flags', ''))
    elif hasattr(packet, 'udp'):
        u = packet.udp
        details['protocol'] = 'UDP'
        details['src_port'] = int(getattr(u, 'srcport', 0) or 0)
        details['dst_port'] = int(getattr(u, 'dstport', 0) or 0)
    elif hasattr(packet, 'icmp'):
        details['protocol'] = 'ICMP'
    elif hasattr(packet, 'arp'):
        details['protocol'] = 'ARP'
        a = packet.arp
        details['arp_op'] = getattr(a, 'opcode', None)

    return details


def packet_capture_callback(packet):
    """Pyshark 콜백: 개별 패킷을 bus에 바로 기록."""
    try:
        if stop_event.is_set():
            return

        packet_details = extract_packet_details(packet)
        log_to_bus("network_packet", packet_details)

    except AttributeError as e:
        logger.warning(
            f"Attr error processing packet "
            f"{getattr(packet, 'number', 'N/A')}: {e}. Skipping."
        )
    except Exception as e:
        logger.error(
            f"Unexpected error in packet callback "
            f"{getattr(packet, 'number', 'N/A')}: {e}",
            exc_info=True
        )


def get_docker_bridge_interface(network_name="simulator"):
    """Docker network 이름에서 브리지 인터페이스 이름 자동 추출."""
    try:
        result = subprocess.run(
            ['docker', 'network', 'inspect', network_name],
            capture_output=True,
            text=True,
            check=True,
        )
        network_info = json.loads(result.stdout)

        bridge_name = network_info[0].get(
            'Options', {}
        ).get('com.docker.network.bridge.name')
        if bridge_name:
            logger.info(
                "Found bridge interface '%s' for Docker network '%s'.",
                bridge_name,
                network_name,
            )
            return bridge_name

        net_id = network_info[0].get('Id', '')
        if net_id:
            candidate = f"br-{net_id[:12]}"
            logger.info(
                "Bridge name not set; trying '%s' derived from network Id.",
                candidate,
            )
            return candidate

        logger.warning(
            "Could not determine bridge interface for network '%s'.",
            network_name
        )
        return None

    except FileNotFoundError:
        logger.error("Docker command not found. Cannot inspect network.")
        return None
    except subprocess.CalledProcessError as e:
        logger.error(f"Error inspecting Docker network '{network_name}': {e}")
        logger.error("Stderr: %s", e.stderr)
        return None
    except (json.JSONDecodeError, IndexError) as e:
        logger.error(
            "Error parsing Docker network inspect output: %s",
            e
        )
        return None
    except Exception as e:
        logger.error(
            "Unexpected error getting Docker bridge interface: %s",
            e,
            exc_info=True
        )
        return None


def start_capture():
    """Pyshark LiveCapture 시작."""
    effective_interface = CAPTURE_INTERFACE
    if CAPTURE_INTERFACE == 'br-simulator':
        logger.info(
            "Attempting to detect bridge interface for 'simulator' network..."
        )
        detected_bridge = get_docker_bridge_interface("simulator")
        if detected_bridge:
            effective_interface = detected_bridge
        else:
            logger.warning(
                "Auto-detect failed. Falling back to '%s'.",
                CAPTURE_INTERFACE,
            )
            logger.warning(
                "Verify interface with "
                "'docker network inspect simulator' or 'ip link'."
            )

    logger.info("Starting network capture on interface: %s", effective_interface)
    if BPF_FILTER:
        logger.info("Using BPF filter: %s", BPF_FILTER)

    logger.info(f"Logging to: {BUS_LOG_PATH}")

    try:
        bus_dir_path.mkdir(parents=True, exist_ok=True)
        logger.info("Ensured bus log directory exists: %s", bus_dir_path)
    except Exception as dir_err:
        logger.critical(
            "Failed to create bus log directory '%s': %s. Exiting.",
            bus_dir_path,
            dir_err,
        )
        return

    capture = None
    try:
        capture = pyshark.LiveCapture(
            interface=effective_interface,
            bpf_filter=BPF_FILTER,
            use_json=True,
        )
        try:
            capture.keep_packets = False
        except Exception:
            pass

        logger.info("LiveCapture initialized. Starting sniffing loop...")
        logger.info(
            "Using 'apply_on_packets' for background capture callback..."
        )

        capture.apply_on_packets(packet_capture_callback, timeout=None)

        # 이 아래는 보통 도달하지 않지만, 안전하게 stop_event를 감시
        while not stop_event.is_set():
            stop_event.wait(1.0)

        logger.info("Packet sniffing loop terminated by stop event.")

    except (PermissionError, OSError) as perm_err:
        logger.critical(
            "PERMISSION ERROR capturing on '%s': %s. "
            "Try sudo or setcap on dumpcap.",
            effective_interface,
            perm_err,
        )
    except FileNotFoundError as fnf_err:
        logger.critical(
            "FILE NOT FOUND: %s. Check interface name and tshark/dumpcap.",
            fnf_err
        )
    except pyshark.capture.capture.TSharkCrashException as ts_crash:
        logger.critical("TSHARK CRASHED during capture: %s", ts_crash)
        logger.critical(
            "Run 'tshark -i %s' manually to diagnose.",
            effective_interface
        )
    except Exception as e:
        logger.critical(
            "UNEXPECTED ERROR during capture: %s",
            e,
            exc_info=True
        )
        logger.critical("Traceback: %s", traceback.format_exc())
    finally:
        stop_capture(capture)


def stop_capture(capture):
    logger.info("Initiating capture stop sequence...")

    if not stop_event.is_set():
        stop_event.set()

    if capture:
        try:
            capture.close()
            logger.info("Pyshark capture resources released.")
        except Exception as close_err:
            logger.error("Error closing pyshark capture: %s", close_err)

    logger.info("Network Traffic Monitor stopped.")


def _signal_handler(signum, frame):
    logger.info("Signal %s received. Stopping monitor...", signum)
    stop_event.set()


signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)


if __name__ == "__main__":
    try:
        start_capture()
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received by main thread. Stopping monitor...")
    except Exception as main_err:
        logger.critical(
            "Unhandled exception in main thread: %s",
            main_err,
            exc_info=True
        )
    finally:
        if not stop_event.is_set():
            logger.info("Ensuring stop event is set before final exit.")
            stop_event.set()
        logger.info("Main thread exiting.")
