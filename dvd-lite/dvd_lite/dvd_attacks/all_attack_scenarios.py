# dvd_lite/dvd_attacks/all_attack_scenarios.py
"""
Damn Vulnerable Drone 전체 공격 시나리오 자동화 시스템
GitHub Wiki에서 제안하는 모든 공격 시나리오를 구현한 자동화 프레임워크
"""

import asyncio
import random
import time
import json
import subprocess
import socket
import struct
import threading
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

# 기존 DVD-Lite 모듈 import
from dvd_lite.main import BaseAttack, AttackType

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =============================================================================
# DVD 공격 분류체계 (GitHub Wiki 기반)
# =============================================================================

class DVDAttackTactic(Enum):
    """DVD 공격 전술 분류"""
    RECONNAISSANCE = "reconnaissance"
    PROTOCOL_TAMPERING = "protocol_tampering"
    DENIAL_OF_SERVICE = "denial_of_service"
    INJECTION = "injection"
    EXFILTRATION = "exfiltration"
    FIRMWARE_ATTACKS = "firmware_attacks"

class DVDFlightState(Enum):
    """드론 비행 상태"""
    PRE_FLIGHT = "pre_flight"
    TAKEOFF = "takeoff"
    AUTOPILOT_FLIGHT = "autopilot_flight"
    MANUAL_FLIGHT = "manual_flight"
    EMERGENCY_RTL = "emergency_rtl"
    POST_FLIGHT = "post_flight"

@dataclass
class DVDAttackScenario:
    """DVD 공격 시나리오 정의"""
    name: str
    tactic: DVDAttackTactic
    description: str
    required_states: List[DVDFlightState]
    difficulty: str  # "beginner", "intermediate", "advanced"
    prerequisites: List[str]
    targets: List[str]  # "flight_controller", "companion_computer", "gcs", "network"

# =============================================================================
# 1. RECONNAISSANCE 공격들
# =============================================================================

class WiFiNetworkDiscovery(BaseAttack):
    """WiFi 네트워크 발견 및 열거"""
    
    def _get_attack_type(self) -> AttackType:
        return AttackType.RECONNAISSANCE
    
    async def _run_attack(self) -> Tuple[bool, List[str], Dict[str, Any]]:
        """WiFi 네트워크 스캔 및 드론 네트워크 식별"""
        await asyncio.sleep(2.5)
        
        # 시뮬레이션된 WiFi 네트워크들
        networks = [
            {"ssid": "Drone_WiFi", "bssid": "aa:bb:cc:dd:ee:01", "channel": 6, "encryption": "WPA2", "signal": -45},
            {"ssid": "DJI_MAVIC_123456", "bssid": "aa:bb:cc:dd:ee:02", "channel": 11, "encryption": "WPA", "signal": -52},
            {"ssid": "ArduPilot_AP", "bssid": "aa:bb:cc:dd:ee:03", "channel": 1, "encryption": "Open", "signal": -38},
            {"ssid": "Companion_Hotspot", "bssid": "aa:bb:cc:dd:ee:04", "channel": 6, "encryption": "WPA2", "signal": -60},
            {"ssid": "192.168.13.1", "bssid": "aa:bb:cc:dd:ee:05", "channel": 9, "encryption": "WEP", "signal": -67}
        ]
        
        discovered = random.sample(networks, k=random.randint(2, 4))
        
        iocs = []
        for network in discovered:
            iocs.append(f"WIFI_SSID:{network['ssid']}")
            iocs.append(f"WIFI_BSSID:{network['bssid']}")
            if network['encryption'] in ['Open', 'WEP']:
                iocs.append(f"VULNERABLE_NETWORK:{network['ssid']}")
        
        success = any('Drone' in net['ssid'] or 'DJI' in net['ssid'] or 'ArduPilot' in net['ssid'] 
                     for net in discovered)
        
        details = {
            "discovered_networks": discovered,
            "vulnerable_networks": [n for n in discovered if n['encryption'] in ['Open', 'WEP']],
            "drone_networks": [n for n in discovered if any(keyword in n['ssid'] 
                             for keyword in ['Drone', 'DJI', 'ArduPilot', 'Companion'])],
            "scan_method": "passive_monitor",
            "success_rate": 0.85 if success else 0.3
        }
        
        return success, iocs, details

class MAVLinkServiceDiscovery(BaseAttack):
    """MAVLink 서비스 발견 및 열거"""
    
    def _get_attack_type(self) -> AttackType:
        return AttackType.RECONNAISSANCE
    
    async def _run_attack(self) -> Tuple[bool, List[str], Dict[str, Any]]:
        """네트워크에서 MAVLink 서비스 스캔"""
        await asyncio.sleep(3.2)
        
        # 스캔할 호스트 및 포트
        target_hosts = [f"192.168.13.{i}" for i in range(1, 11)]
        mavlink_ports = [14550, 14551, 14552, 5760, 5762, 5763]
        
        discovered_services = []
        
        for host in target_hosts:
            if random.random() > 0.7:  # 30% 확률로 서비스 발견
                port = random.choice(mavlink_ports)
                service_info = {
                    "host": host,
                    "port": port,
                    "service": self._identify_mavlink_service(port),
                    "version": f"MAVLink {random.choice(['1.0', '2.0'])}",
                    "system_id": random.randint(1, 255),
                    "component_id": random.randint(1, 255)
                }
                discovered_services.append(service_info)
        
        iocs = []
        for service in discovered_services:
            iocs.append(f"MAVLINK_SERVICE:{service['host']}:{service['port']}")
            iocs.append(f"SYSTEM_ID:{service['system_id']}")
            iocs.append(f"COMPONENT_ID:{service['component_id']}")
        
        success = len(discovered_services) > 0
        
        details = {
            "discovered_services": discovered_services,
            "scan_range": target_hosts,
            "ports_scanned": mavlink_ports,
            "total_discovered": len(discovered_services),
            "success_rate": 0.75 if success else 0.1
        }
        
        return success, iocs, details
    
    def _identify_mavlink_service(self, port: int) -> str:
        """포트 번호로 MAVLink 서비스 식별"""
        service_map = {
            14550: "Flight Controller",
            14551: "Ground Control Station",
            14552: "Companion Computer",
            5760: "SITL Simulator",
            5762: "Secondary GCS",
            5763: "Relay Node"
        }
        return service_map.get(port, "Unknown MAVLink Service")

class DroneComponentEnumeration(BaseAttack):
    """드론 컴포넌트 상세 열거"""
    
    def _get_attack_type(self) -> AttackType:
        return AttackType.RECONNAISSANCE
    
    async def _run_attack(self) -> Tuple[bool, List[str], Dict[str, Any]]:
        """드론 시스템 컴포넌트 식별 및 정보 수집"""
        await asyncio.sleep(4.1)
        
        components = {
            "flight_controller": {
                "autopilot": random.choice(["ArduCopter", "PX4", "Betaflight"]),
                "firmware_version": f"{random.randint(4, 6)}.{random.randint(0, 9)}.{random.randint(0, 9)}",
                "board_type": random.choice(["Pixhawk", "Cube", "Omnibus", "Kakute"]),
                "parameters": random.randint(200, 800)
            },
            "companion_computer": {
                "os": random.choice(["Ubuntu 20.04", "Raspberry Pi OS", "Custom Linux"]),
                "services": ["SSH", "HTTP", "FTP", "RTSP"],
                "camera_streams": random.randint(1, 3)
            },
            "gcs": {
                "software": random.choice(["QGroundControl", "Mission Planner", "MAVProxy"]),
                "connection_type": random.choice(["WiFi", "Radio", "Cellular"]),
                "logging_enabled": random.choice([True, False])
            }
        }
        
        iocs = []
        for comp_type, comp_info in components.items():
            iocs.append(f"COMPONENT:{comp_type}")
            if comp_type == "flight_controller":
                iocs.append(f"AUTOPILOT:{comp_info['autopilot']}")
                iocs.append(f"FIRMWARE:{comp_info['firmware_version']}")
                iocs.append(f"BOARD:{comp_info['board_type']}")
            elif comp_type == "companion_computer":
                iocs.append(f"OS:{comp_info['os']}")
                for service in comp_info['services']:
                    iocs.append(f"SERVICE:{service}")
        
        success = len(components) >= 2
        
        details = {
            "identified_components": components,
            "enumeration_method": "banner_grabbing",
            "vulnerabilities_found": self._check_component_vulnerabilities(components),
            "success_rate": 0.8 if success else 0.2
        }
        
        return success, iocs, details
    
    def _check_component_vulnerabilities(self, components: Dict) -> List[Dict]:
        """컴포넌트 취약점 확인"""
        vulnerabilities = []
        
        if "flight_controller" in components:
            fc = components["flight_controller"]
            if fc["autopilot"] == "ArduCopter" and fc["firmware_version"].startswith("4.0"):
                vulnerabilities.append({
                    "component": "flight_controller",
                    "type": "outdated_firmware",
                    "severity": "medium",
                    "description": "Outdated ArduCopter firmware with known issues"
                })
        
        if "companion_computer" in components:
            cc = components["companion_computer"]
            if "FTP" in cc["services"]:
                vulnerabilities.append({
                    "component": "companion_computer",
                    "type": "insecure_service",
                    "severity": "high",
                    "description": "FTP service running with potential weak credentials"
                })
        
        return vulnerabilities

