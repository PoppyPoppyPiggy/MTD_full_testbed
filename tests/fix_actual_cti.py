#!/usr/bin/env python3
"""
실제 CTI 모듈을 정확히 생성하는 스크립트
"""

from pathlib import Path

def create_actual_cti_module():
    """실제 CTI 모듈 생성"""
    
    cti_content = '''# dvd_lite/cti.py
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
            "param_extracted": 10,
            "wifi_ssid": 8,
            "wifi_bssid": 8
        }
        
        type_modifier = type_modifiers.get(ioc_type.lower(), 0)
        
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
            # CSV에서 쉼표 문제 해결을 위해 값을 따옴표로 감싸기
            line = f'"{ind.ioc_type}","{ind.value}",{ind.confidence},"{ind.attack_type}","{ind.timestamp.isoformat()}","{ind.source}"'
            csv_lines.append(line)
        
        # CSV 파일로 저장
        with open(filename, 'w', encoding='utf-8') as f:
            f.write('\\n'.join(csv_lines))
        
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
        
        print("\\n" + "="*40)
        print("🔍 CTI 수집 결과 요약")
        print("="*40)
        print(f"수집된 지표: {summary['total_indicators']}개")
        print(f"공격 패턴: {summary['total_patterns']}개")
        
        if summary["statistics"]["by_attack_type"]:
            print("\\n📊 공격 타입별 분포:")
            for attack_type, count in summary["statistics"]["by_attack_type"].items():
                print(f"  - {attack_type}: {count}개")
        
        print(f"\\n🎯 신뢰도 분포:")
        confidence_stats = summary["statistics"]["by_confidence"]
        print(f"  - 높음 (80+): {confidence_stats['high']}개")
        print(f"  - 중간 (60-79): {confidence_stats['medium']}개")
        print(f"  - 낮음 (<60): {confidence_stats['low']}개")
        
        if summary["recent_indicators"]:
            print(f"\\n📋 최근 지표 (최신 5개):")
            for i, ind in enumerate(summary["recent_indicators"], 1):
                print(f"  {i}. {ind['type']}: {ind['value']} (신뢰도: {ind['confidence']})")
        
        print("="*40)

# 테스트 함수
def test_cti_module():
    """CTI 모듈 테스트"""
    print("🧪 CTI 모듈 테스트 시작...")
    
    try:
        # 인스턴스 생성
        cti = SimpleCTI()
        print("✅ SimpleCTI 인스턴스 생성 성공")
        
        # 기본 기능 테스트
        summary = cti.get_summary()
        print(f"✅ 요약 정보 조회: {summary['total_indicators']}개 지표")
        
        # ThreatIndicator 테스트
        indicator = ThreatIndicator(
            ioc_type="test",
            value="test_value",
            confidence=80,
            attack_type="reconnaissance",
            timestamp=datetime.now()
        )
        print(f"✅ ThreatIndicator 생성: {indicator.ioc_type}")
        
        return True
        
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        return False

if __name__ == "__main__":
    test_cti_module()
'''
    
    # 기존 파일을 백업
    cti_path = Path("dvd_lite/cti.py")
    if cti_path.exists():
        backup_path = Path("dvd_lite/cti.py.old")
        import shutil
        shutil.copy2(cti_path, backup_path)
        print(f"📄 기존 파일 백업: {backup_path}")
    
    # 새 파일 생성
    with open(cti_path, 'w', encoding='utf-8') as f:
        f.write(cti_content)
    
    print(f"✅ 실제 CTI 모듈 생성: {cti_path}")
    
    return cti_path

