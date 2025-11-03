#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pyshark
import json
import time
import os
import logging
from datetime import datetime, timezone
import queue
import threading
import binascii
import pathlib
import traceback
import subprocess
import signal

# -----------------------------
# 로깅 설정
# -----------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)-7s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("NetworkTrafficMonitor")

# -----------------------------
# 경로/환경 변수
# -----------------------------
script_dir = pathlib.Path(__file__).parent.resolve()
bus_dir_name = os.environ.get('BUS_DIR', '../bus')
bus_dir_path = (script_dir / bus_dir_name).resolve()
# ⭐️ [수정] cti_agent.py가 읽는 'bus_network.log'로 파일명 변경
BUS_LOG_FILENAME = 'bus_network.log'
BUS_LOG_PATH = bus_dir_path / BUS_LOG_FILENAME

CAPTURE_INTERFACE = os.environ.get('NETWORK_CAPTURE_INTERFACE', 'br-simulator')
PACKET_BUFFER_SIZE = int(os.environ.get('NETWORK_PACKET_BUFFER_SIZE', 100))
LOGGING_INTERVAL = int(os.environ.get('NETWORK_LOGGING_INTERVAL', 5))
BPF_FILTER = os.environ.get('NETWORK_BPF_FILTER', None)

# -----------------------------
# 상태/동기화 오브젝트
# -----------------------------
packet_queue = queue.Queue(maxsize=PACKET_BUFFER_SIZE * 2)
stop_event = threading.Event()
logging_thread = None

