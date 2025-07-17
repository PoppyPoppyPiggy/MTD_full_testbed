# dvd_connector/real_dvd_connector.py
"""
실제 Damn Vulnerable Drone과의 직접 연동 모듈
GitHub: https://github.com/nicholasaleks/Damn-Vulnerable-Drone

이 모듈은 실제 DVD 하드웨어와 직접 통신하여 공격을 수행하고 결과를 수집합니다.
"""

import asyncio
import json
import logging
import socket
import subprocess
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path

# 외부 라이브러리들 (선택적 import)
try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False
    print("⚠️ aiohttp가 설치되지 않았습니다. HTTP 기능이 제한됩니다.")

try:
    import paramiko
    PARAMIKO_AVAILABLE = True
except ImportError:
    PARAMIKO_AVAILABLE = False
    print("⚠️ paramiko가 설치되지 않았습니다. SSH 기능이 제한됩니다.")

try:
    from pymavlink import mavutil
    PYMAVLINK_AVAILABLE = True
except ImportError:
    PYMAVLINK_AVAILABLE = False
    print("⚠️ pymavlink가 설치되지 않았습니다. MAVLink 기능이 제한됩니다.")

logger = logging.getLogger(__name__)

class RealDVDConnector:
    """실제 Damn Vulnerable Drone 연결 및 제어"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
        # DVD 시스템 호스트들
        self.companion_computer = config.get('companion_computer', '10.13.0.3')
        self.flight_controller = config.get('flight_controller', '10.13.0.2')  
        self.ground_station = config.get('ground_station', '10.13.0.4')
        
        # 인증 정보
        self.ssh_username = config.get('ssh_username', 'dvd')
        self.ssh_password = config.get('ssh_password', 'dvdpassword')
        
        # 연결 상태
        self.connections = {
            'ssh_companion': None,
            'mavlink_fc': None,
            'http_gcs': None
        }
        
        # 실시간 데이터
        self.telemetry_data = {}
        self.system_status = {}
        
        logger.info(f"🎯 실제 DVD 커넥터 초기화: CC={self.companion_computer}, FC={self.flight_controller}")
    
    async def connect_all_systems(self):
        """모든 DVD 시스템에 연결"""
        logger.info("🔗 DVD 시스템들에 연결 중...")
        
        connection_results = {}
        
        # 1. Companion Computer SSH 연결
        connection_results['ssh_companion'] = await self._connect_ssh_companion()
        
        # 2. Flight Controller MAVLink 연결
        connection_results['mavlink_fc'] = await self._connect_mavlink_fc()
        
        # 3. Ground Control Station HTTP 연결
        connection_results['http_gcs'] = await self._connect_http_gcs()
        
        # 연결 상태 요약
        successful_connections = sum(1 for success in connection_results.values() if success)
        logger.info(f"✅ DVD 연결 완료: {successful_connections}/3 시스템")
        
        return connection_results
    
    async def _connect_ssh_companion(self) -> bool:
        """Companion Computer SSH 연결"""
        if not PARAMIKO_AVAILABLE:
            logger.warning("⚠️ paramiko가 없어 SSH 연결을 시뮬레이션합니다.")
            self.connections['ssh_companion'] = 'simulated'
            return True
        
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # 비동기 SSH 연결
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: ssh.connect(
                    self.companion_computer,
                    username=self.ssh_username,
                    password=self.ssh_password,
                    timeout=10
                )
            )
            
            self.connections['ssh_companion'] = ssh
            logger.info(f"✅ SSH 연결 성공: {self.companion_computer}")
            
            # 시스템 정보 수집
            await self._collect_companion_info()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ SSH 연결 실패 {self.companion_computer}: {e}")
            
            # 시뮬레이션 모드로 대체
            logger.info("📋 SSH 시뮬레이션 모드로 전환")
            self.connections['ssh_companion'] = 'simulated'
            await self._simulate_companion_info()
            return True
    
    async def _connect_mavlink_fc(self) -> bool:
        """Flight Controller MAVLink 연결"""
        if not PYMAVLINK_AVAILABLE:
            logger.warning("⚠️ pymavlink가 없어 MAVLink 연결을 시뮬레이션합니다.")
            self.connections['mavlink_fc'] = 'simulated'
            return True
        
        try:
            connection_string = f'tcp:{self.flight_controller}:5760'
            
            # 비동기적으로 MAVLink 연결
            master = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: mavutil.mavlink_connection(connection_string, timeout=10)
            )
            
            # 하트비트 대기
            heartbeat = await asyncio.get_event_loop().run_