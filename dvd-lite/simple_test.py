#!/usr/bin/env python3
# simple_test_fixed.py
"""
DVD-Lite 오류 수정된 테스트 스크립트
Import 문제 완전 해결 버전
"""

import sys
import os
import asyncio
import json
import time
from datetime import datetime
from pathlib import Path

# 현재 디렉토리를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("🔍 DVD-Lite 모듈 Import 테스트...")

# 단계별 import 테스트
try:
    # 1. 메인 모듈 import
    from dvd_lite.main import DVDLite, BaseAttack, AttackResult, AttackType, AttackStatus
    print("✅ 메인 모듈 import 성공")
    
    # 2. CTI 모듈 import  
    from dvd_lite.cti import SimpleCTI, ThreatIndicator
    print("✅ CTI 모듈 import 성공")
    
    # 3. 개별 공격 클래스 import
    from dvd_lite.attacks import WiFiScan, DroneDiscovery, PacketSniff, TelemetrySpoof
    print("✅ 공격 모듈 import 성공")
    
    # 4. 공격 등록 함수 import
    from dvd_lite.attacks import register_all_attacks
    print("✅ 공격 등록 함수 import 성공")
    
    print("🎉 모든 모듈 import 성공!")
    
except ImportError as e:
    print(f"❌ Import 오류: {e}")
    print("\n🔧 오류 해결 단계:")
    print("1. 파일 구조 확인:")
    
    required_files = [
        "dvd_lite/__init__.py",
        "dvd_lite/main.py",
        "dvd_lite/attacks.py", 
        "dvd_lite/cti.py",
        "dvd_lite/utils.py"
    ]
    
    for file_path in required_files:
        if os.path.exists(file_path):
            size = os.path.getsize(file_path)
            print(f"   ✅ {file_path} ({size} bytes)")
        else:
            print(f"   ❌ {file_path} - 파일 없음!")
    
    print("\n2. 파일 재생성이 필요할 수 있습니다.")
    sys.exit(1)

async def create_test_config():
    """테스트 설정 생성"""
    config = {
        "target": {
            "ip": "10.13.0.2",
            "mavlink_port": 14550,
            "network_range": "10.13.0.0/24"
        },
        "attacks": {
            "enabled": [
                "wifi_scan",
                "drone_discovery", 
                "packet_sniff",
                "telemetry_spoof"
            ],
            "delay_between": 1.0,
            "timeout": 30.0
        },
        "cti": {
            "auto_collect": True,
            "export_format": "json",
            "confidence_threshold": 60
        },
        "output": {
            "results_dir": "results",
            "log_level": "INFO"
        }
    }
    
    # config.json 파일 생성
    with open("config.json", "w") as f:
        json.dump(config, f, indent=2)
    
    return config

