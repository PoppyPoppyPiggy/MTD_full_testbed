#!/usr/bin/env python3
# 파일 위치: /home/kali/MTD/MTD_full_testbed/start_ns3_fanet.py
"""NS-3 FANET 네트워크 시뮬레이션 서비스"""

import socket
import json
import time
import threading
import logging
import random
import math
import sys
import signal

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class FANETNode:
    def __init__(self, node_id, position):
        self.node_id = node_id
        self.position = position
        self.neighbors = []
        self.energy = 100.0
        self.velocity = (0.0, 0.0, 0.0)

class NS3FANETService:
    def __init__(self, port=9999):
        self.port = port
        self.running = False
        self.nodes = {}
        self.simulation_time = 0.0
        self.topology_changes = 0
        self.sock = None
        
    def start_service(self):
        self.running = True
        logger.info(f"🌐 NS-3 FANET 서비스 시작 - 포트 {self.port}")
        
        # 초기 노드 생성
        self.initialize_nodes()
        
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
            logger.error(f"NS-3 FANET 서비스 오류: {e}")
        finally:
            self.cleanup()
            logger.info("🌐 NS-3 FANET 서비스 종료됨")
    
    def initialize_nodes(self):
        logger.info("🔧 FANET 노드 초기화 중...")
        for i in range(10):
            node_id = f"fanet_node_{i:02d}"
            position = (
                random.uniform(-1000, 1000),
                random.uniform(-1000, 1000),
                random.uniform(50, 500)
            )
            self.nodes[node_id] = FANETNode(node_id, position)
            logger.info(f"📡 노드 생성: {node_id} at ({position[0]:.1f}, {position[1]:.1f}, {position[2]:.1f})")
    
    def run_simulation(self):
        while self.running:
            self.simulation_time += 1.0
            
            # 노드 이동
            self.update_mobility()
            
            # 토폴로지 업데이트
            if int(self.simulation_time) % 5 == 0:
                self.update_topology()
            
            if int(self.simulation_time) % 10 == 0:
                total_connections = sum(len(node.neighbors) for node in self.nodes.values()) // 2
                logger.info(f"📊 FANET 시간: {self.simulation_time}s, 노드: {len(self.nodes)}개, 연결: {total_connections}개")
            
            time.sleep(1.0)
    
    def update_mobility(self):
        """노드 이동성 업데이트"""
        for node in self.nodes.values():
            if random.random() < 0.1:  # 10% 확률로 방향 변경
                angle = random.uniform(0, 2 * math.pi)
                speed = random.uniform(5, 15)
                node.velocity = (
                    speed * math.cos(angle),
                    speed * math.sin(angle),
                    random.uniform(-2, 2)
                )
            
            # 위치 업데이트
            x, y, z = node.position
            vx, vy, vz = node.velocity
            
            new_x = max(-2000, min(2000, x + vx))
            new_y = max(-2000, min(2000, y + vy))
            new_z = max(50, min(500, z + vz))
            
            node.position = (new_x, new_y, new_z)
    
    def update_topology(self):
        """토폴로지 업데이트"""
        for node in self.nodes.values():
            node.neighbors.clear()
        
        nodes_list = list(self.nodes.values())
        for i, node1 in enumerate(nodes_list):
            for node2 in nodes_list[i+1:]:
                distance = self.calculate_distance(node1.position, node2.position)
                if distance <= 300:  # 통신 범위
                    node1.neighbors.append(node2.node_id)
                    node2.neighbors.append(node1.node_id)
        
        self.topology_changes += 1
    
    def calculate_distance(self, pos1, pos2):
        return math.sqrt(sum((a - b) ** 2 for a, b in zip(pos1, pos2)))
    
    def handle_client(self, client, addr, client_num):
        try:
            logger.info(f"🔗 NS-3 클라이언트 연결: {addr} (#{client_num})")
            data = client.recv(1024)
            
            total_connections = sum(len(node.neighbors) for node in self.nodes.values()) // 2
            avg_degree = total_connections * 2 / len(self.nodes) if self.nodes else 0
            
            response = {
                "status": "running",
                "simulation_time": self.simulation_time,
                "nodes": len(self.nodes),
                "connections": total_connections,
                "avg_degree": round(avg_degree, 2),
                "topology_changes": self.topology_changes,
                "fanet_protocol": "AODV",
                "mobility_model": "RandomWaypoint",
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
    global fanet_service
    if 'fanet_service' in globals():
        fanet_service.stop_service()
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    fanet_service = NS3FANETService()
    try:
        fanet_service.start_service()
    except KeyboardInterrupt:
        logger.info("사용자에 의해 중단됨")
    finally:
        fanet_service.stop_service()