class CameraStreamDiscovery(BaseAttack):
    """카메라 스트림 발견 및 접근"""
    
    def _get_attack_type(self) -> AttackType:
        return AttackType.RECONNAISSANCE
    
    async def _run_attack(self) -> Tuple[bool, List[str], Dict[str, Any]]:
        """RTSP 및 HTTP 카메라 스트림 발견"""
        await asyncio.sleep(2.8)
        
        # 일반적인 스트림 경로들
        rtsp_paths = [
            "/live/stream1",
            "/axis-media/media.amp",
            "/mjpeg/1",
            "/video.mjpg",
            "/live.sdp",
            "/cam/realmonitor"
        ]
        
        http_paths = [
            "/video_feed",
            "/mjpeg",
            "/stream.mjpg",
            "/axis-cgi/mjpg/video.cgi",
            "/videostream.cgi"
        ]
        
        discovered_streams = []
        
        # RTSP 스트림 시뮬레이션
        if random.random() > 0.4:  # 60% 확률
            stream = {
                "type": "RTSP",
                "url": f"rtsp://192.168.13.{random.randint(1, 10)}:554{random.choice(rtsp_paths)}",
                "resolution": random.choice(["1920x1080", "1280x720", "640x480"]),
                "fps": random.randint(15, 30),
                "authenticated": random.choice([True, False])
            }
            discovered_streams.append(stream)
        
        # HTTP 스트림 시뮬레이션
        if random.random() > 0.5:  # 50% 확률
            stream = {
                "type": "HTTP",
                "url": f"http://192.168.13.{random.randint(1, 10)}:8080{random.choice(http_paths)}",
                "format": random.choice(["MJPEG", "H.264"]),
                "authenticated": random.choice([True, False])
            }
            discovered_streams.append(stream)
        
        iocs = []
        for stream in discovered_streams:
            iocs.append(f"VIDEO_STREAM:{stream['url']}")
            if not stream['authenticated']:
                iocs.append(f"UNAUTH_STREAM:{stream['url']}")
        
        success = len(discovered_streams) > 0
        
        details = {
            "discovered_streams": discovered_streams,
            "unauthenticated_streams": [s for s in discovered_streams if not s['authenticated']],
            "total_streams": len(discovered_streams),
            "access_method": "directory_traversal",
            "success_rate": 0.7 if success else 0.25
        }
        
        return success, iocs, details

# =============================================================================
# 2. PROTOCOL TAMPERING 공격들
# =============================================================================

class MAVLinkPacketInjection(BaseAttack):
    """MAVLink 패킷 주입 공격"""
    
    def _get_attack_type(self) -> AttackType:
        return AttackType.PROTOCOL_TAMPERING
    
    async def _run_attack(self) -> Tuple[bool, List[str], Dict[str, Any]]:
        """악성 MAVLink 메시지 주입"""
        await asyncio.sleep(3.5)
        
        # 주입할 MAVLink 메시지들
        injection_payloads = [
            {
                "msg_id": 11,  # SET_POSITION_TARGET_LOCAL_NED
                "type": "position_manipulation",
                "target": {"x": 100.0, "y": 50.0, "z": -20.0},
                "severity": "high"
            },
            {
                "msg_id": 76,  # COMMAND_LONG
                "type": "command_injection",
                "command": "MAV_CMD_COMPONENT_ARM_DISARM",
                "severity": "critical"
            },
            {
                "msg_id": 84,  # SET_POSITION_TARGET_GLOBAL_INT
                "type": "gps_spoofing",
                "target": {"lat": 37774900, "lon": -122419400, "alt": 100000},
                "severity": "high"
            },
            {
                "msg_id": 39,  # MISSION_ITEM
                "type": "waypoint_injection",
                "waypoint": {"seq": 0, "lat": 37.7749, "lon": -122.4194, "alt": 50},
                "severity": "medium"
            }
        ]
        
        successful_injections = []
        
        for payload in injection_payloads:
            if random.random() > 0.3:  # 70% 성공률
                successful_injections.append(payload)
                
                # 실제 환경에서는 여기서 pymavlink를 사용하여 실제 패킷 전송
                # mavlink_msg = self._create_mavlink_message(payload)
                # self._send_mavlink_packet(mavlink_msg)
        
        iocs = []
        for injection in successful_injections:
            iocs.append(f"MAVLINK_INJECT:{injection['type']}")
            iocs.append(f"MSG_ID:{injection['msg_id']}")
            if injection['severity'] == 'critical':
                iocs.append(f"CRITICAL_INJECTION:{injection['type']}")
        
        success = len(successful_injections) > 0
        
        details = {
            "injection_attempts": len(injection_payloads),
            "successful_injections": successful_injections,
            "failed_injections": len(injection_payloads) - len(successful_injections),
            "attack_vector": "mavlink_protocol",
            "success_rate": len(successful_injections) / len(injection_payloads) if injection_payloads else 0
        }
        
        return success, iocs, details

class GPSSpoofing(BaseAttack):
    """GPS 신호 스푸핑 공격"""
    
    def _get_attack_type(self) -> AttackType:
        return AttackType.PROTOCOL_TAMPERING
    
    async def _run_attack(self) -> Tuple[bool, List[str], Dict[str, Any]]:
        """GPS 신호 조작을 통한 위치 정보 변조"""
        await asyncio.sleep(4.2)
        
        # 원본 GPS 좌표 (시뮬레이션)
        original_coords = {
            "lat": 37.7749295,
            "lon": -122.4194155,
            "alt": 43.0,
            "accuracy": 3.5
        }
        
        # 스푸핑 시나리오들
        spoofing_scenarios = [
            {
                "name": "airport_redirect",
                "target_coords": {"lat": 37.6213, "lon": -122.3790, "alt": 30.0},
                "description": "Redirect to SFO Airport",
                "risk_level": "critical"
            },
            {
                "name": "ocean_crash",
                "target_coords": {"lat": 37.8044, "lon": -122.4695, "alt": 0.0},
                "description": "Force landing in Pacific Ocean",
                "risk_level": "critical"
            },
            {
                "name": "no_fly_zone",
                "target_coords": {"lat": 38.8977, "lon": -77.0365, "alt": 50.0},
                "description": "Redirect to restricted airspace",
                "risk_level": "high"
            },
            {
                "name": "elevation_attack",
                "target_coords": {"lat": 37.7749295, "lon": -122.4194155, "alt": -50.0},
                "description": "Force underground altitude",
                "risk_level": "medium"
            }
        ]
        
        # 랜덤하게 스푸핑 시나리오 선택
        active_scenario = random.choice(spoofing_scenarios)
        
        # 스푸핑 성공 여부 시뮬레이션
        success = random.random() > 0.25  # 75% 성공률
        
        if success:
            # GPS 신호 생성 시뮬레이션
            spoofed_signal = {
                "satellites_used": random.randint(4, 12),
                "signal_strength": random.uniform(-140, -120),  # dBm
                "spoofing_method": "signal_generator",
                "delay_compensation": True
            }
            
            iocs = [
                f"GPS_SPOOF:ORIGINAL_{original_coords['lat']},{original_coords['lon']}",
                f"GPS_SPOOF:TARGET_{active_scenario['target_coords']['lat']},{active_scenario['target_coords']['lon']}",
                f"GPS_SPOOF:SCENARIO_{active_scenario['name']}",
                f"GPS_SPOOF:RISK_{active_scenario['risk_level']}"
            ]
        else:
            spoofed_signal = None
            iocs = [f"GPS_SPOOF:FAILED_{active_scenario['name']}"]
        
        details = {
            "original_coordinates": original_coords,
            "spoofing_scenario": active_scenario,
            "spoofed_signal": spoofed_signal,
            "detection_evasion": {
                "gradual_drift": True,
                "realistic_accuracy": True,
                "satellite_simulation": True
            },
            "success_rate": 0.75 if success else 0.0
        }
        
        return success, iocs, details

class RadioFrequencyJamming(BaseAttack):
    """무선 주파수 재밍 공격"""
    
    def _get_attack_type(self) -> AttackType:
        return AttackType.PROTOCOL_TAMPERING
    
    async def _run_attack(self) -> Tuple[bool, List[str], Dict[str, Any]]:
        """드론 통신 주파수 간섭"""
        await asyncio.sleep(3.8)
        
        # 대상 주파수 대역
        target_frequencies = {
            "2.4_ghz": {
                "range": "2400-2485 MHz",
                "protocols": ["WiFi", "Bluetooth", "RC Control"],
                "channels": list(range(1, 15))
            },
            "5.8_ghz": {
                "range": "5725-5875 MHz", 
                "protocols": ["WiFi 5GHz", "FPV Video"],
                "channels": [36, 40, 44, 48, 149, 153, 157, 161]
            },
            "900_mhz": {
                "range": "902-928 MHz",
                "protocols": ["Telemetry", "Long Range RC"],
                "channels": list(range(1, 25))
            },
            "1.2_ghz": {
                "range": "1240-1300 MHz",
                "protocols": ["Video Downlink"],
                "channels": list(range(1, 9))
            }
        }
        
        # 재밍 공격 시뮬레이션
        jamming_results = {}
        
        for freq_band, info in target_frequencies.items():
            if random.random() > 0.4:  # 60% 확률로 각 대역 공격
                jammed_channels = random.sample(info['channels'], 
                                              k=random.randint(1, min(5, len(info['channels']))))
                
                jamming_results[freq_band] = {
                    "targeted_channels": jammed_channels,
                    "power_level": random.uniform(10, 30),  # dBm
                    "interference_type": random.choice(["white_noise", "sweep", "pulse"]),
                    "affected_protocols": info['protocols'],
                    "success_rate": random.uniform(0.6, 0.95)
                }
        
        # IOC 생성
        iocs = []
        for freq_band, result in jamming_results.items():
            iocs.append(f"RF_JAMMING:{freq_band}")
            for protocol in result['affected_protocols']:
                iocs.append(f"PROTOCOL_DISRUPTED:{protocol}")
            if result['success_rate'] > 0.8:
                iocs.append(f"HIGH_IMPACT_JAMMING:{freq_band}")
        
        success = len(jamming_results) > 0
        
        details = {
            "target_frequencies": target_frequencies,
            "jamming_results": jamming_results,
            "equipment_used": "Software Defined Radio",
            "jamming_duration": random.uniform(30, 300),  # seconds
            "detection_risk": "medium",
            "success_rate": 0.8 if success else 0.15
        }
        
        return success, iocs, details

