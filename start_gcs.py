#!/usr/bin/env python3
"""
간단한 GCS 시뮬레이션 서비스
MAVLink 패킷 수신 및 응답
"""

import socket
import time
import threading
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SimpleGCS:
    def __init__(self, port=14550):
        self.port = port
        self.running = False
        
    def start_service(self):
        """GCS 서비스 시작"""
        self.running = True
        logger.info(f"GCS 서비스 시작 - 포트 {self.port}")
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.bind(('127.0.0.1', self.port))
            sock.settimeout(1.0)
            
            packet_count = 0
            
            while self.running:
                try:
                    data, addr = sock.recvfrom(1024)
                    packet_count += 1
                    
                    if packet_count % 100 == 0:  # 100개마다 로그
                        logger.info(f"MAVLink 패킷 수신: {packet_count}개")
                        
                except socket.timeout:
                    continue
                except Exception as e:
                    logger.error(f"수신 오류: {e}")
                    
        except Exception as e:
            logger.error(f"GCS 서비스 오류: {e}")
        finally:
            if 'sock' in locals():
                sock.close()
            logger.info("GCS 서비스 종료됨")

    def stop_service(self):
        """GCS 서비스 중지"""
        self.running = False

if __name__ == "__main__":
    gcs = SimpleGCS()
    try:
        gcs.start_service()
    except KeyboardInterrupt:
        logger.info("사용자에 의해 중단됨")
        gcs.stop_service()
