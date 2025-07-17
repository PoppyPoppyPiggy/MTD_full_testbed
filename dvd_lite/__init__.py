# dvd_lite/__init__.py
"""
DVD-Lite 패키지 (CTI 없는 버전)
경량화된 드론 보안 테스트 프레임워크
"""

__version__ = "1.0.0"
__author__ = "DVD-Lite Team"
__description__ = "경량화된 드론 보안 테스트 프레임워크"

# 메인 클래스들 import (CTI 제외)
try:
    from .main import DVDLite, BaseAttack, AttackResult, AttackType, AttackStatus
    
    # 기본 공격 모듈들 import (선택적)
    try:
        from .attacks import (
            WiFiScan,
            DroneDiscovery, 
            PacketSniff,
            TelemetrySpoof,
            CommandInject,
            WaypointInject,
            LogExtract,
            ParamExtract,
            register_all_attacks
        )
        BASIC_ATTACKS_AVAILABLE = True
    except ImportError:
        print("Warning: 기본 공격 모듈 import 실패")
        BASIC_ATTACKS_AVAILABLE = False
        register_all_attacks = None
    
    # DVD 공격 시나리오 import (선택적)
    try:
        from .dvd_attacks import (
            register_all_dvd_attacks,
            get_attacks_by_tactic,
            get_attacks_by_difficulty,
            get_attacks_by_flight_state,
            get_attack_info,
            DVDAttackTactic,
            DVDFlightState,
            AttackDifficulty
        )
        
        DVD_ATTACKS_AVAILABLE = True
        
    except ImportError:
        print("Warning: DVD 공격 모듈 import 실패")
        DVD_ATTACKS_AVAILABLE = False
        register_all_dvd_attacks = None
        get_attacks_by_tactic = None
        get_attacks_by_difficulty = None
        get_attacks_by_flight_state = None
        get_attack_info = None
        DVDAttackTactic = None
        DVDFlightState = None
        AttackDifficulty = None
        
except ImportError as e:
    print(f"Warning: DVD-Lite 핵심 모듈 import 오류: {e}")
    DVDLite = None
    BaseAttack = None
    AttackResult = None
    AttackType = None
    AttackStatus = None
    BASIC_ATTACKS_AVAILABLE = False
    DVD_ATTACKS_AVAILABLE = False

# 유틸리티 함수들 (선택적)
try:
    from .utils import (
        check_host_alive,
        check_port_open,
        validate_ip_address,
        validate_port,
        is_safe_target
    )
    UTILS_AVAILABLE = True
except ImportError:
    print("Warning: 유틸리티 모듈 import 실패")
    UTILS_AVAILABLE = False
    check_host_alive = None
    check_port_open = None
    validate_ip_address = None
    validate_port = None
    is_safe_target = None

__all__ = [
    # 메인 클래스들
    "DVDLite",
    "BaseAttack", 
    "AttackResult",
    "AttackType",
    "AttackStatus",
    
    # 기본 공격 모듈들
    "register_all_attacks",
    
    # DVD 공격 시나리오
    "register_all_dvd_attacks",
    "get_attacks_by_tactic",
    "get_attacks_by_difficulty",
    "get_attacks_by_flight_state",
    "get_attack_info",
    "DVDAttackTactic",
    "DVDFlightState", 
    "AttackDifficulty",
    
    # 상태 플래그
    "BASIC_ATTACKS_AVAILABLE",
    "DVD_ATTACKS_AVAILABLE",
    "UTILS_AVAILABLE"
]

# None 값들은 __all__에서 제거
__all__ = [item for item in __all__ if globals().get(item) is not None]
