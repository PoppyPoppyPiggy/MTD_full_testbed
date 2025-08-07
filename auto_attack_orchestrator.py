#!/usr/bin/env python3
"""
DVD 자동 공격 오케스트레이터 및 실시간 탐지 시스템
위치: /home/kali/MTD/MTD_full_testbed/auto_attack_orchestrator.py

기능:
1. DVD 공격 스크립트 자동 실행 및 강도 조절
2. 실시간 공격 탐지 및 이상 지표 분석
3. 공격-탐지 피드백 루프 구현
4. CTI 데이터 자동 생성
"""

import asyncio
import subprocess
import json
import time
import threading
import signal
import sys
import os
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import logging

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class AttackIntensity(Enum):
    """공격 강도 레벨"""
    LIGHT = "light"           # 가벼운 탐지성 테스트
    MODERATE = "moderate"     # 보통 강도 공격
    AGGRESSIVE = "aggressive" # 강력한 공격
    STEALTH = "stealth"       # 은밀한 장기간 공격

class AttackCategory(Enum):
    """공격 카테고리"""
    RECONNAISSANCE = "reconnaissance"
    PROTOCOL_TAMPERING = "protocol_tampering"
    DENIAL_OF_SERVICE = "denial_of_service"
    INJECTION = "injection"
    EXFILTRATION = "exfiltration"
    FIRMWARE_ATTACKS = "firmware_attacks"

@dataclass
class AttackConfig:
    """공격 설정"""
    name: str
    category: AttackCategory
    script_path: str
    intensity: AttackIntensity
    duration: int  # 초
    interval: int  # 공격 간 간격(초)
    max_attempts: int
    success_threshold: float  # 성공률 임계값
    stealth_mode: bool
    target_detection: bool  # 탐지 시스템 목표 여부

@dataclass
class AttackResult:
    """공격 결과"""
    attack_name: str
    start_time: datetime
    end_time: datetime
    success: bool
    exit_code: int
    output: str
    error: str
    iocs_generated: List[str]
    detection_triggered: bool
    anomaly_score: float

@dataclass
class DetectionSignature:
    """탐지 시그니처"""
    name: str
    pattern: str
    category: str
    severity: str
    confidence: float
    description: str

