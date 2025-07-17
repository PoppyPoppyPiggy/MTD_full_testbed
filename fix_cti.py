#!/usr/bin/env python3
"""
CTI 모듈 문제 진단 및 수정 스크립트
"""

import os
import sys
from pathlib import Path

def check_cti_file():
    """CTI 파일 상태 확인"""
    print("🔍 CTI 파일 상태 확인...")
    
    cti_path = Path("dvd_lite/cti.py")
    
    if not cti_path.exists():
        print("❌ dvd_lite/cti.py 파일이 없습니다!")
        return False
    
    print(f"✅ CTI 파일 존재: {cti_path}")
    print(f"📏 파일 크기: {cti_path.stat().st_size} bytes")
    
    # 파일 내용 확인
    try:
        with open(cti_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        print(f"📄 파일 내용 길이: {len(content)} 문자")
        
        # SimpleCTI 클래스가 있는지 확인
        if "class SimpleCTI" in content:
            print("✅ SimpleCTI 클래스 발견")
        else:
            print("❌ SimpleCTI 클래스 없음")
            return False
        
        # ThreatIndicator 클래스가 있는지 확인
        if "class ThreatIndicator" in content:
            print("✅ ThreatIndicator 클래스 발견")
        else:
            print("❌ ThreatIndicator 클래스 없음")
        
        # 파일 첫 부분 확인
        print("\n📋 파일 시작 부분 (첫 10줄):")
        lines = content.split('\n')[:10]
        for i, line in enumerate(lines, 1):
            print(f"  {i:2d}: {line}")
        
        # 문법 오류 확인
        try:
            compile(content, cti_path, 'exec')
            print("✅ 문법 검사 통과")
        except SyntaxError as e:
            print(f"❌ 문법 오류: {e}")
            print(f"   라인 {e.lineno}: {e.text}")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ 파일 읽기 오류: {e}")
        return False

def test_import():
    """import 테스트"""
    print("\n🧪 Import 테스트...")
    
    # 현재 디렉토리를 Python 경로에 추가
    sys.path.insert(0, os.getcwd())
    
    try:
        # 모듈 import 테스트
        import dvd_lite.cti
        print("✅ dvd_lite.cti 모듈 import 성공")
        
        # 모듈 내용 확인
        print(f"📋 모듈 속성: {dir(dvd_lite.cti)}")
        
        # SimpleCTI 클래스 확인
        if hasattr(dvd_lite.cti, 'SimpleCTI'):
            print("✅ SimpleCTI 클래스 발견")
            SimpleCTI = dvd_lite.cti.SimpleCTI
            print(f"📋 SimpleCTI 타입: {type(SimpleCTI)}")
        else:
            print("❌ SimpleCTI 클래스 없음")
            return False
        
        # ThreatIndicator 클래스 확인
        if hasattr(dvd_lite.cti, 'ThreatIndicator'):
            print("✅ ThreatIndicator 클래스 발견")
        else:
            print("❌ ThreatIndicator 클래스 없음")
        
        # 인스턴스 생성 테스트
        try:
            cti = SimpleCTI()
            print("✅ SimpleCTI 인스턴스 생성 성공")
        except Exception as e:
            print(f"❌ SimpleCTI 인스턴스 생성 실패: {e}")
            return False
        
        return True
        
    except ImportError as e:
        print(f"❌ Import 오류: {e}")
        return False
    except Exception as e:
        print(f"❌ 예상치 못한 오류: {e}")
        return False

def create_minimal_cti():
    """최소 기능 CTI 모듈 생성"""
    print("\n🔧 최소 기능 CTI 모듈 생성...")
    
    content = '''# dvd_lite/cti.py
"""
DVD-Lite CTI 수집기 (최소 버전)
"""

import json
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from pathlib import Path

@dataclass
class ThreatIndicator:
    """위협 지표 데이터 클래스"""
    ioc_type: str
    value: str
    confidence: int
    attack_type: str
    timestamp: datetime
    source: str = "dvd-lite"

class SimpleCTI:
    """간단한 CTI 수집기"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {"confidence_threshold": 60, "export_format": "json"}
        self.indicators = []
        self.attack_patterns = {}
        self.statistics = {
            "total_indicators": 0,
            "by_attack_type": {},
            "by_confidence": {"high": 0, "medium": 0, "low": 0},
            "last_update": None
        }
    
    async def collect_from_result(self, attack_result):
        """공격 결과에서 CTI 수집"""
        for ioc in attack_result.iocs:
            indicator = self._create_indicator(ioc, attack_result)
            if indicator:
                self.indicators.append(indicator)
        
        # 공격 패턴 저장
        pattern_id = f"{attack_result.attack_type.value}_{attack_result.attack_name}"
        self.attack_patterns[pattern_id] = {
            "attack_name": attack_result.attack_name,
            "attack_type": attack_result.attack_type.value,
            "success_rate": attack_result.success_rate,
            "last_seen": datetime.now().isoformat(),
            "ioc_count": len(attack_result.iocs)
        }
        
        self._update_statistics()
    
    def _create_indicator(self, ioc: str, attack_result) -> Optional[ThreatIndicator]:
        """IOC에서 위협 지표 생성"""
        try:
            if ":" in ioc:
                ioc_type, value = ioc.split(":", 1)
            else:
                ioc_type = "unknown"
                value = ioc
            
            confidence = self._calculate_confidence(ioc_type, attack_result)
            
            if confidence < self.config["confidence_threshold"]:
                return None
            
            return ThreatIndicator(
                ioc_type=ioc_type.lower(),
                value=value,
                confidence=confidence,
                attack_type=attack_result.attack_type.value,
                timestamp=datetime.now(),
                source="dvd-lite"
            )
        except Exception:
            return None
    
    def _calculate_confidence(self, ioc_type: str, attack_result) -> int:
        """IOC 신뢰도 계산"""
        base_confidence = 70
        
        if attack_result.status.value == "success":
            modifier = 15
        else:
            modifier = -20
        
        final_confidence = base_confidence + modifier
        return max(10, min(100, final_confidence))
    
    def _update_statistics(self):
        """통계 업데이트"""
        self.statistics["total_indicators"] = len(self.indicators)
        self.statistics["last_update"] = datetime.now().isoformat()
        
        # 공격 타입별 통계
        type_counts = {}
        confidence_counts = {"high": 0, "medium": 0, "low": 0}
        
        for indicator in self.indicators:
            attack_type = indicator.attack_type
            type_counts[attack_type] = type_counts.get(attack_type, 0) + 1
            
            if indicator.confidence >= 80:
                confidence_counts["high"] += 1
            elif indicator.confidence >= 60:
                confidence_counts["medium"] += 1
            else:
                confidence_counts["low"] += 1
        
        self.statistics["by_attack_type"] = type_counts
        self.statistics["by_confidence"] = confidence_counts
    
    def get_summary(self) -> Dict[str, Any]:
        """위협 정보 요약"""
        return {
            "total_indicators": len(self.indicators),
            "total_patterns": len(self.attack_patterns),
            "statistics": self.statistics,
            "recent_indicators": [
                {
                    "type": ind.ioc_type,
                    "value": ind.value[:50] + "..." if len(ind.value) > 50 else ind.value,
                    "confidence": ind.confidence,
                    "attack_type": ind.attack_type
                }
                for ind in sorted(self.indicators, key=lambda x: x.timestamp, reverse=True)[:5]
            ]
        }
    
    def export_json(self, filename: str = None) -> str:
        """JSON 형식으로 내보내기"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"results/cti_data_{timestamp}.json"
        
        Path(filename).parent.mkdir(parents=True, exist_ok=True)
        
        export_data = {
            "metadata": {
                "export_time": datetime.now().isoformat(),
                "total_indicators": len(self.indicators),
                "source": "dvd-lite"
            },
            "indicators": [
                {
                    "ioc_type": ind.ioc_type,
                    "value": ind.value,
                    "confidence": ind.confidence,
                    "attack_type": ind.attack_type,
                    "timestamp": ind.timestamp.isoformat(),
                    "source": ind.source
                }
                for ind in self.indicators
            ]
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        return filename
    
    def export_csv(self, filename: str = None) -> str:
        """CSV 형식으로 내보내기"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"results/cti_indicators_{timestamp}.csv"
        
        Path(filename).parent.mkdir(parents=True, exist_ok=True)
        
        csv_lines = ["IOC_Type,Value,Confidence,Attack_Type,Timestamp,Source"]
        
        for ind in self.indicators:
            line = f"{ind.ioc_type},{ind.value},{ind.confidence},{ind.attack_type},{ind.timestamp.isoformat()},{ind.source}"
            csv_lines.append(line)
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write('\\n'.join(csv_lines))
        
        return filename
    
    def print_summary(self):
        """요약 정보 출력"""
        summary = self.get_summary()
        
        print("\\n" + "="*40)
        print("🔍 CTI 수집 결과 요약")
        print("="*40)
        print(f"수집된 지표: {summary['total_indicators']}개")
        print(f"공격 패턴: {summary['total_patterns']}개")
        print("="*40)

# 테스트 함수
def test_cti():
    """CTI 모듈 테스트"""
    print("🧪 CTI 모듈 테스트 시작...")
    
    try:
        cti = SimpleCTI()
        print("✅ SimpleCTI 인스턴스 생성 성공")
        
        # 기본 기능 테스트
        summary = cti.get_summary()
        print(f"✅ 요약 정보: {summary['total_indicators']}개 지표")
        
        return True
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        return False

if __name__ == "__main__":
    test_cti()
'''
    
    # 기존 파일 백업
    cti_path = Path("dvd_lite/cti.py")
    if cti_path.exists():
        backup_path = Path("dvd_lite/cti.py.backup")
        cti_path.rename(backup_path)
        print(f"📄 기존 파일 백업: {backup_path}")
    
    # 새 파일 생성
    with open(cti_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"✅ 새 CTI 파일 생성: {cti_path}")
    return True

def main():
    """메인 함수"""
    print("🔧 CTI 모듈 진단 및 수정 도구")
    print("=" * 50)
    
    # 1. CTI 파일 확인
    if not check_cti_file():
        print("\n❌ CTI 파일에 문제가 있습니다!")
        
        # 최소 기능 CTI 생성
        if input("\n🔧 최소 기능 CTI 모듈을 생성하시겠습니까? (y/n): ").lower() == 'y':
            create_minimal_cti()
        else:
            print("수동으로 CTI 파일을 수정하세요.")
            return
    
    # 2. Import 테스트
    if not test_import():
        print("\n❌ Import 테스트 실패!")
        
        # 최소 기능 CTI 생성
        if input("\n🔧 최소 기능 CTI 모듈을 생성하시겠습니까? (y/n): ").lower() == 'y':
            create_minimal_cti()
            
            # 다시 테스트
            if test_import():
                print("\n✅ 문제 해결됨!")
            else:
                print("\n❌ 여전히 문제가 있습니다.")
        return
    
    print("\n🎉 CTI 모듈이 정상적으로 작동합니다!")
    print("\n🚀 이제 다음 명령을 실행해보세요:")
    print('   python3 -c "from dvd_lite.cti import SimpleCTI; print(\'성공!\')"')
    print("   python3 advanced_start.py")

if __name__ == "__main__":
    main()