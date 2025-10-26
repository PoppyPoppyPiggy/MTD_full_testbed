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
BUS_LOG_FILENAME = 'bus_network_monitor.log'
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
    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
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
                log_to_bus("network_traffic", packet_batch)
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
            log_to_bus("network_traffic", packet_batch)
        except Exception as final_log_err:
            logger.error(f"Failed to log final packet batch: {final_log_err}", exc_info=True)

    logger.info("Packet logging thread finished.")

# -----------------------------
# 패킷 파싱
# -----------------------------
def extract_packet_details(packet):
    details = {
        'capture_timestamp': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        'timestamp': getattr(packet, 'sniff_timestamp', None),
        'number': getattr(packet, 'number', None),
        'length': int(getattr(packet, 'length', 0) or 0),
        'highest_layer': getattr(packet, 'highest_layer', None),
    }

    # L2
    if hasattr(packet, 'eth'):
        details['eth_src'] = getattr(packet.eth, 'src', None)
        details['eth_dst'] = getattr(packet.eth, 'dst', None)
        details['eth_type'] = getattr(packet.eth, 'type', None)

    # L3
    if hasattr(packet, 'ip'):
        details['ip_version'] = getattr(packet.ip, 'version', None)
        details['ip_src'] = getattr(packet.ip, 'src', None)
        details['ip_dst'] = getattr(packet.ip, 'dst', None)
        details['ip_proto'] = getattr(packet.ip, 'proto', None)
        details['ip_ttl'] = getattr(packet.ip, 'ttl', None)
        details['ip_len'] = getattr(packet.ip, 'len', None)
    elif hasattr(packet, 'ipv6'):
        details['ip_version'] = 6
        details['ipv6_src'] = getattr(packet.ipv6, 'src', None)
        details['ipv6_dst'] = getattr(packet.ipv6, 'dst', None)
        details['ipv6_nxt'] = getattr(packet.ipv6, 'nxt', None)
        details['ipv6_hlim'] = getattr(packet.ipv6, 'hlim', None)
        details['ipv6_plen'] = getattr(packet.ipv6, 'plen', None)

    # L4 / 기타
    if hasattr(packet, 'tcp'):
        t = packet.tcp
        details['transport_protocol'] = 'TCP'
        details['tcp_srcport'] = int(getattr(t, 'srcport', 0) or 0)
        details['tcp_dstport'] = int(getattr(t, 'dstport', 0) or 0)
        details['tcp_seq'] = getattr(t, 'seq', None)
        details['tcp_ack'] = getattr(t, 'ack', None)
        details['tcp_flags'] = str(getattr(t, 'flags', ''))
        details['tcp_window_size'] = getattr(t, 'window_size', None)
        details['tcp_payload_len'] = None
        payload_hex = getattr(t, 'payload', None)
        if payload_hex:
            try:
                payload_bytes = binascii.unhexlify(payload_hex.replace(':', ''))
                details['tcp_payload_len'] = len(payload_bytes)
            except binascii.Error as e:
                logger.warning(f"Pkt {details.get('number', 'N/A')} TCP payload hex error: {e}. start={payload_hex[:30]}...")
            except Exception as e:
                logger.error(f"Pkt {details.get('number', 'N/A')} TCP payload unexpected error: {e}")

    elif hasattr(packet, 'udp'):
        u = packet.udp
        details['transport_protocol'] = 'UDP'
        details['udp_srcport'] = int(getattr(u, 'srcport', 0) or 0)
        details['udp_dstport'] = int(getattr(u, 'dstport', 0) or 0)
        details['udp_length'] = int(getattr(u, 'length', 0) or 0)
        details['udp_payload_len'] = None
        payload_hex = getattr(u, 'payload', None)
        if payload_hex:
            try:
                payload_bytes = binascii.unhexlify(payload_hex.replace(':', ''))
                details['udp_payload_len'] = len(payload_bytes)
                if details['udp_length'] > 8 and details['udp_length'] - 8 != details['udp_payload_len']:
                    logger.debug(
                        f"Pkt {details.get('number','N/A')} UDP len mismatch: header={details['udp_length']}, "
                        f"calc payload={details['udp_payload_len']}"
                    )
            except binascii.Error as e:
                logger.warning(f"Pkt {details.get('number', 'N/A')} UDP payload hex error: {e}. start={payload_hex[:30]}...")
            except Exception as e:
                logger.error(f"Pkt {details.get('number', 'N/A')} UDP payload unexpected error: {e}")
        elif details['udp_length'] > 8:
            details['udp_payload_len'] = details['udp_length'] - 8
        elif details['udp_length'] == 8:
            details['udp_payload_len'] = 0

    elif hasattr(packet, 'icmp'):
        i = packet.icmp
        details['transport_protocol'] = 'ICMP'
        details['icmp_type'] = getattr(i, 'type', None)
        details['icmp_code'] = getattr(i, 'code', None)
        if hasattr(i, 'seq'): details['icmp_seq'] = i.seq
        if hasattr(i, 'id'): details['icmp_id'] = i.id

    elif hasattr(packet, 'arp'):
        details['protocol'] = 'ARP'
        a = packet.arp
        details['arp_opcode'] = getattr(a, 'opcode', None)
        details['arp_src_hw_mac'] = getattr(a, 'src_hw_mac', None)
        details['arp_src_proto_ipv4'] = getattr(a, 'src_proto_ipv4', None)
        details['arp_dst_hw_mac'] = getattr(a, 'dst_hw_mac', None)
        details['arp_dst_proto_ipv4'] = getattr(a, 'dst_proto_ipv4', None)

    # DNS
    if hasattr(packet, 'dns'):
        d = packet.dns
        details['dns_id'] = getattr(d, 'id', None)
        if hasattr(d, 'flags'):
            details['dns_flags_qr'] = getattr(d.flags, 'qr', None)
            details['dns_flags_opcode'] = getattr(d.flags, 'opcode', None)
        details['dns_qry_name'] = getattr(d, 'qry_name', None)
        details['dns_qry_type'] = getattr(d, 'qry_type', None)
        details['dns_resp_name'] = getattr(d, 'resp_name', None)
        details['dns_resp_type'] = getattr(d, 'resp_type', None)
        details['dns_resp_ttl'] = getattr(d, 'resp_ttl', None)
        details['dns_resp_addr'] = getattr(d, 'a', None)
        details['dns_resp_addr6'] = getattr(d, 'aaaa', None)

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
            packet_queue.put_nowait(packet_details)
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
    logger.info(f"Packet buffer: {PACKET_BUFFER_SIZE}, Log interval: {LOGGING_INTERVAL}s")
    logger.info(f"Logging to: {BUS_LOG_PATH}")

    try:
        bus_dir_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Ensured bus log directory exists: {bus_dir_path}")
    except Exception as dir_err:
        logger.critical(f"Failed to create bus log directory '{bus_dir_path}': {dir_err}. Exiting.")
        return

    if logging_thread is None or not logging_thread.is_alive():
        logging_thread = threading.Thread(target=log_packets_from_queue, daemon=True)
        logging_thread.start()
    else:
        logger.warning("Logging thread is already running.")

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

        # 제너레이터 직접 순회
        for pkt in capture.sniff_continuously():  # 무한
            if stop_event.is_set():
                break
            packet_capture_callback(pkt)

        logger.info("Packet sniffing loop terminated.")

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

    if logging_thread and logging_thread.is_alive():
        logger.info("Waiting for logging thread to finish...")
        logging_thread.join(timeout=LOGGING_INTERVAL + 2)
        if logging_thread.is_alive():
            logger.warning("Logging thread did not exit gracefully.")
        else:
            logger.info("Logging thread finished.")
    else:
        logger.info("Logging thread was not running or already finished.")

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