class AttackOrchestrator:
    """공격 오케스트레이터"""
    
    def __init__(self, base_dir: str = "/home/kali/MTD/MTD_full_testbed"):
        self.base_dir = Path(base_dir)
        self.dvd_attacks_dir = self.base_dir / "dvd_lite" / "dvd_attacks"
        self.results_dir = self.base_dir / "results"
        self.logs_dir = self.base_dir / "logs"
        
        # 디렉토리 생성
        self.results_dir.mkdir(exist_ok=True)
        self.logs_dir.mkdir(exist_ok=True)
        
        # 공격 설정
        self.attack_configs = self._load_attack_configs()
        self.active_attacks = {}
        self.attack_results = []
        self.is_running = False
        
        # 탐지 시스템
        self.detector = AttackDetector()
        self.monitor = RealTimeMonitor()
        
        # 시그널 핸들러
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """시그널 핸들러"""
        logger.info(f"신호 {signum} 수신. 공격 중지 중...")
        self.stop_all_attacks()
        sys.exit(0)
    
    def _load_attack_configs(self) -> List[AttackConfig]:
        """공격 설정 로드"""
        configs = []
        
        # 정찰 공격
        configs.extend([
            AttackConfig(
                name="wifi_network_discovery",
                category=AttackCategory.RECONNAISSANCE,
                script_path="reconnaissance/wifi_discovery.sh",
                intensity=AttackIntensity.LIGHT,
                duration=30,
                interval=60,
                max_attempts=3,
                success_threshold=0.8,
                stealth_mode=True,
                target_detection=False
            ),
            AttackConfig(
                name="mavlink_service_discovery",
                category=AttackCategory.RECONNAISSANCE,
                script_path="reconnaissance/mavlink_discovery.sh",
                intensity=AttackIntensity.MODERATE,
                duration=45,
                interval=90,
                max_attempts=5,
                success_threshold=0.9,
                stealth_mode=True,
                target_detection=True
            ),
            AttackConfig(
                name="drone_discovery",
                category=AttackCategory.RECONNAISSANCE,
                script_path="reconnaissance/drone_discovery.sh",
                intensity=AttackIntensity.LIGHT,
                duration=60,
                interval=120,
                max_attempts=3,
                success_threshold=0.7,
                stealth_mode=True,
                target_detection=False
            )
        ])
        
        # 프로토콜 변조 공격
        configs.extend([
            AttackConfig(
                name="gps_spoofing",
                category=AttackCategory.PROTOCOL_TAMPERING,
                script_path="protocol_tampering/gps_spoofing.sh",
                intensity=AttackIntensity.AGGRESSIVE,
                duration=120,
                interval=300,
                max_attempts=2,
                success_threshold=0.6,
                stealth_mode=False,
                target_detection=True
            ),
            AttackConfig(
                name="mavlink_injection",
                category=AttackCategory.PROTOCOL_TAMPERING,
                script_path="protocol_tampering/mavlink_injection.sh",
                intensity=AttackIntensity.MODERATE,
                duration=90,
                interval=180,
                max_attempts=3,
                success_threshold=0.7,
                stealth_mode=False,
                target_detection=True
            )
        ])
        
        # DoS 공격
        configs.extend([
            AttackConfig(
                name="wifi_deauth",
                category=AttackCategory.DENIAL_OF_SERVICE,
                script_path="denial_of_service/wifi_deauth.sh",
                intensity=AttackIntensity.AGGRESSIVE,
                duration=60,
                interval=240,
                max_attempts=2,
                success_threshold=0.8,
                stealth_mode=False,
                target_detection=True
            ),
            AttackConfig(
                name="communication_flood",
                category=AttackCategory.DENIAL_OF_SERVICE,
                script_path="denial_of_service/communication_link_flood.sh",
                intensity=AttackIntensity.MODERATE,
                duration=45,
                interval=120,
                max_attempts=4,
                success_threshold=0.9,
                stealth_mode=False,
                target_detection=True
            )
        ])
        
        # 주입 공격
        configs.extend([
            AttackConfig(
                name="command_injection",
                category=AttackCategory.INJECTION,
                script_path="injection/mavlink_injection.sh",
                intensity=AttackIntensity.AGGRESSIVE,
                duration=75,
                interval=200,
                max_attempts=3,
                success_threshold=0.6,
                stealth_mode=False,
                target_detection=True
            ),
            AttackConfig(
                name="waypoint_injection",
                category=AttackCategory.INJECTION,
                script_path="injection/waypoint_injection.sh",
                intensity=AttackIntensity.MODERATE,
                duration=60,
                interval=180,
                max_attempts=3,
                success_threshold=0.7,
                stealth_mode=False,
                target_detection=True
            )
        ])
        
        return configs
    
    async def run_attack_campaign(self, intensity: AttackIntensity = AttackIntensity.MODERATE, 
                                 duration_hours: float = 1.0, 
                                 selected_categories: List[AttackCategory] = None):
        """공격 캠페인 실행"""
        logger.info(f"공격 캠페인 시작 - 강도: {intensity.value}, 지속시간: {duration_hours}시간")
        
        self.is_running = True
        
        # 카테고리 필터링
        if selected_categories:
            filtered_configs = [c for c in self.attack_configs if c.category in selected_categories]
        else:
            filtered_configs = self.attack_configs
        
        # 강도에 따른 설정 조정
        adjusted_configs = self._adjust_configs_for_intensity(filtered_configs, intensity)
        
        # 탐지 시스템 시작
        await self.detector.start()
        await self.monitor.start()
        
        # 공격 스케줄링
        end_time = datetime.now() + timedelta(hours=duration_hours)
        
        try:
            while self.is_running and datetime.now() < end_time:
                # 실행할 공격 선택
                attack_config = self._select_next_attack(adjusted_configs)
                
                if attack_config:
                    # 공격 실행
                    result = await self._execute_attack(attack_config)
                    self.attack_results.append(result)
                    
                    # 탐지 확인
                    if result.detection_triggered:
                        logger.warning(f"공격 {attack_config.name}이 탐지되었습니다!")
                        
                        # 은밀 모드로 전환
                        if intensity != AttackIntensity.STEALTH:
                            await self._switch_to_stealth_mode()
                    
                    # 결과 분석
                    await self._analyze_attack_result(result)
                
                # 다음 공격까지 대기
                await asyncio.sleep(30)  # 기본 대기 시간
                
        except Exception as e:
            logger.error(f"공격 캠페인 오류: {e}")
        finally:
            await self.stop_all_attacks()
    
    def _adjust_configs_for_intensity(self, configs: List[AttackConfig], 
                                    intensity: AttackIntensity) -> List[AttackConfig]:
        """강도에 따른 공격 설정 조정"""
        adjusted = []
        
        for config in configs:
            new_config = AttackConfig(**asdict(config))
            
            if intensity == AttackIntensity.LIGHT:
                new_config.duration = int(config.duration * 0.5)
                new_config.interval = int(config.interval * 2)
                new_config.max_attempts = max(1, config.max_attempts - 1)
                new_config.stealth_mode = True
                
            elif intensity == AttackIntensity.AGGRESSIVE:
                new_config.duration = int(config.duration * 1.5)
                new_config.interval = int(config.interval * 0.5)
                new_config.max_attempts = config.max_attempts + 2
                new_config.stealth_mode = False
                
            elif intensity == AttackIntensity.STEALTH:
                new_config.duration = int(config.duration * 0.3)
                new_config.interval = int(config.interval * 3)
                new_config.max_attempts = 1
                new_config.stealth_mode = True
                
            adjusted.append(new_config)
        
        return adjusted
    
    def _select_next_attack(self, configs: List[AttackConfig]) -> Optional[AttackConfig]:
        """다음 실행할 공격 선택"""
        # 현재 실행 중이지 않은 공격들
        available_attacks = [c for c in configs if c.name not in self.active_attacks]
        
        if not available_attacks:
            return None
        
        # 가중치 기반 선택
        weights = []
        for config in available_attacks:
            weight = 1.0
            
            # 탐지를 목표로 하는 공격에 더 높은 가중치
            if config.target_detection:
                weight *= 1.5
            
            # 최근 실패한 공격은 가중치 감소
            recent_failures = sum(1 for r in self.attack_results[-10:] 
                                if r.attack_name == config.name and not r.success)
            weight *= (0.8 ** recent_failures)
            
            weights.append(weight)
        
        # 가중치 기반 랜덤 선택
        total_weight = sum(weights)
        if total_weight > 0:
            weights = [w / total_weight for w in weights]
            return random.choices(available_attacks, weights=weights)[0]
        
        return random.choice(available_attacks)
    
    async def _execute_attack(self, config: AttackConfig) -> AttackResult:
        """공격 실행"""
        logger.info(f"공격 실행: {config.name} (강도: {config.intensity.value})")
        
        start_time = datetime.now()
        script_path = self.dvd_attacks_dir / config.script_path
        
        # 공격 스크립트 존재 확인
        if not script_path.exists():
            logger.warning(f"공격 스크립트를 찾을 수 없음: {script_path}")
            return self._create_simulated_result(config, start_time, False)
        
        try:
            # 공격 실행
            cmd = self._build_attack_command(config, script_path)
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=script_path.parent
            )
            
            # 활성 공격 목록에 추가
            self.active_attacks[config.name] = process
            
            # 타임아웃과 함께 대기
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), 
                    timeout=config.duration + 30
                )
                exit_code = process.returncode
                
            except asyncio.TimeoutError:
                logger.warning(f"공격 {config.name} 타임아웃")
                process.kill()
                stdout, stderr = b"", b"Timeout"
                exit_code = -1
            
            # 활성 공격 목록에서 제거
            self.active_attacks.pop(config.name, None)
            
            end_time = datetime.now()
            
            # 결과 분석
            success = exit_code == 0
            output = stdout.decode('utf-8', errors='ignore')
            error = stderr.decode('utf-8', errors='ignore')
            
            # IOC 추출
            iocs = self._extract_iocs_from_output(output, error)
            
            # 탐지 여부 확인
            detection_triggered = await self.detector.check_attack_detected(config.name, output)
            
            # 이상 점수 계산
            anomaly_score = await self.monitor.calculate_anomaly_score(config.name, start_time, end_time)
            
            result = AttackResult(
                attack_name=config.name,
                start_time=start_time,
                end_time=end_time,
                success=success,
                exit_code=exit_code,
                output=output,
                error=error,
                iocs_generated=iocs,
                detection_triggered=detection_triggered,
                anomaly_score=anomaly_score
            )
            
            logger.info(f"공격 완료: {config.name} - 성공: {success}, 탐지: {detection_triggered}")
            return result
            
        except Exception as e:
            logger.error(f"공격 실행 오류 {config.name}: {e}")
            return self._create_simulated_result(config, start_time, False)
    
    def _build_attack_command(self, config: AttackConfig, script_path: Path) -> List[str]:
        """공격 명령 구성"""
        cmd = ["bash", str(script_path)]
        
        # 강도에 따른 옵션 추가
        if config.intensity == AttackIntensity.AGGRESSIVE:
            cmd.extend(["--aggressive", "--max-power"])
        elif config.intensity == AttackIntensity.STEALTH:
            cmd.extend(["--stealth", "--quiet"])
        elif config.intensity == AttackIntensity.LIGHT:
            cmd.extend(["--light", "--minimal"])
        
        # 지속시간 설정
        cmd.extend(["--duration", str(config.duration)])
        
        # 은밀 모드
        if config.stealth_mode:
            cmd.append("--stealth")
        
        return cmd
    
    def _extract_iocs_from_output(self, stdout: str, stderr: str) -> List[str]:
        """공격 출력에서 IOC 추출"""
        iocs = []
        
        # 일반적인 IOC 패턴들
        import re
        
        # IP 주소
        ip_pattern = r'\b(?:\d{1,3}\.){3}\d{1,3}\b'
        iocs.extend(re.findall(ip_pattern, stdout + stderr))
        
        # MAC 주소
        mac_pattern = r'\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b'
        iocs.extend(re.findall(mac_pattern, stdout + stderr))
        
        # 파일 경로
        file_pattern = r'/(?:[^/\s]+/)*[^/\s]+'
        iocs.extend(re.findall(file_pattern, stdout + stderr))
        
        return list(set(iocs))  # 중복 제거
    
    def _create_simulated_result(self, config: AttackConfig, start_time: datetime, 
                                success: bool) -> AttackResult:
        """시뮬레이션된 결과 생성"""
        end_time = datetime.now()
        
        return AttackResult(
            attack_name=config.name,
            start_time=start_time,
            end_time=end_time,
            success=success,
            exit_code=0 if success else 1,
            output=f"Simulated attack: {config.name}",
            error="",
            iocs_generated=[],
            detection_triggered=False,
            anomaly_score=random.uniform(0.1, 0.3)
        )
    
    async def _switch_to_stealth_mode(self):
        """은밀 모드로 전환"""
        logger.info("탐지로 인해 은밀 모드로 전환")
        
        # 현재 실행 중인 공격들을 더 은밀하게 조정
        for attack_name, process in self.active_attacks.items():
            # 공격 강도 감소 신호 전송 (실제로는 구현 복잡)
            logger.info(f"공격 {attack_name}을 은밀 모드로 조정")
    
    async def _analyze_attack_result(self, result: AttackResult):
        """공격 결과 분석"""
        # 결과를 파일로 저장
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        result_file = self.results_dir / f"attack_result_{result.attack_name}_{timestamp}.json"
        
        with open(result_file, 'w') as f:
            # datetime 객체를 문자열로 변환
            result_dict = asdict(result)
            result_dict['start_time'] = result.start_time.isoformat()
            result_dict['end_time'] = result.end_time.isoformat()
            json.dump(result_dict, f, indent=2)
    
    async def stop_all_attacks(self):
        """모든 공격 중지"""
        logger.info("모든 공격 중지 중...")
        
        self.is_running = False
        
        # 활성 공격 프로세스 종료
        for attack_name, process in self.active_attacks.items():
            try:
                process.terminate()
                await asyncio.wait_for(process.wait(), timeout=5)
            except asyncio.TimeoutError:
                process.kill()
            except Exception as e:
                logger.error(f"공격 {attack_name} 종료 오류: {e}")
        
        self.active_attacks.clear()
        
        # 탐지 시스템 중지
        await self.detector.stop()
        await self.monitor.stop()
        
        # 최종 리포트 생성
        await self._generate_final_report()
    
    async def _generate_final_report(self):
        """최종 리포트 생성"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = self.results_dir / f"attack_campaign_report_{timestamp}.json"
        
        total_attacks = len(self.attack_results)
        successful_attacks = sum(1 for r in self.attack_results if r.success)
        detected_attacks = sum(1 for r in self.attack_results if r.detection_triggered)
        
        report = {
            "campaign_summary": {
                "total_attacks": total_attacks,
                "successful_attacks": successful_attacks,
                "success_rate": successful_attacks / total_attacks if total_attacks > 0 else 0,
                "detected_attacks": detected_attacks,
                "detection_rate": detected_attacks / total_attacks if total_attacks > 0 else 0,
                "avg_anomaly_score": sum(r.anomaly_score for r in self.attack_results) / total_attacks if total_attacks > 0 else 0
            },
            "attack_results": [asdict(r) for r in self.attack_results],
            "generated_at": datetime.now().isoformat()
        }
        
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        logger.info(f"최종 리포트 생성: {report_file}")

class AttackDetector:
    """공격 탐지 시스템"""
    
    def __init__(self):
        self.signatures = self._load_detection_signatures()
        self.detection_log = []
        self.is_running = False
    
    def _load_detection_signatures(self) -> List[DetectionSignature]:
        """탐지 시그니처 로드"""
        return [
            DetectionSignature(
                name="wifi_deauth_detection",
                pattern=r"deauth|deauthentication|disconnected",
                category="denial_of_service",
                severity="high",
                confidence=0.9,
                description="WiFi 인증 해제 공격 탐지"
            ),
            DetectionSignature(
                name="gps_spoofing_detection",
                pattern=r"gps.*spoof|position.*fake|location.*inject",
                category="protocol_tampering",
                severity="critical",
                confidence=0.95,
                description="GPS 스푸핑 공격 탐지"
            ),
            DetectionSignature(
                name="mavlink_injection_detection",
                pattern=r"mavlink.*inject|command.*inject|message.*tamper",
                category="injection",
                severity="high",
                confidence=0.85,
                description="MAVLink 명령 주입 공격 탐지"
            ),
            DetectionSignature(
                name="reconnaissance_detection",
                pattern=r"scan|discovery|enumerate|probe",
                category="reconnaissance",
                severity="medium",
                confidence=0.7,
                description="정찰 활동 탐지"
            )
        ]
    
    async def start(self):
        """탐지 시스템 시작"""
        self.is_running = True
        logger.info("공격 탐지 시스템 시작")
    
    async def stop(self):
        """탐지 시스템 중지"""
        self.is_running = False
        logger.info("공격 탐지 시스템 중지")
    
    async def check_attack_detected(self, attack_name: str, output: str) -> bool:
        """공격 탐지 확인"""
        import re
        
        for signature in self.signatures:
            if re.search(signature.pattern, output, re.IGNORECASE):
                detection = {
                    "timestamp": datetime.now().isoformat(),
                    "attack_name": attack_name,
                    "signature_name": signature.name,
                    "confidence": signature.confidence,
                    "severity": signature.severity
                }
                
                self.detection_log.append(detection)
                logger.warning(f"공격 탐지: {signature.name} (신뢰도: {signature.confidence})")
                return True
        
        return False

class RealTimeMonitor:
    """실시간 모니터링 시스템"""
    
    def __init__(self):
        self.baseline_metrics = {}
        self.current_metrics = {}
        self.anomaly_threshold = 0.7
        self.is_running = False
    
    async def start(self):
        """모니터링 시작"""
        self.is_running = True
        
        # 베이스라인 메트릭 수집
        await self._collect_baseline_metrics()
        
        # 실시간 모니터링 시작
        asyncio.create_task(self._monitor_loop())
        
        logger.info("실시간 모니터링 시작")
    
    async def stop(self):
        """모니터링 중지"""
        self.is_running = False
        logger.info("실시간 모니터링 중지")
    
    async def _collect_baseline_metrics(self):
        """베이스라인 메트릭 수집"""
        # 정상 상태의 시스템 메트릭 수집
        self.baseline_metrics = {
            "cpu_usage": await self._get_cpu_usage(),
            "memory_usage": await self._get_memory_usage(),
            "network_connections": await self._get_network_connections(),
            "process_count": await self._get_process_count()
        }
        
        logger.info("베이스라인 메트릭 수집 완료")
    
    async def _monitor_loop(self):
        """모니터링 루프"""
        while self.is_running:
            try:
                self.current_metrics = {
                    "cpu_usage": await self._get_cpu_usage(),
                    "memory_usage": await self._get_memory_usage(),
                    "network_connections": await self._get_network_connections(),
                    "process_count": await self._get_process_count()
                }
                
                await asyncio.sleep(10)  # 10초마다 모니터링
                
            except Exception as e:
                logger.error(f"모니터링 루프 오류: {e}")
                await asyncio.sleep(5)
    
    async def calculate_anomaly_score(self, attack_name: str, start_time: datetime, 
                                    end_time: datetime) -> float:
        """이상 점수 계산"""
        if not self.baseline_metrics or not self.current_metrics:
            return 0.0
        
        anomaly_score = 0.0
        
        # CPU 사용률 이상
        cpu_baseline = self.baseline_metrics.get("cpu_usage", 0)
        cpu_current = self.current_metrics.get("cpu_usage", 0)
        cpu_anomaly = abs(cpu_current - cpu_baseline) / 100.0
        anomaly_score += cpu_anomaly * 0.3
        
        # 메모리 사용률 이상
        mem_baseline = self.baseline_metrics.get("memory_usage", 0)
        mem_current = self.current_metrics.get("memory_usage", 0)
        mem_anomaly = abs(mem_current - mem_baseline) / 100.0
        anomaly_score += mem_anomaly * 0.2
        
        # 네트워크 연결 수 이상
        net_baseline = self.baseline_metrics.get("network_connections", 0)
        net_current = self.current_metrics.get("network_connections", 0)
        net_anomaly = abs(net_current - net_baseline) / max(net_baseline, 1)
        anomaly_score += min(net_anomaly, 1.0) * 0.3
        
        # 프로세스 수 이상
        proc_baseline = self.baseline_metrics.get("process_count", 0)
        proc_current = self.current_metrics.get("process_count", 0)
        proc_anomaly = abs(proc_current - proc_baseline) / max(proc_baseline, 1)
        anomaly_score += min(proc_anomaly, 1.0) * 0.2
        
        return min(anomaly_score, 1.0)
    
    async def _get_cpu_usage(self) -> float:
        """CPU 사용률 조회"""
        try:
            result = await asyncio.create_subprocess_exec(
                "cat", "/proc/loadavg",
                stdout=asyncio.subprocess.PIPE
            )
            stdout, _ = await result.communicate()
            load_avg = float(stdout.decode().split()[0])
            return min(load_avg * 100, 100.0)  # 백분율로 변환
        except:
            return 0.0
    
    async def _get_memory_usage(self) -> float:
        """메모리 사용률 조회"""
        try:
            result = await asyncio.create_subprocess_exec(
                "free", "-m",
                stdout=asyncio.subprocess.PIPE
            )
            stdout, _ = await result.communicate()
            lines = stdout.decode().split('\n')
            mem_line = lines[1].split()
            total = int(mem_line[1])
            used = int(mem_line[2])
            return (used / total) * 100 if total > 0 else 0.0
        except:
            return 0.0
    
    async def _get_network_connections(self) -> int:
        """네트워크 연결 수 조회"""
        try:
            result = await asyncio.create_subprocess_exec(
                "netstat", "-tun",
                stdout=asyncio.subprocess.PIPE
            )
            stdout, _ = await result.communicate()
            lines = stdout.decode().split('\n')
            return len([line for line in lines if 'ESTABLISHED' in line])
        except:
            return 0
    
    async def _get_process_count(self) -> int:
        """프로세스 수 조회"""
        try:
            result = await asyncio.create_subprocess_exec(
                "ps", "aux",
                stdout=asyncio.subprocess.PIPE
            )
            stdout, _ = await result.communicate()
            lines = stdout.decode().split('\n')
            return len(lines) - 1  # 헤더 제외
        except:
            return 0

# 메인 실행 함수
async def main():
    """메인 실행 함수"""
    import argparse
    
    parser = argparse.ArgumentParser(description="DVD 자동 공격 오케스트레이터")
    parser.add_argument("--intensity", choices=['light', 'moderate', 'aggressive', 'stealth'],
                       default='moderate', help="공격 강도")
    parser.add_argument("--duration", type=float, default=1.0, help="지속시간 (시간)")
    parser.add_argument("--categories", nargs='+', 
                       choices=['reconnaissance', 'protocol_tampering', 'denial_of_service', 
                               'injection', 'exfiltration', 'firmware_attacks'],
                       help="공격 카테고리 선택")
    
    args = parser.parse_args()
    
    print("🚁 DVD 자동 공격 오케스트레이터 시작")
    print("=" * 50)
    print(f"강도: {args.intensity}")
    print(f"지속시간: {args.duration}시간")
    if args.categories:
        print(f"카테고리: {', '.join(args.categories)}")
    print("=" * 50)
    
    # 공격 오케스트레이터 생성
    orchestrator = AttackOrchestrator()
    
    # 강도 및 카테고리 설정
    intensity = AttackIntensity(args.intensity)
    categories = [AttackCategory(cat) for cat in args.categories] if args.categories else None
    
    try:
        # 공격 캠페인 실행
        await orchestrator.run_attack_campaign(
            intensity=intensity,
            duration_hours=args.duration,
            selected_categories=categories
        )
    except KeyboardInterrupt:
        print("\n사용자 중단")
    except Exception as e:
        print(f"오류 발생: {e}")
    finally:
        await orchestrator.stop_all_attacks()

if __name__ == "__main__":
    asyncio.run(main())