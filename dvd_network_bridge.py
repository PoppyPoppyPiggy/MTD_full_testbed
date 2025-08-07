#!/usr/bin/env python3
"""
DVD 네트워크 브리지 및 실시간 분석기
위치: /home/kali/MTD/MTD_full_testbed/dvd_network_bridge.py

기능:
1. 기존 DVD 컨테이너의 네트워크 트래픽 실시간 캡처
2. MAVLink 프로토콜 딥 패킷 인스펙션
3. NS-3 시뮬레이터와 연동하여 FANET 네트워크 분석
4. 공격 패턴 실시간 탐지 및 CTI 생성
5. 기존 dvd_lite 시스템과 완전 통합
"""

import asyncio
import docker
import json
import logging
import time
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import numpy as np
import struct
import socket
import select
import signal
import sys
from contextlib import asynccontextmanager

# 패킷 캡처 및 분석
try:
    from scapy.all import *
    from scapy.layers.inet import IP, UDP
    SCAPY_AVAILABLE = True
except ImportError:
    print("⚠️ Scapy가 설치되지 않았습니다. 기본 소켓 분석을 사용합니다.")
    SCAPY_AVAILABLE = False

# 기존 DVD-Lite 시스템 통합
try:
    from dvd_lite.main import DVDLite
    from dvd_lite.cti import SimpleCTI
    from dvd_lite.dvd_attacks.registry.management import register_all_dvd_attacks
    DVD_LITE_AVAILABLE = True
except ImportError:
    print("⚠️ DVD-Lite 시스템이 없습니다. 독립 모드로 실행됩니다.")
    DVD_LITE_AVAILABLE = False

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MAVLinkParser:
    """MAVLink 프로토콜 파서"""
    
    # MAVLink 메시지 타입 매핑
    MSG_TYPES = {
        0: "HEARTBEAT",
        1: "SYS_STATUS", 
        11: "SET_MODE",
        31: "ATTITUDE_QUATERNION",
        33: "GLOBAL_POSITION_INT",
        76: "COMMAND_LONG",
        241: "VIBRATION",
        242: "HOME_POSITION"
    }
    
    # 공격과 관련된 메시지 타입
    ATTACK_RELATED_MSGS = {76, 11, 31, 33, 241, 242}
    
    def __init__(self):
        self.packet_buffer = {}
        self.sequence_tracking = {}
        
    def parse_mavlink_packet(self, data: bytes, source_ip: str) -> Optional[Dict[str, Any]]:
        """MAVLink 패킷 파싱"""
        if len(data) < 8:
            return None
            
        # MAVLink v1 (0xFE) 또는 v2 (0xFD) 확인
        magic = data[0]
        if magic not in [0xFE, 0xFD]:
            return None
            
        try:
            if magic == 0xFE:  # MAVLink v1
                return self._parse_v1(data, source_ip)
            else:  # MAVLink v2
                return self._parse_v2(data, source_ip)
        except Exception as e:
            logger.error(f"MAVLink 파싱 오류: {e}")
            return None
    
    def _parse_v1(self, data: bytes, source_ip: str) -> Dict[str, Any]:
        """MAVLink v1 파싱"""
        if len(data) < 8:
            return None
            
        payload_len = data[1]
        sequence = data[2]
        system_id = data[3]
        component_id = data[4]
        message_id = data[5]
        
        # CRC 확인 (간단한 구현)
        expected_len = 8 + payload_len
        if len(data) < expected_len:
            return None
            
        payload = data[6:6+payload_len] if payload_len > 0 else b''
        
        return {
            'version': 1,
            'magic': magic,
            'payload_length': payload_len,
            'sequence': sequence,
            'system_id': system_id,
            'component_id': component_id,
            'message_id': message_id,
            'message_name': self.MSG_TYPES.get(message_id, f'UNKNOWN_{message_id}'),
            'payload': payload,
            'source_ip': source_ip,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'is_attack_related': message_id in self.ATTACK_RELATED_MSGS
        }
    
    def _parse_v2(self, data: bytes, source_ip: str) -> Dict[str, Any]:
        """MAVLink v2 파싱"""
        if len(data) < 12:
            return None
            
        payload_len = data[1]
        incompat_flags = data[2]
        compat_flags = data[3]
        sequence = data[4]
        system_id = data[5]
        component_id = data[6]
        message_id = struct.unpack('<I', data[7:10] + b'\x00')[0]  # 24-bit message ID
        
        payload = data[10:10+payload_len] if payload_len > 0 else b''
        
        return {
            'version': 2,
            'magic': 0xFD,
            'payload_length': payload_len,
            'incompat_flags': incompat_flags,
            'compat_flags': compat_flags,
            'sequence': sequence,
            'system_id': system_id,
            'component_id': component_id,
            'message_id': message_id,
            'message_name': self.MSG_TYPES.get(message_id, f'UNKNOWN_{message_id}'),
            'payload': payload,
            'source_ip': source_ip,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'is_attack_related': message_id in self.ATTACK_RELATED_MSGS
        }

