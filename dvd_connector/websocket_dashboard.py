# dvd_connector/websocket_dashboard.py
"""
DVD-Lite 실시간 WebSocket 대시보드 및 통신 시스템
논문 작성을 위한 실시간 모니터링 및 데이터 시각화
"""

import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Dict, List, Any, Set
import websockets
from websockets.server import WebSocketServerProtocol
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

class WebSocketDashboardServer:
    """실시간 대시보드 WebSocket 서버"""
    
    def __init__(self, host: str = "localhost", port: int = 8765):
        self.host = host
        self.port = port
        self.connected_clients: Set[WebSocketServerProtocol] = set()
        self.server = None
        self.is_running = False
        
        # 대시보드 데이터 버퍼
        self.dashboard_data = {
            'attacks': [],
            'telemetry': [],
            'system_status': {},
            'real_time_metrics': {},
            'connection_count': 0
        }
        
        logger.info(f"🌐 WebSocket 대시보드 서버 초기화: {host}:{port}")
    
    async def start_server(self):
        """WebSocket 서버 시작"""
        try:
            self.server = await websockets.serve(
                self.handle_client_connection,
                self.host,
                self.port,
                ping_interval=20,
                ping_timeout=10
            )
            
            self.is_running = True
            logger.info(f"✅ WebSocket 서버 시작: ws://{self.host}:{self.port}")
            
            # 정기적 데이터 브로드캐스트 시작
            asyncio.create_task(self.periodic_broadcast())
            
        except Exception as e:
            logger.error(f"❌ WebSocket 서버 시작 실패: {e}")
            raise
    
    async def handle_client_connection(self, websocket: WebSocketServerProtocol, path: str):
        """클라이언트 연결 처리"""
        client_id = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        logger.info(f"🔗 클라이언트 연결: {client_id}")
        
        # 클라이언트 등록
        self.connected_clients.add(websocket)
        self.dashboard_data['connection_count'] = len(self.connected_clients)
        
        try:
            # 초기 데이터 전송
            await self.send_initial_data(websocket)
            
            # 클라이언트 메시지 처리
            async for message in websocket:
                await self.handle_client_message(websocket, message)
                
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"🔌 클라이언트 연결 종료: {client_id}")
        except Exception as e:
            logger.error(f"❌ 클라이언트 처리 오류 {client_id}: {e}")
        finally:
            # 클라이언트 정리
            self.connected_clients.discard(websocket)
            self.dashboard_data['connection_count'] = len(self.connected_clients)
    
    async def send_initial_data(self, websocket: WebSocketServerProtocol):
        """신규 클라이언트에게 초기 데이터 전송"""
        initial_data = {
            'type': 'initial_data',
            'timestamp': time.time(),
            'data': {
                'welcome_message': 'DVD-Lite 실시간 대시보드에 연결됨',
                'server_info': {
                    'version': '1.0.0',
                    'start_time': datetime.now().isoformat(),
                    'capabilities': ['real_time_attacks', 'telemetry_streaming', 'system_monitoring']
                },
                'dashboard_config': {
                    'update_interval': 1.0,  # seconds
                    'max_data_points': 100,
                    'supported_charts': ['line', 'bar', 'gauge', 'table']
                }
            }
        }
        
        await websocket.send(json.dumps(initial_data))
    
    async def handle_client_message(self, websocket: WebSocketServerProtocol, message: str):
        """클라이언트 메시지 처리"""
        try:
            data = json.loads(message)
            message_type = data.get('type')
            
            if message_type == 'ping':
                # 핑 응답
                response = {'type': 'pong', 'timestamp': time.time()}
                await websocket.send(json.dumps(response))
                
            elif message_type == 'request_data':
                # 특정 데이터 요청
                requested_data = data.get('data_type')
                response_data = await self.get_requested_data(requested_data)
                
                response = {
                    'type': 'data_response',
                    'requested_type': requested_data,
                    'timestamp': time.time(),
                    'data': response_data
                }
                await websocket.send(json.dumps(response))
                
            elif message_type == 'control_command':
                # 제어 명령 처리
                await self.handle_control_command(websocket, data)
                
            else:
                logger.warning(f"⚠️ 알 수 없는 메시지 타입: {message_type}")
                
        except json.JSONDecodeError:
            logger.error("❌ 잘못된 JSON 메시지 수신")
        except Exception as e:
            logger.error(f"❌ 메시지 처리 오류: {e}")
    
    async def get_requested_data(self, data_type: str) -> Dict[str, Any]:
        """요청된 데이터 반환"""
        if data_type == 'attacks':
            return {
                'recent_attacks': self.dashboard_data['attacks'][-10:],
                'attack_statistics': self.calculate_attack_statistics()
            }
        elif data_type == 'telemetry':
            return {
                'recent_telemetry': self.dashboard_data['telemetry'][-50:],
                'telemetry_summary': self.calculate_telemetry_summary()
            }
        elif data_type == 'system_status':
            return self.dashboard_data['system_status']
        elif data_type == 'all':
            return self.dashboard_data
        else:
            return {'error': f'Unknown data type: {data_type}'}
    
    async def handle_control_command(self, websocket: WebSocketServerProtocol, data: Dict[str, Any]):
        """제어 명령 처리"""
        command = data.get('command')
        
        if command == 'start_attack':
            # 공격 시작 명령
            attack_name = data.get('attack_name')
            response = {
                'type': 'command_response',
                'command': command,
                'status': 'accepted',
                'message': f'공격 {attack_name} 시작 요청을 접수했습니다.',
                'timestamp': time.time()
            }
            
        elif command == 'stop_collection':
            # 데이터 수집 중단
            response = {
                'type': 'command_response', 
                'command': command,
                'status': 'accepted',
                'message': '데이터 수집 중단 요청을 접수했습니다.',
                'timestamp': time.time()
            }
            
        else:
            response = {
                'type': 'command_response',
                'command': command,
                'status': 'error',
                'message': f'알 수 없는 명령: {command}',
                'timestamp': time.time()
            }
        
        await websocket.send(json.dumps(response))
    
    async def broadcast_attack_result(self, attack_data: Dict[str, Any]):
        """공격 결과 실시간 브로드캐스트"""
        # 대시보드 데이터 업데이트
        self.dashboard_data['attacks'].append({
            'timestamp': time.time(),
            'attack_name': attack_data.get('attack_name'),
            'status': attack_data.get('status'),
            'execution_time': attack_data.get('execution_time'),
            'iocs_count': len(attack_data.get('iocs', [])),
            'success_rate': attack_data.get('success_rate', 0)
        })
        
        # 최대 100개까지만 유지
        if len(self.dashboard_data['attacks']) > 100:
            self.dashboard_data['attacks'] = self.dashboard_data['attacks'][-100:]
        
        # 브로드캐스트 메시지 생성
        broadcast_message = {
            'type': 'attack_update',
            'timestamp': time.time(),
            'data': {
                'latest_attack': self.dashboard_data['attacks'][-1],
                'total_attacks': len(self.dashboard_data['attacks']),
                'success_rate': self.calculate_success_rate(),
                'avg_execution_time': self.calculate_avg_execution_time()
            }
        }
        
        await self.broadcast_to_all_clients(broadcast_message)
    
    async def broadcast_telemetry_data(self, telemetry_data: Dict[str, Any]):
        """텔레메트리 데이터 실시간 브로드캐스트"""
        # 대시보드 데이터 업데이트
        processed_telemetry = {
            'timestamp': time.time(),
            'message_type': telemetry_data.get('message_type'),
            'source': telemetry_data.get('source'),
            'data_summary': self.summarize_telemetry(telemetry_data.get('data', {}))
        }
        
        self.dashboard_data['telemetry'].append(processed_telemetry)
        
        # 최대 200개까지만 유지 (텔레메트리는 더 많이)
        if len(self.dashboard_data['telemetry']) > 200:
            self.dashboard_data['telemetry'] = self.dashboard_data['telemetry'][-200:]
        
        # 5초마다 한 번씩만 텔레메트리 브로드캐스트 (너무 빈번한 전송 방지)
        current_time = time.time()
        if not hasattr(self, '_last_telemetry_broadcast'):
            self._last_telemetry_broadcast = 0
            
        if current_time - self._last_telemetry_broadcast >= 5.0:
            broadcast_message = {
                'type': 'telemetry_update',
                'timestamp': current_time,
                'data': {
                    'recent_messages': self.dashboard_data['telemetry'][-5:],
                    'message_rate': len(self.dashboard_data['telemetry']) / max(1, current_time - self._last_telemetry_broadcast),
                    'active_sources': self.get_active_telemetry_sources()
                }
            }
            
            await self.broadcast_to_all_clients(broadcast_message)
            self._last_telemetry_broadcast = current_time
    
    async def broadcast_system_status(self, status_data: Dict[str, Any]):
        """시스템 상태 실시간 브로드캐스트"""
        self.dashboard_data['system_status'] = {
            'timestamp': time.time(),
            'cpu_usage': status_data.get('cpu_usage', 0),
            'memory_usage': status_data.get('memory_usage', 0),
            'network_latency': status_data.get('network_latency', -1),
            'active_connections': status_data.get('active_connections', 0),
            'dvd_connectivity': status_data.get('dvd_connectivity', {}),
            'mavlink_status': status_data.get('mavlink_status', {})
        }
        
        broadcast_message = {
            'type': 'system_status_update',
            'timestamp': time.time(),
            'data': self.dashboard_data['system_status']
        }
        
        await self.broadcast_to_all_clients(broadcast_message)
    
    async def broadcast_to_all_clients(self, message: Dict[str, Any]):
        """모든 연결된 클라이언트에게 메시지 브로드캐스트"""
        if not self.connected_clients:
            return
        
        message_json = json.dumps(message)
        disconnected_clients = set()
        
        for client in self.connected_clients:
            try:
                await client.send(message_json)
            except websockets.exceptions.ConnectionClosed:
                disconnected_clients.add(client)
            except Exception as e:
                logger.error(f"❌ 클라이언트 전송 실패: {e}")
                disconnected_clients.add(client)
        
        # 연결이 끊어진 클라이언트 제거
        self.connected_clients -= disconnected_clients
        self.dashboard_data['connection_count'] = len(self.connected_clients)
    
    async def periodic_broadcast(self):
        """정기적 데이터 브로드캐스트"""
        while self.is_running:
            try:
                # 실시간 메트릭 업데이트
                self.dashboard_data['real_time_metrics'] = {
                    'timestamp': time.time(),
                    'uptime': time.time() - (getattr(self, '_start_time', time.time())),
                    'total_attacks': len(self.dashboard_data['attacks']),
                    'total_telemetry_messages': len(self.dashboard_data['telemetry']),
                    'connected_clients': len(self.connected_clients),
                    'messages_per_second': self.calculate_message_rate()
                }
                
                # 메트릭 브로드캐스트
                if self.connected_clients:
                    metrics_message = {
                        'type': 'metrics_update',
                        'timestamp': time.time(),
                        'data': self.dashboard_data['real_time_metrics']
                    }
                    
                    await self.broadcast_to_all_clients(metrics_message)
                
                await asyncio.sleep(10.0)  # 10초마다 메트릭 업데이트
                
            except Exception as e:
                logger.error(f"❌ 정기 브로드캐스트 오류: {e}")
                await asyncio.sleep(5.0)
    
    def calculate_attack_statistics(self) -> Dict[str, Any]:
        """공격 통계 계산"""
        attacks = self.dashboard_data['attacks']
        if not attacks:
            return {'no_data': True}
        
        successful_attacks = [a for a in attacks if a.get('status') == 'success']
        
        return {
            'total': len(attacks),
            'successful': len(successful_attacks),
            'success_rate': len(successful_attacks) / len(attacks) * 100,
            'avg_execution_time': sum(a.get('execution_time', 0) for a in attacks) / len(attacks),
            'total_iocs': sum(a.get('iocs_count', 0) for a in attacks)
        }
    
    def calculate_telemetry_summary(self) -> Dict[str, Any]:
        """텔레메트리 요약 계산"""
        telemetry = self.dashboard_data['telemetry']
        if not telemetry:
            return {'no_data': True}
        
        message_types = {}
        sources = {}
        
        for msg in telemetry:
            msg_type = msg.get('message_type', 'unknown')
            source = msg.get('source', 'unknown')
            
            message_types[msg_type] = message_types.get(msg_type, 0) + 1
            sources[source] = sources.get(source, 0) + 1
        
        return {
            'total_messages': len(telemetry),
            'message_types': message_types,
            'sources': sources,
            'time_span': telemetry[-1]['timestamp'] - telemetry[0]['timestamp'] if len(telemetry) > 1 else 0
        }
    
    def calculate_success_rate(self) -> float:
        """전체 성공률 계산"""
        attacks = self.dashboard_data['attacks']
        if not attacks:
            return 0.0
        
        successful = sum(1 for a in attacks if a.get('status') == 'success')
        return successful / len(attacks) * 100
    
    def calculate_avg_execution_time(self) -> float:
        """평균 실행 시간 계산"""
        attacks = self.dashboard_data['attacks']
        if not attacks:
            return 0.0
        
        return sum(a.get('execution_time', 0) for a in attacks) / len(attacks)
    
    def summarize_telemetry(self, telemetry_data: Dict[str, Any]) -> Dict[str, Any]:
        """텔레메트리 데이터 요약"""
        summary = {}
        
        # 중요한 필드들만 추출
        important_fields = ['lat', 'lon', 'alt', 'vx', 'vy', 'vz', 'hdg', 'voltage', 'current']
        
        for field in important_fields:
            if field in telemetry_data:
                summary[field] = telemetry_data[field]
        
        return summary
    
    def get_active_telemetry_sources(self) -> List[str]:
        """활성 텔레메트리 소스 목록"""
        recent_telemetry = self.dashboard_data['telemetry'][-20:]  # 최근 20개
        sources = set()
        
        for msg in recent_telemetry:
            source = msg.get('source')
            if source:
                sources.add(source)
        
        return list(sources)
    
    def calculate_message_rate(self) -> float:
        """초당 메시지 처리율 계산"""
        if not hasattr(self, '_start_time'):
            self._start_time = time.time()
            return 0.0
        
        runtime = time.time() - self._start_time
        total_messages = len(self.dashboard_data['attacks']) + len(self.dashboard_data['telemetry'])
        
        return total_messages / max(1, runtime)
    
    async def stop_server(self):
        """WebSocket 서버 정지"""
        self.is_running = False
        
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            
        # 모든 클라이언트 연결 정리
        for client in list(self.connected_clients):
            await client.close()
        
        self.connected_clients.clear()
        logger.info("🛑 WebSocket 서버 정지됨")


