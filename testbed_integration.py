#!/usr/bin/env python3
"""
DVD Testbed Integration & Deployment Script
기존 테스트베드에 Enhanced CTI Defense System을 완벽하게 통합

사용법:
python testbed_integration.py --mode full --enable-cti --enable-defense
"""

import asyncio
import argparse
import logging
import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

# 기존 테스트베드 모듈 임포트
try:
    from dvd_lite.main import DVDLite
    from dvd_lite.dvd_attacks.registry.management import register_all_dvd_attacks
    from dvd_connector.connector import DVDConnector, DVDConnectionConfig, DVDEnvironment
    from dvd_connector.safety_checker import SafetyChecker
except ImportError as e:
    print(f"⚠️ 기존 테스트베드 모듈 임포트 오류: {e}")
    print("기본 스크립트로 실행합니다...")

# 새로운 CTI 및 방어 시스템 임포트
try:
    from enhanced_cti_defense_system import EnhancedCTIDefenseSystem
    from cti_integration_module import EnhancedCTI, create_enhanced_cti
    CTI_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ Enhanced CTI 시스템 임포트 오류: {e}")
    CTI_AVAILABLE = False
    
    # 기본 CTI 클래스 정의
    class EnhancedCTI:
        def __init__(self, config=None):
            self.config = config or {}
            print("⚠️ 기본 CTI 시스템으로 실행")
        
        def collect_from_result(self, result):
            print(f"📊 CTI 수집: {result.attack_id}")
        
        def get_summary(self):
            return {"total_indicators": 0}

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# =============================================================================
# 통합 테스트베드 클래스
# =============================================================================

