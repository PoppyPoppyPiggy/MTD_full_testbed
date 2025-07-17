# dvd_attacks/injection/parameter_manipulation.py
"""
파라미터 조작 공격
"""
import asyncio
import random
from typing import Tuple, List, Dict, Any
from datetime import datetime
from ..core.attack_base import BaseAttack, AttackType

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
