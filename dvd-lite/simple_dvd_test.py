#!/usr/bin/env python3
# simple_dvd_test.py
"""
간단한 DVD 연동 테스트 스크립트
의존성 문제 회피 및 기본 기능 확인
"""

import sys
import os
import asyncio
import json
import argparse
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def check_dependencies():
    """의존성 확인"""
    print("🔍 의존성 확인 중...")
    
    try:
        # 기본 DVD-Lite 모듈 확인
        from dvd_lite.main import DVDLite
        from dvd_lite.cti import SimpleCTI
        from dvd_lite.attacks import register_all_attacks
        print("✅ DVD-Lite 모듈 사용 가능")
        return True
    except ImportError as e:
        print(f"❌ DVD-Lite import 오류: {e}")
        return False

async def simple_simulation_test():
    """간단한 시뮬레이션 테스트"""
    print("\n🚁 DVD-Lite 시뮬레이션 테스트 시작")
    print("=" * 50)
    
    try:
        # DVD-Lite 직접 사용 (연결 모듈 없이)
        from dvd_lite.main import DVDLite
        from dvd_lite.cti import SimpleCTI
        from dvd_lite.attacks import register_all_attacks
        
        # 1. 초기화
        print("1️⃣  DVD-Lite 초기화...")
        dvd = DVDLite()
        cti = SimpleCTI()
        dvd.register_cti_collector(cti)
        
        # 2. 공격 모듈 등록
        print("2️⃣  공격 모듈 등록...")
        attack_names = register_all_attacks(dvd)
        print(f"   등록된 공격: {len(attack_names)}개")
        
        # 3. 기본 공격 실행
        print("3️⃣  기본 공격 실행...")
        test_attacks = ["wifi_scan", "drone_discovery", "packet_sniff"]
        
        results = []
        for attack in test_attacks:
            print(f"   공격 실행: {attack}")
            result = await dvd.run_attack(attack)
            results.append(result)
            
            status_icon = "✅" if result.status.value == "success" else "❌"
            print(f"     {status_icon} 결과: {result.status.value} ({result.response_time:.2f}초)")
            
            await asyncio.sleep(1)  # 간격
        
        # 4. 결과 요약
        print("4️⃣  결과 요약...")
        summary = dvd.get_summary()
        print(f"   총 공격: {summary['total_attacks']}")
        print(f"   성공률: {summary['success_rate']}")
        
        # 5. CTI 데이터
        print("5️⃣  CTI 데이터...")
        cti_summary = cti.get_summary()
        print(f"   수집된 지표: {cti_summary['total_indicators']}개")
        
        # 6. 결과 저장
        print("6️⃣  결과 저장...")
        Path("results").mkdir(exist_ok=True)
        
        results_file = dvd.export_results()
        cti_file = cti.export_json()
        
        print(f"   결과 파일: {results_file}")
        print(f"   CTI 파일: {cti_file}")
        
        print("\n✅ 시뮬레이션 테스트 성공!")
        return True
        
    except Exception as e:
        print(f"\n❌ 테스트 실패: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

async def network_connectivity_test(target_host: str):
    """네트워크 연결성 테스트"""
    print(f"\n🌐 네트워크 연결성 테스트: {target_host}")
    print("=" * 50)
    
    import socket
    import subprocess
    
    # 1. Ping 테스트
    print("1️⃣  Ping 테스트...")
    try:
        process = await asyncio.create_subprocess_exec(
            "ping", "-c", "3", target_host,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:
            print("   ✅ Ping 성공")
        else:
            print("   ❌ Ping 실패")
            print(f"   오류: {stderr.decode()}")
    except Exception as e:
        print(f"   ❌ Ping 테스트 오류: {str(e)}")
    
    # 2. 포트 스캔
    print("2️⃣  포트 스캔...")
    test_ports = [14550, 14551, 80, 22, 21]
    open_ports = []
    
    for port in test_ports:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3.0)
            result = sock.connect_ex((target_host, port))
            sock.close()
            
            if result == 0:
                open_ports.append(port)
                print(f"   ✅ 포트 {port}: 열림")
            else:
                print(f"   ❌ 포트 {port}: 닫힘")
        except Exception as e:
            print(f"   ⚠️  포트 {port}: 테스트 실패 ({str(e)})")
    
    # 3. DVD 컴포넌트 추측
    print("3️⃣  DVD 컴포넌트 식별...")
    if 14550 in open_ports:
        print("   🎯 Flight Controller 감지 (포트 14550)")
    if 14551 in open_ports:
        print("   🎯 Ground Control Station 감지 (포트 14551)")
    if 80 in open_ports:
        print("   🎯 웹 서비스 감지 (포트 80)")
    if 22 in open_ports:
        print("   🎯 SSH 서비스 감지 (포트 22)")
    
    if open_ports:
        print(f"\n✅ 연결 가능: {len(open_ports)}개 포트 열림")
        return True
    else:
        print("\n❌ 연결 불가: 열린 포트 없음")
        return False

async def dvd_environment_test(target_host: str):
    """DVD 환경 테스트 (단순화된 연결 관리자)"""
    print(f"\n🔗 DVD 환경 연결 테스트: {target_host}")
    print("=" * 50)
    
    try:
        # 간단한 연결 관리자 클래스
        class SimpleDVDConnector:
            def __init__(self, host):
                self.host = host
                self.is_connected = False
                self.dvd_lite = None
            
            async def connect(self):
                # 연결성 확인
                connected = await network_connectivity_test(self.host)
                if connected:
                    # DVD-Lite 초기화
                    from dvd_lite.main import DVDLite
                    from dvd_lite.cti import SimpleCTI
                    from dvd_lite.attacks import register_all_attacks
                    
                    self.dvd_lite = DVDLite()
                    cti = SimpleCTI()
                    self.dvd_lite.register_cti_collector(cti)
                    register_all_attacks(self.dvd_lite)
                    
                    self.is_connected = True
                    return True
                return False
            
            async def run_quick_assessment(self):
                if not self.is_connected:
                    return None
                
                # 안전한 공격들만 실행
                safe_attacks = ["wifi_scan", "drone_discovery"]
                results = []
                
                for attack in safe_attacks:
                    result = await self.dvd_lite.run_attack(attack)
                    results.append(result)
                
                return results
        
        # 연결 및 테스트
        connector = SimpleDVDConnector(target_host)
        
        if await connector.connect():
            print("✅ DVD 환경 연결 성공")
            
            print("🛡️  빠른 보안 평가 실행...")
            results = await connector.run_quick_assessment()
            
            if results:
                successful = sum(1 for r in results if r.status.value == "success")
                total = len(results)
                print(f"   📊 결과: {successful}/{total} 성공")
                
                for result in results:
                    status_icon = "✅" if result.status.value == "success" else "❌"
                    print(f"   {status_icon} {result.attack_name}: {result.status.value}")
            
            return True
        else:
            print("❌ DVD 환경 연결 실패")
            return False
            
    except Exception as e:
        print(f"❌ DVD 환경 테스트 실패: {str(e)}")
        return False

def create_parser():
    """명령행 파서 생성"""
    parser = argparse.ArgumentParser(description="간단한 DVD 연동 테스트")
    
    parser.add_argument(
        "--mode",
        choices=["simulation", "network", "dvd"],
        default="simulation",
        help="테스트 모드 (기본: simulation)"
    )
    
    parser.add_argument(
        "--target",
        default="10.13.0.2",
        help="테스트 타겟 호스트 (기본: 10.13.0.2)"
    )
    
    return parser

async def main():
    """메인 함수"""
    parser = create_parser()
    args = parser.parse_args()
    
    print("🚁 DVD-Lite 간단 연동 테스트")
    print("=" * 60)
    
    # 의존성 확인
    if not check_dependencies():
        print("\n💡 해결 방법:")
        print("1. DVD-Lite 기본 파일들이 올바르게 생성되었는지 확인")
        print("2. PYTHONPATH 설정: export PYTHONPATH=$PWD:$PYTHONPATH")
        sys.exit(1)
    
    success = False
    
    try:
        if args.mode == "simulation":
            # 시뮬레이션 모드 (의존성 최소)
            success = await simple_simulation_test()
            
        elif args.mode == "network":
            # 네트워크 연결성만 테스트
            success = await network_connectivity_test(args.target)
            
        elif args.mode == "dvd":
            # DVD 환경 연결 테스트
            success = await dvd_environment_test(args.target)
        
        if success:
            print(f"\n🎉 {args.mode} 모드 테스트 성공!")
            print("\n📝 다음 단계:")
            if args.mode == "simulation":
                print("   1. 네트워크 모드로 실제 연결성 확인")
                print("   2. DVD 환경 설정 및 테스트")
            elif args.mode == "network":
                print("   1. DVD 모드로 보안 테스트 실행")
                print("   2. 전체 평가 스크립트 사용")
            else:
                print("   1. 종합적인 보안 평가 수행")
                print("   2. CTI 데이터 분석")
        else:
            print(f"\n❌ {args.mode} 모드 테스트 실패")
            print("\n💡 문제 해결:")
            print("   1. 네트워크 연결 확인")
            print("   2. DVD 환경 실행 상태 확인")
            print("   3. 방화벽 설정 확인")
        
    except KeyboardInterrupt:
        print("\n👋 테스트 중단됨")
    except Exception as e:
        print(f"\n💥 예상치 못한 오류: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())