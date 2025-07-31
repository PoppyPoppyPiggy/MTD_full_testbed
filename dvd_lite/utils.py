# dvd_lite/utils.py
"""
DVD-Lite 유틸리티 함수들
"""
import socket
import ipaddress
from typing import Optional

def check_host_alive(host: str, port: int = 14550, timeout: int = 3) -> bool:
    """호스트 생존 확인"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except:
        return False

def check_port_open(host: str, port: int, timeout: int = 3) -> bool:
    """포트 열림 확인"""
    return check_host_alive(host, port, timeout)

def validate_ip_address(ip: str) -> bool:
    """IP 주소 유효성 검사"""
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False

def validate_port(port: int) -> bool:
    """포트 번호 유효성 검사"""
    return 1 <= port <= 65535

def is_safe_target(ip: str) -> bool:
    """안전한 타겟인지 확인"""
    try:
        addr = ipaddress.ip_address(ip)
        # 로컬 네트워크만 허용
        safe_networks = [
            ipaddress.ip_network("127.0.0.0/8"),
            ipaddress.ip_network("192.168.0.0/16"),
            ipaddress.ip_network("10.0.0.0/8"),
            ipaddress.ip_network("172.16.0.0/12")
        ]
        
        for network in safe_networks:
            if addr in network:
                return True
        return False
    except:
        return False
