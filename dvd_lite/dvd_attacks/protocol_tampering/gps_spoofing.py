# dvd_lite/dvd_attacks/protocol_tampering/gps_spoofing.py
"""
GPS 신호 스푸핑 공격 (Damn Vulnerable Drone 기반)
"""

import asyncio
import random
import math
from typing import Tuple, List, Dict, Any

from ..core.attack_base import BaseAttack, AttackType

class GPSSpoofing(BaseAttack):
    """GPS 신호 스푸핑 공격"""
    
    def _get_attack_type(self) -> AttackType:
        return AttackType.PROTOCOL_TAMPERING
    
    async def _run_attack(self) -> Tuple[bool, List[str], Dict[str, Any]]:
        """GPS 신호 조작을 통한 위치 정보 변조"""
        await asyncio.sleep(4.2)
        
        # DVD 환경의 실제 GPS 좌표 (시뮬레이션)
        dvd_original_coords = {
            "lat": 37.4419,  # DVD SITL 기본 위치 (Palo Alto)
            "lon": -122.1430,
            "alt": 584.0,    # 미터 단위
            "accuracy": 3.0,
            "satellites": 12,
            "hdop": 1.2,
            "fix_type": "3D_FIX",
            "timestamp": 1703123456
        }
        
        # 다양한 GPS 스푸핑 시나리오들
        spoofing_scenarios = [
            {
                "name": "airport_redirect",
                "target_coords": {
                    "lat": 37.6213,   # SFO Airport
                    "lon": -122.3790,
                    "alt": 4.0
                },
                "description": "Redirect to San Francisco Airport runway",
                "risk_level": "critical",
                "legal_implications": "severe",
                "detection_difficulty": "medium"
            },
            {
                "name": "ocean_crash",
                "target_coords": {
                    "lat": 37.8044,   # Pacific Ocean
                    "lon": -122.4695,
                    "alt": 0.0
                },
                "description": "Force landing in Pacific Ocean",
                "risk_level": "critical",
                "legal_implications": "severe",
                "detection_difficulty": "low"
            },
            {
                "name": "restricted_airspace",
                "target_coords": {
                    "lat": 38.8977,   # Washington DC
                    "lon": -77.0365,
                    "alt": 150.0
                },
                "description": "Redirect to restricted DC airspace",
                "risk_level": "critical",
                "legal_implications": "severe",
                "detection_difficulty": "high"
            },
            {
                "name": "elevation_manipulation",
                "target_coords": {
                    "lat": dvd_original_coords["lat"],
                    "lon": dvd_original_coords["lon"],
                    "alt": -50.0  # Underground
                },
                "description": "Force underground altitude reading",
                "risk_level": "high",
                "legal_implications": "medium",
                "detection_difficulty": "high"
            },
            {
                "name": "gradual_drift",
                "target_coords": {
                    "lat": dvd_original_coords["lat"] + 0.001,
                    "lon": dvd_original_coords["lon"] + 0.001,
                    "alt": dvd_original_coords["alt"] + 10
                },
                "description": "Subtle position drift for covert redirection",
                "risk_level": "medium",
                "legal_implications": "low",
                "detection_difficulty": "very_high"
            },
            {
                "name": "signal_denial",
                "target_coords": None,
                "description": "Complete GPS signal denial/jamming",
                "risk_level": "high",
                "legal_implications": "medium",
                "detection_difficulty": "low"
            }
        ]
        
        # 랜덤하게 스푸핑 시나리오 선택
        active_scenario = random.choice(spoofing_scenarios)
        
        # GPS 스푸핑 방법들
        spoofing_methods = [
            {
                "method": "sdr_based_spoofing",
                "equipment": "HackRF One + GPS-SDR-SIM",
                "success_rate": 0.75,
                "power_required": "10-50W",
                "range": "100-500m",
                "complexity": "high"
            },
            {
                "method": "commercial_spoofer",
                "equipment": "Dedicated GPS Spoofer",
                "success_rate": 0.85,
                "power_required": "20-100W", 
                "range": "200-1000m",
                "complexity": "medium"
            },
            {
                "method": "meaconing_attack",
                "equipment": "Signal Repeater",
                "success_rate": 0.60,
                "power_required": "5-20W",
                "range": "50-200m",
                "complexity": "low"
            },
            {
                "method": "simulation_injection",
                "equipment": "GPS Simulator",
                "success_rate": 0.90,
                "power_required": "1-10W",
                "range": "10-50m",
                "complexity": "very_high"
            }
        ]
        
        chosen_method = random.choice(spoofing_methods)
        
        # 스푸핑 성공 여부 계산
        base_success_rate = chosen_method["success_rate"]
        
        # DVD 환경은 일반적으로 보호되지 않음 (실험 환경)
        dvd_modifier = 1.1  # 10% 보너스
        
        # 시나리오별 난이도 조정
        scenario_modifier = {
            "gradual_drift": 1.2,      # 더 쉬움 (탐지 어려움)
            "elevation_manipulation": 1.0,
            "airport_redirect": 0.9,   # 조금 더 어려움
            "ocean_crash": 0.8,       # 의심스러운 좌표
            "restricted_airspace": 0.7, # 매우 의심스러운 좌표
            "signal_denial": 1.1       # 단순 재밍
        }.get(active_scenario["name"], 1.0)
        
        final_success_rate = base_success_rate * dvd_modifier * scenario_modifier
        success = random.random() < final_success_rate
        
        iocs = []
        attack_details = {}
        
        if success:
            if active_scenario["name"] != "signal_denial":
                # 스푸핑된 GPS 신호 생성
                spoofed_signal = self._generate_spoofed_signal(
                    dvd_original_coords, 
                    active_scenario["target_coords"],
                    chosen_method
                )
                attack_details["spoofed_signal"] = spoofed_signal
                
                # IOC 생성
                iocs.extend([
                    f"GPS_SPOOF:ORIGINAL_{dvd_original_coords['lat']:.6f},{dvd_original_coords['lon']:.6f}",
                    f"GPS_SPOOF:TARGET_{active_scenario['target_coords']['lat']:.6f},{active_scenario['target_coords']['lon']:.6f}",
                    f"GPS_SPOOF:SCENARIO_{active_scenario['name']}",
                    f"GPS_SPOOF:METHOD_{chosen_method['method']}",
                    f"GPS_SPOOF:RISK_{active_scenario['risk_level']}"
                ])
                
                # 거리 기반 IOC
                distance = self._calculate_distance(
                    dvd_original_coords["lat"], dvd_original_coords["lon"],
                    active_scenario["target_coords"]["lat"], active_scenario["target_coords"]["lon"]
                )
                iocs.append(f"GPS_SPOOF:DISTANCE_{distance:.1f}km")
                
                if distance > 100:
                    iocs.append("GPS_SPOOF:LONG_DISTANCE_REDIRECT")
                
                # 고도 변화 IOC
                alt_change = abs(active_scenario["target_coords"]["alt"] - dvd_original_coords["alt"])
                if alt_change > 100:
                    iocs.append("GPS_SPOOF:SIGNIFICANT_ALTITUDE_CHANGE")
                
                if active_scenario["target_coords"]["alt"] < 0:
                    iocs.append("GPS_SPOOF:UNDERGROUND_COORDINATE")
            
            else:
                # 신호 거부 공격
                jamming_details = {
                    "jamming_type": "wideband_noise",
                    "affected_frequencies": ["L1: 1575.42 MHz", "L2: 1227.60 MHz"],
                    "power_level": f"{random.randint(10, 100)}W",
                    "effective_radius": f"{random.randint(100, 1000)}m"
                }
                attack_details["jamming_details"] = jamming_details
                
                iocs.extend([
                    "GPS_JAMMING:SIGNAL_DENIAL",
                    f"GPS_JAMMING:METHOD_{chosen_method['method']}",
                    "GPS_JAMMING:L1_FREQUENCY_BLOCKED",
                    "GPS_JAMMING:L2_FREQUENCY_BLOCKED"
                ])
        
        else:
            # 실패한 경우의 IOC
            iocs.extend([
                f"GPS_SPOOF:FAILED_{active_scenario['name']}",
                f"GPS_SPOOF:METHOD_FAILED_{chosen_method['method']}"
            ])
        
        # 방어 메커니즘 분석
        defense_analysis = self._analyze_gps_defenses(success, chosen_method, active_scenario)
        
        details = {
            "original_coordinates": dvd_original_coords,
            "spoofing_scenario": active_scenario,
            "spoofing_method": chosen_method,
            "attack_details": attack_details,
            "defense_analysis": defense_analysis,
            "success_rate": final_success_rate,
            "dvd_environment": True,
            "legal_warning": "GPS spoofing is illegal in most jurisdictions",
            "countermeasures": [
                "Multi-constellation GNSS (GPS + GLONASS + Galileo)",
                "Inertial Navigation System (INS) backup",
                "GPS signal authentication",
                "Anomaly detection algorithms",
                "Geofencing validation"
            ]
        }
        
        return success, iocs, details
    
    def _generate_spoofed_signal(self, original: Dict, target: Dict, method: Dict) -> Dict[str, Any]:
        """스푸핑된 GPS 신호 생성"""
        return {
            "satellites_used": random.randint(4, 12),
            "signal_strength": random.uniform(-140, -120),  # dBm
            "carrier_noise_ratio": random.uniform(35, 50),  # dB-Hz
            "spoofing_method": method["method"],
            "signal_delay": random.uniform(0.1, 2.0),  # seconds
            "power_level": method["power_required"],
            "frequency_offset": random.uniform(-5, 5),  # Hz
            "code_delay": random.uniform(0, 1023),  # chips
            "doppler_shift": random.uniform(-5000, 5000),  # Hz
            "authenticity_checks_bypassed": [
                "timing_consistency",
                "signal_power_analysis", 
                "carrier_phase_continuity"
            ],
            "trajectory_profile": self._generate_trajectory(original, target)
        }
    
    def _generate_trajectory(self, start: Dict, end: Dict) -> List[Dict]:
        """스푸핑 궤적 생성"""
        if end is None:  # 신호 거부의 경우
            return []
        
        trajectory = []
        steps = random.randint(10, 20)
        
        for i in range(steps + 1):
            progress = i / steps
            lat = start["lat"] + (end["lat"] - start["lat"]) * progress
            lon = start["lon"] + (end["lon"] - start["lon"]) * progress
            alt = start["alt"] + (end["alt"] - start["alt"]) * progress
            
            # 노이즈 추가 (현실적인 GPS 오차)
            lat += random.uniform(-0.00001, 0.00001)
            lon += random.uniform(-0.00001, 0.00001)
            alt += random.uniform(-1, 1)
            
            trajectory.append({
                "step": i,
                "lat": lat,
                "lon": lon,
                "alt": alt,
                "timestamp": start["timestamp"] + i * 2  # 2초 간격
            })
        
        return trajectory
    
    def _calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """두 GPS 좌표 간 거리 계산 (km)"""
        R = 6371  # 지구 반지름 (km)
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)
        
        a = (math.sin(delta_lat/2) * math.sin(delta_lat/2) +
             math.cos(lat1_rad) * math.cos(lat2_rad) *
             math.sin(delta_lon/2) * math.sin(delta_lon/2))
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c
    
    def _analyze_gps_defenses(self, attack_success: bool, method: Dict, scenario: Dict) -> Dict[str, Any]:
        """GPS 방어 메커니즘 분석"""
        defenses = {
            "anti_spoofing_enabled": random.choice([True, False]),
            "ins_backup_available": random.choice([True, False]),
            "multi_constellation": random.choice([True, False]),
            "signal_monitoring": random.choice([True, False]),
            "geofencing_active": random.choice([True, False])
        }
        
        effectiveness = {
            "detection_probability": 0.0,
            "mitigation_capability": "none",
            "alert_generated": False
        }
        
        if not attack_success:
            # 실패 원인 분석
            if defenses["anti_spoofing_enabled"]:
                effectiveness["detection_probability"] += 0.4
                effectiveness["mitigation_capability"] = "high"
            
            if defenses["signal_monitoring"]:
                effectiveness["detection_probability"] += 0.3
            
            if defenses["multi_constellation"]:
                effectiveness["detection_probability"] += 0.2
            
            effectiveness["alert_generated"] = effectiveness["detection_probability"] > 0.5
        
        else:
            # 성공했지만 탐지 가능성
            if scenario["detection_difficulty"] == "low":
                effectiveness["detection_probability"] = random.uniform(0.6, 0.9)
            elif scenario["detection_difficulty"] == "medium":
                effectiveness["detection_probability"] = random.uniform(0.3, 0.6)
            elif scenario["detection_difficulty"] == "high":
                effectiveness["detection_probability"] = random.uniform(0.1, 0.3)
            else:  # very_high
                effectiveness["detection_probability"] = random.uniform(0.0, 0.1)
            
            effectiveness["alert_generated"] = (
                effectiveness["detection_probability"] > 0.4 and 
                random.random() > 0.3
            )
        
        return {
            "active_defenses": defenses,
            "effectiveness": effectiveness,
            "recommended_improvements": [
                "Enable GPS/GNSS anti-spoofing",
                "Implement multi-constellation receiver",
                "Deploy INS backup system",
                "Add signal quality monitoring",
                "Configure geofencing boundaries"
            ]
        }