# =============================================================================
# 3. DENIAL OF SERVICE 공격들
# =============================================================================

class MAVLinkFloodAttack(BaseAttack):
    """MAVLink 프로토콜 플러드 공격"""
    
    def _get_attack_type(self) -> AttackType:
        return AttackType.DOS
    
    async def _run_attack(self) -> Tuple[bool, List[str], Dict[str, Any]]:
        """MAVLink 메시지 폭주로 서비스 거부"""
        await asyncio.sleep(2.5)
        
        # 플러드 공격 설정
        flood_config = {
            "target_port": 14550,
            "message_types": ["HEARTBEAT", "PING", "REQUEST_DATA_STREAM", "PARAM_REQUEST_LIST"],
            "packets_per_second": random.randint(500, 2000),
            "duration": random.randint(60, 300),  # seconds
            "source_spoofing": True
        }
        
        # 공격 시뮬레이션
        total_packets = flood_config["packets_per_second"] * flood_config["duration"]
        
        # 시스템 영향 시뮬레이션
        system_impact = {
            "flight_controller_cpu": random.uniform(80, 99),  # CPU usage %
            "memory_usage": random.uniform(70, 95),  # Memory usage %
            "network_bandwidth": random.uniform(90, 100),  # Bandwidth usage %
            "dropped_packets": random.randint(100, 1000),
            "response_delay": random.uniform(5, 30)  # seconds
        }
        
        # 성공 조건: 시스템 자원 임계치 초과
        success = (system_impact["flight_controller_cpu"] > 85 and 
                  system_impact["network_bandwidth"] > 90)
        
        iocs = [
            f"DOS_FLOOD:MAVLINK_PACKETS_{total_packets}",
            f"DOS_FLOOD:TARGET_PORT_{flood_config['target_port']}",
            f"DOS_FLOOD:CPU_USAGE_{system_impact['flight_controller_cpu']:.1f}%",
            f"DOS_FLOOD:NETWORK_SATURATED"
        ]
        
        if success:
            iocs.append("DOS_FLOOD:SERVICE_DISRUPTED")
            iocs.append("DOS_FLOOD:FLIGHT_CONTROLLER_OVERLOADED")
        
        details = {
            "flood_configuration": flood_config,
            "total_packets_sent": total_packets,
            "system_impact": system_impact,
            "attack_duration": flood_config["duration"],
            "effectiveness": "high" if success else "low",
            "success_rate": 0.85 if success else 0.3
        }
        
        return success, iocs, details

class WiFiDeauthenticationAttack(BaseAttack):
    """WiFi 인증 해제 공격"""
    
    def _get_attack_type(self) -> AttackType:
        return AttackType.DOS
    
    async def _run_attack(self) -> Tuple[bool, List[str], Dict[str, Any]]:
        """WiFi 연결 강제 해제를 통한 서비스 거부"""
        await asyncio.sleep(3.1)
        
        # 대상 WiFi 네트워크들
        target_networks = [
            {"ssid": "Drone_WiFi", "bssid": "aa:bb:cc:dd:ee:01", "clients": 3},
            {"ssid": "DJI_MAVIC_123456", "bssid": "aa:bb:cc:dd:ee:02", "clients": 1},
            {"ssid": "Companion_Hotspot", "bssid": "aa:bb:cc:dd:ee:04", "clients": 2}
        ]
        
        attack_results = []
        
        for network in target_networks:
            if random.random() > 0.3:  # 70% 성공률
                # 인증 해제 프레임 전송 시뮬레이션
                deauth_frames = random.randint(50, 200)
                disconnected_clients = random.randint(1, network["clients"])
                
                result = {
                    "target_ssid": network["ssid"],
                    "target_bssid": network["bssid"],
                    "deauth_frames_sent": deauth_frames,
                    "clients_disconnected": disconnected_clients,
                    "attack_duration": random.uniform(30, 120),  # seconds
                    "success": True
                }
                attack_results.append(result)
        
        # IOC 생성
        iocs = []
        for result in attack_results:
            if result["success"]:
                iocs.append(f"WIFI_DEAUTH:{result['target_ssid']}")
                iocs.append(f"DEAUTH_FRAMES:{result['deauth_frames_sent']}")
                iocs.append(f"CLIENTS_DISCONNECTED:{result['clients_disconnected']}")
        
        success = len(attack_results) > 0 and any(r["success"] for r in attack_results)
        
        details = {
            "target_networks": target_networks,
            "attack_results": attack_results,
            "total_frames_sent": sum(r["deauth_frames_sent"] for r in attack_results),
            "total_clients_affected": sum(r["clients_disconnected"] for r in attack_results),
            "attack_method": "802.11_deauth_frames",
            "success_rate": 0.7 if success else 0.2
        }
        
        return success, iocs, details

class CompanionComputerResourceExhaustion(BaseAttack):
    """컴패니언 컴퓨터 자원 고갈 공격"""
    
    def _get_attack_type(self) -> AttackType:
        return AttackType.DOS
    
    async def _run_attack(self) -> Tuple[bool, List[str], Dict[str, Any]]:
        """컴패니언 컴퓨터 자원을 고갈시켜 서비스 거부"""
        await asyncio.sleep(4.5)
        
        # 자원 고갈 공격 벡터들
        attack_vectors = [
            {
                "type": "cpu_bomb",
                "method": "infinite_loop_processes",
                "target_utilization": 95,
                "processes_spawned": random.randint(50, 200)
            },
            {
                "type": "memory_bomb", 
                "method": "malloc_without_free",
                "target_utilization": 90,
                "memory_allocated": f"{random.randint(500, 1500)}MB"
            },
            {
                "type": "disk_bomb",
                "method": "rapid_file_creation",
                "target_utilization": 95,
                "files_created": random.randint(10000, 50000)
            },
            {
                "type": "network_bomb",
                "method": "connection_flooding",
                "target_utilization": 85,
                "connections_opened": random.randint(1000, 5000)
            }
        ]
        
        successful_attacks = []
        
        for vector in attack_vectors:
            if random.random() > 0.4:  # 60% 성공률
                # 실제 환경에서는 여기서 실제 자원 고갈 코드 실행
                execution_result = {
                    **vector,
                    "execution_time": random.uniform(10, 60),
                    "peak_utilization": vector["target_utilization"] + random.uniform(-10, 5),
                    "system_response": random.choice(["slow", "unresponsive", "crashed"])
                }
                successful_attacks.append(execution_result)
        
        # 시스템 상태 시뮬레이션
        if successful_attacks:
            system_status = {
                "cpu_usage": max([a.get("peak_utilization", 0) for a in successful_attacks if a["type"] == "cpu_bomb"], default=20),
                "memory_usage": max([a.get("peak_utilization", 0) for a in successful_attacks if a["type"] == "memory_bomb"], default=30),
                "disk_usage": max([a.get("peak_utilization", 0) for a in successful_attacks if a["type"] == "disk_bomb"], default=40),
                "network_load": max([a.get("peak_utilization", 0) for a in successful_attacks if a["type"] == "network_bomb"], default=25),
                "overall_health": "critical" if len(successful_attacks) >= 3 else "degraded"
            }
        else:
            system_status = {"overall_health": "normal"}
        
        iocs = []
        for attack in successful_attacks:
            iocs.append(f"RESOURCE_EXHAUSTION:{attack['type']}")
            iocs.append(f"METHOD:{attack['method']}")
            if attack.get("peak_utilization", 0) > 90:
                iocs.append(f"CRITICAL_RESOURCE_USAGE:{attack['type']}")
        
        success = len(successful_attacks) > 0
        
        details = {
            "attack_vectors": attack_vectors,
            "successful_attacks": successful_attacks,
            "system_status": system_status,
            "recovery_time": random.uniform(60, 300) if success else 0,
            "success_rate": 0.6 if success else 0.1
        }
        
        return success, iocs, details

# =============================================================================
# 4. INJECTION 공격들
# =============================================================================

