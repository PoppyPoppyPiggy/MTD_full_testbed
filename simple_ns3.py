
import asyncio
import socket
import json
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SimpleNS3:
    def __init__(self):
        self.running = False
        
    async def start_service(self):
        """간단한 NS-3 시뮬레이션 서비스"""
        self.running = True
        logger.info("NS-3 시뮬레이션 서비스 시작됨 - 포트 9999")
        
        try:
            server = await asyncio.start_server(
                self.handle_client, '127.0.0.1', 9999
            )
            
            async with server:
                await server.serve_forever()
                
        except Exception as e:
            logger.error(f"NS-3 서비스 오류: {e}")
    
    async def handle_client(self, reader, writer):
        """클라이언트 요청 처리"""
        try:
            data = await reader.read(1024)
            if data:
                # 간단한 응답
                response = {
                    "status": "ok",
                    "simulation_time": time.time(),
                    "nodes": 10,
                    "topology": "mesh"
                }
                
                writer.write(json.dumps(response).encode())
                await writer.drain()
                
        except Exception as e:
            logger.error(f"클라이언트 처리 오류: {e}")
        finally:
            writer.close()
            await writer.wait_closed()

if __name__ == "__main__":
    ns3 = SimpleNS3()
    asyncio.run(ns3.start_service())
