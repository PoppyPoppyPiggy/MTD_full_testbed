#!/usr/bin/env python3
"""
DVD 연결 포인트 통합 테스트
실제 DVD 환경과의 연동 기능을 테스트합니다.
"""

import asyncio
import unittest
import sys
import os
import time
from pathlib import Path

# 프로젝트 루트를 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestDVDIntegration(unittest.TestCase):
    """DVD 통합 테스트"""
    
    def setUp(self):
        """테스트 설정"""
        self.test_config = {
            "host": "localhost",
            "dvd_network": "10.13.0.0/24",
            "environment": "SIMULATION",
            "simulation_mode": True,
            "safety_enabled": True
        }
    
    def test_dvd_connector_import(self):
        """DVD Connector 모듈 import 테스트"""
        try:
            from dvd_connector import DVDConnector, DVDEnvironment, DVDConnectionConfig
            from dvd_connector import SafetyChecker, DVDNetworkScanner
            
            print("✅ DVD Connector 모듈 import 성공")
            
            # 기본 클래스 인스턴스 생성 테스트
            config = DVDConnectionConfig(environment=DVDEnvironment.SIMULATION)
            connector = DVDConnector(config)
            checker = SafetyChecker()
            scanner = DVDNetworkScanner()
            
            self.assertIsNotNone(connector)
            self.assertIsNotNone(checker)
            self.assertIsNotNone(scanner)
            
            print("✅ DVD Connector 클래스 인스턴스 생성 성공")
            
        except ImportError as e:
            self.fail(f"DVD Connector import 실패: {e}")
    
    def test_safety_checker(self):
        """안전성 검사기 테스트"""
        try:
            from dvd_connector.safety_checker import SafetyChecker, quick_safety_check
            
            async def safety_test():
                # 빠른 안전성 검사
                is_safe = await quick_safety_check(self.test_config)
                self.assertTrue(is_safe, "시뮬레이션 환경이 안전하지 않음")
                
                # 상세 안전성 검사
                checker = SafetyChecker()
                result = await checker.comprehensive_safety_check(self.test_config)
                
                self.assertIsNotNone(result)
                self.assertTrue(result.is_safe_to_proceed)
                
                print("✅ 안전성 검사 통과")
                return True
            
            # 비동기 테스트 실행
            result = asyncio.run(safety_test())
            self.assertTrue(result)
            
        except Exception as e:
            self.fail(f"안전성 검사 실패: {e}")
    
    def test_network_scanner(self):
        """네트워크 스캐너 테스트"""
        try:
            from dvd_connector.network_scanner import DVDNetworkScanner, quick_dvd_scan
            
            async def scanner_test():
                scanner = DVDNetworkScanner(timeout=2, max_threads=5)
                
                # 로컬호스트 스캔 (안전)
                result = await scanner.scan_network("127.0.0.0/30", quick_scan=True)
                
                self.assertIsNotNone(result)
                self.assertEqual(result.network_range, "127.0.0.0/30")
                
                print(f"✅ 네트워크 스캔 완료: {result.active_hosts}개 호스트 발견")
                
                # 빠른 드론 스캔 테스트
                drone_devices = await scanner.quick_drone_scan("127.0.0.0/30")
                print(f"✅ 드론 디바이스 스캔 완료: {len(drone_devices)}개 발견")
                
                return True
            
            result = asyncio.run(scanner_test())
            self.assertTrue(result)
            
        except Exception as e:
            self.fail(f"네트워크 스캐너 테스트 실패: {e}")
    
    def test_dvd_connector_simulation(self):
        """DVD Connector 시뮬레이션 모드 테스트"""
        try:
            from dvd_connector import DVDConnector, DVDEnvironment, DVDConnectionConfig
            
            async def connection_test():
                config = DVDConnectionConfig(
                    environment=DVDEnvironment.SIMULATION,
                    host="localhost",
                    timeout=10
                )
                
                connector = DVDConnector(config)
                
                # 연결 테스트
                connected = await connector.connect()
                self.assertTrue(connected, "시뮬레이션 모드 연결 실패")
                
                # 상태 확인
                self.assertTrue(connector.is_connected())
                
                # 텔레메트리 데이터 수집 테스트
                telemetry = await connector.get_telemetry()
                self.assertIsInstance(telemetry, dict)
                self.assertIn("timestamp", telemetry)
                
                # MAVLink 메시지 전송 테스트
                test_message = {"type": "heartbeat", "system_id": 1}
                sent = await connector.send_mavlink_message(test_message)
                self.assertTrue(sent, "MAVLink 메시지 전송 실패")
                
                # 상태 확인 테스트
                health_ok = await connector.health_check()
                self.assertTrue(health_ok, "상태 확인 실패")
                
                # 연결 해제
                disconnected = await connector.disconnect()
                self.assertTrue(disconnected, "연결 해제 실패")
                
                print("✅ DVD Connector 시뮬레이션 모드 테스트 완료")
                return True
            
            result = asyncio.run(connection_test())
            self.assertTrue(result)
            
        except Exception as e:
            self.fail(f"DVD Connector 시뮬레이션 테스트 실패: {e}")
    
    def test_dvd_lite_with_connector(self):
        """DVD-Lite와 Connector 통합 테스트"""
        try:
            from dvd_lite.main import DVDLite
            from dvd_lite.dvd_attacks.registry.management import register_all_dvd_attacks
            from dvd_connector import create_dvd_connection, DVDEnvironment
            
            async def integration_test():
                # 안전한 연결 생성
                connector = await create_dvd_connection(DVDEnvironment.SIMULATION)
                
                # DVD-Lite 인스턴스 생성
                dvd = DVDLite()
                register_all_dvd_attacks()
                
                # 간단한 공격 실행
                result = await dvd.run_attack("wifi_network_discovery")
                
                self.assertIsNotNone(result)
                self.assertTrue(hasattr(result, 'status'))
                self.assertTrue(hasattr(result, 'iocs'))
                
                # 연결 해제
                await connector.disconnect()
                
                print("✅ DVD-Lite와 Connector 통합 테스트 완료")
                return True
            
            result = asyncio.run(integration_test())
            self.assertTrue(result)
            
        except Exception as e:
            self.fail(f"DVD-Lite 통합 테스트 실패: {e}")
    
    def test_cti_collection_integration(self):
        """CTI 수집 통합 테스트"""
        try:
            from dvd_lite.main import DVDLite
            from dvd_lite.cti import SimpleCTI
            from dvd_lite.dvd_attacks.registry.management import register_all_dvd_attacks
            
            async def cti_test():
                # CTI 수집기 설정
                cti = SimpleCTI()
                
                # DVD-Lite 설정
                dvd = DVDLite()
                dvd.register_cti_collector(cti)
                register_all_dvd_attacks()
                
                # 공격 실행 및 CTI 수집
                result = await dvd.run_attack("mavlink_service_discovery")
                
                # CTI 데이터 확인
                summary = cti.get_summary()
                self.assertGreater(summary['total_indicators'], 0)
                
                # 임시 파일로 내보내기 테스트
                temp_dir = Path("temp_results")
                temp_dir.mkdir(exist_ok=True)
                
                json_file = cti.export_json(str(temp_dir / "test_cti.json"))
                csv_file = cti.export_csv(str(temp_dir / "test_cti.csv"))
                
                self.assertTrue(Path(json_file).exists())
                self.assertTrue(Path(csv_file).exists())
                
                # 정리
                Path(json_file).unlink()
                Path(csv_file).unlink()
                temp_dir.rmdir()
                
                print("✅ CTI 수집 통합 테스트 완료")
                return True
            
            result = asyncio.run(cti_test())
            self.assertTrue(result)
            
        except Exception as e:
            self.fail(f"CTI 수집 통합 테스트 실패: {e}")
    
    def test_error_handling(self):
        """오류 처리 테스트"""
        try:
            from dvd_connector import DVDConnector, DVDEnvironment, DVDConnectionConfig
            
            async def error_test():
                # 잘못된 설정으로 연결 시도
                config = DVDConnectionConfig(
                    environment=DVDEnvironment.HALF_BAKED,
                    host="invalid_host_12345",
                    timeout=2
                )
                
                connector = DVDConnector(config)
                
                # 연결 실패 테스트
                connected = await connector.connect()
                self.assertFalse(connected, "잘못된 호스트에 연결 성공 (예상치 못한 결과)")
                
                # 상태 확인
                status = connector.get_status()
                self.assertIsNotNone(status.error_message)
                
                print("✅ 오류 처리 테스트 완료")
                return True
            
            result = asyncio.run(error_test())
            self.assertTrue(result)
            
        except Exception as e:
            self.fail(f"오류 처리 테스트 실패: {e}")