class FlightPlanInjection(BaseAttack):
    """비행 계획 주입 공격"""
    
    def _get_attack_type(self) -> AttackType:
        return AttackType.INJECTION
    
    async def _run_attack(self) -> Tuple[bool, List[str], Dict[str, Any]]:
        """악성 웨이포인트로 비행 계획 변조"""
        await asyncio.sleep(3.7)
        
        # 원본 미션 정보
        original_mission = {
            "waypoint_count": random.randint(5, 15),
            "mission_type": "survey",
            "area": "safe_zone", 
            "max_altitude": 100  # meters
        }
        
        # 악성 웨이포인트들
        malicious_waypoints = [
            {
                "seq": 0,
                "type": "redirect_to_restricted",
                "lat": 38.8977,  # Washington DC (restricted)
                "lon": -77.0365,
                "alt": 150,
                "risk": "critical"
            },
            {
                "seq": 1,
                "type": "force_landing",
                "lat": 37.7749,
                "lon": -122.4194,
                "alt": 0,  # Ground level
                "risk": "high"
            },
            {
                "seq": 2,
                "type": "excessive_altitude",
                "lat": 37.7849,
                "lon": -122.4094,
                "alt": 500,  # Above legal limit
                "risk": "medium"
            }
        ]
        
        # 주입 방법들
        injection_methods = [
            {
                "method": "mavlink_mission_item",
                "success_rate": 0.8,
                "detection_risk": "low"
            },
            {
                "method": "gcs_interface_manipulation", 
                "success_rate": 0.6,
                "detection_risk": "medium"
            },
            {
                "method": "parameter_modification",
                "success_rate": 0.9,
                "detection_risk": "high"
            }
        ]
        
        # 주입 시도
        chosen_method = random.choice(injection_methods)
        injected_waypoints = []
        
        for waypoint in malicious_waypoints:
            if random.random() < chosen_method["success_rate"]:
                injected_waypoints.append(waypoint)
        
        success = len(injected_waypoints) > 0
        
        iocs = []
        for wp in injected_waypoints:
            iocs.append(f"WAYPOINT_INJECT:{wp['type']}")
            iocs.append(f"MALICIOUS_COORDS:{wp['lat']},{wp['lon']},{wp['alt']}")
            if wp['risk'] == 'critical':
                iocs.append(f"CRITICAL_WAYPOINT_INJECT:{wp['type']}")
        
        if success:
            iocs.append(f"INJECTION_METHOD:{chosen_method['method']}")
        
        details = {
            "original_mission": original_mission,
            "injection_method": chosen_method,
            "malicious_waypoints": malicious_waypoints,
            "successfully_injected": injected_waypoints,
            "mission_corruption_level": len(injected_waypoints) / len(malicious_waypoints),
            "success_rate": chosen_method["success_rate"] if success else 0.1
        }
        
        return success, iocs, details

class ParameterManipulation(BaseAttack):
    """시스템 파라미터 조작 공격"""
    
    def _get_attack_type(self) -> AttackType:
        return AttackType.INJECTION
    
    async def _run_attack(self) -> Tuple[bool, List[str], Dict[str, Any]]:
        """중요 시스템 파라미터 변조"""
        await asyncio.sleep(4.2)
        
        # 중요 시스템 파라미터들
        critical_parameters = [
            {
                "name": "BATT_LOW_VOLT",
                "original": 10.5,
                "malicious": 5.0,
                "impact": "premature_battery_warning",
                "severity": "medium"
            },
            {
                "name": "FENCE_ENABLE",
                "original": 1,
                "malicious": 0,
                "impact": "geofence_disabled",
                "severity": "high"
            },
            {
                "name": "RTL_ALT",
                "original": 15,
                "malicious": 500,
                "impact": "unsafe_return_altitude",
                "severity": "high"
            },
            {
                "name": "ARMING_CHECK",
                "original": 1,
                "malicious": 0,
                "impact": "safety_checks_disabled",
                "severity": "critical"
            },
            {
                "name": "FS_THR_ENABLE",
                "original": 1,
                "malicious": 0,
                "impact": "throttle_failsafe_disabled",
                "severity": "critical"
            },
            {
                "name": "COMPASS_CAL",
                "original": 1,
                "malicious": 0,
                "impact": "compass_calibration_bypassed",
                "severity": "medium"
            }
        ]
        
        # 파라미터 변조 시도
        modified_parameters = []
        
        for param in critical_parameters:
            if random.random() > 0.35:  # 65% 성공률
                modification = {
                    **param,
                    "modification_time": datetime.now().isoformat(),
                    "modification_method": random.choice(["mavlink_param_set", "config_file_edit", "eeprom_direct"])
                }
                modified_parameters.append(modification)
        
        # 시스템 안정성 영향 계산
        if modified_parameters:
            stability_impact = {
                "flight_safety": sum(1 for p in modified_parameters if p['severity'] in ['high', 'critical']),
                "operational_integrity": len(modified_parameters),
                "detection_likelihood": "low" if len(modified_parameters) <= 2 else "high",
                "recovery_difficulty": "easy" if len(modified_parameters) <= 1 else "complex"
            }
        else:
            stability_impact = {"impact": "none"}
        
        iocs = []
        for param in modified_parameters:
            iocs.append(f"PARAM_MODIFIED:{param['name']}")
            iocs.append(f"PARAM_VALUE_CHANGE:{param['name']}_{param['original']}_to_{param['malicious']}")
            if param['severity'] == 'critical':
                iocs.append(f"CRITICAL_PARAM_MODIFIED:{param['name']}")
        
        success = len(modified_parameters) > 0
        
        details = {
            "target_parameters": critical_parameters,
            "modified_parameters": modified_parameters,
            "stability_impact": stability_impact,
            "modification_persistence": random.choice(["volatile", "persistent"]),
            "success_rate": 0.65 if success else 0.15
        }
        
        return success, iocs, details

class FirmwareUploadManipulation(BaseAttack):
    """펌웨어 업로드 조작 공격"""
    
    def _get_attack_type(self) -> AttackType:
        return AttackType.INJECTION
    
    async def _run_attack(self) -> Tuple[bool, List[str], Dict[str, Any]]:
        """펌웨어 업데이트 과정에서 악성 코드 주입"""
        await asyncio.sleep(5.5)
        
        # 펌웨어 정보
        firmware_info = {
            "current_version": f"ArduCopter-{random.randint(4, 6)}.{random.randint(0, 9)}.{random.randint(0, 9)}",
            "target_version": f"ArduCopter-{random.randint(4, 6)}.{random.randint(0, 9)}.{random.randint(0, 9)}-modified",
            "file_size": random.randint(1000000, 5000000),  # bytes
            "checksum_original": "a1b2c3d4e5f6",
            "checksum_modified": "f6e5d4c3b2a1"
        }
        
        # 조작 방법들
        manipulation_techniques = [
            {
                "technique": "bootloader_exploit",
                "success_rate": 0.4,
                "payload_type": "persistent_backdoor",
                "stealth": "high"
            },
            {
                "technique": "firmware_patching",
                "success_rate": 0.7,
                "payload_type": "parameter_override",
                "stealth": "medium"
            },
            {
                "technique": "update_interception",
                "success_rate": 0.8,
                "payload_type": "malicious_firmware",
                "stealth": "low"
            },
            {
                "technique": "signature_bypass",
                "success_rate": 0.3,
                "payload_type": "signed_malware",
                "stealth": "high"
            }
        ]
        
        # 조작 시도
        chosen_technique = random.choice(manipulation_techniques)
        success = random.random() < chosen_technique["success_rate"]
        
        if success:
            payload_info = {
                "payload_type": chosen_technique["payload_type"],
                "injection_point": random.choice(["init_sequence", "main_loop", "failsafe_handler"]),
                "persistence": random.choice(["boot_persistent", "flash_persistent", "memory_only"]),
                "capabilities": [
                    "remote_command_execution",
                    "parameter_manipulation", 
                    "telemetry_exfiltration",
                    "flight_control_override"
                ]
            }
        else:
            payload_info = None
        
        iocs = []
        if success:
            iocs.append(f"FIRMWARE_MANIPULATION:{chosen_technique['technique']}")
            iocs.append(f"MALICIOUS_PAYLOAD:{chosen_technique['payload_type']}")
            iocs.append(f"CHECKSUM_MISMATCH:{firmware_info['checksum_original']}_vs_{firmware_info['checksum_modified']}")
            iocs.append(f"FIRMWARE_VERSION_ANOMALY:{firmware_info['target_version']}")
        else:
            iocs.append(f"FIRMWARE_MANIPULATION_FAILED:{chosen_technique['technique']}")
        
        details = {
            "firmware_info": firmware_info,
            "manipulation_technique": chosen_technique,
            "payload_info": payload_info,
            "upload_method": random.choice(["mavlink", "usb", "wifi", "sd_card"]),
            "verification_bypassed": success,
            "success_rate": chosen_technique["success_rate"] if success else 0.0
        }
        
        return success, iocs, details

# =============================================================================
# 5. EXFILTRATION 공격들
# =============================================================================

