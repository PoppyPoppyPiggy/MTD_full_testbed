# dvd_lite/dvd_attacks/reconnaissance/mavlink_discovery.py
"""
MAVLink 서비스 발견 및 열거 공격 (Damn Vulnerable Drone 기반)
"""

import asyncio
import random
import struct
from typing import Tuple, List, Dict, Any

from ..core.attack_base import BaseAttack, AttackType

class MAVLinkServiceDiscovery(BaseAttack):
    """MAVLink 서비스 발견 및 열거"""
    
    def _get_attack_type(self) -> AttackType:
        return AttackType.RECONNAISSANCE
    
    async def _run_attack(self) -> Tuple[bool, List[str], Dict[str, Any]]:
        """네트워크에서 MAVLink 서비스 스캔 및 시스템 정보 수집"""
        await asyncio.sleep(3.2)
        
        # DVD 환경의 실제 네트워크 구성
        target_networks = [
            "192.168.13.0/24",  # DVD 기본 네트워크
            "127.0.0.1/32",     # 로컬 시스템
            "10.0.1.0/24",      # 컴패니언 컴퓨터 네트워크
            "172.16.0.0/24"     # 추가 내부 네트워크
        ]
        
        # 일반적인 MAVLink 포트들
        mavlink_ports = [
            {"port": 14550, "service": "Flight Controller (Primary)", "protocol": "UDP"},
            {"port": 14551, "service": "Ground Control Station", "protocol": "UDP"},
            {"port": 14552, "service": "Companion Computer", "protocol": "UDP"},
            {"port": 5760, "service": "SITL Simulator", "protocol": "TCP"},
            {"port": 5762, "service": "Secondary GCS", "protocol": "TCP"},
            {"port": 5763, "service": "Relay Node", "protocol": "TCP"},
            {"port": 9000, "service": "QGroundControl Custom", "protocol": "UDP"},
            {"port": 18570, "service": "Mission Planner", "protocol": "UDP"}
        ]
        
        discovered_services = []
        heartbeat_responses = []
        
        # DVD 환경 특정 서비스들
        dvd_services = [
            {
                "host": "192.168.13.2",
                "port": 14550,
                "service": "ArduPilot SITL Flight Controller",
                "version": "MAVLink 2.0",
                "system_id": 1,
                "component_id": 1,
                "autopilot": "ArduPilot",
                "vehicle_type": "Quadrotor",
                "firmware_version": "4.3.8",
                "capabilities": [
                    "MISSION_FLOAT", "PARAM_FLOAT", "COMPASS_CAL",
                    "FLIGHT_TERMINATION", "FLIGHT_INFORMATION"
                ],
                "flight_modes": [
                    "STABILIZE", "ACRO", "ALT_HOLD", "AUTO", "GUIDED",
                    "LOITER", "RTL", "CIRCLE", "LAND", "BRAKE"
                ]
            },
            {
                "host": "192.168.13.3",
                "port": 14552,
                "service": "Companion Computer MAVLink Router",
                "version": "MAVLink 2.0",
                "system_id": 2,
                "component_id": 191,
                "autopilot": "Invalid",
                "vehicle_type": "Generic",
                "os": "Ubuntu 20.04",
                "mavlink_router_version": "2.1",
                "endpoints": [
                    "udp:192.168.13.1:14550",
                    "serial:/dev/ttyACM0:57600",
                    "tcp:0.0.0.0:5760"
                ]
            }
        ]
        
        # 네트워크 스캔 시뮬레이션
        scan_results = []
        for network in target_networks:
            if "192.168.13" in network:  # DVD 네트워크
                # DVD 환경에서는 더 높은 발견률
                for service in dvd_services:
                    if random.random() > 0.1:  # 90% 발견률
                        discovered_services.append(service)
                        scan_results.append({
                            "network": network,
                            "host": service["host"],
                            "port": service["port"],
                            "status": "open",
                            "service": service["service"]
                        })
            else:
                # 다른 네트워크에서는 일반적인 스캔
                hosts_in_network = random.randint(1, 5)
                for i in range(hosts_in_network):
                    if random.random() > 0.6:  # 40% 확률
                        host_ip = self._generate_ip_in_network(network)
                        port_info = random.choice(mavlink_ports)
                        
                        service_info = {
                            "host": host_ip,
                            "port": port_info["port"],
                            "service": port_info["service"],
                            "protocol": port_info["protocol"],
                            "version": random.choice(["MAVLink 1.0", "MAVLink 2.0"]),
                            "system_id": random.randint(1, 255),
                            "component_id": random.randint(1, 255),
                            "autopilot": random.choice([
                                "ArduPilot", "PX4", "Generic", "Invalid"
                            ])
                        }
                        discovered_services.append(service_info)
                        scan_results.append({
                            "network": network,
                            "host": host_ip,
                            "port": port_info["port"],
                            "status": "open",
                            "service": port_info["service"]
                        })
        
        # MAVLink 메시지 시뮬레이션
        for service in discovered_services:
            if random.random() > 0.3:  # 70% 확률로 HEARTBEAT 응답
                heartbeat = self._simulate_heartbeat(service)
                heartbeat_responses.append(heartbeat)
        
        # 시스템 분석
        system_analysis = self._analyze_discovered_systems(discovered_services)
        
        # IOC 생성
        iocs = []
        for service in discovered_services:
            iocs.append(f"MAVLINK_SERVICE:{service['host']}:{service['port']}")
            iocs.append(f"MAVLINK_SYSTEM_ID:{service.get('system_id', 'unknown')}")
            iocs.append(f"MAVLINK_COMPONENT_ID:{service.get('component_id', 'unknown')}")
            
            if service.get("autopilot") == "ArduPilot":
                iocs.append(f"ARDUPILOT_DETECTED:{service['host']}")
            elif service.get("autopilot") == "PX4":
                iocs.append(f"PX4_DETECTED:{service['host']}")
            
            # DVD 환경 특정 IOC
            if "192.168.13" in service["host"]:
                iocs.append("DVD_MAVLINK_SERVICE")
                if "SITL" in service.get("service", ""):
                    iocs.append("SITL_SIMULATOR_DETECTED")
        
        # 취약점 식별
        vulnerabilities = self._identify_vulnerabilities(discovered_services)
        for vuln in vulnerabilities:
            iocs.append(f"MAVLINK_VULNERABILITY:{vuln['type']}")
        
        success = len(discovered_services) > 0
        
        details = {
            "scan_results": scan_results,
            "discovered_services": discovered_services,
            "heartbeat_responses": heartbeat_responses,
            "system_analysis": system_analysis,
            "vulnerabilities": vulnerabilities,
            "dvd_environment_detected": any("192.168.13" in s["host"] for s in discovered_services),
            "total_discovered": len(discovered_services),
            "success_rate": 0.75 if success else 0.1,
            "recommended_attacks": [
                "MAVLink message injection",
                "Parameter manipulation",
                "Mission upload/download",
                "Telemetry interception"
            ]
        }
        
        return success, iocs, details
    
    def _generate_ip_in_network(self, network: str) -> str:
        """네트워크 범위 내에서 IP 생성"""
        if "192.168.13" in network:
            return f"192.168.13.{random.randint(1, 254)}"
        elif "127.0.0.1" in network:
            return "127.0.0.1"
        elif "10.0.1" in network:
            return f"10.0.1.{random.randint(1, 254)}"
        elif "172.16" in network:
            return f"172.16.{random.randint(0, 255)}.{random.randint(1, 254)}"
        else:
            return f"192.168.{random.randint(1, 254)}.{random.randint(1, 254)}"
    
    def _simulate_heartbeat(self, service: Dict[str, Any]) -> Dict[str, Any]:
        """MAVLink HEARTBEAT 메시지 시뮬레이션"""
        return {
            "host": service["host"],
            "port": service["port"],
            "message_type": "HEARTBEAT",
            "system_id": service.get("system_id", 1),
            "component_id": service.get("component_id", 1),
            "mavlink_version": service.get("version", "MAVLink 2.0"),
            "autopilot": service.get("autopilot", "ArduPilot"),
            "vehicle_type": service.get("vehicle_type", "Generic"),
            "system_status": random.choice([
                "MAV_STATE_UNINIT", "MAV_STATE_BOOT", "MAV_STATE_CALIBRATING",
                "MAV_STATE_STANDBY", "MAV_STATE_ACTIVE", "MAV_STATE_CRITICAL"
            ]),
            "base_mode": random.randint(0, 255),
            "custom_mode": random.randint(0, 4294967295),
            "timestamp": random.randint(0, 4294967295)
        }
    
    def _analyze_discovered_systems(self, services: List[Dict[str, Any]]) -> Dict[str, Any]:
        """발견된 시스템들 분석"""
        analysis = {
            "total_systems": len(set(s["host"] for s in services)),
            "autopilot_breakdown": {},
            "version_breakdown": {},
            "network_topology": {},
            "potential_fleet": len(services) > 3
        }
        
        for service in services:
            # Autopilot 분석
            autopilot = service.get("autopilot", "Unknown")
            analysis["autopilot_breakdown"][autopilot] = analysis["autopilot_breakdown"].get(autopilot, 0) + 1
            
            # 버전 분석
            version = service.get("version", "Unknown")
            analysis["version_breakdown"][version] = analysis["version_breakdown"].get(version, 0) + 1
            
            # 네트워크 토폴로지
            network = ".".join(service["host"].split(".")[:3]) + ".0"
            if network not in analysis["network_topology"]:
                analysis["network_topology"][network] = []
            analysis["network_topology"][network].append({
                "host": service["host"],
                "service": service.get("service", "Unknown")
            })
        
        return analysis
    
    def _identify_vulnerabilities(self, services: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """MAVLink 서비스 취약점 식별"""
        vulnerabilities = []
        
        for service in services:
            # 인증 없는 MAVLink
            vulnerabilities.append({
                "host": service["host"],
                "port": service["port"],
                "type": "unauthenticated_mavlink",
                "severity": "high",
                "description": "MAVLink service without authentication"
            })
            
            # MAVLink 1.0 사용 (낮은 보안)
            if service.get("version") == "MAVLink 1.0":
                vulnerabilities.append({
                    "host": service["host"],
                    "port": service["port"],
                    "type": "mavlink_v1_insecure",
                    "severity": "medium",
                    "description": "Using insecure MAVLink 1.0 protocol"
                })
            
            # SITL 환경 노출
            if "SITL" in service.get("service", ""):
                vulnerabilities.append({
                    "host": service["host"],
                    "port": service["port"],
                    "type": "sitl_exposure",
                    "severity": "medium",
                    "description": "SITL simulator exposed on network"
                })
            
            # 기본 포트 사용
            if service["port"] in [14550, 14551, 14552]:
                vulnerabilities.append({
                    "host": service["host"],
                    "port": service["port"],
                    "type": "default_port_usage",
                    "severity": "low",
                    "description": "Using default MAVLink ports"
                })
        
        return vulnerabilities