class TestDVDEnvironmentCompatibility(unittest.TestCase):
    """DVD 환경 호환성 테스트"""
    
    def test_environment_detection(self):
        """DVD 환경 감지 테스트"""
        try:
            from dvd_connector.safety_checker import SafetyChecker
            
            async def env_test():
                checker = SafetyChecker()
                
                # 시뮬레이션 환경 테스트
                sim_config = {
                    "host": "localhost",
                    "environment": "SIMULATION",
                    "simulation_mode": True
                }
                
                result = await checker.comprehensive_safety_check(sim_config)
                self.assertEqual(result.safety_level.value, "safe")
                
                # 의심스러운 환경 테스트
                suspicious_config = {
                    "host": "192.168.1.100",
                    "environment": "PRODUCTION",
                    "real_hardware": True
                }
                
                result = await checker.comprehensive_safety_check(suspicious_config)
                self.assertIn(result.safety_level.value, ["warning", "danger"])
                
                print("✅ 환경 감지 테스트 완료")
                return True
            
            result = asyncio.run(env_test())
            self.assertTrue(result)
            
        except Exception as e:
            self.fail(f"환경 감지 테스트 실패: {e}")
    
    def test_docker_integration(self):
        """Docker 환경 통합 테스트"""
        try:
            from dvd_connector import DVDConnector, DVDEnvironment, DVDConnectionConfig
            import subprocess
            
            async def docker_test():
                # Docker 상태 확인
                try:
                    result = subprocess.run(
                        ["docker", "--version"], 
                        capture_output=True, 
                        text=True, 
                        timeout=5
                    )
                    docker_available = result.returncode == 0
                except Exception:
                    docker_available = False
                
                if not docker_available:
                    print("⚠️ Docker를 사용할 수 없음 - 시뮬레이션으로 테스트")
                    
                    # 시뮬레이션 모드로 테스트
                    config = DVDConnectionConfig(environment=DVDEnvironment.SIMULATION)
                    connector = DVDConnector(config)
                    
                    connected = await connector.connect()
                    self.assertTrue(connected)
                    
                    await connector.disconnect()
                else:
                    print("✅ Docker 사용 가능")
                    
                    # Half-Baked 모드 테스트 시도
                    config = DVDConnectionConfig(environment=DVDEnvironment.HALF_BAKED)
                    connector = DVDConnector(config)
                    
                    # 연결 시도 (실패할 수 있음)
                    connected = await connector.connect()
                    
                    if connected:
                        print("✅ Half-Baked 모드 연결 성공")
                        await connector.disconnect()
                    else:
                        print("⚠️ Half-Baked 모드 연결 실패 (예상됨)")
                
                print("✅ Docker 통합 테스트 완료")
                return True
            
            result = asyncio.run(docker_test())
            self.assertTrue(result)
            
        except Exception as e:
            self.fail(f"Docker 통합 테스트 실패: {e}")