class MQTTCommunicationBridge:
    """MQTT 통신 브리지 - DVD와 외부 시스템 간 메시지 중계"""
    
    def __init__(self, broker_host: str = "localhost", broker_port: int = 1883):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.client = None
        self.is_connected = False
        self.message_handlers = {}
        
        # 메시지 통계
        self.stats = {
            'messages_sent': 0,
            'messages_received': 0,
            'connection_time': None,
            'last_message_time': None
        }
        
        logger.info(f"🔌 MQTT 브리지 초기화: {broker_host}:{broker_port}")
    
    async def connect(self):
        """MQTT 브로커 연결"""
        try:
            import paho.mqtt.client as mqtt
            
            self.client = mqtt.Client(client_id="dvd_lite_bridge")
            self.client.on_connect = self._on_connect
            self.client.on_message = self._on_message
            self.client.on_disconnect = self._on_disconnect
            
            # 연결 시도
            self.client.connect(self.broker_host, self.broker_port, 60)
            self.client.loop_start()
            
            # 연결 확인 대기
            await asyncio.sleep(2.0)
            
            if self.is_connected:
                logger.info("✅ MQTT 브로커 연결 성공")
                
                # 기본 토픽 구독
                await self.subscribe_to_topics()
                
            else:
                raise Exception("MQTT 연결 실패")
                
        except Exception as e:
            logger.error(f"❌ MQTT 연결 실패: {e}")
            raise
    
    def _on_connect(self, client, userdata, flags, rc):
        """MQTT 연결 콜백"""
        if rc == 0:
            self.is_connected = True
            self.stats['connection_time'] = time.time()
            logger.info("🔗 MQTT 브로커 연결됨")
        else:
            logger.error(f"❌ MQTT 연결 실패 (코드: {rc})")
    
    def _on_message(self, client, userdata, msg):
        """MQTT 메시지 수신 콜백"""
        try:
            topic = msg.topic
            payload = json.loads(msg.payload.decode())
            
            self.stats['messages_received'] += 1
            self.stats['last_message_time'] = time.time()
            
            # 토픽별 핸들러 실행
            if topic in self.message_handlers:
                handler = self.message_handlers[topic]
                asyncio.create_task(handler(topic, payload))
            
            logger.debug(f"📨 MQTT 메시지 수신: {topic}")
            
        except Exception as e:
            logger.error(f"❌ MQTT 메시지 처리 오류: {e}")
    
    def _on_disconnect(self, client, userdata, rc):
        """MQTT 연결 해제 콜백"""
        self.is_connected = False
        logger.warning("🔌 MQTT 브로커 연결 해제됨")
    
    async def subscribe_to_topics(self):
        """기본 토픽 구독"""
        topics = [
            "dvd/attacks/+",      # 공격 관련 메시지
            "dvd/telemetry/+",    # 텔레메트리 메시지
            "dvd/system/+",       # 시스템 상태 메시지
            "dvd/control/+",      # 제어 명령 메시지
        ]
        
        for topic in topics:
            self.client.subscribe(topic)
            logger.info(f"📡 MQTT 토픽 구독: {topic}")
    
    def register_message_handler(self, topic: str, handler_func):
        """메시지 핸들러 등록"""
        self.message_handlers[topic] = handler_func
        logger.info(f"🎯 MQTT 핸들러 등록: {topic}")
    
    async def publish_attack_result(self, attack_data: Dict[str, Any]):
        """공격 결과 발행"""
        try:
            topic = f"dvd/attacks/{attack_data.get('attack_name', 'unknown')}"
            
            payload = {
                'timestamp': time.time(),
                'attack_name': attack_data.get('attack_name'),
                'status': attack_data.get('status'),
                'execution_time': attack_data.get('execution_time'),
                'success_rate': attack_data.get('success_rate'),
                'iocs_count': len(attack_data.get('iocs', [])),
                'source': 'dvd_lite'
            }
            
            self.client.publish(topic, json.dumps(payload))
            self.stats['messages_sent'] += 1
            
            logger.debug(f"📤 공격 결과 발행: {topic}")
            
        except Exception as e:
            logger.error(f"❌ 공격 결과 발행 실패: {e}")
    
    async def publish_telemetry_data(self, telemetry_data: Dict[str, Any]):
        """텔레메트리 데이터 발행"""
        try:
            message_type = telemetry_data.get('message_type', 'unknown')
            topic = f"dvd/telemetry/{message_type}"
            
            payload = {
                'timestamp': time.time(),
                'message_type': message_type,
                'source': telemetry_data.get('source'),
                'data': telemetry_data.get('data'),
                'source': 'dvd_lite'
            }
            
            self.client.publish(topic, json.dumps(payload))
            self.stats['messages_sent'] += 1
            
        except Exception as e:
            logger.error(f"❌ 텔레메트리 발행 실패: {e}")
    
    async def publish_system_status(self, status_data: Dict[str, Any]):
        """시스템 상태 발행"""
        try:
            topic = "dvd/system/status"
            
            payload = {
                'timestamp': time.time(),
                'cpu_usage': status_data.get('cpu_usage'),
                'memory_usage': status_data.get('memory_usage'),
                'network_latency': status_data.get('network_latency'),
                'active_connections': status_data.get('active_connections'),
                'source': 'dvd_lite'
            }
            
            self.client.publish(topic, json.dumps(payload))
            self.stats['messages_sent'] += 1
            
        except Exception as e:
            logger.error(f"❌ 시스템 상태 발행 실패: {e}")
    
    async def handle_control_command(self, topic: str, payload: Dict[str, Any]):
        """제어 명령 처리 핸들러"""
        try:
            command = payload.get('command')
            logger.info(f"🎮 제어 명령 수신: {command}")
            
            # 명령별 처리 로직
            if command == 'start_attack':
                attack_name = payload.get('attack_name')
                logger.info(f"🎯 공격 시작 명령: {attack_name}")
                
                # 실제 공격 실행 로직 (여기서는 로그만)
                response_topic = topic.replace('/control/', '/response/')
                response = {
                    'timestamp': time.time(),
                    'command': command,
                    'status': 'accepted',
                    'message': f'공격 {attack_name} 시작됨'
                }
                
                self.client.publish(response_topic, json.dumps(response))
                
            elif command == 'stop_attacks':
                logger.info("🛑 모든 공격 중단 명령")
                
                response_topic = topic.replace('/control/', '/response/')
                response = {
                    'timestamp': time.time(),
                    'command': command,
                    'status': 'accepted',
                    'message': '모든 공격이 중단됨'
                }
                
                self.client.publish(response_topic, json.dumps(response))
                
        except Exception as e:
            logger.error(f"❌ 제어 명령 처리 실패: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """MQTT 통신 통계"""
        return {
            'is_connected': self.is_connected,
            'connection_time': self.stats['connection_time'],
            'messages_sent': self.stats['messages_sent'],
            'messages_received': self.stats['messages_received'],
            'last_message_time': self.stats['last_message_time'],
            'uptime': time.time() - self.stats['connection_time'] if self.stats['connection_time'] else 0
        }
    
    async def disconnect(self):
        """MQTT 연결 해제"""
        if self.client and self.is_connected:
            self.client.loop_stop()
            self.client.disconnect()
            self.is_connected = False
            logger.info("🔌 MQTT 연결 해제됨")


class HTMLDashboardGenerator:
    """실시간 대시보드 HTML 생성기"""
    
    @staticmethod
    def generate_dashboard_html() -> str:
        """대시보드 HTML 페이지 생성"""
        html_content = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DVD-Lite 실시간 대시보드</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.9.1/chart.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            color: white;
            min-height: 100vh;
        }
        
        .header {
            background: rgba(0,0,0,0.3);
            padding: 1rem 2rem;
            text-align: center;
            border-bottom: 2px solid rgba(255,255,255,0.1);
        }
        
        .header h1 {
            font-size: 2rem;
            margin-bottom: 0.5rem;
        }
        
        .connection-status {
            display: inline-block;
            padding: 0.3rem 1rem;
            border-radius: 15px;
            font-size: 0.9rem;
            margin-top: 0.5rem;
        }
        
        .connected { background: #27ae60; }
        .disconnected { background: #e74c3c; }
        
        .dashboard-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 1.5rem;
            padding: 2rem;
            max-width: 1400px;
            margin: 0 auto;
        }
        
        .dashboard-card {
            background: rgba(255,255,255,0.1);
            backdrop-filter: blur(10px);
            border-radius: 15px;
            padding: 1.5rem;
            border: 1px solid rgba(255,255,255,0.2);
            transition: transform 0.3s ease;
        }
        
        .dashboard-card:hover {
            transform: translateY(-5px);
        }
        
        .card-title {
            font-size: 1.3rem;
            margin-bottom: 1rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        
        .metric-value {
            font-size: 2rem;
            font-weight: bold;
            color: #3498db;
            margin: 0.5rem 0;
        }
        
        .metric-label {
            font-size: 0.9rem;
            opacity: 0.8;
        }
        
        .chart-container {
            position: relative;
            height: 200px;
            margin-top: 1rem;
        }
        
        .log-container {
            max-height: 200px;
            overflow-y: auto;
            background: rgba(0,0,0,0.3);
            border-radius: 8px;
            padding: 1rem;
            font-family: 'Courier New', monospace;
            font-size: 0.85rem;
        }
        
        .log-entry {
            margin-bottom: 0.5rem;
            padding: 0.3rem;
            border-radius: 4px;
        }
        
        .log-success { background: rgba(39, 174, 96, 0.3); }
        .log-error { background: rgba(231, 76, 60, 0.3); }
        .log-info { background: rgba(52, 152, 219, 0.3); }
        
        .controls {
            display: flex;
            gap: 1rem;
            margin-top: 1rem;
            flex-wrap: wrap;
        }
        
        .btn {
            background: #3498db;
            color: white;
            border: none;
            padding: 0.7rem 1.5rem;
            border-radius: 8px;
            cursor: pointer;
            font-size: 0.9rem;
            transition: background 0.3s ease;
        }
        
        .btn:hover { background: #2980b9; }
        .btn-danger { background: #e74c3c; }
        .btn-danger:hover { background: #c0392b; }
        .btn-success { background: #27ae60; }
        .btn-success:hover { background: #229954; }
        
        .status-indicator {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 0.5rem;
        }
        
        .status-online { background: #27ae60; }
        .status-offline { background: #e74c3c; }
        .status-warning { background: #f39c12; }
        
        @media (max-width: 768px) {
            .dashboard-grid {
                grid-template-columns: 1fr;
                padding: 1rem;
            }
            
            .header h1 { font-size: 1.5rem; }
            .controls { justify-content: center; }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🚁 DVD-Lite 실시간 대시보드</h1>
        <p>Damn Vulnerable Drone 연동 모니터링 시스템</p>
        <div id="connection-status" class="connection-status disconnected">
            연결 중...
        </div>
    </div>

    <div class="dashboard-grid">
        <!-- 공격 통계 카드 -->
        <div class="dashboard-card">
            <div class="card-title">
                🎯 공격 실행 통계
            </div>
            <div class="metric-value" id="total-attacks">0</div>
            <div class="metric-label">총 실행된 공격</div>
            
            <div class="metric-value" id="success-rate">0%</div>
            <div class="metric-label">성공률</div>
            
            <div class="controls">
                <button class="btn btn-success" onclick="startRandomAttack()">
                    공격 시작
                </button>
                <button class="btn btn-danger" onclick="stopAllAttacks()">
                    모든 공격 중단
                </button>
            </div>
        </div>

        <!-- 시스템 상태 카드 -->
        <div class="dashboard-card">
            <div class="card-title">
                📊 시스템 상태
            </div>
            <div style="display: flex; justify-content: space-between; margin-bottom: 1rem;">
                <div>
                    <div class="metric-value" id="cpu-usage">0%</div>
                    <div class="metric-label">CPU 사용률</div>
                </div>
                <div>
                    <div class="metric-value" id="memory-usage">0%</div>
                    <div class="metric-label">메모리 사용률</div>
                </div>
            </div>
            
            <div>
                <span class="status-indicator" id="dvd-status"></span>
                <span id="dvd-status-text">DVD 연결 상태</span>
            </div>
        </div>

        <!-- 실시간 성능 차트 -->
        <div class="dashboard-card">
            <div class="card-title">
                📈 실시간 성능
            </div>
            <div class="chart-container">
                <canvas id="performance-chart"></canvas>
            </div>
        </div>

        <!-- 최근 공격 로그 -->
        <div class="dashboard-card">
            <div class="card-title">
                📋 최근 공격 로그
            </div>
            <div class="log-container" id="attack-logs">
                <div class="log-entry log-info">
                    대시보드 초기화 중...
                </div>
            </div>
        </div>

        <!-- 텔레메트리 데이터 -->
        <div class="dashboard-card">
            <div class="card-title">
                📡 텔레메트리 데이터
            </div>
            <div class="metric-value" id="telemetry-rate">0</div>
            <div class="metric-label">초당 메시지 수</div>
            
            <div class="log-container" id="telemetry-logs">
                <div class="log-entry log-info">
                    텔레메트리 대기 중...
                </div>
            </div>
        </div>

        <!-- 네트워크 상태 -->
        <div class="dashboard-card">
            <div class="card-title">
                🌐 네트워크 연결
            </div>
            <div id="network-status">
                <div style="margin-bottom: 0.5rem;">
                    <span class="status-indicator status-offline"></span>
                    Flight Controller (10.13.0.2)
                </div>
                <div style="margin-bottom: 0.5rem;">
                    <span class="status-indicator status-offline"></span>
                    Companion Computer (10.13.0.3)
                </div>
                <div>
                    <span class="status-indicator status-offline"></span>
                    Ground Control Station (10.13.0.4)
                </div>
            </div>
        </div>
    </div>

    <script>
        // WebSocket 연결
        let socket = null;
        let performanceChart = null;
        let isConnected = false;

        // 차트 초기화
        function initializeChart() {
            const ctx = document.getElementById('performance-chart').getContext('2d');
            performanceChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        label: '공격 성공률',
                        data: [],
                        borderColor: '#3498db',
                        backgroundColor: 'rgba(52, 152, 219, 0.1)',
                        tension: 0.4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            beginAtZero: true,
                            max: 100,
                            ticks: { color: 'white' }
                        },
                        x: {
                            ticks: { color: 'white' }
                        }
                    },
                    plugins: {
                        legend: {
                            labels: { color: 'white' }
                        }
                    }
                }
            });
        }

        // WebSocket 연결 함수
        function connectWebSocket() {
            const wsUrl = 'ws://localhost:8765';
            socket = new WebSocket(wsUrl);

            socket.onopen = function(event) {
                console.log('WebSocket 연결됨');
                isConnected = true;
                updateConnectionStatus(true);
                
                // 핑 메시지 시작
                startPingInterval();
            };

            socket.onmessage = function(event) {
                try {
                    const data = JSON.parse(event.data);
                    handleWebSocketMessage(data);
                } catch (e) {
                    console.error('메시지 파싱 오류:', e);
                }
            };

            socket.onclose = function(event) {
                console.log('WebSocket 연결 종료');
                isConnected = false;
                updateConnectionStatus(false);
                
                // 3초 후 재연결 시도
                setTimeout(connectWebSocket, 3000);
            };

            socket.onerror = function(error) {
                console.error('WebSocket 오류:', error);
                updateConnectionStatus(false);
            };
        }

        // WebSocket 메시지 처리
        function handleWebSocketMessage(data) {
            switch(data.type) {
                case 'initial_data':
                    console.log('초기 데이터 수신:', data);
                    break;
                    
                case 'attack_update':
                    updateAttackStats(data.data);
                    addAttackLog(data.data.latest_attack);
                    break;
                    
                case 'telemetry_update':
                    updateTelemetryData(data.data);
                    break;
                    
                case 'system_status_update':
                    updateSystemStatus(data.data);
                    break;
                    
                case 'metrics_update':
                    updateMetrics(data.data);
                    break;
                    
                case 'pong':
                    // 핑 응답 수신
                    break;
                    
                default:
                    console.log('알 수 없는 메시지 타입:', data.type);
            }
        }

        // 공격 통계 업데이트
        function updateAttackStats(data) {
            document.getElementById('total-attacks').textContent = data.total_attacks || 0;
            document.getElementById('success-rate').textContent = 
                (data.success_rate || 0).toFixed(1) + '%';
            
            // 성능 차트 업데이트
            if (performanceChart) {
                const now = new Date().toLocaleTimeString();
                performanceChart.data.labels.push(now);
                performanceChart.data.datasets[0].data.push(data.success_rate || 0);
                
                // 최대 20개 데이터 포인트 유지
                if (performanceChart.data.labels.length > 20) {
                    performanceChart.data.labels.shift();
                    performanceChart.data.datasets[0].data.shift();
                }
                
                performanceChart.update('none');
            }
        }

        // 공격 로그 추가
        function addAttackLog(attack) {
            if (!attack) return;
            
            const logsContainer = document.getElementById('attack-logs');
            const logEntry = document.createElement('div');
            logEntry.className = `log-entry ${attack.status === 'success' ? 'log-success' : 'log-error'}`;
            
            const time = new Date().toLocaleTimeString();
            logEntry.innerHTML = `
                [${time}] ${attack.attack_name}: ${attack.status} 
                (${attack.execution_time?.toFixed(2)}s, IOCs: ${attack.iocs_count || 0})
            `;
            
            logsContainer.insertBefore(logEntry, logsContainer.firstChild);
            
            // 최대 10개 로그 유지
            while (logsContainer.children.length > 10) {
                logsContainer.removeChild(logsContainer.lastChild);
            }
        }

        // 텔레메트리 데이터 업데이트
        function updateTelemetryData(data) {
            const rateElement = document.getElementById('telemetry-rate');
            if (rateElement) {
                rateElement.textContent = (data.message_rate || 0).toFixed(1);
            }
            
            // 텔레메트리 로그 업데이트
            if (data.recent_messages) {
                const logsContainer = document.getElementById('telemetry-logs');
                logsContainer.innerHTML = '';
                
                data.recent_messages.forEach(msg => {
                    const logEntry = document.createElement('div');
                    logEntry.className = 'log-entry log-info';
                    
                    const time = new Date(msg.timestamp * 1000).toLocaleTimeString();
                    logEntry.innerHTML = `[${time}] ${msg.message_type} from ${msg.source}`;
                    
                    logsContainer.appendChild(logEntry);
                });
            }
        }

        // 시스템 상태 업데이트
        function updateSystemStatus(data) {
            document.getElementById('cpu-usage').textContent = 
                (data.cpu_usage || 0).toFixed(1) + '%';
            document.getElementById('memory-usage').textContent = 
                (data.memory_usage || 0).toFixed(1) + '%';
            
            // DVD 연결 상태 업데이트
            const statusElement = document.getElementById('dvd-status');
            const statusTextElement = document.getElementById('dvd-status-text');
            
            const mavlinkConnected = data.mavlink_status?.connected || false;
            
            if (mavlinkConnected) {
                statusElement.className = 'status-indicator status-online';
                statusTextElement.textContent = 'DVD 연결됨';
            } else {
                statusElement.className = 'status-indicator status-offline';
                statusTextElement.textContent = 'DVD 연결 안됨';
            }
        }

        // 메트릭 업데이트
        function updateMetrics(data) {
            // 연결된 클라이언트 수 등 추가 메트릭 표시
            console.log('메트릭 업데이트:', data);
        }

        // 연결 상태 업데이트
        function updateConnectionStatus(connected) {
            const statusElement = document.getElementById('connection-status');
            
            if (connected) {
                statusElement.className = 'connection-status connected';
                statusElement.textContent = '✅ 연결됨';
            } else {
                statusElement.className = 'connection-status disconnected';
                statusElement.textContent = '❌ 연결 안됨';
            }
        }

        // 핑 인터벌 시작
        function startPingInterval() {
            setInterval(() => {
                if (socket && socket.readyState === WebSocket.OPEN) {
                    socket.send(JSON.stringify({
                        type: 'ping',
                        timestamp: Date.now()
                    }));
                }
            }, 30000); // 30초마다 핑
        }

        // 제어 함수들
        function startRandomAttack() {
            if (socket && socket.readyState === WebSocket.OPEN) {
                const attacks = [
                    'wifi_network_discovery', 'gps_spoofing', 'mavlink_flood',
                    'telemetry_exfiltration', 'parameter_manipulation'
                ];
                
                const randomAttack = attacks[Math.floor(Math.random() * attacks.length)];
                
                socket.send(JSON.stringify({
                    type: 'control_command',
                    command: 'start_attack',
                    attack_name: randomAttack
                }));
            }
        }

        function stopAllAttacks() {
            if (socket && socket.readyState === WebSocket.OPEN) {
                socket.send(JSON.stringify({
                    type: 'control_command',
                    command: 'stop_attacks'
                }));
            }
        }

        // 페이지 로드 시 초기화
        document.addEventListener('DOMContentLoaded', function() {
            initializeChart();
            connectWebSocket();
        });
    </script>
</body>
</html>
        """
        
        return html_content
    
    @staticmethod
    def save_dashboard_file(filename: str = "dashboard.html"):
        """대시보드 HTML 파일 저장"""
        html_content = HTMLDashboardGenerator.generate_dashboard_html()
        
        Path(filename).parent.mkdir(parents=True, exist_ok=True)
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        logger.info(f"📄 대시보드 HTML 파일 저장: {filename}")
        return filename


# 통합 실행 예제
async def run_complete_dashboard_system():
    """완전한 대시보드 시스템 실행"""
    logger.info("🚀 완전한 대시보드 시스템 시작")
    
    try:
        # WebSocket 대시보드 서버 시작
        dashboard_server = WebSocketDashboardServer("localhost", 8765)
        await dashboard_server.start_server()
        
        # MQTT 브리지 시작
        mqtt_bridge = MQTTCommunicationBridge("localhost", 1883)
        try:
            await mqtt_bridge.connect()
            
            # 제어 명령 핸들러 등록
            mqtt_bridge.register_message_handler(
                "dvd/control/+", 
                mqtt_bridge.handle_control_command
            )
            
        except Exception as e:
            logger.warning(f"⚠️ MQTT 연결 실패 (선택적): {e}")
        
        # HTML 대시보드 파일 생성
        dashboard_file = HTMLDashboardGenerator.save_dashboard_file("dashboard/index.html")
        
        logger.info("✅ 대시보드 시스템 완전 초기화 완료")
        logger.info(f"🌐 웹 대시보드: file://{Path(dashboard_file).absolute()}")
        logger.info("🔌 WebSocket 서버: ws://localhost:8765")
        
        # 시뮬레이션 데이터 생성 (테스트용)
        await simulate_realtime_data(dashboard_server, mqtt_bridge)
        
    except Exception as e:
        logger.error(f"❌ 대시보드 시스템 오류: {e}")
        raise

async def simulate_realtime_data(dashboard_server, mqtt_bridge):
    """실시간 데이터 시뮬레이션 (테스트용)"""
    import random
    
    logger.info("🎭 실시간 데이터 시뮬레이션 시작")
    
    attack_names = [
        'wifi_network_discovery', 'gps_spoofing', 'mavlink_flood',
        'telemetry_exfiltration', 'parameter_manipulation', 'bootloader_exploit'
    ]
    
    for i in range(20):  # 20개 시뮬레이션 공격
        await asyncio.sleep(2.0)  # 2초 간격
        
        # 공격 결과 시뮬레이션
        attack_data = {
            'attack_name': random.choice(attack_names),
            'status': random.choice(['success', 'failed', 'detected']),
            'execution_time': random.uniform(1.0, 5.0),
            'success_rate': random.uniform(0.3, 0.9),
            'iocs': [f"IOC_{j}" for j in range(random.randint(1, 8))]
        }
        
        # 대시보드에 브로드캐스트
        await dashboard_server.broadcast_attack_result(attack_data)
        
        # MQTT로 발행 (연결된 경우)
        if mqtt_bridge.is_connected:
            await mqtt_bridge.publish_attack_result(attack_data)
        
        # 시스템 상태 시뮬레이션
        if i % 3 == 0:  # 3번에 한 번씩
            status_data = {
                'cpu_usage': random.uniform(20, 80),
                'memory_usage': random.uniform(30, 70),
                'network_latency': random.uniform(10, 50),
                'active_connections': random.randint(5, 25),
                'mavlink_status': {'connected': random.choice([True, False])}
            }
            
            await dashboard_server.broadcast_system_status(status_data)
            
            if mqtt_bridge.is_connected:
                await mqtt_bridge.publish_system_status(status_data)
        
        # 텔레메트리 시뮬레이션
        if i % 2 == 0:  # 2번에 한 번씩
            telemetry_data = {
                'message_type': random.choice(['HEARTBEAT', 'GPS_RAW_INT', 'ATTITUDE']),
                'source': 'flight_controller',
                'data': {
                    'lat': 37.7749 + random.uniform(-0.01, 0.01),
                    'lon': -122.4194 + random.uniform(-0.01, 0.01),
                    'alt': random.uniform(50, 150)
                }
            }
            
            await dashboard_server.broadcast_telemetry_data(telemetry_data)
            
            if mqtt_bridge.is_connected:
                await mqtt_bridge.publish_telemetry_data(telemetry_data)
        
        logger.info(f"📊 시뮬레이션 진행: {i+1}/20")
    
    logger.info("🎭 시뮬레이션 완료")

if __name__ == "__main__":
    print("🌐 DVD-Lite 실시간 대시보드 시스템")
    print("📊 WebSocket + MQTT 통합 통신 플랫폼")
    
    try:
        asyncio.run(run_complete_dashboard_system())
    except KeyboardInterrupt:
        print("\n🛑 사용자에 의해 중단됨")
    except Exception as e:
        print(f"\n❌ 시스템 오류: {e}")
        import traceback
        traceback.print_exc()