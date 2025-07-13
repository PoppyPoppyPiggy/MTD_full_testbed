# dvd_lite/__init__.py
"""
DVD-Lite 패키지
경량화된 드론 보안 테스트 프레임워크
"""

__version__ = "1.0.0"
__author__ = "DVD-Lite Team"
__description__ = "경량화된 드론 보안 테스트 및 CTI 수집 프레임워크"

# 메인 클래스들 import
from .main import DVDLite, BaseAttack, AttackResult, AttackType, AttackStatus
from .cti import SimpleCTI, ThreatIndicator
from .attacks import register_all_attacks

# 공격 모듈들 import
from .attacks import (
    WiFiScan,
    DroneDiscovery, 
    PacketSniff,
    TelemetrySpoof,
    CommandInject,
    WaypointInject,
    LogExtract,
    ParamExtract
)

# 유틸리티 함수들
from .utils import (
    check_host_alive,
    check_port_open,
    scan_network_range,
    validate_ip_address,
    validate_port,
    is_safe_target,
    calculate_success_rate,
    generate_statistics_summary
)

__all__ = [
    # 메인 클래스들
    "DVDLite",
    "BaseAttack", 
    "AttackResult",
    "AttackType",
    "AttackStatus",
    
    # CTI 관련
    "SimpleCTI",
    "ThreatIndicator",
    
    # 공격 모듈들
    "WiFiScan",
    "DroneDiscovery",
    "PacketSniff", 
    "TelemetrySpoof",
    "CommandInject",
    "WaypointInject",
    "LogExtract",
    "ParamExtract",
    "register_all_attacks",
    
    # 유틸리티 함수들
    "check_host_alive",
    "check_port_open",
    "scan_network_range",
    "validate_ip_address",
    "validate_port",
    "is_safe_target",
    "calculate_success_rate",
    "generate_statistics_summary"
]