class TestPerformanceAndReliability(unittest.TestCase):
    """성능 및 안정성 테스트"""
    
    def test_multiple_attacks_performance(self):
        """다중 공격 성능 테스트"""
        try:
            from dvd_lite.main import DVDLite
            from dvd_lite.dvd_attacks.registry.management import register_all_dvd_attacks, get_attacks_by_difficulty, AttackDifficulty
            
            async def performance_test():
                dvd = DVDLite()
                register_all_dvd_attacks()
                
                # 초급 공격들 실행
                beginner_attacks = get_attacks_by_difficulty(AttackDifficulty.BEGINNER)
                
                start_time = time.time()
                
                # 순차 실행
                results = []
                for attack in beginner_attacks[:3]:  # 처음 3개만 테스트
                    result = await dvd.run_attack(attack)
                    results.append(result)
                
                execution_time = time.time() - start_time
                
                # 성능 검증
                self.assertLess(execution_time, 30, "공격 실행 시간이 너무 오래 걸림")
                self.assertEqual(len(results), 3, "예상된 수의 결과가 반환되지 않음")
                
                # 성공률 확인
                success_count = sum(1 for r in results if r.success)
                success_rate = success_count / len(results)
                self.assertGreater(success_rate, 0.5, "성공률이 너무 낮음")
                
                print(f"✅ 성능 테스트 완료: {execution_time:.2f}초, 성공률: {success_rate:.1%}")
                return True
            
            result = asyncio.run(performance_test())
            self.assertTrue(result)
            
        except Exception as e:
            self.fail(f"성능 테스트 실패: {e}")
    
    def test_concurrent_operations(self):
        """동시 작업 테스트"""
        try:
            from dvd_connector.network_scanner import DVDNetworkScanner
            from dvd_connector.safety_checker import SafetyChecker
            
            async def concurrent_test():
                # 동시에 여러 작업 실행
                scanner = DVDNetworkScanner(timeout=2, max_threads=5)
                checker = SafetyChecker()
                
                # 동시 실행할 작업들
                tasks = [
                    scanner.scan_network("127.0.0.0/30", quick_scan=True),
                    checker.comprehensive_safety_check({"host": "localhost"}),
                    scanner.quick_drone_scan("127.0.0.0/30")
                ]
                
                start_time = time.time()
                results = await asyncio.gather(*tasks, return_exceptions=True)
                execution_time = time.time() - start_time
                
                # 결과 검증
                self.assertEqual(len(results), 3)
                
                # 예외가 발생하지 않았는지 확인
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        self.fail(f"작업 {i} 실행 중 예외 발생: {result}")
                
                self.assertLess(execution_time, 15, "동시 작업 실행 시간이 너무 오래 걸림")
                
                print(f"✅ 동시 작업 테스트 완료: {execution_time:.2f}초")
                return True
            
            result = asyncio.run(concurrent_test())
            self.assertTrue(result)
            
        except Exception as e:
            self.fail(f"동시 작업 테스트 실패: {e}")
    
    def test_memory_usage(self):
        """메모리 사용량 테스트"""
        try:
            import psutil
            import gc
            
            from dvd_lite.main import DVDLite
            from dvd_lite.cti import SimpleCTI
            from dvd_lite.dvd_attacks.registry.management import register_all_dvd_attacks
            
            async def memory_test():
                # 초기 메모리 사용량
                process = psutil.Process()
                initial_memory = process.memory_info().rss / 1024 / 1024  # MB
                
                # 대량 작업 실행
                for i in range(5):
                    dvd = DVDLite()
                    cti = SimpleCTI()
                    dvd.register_cti_collector(cti)
                    register_all_dvd_attacks()
                    
                    # 공격 실행
                    result = await dvd.run_attack("wifi_network_discovery")
                    
                    # 명시적 정리
                    del dvd, cti, result
                    gc.collect()
                
                # 최종 메모리 사용량
                final_memory = process.memory_info().rss / 1024 / 1024  # MB
                memory_increase = final_memory - initial_memory
                
                # 메모리 누수 확인 (100MB 이상 증가하면 문제)
                self.assertLess(memory_increase, 100, f"메모리 사용량이 {memory_increase:.1f}MB 증가함")
                
                print(f"✅ 메모리 테스트 완료: {memory_increase:.1f}MB 증가")
                return True
            
            result = asyncio.run(memory_test())
            self.assertTrue(result)
            
        except ImportError:
            print("⚠️ psutil 모듈이 없어 메모리 테스트를 건너뜀")
        except Exception as e:
            self.fail(f"메모리 테스트 실패: {e}")