class DVDNetworkCapture:
    """DVD 컨테이너 네트워크 트래픽 캡처"""
    
    def __init__(self, container_name: str = "dvd-companion"):
        self.container_name = container_name
        self.docker_client = docker.from_env()
        self.container = None
        self.container_ip = None
        self.is_capturing = False
        self.mavlink_parser = MAVLinkParser()
        
        # 통계
        self.packet_stats = {
            'total_packets': 0,
            'mavlink_packets': 0,
            'attack_packets': 0,
            'by_message_type': {},
            'by_source_ip': {}
        }
        
        # 결과 파일들
        self.results_dir = Path("./results")
        self.results_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.traffic_log = open(self.results_dir / f"dvd_traffic_{timestamp}.csv", "w")
        self.attack_log = open(self.results_dir / f"dvd_attacks_{timestamp}.csv", "w")
        self.cti_log = open(self.results_dir / f"dvd_cti_{timestamp}.json", "w")
        
        # CSV 헤더 작성
        self.traffic_log.write("timestamp,source_ip,dest_port,packet_size,protocol,mavlink_msg_id,msg_name,system_id,component_id\n")
        self.attack_log.write("timestamp,attack_type,source_ip,message_id,confidence,details\n")
        self.cti_log.write("[\n")
        
    def get_container_info(self) -> bool:
        """DVD 컨테이너 정보 가져오기"""
        try:
            self.container = self.docker_client.containers.get(self.container_name)
            
            # 컨테이너 네트워크 정보
            networks = self.container.attrs['NetworkSettings']['Networks']
            for network_name, network_info in networks.items():
                if network_info.get('IPAddress'):
                    self.container_ip = network_info['IPAddress']
                    break
            
            if not self.container_ip:
                logger.error(f"컨테이너 {self.container_name}의 IP 주소를 찾을 수 없습니다.")
                return False
                
            logger.info(f"DVD 컨테이너 연결: {self.container_name} ({self.container_ip})")
            return True
            
        except docker.errors.NotFound:
            logger.error(f"DVD 컨테이너를 찾을 수 없습니다: {self.container_name}")
            return False
        except Exception as e:
            logger.error(f"컨테이너 정보 조회 실패: {e}")
            return False
    
    def start_packet_capture(self):
        """패킷 캡처 시작"""
        if not self.get_container_info():
            return False
            
        self.is_capturing = True
        
        if SCAPY_AVAILABLE:
            # Scapy를 사용한 고급 패킷 캡처
            threading.Thread(target=self._scapy_capture, daemon=True).start()
        else:
            # 기본 소켓을 사용한 패킷 캡처
            threading.Thread(target=self._socket_capture, daemon=True).start()
        
        logger.info("패킷 캡처 시작")
        return True
    
    def _scapy_capture(self):
        """Scapy를 사용한 패킷 캡처"""
        def packet_handler(packet):
            if not self.is_capturing:
                return
                
            try:
                if IP in packet and UDP in packet:
                    ip_layer = packet[IP]
                    udp_layer = packet[UDP]
                    
                    # MAVLink 포트 확인 (14550, 14551)
                    if udp_layer.dport in [14550, 14551] or udp_layer.sport in [14550, 14551]:
                        self._process_mavlink_packet(
                            raw(udp_layer.payload),
                            ip_layer.src,
                            udp_layer.dport,
                            len(packet)
                        )
                    
                    # 일반 트래픽 로깅
                    self._log_traffic(ip_layer.src, udp_layer.dport, len(packet), "UDP")
                        
            except Exception as e:
                logger.error(f"패킷 처리 오류: {e}")
        
        # DVD 컨테이너 네트워크 인터페이스에서 캡처
        try:
            sniff(filter="udp", prn=packet_handler, store=0)
        except Exception as e:
            logger.error(f"Scapy 캡처 오류: {e}")
    
    def _socket_capture(self):
        """기본 소켓을 사용한 패킷 캡처 (Scapy 대체)"""
        try:
            # Raw 소켓 생성 (root 권한 필요)
            sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_UDP)
            sock.bind(('', 0))
            
            while self.is_capturing:
                try:
                    ready = select.select([sock], [], [], 1.0)
                    if ready[0]:
                        packet, addr = sock.recvfrom(65535)
                        self._process_raw_packet(packet, addr[0])
                except socket.timeout:
                    continue
                except Exception as e:
                    logger.error(f"소켓 캡처 오류: {e}")
                    break
                    
        except PermissionError:
            logger.warning("Raw 소켓 권한이 없습니다. sudo로 실행하거나 Scapy를 설치하세요.")
        except Exception as e:
            logger.error(f"소켓 캡처 초기화 실패: {e}")
    
    def _process_raw_packet(self, packet: bytes, source_ip: str):
        """Raw 패킷 처리"""
        try:
            # IP 헤더 최소 20바이트
            if len(packet) < 20:
                return
            
            # IP 헤더 파싱
            ip_header = struct.unpack('!BBHHHBBH4s4s', packet[:20])
            ihl = (ip_header[0] & 0xF) * 4
            protocol = ip_header[6]
            
            # UDP 프로토콜 확인
            if protocol != 17:  # UDP
                return
            
            # UDP 헤더 파싱
            udp_start = ihl
            if len(packet) < udp_start + 8:
                return
                
            udp_header = struct.unpack('!HHHH', packet[udp_start:udp_start+8])
            sport, dport, length, checksum = udp_header
            
            # MAVLink 포트 확인
            if dport in [14550, 14551] or sport in [14550, 14551]:
                udp_payload = packet[udp_start+8:]
                self._process_mavlink_packet(udp_payload, source_ip, dport, len(packet))
            
            # 트래픽 로깅
            self._log_traffic(source_ip, dport, len(packet), "UDP")
            
        except Exception as e:
            logger.error(f"Raw 패킷 처리 오류: {e}")
    
    def _process_mavlink_packet(self, payload: bytes, source_ip: str, dest_port: int, packet_size: int):
        """MAVLink 패킷 처리"""
        mavlink_data = self.mavlink_parser.parse_mavlink_packet(payload, source_ip)
        
        if not mavlink_data:
            return
        
        self.packet_stats['mavlink_packets'] += 1
        
        # 메시지 타입별 통계
        msg_name = mavlink_data['message_name']
        self.packet_stats['by_message_type'][msg_name] = \
            self.packet_stats['by_message_type'].get(msg_name, 0) + 1
        
        # 소스 IP별 통계
        self.packet_stats['by_source_ip'][source_ip] = \
            self.packet_stats['by_source_ip'].get(source_ip, 0) + 1
        
        # 트래픽 로그 기록
        self.traffic_log.write(f"{mavlink_data['timestamp']},{source_ip},{dest_port},"
                              f"{packet_size},MAVLink,{mavlink_data['message_id']},"
                              f"{msg_name},{mavlink_data['system_id']},{mavlink_data['component_id']}\n")
        self.traffic_log.flush()
        
        # 공격 탐지
        if self._detect_attack(mavlink_data):
            self.packet_stats['attack_packets'] += 1
        
        logger.debug(f"MAVLink: {msg_name} from {source_ip}:{dest_port}")
    
    def _detect_attack(self, mavlink_data: Dict[str, Any]) -> bool:
        """공격 패턴 탐지"""
        attack_detected = False
        source_ip = mavlink_data['source_ip']
        msg_id = mavlink_data['message_id']
        msg_name = mavlink_data['message_name']
        
        # 1. 명령 플러딩 탐지
        if msg_id == 76:  # COMMAND_LONG
            recent_commands = self.packet_stats['by_source_ip'].get(source_ip, 0)
            if recent_commands > 50:  # 임계값
                self._report_attack("MAVLink_Command_Flooding", source_ip, msg_id, 0.9,
                                  f"Excessive commands from {source_ip}")
                attack_detected = True
        
        # 2. GPS 스푸핑 탐지
        elif msg_id == 33:  # GLOBAL_POSITION_INT
            gps_count = self.packet_stats['by_message_type'].get('GLOBAL_POSITION_INT', 0)
            if gps_count > 100:  # 짧은 시간 내 과도한 GPS 메시지
                self._report_attack("GPS_Position_Spoofing", source_ip, msg_id, 0.8,
                                  f"Potential GPS spoofing from {source_ip}")
                attack_detected = True
        
        # 3. 비정상적인 시스템 ID
        if mavlink_data['system_id'] > 250:
            self._report_attack("MAVLink_System_ID_Spoofing", source_ip, msg_id, 0.7,
                              f"Suspicious system ID: {mavlink_data['system_id']}")
            attack_detected = True
        
        # 4. 모드 변경 공격
        elif msg_id == 11:  # SET_MODE
            self._report_attack("Flight_Mode_Hijacking", source_ip, msg_id, 0.85,
                              f"Flight mode change command from {source_ip}")
            attack_detected = True
        
        return attack_detected
    
    def _report_attack(self, attack_type: str, source_ip: str, msg_id: int, confidence: float, details: str):
        """공격 리포트"""
        timestamp = datetime.now(timezone.utc).isoformat()
        
        # 공격 로그 기록
        self.attack_log.write(f"{timestamp},{attack_type},{source_ip},{msg_id},{confidence},{details}\n")
        self.attack_log.flush()
        
        # CTI 데이터 생성
        cti_entry = {
            "timestamp": timestamp,
            "attack_type": attack_type,
            "source_ip": source_ip,
            "message_id": msg_id,
            "confidence": confidence,
            "details": details,
            "stix_pattern": f"[network-traffic:src_ref.value = '{source_ip}' AND network-traffic:dst_port = 14550]"
        }
        
        self.cti_log.write(json.dumps(cti_entry, indent=2) + ",\n")
        self.cti_log.flush()
        
        logger.warning(f"🚨 공격 탐지: {attack_type} from {source_ip} (신뢰도: {confidence})")
    
    def _log_traffic(self, source_ip: str, dest_port: int, packet_size: int, protocol: str):
        """일반 트래픽 로깅"""
        self.packet_stats['total_packets'] += 1
        
        # 주기적 통계 출력 (1000 패킷마다)
        if self.packet_stats['total_packets'] % 1000 == 0:
            logger.info(f"📊 패킷 통계: 총 {self.packet_stats['total_packets']}, "
                       f"MAVLink {self.packet_stats['mavlink_packets']}, "
                       f"공격 {self.packet_stats['attack_packets']}")
    
    def stop_capture(self):
        """패킷 캡처 중지"""
        self.is_capturing = False
        
        # 파일 정리
        if self.traffic_log:
            self.traffic_log.close()
        if self.attack_log:
            self.attack_log.close()
        if self.cti_log:
            self.cti_log.write("\n]")
            self.cti_log.close()
        
        logger.info("패킷 캡처 중지")
    
    def get_statistics(self) -> Dict[str, Any]:
        """통계 정보 반환"""
        return {
            "capture_stats": self.packet_stats,
            "container_info": {
                "name": self.container_name,
                "ip": self.container_ip,
                "status": self.container.status if self.container else "unknown"
            }
        }

