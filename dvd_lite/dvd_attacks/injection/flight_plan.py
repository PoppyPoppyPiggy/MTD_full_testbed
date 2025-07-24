# dvd_attacks/injection/flight_plan.py
"""
비행 계획 주입 공격 - Damn Vulnerable Drone 기반 업데이트
"""
import asyncio
import random
from typing import Tuple, List, Dict, Any
from datetime import datetime
from ..core.attack_base import BaseAttack, AttackType

class FlightPlanInjection(BaseAttack):
    """비행 계획 주입 공격 - MAVLink Mission Protocol 타겟"""
    
    def _get_attack_type(self) -> AttackType:
        return AttackType.INJECTION
    
    async def _run_attack(self) -> Tuple[bool, List[str], Dict[str, Any]]:
        """악성 웨이포인트로 비행 계획 변조"""
        await asyncio.sleep(3.7)
        
        # 원본 미션 정보 (실제 ArduPilot 미션 구조)
        original_mission = {
            "mission_type": random.choice(["survey", "delivery", "inspection", "patrol"]),
            "waypoint_count": random.randint(5, 20),
            "total_distance": random.uniform(500, 5000),  # meters
            "estimated_flight_time": random.uniform(300, 3600),  # seconds
            "max_altitude": random.randint(30, 150),  # meters
            "area_type": "safe_zone",
            "geofence_enabled": random.choice([True, False]),
            "rtl_altitude": random.randint(15, 50),  # meters
            "home_location": {
                "lat": 37.7749295 + random.uniform(-0.01, 0.01),
                "lon": -122.4194155 + random.uniform(-0.01, 0.01),
                "alt": 10
            }
        }
        
        # 악성 웨이포인트들 (실제 위험 지역 및 공격 시나리오)
        malicious_waypoints = [
            {
                "seq": 1,
                "type": "MAV_CMD_NAV_WAYPOINT",
                "lat": 38.8977,  # Washington DC (No-fly zone)
                "lon": -77.0365,
                "alt": 150,
                "param1": 5,  # Hold time
                "risk": "critical",
                "description": "Redirect to restricted airspace (Washington DC)",
                "violation_type": "restricted_airspace"
            },
            {
                "seq": 2, 
                "type": "MAV_CMD_NAV_LAND",
                "lat": 40.6892,  # JFK Airport
                "lon": -74.1745,
                "alt": 0,
                "param1": 0,
                "risk": "critical",
                "description": "Force landing at major airport",
                "violation_type": "airport_interference"
            },
            {
                "seq": 3,
                "type": "MAV_CMD_NAV_WAYPOINT", 
                "lat": original_mission["home_location"]["lat"],
                "lon": original_mission["home_location"]["lon"],
                "alt": 500,  # Above legal limit
                "param1": 10,
                "risk": "high",
                "description": "Excessive altitude violation",
                "violation_type": "altitude_violation"
            },
            {
                "seq": 4,
                "type": "MAV_CMD_DO_SET_SERVO",
                "lat": 0,
                "lon": 0,
                "alt": 0,
                "param1": 9,   # Servo channel
                "param2": 1000,  # PWM value (payload drop)
                "risk": "medium",
                "description": "Unauthorized payload release",
                "violation_type": "payload_manipulation"
            },
            {
                "seq": 5,
                "type": "MAV_CMD_NAV_LOITER_UNLIM",
                "lat": 37.4419,  # Near tech companies
                "lon": -122.1430,
                "alt": 100,
                "param1": 50,  # Loiter radius
                "risk": "high",
                "description": "Unlimited loiter over sensitive area",
                "violation_type": "surveillance_mission"
            },
            {
                "seq": 6,
                "type": "MAV_CMD_CONDITION_DELAY",
                "lat": 0,
                "lon": 0, 
                "alt": 0,
                "param1": 86400,  # 24 hours delay
                "risk": "medium",
                "description": "Excessive delay causing mission timeout",
                "violation_type": "mission_disruption"
            }
        ]
        
        # 주입 방법들 (실제 MAVLink 프로토콜 기법)
        injection_methods = [
            {
                "method": "mavlink_mission_clear_all",
                "success_rate": 0.9,
                "detection_risk": "low",
                "description": "Clear existing mission and upload malicious waypoints",
                "mavlink_commands": ["MISSION_CLEAR_ALL", "MISSION_COUNT", "MISSION_ITEM_INT"],
                "stealth_level": "medium"
            },
            {
                "method": "mavlink_mission_item_replace",
                "success_rate": 0.8,
                "detection_risk": "medium", 
                "description": "Replace specific mission items with malicious ones",
                "mavlink_commands": ["MISSION_ITEM_INT", "MISSION_WRITE_PARTIAL_LIST"],
                "stealth_level": "high"
            },
            {
                "method": "gcs_interface_manipulation",
                "success_rate": 0.6,
                "detection_risk": "medium",
                "description": "Manipulate Ground Control Station mission planning",
                "mavlink_commands": ["MISSION_REQUEST", "MISSION_ACK"],
                "stealth_level": "medium"
            },
            {
                "method": "parameter_based_injection",
                "success_rate": 0.7,
                "detection_risk": "high",
                "description": "Modify mission through parameter manipulation",
                "mavlink_commands": ["PARAM_SET", "MISSION_SET_CURRENT"],
                "stealth_level": "low"
            },
            {
                "method": "companion_computer_hijack", 
                "success_rate": 0.5,
                "detection_risk": "low",
                "description": "Upload mission through compromised companion computer",
                "mavlink_commands": ["MISSION_COUNT", "MISSION_ITEM"],
                "stealth_level": "very_high"
            }
        ]
        
        # 주입 시도
        chosen_method = random.choice(injection_methods)
        injected_waypoints = []
        
        # 지오펜스 우회 시도
        geofence_bypass = False
        if original_mission["geofence_enabled"]:
            bypass_techniques = [
                {"technique": "geofence_disable", "success_rate": 0.6},
                {"technique": "altitude_jump", "success_rate": 0.4},
                {"technique": "rapid_waypoint_change", "success_rate": 0.7}
            ]
            bypass_tech = random.choice(bypass_techniques)
            geofence_bypass = random.random() < bypass_tech["success_rate"]
        
        # 웨이포인트 주입 시뮬레이션
        for waypoint in malicious_waypoints:
            injection_success_rate = chosen_method["success_rate"]
            
            # 리스크 수준에 따른 성공률 조정
            if waypoint["risk"] == "critical":
                injection_success_rate *= 0.8  # 더 어려움
            elif waypoint["risk"] == "high":
                injection_success_rate *= 0.9
            
            # 지오펜스 검사
            if original_mission["geofence_enabled"] and not geofence_bypass:
                if waypoint["violation_type"] in ["restricted_airspace", "altitude_violation"]:
                    injection_success_rate *= 0.3  # 지오펜스가 막을 가능성
            
            if random.random() < injection_success_rate:
                injection_result = {
                    **waypoint,
                    "injection_timestamp": datetime.now().isoformat(),
                    "injection_method": chosen_method["method"],
                    "mavlink_sequence": len(injected_waypoints) + 1,
                    "original_waypoint_replaced": random.choice([True, False])
                }
                injected_waypoints.append(injection_result)
        
        success = len(injected_waypoints) > 0
        
        if success:
            # 주입 성공 시 영향 분석
            mission_impact = {
                "safety_violations": len([wp for wp in injected_waypoints if wp["risk"] == "critical"]),
                "legal_violations": len([wp for wp in injected_waypoints if wp["violation_type"] in ["restricted_airspace", "airport_interference"]]),
                "mission_corruption_level": len(injected_waypoints) / len(malicious_waypoints),
                "estimated_detection_time": self._calculate_detection_time(injected_waypoints, chosen_method),
                "flight_safety_risk": max([self._risk_to_score(wp["risk"]) for wp in injected_waypoints]),
                "geofence_bypassed": geofence_bypass
            }
            
            # 실행 시나리오 예측
            execution_scenarios = []
            for wp in injected_waypoints:
                scenario = {
                    "waypoint_seq": wp["seq"],
                    "execution_probability": random.uniform(0.6, 0.95),
                    "expected_outcome": self._predict_outcome(wp),
                    "intervention_possible": random.choice([True, False]),
                    "damage_potential": wp["risk"]
                }
                execution_scenarios.append(scenario)
        else:
            mission_impact = {"impact": "none"}
            execution_scenarios = []
        
        # IOC 생성
        iocs = []
        if success:
            iocs.extend([
                f"MISSION_INJECTION:{chosen_method['method']}",
                f"MALICIOUS_WAYPOINTS_INJECTED:{len(injected_waypoints)}",
                "FLIGHT_PLAN_COMPROMISED"
            ])
            
            for wp in injected_waypoints:
                iocs.extend([
                    f"WAYPOINT_INJECT:{wp['type']}_{wp['violation_type']}",
                    f"MALICIOUS_COORDS:{wp['lat']:.6f},{wp['lon']:.6f},{wp['alt']}",
                    f"MAVLINK_COMMAND_INJECTED:{wp['type']}"
                ])
                
                if wp['risk'] == 'critical':
                    iocs.append(f"CRITICAL_WAYPOINT_INJECT:{wp['violation_type']}")
                
                if wp['violation_type'] == 'restricted_airspace':
                    iocs.append("RESTRICTED_AIRSPACE_VIOLATION")
                elif wp['violation_type'] == 'airport_interference':
                    iocs.append("AIRPORT_INTERFERENCE_RISK")
            
            if geofence_bypass:
                iocs.append("GEOFENCE_BYPASS_SUCCESSFUL")
            
            # MAVLink 프로토콜 IOCs
            for cmd in chosen_method["mavlink_commands"]:
                iocs.append(f"MAVLINK_COMMAND_USED:{cmd}")
        else:
            iocs.extend([
                f"MISSION_INJECTION_FAILED:{chosen_method['method']}",
                "FLIGHT_PLAN_INTEGRITY_MAINTAINED"
            ])
            
            if original_mission["geofence_enabled"]:
                iocs.append("GEOFENCE_PROTECTION_EFFECTIVE")
        
        details = {
            "original_mission": original_mission,
            "injection_method": chosen_method,
            "malicious_waypoints": malicious_waypoints,
            "successfully_injected": injected_waypoints,
            "mission_impact": mission_impact,
            "execution_scenarios": execution_scenarios,
            "geofence_bypass_attempted": original_mission["geofence_enabled"],
            "geofence_bypass_successful": geofence_bypass,
            "mavlink_protocol_abuse": {
                "commands_used": chosen_method["mavlink_commands"],
                "protocol_version": "MAVLink 2.0",
                "system_id_spoofed": random.choice([True, False]),
                "component_id_spoofed": random.choice([True, False])
            },
            "regulatory_impact": {
                "faa_violations": len([wp for wp in injected_waypoints if wp["violation_type"] in ["restricted_airspace", "altitude_violation"]]),
                "privacy_violations": len([wp for wp in injected_waypoints if wp["violation_type"] == "surveillance_mission"]),
                "safety_violations": len([wp for wp in injected_waypoints if wp["risk"] == "critical"])
            },
            "success_rate": chosen_method["success_rate"] if success else 0.0
        }
        
        return success, iocs, details
    
    def _risk_to_score(self, risk: str) -> int:
        """위험도를 숫자 점수로 변환"""
        risk_scores = {"low": 1, "medium": 2, "high": 3, "critical": 4}
        return risk_scores.get(risk, 0)
    
    def _calculate_detection_time(self, waypoints: List[Dict], method: Dict) -> str:
        """탐지 예상 시간 계산"""
        base_detection_time = {
            "mavlink_mission_clear_all": "immediate",
            "mavlink_mission_item_replace": "during_flight", 
            "gcs_interface_manipulation": "pre_flight",
            "parameter_based_injection": "during_preflight_check",
            "companion_computer_hijack": "post_incident_analysis"
        }
        
        detection_time = base_detection_time.get(method["method"], "unknown")
        
        # 고위험 웨이포인트가 많으면 더 빨리 탐지될 가능성
        critical_count = len([wp for wp in waypoints if wp["risk"] == "critical"])
        if critical_count > 2 and detection_time == "during_flight":
            detection_time = "early_flight"
        
        return detection_time
    
    def _predict_outcome(self, waypoint: Dict) -> str:
        """웨이포인트 실행 결과 예측"""
        outcomes = {
            "restricted_airspace": "airspace_violation_incident",
            "airport_interference": "emergency_landing_forced",
            "altitude_violation": "regulatory_investigation",
            "payload_manipulation": "unintended_payload_release",
            "surveillance_mission": "privacy_breach_incident",
            "mission_disruption": "mission_failure"
        }
        return outcomes.get(waypoint["violation_type"], "unknown_outcome")