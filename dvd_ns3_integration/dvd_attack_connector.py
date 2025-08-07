# 파일: /home/kali/MTD/MTD_full_testbed/dvd_ns3_integration/dvd_attack_connector.py
# 목적: DVD 공격 스크립트들과 NS-3 시뮬레이션 연동을 위한 커넥터
# 기반: dvd_lite/dvd_attacks 모듈들의 실시간 모니터링

import asyncio
import subprocess
import json
import time
import threading
import logging
import psutil
import os
import signal
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import docker

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('DVD-Attack-Connector')

class DVDAttackFileMonitor(FileSystemEventHandler):
    """DVD 공격 스크립트 파일 모니터링"""
    
    def __init__(self, callback):
        self.callback = callback
        self.monitored_extensions = {'.sh', '.py', '.txt'}  # IOC 파일 포함
        
    def on_modified(self, event):
        if not event.is_directory:
            file_path = Path(event.src_path)
            if file_path.suffix in self.monitored_extensions:
                self.callback('file_modified', str(file_path))
    
    def on_created(self, event):
        if not event.is_directory:
            file_path = Path(event.src_path)
            if file_path.suffix in self.monitored_extensions:
                self.callback('file_created', str(file_path))

class DVDAttackExecutor:
    """DVD 공격 스크립트 실행 및 모니터링"""
    
    def __init__(self, attack_base_dir: str = "/home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks"):
        self.attack_base_dir = Path(attack_base_dir)
        self.running_attacks = {}
        self.attack_results = {}
        self.file_observer = None
        
        # 공격 카테고리별 스크립트 매핑
        self.attack_categories = {
            'reconnaissance': [
                'wifi_network_discovery.sh',
                'mavlink_service_discovery.sh',
                'drone_component_enumeration.sh',
                'camera_stream_discovery.sh'
            ],
            'protocol_tampering': [
                'gps_spoofing.sh',
                'mavlink_packet_injection.sh',
                'rf_jamming.sh'
            ],
            'denial_of_service': [
                'mavlink_flood.sh',
                'wifi_deauth.sh',
                'resource_exhaustion.sh',
                'service_disruption.sh'
            ],
            'injection': [
                'flight_plan_injection.sh',
                'parameter_manipulation.sh',
                'firmware_upload_manipulation.sh',
                'sql_injection.sh'
            ],
            'exfiltration': [
                'telemetry_data_exfiltration.sh',
                'flight_log_extraction.sh',
                'video_stream_hijacking.sh'
            ],
            'firmware_attacks': [
                'bootloader_exploitation.sh',
                'firmware_rollback.sh',
                'secure_boot_bypass.sh'
            ]
        }
    
    async def start_monitoring(self):
        """공격 모니터링 시작"""
        logger.info("🎯 DVD 공격 모니터링 시작")
        
        # 파일 시스템 모니터링 시작
        self.file_observer = Observer()
        event_handler = DVDAttackFileMonitor(self._handle_file_event)
        self.file_observer.schedule(event_handler, str(self.attack_base_dir), recursive=True)
        self.file_observer.start()
        
        # 주기적 프로세스 모니터링
        while True:
            await self._monitor_attack_processes()
            await self._monitor_ioc_files()
            await asyncio.sleep(5)
    
    def _handle_file_event(self, event_type: str, file_path: str):
        """파일 이벤트 처리"""
        logger.debug(f"📁 파일 이벤트: {event_type} - {file_path}")
        
        # IOC 파일 업데이트 감지
        if 'iocs.txt' in file_path:
            asyncio.create_task(self._process_ioc_update(file_path))
    
    async def _monitor_attack_processes(self):
        """실행 중인 공격 프로세스 모니터링"""
        current_processes = {}
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time', 'cpu_percent', 'memory_percent']):
            try:
                cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
                
                # DVD 공격 스크립트 실행 탐지
                if 'dvd_attacks' in cmdline:
                    attack_type = self._identify_attack_type(cmdline)
                    if attack_type:
                        pid = proc.info['pid']
                        current_processes[pid] = {
                            'pid': pid,
                            'attack_type': attack_type,
                            'cmdline': cmdline,
                            'start_time': proc.info['create_time'],
                            'cpu_percent': proc.info['cpu_percent'],
                            'memory_percent': proc.info['memory_percent'],
                            'status': 'RUNNING'
                        }
                        
                        # 새로운 공격 프로세스 발견
                        if pid not in self.running_attacks:
                            logger.info(f"🚨 새로운 공격 탐지: {attack_type} (PID: {pid})")
                            await self._notify_attack_start(current_processes[pid])
            
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        # 종료된 공격 프로세스 탐지
        for pid in list(self.running_attacks.keys()):
            if pid not in current_processes:
                logger.info(f"✅ 공격 종료: {self.running_attacks[pid]['attack_type']} (PID: {pid})")
                await self._notify_attack_end(self.running_attacks[pid])
                del self.running_attacks[pid]
        
        # 실행 중인 공격 목록 업데이트
        self.running_attacks.update(current_processes)
    
    def _identify_attack_type(self, cmdline: str) -> Optional[str]:
        """명령줄에서 공격 유형 식별"""
        for category, scripts in self.attack_categories.items():
            for script in scripts:
                if script in cmdline:
                    return f"{category}/{script}"
        return None
    
    async def _monitor_ioc_files(self):
        """IOC 파일 모니터링"""
        ioc_dir = Path("/tmp")
        ioc_files = list(ioc_dir.glob("*iocs.txt"))
        
        for ioc_file in ioc_files:
            try:
                # 최근 수정된 IOC 파일만 처리
                if ioc_file.stat().st_mtime > time.time() - 60:
                    await self._process_ioc_update(str(ioc_file))
            except Exception as e:
                logger.error(f"IOC 파일 처리 오류: {e}")
    
    async def _process_ioc_update(self, ioc_file_path: str):
        """IOC 파일 업데이트 처리"""
        try:
            with open(ioc_file_path, 'r') as f:
                iocs = [line.strip() for line in f.readlines() if line.strip()]
            
            if iocs:
                attack_type = Path(ioc_file_path).stem.replace('_iocs', '')
                logger.info(f"📄 IOC 업데이트: {attack_type} - {len(iocs)}개 지표")
                
                # IOC 분석 및 분류
                categorized_iocs = self._categorize_iocs(iocs)
                
                # NS-3로 IOC 정보 전송
                await self._send_iocs_to_ns3(attack_type, categorized_iocs)
                
        except Exception as e:
            logger.error(f"IOC 처리 오류: {e}")
    
    def _categorize_iocs(self, iocs: List[str]) -> Dict[str, List[str]]:
        """IOC를 카테고리별로 분류"""
        categories = {
            'network': [],
            'process': [],
            'file': [],
            'registry': [],
            'behavior': []
        }
        
        for ioc in iocs:
            if any(keyword in ioc.lower() for keyword in ['ip:', 'port:', 'tcp:', 'udp:', 'http:']):
                categories['network'].append(ioc)
            elif any(keyword in ioc.lower() for keyword in ['pid:', 'process:', 'exec:']):
                categories['process'].append(ioc)
            elif any(keyword in ioc.lower() for keyword in ['file:', 'path:', 'created:', 'modified:']):
                categories['file'].append(ioc)
            elif any(keyword in ioc.lower() for keyword in ['registry:', 'key:', 'hklm:', 'hkcu:']):
                categories['registry'].append(ioc)
            else:
                categories['behavior'].append(ioc)
        
        return categories
    
    async def _notify_attack_start(self, attack_info: Dict):
        """공격 시작 알림"""
        logger.info(f"🎯 공격 시작 알림: {attack_info}")
        # NS-3로 공격 시작 이벤트 전송
        await self._send_to_ns3('attack_start', attack_info)
    
    async def _notify_attack_end(self, attack_info: Dict):
        """공격 종료 알림"""
        logger.info(f"✅ 공격 종료 알림: {attack_info}")
        # NS-3로 공격 종료 이벤트 전송
        await self._send_to_ns3('attack_end', attack_info)
    
    async def _send_to_ns3(self, event_type: str, data: Dict):
        """NS-3로 이벤트 전송"""
        try:
            # NS-3 통신 소켓을 통해 이벤트 전송
            message = {
                'event_type': event_type,
                'timestamp': time.time(),
                'data': data
            }
            # 실제 구현에서는 소켓 통신 코드 추가
            logger.debug(f"📡 NS-3로 전송: {message}")
        except Exception as e:
            logger.error(f"NS-3 전송 오류: {e}")
    
    async def _send_iocs_to_ns3(self, attack_type: str, iocs: Dict[str, List[str]]):
        """IOC 정보를 NS-3로 전송"""
        message = {
            'event_type': 'ioc_update',
            'attack_type': attack_type,
            'timestamp': time.time(),
            'iocs': iocs
        }
        await self._send_to_ns3('ioc_update', message)
    
    async def execute_attack_scenario(self, category: str, script_name: str = None) -> Dict:
        """공격 시나리오 실행"""
        if category not in self.attack_categories:
            raise ValueError(f"지원하지 않는 공격 카테고리: {category}")
        
        scripts = self.attack_categories[category]
        if script_name:
            if script_name not in scripts:
                raise ValueError(f"카테고리 {category}에 {script_name} 스크립트가 없습니다")
            scripts = [script_name]
        
        results = {}
        
        for script in scripts:
            script_path = self.attack_base_dir / category / script
            if script_path.exists():
                logger.info(f"🚀 공격 실행: {category}/{script}")
                result = await self._execute_script(script_path)
                results[script] = result
            else:
                logger.warning(f"⚠️ 스크립트 없음: {script_path}")
                results[script] = {'status': 'not_found', 'error': 'Script file not found'}
        
        return results
    
    async def _execute_script(self, script_path: Path) -> Dict:
        """개별 스크립트 실행"""
        try:
            # 스크립트 실행 권한 확인
            if not os.access(script_path, os.X_OK):
                os.chmod(script_path, 0o755)
            
            # 스크립트 실행
            process = await asyncio.create_subprocess_exec(
                str(script_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=script_path.parent
            )
            
            stdout, stderr = await process.communicate()
            
            result = {
                'status': 'completed' if process.returncode == 0 else 'failed',
                'return_code': process.returncode,
                'stdout': stdout.decode('utf-8', errors='ignore'),
                'stderr': stderr.decode('utf-8', errors='ignore'),
                'execution_time': time.time()
            }
            
            logger.info(f"✅ 스크립트 실행 완료: {script_path.name} (코드: {process.returncode})")
            return result
            
        except Exception as e:
            logger.error(f"❌ 스크립트 실행 오류: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'execution_time': time.time()
            }
    
    def get_attack_status(self) -> Dict:
        """현재 공격 상태 반환"""
        return {
            'running_attacks': self.running_attacks,
            'attack_results': self.attack_results,
            'monitored_categories': list(self.attack_categories.keys()),
            'timestamp': time.time()
        }
    
    def stop_monitoring(self):
        """모니터링 중지"""
        if self.file_observer:
            self.file_observer.stop()
            self.file_observer.join()
        logger.info("🛑 DVD 공격 모니터링 중지")

class DVDDockerIntegration:
    """DVD 도커 컨테이너와의 통합"""
    
    def __init__(self):
        self.docker_client = docker.from_env()
        self.monitored_containers = {}
        
    async def monitor_dvd_containers(self):
        """DVD 도커 컨테이너 모니터링"""
        while True:
            try:
                containers = self.docker_client.containers.list(all=True)
                dvd_containers = [c for c in containers 
                                if any(keyword in c.name.lower() 
                                      for keyword in ['dvd', 'drone', 'ardupilot', 'mavlink'])]
                
                for container in dvd_containers:
                    container_info = await self._analyze_container(container)
                    self.monitored_containers[container.id] = container_info
                    
                    # 컨테이너 상태 변화 감지
                    if self._detect_container_anomaly(container_info):
                        logger.warning(f"🚨 컨테이너 이상 탐지: {container.name}")
                        await self._handle_container_anomaly(container_info)
                
                await asyncio.sleep(10)
                
            except Exception as e:
                logger.error(f"도커 모니터링 오류: {e}")
                await asyncio.sleep(30)
    
    async def _analyze_container(self, container) -> Dict:
        """컨테이너 상태 분석"""
        try:
            stats = container.stats(stream=False)
            
            # 기본 정보
            info = {
                'id': container.id[:12],
                'name': container.name,
                'status': container.status,
                'image': container.image.tags[0] if container.image.tags else 'unknown',
                'created': container.attrs['Created'],
                'timestamp': time.time()
            }
            
            # 리소스 사용량
            if container.status == 'running':
                info.update({
                    'cpu_usage': self._calculate_cpu_usage(stats),
                    'memory_usage': self._calculate_memory_usage(stats),
                    'network_io': self._get_network_io(stats),
                    'block_io': self._get_block_io(stats)
                })
                
                # 로그 분석
                info['log_analysis'] = await self._analyze_container_logs(container)
            
            return info
            
        except Exception as e:
            logger.error(f"컨테이너 분석 오류: {e}")
            return {'id': container.id[:12], 'error': str(e)}
    
    def _calculate_cpu_usage(self, stats) -> float:
        """CPU 사용률 계산"""
        try:
            cpu_delta = stats['cpu_stats']['cpu_usage']['total_usage'] - \
                       stats['precpu_stats']['cpu_usage']['total_usage']
            system_delta = stats['cpu_stats']['system_cpu_usage'] - \
                          stats['precpu_stats']['system_cpu_usage']
            
            if system_delta > 0:
                return round((cpu_delta / system_delta) * 100.0, 2)
        except:
            pass
        return 0.0
    
    def _calculate_memory_usage(self, stats) -> Dict:
        """메모리 사용량 계산"""
        try:
            memory_usage = stats['memory_stats']['usage']
            memory_limit = stats['memory_stats']['limit']
            return {
                'usage_bytes': memory_usage,
                'limit_bytes': memory_limit,
                'usage_percent': round((memory_usage / memory_limit) * 100, 2)
            }
        except:
            return {'usage_bytes': 0, 'limit_bytes': 0, 'usage_percent': 0}
    
    def _get_network_io(self, stats) -> Dict:
        """네트워크 I/O 정보"""
        try:
            networks = stats.get('networks', {})
            total_rx = sum(net['rx_bytes'] for net in networks.values())
            total_tx = sum(net['tx_bytes'] for net in networks.values())
            return {'rx_bytes': total_rx, 'tx_bytes': total_tx}
        except:
            return {'rx_bytes': 0, 'tx_bytes': 0}
    
    def _get_block_io(self, stats) -> Dict:
        """블록 I/O 정보"""
        try:
            blkio_stats = stats.get('blkio_stats', {})
            io_service_bytes = blkio_stats.get('io_service_bytes_recursive', [])
            
            read_bytes = sum(entry['value'] for entry in io_service_bytes 
                           if entry['op'] == 'Read')
            write_bytes = sum(entry['value'] for entry in io_service_bytes 
                            if entry['op'] == 'Write')
            
            return {'read_bytes': read_bytes, 'write_bytes': write_bytes}
        except:
            return {'read_bytes': 0, 'write_bytes': 0}
    
    async def _analyze_container_logs(self, container) -> Dict:
        """컨테이너 로그 분석"""
        try:
            logs = container.logs(tail=100).decode('utf-8', errors='ignore')
            
            # 공격 패턴 탐지
            attack_indicators = []
            error_count = 0
            warning_count = 0
            
            for line in logs.split('\n'):
                line_lower = line.lower()
                
                # 에러 및 경고 카운트
                if 'error' in line_lower:
                    error_count += 1
                if 'warning' in line_lower or 'warn' in line_lower:
                    warning_count += 1
                
                # 공격 지표 탐지
                attack_patterns = [
                    ('sql_injection', ['union select', 'drop table', "' or 1=1"]),
                    ('xss', ['<script>', 'javascript:', 'onerror=']),
                    ('command_injection', ['&& cat', '; cat', '| cat']),
                    ('brute_force', ['401 unauthorized', 'authentication failed']),
                    ('dos', ['connection timeout', 'too many requests'])
                ]
                
                for attack_type, patterns in attack_patterns:
                    if any(pattern in line_lower for pattern in patterns):
                        attack_indicators.append(f"{attack_type}:{line.strip()[:100]}")
            
            return {
                'error_count': error_count,
                'warning_count': warning_count,
                'attack_indicators': attack_indicators,
                'log_lines': len(logs.split('\n'))
            }
            
        except Exception as e:
            logger.error(f"로그 분석 오류: {e}")
            return {'error': str(e)}
    
    def _detect_container_anomaly(self, container_info: Dict) -> bool:
        """컨테이너 이상 탐지"""
        if 'error' in container_info:
            return False
        
        # CPU 사용률 이상
        if container_info.get('cpu_usage', 0) > 80:
            return True
        
        # 메모리 사용률 이상
        memory_usage = container_info.get('memory_usage', {})
        if memory_usage.get('usage_percent', 0) > 90:
            return True
        
        # 공격 지표 탐지
        log_analysis = container_info.get('log_analysis', {})
        if log_analysis.get('attack_indicators', []):
            return True
        
        # 에러 비율 이상
        error_count = log_analysis.get('error_count', 0)
        log_lines = log_analysis.get('log_lines', 1)
        if error_count / log_lines > 0.1:  # 10% 이상 에러
            return True
        
        return False
    
    async def _handle_container_anomaly(self, container_info: Dict):
        """컨테이너 이상 처리"""
        logger.warning(f"🚨 컨테이너 이상 처리: {container_info['name']}")
        
        # NS-3로 이상 상황 전송
        anomaly_data = {
            'container_id': container_info['id'],
            'container_name': container_info['name'],
            'anomaly_type': 'container_anomaly',
            'details': container_info,
            'timestamp': time.time()
        }
        
        # 여기서 NS-3 통신 구현
        logger.info(f"📡 NS-3로 컨테이너 이상 알림 전송: {anomaly_data}")

class IntegratedDVDNS3Service:
    """통합 DVD-NS3 서비스"""
    
    def __init__(self):
        self.attack_executor = DVDAttackExecutor()
        self.docker_integration = DVDDockerIntegration()
        self.running = False
        
    async def start_service(self):
        """통합 서비스 시작"""
        self.running = True
        logger.info("🚀 통합 DVD-NS3 서비스 시작")
        
        # 병렬 태스크 실행
        tasks = [
            asyncio.create_task(self.attack_executor.start_monitoring()),
            asyncio.create_task(self.docker_integration.monitor_dvd_containers()),
            asyncio.create_task(self._integration_coordination())
        ]
        
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            logger.info("서비스 중지 요청됨")
        finally:
            await self.stop_service()
    
    async def _integration_coordination(self):
        """통합 조정 루프"""
        while self.running:
            try:
                # 공격 상태와 도커 상태 통합 분석
                attack_status = self.attack_executor.get_attack_status()
                docker_status = self.docker_integration.monitored_containers
                
                # 상관관계 분석
                correlations = self._analyze_correlations(attack_status, docker_status)
                
                if correlations:
                    logger.info(f"🔗 상관관계 탐지: {len(correlations)}개")
                    for correlation in correlations:
                        await self._handle_correlation(correlation)
                
                await asyncio.sleep(30)
                
            except Exception as e:
                logger.error(f"통합 조정 오류: {e}")
                await asyncio.sleep(60)
    
    def _analyze_correlations(self, attack_status: Dict, docker_status: Dict) -> List[Dict]:
        """공격과 도커 상태 간 상관관계 분석"""
        correlations = []
        
        # 실행 중인 공격과 컨테이너 이상의 시간 상관관계
        for attack_pid, attack_info in attack_status['running_attacks'].items():
            attack_time = attack_info['start_time']
            
            for container_id, container_info in docker_status.items():
                if 'log_analysis' in container_info:
                    log_analysis = container_info['log_analysis']
                    
                    # 공격 시작 후 컨테이너에서 공격 지표 발견
                    if (log_analysis.get('attack_indicators') and
                        container_info['timestamp'] > attack_time):
                        
                        correlations.append({
                            'type': 'attack_container_correlation',
                            'attack_info': attack_info,
                            'container_info': container_info,
                            'correlation_score': self._calculate_correlation_score(
                                attack_info, container_info
                            )
                        })
        
        return correlations
    
    def _calculate_correlation_score(self, attack_info: Dict, container_info: Dict) -> float:
        """상관관계 점수 계산"""
        score = 0.0
        
        # 시간 근접성 (최근일수록 높은 점수)
        time_diff = container_info['timestamp'] - attack_info['start_time']
        if time_diff < 300:  # 5분 이내
            score += 0.5
        elif time_diff < 900:  # 15분 이내
            score += 0.3
        
        # 공격 유형과 컨테이너 지표 매칭
        attack_type = attack_info.get('attack_type', '')
        log_analysis = container_info.get('log_analysis', {})
        
        if 'sql_injection' in attack_type and any('sql' in indicator.lower() 
                                                 for indicator in log_analysis.get('attack_indicators', [])):
            score += 0.4
        
        if 'dos' in attack_type and log_analysis.get('error_count', 0) > 10:
            score += 0.3
        
        return min(score, 1.0)
    
    async def _handle_correlation(self, correlation: Dict):
        """상관관계 처리"""
        logger.info(f"🔗 상관관계 처리: {correlation['type']} (점수: {correlation['correlation_score']})")
        
        # NS-3로 상관관계 정보 전송
        correlation_event = {
            'event_type': 'attack_container_correlation',
            'correlation': correlation,
            'timestamp': time.time()
        }
        
        # 실제 NS-3 통신 구현 필요
        logger.info(f"📡 NS-3로 상관관계 전송: {correlation_event}")
    
    async def stop_service(self):
        """서비스 중지"""
        self.running = False
        self.attack_executor.stop_monitoring()
        logger.info("🛑 통합 DVD-NS3 서비스 중지")
    
    def get_comprehensive_status(self) -> Dict:
        """종합 상태 반환"""
        return {
            'service_status': 'RUNNING' if self.running else 'STOPPED',
            'attack_status': self.attack_executor.get_attack_status(),
            'docker_status': self.docker_integration.monitored_containers,
            'timestamp': time.time()
        }

async def main():
    """메인 실행 함수"""
    service = IntegratedDVDNS3Service()
    
    def signal_handler(signum, frame):
        logger.info("종료 신호 수신")
        asyncio.create_task(service.stop_service())
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        await service.start_service()
    except KeyboardInterrupt:
        logger.info("사용자 중단 요청")
    except Exception as e:
        logger.error(f"서비스 실행 오류: {e}")
    finally:
        await service.stop_service()

if __name__ == "__main__":
    asyncio.run(main())