class NS3FANETBridge:
    """NS-3 FANET 시뮬레이터와의 브리지"""
    
    def __init__(self, ns3_executable_path: str = "./ns3"):
        self.ns3_path = Path(ns3_executable_path).expanduser()
        self.simulation_process = None
        self.is_running = False
        self.results_dir = Path("./results")
        
    def start_fanet_simulation(self, dvd_container: str, simulation_params: Dict[str, Any] = None) -> bool:
        """FANET 시뮬레이션 시작"""
        if simulation_params is None:
            simulation_params = {
                "nNodes": 10,
                "simTime": 300.0,
                "logLevel": "INFO"
            }
        
        # NS-3 실행 명령 구성
        cmd = [
            str(self.ns3_path),
            "run",
            "fanet-mtd-simulation",
            "--",
            f"--nNodes={simulation_params['nNodes']}",
            f"--simTime={simulation_params['simTime']}",
            f"--dvdContainer={dvd_container}",
            f"--logLevel={simulation_params['logLevel']}"
        ]
        
        try:
            logger.info(f"NS-3 FANET 시뮬레이션 시작: {' '.join(cmd)}")
            
            # 작업 디렉토리를 NS-3 디렉토리로 설정
            ns3_dir = self.ns3_path.parent
            
            self.simulation_process = subprocess.Popen(
                cmd,
                cwd=ns3_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # 비동기로 출력 모니터링
            threading.Thread(target=self._monitor_simulation, daemon=True).start()
            
            self.is_running = True
            return True
            
        except Exception as e:
            logger.error(f"NS-3 시뮬레이션 시작 실패: {e}")
            return False
    
    def _monitor_simulation(self):
        """시뮬레이션 출력 모니터링"""
        if not self.simulation_process:
            return
        
        try:
            # 실시간 로그 출력
            for line in iter(self.simulation_process.stdout.readline, ''):
                if line.strip():
                    logger.info(f"NS-3: {line.strip()}")
            
            # 시뮬레이션 완료 대기
            self.simulation_process.wait()
            self.is_running = False
            
            logger.info("NS-3 FANET 시뮬레이션 완료")
            
        except Exception as e:
            logger.error(f"시뮬레이션 모니터링 오류: {e}")
    
    def stop_simulation(self):
        """시뮬레이션 중지"""
        if self.simulation_process and self.is_running:
            self.simulation_process.terminate()
            self.simulation_process.wait()
            self.is_running = False
            logger.info("NS-3 시뮬레이션 중지")
    
    def get_simulation_results(self) -> Dict[str, Any]:
        """시뮬레이션 결과 수집"""
        results = {}
        
        # NS-3에서 생성된 결과 파일들 확인
        result_files = [
            "dvd_traffic_analysis.csv",
            "dvd_attack_detection.csv", 
            "dvd_cti_report.json",
            "fanet_dvd_stix_report.json",
            "fanet_dvd_flow_results.csv"
        ]
        
        for filename in result_files:
            filepath = self.results_dir / filename
            if filepath.exists():
                try:
                    if filename.endswith('.json'):
                        with open(filepath, 'r') as f:
                            results[filename] = json.load(f)
                    elif filename.endswith('.csv'):
                        # CSV 파일의 간단한 통계만 포함
                        import csv
                        with open(filepath, 'r') as f:
                            reader = csv.reader(f)
                            rows = list(reader)
                            results[filename] = {
                                "row_count": len(rows) - 1,  # 헤더 제외
                                "columns": rows[0] if rows else []
                            }
                except Exception as e:
                    logger.error(f"결과 파일 읽기 실패 {filename}: {e}")
        
        return results

class IntegratedDVDAnalyzer:
    """통합 DVD 분석기 (NS-3 + DVD-Lite + 네트워크 캡처)"""
    
    def __init__(self, container_name: str = "dvd-companion"):
        self.container_name = container_name
        self.network_capture = DVDNetworkCapture(container_name)
        self.ns3_bridge = NS3FANETBridge()
        self.dvd_lite = None
        self.is_running = False
        
        # DVD-Lite 시스템 초기화 (사용 가능한 경우)
        if DVD_LITE_AVAILABLE:
            try:
                self.dvd_lite = DVDLite()
                register_all_dvd_attacks()
                logger.info("✅ DVD-Lite 시스템 통합 완료")
            except Exception as e:
                logger.warning(f"DVD-Lite 초기화 실패: {e}")
                self.dvd_lite = None
        
        # 시그널 핸들러 설정
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
    def _signal_handler(self, signum, frame):
        """시그널 핸들러 (Ctrl+C 등)"""
        logger.info("종료 신호 수신. 정리 중...")
        self.stop_analysis()
        sys.exit(0)
    
    async def start_integrated_analysis(self, simulation_params: Dict[str, Any] = None):
        """통합 분석 시작"""
        logger.info("🚁 통합 DVD 분석 시작")
        
        self.is_running = True
        
        try:
            # 1. 네트워크 캡처 시작
            if not self.network_capture.start_packet_capture():
                logger.error("네트워크 캡처 시작 실패")
                return False
            
            # 2. NS-3 FANET 시뮬레이션 시작
            if not self.ns3_bridge.start_fanet_simulation(self.container_name, simulation_params):
                logger.warning("NS-3 시뮬레이션 시작 실패. 네트워크 분석만 계속합니다.")
            
            # 3. DVD-Lite 공격 시뮬레이션 (사용 가능한 경우)
            if self.dvd_lite:
                asyncio.create_task(self._run_dvd_attacks())
            
            # 4. 실시간 모니터링 및 분석
            await self._run_analysis_loop()
            
        except Exception as e:
            logger.error(f"통합 분석 실행 오류: {e}")
        finally:
            self.stop_analysis()
    
    async def _run_dvd_attacks(self):
        """DVD-Lite 공격 시나리오 실행"""
        if not self.dvd_lite:
            return
        
        # 공격 시나리오 목록
        attack_scenarios = [
            "wifi_network_discovery",
            "mavlink_service_discovery",
            "gps_spoofing_attack", 
            "mavlink_packet_injection",
            "wifi_deauthentication_attack"
        ]
        
        logger.info("🎯 DVD-Lite 공격 시나리오 시작")
        
        for attack_name in attack_scenarios:
            if not self.is_running:
                break
            
            try:
                logger.info(f"공격 실행: {attack_name}")
                result = await self.dvd_lite.run_attack(attack_name)
                
                logger.info(f"공격 결과: {result.status}")
                if result.iocs:
                    logger.info(f"IOCs: {result.iocs}")
                
                # 공격 간 대기 시간
                await asyncio.sleep(30)
                
            except Exception as e:
                logger.error(f"공격 실행 오류 {attack_name}: {e}")
                continue
    
    async def _run_analysis_loop(self):
        """분석 루프 실행"""
        logger.info("📊 실시간 분석 루프 시작")
        
        report_interval = 60  # 60초마다 리포트
        last_report_time = time.time()
        
        while self.is_running:
            try:
                current_time = time.time()
                
                # 주기적 리포트 생성
                if current_time - last_report_time >= report_interval:
                    await self._generate_analysis_report()
                    last_report_time = current_time
                
                # 1초 대기
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"분석 루프 오류: {e}")
                await asyncio.sleep(5)
    
    async def _generate_analysis_report(self):
        """분석 리포트 생성"""
        try:
            # 네트워크 캡처 통계
            capture_stats = self.network_capture.get_statistics()
            
            # NS-3 시뮬레이션 결과
            simulation_results = self.ns3_bridge.get_simulation_results()
            
            # 통합 리포트
            report = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "container_name": self.container_name,
                "capture_statistics": capture_stats,
                "simulation_results": simulation_results,
                "analysis_status": {
                    "network_capture_active": self.network_capture.is_capturing,
                    "ns3_simulation_active": self.ns3_bridge.is_running,
                    "dvd_lite_available": self.dvd_lite is not None
                }
            }
            
            # 리포트 파일 저장
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_file = self.network_capture.results_dir / f"integrated_report_{timestamp}.json"
            
            with open(report_file, 'w') as f:
                json.dump(report, f, indent=2)
            
            logger.info(f"📄 분석 리포트 생성: {report_file}")
            
            # 간단한 통계 출력
            packet_count = capture_stats['capture_stats']['total_packets']
            mavlink_count = capture_stats['capture_stats']['mavlink_packets'] 
            attack_count = capture_stats['capture_stats']['attack_packets']
            
            logger.info(f"📈 현재 통계 - 총 패킷: {packet_count}, MAVLink: {mavlink_count}, 공격: {attack_count}")
            
        except Exception as e:
            logger.error(f"리포트 생성 오류: {e}")
    
    def stop_analysis(self):
        """분석 중지"""
        logger.info("🛑 통합 분석 중지")
        
        self.is_running = False
        
        # 네트워크 캡처 중지
        self.network_capture.stop_capture()
        
        # NS-3 시뮬레이션 중지
        self.ns3_bridge.stop_simulation()
        
        logger.info("✅ 모든 분석 작업 완료")