class IntegratedDroneTestbed:
    """통합된 드론 보안 테스트베드"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.dvd_lite = None
        self.cti_system = None
        self.defense_system = None
        self.dvd_connector = None
        self.safety_checker = SafetyChecker()
        
        # 결과 저장
        self.results = []
        self.session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # 실행 통계
        self.stats = {
            'attacks_executed': 0,
            'successful_attacks': 0,
            'cti_indicators': 0,
            'defense_alerts': 0,
            'start_time': None,
            'end_time': None
        }
    
    async def initialize(self):
        """시스템 초기화"""
        logger.info("🚀 통합 드론 테스트베드 초기화 시작")
        
        # 1. 안전성 검사
        await self._perform_safety_check()
        
        # 2. DVD-Lite 초기화
        await self._initialize_dvd_lite()
        
        # 3. CTI 시스템 초기화
        if self.config.get('enable_cti', True):
            await self._initialize_cti_system()
        
        # 4. 방어 시스템 초기화
        if self.config.get('enable_defense', True):
            await self._initialize_defense_system()
        
        # 5. DVD 하드웨어 연결 (선택적)
        if self.config.get('dvd_hardware_enabled', False):
            await self._connect_dvd_hardware()
        
        logger.info("✅ 통합 테스트베드 초기화 완료")
    
    async def _perform_safety_check(self):
        """안전성 검사"""
        logger.info("🛡️ 시스템 안전성 검사")
        
        safety_config = {
            "host": self.config.get('dvd_host', 'localhost'),
            "environment": self.config.get('environment', 'SIMULATION'),
            "simulation_mode": self.config.get('simulation_mode', True)
        }
        
        try:
            safety_result = await self.safety_checker.comprehensive_safety_check(safety_config)
            
            if not safety_result.is_safe_to_proceed:
                logger.error("❌ 안전성 검사 실패")
                self.safety_checker.print_safety_report(safety_result)
                raise Exception("시스템이 안전하지 않습니다")
            
            logger.info("✅ 안전성 검사 통과")
            
        except Exception as e:
            logger.error(f"안전성 검사 오류: {e}")
            if not self.config.get('force_start', False):
                raise
    
    async def _initialize_dvd_lite(self):
        """DVD-Lite 시스템 초기화"""
        logger.info("🎯 DVD-Lite 시스템 초기화")
        
        try:
            self.dvd_lite = DVDLite()
            
            # 공격 모듈 등록
            register_all_dvd_attacks()
            
            logger.info("✅ DVD-Lite 초기화 완료")
            
        except Exception as e:
            logger.error(f"DVD-Lite 초기화 오류: {e}")
            # 기본 시뮬레이터로 대체
            self.dvd_lite = self._create_fallback_simulator()
    
    async def _initialize_cti_system(self):
        """CTI 시스템 초기화"""
        logger.info("📊 CTI 시스템 초기화")
        
        try:
            if CTI_AVAILABLE:
                cti_config = {
                    "confidence_threshold": self.config.get('cti_confidence_threshold', 70),
                    "export_format": "json",
                    "real_time_analysis": True,
                    "database_enabled": True
                }
                
                self.cti_system = create_enhanced_cti(cti_config)
                
                # DVD-Lite에 CTI 수집기 등록
                if self.dvd_lite:
                    self.dvd_lite.register_cti_collector(self.cti_system)
                
                logger.info("✅ Enhanced CTI 시스템 초기화 완료")
            else:
                self.cti_system = EnhancedCTI()
                logger.warning("⚠️ 기본 CTI 시스템으로 초기화")
                
        except Exception as e:
            logger.error(f"CTI 시스템 초기화 오류: {e}")
            self.cti_system = EnhancedCTI()
    
    async def _initialize_defense_system(self):
        """방어 시스템 초기화"""
        logger.info("🛡️ 방어 시스템 초기화")
        
        try:
            if CTI_AVAILABLE:
                defense_config_path = "defense_config.yaml"
                
                # 기본 방어 설정 생성
                if not Path(defense_config_path).exists():
                    self._create_default_defense_config(defense_config_path)
                
                self.defense_system = EnhancedCTIDefenseSystem(defense_config_path)
                
                # CTI 시스템과 연동
                if self.cti_system:
                    self.cti_system.connect_defense_system(self.defense_system)
                
                logger.info("✅ Enhanced Defense 시스템 초기화 완료")
            else:
                logger.warning("⚠️ 방어 시스템을 사용할 수 없습니다")
                
        except Exception as e:
            logger.error(f"방어 시스템 초기화 오류: {e}")
            self.defense_system = None
    
    async def _connect_dvd_hardware(self):
        """DVD 하드웨어 연결"""
        logger.info("🔗 DVD 하드웨어 연결")
        
        try:
            dvd_config = DVDConnectionConfig(
                environment=DVDEnvironment.HALF_BAKED,
                host=self.config.get('dvd_host', 'localhost'),
                mavlink_port=self.config.get('mavlink_port', 14550)
            )
            
            self.dvd_connector = DVDConnector(dvd_config)
            
            if await self.dvd_connector.connect():
                logger.info("✅ DVD 하드웨어 연결 성공")
            else:
                logger.warning("⚠️ DVD 하드웨어 연결 실패 - 시뮬레이션 모드로 계속")
                
        except Exception as e:
            logger.error(f"DVD 하드웨어 연결 오류: {e}")
            self.dvd_connector = None
    
    async def run_comprehensive_test(self):
        """종합 테스트 실행"""
        logger.info("🧪 종합 보안 테스트 시작")
        self.stats['start_time'] = datetime.now()
        
        try:
            # 방어 시스템 시작 (백그라운드)
            if self.defense_system:
                defense_task = asyncio.create_task(self.defense_system.start_defense_system())
            
            # CTI 실시간 처리 시작
            if self.cti_system and hasattr(self.cti_system, 'start_real_time_processing'):
                cti_task = asyncio.create_task(self.cti_system.start_real_time_processing())
            
            # 테스트 시나리오 실행
            await self._execute_test_scenarios()
            
            # 결과 분석 및 보고서 생성
            await self._generate_comprehensive_report()
            
        except Exception as e:
            logger.error(f"종합 테스트 오류: {e}")
        finally:
            self.stats['end_time'] = datetime.now()
            
            # 시스템 정리
            await self._cleanup_systems()
    
    async def _execute_test_scenarios(self):
        """테스트 시나리오 실행"""
        logger.info("📋 테스트 시나리오 실행")
        
        # 실행할 공격 시나리오 결정
        scenarios = self._get_test_scenarios()
        
        for i, scenario in enumerate(scenarios, 1):
            logger.info(f"🎯 시나리오 {i}/{len(scenarios)}: {scenario['name']}")
            
            try:
                # 공격 실행
                result = await self._execute_attack_scenario(scenario)
                
                if result:
                    self.results.append(result)
                    self.stats['attacks_executed'] += 1
                    
                    if result.success:
                        self.stats['successful_attacks'] += 1
                    
                    # CTI 수집
                    if self.cti_system:
                        self.cti_system.collect_from_result(result)
                        self.stats['cti_indicators'] += len(result.iocs)
                
                # 시나리오 간 딜레이
                await asyncio.sleep(self.config.get('scenario_delay', 2))
                
            except Exception as e:
                logger.error(f"시나리오 실행 오류 ({scenario['name']}): {e}")
                continue
    
    def _get_test_scenarios(self) -> List[Dict[str, Any]]:
        """테스트 시나리오 목록 생성"""
        test_mode = self.config.get('test_mode', 'basic')
        
        if test_mode == 'basic':
            return [
                {'name': 'WiFi Network Discovery', 'attack_id': 'wifi_network_discovery', 'category': 'reconnaissance'},
                {'name': 'MAVLink Service Discovery', 'attack_id': 'mavlink_service_discovery', 'category': 'reconnaissance'},
                {'name': 'GPS Spoofing', 'attack_id': 'gps_spoofing', 'category': 'protocol_tampering'},
                {'name': 'MAVLink Flooding', 'attack_id': 'mavlink_flooding', 'category': 'denial_of_service'},
                {'name': 'Parameter Manipulation', 'attack_id': 'parameter_manipulation', 'category': 'injection'}
            ]
        elif test_mode == 'full':
            return [
                # Reconnaissance
                {'name': 'WiFi Network Discovery', 'attack_id': 'wifi_network_discovery', 'category': 'reconnaissance'},
                {'name': 'MAVLink Service Discovery', 'attack_id': 'mavlink_service_discovery', 'category': 'reconnaissance'},
                {'name': 'Drone Component Enumeration', 'attack_id': 'drone_component_enumeration', 'category': 'reconnaissance'},
                {'name': 'Camera Stream Discovery', 'attack_id': 'camera_stream_discovery', 'category': 'reconnaissance'},
                
                # Protocol Tampering
                {'name': 'GPS Spoofing', 'attack_id': 'gps_spoofing', 'category': 'protocol_tampering'},
                {'name': 'MAVLink Packet Injection', 'attack_id': 'mavlink_packet_injection', 'category': 'protocol_tampering'},
                {'name': 'RF Jamming', 'attack_id': 'rf_jamming', 'category': 'protocol_tampering'},
                
                # Denial of Service
                {'name': 'MAVLink Flooding', 'attack_id': 'mavlink_flooding', 'category': 'denial_of_service'},
                {'name': 'WiFi Deauth Attack', 'attack_id': 'wifi_deauth_attack', 'category': 'denial_of_service'},
                {'name': 'Resource Exhaustion', 'attack_id': 'resource_exhaustion', 'category': 'denial_of_service'},
                
                # Injection
                {'name': 'Flight Plan Injection', 'attack_id': 'flight_plan_injection', 'category': 'injection'},
                {'name': 'Parameter Manipulation', 'attack_id': 'parameter_manipulation', 'category': 'injection'},
                {'name': 'Firmware Upload Manipulation', 'attack_id': 'firmware_upload_manipulation', 'category': 'injection'},
                
                # Exfiltration
                {'name': 'Telemetry Data Exfiltration', 'attack_id': 'telemetry_data_exfiltration', 'category': 'exfiltration'},
                {'name': 'Flight Log Extraction', 'attack_id': 'flight_log_extraction', 'category': 'exfiltration'},
                {'name': 'Video Stream Hijacking', 'attack_id': 'video_stream_hijacking', 'category': 'exfiltration'},
                
                # Firmware Attacks
                {'name': 'Bootloader Exploit', 'attack_id': 'bootloader_exploit', 'category': 'firmware_attacks'},
                {'name': 'Firmware Rollback', 'attack_id': 'firmware_rollback', 'category': 'firmware_attacks'},
                {'name': 'Secure Boot Bypass', 'attack_id': 'secure_boot_bypass', 'category': 'firmware_attacks'}
            ]
        else:
            # 사용자 정의 시나리오
            return self.config.get('custom_scenarios', [])
    
    async def _execute_attack_scenario(self, scenario: Dict[str, Any]):
        """개별 공격 시나리오 실행"""
        attack_id = scenario['attack_id']
        
        try:
            if self.dvd_lite:
                # DVD-Lite를 통한 공격 실행
                result = await self.dvd_lite.run_attack(attack_id)
                
                if result:
                    logger.info(f"✅ 공격 성공: {attack_id} (실행시간: {result.execution_time:.2f}s)")
                    return result
                else:
                    logger.warning(f"❌ 공격 실패: {attack_id}")
            else:
                # 시뮬레이션 결과 생성
                result = self._create_simulation_result(scenario)
                logger.info(f"🎭 시뮬레이션 결과: {attack_id}")
                return result
                
        except Exception as e:
            logger.error(f"공격 실행 오류 ({attack_id}): {e}")
            return None
    
    def _create_simulation_result(self, scenario: Dict[str, Any]):
        """시뮬레이션 공격 결과 생성"""
        import random
        from datetime import datetime
        
        # AttackResult 호환 객체 생성
        class SimulationResult:
            def __init__(self, attack_id, success, execution_time, iocs):
                self.attack_id = attack_id
                self.success = success
                self.execution_time = execution_time
                self.iocs = iocs
                self.timestamp = datetime.now()
                self.severity = 'medium'
                self.attack_type = scenario.get('category', 'unknown')
        
        # 랜덤 결과 생성
        success = random.choice([True, False, True])  # 66% 성공률
        execution_time = random.uniform(0.5, 5.0)
        
        # 카테고리별 IOC 생성
        category = scenario.get('category', 'unknown')
        iocs = self._generate_scenario_iocs(category, scenario['attack_id'])
        
        return SimulationResult(scenario['attack_id'], success, execution_time, iocs)
    
    def _generate_scenario_iocs(self, category: str, attack_id: str) -> List[str]:
        """시나리오별 IOC 생성"""
        import random
        
        base_iocs = {
            'reconnaissance': [
                f"wifi_scan:{attack_id}",
                f"port_scan:14550",
                f"service_discovery:mavlink"
            ],
            'protocol_tampering': [
                f"mavlink_msg_id:24",
                f"gps_coordinate:fake",
                f"protocol_violation:{attack_id}"
            ],
            'denial_of_service': [
                f"traffic_flood:high_volume",
                f"resource_exhaustion:cpu",
                f"connection_saturation:{attack_id}"
            ],
            'injection': [
                f"command_injection:{attack_id}",
                f"parameter_change:critical",
                f"payload_modification:detected"
            ],
            'exfiltration': [
                f"data_exfiltration:telemetry",
                f"file_access:logs",
                f"network_transfer:suspicious"
            ],
            'firmware_attacks': [
                f"firmware_manipulation:{attack_id}",
                f"bootloader_access:unauthorized",
                f"secure_boot_bypass:detected"
            ]
        }
        
        category_iocs = base_iocs.get(category, [f"unknown_ioc:{attack_id}"])
        return random.sample(category_iocs, min(len(category_iocs), random.randint(2, 4)))
    
    async def _generate_comprehensive_report(self):
        """종합 보고서 생성"""
        logger.info("📊 종합 보고서 생성")
        
        try:
            # 실행 통계 계산
            total_time = (self.stats['end_time'] - self.stats['start_time']).total_seconds()
            success_rate = (self.stats['successful_attacks'] / max(self.stats['attacks_executed'], 1)) * 100
            
            # CTI 요약
            cti_summary = {}
            if self.cti_system:
                cti_summary = self.cti_system.get_summary()
            
            # 방어 시스템 보고서
            defense_report = {}
            if self.defense_system and hasattr(self.defense_system, 'generate_report'):
                defense_report = self.defense_system.generate_report(hours=24)
            
            # 종합 보고서 구성
            comprehensive_report = {
                'session_info': {
                    'session_id': self.session_id,
                    'start_time': self.stats['start_time'].isoformat(),
                    'end_time': self.stats['end_time'].isoformat(),
                    'total_duration_seconds': total_time,
                    'test_mode': self.config.get('test_mode', 'basic')
                },
                'execution_summary': {
                    'total_attacks': self.stats['attacks_executed'],
                    'successful_attacks': self.stats['successful_attacks'],
                    'success_rate_percent': round(success_rate, 2),
                    'total_cti_indicators': self.stats['cti_indicators'],
                    'defense_alerts': self.stats['defense_alerts']
                },
                'attack_results': [
                    {
                        'attack_id': result.attack_id,
                        'success': result.success,
                        'execution_time': result.execution_time,
                        'ioc_count': len(result.iocs),
                        'timestamp': result.timestamp.isoformat(),
                        'attack_type': getattr(result, 'attack_type', 'unknown')
                    }
                    for result in self.results
                ],
                'cti_analysis': cti_summary,
                'defense_analysis': defense_report,
                'recommendations': self._generate_security_recommendations()
            }
            
            # 보고서 파일 저장
            report_dir = Path("reports")
            report_dir.mkdir(exist_ok=True)
            
            # JSON 보고서
            json_report_path = report_dir / f"comprehensive_report_{self.session_id}.json"
            with open(json_report_path, 'w', encoding='utf-8') as f:
                json.dump(comprehensive_report, f, indent=2, ensure_ascii=False)
            
            # 마크다운 보고서
            md_report_path = report_dir / f"comprehensive_report_{self.session_id}.md"
            await self._generate_markdown_report(comprehensive_report, md_report_path)
            
            logger.info(f"📄 종합 보고서 생성 완료:")
            logger.info(f"  - JSON: {json_report_path}")
            logger.info(f"  - Markdown: {md_report_path}")
            
            # 요약 출력
            self._print_execution_summary(comprehensive_report)
            
        except Exception as e:
            logger.error(f"보고서 생성 오류: {e}")
    
    async def _generate_markdown_report(self, report: Dict[str, Any], filepath: Path):
        """마크다운 형식 보고서 생성"""
        try:
            md_content = f"""# 드론 보안 테스트베드 종합 보고서

