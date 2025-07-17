"""
기본 테스트
"""
import unittest
import sys
import os

# 프로젝트 루트를 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestBasic(unittest.TestCase):
    
    def test_imports(self):
        """기본 import 테스트"""
        try:
            from dvd_lite.main import DVDLite, BaseAttack, AttackType
            from dvd_lite.dvd_attacks.core.enums import DVDAttackTactic, DVDFlightState
            print("✅ 기본 import 성공")
        except ImportError as e:
            self.fail(f"Import 실패: {e}")
    
    def test_dvd_lite_creation(self):
        """DVD-Lite 인스턴스 생성 테스트"""
        try:
            from dvd_lite.main import DVDLite
            dvd = DVDLite()
            self.assertIsInstance(dvd, DVDLite)
            print("✅ DVD-Lite 인스턴스 생성 성공")
        except Exception as e:
            self.fail(f"DVD-Lite 생성 실패: {e}")

if __name__ == "__main__":
    unittest.main()