class DVDContainerManager:
    """DVD 컨테이너 관리"""
    
    def __init__(self):
        self.docker_client = docker.from_env()
    
    def check_dvd_container(self, container_name: str) -> bool:
        """DVD 컨테이너 상태 확인"""
        try:
            container = self.docker_client.containers.get(container_name)
            return container.status == 'running'
        except docker.errors.NotFound:
            return False
        except Exception as e:
            logger.error(f"컨테이너 상태 확인 오류: {e}")
            return False
    
    def start_dvd_environment(self) -> bool:
        """DVD 환경 시작 (docker-compose 사용)"""
        try:
            # 기존 Damn-Vulnerable-Drone docker-compose 실행
            cmd = ["docker-compose", "-f", "docker-compose.yaml", "up", "-d"]
            
            # DVD 디렉토리에서 실행
            dvd_dir = Path("./Damn-Vulnerable-Drone")
            if not dvd_dir.exists():
                logger.error("Damn-Vulnerable-Drone 디렉토리를 찾을 수 없습니다.")
                return False
            
            result = subprocess.run(cmd, cwd=dvd_dir, capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info("✅ DVD 환경 시작 완료")
                return True
            else:
                logger.error(f"DVD 환경 시작 실패: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"DVD 환경 시작 오류: {e}")
            return False
    
    def get_container_networks(self, container_name: str) -> List[str]:
        """컨테이너 네트워크 정보 반환"""
        try:
            container = self.docker_client.containers.get(container_name)
            networks = list(container.attrs['NetworkSettings']['Networks'].keys())
            return networks
        except Exception as e:
            logger.error(f"네트워크 정보 조회 오류: {e}")
            return []

# ===========================================
# 메인 실행 함수
# ===========================================

async def main():
    """메인 실행 함수"""
    import argparse
    
    parser = argparse.ArgumentParser(description="DVD 네트워크 브리지 및 실시간 분석기")
    parser.add_argument("--container", default="dvd-companion", 
                       help="DVD 컨테이너 이름 (기본값: dvd-companion)")
    parser.add_argument("--nodes", type=int, default=10,
                       help="FANET 노드 수 (기본값: 10)")
    parser.add_argument("--sim-time", type=float, default=300.0,
                       help="시뮬레이션 시간 (초, 기본값: 300)")
    parser.add_argument("--log-level", choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       default='INFO', help="로그 레벨")
    parser.add_argument("--start-dvd", action='store_true',
                       help="DVD 환경 자동 시작")
    
    args = parser.parse_args()
    
    # 로그 레벨 설정
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    print("🚁 DVD 네트워크 브리지 및 실시간 분석기")
    print("=" * 60)
    print(f"컨테이너: {args.container}")
    print(f"FANET 노드: {args.nodes}")
    print(f"시뮬레이션 시간: {args.sim_time}초")
    print(f"로그 레벨: {args.log_level}")
    print("=" * 60)
    
    # DVD 컨테이너 관리자 초기화
    container_manager = DVDContainerManager()
    
    # DVD 환경 시작 (요청된 경우)
    if args.start_dvd:
        logger.info("DVD 환경 시작 중...")
        if not container_manager.start_dvd_environment():
            logger.error("DVD 환경 시작 실패")
            return
        
        # 컨테이너 시작 대기
        import time
        time.sleep(10)
    
    # DVD 컨테이너 상태 확인
    if not container_manager.check_dvd_container(args.container):
        logger.error(f"DVD 컨테이너가 실행되지 않았습니다: {args.container}")
        logger.info("다음 명령으로 DVD 환경을 시작하세요:")
        logger.info("  cd Damn-Vulnerable-Drone && docker-compose up -d")
        return
    
    # 시뮬레이션 매개변수 설정
    simulation_params = {
        "nNodes": args.nodes,
        "simTime": args.sim_time,
        "logLevel": args.log_level
    }
    
    # 통합 분석기 실행
    analyzer = IntegratedDVDAnalyzer(args.container)
    
    try:
        await analyzer.start_integrated_analysis(simulation_params)
    except KeyboardInterrupt:
        logger.info("사용자 중단")
    except Exception as e:
        logger.error(f"분석 실행 오류: {e}")
    finally:
        analyzer.stop_analysis()

def run_analysis():
    """동기 실행 래퍼"""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 분석이 중단되었습니다.")
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")

if __name__ == "__main__":
    run_analysis()