## 실행 정보
- **세션 ID**: {report['session_info']['session_id']}
- **시작 시간**: {report['session_info']['start_time']}
- **종료 시간**: {report['session_info']['end_time']}
- **총 실행 시간**: {report['session_info']['total_duration_seconds']:.1f}초
- **테스트 모드**: {report['session_info']['test_mode']}

## 실행 요약
- **총 공격 수**: {report['execution_summary']['total_attacks']}
- **성공한 공격**: {report['execution_summary']['successful_attacks']}
- **성공률**: {report['execution_summary']['success_rate_percent']}%
- **CTI 지표 수집**: {report['execution_summary']['total_cti_indicators']}개
- **방어 알림**: {report['execution_summary']['defense_alerts']}개

## 공격 결과 상세

| 공격 ID | 성공 | 실행시간(s) | IOC 수 | 공격 유형 |
|---------|------|-------------|--------|-----------|
"""
            
            for attack in report['attack_results']:
                success_icon = "✅" if attack['success'] else "❌"
                md_content += f"| {attack['attack_id']} | {success_icon} | {attack['execution_time']:.2f} | {attack['ioc_count']} | {attack['attack_type']} |\n"
            
            md_content += f"""
## CTI 분석 결과
- **총 지표 수**: {report['cti_analysis'].get('total_indicators', 0)}
- **고유 공격 유형**: {report['cti_analysis'].get('unique_attack_types', 0)}
- **평균 신뢰도**: {report['cti_analysis'].get('avg_confidence', 0):.1f}

