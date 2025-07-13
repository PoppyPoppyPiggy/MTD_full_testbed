# dvd_connector/safety_checker.py
"""
DVD 안전성 검증 모듈
실제 DVD 환경 연동 시 안전성 확인
"""

import logging
import ipaddress
import socket
from typing import Dict, List, Any, Optional
import subprocess

logger = logging.getLogger(__name__)

class SafetyChecker:
    """DVD 연동 안전성 검증"""
    
    def __init__(self):
        self.safe_networks = [
            "10.13.0.0/24",      # DVD 표준 네트워크
            "192.168.13.0/24",   # DVD WiFi 네트워크
            "172.20.0.0/16",     # Docker 네트워크
            "127.0.0.0/8"        # Localhost
        ]
        
        self.dvd_indicators = [
            # DVD 환경 식별 지표들
            {"type": "hostname", "patterns": ["dvd", "drone", "ardupilot", "mavlink"]},
            {"type": "service", "ports": [14550, 14551, 5760]},
            {"type": "network", "ranges": ["10.13.0.0/24", "192.168.13.0/24"]}
        ]
        
        self.forbidden_networks = [
            # 절대 공격하면 안되는 네트워크들
            "192.168.1.0/24",   # 일반 가정용 네트워크
            "192.168.0.0/24",   # 일반 가정용 네트워크
            "10.0.0.0/24",      # 일반 기업 네트워크
            "172.16.0.0/12"     # 일반 사설 네트워크 (Docker 제외)
        ]
    
    async def check_target_safety(self, target) -> Dict[str, Any]:
        """타겟 안전성 종합 검사"""
        logger.info(f"🛡️  안전성 검사 시작: {target.host}")
        
        safety_result = {
            "safe": False,
            "confidence": 0.0,
            "reason": "",
            "checks": {},
            "warnings": [],
            "recommendations": []
        }
        
        try:
            # 1. 네트워크 범위 검사
            network_check = await self._check_network_safety(target)
            safety_result["checks"]["network"] = network_check
            
            # 2. DVD 환경 식별
            dvd_check = await self._check_dvd_environment(target)
            safety_result["checks"]["dvd_environment"] = dvd_check
            
            # 3. 서비스 검사
            service_check = await self._check_service_safety(target)
            safety_result["checks"]["services"] = service_check
            
            # 4. 사용자 확인 (대화형 모드)
            user_check = await self._check_user_authorization(target)
            safety_result["checks"]["user_authorization"] = user_check
            
            # 5. 종합 평가
            overall_assessment = self._assess_overall_safety(safety_result["checks"])
            safety_result.update(overall_assessment)
            
            logger.info(f"🛡️  안전성 검사 완료: {'안전' if safety_result['safe'] else '위험'}")
            
        except Exception as e:
            logger.error(f"❌ 안전성 검사 실패: {str(e)}")
            safety_result["reason"] = f"안전성 검사 오류: {str(e)}"
        
        return safety_result
    
    async def _check_network_safety(self, target) -> Dict[str, Any]:
        """네트워크 안전성 검사"""
        check_result = {
            "safe": False,
            "score": 0.0,
            "details": {},
            "warnings": []
        }
        
        try:
            target_ip = ipaddress.ip_address(target.host)
            
            # 안전한 네트워크 범위 확인
            in_safe_network = False
            for safe_network in self.safe_networks:
                if target_ip in ipaddress.ip_network(safe_network):
                    in_safe_network = True
                    check_result["details"]["safe_network"] = safe_network
                    check_result["score"] += 0.4
                    break
            
            # 금지된 네트워크 확인
            in_forbidden_network = False
            for forbidden_network in self.forbidden_networks:
                if target_ip in ipaddress.ip_network(forbidden_network):
                    in_forbidden_network = True
                    check_result["warnings"].append(f"금지된 네트워크 범위: {forbidden_network}")
                    check_result["score"] -= 0.5
                    break
            
            # 로컬 네트워크 확인
            if target_ip.is_private:
                check_result["score"] += 0.2
                check_result["details"]["is_private"] = True
            else:
                check_result["warnings"].append("공인 IP 주소는 위험할 수 있습니다")
            
            # 안전성 결정
            if in_safe_network and not in_forbidden_network:
                check_result["safe"] = True
            elif not in_forbidden_network and target_ip.is_private:
                check_result["safe"] = True
                check_result["warnings"].append("표준 DVD 네트워크가 아닙니다")
            
        except ValueError:
            # 호스트명인 경우
            if target.host.lower() in ["localhost", "127.0.0.1"]:
                check_result["safe"] = True
                check_result["score"] = 1.0
                check_result["details"]["localhost"] = True
            else:
                check_result["warnings"].append("호스트명 해석이 필요합니다")
        
        return check_result
    
    async def _check_dvd_environment(self, target) -> Dict[str, Any]:
        """DVD 환경 식별 검사"""
        check_result = {
            "is_dvd": False,
            "confidence": 0.0,
            "indicators": [],
            "details": {}
        }
        
        try:
            # MAVLink 포트 확인
            mavlink_ports = [14550, 14551, 5760]
            open_mavlink_ports = []
            
            for port in mavlink_ports:
                if await self._check_port_open(target.host, port):
                    open_mavlink_ports.append(port)
                    check_result["confidence"] += 0.3
            
            if open_mavlink_ports:
                check_result["indicators"].append(f"MAVLink 포트 열림: {open_mavlink_ports}")
                check_result["details"]["mavlink_ports"] = open_mavlink_ports
            
            # 호스트명 확인
            hostname_indicators = ["dvd", "drone", "ardupilot", "sitl"]
            for indicator in hostname_indicators:
                if indicator in target.host.lower():
                    check_result["indicators"].append(f"호스트명에 '{indicator}' 포함")
                    check_result["confidence"] += 0.2
            
            # DVD 식별 임계값
            if check_result["confidence"] >= 0.5:
                check_result["is_dvd"] = True
            
        except Exception as e:
            logger.debug(f"DVD 환경 확인 오류: {str(e)}")
        
        return check_result
    
    async def _check_port_open(self, host: str, port: int, timeout: float = 3.0) -> bool:
        """포트 개방 확인"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        except:
            return False
    
    async def _check_service_safety(self, target) -> Dict[str, Any]:
        """서비스 안전성 검사"""
        check_result = {
            "safe_services": [],
            "risky_services": [],
            "unknown_services": [],
            "score": 0.0
        }
        
        # DVD 표준 서비스 포트들
        dvd_services = {
            14550: {"name": "mavlink_fc", "risk": "medium"},
            14551: {"name": "mavlink_gcs", "risk": "medium"},
            5760: {"name": "mavlink_sitl", "risk": "low"},
            80: {"name": "http", "risk": "medium"},
            8554: {"name": "rtsp", "risk": "low"},
            21: {"name": "ftp", "risk": "high"},
            22: {"name": "ssh", "risk": "medium"},
            23: {"name": "telnet", "risk": "high"}
        }
        
        try:
            for port, service_info in dvd_services.items():
                if await self._check_port_open(target.host, port):
                    service_name = service_info["name"]
                    risk_level = service_info["risk"]
                    
                    if risk_level == "low":
                        check_result["safe_services"].append({
                            "port": port, "service": service_name, "risk": risk_level
                        })
                        check_result["score"] += 0.1
                    elif risk_level == "medium":
                        check_result["unknown_services"].append({
                            "port": port, "service": service_name, "risk": risk_level
                        })
                    else:  # high risk
                        check_result["risky_services"].append({
                            "port": port, "service": service_name, "risk": risk_level
                        })
                        check_result["score"] -= 0.2
        
        except Exception as e:
            logger.debug(f"서비스 검사 오류: {str(e)}")
        
        return check_result
    
    async def _check_user_authorization(self, target) -> Dict[str, Any]:
        """사용자 승인 확인"""
        check_result = {
            "authorized": False,
            "method": "automatic",
            "details": {}
        }
        
        # 자동 승인 조건들
        auto_approve_conditions = [
            target.host in ["localhost", "127.0.0.1"],
            target.host.startswith("10.13.0."),
            "dvd" in target.host.lower(),
            "simulation" in target.host.lower()
        ]
        
        if any(auto_approve_conditions):
            check_result["authorized"] = True
            check_result["method"] = "automatic"
            check_result["details"]["reason"] = "안전한 대상으로 자동 승인"
        else:
            # 대화형 승인 (실제 구현에서는 사용자 입력 받기)
            check_result["authorized"] = True  # 기본적으로 승인 (데모용)
            check_result["method"] = "manual_override"
            check_result["details"]["warning"] = "표준 DVD 환경이 아닐 수 있습니다"
        
        return check_result
    
    def _assess_overall_safety(self, checks: Dict[str, Any]) -> Dict[str, Any]:
        """종합 안전성 평가"""
        assessment = {
            "safe": False,
            "confidence": 0.0,
            "reason": "",
            "warnings": [],
            "recommendations": []
        }
        
        # 각 검사 결과 가중치 적용
        weights = {
            "network": 0.4,
            "dvd_environment": 0.3,
            "services": 0.2,
            "user_authorization": 0.1
        }
        
        total_score = 0.0
        
        # 네트워크 안전성
        if checks.get("network", {}).get("safe", False):
            total_score += weights["network"]
        else:
            assessment["warnings"].extend(checks.get("network", {}).get("warnings", []))
        
        # DVD 환경 식별
        if checks.get("dvd_environment", {}).get("is_dvd", False):
            total_score += weights["dvd_environment"]
        else:
            assessment["warnings"].append("DVD 환경으로 확인되지 않음")
        
        # 서비스 안전성
        service_score = checks.get("services", {}).get("score", 0.0)
        if service_score >= 0:
            total_score += weights["services"] * min(service_score, 1.0)
        
        # 사용자 승인
        if checks.get("user_authorization", {}).get("authorized", False):
            total_score += weights["user_authorization"]
        
        # 최종 판정
        assessment["confidence"] = total_score
        
        if total_score >= 0.7:
            assessment["safe"] = True
            assessment["reason"] = "안전성 검사 통과"
        elif total_score >= 0.5:
            assessment["safe"] = True
            assessment["reason"] = "조건부 안전 (주의 필요)"
            assessment["warnings"].append("일부 안전성 검사에서 경고 발생")
        else:
            assessment["safe"] = False
            assessment["reason"] = "안전성 검사 실패"
        
        # 권장사항 생성
        assessment["recommendations"] = self._generate_safety_recommendations(checks, total_score)
        
        return assessment
    
    def _generate_safety_recommendations(self, checks: Dict, score: float) -> List[str]:
        """안전성 권장사항 생성"""
        recommendations = []
        
        if score < 0.7:
            recommendations.append("대상 환경의 안전성을 재확인하세요")
        
        # 네트워크 관련 권장사항
        network_check = checks.get("network", {})
        if not network_check.get("safe", False):
            recommendations.append("표준 DVD 네트워크 범위 사용을 권장합니다")
        
        # DVD 환경 관련 권장사항
        dvd_check = checks.get("dvd_environment", {})
        if not dvd_check.get("is_dvd", False):
            recommendations.append("DVD 환경 여부를 재확인하세요")
        
        # 서비스 관련 권장사항
        service_check = checks.get("services", {})
        if service_check.get("risky_services"):
            recommendations.append("위험한 서비스들을 비활성화하세요")
        
        # 일반 권장사항
        recommendations.extend([
            "공격 전 네트워크 소유자의 명시적 승인을 받으세요",
            "공격 로그를 기록하고 모니터링하세요",
            "파괴적 공격은 피하세요"
        ])
        
        return recommendations
    
    def is_safe_attack(self, attack_name: str, target_mode: str) -> bool:
        """공격의 안전성 확인"""
        # 공격별 안전성 분류
        safe_attacks = {
            "wifi_scan": True,
            "drone_discovery": True,
            "packet_sniff": True,
            "param_extract": True
        }
        
        risky_attacks = {
            "command_inject": False,
            "waypoint_inject": False,
            "telemetry_spoof": False,
            "firmware_mod": False
        }
        
        # 시뮬레이션 모드에서는 모든 공격 허용
        if target_mode == "simulation":
            return True
        
        # 안전한 공격만 허용
        return safe_attacks.get(attack_name, False)