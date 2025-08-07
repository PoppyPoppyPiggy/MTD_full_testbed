#!/usr/bin/env python3
"""
=============================================================================
DVD Attack Orchestrator - 전체 공격 순회 및 지도학습 시스템
=============================================================================
파일: /home/kali/MTD/MTD_full_testbed/dvd_lite/dvd_attacks/attack_orchestrator.py
목적: 모든 공격 시나리오의 체계적 실행 및 지도학습 데이터 생성
작성자: MTD Testbed Team
=============================================================================
"""

import asyncio
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
import logging
from enum import Enum

# 프로젝트 루트 경로 설정
PROJECT_ROOT = Path("/home/kali/MTD/MTD_full_testbed")
sys.path.append(str(PROJECT_ROOT))

try:
    from dvd_lite.dvd_attacks.registry.management import (
        get_all_attacks, get_attacks_by_tactic, get_attacks_by_difficulty,
        DVDAttackTactic, DVDAttackDifficulty
    )
    from dvd_lite.cti.simple_cti import SimpleCTI
    from dvd_lite.main import DVDLite
except ImportError as e:
    print(f"Import error: {e}")
    print("Please ensure all required modules are properly installed.")
    sys.exit(1)

# 공격 실행 모드
class ExecutionMode(Enum):
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    RANDOM = "random"
    PRIORITY = "priority"

# 지도학습 레이블
class SupervisedLabel(Enum):
    ATTACK_SUCCESS = "attack_success"
    ATTACK_FAILURE = "attack_failure"
    DETECTION_SUCCESS = "detection_success"
    DETECTION_FAILURE = "detection_failure"
    MTD_EFFECTIVE = "mtd_effective"
    MTD_INEFFECTIVE = "mtd_ineffective"

@dataclass
class AttackExecutionResult:
    """개별 공격 실행 결과"""
    attack_name: str
    attack_type: str
    tactic: str
    difficulty: str
    success: bool
    duration: float
    iocs_generated: int
    detection_triggered: bool
    mtd_activated: bool
    error_message: Optional[str] = None
    detailed_logs: Optional[str] = None
    
@dataclass
class SupervisedLearningData:
    """지도학습을 위한 레이블된 데이터"""
    timestamp: str
    attack_vector: str
    network_features: Dict[str, Any]
    attack_features: Dict[str, Any]
    mtd_features: Dict[str, Any]
    label: str
    confidence: float
    metadata: Dict[str, Any]

