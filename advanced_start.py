#!/usr/bin/env python3
"""
DVD 공격 시나리오 빠른 실행 스크립트 (DVD 연동 버전)
Damn Vulnerable Drone과의 완전한 연동을 지원하는 고급 실행 스크립트
"""

import asyncio
import sys
import logging
import argparse
import json
from pathlib import Path
from typing import List, Dict, Any, Optional

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from dvd_lite.main import DVDLite
    from dvd_lite.cti import SimpleCTI
    
    # DVD 연결 모듈
    from dvd_connector.connector import DVDConnector, DVDEnvironment, SafetyChecker
    
    # DVD 공격 모듈
    from dvd_lite.dvd_attacks import (
        register_all_dvd_attacks, 
        get_attacks_by_tactic, 
        get_attacks_by_difficulty,
        get_attacks_by_flight_state,
        get_attack_info,
        DVDAttackTactic,
        DVDFlightState,
        AttackDifficulty,
        AttackStatus
    )
    
    DVD_CONNECTOR_AVAILABLE = True
    
except ImportError as e:
    print(f"⚠️  일부 모듈 import 실패: {e}")
    DVD_CONNECTOR_AVAILABLE = False
    
    # 기본 모듈만 사용
    try:
        from dvd_lite.main import DVDLite
        from dvd_lite.attacks import register_all_attacks
    except ImportError:
        print("❌ 기본 모듈 import 실패")
        sys.exit(1)

def print_banner():
    """배너 출력"""
    banner = """
╔════════════════════════════════════════════════════════════════════════╗
║                    DVD Attack Scenarios (Advanced)                     ║
║              Damn Vulnerable Drone 완전 연동 버전                      ║
║                                                                        ║
║  🎯 실제 DVD 환경과의 연동                                              ║
║  🔗 MAVLink, WiFi, 컴패니언 컴퓨터 연결                                  ║
║  🛡️  안전성 검사 및 타겟 검증                                           ║
║  📊 실시간 CTI 수집 및 분석                                             ║
║  🚁 SITL/Docker/실제 하드웨어 지원                                      ║
╚════════════════════════════════════════════════════════════════════════╝
"""
    print(banner)

