#!/usr/bin/env python3
import pyshark
import time
import json
import os
import logging
from datetime import datetime
import threading
import queue
import traceback # 상세 오류 로깅용

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 환경 변수 또는 기본값 설정
BUS_LOG_PATH = os.environ.get('BUS_LOG_PATH', './bus.log')
CAPTURE_INTERFACE = os.environ.get('NETWORK_CAPTURE_INTERFACE', 'any') # 기본값 'any'로 변경 (모든 인터페이스)
CAPTURE_FILTER = os.environ.get('NETWORK_CAPTURE_FILTER', '') # BPF 필터 (예: 'udp port 14550 or tcp port 80')
MAX_PACKETS_PER_LOG = int(os.environ.get('NETWORK_MAX_PACKETS_PER_LOG', 50)) # 로그 한번에 기록할 최대 패킷 수 (조정)
MAX_QUEUE_SIZE = int(os.environ.get('NETWORK_MAX_QUEUE_SIZE', 2000)) # 패킷 처리 큐 최대 크기 (증가)
LOGGING_INTERVAL = float(os.environ.get('NETWORK_LOGGING_INTERVAL', 1.0)) # 로그 기록 최대 주기 (초)

# 패킷 처리를 위한 스레드 안전 큐
packet_queue = queue.Queue(maxsize=MAX_QUEUE_SIZE)
# 스레드 종료 플래그
terminate_flag = threading.Event()

