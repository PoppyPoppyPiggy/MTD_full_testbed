# dvd_lite/cti.py
"""
DVD-Lite CTI 수집기
간단한 위협 정보 수집 및 내보내기
"""

import json
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from pathlib import Path

# ThreatIndicator를 여기서 정의
@dataclass
class ThreatIndicator:
    ioc_type: str
    value: str
    confidence: int
    attack_type: str
    timestamp: datetime
    source: str = "dvd-lite"

# =============================================================================
# 간단한 CTI 수집기
# =============================================================================

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
        # IOC에서 위협 지표 생성
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
            "avg_response_time": attack_result.response_time,
            "last_seen": datetime.fromtimestamp(attack_result.timestamp).isoformat(),
            "ioc_count": len(attack_result.iocs)
        }
        
        # 통계 업데이트
        self._update_statistics()
    
    def _create_indicator(self, ioc: str, attack_result) -> Optional[ThreatIndicator]:
        """IOC에서 위협 지표 생성"""
        try:
            # IOC 파싱
            if ":" in ioc:
                ioc_type, value = ioc.split(":", 1)
            else:
                ioc_type = "unknown"
                value = ioc
            
            # 신뢰도 계산
            confidence = self._calculate_confidence(ioc_type, attack_result)
            
            # 최소 신뢰도 확인
            if confidence < self.config["confidence_threshold"]:
                return None
            
            indicator = ThreatIndicator(
                ioc_type=ioc_type.lower(),
                value=value,
                confidence=confidence,
                attack_type=attack_result.attack_type.value,
                timestamp=datetime.fromtimestamp(attack_result.timestamp),
                source="dvd-lite"
            )
            
            return indicator
            
        except Exception:
            return None
    
    def _calculate_confidence(self, ioc_type: str, attack_result) -> int:
        """IOC 신뢰도 계산"""
        base_confidence = 70
        
        # 공격 성공 여부에 따른 조정
        if attack_result.status.value == "success":
            confidence_modifier = 15
        elif attack_result.status.value == "detected":
            confidence_modifier = 10
        else:
            confidence_modifier = -20
        
        # IOC 타입별 조정
        type_modifiers = {
            "mavlink_msg": 10,
            "mavlink_host": 15,
            "command_injected": 20,
            "fake_gps": 25,
            "waypoint_injected": 18,
            "log_extracted": 12,
            "param_extracted": 10
        }
        
        type_modifier = type_modifiers.get(ioc_type, 0)
        
        final_confidence = base_confidence + confidence_modifier + type_modifier
        return max(10, min(100, final_confidence))
    
    def _update_statistics(self):
        """통계 업데이트"""
        self.statistics["total_indicators"] = len(self.indicators)
        self.statistics["last_update"] = datetime.now().isoformat()
        
        # 공격 타입별 통계
        type_counts = {}
        confidence_counts = {"high": 0, "medium": 0, "low": 0}
        
        for indicator in self.indicators:
            # 공격 타입별
            attack_type = indicator.attack_type
            type_counts[attack_type] = type_counts.get(attack_type, 0) + 1
            
            # 신뢰도별
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
        
        # 결과 디렉토리 생성
        Path(filename).parent.mkdir(parents=True, exist_ok=True)
        
        # 내보낼 데이터 구성
        export_data = {
            "metadata": {
                "export_time": datetime.now().isoformat(),
                "total_indicators": len(self.indicators),
                "total_patterns": len(self.attack_patterns),
                "source": "dvd-lite"
            },
            "statistics": self.statistics,
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
            ],
            "attack_patterns": self.attack_patterns
        }
        
        # JSON 파일로 저장
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        return filename
    
    def export_csv(self, filename: str = None) -> str:
        """CSV 형식으로 내보내기"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"results/cti_indicators_{timestamp}.csv"
        
        # 결과 디렉토리 생성
        Path(filename).parent.mkdir(parents=True, exist_ok=True)
        
        # CSV 내용 생성
        csv_lines = [
            "IOC_Type,Value,Confidence,Attack_Type,Timestamp,Source"
        ]
        
        for ind in self.indicators:
            line = f"{ind.ioc_type},{ind.value},{ind.confidence},{ind.attack_type},{ind.timestamp.isoformat()},{ind.source}"
            csv_lines.append(line)
        
        # CSV 파일로 저장
        with open(filename, 'w', encoding='utf-8') as f:
            f.write('\n'.join(csv_lines))
        
        return filename
    
    def query_indicators(self, **filters) -> List[ThreatIndicator]:
        """지표 쿼리"""
        results = []
        
        for indicator in self.indicators:
            match = True
            
            # 필터 조건 확인
            for key, value in filters.items():
                if key == "ioc_type" and indicator.ioc_type != value:
                    match = False
                    break
                elif key == "attack_type" and indicator.attack_type != value:
                    match = False
                    break
                elif key == "min_confidence" and indicator.confidence < value:
                    match = False
                    break
            
            if match:
                results.append(indicator)
        
        return results
    
    def print_summary(self):
        """요약 정보 출력"""
        summary = self.get_summary()
        
        print("\n" + "="*40)
        print("🔍 CTI 수집 결과 요약")
        print("="*40)
        print(f"수집된 지표: {summary['total_indicators']}개")
        print(f"공격 패턴: {summary['total_patterns']}개")
        
        if summary["statistics"]["by_attack_type"]:
            print("\n📊 공격 타입별 분포:")
            for attack_type, count in summary["statistics"]["by_attack_type"].items():
                print(f"  - {attack_type}: {count}개")
        
        print(f"\n🎯 신뢰도 분포:")
        confidence_stats = summary["statistics"]["by_confidence"]
        print(f"  - 높음 (80+): {confidence_stats['high']}개")
        print(f"  - 중간 (60-79): {confidence_stats['medium']}개")
        print(f"  - 낮음 (<60): {confidence_stats['low']}개")
        
        if summary["recent_indicators"]:
            print(f"\n📋 최근 지표 (최신 5개):")
            for i, ind in enumerate(summary["recent_indicators"], 1):
                print(f"  {i}. {ind['type']}: {ind['value']} (신뢰도: {ind['confidence']})")
        
        print("="*40)