class TelemetryDataExfiltration(BaseAttack):
    """텔레메트리 데이터 탈취"""
    
    def _get_attack_type(self) -> AttackType:
        return AttackType.EXFILTRATION
    
    async def _run_attack(self) -> Tuple[bool, List[str], Dict[str, Any]]:
        """민감한 텔레메트리 정보 수집 및 탈취"""
        await asyncio.sleep(3.9)
        
        # 수집 가능한 텔레메트리 데이터 유형들
        telemetry_types = [
            {
                "type": "gps_coordinates",
                "sensitivity": "high",
                "data_points": random.randint(100, 1000),
                "format": "lat/lon/alt_timestamp"
            },
            {
                "type": "flight_patterns",
                "sensitivity": "medium",
                "data_points": random.randint(50, 500),
                "format": "waypoint_sequence"
            },
            {
                "type": "camera_metadata",
                "sensitivity": "high",
                "data_points": random.randint(20, 200),
                "format": "exif_gps_timestamp"
            },
            {
                "type": "operator_identity",
                "sensitivity": "critical",
                "data_points": 1,
                "format": "device_id_credentials"
            },
            {
                "type": "system_diagnostics",
                "sensitivity": "low",
                "data_points": random.randint(200, 2000),
                "format": "sensor_readings"
            },
            {
                "type": "mission_parameters",
                "sensitivity": "medium",
                "data_points": random.randint(10, 100),
                "format": "config_values"
            }
        ]
        
        # 데이터 수집 방법들
        collection_methods = [
            {
                "method": "mavlink_interception",
                "stealth": "high",
                "success_rate": 0.9,
                "data_quality": "complete"
            },
            {
                "method": "log_file_access",
                "stealth": "medium", 
                "success_rate": 0.7,
                "data_quality": "historical"
            },
            {
                "method": "memory_dump",
                "stealth": "low",
                "success_rate": 0.4,
                "data_quality": "raw"
            },
            {
                "method": "network_sniffing",
                "stealth": "high",
                "success_rate": 0.8,
                "data_quality": "real_time"
            }
        ]
        
        # 데이터 수집 시뮬레이션
        chosen_method = random.choice(collection_methods)
        exfiltrated_data = []
        
        for data_type in telemetry_types:
            if random.random() < chosen_method["success_rate"]:
                # 수집된 데이터 크기 계산
                data_size = data_type["data_points"] * random.randint(50, 500)  # bytes per point
                
                exfiltration_result = {
                    **data_type,
                    "collection_method": chosen_method["method"],
                    "data_size_bytes": data_size,
                    "collection_time": random.uniform(10, 300),  # seconds
                    "exfiltration_channel": random.choice(["http", "dns_tunnel", "steganography", "direct_tcp"])
                }
                exfiltrated_data.append(exfiltration_result)
        
        # 민감도 분석
        if exfiltrated_data:
            sensitivity_analysis = {
                "critical_data": [d for d in exfiltrated_data if d["sensitivity"] == "critical"],
                "high_sensitivity": [d for d in exfiltrated_data if d["sensitivity"] == "high"],
                "total_data_size": sum(d["data_size_bytes"] for d in exfiltrated_data),
                "privacy_impact": "severe" if any(d["sensitivity"] == "critical" for d in exfiltrated_data) else "moderate"
            }
        else:
            sensitivity_analysis = {"impact": "none"}
        
        iocs = []
        for data in exfiltrated_data:
            iocs.append(f"DATA_EXFILTRATION:{data['type']}")
            iocs.append(f"EXFIL_METHOD:{data['collection_method']}")
            iocs.append(f"EXFIL_CHANNEL:{data['exfiltration_channel']}")
            if data['sensitivity'] in ['critical', 'high']:
                iocs.append(f"SENSITIVE_DATA_STOLEN:{data['type']}")
        
        success = len(exfiltrated_data) > 0
        
        details = {
            "available_telemetry": telemetry_types,
            "collection_method": chosen_method,
            "exfiltrated_data": exfiltrated_data,
            "sensitivity_analysis": sensitivity_analysis,
            "detection_evasion": chosen_method["stealth"],
            "success_rate": chosen_method["success_rate"] if success else 0.1
        }
        
        return success, iocs, details

class FlightLogExtraction(BaseAttack):
    """비행 로그 추출 공격"""
    
    def _get_attack_type(self) -> AttackType:
        return AttackType.EXFILTRATION
    
    async def _run_attack(self) -> Tuple[bool, List[str], Dict[str, Any]]:
        """비행 기록 및 로그 파일 탈취"""
        await asyncio.sleep(4.8)
        
        # 탈취 가능한 로그 파일들
        log_files = [
            {
                "filename": "flight_log_20241214_143022.bin",
                "type": "binary_flight_data",
                "size_mb": random.uniform(5, 50),
                "contains": ["gps_tracks", "imu_data", "commands", "errors"],
                "sensitivity": "high"
            },
            {
                "filename": "telemetry_20241214.tlog",
                "type": "telemetry_log",
                "size_mb": random.uniform(1, 10),
                "contains": ["mavlink_messages", "gcs_commands", "status_updates"],
                "sensitivity": "medium"
            },
            {
                "filename": "parameters_backup.param",
                "type": "parameter_file",
                "size_mb": random.uniform(0.1, 1),
                "contains": ["system_config", "calibration_data", "security_settings"],
                "sensitivity": "high"
            },
            {
                "filename": "crash_dump_20241214.core",
                "type": "crash_dump",
                "size_mb": random.uniform(10, 100),
                "contains": ["memory_contents", "stack_traces", "system_state"],
                "sensitivity": "critical"
            },
            {
                "filename": "mission_archive.waypoints",
                "type": "mission_data",
                "size_mb": random.uniform(0.5, 5),
                "contains": ["flight_plans", "waypoints", "geofence_data"],
                "sensitivity": "medium"
            }
        ]
        
        # 접근 방법들
        access_methods = [
            {
                "method": "ftp_access",
                "success_rate": 0.8,
                "requirements": ["network_access", "weak_credentials"],
                "stealth": "low"
            },
            {
                "method": "sd_card_extraction",
                "success_rate": 0.95,
                "requirements": ["physical_access"],
                "stealth": "medium"
            },
            {
                "method": "ssh_access",
                "success_rate": 0.6,
                "requirements": ["network_access", "ssh_credentials"],
                "stealth": "medium"
            },
            {
                "method": "usb_debugging",
                "success_rate": 0.7,
                "requirements": ["physical_access", "debug_enabled"],
                "stealth": "high"
            },
            {
                "method": "companion_computer_exploit",
                "success_rate": 0.5,
                "requirements": ["network_access", "vulnerability"],
                "stealth": "high"
            }
        ]
        
        # 로그 추출 시뮬레이션
        chosen_method = random.choice(access_methods)
        extracted_logs = []
        
        for log_file in log_files:
            if random.random() < chosen_method["success_rate"]:
                extraction_result = {
                    **log_file,
                    "extraction_method": chosen_method["method"],
                    "extraction_time": random.uniform(10, log_file["size_mb"] * 2),  # seconds
                    "integrity_verified": random.choice([True, False]),
                    "exfiltration_success": True
                }
                extracted_logs.append(extraction_result)
        
        # 데이터 분석 및 가치 평가
        if extracted_logs:
            intelligence_value = {
                "operational_intelligence": [log for log in extracted_logs if "gps_tracks" in log.get("contains", [])],
                "technical_intelligence": [log for log in extracted_logs if "system_config" in log.get("contains", [])],
                "security_intelligence": [log for log in extracted_logs if log["sensitivity"] == "critical"],
                "total_size_mb": sum(log["size_mb"] for log in extracted_logs),
                "actionable_data": len([log for log in extracted_logs if log["sensitivity"] in ["high", "critical"]])
            }
        else:
            intelligence_value = {"value": "none"}
        
        iocs = []
        for log in extracted_logs:
            iocs.append(f"LOG_EXTRACTED:{log['filename']}")
            iocs.append(f"LOG_TYPE:{log['type']}")
            iocs.append(f"EXTRACTION_METHOD:{log['extraction_method']}")
            if log['sensitivity'] in ['critical', 'high']:
                iocs.append(f"SENSITIVE_LOG_STOLEN:{log['filename']}")
        
        success = len(extracted_logs) > 0
        
        details = {
            "available_logs": log_files,
            "access_method": chosen_method,
            "extracted_logs": extracted_logs,
            "intelligence_value": intelligence_value,
            "anti_forensics": random.choice([True, False]),  # Log deletion attempt
            "success_rate": chosen_method["success_rate"] if success else 0.1
        }
        
        return success, iocs, details

