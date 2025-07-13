# dvd_connector/__init__.py
"""
DVD-Lite ↔ Damn Vulnerable Drone 연계 모듈
실제 DVD 환경과의 안전한 연동을 위한 모듈
"""

__version__ = "1.0.0"
__author__ = "DVD-Lite Team"
__description__ = "DVD-Lite와 Damn Vulnerable Drone 연계 모듈"

# 메인 클래스들 import
from .connector import DVDConnector, DVDEnvironment
from .real_attacks import RealAttackAdapter
from .network_scanner import DVDNetworkScanner
from .safety_checker import SafetyChecker

# 설정 및 유틸리티
from .connector import DVDConnectionMode, DVDTarget

__all__ = [
    # 메인 클래스들
    "DVDConnector",
    "DVDEnvironment", 
    "RealAttackAdapter",
    "DVDNetworkScanner",
    "SafetyChecker",
    
    # 설정 클래스들
    "DVDConnectionMode",
    "DVDTarget"
]