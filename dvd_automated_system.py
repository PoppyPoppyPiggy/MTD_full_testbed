#!/usr/bin/env python3
# dvd_automated_system.py
"""
Damn Vulnerable Drone 자동화 테스트 및 머신러닝 탐지 통합 시스템
모든 공격 시나리오 자동 실행 + 실시간 ML 기반 탐지
"""

import asyncio
import json
import logging
import argparse
import signal
import sys
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import asdict

# DVD-Lite 모듈들
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dvd_lite.main import DVDLite, AttackStatus
from dvd_lite.cti import SimpleCTI
from dvd_attacks.all_attack_scenarios import (
    register_all_dvd_attacks, 
    DVD_ATTACK_SCENARIOS,
    DVDAttackTactic,
    DVDFlightState,
    get_attacks_by_tactic,
    get_attacks_by_difficulty,
    get_attacks_by_flight_state
)
from ml_detection.attack_detector import (
    DVDMLDetectionSystem,
    AttackCategory,
    ThreatLevel
)

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('dvd_automated_system.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class DVDAutomatedTestingSystem:
    """DVD 자동화 테스트 및 탐지 통합 시스템"""
    
    def __init__(self, config_file: str = "dvd_config.json"):
        self.config = self._load_config(config_file)
        self.dvd_lite = None
        self.cti_collector = None
        self.ml_detection_system = None
        self.attack_results = []
        self.detection_results = []
        self.current_flight_state = DVDFlightState.PRE_FLIGHT
        self.is_running = False
        
        # 시그널 핸들러 등록
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _load_config(self, config_file: str) -> Dict[str, Any]:
        """설정 파일 로드"""
        default_config = {
            "target": {
                "host": "10.13.0.2",
                "mode": "simulation",
                "network_range": "10.13.0.0/24"
            },
            "testing": {
                "attack_delay": 3.0,
                "flight_state_duration": 60,
                "include_tactics": ["all"],
                "exclude_attacks": [],
                "difficulty_filter": ["beginner", "intermediate", "advanced"],
                "iterations": 1,
                "parallel_attacks": False
            },
            "ml_detection": {
                "enabled": True,
                "training_samples_per_scenario": 150,
                "real_time_detection": True,
                "detection_interval": 30,
                "alert_threshold": 0.7
            },
            "output": {
                "results_directory": "results/automated_testing",
                "save_models": True,
                "generate_report": True,
                "export_formats": ["json", "csv", "html"]
            },
            "safety": {
                "safe_mode": True,
                "auto_stop_on_critical": True,
                "max_attack_duration": 300
            }
        }
        
        try:
            with open(config_file, 'r') as f:
                user_config = json.load(f)
            
            # 기본 설정에 사용자 설정 병합
            def merge_dicts(default, user):
                for key, value in user.items():
                    if key in default and isinstance(default[key], dict) and isinstance(value, dict):
                        merge_dicts(default[key], value)
                    else:
                        default[key] = value
            
            merge_dicts(default_config, user_config)
            return default_config
            
        except FileNotFoundError:
            logger.warning(f"설정 파일 {config_file}을 찾을 수 없습니다. 기본 설정을 사용합니다.")
            return default_config
        except json.JSONDecodeError as e:
            logger.error(f"설정 파일 JSON 오류: {e}")
            return default_config
    
    def _signal_handler(self, signum, frame):
        """시그널 핸들러"""
        logger.info(f"종료 신호 수신 ({signum})")
        self.is_running = False
    
    async def initialize_system(self) -> bool:
        """시스템 초기화"""
        logger.info("🚁 DVD 자동화 테스트 시스템 초기화 중...")
        
        try:
            # 1. DVD-Lite 초기화
            self.dvd_lite = DVDLite()
            self.cti_collector = SimpleCTI(self.config["target"])
            self.dvd_lite.register_cti_collector(self.cti_collector)
            
            # 2. 모든 공격 시나리오 등록
            registered_attacks = register_all_dvd_attacks(self.dvd_lite)
            logger.info(f"✅ {len(registered_attacks)}개 공격 시나리오 등록 완료")
            
            # 3. ML 탐지 시스템 초기화
            if self.config["ml_detection"]["enabled"]:
                logger.info("🤖 머신러닝 탐지 시스템 초기화 중...")
                self.ml_detection_system = DVDMLDetectionSystem()
                
                # 기존 모델 로드 시도
                if Path("models").exists():
                    try:
                        self.ml_detection_system.load_models()
                        if self.ml_detection_system.is_trained:
                            logger.info("✅ 기존 학습된 모델 로드 완료")
                        else:
                            raise ValueError("모델이 제대로 로드되지 않음")
                    except:
                        logger.info("기존 모델을 찾을 수 없습니다. 새로 학습합니다...")
                        await self._train_ml_models()
                else:
                    await self._train_ml_models()
                
                # 실시간 탐지 설정
                if self.config["ml_detection"]["real_time_detection"]:
                    self.ml_detection_system.real_time_system.detection_interval = \
                        self.config["ml_detection"]["detection_interval"]
            
            # 4. 결과 디렉토리 생성
            Path(self.config["output"]["results_directory"]).mkdir(parents=True, exist_ok=True)
            
            logger.info("✅ 시스템 초기화 완료")
            return True
            
        except Exception as e:
            logger.error(f"❌ 시스템 초기화 실패: {str(e)}")
            return False
    
    async def _train_ml_models(self):
        """ML 모델 학습"""
        logger.info("🎓 머신러닝 모델 학습 중...")
        
        samples_per_scenario = self.config["ml_detection"]["training_samples_per_scenario"]
        training_results = await self.ml_detection_system.initialize_and_train(samples_per_scenario)
        
        logger.info(f"✅ 모델 학습 완료: {training_results['total_samples']}개 샘플")
        
        # 모델 저장
        if self.config["output"]["save_models"]:
            self.ml_detection_system.save_models()
            logger.info("💾 학습된 모델 저장 완료")
    
    async def run_comprehensive_testing(self) -> Dict[str, Any]:
        """종합적인 자동화 테스트 실행"""
        logger.info("🚀 종합 자동화 테스트 시작")
        
        self.is_running = True
        start_time = datetime.now()
        
        try:
            # 1. ML 실시간 탐지 시작
            if self.ml_detection_system and self.config["ml_detection"]["real_time_detection"]:
                detection_task = asyncio.create_task(
                    self.ml_detection_system.start_real_time_detection()
                )
                logger.info("🤖 실시간 ML 탐지 시작")
            else:
                detection_task = None
            
            # 2. 비행 상태별 테스트 실행
            flight_states = [
                DVDFlightState.PRE_FLIGHT,
                DVDFlightState.TAKEOFF,
                DVDFlightState.AUTOPILOT_FLIGHT,
                DVDFlightState.MANUAL_FLIGHT,
                DVDFlightState.EMERGENCY_RTL,
                DVDFlightState.POST_FLIGHT
            ]
            
            for state in flight_states:
                if not self.is_running:
                    break
                
                logger.info(f"🛩️  비행 상태 전환: {state.value}")
                self.current_flight_state = state
                
                # 해당 상태에서 가능한 공격들 실행
                await self._run_flight_state_attacks(state)
                
                # 상태 간 대기
                if state != flight_states[-1]:
                    await self._wait_with_monitoring(
                        self.config["testing"]["flight_state_duration"]
                    )
            
            # 3. 전술별 추가 테스트
            await self._run_tactic_based_testing()
            
            # 4. 난이도별 테스트
            await self._run_difficulty_based_testing()
            
            # 5. 실시간 탐지 중지
            if detection_task:
                self.ml_detection_system.stop_real_time_detection()
                await asyncio.sleep(2)  # 정리 시간
            
            end_time = datetime.now()
            duration = end_time - start_time
            
            # 6. 결과 분석 및 보고서 생성
            results = await self._analyze_results(duration)
            
            if self.config["output"]["generate_report"]:
                await self._generate_comprehensive_report(results)
            
            logger.info(f"✅ 종합 테스트 완료 (소요시간: {duration})")
            return results
            
        except Exception as e:
            logger.error(f"❌ 테스트 실행 중 오류: {str(e)}")
            raise
        finally:
            self.is_running = False
            if detection_task and not detection_task.done():
                detection_task.cancel()
    
    async def _run_flight_state_attacks(self, flight_state: DVDFlightState):
        """특정 비행 상태에서 가능한 공격들 실행"""
        available_attacks = get_attacks_by_flight_state(flight_state)
        
        # 설정에 따른 필터링
        filtered_attacks = self._filter_attacks(available_attacks)
        
        if not filtered_attacks:
            logger.info(f"   {flight_state.value} 상태에서 실행할 공격이 없습니다")
            return
        
        logger.info(f"   {len(filtered_attacks)}개 공격 실행 예정: {flight_state.value}")
        
        for attack_name in filtered_attacks:
            if not self.is_running:
                break
                
            await self._execute_single_attack(attack_name, flight_state)
            
            # 공격 간 대기
            await asyncio.sleep(self.config["testing"]["attack_delay"])
    
    async def _run_tactic_based_testing(self):
        """전술별 공격 테스트"""
        logger.info("🎯 전술별 공격 테스트 시작")
        
        tactics = [
            DVDAttackTactic.RECONNAISSANCE,
            DVDAttackTactic.PROTOCOL_TAMPERING,
            DVDAttackTactic.DENIAL_OF_SERVICE,
            DVDAttackTactic.INJECTION,
            DVDAttackTactic.EXFILTRATION,
            DVDAttackTactic.FIRMWARE_ATTACKS
        ]
        
        for tactic in tactics:
            if not self.is_running:
                break
            
            logger.info(f"   전술: {tactic.value}")
            tactic_attacks = get_attacks_by_tactic(tactic)
            filtered_attacks = self._filter_attacks(tactic_attacks)
            
            for attack_name in filtered_attacks:
                if not self.is_running:
                    break
                await self._execute_single_attack(attack_name, self.current_flight_state, tactic)
                await asyncio.sleep(self.config["testing"]["attack_delay"])
    
    async def _run_difficulty_based_testing(self):
        """난이도별 공격 테스트"""
        logger.info("📈 난이도별 공격 테스트 시작")
        
        difficulties = ["beginner", "intermediate", "advanced"]
        
        for difficulty in difficulties:
            if not self.is_running:
                break
            
            if difficulty not in self.config["testing"]["difficulty_filter"]:
                continue
            
            logger.info(f"   난이도: {difficulty}")
            difficulty_attacks = get_attacks_by_difficulty(difficulty)
            filtered_attacks = self._filter_attacks(difficulty_attacks)
            
            # 어려운 공격일수록 더 신중하게
            attack_delay = self.config["testing"]["attack_delay"] * (difficulties.index(difficulty) + 1)
            
            for attack_name in filtered_attacks:
                if not self.is_running:
                    break
                await self._execute_single_attack(attack_name, self.current_flight_state)
                await asyncio.sleep(attack_delay)
    
    def _filter_attacks(self, attacks: List[str]) -> List[str]:
        """설정에 따른 공격 필터링"""
        filtered = []
        
        for attack_name in attacks:
            # 제외 목록 확인
            if attack_name in self.config["testing"]["exclude_attacks"]:
                continue
            
            # 전술 필터 확인
            include_tactics = self.config["testing"]["include_tactics"]
            if "all" not in include_tactics:
                attack_info = DVD_ATTACK_SCENARIOS.get(attack_name)
                if attack_info and attack_info["scenario"].tactic.value not in include_tactics:
                    continue
            
            # 난이도 필터 확인
            attack_info = DVD_ATTACK_SCENARIOS.get(attack_name)
            if attack_info:
                difficulty = attack_info["scenario"].difficulty
                if difficulty not in self.config["testing"]["difficulty_filter"]:
                    continue
            
            # 안전 모드 확인
            if self.config["safety"]["safe_mode"]:
                # 위험한 공격들 제외
                dangerous_attacks = ["firmware_rollback", "secure_boot_bypass", "bootloader_exploit"]
                if attack_name in dangerous_attacks:
                    logger.warning(f"   안전 모드: {attack_name} 공격 건너뜀")
                    continue
            
            filtered.append(attack_name)
        
        return filtered
    
    async def _execute_single_attack(self, 
                                   attack_name: str, 
                                   flight_state: DVDFlightState,
                                   tactic: Optional[DVDAttackTactic] = None):
        """단일 공격 실행 및 모니터링"""
        attack_info = DVD_ATTACK_SCENARIOS.get(attack_name)
        if not attack_info:
            logger.error(f"알 수 없는 공격: {attack_name}")
            return
        
        logger.info(f"⚔️  공격 실행: {attack_name} (상태: {flight_state.value})")
        
        start_time = datetime.now()
        
        try:
            # 1. DVD-Lite로 공격 실행
            attack_result = await self.dvd_lite.run_attack(attack_name)
            
            # 2. ML 탐지 시뮬레이션 (실시간 탐지가 비활성화된 경우)
            detection_result = None
            if self.ml_detection_system and not self.config["ml_detection"]["real_time_detection"]:
                detection_result = await self._simulate_ml_detection(attack_result)
            
            # 3. 결과 저장
            combined_result = {
                "attack_name": attack_name,
                "flight_state": flight_state.value,
                "tactic": tactic.value if tactic else attack_info["scenario"].tactic.value,
                "difficulty": attack_info["scenario"].difficulty,
                "attack_result": asdict(attack_result),
                "detection_result": asdict(detection_result) if detection_result else None,
                "execution_time": start_time.isoformat(),
                "duration": (datetime.now() - start_time).total_seconds()
            }
            
            self.attack_results.append(combined_result)
            
            # 4. 실시간 분석
            await self._analyze_attack_result(combined_result)
            
            # 5. 안전 검사
            if self.config["safety"]["auto_stop_on_critical"]:
                if detection_result and detection_result.threat_level == ThreatLevel.CRITICAL:
                    logger.critical(f"⛔ 치명적 위협 탐지! 테스트 중단: {attack_name}")
                    self.is_running = False
                    return
            
            # 성공/실패 로그
            status_icon = "✅" if attack_result.status == AttackStatus.SUCCESS else "❌"
            logger.info(f"   {status_icon} {attack_name}: {attack_result.status.value} "
                      f"({attack_result.response_time:.2f}초)")
            
            if detection_result:
                detection_icon = "🚨" if detection_result.attack_detected else "🟢"
                logger.info(f"   {detection_icon} ML 탐지: {detection_result.attack_detected} "
                          f"(신뢰도: {detection_result.confidence:.2f})")
            
        except Exception as e:
            logger.error(f"   ❌ {attack_name} 실행 실패: {str(e)}")
            
            # 실패 기록
            failed_result = {
                "attack_name": attack_name,
                "flight_state": flight_state.value,
                "tactic": tactic.value if tactic else attack_info["scenario"].tactic.value,
                "error": str(e),
                "execution_time": start_time.isoformat()
            }
            self.attack_results.append(failed_result)
    
    async def _simulate_ml_detection(self, attack_result) -> Any:
        """ML 탐지 시뮬레이션"""
        # 공격 결과를 바탕으로 네트워크/시스템 데이터 시뮬레이션
        simulated_network_data = {
            'packets': [
                {
                    'timestamp': datetime.now().timestamp(),
                    'protocol': 'MAVLink' if 'mavlink' in attack_result.attack_name.lower() else 'TCP',
                    'size': len(attack_result.iocs) * 100,  # IOC 수에 비례
                }
                for _ in range(max(10, len(attack_result.iocs) * 5))
            ]
        }
        
        simulated_system_data = {
            'cpu_usage': 90 if attack_result.status == AttackStatus.SUCCESS else 30,
            'memory_usage': 80 if len(attack_result.iocs) > 5 else 40,
            'parameter_changes': 1 if 'param' in attack_result.attack_name.lower() else 0,
        }
        
        simulated_mavlink_data = {
            'commands': attack_result.iocs[:10],  # IOC를 명령으로 시뮬레이션
            'gps_data': []
        }
        
        return await self.ml_detection_system.manual_detection(
            simulated_network_data, simulated_system_data, simulated_mavlink_data
        )
    
    async def _analyze_attack_result(self, result: Dict[str, Any]):
        """공격 결과 실시간 분석"""
        attack_result = result["attack_result"]
        detection_result = result.get("detection_result")
        
        # 통계 업데이트
        if detection_result:
            # 탐지 정확도 분석
            actual_attack = attack_result["status"] == "success"
            detected_attack = detection_result["attack_detected"]
            
            analysis = {
                "true_positive": actual_attack and detected_attack,
                "false_positive": not actual_attack and detected_attack,
                "true_negative": not actual_attack and not detected_attack,
                "false_negative": actual_attack and not detected_attack
            }
            
            result["detection_analysis"] = analysis
    
    async def _wait_with_monitoring(self, duration: int):
        """대기 중 모니터링 수행"""
        logger.info(f"⏳ {duration}초 대기 중 (모니터링 활성)")
        
        end_time = datetime.now() + timedelta(seconds=duration)
        
        while datetime.now() < end_time and self.is_running:
            await asyncio.sleep(5)  # 5초마다 체크
            
            # ML 탐지 시스템 상태 확인
            if self.ml_detection_system:
                status = self.ml_detection_system.get_system_status()
                if status["detection_statistics"].get("attack_detections", 0) > 0:
                    logger.info(f"   📊 실시간 탐지 현황: "
                              f"{status['detection_statistics']['attack_detections']}건")
    
    async def _analyze_results(self, duration: timedelta) -> Dict[str, Any]:
        """결과 종합 분석"""
        logger.info("📊 결과 분석 중...")
        
        total_attacks = len(self.attack_results)
        successful_attacks = len([r for r in self.attack_results 
                                if r.get("attack_result", {}).get("status") == "success"])
        
        # 전술별 성공률
        tactic_stats = {}
        for result in self.attack_results:
            tactic = result.get("tactic", "unknown")
            if tactic not in tactic_stats:
                tactic_stats[tactic] = {"total": 0, "success": 0}
            
            tactic_stats[tactic]["total"] += 1
            if result.get("attack_result", {}).get("status") == "success":
                tactic_stats[tactic]["success"] += 1
        
        # 탐지 정확도 분석
        detection_accuracy = self._calculate_detection_accuracy()
        
        # ML 시스템 통계
        ml_stats = {}
        if self.ml_detection_system:
            ml_stats = self.ml_detection_system.get_system_status()
        
        results = {
            "summary": {
                "total_duration": str(duration),
                "total_attacks": total_attacks,
                "successful_attacks": successful_attacks,
                "success_rate": (successful_attacks / total_attacks * 100) if total_attacks > 0 else 0,
                "attacks_per_hour": total_attacks / (duration.total_seconds() / 3600) if duration.total_seconds() > 0 else 0
            },
            "tactic_statistics": tactic_stats,
            "detection_accuracy": detection_accuracy,
            "ml_system_stats": ml_stats,
            "detailed_results": self.attack_results,
            "cti_summary": self.cti_collector.get_summary() if self.cti_collector else {},
            "config_used": self.config
        }
        
        return results
    
    def _calculate_detection_accuracy(self) -> Dict[str, Any]:
        """탐지 정확도 계산"""
        tp = fp = tn = fn = 0
        
        for result in self.attack_results:
            analysis = result.get("detection_analysis")
            if analysis:
                if analysis["true_positive"]:
                    tp += 1
                elif analysis["false_positive"]:
                    fp += 1
                elif analysis["true_negative"]:
                    tn += 1
                elif analysis["false_negative"]:
                    fn += 1
        
        total = tp + fp + tn + fn
        if total == 0:
            return {"message": "탐지 데이터 없음"}
        
        accuracy = (tp + tn) / total if total > 0 else 0
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
        
        return {
            "accuracy": accuracy,
            "precision": precision,
            "recall": recall,
            "f1_score": f1_score,
            "confusion_matrix": {
                "true_positive": tp,
                "false_positive": fp,
                "true_negative": tn,
                "false_negative": fn
            }
        }
    
    async def _generate_comprehensive_report(self, results: Dict[str, Any]):
        """종합 보고서 생성"""
        logger.info("📋 종합 보고서 생성 중...")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_dir = Path(self.config["output"]["results_directory"])
        
        # JSON 보고서
        if "json" in self.config["output"]["export_formats"]:
            json_file = results_dir / f"dvd_comprehensive_report_{timestamp}.json"
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False, default=str)
            logger.info(f"📄 JSON 보고서: {json_file}")
        
        # CSV 보고서
        if "csv" in self.config["output"]["export_formats"]:
            csv_file = results_dir / f"dvd_attack_results_{timestamp}.csv"
            await self._generate_csv_report(csv_file, results)
            logger.info(f"📊 CSV 보고서: {csv_file}")
        
        # HTML 보고서
        if "html" in self.config["output"]["export_formats"]:
            html_file = results_dir / f"dvd_report_{timestamp}.html"
            await self._generate_html_report(html_file, results)
            logger.info(f"🌐 HTML 보고서: {html_file}")
        
        # CTI 데이터 별도 저장
        if self.cti_collector:
            cti_json = self.cti_collector.export_json(
                str(results_dir / f"dvd_cti_data_{timestamp}.json")
            )
            cti_csv = self.cti_collector.export_csv(
                str(results_dir / f"dvd_cti_indicators_{timestamp}.csv")
            )
            logger.info(f"🔍 CTI 데이터: {cti_json}, {cti_csv}")
    
    async def _generate_csv_report(self, filepath: Path, results: Dict[str, Any]):
        """CSV 보고서 생성"""
        import csv
        
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = [
                'attack_name', 'tactic', 'difficulty', 'flight_state',
                'attack_status', 'response_time', 'ioc_count',
                'ml_detected', 'ml_confidence', 'threat_level',
                'execution_time', 'duration'
            ]
            
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for result in results["detailed_results"]:
                attack_result = result.get("attack_result", {})
                detection_result = result.get("detection_result", {})
                
                row = {
                    'attack_name': result.get("attack_name", ""),
                    'tactic': result.get("tactic", ""),
                    'difficulty': result.get("difficulty", ""),
                    'flight_state': result.get("flight_state", ""),
                    'attack_status': attack_result.get("status", ""),
                    'response_time': attack_result.get("response_time", 0),
                    'ioc_count': len(attack_result.get("iocs", [])),
                    'ml_detected': detection_result.get("attack_detected", False) if detection_result else False,
                    'ml_confidence': detection_result.get("confidence", 0) if detection_result else 0,
                    'threat_level': detection_result.get("threat_level", "") if detection_result else "",
                    'execution_time': result.get("execution_time", ""),
                    'duration': result.get("duration", 0)
                }
                writer.writerow(row)
    
    async def _generate_html_report(self, filepath: Path, results: Dict[str, Any]):
        """HTML 보고서 생성"""
        
        html_template = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DVD 자동화 테스트 종합 보고서</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1, h2, h3 { color: #2c3e50; }
        .summary-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }
        .stat-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
        }
        .stat-value {
            font-size: 2em;
            font-weight: bold;
            margin-bottom: 5px;
        }
        .stat-label {
            font-size: 0.9em;
            opacity: 0.9;
        }
        .tactic-table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }
        .tactic-table th, .tactic-table td {
            border: 1px solid #ddd;
            padding: 12px;
            text-align: left;
        }
        .tactic-table th {
            background-color: #f8f9fa;
            font-weight: bold;
        }
        .success-rate {
            font-weight: bold;
        }
        .success-rate.high { color: #27ae60; }
        .success-rate.medium { color: #f39c12; }
        .success-rate.low { color: #e74c3c; }
        .attack-details {
            background-color: #f8f9fa;
            border-left: 4px solid #3498db;
            padding: 15px;
            margin: 10px 0;
        }
        .detection-accuracy {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 20px;
            margin: 20px 0;
        }
        .confusion-matrix {
            background-color: #ecf0f1;
            padding: 15px;
            border-radius: 5px;
        }
        .timestamp {
            color: #7f8c8d;
            font-size: 0.9em;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚁 DVD 자동화 테스트 종합 보고서</h1>
        <p class="timestamp">생성 시간: {timestamp}</p>
        
        <h2>📊 실행 요약</h2>
        <div class="summary-grid">
            <div class="stat-card">
                <div class="stat-value">{total_attacks}</div>
                <div class="stat-label">총 공격 수</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{success_rate:.1f}%</div>
                <div class="stat-label">성공률</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{total_duration}</div>
                <div class="stat-label">총 소요시간</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{attacks_per_hour:.1f}</div>
                <div class="stat-label">시간당 공격 수</div>
            </div>
        </div>
        
        <h2>🎯 전술별 성과</h2>
        <table class="tactic-table">
            <thead>
                <tr>
                    <th>전술</th>
                    <th>총 공격</th>
                    <th>성공</th>
                    <th>성공률</th>
                </tr>
            </thead>
            <tbody>
                {tactic_rows}
            </tbody>
        </table>
        
        <h2>🤖 ML 탐지 정확도</h2>
        <div class="detection-accuracy">
            <div>
                <h3>전체 정확도</h3>
                <div class="stat-card">
                    <div class="stat-value">{detection_accuracy:.1f}%</div>
                    <div class="stat-label">정확도</div>
                </div>
            </div>
            <div class="confusion-matrix">
                <h3>혼동 행렬</h3>
                <p>참 양성: {tp}</p>
                <p>거짓 양성: {fp}</p>
                <p>참 음성: {tn}</p>
                <p>거짓 음성: {fn}</p>
            </div>
        </div>
        
        <h2>📋 상세 결과</h2>
        {detailed_results}
        
        <h2>🔍 CTI 수집 결과</h2>
        <div class="attack-details">
            <p><strong>수집된 지표:</strong> {cti_indicators}개</p>
            <p><strong>공격 패턴:</strong> {cti_patterns}개</p>
            <p><strong>신뢰도별 분포:</strong> 높음({cti_high}), 중간({cti_medium}), 낮음({cti_low})</p>
        </div>
        
        <footer style="margin-top: 40px; text-align: center; color: #7f8c8d;">
            <p>DVD-Lite 자동화 테스트 시스템 | 생성 시간: {timestamp}</p>
        </footer>
    </div>
</body>
</html>
        """
        
        # 데이터 준비
        summary = results["summary"]
        tactic_stats = results["tactic_statistics"]
        detection_acc = results["detection_accuracy"]
        cti_summary = results["cti_summary"]
        
        # 전술별 테이블 생성
        tactic_rows = ""
        for tactic, stats in tactic_stats.items():
            success_rate = (stats["success"] / stats["total"] * 100) if stats["total"] > 0 else 0
            rate_class = "high" if success_rate >= 70 else "medium" if success_rate >= 40 else "low"
            
            tactic_rows += f"""
                <tr>
                    <td>{tactic}</td>
                    <td>{stats["total"]}</td>
                    <td>{stats["success"]}</td>
                    <td class="success-rate {rate_class}">{success_rate:.1f}%</td>
                </tr>
            """
        
        # 상세 결과 생성
        detailed_results = ""
        for result in results["detailed_results"][:10]:  # 상위 10개만
            attack_result = result.get("attack_result", {})
            detection_result = result.get("detection_result", {})
            
            status_icon = "✅" if attack_result.get("status") == "success" else "❌"
            detection_icon = "🚨" if detection_result and detection_result.get("attack_detected") else "🟢"
            
            detailed_results += f"""
                <div class="attack-details">
                    <h4>{status_icon} {result.get("attack_name", "Unknown")}</h4>
                    <p><strong>전술:</strong> {result.get("tactic", "")}</p>
                    <p><strong>비행 상태:</strong> {result.get("flight_state", "")}</p>
                    <p><strong>공격 결과:</strong> {attack_result.get("status", "")} ({attack_result.get("response_time", 0):.2f}초)</p>
                    <p><strong>ML 탐지:</strong> {detection_icon} {detection_result.get("attack_detected", False) if detection_result else "N/A"}</p>
                    <p><strong>IOC 수:</strong> {len(attack_result.get("iocs", []))}</p>
                </div>
            """
        
        # HTML 생성
        html_content = html_template.format(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            total_attacks=summary["total_attacks"],
            success_rate=summary["success_rate"],
            total_duration=summary["total_duration"],
            attacks_per_hour=summary["attacks_per_hour"],
            tactic_rows=tactic_rows,
            detection_accuracy=detection_acc.get("accuracy", 0) * 100,
            tp=detection_acc.get("confusion_matrix", {}).get("true_positive", 0),
            fp=detection_acc.get("confusion_matrix", {}).get("false_positive", 0),
            tn=detection_acc.get("confusion_matrix", {}).get("true_negative", 0),
            fn=detection_acc.get("confusion_matrix", {}).get("false_negative", 0),
            detailed_results=detailed_results,
            cti_indicators=cti_summary.get("total_indicators", 0),
            cti_patterns=cti_summary.get("total_patterns", 0),
            cti_high=cti_summary.get("statistics", {}).get("by_confidence", {}).get("high", 0),
            cti_medium=cti_summary.get("statistics", {}).get("by_confidence", {}).get("medium", 0),
            cti_low=cti_summary.get("statistics", {}).get("by_confidence", {}).get("low", 0)
        )
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)

# =============================================================================
# 명령행 인터페이스
# =============================================================================

def create_argument_parser():
    """명령행 인자 파서 생성"""
    parser = argparse.ArgumentParser(
        description="DVD 자동화 테스트 및 ML 탐지 통합 시스템",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  # 기본 종합 테스트 실행
  python dvd_automated_system.py --mode comprehensive

  # 특정 전술만 테스트
  python dvd_automated_system.py --mode tactical --tactics reconnaissance protocol_tampering

  # 난이도별 테스트
  python dvd_automated_system.py --mode difficulty --difficulty intermediate advanced

  # ML 모델만 학습
  python dvd_automated_system.py --mode train-ml --samples 200

  # 실시간 모니터링만
  python dvd_automated_system.py --mode monitor --duration 300

  # 설정 파일 사용
  python dvd_automated_system.py --config custom_config.json
        """
    )
    
    parser.add_argument(
        "--mode",
        choices=["comprehensive", "tactical", "difficulty", "train-ml", "monitor", "single-attack"],
        default="comprehensive",
        help="실행 모드 선택"
    )
    
    parser.add_argument(
        "--config",
        default="dvd_config.json",
        help="설정 파일 경로"
    )
    
    parser.add_argument(
        "--tactics",
        nargs="+",
        choices=["reconnaissance", "protocol_tampering", "denial_of_service", "injection", "exfiltration", "firmware_attacks"],
        help="테스트할 전술들 (tactical 모드에서 사용)"
    )
    
    parser.add_argument(
        "--difficulty",
        nargs="+",
        choices=["beginner", "intermediate", "advanced"],
        default=["beginner", "intermediate", "advanced"],
        help="테스트할 난이도들"
    )
    
    parser.add_argument(
        "--attack",
        help="단일 공격 실행 (single-attack 모드에서 사용)"
    )
    
    parser.add_argument(
        "--samples",
        type=int,
        default=150,
        help="ML 학습용 시나리오당 샘플 수"
    )
    
    parser.add_argument(
        "--duration",
        type=int,
        default=300,
        help="모니터링 지속 시간 (초)"
    )
    
    parser.add_argument(
        "--no-ml",
        action="store_true",
        help="ML 탐지 시스템 비활성화"
    )
    
    parser.add_argument(
        "--safe-mode",
        action="store_true",
        help="안전 모드 활성화 (위험한 공격 제외)"
    )
    
    parser.add_argument(
        "--output-dir",
        default="results/automated_testing",
        help="결과 출력 디렉토리"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="상세 로그 출력"
    )
    
    return parser

async def main():
    """메인 함수"""
    parser = create_argument_parser()
    args = parser.parse_args()
    
    # 로깅 레벨 설정
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # 설정 오버라이드
    config_overrides = {}
    if args.no_ml:
        config_overrides["ml_detection"] = {"enabled": False}
    if args.safe_mode:
        config_overrides["safety"] = {"safe_mode": True}
    if args.output_dir:
        config_overrides["output"] = {"results_directory": args.output_dir}
    
    try:
        # 시스템 초기화
        system = DVDAutomatedTestingSystem(args.config)
        
        # 설정 오버라이드 적용
        for key, value in config_overrides.items():
            if isinstance(value, dict) and key in system.config:
                system.config[key].update(value)
            else:
                system.config[key] = value
        
        # 시스템 초기화
        if not await system.initialize_system():
            logger.error("시스템 초기화 실패")
            sys.exit(1)
        
        # 모드별 실행
        if args.mode == "comprehensive":
            logger.info("🚀 종합 자동화 테스트 시작")
            results = await system.run_comprehensive_testing()
            
        elif args.mode == "tactical":
            if not args.tactics:
                logger.error("--tactics 옵션이 필요합니다")
                sys.exit(1)
            
            logger.info(f"🎯 전술별 테스트: {args.tactics}")
            system.config["testing"]["include_tactics"] = args.tactics
            results = await system.run_comprehensive_testing()
            
        elif args.mode == "difficulty":
            logger.info(f"📈 난이도별 테스트: {args.difficulty}")
            system.config["testing"]["difficulty_filter"] = args.difficulty
            results = await system.run_comprehensive_testing()
            
        elif args.mode == "train-ml":
            if not system.ml_detection_system:
                logger.error("ML 시스템이 비활성화되어 있습니다")
                sys.exit(1)
            
            logger.info(f"🎓 ML 모델 학습 시작 (샘플: {args.samples})")
            training_results = await system.ml_detection_system.initialize_and_train(args.samples)
            system.ml_detection_system.save_models()
            
            print("학습 결과:")
            for model_name, result in training_results["training_results"].items():
                if "accuracy" in result:
                    print(f"  {model_name}: 정확도 {result['accuracy']:.3f}")
                else:
                    print(f"  {model_name}: {result}")
            
            return
            
        elif args.mode == "monitor":
            if not system.ml_detection_system:
                logger.error("ML 시스템이 비활성화되어 있습니다")
                sys.exit(1)
            
            logger.info(f"👀 실시간 모니터링 시작 ({args.duration}초)")
            
            # 모니터링 태스크 시작
            monitor_task = asyncio.create_task(
                system.ml_detection_system.start_real_time_detection()
            )
            
            # 지정된 시간만큼 대기
            await asyncio.sleep(args.duration)
            
            # 모니터링 중지
            system.ml_detection_system.stop_real_time_detection()
            
            # 통계 출력
            stats = system.ml_detection_system.get_system_status()
            print("\n모니터링 결과:")
            print(f"  탐지된 공격: {stats['detection_statistics'].get('attack_detections', 0)}건")
            print(f"  총 탐지: {stats['detection_statistics'].get('total_detections', 0)}건")
            
            return
            
        elif args.mode == "single-attack":
            if not args.attack:
                logger.error("--attack 옵션이 필요합니다")
                sys.exit(1)
            
            logger.info(f"⚔️  단일 공격 실행: {args.attack}")
            await system._execute_single_attack(args.attack, DVDFlightState.AUTOPILOT_FLIGHT)
            
            if system.attack_results:
                result = system.attack_results[-1]
                print(f"\n공격 결과:")
                print(f"  상태: {result['attack_result']['status']}")
                print(f"  응답시간: {result['attack_result']['response_time']:.2f}초")
                print(f"  IOC 수: {len(result['attack_result']['iocs'])}")
            
            return
        
        # 결과 출력
        if 'results' in locals():
            print("\n" + "="*60)
            print("📊 최종 결과 요약")
            print("="*60)
            print(f"총 공격 수: {results['summary']['total_attacks']}")
            print(f"성공률: {results['summary']['success_rate']:.1f}%")
            print(f"소요시간: {results['summary']['total_duration']}")
            
            if results['detection_accuracy'].get('accuracy'):
                print(f"ML 탐지 정확도: {results['detection_accuracy']['accuracy']:.1f}%")
            
            print(f"\n📁 상세 보고서가 {system.config['output']['results_directory']}에 저장되었습니다.")
        
    except KeyboardInterrupt:
        logger.info("\n👋 사용자에 의해 중단됨")
    except Exception as e:
        logger.error(f"❌ 실행 중 오류 발생: {str(e)}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())