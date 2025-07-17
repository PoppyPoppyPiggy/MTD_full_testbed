# =============================================================================
# 4. INJECTION 공격들
# =============================================================================

# dvd_attacks/injection/flight_plan.py
"""
비행 계획 주입 공격
"""
import asyncio
import random
from typing import Tuple, List, Dict, Any
from datetime import datetime
from ..core.attack_base import BaseAttack, AttackType

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