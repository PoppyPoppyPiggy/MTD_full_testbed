#!/usr/bin/env python3
"""
MTD Orchestrator 메인 스크립트
위치: ~/MTD/MTD_full_testbed/docker/mtd/mtd_orchestrator.py
"""

import asyncio
import docker
import json
import logging
import time
from datetime import datetime
from typing import Dict, List, Any
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MTDOrchestrator:
    def __init__(self, config_path: str = "/configs/mtd_config.json"):
        self.docker_client = docker.from_env()
        self.config = self.load_config(config_path)
        self.active_strategies = {}
        self.threat_level = 0.0
        
    def load_config(self, config_path: str) -> Dict[str, Any]:
        """MTD 설정 로드"""
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"설정 파일을 찾을 수 없습니다: {config_path}")
            return self.get_default_config()
    
    def get_default_config(self) -> Dict[str, Any]:
        """기본 MTD 설정"""
        return {
            "mutation_cycle": 60,
            "threat_threshold": 0.5,
            "strategies": {
                "container_migration": {
                    "enabled": True,
                    "cooldown": 30,
                    "threshold": 0.7
                },
                "port_randomization": {
                    "enabled": True,
                    "cooldown": 15,
                    "threshold": 0.5
                },
                "ip_shuffling": {
                    "enabled": True,
                    "cooldown": 45,
                    "threshold": 0.6
                }
            }
        }
    
    async def run(self):
        """MTD 오케스트레이터 실행"""
        logger.info("MTD Orchestrator 시작")
        
        while True:
            try:
                # 위협 수준 평가
                self.threat_level = await self.assess_threat_level()
                
                # MTD 전략 실행
                await self.execute_mtd_strategies()
                
                # 로그 출력
                logger.info(f"위협 수준: {self.threat_level:.2f}")
                
                await asyncio.sleep(10)
                
            except Exception as e:
                logger.error(f"MTD 실행 오류: {e}")
                await asyncio.sleep(5)
    
    async def assess_threat_level(self) -> float:
        """위협 수준 평가"""
        threat_score = 0.0
        
        # 컨테이너 상태 확인
        try:
            containers = self.docker_client.containers.list()
            running_containers = len([c for c in containers if c.status == 'running'])
            
            if running_containers < 5:  # 최소 컨테이너 수
                threat_score += 0.2
                
        except Exception as e:
            logger.error(f"컨테이너 상태 확인 실패: {e}")
            threat_score += 0.3
        
        # 시뮬레이션된 위협 탐지
        if np.random.random() < 0.1:  # 10% 확률로 위협 발생
            threat_score += np.random.uniform(0.3, 0.8)
        
        return min(1.0, threat_score)
    
    async def execute_mtd_strategies(self):
        """MTD 전략 실행"""
        for strategy_name, strategy_config in self.config["strategies"].items():
            if not strategy_config.get("enabled", False):
                continue
                
            threshold = strategy_config.get("threshold", 0.5)
            
            if self.threat_level >= threshold:
                await self.execute_strategy(strategy_name, strategy_config)
    
    async def execute_strategy(self, strategy_name: str, config: Dict[str, Any]):
        """개별 전략 실행"""
        logger.warning(f"MTD 전략 실행: {strategy_name}")
        
        if strategy_name == "container_migration":
            await self.migrate_containers()
        elif strategy_name == "port_randomization":
            await self.randomize_ports()
        elif strategy_name == "ip_shuffling":
            await self.shuffle_ips()
    
    async def migrate_containers(self):
        """컨테이너 마이그레이션"""
        logger.info("컨테이너 마이그레이션 실행")
        # 실제 마이그레이션 로직 구현
        await asyncio.sleep(2)  # 시뮬레이션
    
    async def randomize_ports(self):
        """포트 랜덤화"""
        logger.info("포트 랜덤화 실행")
        # 실제 포트 변경 로직 구현
        await asyncio.sleep(1)  # 시뮬레이션
    
    async def shuffle_ips(self):
        """IP 주소 셔플링"""
        logger.info("IP 주소 셔플링 실행") 
        # 실제 IP 변경 로직 구현
        await asyncio.sleep(1)  # 시뮬레이션

if __name__ == "__main__":
    orchestrator = MTDOrchestrator()
    asyncio.run(orchestrator.run())
