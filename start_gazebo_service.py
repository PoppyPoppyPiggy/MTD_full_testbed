#!/usr/bin/env python3
# 파일 위치: /home/kali/MTD/MTD_full_testbed/start_gazebo_service.py
"""Gazebo 시뮬레이션 대체 서비스"""

import socket
import json
import time
import threading
import logging
import sys
import signal

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class GazeboService:
    def __init__(self, port=11345):
        self.port = port
        self.running = False
        self.simulation_time = 0.0
        self.drones = {}
        self.sock = None
        
    def start_service(self):
        self.running = True
        logger.info(f"🌍 Gazebo 서비스 시작 - 포트 {self.port}")
        
        # 시뮬레이션 스레드
        sim_thread = threading.Thread(target=self.run_simulation)
        sim_thread.daemon = True
        sim_thread.start()
        
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.bind(('127.0.0.1', self.port))
            self.sock.listen(5)
            self.sock.settimeout(1.0)
            
            client_count = 0
            
            while self.running:
                try:
                    client, addr = self.sock.accept()
                    client_count += 1
                    client_thread = threading.Thread(
                        target=self.handle_client, 
                        args=(client, addr, client_count)
                    )
                    client_thread.daemon = True
                    client_thread.start()
                except socket.timeout:
                    continue
                except socket.error as e:
                    if self.running:
                        logger.error(f"소켓 오류: {e}")
                    break
                except Exception as e:
                    logger.error(f"클라이언트 연결 오류: {e}")
                    
        except Exception as e:
            logger.error(f"Gazebo 서비스 오류: {e}")
        finally:
            self.cleanup()
            logger.info("🌍 Gazebo 서비스 종료됨")
    
    def run_simulation(self):
        while self.running:
            self.simulation_time += 0.1
            if int(self.simulation_time) % 10 == 0 and self.simulation_time % 1 < 0.1:
                logger.info(f"⏱️ 시뮬레이션 시간: {self.simulation_time:.1f}초, 드론: {len(self.drones)}대")
            time.sleep(0.1)
    
    def handle_client(self, client, addr, client_num):
        try:
            logger.info(f"🔗 Gazebo 클라이언트 연결: {addr} (#{client_num})")
            data = client.recv(1024)
            response = {
                "status": "running",
                "simulation_time": self.simulation_time,
                "world": "empty_world",
                "client_number": client_num
            }
            client.send(json.dumps(response).encode())
        except Exception as e:
            logger.error(f"클라이언트 처리 오류: {e}")
        finally:
            try:
                client.close()
            except:
                pass
    
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
    global gazebo_service
    if 'gazebo_service' in globals():
        gazebo_service.stop_service()
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    gazebo_service = GazeboService()
    try:
        gazebo_service.start_service()
    except KeyboardInterrupt:
        logger.info("사용자에 의해 중단됨")
    finally:
        gazebo_service.stop_service()