class AttackOrchestrator:
    """전체 공격 시나리오를 관리하고 실행하는 메인 클래스"""
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.setup_logging()
        self.setup_directories()
        
        # CTI 수집기 초기화
        self.cti_collector = SimpleCTI({
            "confidence_threshold": 70,
            "export_format": "json"
        })
        
        # DVD-Lite 인스턴스 초기화
        self.dvd_lite = DVDLite()
        self.dvd_lite.register_cti_collector(self.cti_collector)
        
        # 실행 결과 저장
        self.execution_results: List[AttackExecutionResult] = []
        self.supervised_data: List[SupervisedLearningData] = []
        
        # 공격 스크립트 경로 매핑
        self.attack_scripts = self._build_attack_script_mapping()
        
    def setup_logging(self):
        """로깅 설정"""
        log_dir = PROJECT_ROOT / "logs" / "orchestrator"
        log_dir.mkdir(parents=True, exist_ok=True)
        
        log_file = log_dir / f"attack_orchestrator_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler(sys.stdout)
            ]
        )
        
        self.logger = logging.getLogger("AttackOrchestrator")
        self.log_file = log_file
        
    def setup_directories(self):
        """필요한 디렉토리 구조 생성"""
        dirs = [
            "attack_logs", "attack_output", "supervised_data",
            "cti_reports", "visualization", "firmware_analysis"
        ]
        
        for dir_name in dirs:
            (PROJECT_ROOT / dir_name).mkdir(parents=True, exist_ok=True)
            
        # 하위 카테고리 디렉토리
        attack_categories = [
            "reconnaissance", "protocol_tampering", "denial_of_service",
            "injection", "exfiltration", "firmware_attacks"
        ]
        
        for category in attack_categories:
            (PROJECT_ROOT / "attack_logs" / category).mkdir(parents=True, exist_ok=True)
            (PROJECT_ROOT / "attack_output" / category).mkdir(parents=True, exist_ok=True)
    
    def _build_attack_script_mapping(self) -> Dict[str, str]:
        """공격 이름과 스크립트 경로 매핑 생성"""
        attack_base_dir = PROJECT_ROOT / "dvd_lite" / "dvd_attacks"
        
        mapping = {
            # Reconnaissance
            "wifi_network_discovery": str(attack_base_dir / "reconnaissance" / "wifi_network_discovery.sh"),
            "mavlink_discovery": str(attack_base_dir / "reconnaissance" / "mavlink_discovery.sh"),
            "drone_fingerprinting": str(attack_base_dir / "reconnaissance" / "drone_fingerprinting.sh"),
            
            # Protocol Tampering
            "gps_spoofing": str(attack_base_dir / "protocol_tampering" / "gps_spoofing.sh"),
            "mavlink_injection": str(attack_base_dir / "protocol_tampering" / "mavlink_injection.sh"),
            "rf_jamming": str(attack_base_dir / "protocol_tampering" / "rf_jamming.sh"),
            
            # Denial of Service
            "mavlink_flood": str(attack_base_dir / "denial_of_service" / "mavlink_flood.sh"),
            "wifi_deauth": str(attack_base_dir / "denial_of_service" / "wifi_deauth.sh"),
            "resource_exhaustion": str(attack_base_dir / "denial_of_service" / "resource_exhaustion.sh"),
            
            # Injection
            "flight_plan_injection": str(attack_base_dir / "injection" / "flight_plan_injection.sh"),
            "parameter_manipulation": str(attack_base_dir / "injection" / "parameter_manipulation.sh"),
            "firmware_upload_manipulation": str(attack_base_dir / "injection" / "firmware_upload_manipulation.sh"),
            
            # Exfiltration
            "telemetry_exfiltration": str(attack_base_dir / "exfiltration" / "telemetry_exfiltration.sh"),
            "flight_log_extraction": str(attack_base_dir / "exfiltration" / "flight_log_extraction.sh"),
            "video_stream_hijacking": str(attack_base_dir / "exfiltration" / "video_stream_hijacking.sh"),
            
            # Firmware Attacks
            "bootloader_exploit": str(attack_base_dir / "firmware_attacks" / "bootloader_exploit.sh"),
            "firmware_rollback": str(attack_base_dir / "firmware_attacks" / "firmware_rollback.sh"),
            "secure_boot_bypass": str(attack_base_dir / "firmware_attacks" / "secure_boot_bypass.sh"),
        }
        
        return mapping
    
    async def execute_single_attack(self, attack_name: str) -> AttackExecutionResult:
        """단일 공격 실행"""
        self.logger.info(f"Executing attack: {attack_name}")
        
        start_time = time.time()
        script_path = self.attack_scripts.get(attack_name)
        
        if not script_path:
            error_msg = f"Attack script not found: {attack_name}"
            return AttackExecutionResult(
                attack_name=attack_name,
                attack_type="UNKNOWN",
                tactic="UNKNOWN",
                difficulty="UNKNOWN",
                success=False,
                duration=0.0,
                iocs_generated=0,
                detection_triggered=False,
                mtd_activated=False,
                error_message=error_msg
            )
        
        if not os.path.exists(script_path):
            error_msg = f"Script file does not exist: {script_path}"
            return AttackExecutionResult(
                attack_name=attack_name,
                attack_type="UNKNOWN",
                tactic="UNKNOWN",
                difficulty="UNKNOWN",
                success=False,
                duration=0.0,
                iocs_generated=0,
                detection_triggered=False,
                mtd_activated=False,
                error_message=error_msg
            )
        
        try:
            # 스크립트 실행 권한 확인
            os.chmod(script_path, 0o755)
            
            # 공격 스크립트 실행
            process = subprocess.run(
                ["bash", script_path],
                capture_output=True,
                text=True,
                timeout=300  # 5분 타임아웃
            )
            
            duration = time.time() - start_time
            
            # 실행 결과 분석
            success = process.returncode == 0
            output = process.stdout + process.stderr
            
            # IOC 파일에서 지표 수 계산
            ioc_count = self._count_iocs_from_output(output)
            
            # 탐지 및 MTD 활성화 여부 확인
            detection_triggered = "DETECTION:" in output or "ANOMALY:" in output
            mtd_activated = "MTD:" in output or "MITIGATION:" in output
            
            # 공격 정보 추출
            attack_info = self._extract_attack_info(attack_name, output)
            
            result = AttackExecutionResult(
                attack_name=attack_name,
                attack_type=attack_info.get("type", "UNKNOWN"),
                tactic=attack_info.get("tactic", "UNKNOWN"),
                difficulty=attack_info.get("difficulty", "UNKNOWN"),
                success=success,
                duration=duration,
                iocs_generated=ioc_count,
                detection_triggered=detection_triggered,
                mtd_activated=mtd_activated,
                detailed_logs=output
            )
            
            # 지도학습 데이터 생성
            await self._generate_supervised_data(result, output)
            
            return result
            
        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            error_msg = f"Attack script timeout after 300 seconds"
            
            return AttackExecutionResult(
                attack_name=attack_name,
                attack_type="UNKNOWN",
                tactic="UNKNOWN", 
                difficulty="UNKNOWN",
                success=False,
                duration=duration,
                iocs_generated=0,
                detection_triggered=False,
                mtd_activated=False,
                error_message=error_msg
            )
            
        except Exception as e:
            duration = time.time() - start_time
            error_msg = f"Attack execution error: {str(e)}"
            
            return AttackExecutionResult(
                attack_name=attack_name,
                attack_type="UNKNOWN",
                tactic="UNKNOWN",
                difficulty="UNKNOWN", 
                success=False,
                duration=duration,
                iocs_generated=0,
                detection_triggered=False,
                mtd_activated=False,
                error_message=error_msg
            )
    
    def _count_iocs_from_output(self, output: str) -> int:
        """출력에서 IOC 수 계산"""
        ioc_indicators = [
            "IOC:", "INDICATOR:", "THREAT:", "MALWARE:", "EXPLOIT:",
            "VULNERABILITY:", "BACKDOOR:", "C2_SERVER:", "ATTACK_VECTOR:"
        ]
        
        count = 0
        for line in output.split('\n'):
            for indicator in ioc_indicators:
                if indicator in line:
                    count += 1
                    break
                    
        return count
    
    def _extract_attack_info(self, attack_name: str, output: str) -> Dict[str, str]:
        """공격 출력에서 메타정보 추출"""
        info = {
            "type": "UNKNOWN",
            "tactic": "UNKNOWN", 
            "difficulty": "UNKNOWN"
        }
        
        # 출력에서 공격 타입 추출
        if "RECONNAISSANCE" in output:
            info["tactic"] = "RECONNAISSANCE"
        elif "PROTOCOL_TAMPERING" in output:
            info["tactic"] = "PROTOCOL_TAMPERING"
        elif "DENIAL_OF_SERVICE" in output:
            info["tactic"] = "DENIAL_OF_SERVICE"
        elif "INJECTION" in output:
            info["tactic"] = "INJECTION"
        elif "EXFILTRATION" in output:
            info["tactic"] = "EXFILTRATION"
        elif "FIRMWARE_ATTACKS" in output:
            info["tactic"] = "FIRMWARE_ATTACKS"
        
        # 공격 이름 기반 정보 매핑
        attack_mapping = {
            # Reconnaissance
            "wifi_network_discovery": {"type": "NETWORK_SCAN", "tactic": "RECONNAISSANCE", "difficulty": "BEGINNER"},
            "mavlink_discovery": {"type": "PROTOCOL_SCAN", "tactic": "RECONNAISSANCE", "difficulty": "BEGINNER"},
            "drone_fingerprinting": {"type": "DEVICE_ENUM", "tactic": "RECONNAISSANCE", "difficulty": "INTERMEDIATE"},
            
            # Protocol Tampering  
            "gps_spoofing": {"type": "SIGNAL_SPOOF", "tactic": "PROTOCOL_TAMPERING", "difficulty": "ADVANCED"},
            "mavlink_injection": {"type": "PACKET_INJECT", "tactic": "PROTOCOL_TAMPERING", "difficulty": "INTERMEDIATE"},
            "rf_jamming": {"type": "RF_ATTACK", "tactic": "PROTOCOL_TAMPERING", "difficulty": "ADVANCED"},
            
            # Denial of Service
            "mavlink_flood": {"type": "FLOOD_ATTACK", "tactic": "DENIAL_OF_SERVICE", "difficulty": "INTERMEDIATE"},
            "wifi_deauth": {"type": "DEAUTH_ATTACK", "tactic": "DENIAL_OF_SERVICE", "difficulty": "BEGINNER"},
            "resource_exhaustion": {"type": "RESOURCE_ATTACK", "tactic": "DENIAL_OF_SERVICE", "difficulty": "INTERMEDIATE"},
            
            # Injection
            "flight_plan_injection": {"type": "WAYPOINT_INJECT", "tactic": "INJECTION", "difficulty": "ADVANCED"},
            "parameter_manipulation": {"type": "PARAM_INJECT", "tactic": "INJECTION", "difficulty": "INTERMEDIATE"},
            "firmware_upload_manipulation": {"type": "FIRMWARE_INJECT", "tactic": "INJECTION", "difficulty": "ADVANCED"},
            
            # Exfiltration
            "telemetry_exfiltration": {"type": "DATA_EXFIL", "tactic": "EXFILTRATION", "difficulty": "INTERMEDIATE"},
            "flight_log_extraction": {"type": "LOG_EXFIL", "tactic": "EXFILTRATION", "difficulty": "BEGINNER"},
            "video_stream_hijacking": {"type": "STREAM_HIJACK", "tactic": "EXFILTRATION", "difficulty": "ADVANCED"},
            
            # Firmware Attacks
            "bootloader_exploit": {"type": "BOOTLOADER_EXPLOIT", "tactic": "FIRMWARE_ATTACKS", "difficulty": "ADVANCED"},
            "firmware_rollback": {"type": "FIRMWARE_ROLLBACK", "tactic": "FIRMWARE_ATTACKS", "difficulty": "ADVANCED"},
            "secure_boot_bypass": {"type": "SECURE_BOOT_BYPASS", "tactic": "FIRMWARE_ATTACKS", "difficulty": "ADVANCED"},
        }
        
        if attack_name in attack_mapping:
            info.update(attack_mapping[attack_name])
            
        return info
    
    async def _generate_supervised_data(self, result: AttackExecutionResult, output: str):
        """지도학습 데이터 생성"""
        timestamp = datetime.now().isoformat()
        
        # 네트워크 특성 추출
        network_features = self._extract_network_features(output)
        
        # 공격 특성 추출  
        attack_features = self._extract_attack_features(result, output)
        
        # MTD 특성 추출
        mtd_features = self._extract_mtd_features(output)
        
        # 레이블 결정
        labels = self._determine_labels(result, output)
        
        # 각 레이블에 대해 지도학습 데이터 생성
        for label, confidence in labels.items():
            supervised_data = SupervisedLearningData(
                timestamp=timestamp,
                attack_vector=result.attack_name,
                network_features=network_features,
                attack_features=attack_features,
                mtd_features=mtd_features,
                label=label,
                confidence=confidence,
                metadata={
                    "attack_success": result.success,
                    "duration": result.duration,
                    "iocs_count": result.iocs_generated,
                    "tactic": result.tactic,
                    "difficulty": result.difficulty
                }
            )
            
            self.supervised_data.append(supervised_data)
    
    def _extract_network_features(self, output: str) -> Dict[str, Any]:
        """네트워크 특성 추출"""
        features = {
            "packet_count": 0,
            "connection_attempts": 0,
            "unique_ips": 0,
            "port_scans": 0,
            "protocol_violations": 0,
            "bandwidth_usage": 0.0,
            "latency_avg": 0.0,
            "connection_duration": 0.0
        }
        
        # 출력에서 네트워크 지표 추출
        for line in output.split('\n'):
            if "packets sent:" in line.lower():
                try:
                    features["packet_count"] = int(line.split(':')[1].strip())
                except:
                    pass
            elif "connection attempts:" in line.lower():
                try:
                    features["connection_attempts"] = int(line.split(':')[1].strip())
                except:
                    pass
            elif "unique ips:" in line.lower():
                try:
                    features["unique_ips"] = int(line.split(':')[1].strip())
                except:
                    pass
        
        return features
    
    def _extract_attack_features(self, result: AttackExecutionResult, output: str) -> Dict[str, Any]:
        """공격 특성 추출"""
        features = {
            "attack_complexity": self._calculate_complexity(result.difficulty),
            "payload_size": 0,
            "exploit_attempts": 0,
            "stealth_level": 0.0,
            "persistence_mechanisms": 0,
            "privilege_escalation": False,
            "lateral_movement": False,
            "data_destruction": False
        }
        
        # 난이도 기반 복잡도 계산
        difficulty_mapping = {
            "BEGINNER": 1,
            "INTERMEDIATE": 2, 
            "ADVANCED": 3
        }
        features["attack_complexity"] = difficulty_mapping.get(result.difficulty, 1)
        
        # 출력에서 공격 특성 추출
        for line in output.split('\n'):
            if "payload size:" in line.lower():
                try:
                    features["payload_size"] = int(line.split(':')[1].strip().replace('bytes', '').strip())
                except:
                    pass
            elif "exploit attempts:" in line.lower():
                try:
                    features["exploit_attempts"] = int(line.split(':')[1].strip())
                except:
                    pass
            elif "stealth mode" in line.lower():
                features["stealth_level"] = 0.8
            elif "persistence" in line.lower():
                features["persistence_mechanisms"] += 1
            elif "privilege escalation" in line.lower():
                features["privilege_escalation"] = True
        
        return features
    
    def _extract_mtd_features(self, output: str) -> Dict[str, Any]:
        """MTD 특성 추출"""
        features = {
            "mtd_triggers": 0,
            "topology_changes": 0,
            "encryption_rotations": 0,
            "frequency_hops": 0,
            "emergency_responses": 0,
            "response_time": 0.0,
            "effectiveness_score": 0.0
        }
        
        # 출력에서 MTD 지표 추출
        mtd_keywords = {
            "topology_change": "topology_changes",
            "encryption_rotate": "encryption_rotations", 
            "frequency_hop": "frequency_hops",
            "emergency_response": "emergency_responses"
        }
        
        for line in output.split('\n'):
            for keyword, feature in mtd_keywords.items():
                if keyword in line.lower():
                    features[feature] += 1
                    features["mtd_triggers"] += 1
            
            if "mtd response time:" in line.lower():
                try:
                    features["response_time"] = float(line.split(':')[1].strip().replace('ms', '').strip())
                except:
                    pass
        
        # 효율성 점수 계산
        if features["mtd_triggers"] > 0:
            features["effectiveness_score"] = min(1.0, features["mtd_triggers"] / 10.0)
        
        return features
    
    def _determine_labels(self, result: AttackExecutionResult, output: str) -> Dict[str, float]:
        """지도학습 레이블 결정"""
        labels = {}
        
        # 공격 성공/실패 레이블
        if result.success:
            labels[SupervisedLabel.ATTACK_SUCCESS.value] = 0.95
            labels[SupervisedLabel.ATTACK_FAILURE.value] = 0.05
        else:
            labels[SupervisedLabel.ATTACK_SUCCESS.value] = 0.05
            labels[SupervisedLabel.ATTACK_FAILURE.value] = 0.95
        
        # 탐지 성공/실패 레이블
        if result.detection_triggered:
            labels[SupervisedLabel.DETECTION_SUCCESS.value] = 0.90
            labels[SupervisedLabel.DETECTION_FAILURE.value] = 0.10
        else:
            labels[SupervisedLabel.DETECTION_SUCCESS.value] = 0.10
            labels[SupervisedLabel.DETECTION_FAILURE.value] = 0.90
        
        # MTD 효과성 레이블
        if result.mtd_activated and not result.success:
            labels[SupervisedLabel.MTD_EFFECTIVE.value] = 0.85
            labels[SupervisedLabel.MTD_INEFFECTIVE.value] = 0.15
        elif result.mtd_activated and result.success:
            labels[SupervisedLabel.MTD_EFFECTIVE.value] = 0.30
            labels[SupervisedLabel.MTD_INEFFECTIVE.value] = 0.70
        else:
            labels[SupervisedLabel.MTD_EFFECTIVE.value] = 0.50
            labels[SupervisedLabel.MTD_INEFFECTIVE.value] = 0.50
        
        return labels
    
    def _calculate_complexity(self, difficulty: str) -> int:
        """공격 복잡도 계산"""
        mapping = {
            "BEGINNER": 1,
            "INTERMEDIATE": 2,
            "ADVANCED": 3
        }
        return mapping.get(difficulty, 1)
    
    async def run_sequential_attacks(self, attack_list: List[str]) -> List[AttackExecutionResult]:
        """순차적 공격 실행"""
        self.logger.info(f"Starting sequential execution of {len(attack_list)} attacks")
        
        results = []
        for i, attack_name in enumerate(attack_list, 1):
            self.logger.info(f"[{i}/{len(attack_list)}] Executing: {attack_name}")
            
            result = await self.execute_single_attack(attack_name)
            results.append(result)
            self.execution_results.append(result)
            
            # 공격 간 간격 (MTD 적응 시간 고려)
            await asyncio.sleep(self.config.get("attack_interval", 5))
            
            # 중간 결과 출력
            status = "✓ SUCCESS" if result.success else "✗ FAILED"
            self.logger.info(f"  Result: {status} (Duration: {result.duration:.2f}s)")
            
        return results
    
    async def run_parallel_attacks(self, attack_list: List[str], max_concurrent: int = 3) -> List[AttackExecutionResult]:
        """병렬 공격 실행"""
        self.logger.info(f"Starting parallel execution of {len(attack_list)} attacks (max_concurrent: {max_concurrent})")
        
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def execute_with_semaphore(attack_name: str) -> AttackExecutionResult:
            async with semaphore:
                return await self.execute_single_attack(attack_name)
        
        # 모든 공격을 동시에 시작
        tasks = [execute_with_semaphore(attack) for attack in attack_list]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 예외 처리
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                error_result = AttackExecutionResult(
                    attack_name=attack_list[i],
                    attack_type="UNKNOWN",
                    tactic="UNKNOWN",
                    difficulty="UNKNOWN",
                    success=False,
                    duration=0.0,
                    iocs_generated=0,
                    detection_triggered=False,
                    mtd_activated=False,
                    error_message=str(result)
                )
                processed_results.append(error_result)
            else:
                processed_results.append(result)
                
        self.execution_results.extend(processed_results)
        return processed_results
    
    async def run_priority_attacks(self, attack_list: List[str]) -> List[AttackExecutionResult]:
        """우선순위 기반 공격 실행"""
        self.logger.info("Starting priority-based attack execution")
        
        # 공격 우선순위 정의
        priority_mapping = {
            # 1순위: 정찰 (기반 정보 수집)
            "wifi_network_discovery": 1,
            "mavlink_discovery": 1,
            "drone_fingerprinting": 1,
            
            # 2순위: 프로토콜 조작 (시스템 이해 후)
            "gps_spoofing": 2,
            "mavlink_injection": 2,
            "rf_jamming": 2,
            
            # 3순위: 서비스 거부 (시스템 무력화)
            "mavlink_flood": 3,
            "wifi_deauth": 3,
            "resource_exhaustion": 3,
            
            # 4순위: 주입 공격 (시스템 조작)
            "flight_plan_injection": 4,
            "parameter_manipulation": 4,
            "firmware_upload_manipulation": 4,
            
            # 5순위: 데이터 탈취 (정보 수집)
            "telemetry_exfiltration": 5,
            "flight_log_extraction": 5,
            "video_stream_hijacking": 5,
            
            # 6순위: 펌웨어 공격 (완전 장악)
            "bootloader_exploit": 6,
            "firmware_rollback": 6,
            "secure_boot_bypass": 6,
        }
        
        # 우선순위로 정렬
        sorted_attacks = sorted(attack_list, key=lambda x: priority_mapping.get(x, 999))
        
        self.logger.info("Attack execution order:")
        for i, attack in enumerate(sorted_attacks, 1):
            priority = priority_mapping.get(attack, 999)
            self.logger.info(f"  {i}. {attack} (Priority: {priority})")
        
        # 우선순위 단계별 실행
        results = []
        current_priority = 0
        
        for attack_name in sorted_attacks:
            attack_priority = priority_mapping.get(attack_name, 999)
            
            # 새 우선순위 단계 시작
            if attack_priority != current_priority:
                if current_priority > 0:  # 첫 번째 단계가 아니면 대기
                    self.logger.info(f"Waiting before next priority level...")
                    await asyncio.sleep(10)  # 단계 간 대기
                
                current_priority = attack_priority
                self.logger.info(f"Starting Priority Level {current_priority}")
            
            result = await self.execute_single_attack(attack_name)
            results.append(result)
            self.execution_results.append(result)
            
            # 실패한 정찰 공격이 있으면 나머지 공격 중단
            if current_priority == 1 and not result.success:
                self.logger.warning(f"Critical reconnaissance attack failed: {attack_name}")
                self.logger.warning("Aborting remaining attacks due to reconnaissance failure")
                break
        
        return results
    
    async def run_all_attacks(self, mode: ExecutionMode = ExecutionMode.SEQUENTIAL) -> Dict[str, Any]:
        """모든 공격 실행"""
        self.logger.info(f"Starting comprehensive attack suite in {mode.value} mode")
        
        # 모든 등록된 공격 가져오기
        all_attacks = list(self.attack_scripts.keys())
        
        start_time = time.time()
        
        if mode == ExecutionMode.SEQUENTIAL:
            results = await self.run_sequential_attacks(all_attacks)
        elif mode == ExecutionMode.PARALLEL:
            results = await self.run_parallel_attacks(all_attacks, max_concurrent=3)
        elif mode == ExecutionMode.PRIORITY:
            results = await self.run_priority_attacks(all_attacks)
        elif mode == ExecutionMode.RANDOM:
            import random
            random.shuffle(all_attacks)
            results = await self.run_sequential_attacks(all_attacks)
        else:
            results = await self.run_sequential_attacks(all_attacks)
        
        total_duration = time.time() - start_time
        
        # 결과 요약
        summary = self._generate_execution_summary(results, total_duration)
        
        # 지도학습 데이터 저장
        await self._save_supervised_data()
        
        # CTI 데이터 저장
        await self._save_cti_data()
        
        return summary
    
    async def run_tactic_based_attacks(self, tactic: DVDAttackTactic) -> Dict[str, Any]:
        """전술별 공격 실행"""
        self.logger.info(f"Starting {tactic.value} attacks")
        
        # 해당 전술의 공격들 필터링
        tactic_attacks = []
        tactic_mapping = {
            DVDAttackTactic.RECONNAISSANCE: ["wifi_network_discovery", "mavlink_discovery", "drone_fingerprinting"],
            DVDAttackTactic.PROTOCOL_TAMPERING: ["gps_spoofing", "mavlink_injection", "rf_jamming"],
            DVDAttackTactic.DENIAL_OF_SERVICE: ["mavlink_flood", "wifi_deauth", "resource_exhaustion"],
            DVDAttackTactic.INJECTION: ["flight_plan_injection", "parameter_manipulation", "firmware_upload_manipulation"],
            DVDAttackTactic.EXFILTRATION: ["telemetry_exfiltration", "flight_log_extraction", "video_stream_hijacking"],
            DVDAttackTactic.FIRMWARE_ATTACKS: ["bootloader_exploit", "firmware_rollback", "secure_boot_bypass"]
        }
        
        tactic_attacks = tactic_mapping.get(tactic, [])
        
        if not tactic_attacks:
            self.logger.warning(f"No attacks found for tactic: {tactic.value}")
            return {"error": "No attacks found for specified tactic"}
        
        start_time = time.time()
        results = await self.run_sequential_attacks(tactic_attacks)
        total_duration = time.time() - start_time
        
        return self._generate_execution_summary(results, total_duration, f"{tactic.value} Attacks")
    
    async def run_difficulty_based_attacks(self, difficulty: DVDAttackDifficulty) -> Dict[str, Any]:
        """난이도별 공격 실행"""
        self.logger.info(f"Starting {difficulty.value} difficulty attacks")
        
        # 난이도별 공격 매핑
        difficulty_mapping = {
            DVDAttackDifficulty.BEGINNER: [
                "wifi_network_discovery", "mavlink_discovery", "wifi_deauth", "flight_log_extraction"
            ],
            DVDAttackDifficulty.INTERMEDIATE: [
                "drone_fingerprinting", "mavlink_injection", "mavlink_flood", 
                "parameter_manipulation", "telemetry_exfiltration", "resource_exhaustion"
            ],
            DVDAttackDifficulty.ADVANCED: [
                "gps_spoofing", "rf_jamming", "flight_plan_injection", 
                "firmware_upload_manipulation", "video_stream_hijacking",
                "bootloader_exploit", "firmware_rollback", "secure_boot_bypass"
            ]
        }
        
        difficulty_attacks = difficulty_mapping.get(difficulty, [])
        
        if not difficulty_attacks:
            self.logger.warning(f"No attacks found for difficulty: {difficulty.value}")
            return {"error": "No attacks found for specified difficulty"}
        
        start_time = time.time()
        results = await self.run_sequential_attacks(difficulty_attacks)
        total_duration = time.time() - start_time
        
        return self._generate_execution_summary(results, total_duration, f"{difficulty.value} Difficulty Attacks")
    
    def _generate_execution_summary(self, results: List[AttackExecutionResult], 
                                  total_duration: float, title: str = "Attack Execution") -> Dict[str, Any]:
        """실행 결과 요약 생성"""
        
        # 기본 통계
        total_attacks = len(results)
        successful_attacks = sum(1 for r in results if r.success)
        success_rate = (successful_attacks / total_attacks) * 100 if total_attacks > 0 else 0
        
        # 전술별 통계
        tactic_stats = {}
        for result in results:
            tactic = result.tactic
            if tactic not in tactic_stats:
                tactic_stats[tactic] = {"total": 0, "success": 0}
            tactic_stats[tactic]["total"] += 1
            if result.success:
                tactic_stats[tactic]["success"] += 1
        
        # 난이도별 통계
        difficulty_stats = {}
        for result in results:
            difficulty = result.difficulty
            if difficulty not in difficulty_stats:
                difficulty_stats[difficulty] = {"total": 0, "success": 0}
            difficulty_stats[difficulty]["total"] += 1
            if result.success:
                difficulty_stats[difficulty]["success"] += 1
        
        # 탐지 및 MTD 통계
        detection_triggered = sum(1 for r in results if r.detection_triggered)
        mtd_activated = sum(1 for r in results if r.mtd_activated)
        total_iocs = sum(r.iocs_generated for r in results)
        
        # 평균 실행 시간
        avg_duration = sum(r.duration for r in results) / total_attacks if total_attacks > 0 else 0
        
        summary = {
            "execution_info": {
                "title": title,
                "timestamp": datetime.now().isoformat(),
                "total_duration": total_duration,
                "average_attack_duration": avg_duration
            },
            "attack_statistics": {
                "total_attacks": total_attacks,
                "successful_attacks": successful_attacks,
                "success_rate": success_rate,
                "failed_attacks": total_attacks - successful_attacks
            },
            "tactic_breakdown": {
                tactic: {
                    **stats,
                    "success_rate": (stats["success"] / stats["total"]) * 100 if stats["total"] > 0 else 0
                }
                for tactic, stats in tactic_stats.items()
            },
            "difficulty_breakdown": {
                difficulty: {
                    **stats,
                    "success_rate": (stats["success"] / stats["total"]) * 100 if stats["total"] > 0 else 0
                }
                for difficulty, stats in difficulty_stats.items()
            },
            "defense_statistics": {
                "detection_triggered": detection_triggered,
                "detection_rate": (detection_triggered / total_attacks) * 100 if total_attacks > 0 else 0,
                "mtd_activated": mtd_activated,
                "mtd_activation_rate": (mtd_activated / total_attacks) * 100 if total_attacks > 0 else 0,
                "total_iocs_generated": total_iocs
            },
            "detailed_results": [asdict(result) for result in results]
        }
        
        return summary
    
    async def _save_supervised_data(self):
        """지도학습 데이터 저장"""
        if not self.supervised_data:
            return
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # JSON 형식으로 저장
        json_file = PROJECT_ROOT / "supervised_data" / f"supervised_learning_data_{timestamp}.json"
        
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump([asdict(data) for data in self.supervised_data], f, indent=2, ensure_ascii=False)
        
        # CSV 형식으로도 저장 (ML 도구와의 호환성)
        csv_file = PROJECT_ROOT / "supervised_data" / f"supervised_features_{timestamp}.csv"
        
        import pandas as pd
        
        # 특성 데이터를 평면화
        flattened_data = []
        for data in self.supervised_data:
            row = {
                "timestamp": data.timestamp,
                "attack_vector": data.attack_vector,
                "label": data.label,
                "confidence": data.confidence
            }
            
            # 특성들을 평면화하여 추가
            for feature_type in ["network_features", "attack_features", "mtd_features"]:
                features = getattr(data, feature_type)
                for key, value in features.items():
                    row[f"{feature_type}_{key}"] = value
            
            # 메타데이터 추가
            for key, value in data.metadata.items():
                row[f"meta_{key}"] = value
                
            flattened_data.append(row)
        
        df = pd.DataFrame(flattened_data)
        df.to_csv(csv_file, index=False)
        
        self.logger.info(f"Supervised learning data saved:")
        self.logger.info(f"  JSON: {json_file}")
        self.logger.info(f"  CSV: {csv_file}")
        self.logger.info(f"  Records: {len(self.supervised_data)}")
    
    async def _save_cti_data(self):
        """CTI 데이터 저장"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # CTI JSON 내보내기
        cti_json = PROJECT_ROOT / "cti_reports" / f"cti_indicators_{timestamp}.json"
        self.cti_collector.export_json(str(cti_json))
        
        # CTI CSV 내보내기
        cti_csv = PROJECT_ROOT / "cti_reports" / f"cti_indicators_{timestamp}.csv"
        self.cti_collector.export_csv(str(cti_csv))
        
        self.logger.info(f"CTI data exported:")
        self.logger.info(f"  JSON: {cti_json}")
        self.logger.info(f"  CSV: {cti_csv}")
    
    def generate_training_dataset(self, output_file: Optional[str] = None) -> str:
        """지도학습용 훈련 데이터셋 생성"""
        if output_file is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = str(PROJECT_ROOT / "supervised_data" / f"training_dataset_{timestamp}.json")
        
        # 특성 벡터와 레이블 분리
        features = []
        labels = []
        
        for data in self.supervised_data:
            # 모든 특성을 하나의 벡터로 결합
            feature_vector = {
                **data.network_features,
                **data.attack_features,
                **data.mtd_features,
                "attack_vector_encoded": hash(data.attack_vector) % 1000  # 공격 벡터 인코딩
            }
            
            features.append(feature_vector)
            labels.append({
                "label": data.label,
                "confidence": data.confidence,
                "timestamp": data.timestamp
            })
        
        # 훈련 데이터셋 구성
        dataset = {
            "metadata": {
                "created_at": datetime.now().isoformat(),
                "total_samples": len(features),
                "feature_dimensions": len(features[0]) if features else 0,
                "label_types": list(set(label["label"] for label in labels)),
                "source": "DVD_MTD_Testbed"
            },
            "features": features,
            "labels": labels,
            "statistics": self._calculate_dataset_statistics(features, labels)
        }
        
        # 파일 저장
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(dataset, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"Training dataset generated: {output_file}")
        self.logger.info(f"  Samples: {len(features)}")
        self.logger.info(f"  Features: {len(features[0]) if features else 0}")
        self.logger.info(f"  Labels: {len(set(label['label'] for label in labels))}")
        
        return output_file
    
    def _calculate_dataset_statistics(self, features: List[Dict], labels: List[Dict]) -> Dict[str, Any]:
        """데이터셋 통계 계산"""
        if not features or not labels:
            return {}
        
        # 레이블 분포
        label_counts = {}
        for label in labels:
            label_type = label["label"]
            label_counts[label_type] = label_counts.get(label_type, 0) + 1
        
        # 특성 통계 (수치형 특성만)
        numeric_features = {}
        for feature_dict in features:
            for key, value in feature_dict.items():
                if isinstance(value, (int, float)):
                    if key not in numeric_features:
                        numeric_features[key] = []
                    numeric_features[key].append(value)
        
        feature_stats = {}
        for key, values in numeric_features.items():
            feature_stats[key] = {
                "mean": sum(values) / len(values),
                "min": min(values),
                "max": max(values),
                "std": (sum((x - sum(values)/len(values))**2 for x in values) / len(values))**0.5
            }
        
        return {
            "label_distribution": label_counts,
            "feature_statistics": feature_stats,
            "data_quality": {
                "completeness": sum(1 for f in features if all(v is not None for v in f.values())) / len(features),
                "label_balance": min(label_counts.values()) / max(label_counts.values()) if label_counts else 0
            }
        }
    
    def print_execution_summary(self, summary: Dict[str, Any]):
        """실행 결과 요약 출력"""
        print("\n" + "="*80)
        print(f"🎯 {summary['execution_info']['title']} 결과 요약")
        print("="*80)
        
        # 기본 통계
        stats = summary["attack_statistics"]
        print(f"\n📊 공격 통계:")
        print(f"  • 총 공격 수행: {stats['total_attacks']}회")
        print(f"  • 성공한 공격: {stats['successful_attacks']}회")
        print(f"  • 전체 성공률: {stats['success_rate']:.1f}%")
        print(f"  • 실행 시간: {summary['execution_info']['total_duration']:.1f}초")
        
        # 전술별 결과
        print(f"\n🎯 전술별 성공률:")
        for tactic, tactic_stats in summary["tactic_breakdown"].items():
            print(f"  • {tactic}: {tactic_stats['success_rate']:.1f}% ({tactic_stats['success']}/{tactic_stats['total']})")
        
        # 난이도별 결과
        print(f"\n📈 난이도별 성공률:")
        for difficulty, diff_stats in summary["difficulty_breakdown"].items():
            print(f"  • {difficulty}: {diff_stats['success_rate']:.1f}% ({diff_stats['success']}/{diff_stats['total']})")
        
        # 방어 통계
        defense = summary["defense_statistics"]
        print(f"\n🛡️ 방어 시스템 성능:")
        print(f"  • 탐지율: {defense['detection_rate']:.1f}% ({defense['detection_triggered']}회)")
        print(f"  • MTD 활성화율: {defense['mtd_activation_rate']:.1f}% ({defense['mtd_activated']}회)")
        print(f"  • 생성된 IOC: {defense['total_iocs_generated']}개")
        
        # 지도학습 데이터
        print(f"\n🤖 지도학습 데이터:")
        print(f"  • 레이블된 샘플: {len(self.supervised_data)}개")
        print(f"  • 특성 차원: {len(self.supervised_data[0].network_features) + len(self.supervised_data[0].attack_features) + len(self.supervised_data[0].mtd_features) if self.supervised_data else 0}개")
        
        print("\n" + "="*80)

async def main():
    """메인 실행 함수"""
    
    print("🚀 DVD MTD 테스트베드 - 공격 오케스트레이터")
    print("="*60)
    
    # 설정
    config = {
        "attack_interval": 3,  # 공격 간 간격 (초)
        "max_concurrent": 2,   # 최대 동시 실행 수
        "enable_logging": True,
        "generate_reports": True
    }
    
    # 오케스트레이터 초기화
    orchestrator = AttackOrchestrator(config)
    
    # 실행 모드 선택
    print("\n실행 모드를 선택하세요:")
    print("1. 전체 공격 순차 실행 (Sequential)")
    print("2. 전체 공격 병렬 실행 (Parallel)")
    print("3. 우선순위 기반 실행 (Priority)")
    print("4. 전술별 실행 (Tactic-based)")
    print("5. 난이도별 실행 (Difficulty-based)")
    print("6. 단일 공격 실행 (Single)")
    print("7. 지도학습 데이터셋 생성 (Supervised Learning)")
    
    try:
        choice = input("\n선택 (1-7): ").strip()
        
        if choice == "1":
            print("\n🔄 순차적 전체 공격 실행 시작...")
            summary = await orchestrator.run_all_attacks(ExecutionMode.SEQUENTIAL)
            orchestrator.print_execution_summary(summary)
            
        elif choice == "2":
            print("\n⚡ 병렬 전체 공격 실행 시작...")
            summary = await orchestrator.run_all_attacks(ExecutionMode.PARALLEL)
            orchestrator.print_execution_summary(summary)
            
        elif choice == "3":
            print("\n🎯 우선순위 기반 공격 실행 시작...")
            summary = await orchestrator.run_all_attacks(ExecutionMode.PRIORITY)
            orchestrator.print_execution_summary(summary)
            
        elif choice == "4":
            print("\n전술을 선택하세요:")
            tactics = list(DVDAttackTactic)
            for i, tactic in enumerate(tactics, 1):
                print(f"{i}. {tactic.value}")
            
            tactic_choice = int(input("선택: ")) - 1
            selected_tactic = tactics[tactic_choice]
            
            print(f"\n🎯 {selected_tactic.value} 전술 공격 실행 시작...")
            summary = await orchestrator.run_tactic_based_attacks(selected_tactic)
            orchestrator.print_execution_summary(summary)
            
        elif choice == "5":
            print("\n난이도를 선택하세요:")
            difficulties = list(DVDAttackDifficulty)
            for i, difficulty in enumerate(difficulties, 1):
                print(f"{i}. {difficulty.value}")
            
            diff_choice = int(input("선택: ")) - 1
            selected_difficulty = difficulties[diff_choice]
            
            print(f"\n📈 {selected_difficulty.value} 난이도 공격 실행 시작...")
            summary = await orchestrator.run_difficulty_based_attacks(selected_difficulty)
            orchestrator.print_execution_summary(summary)
            
        elif choice == "6":
            print("\n공격을 선택하세요:")
            attacks = list(orchestrator.attack_scripts.keys())
            for i, attack in enumerate(attacks, 1):
                print(f"{i:2d}. {attack}")
            
            attack_choice = int(input("선택: ")) - 1
            selected_attack = attacks[attack_choice]
            
            print(f"\n🎯 {selected_attack} 공격 실행 시작...")
            result = await orchestrator.execute_single_attack(selected_attack)
            
            print(f"\n결과: {'✓ 성공' if result.success else '✗ 실패'}")
            print(f"실행 시간: {result.duration:.2f}초")
            print(f"IOC 생성: {result.iocs_generated}개")
            
        elif choice == "7":
            print("\n🤖 지도학습 데이터셋 생성 시작...")
            
            # 먼저 몇 개의 공격을 실행하여 데이터 생성
            sample_attacks = ["wifi_network_discovery", "mavlink_injection", "firmware_rollback"]
            
            print("샘플 공격 실행 중...")
            for attack in sample_attacks:
                await orchestrator.execute_single_attack(attack)
            
            # 훈련 데이터셋 생성
            dataset_file = orchestrator.generate_training_dataset()
            print(f"\n✅ 훈련 데이터셋 생성 완료: {dataset_file}")
            
        else:
            print("❌ 잘못된 선택입니다.")
            
    except KeyboardInterrupt:
        print("\n\n⚠️ 사용자에 의해 중단되었습니다.")
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        orchestrator.logger.error(f"Main execution error: {e}")

if __name__ == "__main__":
    # 비동기 메인 함수 실행
    asyncio.run(main())