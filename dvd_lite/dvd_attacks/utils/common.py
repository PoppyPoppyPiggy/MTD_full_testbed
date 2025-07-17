# =============================================================================
# 유틸리티 함수들
# =============================================================================

# dvd_attacks/utils/common.py
"""
DVD 공격 시스템 공통 유틸리티
"""
import random
import time
import asyncio
from typing import List, Dict, Any, Optional

def generate_fake_mac_address() -> str:
    """가짜 MAC 주소 생성"""
    return ":".join([f"{random.randint(0, 255):02x}" for _ in range(6)])

def generate_fake_ip_address(network: str = "192.168.13") -> str:
    """가짜 IP 주소 생성"""
    return f"{network}.{random.randint(1, 254)}"

def simulate_network_delay(min_delay: float = 0.1, max_delay: float = 2.0) -> float:
    """네트워크 지연 시뮬레이션"""
    delay = random.uniform(min_delay, max_delay)
    time.sleep(delay)
    return delay

async def async_network_delay(min_delay: float = 0.1, max_delay: float = 2.0) -> float:
    """비동기 네트워크 지연 시뮬레이션"""
    delay = random.uniform(min_delay, max_delay)
    await asyncio.sleep(delay)
    return delay

def calculate_success_probability(base_rate: float, modifiers: List[float]) -> float:
    """성공 확률 계산"""
    modified_rate = base_rate
    for modifier in modifiers:
        modified_rate *= modifier
    return max(0.0, min(1.0, modified_rate))

def generate_ioc_id(prefix: str = "DVD") -> str:
    """IOC ID 생성"""
    timestamp = int(time.time())
    random_suffix = random.randint(1000, 9999)
    return f"{prefix}_{timestamp}_{random_suffix}"

def format_duration(seconds: float) -> str:
    """지속 시간 포맷팅"""
    if seconds < 60:
        return f"{seconds:.1f}초"
    elif seconds < 3600:
        return f"{seconds/60:.1f}분"
    else:
        return f"{seconds/3600:.1f}시간"

def classify_risk_level(impact_score: float) -> str:
    """위험도 분류"""
    if impact_score >= 0.8:
        return "critical"
    elif impact_score >= 0.6:
        return "high"
    elif impact_score >= 0.4:
        return "medium"
    elif impact_score >= 0.2:
        return "low"
    else:
        return "minimal"