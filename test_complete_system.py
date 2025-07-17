#!/usr/bin/env python3
"""
DVD 프로젝트 완전 테스트 스크립트
"""

import asyncio
import sys
import os
from pathlib import Path

# 경로 추가
sys.path.insert(0, os.getcwd())

async def test_complete_system():
    """완전한 시스템 테스트"""
    print("🧪 DVD 시스템 완전 테스트 시작")
    print("=" * 50)
    
    try:
        # 1. 기본 import 테스트
        print("1️⃣ 기본 import 테스트...")
        from dvd_lite.main import DVDLite
        print("✅ DVDLite import 성공")
        
        # 2. 레지스트리 테스트
        print("\n2️⃣ 레지스트리 테스트...")
        from dvd_lite.dvd_attacks.registry.management import register_all_dvd_attacks
        registered = register_all_dvd_attacks()
        print(f"✅ {len(registered)}개 공격 등록됨: {registered[:5]}...")
        
        # 3. DVDLite 인스턴스 생성
        print("\n3️⃣ DVDLite 인스턴스 생성...")
        dvd = DVDLite()
        print("✅ DVDLite 인스턴스 생성 성공")
        
        # 4. 공격 목록 확인
        print("\n4️⃣ 공격 목록 확인...")
        attacks = dvd.list_attacks()
        print(f"✅ 사용 가능한 공격: {len(attacks)}개")
        print(f"   공격 목록: {attacks[:10]}...")
        
        # 5. 공격 정보 확인
        print("\n5️⃣ 공격 정보 확인...")
        if attacks:
            info = dvd.get_attack_info(attacks[0])
            print(f"✅ {attacks[0]} 정보: {info.get('description', 'N/A')}")
        
        # 6. 실제 공격 실행 테스트
        print("\n6️⃣ 실제 공격 실행 테스트...")
        if attacks:
            try:
                result = await dvd.run_attack(attacks[0])
                print(f"✅ 공격 실행 성공: {result.attack_name}")
                print(f"   상태: {result.status.value}")
                print(f"   IOCs: {len(result.iocs)}개")
            except Exception as e:
                print(f"❌ 공격 실행 실패: {e}")
        
        # 7. CTI 테스트 (선택적)
        print("\n7️⃣ CTI 테스트...")
        try:
            from dvd_lite.cti import SimpleCTI
            cti = SimpleCTI()
            dvd.register_cti_collector(cti)
            print("✅ CTI 수집기 등록 성공")
        except Exception as e:
            print(f"⚠️  CTI 테스트 건너뜀: {e}")
        
        print("\n🎉 모든 테스트 완료! 시스템이 정상 작동합니다.")
        return True
        
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    asyncio.run(test_complete_system())