class VideoStreamHijacking(BaseAttack):
    """비디오 스트림 하이재킹"""
    
    def _get_attack_type(self) -> AttackType:
        return AttackType.EXFILTRATION
    
    async def _run_attack(self) -> Tuple[bool, List[str], Dict[str, Any]]:
        """실시간 비디오 스트림 탈취 및 조작"""
        await asyncio.sleep(3.4)
        
        # 비디오 스트림 정보
        video_streams = [
            {
                "stream_id": "camera_main",
                "url": "rtsp://192.168.13.2:554/live/stream1",
                "resolution": "1920x1080",
                "fps": 30,
                "codec": "H.264",
                "bitrate_mbps": 5.2,
                "authentication": "none"
            },
            {
                "stream_id": "camera_gimbal",
                "url": "rtsp://192.168.13.2:554/live/stream2", 
                "resolution": "1280x720",
                "fps": 25,
                "codec": "H.265",
                "bitrate_mbps": 3.1,
                "authentication": "basic"
            },
            {
                "stream_id": "fpv_feed",
                "url": "udp://192.168.13.2:5000",
                "resolution": "640x480",
                "fps": 60,
                "codec": "MJPEG",
                "bitrate_mbps": 2.5,
                "authentication": "none"
            }
        ]
        
        # 하이재킹 기법들
        hijacking_techniques = [
            {
                "technique": "rtsp_stream_interception",
                "success_rate": 0.9,
                "capabilities": ["view", "record"],
                "stealth": "high"
            },
            {
                "technique": "man_in_the_middle",
                "success_rate": 0.7,
                "capabilities": ["view", "record", "modify"],
                "stealth": "medium"
            },
            {
                "technique": "direct_camera_access",
                "success_rate": 0.5,
                "capabilities": ["view", "record", "control"],
                "stealth": "low"
            },
            {
                "technique": "stream_replay_attack",
                "success_rate": 0.8,
                "capabilities": ["inject_fake_feed"],
                "stealth": "high"
            }
        ]
        
        # 하이재킹 시뮬레이션
        hijacked_streams = []
        
        for stream in video_streams:
            if stream["authentication"] == "none" or random.random() > 0.3:
                technique = random.choice(hijacking_techniques)
                
                if random.random() < technique["success_rate"]:
                    hijack_result = {
                        **stream,
                        "hijacking_technique": technique["technique"],
                        "capabilities_achieved": technique["capabilities"],
                        "capture_duration": random.uniform(60, 1800),  # 1-30 minutes
                        "data_captured_mb": stream["bitrate_mbps"] * (random.uniform(60, 1800) / 60),
                        "real_time_access": "view" in technique["capabilities"]
                    }
                    hijacked_streams.append(hijack_result)
        
        # 정보 가치 분석
        if hijacked_streams:
            intelligence_analysis = {
                "surveillance_value": len([s for s in hijacked_streams if s["resolution"] in ["1920x1080", "1280x720"]]),
                "real_time_capability": len([s for s in hijacked_streams if s["real_time_access"]]),
                "total_footage_mb": sum(s["data_captured_mb"] for s in hijacked_streams),
                "operational_exposure": "high" if len(hijacked_streams) >= 2 else "medium",
                "privacy_violation": "severe" if any("control" in s["capabilities_achieved"] for s in hijacked_streams) else "moderate"
            }
        else:
            intelligence_analysis = {"exposure": "none"}
        
        iocs = []
        for stream in hijacked_streams:
            iocs.append(f"VIDEO_STREAM_HIJACKED:{stream['stream_id']}")
            iocs.append(f"HIJACK_TECHNIQUE:{stream['hijacking_technique']}")
            iocs.append(f"STREAM_URL:{stream['url']}")
            if "control" in stream["capabilities_achieved"]:
                iocs.append(f"CAMERA_CONTROL_GAINED:{stream['stream_id']}")
        
        success = len(hijacked_streams) > 0
        
        details = {
            "available_streams": video_streams,
            "hijacked_streams": hijacked_streams,
            "intelligence_analysis": intelligence_analysis,
            "countermeasures_bypassed": len([s for s in hijacked_streams if s["authentication"] != "none"]),
            "success_rate": 0.8 if success else 0.2
        }
        
        return success, iocs, details

# =============================================================================
# 6. FIRMWARE ATTACKS 공격들
# =============================================================================

class BootloaderExploit(BaseAttack):
    """부트로더 취약점 공격"""
    
    def _get_attack_type(self) -> AttackType:
        return AttackType.FIRMWARE_ATTACKS
    
    async def _run_attack(self) -> Tuple[bool, List[str], Dict[str, Any]]:
        """부트로더 단계에서 시스템 컴프로마이즈"""
        await asyncio.sleep(6.2)
        
        # 부트로더 정보
        bootloader_info = {
            "type": random.choice(["PX4 Bootloader", "ArduPilot Bootloader", "Custom Bootloader"]),
            "version": f"{random.randint(1, 3)}.{random.randint(0, 9)}.{random.randint(0, 9)}",
            "security_features": {
                "secure_boot": random.choice([True, False]),
                "code_signing": random.choice([True, False]),
                "encryption": random.choice([True, False]),
                "debug_locked": random.choice([True, False])
            }
        }
        
        # 공격 벡터들
        exploit_vectors = [
            {
                "vector": "buffer_overflow",
                "cve": "CVE-2023-XXXX",
                "success_rate": 0.6,
                "requirements": ["physical_access", "debug_interface"],
                "persistence": "boot_persistent"
            },
            {
                "vector": "signature_bypass",
                "cve": "CVE-2022-YYYY", 
                "success_rate": 0.3,
                "requirements": ["weak_crypto", "timing_attack"],
                "persistence": "firmware_level"
            },
            {
                "vector": "debug_interface_abuse",
                "cve": "N/A",
                "success_rate": 0.8,
                "requirements": ["jtag_access", "debug_enabled"],
                "persistence": "memory_only"
            },
            {
                "vector": "electromagnetic_fault_injection",
                "cve": "N/A",
                "success_rate": 0.4,
                "requirements": ["specialized_equipment", "precise_timing"],
                "persistence": "temporary"
            }
        ]
        
        # 공격 실행
        successful_exploits = []
        
        for vector in exploit_vectors:
            # 보안 기능 확인
            blocked_by_security = False
            if vector["vector"] == "signature_bypass" and bootloader_info["security_features"]["code_signing"]:
                if random.random() > 0.2:  # 80% 차단
                    blocked_by_security = True
            
            if not blocked_by_security and random.random() < vector["success_rate"]:
                exploit_result = {
                    **vector,
                    "execution_time": random.uniform(30, 300),
                    "payload_injected": True,
                    "system_compromise_level": random.choice(["partial", "full"]),
                    "detection_risk": random.choice(["low", "medium", "high"])
                }
                successful_exploits.append(exploit_result)
        
        # 페이로드 정보
        if successful_exploits:
            payload_info = {
                "type": random.choice(["backdoor", "rootkit", "keylogger", "remote_shell"]),
                "capabilities": [
                    "firmware_modification",
                    "parameter_manipulation", 
                    "command_injection",
                    "data_exfiltration"
                ],
                "stealth_features": [
                    "anti_debug",
                    "code_obfuscation",
                    "legitimate_signature_spoofing"
                ],
                "activation_trigger": random.choice(["boot_sequence", "specific_command", "timer_based"])
            }
        else:
            payload_info = None
        
        iocs = []
        for exploit in successful_exploits:
            iocs.append(f"BOOTLOADER_EXPLOIT:{exploit['vector']}")
            iocs.append(f"FIRMWARE_COMPROMISE:{exploit['persistence']}")
            if exploit.get("cve") != "N/A":
                iocs.append(f"CVE_EXPLOITED:{exploit['cve']}")
            if exploit["system_compromise_level"] == "full":
                iocs.append(f"FULL_SYSTEM_COMPROMISE")
        
        success = len(successful_exploits) > 0
        
        details = {
            "bootloader_info": bootloader_info,
            "exploit_vectors": exploit_vectors,
            "successful_exploits": successful_exploits,
            "payload_info": payload_info,
            "security_bypass": len([e for e in successful_exploits if "bypass" in e["vector"]]),
            "success_rate": 0.5 if success else 0.1
        }
        
        return success, iocs, details

class FirmwareRollbackAttack(BaseAttack):
    """펌웨어 롤백 공격"""
    
    def _get_attack_type(self) -> AttackType:
        return AttackType.FIRMWARE_ATTACKS
    
    async def _run_attack(self) -> Tuple[bool, List[str], Dict[str, Any]]:
        """취약한 이전 버전 펌웨어로 강제 다운그레이드"""
        await asyncio.sleep(4.7)
        
        # 현재 펌웨어 정보
        current_firmware = {
            "version": f"ArduCopter-4.{random.randint(3, 5)}.{random.randint(0, 9)}",
            "build_date": "2024-12-01",
            "security_patches": random.randint(15, 30),
            "known_vulnerabilities": 0
        }
        
        # 타겟 롤백 버전들
        vulnerable_versions = [
            {
                "version": "ArduCopter-4.0.7",
                "vulnerabilities": [
                    {"cve": "CVE-2021-1234", "severity": "high", "type": "buffer_overflow"},
                    {"cve": "CVE-2021-5678", "severity": "medium", "type": "privilege_escalation"}
                ],
                "rollback_difficulty": "easy",
                "exploitation_tools_available": True
            },
            {
                "version": "ArduCopter-3.6.12",
                "vulnerabilities": [
                    {"cve": "CVE-2020-9999", "severity": "critical", "type": "remote_code_execution"},
                    {"cve": "CVE-2020-8888", "severity": "high", "type": "authentication_bypass"}
                ],
                "rollback_difficulty": "medium",
                "exploitation_tools_available": True
            },
            {
                "version": "ArduCopter-3.4.6",
                "vulnerabilities": [
                    {"cve": "CVE-2019-7777", "severity": "critical", "type": "memory_corruption"},
                    {"cve": "CVE-2019-6666", "severity": "high", "type": "input_validation"}
                ],
                "rollback_difficulty": "hard", 
                "exploitation_tools_available": False
            }
        ]
        
        # 롤백 공격 방법들
        rollback_methods = [
            {
                "method": "firmware_update_interception",
                "success_rate": 0.7,
                "requirements": ["network_access", "mitm_capability"],
                "detection_difficulty": "medium"
            },
            {
                "method": "bootloader_manipulation",
                "success_rate": 0.5,
                "requirements": ["physical_access", "debug_interface"],
                "detection_difficulty": "low"
            },
            {
                "method": "update_server_compromise",
                "success_rate": 0.3,
                "requirements": ["server_access", "code_signing_bypass"],
                "detection_difficulty": "high"
            },
            {
                "method": "local_firmware_replacement",
                "success_rate": 0.9,
                "requirements": ["file_system_access", "signature_bypass"],
                "detection_difficulty": "low"
            }
        ]
        
        # 롤백 시도
        chosen_method = random.choice(rollback_methods)
        target_version = random.choice(vulnerable_versions)
        
        success = random.random() < chosen_method["success_rate"]
        
        if success:
            rollback_result = {
                "original_version": current_firmware["version"],
                "target_version": target_version["version"],
                "method_used": chosen_method["method"],
                "vulnerabilities_introduced": target_version["vulnerabilities"],
                "exploitation_readiness": target_version["exploitation_tools_available"],
                "rollback_duration": random.uniform(60, 600)  # seconds
            }
            
            # 즉시 취약점 활용 시도
            if target_version["exploitation_tools_available"]:
                immediate_exploitation = {
                    "attempted": True,
                    "successful_exploits": random.sample(
                        target_version["vulnerabilities"], 
                        k=random.randint(1, len(target_version["vulnerabilities"]))
                    ),
                    "privileges_gained": random.choice(["user", "admin", "root"]),
                    "persistence_established": random.choice([True, False])
                }
            else:
                immediate_exploitation = {"attempted": False}
        else:
            rollback_result = None
            immediate_exploitation = {"attempted": False}
        
        iocs = []
        if success:
            iocs.append(f"FIRMWARE_ROLLBACK:{current_firmware['version']}_to_{target_version['version']}")
            iocs.append(f"ROLLBACK_METHOD:{chosen_method['method']}")
            for vuln in target_version["vulnerabilities"]:
                iocs.append(f"VULNERABILITY_INTRODUCED:{vuln['cve']}")
            
            if immediate_exploitation.get("successful_exploits"):
                for exploit in immediate_exploitation["successful_exploits"]:
                    iocs.append(f"IMMEDIATE_EXPLOIT:{exploit['cve']}")
        else:
            iocs.append(f"ROLLBACK_ATTEMPT_FAILED:{chosen_method['method']}")
        
        details = {
            "current_firmware": current_firmware,
            "target_versions": vulnerable_versions,
            "rollback_method": chosen_method,
            "rollback_result": rollback_result,
            "immediate_exploitation": immediate_exploitation,
            "risk_amplification": len(target_version["vulnerabilities"]) if success else 0,
            "success_rate": chosen_method["success_rate"] if success else 0.0
        }
        
        return success, iocs, details