class DVDAdvancedRunner:
    """DVD 고급 실행기"""
    
    def __init__(self, config_path: str = "dvd_config.json"):
        self.config_path = config_path
        self.dvd_environment = None
        self.dvd_connector = None
        self.dvd_lite = None
        self.cti_collector = None
        self.safety_checker = SafetyChecker()
        
    async def initialize(self, environment_type: str = "auto") -> bool:
        """시스템 초기화"""
        print("🔧 DVD 고급 실행기 초기화 중...")
        
        try:
            # 1. DVD 환경 설정
            if DVD_CONNECTOR_AVAILABLE:
                await self._setup_dvd_environment(environment_type)
            
            # 2. DVD-Lite 인스턴스 생성
            self.dvd_lite = DVDLite()
            
            # 3. CTI 수집기 설정
            self.cti_collector = SimpleCTI()
            self.dvd_lite.register_cti_collector(self.cti_collector)
            
            # 4. 공격 모듈 등록
            if DVD_CONNECTOR_AVAILABLE:
                registered_attacks = register_all_dvd_attacks()
                print(f"✅ DVD 공격 모듈 등록: {len(registered_attacks)}개")
            else:
                registered_attacks = register_all_attacks(self.dvd_lite)
                print(f"✅ 기본 공격 모듈 등록: {len(registered_attacks)}개")
            
            return True
            
        except Exception as e:
            logger.error(f"초기화 실패: {e}")
            return False
    
    async def _setup_dvd_environment(self, environment_type: str):
        """DVD 환경 설정"""
        print(f"🚁 DVD 환경 설정 중: {environment_type}")
        
        # 환경 타입 자동 감지
        if environment_type == "auto":
            environment_type = await self._detect_environment_type()
        
        # DVD 환경 생성
        self.dvd_environment = DVDEnvironment(self.config_path)
        
        # 설정 업데이트
        await self._update_environment_config(environment_type)
        
        # DVD 커넥터 생성
        self.dvd_connector = DVDConnector(self.dvd_environment)
        
        # 연결 초기화
        if await self.dvd_connector.initialize():
            print("✅ DVD 환경 연결 성공")
        else:
            print("⚠️  DVD 환경 연결 실패 - 시뮬레이션 모드로 진행")
    
    async def _detect_environment_type(self) -> str:
        """환경 타입 자동 감지"""
        print("🔍 DVD 환경 자동 감지 중...")
        
        # Docker 환경 확인
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "ps", "--format", "{{.Names}}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            
            if "dvd" in stdout.decode().lower():
                print("🐳 Docker DVD 환경 감지됨")
                return "docker"
        except:
            pass
        
        # ArduPilot SITL 확인
        ardupilot_paths = [
            "/opt/ardupilot",
            "~/ardupilot",
            "./ardupilot"
        ]
        
        for path in ardupilot_paths:
            if Path(path).expanduser().exists():
                print("🛩️  ArduPilot SITL 환경 감지됨")
                return "simulation"
        
        # 실제 하드웨어 확인 (MAVLink 포트 스캔)
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection("192.168.13.2", 14550),
                timeout=2
            )
            writer.close()
            await writer.wait_closed()
            print("🚁 실제 DVD 하드웨어 감지됨")
            return "real_hardware"
        except:
            pass
        
        print("💻 시뮬레이션 환경으로 설정")
        return "simulation"
    
    async def _update_environment_config(self, environment_type: str):
        """환경 설정 업데이트"""
        config_updates = {
            "simulation": {
                "dvd_environment": {
                    "type": "simulation",
                    "ardupilot_path": "/opt/ardupilot"
                },
                "targets": {
                    "primary": {
                        "ip": "127.0.0.1",
                        "mavlink_port": 14550
                    }
                }
            },
            "docker": {
                "dvd_environment": {
                    "type": "docker"
                },
                "targets": {
                    "primary": {
                        "ip": "127.0.0.1",
                        "mavlink_port": 14550
                    }
                }
            },
            "real_hardware": {
                "dvd_environment": {
                    "type": "real_hardware"
                },
                "targets": {
                    "primary": {
                        "ip": "192.168.13.2",
                        "mavlink_port": 14550
                    },
                    "companion": {
                        "ip": "192.168.13.3",
                        "ssh_port": 22
                    }
                }
            }
        }
        
        if environment_type in config_updates:
            # 기존 설정과 병합
            current_config = self.dvd_environment.config
            update_config = config_updates[environment_type]
            
            for key, value in update_config.items():
                if isinstance(value, dict) and key in current_config:
                    current_config[key].update(value)
                else:
                    current_config[key] = value
            
            # 설정 저장
            with open(self.config_path, 'w') as f:
                json.dump(current_config, f, indent=2)
    
    async def run_comprehensive_test(self) -> Dict[str, Any]:
        """종합적인 DVD 테스트 실행"""
        print("\n" + "="*70)
        print("🧪 종합적인 DVD 보안 테스트 실행")
        print("="*70)
        
        results = {
            "environment_status": {},
            "attack_results": [],
            "cti_analysis": {},
            "security_assessment": {}
        }
        
        try:
            # 1. 환경 상태 확인
            results["environment_status"] = await self._check_environment_status()
            
            # 2. 안전성 검사
            if not await self._perform_safety_checks():
                print("❌ 안전성 검사 실패 - 테스트 중단")
                return results
            
            # 3. 단계별 공격 실행
            attack_sequence = await self._get_attack_sequence()
            
            for phase, attacks in attack_sequence.items():
                print(f"\n🎯 {phase} 단계 실행...")
                phase_results = await self._execute_attack_phase(attacks)
                results["attack_results"].extend(phase_results)
            
            # 4. CTI 분석
            results["cti_analysis"] = await self._analyze_cti_data()
            
            # 5. 보안 평가
            results["security_assessment"] = await self._generate_security_assessment(results)
            
            # 6. 보고서 생성
            await self._generate_comprehensive_report(results)
            
        except Exception as e:
            logger.error(f"종합 테스트 실행 실패: {e}")
            results["error"] = str(e)
        
        return results
    
    async def _check_environment_status(self) -> Dict[str, Any]:
        """환경 상태 확인"""
        print("📊 DVD 환경 상태 확인 중...")
        
        status = {
            "environment_type": "unknown",
            "connectivity": False,
            "targets": {},
            "services": {}
        }
        
        if self.dvd_connector:
            # 타겟 상태 확인
            for target_name in ["primary", "companion", "gcs"]:
                try:
                    target_status = await self.dvd_connector.get_target_status(target_name)
                    status["targets"][target_name] = target_status
                    if target_status["status"] == "connected":
                        status["connectivity"] = True
                except:
                    status["targets"][target_name] = {"status": "unknown"}
            
            status["environment_type"] = self.dvd_environment.config["dvd_environment"]["type"]
        
        print(f"   환경 타입: {status['environment_type']}")
        print(f"   연결 상태: {'✅' if status['connectivity'] else '❌'}")
        
        return status
    
    async def _perform_safety_checks(self) -> bool:
        """안전성 검사 수행"""
        print("🛡️  안전성 검사 수행 중...")
        
        try:
            safety_ok = await self.safety_checker.perform_safety_check()
            
            if safety_ok:
                print("✅ 안전성 검사 통과")
                return True
            else:
                print("❌ 안전성 검사 실패")
                return False
                
        except Exception as e:
            logger.error(f"안전성 검사 오류: {e}")
            return False
    
    async def _get_attack_sequence(self) -> Dict[str, List[str]]:
        """단계별 공격 시퀀스 생성"""
        if DVD_CONNECTOR_AVAILABLE:
            return {
                "정찰": get_attacks_by_tactic(DVDAttackTactic.RECONNAISSANCE),
                "프로토콜_조작": get_attacks_by_tactic(DVDAttackTactic.PROTOCOL_TAMPERING)[:2],
                "주입": get_attacks_by_tactic(DVDAttackTactic.INJECTION)[:2],
                "데이터_탈취": get_attacks_by_tactic(DVDAttackTactic.EXFILTRATION)[:2]
            }
        else:
            return {
                "기본_정찰": ["wifi_scan", "drone_discovery"],
                "기본_공격": ["telemetry_spoof", "command_inject"],
                "기본_탈취": ["log_extract", "param_extract"]
            }
    
    async def _execute_attack_phase(self, attacks: List[str]) -> List[Dict[str, Any]]:
        """공격 단계 실행"""
        results = []
        
        for attack_name in attacks:
            print(f"   🚀 {attack_name} 실행 중...")
            
            try:
                if self.dvd_connector:
                    # 실제 타겟에 대해 공격 실행
                    result_data = await self.dvd_connector.execute_attack_on_target(attack_name)
                    result = result_data["result"]
                else:
                    # 시뮬레이션 공격 실행
                    result = await self.dvd_lite.run_attack(attack_name)
                
                status_icon = "✅" if result.status == AttackStatus.SUCCESS else "❌"
                print(f"      {status_icon} 완료: {result.response_time:.2f}s, IOCs: {len(result.iocs)}")
                
                results.append({
                    "attack_name": attack_name,
                    "result": result,
                    "target_info": getattr(result, 'target_info', None)
                })
                
                # 공격 간 대기
                await asyncio.sleep(1.0)
                
            except Exception as e:
                print(f"      ❌ 실패: {str(e)}")
                results.append({
                    "attack_name": attack_name,
                    "error": str(e)
                })
        
        return results
    
    async def _analyze_cti_data(self) -> Dict[str, Any]:
        """CTI 데이터 분석"""
        print("🔍 CTI 데이터 분석 중...")
        
        if not self.cti_collector:
            return {"status": "no_cti_collector"}
        
        cti_summary = self.cti_collector.get_summary()
        
        # 고급 분석 수행
        analysis = {
            "summary": cti_summary,
            "threat_landscape": self._analyze_threat_landscape(cti_summary),
            "attack_patterns": self._identify_attack_patterns(cti_summary),
            "recommendations": self._generate_recommendations(cti_summary)
        }
        
        print(f"   📊 수집된 지표: {cti_summary['total_indicators']}개")
        print(f"   📈 공격 패턴: {cti_summary['total_patterns']}개")
        
        return analysis
    
    def _analyze_threat_landscape(self, cti_summary: Dict[str, Any]) -> Dict[str, Any]:
        """위협 환경 분석"""
        if not cti_summary.get("statistics", {}).get("by_attack_type"):
            return {"status": "insufficient_data"}
        
        attack_types = cti_summary["statistics"]["by_attack_type"]
        
        return {
            "primary_threats": sorted(attack_types.items(), key=lambda x: x[1], reverse=True)[:3],
            "threat_diversity": len(attack_types),
            "total_indicators": cti_summary["total_indicators"]
        }
    
    def _identify_attack_patterns(self, cti_summary: Dict[str, Any]) -> List[Dict[str, Any]]:
        """공격 패턴 식별"""
        patterns = []
        
        # 시간 기반 패턴 분석
        if cti_summary["total_indicators"] > 10:
            patterns.append({
                "type": "high_volume_attack",
                "description": "다량의 공격 지표 발견",
                "severity": "high"
            })
        
        # 공격 타입 기반 패턴
        if cti_summary.get("statistics", {}).get("by_attack_type"):
            attack_types = cti_summary["statistics"]["by_attack_type"]
            if len(attack_types) > 3:
                patterns.append({
                    "type": "multi_vector_attack",
                    "description": "다중 벡터 공격 패턴",
                    "severity": "medium"
                })
        
        return patterns
    
    def _generate_recommendations(self, cti_summary: Dict[str, Any]) -> List[str]:
        """보안 권장사항 생성"""
        recommendations = []
        
        if cti_summary["total_indicators"] > 5:
            recommendations.append("MAVLink 통신 암호화 강화 권장")
            recommendations.append("네트워크 접근 제어 정책 검토")
        
        confidence_stats = cti_summary.get("statistics", {}).get("by_confidence", {})
        if confidence_stats.get("high", 0) > 3:
            recommendations.append("높은 신뢰도 위협에 대한 즉시 대응 필요")
        
        return recommendations
    
    async def _generate_security_assessment(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """보안 평가 생성"""
        print("📋 보안 평가 생성 중...")
        
        attack_results = results.get("attack_results", [])
        successful_attacks = [r for r in attack_results if r.get("result") and r["result"].status == AttackStatus.SUCCESS]
        
        assessment = {
            "overall_security_score": self._calculate_security_score(attack_results),
            "successful_attacks": len(successful_attacks),
            "total_attacks": len(attack_results),
            "critical_vulnerabilities": self._identify_critical_vulnerabilities(successful_attacks),
            "security_recommendations": self._generate_security_recommendations(successful_attacks)
        }
        
        print(f"   🎯 보안 점수: {assessment['overall_security_score']}/100")
        print(f"   ⚠️  성공한 공격: {assessment['successful_attacks']}/{assessment['total_attacks']}")
        
        return assessment
    
    def _calculate_security_score(self, attack_results: List[Dict[str, Any]]) -> int:
        """보안 점수 계산"""
        if not attack_results:
            return 100
        
        successful_attacks = len([r for r in attack_results if r.get("result") and r["result"].status == AttackStatus.SUCCESS])
        total_attacks = len(attack_results)
        
        success_rate = successful_attacks / total_attacks
        security_score = max(0, 100 - int(success_rate * 100))
        
        return security_score
    
    def _identify_critical_vulnerabilities(self, successful_attacks: List[Dict[str, Any]]) -> List[str]:
        """치명적 취약점 식별"""
        critical_vulns = []
        
        for attack in successful_attacks:
            attack_name = attack.get("attack_name", "")
            
            if "injection" in attack_name.lower():
                critical_vulns.append("명령 주입 취약점")
            elif "firmware" in attack_name.lower():
                critical_vulns.append("펌웨어 보안 취약점")
            elif "gps" in attack_name.lower():
                critical_vulns.append("GPS 스푸핑 취약점")
        
        return list(set(critical_vulns))
    
    def _generate_security_recommendations(self, successful_attacks: List[Dict[str, Any]]) -> List[str]:
        """보안 권장사항 생성"""
        recommendations = []
        
        if any("network" in attack.get("attack_name", "") for attack in successful_attacks):
            recommendations.append("네트워크 보안 강화 필요")
        
        if any("mavlink" in attack.get("attack_name", "") for attack in successful_attacks):
            recommendations.append("MAVLink 프로토콜 보안 검토")
        
        if any("firmware" in attack.get("attack_name", "") for attack in successful_attacks):
            recommendations.append("펌웨어 무결성 검증 시스템 도입")
        
        return recommendations
    
    async def _generate_comprehensive_report(self, results: Dict[str, Any]):
        """종합 보고서 생성"""
        print("📄 종합 보고서 생성 중...")
        
        try:
            # JSON 보고서
            json_filename = f"results/dvd_comprehensive_report_{int(asyncio.get_event_loop().time())}.json"
            Path("results").mkdir(exist_ok=True)
            
            with open(json_filename, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, default=str, ensure_ascii=False)
            
            print(f"✅ JSON 보고서 저장: {json_filename}")
            
            # CTI 데이터 내보내기
            if self.cti_collector:
                cti_filename = self.cti_collector.export_json()
                print(f"✅ CTI 데이터 저장: {cti_filename}")
            
        except Exception as e:
            logger.error(f"보고서 생성 실패: {e}")
    
    async def cleanup(self):
        """정리 작업"""
        print("🧹 정리 작업 수행 중...")
        
        if self.dvd_connector:
            await self.dvd_connector.cleanup()
        
        print("✅ 정리 완료")

async def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description="DVD 고급 공격 시나리오 실행기")
    parser.add_argument("--mode", choices=["test", "interactive", "comprehensive"], 
                       default="comprehensive", help="실행 모드")
    parser.add_argument("--environment", choices=["auto", "simulation", "docker", "real_hardware"],
                       default="auto", help="DVD 환경 타입")
    parser.add_argument("--config", default="dvd_config.json", help="설정 파일 경로")
    
    args = parser.parse_args()
    
    print_banner()
    
    # DVD 고급 실행기 생성
    runner = DVDAdvancedRunner(args.config)
    
    try:
        # 초기화
        if not await runner.initialize(args.environment):
            print("❌ 초기화 실패")
            return
        
        if args.mode == "comprehensive":
            # 종합 테스트 실행
            results = await runner.run_comprehensive_test()
            
        elif args.mode == "interactive":
            # 대화형 모드
            await interactive_mode(runner)
            
        elif args.mode == "test":
            # 기본 테스트
            await basic_test(runner)
        
        # 정리
        await runner.cleanup()
        
    except KeyboardInterrupt:
        print("\n👋 사용자에 의해 중단되었습니다.")
        await runner.cleanup()
    except Exception as e:
        logger.error(f"실행 오류: {e}")
        await runner.cleanup()

