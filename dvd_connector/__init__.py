# dvd_connector/__init__.py
"""
DVD-Lite ↔ Damn Vulnerable Drone 연계 모듈
실제 DVD 환경과의 안전한 연결 및 통신을 제공
"""

__version__ = "1.0.0"
__author__ = "DVD-Lite Team"
__description__ = "DVD 연결 및 안전성 관리 모듈"

try:
    from .connector import DVDConnector, DVDEnvironment, DVDConnectionConfig, DVDConnectionStatus, DVDStatus
    from .safety_checker import SafetyChecker, SafetyLevel, NetworkType, SafetyCheckResult, quick_safety_check
    from .network_scanner import DVDNetworkScanner, NetworkDevice, NetworkService, NetworkScanResult, quick_dvd_scan, find_drone_devices
    
    # 편의 함수들
    from .connector import create_dvd_connection, test_dvd_connection
    
    DVD_CONNECTOR_AVAILABLE = True
    
except ImportError as e:
    print(f"Warning: DVD Connector 모듈 import 오류: {e}")
    DVD_CONNECTOR_AVAILABLE = False
    
    # 기본값들
    DVDConnector = None
    DVDEnvironment = None
    DVDConnectionConfig = None
    DVDConnectionStatus = None
    DVDStatus = None
    SafetyChecker = None
    SafetyLevel = None
    NetworkType = None
    SafetyCheckResult = None
    quick_safety_check = None
    DVDNetworkScanner = None
    NetworkDevice = None
    NetworkService = None
    NetworkScanResult = None
    quick_dvd_scan = None
    find_drone_devices = None
    create_dvd_connection = None
    test_dvd_connection = None

__all__ = [
    # 연결 관리
    "DVDConnector",
    "DVDEnvironment", 
    "DVDConnectionConfig",
    "DVDConnectionStatus",
    "DVDStatus",
    "create_dvd_connection",
    "test_dvd_connection",
    
    # 안전성 검사
    "SafetyChecker",
    "SafetyLevel",
    "NetworkType", 
    "SafetyCheckResult",
    "quick_safety_check",
    
    # 네트워크 스캐너
    "DVDNetworkScanner",
    "NetworkDevice",
    "NetworkService",
    "NetworkScanResult",
    "quick_dvd_scan",
    "find_drone_devices",
    
    # 상태 플래그
    "DVD_CONNECTOR_AVAILABLE"
]

# None 값들은 __all__에서 제거
__all__ = [item for item in __all__ if globals().get(item) is not None]

# 편의 함수들
def get_available_features():
    """사용 가능한 기능 목록 반환"""
    features = {
        "dvd_connector": DVD_CONNECTOR_AVAILABLE,
        "safety_checker": SafetyChecker is not None,
        "network_scanner": DVDNetworkScanner is not None
    }
    return features

def print_connection_status():
    """연결 상태 정보 출력"""
    print("\n🔗 DVD Connector 모듈 상태")
    print("="*40)
    
    features = get_available_features()
    
    for feature, available in features.items():
        status = "✅ 사용 가능" if available else "❌ 사용 불가"
        print(f"{feature}: {status}")
    
    if DVD_CONNECTOR_AVAILABLE:
        print("\n🚀 사용 예시:")
        print("  from dvd_connector import DVDConnector, SafetyChecker")
        print("  connector = DVDConnector()")
        print("  await connector.connect()")
    else:
        print("\n⚠️ 모듈을 사용하려면 다음을 확인하세요:")
        print("  1. 필요한 의존성 설치")
        print("  2. Python 경로 설정")
        print("  3. 모듈 파일 존재 여부")
    
    print("="*40)

# 모듈 로드 시 자동 상태 확인 (디버그 모드)
import os
if os.getenv("DVD_DEBUG"):
    print_connection_status()