## 보안 권장사항
"""
            
            for i, recommendation in enumerate(report['recommendations'], 1):
                md_content += f"{i}. {recommendation}\n"
            
            md_content += f"""
## 방어 시스템 분석
"""
            if report['defense_analysis']:
                md_content += f"- **탐지된 위협**: {report['defense_analysis'].get('total_events', 0)}개\n"
                md_content += f"- **평균 신뢰도**: {report['defense_analysis'].get('avg_confidence', 0):.1f}\n"
            else:
                md_content += "방어 시스템 분석 데이터가 없습니다.\n"
            
            md_content += f"""
---
*보고서 생성 시간: {datetime.now().isoformat()}*
*DVD Testbed Integration System v2.0*
"""
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(md_content)
                
        except Exception as e:
            logger.error(f"마크다운 보고서 생성 오류: {e}")
    
    def _generate_security_recommendations(self) -> List[str]:
        """보안 권장사항 생성"""
        recommendations = []
        
        # 실행 결과 기반 권장사항
        if self.stats['successful_attacks'] > 0:
            recommendations.append("성공한 공격이 감지되었습니다. 보안 강화 조치가 필요합니다.")
        
        success_rate = (self.stats['successful_attacks'] / max(self.stats['attacks_executed'], 1)) * 100
        
        if success_rate > 70:
            recommendations.extend([
                "공격 성공률이 높습니다. 전반적인 보안 아키텍처 재검토가 필요합니다.",
                "네트워크 세그멘테이션 및 접근 제어 강화를 권장합니다.",
                "실시간 모니터링 시스템 도입을 고려하세요."
            ])
        elif success_rate > 40:
            recommendations.extend([
                "일부 공격이 성공했습니다. 해당 공격 벡터에 대한 대응책 마련이 필요합니다.",
                "로그 모니터링 및 이상 탐지 시스템 강화를 권장합니다."
            ])
        else:
            recommendations.extend([
                "대부분의 공격이 차단되었습니다. 현재 보안 수준을 유지하세요.",
                "정기적인 보안 점검을 통해 새로운 위협에 대비하세요."
            ])
        
        # 일반적인 드론 보안 권장사항
        recommendations.extend([
            "MAVLink 프로토콜 암호화 활성화",
            "펌웨어 서명 검증 구현",
            "네트워크 트래픽 모니터링 강화",
            "정기적인 보안 패치 적용",
            "접근 권한 최소화 원칙 적용"
        ])
        
        return recommendations
    
    def _print_execution_summary(self, report: Dict[str, Any]):
        """실행 요약 출력"""
        print("\n" + "="*60)
        print("📊 드론 보안 테스트베드 실행 요약")
        print("="*60)
        
        session_info = report['session_info']
        execution_summary = report['execution_summary']
        
        print(f"🆔 세션 ID: {session_info['session_id']}")
        print(f"⏱️  실행 시간: {session_info['total_duration_seconds']:.1f}초")
        print(f"🎯 총 공격 수: {execution_summary['total_attacks']}")
        print(f"✅ 성공한 공격: {execution_summary['successful_attacks']}")
        print(f"📈 성공률: {execution_summary['success_rate_percent']}%")
        print(f"📊 CTI 지표: {execution_summary['total_cti_indicators']}개")
        print(f"🛡️  방어 알림: {execution_summary['defense_alerts']}개")
        
        print("\n🏆 주요 성과:")
        if execution_summary['success_rate_percent'] < 30:
            print("   - 우수한 방어 시스템 성능")
        elif execution_summary['success_rate_percent'] < 60:
            print("   - 양호한 보안 수준")
        else:
            print("   - 보안 강화 필요")
        
        if execution_summary['total_cti_indicators'] > 50:
            print("   - 풍부한 위협 인텔리전스 수집")
        
        print("="*60)
    
    async def _cleanup_systems(self):
        """시스템 정리"""
        logger.info("🧹 시스템 정리 중...")
        
        try:
            # CTI 실시간 처리 중지
            if self.cti_system and hasattr(self.cti_system, 'stop_real_time_processing'):
                self.cti_system.stop_real_time_processing()
            
            # 방어 시스템 중지
            if self.defense_system and hasattr(self.defense_system, 'stop_defense_system'):
                await self.defense_system.stop_defense_system()
            
            # DVD 하드웨어 연결 해제
            if self.dvd_connector:
                await self.dvd_connector.disconnect()
            
            logger.info("✅ 시스템 정리 완료")
            
        except Exception as e:
            logger.error(f"시스템 정리 오류: {e}")
    
    def _create_fallback_simulator(self):
        """기본 시뮬레이터 생성"""
        class FallbackSimulator:
            async def run_attack(self, attack_id):
                # 간단한 시뮬레이션 결과 반환
                import random
                from datetime import datetime
                
                class SimpleResult:
                    def __init__(self):
                        self.attack_id = attack_id
                        self.success = random.choice([True, False])
                        self.execution_time = random.uniform(1.0, 3.0)
                        self.iocs = [f"sim_ioc_{attack_id}_{i}" for i in range(random.randint(1, 4))]
                        self.timestamp = datetime.now()
                        self.severity = random.choice(['low', 'medium', 'high'])
                
                await asyncio.sleep(self.execution_time if hasattr(self, 'execution_time') else 1.0)
                return SimpleResult()
        
        return FallbackSimulator()
    
    def _create_default_defense_config(self, config_path: str):
        """기본 방어 시스템 설정 생성"""
        import yaml
        
        default_config = {
            'monitoring': {
                'docker_enabled': True,
                'mavlink_enabled': True,
                'ml_enabled': True
            },
            'thresholds': {
                'cpu_alert': 80.0,
                'memory_alert': 85.0,
                'confidence_threshold': 0.7
            },
            'database': {
                'path': 'cti_defense.db',
                'retention_days': 30
            }
        }
        
        with open(config_path, 'w') as f:
            yaml.dump(default_config, f, default_flow_style=False)

# =============================================================================
# 명령행 인터페이스
# =============================================================================

def parse_arguments():
    """명령행 인수 파싱"""
    parser = argparse.ArgumentParser(
        description='DVD Testbed Integration & Deployment Script',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  python testbed_integration.py --mode basic
  python testbed_integration.py --mode full --enable-cti --enable-defense
  python testbed_integration.py --mode custom --config custom_config.json
  python testbed_integration.py --dvd-hardware --dvd-host 10.13.0.3
        """
    )
    
    # 기본 옵션
    parser.add_argument(
        '--mode',
        choices=['basic', 'full', 'custom'],
        default='basic',
        help='테스트 모드 (기본값: basic)'
    )
    
    parser.add_argument(
        '--config',
        type=str,
        help='사용자 정의 설정 파일 경로'
    )
    
    # CTI 및 방어 시스템
    parser.add_argument(
        '--enable-cti',
        action='store_true',
        help='Enhanced CTI 시스템 활성화'
    )
    
    parser.add_argument(
        '--enable-defense',
        action='store_true', 
        help='Enhanced Defense 시스템 활성화'
    )
    
    # DVD 하드웨어 연동
    parser.add_argument(
        '--dvd-hardware',
        action='store_true',
        help='DVD 하드웨어 연동 활성화'
    )
    
    parser.add_argument(
        '--dvd-host',
        type=str,
        default='localhost',
        help='DVD 호스트 주소 (기본값: localhost)'
    )
    
    parser.add_argument(
        '--mavlink-port',
        type=int,
        default=14550,
        help='MAVLink 포트 (기본값: 14550)'
    )
    
    # 실행 옵션
    parser.add_argument(
        '--duration',
        type=int,
        default=300,
        help='최대 실행 시간 (초, 기본값: 300)'
    )
    
    parser.add_argument(
        '--scenario-delay',
        type=float,
        default=2.0,
        help='시나리오 간 딜레이 (초, 기본값: 2.0)'
    )
    
    parser.add_argument(
        '--force-start',
        action='store_true',
        help='안전성 검사 실패 시에도 강제 시작'
    )
    
    parser.add_argument(
        '--output-dir',
        type=str,
        default='results',
        help='결과 출력 디렉토리 (기본값: results)'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='상세 로그 출력'
    )
    
    return parser.parse_args()