async def interactive_mode(runner: DVDAdvancedRunner):
    """대화형 모드"""
    print("\n🎮 대화형 모드 시작")
    
    while True:
        print("\n🎯 선택 옵션:")
        print("   1. 환경 상태 확인")
        print("   2. 단일 공격 실행") 
        print("   3. 정찰 공격 수행")
        print("   4. CTI 분석 보기")
        print("   5. 종합 테스트 실행")
        print("   6. 종료")
        
        try:
            choice = input("\n선택하세요 (1-6): ").strip()
            
            if choice == "1":
                status = await runner._check_environment_status()
                print(f"📊 환경 상태: {json.dumps(status, indent=2, ensure_ascii=False)}")
                
            elif choice == "2":
                await single_attack_mode(runner)
                
            elif choice == "3":
                if DVD_CONNECTOR_AVAILABLE:
                    recon_attacks = get_attacks_by_tactic(DVDAttackTactic.RECONNAISSANCE)
                    results = await runner._execute_attack_phase(recon_attacks)
                    print(f"✅ 정찰 완료: {len(results)}개 공격 실행")
                
            elif choice == "4":
                if runner.cti_collector:
                    runner.cti_collector.print_summary()
                
            elif choice == "5":
                await runner.run_comprehensive_test()
                
            elif choice == "6":
                print("👋 종료합니다.")
                break
                
        except KeyboardInterrupt:
            print("\n👋 종료합니다.")
            break