class SecureBootBypass(BaseAttack):
    """보안 부팅 우회 공격"""
    
    def _get_attack_type(self) -> AttackType:
        return AttackType.FIRMWARE_ATTACKS
    
    async def _run_attack(self) -> Tuple[bool, List[str], Dict[str, Any]]:
        """보안 부팅 메커니즘 우회하여 무결성 검사 무력화"""
        await asyncio.sleep(5.8)
        
        # 보안 부팅 구성
        secure_boot_config = {
            "enabled": True,
            "boot_chain": ["bootloader", "kernel", "filesystem"],
            "signature_algorithm": random.choice(["RSA-2048", "ECDSA-256", "RSA-4096"]),
            "key_storage": random.choice(["efuse", "otp", "secure_element"]),
            "rollback_protection": random.choice([True, False]),
            "debug_disable": random.choice([True, False])
        }
        
        # 우회 기법들
        bypass_techniques = [
            {
                "technique": "key_extraction",
                "method": "side_channel_analysis",
                "success_rate": 0.3,
                "requirements": ["specialized_equipment", "physical_access", "time"],
                "complexity": "very_high"
            },
            {
                "technique": "signature_forgery",
                "method": "cryptographic_weakness",
                "success_rate": 0.2,
                "requirements": ["weak_rng", "mathematical_analysis"],
                "complexity": "high"
            },
            {
                "technique": "boot_chain_manipulation",
                "method": "intermediate_certificate",
                "success_rate": 0.4,
                "requirements": ["certificate_authority_compromise"],
                "complexity": "medium"
            },
            {
                "technique": "hardware_glitching",
                "method": "voltage_fault_injection",
                "success_rate": 0.5,
                "requirements": ["precise_timing", "voltage_control"],
                "complexity": "high"
            },
            {
                "technique": "jtag_exploitation",
                "method": "debug_interface_abuse",
                "success_rate": 0.8,
                "requirements": ["debug_enabled", "jtag_access"],
                "complexity": "low"
            },
            {
                "technique": "secure_element_bypass",
                "method": "communication_interception",
                "success_rate": 0.3,
                "requirements": ["bus_access", "protocol_knowledge"],
                "complexity": "medium"
            }
        ]
        
        # 우회 시도
        attempted_bypasses = []
        successful_bypasses = []
        
        for technique in bypass_techniques:
            # 현재 보안 설정에 따른 성공률 조정
            adjusted_success_rate = technique["success_rate"]
            
            if technique["technique"] == "jtag_exploitation" and secure_boot_config["debug_disable"]:
                adjusted_success_rate *= 0.1  # 디버그 비활성화시 성공률 대폭 감소
            
            if technique["technique"] == "signature_forgery" and secure_boot_config["signature_algorithm"] == "RSA-4096":
                adjusted_success_rate *= 0.5  # 강한 암호화시 성공률 감소
            
            attempt = {
                **technique,
                "attempted": True,
                "adjusted_success_rate": adjusted_success_rate,
                "attempt_duration": random.uniform(300, 3600)  # 5분-1시간
            }
            attempted_bypasses.append(attempt)
            
            if random.random() < adjusted_success_rate:
                bypass_result = {
                    **attempt,
                    "successful": True,
                    "bypass_method": technique["method"],
                    "persistence": random.choice(["boot_persistent", "session_only"]),
                    "stealth_level": random.choice(["high", "medium", "low"])
                }
                successful_bypasses.append(bypass_result)
        
        # 우회 성공 시 추가 권한
        if successful_bypasses:
            gained_capabilities = {
                "unsigned_code_execution": True,
                "firmware_modification": True,
                "boot_process_control": True,
                "secure_storage_access": len([b for b in successful_bypasses if "secure_element" in b["technique"]]) > 0,
                "debug_access_restored": len([b for b in successful_bypasses if "jtag" in b["technique"]]) > 0
            }
            
            # 후속 공격 기회
            follow_up_attacks = [
                "firmware_implant_installation",
                "cryptographic_key_extraction", 
                "persistent_backdoor_creation",
                "secure_boot_permanent_disable"
            ]
        else:
            gained_capabilities = {}
            follow_up_attacks = []
        
        iocs = []
        for bypass in successful_bypasses:
            iocs.append(f"SECURE_BOOT_BYPASS:{bypass['technique']}")
            iocs.append(f"BYPASS_METHOD:{bypass['method']}")
            if bypass["persistence"] == "boot_persistent":
                iocs.append(f"PERSISTENT_BOOT_COMPROMISE")
        
        if gained_capabilities.get("unsigned_code_execution"):
            iocs.append("UNSIGNED_CODE_EXECUTION_ENABLED")
        if gained_capabilities.get("secure_storage_access"):
            iocs.append("SECURE_STORAGE_COMPROMISED")
        
        success = len(successful_bypasses) > 0
        
        details = {
            "secure_boot_config": secure_boot_config,
            "bypass_techniques": bypass_techniques,
            "attempted_bypasses": attempted_bypasses,
            "successful_bypasses": successful_bypasses,
            "gained_capabilities": gained_capabilities,
            "follow_up_attacks": follow_up_attacks,
            "overall_security_impact": "critical" if success else "none",
            "success_rate": len(successful_bypasses) / len(attempted_bypasses) if attempted_bypasses else 0.0
        }
        
        return success, iocs, details

# =============================================================================
# 공격 시나리오 등록 및 관리
# =============================================================================