def log_to_bus(packets_data):
    """
    수집된 패킷 데이터를 bus 로그 파일에 기록합니다.
    """
    if not packets_data:
        return

    log_entry = {
        # datetime.utcnow() -> datetime.now(timezone.utc)
        "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        "source": "network_traffic_monitor",
        "type": "network_packets",
        "interface": CAPTURE_INTERFACE,
        "filter": CAPTURE_FILTER,
        "packet_count": len(packets_data),
        "data": packets_data # 패킷 정보 리스트
    }
    try:
        with open(BUS_LOG_PATH, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
        logger.debug(f"{len(packets_data)}개의 패킷 정보를 로그에 기록했습니다.")
    except IOError as e:
        logger.error(f"Bus 로그 파일 '{BUS_LOG_PATH}'에 쓰기 실패: {e}")
    except Exception as e:
        logger.error(f"로그 기록 중 예상치 못한 오류 발생: {e}")

def process_packet(pkt):
    """
    캡처된 패킷에서 상세 정보를 추출하여 딕셔너리로 반환합니다.
    """
    try:
        # pkt.captured_length가 None일 경우 pkt.length 또는 0 사용
        captured_length_val = getattr(pkt, 'captured_length', None)
        captured_length = int(captured_length_val) if captured_length_val is not None else int(getattr(pkt, 'length', 0))

        packet_info = {
            'timestamp': float(pkt.sniff_timestamp),
            'number': int(pkt.number),
            'length': int(pkt.length),
            'captured_length': captured_length, # 수정된 값 사용
            'highest_layer': pkt.highest_layer,
            'interface_captured': getattr(pkt, 'interface_captured', None),
            'protocols': pkt.protocol.split(':') if hasattr(pkt, 'protocol') else [], # pyshark 0.5.3+
            'layers': [layer.layer_name for layer in pkt.layers]
        }

        # Ethernet 레이어
        if hasattr(pkt, 'eth'):
            packet_info['eth_src'] = pkt.eth.src
            packet_info['eth_dst'] = pkt.eth.dst
            packet_info['eth_type'] = pkt.eth.type

        # IP 레이어 (IPv4/IPv6)
        ip_layer = getattr(pkt, 'ip', getattr(pkt, 'ipv6', None))
        if ip_layer:
            packet_info['ip_version'] = ip_layer.version
            packet_info['ip_src'] = ip_layer.src
            packet_info['ip_dst'] = ip_layer.dst
            packet_info['ip_len'] = int(ip_layer.len)
            packet_info['ip_ttl'] = int(ip_layer.ttl) if hasattr(ip_layer, 'ttl') else None # IPv4 TTL
            packet_info['ip_hop_limit'] = int(ip_layer.hlim) if hasattr(ip_layer, 'hlim') else None # IPv6 Hop Limit
            packet_info['ip_proto'] = int(ip_layer.proto) if hasattr(ip_layer, 'proto') else int(ip_layer.nxt) # Protocol / Next Header
            packet_info['ip_flags'] = str(ip_layer.flags) if hasattr(ip_layer, 'flags') else None # IPv4 Flags
            packet_info['ip_frag_offset'] = int(ip_layer.frag_offset) if hasattr(ip_layer, 'frag_offset') else None # IPv4 Fragment Offset

        # TCP 레이어
        if hasattr(pkt, 'tcp'):
            packet_info['tcp_srcport'] = int(pkt.tcp.srcport)
            packet_info['tcp_dstport'] = int(pkt.tcp.dstport)
            packet_info['tcp_seq'] = int(pkt.tcp.seq)
            packet_info['tcp_ack'] = int(pkt.tcp.ack)
            packet_info['tcp_flags'] = str(pkt.tcp.flags) # Flags (e.g., "0x00000012" (SYN, ACK))
            packet_info['tcp_window_size'] = int(pkt.tcp.window_size)
            packet_info['tcp_payload_len'] = len(pkt.tcp.payload.binary_value) if hasattr(pkt.tcp, 'payload') else 0

        # UDP 레이어
        elif hasattr(pkt, 'udp'):
            packet_info['udp_srcport'] = int(pkt.udp.srcport)
            packet_info['udp_dstport'] = int(pkt.udp.dstport)
            packet_info['udp_length'] = int(pkt.udp.length)
            packet_info['udp_payload_len'] = len(pkt.udp.payload.binary_value) if hasattr(pkt.udp, 'payload') else 0
            # UDP payload 일부 로깅 (주의: 성능 및 로그 크기 영향)
            # if 'udp_payload_len' in packet_info and packet_info['udp_payload_len'] > 0:
            #     payload_bytes = pkt.udp.payload.binary_value
            #     packet_info['udp_payload_hex'] = payload_bytes[:min(32, len(payload_bytes))].hex() # 앞 32바이트 hex

        # ICMP 레이어
        elif hasattr(pkt, 'icmp'):
            packet_info['icmp_type'] = int(pkt.icmp.type)
            packet_info['icmp_code'] = int(pkt.icmp.code)
            packet_info['icmp_seq'] = int(pkt.icmp.seq) if hasattr(pkt.icmp, 'seq') else None

        # DNS 레이어 (일반적으로 UDP 위에 있음)
        if hasattr(pkt, 'dns'):
            packet_info['dns_id'] = pkt.dns.id
            packet_info['dns_flags'] = str(pkt.dns.flags)
            packet_info['dns_qry_name'] = pkt.dns.qry_name if hasattr(pkt.dns, 'qry_name') else None
            packet_info['dns_qry_type'] = pkt.dns.qry_type if hasattr(pkt.dns, 'qry_type') else None
            packet_info['dns_resp_name'] = pkt.dns.resp_name if hasattr(pkt.dns, 'resp_name') else None
            packet_info['dns_resp_addr'] = pkt.dns.resp_addr if hasattr(pkt.dns, 'resp_addr') else None

        # MAVLink (UDP 페이로드로 표시될 가능성 높음)
        # TODO: MAVLink 페이로드 디코딩 필요 시 추가 구현 (별도 라이브러리 사용 고려)
        # if packet_info.get('udp_dstport') == 14550 or packet_info.get('udp_srcport') == 14550:
             # try:
             #     payload = pkt.udp.payload.binary_value
             #     # mavlink_message = decode_mavlink_payload(payload) # 별도 함수 구현 필요
             #     # packet_info['mavlink'] = mavlink_message
             # except Exception as mav_err:
             #     packet_info['mavlink_error'] = str(mav_err)

        return packet_info

    except AttributeError as e:
        logger.debug(f"패킷 정보 추출 중 속성 오류: {e} - 패킷 번호: {getattr(pkt, 'number', 'N/A')}")
        # 기본적인 정보만이라도 반환 시도
        return {
            'timestamp': float(getattr(pkt, 'sniff_timestamp', 0.0)),
            'length': int(getattr(pkt, 'length', 0)),
            'error': f"AttributeError: {e}",
            'layers': [layer.layer_name for layer in getattr(pkt, 'layers', [])]
        }
    except Exception as e:
        logger.error(f"패킷 처리 중 예상치 못한 오류 발생: {e} - 패킷 번호: {getattr(pkt, 'number', 'N/A')}")
        logger.error(traceback.format_exc()) # 상세 오류 스택 로깅
        return None

def packet_capture_thread():
    """네트워크 인터페이스에서 패킷을 캡처하여 큐에 넣는 스레드 함수."""
    logger.info(f"인터페이스 '{CAPTURE_INTERFACE}'에서 패킷 캡처 시작 (필터: '{CAPTURE_FILTER if CAPTURE_FILTER else '없음'}').")
    capture = None
    try:
        # use_json=True, include_raw=False : tshark 처리 부담 감소 시도
        capture = pyshark.LiveCapture(
            interface=CAPTURE_INTERFACE,
            bpf_filter=CAPTURE_FILTER,
            use_json=True,
            include_raw=False
        )
        # sniff_continuously는 제너레이터
        for packet in capture.sniff_continuously():
            if terminate_flag.is_set():
                logger.info("종료 신호 수신, 패킷 캡처 중단.")
                break

            processed_packet = process_packet(packet)
            if processed_packet:
                try:
                    packet_queue.put(processed_packet, block=False) # Non-blocking
                except queue.Full:
                    logger.warning(f"패킷 처리 큐가 가득 찼습니다 (크기: {MAX_QUEUE_SIZE}). 일부 패킷이 유실될 수 있습니다.")
                    # 큐가 꽉 찼을 때 처리: 오래된 것 버리기 (큐에서 하나 빼고 넣기)
                    try:
                        packet_queue.get_nowait()
                        packet_queue.put(processed_packet, block=False)
                    except queue.Empty:
                        pass # 빼려는데 비어있으면 그냥 넣기
                    except queue.Full:
                        pass # 또 꽉찼으면 어쩔 수 없이 버림

    except FileNotFoundError:
         logger.error(f"캡처 도구(tshark)를 찾을 수 없습니다. tshark가 설치되어 있고 PATH에 있는지 확인하세요.")
    except PermissionError:
         logger.error(f"인터페이스 '{CAPTURE_INTERFACE}' 캡처 권한이 없습니다. root 권한 또는 적절한 권한으로 실행하세요.")
    except Exception as e:
        logger.error(f"패킷 캡처 중 심각한 오류 발생: {e}", exc_info=True)
    finally:
        if capture:
            capture.close()
        # 스레드 종료 시 None을 넣어 처리 스레드에게 종료 신호 전달
        # 큐가 꽉 차도 넣을 수 있도록 block=True 사용 고려 또는 예외 처리 강화
        try:
             packet_queue.put(None, block=True, timeout=1.0) # 로깅 스레드가 받을 때까지 잠시 대기
        except queue.Full:
             logger.error("종료 신호(None)를 패킷 큐에 넣지 못했습니다.")
        logger.info("패킷 캡처 스레드 종료.")


def packet_logging_thread():
    """큐에서 패킷 정보를 가져와 주기적으로 로그 파일에 기록하는 스레드 함수."""
    logger.info("패킷 로깅 스레드 시작.")
    packets_buffer = []
    last_log_time = time.time()
    while True:
        try:
            # 큐에서 패킷 가져오기 (타임아웃 설정하여 주기적 로깅 및 종료 확인)
            packet_info = packet_queue.get(block=True, timeout=LOGGING_INTERVAL / 2) # 로깅 간격의 절반 정도 대기

            if packet_info is None: # 캡처 스레드로부터 종료 신호 수신
                logger.info("캡처 스레드로부터 종료 신호 수신.")
                break # 루프 종료 -> finally 블록 실행

            packets_buffer.append(packet_info)
            packet_queue.task_done() # 큐 작업 완료 알림

            # 버퍼가 가득 차면 즉시 로깅
            if len(packets_buffer) >= MAX_PACKETS_PER_LOG:
                log_to_bus(packets_buffer)
                packets_buffer = [] # 버퍼 비우기
                last_log_time = time.time()

        except queue.Empty:
            # 타임아웃 발생 시 (큐가 비어있음)
            current_time = time.time()
            # 버퍼에 내용이 있고, 마지막 로그 기록 후 일정 시간 지났으면 로깅
            if packets_buffer and (current_time - last_log_time >= LOGGING_INTERVAL):
                logger.debug(f"타임아웃 및 로깅 간격 경과로 버퍼 로깅 수행 ({len(packets_buffer)}개).")
                log_to_bus(packets_buffer)
                packets_buffer = [] # 버퍼 비우기
                last_log_time = current_time
            # 종료 플래그 확인
            if terminate_flag.is_set():
                logger.info("종료 신호 확인, 로깅 스레드 종료 준비.")
                break
            continue # 계속 큐 확인

        except Exception as e:
            logger.error(f"패킷 로깅 중 오류 발생: {e}", exc_info=True)
            # 오류 발생 시에도 계속 시도

        # 루프 종료 후 남아있는 버퍼 내용 로깅
        finally:
            if packets_buffer:
                logger.info(f"종료 전 마지막 버퍼 로깅 ({len(packets_buffer)}개).")
                log_to_bus(packets_buffer)
            logger.info("패킷 로깅 스레드 종료.")


def main():
    """네트워크 트래픽 모니터링을 위한 스레드를 시작하고 관리합니다."""
    logger.info("네트워크 트래픽 모니터 시작.")

    # 캡처 스레드 시작
    capture_thread = threading.Thread(target=packet_capture_thread, name="PacketCaptureThread", daemon=True)
    capture_thread.start()

    # 로깅 스레드 시작
    logging_thread = threading.Thread(target=packet_logging_thread, name="PacketLoggingThread", daemon=True)
    logging_thread.start()

    try:
        # 메인 스레드는 스레드들이 종료될 때까지 대기
        while capture_thread.is_alive() and logging_thread.is_alive():
            # 메인 스레드에서 주기적으로 상태 확인 또는 다른 작업 수행 가능
            time.sleep(1)
            # 예: 큐 크기 로깅
            # logger.debug(f"Current packet queue size: {packet_queue.qsize()}")

    except KeyboardInterrupt:
        logger.info("사용자에 의해 모니터링 중단 신호 수신...")
    finally:
        # 스레드들에 종료 신호 전달
        terminate_flag.set()
        logger.info("캡처 및 로깅 스레드에 종료 신호 전송됨.")

        # 스레드 종료 대기
        capture_thread.join(timeout=5)
        if capture_thread.is_alive():
             logger.warning("캡처 스레드가 시간 내에 종료되지 않았습니다.")
        logging_thread.join(timeout=5)
        if logging_thread.is_alive():
             logger.warning("로깅 스레드가 시간 내에 종료되지 않았습니다.")

        logger.info("네트워크 트래픽 모니터 종료.")

if __name__ == "__main__":
    # 스크립트 실행 권한 확인 (Linux/macOS)
    if os.name == 'posix' and os.geteuid() != 0:
        logger.warning("네트워크 패킷 캡처를 위해 root 권한이 필요할 수 있습니다.")
    main()