async def minimal_test():
    """최소 기능 테스트"""
    print("\n🧪 최소 기능 테스트 시작...")
    
    try:
        # 1. 객체 생성 테스트
        print("1️⃣  객체 생성 테스트...")
        dvd = DVDLite()
        print("   ✅ DVDLite 객체 생성")
        
        cti = SimpleCTI()
        print("   ✅ SimpleCTI 객체 생성")
        
        # 2. CTI 등록 테스트
        print("2️⃣  CTI 등록 테스트...")
        dvd.register_cti_collector(cti)
        print("   ✅ CTI 수집기 등록")
        
        # 3. 단일 공격 등록 테스트
        print("3️⃣  공격 등록 테스트...")
        dvd.register_attack("wifi_scan", WiFiScan)
        print("   ✅ WiFiScan 공격 등록")
        
        # 4. 공격 실행 테스트
        print("4️⃣  공격 실행 테스트...")
        result = await dvd.run_attack("wifi_scan")
        print(f"   ✅ 공격 실행 완료: {result.status.value}")
        print(f"   📊 응답시간: {result.response_time:.2f}초")
        print(f"   📋 IOC 수집: {len(result.iocs)}개")
        
        # 5. CTI 데이터 확인
        print("5️⃣  CTI 데이터 확인...")
        cti_summary = cti.get_summary()
        print(f"   📊 수집된 지표: {cti_summary['total_indicators']}개")
        
        print("\n✅ 최소 기능 테스트 성공!")
        return True
        
    except Exception as e:
        print(f"\n❌ 최소 테스트 실패: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

async def full_test():
    """전체 기능 테스트"""
    print("\n🚀 전체 기능 테스트 시작...")
    
    try:
        # 1. 설정 및 초기화
        print("1️⃣  설정 및 초기화...")
        Path("results").mkdir(exist_ok=True)
        config = await create_test_config()
        
        dvd = DVDLite("config.json")
        cti = SimpleCTI(config.get("cti", {}))
        dvd.register_cti_collector(cti)
        print("   ✅ 초기화 완료")
        
        # 2. 모든 공격 등록
        print("2️⃣  공격 모듈 등록...")
        attack_names = register_all_attacks(dvd)
        print(f"   ✅ {len(attack_names)}개 공격 등록")
        print(f"   📋 등록된 공격: {', '.join(attack_names[:4])}...")
        
        # 3. 샘플 공격 실행
        print("3️⃣  샘플 공격 실행...")
        sample_attacks = ["wifi_scan", "drone_discovery"]
        
        for i, attack_name in enumerate(sample_attacks, 1):
            print(f"   공격 {i}/{len(sample_attacks)}: {attack_name}")
            result = await dvd.run_attack(attack_name)
            status_icon = "✅" if result.status == AttackStatus.SUCCESS else "❌"
            print(f"     {status_icon} 결과: {result.status.value}")
            
            if i < len(sample_attacks):
                await asyncio.sleep(0.5)  # 짧은 대기
        
        # 4. 결과 요약
        print("4️⃣  결과 요약...")
        summary = dvd.get_summary()
        print(f"   📊 총 공격: {summary['total_attacks']}")
        print(f"   🎯 성공률: {summary['success_rate']}")
        
        # 5. CTI 요약
        print("5️⃣  CTI 요약...")
        cti_summary = cti.get_summary()
        print(f"   📋 수집 지표: {cti_summary['total_indicators']}개")
        print(f"   📊 공격 패턴: {cti_summary['total_patterns']}개")
        
        # 6. 데이터 저장
        print("6️⃣  데이터 저장...")
        results_file = dvd.export_results()
        cti_json = cti.export_json()
        cti_csv = cti.export_csv()
        
        print(f"   💾 공격 결과: {results_file}")
        print(f"   💾 CTI JSON: {cti_json}")
        print(f"   💾 CTI CSV: {cti_csv}")
        
        print("\n🎉 전체 기능 테스트 성공!")
        return True
        
    except Exception as e:
        print(f"\n❌ 전체 테스트 실패: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """메인 함수"""
    print("🚁 DVD-Lite 수정된 테스트 스크립트")
    print("=" * 50)
    
    try:
        # 최소 기능 테스트
        if await minimal_test():
            print("\n" + "=" * 50)
            
            # 전체 기능 테스트
            if await full_test():
                print("\n🎊 모든 테스트 성공!")
                print("\n📁 생성된 파일들:")
                print("   - config.json")
                print("   - results/dvd_lite_results_*.json")
                print("   - results/cti_data_*.json")
                print("   - results/cti_indicators_*.csv")
                
                print("\n🎯 다음 단계:")
                print("   1. 실제 DVD 환경과 연동")
                print("   2. 추가 공격 모듈 개발")
                print("   3. CTI 분석 도구 구축")
                
            else:
                print("\n⚠️  최소 기능은 작동하지만 일부 문제가 있습니다.")
        else:
            print("\n💡 문제 해결:")
            print("   1. 모든 파일이 올바르게 생성되었는지 확인")
            print("   2. PYTHONPATH 설정: export PYTHONPATH=$PWD:$PYTHONPATH")
            print("   3. 가상환경 사용 권장")
            
    except KeyboardInterrupt:
        print("\n👋 테스트 중단됨")
    except Exception as e:
        print(f"\n💥 예상치 못한 오류: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())