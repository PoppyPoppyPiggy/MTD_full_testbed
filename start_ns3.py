#!/usr/bin/env python3
"""
간단한 NS-3 시뮬레이션 서비스
FANET 네트워크 시뮬레이션
"""

import socket
import json
import time
import threading
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SimpleNS3:
    def __init__(self, port=9999):
        self.port = port
        self.running = False
        
    def start_service(self):
        """NS-3 서비스 시작"""
        self.running = True
        logger.info(f"NS-3 시뮬레이션 서비스 시작 - 포트 {self.port}")
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(('127.0.0.1', self.port))
            sock.listen(5)
            sock.settimeout(1.0)
            
            client_count = 0
            
            while self.running:
                try:
                    client, addr = sock.accept()
                    client_count += 1
                    
                    # 클라이언트 요청 처리
                    self.handle_client(client, addr, client_count)
                    
                except socket.timeout:
                    continue
                except Exception as e:
                    logger.error(f"연결 처리 오류: {e}")
                    
        except Exception as e:
            logger.error(f"NS-3 서비스 오류: {e}")
        finally:
            if 'sock' in locals():
                sock.close()
            logger.info("NS-3 서비스 종료됨")
    
    def handle_client(self, client, addr, client_num):
        """클라이언트 요청 처리"""
        try:
            data = client.recv(1024)
            
            response = {
                "status": "ok",
                "simulation_time": time.time(),
                "nodes": 10,
                "topology": "mesh",
                "client_number": client_num,
                "fanet_active": True
            }
            
            client.send(json.dumps(response).encode())
            logger.info(f"클라이언트 {client_num} 응답 전송: {addr}")
            
        except Exception as e:
            logger.error(f"클라이언트 처리 오류: {e}")
        finally:
            client.close()

    def stop_service(self):
        """NS-3 서비스 중지"""
        self.running = False

if __name__ == "__main__":
    ns3 = SimpleNS3()
    try:
        ns3.start_service()
    except KeyboardInterrupt:
        logger.info("사용자에 의해 중단됨")
        ns3.stop_service()
