# dvd_lite/utils.py
"""
DVD-Lite 유틸리티 함수들
공통으로 사용되는 헬퍼 함수들
"""

import socket
import subprocess
import time
import random
from typing import List, Dict, Any, Optional, Tuple

# =============================================================================
# 네트워크 유틸리티
# =============================================================================

def check_host_alive(host: str, timeout: float = 3.0) -> bool:
    """호스트 생존 확인 (ping)"""
    try:
        # ping 명령 실행
        result = subprocess.run(
            ["ping", "-c", "1", "-W", str(int(timeout * 1000)), host],
            capture_output=True,
            timeout=timeout + 1
        )
        return result.returncode == 0
    except:
        return False

def check_port_open(host: str, port: int, timeout: float = 3.0) -> bool:
    """포트 개방 확인"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            result = sock.connect_ex((host, port))
            return result == 0
    except:
        return False

def scan_network_range(network: str, timeout: float = 1.0) -> List[str]:
    """네트워크 범위 스캔 (간단 버전)"""
    # 예: "192.168.1.0/24" -> ["192.168.1.1", "192.168.1.2", ...]
    if "/" not in network:
        return []
    
    base_ip, _ = network.split("/")
    base_parts = base_ip.split(".")
    
    if len(base_parts) != 4:
        return []
    
    # 간단히 마지막 옥텟만 스캔 (1-254)
    base = ".".join(base_parts[:-1])
    alive_hosts = []
    
    # 실제로는 ping을 하지만, 시뮬레이션을 위해 랜덤 생성
    for i in range(1, 11):  # 처음 10개만 체크
        host = f"{base}.{i}"
        if random.random() > 0.7:  # 30% 확률로 살아있음
            alive_hosts.append(host)
    
    return alive_hosts

# =============================================================================
# 시뮬레이션 유틸리티
# =============================================================================

def simulate_network_delay(min_delay: float = 0.1, max_delay: float = 2.0) -> float:
    """네트워크 지연 시뮬레이션"""
    delay = random.uniform(min_delay, max_delay)
    time.sleep(delay)
    return delay

def generate_fake_mac() -> str:
    """가짜 MAC 주소 생성"""
    return ":".join([f"{random.randint(0, 255):02x}" for _ in range(6)])

def generate_fake_ip(network: str = "192.168.1") -> str:
    """가짜 IP 주소 생성"""
    return f"{network}.{random.randint(1, 254)}"

def simulate_packet_capture(duration: float = 3.0) -> List[Dict[str, Any]]:
    """패킷 캡처 시뮬레이션"""
    packets = []
    packet_types = ["TCP", "UDP", "ICMP", "MAVLink"]
    
    num_packets = random.randint(10, 50)
    
    for i in range(num_packets):
        packet = {
            "timestamp": time.time() + i * 0.1,
            "type": random.choice(packet_types),
            "src_ip": generate_fake_ip("10.13.0"),
            "dst_ip": generate_fake_ip("10.13.0"),
            "size": random.randint(64, 1500),
            "protocol": random.choice(packet_types)
        }
        packets.append(packet)
    
    return packets

# =============================================================================
# MAVLink 시뮬레이션 유틸리티
# =============================================================================

def simulate_mavlink_connection(host: str, port: int = 14550) -> bool:
    """MAVLink 연결 시뮬레이션"""
    # 실제로는 pymavlink를 사용하지만, 시뮬레이션만 수행
    simulate_network_delay(0.5, 1.5)
    
    # 80% 확률로 성공
    return random.random() > 0.2

def generate_mavlink_messages() -> List[str]:
    """MAVLink 메시지 생성"""
    messages = [
        "HEARTBEAT",
        "SYS_STATUS", 
        "SYSTEM_TIME",
        "GPS_RAW_INT",
        "ATTITUDE",
        "GLOBAL_POSITION_INT",
        "RC_CHANNELS",
        "SERVO_OUTPUT_RAW",
        "MISSION_CURRENT",
        "NAV_CONTROLLER_OUTPUT",
        "VFR_HUD",
        "COMMAND_ACK"
    ]
    
    return random.sample(messages, k=random.randint(3, 8))

def simulate_parameter_request() -> Dict[str, Any]:
    """파라미터 요청 시뮬레이션"""
    parameters = {
        "BATT_CAPACITY": 5000,
        "BATT_MONITOR": 4,
        "FENCE_ENABLE": 1,
        "FENCE_ALT_MAX": 100,
        "RTL_ALT": 15,
        "COMPASS_CAL": 1,
        "GPS_TYPE": 1,
        "SERIAL1_BAUD": 57600,
        "SCHED_LOOP_RATE": 400,
        "INS_GYRO_FILTER": 20
    }
    
    # 일부 파라미터만 반환
    available_params = random.sample(list(parameters.items()), k=random.randint(3, 7))
    return dict(available_params)

# =============================================================================
# 파일 및 데이터 유틸리티
# =============================================================================

def format_file_size(size_bytes: int) -> str:
    """파일 크기 포맷팅"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"