# 모든 DVD 공격 시나리오 정의
DVD_ATTACK_SCENARIOS = {
    # Reconnaissance
    "wifi_network_discovery": {
        "class": WiFiNetworkDiscovery,
        "scenario": DVDAttackScenario(
            name="WiFi Network Discovery",
            tactic=DVDAttackTactic.RECONNAISSANCE,
            description="Discover and enumerate drone WiFi networks",
            required_states=[DVDFlightState.PRE_FLIGHT, DVDFlightState.TAKEOFF, DVDFlightState.AUTOPILOT_FLIGHT],
            difficulty="beginner",
            prerequisites=["wifi_adapter", "monitor_mode"],
            targets=["network", "companion_computer"]
        )
    },
    "mavlink_service_discovery": {
        "class": MAVLinkServiceDiscovery,
        "scenario": DVDAttackScenario(
            name="MAVLink Service Discovery",
            tactic=DVDAttackTactic.RECONNAISSANCE,
            description="Scan for and identify MAVLink services",
            required_states=[DVDFlightState.PRE_FLIGHT, DVDFlightState.AUTOPILOT_FLIGHT],
            difficulty="beginner",
            prerequisites=["network_access"],
            targets=["flight_controller", "gcs"]
        )
    },
    "drone_component_enumeration": {
        "class": DroneComponentEnumeration,
        "scenario": DVDAttackScenario(
            name="Drone Component Enumeration",
            tactic=DVDAttackTactic.RECONNAISSANCE,
            description="Identify and catalog drone system components",
            required_states=list(DVDFlightState),
            difficulty="intermediate",
            prerequisites=["network_access", "scanning_tools"],
            targets=["flight_controller", "companion_computer", "gcs"]
        )
    },
    "camera_stream_discovery": {
        "class": CameraStreamDiscovery,
        "scenario": DVDAttackScenario(
            name="Camera Stream Discovery",
            tactic=DVDAttackTactic.RECONNAISSANCE,
            description="Locate and access video streams",
            required_states=[DVDFlightState.TAKEOFF, DVDFlightState.AUTOPILOT_FLIGHT],
            difficulty="beginner",
            prerequisites=["network_access"],
            targets=["companion_computer"]
        )
    },
    
    # Protocol Tampering
    "mavlink_packet_injection": {
        "class": MAVLinkPacketInjection,
        "scenario": DVDAttackScenario(
            name="MAVLink Packet Injection",
            tactic=DVDAttackTactic.PROTOCOL_TAMPERING,
            description="Inject malicious MAVLink messages",
            required_states=[DVDFlightState.AUTOPILOT_FLIGHT, DVDFlightState.MANUAL_FLIGHT],
            difficulty="intermediate",
            prerequisites=["mavlink_knowledge", "packet_crafting"],
            targets=["flight_controller"]
        )
    },
    "gps_spoofing": {
        "class": GPSSpoofing,
        "scenario": DVDAttackScenario(
            name="GPS Spoofing",
            tactic=DVDAttackTactic.PROTOCOL_TAMPERING,
            description="Manipulate GPS signals to alter drone position",
            required_states=[DVDFlightState.AUTOPILOT_FLIGHT],
            difficulty="advanced",
            prerequisites=["sdr_equipment", "gps_knowledge"],
            targets=["flight_controller"]
        )
    },
    "rf_jamming": {
        "class": RadioFrequencyJamming,
        "scenario": DVDAttackScenario(
            name="Radio Frequency Jamming",
            tactic=DVDAttackTactic.PROTOCOL_TAMPERING,
            description="Disrupt drone communications via RF interference",
            required_states=list(DVDFlightState),
            difficulty="intermediate",
            prerequisites=["rf_equipment", "frequency_knowledge"],
            targets=["network", "flight_controller", "gcs"]
        )
    },
    
    # Denial of Service
    "mavlink_flood": {
        "class": MAVLinkFloodAttack,
        "scenario": DVDAttackScenario(
            name="MAVLink Flood Attack",
            tactic=DVDAttackTactic.DENIAL_OF_SERVICE,
            description="Overwhelm MAVLink services with excessive traffic",
            required_states=list(DVDFlightState),
            difficulty="beginner",
            prerequisites=["network_access"],
            targets=["flight_controller", "gcs"]
        )
    },
    "wifi_deauth": {
        "class": WiFiDeauthenticationAttack,
        "scenario": DVDAttackScenario(
            name="WiFi Deauthentication",
            tactic=DVDAttackTactic.DENIAL_OF_SERVICE,
            description="Force disconnect WiFi clients from drone networks",
            required_states=list(DVDFlightState),
            difficulty="beginner",
            prerequisites=["wifi_adapter", "monitor_mode"],
            targets=["network", "companion_computer"]
        )
    },
    "resource_exhaustion": {
        "class": CompanionComputerResourceExhaustion,
        "scenario": DVDAttackScenario(
            name="Resource Exhaustion",
            tactic=DVDAttackTactic.DENIAL_OF_SERVICE,
            description="Exhaust companion computer system resources",
            required_states=list(DVDFlightState),
            difficulty="intermediate",
            prerequisites=["system_access", "scripting"],
            targets=["companion_computer"]
        )
    },
    
    # Injection
    "flight_plan_injection": {
        "class": FlightPlanInjection,
        "scenario": DVDAttackScenario(
            name="Flight Plan Injection",
            tactic=DVDAttackTactic.INJECTION,
            description="Inject malicious waypoints into flight plans",
            required_states=[DVDFlightState.PRE_FLIGHT, DVDFlightState.AUTOPILOT_FLIGHT],
            difficulty="intermediate",
            prerequisites=["mavlink_access", "mission_planning"],
            targets=["flight_controller", "gcs"]
        )
    },
    "parameter_manipulation": {
        "class": ParameterManipulation,
        "scenario": DVDAttackScenario(
            name="Parameter Manipulation",
            tactic=DVDAttackTactic.INJECTION,
            description="Modify critical system parameters",
            required_states=[DVDFlightState.PRE_FLIGHT],
            difficulty="advanced",
            prerequisites=["parameter_access", "system_knowledge"],
            targets=["flight_controller"]
        )
    },
    "firmware_upload_manipulation": {
        "class": FirmwareUploadManipulation,
        "scenario": DVDAttackScenario(
            name="Firmware Upload Manipulation",
            tactic=DVDAttackTactic.INJECTION,
            description="Inject malicious code during firmware updates",
            required_states=[DVDFlightState.PRE_FLIGHT, DVDFlightState.POST_FLIGHT],
            difficulty="advanced",
            prerequisites=["firmware_access", "binary_analysis"],
            targets=["flight_controller"]
        )
    },
    
    # Exfiltration
    "telemetry_exfiltration": {
        "class": TelemetryDataExfiltration,
        "scenario": DVDAttackScenario(
            name="Telemetry Data Exfiltration",
            tactic=DVDAttackTactic.EXFILTRATION,
            description="Extract sensitive telemetry and operational data",
            required_states=list(DVDFlightState),
            difficulty="intermediate",
            prerequisites=["network_access", "data_analysis"],
            targets=["flight_controller", "companion_computer", "gcs"]
        )
    },
    "flight_log_extraction": {
        "class": FlightLogExtraction,
        "scenario": DVDAttackScenario(
            name="Flight Log Extraction",
            tactic=DVDAttackTactic.EXFILTRATION,
            description="Extract flight logs and historical data",
            required_states=[DVDFlightState.POST_FLIGHT],
            difficulty="beginner",
            prerequisites=["file_access"],
            targets=["flight_controller", "companion_computer"]
        )
    },
    "video_stream_hijacking": {
        "class": VideoStreamHijacking,
        "scenario": DVDAttackScenario(
            name="Video Stream Hijacking",
            tactic=DVDAttackTactic.EXFILTRATION,
            description="Intercept and manipulate real-time video feeds",
            required_states=[DVDFlightState.TAKEOFF, DVDFlightState.AUTOPILOT_FLIGHT],
            difficulty="intermediate",
            prerequisites=["network_access", "video_tools"],
            targets=["companion_computer"]
        )
    },
    
    # Firmware Attacks
    "bootloader_exploit": {
        "class": BootloaderExploit,
        "scenario": DVDAttackScenario(
            name="Bootloader Exploit",
            tactic=DVDAttackTactic.FIRMWARE_ATTACKS,
            description="Exploit bootloader vulnerabilities for system compromise",
            required_states=[DVDFlightState.PRE_FLIGHT, DVDFlightState.POST_FLIGHT],
            difficulty="advanced",
            prerequisites=["physical_access", "hardware_tools"],
            targets=["flight_controller"]
        )
    },
    "firmware_rollback": {
        "class": FirmwareRollbackAttack,
        "scenario": DVDAttackScenario(
            name="Firmware Rollback Attack",
            tactic=DVDAttackTactic.FIRMWARE_ATTACKS,
            description="Downgrade to vulnerable firmware versions",
            required_states=[DVDFlightState.PRE_FLIGHT, DVDFlightState.POST_FLIGHT],
            difficulty="advanced",
            prerequisites=["firmware_access", "vulnerability_database"],
            targets=["flight_controller"]
        )
    },
    "secure_boot_bypass": {
        "class": SecureBootBypass,
        "scenario": DVDAttackScenario(
            name="Secure Boot Bypass",
            tactic=DVDAttackTactic.FIRMWARE_ATTACKS,
            description="Bypass secure boot mechanisms",
            required_states=[DVDFlightState.PRE_FLIGHT],
            difficulty="advanced",
            prerequisites=["hardware_access", "cryptographic_tools"],
            targets=["flight_controller"]
        )
    }
}

def register_all_dvd_attacks(dvd_lite):
    """DVD-Lite에 모든 DVD 공격 시나리오 등록"""
    registered_attacks = []
    
    for attack_name, attack_info in DVD_ATTACK_SCENARIOS.items():
        try:
            dvd_lite.register_attack(attack_name, attack_info["class"])
            registered_attacks.append(attack_name)
        except Exception as e:
            logger.error(f"공격 등록 실패 {attack_name}: {str(e)}")
    
    logger.info(f"✅ {len(registered_attacks)}개 DVD 공격 시나리오 등록 완료")
    return registered_attacks

def get_attacks_by_tactic(tactic: DVDAttackTactic) -> List[str]:
    """전술별 공격 목록 반환"""
    return [
        name for name, info in DVD_ATTACK_SCENARIOS.items()
        if info["scenario"].tactic == tactic
    ]

def get_attacks_by_difficulty(difficulty: str) -> List[str]:
    """난이도별 공격 목록 반환"""
    return [
        name for name, info in DVD_ATTACK_SCENARIOS.items()
        if info["scenario"].difficulty == difficulty
    ]

def get_attacks_by_flight_state(state: DVDFlightState) -> List[str]:
    """비행 상태별 가능한 공격 목록 반환"""
    return [
        name for name, info in DVD_ATTACK_SCENARIOS.items()
        if state in info["scenario"].required_states
    ]