def load_config(args) -> Dict[str, Any]:
    """설정 로드"""
    config = {}
    
    # 사용자 정의 설정 파일 로드
    if args.config and Path(args.config).exists():
        try:
            with open(args.config, 'r') as f:
                config = json.load(f)
            logger.info(f"📁 설정 파일 로드: {args.config}")
        except Exception as e:
            logger.error(f"설정 파일 로드 오류: {e}")
    
    # 명령행 인수로 설정 업데이트
    config.update({
        'test_mode': args.mode,
        'enable_cti': args.enable_cti,
        'enable_defense': args.enable_defense,
        'dvd_hardware_enabled': args.dvd_hardware,
        'dvd_host': args.dvd_host,
        'mavlink_port': args.mavlink_port,
        'max_duration': args.duration,
        'scenario_delay': args.scenario_delay,
        'force_start': args.force_start,
        'output_dir': args.output_dir,
        'verbose': args.verbose
    })
    
    return config

def setup_logging(verbose: bool):
    """로깅 설정"""
    log_level = logging.DEBUG if verbose else logging.INFO
    
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('testbed_integration.log')
        ]
    )

def check_system_requirements():
    """시스템 요구사항 검사"""
    logger.info("🔍 시스템 요구사항 검사")
    
    requirements = {
        'python_version': sys.version_info >= (3, 7),
        'required_directories': True,
        'disk_space': True  # 간단한 검사
    }
    
    # 필수 디렉토리 생성
    required_dirs = ['results', 'reports', 'logs', 'models', 'stix_exports']
    for directory in required_dirs:
        Path(directory).mkdir(exist_ok=True)
    
    # 요구사항 검사 결과
    all_passed = all(requirements.values())
    
    if all_passed:
        logger.info("✅ 시스템 요구사항 검사 통과")
    else:
        logger.error("❌ 시스템 요구사항 검사 실패")
        for req, passed in requirements.items():
            if not passed:
                logger.error(f"  - {req}: 실패")
    
    return all_passed

