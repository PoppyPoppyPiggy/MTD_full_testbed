#!/usr/bin/env python3
# 파일 위치: /home/kali/MTD/MTD_full_testbed/start_qgc_service.py
"""QGroundControl 대체 서비스"""

import socket
import time
import logging
import threading
import sys
import signal

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class QGCService:
    def __init__(self, port=14550):
        self.port = port
        self.running = False
        self.sock = None
        
    def start_service(self):
        self.running = True
        logger.info(f"🖥️ QGroundControl 서비스 시작 - 포트 {self.port}")
        
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.bind(('127.0.0.1', self.port))
            self.sock.settimeout(1.0)
            
            packet_count = 0
            last_log_time = time.time()
            
            while self.running:
                try:
                    data, addr = self.sock.recvfrom(1024)
                    packet_count += 1
                    
                    # 10초마다 로그 출력
                    current_time = time.time()
                    if current_time - last_log_time >= 10:
                        logger.info(f"📡 MAVLink 패킷 수신: {packet_count}개 from {addr[0]}")
                        last_log_time = current_time
                        
                except socket.timeout:
                    continue
                except socket.error as e:
                    if self.running:
                        logger.error(f"소켓 오류: {e}")
                    break
                except Exception as e:
                    logger.error(f"패킷 처리 오류: {e}")
                    
        except Exception as e:
            logger.error(f"QGC 서비스 오류: {e}")
        finally:
            self.cleanup()
            logger.info("🖥️ QGroundControl 서비스 종료됨")
    
    def cleanup(self):
        if self.sock:
            try:
                self.sock.close()
            except:
                pass
            self.sock = None
    
    def stop_service(self):
        self.running = False
        self.cleanup()

def signal_handler(signum, frame):
    logger.info("신호 수신됨, 서비스 종료 중...")
    global qgc_service
    if 'qgc_service' in globals():
        qgc_service.stop_service()
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    qgc_service = QGCService()
    try:
        qgc_service.start_service()
    except KeyboardInterrupt:
        logger.info("사용자에 의해 중단됨")
    finally:
        qgc_service.stop_service()