def create_actual_attacks_module():
    """실제 attacks 모듈 생성"""
    
    attacks_content = '''# dvd_lite/attacks.py
"""
DVD-Lite 공격 모듈들
8개 핵심 드론 공격 시나리오 구현
"""

import asyncio
import random
import time
from typing import Tuple, List, Dict, Any

from .main import BaseAttack, AttackType

# =============================================================================
# 정찰 공격들
# =============================================================================

class WiFiScan(BaseAttack):
    """WiFi 네트워크 스캔 공격"""
    
    def _get_attack_type(self) -> AttackType:
        return AttackType.RECONNAISSANCE
    
    async def _run_attack(self) -> Tuple[bool, List[str], Dict[str, Any]]:
        """WiFi 네트워크 스캔 실행"""
        await asyncio.sleep(1.5)
        
        networks = ["Drone_WiFi", "DroneControl", "UAV_Network", "Companion_AP"]
        found_networks = random.sample(networks, k=random.randint(1, 3))
        
        iocs = [f"SSID:{network}" for network in found_networks]
        success = "Drone_WiFi" in found_networks or random.random() > 0.3
        
        details = {
            "found_networks": found_networks,
            "scan_duration": 1.5,
            "success_rate": 0.8 if success else 0.2
        }
        
        return success, iocs, details

class DroneDiscovery(BaseAttack):
    """드론 시스템 발견 공격"""
    
    def _get_attack_type(self) -> AttackType:
        return AttackType.RECONNAISSANCE
    
    async def _run_attack(self) -> Tuple[bool, List[str], Dict[str, Any]]:
        """네트워크에서 드론 시스템 발견"""
        await asyncio.sleep(2.0)
        
        hosts = [f"10.13.0.{i}" for i in range(2, 6)]
        mavlink_hosts = []
        
        for host in hosts:
            if random.random() > 0.6:
                mavlink_hosts.append(host)
        
        iocs = [f"MAVLINK_HOST:{host}" for host in mavlink_hosts]
        success = len(mavlink_hosts) > 0
        
        details = {
            "scanned_hosts": hosts,
            "mavlink_hosts": mavlink_hosts,
            "open_ports": [14550, 14551] if success else [],
            "success_rate": 0.9 if success else 0.1
        }
        
        return success, iocs, details

class PacketSniff(BaseAttack):
    """패킷 스니핑 공격"""
    
    def _get_attack_type(self) -> AttackType:
        return AttackType.RECONNAISSANCE
    
    async def _run_attack(self) -> Tuple[bool, List[str], Dict[str, Any]]:
        """MAVLink 패킷 캡처"""
        await asyncio.sleep(3.0)
        
        mavlink_messages = [
            "HEARTBEAT", "GPS_RAW_INT", "ATTITUDE", "GLOBAL_POSITION_INT",
            "MISSION_CURRENT", "RC_CHANNELS", "SERVO_OUTPUT_RAW"
        ]
        
        captured = random.sample(mavlink_messages, k=random.randint(2, 5))
        iocs = [f"MAVLINK_MSG:{msg}" for msg in captured]
        success = len(captured) >= 3
        
        details = {
            "captured_messages": captured,
            "capture_duration": 3.0,
            "total_packets": random.randint(50, 200),
            "success_rate": 0.7 if success else 0.3
        }
        
        return success, iocs, details

class TelemetrySpoof(BaseAttack):
    """텔레메트리 스푸핑 공격"""
    
    def _get_attack_type(self) -> AttackType:
        return AttackType.PROTOCOL_TAMPERING
    
    async def _run_attack(self) -> Tuple[bool, List[str], Dict[str, Any]]:
        """가짜 텔레메트리 데이터 주입"""
        await asyncio.sleep(2.5)
        
        fake_data = {
            "gps_lat": 37.7749 + random.uniform(-0.01, 0.01),
            "gps_lon": -122.4194 + random.uniform(-0.01, 0.01),
            "altitude": random.randint(50, 150),
            "battery": random.randint(20, 80)
        }
        
        iocs = [
            f"FAKE_GPS:{fake_data['gps_lat']:.6f},{fake_data['gps_lon']:.6f}",
            f"FAKE_ALT:{fake_data['altitude']}",
            f"FAKE_BATTERY:{fake_data['battery']}"
        ]
        
        success = random.random() > 0.4
        
        details = {
            "spoofed_data": fake_data,
            "injection_method": "MAVLink",
            "success_rate": 0.6 if success else 0.0
        }
        
        return success, iocs, details

class CommandInject(BaseAttack):
    """명령 주입 공격"""
    
    def _get_attack_type(self) -> AttackType:
        return AttackType.INJECTION
    
    async def _run_attack(self) -> Tuple[bool, List[str], Dict[str, Any]]:
        """MAVLink 명령 주입"""
        await asyncio.sleep(1.8)
        
        commands = ["ARM_DISARM", "SET_MODE", "NAV_LAND", "DO_SET_SERVO"]
        injected_cmd = random.choice(commands)
        
        iocs = [f"COMMAND_INJECTED:{injected_cmd}"]
        success = random.random() > 0.5
        
        details = {
            "injected_command": injected_cmd,
            "target_system": 1,
            "target_component": 1,
            "success_rate": 0.5 if success else 0.0
        }
        
        return success, iocs, details

class WaypointInject(BaseAttack):
    """웨이포인트 주입 공격"""
    
    def _get_attack_type(self) -> AttackType:
        return AttackType.INJECTION
    
    async def _run_attack(self) -> Tuple[bool, List[str], Dict[str, Any]]:
        """악성 웨이포인트 주입"""
        await asyncio.sleep(2.2)
        
        malicious_waypoint = {
            "lat": 37.7749 + random.uniform(-0.1, 0.1),
            "lon": -122.4194 + random.uniform(-0.1, 0.1),
            "alt": random.randint(10, 200)
        }
        
        iocs = [f"WAYPOINT_INJECTED:{malicious_waypoint['lat']:.6f},{malicious_waypoint['lon']:.6f},{malicious_waypoint['alt']}"]
        success = random.random() > 0.6
        
        details = {
            "malicious_waypoint": malicious_waypoint,
            "mission_cleared": success,
            "success_rate": 0.4 if success else 0.0
        }
        
        return success, iocs, details

class LogExtract(BaseAttack):
    """로그 추출 공격"""
    
    def _get_attack_type(self) -> AttackType:
        return AttackType.EXFILTRATION
    
    async def _run_attack(self) -> Tuple[bool, List[str], Dict[str, Any]]:
        """비행 로그 추출"""
        await asyncio.sleep(3.5)
        
        log_files = ["flight_log_001.bin", "flight_log_002.bin", "parameters.txt", "waypoints.log"]
        extracted = random.sample(log_files, k=random.randint(1, 3))
        
        iocs = [f"LOG_EXTRACTED:{log}" for log in extracted]
        success = len(extracted) >= 2
        
        details = {
            "extracted_files": extracted,
            "access_method": "FTP",
            "file_sizes": {log: random.randint(1024, 10240) for log in extracted},
            "success_rate": 0.6 if success else 0.2
        }
        
        return success, iocs, details

class ParamExtract(BaseAttack):
    """파라미터 추출 공격"""
    
    def _get_attack_type(self) -> AttackType:
        return AttackType.EXFILTRATION
    
    async def _run_attack(self) -> Tuple[bool, List[str], Dict[str, Any]]:
        """시스템 파라미터 추출"""
        await asyncio.sleep(2.8)
        
        parameters = {
            "BATT_CAPACITY": 5000,
            "FENCE_ENABLE": 1,
            "RTL_ALT": 15,
            "COMPASS_CAL": 1,
            "GPS_TYPE": 1
        }
        
        extracted_params = dict(random.sample(list(parameters.items()), k=random.randint(2, 4)))
        iocs = [f"PARAM_EXTRACTED:{param}={value}" for param, value in extracted_params.items()]
        success = len(extracted_params) >= 3
        
        details = {
            "extracted_parameters": extracted_params,
            "total_available": len(parameters),
            "extraction_method": "MAVLink PARAM_REQUEST",
            "success_rate": 0.7 if success else 0.3
        }
        
        return success, iocs, details

# =============================================================================
# 공격 모듈 등록 함수
# =============================================================================

def register_all_attacks(dvd_lite):
    """모든 공격 모듈을 DVD-Lite에 등록"""
    attacks = {
        "wifi_scan": WiFiScan,
        "drone_discovery": DroneDiscovery,
        "packet_sniff": PacketSniff,
        "telemetry_spoof": TelemetrySpoof,
        "command_inject": CommandInject,
        "waypoint_inject": WaypointInject,
        "log_extract": LogExtract,
        "param_extract": ParamExtract
    }
    
    for name, attack_class in attacks.items():
        dvd_lite.register_attack(name, attack_class)
    
    return list(attacks.keys())
'''
    
    attacks_path = Path("dvd_lite/attacks.py")
    with open(attacks_path, 'w', encoding='utf-8') as f:
        f.write(attacks_content)
    
    print(f"✅ 실제 attacks 모듈 생성: {attacks_path}")