async def single_attack_mode(runner: DVDAdvancedRunner):
    """단일 공격 모드"""
    if DVD_CONNECTOR_AVAILABLE:
        all_attacks = []
        for tactic in DVDAttackTactic:
            all_attacks.extend(get_attacks_by_tactic(tactic))
    else:
        all_attacks = ["wifi_scan", "drone_discovery", "packet_sniff", "telemetry_spoof"]
    
    print(f"\n📋 사용 가능한 공격 ({len(all_attacks)}개):")
    for i, attack in enumerate(all_attacks, 1):
        print(f"   {i}. {attack}")
    
    try:
        choice = int(input(f"\n실행할 공격을 선택하세요 (1-{len(all_attacks)}): ")) - 1
        
        if 0 <= choice < len(all_attacks):
            attack_name = all_attacks[choice]
            results = await runner._execute_attack_phase([attack_name])
            
            if results and results[0].get("result"):
                result = results[0]["result"]
                print(f"\n🎯 공격 결과:")
                print(f"   상태: {result.status.value}")
                print(f"   실행시간: {result.response_time:.2f}초")
                print(f"   IOCs: {len(result.iocs)}개")
    except (ValueError, IndexError):
        print("❌ 잘못된 선택입니다.")

async def basic_test(runner: DVDAdvancedRunner):
    """기본 테스트"""
    print("\n🧪 기본 테스트 실행")
    
    # 환경 상태 확인
    status = await runner._check_environment_status()
    print(f"📊 환경: {status['environment_type']}, 연결: {status['connectivity']}")
    
    # 간단한 공격 실행
    if DVD_CONNECTOR_AVAILABLE:
        test_attacks = ["wifi_network_discovery"]
    else:
        test_attacks = ["wifi_scan"]
    
    results = await runner._execute_attack_phase(test_attacks)
    print(f"✅ 테스트 완료: {len(results)}개 공격 실행")

if __name__ == "__main__":
    asyncio.run(main())