def run_comprehensive_tests():
    """종합 테스트 실행"""
    print("🧪 DVD 연결 포인트 종합 테스트 시작")
    print("="*60)
    
    # 테스트 스위트 생성
    test_suite = unittest.TestSuite()
    
    # 기본 통합 테스트
    test_suite.addTest(TestDVDIntegration('test_dvd_connector_import'))
    test_suite.addTest(TestDVDIntegration('test_safety_checker'))
    test_suite.addTest(TestDVDIntegration('test_network_scanner'))
    test_suite.addTest(TestDVDIntegration('test_dvd_connector_simulation'))
    test_suite.addTest(TestDVDIntegration('test_dvd_lite_with_connector'))
    test_suite.addTest(TestDVDIntegration('test_cti_collection_integration'))
    test_suite.addTest(TestDVDIntegration('test_error_handling'))
    
    # 환경 호환성 테스트
    test_suite.addTest(TestDVDEnvironmentCompatibility('test_environment_detection'))
    test_suite.addTest(TestDVDEnvironmentCompatibility('test_docker_integration'))
    
    # 성능 테스트
    test_suite.addTest(TestPerformanceAndReliability('test_multiple_attacks_performance'))
    test_suite.addTest(TestPerformanceAndReliability('test_concurrent_operations'))
    test_suite.addTest(TestPerformanceAndReliability('test_memory_usage'))
    
    # 테스트 실행
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # 결과 요약
    print("\n" + "="*60)
    print("📊 테스트 결과 요약")
    print("="*60)
    print(f"총 테스트: {result.testsRun}")
    print(f"성공: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"실패: {len(result.failures)}")
    print(f"오류: {len(result.errors)}")
    
    if result.failures:
        print("\n❌ 실패한 테스트:")
        for test, traceback in result.failures:
            print(f"  - {test}: {traceback.split('AssertionError: ')[-1].split('\n')[0]}")
    
    if result.errors:
        print("\n🚨 오류가 발생한 테스트:")
        for test, traceback in result.errors:
            print(f"  - {test}: {traceback.split('\n')[-2]}")
    
    success_rate = (result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun
    
    if success_rate == 1.0:
        print("\n🎉 모든 테스트가 성공했습니다!")
    elif success_rate >= 0.8:
        print(f"\n✅ 대부분의 테스트가 성공했습니다 ({success_rate:.1%})")
    else:
        print(f"\n⚠️ 일부 테스트가 실패했습니다 ({success_rate:.1%})")
    
    print("="*60)
    
    return result.wasSuccessful()

if __name__ == "__main__":
    # 개별 테스트 실행 vs 종합 테스트
    if len(sys.argv) > 1 and sys.argv[1] == "comprehensive":
        success = run_comprehensive_tests()
        sys.exit(0 if success else 1)
    else:
        # 표준 unittest 실행
        unittest.main(verbosity=2)