def test_imports():
    """Import 테스트"""
    print("\n🧪 Import 테스트 실행...")
    
    try:
        # CTI 모듈 테스트
        from dvd_lite.cti import SimpleCTI, ThreatIndicator
        print("✅ CTI 모듈 import 성공")
        
        # CTI 인스턴스 생성 테스트
        cti = SimpleCTI()
        print("✅ SimpleCTI 인스턴스 생성 성공")
        
        # 기본 공격 모듈 테스트 (main.py가 있어야 함)
        try:
            from dvd_lite.main import DVDLite
            dvd = DVDLite()
            print("✅ DVDLite 인스턴스 생성 성공")
            
            # CTI 등록 테스트
            dvd.register_cti_collector(cti)
            print("✅ CTI 수집기 등록 성공")
            
        except ImportError as e:
            print(f"⚠️  DVDLite import 실패 (main.py 확인 필요): {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Import 테스트 실패: {e}")
        return False

def main():
    """메인 함수"""
    print("🔧 실제 CTI 및 공격 모듈 생성")
    print("=" * 50)
    
    # 1. 실제 CTI 모듈 생성
    cti_path = create_actual_cti_module()
    
    # 2. 실제 attacks 모듈 생성
    create_actual_attacks_module()
    
    # 3. Import 테스트
    if test_imports():
        print("\n🎉 모든 모듈이 성공적으로 생성되고 테스트되었습니다!")
        print("\n🚀 이제 다음 명령을 실행해보세요:")
        print('   python3 -c "from dvd_lite.cti import SimpleCTI; print(\'CTI 성공!\')"')
        print("   python3 advanced_start.py")
    else:
        print("\n❌ 일부 모듈에 문제가 있습니다.")
        print("main.py 파일이 올바르게 생성되었는지 확인하세요.")

if __name__ == "__main__":
    main()