def generate_log_files() -> List[Dict[str, Any]]:
    """로그 파일 목록 생성"""
    log_files = []
    
    for i in range(1, random.randint(3, 8)):
        log_file = {
            "name": f"flight_log_{i:03d}.bin",
            "size": random.randint(1024, 10 * 1024 * 1024),  # 1KB ~ 10MB
            "created": time.time() - random.randint(3600, 7 * 24 * 3600),  # 1시간 ~ 1주일 전
            "type": "binary"
        }
        log_files.append(log_file)
    
    # 추가 파일들
    additional_files = [
        {"name": "parameters.txt", "size": random.randint(1024, 10240), "type": "text"},
        {"name": "waypoints.log", "size": random.randint(512, 5120), "type": "text"},
        {"name": "events.log", "size": random.randint(2048, 20480), "type": "text"}
    ]
    
    log_files.extend(random.sample(additional_files, k=random.randint(1, 3)))
    
    return log_files

# =============================================================================
# 검증 및 안전성 유틸리티
# =============================================================================

def validate_ip_address(ip: str) -> bool:
    """IP 주소 유효성 검증"""
    try:
        socket.inet_aton(ip)
        return True
    except socket.error:
        return False

def validate_port(port: int) -> bool:
    """포트 번호 유효성 검증"""
    return 1 <= port <= 65535

def sanitize_filename(filename: str) -> str:
    """파일명 안전화"""
    import re
    # 위험한 문자 제거
    safe_filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    return safe_filename[:255]  # 길이 제한

def is_safe_target(target_ip: str) -> bool:
    """안전한 타겟인지 확인 (테스트 환경만)"""
    # DVD 테스트베드 IP 범위만 허용
    safe_ranges = [
        "10.13.0.",     # DVD 기본 네트워크
        "192.168.13.",  # DVD WiFi 네트워크
        "127.0.0.1"     # localhost
    ]
    
    return any(target_ip.startswith(range_prefix) for range_prefix in safe_ranges)

# =============================================================================
# 통계 및 메트릭 유틸리티
# =============================================================================

def calculate_success_rate(results: List[Any]) -> float:
    """성공률 계산"""
    if not results:
        return 0.0
    
    successful = sum(1 for r in results if hasattr(r, 'status') and r.status.value == 'success')
    return (successful / len(results)) * 100

def calculate_average_response_time(results: List[Any]) -> float:
    """평균 응답 시간 계산"""
    if not results:
        return 0.0
    
    times = [r.response_time for r in results if hasattr(r, 'response_time')]
    return sum(times) / len(times) if times else 0.0

def generate_statistics_summary(results: List[Any]) -> Dict[str, Any]:
    """통계 요약 생성"""
    if not results:
        return {"message": "결과 없음"}
    
    return {
        "total_count": len(results),
        "success_rate": f"{calculate_success_rate(results):.1f}%",
        "avg_response_time": f"{calculate_average_response_time(results):.2f}s",
        "total_iocs": sum(len(r.iocs) for r in results if hasattr(r, 'iocs')),
        "attack_types": list(set(r.attack_type.value for r in results if hasattr(r, 'attack_type')))
    }