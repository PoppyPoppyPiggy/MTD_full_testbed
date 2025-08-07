
import asyncio
import socket
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SimpleGCS:
    def __init__(self):
        self.running = False
        
    async def start_service(self):
        """간단한 GCS 서비스 시작"""
        self.running = True
        logger.info("GCS 서비스 시작됨 - 포트 14550에서 MAVLink 수신 대기")
        
        try:
            # UDP 소켓 생성
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.bind(('127.0.0.1', 14550))
            sock.settimeout(1.0)
            
            while self.running:
                try:
                    data, addr = sock.recvfrom(1024)
                    logger.info(f"MAVLink 데이터 수신: {len(data)} bytes from {addr}")
                except socket.timeout:
                    continue
                except Exception as e:
                    logger.error(f"수신 오류: {e}")
                    
        except Exception as e:
            logger.error(f"GCS 서비스 오류: {e}")
        finally:
            if 'sock' in locals():
                sock.close()

if __name__ == "__main__":
    gcs = SimpleGCS()
    asyncio.run(gcs.start_service())