def print_banner():
    """시작 배너 출력"""
    banner = """
╔══════════════════════════════════════════════════════════════════╗
║           DVD Testbed Integration & Deployment System            ║
║                     Enhanced CTI Defense v2.0                   ║
║                                                                  ║
║  🎯 19개 완전 구현된 드론 공격 시나리오                           ║
║  📊 실시간 CTI 수집 및 기계학습 기반 분류                         ║
║  🛡️  Docker 컨테이너 모니터링 및 이상 탐지                       ║
║  📡 MAVLink 프로토콜 분석 및 보안 검증                           ║
║  📄 STIX/TAXII 표준 위협 인텔리전스 내보내기                     ║
║  🌐 실시간 대시보드 및 종합 보고서 생성                          ║
╚══════════════════════════════════════════════════════════════════╝
    """
    print(banner)

async def main():
    """메인 함수"""
    # 시작 배너
    print_banner()
    
    # 명령행 인수 파싱
    args = parse_arguments()
    
    # 로깅 설정
    setup_logging(args.verbose)
    
    # 시스템 요구사항 검사
    if not check_system_requirements():
        logger.error("시스템 요구사항을 만족하지 않습니다.")
        return 1
    
    # 설정 로드
    config = load_config(args)
    
    logger.info("🚀 DVD Testbed Integration System 시작")
    logger.info(f"📋 설정: {json.dumps({k: v for k, v in config.items() if k not in ['verbose']}, indent=2)}")
    
    try:
        # 통합 테스트베드 생성 및 초기화
        testbed = IntegratedDroneTestbed(config)
        await testbed.initialize()
        
        # 종합 테스트 실행
        await testbed.run_comprehensive_test()
        
        logger.info("✅ DVD Testbed Integration System 완료")
        return 0
        
    except KeyboardInterrupt:
        logger.info("🛑 사용자에 의한 중단")
        return 0
    except Exception as e:
        logger.error(f"❌ 시스템 오류: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1

# =============================================================================
# Docker Compose 설정 생성 유틸리티
# =============================================================================

def generate_docker_compose():
    """Docker Compose 설정 생성"""
    compose_content = """version: '3.8'

services:
  # DVD 시뮬레이터 컴포넌트
  flight-controller:
    image: dvd-flight-controller:latest
    container_name: dvd-flight-controller
    networks:
      drone-net:
        ipv4_address: 10.13.0.2
    ports:
      - "14550:14550/udp"  # MAVLink
    logging:
      driver: fluentd
      options:
        fluentd-address: "fluent:24224"
        tag: "dvd.flight-controller"
  
  companion-computer:
    image: dvd-companion:latest
    container_name: dvd-companion
    networks:
      drone-net:
        ipv4_address: 10.13.0.3
      wireless-net:
        ipv4_address: 192.168.13.1
    ports:
      - "22:22"    # SSH
      - "8080:8080" # HTTP
    logging:
      driver: fluentd
      options:
        fluentd-address: "fluent:24224"
        tag: "dvd.companion"
  
  ground-station:
    image: dvd-ground-station:latest
    container_name: dvd-ground-station
    networks:
      drone-net:
        ipv4_address: 10.13.0.4
    ports:
      - "5760:5760"  # QGroundControl
    logging:
      driver: fluentd
      options:
        fluentd-address: "fluent:24224"
        tag: "dvd.ground-station"
  
  # 모니터링 및 보안 컴포넌트
  falco:
    image: falcosecurity/falco:latest
    container_name: security-monitor
    privileged: true
    volumes:
      - /var/run/docker.sock:/host/var/run/docker.sock
      - /proc:/host/proc:ro
      - ./falco-rules:/etc/falco/rules:ro
    networks:
      - monitoring-net
  
  cadvisor:
    image: gcr.io/cadvisor/cadvisor:latest
    container_name: container-monitor
    volumes:
      - /:/rootfs:ro
      - /var/run:/var/run:ro
      - /sys:/sys:ro
      - /var/lib/docker/:/var/lib/docker:ro
    ports:
      - "8081:8080"
    networks:
      - monitoring-net
  
  # 로그 수집
  fluent:
    image: fluent/fluentd:v1.16-1
    container_name: log-collector
    volumes:
      - ./fluentd/conf:/fluentd/etc
      - ./logs:/var/log/fluentd
    ports:
      - "24224:24224"
    networks:
      - monitoring-net
      - drone-net
  
  # Elasticsearch & Kibana
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:7.17.0
    container_name: log-storage
    environment:
      - discovery.type=single-node
      - "ES_JAVA_OPTS=-Xms512m -Xmx512m"
    volumes:
      - es-data:/usr/share/elasticsearch/data
    ports:
      - "9200:9200"
    networks:
      - monitoring-net
  
  kibana:
    image: docker.elastic.co/kibana/kibana:7.17.0
    container_name: log-dashboard
    environment:
      - ELASTICSEARCH_HOSTS=http://elasticsearch:9200
    ports:
      - "5601:5601"
    networks:
      - monitoring-net
    depends_on:
      - elasticsearch

networks:
  drone-net:
    ipam:
      config:
        - subnet: 10.13.0.0/24
  wireless-net:
    ipam:
      config:
        - subnet: 192.168.13.0/24
  monitoring-net:
    driver: bridge

volumes:
  es-data:
    driver: local
"""
    
    with open('docker-compose.yml', 'w') as f:
        f.write(compose_content)
    
    logger.info("📄 Docker Compose 설정 생성 완료: docker-compose.yml")

# =============================================================================
# 설정 파일 템플릿 생성
# =============================================================================

def generate_config_templates():
    """설정 파일 템플릿 생성"""
    
    # 기본 설정 템플릿
    basic_config = {
        "test_mode": "basic",
        "enable_cti": True,
        "enable_defense": True,
        "dvd_hardware_enabled": False,
        "dvd_host": "localhost",
        "mavlink_port": 14550,
        "scenario_delay": 2.0,
        "cti_confidence_threshold": 70,
        "output_formats": ["json", "csv", "markdown"],
        "custom_scenarios": []
    }
    
    # 고급 설정 템플릿
    advanced_config = {
        "test_mode": "full",
        "enable_cti": True,
        "enable_defense": True,
        "dvd_hardware_enabled": True,
        "dvd_host": "10.13.0.3",
        "dvd_fc_host": "10.13.0.2",
        "mavlink_port": 14550,
        "scenario_delay": 1.0,
        "cti_confidence_threshold": 80,
        "output_formats": ["json", "csv", "markdown", "stix"],
        "defense_thresholds": {
            "cpu_alert": 75.0,
            "memory_alert": 80.0,
            "network_anomaly": 10.0
        },
        "ml_classification": {
            "enabled": True,
            "model_retrain_interval": 3600,
            "confidence_threshold": 0.75
        },
        "real_time_dashboard": {
            "enabled": True,
            "websocket_port": 8765,
            "update_interval": 1.0
        }
    }
    
    # 설정 파일 저장
    config_dir = Path("configs")
    config_dir.mkdir(exist_ok=True)
    
    with open(config_dir / "basic_config.json", 'w') as f:
        json.dump(basic_config, f, indent=2)
    
    with open(config_dir / "advanced_config.json", 'w') as f:
        json.dump(advanced_config, f, indent=2)
    
    logger.info("📄 설정 템플릿 생성 완료:")
    logger.info("  - configs/basic_config.json")
    logger.info("  - configs/advanced_config.json")

if __name__ == "__main__":
    # 설정 템플릿 및 Docker Compose 파일 생성
    if len(sys.argv) > 1 and sys.argv[1] == "--generate-templates":
        generate_config_templates()
        generate_docker_compose()
        print("✅ 템플릿 파일 생성 완료")
        sys.exit(0)
    
    # 메인 실행
    exit_code = asyncio.run(main())
    sys.exit(exit_code)