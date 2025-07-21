# dvd_lite/dvd_attacks/injection/mavlink_injection.py
"""
MAVLink 메시지 주입 공격 (Damn Vulnerable Drone 기반)
"""

import asyncio
import random
import struct
import time
from typing import Tuple, List, Dict, Any

from ..core.attack_base import BaseAttack, AttackType

class MAVLinkMessageInjection(BaseAttack):
    """MAVLink 메시지 주입 공격"""
    
    def _get_attack_type(self) -> AttackType:
        return AttackType.INJECTION
    
    async def _run_attack(self) -> Tuple[bool, List[str], Dict[str, Any]]:
        """악성 MAVLink 메시지 주입으로 드론 제어 시도"""
        await asyncio.sleep(3.5)
        
        # DVD 환경의 타겟 시스템 정보
        target_systems = [
            {
                "host": "192.168.13.2",
                "port": 14550,
                "system_id": 1,
                "component_id": 1,
                "autopilot": "ArduPilot",
                "vehicle_type": "Quadrotor",
                "description": "Primary Flight Controller"
            },
            {
                "host": "192.168.13.3", 
                "port": 14552,
                "system_id": 2,
                "component_id": 191,
                "autopilot": "Generic",
                "vehicle_type": "GCS",
                "description": "Companion Computer MAVLink Router"
            }
        ]
        
        # 주입할 MAVLink 메시지들 (위험도별 분류)
        injection_payloads = [
            # Critical Severity
            {
                "msg_id": 76,  # COMMAND_LONG
                "msg_name": "COMMAND_LONG",
                "command": "MAV_CMD_COMPONENT_ARM_DISARM",
                "type": "arm_disarm_manipulation",
                "severity": "critical",
                "description": "Force arm/disarm drone motors",
                "params": {"param1": 0},  # 0 = disarm, 1 = arm
                "flight_state_required": ["STANDBY", "ARMED"],
                "success_indicators": ["motor_stop", "safety_disable"]
            },
            {
                "msg_id": 76,
                "msg_name": "COMMAND_LONG", 
                "command": "MAV_CMD_NAV_LAND",
                "type": "forced_landing",
                "severity": "critical",
                "description": "Force immediate emergency landing",
                "params": {"param4": float('nan')},  # Use current position
                "flight_state_required": ["FLYING"],
                "success_indicators": ["mode_change_land", "altitude_descent"]
            },
            {
                "msg_id": 76,
                "msg_name": "COMMAND_LONG",
                "command": "MAV_CMD_DO_FLIGHTTERMINATION", 
                "type": "flight_termination",
                "severity": "critical",
                "description": "Trigger flight termination system",
                "params": {"param1": 1},  # Enable termination
                "flight_state_required": ["FLYING"],
                "success_indicators": ["motors_stop", "parachute_deploy"]
            },
            
            # High Severity
            {
                "msg_id": 11,  # SET_POSITION_TARGET_LOCAL_NED
                "msg_name": "SET_POSITION_TARGET_LOCAL_NED",
                "type": "position_manipulation",
                "severity": "high", 
                "description": "Inject malicious position targets",
                "params": {
                    "x": 1000.0,  # 1km offset
                    "y": 1000.0,
                    "z": -100.0   # Force dangerous altitude
                },
                "flight_state_required": ["GUIDED", "AUTO"],
                "success_indicators": ["position_change", "waypoint_deviation"]
            },
            {
                "msg_id": 84,  # SET_POSITION_TARGET_GLOBAL_INT
                "msg_name": "SET_POSITION_TARGET_GLOBAL_INT",
                "type": "global_position_spoof",
                "severity": "high",
                "description": "Spoof global position coordinates",
                "params": {
                    "lat_int": 374419000,  # SFO Airport (dangerous location)
                    "lon_int": -1221430000,
                    "alt": 4.0
                },
                "flight_state_required": ["GUIDED", "AUTO"],
                "success_indicators": ["gps_coordinate_change", "navigation_redirect"]
            },
            {
                "msg_id": 76,
                "msg_name": "COMMAND_LONG",
                "command": "MAV_CMD_DO_SET_MODE",
                "type": "flight_mode_change",
                "severity": "high",
                "description": "Force dangerous flight mode changes",
                "params": {
                    "param1": 4,  # GUIDED mode
                    "param2": 0
                },
                "flight_state_required": ["STABILIZE", "ALT_HOLD"],
                "success_indicators": ["mode_change", "control_authority_gained"]
            },
            
            # Medium Severity
            {
                "msg_id": 39,  # MISSION_ITEM
                "msg_name": "MISSION_ITEM",
                "type": "waypoint_injection",
                "severity": "medium",
                "description": "Inject malicious waypoints into mission",
                "params": {
                    "seq": 0,
                    "frame": 3,  # MAV_FRAME_GLOBAL_RELATIVE_ALT
                    "command": 16,  # MAV_CMD_NAV_WAYPOINT
                    "x": 37.7749,  # Dangerous location
                    "y": -122.4194,
                    "z": 500.0  # Dangerous altitude
                },
                "flight_state_required": ["PRE_FLIGHT", "AUTO"],
                "success_indicators": ["mission_modified", "waypoint_added"]
            },
            {
                "msg_id": 23,  # PARAM_SET
                "msg_name": "PARAM_SET", 
                "type": "parameter_manipulation",
                "severity": "medium",
                "description": "Modify critical system parameters",
                "params": {
                    "param_id": "FENCE_ENABLE",
                    "param_value": 0.0,  # Disable geofence
                    "param_type": 2  # UINT8
                },
                "flight_state_required": ["ANY"],
                "success_indicators": ["parameter_changed", "safety_disabled"]
            },
            {
                "msg_id": 76,
                "msg_name": "COMMAND_LONG",
                "command": "MAV_CMD_DO_SET_SERVO",
                "type": "servo_manipulation",
                "severity": "medium", 
                "description": "Manipulate servo/gimbal controls",
                "params": {
                    "param1": 9,    # Servo number
                    "param2": 2000  # PWM value (max)
                },
                "flight_state_required": ["ANY"],
                "success_indicators": ["servo_movement", "gimbal_control"]
            },
            
            # Low Severity (Reconnaissance/Testing)
            {
                "msg_id": 21,  # PARAM_REQUEST_LIST
                "msg_name": "PARAM_REQUEST_LIST",
                "type": "parameter_enumeration",
                "severity": "low",
                "description": "Request all system parameters",
                "params": {},
                "flight_state_required": ["ANY"],
                "success_indicators": ["param_list_received", "system_info_leaked"]
            },
            {
                "msg_id": 43,  # MISSION_REQUEST_LIST
                "msg_name": "MISSION_REQUEST_LIST", 
                "type": "mission_enumeration",
                "severity": "low",
                "description": "Request current mission waypoints",
                "params": {},
                "flight_state_required": ["ANY"], 
                "success_indicators": ["mission_data_received", "flight_plan_leaked"]
            }
        ]
        
        # 공격 실행 시뮬레이션
        injection_attempts = []
        successful_injections = []
        
        # 타겟 시스템 선택
        primary_target = target_systems[0]  # Flight Controller
        
        # 현재 비행 상태 시뮬레이션
        current_flight_state = random.choice([
            "PRE_FLIGHT", "STANDBY", "ARMED", "FLYING", "GUIDED", "AUTO"
        ])
        
        # 각 페이로드에 대해 주입 시도
        for payload in injection_payloads:
            # 비행 상태 확인
            state_compatible = (
                "ANY" in payload["flight_state_required"] or
                current_flight_state in payload["flight_state_required"]
            )
            
            injection_attempt = {
                **payload,
                "target_host": primary_target["host"],
                "target_port": primary_target["port"],
                "target_system_id": primary_target["system_id"],
                "target_component_id": primary_target["component_id"],
                "current_flight_state": current_flight_state,
                "state_compatible": state_compatible,
                "attempted": True,
                "timestamp": time.time()
            }
            
            # 성공률 계산
            base_success_rate = self._calculate_success_rate(payload, state_compatible)
            injection_attempt["calculated_success_rate"] = base_success_rate
            
            # 주입 시도
            if random.random() < base_success_rate:
                injection_attempt["success"] = True
                injection_attempt["response_time"] = random.uniform(0.1, 0.5)
                injection_attempt["mavlink_ack"] = self._generate_mavlink_ack(payload)
                
                # 시스템 영향 시뮬레이션
                injection_attempt["system_impact"] = self._simulate_system_impact(payload)
                successful_injections.append(injection_attempt)
            else:
                injection_attempt["success"] = False
                injection_attempt["failure_reason"] = random.choice([
                    "invalid_checksum", "message_rejected", "permission_denied",
                    "invalid_state", "parameter_validation_failed"
                ])
            
            injection_attempts.append(injection_attempt)
            
            # 주입 간 지연
            await asyncio.sleep(random.uniform(0.1, 0.3))
        
        # 연쇄 공격 시뮬레이션 (성공한 주입이 있는 경우)
        chain_attacks = []
        if successful_injections:
            chain_attacks = self._simulate_chain_attacks(successful_injections, current_flight_state)
        
        # IOC 생성
        iocs = []
        for injection in injection_attempts:
            iocs.append(f"MAVLINK_INJECT_ATTEMPT:{injection['type']}")
            iocs.append(f"MAVLINK_MSG_ID:{injection['msg_id']}")
            iocs.append(f"MAVLINK_TARGET:{injection['target_host']}")
            
            if injection["success"]:
                iocs.append(f"MAVLINK_INJECT_SUCCESS:{injection['type']}")
                iocs.append(f"MAVLINK_SEVERITY:{injection['severity']}")
                
                if injection["severity"] == "critical":
                    iocs.append(f"CRITICAL_MAVLINK_INJECTION:{injection['type']}")
                
                # 특정 명령어 IOC
                if "arm_disarm" in injection["type"]:
                    iocs.append("MAVLINK_MOTOR_CONTROL_HIJACKED")
                elif "landing" in injection["type"]:
                    iocs.append("MAVLINK_FORCED_LANDING")
                elif "termination" in injection["type"]:
                    iocs.append("MAVLINK_FLIGHT_TERMINATION")
                elif "position" in injection["type"]:
                    iocs.append("MAVLINK_POSITION_SPOOFED")
                elif "mode" in injection["type"]:
                    iocs.append("MAVLINK_FLIGHT_MODE_HIJACKED")
        
        # 연쇄 공격 IOC
        for chain in chain_attacks:
            iocs.append(f"MAVLINK_CHAIN_ATTACK:{chain['attack_type']}")
        
        success = len(successful_injections) > 0
        
        # 위험도 평가
        risk_assessment = self._assess_attack_risk(successful_injections, current_flight_state)
        
        # 대응 권장사항
        countermeasures = self._generate_countermeasures(injection_attempts, successful_injections)
        
        details = {
            "target_systems": target_systems,
            "current_flight_state": current_flight_state,
            "injection_attempts": injection_attempts,
            "successful_injections": successful_injections,
            "chain_attacks": chain_attacks,
            "risk_assessment": risk_assessment,
            "countermeasures": countermeasures,
            "attack_timeline": self._generate_attack_timeline(injection_attempts),
            "success_rate": len(successful_injections) / len(injection_attempts) if injection_attempts else 0,
            "dvd_environment": True
        }
        
        return success, iocs, details
    
    def _calculate_success_rate(self, payload: Dict[str, Any], state_compatible: bool) -> float:
        """주입 성공률 계산"""
        base_rates = {
            "critical": 0.4,  # 중요한 명령어는 보호될 가능성 높음
            "high": 0.6,
            "medium": 0.7,
            "low": 0.9       # 정보 수집은 쉬움
        }
        
        base_rate = base_rates.get(payload["severity"], 0.5)
        
        # 비행 상태 호환성
        if not state_compatible:
            base_rate *= 0.2  # 비호환 상태에서는 성공률 대폭 감소
        
        # DVD 환경 보너스 (실험 환경이므로 보안이 약함)
        base_rate *= 1.2
        
        # 메시지별 조정
        if payload["msg_name"] in ["PARAM_REQUEST_LIST", "MISSION_REQUEST_LIST"]:
            base_rate *= 1.3  # 정보 수집은 더 쉬움
        elif "TERMINATION" in payload.get("command", ""):
            base_rate *= 0.7  # 비상 종료는 더 보호됨
        
        return min(1.0, base_rate)
    
    def _generate_mavlink_ack(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """MAVLink ACK 메시지 시뮬레이션"""
        return {
            "command": payload.get("command", payload["msg_name"]),
            "result": "MAV_RESULT_ACCEPTED" if random.random() > 0.1 else "MAV_RESULT_TEMPORARILY_REJECTED",
            "progress": random.randint(0, 100),
            "result_param2": 0,
            "target_system": 1,
            "target_component": 1
        }
    
    def _simulate_system_impact(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """시스템 영향 시뮬레이션"""
        impact = {
            "immediate_effects": [],
            "delayed_effects": [],
            "safety_impact": "none",
            "operational_impact": "none"
        }
        
        if payload["severity"] == "critical":
            impact["immediate_effects"] = payload.get("success_indicators", [])
            impact["safety_impact"] = "severe"
            impact["operational_impact"] = "mission_abort"
            
            if "arm_disarm" in payload["type"]:
                impact["delayed_effects"] = ["potential_crash", "loss_of_control"]
            elif "termination" in payload["type"]:
                impact["delayed_effects"] = ["forced_landing", "mission_termination"]
                
        elif payload["severity"] == "high":
            impact["immediate_effects"] = payload.get("success_indicators", [])
            impact["safety_impact"] = "moderate"
            impact["operational_impact"] = "mission_deviation"
            
        elif payload["severity"] == "medium":
            impact["immediate_effects"] = payload.get("success_indicators", [])
            impact["safety_impact"] = "low"
            impact["operational_impact"] = "minor_disruption"
            
        else:  # low severity
            impact["immediate_effects"] = payload.get("success_indicators", [])
            impact["safety_impact"] = "none"
            impact["operational_impact"] = "information_disclosure"
        
        return impact
    
    def _simulate_chain_attacks(self, successful_injections: List[Dict], flight_state: str) -> List[Dict]:
        """연쇄 공격 시뮬레이션"""
        chain_attacks = []
        
        # 정보 수집 후 공격 에스컬레이션
        info_gathering = [inj for inj in successful_injections if inj["severity"] == "low"]
        if info_gathering and random.random() > 0.5:
            chain_attacks.append({
                "attack_type": "parameter_exploitation",
                "description": "Use gathered parameters for targeted attacks",
                "based_on": [inj["type"] for inj in info_gathering],
                "success_probability": 0.7
            })
        
        # 모드 변경 후 위치 조작
        mode_changes = [inj for inj in successful_injections if "mode" in inj["type"]]
        if mode_changes and random.random() > 0.4:
            chain_attacks.append({
                "attack_type": "guided_mode_exploitation", 
                "description": "Exploit GUIDED mode for position manipulation",
                "based_on": [inj["type"] for inj in mode_changes],
                "success_probability": 0.8
            })
        
        # 복합 공격 (여러 성공한 주입이 있는 경우)
        if len(successful_injections) >= 3:
            chain_attacks.append({
                "attack_type": "coordinated_control_takeover",
                "description": "Complete flight control takeover using multiple vectors", 
                "based_on": [inj["type"] for inj in successful_injections],
                "success_probability": 0.9
            })
        
        return chain_attacks
    
    def _assess_attack_risk(self, successful_injections: List[Dict], flight_state: str) -> Dict[str, Any]:
        """공격 위험도 평가"""
        risk_levels = {
            "critical": 10,
            "high": 7,
            "medium": 4,
            "low": 1
        }
        
        total_risk_score = sum(risk_levels.get(inj["severity"], 0) for inj in successful_injections)
        
        if total_risk_score >= 15:
            overall_risk = "critical"
        elif total_risk_score >= 10:
            overall_risk = "high"
        elif total_risk_score >= 5:
            overall_risk = "medium"
        else:
            overall_risk = "low"
        
        return {
            "overall_risk_level": overall_risk,
            "total_risk_score": total_risk_score,
            "flight_state_impact": flight_state,
            "potential_consequences": self._get_risk_consequences(overall_risk, flight_state),
            "attack_sophistication": "high" if len(successful_injections) >= 3 else "medium"
        }
    
    def _get_risk_consequences(self, risk_level: str, flight_state: str) -> List[str]:
        """위험도별 잠재적 결과"""
        consequences = {
            "critical": [
                "Complete loss of vehicle control",
                "Potential crash or destruction", 
                "Safety system bypass",
                "Mission termination"
            ],
            "high": [
                "Partial control compromise",
                "Mission deviation or failure",
                "Safety system degradation",
                "Unauthorized vehicle behavior"
            ],
            "medium": [
                "Minor mission disruption",
                "Parameter manipulation",
                "Information disclosure"
            ],
            "low": [
                "System reconnaissance",
                "Information gathering"
            ]
        }
        
        base_consequences = consequences.get(risk_level, [])
        
        # 비행 상태별 추가 위험
        if flight_state == "FLYING":
            base_consequences.append("In-flight emergency situation")
        elif flight_state == "ARMED":
            base_consequences.append("Pre-flight safety compromise")
        
        return base_consequences
    
    def _generate_countermeasures(self, attempts: List[Dict], successful: List[Dict]) -> Dict[str, Any]:
        """대응 방안 생성"""
        return {
            "immediate_actions": [
                "Disconnect from compromised network",
                "Switch to manual flight mode",
                "Activate emergency protocols",
                "Land safely if in flight"
            ],
            "technical_mitigations": [
                "Enable MAVLink message authentication",
                "Implement command rate limiting",
                "Deploy network segmentation",
                "Add anomaly detection systems"
            ],
            "long_term_solutions": [
                "Upgrade to MAVLink 2.0 with signing",
                "Implement zero-trust architecture",
                "Add behavioral analysis systems",
                "Deploy AI-based threat detection"
            ],
            "detection_indicators": [
                "Unexpected flight mode changes",
                "Unauthorized parameter modifications",
                "Anomalous MAVLink traffic patterns",
                "System behavior inconsistencies"
            ]
        }
    
    def _generate_attack_timeline(self, attempts: List[Dict]) -> List[Dict]:
        """공격 타임라인 생성"""
        timeline = []
        base_time = time.time()
        
        for i, attempt in enumerate(attempts):
            timeline.append({
                "timestamp": base_time + i * 0.5,
                "event_type": "injection_attempt",
                "message_type": attempt["msg_name"],
                "severity": attempt["severity"],
                "success": attempt["success"],
                "target": f"{attempt['target_host']}:{attempt['target_port']}"
            })
        
        return timeline