# -----------------------------
# Bus 로그 유틸
# -----------------------------
def log_to_bus(message_type, data):
    current_time_dt = datetime.now(timezone.utc)
    current_time_unix = current_time_dt.timestamp()

    log_entry = {
        "timestamp": current_time_dt.isoformat().replace('+00:00', 'Z'),
        "ts": current_time_unix, # ⭐️ ML 에이전트가 사용할 Unix timestamp 추가
        "source": "network_traffic_monitor",
        "type": message_type,
        "data": data
    }
    try:
        BUS_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(BUS_LOG_PATH, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
    except IOError as e:
        logger.error(f"Bus 로그 파일 '{BUS_LOG_PATH}'에 쓰기 실패: {e}")
    except Exception as e:
        logger.error(f"로그 기록 중 예상치 못한 오류 발생: {e}", exc_info=True)

# -----------------------------
# 로깅 스레드
# -----------------------------
def log_packets_from_queue():
    packet_batch = []
    last_log_time = time.monotonic()
    logger.info("Packet logging thread started.")

    while not stop_event.is_set() or not packet_queue.empty():
        try:
            packet_data = packet_queue.get(timeout=0.5)
            packet_batch.append(packet_data)
            packet_queue.task_done()
        except queue.Empty:
            pass
        except Exception as q_err:
            logger.error(f"Error getting packet from queue: {q_err}", exc_info=True)
            time.sleep(0.1)
            continue

        current_time = time.monotonic()
        should_log = packet_batch and (
            len(packet_batch) >= PACKET_BUFFER_SIZE or
            (current_time - last_log_time >= LOGGING_INTERVAL)
        )

        if should_log:
            try:
                # ⭐️ [수정] 로그 타입을 'network_packet'으로 변경 (cti_agent와 맞추기 위해)
                #    (cti_agent는 data_builder 로직을 따르며, data_builder는 이 데이터를 처리하지 않았었음)
                #    (cti_agent가 이 데이터를 처리하도록 수정하거나, 이 로그 타입을 cti_agent가 아는 타입으로 변경해야 함)
                #    (일단은 'network_traffic_batch'로 로깅)
                log_to_bus("network_traffic_batch", packet_batch)
                logger.info(f"Logged {len(packet_batch)} packets to {BUS_LOG_PATH}.")
            except Exception as log_err:
                logger.error(f"Failed to log packet batch: {log_err}", exc_info=True)
            finally:
                packet_batch = []
                last_log_time = current_time

        if stop_event.is_set() and packet_queue.empty():
            break

    if packet_batch:
        logger.info(f"Logging remaining {len(packet_batch)} packets before exit.")
        try:
            log_to_bus("network_traffic_batch", packet_batch)
        except Exception as final_log_err:
            logger.error(f"Failed to log final packet batch: {final_log_err}", exc_info=True)

    logger.info("Packet logging thread finished.")

# -----------------------------
# 패킷 파싱 (⭐️ cti_agent.py 기대치에 맞게 수정)
# -----------------------------
def extract_packet_details(packet):
    # ⭐️ ML 에이전트가 사용할 Unix timestamp 추가
    try:
        packet_timestamp = float(packet.sniff_timestamp)
    except Exception:
        packet_timestamp = time.time()

    details = {
        'ts': packet_timestamp, # ⭐️ ts 필드 추가
        'capture_timestamp': datetime.fromtimestamp(packet_timestamp, timezone.utc).isoformat().replace('+00:00', 'Z'),
        'length': int(getattr(packet, 'length', 0) or 0),
        'highest_layer': getattr(packet, 'highest_layer', None),
    }

    # L2 (필요 시)
    # if hasattr(packet, 'eth'):
    #     details['eth_src'] = getattr(packet.eth, 'src', None)
    #     details['eth_dst'] = getattr(packet.eth, 'dst', None)

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
        details['tcp_flags'] = str(getattr(t, 'flags', '')) # ⭐️ cti_agent가 사용할 'tcp_flags'

    elif hasattr(packet, 'udp'):
        u = packet.udp
        details['protocol'] = 'UDP'
        details['src_port'] = int(getattr(u, 'srcport', 0) or 0)
        details['dst_port'] = int(getattr(u, 'dstport', 0) or 0)

    elif hasattr(packet, 'icmp'):
        details['protocol'] = 'ICMP'
        # ... (ICMP 상세 정보는 cti_agent.py가 현재 사용하지 않음)

    elif hasattr(packet, 'arp'):
        details['protocol'] = 'ARP'
        a = packet.arp
        details['arp_op'] = getattr(a, 'opcode', None) # ⭐️ cti_agent가 사용할 'arp_op'

    return details

# -----------------------------
# 캡처 콜백
# -----------------------------
def packet_capture_callback(packet):
    try:
        if stop_event.is_set():
            return
        packet_details = extract_packet_details(packet)
        try:
            # ⭐️ [수정] 큐에 넣을 때 개별 패킷을 분리된 로그 항목으로 처리
            # (cti_agent는 개별 로그 항목을 기대함)
            # log_to_bus 함수를 직접 호출하거나, 로깅 스레드 로직 변경 필요
            # ⭐️ 여기서는 큐에 넣고 로깅 스레드가 *배치*로 기록하도록 유지
            #    (cti_agent.py가 이 'network_traffic_batch' 타입을 처리하도록 수정이 필요함)
            #    (임시방편: cti_agent.py가 처리할 수 있도록 개별 로그로 바로 기록)
            
            # ⭐️ [수정안] 큐를 사용하지 않고 바로 bus에 기록 (부하 증가 가능성 있음)
            # ⭐️ cti_agent.py는 'data' 필드 안에 개별 패킷 정보가 있을 것으로 기대
            log_to_bus("network_packet", packet_details) 

            # [기존 로직: 큐 사용]
            # packet_queue.put_nowait(packet_details) 
            
        except queue.Full:
            logger.warning("Packet queue full. Dropping packet. Consider increasing buffer/interval.")
    except AttributeError as e:
        logger.warning(f"Attr error processing packet {getattr(packet, 'number', 'N/A')}: {e}. Skipping.")
    except Exception as e:
        logger.error(f"Unexpected error in packet callback {getattr(packet, 'number', 'N/A')}: {e}", exc_info=True)

# -----------------------------
# Docker 브리지 자동 감지
# -----------------------------
def get_docker_bridge_interface(network_name="simulator"):
    try:
        result = subprocess.run(['docker', 'network', 'inspect', network_name],
                                capture_output=True, text=True, check=True)
        network_info = json.loads(result.stdout)

        bridge_name = network_info[0].get('Options', {}).get('com.docker.network.bridge.name')
        if bridge_name:
            logger.info(f"Found bridge interface '{bridge_name}' for Docker network '{network_name}'.")
            return bridge_name

        net_id = network_info[0].get('Id', '')
        if net_id:
            candidate = f"br-{net_id[:12]}"
            logger.info(f"Bridge name not set; trying '{candidate}' derived from network Id.")
            return candidate

        logger.warning(f"Could not determine bridge interface for network '{network_name}'.")
        return None

    except FileNotFoundError:
        logger.error("Docker command not found. Cannot inspect network.")
        return None
    except subprocess.CalledProcessError as e:
        logger.error(f"Error inspecting Docker network '{network_name}': {e}")
        logger.error(f"Stderr: {e.stderr}")
        return None
    except (json.JSONDecodeError, IndexError) as e:
        logger.error(f"Error parsing Docker network inspect output: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error getting Docker bridge interface: {e}", exc_info=True)
        return None

# -----------------------------
# 캡처 시작/종료
# -----------------------------
def start_capture():
    global logging_thread

    effective_interface = CAPTURE_INTERFACE
    if CAPTURE_INTERFACE == 'br-simulator':
        logger.info("Attempting to detect bridge interface for 'simulator' network...")
        detected_bridge = get_docker_bridge_interface("simulator")
        if detected_bridge:
            effective_interface = detected_bridge
        else:
            logger.warning(f"Auto-detect failed. Falling back to '{CAPTURE_INTERFACE}'.")
            logger.warning("Verify interface with 'docker network inspect simulator' or 'ip link'.")

    logger.info(f"Starting network capture on interface: {effective_interface}")
    if BPF_FILTER:
        logger.info(f"Using BPF filter: {BPF_FILTER}")
    # logger.info(f"Packet buffer: {PACKET_BUFFER_SIZE}, Log interval: {LOGGING_INTERVAL}s") # ⭐️ 큐 방식 대신 직접 로깅
    logger.info(f"Logging to: {BUS_LOG_PATH}")

    try:
        bus_dir_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Ensured bus log directory exists: {bus_dir_path}")
    except Exception as dir_err:
        logger.critical(f"Failed to create bus log directory '{bus_dir_path}': {dir_err}. Exiting.")
        return

    # ⭐️ [수정] 큐/로깅 스레드 방식 대신, 콜백에서 직접 로깅하므로 스레드 시작 부분 주석 처리
    # if logging_thread is None or not logging_thread.is_alive():
    #     logging_thread = threading.Thread(target=log_packets_from_queue, daemon=True)
    #     logging_thread.start()
    # else:
    #     logger.warning("Logging thread is already running.")

    capture = None
    try:
        # ---- 핵심: 생성자 인자 호환 ----
        capture = pyshark.LiveCapture(
            interface=effective_interface,
            bpf_filter=BPF_FILTER,
            use_json=True  # 지원되는 버전 대부분에서 동작
        )
        # 일부 버전은 생성 후 속성으로만 설정 가능
        try:
            capture.keep_packets = False
        except Exception:
            pass

        logger.info("LiveCapture initialized. Starting sniffing loop...")

        # ⭐️ [수정] 콜백 함수를 apply_on_packets에 전달
        # (sniff_continuously는 패킷을 반환받아 메인 스레드에서 처리하는 방식)
        logger.info("Using 'apply_on_packets' for background capture callback...")
        capture.apply_on_packets(packet_capture_callback, timeout=None) # timeout=None은 무한 대기
        
        # ⭐️ apply_on_packets가 백그라운드 스레드에서 실행되므로, 메인 스레드는 종료 신호를 대기해야 함
        while not stop_event.is_set():
            stop_event.wait(1.0) # 1초 간격으로 종료 신호 확인
            
        logger.info("Packet sniffing loop terminated by stop event.")

    except (PermissionError, OSError) as perm_err:
        logger.critical(
            f"PERMISSION ERROR capturing on '{effective_interface}': {perm_err}. "
            f"Try sudo or set dumpcap capabilities: sudo setcap cap_net_raw,cap_net_admin=eip $(which dumpcap)"
        )
    except FileNotFoundError as fnf_err:
        logger.critical(f"FILE NOT FOUND: {fnf_err}. Check interface name and tshark/dumpcap installation.")
    except pyshark.capture.capture.TSharkCrashException as ts_crash:
        logger.critical(f"TSHARK CRASHED during capture: {ts_crash}")
        logger.critical("Run 'tshark -i <iface>' manually to diagnose version/permission issues.")
    except Exception as e:
        logger.critical(f"UNEXPECTED ERROR during capture: {e}", exc_info=True)
        logger.critical(f"Traceback: {traceback.format_exc()}")
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
            logger.error(f"Error closing pyshark capture: {close_err}")

    # ⭐️ [수정] 로깅 스레드 관련 부분 주석 처리
    # if logging_thread and logging_thread.is_alive():
    #     logger.info("Waiting for logging thread to finish...")
    #     logging_thread.join(timeout=LOGGING_INTERVAL + 2)
    #     if logging_thread.is_alive():
    #         logger.warning("Logging thread did not exit gracefully.")
    #     else:
    #         logger.info("Logging thread finished.")
    # else:
    #     logger.info("Logging thread was not running or already finished.")

    logger.info("Network Traffic Monitor stopped.")

# -----------------------------
# 신호 처리
# -----------------------------
def _signal_handler(signum, frame):
    logger.info(f"Signal {signum} received. Stopping monitor...")
    stop_event.set()

signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)

# -----------------------------
# 엔트리포인트
# -----------------------------
if __name__ == "__main__":
    try:
        start_capture()
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received by main thread. Stopping monitor...")
    except Exception as main_err:
        logger.critical(f"Unhandled exception in main thread: {main_err}", exc_info=True)
    finally:
        if not stop_event.is_set():
            logger.info("Ensuring stop event is set before final exit.")
            stop_event.set()
        logger.info("Main thread exiting.")
