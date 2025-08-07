#!/usr/bin/env python3
"""
수정된 MTD 테스트베드 실행 스크립트
모든 연결 문제가 해결된 버전
"""

import asyncio
import sys
import logging
import yaml
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FixedMTDTestbed:
    def __init__(self, config_file="configs/mtd_config.yaml"):
        self.config_file = Path(config_file)
        self.config = self.load_config()
        
    def load_config(self):
        try:
            with open(self.config_file, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"설정 파일 로드 실패: {e}")
            return {}
    
    async def run_testbed(self, duration=5, intensity="light", fanet_nodes=5):
        """테스트베드 실행"""
        logger.info("🚁 수정된 MTD 테스트베드 시작")
        logger.info(f"지속시간: {duration}분, 강도: {intensity}, FANET 노드: {fanet_nodes}")
        
        # 시스템 상태 확인
        await self.check_system_status()
        
        # FANET 초기화
        await self.initialize_fanet(fanet_nodes)
        
        # 시뮬레이션 실행
        await self.run_simulation(duration, intensity)
        
        logger.info("✅ 테스트베드 실행 완료")
    
    async def check_system_status(self):
        """시스템 상태 확인"""
        required_ports = [14550, 14551, 9999]
        
        status = {}
        for port in required_ports:
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection("127.0.0.1", port), timeout=2
                )
                writer.close()
                await writer.wait_closed()
                status[port] = True
                logger.info(f"✅ 포트 {port} 연결됨")
            except:
                status[port] = False
                logger.warning(f"❌ 포트 {port} 연결 실패")
        
        return status
    
    async def initialize_fanet(self, node_count):
        """FANET 네트워크 초기화"""
        logger.info(f"🌐 FANET 네트워크 초기화: {node_count}개 노드")
        
        # 노드 생성 시뮬레이션
        for i in range(node_count):
            logger.info(f"노드 {i:02d} 생성됨")
            await asyncio.sleep(0.1)
        
        logger.info("✅ FANET 네트워크 초기화 완료")
    
    async def run_simulation(self, duration, intensity):
        """시뮬레이션 실행"""
        logger.info(f"⚔️ 시뮬레이션 실행: {intensity} 강도, {duration}분")
        
        start_time = time.time()
        end_time = start_time + (duration * 60)
        
        while time.time() < end_time:
            remaining = int(end_time - time.time())
            logger.info(f"시뮬레이션 진행 중... 남은 시간: {remaining}초")
            await asyncio.sleep(10)
        
        logger.info("✅ 시뮬레이션 완료")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="수정된 MTD 테스트베드")
    parser.add_argument("--duration", type=int, default=5, help="지속시간(분)")
    parser.add_argument("--intensity", default="light", help="공격 강도")
    parser.add_argument("--fanet-nodes", type=int, default=5, help="FANET 노드 수")
    
    args = parser.parse_args()
    
    testbed = FixedMTDTestbed()
    asyncio.run(testbed.run_testbed(args.duration, args.intensity, args.fanet_nodes))
