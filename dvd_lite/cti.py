#!/usr/bin/env python3
"""
DVD Testbed CTI Integration Module
기존 테스트베드와 완전 통합되는 CTI 수집 및 분류 시스템

이 모듈은 기존의 dvd_lite/cti.py를 대체하고 enhanced_cti_defense_system과 연동합니다.
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
import sqlite3
import pandas as pd
import numpy as np
from collections import defaultdict, deque

# 기존 테스트베드 모듈과 호환성 유지
try:
    from dvd_lite.dvd_attacks.core.enums import AttackTactic, AttackSeverity
    from dvd_lite.dvd_attacks.core.result import AttackResult
except ImportError:
    # 호환성을 위한 기본 정의
    class AttackTactic(Enum):
        RECONNAISSANCE = "reconnaissance"
        PROTOCOL_TAMPERING = "protocol_tampering"
        DENIAL_OF_SERVICE = "denial_of_service"
        INJECTION = "injection"
        EXFILTRATION = "exfiltration"
        FIRMWARE_ATTACKS = "firmware_attacks"
    
    class AttackSeverity(Enum):
        LOW = "low"
        MEDIUM = "medium"
        HIGH = "high"
        CRITICAL = "critical"
    
    @dataclass
    class AttackResult:
        attack_id: str
        success: bool
        execution_time: float
        severity: AttackSeverity
        iocs: List[str]
        timestamp: datetime
        additional_data: Dict[str, Any] = None

logger = logging.getLogger(__name__)

# =============================================================================
# CTI 데이터 구조 확장
# =============================================================================

@dataclass
class IOCIndicator:
    """IOC 지표 데이터 구조"""
    ioc_type: str
    value: str
    confidence: int
    attack_type: str
    first_seen: datetime
    last_seen: datetime
    context: Dict[str, Any]
    threat_level: str = "medium"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'ioc_type': self.ioc_type,
            'value': self.value,
            'confidence': self.confidence,
            'attack_type': self.attack_type,
            'first_seen': self.first_seen.isoformat(),
            'last_seen': self.last_seen.isoformat(),
            'context': self.context,
            'threat_level': self.threat_level
        }

@dataclass
class AttackPattern:
    """공격 패턴 데이터 구조"""
    pattern_id: str
    name: str
    attack_category: str
    success_rate: float
    avg_execution_time: float
    ioc_count: int
    detection_rules: List[str]
    mitigation_strategies: List[str]
    last_updated: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'pattern_id': self.pattern_id,
            'name': self.name,
            'attack_category': self.attack_category,
            'success_rate': self.success_rate,
            'avg_execution_time': self.avg_execution_time,
            'ioc_count': self.ioc_count,
            'detection_rules': self.detection_rules,
            'mitigation_strategies': self.mitigation_strategies,
            'last_updated': self.last_updated.isoformat()
        }

# =============================================================================
# 기존 SimpleCTI를 확장한 EnhancedCTI
# =============================================================================

class EnhancedCTI:
    """
    기존 dvd_lite/cti.py의 SimpleCTI를 대체하는 향상된 CTI 시스템
    완전한 하위 호환성 제공
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {
            "confidence_threshold": 70,
            "export_format": "json",
            "real_time_analysis": True,
            "database_enabled": True
        }
        
        # 기존 SimpleCTI 호환성 유지
        self.indicators = []
        self.attack_patterns = {}
        self.total_indicators = 0
        
        # 새로운 기능
        self.ioc_database = {}
        self.pattern_database = {}
        self.defense_system = None
        
        # 데이터베이스 설정
        if self.config.get("database_enabled", True):
            self.db_path = "enhanced_cti.db"
            self._init_database()
        
        # 실시간 분석 큐
        self.analysis_queue = deque(maxlen=10000)
        self.running = False
        
        logger.info("✅ Enhanced CTI 시스템 초기화 완료")
    
    def _init_database(self):
        """CTI 전용 데이터베이스 초기화"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # IOC 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ioc_indicators (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ioc_type TEXT NOT NULL,
                    value TEXT NOT NULL,
                    confidence INTEGER,
                    attack_type TEXT,
                    first_seen TEXT,
                    last_seen TEXT,
                    context TEXT,
                    threat_level TEXT,
                    UNIQUE(ioc_type, value)
                )
            ''')
            
            # 공격 패턴 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS attack_patterns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pattern_id TEXT UNIQUE NOT NULL,
                    name TEXT,
                    attack_category TEXT,
                    success_rate REAL,
                    avg_execution_time REAL,
                    ioc_count INTEGER,
                    detection_rules TEXT,
                    mitigation_strategies TEXT,
                    last_updated TEXT
                )
            ''')
            
            # 분석 결과 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS analysis_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    attack_id TEXT,
                    analysis_type TEXT,
                    confidence REAL,
                    classification TEXT,
                    features TEXT,
                    recommendation TEXT
                )
            ''')
            
            conn.commit()
            conn.close()
            logger.info("✅ Enhanced CTI 데이터베이스 초기화 완료")
            
        except Exception as e:
            logger.error(f"CTI 데이터베이스 초기화 오류: {e}")
    
    # =============================================================================
    # 기존 SimpleCTI 호환성 메서드들
    # =============================================================================
    
    def collect_from_result(self, result: AttackResult):
        """기존 SimpleCTI의 collect_from_result 메서드 호환성 유지"""
        try:
            # 기본 IOC 수집
            for ioc in result.iocs:
                self._add_indicator_legacy(ioc, result)
            
            # 공격 패턴 업데이트
            self._update_attack_pattern_legacy(result)
            
            # 새로운 향상된 분석 추가
            asyncio.create_task(self._enhanced_analysis(result))
            
            logger.info(f"📊 CTI 수집 완료: {result.attack_id}")
            
        except Exception as e:
            logger.error(f"CTI 수집 오류: {e}")
    
    def _add_indicator_legacy(self, ioc: str, result: AttackResult):
        """기존 방식의 IOC 추가 (호환성)"""
        indicator = {
            "ioc_type": self._classify_ioc_type(ioc),
            "value": ioc,
            "confidence": self._calculate_confidence(result),
            "attack_type": getattr(result, 'attack_type', 'unknown'),
            "timestamp": result.timestamp.isoformat() if hasattr(result.timestamp, 'isoformat') else str(result.timestamp)
        }
        
        self.indicators.append(indicator)
        self.total_indicators += 1
    
    def _update_attack_pattern_legacy(self, result: AttackResult):
        """기존 방식의 공격 패턴 업데이트 (호환성)"""
        attack_type = getattr(result, 'attack_type', result.attack_id.split('_')[0])
        
        if attack_type not in self.attack_patterns:
            self.attack_patterns[attack_type] = {
                "success_rate": 0.0,
                "avg_response_time": 0.0,
                "ioc_count": 0,
                "total_attempts": 0,
                "successful_attempts": 0
            }
        
        pattern = self.attack_patterns[attack_type]
        pattern["total_attempts"] += 1
        
        if result.success:
            pattern["successful_attempts"] += 1
        
        pattern["success_rate"] = pattern["successful_attempts"] / pattern["total_attempts"]
        pattern["avg_response_time"] = (pattern["avg_response_time"] + result.execution_time) / 2
        pattern["ioc_count"] += len(result.iocs)
    
    def get_summary(self) -> Dict[str, Any]:
        """기존 SimpleCTI의 get_summary 메서드 호환성 유지"""
        return {
            "total_indicators": self.total_indicators,
            "unique_attack_types": len(self.attack_patterns),
            "avg_confidence": self._calculate_avg_confidence(),
            "statistics": {
                "by_attack_type": dict(self.attack_patterns),
                "by_ioc_type": self._get_ioc_type_distribution(),
                "timeline": self._get_recent_timeline()
            },
            "enhanced_features": {
                "real_time_analysis": self.config.get("real_time_analysis", False),
                "ml_classification": self.defense_system is not None,
                "database_records": self._get_database_stats()
            }
        }
    
    def export_json(self, filepath: str) -> str:
        """기존 SimpleCTI의 export_json 메서드 호환성 유지"""
        try:
            export_data = {
                "metadata": {
                    "export_time": datetime.now().isoformat(),
                    "total_indicators": self.total_indicators,
                    "source": "enhanced-cti-system",
                    "version": "2.0"
                },
                "indicators": self.indicators,
                "attack_patterns": self.attack_patterns,
                "enhanced_data": {
                    "ioc_database": [ioc.to_dict() for ioc in self.ioc_database.values()],
                    "pattern_database": [pattern.to_dict() for pattern in self.pattern_database.values()],
                    "analysis_summary": self._get_analysis_summary()
                }
            }
            
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"📄 CTI 데이터 JSON 내보내기 완료: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"JSON 내보내기 오류: {e}")
            return ""
    
    def export_csv(self, filepath: str) -> str:
        """기존 SimpleCTI의 export_csv 메서드 호환성 유지"""
        try:
            # IOC 데이터를 CSV로 변환
            csv_data = []
            
            for indicator in self.indicators:
                csv_data.append({
                    'ioc_type': indicator.get('ioc_type', ''),
                    'value': indicator.get('value', ''),
                    'confidence': indicator.get('confidence', 0),
                    'attack_type': indicator.get('attack_type', ''),
                    'timestamp': indicator.get('timestamp', ''),
                    'threat_level': indicator.get('threat_level', 'medium')
                })
            
            # Enhanced IOC 데이터 추가
            for ioc in self.ioc_database.values():
                csv_data.append({
                    'ioc_type': ioc.ioc_type,
                    'value': ioc.value,
                    'confidence': ioc.confidence,
                    'attack_type': ioc.attack_type,
                    'timestamp': ioc.last_seen.isoformat(),
                    'threat_level': ioc.threat_level
                })
            
            df = pd.DataFrame(csv_data)
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(filepath, index=False)
            
            logger.info(f"📄 CTI 데이터 CSV 내보내기 완료: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"CSV 내보내기 오류: {e}")
            return ""
    
    # =============================================================================
    # 새로운 향상된 CTI 기능들
    # =============================================================================
    
    async def _enhanced_analysis(self, result: AttackResult):
        """향상된 실시간 분석"""
        try:
            analysis_data = {
                'timestamp': datetime.now(),
                'attack_id': result.attack_id,
                'result': result,
                'features': self._extract_features(result),
                'context': self._build_context(result)
            }
            
            self.analysis_queue.append(analysis_data)
            
            # 실시간 분석 수행
            if self.config.get("real_time_analysis", True):
                await self._perform_real_time_analysis(analysis_data)
            
            # IOC 고도화
            await self._enhance_iocs(result)
            
            # 공격 패턴 학습
            await self._learn_attack_patterns(result)
            
        except Exception as e:
            logger.error(f"향상된 분석 오류: {e}")
    
    async def _perform_real_time_analysis(self, analysis_data: Dict[str, Any]):
        """실시간 분석 수행"""
        try:
            result = analysis_data['result']
            features = analysis_data['features']
            
            # 1. 위험도 분석
            risk_score = self._calculate_risk_score(result, features)
            
            # 2. 연관성 분석
            correlations = await self._find_correlations(result)
            
            # 3. 예측 분석
            predictions = await self._predict_next_attacks(result)
            
            # 4. 권장사항 생성
            recommendations = self._generate_recommendations(result, risk_score)
            
            # 분석 결과 저장
            analysis_result = {
                'timestamp': datetime.now().isoformat(),
                'attack_id': result.attack_id,
                'analysis_type': 'real_time',
                'confidence': risk_score,
                'classification': self._classify_attack_sophistication(result),
                'features': json.dumps(features),
                'correlations': correlations,
                'predictions': predictions,
                'recommendations': recommendations
            }
            
            await self._save_analysis_result(analysis_result)
            
            # 방어 시스템에 전달
            if self.defense_system:
                await self.defense_system._process_cti_analysis(analysis_result)
            
        except Exception as e:
            logger.error(f"실시간 분석 오류: {e}")
    
    async def _enhance_iocs(self, result: AttackResult):
        """IOC 고도화 및 컨텍스트 추가"""
        try:
            for ioc_value in result.iocs:
                ioc_type = self._classify_ioc_type(ioc_value)
                
                # 기존 IOC 업데이트 또는 새로 생성
                ioc_key = f"{ioc_type}:{ioc_value}"
                
                if ioc_key in self.ioc_database:
                    # 기존 IOC 업데이트
                    existing_ioc = self.ioc_database[ioc_key]
                    existing_ioc.last_seen = datetime.now()
                    existing_ioc.confidence = min(100, existing_ioc.confidence + 5)
                    existing_ioc.context.update(self._build_ioc_context(result))
                else:
                    # 새 IOC 생성
                    new_ioc = IOCIndicator(
                        ioc_type=ioc_type,
                        value=ioc_value,
                        confidence=self._calculate_confidence(result),
                        attack_type=getattr(result, 'attack_type', 'unknown'),
                        first_seen=datetime.now(),
                        last_seen=datetime.now(),
                        context=self._build_ioc_context(result),
                        threat_level=self._determine_threat_level(result)
                    )
                    self.ioc_database[ioc_key] = new_ioc
                
                # 데이터베이스에 저장
                await self._save_ioc_to_db(self.ioc_database[ioc_key])
            
        except Exception as e:
            logger.error(f"IOC 고도화 오류: {e}")
    
    async def _learn_attack_patterns(self, result: AttackResult):
        """공격 패턴 학습 및 업데이트"""
        try:
            attack_type = getattr(result, 'attack_type', result.attack_id.split('_')[0])
            pattern_id = f"pattern_{attack_type}"
            
            if pattern_id in self.pattern_database:
                # 기존 패턴 업데이트
                pattern = self.pattern_database[pattern_id]
                pattern.last_updated = datetime.now()
                
                # 성공률 업데이트
                total_attempts = getattr(pattern, 'total_attempts', 1) + 1
                successful_attempts = getattr(pattern, 'successful_attempts', 0)
                if result.success:
                    successful_attempts += 1
                
                pattern.success_rate = successful_attempts / total_attempts
                pattern.avg_execution_time = (pattern.avg_execution_time + result.execution_time) / 2
                pattern.ioc_count += len(result.iocs)
                
                # 패턴 정보 업데이트
                setattr(pattern, 'total_attempts', total_attempts)
                setattr(pattern, 'successful_attempts', successful_attempts)
                
            else:
                # 새 패턴 생성
                new_pattern = AttackPattern(
                    pattern_id=pattern_id,
                    name=f"{attack_type.replace('_', ' ').title()} Attack Pattern",
                    attack_category=attack_type,
                    success_rate=1.0 if result.success else 0.0,
                    avg_execution_time=result.execution_time,
                    ioc_count=len(result.iocs),
                    detection_rules=self._generate_detection_rules(result),
                    mitigation_strategies=self._generate_mitigation_strategies(result),
                    last_updated=datetime.now()
                )
                
                self.pattern_database[pattern_id] = new_pattern
                setattr(new_pattern, 'total_attempts', 1)
                setattr(new_pattern, 'successful_attempts', 1 if result.success else 0)
            
            # 데이터베이스에 저장
            await self._save_pattern_to_db(self.pattern_database[pattern_id])
            
        except Exception as e:
            logger.error(f"패턴 학습 오류: {e}")
    
    def _extract_features(self, result: AttackResult) -> Dict[str, Any]:
        """공격 결과에서 특징 추출"""
        features = {
            'execution_time': result.execution_time,
            'success': result.success,
            'ioc_count': len(result.iocs),
            'severity': getattr(result, 'severity', 'medium'),
            'timestamp_hour': result.timestamp.hour if hasattr(result.timestamp, 'hour') else 0,
            'timestamp_weekday': result.timestamp.weekday() if hasattr(result.timestamp, 'weekday') else 0
        }
        
        # 추가 데이터에서 특징 추출
        if hasattr(result, 'additional_data') and result.additional_data:
            additional = result.additional_data
            features.update({
                'network_packets': additional.get('network_packets', 0),
                'system_calls': additional.get('system_calls', 0),
                'file_operations': len(additional.get('files_accessed', [])),
                'registry_changes': len(additional.get('registry_changes', [])),
                'process_spawns': len(additional.get('processes_spawned', []))
            })
        
        return features
    
    def _build_context(self, result: AttackResult) -> Dict[str, Any]:
        """공격 컨텍스트 구축"""
        context = {
            'attack_id': result.attack_id,
            'timestamp': result.timestamp.isoformat() if hasattr(result.timestamp, 'isoformat') else str(result.timestamp),
            'execution_environment': {
                'os_type': 'linux',  # DVD 환경
                'container_environment': True,
                'simulation_mode': True
            },
            'attack_metadata': {
                'tactic': getattr(result, 'tactic', 'unknown'),
                'technique': getattr(result, 'technique', 'unknown'),
                'target_system': 'drone_system'
            }
        }
        
        return context
    
    def _build_ioc_context(self, result: AttackResult) -> Dict[str, Any]:
        """IOC 컨텍스트 구축"""
        return {
            'attack_id': result.attack_id,
            'success': result.success,
            'execution_time': result.execution_time,
            'detection_method': 'testbed_simulation',
            'environment': 'dvd_testbed',
            'related_techniques': getattr(result, 'techniques', []),
            'target_components': getattr(result, 'target_components', [])
        }
    
    def _calculate_risk_score(self, result: AttackResult, features: Dict[str, Any]) -> float:
        """위험도 점수 계산"""
        base_score = 0.5
        
        # 성공 여부
        if result.success:
            base_score += 0.3
        
        # 심각도
        severity_scores = {'low': 0.1, 'medium': 0.2, 'high': 0.3, 'critical': 0.4}
        severity = getattr(result, 'severity', 'medium')
        if hasattr(severity, 'value'):
            severity = severity.value
        base_score += severity_scores.get(severity.lower(), 0.2)
        
        # IOC 수
        base_score += min(0.2, len(result.iocs) * 0.02)
        
        # 실행 시간 (빠른 공격이 더 위험)
        if result.execution_time < 1.0:
            base_score += 0.1
        
        return min(1.0, base_score)
    
    async def _find_correlations(self, result: AttackResult) -> List[Dict[str, Any]]:
        """연관성 분석"""
        correlations = []
        
        try:
            # 최근 공격들과의 연관성 찾기
            recent_attacks = [
                item for item in self.analysis_queue
                if (datetime.now() - item['timestamp']).total_seconds() < 3600  # 1시간 내
            ]
            
            for attack_data in recent_attacks:
                if attack_data['result'].attack_id != result.attack_id:
                    correlation_score = self._calculate_correlation_score(result, attack_data['result'])
                    
                    if correlation_score > 0.5:
                        correlations.append({
                            'related_attack': attack_data['result'].attack_id,
                            'correlation_score': correlation_score,
                            'correlation_type': self._determine_correlation_type(result, attack_data['result']),
                            'time_difference': (result.timestamp - attack_data['timestamp']).total_seconds()
                        })
            
        except Exception as e:
            logger.error(f"연관성 분석 오류: {e}")
        
        return correlations
    
    async def _predict_next_attacks(self, result: AttackResult) -> List[Dict[str, Any]]:
        """다음 공격 예측"""
        predictions = []
        
        try:
            # 공격 체인 패턴 기반 예측
            attack_chains = {
                'reconnaissance': ['protocol_tampering', 'injection'],
                'protocol_tampering': ['denial_of_service', 'exfiltration'],
                'injection': ['exfiltration', 'firmware_attacks'],
                'denial_of_service': ['firmware_attacks'],
                'exfiltration': ['firmware_attacks']
            }
            
            current_type = getattr(result, 'attack_type', result.attack_id.split('_')[0])
            likely_next = attack_chains.get(current_type, [])
            
            for next_attack in likely_next:
                # 패턴 데이터베이스에서 확률 계산
                pattern_id = f"pattern_{next_attack}"
                if pattern_id in self.pattern_database:
                    pattern = self.pattern_database[pattern_id]
                    probability = pattern.success_rate * 0.8  # 체인 확률 보정
                else:
                    probability = 0.3  # 기본 확률
                
                predictions.append({
                    'attack_type': next_attack,
                    'probability': probability,
                    'estimated_time_window': '1-6 hours',
                    'reasoning': f"Common attack chain from {current_type}"
                })
        
        except Exception as e:
            logger.error(f"공격 예측 오류: {e}")
        
        return predictions
    
    def _generate_recommendations(self, result: AttackResult, risk_score: float) -> List[str]:
        """보안 권장사항 생성"""
        recommendations = []
        
        try:
            attack_type = getattr(result, 'attack_type', result.attack_id.split('_')[0])
            
            # 일반적인 권장사항
            if result.success:
                recommendations.append("공격이 성공했습니다. 즉시 보안 강화 조치가 필요합니다.")
            
            # 공격 유형별 권장사항
            type_recommendations = {
                'reconnaissance': [
                    "네트워크 세그멘테이션 강화",
                    "불필요한 서비스 포트 차단",
                    "네트워크 모니터링 강화"
                ],
                'protocol_tampering': [
                    "MAVLink 프로토콜 암호화 활성화",
                    "메시지 무결성 검증 구현",
                    "GPS 스푸핑 탐지 시스템 배포"
                ],
                'injection': [
                    "입력 유효성 검사 강화",
                    "권한 관리 정책 개선",
                    "코드 실행 방지 기술 적용"
                ],
                'denial_of_service': [
                    "트래픽 제한 정책 적용",
                    "DDoS 방어 시스템 배치",
                    "서비스 이중화 구성"
                ],
                'exfiltration': [
                    "데이터 유출 방지 솔루션 배치",
                    "네트워크 트래픽 암호화",
                    "접근 권한 최소화 원칙 적용"
                ],
                'firmware_attacks': [
                    "펌웨어 서명 검증 강화",
                    "보안 부팅 활성화",
                    "펌웨어 업데이트 채널 보안"
                ]
            }
            
            recommendations.extend(type_recommendations.get(attack_type, []))
            
            # 위험도 기반 추가 권장사항
            if risk_score > 0.8:
                recommendations.extend([
                    "즉시 시스템 격리 고려",
                    "포렌식 분석 수행",
                    "인시던트 대응 팀 활성화"
                ])
            elif risk_score > 0.6:
                recommendations.extend([
                    "모니터링 강화",
                    "로그 분석 수행",
                    "보안 정책 재검토"
                ])
        
        except Exception as e:
            logger.error(f"권장사항 생성 오류: {e}")
        
        return recommendations
    
    def _generate_detection_rules(self, result: AttackResult) -> List[str]:
        """탐지 규칙 생성"""
        rules = []
        
        attack_type = getattr(result, 'attack_type', result.attack_id.split('_')[0])
        
        # 공격 유형별 탐지 규칙
        rule_templates = {
            'reconnaissance': [
                "alert tcp any any -> any 14550 (msg:\"MAVLink reconnaissance detected\"; flow:to_server,established; threshold:type limit, track by_src, count 10, seconds 60;)",
                "alert icmp any any -> 10.13.0.0/24 any (msg:\"Network scanning detected\"; threshold:type limit, track by_src, count 20, seconds 30;)"
            ],
            'protocol_tampering': [
                "alert udp any any -> any 14550 (msg:\"Suspicious MAVLink message\"; content:\"|FE|\"; offset:0; depth:1; content:\"|FF|\"; offset:5; depth:1;)",
                "alert tcp any any -> any 14550 (msg:\"GPS spoofing attempt\"; content:\"GPS_RAW_INT\"; nocase;)"
            ],
            'injection': [
                "alert tcp any any -> any 14550 (msg:\"MAVLink injection attempt\"; content:\"COMMAND_LONG\"; nocase; threshold:type limit, track by_src, count 5, seconds 10;)",
                "alert tcp any any -> any 22 (msg:\"SSH injection attempt\"; content:\"bash\"; nocase; flow:to_server,established;)"
            ]
        }
        
        rules.extend(rule_templates.get(attack_type, []))
        
        return rules
    
    def _generate_mitigation_strategies(self, result: AttackResult) -> List[str]:
        """완화 전략 생성"""
        strategies = []
        
        attack_type = getattr(result, 'attack_type', result.attack_id.split('_')[0])
        
        # 공격 유형별 완화 전략
        strategy_templates = {
            'reconnaissance': [
                "네트워크 세그멘테이션 적용",
                "포트 스캔 탐지 및 차단",
                "허용된 IP에서만 접근 가능하도록 화이트리스트 적용"
            ],
            'protocol_tampering': [
                "MAVLink 메시지 암호화",
                "메시지 시퀀스 번호 검증",
                "GPS 신호 검증 메커니즘 구현"
            ],
            'injection': [
                "입력 매개변수 검증 강화",
                "명령어 실행 권한 제한",
                "애플리케이션 방화벽 배치"
            ]
        }
        
        strategies.extend(strategy_templates.get(attack_type, []))
        
        return strategies
    
    # =============================================================================
    # 데이터베이스 관련 메서드들
    # =============================================================================
    
    async def _save_ioc_to_db(self, ioc: IOCIndicator):
        """IOC를 데이터베이스에 저장"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO ioc_indicators 
                (ioc_type, value, confidence, attack_type, first_seen, last_seen, context, threat_level)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                ioc.ioc_type,
                ioc.value,
                ioc.confidence,
                ioc.attack_type,
                ioc.first_seen.isoformat(),
                ioc.last_seen.isoformat(),
                json.dumps(ioc.context),
                ioc.threat_level
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"IOC 데이터베이스 저장 오류: {e}")
    
    async def _save_pattern_to_db(self, pattern: AttackPattern):
        """공격 패턴을 데이터베이스에 저장"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO attack_patterns 
                (pattern_id, name, attack_category, success_rate, avg_execution_time, 
                 ioc_count, detection_rules, mitigation_strategies, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                pattern.pattern_id,
                pattern.name,
                pattern.attack_category,
                pattern.success_rate,
                pattern.avg_execution_time,
                pattern.ioc_count,
                json.dumps(pattern.detection_rules),
                json.dumps(pattern.mitigation_strategies),
                pattern.last_updated.isoformat()
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"패턴 데이터베이스 저장 오류: {e}")
    
    async def _save_analysis_result(self, analysis_result: Dict[str, Any]):
        """분석 결과를 데이터베이스에 저장"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO analysis_results 
                (timestamp, attack_id, analysis_type, confidence, classification, features, recommendation)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                analysis_result['timestamp'],
                analysis_result['attack_id'],
                analysis_result['analysis_type'],
                analysis_result['confidence'],
                analysis_result['classification'],
                analysis_result['features'],
                json.dumps(analysis_result.get('recommendations', []))
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"분석 결과 데이터베이스 저장 오류: {e}")
    
    # =============================================================================
    # 유틸리티 메서드들
    # =============================================================================
    
    def _classify_ioc_type(self, ioc: str) -> str:
        """IOC 타입 분류"""
        if ioc.startswith('http'):
            return 'url'
        elif '.' in ioc and len(ioc.split('.')) == 4:
            return 'ip_address'
        elif ':' in ioc and len(ioc.split(':')) == 2:
            return 'network_endpoint'
        elif ioc.startswith('mavlink_'):
            return 'mavlink_signature'
        elif ioc.startswith('wifi_'):
            return 'wifi_ssid'
        elif ioc.startswith('process_'):
            return 'process_name'
        elif ioc.startswith('file_'):
            return 'file_path'
        else:
            return 'unknown'
    
    def _calculate_confidence(self, result: AttackResult) -> int:
        """신뢰도 계산"""
        base_confidence = 70
        
        if result.success:
            base_confidence += 20
        
        if len(result.iocs) > 3:
            base_confidence += 10
        
        if result.execution_time < 5.0:
            base_confidence += 5
        
        return min(100, base_confidence)
    
    def _determine_threat_level(self, result: AttackResult) -> str:
        """위협 레벨 결정"""
        severity = getattr(result, 'severity', 'medium')
        if hasattr(severity, 'value'):
            severity = severity.value
        
        threat_mapping = {
            'low': 'low',
            'medium': 'medium', 
            'high': 'high',
            'critical': 'critical'
        }
        
        return threat_mapping.get(severity.lower(), 'medium')
    
    def _calculate_avg_confidence(self) -> float:
        """평균 신뢰도 계산"""
        if not self.indicators:
            return 0.0
        
        total_confidence = sum(ind.get('confidence', 0) for ind in self.indicators)
        return total_confidence / len(self.indicators)
    
    def _get_ioc_type_distribution(self) -> Dict[str, int]:
        """IOC 타입별 분포"""
        distribution = defaultdict(int)
        
        for indicator in self.indicators:
            ioc_type = indicator.get('ioc_type', 'unknown')
            distribution[ioc_type] += 1
        
        return dict(distribution)
    
    def _get_recent_timeline(self) -> List[Dict[str, Any]]:
        """최근 타임라인"""
        timeline = []
        
        for indicator in self.indicators[-10:]:  # 최근 10개
            timeline.append({
                'timestamp': indicator.get('timestamp', ''),
                'ioc_type': indicator.get('ioc_type', ''),
                'attack_type': indicator.get('attack_type', ''),
                'confidence': indicator.get('confidence', 0)
            })
        
        return timeline
    
    def _get_database_stats(self) -> Dict[str, int]:
        """데이터베이스 통계"""
        stats = {'iocs': 0, 'patterns': 0, 'analyses': 0}
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM ioc_indicators")
            stats['iocs'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM attack_patterns")
            stats['patterns'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM analysis_results")
            stats['analyses'] = cursor.fetchone()[0]
            
            conn.close()
            
        except Exception as e:
            logger.error(f"데이터베이스 통계 조회 오류: {e}")
        
        return stats
    
    def _get_analysis_summary(self) -> Dict[str, Any]:
        """분석 요약"""
        return {
            'total_analyses': len(self.analysis_queue),
            'real_time_enabled': self.config.get("real_time_analysis", False),
            'average_risk_score': 0.0,  # 계산 로직 추가 필요
            'prediction_accuracy': 0.0  # 계산 로직 추가 필요
        }
    
    def _classify_attack_sophistication(self, result: AttackResult) -> str:
        """공격 정교함 분류"""
        # 간단한 분류 로직
        if result.execution_time < 1.0 and result.success and len(result.iocs) > 5:
            return 'advanced'
        elif result.success and len(result.iocs) > 3:
            return 'intermediate'
        else:
            return 'basic'
    
    def _calculate_correlation_score(self, result1: AttackResult, result2: AttackResult) -> float:
        """두 공격 간의 연관성 점수 계산"""
        score = 0.0
        
        # 시간 근접성
        time_diff = abs((result1.timestamp - result2.timestamp).total_seconds())
        if time_diff < 300:  # 5분 이내
            score += 0.3
        elif time_diff < 1800:  # 30분 이내
            score += 0.2
        
        # IOC 공통성
        common_iocs = set(result1.iocs) & set(result2.iocs)
        if common_iocs:
            score += 0.4 * len(common_iocs) / max(len(result1.iocs), len(result2.iocs))
        
        # 공격 유형 연관성
        type1 = getattr(result1, 'attack_type', result1.attack_id.split('_')[0])
        type2 = getattr(result2, 'attack_type', result2.attack_id.split('_')[0])
        
        related_types = {
            'reconnaissance': ['protocol_tampering', 'injection'],
            'protocol_tampering': ['denial_of_service', 'exfiltration'],
            'injection': ['exfiltration', 'firmware_attacks']
        }
        
        if type2 in related_types.get(type1, []):
            score += 0.3
        
        return min(1.0, score)
    
    def _determine_correlation_type(self, result1: AttackResult, result2: AttackResult) -> str:
        """연관성 타입 결정"""
        # 시간 기반
        time_diff = abs((result1.timestamp - result2.timestamp).total_seconds())
        if time_diff < 300:
            return 'temporal'
        
        # IOC 기반
        common_iocs = set(result1.iocs) & set(result2.iocs)
        if common_iocs:
            return 'ioc_overlap'
        
        # 공격 체인 기반
        type1 = getattr(result1, 'attack_type', result1.attack_id.split('_')[0])
        type2 = getattr(result2, 'attack_type', result2.attack_id.split('_')[0])
        
        attack_chains = {
            'reconnaissance': ['protocol_tampering', 'injection'],
            'protocol_tampering': ['denial_of_service', 'exfiltration']
        }
        
        if type2 in attack_chains.get(type1, []):
            return 'attack_chain'
        
        return 'unknown'
    
    # =============================================================================
    # 방어 시스템 연동
    # =============================================================================
    
    def connect_defense_system(self, defense_system):
        """방어 시스템과 연동"""
        self.defense_system = defense_system
        logger.info("✅ 방어 시스템과 CTI 연동 완료")
    
    async def start_real_time_processing(self):
        """실시간 처리 시작"""
        self.running = True
        logger.info("🚀 CTI 실시간 처리 시작")
        
        while self.running:
            try:
                # 큐에서 분석 대상 가져오기
                if self.analysis_queue:
                    analysis_data = self.analysis_queue.popleft()
                    await self._perform_real_time_analysis(analysis_data)
                
                await asyncio.sleep(1)  # 1초 간격
                
            except Exception as e:
                logger.error(f"실시간 처리 오류: {e}")
                await asyncio.sleep(5)
    
    def stop_real_time_processing(self):
        """실시간 처리 중지"""
        self.running = False
        logger.info("🛑 CTI 실시간 처리 중지")

# =============================================================================
# 기존 SimpleCTI와의 호환성을 위한 별칭
# =============================================================================

SimpleCTI = EnhancedCTI  # 기존 코드 호환성

# =============================================================================
# 테스트베드 통합을 위한 팩토리 함수
# =============================================================================

def create_enhanced_cti(config: Dict[str, Any] = None) -> EnhancedCTI:
    """Enhanced CTI 인스턴스 생성"""
    return EnhancedCTI(config)

def create_compatible_cti(config: Dict[str, Any] = None) -> EnhancedCTI:
    """기존 SimpleCTI 호환 인스턴스 생성"""
    return EnhancedCTI(config)

# =============================================================================
# 메인 실행 (테스트용)
# =============================================================================

async def main():
    """테스트용 메인 함수"""
    print("🧪 Enhanced CTI Integration Module 테스트")
    
    # CTI 시스템 생성
    cti = EnhancedCTI({
        "confidence_threshold": 70,
        "export_format": "json",
        "real_time_analysis": True,
        "database_enabled": True
    })
    
    # 샘플 공격 결과 생성
    sample_result = AttackResult(
        attack_id="test_reconnaissance_001",
        success=True,
        execution_time=2.5,
        severity=AttackSeverity.MEDIUM,
        iocs=["ip:10.13.0.2", "port:14550", "mavlink_msg:24"],
        timestamp=datetime.now(),
        additional_data={
            "network_packets": 150,
            "system_calls": 25,
            "files_accessed": ["config.txt", "telemetry.log"]
        }
    )
    
    # CTI 수집 테스트
    print("📊 CTI 수집 테스트...")
    cti.collect_from_result(sample_result)
    
    # 요약 정보 출력
    summary = cti.get_summary()
    print(f"📈 수집 결과: {summary['total_indicators']}개 지표")
    
    # 내보내기 테스트
    json_file = cti.export_json("test_cti_export.json")
    csv_file = cti.export_csv("test_cti_export.csv")
    
    print(f"📄 내보내기 완료: {json_file}, {csv_file}")
    
    # 실시간 처리 시작 (짧은 테스트)
    print("🚀 실시간 처리 테스트...")
    processing_task = asyncio.create_task(cti.start_real_time_processing())
    
    # 3초 후 중지
    await asyncio.sleep(3)
    cti.stop_real_time_processing()
    
    try:
        await asyncio.wait_for(processing_task, timeout=1.0)
    except asyncio.TimeoutError:
        processing_task.cancel()
    
    print("✅ Enhanced CTI 통합 모듈 테스트 완료")

if __name__ == "__main__":
    asyncio.run(main())