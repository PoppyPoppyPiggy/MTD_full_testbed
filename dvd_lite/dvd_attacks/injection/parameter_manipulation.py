# dvd_attacks/injection/parameter_manipulation.py
"""
파라미터 조작 공격 - Damn Vulnerable Drone 기반 업데이트
"""
import asyncio
import random
from typing import Tuple, List, Dict, Any
from datetime import datetime
from ..core.attack_base import BaseAttack, AttackType

class ParameterManipulation(BaseAttack):
    """시스템 파라미터 조작 공격 - ArduPilot Parameter System 타겟"""
    
    def _get_attack_type(self) -> AttackType:
        return AttackType.INJECTION
    
    async def _run_attack(self) -> Tuple[bool, List[str], Dict[str, Any]]:
        """중요 시스템 파라미터 변조"""
        await asyncio.sleep(4.2)
        
        # 중요 ArduPilot 파라미터들 (실제 파라미터 이름 기반)
        critical_parameters = [
            {
                "name": "BATT_LOW_VOLT",
                "original": round(random.uniform(10.5, 11.2), 1),
                "malicious": round(random.uniform(5.0, 8.0), 1),
                "impact": "premature_low_battery_warning",
                "severity": "medium",
                "category": "power_management",
                "description": "Battery low voltage threshold"
            },
            {
                "name": "FENCE_ENABLE",
                "original": 1,
                "malicious": 0,
                "impact": "geofence_disabled",
                "severity": "high",
                "category": "safety",
                "description": "Enable/disable geofencing"
            },
            {
                "name": "RTL_ALT",
                "original": random.randint(15, 30),
                "malicious": random.randint(300, 500),
                "impact": "unsafe_return_altitude",
                "severity": "high", 
                "category": "navigation",
                "description": "Return to launch altitude"
            },
            {
                "name": "ARMING_CHECK",
                "original": 1,
                "malicious": 0,
                "impact": "safety_checks_disabled",
                "severity": "critical",
                "category": "safety",
                "description": "Pre-arm safety checks"
            },
            {
                "name": "FS_THR_ENABLE",
                "original": 1,
                "malicious": 0,
                "impact": "throttle_failsafe_disabled",
                "severity": "critical",
                "category": "failsafe",
                "description": "Throttle failsafe enable"
            },
            {
                "name": "FS_GCS_ENABLE",
                "original": 1,
                "malicious": 0,
                "impact": "gcs_failsafe_disabled",
                "severity": "critical",
                "category": "failsafe",
                "description": "Ground Control Station failsafe"
            },
            {
                "name": "COMPASS_CAL",
                "original": 1,
                "malicious": 0,
                "impact": "compass_calibration_bypassed",
                "severity": "medium",
                "category": "sensors",
                "description": "Compass calibration requirement"
            },
            {
                "name": "GPS_TYPE",
                "original": 1,
                "malicious": 0,
                "impact": "gps_disabled",
                "severity": "high",
                "category": "navigation",
                "description": "GPS receiver type"
            },
            {
                "name": "PILOT_TKOFF_ALT",
                "original": random.randint(5, 15),
                "malicious": random.randint(200, 400),
                "impact": "excessive_takeoff_altitude",
                "severity": "medium",
                "category": "flight_modes",
                "description": "Pilot takeoff altitude"
            },
            {
                "name": "WPNAV_SPEED",
                "original": random.randint(500, 1000),
                "malicious": random.randint(2000, 5000),
                "impact": "excessive_navigation_speed",
                "severity": "high",
                "category": "navigation",
                "description": "Waypoint navigation speed"
            },
            {
                "name": "ANGLE_MAX",
                "original": random.randint(2000, 4500),
                "malicious": random.randint(8000, 9000),
                "impact": "dangerous_angle_limits",
                "severity": "high",
                "category": "flight_control",
                "description": "Maximum lean angle"
            },
            {
                "name": "MOT_SPIN_ARM",
                "original": random.randint(70, 100),
                "malicious": random.randint(500, 1000),
                "impact": "motors_spin_when_armed",
                "severity": "critical",
                "category": "motors",
                "description": "Motor spin when armed"
            }
        ]
        
        # 파라미터 변조 방법들 (실제 MAVLink 프로토콜)
        manipulation_methods = [
            {
                "method": "mavlink_param_set",
                "success_rate": 0.9,
                "detection_risk": "medium",
                "description": "Set parameters via MAVLink PARAM_SET message",
                "mavlink_command": "PARAM_SET",
                "stealth_level": "medium",
                "persistence": "eeprom_persistent"
            },
            {
                "method": "config_file_modification",
                "success_rate": 0.8,
                "detection_risk": "low",
                "description": "Modify parameter configuration files",
                "mavlink_command": None,
                "stealth_level": "high",
                "persistence": "file_persistent"
            },
            {
                "method": "eeprom_direct_write",
                "success_rate": 0.4,
                "detection_risk": "very_low",
                "description": "Direct EEPROM manipulation via debug interface",
                "mavlink_command": None,
                "stealth_level": "very_high",
                "persistence": "hardware_persistent"
            },
            {
                "method": "gcs_parameter_upload",
                "success_rate": 0.7,
                "detection_risk": "high",
                "description": "Upload malicious parameter file via Ground Control Station",
                "mavlink_command": "PARAM_REQUEST_LIST",
                "stealth_level": "low",
                "persistence": "eeprom_persistent"
            },
            {
                "method": "companion_computer_injection",
                "success_rate": 0.6,
                "detection_risk": "medium",
                "description": "Inject parameters through compromised companion computer",
                "mavlink_command": "PARAM_SET",
                "stealth_level": "high",
                "persistence": "eeprom_persistent"
            }
        ]
        
        # 파라미터 보호 메커니즘 확인
        parameter_protection = {
            "param_file_checksum": random.choice([True, False]),
            "write_protection": random.choice([True, False]),
            "parameter_validation": random.choice([True, False]),
            "audit_logging": random.choice([True, False]),
            "backup_parameters": random.choice([True, False])
        }
        
        # 파라미터 변조 시도
        chosen_method = random.choice(manipulation_methods)
        modified_parameters = []
        
        for param in critical_parameters:
            # 보호 메커니즘에 따른 성공률 조정
            adjustment_factor = 1.0
            
            if parameter_protection["write_protection"] and param["severity"] == "critical":
                adjustment_factor *= 0.3
            
            if parameter_protection["parameter_validation"]:
                adjustment_factor *= 0.7
            
            if parameter_protection["param_file_checksum"] and chosen_method["method"] == "config_file_modification":
                adjustment_factor *= 0.2
            
            adjusted_success_rate = chosen_method["success_rate"] * adjustment_factor
            
            if random.random() < adjusted_success_rate:
                modification = {
                    **param,
                    "modification_time": datetime.now().isoformat(),
                    "modification_method": chosen_method["method"],
                    "mavlink_command_used": chosen_method["mavlink_command"],
                    "original_backed_up": parameter_protection["backup_parameters"],
                    "change_logged": parameter_protection["audit_logging"],
                    "validation_bypassed": not parameter_protection["parameter_validation"]
                }
                modified_parameters.append(modification)
        
        success = len(modified_parameters) > 0
        
        if success:
            # 시스템 안정성 영향 분석
            safety_impact = {
                "critical_safety_disabled": len([p for p in modified_parameters if p['category'] == 'safety' and p['severity'] == 'critical']),
                "failsafe_systems_disabled": len([p for p in modified_parameters if p['category'] == 'failsafe']),
                "navigation_compromised": len([p for p in modified_parameters if p['category'] == 'navigation']),
                "motor_control_affected": len([p for p in modified_parameters if p['category'] == 'motors']),
                "flight_envelope_exceeded": len([p for p in modified_parameters if p['impact'] in ['excessive_takeoff_altitude', 'unsafe_return_altitude', 'dangerous_angle_limits']])
            }
            
            # 비행 시나리오별 위험도 평가
            flight_risks = self._assess_flight_risks(modified_parameters)
            
            # 탐지 가능성 평가
            detection_likelihood = self._calculate_detection_likelihood(modified_parameters, chosen_method, parameter_protection)
            
            stability_impact = {
                "overall_safety_level": self._calculate_safety_level(safety_impact),
                "flight_risks": flight_risks,
                "operational_impact": self._assess_operational_impact(modified_parameters),
                "detection_likelihood": detection_likelihood,
                "recovery_difficulty": self._assess_recovery_difficulty(modified_parameters, parameter_protection)
            }
        else:
            safety_impact = {}
            stability_impact = {"impact": "none", "reason": "parameter_protection_effective"}
        
        # IOC 생성
        iocs = []
        if success:
            iocs.extend([
                f"PARAMETER_MANIPULATION:{chosen_method['method']}",
                f"PARAMETERS_MODIFIED:{len(modified_parameters)}",
                "FLIGHT_PARAMETERS_COMPROMISED"
            ])
            
            for param in modified_parameters:
                iocs.extend([
                    f"PARAM_MODIFIED:{param['name']}",
                    f"PARAM_VALUE_CHANGE:{param['name']}_{param['original']}_to_{param['malicious']}",
                    f"PARAM_CATEGORY_AFFECTED:{param['category']}"
                ])
                
                if param['severity'] == 'critical':
                    iocs.append(f"CRITICAL_PARAM_MODIFIED:{param['name']}")
                
                if param['category'] == 'safety':
                    iocs.append(f"SAFETY_PARAM_COMPROMISED:{param['name']}")
                elif param['category'] == 'failsafe':
                    iocs.append(f"FAILSAFE_DISABLED:{param['name']}")
                elif param['category'] == 'navigation':
                    iocs.append(f"NAVIGATION_PARAM_ALTERED:{param['name']}")
            
            # MAVLink 프로토콜 IOCs
            if chosen_method["mavlink_command"]:
                iocs.append(f"MAVLINK_COMMAND_ABUSE:{chosen_method['mavlink_command']}")
            
            # 보호 우회 IOCs
            if not parameter_protection["parameter_validation"]:
                iocs.append("PARAMETER_VALIDATION_BYPASSED")
            if not parameter_protection["audit_logging"]:
                iocs.append("PARAMETER_CHANGES_UNLOGGED")
            
            # 위험도별 IOCs
            if safety_impact.get("critical_safety_disabled", 0) > 0:
                iocs.append("CRITICAL_SAFETY_SYSTEMS_DISABLED")
            if safety_impact.get("failsafe_systems_disabled", 0) > 0:
                iocs.append("FAILSAFE_SYSTEMS_COMPROMISED")
        else:
            iocs.extend([
                f"PARAMETER_MANIPULATION_FAILED:{chosen_method['method']}",
                "PARAMETER_INTEGRITY_MAINTAINED"
            ])
            
            # 보호 메커니즘 효과성 IOCs
            if parameter_protection["write_protection"]:
                iocs.append("WRITE_PROTECTION_EFFECTIVE")
            if parameter_protection["parameter_validation"]:
                iocs.append("PARAMETER_VALIDATION_EFFECTIVE")
        
        details = {
            "target_parameters": critical_parameters,
            "parameter_protection": parameter_protection,
            "manipulation_method": chosen_method,
            "modified_parameters": modified_parameters,
            "safety_impact": safety_impact,
            "stability_impact": stability_impact,
            "modification_persistence": chosen_method["persistence"],
            "mavlink_protocol_abuse": {
                "command_used": chosen_method["mavlink_command"],
                "system_id_spoofed": random.choice([True, False]),
                "component_id_spoofed": random.choice([True, False])
            } if chosen_method["mavlink_command"] else None,
            "regulatory_violations": {
                "safety_standard_violations": len([p for p in modified_parameters if p['severity'] == 'critical']),
                "operational_limit_violations": len([p for p in modified_parameters if 'excessive' in p['impact']]),
                "airworthiness_impact": "significant" if len(modified_parameters) > 3 else "minor"
            },
            "success_rate": chosen_method["success_rate"] if success else 0.0
        }
        
        return success, iocs, details
    
    def _assess_flight_risks(self, modified_params: List[Dict]) -> Dict[str, str]:
        """수정된 파라미터에 따른 비행 위험도 평가"""
        risks = {
            "takeoff_risk": "low",
            "flight_risk": "low", 
            "landing_risk": "low",
            "emergency_response": "normal"
        }
        
        for param in modified_params:
            if param["name"] in ["ARMING_CHECK", "MOT_SPIN_ARM"]:
                risks["takeoff_risk"] = "critical"
            elif param["name"] in ["FENCE_ENABLE", "FS_THR_ENABLE", "FS_GCS_ENABLE"]:
                risks["emergency_response"] = "compromised"
            elif param["name"] in ["WPNAV_SPEED", "ANGLE_MAX"]:
                risks["flight_risk"] = "high"
            elif param["name"] in ["RTL_ALT", "GPS_TYPE"]:
                risks["landing_risk"] = "high"
        
        return risks
    
    def _calculate_safety_level(self, safety_impact: Dict) -> str:
        """전체 안전 수준 계산"""
        critical_issues = safety_impact.get("critical_safety_disabled", 0)
        failsafe_issues = safety_impact.get("failsafe_systems_disabled", 0)
        
        if critical_issues > 2 or failsafe_issues > 2:
            return "critically_compromised"
        elif critical_issues > 0 or failsafe_issues > 0:
            return "significantly_degraded"
        elif safety_impact.get("navigation_compromised", 0) > 0:
            return "moderately_degraded"
        else:
            return "minimally_affected"
    
    def _assess_operational_impact(self, modified_params: List[Dict]) -> Dict[str, Any]:
        """운영 영향 평가"""
        return {
            "flight_performance_degraded": any(p["category"] == "flight_control" for p in modified_params),
            "navigation_reliability": "compromised" if any(p["category"] == "navigation" for p in modified_params) else "normal",
            "sensor_functionality": "degraded" if any(p["category"] == "sensors" for p in modified_params) else "normal",
            "power_management": "affected" if any(p["name"].startswith("BATT_") for p in modified_params) else "normal",
            "mission_capability": "reduced" if len(modified_params) > 2 else "normal"
        }
    
    def _calculate_detection_likelihood(self, modified_params: List[Dict], method: Dict, protection: Dict) -> str:
        """탐지 가능성 계산"""
        base_detection = {
            "mavlink_param_set": "medium",
            "config_file_modification": "low",
            "eeprom_direct_write": "very_low",
            "gcs_parameter_upload": "high",
            "companion_computer_injection": "medium"
        }
        
        detection = base_detection[method["method"]]
        
        # 보호 메커니즘이 있으면 탐지 가능성 증가
        if protection["audit_logging"]:
            detection_levels = {"very_low": "low", "low": "medium", "medium": "high", "high": "very_high"}
            detection = detection_levels.get(detection, "very_high")
        
        # 크리티컬 파라미터 수정 시 탐지 가능성 증가
        critical_count = len([p for p in modified_params if p["severity"] == "critical"])
        if critical_count > 1 and detection in ["very_low", "low"]:
            detection = "medium"
        
        return detection
    
    def _assess_recovery_difficulty(self, modified_params: List[Dict], protection: Dict) -> str:
        """복구 난이도 평가"""
        if protection["backup_parameters"]:
            return "easy"
        elif len(modified_params) <= 2:
            return "moderate"
        elif any(p["category"] == "safety" and p["severity"] == "critical" for p in modified_params):
            return "difficult"
        else:
            return "moderate"